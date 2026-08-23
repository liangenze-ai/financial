from django.core.management.base import BaseCommand

from api.services.quant_baseline import TARGETS, diagnose_quant_baseline_slice
from config.logging_setup import logger


class Command(BaseCommand):
    help = 'Diagnose top/bottom score cohorts for a trained quant baseline artifact over one month.'

    def add_arguments(self, parser):
        parser.add_argument('--artifacts-dir', required=True, help='Directory containing trained baseline artifacts.')
        parser.add_argument('--fallback-artifacts-dir', help='Optional fallback artifact directory used for switch months.')
        parser.add_argument(
            '--switch-months',
            default='',
            help='Comma-separated YYYYMM months that should use the fallback model when provided.',
        )
        parser.add_argument('--feature-version', default='v1', help='Feature version stored in model_sample_v1.')
        parser.add_argument('--month', default='202604', help='Target month formatted as YYYYMM.')
        parser.add_argument('--target', default='up', choices=TARGETS.keys(), help='Target model to diagnose.')
        parser.add_argument('--max-rows', type=int, default=50000, help='Maximum rows sampled from the month.')
        parser.add_argument('--random-state', type=int, default=42, help='Random seed for stable per-date sampling.')

    def handle(self, *args, **options):
        switch_months = [
            month.strip()
            for month in options['switch_months'].split(',')
            if month.strip()
        ]
        logger.info(
            'diagnose_quant_baseline_slice started: artifacts_dir={}, fallback_artifacts_dir={}, switch_months={}, feature_version={}, month={}, target={}, max_rows={}, random_state={}',
            options['artifacts_dir'],
            options.get('fallback_artifacts_dir'),
            switch_months,
            options['feature_version'],
            options['month'],
            options['target'],
            options['max_rows'],
            options['random_state'],
        )
        report = diagnose_quant_baseline_slice(
            artifacts_dir=options['artifacts_dir'],
            fallback_artifacts_dir=options.get('fallback_artifacts_dir'),
            switch_months=switch_months,
            feature_version=options['feature_version'],
            month=options['month'],
            target_name=options['target'],
            max_rows=options['max_rows'],
            random_state=options['random_state'],
            stdout=self.stdout,
        )
        summary = report['summary']
        cohorts = summary['cohorts']

        self.stdout.write(self.style.SUCCESS(f'diagnostic_outputs: {report["output_prefix"]}_*.csv/json'))
        self.stdout.write(
            f'model_role={summary["model_role"]}, '
            f'artifact_dir={summary["artifact_dir"]}, '
            f'use_fallback={summary["use_fallback"]}'
        )
        self.stdout.write(f'rows={summary["rows"]}, trade_dates={len(summary["trade_dates"])}')
        for cohort in ['top', 'bottom', 'middle']:
            if cohort not in cohorts:
                continue
            metrics = cohorts[cohort]
            self.stdout.write(
                f'{cohort}: '
                f'rows={metrics["rows"]}, '
                f'positive_rate={_fmt(metrics["positive_rate"])}, '
                f'score_mean={_fmt(metrics["score_mean"])}, '
                f'future_ret={_fmt(metrics["future_ret_20_mean"])}, '
                f'future_excess={_fmt(metrics["future_excess_ret_20_mean"])}, '
                f'total_mv_median={_fmt(metrics["total_mv_median"])}'
            )
        self.stdout.write(f'top_minus_bottom: {summary["top_minus_bottom"]}')

        self.stdout.write('largest_feature_gaps:')
        for row in report['feature_rows'][:12]:
            self.stdout.write(
                f'  {row["feature"]}: '
                f'top={_fmt(row.get("top_mean"))}, '
                f'bottom={_fmt(row.get("bottom_mean"))}, '
                f'diff={_fmt(row.get("top_minus_bottom_mean"))}'
            )

        self.stdout.write('top_cohort_industries:')
        top_industries = [
            row for row in report['industry_rows']
            if row['cohort'] == 'top'
        ]
        top_industries.sort(key=lambda row: row['rows'], reverse=True)
        for row in top_industries[:12]:
            self.stdout.write(
                f'  {row["industry"]}: '
                f'rows={row["rows"]}, '
                f'share={_fmt(row["cohort_share"])}, '
                f'excess={_fmt(row["future_excess_ret_20_mean"])}'
            )
        logger.info('diagnose_quant_baseline_slice finished: output_prefix={}', report['output_prefix'])


def _fmt(value):
    if value is None:
        return 'None'
    if isinstance(value, float):
        return f'{value:.6f}'
    return str(value)
