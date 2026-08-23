from django.core.management.base import BaseCommand

from api.services.model_samples import apply_daily_rolling_features_to_samples
from config.logging_setup import logger


class Command(BaseCommand):
    help = 'Apply persistent daily rolling features to model_sample_v1.'

    def add_arguments(self, parser):
        parser.add_argument('--start-date', dest='start_date', required=True, help='Start trade date, e.g. 20240101.')
        parser.add_argument('--end-date', dest='end_date', required=True, help='End trade date, e.g. 20240531.')
        parser.add_argument('--feature-version', default='v1', help='Feature version stored in model_sample_v1.')

    def handle(self, *args, **options):
        logger.info(
            'apply_daily_rolling_features started: start_date={}, end_date={}, feature_version={}',
            options['start_date'],
            options['end_date'],
            options['feature_version'],
        )
        result = apply_daily_rolling_features_to_samples(
            start_date=options['start_date'],
            end_date=options['end_date'],
            feature_version=options['feature_version'],
        )
        logger.info('apply_daily_rolling_features finished: {}', result)
        self.stdout.write(self.style.SUCCESS(str(result)))
