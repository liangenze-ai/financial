from django.core.management.base import BaseCommand

from api.services.model_samples import build_daily_rolling_features
from config.logging_setup import logger


class Command(BaseCommand):
    help = 'Build persistent daily rolling features used by model_sample_v1.'

    def add_arguments(self, parser):
        parser.add_argument('--start-date', dest='start_date', required=True, help='Start trade date, e.g. 20240101.')
        parser.add_argument('--end-date', dest='end_date', required=True, help='End trade date, e.g. 20240531.')
        parser.add_argument('--replace', action='store_true', help='Delete existing rolling features in range before upsert.')

    def handle(self, *args, **options):
        logger.info(
            'build_daily_rolling_features started: start_date={}, end_date={}, replace={}',
            options['start_date'],
            options['end_date'],
            options['replace'],
        )
        result = build_daily_rolling_features(
            start_date=options['start_date'],
            end_date=options['end_date'],
            replace=options['replace'],
        )
        logger.info('build_daily_rolling_features finished: {}', result)
        self.stdout.write(self.style.SUCCESS(str(result)))
