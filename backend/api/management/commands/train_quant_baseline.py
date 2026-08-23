from django.core.management.base import BaseCommand

from api.services.quant_baseline import FEATURE_COLUMNS, TARGETS, train_quant_baseline
from config.logging_setup import logger


class Command(BaseCommand):
    help = 'Train explainable Elastic Net baseline models from model_sample_v1.'

    def add_arguments(self, parser):
        parser.add_argument('--feature-version', default='v1', help='Feature version stored in model_sample_v1.')
        parser.add_argument('--output-dir', help='Directory for model artifacts. Defaults to backend/artifacts/quant_baseline_v1.')
        parser.add_argument('--chunk-size', type=int, default=100000, help='Rows fetched per database batch.')
        parser.add_argument('--random-state', type=int, default=42, help='Random seed for model training.')
        parser.add_argument(
            '--max-rows-per-split',
            type=int,
            help='Optional cap for smoke tests. Reads at most this many rows from each split.',
        )
        parser.add_argument(
            '--exclude-limit-flags',
            action='store_true',
            help='Exclude is_limit_up/is_limit_down from the feature set for robustness checks.',
        )
        parser.add_argument(
            '--exclude-features',
            default='',
            help='Comma-separated feature names to exclude from the feature set for robustness checks.',
        )
        parser.add_argument(
            '--time-decay-half-life-days',
            type=float,
            help='Optional train-split time decay half-life in calendar days. Recent train rows receive higher weight.',
        )
        parser.add_argument(
            '--rank-features-by-date',
            action='store_true',
            help='Convert numeric features to per-trade-date percentile ranks before impute/winsorize/scale.',
        )
        parser.add_argument(
            '--neutralize-by-industry-size',
            action='store_true',
            help='Within each trade date, industry-demean numeric features and regress out log(total_mv).',
        )

    def handle(self, *args, **options):
        exclude_features = [
            feature.strip()
            for feature in options['exclude_features'].split(',')
            if feature.strip()
        ]
        unknown_features = sorted(set(exclude_features) - set(FEATURE_COLUMNS))
        if unknown_features:
            raise ValueError(f'Unknown features in --exclude-features: {", ".join(unknown_features)}')

        logger.info(
            'train_quant_baseline started: feature_version={}, output_dir={}, chunk_size={}, random_state={}, max_rows_per_split={}, exclude_limit_flags={}, exclude_features={}, time_decay_half_life_days={}, rank_features_by_date={}, neutralize_by_industry_size={}',
            options['feature_version'],
            options.get('output_dir'),
            options['chunk_size'],
            options['random_state'],
            options.get('max_rows_per_split'),
            options['exclude_limit_flags'],
            exclude_features,
            options.get('time_decay_half_life_days'),
            options['rank_features_by_date'],
            options['neutralize_by_industry_size'],
        )
        result = train_quant_baseline(
            feature_version=options['feature_version'],
            output_dir=options.get('output_dir'),
            chunk_size=options['chunk_size'],
            random_state=options['random_state'],
            max_rows_per_split=options.get('max_rows_per_split'),
            exclude_limit_flags=options['exclude_limit_flags'],
            exclude_features=exclude_features,
            time_decay_half_life_days=options.get('time_decay_half_life_days'),
            rank_features_by_date=options['rank_features_by_date'],
            neutralize_by_industry_size=options['neutralize_by_industry_size'],
            stdout=self.stdout,
        )
        metrics = result['metrics']

        self.stdout.write(self.style.SUCCESS(f'train_quant_baseline artifacts: {result["output_dir"]}'))
        self.stdout.write(f'split_counts: {metrics["split_counts"]}')
        for target_name in TARGETS:
            self.stdout.write('')
            self.stdout.write(f'target={target_name}, baseline_pass={metrics["targets"][target_name]["baseline_pass"]}')
            for split_name, split_metrics in metrics['targets'][target_name].items():
                if split_name == 'baseline_pass':
                    continue
                self.stdout.write(
                    f'  {split_name}: '
                    f'rows={split_metrics["rows"]}, '
                    f'positive_rate={_fmt(split_metrics["positive_rate"])}, '
                    f'auc={_fmt(split_metrics["auc"])}, '
                    f'log_loss={_fmt(split_metrics["log_loss"])}, '
                    f'brier={_fmt(split_metrics["brier"])}, '
                    f'top_excess={_fmt(split_metrics["top_decile_future_excess_ret_20_mean"])}, '
                    f'bottom_excess={_fmt(split_metrics["bottom_decile_future_excess_ret_20_mean"])}, '
                    f'rank_ic={_fmt(split_metrics["rank_ic_mean"])}, '
                    f'rank_ic_excess={_fmt(split_metrics["rank_ic_excess_mean"])}'
                )

        logger.info('train_quant_baseline finished: output_dir={}', result['output_dir'])


def _fmt(value):
    if value is None:
        return 'None'
    if isinstance(value, float):
        return f'{value:.6f}'
    return str(value)
