from django.core.management.base import BaseCommand

from api.services.quant_baseline import TARGETS, calibrate_quant_baseline
from config.logging_setup import logger


class Command(BaseCommand):
    help = 'Fit probability calibrators for trained quant baseline artifacts.'

    def add_arguments(self, parser):
        parser.add_argument('--artifacts-dir', required=True, help='Source model artifact directory.')
        parser.add_argument('--output-dir', help='Directory for calibrated model artifacts.')
        parser.add_argument('--feature-version', default='v1', help='Feature version stored in model_sample_v1.')
        parser.add_argument(
            '--method',
            default='sigmoid',
            choices=['sigmoid', 'isotonic'],
            help='Calibration method fitted on the validation split.',
        )
        parser.add_argument(
            '--max-rows-per-split',
            type=int,
            default=50000,
            help='Rows sampled from each split for calibration and evaluation.',
        )
        parser.add_argument('--random-state', type=int, default=42, help='Random seed for stable sampling.')

    def handle(self, *args, **options):
        logger.info(
            'calibrate_quant_baseline started: artifacts_dir={}, output_dir={}, method={}, max_rows_per_split={}',
            options['artifacts_dir'],
            options.get('output_dir'),
            options['method'],
            options['max_rows_per_split'],
        )
        result = calibrate_quant_baseline(
            artifacts_dir=options['artifacts_dir'],
            output_dir=options.get('output_dir'),
            feature_version=options['feature_version'],
            method=options['method'],
            max_rows_per_split=options['max_rows_per_split'],
            random_state=options['random_state'],
            stdout=self.stdout,
        )
        metrics = result['metrics']
        self.stdout.write(self.style.SUCCESS(f'calibrated_artifacts: {result["output_dir"]}'))
        self.stdout.write(f'method={metrics["method"]}, fit_split={metrics["fit_split"]}')
        for target_name in TARGETS:
            self.stdout.write(f'target={target_name}')
            for split_name, split_metrics in metrics['targets'][target_name]['calibrated'].items():
                raw = metrics['targets'][target_name]['raw'][split_name]
                self.stdout.write(
                    f'  {split_name}: '
                    f'raw_log_loss={_fmt(raw["log_loss"])}, '
                    f'cal_log_loss={_fmt(split_metrics["log_loss"])}, '
                    f'raw_brier={_fmt(raw["brier"])}, '
                    f'cal_brier={_fmt(split_metrics["brier"])}, '
                    f'auc={_fmt(split_metrics["auc"])}'
                )
        logger.info('calibrate_quant_baseline finished: output_dir={}', result['output_dir'])


def _fmt(value):
    if value is None:
        return 'None'
    if isinstance(value, float):
        return f'{value:.6f}'
    return str(value)
