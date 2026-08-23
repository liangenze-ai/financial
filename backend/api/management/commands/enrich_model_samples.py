from django.core.management.base import BaseCommand

from api.services.model_samples import enrich_model_samples, enrich_model_samples_batch, enrich_summary, enrich_trade_dates
from config.logging_setup import logger


class Command(BaseCommand):
    help = 'Enrich model_sample_v1 with low-frequency financial, pledge, and hk-hold features.'

    def add_arguments(self, parser):
        parser.add_argument('--start-date', dest='start_date', help='Start trade date, e.g. 20240501.')
        parser.add_argument('--end-date', dest='end_date', help='End trade date, e.g. 20240531.')
        parser.add_argument('--feature-version', default='v1', help='Feature version stored in model_sample_v1.')
        parser.add_argument('--only-missing', action='store_true', help='Only enrich rows that have not been updated after sample creation.')
        parser.add_argument('--batch-size', type=int, default=20, help='Number of trade dates to enrich per batch. Use 0 to run as one SQL batch.')
        parser.add_argument('--check', action='store_true', help='Only print current enrichment coverage.')

    def handle(self, *args, **options):
        feature_version = options['feature_version']
        start_date = options.get('start_date')
        end_date = options.get('end_date')

        if options['check']:
            self.stdout.write(str(enrich_summary(feature_version=feature_version, start_date=start_date, end_date=end_date)))
            return

        logger.info(
            'enrich_model_samples started: start_date={}, end_date={}, feature_version={}, only_missing={}',
            start_date,
            end_date,
            feature_version,
            options['only_missing'],
        )
        batch_size = options['batch_size']
        if batch_size and batch_size > 0:
            trade_dates = enrich_trade_dates(
                start_date=start_date,
                end_date=end_date,
                feature_version=feature_version,
                only_missing=options['only_missing'],
            )
            total_dates = len(trade_dates)
            self.stdout.write(f'enrich_model_samples dates to process: {total_dates}, batch_size={batch_size}')
            self.stdout.flush()

            total_rows = 0
            for index in range(0, total_dates, batch_size):
                batch_dates = trade_dates[index:index + batch_size]
                batch_result = enrich_model_samples_batch(
                    start_date=start_date,
                    end_date=end_date,
                    feature_version=feature_version,
                    only_missing=options['only_missing'],
                    batch_dates=batch_dates,
                )
                total_rows += batch_result['target_rows']
                self.stdout.write(
                    f'enrich_model_samples progress: '
                    f'{min(index + batch_size, total_dates)}/{total_dates} dates, '
                    f'range={batch_dates[0]}..{batch_dates[-1]}, '
                    f'batch_rows={batch_result["target_rows"]}, total_rows={total_rows}'
                )
                self.stdout.flush()

            result = {
                'processed_dates': total_dates,
                'target_rows': total_rows,
                'summary': 'skipped in batch mode; use --check for a full coverage summary',
            }
        else:
            result = enrich_model_samples(
                start_date=start_date,
                end_date=end_date,
                feature_version=feature_version,
                only_missing=options['only_missing'],
            )
        logger.info('enrich_model_samples finished: {}', result)
        self.stdout.write(self.style.SUCCESS(str(result)))
