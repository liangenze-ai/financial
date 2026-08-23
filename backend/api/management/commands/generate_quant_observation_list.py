from datetime import datetime

from django.core.management.base import BaseCommand

from api.services.quant_baseline import TARGETS, generate_quant_observation_list
from config.logging_setup import logger


class Command(BaseCommand):
    help = 'Generate a month-level quant observation list, including unlabeled rows.'

    def add_arguments(self, parser):
        parser.add_argument('--artifacts-dir', required=True, help='Primary model artifact directory.')
        parser.add_argument('--fallback-artifacts-dir', help='Optional fallback artifact directory used for switch months.')
        parser.add_argument(
            '--switch-months',
            default='',
            help='Comma-separated YYYYMM months that should use the fallback model when provided.',
        )
        parser.add_argument('--feature-version', default='v1', help='Feature version stored in model_sample_v1.')
        parser.add_argument('--month', default=datetime.now().strftime('%Y%m'), help='Target month formatted as YYYYMM.')
        parser.add_argument('--target', default='all', choices=['all', *TARGETS.keys()], help='Target model to score.')
        parser.add_argument('--max-rows', type=int, default=50000, help='Maximum rows sampled from the month.')
        parser.add_argument('--random-state', type=int, default=42, help='Random seed for stable per-date sampling.')
        parser.add_argument('--top-quantile', type=float, default=0.1, help='Top score fraction selected each date.')
        parser.add_argument('--output-dir', help='Directory for observation list files.')

    def handle(self, *args, **options):
        switch_months = [
            month.strip()
            for month in options['switch_months'].split(',')
            if month.strip()
        ]
        logger.info(
            'generate_quant_observation_list started: artifacts_dir={}, fallback_artifacts_dir={}, switch_months={}, month={}, target={}, max_rows={}, top_quantile={}',
            options['artifacts_dir'],
            options.get('fallback_artifacts_dir'),
            switch_months,
            options['month'],
            options['target'],
            options['max_rows'],
            options['top_quantile'],
        )
        result = generate_quant_observation_list(
            artifacts_dir=options['artifacts_dir'],
            fallback_artifacts_dir=options.get('fallback_artifacts_dir'),
            switch_months=switch_months,
            feature_version=options['feature_version'],
            month=options['month'],
            target_name=options['target'],
            max_rows=options['max_rows'],
            random_state=options['random_state'],
            top_quantile=options['top_quantile'],
            output_dir=options.get('output_dir'),
            stdout=self.stdout,
        )
        summary = result['summary']

        self.stdout.write(self.style.SUCCESS(f'observation_outputs: {result["output_prefix"]}_*.csv/json'))
        self.stdout.write(
            f'model_role={summary["model_role"]}, '
            f'use_fallback={summary["use_fallback"]}, '
            f'rows={summary["rows"]}, '
            f'trade_dates={len(summary["trade_dates"])}'
        )
        self.stdout.write(f'split_counts: {summary["split_counts"]}')
        self.stdout.write(f'cohort_counts: {summary["cohort_counts"]}')
        self.stdout.write('combined_signal_counts:')
        for label, count in summary.get('combined_signal_counts', {}).items():
            self.stdout.write(f'  {label}: {count}')
        self.stdout.write('target_summaries:')
        for target_name, target_summary in summary['target_summaries'].items():
            self.stdout.write(
                f'  {target_name}: rows={target_summary["rows"]}, '
                f'score_mean={_fmt(target_summary["score_mean"])}, '
                f'percent_rank_mean={_fmt(target_summary["score_pct_rank_mean"])}, '
                f'top_rows={target_summary["top_rows"]}, '
                f'bottom_rows={target_summary["bottom_rows"]}'
            )
        logger.info('generate_quant_observation_list finished: output_prefix={}', result['output_prefix'])


def _fmt(value):
    if value is None:
        return 'None'
    if isinstance(value, float):
        return f'{value:.6f}'
    return str(value)
