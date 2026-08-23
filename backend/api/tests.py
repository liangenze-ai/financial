import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from django.test import RequestFactory, SimpleTestCase

from api.services.quant_baseline import (
    BOOLEAN_FEATURES,
    FEATURE_COLUMNS,
    QuantBaselinePreprocessor,
    _diagnostic_feature_rows,
    _passes_baseline,
    _missing_rates,
    _time_decay_weights,
    evaluate_split,
    rank_ic_by_date,
    selected_feature_columns,
    split_for_date,
    train_quant_baseline,
)
from api.views import quant_stock_diagnosis


class QuantBaselineTests(SimpleTestCase):
    def test_split_for_date_uses_expected_non_overlapping_windows(self):
        self.assertEqual(split_for_date('20140403'), 'train')
        self.assertEqual(split_for_date('20211231'), 'train')
        self.assertEqual(split_for_date('20220101'), 'validation')
        self.assertEqual(split_for_date('20231231'), 'validation')
        self.assertEqual(split_for_date('20240101'), 'test')
        self.assertEqual(split_for_date('20251231'), 'test')
        self.assertEqual(split_for_date('20260101'), 'rolling_2026')
        self.assertEqual(split_for_date('20260428'), 'rolling_2026')
        self.assertIsNone(split_for_date('20260429'))

    def test_preprocessor_fits_train_bounds_and_transforms_missing_extremes_and_booleans(self):
        train = self._frame_for_preprocessor([1.0, 2.0, 3.0, 4.0])
        preprocessor = QuantBaselinePreprocessor(FEATURE_COLUMNS, BOOLEAN_FEATURES).fit(train)

        validation = self._frame_for_preprocessor([None, 9999.0])
        validation['is_limit_up'] = [None, True]
        transformed = preprocessor.transform(validation)

        self.assertEqual(transformed.shape, (2, len(FEATURE_COLUMNS)))
        self.assertFalse(np.isnan(transformed).any())
        self.assertLessEqual(preprocessor.upper_bounds['ret_5'], 9999.0)

    def test_rank_ic_by_date_returns_average_spearman_correlation(self):
        frame = pd.DataFrame(
            {
                'trade_date': ['20240102', '20240102', '20240102', '20240103', '20240103', '20240103'],
                'score': [0.1, 0.2, 0.3, 0.9, 0.8, 0.7],
                'future_ret_20': [1.0, 2.0, 3.0, 3.0, 2.0, 1.0],
            }
        )

        self.assertAlmostEqual(rank_ic_by_date(frame, 'score', 'future_ret_20'), 1.0)

    def test_missing_rates_are_reported_by_split_and_year(self):
        frame = self._training_frame(rows_per_split=4)
        frame.loc[frame.index[0], 'ret_5'] = None

        rows = _missing_rates(frame)

        self.assertTrue(any(row['scope'] == 'split' and row['feature'] == 'ret_5' for row in rows))
        self.assertTrue(any(row['scope'] == 'year' and row['feature'] == 'ret_5' for row in rows))

    def test_selected_feature_columns_can_exclude_limit_flags(self):
        features = selected_feature_columns(
            exclude_limit_flags=True,
            exclude_features=['hk_hold_ratio'],
        )

        self.assertNotIn('is_limit_up', features)
        self.assertNotIn('is_limit_down', features)
        self.assertNotIn('hk_hold_ratio', features)
        self.assertIn('ret_5', features)

    def test_preprocessor_can_rank_numeric_features_by_trade_date(self):
        frame = self._frame_for_preprocessor([10.0, 20.0, 30.0, 40.0])
        frame['trade_date'] = ['20240102', '20240102', '20240103', '20240103']
        frame['is_limit_up'] = [False, True, False, True]

        preprocessor = QuantBaselinePreprocessor(
            FEATURE_COLUMNS,
            BOOLEAN_FEATURES,
            rank_features_by_date=True,
        ).fit(frame)
        numeric = preprocessor._numeric_frame(frame)

        self.assertAlmostEqual(numeric.loc[0, 'ret_5'], 0.0)
        self.assertAlmostEqual(numeric.loc[1, 'ret_5'], 0.5)
        self.assertAlmostEqual(numeric.loc[2, 'ret_5'], 0.0)
        self.assertAlmostEqual(numeric.loc[3, 'ret_5'], 0.5)
        self.assertEqual(numeric.loc[1, 'is_limit_up'], 1.0)

    def test_preprocessor_can_neutralize_numeric_features_by_industry_and_size(self):
        frame = self._frame_for_preprocessor([1.0, 3.0, 10.0, 14.0])
        frame['trade_date'] = ['20240102', '20240102', '20240102', '20240102']
        frame['industry'] = ['bank', 'bank', 'tech', 'tech']
        frame['total_mv'] = [100.0, 200.0, 100.0, 200.0]
        frame['ret_5'] = [1.0, 3.0, 10.0, 14.0]
        frame['is_limit_up'] = [False, True, False, True]

        preprocessor = QuantBaselinePreprocessor(
            FEATURE_COLUMNS,
            BOOLEAN_FEATURES,
            neutralize_by_industry_size=True,
        ).fit(frame)
        numeric = preprocessor._numeric_frame(frame)

        self.assertAlmostEqual(float(numeric.groupby(frame['industry'])['ret_5'].mean().abs().max()), 0.0)
        size = np.log1p(pd.Series(frame['total_mv']))
        self.assertAlmostEqual(float((numeric['ret_5'] * (size - size.mean())).sum()), 0.0)
        self.assertEqual(numeric.loc[1, 'is_limit_up'], 1.0)

    def test_baseline_pass_requires_rolling_2026_not_reversed(self):
        good_split = {
            'auc': 0.55,
            'all_future_excess_ret_20_mean': 0.01,
            'top_decile_future_excess_ret_20_mean': 0.03,
            'bottom_decile_future_excess_ret_20_mean': -0.01,
            'rank_ic_excess_mean': 0.03,
        }
        reversed_rolling = {
            'auc': 0.51,
            'all_future_excess_ret_20_mean': -0.01,
            'top_decile_future_excess_ret_20_mean': -0.02,
            'bottom_decile_future_excess_ret_20_mean': 0.01,
            'rank_ic_excess_mean': -0.01,
        }

        self.assertFalse(
            _passes_baseline(
                {
                    'validation': good_split,
                    'test': good_split,
                    'rolling_2026': reversed_rolling,
                }
            )
        )

    def test_time_decay_weights_prioritize_recent_train_rows(self):
        frame = pd.DataFrame({'trade_date': ['20200102', '20210104', '20211231']})

        weights = _time_decay_weights(frame, half_life_days=365)

        self.assertLess(weights[0], weights[1])
        self.assertLess(weights[1], weights[2])
        self.assertAlmostEqual(float(np.mean(weights)), 1.0)

    def test_diagnostic_feature_rows_sort_by_top_bottom_gap(self):
        frame = pd.DataFrame(
            {
                'cohort': ['top', 'top', 'bottom', 'bottom'],
                'ret_5': [10.0, 12.0, 1.0, 2.0],
                'pb': [1.0, 1.1, 1.2, 1.3],
            }
        )

        rows = _diagnostic_feature_rows(frame, ['ret_5', 'pb'])

        self.assertEqual(rows[0]['feature'], 'ret_5')
        self.assertAlmostEqual(rows[0]['top_minus_bottom_mean'], 9.5)

    def test_evaluate_split_returns_required_metric_keys(self):
        frame = self._training_frame()
        train_frame = frame[frame['split'] == 'train']
        preprocessor = QuantBaselinePreprocessor(FEATURE_COLUMNS, BOOLEAN_FEATURES).fit(train_frame)

        from sklearn.linear_model import LogisticRegression

        model = LogisticRegression(penalty='elasticnet', solver='saga', l1_ratio=0.5, max_iter=200, random_state=42)
        model.fit(preprocessor.transform(train_frame), train_frame['label_up_20'].astype(int))

        metrics = evaluate_split(model, preprocessor, frame[frame['split'] == 'validation'], 'label_up_20')

        self.assertIn('auc', metrics)
        self.assertIn('log_loss', metrics)
        self.assertIn('brier', metrics)
        self.assertIn('top_decile_future_excess_ret_20_mean', metrics)
        self.assertIn('rank_ic_mean', metrics)

    def test_train_quant_baseline_can_train_both_targets_with_fake_data(self):
        fake_frame = self._training_frame(rows_per_split=24)

        with tempfile.TemporaryDirectory() as output_dir:
            with self.settings(BASE_DIR='.'):
                from api.services import quant_baseline

                original_loader = quant_baseline.load_training_frame
                quant_baseline.load_training_frame = lambda **kwargs: fake_frame.copy()
                try:
                    result = train_quant_baseline(output_dir=output_dir, max_rows_per_split=10)
                finally:
                    quant_baseline.load_training_frame = original_loader

            self.assertIn('up', result['metrics']['targets'])
            self.assertIn('outperform', result['metrics']['targets'])
            self.assertTrue((pd.read_csv(f'{output_dir}/feature_coefficients.csv')).shape[0] > 0)

    def test_calibrate_quant_baseline_writes_calibrated_artifacts(self):
        from api.services import quant_baseline

        fake_frame = self._training_frame(rows_per_split=16)
        scores = np.linspace(0.1, 0.9, len(fake_frame))
        payload = self._payload_with_scores(scores)
        original_loader = quant_baseline.load_training_frame
        original_payload_loader = quant_baseline._load_target_payload
        original_dump = quant_baseline.joblib.dump
        quant_baseline.load_training_frame = lambda **kwargs: fake_frame.copy()
        quant_baseline._load_target_payload = lambda artifacts_dir, target_name: payload
        quant_baseline.joblib.dump = lambda payload, path: Path(path).write_bytes(b'joblib-placeholder')
        try:
            with tempfile.TemporaryDirectory() as output_dir:
                result = quant_baseline.calibrate_quant_baseline(
                    artifacts_dir='source',
                    output_dir=output_dir,
                    max_rows_per_split=16,
                )
                self.assertTrue(Path(output_dir, 'up_model.joblib').exists())
                self.assertTrue(Path(output_dir, 'outperform_model.joblib').exists())
                self.assertTrue(Path(output_dir, 'calibration_metrics.json').exists())
                self.assertTrue(Path(output_dir, 'calibration_bins.csv').exists())
        finally:
            quant_baseline.load_training_frame = original_loader
            quant_baseline._load_target_payload = original_payload_loader
            quant_baseline.joblib.dump = original_dump

        self.assertEqual(result['metrics']['method'], 'sigmoid')
        self.assertIn('calibrated', result['metrics']['targets']['up'])

    def test_paper_trade_quant_strategy_writes_tracking_reports(self):
        from api.services import quant_baseline

        fake_frame = self._training_frame(rows_per_split=16)
        scores = np.linspace(0.1, 0.9, len(fake_frame))
        payload = self._payload_with_scores(scores)
        original_loader = quant_baseline.load_training_frame
        original_payload_loader = quant_baseline._load_target_payload
        quant_baseline.load_training_frame = lambda **kwargs: fake_frame.copy()
        quant_baseline._load_target_payload = lambda artifacts_dir, target_name: payload
        try:
            with tempfile.TemporaryDirectory() as output_dir:
                result = quant_baseline.paper_trade_quant_strategy(
                    artifacts_dir='source',
                    target_name='up',
                    output_dir=output_dir,
                    max_rows_per_split=16,
                    top_quantile=0.25,
                )
                self.assertTrue(Path(result['report_path']).exists())
                self.assertTrue(Path(result['daily_path']).exists())
                self.assertTrue(Path(result['month_path']).exists())
        finally:
            quant_baseline.load_training_frame = original_loader
            quant_baseline._load_target_payload = original_payload_loader

        self.assertEqual(result['summary']['target'], 'up')
        self.assertTrue(result['summary']['by_split'])

    def test_evaluate_quant_regime_blend_switches_selected_months(self):
        from api.services import quant_baseline

        fake_frame = self._training_frame(rows_per_split=4)
        fake_frame.loc[fake_frame['split'] == 'validation', 'trade_date'] = '20260401'
        scores = np.linspace(0.1, 0.9, len(fake_frame))
        primary_payload = self._payload_with_scores(scores)
        fallback_payload = self._payload_with_scores(1.0 - scores)
        original_loader = quant_baseline.load_training_frame
        original_payload_loader = quant_baseline._load_target_payload
        quant_baseline.load_training_frame = lambda **kwargs: fake_frame.copy()
        quant_baseline._load_target_payload = (
            lambda artifacts_dir, target_name: fallback_payload
            if 'fallback' in str(artifacts_dir)
            else primary_payload
        )
        try:
            with tempfile.TemporaryDirectory() as output_dir:
                result = quant_baseline.evaluate_quant_regime_blend(
                    primary_artifacts_dir='primary',
                    fallback_artifacts_dir='fallback',
                    switch_months=['202604'],
                    output_dir=output_dir,
                )
        finally:
            quant_baseline.load_training_frame = original_loader
            quant_baseline._load_target_payload = original_payload_loader

        report = result['report']
        self.assertEqual(report['fallback_rows'], 4)
        self.assertIn('validation', report['by_split'])
        self.assertTrue(result['report_path'].endswith('regime_blend_up_202604.json'))

    def test_evaluate_quant_regime_blend_can_auto_switch_on_weak_ma60(self):
        from api.services import quant_baseline

        fake_frame = self._training_frame(rows_per_split=4)
        fake_frame.loc[fake_frame['split'] == 'validation', 'trade_date'] = '20260401'
        fake_frame['ma60_bias'] = 0.02
        fake_frame.loc[fake_frame['trade_date'] == '20260401', 'ma60_bias'] = -0.08
        scores = np.linspace(0.1, 0.9, len(fake_frame))
        primary_payload = self._payload_with_scores(scores)
        fallback_payload = self._payload_with_scores(1.0 - scores)
        original_loader = quant_baseline.load_training_frame
        original_payload_loader = quant_baseline._load_target_payload
        quant_baseline.load_training_frame = lambda **kwargs: fake_frame.copy()
        quant_baseline._load_target_payload = (
            lambda artifacts_dir, target_name: fallback_payload
            if 'fallback' in str(artifacts_dir)
            else primary_payload
        )
        try:
            with tempfile.TemporaryDirectory() as output_dir:
                result = quant_baseline.evaluate_quant_regime_blend(
                    primary_artifacts_dir='primary',
                    fallback_artifacts_dir='fallback',
                    switch_months=[],
                    auto_switch_rule='weak_ma60',
                    ma60_bias_threshold=-0.04,
                    output_dir=output_dir,
                )
        finally:
            quant_baseline.load_training_frame = original_loader
            quant_baseline._load_target_payload = original_payload_loader

        report = result['report']
        self.assertEqual(report['switch_months'], ['202604'])
        self.assertEqual(report['fallback_rows'], 4)

    def test_evaluate_quant_regime_blend_can_auto_switch_on_rebound_after_weakness(self):
        from api.services import quant_baseline

        fake_frame = self._training_frame(rows_per_split=4)
        fake_frame.loc[fake_frame['split'] == 'validation', 'trade_date'] = '20260401'
        fake_frame.loc[fake_frame['split'] == 'test', 'trade_date'] = '20240801'
        fake_frame.loc[fake_frame['split'] == 'rolling_2026', 'trade_date'] = '20240701'
        fake_frame['ma60_bias'] = 0.02
        fake_frame['ret_20'] = 0.01
        fake_frame.loc[fake_frame['trade_date'] == '20260401', 'ma60_bias'] = -0.08
        fake_frame.loc[fake_frame['trade_date'] == '20260401', 'ret_20'] = -0.03
        fake_frame.loc[fake_frame['trade_date'] == '20240801', 'ma60_bias'] = -0.08
        fake_frame.loc[fake_frame['trade_date'] == '20240801', 'ret_20'] = -0.015
        fake_frame.loc[fake_frame['trade_date'] == '20240701', 'ma60_bias'] = -0.09
        fake_frame.loc[fake_frame['trade_date'] == '20240701', 'ret_20'] = -0.03
        scores = np.linspace(0.1, 0.9, len(fake_frame))
        primary_payload = self._payload_with_scores(scores)
        fallback_payload = self._payload_with_scores(1.0 - scores)
        original_loader = quant_baseline.load_training_frame
        original_payload_loader = quant_baseline._load_target_payload
        quant_baseline.load_training_frame = lambda **kwargs: fake_frame.copy()
        quant_baseline._load_target_payload = (
            lambda artifacts_dir, target_name: fallback_payload
            if 'fallback' in str(artifacts_dir)
            else primary_payload
        )
        try:
            with tempfile.TemporaryDirectory() as output_dir:
                result = quant_baseline.evaluate_quant_regime_blend(
                    primary_artifacts_dir='primary',
                    fallback_artifacts_dir='fallback',
                    switch_months=[],
                    auto_switch_rule='rebound_after_weakness',
                    ma60_bias_threshold=-0.04,
                    ma60_bias_floor=-0.085,
                    ret20_rebound_threshold=-0.04,
                    ret20_rebound_ceiling=-0.02,
                    output_dir=output_dir,
                )
        finally:
            quant_baseline.load_training_frame = original_loader
            quant_baseline._load_target_payload = original_payload_loader

        report = result['report']
        self.assertEqual(report['switch_months'], ['202604'])
        self.assertEqual(report['fallback_rows'], 4)

    def test_evaluate_quant_regime_blend_can_use_database_auto_switch_source(self):
        from api.services import quant_baseline

        fake_frame = self._training_frame(rows_per_split=4)
        fake_frame.loc[fake_frame['split'] == 'validation', 'trade_date'] = '20260401'
        scores = np.linspace(0.1, 0.9, len(fake_frame))
        primary_payload = self._payload_with_scores(scores)
        fallback_payload = self._payload_with_scores(1.0 - scores)
        original_loader = quant_baseline.load_training_frame
        original_payload_loader = quant_baseline._load_target_payload
        original_auto_switch = quant_baseline._auto_switch_months_from_database
        quant_baseline.load_training_frame = lambda **kwargs: fake_frame.copy()
        quant_baseline._load_target_payload = (
            lambda artifacts_dir, target_name: fallback_payload
            if 'fallback' in str(artifacts_dir)
            else primary_payload
        )
        quant_baseline._auto_switch_months_from_database = lambda **kwargs: (
            ['202604'],
            [
                {
                    'month': '202604',
                    'rows': 100,
                    'ma60_bias_median': -0.045,
                    'ret_20_median': -0.02,
                    'use_fallback': True,
                }
            ],
        )
        try:
            with tempfile.TemporaryDirectory() as output_dir:
                result = quant_baseline.evaluate_quant_regime_blend(
                    primary_artifacts_dir='primary',
                    fallback_artifacts_dir='fallback',
                    switch_months=[],
                    auto_switch_rule='rebound_after_weakness',
                    auto_switch_source='database',
                    output_dir=output_dir,
                )
        finally:
            quant_baseline.load_training_frame = original_loader
            quant_baseline._load_target_payload = original_payload_loader
            quant_baseline._auto_switch_months_from_database = original_auto_switch

        report = result['report']
        self.assertEqual(report['auto_switch_source'], 'database')
        self.assertEqual(report['switch_months'], ['202604'])
        self.assertEqual(report['fallback_rows'], 4)

    def test_diagnose_quant_baseline_slice_can_use_fallback_for_switch_month(self):
        from api.services import quant_baseline

        fake_frame = self._training_frame(rows_per_split=8)
        fake_frame = fake_frame[fake_frame['split'] == 'validation'].copy()
        fake_frame['trade_date'] = '20260401'
        fake_frame['stock_name'] = fake_frame['ts_code']
        fake_frame['industry'] = 'test_industry'
        scores = np.linspace(0.1, 0.9, len(fake_frame))
        primary_payload = self._payload_with_scores(scores)
        fallback_payload = self._payload_with_scores(1.0 - scores)
        original_loader = quant_baseline.load_diagnostic_slice_frame
        original_joblib_load = quant_baseline.joblib.load
        quant_baseline.load_diagnostic_slice_frame = lambda **kwargs: fake_frame.copy()

        with tempfile.TemporaryDirectory() as primary_dir, tempfile.TemporaryDirectory() as fallback_dir:
            Path(primary_dir, 'up_model.joblib').touch()
            Path(fallback_dir, 'up_model.joblib').touch()
            quant_baseline.joblib.load = (
                lambda path: fallback_payload
                if Path(path).parent == Path(fallback_dir)
                else primary_payload
            )
            try:
                result = quant_baseline.diagnose_quant_baseline_slice(
                    artifacts_dir=primary_dir,
                    fallback_artifacts_dir=fallback_dir,
                    switch_months=['202604'],
                    month='202604',
                    target_name='up',
                )
            finally:
                quant_baseline.load_diagnostic_slice_frame = original_loader
                quant_baseline.joblib.load = original_joblib_load

        summary = result['summary']
        self.assertEqual(summary['model_role'], 'fallback')
        self.assertTrue(summary['use_fallback'])
        self.assertEqual(summary['switch_months'], ['202604'])

    def test_diagnose_quant_stock_reports_fallback_score_for_switch_month(self):
        from api.services import quant_baseline

        fake_frame = self._training_frame(rows_per_split=8)
        fake_frame = fake_frame[fake_frame['split'] == 'validation'].copy()
        fake_frame['trade_date'] = '20260401'
        fake_frame['stock_name'] = fake_frame['ts_code']
        fake_frame['industry'] = 'test_industry'
        target_code = fake_frame.iloc[0]['ts_code']
        scores = np.linspace(0.1, 0.9, len(fake_frame))
        primary_payload = self._payload_with_scores(scores)
        fallback_payload = self._payload_with_scores(1.0 - scores)
        original_loader = quant_baseline.load_stock_diagnostic_frame
        original_joblib_load = quant_baseline.joblib.load
        quant_baseline.load_stock_diagnostic_frame = lambda **kwargs: fake_frame.copy()

        with tempfile.TemporaryDirectory() as primary_dir, tempfile.TemporaryDirectory() as fallback_dir:
            Path(primary_dir, 'up_model.joblib').touch()
            Path(fallback_dir, 'up_model.joblib').touch()
            quant_baseline.joblib.load = (
                lambda path: fallback_payload
                if Path(path).parent == Path(fallback_dir)
                else primary_payload
            )
            try:
                result = quant_baseline.diagnose_quant_stock(
                    ts_code=target_code,
                    trade_date='20260401',
                    artifacts_dir=primary_dir,
                    fallback_artifacts_dir=fallback_dir,
                    switch_months=['202604'],
                    target_name='up',
                )
                report_exists = Path(result['report_path']).exists()
            finally:
                quant_baseline.load_stock_diagnostic_frame = original_loader
                quant_baseline.joblib.load = original_joblib_load

        summary = result['summary']
        self.assertEqual(summary['model_role'], 'fallback')
        self.assertTrue(summary['use_fallback'])
        self.assertEqual(summary['cohort'], 'top')
        self.assertTrue(report_exists)

    def test_diagnose_quant_stock_combined_reports_target_alignment(self):
        from api.services import quant_baseline

        fake_frame = self._training_frame(rows_per_split=8)
        fake_frame = fake_frame[fake_frame['split'] == 'validation'].copy()
        fake_frame['trade_date'] = '20260401'
        fake_frame['stock_name'] = fake_frame['ts_code']
        fake_frame['industry'] = 'test_industry'
        target_code = fake_frame.iloc[-1]['ts_code']
        scores = np.linspace(0.1, 0.9, len(fake_frame))
        payload = self._payload_with_scores(scores)
        original_loader = quant_baseline.load_stock_diagnostic_frame
        original_joblib_load = quant_baseline.joblib.load
        quant_baseline.load_stock_diagnostic_frame = lambda **kwargs: fake_frame.copy()

        with tempfile.TemporaryDirectory() as primary_dir:
            Path(primary_dir, 'up_model.joblib').touch()
            Path(primary_dir, 'outperform_model.joblib').touch()
            quant_baseline.joblib.load = lambda path: payload
            try:
                result = quant_baseline.diagnose_quant_stock_combined(
                    ts_code=target_code,
                    trade_date='20260401',
                    artifacts_dir=primary_dir,
                )
                report_exists = Path(result['report_path']).exists()
            finally:
                quant_baseline.load_stock_diagnostic_frame = original_loader
                quant_baseline.joblib.load = original_joblib_load

        summary = result['summary']
        self.assertEqual(summary['combined_signal']['label'], 'strong_positive')
        self.assertEqual(summary['targets']['up']['cohort'], 'top')
        self.assertEqual(summary['targets']['outperform']['cohort'], 'top')
        self.assertTrue(report_exists)

    def test_quant_stock_diagnosis_api_returns_combined_summary(self):
        from api import views

        original = views.diagnose_quant_stock_combined
        views.diagnose_quant_stock_combined = lambda **kwargs: {
            'summary': {
                'ts_code': kwargs['ts_code'],
                'trade_date': kwargs['trade_date'],
                'combined_signal': {'label': 'strong_positive'},
                'targets': {},
                'warnings': [],
            }
        }
        try:
            request = RequestFactory().get(
                '/api/quant/stock-diagnosis/',
                {'ts_code': '001390.SZ', 'trade_date': '20260401'},
            )
            response = quant_stock_diagnosis(request)
        finally:
            views.diagnose_quant_stock_combined = original

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'strong_positive', response.content)

    def test_quant_stock_diagnosis_api_requires_query_params(self):
        response = quant_stock_diagnosis(RequestFactory().get('/api/quant/stock-diagnosis/'))

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'ts_code is required', response.content)

    def test_quant_stock_diagnosis_api_maps_missing_sample_to_404(self):
        from api import views

        original = views.diagnose_quant_stock_combined
        views.diagnose_quant_stock_combined = lambda **kwargs: (_ for _ in ()).throw(
            ValueError('No diagnostic rows found for feature_version=v1, trade_date=20260401.')
        )
        try:
            request = RequestFactory().get(
                '/api/quant/stock-diagnosis/',
                {'ts_code': '001390.SZ', 'trade_date': '20260401'},
            )
            response = quant_stock_diagnosis(request)
        finally:
            views.diagnose_quant_stock_combined = original

        self.assertEqual(response.status_code, 404)

    def test_quant_stock_diagnosis_api_can_return_single_target(self):
        from api import views

        original = views.diagnose_quant_stock
        views.diagnose_quant_stock = lambda **kwargs: {
            'summary': {
                'ts_code': kwargs['ts_code'],
                'trade_date': kwargs['trade_date'],
                'target': kwargs['target_name'],
                'score_decile': 10,
            }
        }
        try:
            request = RequestFactory().get(
                '/api/quant/stock-diagnosis/',
                {'ts_code': '001390.SZ', 'trade_date': '20260401', 'target': 'up'},
            )
            response = quant_stock_diagnosis(request)
        finally:
            views.diagnose_quant_stock = original

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"target": "up"', response.content)

    def _frame_for_preprocessor(self, values):
        frame = pd.DataFrame({feature: values for feature in FEATURE_COLUMNS})
        for feature in BOOLEAN_FEATURES:
            frame[feature] = [False for _ in values]
        return frame

    def _training_frame(self, rows_per_split=16):
        rows = []
        split_dates = {
            'train': '20200102',
            'validation': '20220104',
            'test': '20240102',
            'rolling_2026': '20260105',
        }
        for split_name, trade_date in split_dates.items():
            for index in range(rows_per_split):
                signal = index % 2
                row = {
                    'ts_code': f'{index:06d}.SZ',
                    'trade_date': trade_date,
                    'split': split_name,
                    'future_ret_20': 0.05 if signal else -0.03,
                    'future_excess_ret_20': 0.03 if signal else -0.02,
                    'label_up_20': bool(signal),
                    'label_outperform_20': bool((index + (split_name == 'test')) % 2),
                }
                for feature_index, feature in enumerate(FEATURE_COLUMNS):
                    row[feature] = float(index + feature_index / 100.0)
                row['is_limit_up'] = bool(index % 3 == 0)
                row['is_limit_down'] = bool(index % 5 == 0)
                rows.append(row)
        return pd.DataFrame(rows)

    def _payload_with_scores(self, scores):
        class FakePreprocessor:
            def transform(self, frame):
                return np.zeros((len(frame), 1))

        class FakeModel:
            def __init__(self, probabilities):
                self.probabilities = probabilities

            def predict_proba(self, values):
                probabilities = self.probabilities[: len(values)]
                return np.column_stack([1.0 - probabilities, probabilities])

        return {
            'model': FakeModel(np.array(scores)),
            'preprocessor': FakePreprocessor(),
            'feature_columns': FEATURE_COLUMNS,
        }
