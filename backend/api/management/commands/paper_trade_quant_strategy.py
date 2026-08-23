from django.core.management.base import BaseCommand

from api.services.quant_baseline import TARGETS, paper_trade_quant_strategy
from config.logging_setup import logger


class Command(BaseCommand):
    help = 'Run a paper-trading style top-quantile validation report for quant baseline artifacts.'

    def add_arguments(self, parser):
        parser.add_argument('--artifacts-dir', required=True, help='Primary model artifact directory.')
        parser.add_argument('--fallback-artifacts-dir', help='Optional fallback artifact directory used for switch months.')
        parser.add_argument(
            '--switch-months',
            default='',
            help='Comma-separated YYYYMM months that should use the fallback model when provided.',
        )
        parser.add_argument('--feature-version', default='v1', help='Feature version stored in model_sample_v1.')
        parser.add_argument(
            '--target',
            default='all',
            choices=['all', *TARGETS.keys()],
            help='Target model to paper trade. Use all to generate both reports.',
        )
        parser.add_argument(
            '--max-rows-per-split',
            type=int,
            default=50000,
            help='Rows sampled from each split for paper trading.',
        )
        parser.add_argument('--top-quantile', type=float, default=0.1, help='Top score fraction selected each date.')
        parser.add_argument('--random-state', type=int, default=42, help='Random seed for stable sampling.')
        parser.add_argument('--output-dir', help='Directory for paper trading report files.')

    def handle(self, *args, **options):
        switch_months = [
            month.strip()
            for month in options['switch_months'].split(',')
            if month.strip()
        ]
        target_names = list(TARGETS.keys()) if options['target'] == 'all' else [options['target']]
        logger.info(
            'paper_trade_quant_strategy started: artifacts_dir={}, fallback_artifacts_dir={}, switch_months={}, targets={}, max_rows_per_split={}, top_quantile={}',
            options['artifacts_dir'],
            options.get('fallback_artifacts_dir'),
            switch_months,
            target_names,
            options['max_rows_per_split'],
            options['top_quantile'],
        )
        for target_name in target_names:
            result = paper_trade_quant_strategy(
                artifacts_dir=options['artifacts_dir'],
                fallback_artifacts_dir=options.get('fallback_artifacts_dir'),
                switch_months=switch_months,
                feature_version=options['feature_version'],
                target_name=target_name,
                max_rows_per_split=options['max_rows_per_split'],
                top_quantile=options['top_quantile'],
                random_state=options['random_state'],
                output_dir=options.get('output_dir'),
                stdout=self.stdout,
            )
            summary = result['summary']
            self.stdout.write(self.style.SUCCESS(f'paper_trading_report: {result["report_path"]}'))
            self.stdout.write(f'target={target_name}, trade_dates={summary["trade_dates"]}, rows={summary["rows"]}')
            self.stdout.write('by_split:')
            for row in summary['by_split']:
                self.stdout.write(
                    f'  {row["split"]}: '
                    f'trade_dates={row["trade_dates"]}, '
                    f'avg_ret={_fmt(row["avg_portfolio_future_ret_20"])}, '
                    f'avg_excess={_fmt(row["avg_portfolio_future_excess_ret_20"])}, '
                    f'hit_up={_fmt(row["hit_rate_up"])}, '
                    f'hit_outperform={_fmt(row["hit_rate_outperform"])}, '
                    f'fallback_dates={row["fallback_trade_dates"]}'
                )
        logger.info('paper_trade_quant_strategy finished: artifacts_dir={}', options['artifacts_dir'])


def _fmt(value):
    if value is None:
        return 'None'
    if isinstance(value, float):
        return f'{value:.6f}'
    return str(value)
