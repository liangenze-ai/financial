from django.core.management.base import BaseCommand

from api.services.model_samples import (
    repair_model_sample_core_features,
    repair_model_sample_core_features_staged,
    repair_model_sample_days_since_list,
    repair_model_sample_days_since_list_batch,
)
from config.logging_setup import logger


class Command(BaseCommand):
    help = 'Repair derived core features in model_sample_v1 without rebuilding labels.'

    def add_arguments(self, parser):
        parser.add_argument('--start-date', dest='start_date', help='Start trade date, e.g. 20240101.')
        parser.add_argument('--end-date', dest='end_date', help='End trade date, e.g. 20240531.')
        parser.add_argument('--feature-version', default='v1', help='Feature version stored in model_sample_v1.')
        parser.add_argument(
            '--mode',
            choices=['staged', 'legacy', 'days-only', 'days-only-batch'],
            default='staged',
            help='Repair implementation. days-only only fixes days_since_list.',
        )
        parser.add_argument('--batch-size', type=int, default=20, help='Trade dates per batch for batch modes.')

    def handle(self, *args, **options):
        logger.info(
            'repair_model_sample_features started: start_date={}, end_date={}, feature_version={}, mode={}, batch_size={}',
            options.get('start_date'),
            options.get('end_date'),
            options['feature_version'],
            options['mode'],
            options['batch_size'],
        )
        if options['mode'] == 'days-only-batch':
            result = repair_model_sample_days_since_list_batch(
                start_date=options.get('start_date'),
                end_date=options.get('end_date'),
                feature_version=options['feature_version'],
                batch_size=options['batch_size'],
                stdout=self.stdout,
            )
        else:
            if options['mode'] == 'staged':
                repair_func = repair_model_sample_core_features_staged
            elif options['mode'] == 'days-only':
                repair_func = repair_model_sample_days_since_list
            else:
                repair_func = repair_model_sample_core_features
            result = repair_func(
                start_date=options.get('start_date'),
                end_date=options.get('end_date'),
                feature_version=options['feature_version'],
            )
        logger.info('repair_model_sample_features finished: {}', result)
        self.stdout.write(self.style.SUCCESS(str(result)))
