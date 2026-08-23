from django.core.management.base import BaseCommand

from api.services.quant_baseline import TARGETS, diagnose_quant_stock, diagnose_quant_stock_combined
from config.logging_setup import logger


class Command(BaseCommand):
    help = 'Generate a regime-aware single-stock quant baseline diagnostic report.'

    def add_arguments(self, parser):
        parser.add_argument('--ts-code', required=True, help='Stock code, for example 000001.SZ.')
        parser.add_argument('--trade-date', required=True, help='Trade date formatted as YYYYMMDD.')
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
            help='Target model to diagnose. Use all to generate both reports.',
        )
        parser.add_argument('--output-dir', help='Directory for stock diagnostic JSON reports.')

    def handle(self, *args, **options):
        switch_months = [
            month.strip()
            for month in options['switch_months'].split(',')
            if month.strip()
        ]
        target_names = list(TARGETS.keys()) if options['target'] == 'all' else [options['target']]

        logger.info(
            'diagnose_quant_stock started: ts_code={}, trade_date={}, artifacts_dir={}, fallback_artifacts_dir={}, switch_months={}, targets={}',
            options['ts_code'],
            options['trade_date'],
            options['artifacts_dir'],
            options.get('fallback_artifacts_dir'),
            switch_months,
            target_names,
        )
        if options['target'] == 'all':
            combined = diagnose_quant_stock_combined(
                ts_code=options['ts_code'],
                trade_date=options['trade_date'],
                artifacts_dir=options['artifacts_dir'],
                fallback_artifacts_dir=options.get('fallback_artifacts_dir'),
                switch_months=switch_months,
                feature_version=options['feature_version'],
                output_dir=options.get('output_dir'),
                stdout=self.stdout,
            )
            summary = combined['summary']
            signal = summary['combined_signal']
            self.stdout.write(self.style.SUCCESS(f'combined_stock_diagnostic_report: {combined["report_path"]}'))
            self.stdout.write(
                f'combined_signal={signal["label"]}, '
                f'confidence={signal["confidence"]}, '
                f'up_decile={signal["up_decile"]}, '
                f'outperform_decile={signal["outperform_decile"]}'
            )
            if summary['warnings']:
                self.stdout.write('combined_warnings:')
                for warning in summary['warnings']:
                    self.stdout.write(f'  {warning}')
            target_results = combined['target_results']
        else:
            target_results = {}
            for target_name in target_names:
                target_results[target_name] = diagnose_quant_stock(
                    ts_code=options['ts_code'],
                    trade_date=options['trade_date'],
                    artifacts_dir=options['artifacts_dir'],
                    fallback_artifacts_dir=options.get('fallback_artifacts_dir'),
                    switch_months=switch_months,
                    feature_version=options['feature_version'],
                    target_name=target_name,
                    output_dir=options.get('output_dir'),
                    stdout=self.stdout,
                )

        for target_name in target_names:
            result = target_results[target_name]
            summary = result['summary']
            self.stdout.write(self.style.SUCCESS(f'stock_diagnostic_report: {result["report_path"]}'))
            self.stdout.write(
                f'target={summary["target"]}, '
                f'model_role={summary["model_role"]}, '
                f'score={_fmt(summary["score"])}, '
                f'pct_rank={_fmt(summary["score_pct_rank"])}, '
                f'decile={summary["score_decile"]}, '
                f'cohort={summary["cohort"]}'
            )
            observed = summary['observed']
            self.stdout.write(
                f'observed_future_ret={_fmt(observed["future_ret_20"])}, '
                f'observed_future_excess={_fmt(observed["future_excess_ret_20"])}, '
                f'label={observed["label"]}'
            )
            if summary['warnings']:
                self.stdout.write('warnings:')
                for warning in summary['warnings']:
                    self.stdout.write(f'  {warning}')
            self.stdout.write('top_positive_contributions:')
            for row in summary['top_positive_contributions'][:5]:
                self.stdout.write(
                    f'  {row["feature"]}: raw={_fmt(row["raw_value"])}, contribution={_fmt(row["contribution"])}'
                )
            self.stdout.write('top_negative_contributions:')
            for row in summary['top_negative_contributions'][:5]:
                self.stdout.write(
                    f'  {row["feature"]}: raw={_fmt(row["raw_value"])}, contribution={_fmt(row["contribution"])}'
                )
        logger.info('diagnose_quant_stock finished: ts_code={}, trade_date={}', options['ts_code'], options['trade_date'])


def _fmt(value):
    if value is None:
        return 'None'
    if isinstance(value, float):
        return f'{value:.6f}'
    return str(value)
