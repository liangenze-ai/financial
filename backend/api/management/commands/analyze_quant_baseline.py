from django.core.management.base import BaseCommand

from api.services.quant_baseline import TARGETS, analyze_quant_baseline
from config.logging_setup import logger


class Command(BaseCommand):
    help = 'Analyze trained quant baseline artifacts by split, year, missing rates, and data quality.'

    def add_arguments(self, parser):
        parser.add_argument('--artifacts-dir', required=True, help='Directory containing trained baseline artifacts.')
        parser.add_argument('--feature-version', default='v1', help='Feature version stored in model_sample_v1.')
        parser.add_argument(
            '--max-rows-per-split',
            type=int,
            default=50000,
            help='Rows sampled from each split for analysis.',
        )

    def handle(self, *args, **options):
        logger.info(
            'analyze_quant_baseline started: artifacts_dir={}, feature_version={}, max_rows_per_split={}',
            options['artifacts_dir'],
            options['feature_version'],
            options['max_rows_per_split'],
        )
        report = analyze_quant_baseline(
            artifacts_dir=options['artifacts_dir'],
            feature_version=options['feature_version'],
            max_rows_per_split=options['max_rows_per_split'],
            stdout=self.stdout,
        )

        self.stdout.write(self.style.SUCCESS(f'analysis_report: {options["artifacts_dir"]}\\analysis_report.json'))
        self.stdout.write(f'split_counts: {report["split_counts"]}')
        self.stdout.write(f'data_quality: {report["data_quality"]}')
        for target_name in TARGETS:
            self.stdout.write('')
            self.stdout.write(f'target={target_name}')
            for year, metrics in report['targets'][target_name]['by_year'].items():
                self.stdout.write(
                    f'  {year}: '
                    f'rows={metrics["rows"]}, '
                    f'positive_rate={_fmt(metrics["positive_rate"])}, '
                    f'auc={_fmt(metrics["auc"])}, '
                    f'rank_ic={_fmt(metrics["rank_ic_mean"])}, '
                    f'top_excess={_fmt(metrics["top_decile_future_excess_ret_20_mean"])}, '
                    f'bottom_excess={_fmt(metrics["bottom_decile_future_excess_ret_20_mean"])}'
                )
            self.stdout.write('  rolling_2026_by_month:')
            for month, metrics in report['targets'][target_name]['by_month'].items():
                if not month.startswith('2026'):
                    continue
                self.stdout.write(
                    f'    {month}: '
                    f'rows={metrics["rows"]}, '
                    f'positive_rate={_fmt(metrics["positive_rate"])}, '
                    f'auc={_fmt(metrics["auc"])}, '
                    f'rank_ic={_fmt(metrics["rank_ic_mean"])}, '
                    f'top_excess={_fmt(metrics["top_decile_future_excess_ret_20_mean"])}, '
                    f'bottom_excess={_fmt(metrics["bottom_decile_future_excess_ret_20_mean"])}'
                )
        logger.info('analyze_quant_baseline finished: artifacts_dir={}', options['artifacts_dir'])


def _fmt(value):
    if value is None:
        return 'None'
    if isinstance(value, float):
        return f'{value:.6f}'
    return str(value)
