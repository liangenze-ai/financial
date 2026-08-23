from django.core.management.base import BaseCommand

from api.services.quant_baseline import TARGETS, evaluate_quant_regime_blend
from config.logging_setup import logger


class Command(BaseCommand):
    help = 'Evaluate a month-based regime blend between two trained quant baseline artifacts.'

    def add_arguments(self, parser):
        parser.add_argument('--primary-artifacts-dir', required=True, help='Default model artifact directory.')
        parser.add_argument('--fallback-artifacts-dir', required=True, help='Model artifact directory used for switch months.')
        parser.add_argument(
            '--switch-months',
            default='',
            help='Comma-separated YYYYMM months that should use the fallback model.',
        )
        parser.add_argument(
            '--auto-switch-rule',
            choices=['weak_ma60', 'rebound_after_weakness'],
            help='Automatically choose fallback months using a no-future-leakage market-state rule.',
        )
        parser.add_argument(
            '--auto-switch-source',
            choices=['sample', 'database'],
            default='sample',
            help='Use sampled evaluation rows or full database month medians to choose auto switch months.',
        )
        parser.add_argument(
            '--ma60-bias-threshold',
            type=float,
            default=-0.04,
            help='Fallback when monthly median ma60_bias is at or below this threshold for auto-switch-rule=weak_ma60.',
        )
        parser.add_argument(
            '--ma60-bias-floor',
            type=float,
            help='Optional lower bound for monthly median ma60_bias when auto-switch-rule=rebound_after_weakness.',
        )
        parser.add_argument(
            '--ret20-rebound-threshold',
            type=float,
            default=-0.04,
            help='Fallback when monthly median ret_20 is at or above this threshold for auto-switch-rule=rebound_after_weakness.',
        )
        parser.add_argument(
            '--ret20-rebound-ceiling',
            type=float,
            help='Optional upper bound for monthly median ret_20 when auto-switch-rule=rebound_after_weakness.',
        )
        parser.add_argument('--feature-version', default='v1', help='Feature version stored in model_sample_v1.')
        parser.add_argument('--target', default='up', choices=TARGETS.keys(), help='Target model to evaluate.')
        parser.add_argument(
            '--max-rows-per-split',
            type=int,
            default=50000,
            help='Rows sampled from each split for evaluation.',
        )
        parser.add_argument('--random-state', type=int, default=42, help='Random seed for stable per-date sampling.')
        parser.add_argument('--output-dir', help='Directory for regime blend report files.')

    def handle(self, *args, **options):
        switch_months = [
            month.strip()
            for month in options['switch_months'].split(',')
            if month.strip()
        ]
        logger.info(
            'evaluate_quant_regime_blend started: primary={}, fallback={}, switch_months={}, target={}, max_rows_per_split={}',
            options['primary_artifacts_dir'],
            options['fallback_artifacts_dir'],
            switch_months,
            options['target'],
            options['max_rows_per_split'],
        )
        result = evaluate_quant_regime_blend(
            primary_artifacts_dir=options['primary_artifacts_dir'],
            fallback_artifacts_dir=options['fallback_artifacts_dir'],
            switch_months=switch_months,
            feature_version=options['feature_version'],
            target_name=options['target'],
            max_rows_per_split=options['max_rows_per_split'],
            random_state=options['random_state'],
            output_dir=options.get('output_dir'),
            auto_switch_rule=options.get('auto_switch_rule'),
            auto_switch_source=options['auto_switch_source'],
            ma60_bias_threshold=options['ma60_bias_threshold'],
            ma60_bias_floor=options.get('ma60_bias_floor'),
            ret20_rebound_threshold=options['ret20_rebound_threshold'],
            ret20_rebound_ceiling=options.get('ret20_rebound_ceiling'),
            stdout=self.stdout,
        )
        report = result['report']

        self.stdout.write(self.style.SUCCESS(f'regime_blend_report: {result["report_path"]}'))
        self.stdout.write(f'rows={report["rows"]}, fallback_rows={report["fallback_rows"]}')
        if report.get('auto_switch_rule'):
            self.stdout.write(
                f'auto_switch_rule={report["auto_switch_rule"]}, '
                f'auto_switch_source={report["auto_switch_source"]}, '
                f'ma60_bias_threshold={report["ma60_bias_threshold"]}, '
                f'ma60_bias_floor={report["ma60_bias_floor"]}, '
                f'ret20_rebound_threshold={report["ret20_rebound_threshold"]}, '
                f'ret20_rebound_ceiling={report["ret20_rebound_ceiling"]}, '
                f'switch_months={report["switch_months"]}'
            )
        self.stdout.write('by_split:')
        for split_name, metrics in report['by_split'].items():
            self.stdout.write(
                f'  {split_name}: '
                f'rows={metrics["rows"]}, '
                f'positive_rate={_fmt(metrics["positive_rate"])}, '
                f'auc={_fmt(metrics["auc"])}, '
                f'top_excess={_fmt(metrics["top_decile_future_excess_ret_20_mean"])}, '
                f'bottom_excess={_fmt(metrics["bottom_decile_future_excess_ret_20_mean"])}, '
                f'rank_ic={_fmt(metrics["rank_ic_mean"])}'
            )

        self.stdout.write('switch_months:')
        for month in report['switch_months']:
            metrics = report['by_month'].get(month)
            if not metrics:
                continue
            self.stdout.write(
                f'  {month}: '
                f'rows={metrics["rows"]}, '
                f'auc={_fmt(metrics["auc"])}, '
                f'top_excess={_fmt(metrics["top_decile_future_excess_ret_20_mean"])}, '
                f'bottom_excess={_fmt(metrics["bottom_decile_future_excess_ret_20_mean"])}, '
                f'rank_ic={_fmt(metrics["rank_ic_mean"])}'
            )
        logger.info('evaluate_quant_regime_blend finished: report_path={}', result['report_path'])


def _fmt(value):
    if value is None:
        return 'None'
    if isinstance(value, float):
        return f'{value:.6f}'
    return str(value)
