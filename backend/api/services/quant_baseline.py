import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.db import connection
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import StandardScaler


FEATURE_GROUPS = {
    'momentum': [
        'ret_5',
        'ret_20',
        'ret_60',
        'ma20_bias',
        'ma60_bias',
        'vol_20',
        'amount_ratio_20',
    ],
    'valuation': [
        'pe_ttm',
        'pb',
        'ps_ttm',
        'dv_ttm',
        'total_mv',
        'circ_mv',
    ],
    'quality_growth': [
        'roe',
        'roa',
        'grossprofit_margin',
        'netprofit_margin',
        'debt_to_assets',
        'ocf_to_profit',
        'revenue_yoy',
        'netprofit_yoy',
    ],
    'capital_risk': [
        'net_mf_amount_ratio',
        'margin_buy_ratio',
        'hk_hold_ratio',
        'pledge_ratio',
        'is_limit_up',
        'is_limit_down',
    ],
}

FEATURE_COLUMNS = [column for columns in FEATURE_GROUPS.values() for column in columns]
BOOLEAN_FEATURES = {'is_limit_up', 'is_limit_down'}
LIMIT_FLAG_FEATURES = {'is_limit_up', 'is_limit_down'}
SIZE_FEATURES = {'total_mv', 'circ_mv'}
NEUTRALIZATION_METADATA_COLUMNS = ['industry', 'total_mv']
DIAGNOSTIC_METADATA_COLUMNS = ['stock_name', 'industry', 'days_since_list', 'total_mv', 'circ_mv']
CORE_REQUIRED_COLUMNS = [
    'close',
    'amount',
    'ret_5',
    'ret_20',
    'ret_60',
    'future_ret_20',
    'future_excess_ret_20',
]
OBSERVATION_REQUIRED_COLUMNS = [
    'close',
    'amount',
    'ret_5',
    'ret_20',
    'ret_60',
]
TARGETS = {
    'up': {
        'column': 'label_up_20',
        'model_file': 'up_model.joblib',
        'description': 'future 20 trading day positive return probability',
    },
    'outperform': {
        'column': 'label_outperform_20',
        'model_file': 'outperform_model.joblib',
        'description': 'future 20 trading day benchmark outperformance probability',
    },
}
SPLITS = {
    'train': ('20140403', '20211231'),
    'validation': ('20220101', '20231231'),
    'test': ('20240101', '20251231'),
    'rolling_2026': ('20260101', '20260428'),
}


def default_output_dir():
    return settings.BASE_DIR / 'artifacts' / 'quant_baseline_v1'


def split_for_date(trade_date):
    for name, (start_date, end_date) in SPLITS.items():
        if start_date <= str(trade_date) <= end_date:
            return name
    return None


def feature_group(feature):
    for group, columns in FEATURE_GROUPS.items():
        if feature in columns:
            return group
    return 'unknown'


def selected_feature_columns(exclude_limit_flags=False, exclude_features=None):
    excluded = set(exclude_features or [])
    if exclude_limit_flags:
        excluded.update(LIMIT_FLAG_FEATURES)
    return [feature for feature in FEATURE_COLUMNS if feature not in excluded]


def _selected_metadata_columns(feature_columns, metadata_columns=None):
    feature_set = set(feature_columns or [])
    return [column for column in (metadata_columns or []) if column not in feature_set]


@dataclass
class QuantBaselinePreprocessor:
    feature_columns: list
    boolean_features: set
    rank_features_by_date: bool = False
    neutralize_by_industry_size: bool = False
    medians: Optional[pd.Series] = None
    lower_bounds: Optional[pd.Series] = None
    upper_bounds: Optional[pd.Series] = None
    scaler: Optional[StandardScaler] = None

    def fit(self, frame):
        clean = self._numeric_frame(frame)
        self.medians = clean.median(numeric_only=True).fillna(0.0)
        filled = clean.fillna(self.medians)
        self.lower_bounds = filled.quantile(0.01).fillna(self.medians)
        self.upper_bounds = filled.quantile(0.99).fillna(self.medians)
        clipped = filled.clip(lower=self.lower_bounds, upper=self.upper_bounds, axis=1)
        self.scaler = StandardScaler()
        self.scaler.fit(clipped)
        return self

    def transform(self, frame):
        if self.medians is None or self.lower_bounds is None or self.upper_bounds is None or self.scaler is None:
            raise ValueError('QuantBaselinePreprocessor must be fitted before transform.')

        clean = self._numeric_frame(frame)
        filled = clean.fillna(self.medians)
        clipped = filled.clip(lower=self.lower_bounds, upper=self.upper_bounds, axis=1)
        return self.scaler.transform(clipped)

    def _numeric_frame(self, frame):
        clean = frame.reindex(columns=self.feature_columns).copy()
        for column in self.boolean_features:
            if column in clean:
                clean[column] = clean[column].fillna(False).astype(float)
        clean = clean.apply(pd.to_numeric, errors='coerce')
        clean = clean.replace([np.inf, -np.inf], np.nan)
        if self.neutralize_by_industry_size:
            clean = _neutralize_frame_by_date_industry_size(clean, frame, self.feature_columns, self.boolean_features)
        if self.rank_features_by_date:
            if 'trade_date' not in frame:
                raise ValueError('trade_date is required when rank_features_by_date is enabled.')
            ranked_columns = [column for column in self.feature_columns if column not in self.boolean_features]
            clean[ranked_columns] = clean[ranked_columns].groupby(frame['trade_date']).rank(method='average', pct=True) - 0.5
        return clean


def _neutralize_frame_by_date_industry_size(clean, frame, feature_columns, boolean_features):
    if 'trade_date' not in frame:
        raise ValueError('trade_date is required when neutralize_by_industry_size is enabled.')
    if 'industry' not in frame:
        raise ValueError('industry is required when neutralize_by_industry_size is enabled.')
    if 'total_mv' not in frame:
        raise ValueError('total_mv is required when neutralize_by_industry_size is enabled.')

    neutralized = clean.copy()
    numeric_columns = [column for column in feature_columns if column not in boolean_features and column not in SIZE_FEATURES]
    if not numeric_columns:
        return neutralized

    metadata = pd.DataFrame(
        {
            'trade_date': frame['trade_date'].astype(str),
            'industry': frame['industry'].fillna('__missing__').astype(str),
            'log_total_mv': pd.to_numeric(frame['total_mv'], errors='coerce'),
        },
        index=frame.index,
    )
    metadata['log_total_mv'] = np.log1p(metadata['log_total_mv'].clip(lower=0))

    for _, date_index in metadata.groupby('trade_date', sort=False).groups.items():
        date_index = list(date_index)
        date_meta = metadata.loc[date_index]
        date_values = neutralized.loc[date_index, numeric_columns]
        industry_means = date_values.groupby(date_meta['industry']).transform('mean')
        adjusted = date_values - industry_means

        size = date_meta['log_total_mv']
        size_centered = size - size.mean()
        denominator = float(np.nansum(np.square(size_centered)))
        if denominator > 0:
            slopes = adjusted.mul(size_centered, axis=0).sum(skipna=True) / denominator
            adjusted = adjusted.sub(size_centered.to_numpy()[:, None] * slopes.to_numpy(), axis=0)

        neutralized.loc[date_index, numeric_columns] = adjusted

    return neutralized


def load_training_frame(
    feature_version='v1',
    chunk_size=100000,
    max_rows_per_split=None,
    stdout=None,
    feature_columns=None,
    random_state=42,
    metadata_columns=None,
):
    feature_columns = feature_columns or FEATURE_COLUMNS
    metadata_columns = _selected_metadata_columns(feature_columns, metadata_columns)
    if max_rows_per_split:
        return _load_training_frame_by_split_limit(
            feature_version,
            max_rows_per_split,
            stdout,
            feature_columns=feature_columns,
            random_state=random_state,
            metadata_columns=metadata_columns,
        )

    columns = [
        'ts_code',
        'trade_date',
        *metadata_columns,
        'future_ret_20',
        'future_excess_ret_20',
        *feature_columns,
        *(target['column'] for target in TARGETS.values()),
    ]
    select_columns = ', '.join(columns)
    required_not_null = ' and '.join(f'{column} is not null' for column in CORE_REQUIRED_COLUMNS)
    sql = f"""
        select {select_columns}
        from model_sample_v1
        where feature_version = %s
          and is_st = false
          and (days_since_list is null or days_since_list >= 120)
          and label_up_20 is not null
          and label_outperform_20 is not null
          and {required_not_null}
          and trade_date between %s and %s
        order by trade_date, ts_code
    """
    min_date = min(start_date for start_date, _ in SPLITS.values())
    max_date = max(end_date for _, end_date in SPLITS.values())

    frames = []
    with connection.cursor() as cursor:
        cursor.execute(sql, [feature_version, min_date, max_date])
        field_names = [item[0] for item in cursor.description]
        total_rows = 0
        while True:
            rows = cursor.fetchmany(chunk_size)
            if not rows:
                break
            chunk = pd.DataFrame.from_records(rows, columns=field_names)
            chunk['split'] = chunk['trade_date'].map(split_for_date)
            chunk = chunk[chunk['split'].notna()]
            if max_rows_per_split:
                chunk = _cap_rows_per_split(chunk, frames, max_rows_per_split)
            if not chunk.empty:
                frames.append(chunk)
                total_rows += len(chunk)
                if stdout:
                    stdout.write(f'train_quant_baseline loaded rows: {total_rows}')
                    stdout.flush()
            if max_rows_per_split and _all_split_caps_reached(frames, max_rows_per_split):
                break

    if not frames:
        return pd.DataFrame(columns=[*columns, 'split'])

    return pd.concat(frames, ignore_index=True)


def _load_training_frame_by_split_limit(
    feature_version,
    max_rows_per_split,
    stdout=None,
    feature_columns=None,
    random_state=42,
    metadata_columns=None,
):
    feature_columns = feature_columns or FEATURE_COLUMNS
    metadata_columns = _selected_metadata_columns(feature_columns, metadata_columns)
    columns = [
        'ts_code',
        'trade_date',
        *metadata_columns,
        'future_ret_20',
        'future_excess_ret_20',
        *feature_columns,
        *(target['column'] for target in TARGETS.values()),
    ]
    select_columns = ', '.join(columns)
    required_not_null = ' and '.join(f'{column} is not null' for column in CORE_REQUIRED_COLUMNS)
    date_sql = """
        select distinct trade_date
        from model_sample_v1
        where feature_version = %s
          and trade_date between %s and %s
        order by trade_date
    """
    sql = f"""
        select *
        from (
            select
                {select_columns},
                row_number() over (
                    partition by trade_date
                    order by md5(ts_code || %s), ts_code
                ) as row_num
            from model_sample_v1
            where feature_version = %s
              and is_st = false
              and (days_since_list is null or days_since_list >= 120)
              and label_up_20 is not null
              and label_outperform_20 is not null
              and {required_not_null}
              and trade_date = any(%s)
        ) limited_rows
        where row_num <= %s
        order by trade_date, row_num
    """

    frames = []
    total_rows = 0
    with connection.cursor() as cursor:
        for split_name, (start_date, end_date) in SPLITS.items():
            cursor.execute(date_sql, [feature_version, start_date, end_date])
            all_trade_dates = [row[0] for row in cursor.fetchall()]
            trade_dates = _evenly_sampled_values(all_trade_dates, max_rows_per_split)
            if not trade_dates:
                continue

            rows_per_date = max(1, int(np.ceil(max_rows_per_split / len(trade_dates))))
            cursor.execute(sql, [str(random_state), feature_version, trade_dates, rows_per_date])
            field_names = [item[0] for item in cursor.description]
            rows = cursor.fetchall()
            if not rows:
                continue
            chunk = pd.DataFrame.from_records(rows, columns=field_names)
            if 'row_num' in chunk:
                chunk = chunk.drop(columns=['row_num'])
            if len(chunk) > max_rows_per_split:
                chunk = _balanced_head_by_date(chunk, max_rows_per_split)
            chunk['split'] = split_name
            frames.append(chunk)
            total_rows += len(chunk)
            if stdout:
                stdout.write(f'train_quant_baseline loaded {split_name} rows: {len(chunk)}, total={total_rows}')
                stdout.flush()

    if not frames:
        return pd.DataFrame(columns=[*columns, 'split'])

    return pd.concat(frames, ignore_index=True)


def train_quant_baseline(
    feature_version='v1',
    output_dir=None,
    chunk_size=100000,
    random_state=42,
    max_rows_per_split=None,
    exclude_limit_flags=False,
    exclude_features=None,
    time_decay_half_life_days=None,
    rank_features_by_date=False,
    neutralize_by_industry_size=False,
    stdout=None,
):
    output_path = Path(output_dir) if output_dir else default_output_dir()
    output_path.mkdir(parents=True, exist_ok=True)
    feature_columns = selected_feature_columns(
        exclude_limit_flags=exclude_limit_flags,
        exclude_features=exclude_features,
    )

    frame = load_training_frame(
        feature_version=feature_version,
        chunk_size=chunk_size,
        max_rows_per_split=max_rows_per_split,
        feature_columns=feature_columns,
        random_state=random_state,
        metadata_columns=NEUTRALIZATION_METADATA_COLUMNS if neutralize_by_industry_size else None,
        stdout=stdout,
    )
    if frame.empty:
        raise ValueError(f'No training rows found for feature_version={feature_version}.')

    split_counts = {name: int((frame['split'] == name).sum()) for name in SPLITS}
    if split_counts['train'] == 0:
        raise ValueError('No training rows found in train split.')

    train_frame = frame[frame['split'] == 'train'].copy()
    preprocessor = QuantBaselinePreprocessor(
        feature_columns,
        BOOLEAN_FEATURES,
        rank_features_by_date=rank_features_by_date,
        neutralize_by_industry_size=neutralize_by_industry_size,
    ).fit(train_frame)

    metrics = {
        'feature_version': feature_version,
        'split_counts': split_counts,
        'features': feature_columns,
        'exclude_limit_flags': exclude_limit_flags,
        'exclude_features': sorted(set(exclude_features or [])),
        'time_decay_half_life_days': time_decay_half_life_days,
        'rank_features_by_date': rank_features_by_date,
        'neutralize_by_industry_size': neutralize_by_industry_size,
        'targets': {},
    }
    coefficient_rows = []
    model_payloads = {}

    x_train = preprocessor.transform(train_frame)
    sample_weight = _time_decay_weights(train_frame, time_decay_half_life_days)
    for target_name, target_config in TARGETS.items():
        target_column = target_config['column']
        y_train = train_frame[target_column].astype(int)
        if y_train.nunique() < 2:
            raise ValueError(f'Target {target_column} has only one class in train split.')

        model = LogisticRegression(
            penalty='elasticnet',
            solver='saga',
            l1_ratio=0.5,
            max_iter=1000,
            n_jobs=-1,
            random_state=random_state,
        )
        model.fit(x_train, y_train, sample_weight=sample_weight)

        target_metrics = {}
        for split_name in SPLITS:
            split_frame = frame[frame['split'] == split_name].copy()
            target_metrics[split_name] = evaluate_split(model, preprocessor, split_frame, target_column)

        target_metrics['baseline_pass'] = _passes_baseline(target_metrics)
        metrics['targets'][target_name] = target_metrics

        for feature, coefficient in zip(feature_columns, model.coef_[0]):
            coefficient_rows.append(
                {
                    'target': target_name,
                    'feature': feature,
                    'factor_group': feature_group(feature),
                    'coefficient': float(coefficient),
                    'abs_coefficient': float(abs(coefficient)),
                }
            )

        model_payload = {
            'model': model,
            'preprocessor': preprocessor,
            'feature_columns': feature_columns,
            'target': target_config,
            'feature_version': feature_version,
            'splits': SPLITS,
            'exclude_limit_flags': exclude_limit_flags,
            'exclude_features': sorted(set(exclude_features or [])),
            'time_decay_half_life_days': time_decay_half_life_days,
            'rank_features_by_date': rank_features_by_date,
            'neutralize_by_industry_size': neutralize_by_industry_size,
        }
        model_payloads[target_name] = model_payload
        joblib.dump(model_payload, output_path / target_config['model_file'])

    coefficients = pd.DataFrame(coefficient_rows).sort_values(
        ['target', 'abs_coefficient'],
        ascending=[True, False],
    )
    coefficients.to_csv(output_path / 'feature_coefficients.csv', index=False, encoding='utf-8')
    (output_path / 'metrics.json').write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    return {
        'output_dir': str(output_path),
        'metrics': metrics,
        'models': model_payloads,
    }


def calibrate_quant_baseline(
    artifacts_dir,
    output_dir=None,
    feature_version='v1',
    method='sigmoid',
    max_rows_per_split=50000,
    random_state=42,
    stdout=None,
):
    if method not in {'sigmoid', 'isotonic'}:
        raise ValueError('method must be one of: sigmoid, isotonic.')

    artifacts_path = Path(artifacts_dir)
    output_path = Path(output_dir) if output_dir else artifacts_path.with_name(f'{artifacts_path.name}_calibrated')
    output_path.mkdir(parents=True, exist_ok=True)

    first_payload = _load_target_payload(artifacts_path, next(iter(TARGETS)))
    feature_columns = first_payload.get('feature_columns') or FEATURE_COLUMNS
    neutralize_by_industry_size = bool(first_payload.get('neutralize_by_industry_size'))
    frame = load_training_frame(
        feature_version=feature_version,
        max_rows_per_split=max_rows_per_split,
        feature_columns=feature_columns,
        random_state=random_state,
        metadata_columns=NEUTRALIZATION_METADATA_COLUMNS if neutralize_by_industry_size else None,
        stdout=stdout,
    )
    if frame.empty:
        raise ValueError(f'No calibration rows found for feature_version={feature_version}.')
    if not (frame['split'] == 'validation').any():
        raise ValueError('Calibration requires validation split rows.')

    metrics = {
        'feature_version': feature_version,
        'source_artifacts_dir': str(artifacts_path),
        'output_dir': str(output_path),
        'method': method,
        'fit_split': 'validation',
        'split_counts': {name: int((frame['split'] == name).sum()) for name in SPLITS},
        'targets': {},
    }
    bin_rows = []

    for target_name, target_config in TARGETS.items():
        payload = _load_target_payload(artifacts_path, target_name)
        target_column = target_config['column']
        raw_scores = _predict_uncalibrated_payload_scores(payload, frame)
        validation_mask = frame['split'] == 'validation'
        y_validation = frame.loc[validation_mask, target_column].astype(int)
        if y_validation.nunique() < 2:
            raise ValueError(f'Target {target_column} has only one class in validation split.')

        calibrator = _fit_score_calibrator(
            raw_scores[validation_mask.to_numpy()],
            y_validation.to_numpy(),
            method=method,
        )
        calibrated_scores = _apply_score_calibrator(
            {
                **payload,
                'calibrator': calibrator,
                'calibration_method': method,
            },
            raw_scores,
        )

        target_metrics = {'raw': {}, 'calibrated': {}}
        for split_name in SPLITS:
            split_mask = frame['split'] == split_name
            split_frame = frame.loc[split_mask].copy()
            split_raw = raw_scores[split_mask.to_numpy()]
            split_calibrated = calibrated_scores[split_mask.to_numpy()]
            target_metrics['raw'][split_name] = evaluate_scored_frame(split_frame, split_raw, target_column)
            target_metrics['calibrated'][split_name] = evaluate_scored_frame(split_frame, split_calibrated, target_column)
            bin_rows.extend(
                _calibration_bin_rows(
                    target_name=target_name,
                    split_name=split_name,
                    y_true=split_frame[target_column].astype(int).to_numpy(),
                    probabilities=split_calibrated,
                )
            )
        metrics['targets'][target_name] = target_metrics

        calibrated_payload = {
            **payload,
            'calibrator': calibrator,
            'calibration_method': method,
            'calibration_fit_split': 'validation',
            'calibration_source_artifacts_dir': str(artifacts_path),
        }
        joblib.dump(calibrated_payload, output_path / target_config['model_file'])

    coefficients_path = artifacts_path / 'feature_coefficients.csv'
    if coefficients_path.exists():
        pd.read_csv(coefficients_path).to_csv(output_path / 'feature_coefficients.csv', index=False, encoding='utf-8')

    (output_path / 'calibration_metrics.json').write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    pd.DataFrame(bin_rows).to_csv(output_path / 'calibration_bins.csv', index=False, encoding='utf-8')
    return {
        'output_dir': str(output_path),
        'metrics': metrics,
    }


def paper_trade_quant_strategy(
    artifacts_dir,
    fallback_artifacts_dir=None,
    switch_months=None,
    feature_version='v1',
    target_name='up',
    max_rows_per_split=50000,
    top_quantile=0.1,
    random_state=42,
    output_dir=None,
    stdout=None,
):
    if target_name not in TARGETS:
        raise ValueError(f'Unknown target_name={target_name}. Expected one of: {", ".join(TARGETS)}')
    if not 0 < top_quantile < 1:
        raise ValueError('top_quantile must be between 0 and 1.')

    switch_months = sorted({str(item).strip() for item in (switch_months or []) if str(item).strip()})
    invalid_months = [item for item in switch_months if len(item) != 6 or not item.isdigit()]
    if invalid_months:
        raise ValueError(f'switch_months must be YYYYMM values: {", ".join(invalid_months)}')

    primary_payload = _load_target_payload(artifacts_dir, target_name)
    fallback_payload = _load_target_payload(fallback_artifacts_dir, target_name) if fallback_artifacts_dir else None
    feature_columns = _dedupe_preserve_order(
        [
            *(primary_payload.get('feature_columns') or FEATURE_COLUMNS),
            *((fallback_payload or {}).get('feature_columns') or []),
        ]
    )
    needs_neutralization_metadata = bool(
        primary_payload.get('neutralize_by_industry_size')
        or (fallback_payload and fallback_payload.get('neutralize_by_industry_size'))
    )
    frame = load_training_frame(
        feature_version=feature_version,
        max_rows_per_split=max_rows_per_split,
        feature_columns=feature_columns,
        random_state=random_state,
        metadata_columns=NEUTRALIZATION_METADATA_COLUMNS if needs_neutralization_metadata else None,
        stdout=stdout,
    )
    if frame.empty:
        raise ValueError(f'No paper trading rows found for feature_version={feature_version}.')

    primary_scores = _predict_payload_scores(primary_payload, frame)
    if fallback_payload:
        fallback_scores = _predict_payload_scores(fallback_payload, frame)
        use_fallback = frame['trade_date'].str[:6].isin(switch_months).to_numpy()
        scores = np.where(use_fallback, fallback_scores, primary_scores)
    else:
        use_fallback = np.zeros(len(frame), dtype=bool)
        scores = primary_scores

    scored = frame[['ts_code', 'trade_date', 'split', 'future_ret_20', 'future_excess_ret_20']].copy()
    scored['score'] = scores
    scored['use_fallback'] = use_fallback
    scored['score_pct_rank'] = scored.groupby('trade_date')['score'].rank(method='first', pct=True)
    scored['selected'] = scored['score_pct_rank'] >= (1 - top_quantile)

    daily_rows = []
    for trade_date, group in scored.groupby('trade_date', sort=True):
        selected = group[group['selected']]
        daily_rows.append(
            {
                'trade_date': str(trade_date),
                'split': str(group['split'].iloc[0]),
                'rows': int(len(group)),
                'selected_rows': int(len(selected)),
                'use_fallback': bool(group['use_fallback'].any()),
                'mean_score': _nullable_mean(selected['score']),
                'portfolio_future_ret_20': _nullable_mean(selected['future_ret_20']),
                'portfolio_future_excess_ret_20': _nullable_mean(selected['future_excess_ret_20']),
                'universe_future_ret_20': _nullable_mean(group['future_ret_20']),
                'universe_future_excess_ret_20': _nullable_mean(group['future_excess_ret_20']),
                'hit_rate_up': _nullable_mean((selected['future_ret_20'] > 0).astype(float)) if not selected.empty else None,
                'hit_rate_outperform': _nullable_mean((selected['future_excess_ret_20'] > 0).astype(float)) if not selected.empty else None,
            }
        )

    daily = pd.DataFrame(daily_rows)
    daily['month'] = daily['trade_date'].str[:6]
    summary = {
        'feature_version': feature_version,
        'target': target_name,
        'artifacts_dir': str(artifacts_dir),
        'fallback_artifacts_dir': str(fallback_artifacts_dir) if fallback_artifacts_dir else None,
        'switch_months': switch_months,
        'top_quantile': top_quantile,
        'rows': int(len(scored)),
        'trade_dates': int(daily['trade_date'].nunique()) if not daily.empty else 0,
        'warnings': [
            'paper_returns_use_overlapping_future_20_day_labels: summary is for model validation, not an executable daily NAV backtest'
        ],
        'by_split': _paper_summary_by_group(daily, 'split'),
        'by_month': _paper_summary_by_group(daily, 'month'),
    }

    output_path = Path(output_dir) if output_dir else Path(artifacts_dir) / 'paper_trading'
    output_path.mkdir(parents=True, exist_ok=True)
    report_path = output_path / f'paper_trading_{target_name}.json'
    daily_path = output_path / f'paper_trading_{target_name}_daily.csv'
    month_path = output_path / f'paper_trading_{target_name}_months.csv'
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    daily.to_csv(daily_path, index=False, encoding='utf-8')
    pd.DataFrame(summary['by_month']).to_csv(month_path, index=False, encoding='utf-8')
    return {
        'summary': summary,
        'report_path': str(report_path),
        'daily_path': str(daily_path),
        'month_path': str(month_path),
    }


def analyze_quant_baseline(
    artifacts_dir,
    feature_version='v1',
    max_rows_per_split=50000,
    stdout=None,
):
    artifacts_path = Path(artifacts_dir)
    first_target = next(iter(TARGETS.values()))
    first_model_path = artifacts_path / first_target['model_file']
    if not first_model_path.exists():
        raise FileNotFoundError(f'Model artifact not found: {first_model_path}')
    first_payload = joblib.load(first_model_path)
    feature_columns = first_payload.get('feature_columns') or FEATURE_COLUMNS
    neutralize_by_industry_size = bool(first_payload.get('neutralize_by_industry_size'))
    frame = load_training_frame(
        feature_version=feature_version,
        max_rows_per_split=max_rows_per_split,
        feature_columns=feature_columns,
        random_state=42,
        metadata_columns=NEUTRALIZATION_METADATA_COLUMNS if neutralize_by_industry_size else None,
        stdout=stdout,
    )
    if frame.empty:
        raise ValueError(f'No analysis rows found for feature_version={feature_version}.')

    report = {
        'feature_version': feature_version,
        'artifacts_dir': str(artifacts_path),
        'rows': int(len(frame)),
        'features': feature_columns,
        'split_counts': {name: int((frame['split'] == name).sum()) for name in SPLITS},
        'year_counts': {str(year): int(count) for year, count in frame['trade_date'].str[:4].value_counts().sort_index().items()},
        'month_counts': {str(month): int(count) for month, count in frame['trade_date'].str[:6].value_counts().sort_index().items()},
        'missing_rates': _missing_rates(frame, feature_columns),
        'data_quality': data_quality_summary(feature_version=feature_version),
        'targets': {},
    }

    for target_name, target_config in TARGETS.items():
        model_path = artifacts_path / target_config['model_file']
        if not model_path.exists():
            raise FileNotFoundError(f'Model artifact not found: {model_path}')
        payload = first_payload if model_path == first_model_path else joblib.load(model_path)
        model = payload['model']
        preprocessor = payload['preprocessor']
        target_column = target_config['column']
        target_report = {
            'by_split': {},
            'by_year': {},
            'by_month': {},
        }

        for split_name in SPLITS:
            split_frame = frame[frame['split'] == split_name].copy()
            target_report['by_split'][split_name] = evaluate_split(model, preprocessor, split_frame, target_column)

        for year, year_frame in frame.groupby(frame['trade_date'].str[:4], sort=True):
            target_report['by_year'][str(year)] = evaluate_split(model, preprocessor, year_frame.copy(), target_column)

        for month, month_frame in frame.groupby(frame['trade_date'].str[:6], sort=True):
            target_report['by_month'][str(month)] = evaluate_split(model, preprocessor, month_frame.copy(), target_column)

        report['targets'][target_name] = target_report

    report_path = artifacts_path / 'analysis_report.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    _write_missing_rates_csv(report['missing_rates'], artifacts_path / 'missing_rates.csv')
    _write_year_metrics_csv(report['targets'], artifacts_path / 'year_metrics.csv')
    _write_month_metrics_csv(report['targets'], artifacts_path / 'month_metrics.csv')
    return report


def evaluate_quant_regime_blend(
    primary_artifacts_dir,
    fallback_artifacts_dir,
    switch_months=None,
    feature_version='v1',
    target_name='up',
    max_rows_per_split=50000,
    random_state=42,
    output_dir=None,
    auto_switch_rule=None,
    auto_switch_source='sample',
    ma60_bias_threshold=-0.04,
    ma60_bias_floor=None,
    ret20_rebound_threshold=-0.04,
    ret20_rebound_ceiling=None,
    stdout=None,
):
    if target_name not in TARGETS:
        raise ValueError(f'Unknown target_name={target_name}. Expected one of: {", ".join(TARGETS)}')
    switch_months = sorted({str(month).strip() for month in (switch_months or []) if str(month).strip()})
    auto_switch_rule = (auto_switch_rule or '').strip() or None
    auto_switch_source = (auto_switch_source or 'sample').strip()
    if auto_switch_source not in {'sample', 'database'}:
        raise ValueError('auto_switch_source must be one of: sample, database.')

    primary_payload = _load_target_payload(primary_artifacts_dir, target_name)
    fallback_payload = _load_target_payload(fallback_artifacts_dir, target_name)
    feature_columns = _dedupe_preserve_order(
        [
            *(primary_payload.get('feature_columns') or FEATURE_COLUMNS),
            *(fallback_payload.get('feature_columns') or FEATURE_COLUMNS),
        ]
    )
    if auto_switch_rule in {'weak_ma60', 'rebound_after_weakness'} and 'ma60_bias' not in feature_columns:
        feature_columns.append('ma60_bias')
    if auto_switch_rule == 'rebound_after_weakness' and 'ret_20' not in feature_columns:
        feature_columns.append('ret_20')
    invalid_months = [month for month in switch_months if len(month) != 6 or not month.isdigit()]
    if invalid_months:
        raise ValueError(f'switch_months must be YYYYMM values: {", ".join(invalid_months)}')
    if not switch_months and not auto_switch_rule:
        raise ValueError('Either switch_months or auto_switch_rule must be provided.')
    needs_neutralization_metadata = bool(
        primary_payload.get('neutralize_by_industry_size')
        or fallback_payload.get('neutralize_by_industry_size')
    )
    auto_switch_report = None
    if auto_switch_rule and auto_switch_source == 'database':
        switch_months, auto_switch_report = _auto_switch_months_from_database(
            feature_version=feature_version,
            auto_switch_rule=auto_switch_rule,
            ma60_bias_threshold=ma60_bias_threshold,
            ma60_bias_floor=ma60_bias_floor,
            ret20_rebound_threshold=ret20_rebound_threshold,
            ret20_rebound_ceiling=ret20_rebound_ceiling,
        )

    frame = load_training_frame(
        feature_version=feature_version,
        max_rows_per_split=max_rows_per_split,
        feature_columns=feature_columns,
        random_state=random_state,
        metadata_columns=NEUTRALIZATION_METADATA_COLUMNS if needs_neutralization_metadata else None,
        stdout=stdout,
    )
    if frame.empty:
        raise ValueError(f'No rows found for regime blend evaluation: feature_version={feature_version}.')

    if auto_switch_rule and auto_switch_source == 'sample':
        switch_months, auto_switch_report = _auto_switch_months(
            frame,
            auto_switch_rule=auto_switch_rule,
            ma60_bias_threshold=ma60_bias_threshold,
            ma60_bias_floor=ma60_bias_floor,
            ret20_rebound_threshold=ret20_rebound_threshold,
            ret20_rebound_ceiling=ret20_rebound_ceiling,
        )

    primary_scores = _predict_payload_scores(primary_payload, frame)
    fallback_scores = _predict_payload_scores(fallback_payload, frame)
    use_fallback = frame['trade_date'].str[:6].isin(switch_months).to_numpy()
    blended_scores = np.where(use_fallback, fallback_scores, primary_scores)
    target_column = TARGETS[target_name]['column']

    report = {
        'feature_version': feature_version,
        'target': target_name,
        'primary_artifacts_dir': str(primary_artifacts_dir),
        'fallback_artifacts_dir': str(fallback_artifacts_dir),
        'switch_months': switch_months,
        'auto_switch_rule': auto_switch_rule,
        'auto_switch_source': auto_switch_source if auto_switch_rule else None,
        'auto_switch_report': auto_switch_report,
        'ma60_bias_threshold': ma60_bias_threshold if auto_switch_rule else None,
        'ma60_bias_floor': ma60_bias_floor if auto_switch_rule == 'rebound_after_weakness' else None,
        'ret20_rebound_threshold': ret20_rebound_threshold if auto_switch_rule == 'rebound_after_weakness' else None,
        'ret20_rebound_ceiling': ret20_rebound_ceiling if auto_switch_rule == 'rebound_after_weakness' else None,
        'rows': int(len(frame)),
        'fallback_rows': int(use_fallback.sum()),
        'split_counts': {name: int((frame['split'] == name).sum()) for name in SPLITS},
        'by_split': {},
        'by_month': {},
    }
    for split_name in SPLITS:
        mask = frame['split'] == split_name
        report['by_split'][split_name] = evaluate_scored_frame(
            frame.loc[mask].copy(),
            blended_scores[mask.to_numpy()],
            target_column,
        )
    for month, month_frame in frame.groupby(frame['trade_date'].str[:6], sort=True):
        month_index = month_frame.index.to_numpy()
        report['by_month'][str(month)] = evaluate_scored_frame(
            month_frame.copy(),
            blended_scores[month_index],
            target_column,
        )

    output_path = Path(output_dir) if output_dir else Path(primary_artifacts_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    switch_label = '_'.join(switch_months) if switch_months else (auto_switch_rule or 'none')
    report_path = output_path / f'regime_blend_{target_name}_{switch_label}.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    _write_regime_blend_month_csv(report['by_month'], output_path / f'regime_blend_{target_name}_{switch_label}_months.csv')
    return {
        'report': report,
        'report_path': str(report_path),
    }


def diagnose_quant_baseline_slice(
    artifacts_dir,
    fallback_artifacts_dir=None,
    switch_months=None,
    feature_version='v1',
    month='202604',
    target_name='up',
    max_rows=50000,
    random_state=42,
    stdout=None,
):
    if target_name not in TARGETS:
        raise ValueError(f'Unknown target_name={target_name}. Expected one of: {", ".join(TARGETS)}')
    if len(month) != 6 or not month.isdigit():
        raise ValueError('month must be formatted as YYYYMM.')

    switch_months = sorted({str(item).strip() for item in (switch_months or []) if str(item).strip()})
    invalid_months = [item for item in switch_months if len(item) != 6 or not item.isdigit()]
    if invalid_months:
        raise ValueError(f'switch_months must be YYYYMM values: {", ".join(invalid_months)}')

    primary_artifacts_path = Path(artifacts_dir)
    use_fallback = bool(fallback_artifacts_dir and month in switch_months)
    artifacts_path = Path(fallback_artifacts_dir) if use_fallback else primary_artifacts_path
    model_role = 'fallback' if use_fallback else 'primary'
    target_config = TARGETS[target_name]
    model_path = artifacts_path / target_config['model_file']
    if not model_path.exists():
        raise FileNotFoundError(f'Model artifact not found: {model_path}')

    payload = joblib.load(model_path)
    feature_columns = payload.get('feature_columns') or FEATURE_COLUMNS
    preprocessor = payload['preprocessor']
    model = payload['model']
    frame = load_diagnostic_slice_frame(
        feature_version=feature_version,
        month=month,
        feature_columns=feature_columns,
        max_rows=max_rows,
        random_state=random_state,
        stdout=stdout,
    )
    if frame.empty:
        raise ValueError(f'No diagnostic rows found for feature_version={feature_version}, month={month}.')

    x_values = preprocessor.transform(frame)
    probabilities = model.predict_proba(x_values)[:, 1]
    scored = frame.copy()
    scored['score'] = probabilities
    scored['score_pct_rank'] = scored.groupby('trade_date')['score'].rank(method='first', pct=True)
    scored['cohort'] = 'middle'
    scored.loc[scored['score_pct_rank'] >= 0.9, 'cohort'] = 'top'
    scored.loc[scored['score_pct_rank'] <= 0.1, 'cohort'] = 'bottom'

    target_column = target_config['column']
    summary = {
        'artifact_dir': str(artifacts_path),
        'primary_artifact_dir': str(primary_artifacts_path),
        'fallback_artifact_dir': str(fallback_artifacts_dir) if fallback_artifacts_dir else None,
        'switch_months': switch_months,
        'model_role': model_role,
        'use_fallback': use_fallback,
        'feature_version': feature_version,
        'month': month,
        'target': target_name,
        'rows': int(len(scored)),
        'trade_dates': sorted(scored['trade_date'].unique().tolist()),
        'cohorts': {
            cohort: _diagnostic_cohort_summary(group, target_column)
            for cohort, group in scored.groupby('cohort', sort=True)
        },
    }
    summary['top_minus_bottom'] = _top_minus_bottom_summary(summary['cohorts'])

    industry_rows = _diagnostic_industry_rows(scored)
    feature_rows = _diagnostic_feature_rows(scored, feature_columns)
    member_columns = [
        'cohort',
        'trade_date',
        'ts_code',
        'stock_name',
        'industry',
        'score',
        'score_pct_rank',
        'future_ret_20',
        'future_excess_ret_20',
        target_column,
        'total_mv',
        'circ_mv',
    ]
    member_columns = [column for column in member_columns if column in scored]
    members = scored[scored['cohort'].isin(['top', 'bottom'])].sort_values(
        ['trade_date', 'cohort', 'score'],
        ascending=[True, True, False],
    )[member_columns]

    output_prefix = f'diagnostic_{target_name}_{month}'
    (artifacts_path / f'{output_prefix}_summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    pd.DataFrame(industry_rows).to_csv(artifacts_path / f'{output_prefix}_industry.csv', index=False, encoding='utf-8')
    pd.DataFrame(feature_rows).to_csv(artifacts_path / f'{output_prefix}_features.csv', index=False, encoding='utf-8')
    members.to_csv(artifacts_path / f'{output_prefix}_members.csv', index=False, encoding='utf-8')

    return {
        'summary': summary,
        'industry_rows': industry_rows,
        'feature_rows': feature_rows,
        'output_prefix': str(artifacts_path / output_prefix),
    }


def generate_quant_observation_list(
    artifacts_dir,
    fallback_artifacts_dir=None,
    switch_months=None,
    feature_version='v1',
    month='202608',
    target_name='all',
    max_rows=50000,
    random_state=42,
    top_quantile=0.1,
    output_dir=None,
    stdout=None,
):
    if target_name not in {'all', *TARGETS.keys()}:
        raise ValueError(f'Unknown target_name={target_name}. Expected one of: all, {", ".join(TARGETS)}')
    if len(month) != 6 or not month.isdigit():
        raise ValueError('month must be formatted as YYYYMM.')
    if not 0 < top_quantile < 1:
        raise ValueError('top_quantile must be between 0 and 1.')

    switch_months = sorted({str(item).strip() for item in (switch_months or []) if str(item).strip()})
    invalid_months = [item for item in switch_months if len(item) != 6 or not item.isdigit()]
    if invalid_months:
        raise ValueError(f'switch_months must be YYYYMM values: {", ".join(invalid_months)}')

    target_names = list(TARGETS.keys()) if target_name == 'all' else [target_name]
    primary_artifacts_path = Path(artifacts_dir)
    use_fallback = bool(fallback_artifacts_dir and month in switch_months)
    artifacts_path = Path(fallback_artifacts_dir) if use_fallback else primary_artifacts_path
    model_role = 'fallback' if use_fallback else 'primary'

    payloads = {}
    feature_columns = []
    needs_neutralization_metadata = False
    for current_target in target_names:
        target_config = TARGETS[current_target]
        model_path = artifacts_path / target_config['model_file']
        if not model_path.exists():
            raise FileNotFoundError(f'Model artifact not found: {model_path}')
        payload = joblib.load(model_path)
        payloads[current_target] = payload
        feature_columns.extend(payload.get('feature_columns') or FEATURE_COLUMNS)
        needs_neutralization_metadata = needs_neutralization_metadata or bool(payload.get('neutralize_by_industry_size'))
    feature_columns = _dedupe_preserve_order(feature_columns)

    frame = load_diagnostic_slice_frame(
        feature_version=feature_version,
        month=month,
        feature_columns=feature_columns,
        max_rows=max_rows,
        random_state=random_state,
        require_labels=False,
        stdout=stdout,
    )
    if frame.empty:
        raise ValueError(f'No observation rows found for feature_version={feature_version}, month={month}.')

    scored = frame.copy()
    scored['split'] = scored['trade_date'].apply(split_for_date)
    def _cohort_from_rank(score_pct_rank):
        if score_pct_rank is None or pd.isna(score_pct_rank):
            return 'middle'
        if score_pct_rank >= 1 - top_quantile:
            return 'top'
        if score_pct_rank <= top_quantile:
            return 'bottom'
        return 'middle'

    target_summaries = {}
    for current_target in target_names:
        payload = payloads[current_target]
        model = payload['model']
        preprocessor = payload['preprocessor']
        probabilities = _apply_score_calibrator(payload, model.predict_proba(preprocessor.transform(frame))[:, 1])
        score_column = f'{current_target}_score'
        pct_rank_column = f'{current_target}_score_pct_rank'
        decile_column = f'{current_target}_score_decile'
        cohort_column = f'{current_target}_cohort'
        scored[score_column] = probabilities
        scored[pct_rank_column] = scored.groupby('trade_date')[score_column].rank(method='first', pct=True)
        scored[decile_column] = np.ceil(scored[pct_rank_column] * 10).clip(1, 10).astype(int)
        scored[cohort_column] = scored[pct_rank_column].apply(_cohort_from_rank)
        target_summaries[current_target] = {
            'rows': int(len(scored)),
            'score_mean': _nullable_mean(scored[score_column]),
            'score_pct_rank_mean': _nullable_mean(scored[pct_rank_column]),
            'top_rows': int((scored[cohort_column] == 'top').sum()),
            'bottom_rows': int((scored[cohort_column] == 'bottom').sum()),
        }

    if 'up' in target_names and 'outperform' in target_names:
        combined_signal_rows = []
        combined_pct_ranks = []
        combined_cohorts = []
        for row in scored.itertuples(index=False):
            up_summary = {
                'score_pct_rank': getattr(row, 'up_score_pct_rank'),
                'score_decile': getattr(row, 'up_score_decile'),
            }
            outperform_summary = {
                'score_pct_rank': getattr(row, 'outperform_score_pct_rank'),
                'score_decile': getattr(row, 'outperform_score_decile'),
            }
            combined = _combined_stock_signal({'up': up_summary, 'outperform': outperform_summary})
            combined_signal_rows.append(combined)
            up_rank = up_summary['score_pct_rank']
            outperform_rank = outperform_summary['score_pct_rank']
            if up_rank is None or outperform_rank is None:
                combined_pct_rank = None
            else:
                combined_pct_rank = float((float(up_rank) + float(outperform_rank)) / 2.0)
            combined_pct_ranks.append(combined_pct_rank)
            combined_cohorts.append(_cohort_from_rank(combined_pct_rank))

        scored['combined_signal_label'] = [item['label'] for item in combined_signal_rows]
        scored['combined_signal_confidence'] = [item['confidence'] for item in combined_signal_rows]
        scored['combined_decile_gap'] = [item.get('decile_gap') for item in combined_signal_rows]
        scored['combined_score_pct_rank'] = combined_pct_ranks
        scored['cohort'] = combined_cohorts
        scored['score'] = scored['combined_score_pct_rank']
    else:
        only_target = target_names[0]
        scored['combined_signal_label'] = None
        scored['combined_signal_confidence'] = None
        scored['combined_decile_gap'] = None
        scored['combined_score_pct_rank'] = scored[f'{only_target}_score_pct_rank']
        scored['cohort'] = scored[f'{only_target}_cohort']
        scored['score'] = scored[f'{only_target}_score']

    summary = {
        'feature_version': feature_version,
        'month': month,
        'rows': int(len(scored)),
        'trade_dates': sorted(scored['trade_date'].unique().tolist()),
        'model_role': model_role,
        'use_fallback': use_fallback,
        'artifact_dir': str(artifacts_path),
        'primary_artifact_dir': str(primary_artifacts_path),
        'fallback_artifact_dir': str(fallback_artifacts_dir) if fallback_artifacts_dir else None,
        'switch_months': switch_months,
        'top_quantile': top_quantile,
        'target_names': target_names,
        'split_counts': {name: int((scored['split'] == name).sum()) for name in SPLITS},
        'target_summaries': target_summaries,
        'combined_signal_counts': {
            str(label): int(count)
            for label, count in scored['combined_signal_label'].value_counts(dropna=False).items()
        },
        'cohort_counts': {str(label): int(count) for label, count in scored['cohort'].value_counts(dropna=False).items()},
    }

    if 'up' in target_names and 'outperform' in target_names:
        summary['combined_signal'] = _combined_stock_signal(
            {
                'up': {
                    'score_pct_rank': _nullable_mean(scored['up_score_pct_rank']),
                    'score_decile': int(scored['up_score_decile'].median()) if not scored['up_score_decile'].empty else None,
                },
                'outperform': {
                    'score_pct_rank': _nullable_mean(scored['outperform_score_pct_rank']),
                    'score_decile': int(scored['outperform_score_decile'].median())
                    if not scored['outperform_score_decile'].empty
                    else None,
                },
            }
        )

    feature_rows = _diagnostic_feature_rows(scored, feature_columns)
    industry_rows = _diagnostic_industry_rows(scored)
    member_columns = [
        'cohort',
        'trade_date',
        'ts_code',
        'stock_name',
        'industry',
        'score',
        'combined_score_pct_rank',
        'combined_signal_label',
        'combined_signal_confidence',
        'combined_decile_gap',
        'future_ret_20',
        'future_excess_ret_20',
        'total_mv',
        'circ_mv',
        'days_since_list',
    ]
    for current_target in target_names:
        member_columns.extend(
            [
                f'{current_target}_score',
                f'{current_target}_score_pct_rank',
                f'{current_target}_score_decile',
            ]
        )
    member_columns = _dedupe_preserve_order([column for column in member_columns if column in scored])
    members = scored[scored['cohort'].isin(['top', 'bottom'])].sort_values(
        ['trade_date', 'cohort', 'combined_score_pct_rank', 'score'],
        ascending=[True, True, False, False],
    )[member_columns]

    output_path = Path(output_dir) if output_dir else artifacts_path / 'observation_lists'
    output_path.mkdir(parents=True, exist_ok=True)
    output_prefix = f'observation_{month}'
    (output_path / f'{output_prefix}_summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    scored.to_csv(output_path / f'{output_prefix}_scored.csv', index=False, encoding='utf-8')
    pd.DataFrame(industry_rows).to_csv(output_path / f'{output_prefix}_industry.csv', index=False, encoding='utf-8')
    pd.DataFrame(feature_rows).to_csv(output_path / f'{output_prefix}_features.csv', index=False, encoding='utf-8')
    members.to_csv(output_path / f'{output_prefix}_members.csv', index=False, encoding='utf-8')
    scored[scored['cohort'] == 'top'].to_csv(output_path / f'{output_prefix}_watchlist.csv', index=False, encoding='utf-8')

    return {
        'summary': summary,
        'industry_rows': industry_rows,
        'feature_rows': feature_rows,
        'output_prefix': str(output_path / output_prefix),
    }


def diagnose_quant_stock(
    ts_code,
    trade_date,
    artifacts_dir,
    fallback_artifacts_dir=None,
    switch_months=None,
    feature_version='v1',
    target_name='up',
    output_dir=None,
    write_report=True,
    stdout=None,
):
    if target_name not in TARGETS:
        raise ValueError(f'Unknown target_name={target_name}. Expected one of: {", ".join(TARGETS)}')
    trade_date = str(trade_date)
    if len(trade_date) != 8 or not trade_date.isdigit():
        raise ValueError('trade_date must be formatted as YYYYMMDD.')
    if not ts_code:
        raise ValueError('ts_code is required.')

    switch_months = sorted({str(item).strip() for item in (switch_months or []) if str(item).strip()})
    invalid_months = [item for item in switch_months if len(item) != 6 or not item.isdigit()]
    if invalid_months:
        raise ValueError(f'switch_months must be YYYYMM values: {", ".join(invalid_months)}')

    month = trade_date[:6]
    primary_artifacts_path = Path(artifacts_dir)
    use_fallback = bool(fallback_artifacts_dir and month in switch_months)
    artifacts_path = Path(fallback_artifacts_dir) if use_fallback else primary_artifacts_path
    model_role = 'fallback' if use_fallback else 'primary'
    target_config = TARGETS[target_name]
    model_path = artifacts_path / target_config['model_file']
    if not model_path.exists():
        raise FileNotFoundError(f'Model artifact not found: {model_path}')

    payload = joblib.load(model_path)
    feature_columns = payload.get('feature_columns') or FEATURE_COLUMNS
    frame = load_stock_diagnostic_frame(
        feature_version=feature_version,
        trade_date=trade_date,
        feature_columns=feature_columns,
        stdout=stdout,
    )
    if frame.empty:
        raise ValueError(f'No diagnostic rows found for feature_version={feature_version}, trade_date={trade_date}.')

    target_rows = frame[frame['ts_code'] == ts_code]
    if target_rows.empty:
        raise ValueError(f'{ts_code} was not found in the diagnostic universe for trade_date={trade_date}.')
    if len(target_rows) > 1:
        target_rows = target_rows.head(1)

    model = payload['model']
    preprocessor = payload['preprocessor']
    transformed = preprocessor.transform(frame)
    raw_probabilities = model.predict_proba(transformed)[:, 1]
    probabilities = _apply_score_calibrator(payload, raw_probabilities)
    scored = frame.copy()
    scored['score'] = probabilities
    scored['score_pct_rank'] = scored['score'].rank(method='first', pct=True)
    scored['score_decile'] = np.ceil(scored['score_pct_rank'] * 10).clip(1, 10).astype(int)

    target_index = target_rows.index[0]
    target_position = scored.index.get_loc(target_index)
    target_scored = scored.iloc[target_position]
    target_column = target_config['column']
    contributions = _stock_feature_contributions(
        payload=payload,
        frame=frame,
        transformed=transformed,
        row_position=target_position,
    )

    summary = {
        'ts_code': ts_code,
        'stock_name': _json_value(target_scored.get('stock_name')),
        'industry': _json_value(target_scored.get('industry')),
        'trade_date': trade_date,
        'feature_version': feature_version,
        'target': target_name,
        'target_description': target_config['description'],
        'model_role': model_role,
        'use_fallback': use_fallback,
        'artifact_dir': str(artifacts_path),
        'primary_artifact_dir': str(primary_artifacts_path),
        'fallback_artifact_dir': str(fallback_artifacts_dir) if fallback_artifacts_dir else None,
        'switch_months': switch_months,
        'universe_rows': int(len(scored)),
        'score': float(target_scored['score']),
        'score_pct_rank': float(target_scored['score_pct_rank']),
        'score_decile': int(target_scored['score_decile']),
        'cohort': _score_cohort(target_scored['score_pct_rank']),
        'split': split_for_date(trade_date),
        'warnings': _stock_diagnostic_warnings(
            model_role=model_role,
            score_pct_rank=float(target_scored['score_pct_rank']),
            split_name=split_for_date(trade_date),
            missing_feature_count=int(target_rows.iloc[0][feature_columns].isna().sum()),
            feature_count=len(feature_columns),
        ),
        'observed': {
            'future_ret_20': _json_value(target_scored.get('future_ret_20')),
            'future_excess_ret_20': _json_value(target_scored.get('future_excess_ret_20')),
            'label': _json_value(target_scored.get(target_column)),
        },
        'metadata': {
            'days_since_list': _json_value(target_scored.get('days_since_list')),
            'total_mv': _json_value(target_scored.get('total_mv')),
            'circ_mv': _json_value(target_scored.get('circ_mv')),
        },
        'top_positive_contributions': contributions['positive'][:10],
        'top_negative_contributions': contributions['negative'][:10],
        'factor_group_contributions': contributions['factor_groups'],
    }

    report_path = None
    if write_report:
        output_path = Path(output_dir) if output_dir else primary_artifacts_path / 'stock_diagnostics'
        output_path.mkdir(parents=True, exist_ok=True)
        safe_code = ts_code.replace('.', '_')
        report_path = output_path / f'stock_diagnostic_{target_name}_{safe_code}_{trade_date}.json'
        report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return {
        'summary': summary,
        'report_path': str(report_path) if report_path else None,
    }


def diagnose_quant_stock_combined(
    ts_code,
    trade_date,
    artifacts_dir,
    fallback_artifacts_dir=None,
    switch_months=None,
    feature_version='v1',
    output_dir=None,
    write_report=True,
    stdout=None,
):
    target_results = {}
    target_summaries = {}
    for target_name in TARGETS:
        result = diagnose_quant_stock(
            ts_code=ts_code,
            trade_date=trade_date,
            artifacts_dir=artifacts_dir,
            fallback_artifacts_dir=fallback_artifacts_dir,
            switch_months=switch_months,
            feature_version=feature_version,
            target_name=target_name,
            output_dir=output_dir,
            write_report=write_report,
            stdout=stdout,
        )
        target_results[target_name] = result
        target_summaries[target_name] = result['summary']

    first = target_summaries[next(iter(TARGETS))]
    combined_summary = {
        'ts_code': first['ts_code'],
        'stock_name': first['stock_name'],
        'industry': first['industry'],
        'trade_date': first['trade_date'],
        'feature_version': feature_version,
        'model_role': first['model_role'],
        'use_fallback': first['use_fallback'],
        'primary_artifact_dir': first['primary_artifact_dir'],
        'fallback_artifact_dir': first['fallback_artifact_dir'],
        'switch_months': first['switch_months'],
        'split': first['split'],
        'universe_rows': first['universe_rows'],
        'targets': {
            target_name: _compact_stock_target_summary(summary)
            for target_name, summary in target_summaries.items()
        },
    }
    combined_summary['combined_signal'] = _combined_stock_signal(target_summaries)
    combined_summary['warnings'] = _combined_stock_warnings(target_summaries, combined_summary['combined_signal'])

    report_path = None
    if write_report:
        output_path = Path(output_dir) if output_dir else Path(artifacts_dir) / 'stock_diagnostics'
        output_path.mkdir(parents=True, exist_ok=True)
        safe_code = str(ts_code).replace('.', '_')
        report_path = output_path / f'stock_diagnostic_combined_{safe_code}_{trade_date}.json'
        report_path.write_text(json.dumps(combined_summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return {
        'summary': combined_summary,
        'report_path': str(report_path) if report_path else None,
        'target_results': target_results,
    }


def load_stock_diagnostic_frame(
    feature_version='v1',
    trade_date=None,
    feature_columns=None,
    stdout=None,
):
    if not trade_date:
        raise ValueError('trade_date is required.')
    feature_columns = feature_columns or FEATURE_COLUMNS
    metadata_columns = _selected_metadata_columns(feature_columns, DIAGNOSTIC_METADATA_COLUMNS)
    columns = [
        'ts_code',
        'trade_date',
        *metadata_columns,
        'future_ret_20',
        'future_excess_ret_20',
        *feature_columns,
        *(target['column'] for target in TARGETS.values()),
    ]
    columns = _dedupe_preserve_order(columns)
    select_columns = ', '.join(columns)
    sql = f"""
        select {select_columns}
        from model_sample_v1
        where feature_version = %s
          and is_st = false
          and (days_since_list is null or days_since_list >= 120)
          and trade_date = %s
        order by ts_code
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [feature_version, trade_date])
        field_names = [item[0] for item in cursor.description]
        rows = cursor.fetchall()
    frame = pd.DataFrame.from_records(rows, columns=field_names)
    if stdout:
        stdout.write(f'diagnose_quant_stock loaded rows: {len(frame)}')
        stdout.flush()
    return frame


def load_diagnostic_slice_frame(
    feature_version='v1',
    month='202604',
    feature_columns=None,
    max_rows=50000,
    random_state=42,
    require_labels=True,
    stdout=None,
):
    feature_columns = feature_columns or FEATURE_COLUMNS
    metadata_columns = _selected_metadata_columns(feature_columns, DIAGNOSTIC_METADATA_COLUMNS)
    columns = [
        'ts_code',
        'trade_date',
        *metadata_columns,
        'future_ret_20',
        'future_excess_ret_20',
        *feature_columns,
        *(target['column'] for target in TARGETS.values()),
    ]
    columns = _dedupe_preserve_order(columns)
    select_columns = ', '.join(columns)
    required_columns = CORE_REQUIRED_COLUMNS if require_labels else OBSERVATION_REQUIRED_COLUMNS
    required_not_null = ' and '.join(f'{column} is not null' for column in required_columns)
    label_filters = ''
    if require_labels:
        label_filters = "and label_up_20 is not null\n              and label_outperform_20 is not null"
    date_sql = """
        select distinct trade_date
        from model_sample_v1
        where feature_version = %s
        and trade_date like %s
        order by trade_date
    """
    sql = f"""
        select *
        from (
            select
                {select_columns},
                row_number() over (
                    partition by trade_date
                    order by md5(ts_code || %s), ts_code
                ) as row_num
            from model_sample_v1
            where feature_version = %s
              and is_st = false
              and (days_since_list is null or days_since_list >= 120)
              {label_filters}
              and {required_not_null}
              and trade_date = any(%s)
        ) limited_rows
        where row_num <= %s
        order by trade_date, row_num
    """
    with connection.cursor() as cursor:
        cursor.execute(date_sql, [feature_version, f'{month}%'])
        trade_dates = [row[0] for row in cursor.fetchall()]
        if not trade_dates:
            return pd.DataFrame(columns=columns)
        rows_per_date = max(1, int(np.ceil(max_rows / len(trade_dates))))
        cursor.execute(sql, [str(random_state), feature_version, trade_dates, rows_per_date])
        field_names = [item[0] for item in cursor.description]
        rows = cursor.fetchall()

    frame = pd.DataFrame.from_records(rows, columns=field_names)
    if 'row_num' in frame:
        frame = frame.drop(columns=['row_num'])
    if len(frame) > max_rows:
        frame = _balanced_head_by_date(frame, max_rows)
    if stdout:
        stdout.write(f'diagnose_quant_baseline_slice loaded rows: {len(frame)}')
        stdout.flush()
    return frame


def data_quality_summary(feature_version='v1'):
    sql = """
        with sample_dates as (
            select min(trade_date) as min_date, max(trade_date) as max_date
            from model_sample_v1
            where feature_version = %s
        ),
        estimated as (
            select coalesce(reltuples::bigint, 0) as estimated_rows
            from pg_class
            where oid = 'model_sample_v1'::regclass
        ),
        sampled_quality as (
            select
                count(*) as sampled_rows,
                count(*) filter (where days_since_list is null) as sampled_days_since_list_null_rows,
                count(*) filter (where days_since_list is not null and days_since_list < 120) as sampled_new_stock_rows,
                count(*) filter (where label_up_20 is not null and label_outperform_20 is not null) as sampled_labeled_rows
            from model_sample_v1
            where feature_version = %s
              and trade_date in ('20150105', '20200102', '20240102', '20260105')
        )
        select
            sample_dates.min_date,
            sample_dates.max_date,
            estimated.estimated_rows,
            sampled_quality.sampled_rows,
            sampled_quality.sampled_days_since_list_null_rows,
            sampled_quality.sampled_new_stock_rows,
            sampled_quality.sampled_labeled_rows
        from sample_dates, estimated, sampled_quality
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [feature_version, feature_version])
        row = cursor.fetchone()
    estimated_rows = int(row[2] or 0)
    sampled_rows = int(row[3] or 0)
    sampled_days_null_rows = int(row[4] or 0)
    return {
        'min_date': row[0],
        'max_date': row[1],
        'estimated_rows': estimated_rows,
        'sampled_rows': sampled_rows,
        'sampled_days_since_list_null_rows': sampled_days_null_rows,
        'sampled_days_since_list_null_rate': float(sampled_days_null_rows / sampled_rows) if sampled_rows else None,
        'sampled_new_stock_rows': int(row[5] or 0),
        'sampled_labeled_rows': int(row[6] or 0),
    }


def evaluate_split(model, preprocessor, frame, target_column):
    if frame.empty:
        return _empty_metrics()

    x_values = preprocessor.transform(frame)
    probabilities = model.predict_proba(x_values)[:, 1]
    return evaluate_scored_frame(frame, probabilities, target_column)


def evaluate_scored_frame(frame, probabilities, target_column):
    if frame.empty:
        return _empty_metrics()

    y_true = frame[target_column].astype(int)
    result = {
        'rows': int(len(frame)),
        'positive_rate': float(y_true.mean()),
        'auc': _safe_auc(y_true, probabilities),
        'log_loss': _safe_log_loss(y_true, probabilities),
        'brier': float(brier_score_loss(y_true, probabilities)),
    }
    result.update(_decile_metrics(frame, probabilities))
    return result


def _missing_rates(frame, feature_columns=None):
    feature_columns = feature_columns or FEATURE_COLUMNS
    rows = []
    group_columns = ['split']
    for split_name, group in frame.groupby(group_columns, sort=True):
        if isinstance(split_name, tuple):
            split_name = split_name[0]
        for feature in feature_columns:
            rows.append(
                {
                    'scope': 'split',
                    'name': str(split_name),
                    'feature': feature,
                    'factor_group': feature_group(feature),
                    'missing_rate': float(group[feature].isna().mean()),
                }
            )
    for year, group in frame.groupby(frame['trade_date'].str[:4], sort=True):
        for feature in feature_columns:
            rows.append(
                {
                    'scope': 'year',
                    'name': str(year),
                    'feature': feature,
                    'factor_group': feature_group(feature),
                    'missing_rate': float(group[feature].isna().mean()),
                }
            )
    return rows


def rank_ic_by_date(frame, score_column, return_column):
    values = []
    for _, group in frame.groupby('trade_date'):
        if len(group) < 2:
            continue
        if group[score_column].nunique(dropna=True) < 2 or group[return_column].nunique(dropna=True) < 2:
            continue
        corr = group[score_column].rank().corr(group[return_column].rank())
        if pd.notna(corr):
            values.append(float(corr))
    if not values:
        return None
    return float(np.mean(values))


def _write_missing_rates_csv(rows, path):
    pd.DataFrame(rows).sort_values(['scope', 'name', 'missing_rate'], ascending=[True, True, False]).to_csv(
        path,
        index=False,
        encoding='utf-8',
    )


def _write_year_metrics_csv(targets, path):
    rows = []
    for target_name, target_report in targets.items():
        for year, metrics in target_report['by_year'].items():
            rows.append(
                {
                    'target': target_name,
                    'year': year,
                    'rows': metrics['rows'],
                    'positive_rate': metrics['positive_rate'],
                    'auc': metrics['auc'],
                    'rank_ic_mean': metrics['rank_ic_mean'],
                    'rank_ic_excess_mean': metrics['rank_ic_excess_mean'],
                    'top_decile_future_excess_ret_20_mean': metrics['top_decile_future_excess_ret_20_mean'],
                    'bottom_decile_future_excess_ret_20_mean': metrics['bottom_decile_future_excess_ret_20_mean'],
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False, encoding='utf-8')


def _write_month_metrics_csv(targets, path):
    rows = []
    for target_name, target_report in targets.items():
        for month, metrics in target_report['by_month'].items():
            rows.append(
                {
                    'target': target_name,
                    'month': month,
                    'rows': metrics['rows'],
                    'positive_rate': metrics['positive_rate'],
                    'auc': metrics['auc'],
                    'rank_ic_mean': metrics['rank_ic_mean'],
                    'rank_ic_excess_mean': metrics['rank_ic_excess_mean'],
                    'top_decile_future_excess_ret_20_mean': metrics['top_decile_future_excess_ret_20_mean'],
                    'bottom_decile_future_excess_ret_20_mean': metrics['bottom_decile_future_excess_ret_20_mean'],
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False, encoding='utf-8')


def _write_regime_blend_month_csv(by_month, path):
    rows = []
    for month, metrics in by_month.items():
        rows.append(
            {
                'month': month,
                'rows': metrics['rows'],
                'positive_rate': metrics['positive_rate'],
                'auc': metrics['auc'],
                'rank_ic_mean': metrics['rank_ic_mean'],
                'rank_ic_excess_mean': metrics['rank_ic_excess_mean'],
                'top_decile_future_excess_ret_20_mean': metrics['top_decile_future_excess_ret_20_mean'],
                'bottom_decile_future_excess_ret_20_mean': metrics['bottom_decile_future_excess_ret_20_mean'],
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False, encoding='utf-8')


def _load_target_payload(artifacts_dir, target_name):
    target_config = TARGETS[target_name]
    model_path = Path(artifacts_dir) / target_config['model_file']
    if not model_path.exists():
        raise FileNotFoundError(f'Model artifact not found: {model_path}')
    return joblib.load(model_path)


def _predict_uncalibrated_payload_scores(payload, frame):
    model = payload['model']
    preprocessor = payload['preprocessor']
    return model.predict_proba(preprocessor.transform(frame))[:, 1]


def _predict_payload_scores(payload, frame):
    raw_scores = _predict_uncalibrated_payload_scores(payload, frame)
    return _apply_score_calibrator(payload, raw_scores)


def _apply_score_calibrator(payload, raw_scores):
    calibrator = payload.get('calibrator')
    if calibrator is None:
        return raw_scores
    method = payload.get('calibration_method')
    if method == 'sigmoid':
        return calibrator.predict_proba(np.asarray(raw_scores).reshape(-1, 1))[:, 1]
    if method == 'isotonic':
        return calibrator.predict(np.asarray(raw_scores))
    raise ValueError(f'Unknown calibration_method={method}.')


def _fit_score_calibrator(raw_scores, y_true, method='sigmoid'):
    raw_scores = np.asarray(raw_scores).reshape(-1, 1)
    if method == 'sigmoid':
        calibrator = LogisticRegression(solver='lbfgs', random_state=42)
        calibrator.fit(raw_scores, y_true)
        return calibrator
    if method == 'isotonic':
        calibrator = IsotonicRegression(out_of_bounds='clip')
        calibrator.fit(raw_scores.ravel(), y_true)
        return calibrator
    raise ValueError(f'Unknown calibration method={method}.')


def _calibration_bin_rows(target_name, split_name, y_true, probabilities, bins=10):
    y_true = np.asarray(y_true)
    probabilities = np.asarray(probabilities)
    if len(probabilities) == 0:
        return []
    order = np.argsort(probabilities)
    rows = []
    for bin_index, indexes in enumerate(np.array_split(order, min(bins, len(order))), start=1):
        if len(indexes) == 0:
            continue
        bin_probabilities = probabilities[indexes]
        bin_y = y_true[indexes]
        rows.append(
            {
                'target': target_name,
                'split': split_name,
                'bin': bin_index,
                'rows': int(len(indexes)),
                'score_min': float(np.min(bin_probabilities)),
                'score_max': float(np.max(bin_probabilities)),
                'mean_predicted_probability': float(np.mean(bin_probabilities)),
                'observed_positive_rate': float(np.mean(bin_y)),
                'calibration_error': float(np.mean(bin_probabilities) - np.mean(bin_y)),
            }
        )
    return rows


def _paper_summary_by_group(daily, group_column):
    if daily.empty:
        return []
    rows = []
    for group_value, group in daily.groupby(group_column, sort=True):
        returns = pd.to_numeric(group['portfolio_future_ret_20'], errors='coerce').dropna()
        excess = pd.to_numeric(group['portfolio_future_excess_ret_20'], errors='coerce').dropna()
        rows.append(
            {
                group_column: str(group_value),
                'trade_dates': int(len(group)),
                'avg_selected_rows': _nullable_mean(group['selected_rows']),
                'avg_portfolio_future_ret_20': _nullable_mean(group['portfolio_future_ret_20']),
                'avg_portfolio_future_excess_ret_20': _nullable_mean(group['portfolio_future_excess_ret_20']),
                'avg_universe_future_ret_20': _nullable_mean(group['universe_future_ret_20']),
                'avg_universe_future_excess_ret_20': _nullable_mean(group['universe_future_excess_ret_20']),
                'hit_rate_up': _nullable_mean(group['hit_rate_up']),
                'hit_rate_outperform': _nullable_mean(group['hit_rate_outperform']),
                'fallback_trade_dates': int(group['use_fallback'].sum()),
                'overlap_compounded_return_20': _compounded_return(returns),
                'overlap_compounded_excess_return_20': _compounded_return(excess),
            }
        )
    return rows


def _compounded_return(values):
    if len(values) == 0:
        return None
    return float(np.prod(1 + values.to_numpy(dtype=float)) - 1)


def _auto_switch_months(
    frame,
    auto_switch_rule,
    ma60_bias_threshold=-0.04,
    ma60_bias_floor=None,
    ret20_rebound_threshold=-0.04,
    ret20_rebound_ceiling=None,
):
    if auto_switch_rule not in {'weak_ma60', 'rebound_after_weakness'}:
        raise ValueError(f'Unknown auto_switch_rule={auto_switch_rule}.')
    if 'ma60_bias' not in frame:
        raise ValueError(f'ma60_bias is required for auto_switch_rule={auto_switch_rule}.')
    if auto_switch_rule == 'rebound_after_weakness' and 'ret_20' not in frame:
        raise ValueError('ret_20 is required for auto_switch_rule=rebound_after_weakness.')

    report = []
    switch_months = []
    for month, group in frame.groupby(frame['trade_date'].str[:6], sort=True):
        ma60_bias_median = _nullable_median(group['ma60_bias'])
        ret_20_median = _nullable_median(group['ret_20']) if 'ret_20' in group else None
        use_fallback = _auto_switch_month_decision(
            auto_switch_rule=auto_switch_rule,
            ma60_bias_median=ma60_bias_median,
            ret_20_median=ret_20_median,
            ma60_bias_threshold=ma60_bias_threshold,
            ma60_bias_floor=ma60_bias_floor,
            ret20_rebound_threshold=ret20_rebound_threshold,
            ret20_rebound_ceiling=ret20_rebound_ceiling,
        )
        if use_fallback:
            switch_months.append(str(month))
        report.append(
            {
                'month': str(month),
                'rows': int(len(group)),
                'ma60_bias_median': ma60_bias_median,
                'ret_20_median': ret_20_median,
                'use_fallback': bool(use_fallback),
            }
        )
    return switch_months, report


def _auto_switch_months_from_database(
    feature_version,
    auto_switch_rule,
    ma60_bias_threshold=-0.04,
    ma60_bias_floor=None,
    ret20_rebound_threshold=-0.04,
    ret20_rebound_ceiling=None,
):
    if auto_switch_rule not in {'weak_ma60', 'rebound_after_weakness'}:
        raise ValueError(f'Unknown auto_switch_rule={auto_switch_rule}.')

    min_date = min(start_date for start_date, _ in SPLITS.values())
    max_date = max(end_date for _, end_date in SPLITS.values())
    sql = """
        select
            substr(trade_date, 1, 6) as month,
            count(*) as rows,
            percentile_cont(0.5) within group (order by ma60_bias) as ma60_bias_median,
            percentile_cont(0.5) within group (order by ret_20) as ret_20_median
        from model_sample_v1
        where feature_version = %s
          and is_st = false
          and (days_since_list is null or days_since_list >= 120)
          and ma60_bias is not null
          and ret_20 is not null
          and trade_date between %s and %s
        group by substr(trade_date, 1, 6)
        order by month
    """
    report = []
    switch_months = []
    with connection.cursor() as cursor:
        cursor.execute(sql, [feature_version, min_date, max_date])
        for month, rows, ma60_bias_median, ret_20_median in cursor.fetchall():
            ma60_bias_median = float(ma60_bias_median) if ma60_bias_median is not None else None
            ret_20_median = float(ret_20_median) if ret_20_median is not None else None
            use_fallback = _auto_switch_month_decision(
                auto_switch_rule=auto_switch_rule,
                ma60_bias_median=ma60_bias_median,
                ret_20_median=ret_20_median,
                ma60_bias_threshold=ma60_bias_threshold,
                ma60_bias_floor=ma60_bias_floor,
                ret20_rebound_threshold=ret20_rebound_threshold,
                ret20_rebound_ceiling=ret20_rebound_ceiling,
            )
            if use_fallback:
                switch_months.append(str(month))
            report.append(
                {
                    'month': str(month),
                    'rows': int(rows),
                    'ma60_bias_median': ma60_bias_median,
                    'ret_20_median': ret_20_median,
                    'use_fallback': bool(use_fallback),
                }
            )
    return switch_months, report


def _auto_switch_month_decision(
    auto_switch_rule,
    ma60_bias_median,
    ret_20_median,
    ma60_bias_threshold=-0.04,
    ma60_bias_floor=None,
    ret20_rebound_threshold=-0.04,
    ret20_rebound_ceiling=None,
):
    if auto_switch_rule == 'weak_ma60':
        return ma60_bias_median is not None and ma60_bias_median <= ma60_bias_threshold
    return (
        ma60_bias_median is not None
        and ret_20_median is not None
        and ma60_bias_median <= ma60_bias_threshold
        and (ma60_bias_floor is None or ma60_bias_median >= ma60_bias_floor)
        and ret_20_median >= ret20_rebound_threshold
        and (ret20_rebound_ceiling is None or ret_20_median <= ret20_rebound_ceiling)
    )


def _stock_feature_contributions(payload, frame, transformed, row_position):
    model = payload.get('model')
    feature_columns = payload.get('feature_columns') or FEATURE_COLUMNS
    coefficients = getattr(model, 'coef_', None)
    if coefficients is None or len(coefficients) == 0:
        return {'positive': [], 'negative': [], 'factor_groups': []}

    row = frame.iloc[row_position]
    transformed_row = transformed[row_position]
    rows = []
    for feature, transformed_value, coefficient in zip(feature_columns, transformed_row, coefficients[0]):
        contribution = float(transformed_value * coefficient)
        rows.append(
            {
                'feature': feature,
                'factor_group': feature_group(feature),
                'raw_value': _json_value(row.get(feature)),
                'transformed_value': float(transformed_value),
                'coefficient': float(coefficient),
                'contribution': contribution,
            }
        )

    positive = sorted([item for item in rows if item['contribution'] > 0], key=lambda item: item['contribution'], reverse=True)
    negative = sorted([item for item in rows if item['contribution'] < 0], key=lambda item: item['contribution'])
    factor_groups = []
    for group in sorted({item['factor_group'] for item in rows}):
        group_rows = [item for item in rows if item['factor_group'] == group]
        factor_groups.append(
            {
                'factor_group': group,
                'contribution': float(sum(item['contribution'] for item in group_rows)),
                'abs_contribution': float(sum(abs(item['contribution']) for item in group_rows)),
            }
        )
    factor_groups.sort(key=lambda item: item['abs_contribution'], reverse=True)
    return {
        'positive': positive,
        'negative': negative,
        'factor_groups': factor_groups,
    }


def _score_cohort(score_pct_rank):
    if score_pct_rank >= 0.9:
        return 'top'
    if score_pct_rank <= 0.1:
        return 'bottom'
    if score_pct_rank >= 0.7:
        return 'upper'
    if score_pct_rank <= 0.3:
        return 'lower'
    return 'middle'


def _stock_diagnostic_warnings(model_role, score_pct_rank, split_name, missing_feature_count, feature_count):
    warnings = []
    if model_role == 'fallback':
        warnings.append('fallback_model_used: regime-specific fallback is experimental and should be interpreted with extra caution')
    if split_name == 'rolling_2026':
        warnings.append('rolling_validation_window: this date belongs to the 2026 rolling validation period')
    elif split_name is None:
        warnings.append('outside_validation_windows: this date is outside the configured training/validation/test windows')
    if 0.4 <= score_pct_rank <= 0.6:
        warnings.append('neutral_score: cross-sectional percentile is near the middle of the universe')
    if feature_count and missing_feature_count / feature_count >= 0.25:
        warnings.append('many_missing_features: at least 25 percent of model features were missing before imputation')
    return warnings


def _compact_stock_target_summary(summary):
    return {
        'score': summary['score'],
        'score_pct_rank': summary['score_pct_rank'],
        'score_decile': summary['score_decile'],
        'cohort': summary['cohort'],
        'observed': summary['observed'],
        'top_positive_contributions': summary['top_positive_contributions'][:5],
        'top_negative_contributions': summary['top_negative_contributions'][:5],
        'factor_group_contributions': summary['factor_group_contributions'],
    }


def _combined_stock_signal(target_summaries):
    up = target_summaries.get('up', {})
    outperform = target_summaries.get('outperform', {})
    up_rank = up.get('score_pct_rank')
    outperform_rank = outperform.get('score_pct_rank')
    up_decile = up.get('score_decile')
    outperform_decile = outperform.get('score_decile')

    signal = {
        'label': 'insufficient_data',
        'description': 'Missing one or more target scores.',
        'up_score_pct_rank': up_rank,
        'outperform_score_pct_rank': outperform_rank,
        'up_decile': up_decile,
        'outperform_decile': outperform_decile,
        'confidence': 'low',
    }
    if up_rank is None or outperform_rank is None:
        return signal

    if up_rank >= 0.8 and outperform_rank >= 0.8:
        signal.update(
            {
                'label': 'strong_positive',
                'description': 'Both absolute upside and relative outperformance scores are high.',
                'confidence': 'medium',
            }
        )
    elif up_rank >= 0.8 and outperform_rank < 0.5:
        signal.update(
            {
                'label': 'absolute_upside_but_weak_relative',
                'description': 'Absolute upside score is high, but relative outperformance score is weak.',
                'confidence': 'low',
            }
        )
    elif up_rank < 0.5 and outperform_rank >= 0.8:
        signal.update(
            {
                'label': 'relative_resilience_without_absolute_upside',
                'description': 'Relative score is high, but absolute upside score is weak.',
                'confidence': 'low',
            }
        )
    elif up_rank <= 0.2 and outperform_rank <= 0.2:
        signal.update(
            {
                'label': 'weak_negative',
                'description': 'Both absolute upside and relative outperformance scores are low.',
                'confidence': 'medium',
            }
        )
    else:
        signal.update(
            {
                'label': 'mixed_or_neutral',
                'description': 'Target scores are not aligned enough for a strong directional signal.',
                'confidence': 'low',
            }
        )

    if up_decile is not None and outperform_decile is not None:
        signal['decile_gap'] = int(up_decile) - int(outperform_decile)
    return signal


def _combined_stock_warnings(target_summaries, combined_signal):
    warnings = []
    for summary in target_summaries.values():
        for warning in summary.get('warnings', []):
            if warning not in warnings:
                warnings.append(warning)

    if abs(int(combined_signal.get('decile_gap') or 0)) >= 3:
        warnings.append('target_disagreement: up and outperform scores are materially different')
    if combined_signal.get('confidence') == 'low':
        warnings.append('low_combined_confidence: combined signal should not be used as a standalone recommendation')

    observed_labels = {
        target_name: summary.get('observed', {}).get('label')
        for target_name, summary in target_summaries.items()
    }
    if observed_labels.get('up') is not None and observed_labels.get('outperform') is not None:
        if bool(observed_labels['up']) != bool(observed_labels['outperform']):
            warnings.append('observed_label_conflict: historical up and outperform labels disagree for this sample')
    return warnings


def _json_value(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _diagnostic_cohort_summary(group, target_column):
    return {
        'rows': int(len(group)),
        'positive_rate': _nullable_mean(group[target_column].astype(float)),
        'score_mean': _nullable_mean(group['score']),
        'score_min': _nullable_mean(group['score'].min(skipna=True) if not group.empty else pd.Series(dtype=float)),
        'score_max': _nullable_mean(group['score'].max(skipna=True) if not group.empty else pd.Series(dtype=float)),
        'future_ret_20_mean': _nullable_mean(group['future_ret_20']),
        'future_excess_ret_20_mean': _nullable_mean(group['future_excess_ret_20']),
        'total_mv_median': _nullable_median(group['total_mv']) if 'total_mv' in group else None,
        'circ_mv_median': _nullable_median(group['circ_mv']) if 'circ_mv' in group else None,
        'days_since_list_median': _nullable_median(group['days_since_list']) if 'days_since_list' in group else None,
    }


def _top_minus_bottom_summary(cohorts):
    top = cohorts.get('top') or {}
    bottom = cohorts.get('bottom') or {}
    keys = [
        'positive_rate',
        'score_mean',
        'future_ret_20_mean',
        'future_excess_ret_20_mean',
        'total_mv_median',
        'circ_mv_median',
        'days_since_list_median',
    ]
    return {
        key: top.get(key) - bottom.get(key)
        for key in keys
        if top.get(key) is not None and bottom.get(key) is not None
    }


def _diagnostic_industry_rows(scored):
    rows = []
    cohort_totals = scored['cohort'].value_counts().to_dict()
    for (cohort, industry), group in scored.groupby(['cohort', 'industry'], dropna=False, sort=True):
        rows.append(
            {
                'cohort': cohort,
                'industry': industry,
                'rows': int(len(group)),
                'cohort_share': float(len(group) / cohort_totals.get(cohort, len(group))),
                'score_mean': _nullable_mean(group['score']),
                'future_ret_20_mean': _nullable_mean(group['future_ret_20']),
                'future_excess_ret_20_mean': _nullable_mean(group['future_excess_ret_20']),
            }
        )
    return rows


def _diagnostic_feature_rows(scored, feature_columns):
    rows = []
    cohort_groups = {cohort: group for cohort, group in scored.groupby('cohort', sort=True)}
    top = cohort_groups.get('top')
    bottom = cohort_groups.get('bottom')
    for feature in feature_columns:
        if feature not in scored:
            continue
        row = {
            'feature': feature,
            'factor_group': feature_group(feature),
        }
        for cohort, group in cohort_groups.items():
            row[f'{cohort}_mean'] = _nullable_mean(pd.to_numeric(group[feature], errors='coerce'))
        if top is not None and bottom is not None:
            top_mean = row.get('top_mean')
            bottom_mean = row.get('bottom_mean')
            row['top_minus_bottom_mean'] = (
                top_mean - bottom_mean
                if top_mean is not None and bottom_mean is not None
                else None
            )
        rows.append(row)
    return sorted(
        rows,
        key=lambda row: abs(row.get('top_minus_bottom_mean') or 0),
        reverse=True,
    )


def _decile_metrics(frame, probabilities):
    scored = frame[['trade_date', 'future_ret_20', 'future_excess_ret_20']].copy()
    scored['score'] = probabilities
    scored['score_pct_rank'] = scored.groupby('trade_date')['score'].rank(method='first', pct=True)
    top = scored[scored['score_pct_rank'] >= 0.9]
    bottom = scored[scored['score_pct_rank'] <= 0.1]

    return {
        'all_future_ret_20_mean': _nullable_mean(scored['future_ret_20']),
        'all_future_excess_ret_20_mean': _nullable_mean(scored['future_excess_ret_20']),
        'top_decile_rows': int(len(top)),
        'bottom_decile_rows': int(len(bottom)),
        'top_decile_future_ret_20_mean': _nullable_mean(top['future_ret_20']),
        'bottom_decile_future_ret_20_mean': _nullable_mean(bottom['future_ret_20']),
        'top_decile_future_excess_ret_20_mean': _nullable_mean(top['future_excess_ret_20']),
        'bottom_decile_future_excess_ret_20_mean': _nullable_mean(bottom['future_excess_ret_20']),
        'rank_ic_mean': rank_ic_by_date(scored, 'score', 'future_ret_20'),
        'rank_ic_excess_mean': rank_ic_by_date(scored, 'score', 'future_excess_ret_20'),
    }


def _cap_rows_per_split(chunk, existing_frames, max_rows_per_split):
    existing_counts = {name: 0 for name in SPLITS}
    for frame in existing_frames:
        counts = frame['split'].value_counts()
        for split_name, count in counts.items():
            existing_counts[split_name] += int(count)

    capped_parts = []
    for split_name, split_chunk in chunk.groupby('split', sort=False):
        remaining = max_rows_per_split - existing_counts.get(split_name, 0)
        if remaining > 0:
            capped_parts.append(split_chunk.head(remaining))
    if not capped_parts:
        return chunk.iloc[0:0]
    return pd.concat(capped_parts, ignore_index=True)


def _all_split_caps_reached(frames, max_rows_per_split):
    if not frames:
        return False
    combined = pd.concat(frames, ignore_index=True)
    counts = combined['split'].value_counts()
    return all(int(counts.get(split_name, 0)) >= max_rows_per_split for split_name in SPLITS)


def _evenly_sampled_values(values, target_rows):
    if not values:
        return []
    target_dates = max(1, min(len(values), int(np.ceil(target_rows / 1000))))
    if target_dates >= len(values):
        return values
    indexes = np.linspace(0, len(values) - 1, num=target_dates, dtype=int)
    return [values[index] for index in sorted(set(indexes))]


def _balanced_head_by_date(frame, target_rows):
    parts = []
    remaining = target_rows
    grouped = list(frame.groupby('trade_date', sort=True))
    for index, (_, group) in enumerate(grouped):
        groups_left = len(grouped) - index
        take = min(len(group), int(np.ceil(remaining / groups_left)))
        parts.append(group.head(take))
        remaining -= take
        if remaining <= 0:
            break
    return pd.concat(parts, ignore_index=True)


def _safe_auc(y_true, probabilities):
    if y_true.nunique() < 2:
        return None
    return float(roc_auc_score(y_true, probabilities))


def _safe_log_loss(y_true, probabilities):
    return float(log_loss(y_true, probabilities, labels=[0, 1]))


def _passes_baseline(target_metrics):
    validation = target_metrics['validation']
    test = target_metrics['test']
    rolling = target_metrics['rolling_2026']
    return bool(
        _metric_gt(validation['auc'], 0.52)
        and _metric_gt(test['auc'], 0.52)
        and _metric_gt(
            validation['top_decile_future_excess_ret_20_mean'],
            validation['all_future_excess_ret_20_mean'],
        )
        and _metric_gt(
            test['top_decile_future_excess_ret_20_mean'],
            test['all_future_excess_ret_20_mean'],
        )
        and _metric_gt(
            rolling['top_decile_future_excess_ret_20_mean'],
            rolling['all_future_excess_ret_20_mean'],
        )
        and _metric_gt(
            rolling['top_decile_future_excess_ret_20_mean'],
            rolling['bottom_decile_future_excess_ret_20_mean'],
        )
        and rolling['rank_ic_excess_mean'] is not None
        and rolling['rank_ic_excess_mean'] >= -0.005
    )


def _metric_gt(left, right):
    return left is not None and right is not None and left > right


def _time_decay_weights(frame, half_life_days):
    if not half_life_days:
        return None
    if half_life_days <= 0:
        raise ValueError('time_decay_half_life_days must be positive.')

    trade_dates = pd.to_datetime(frame['trade_date'], format='%Y%m%d')
    max_date = trade_dates.max()
    age_days = (max_date - trade_dates).dt.days.astype(float)
    weights = np.power(0.5, age_days / float(half_life_days))
    mean_weight = weights.mean()
    if mean_weight and not pd.isna(mean_weight):
        weights = weights / mean_weight
    return weights.to_numpy()


def _nullable_mean(series):
    if not hasattr(series, 'mean'):
        if pd.isna(series):
            return None
        return float(series)
    value = series.mean()
    if pd.isna(value):
        return None
    return float(value)


def _nullable_median(series):
    value = pd.to_numeric(series, errors='coerce').median()
    if pd.isna(value):
        return None
    return float(value)


def _dedupe_preserve_order(values):
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _empty_metrics():
    return {
        'rows': 0,
        'positive_rate': None,
        'auc': None,
        'log_loss': None,
        'brier': None,
        'all_future_ret_20_mean': None,
        'all_future_excess_ret_20_mean': None,
        'top_decile_rows': 0,
        'bottom_decile_rows': 0,
        'top_decile_future_ret_20_mean': None,
        'bottom_decile_future_ret_20_mean': None,
        'top_decile_future_excess_ret_20_mean': None,
        'bottom_decile_future_excess_ret_20_mean': None,
        'rank_ic_mean': None,
        'rank_ic_excess_mean': None,
    }
