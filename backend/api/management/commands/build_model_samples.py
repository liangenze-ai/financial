from django.core.management.base import BaseCommand

from api.services.model_samples import build_model_samples, check_core_tables, sample_summary
from config.logging_setup import logger


class Command(BaseCommand):
    help = 'Build model_sample_v1 for the first quant diagnosis baseline.'

    def add_arguments(self, parser):
        parser.add_argument('--start-date', dest='start_date', help='Start trade date, e.g. 20240101.')
        parser.add_argument('--end-date', dest='end_date', help='End trade date, e.g. 20240531.')
        parser.add_argument('--benchmark-code', default='000300.SH', help='Benchmark index code for excess return labels.')
        parser.add_argument('--feature-version', default='v1', help='Feature version stored in model_sample_v1.')
        parser.add_argument('--append', action='store_true', help='Append/upsert without deleting existing samples in range first.')
        parser.add_argument('--skip-existing', action='store_true', help='When appending, skip trade dates already present in model_sample_v1.')
        parser.add_argument('--check', action='store_true', help='Only print core table integrity and current sample summary.')
        parser.add_argument('--skip-integrity', action='store_true', help='Skip printing core table integrity before building.')
        parser.add_argument('--include-technical', action='store_true', help='Include stk_factor_pro technical indicators. Slower on large local tables.')

    def handle(self, *args, **options):
        if not options['skip_integrity'] or options['check']:
            checks = check_core_tables()
            self.stdout.write('Core TuShare table integrity:')
            for item in checks:
                status = 'ok' if item.exists and item.sample_count > 0 else 'missing_or_empty'
                self.stdout.write(
                    f'- {item.name}: {status}, table={item.table}, '
                    f'sample_count={item.sample_count}, estimated_rows={item.estimated_rows}, '
                    f'range={item.min_date}..{item.max_date}'
                )

        feature_version = options['feature_version']
        if options['check']:
            self.stdout.write(f'Current sample summary: {sample_summary(feature_version=feature_version)}')
            return

        logger.info(
            'build_model_samples started: start_date={}, end_date={}, benchmark_code={}, feature_version={}, replace={}, include_technical={}, skip_existing={}',
            options.get('start_date'),
            options.get('end_date'),
            options['benchmark_code'],
            feature_version,
            not options['append'],
            options['include_technical'],
            options['skip_existing'],
        )
        result = build_model_samples(
            start_date=options.get('start_date'),
            end_date=options.get('end_date'),
            benchmark_code=options['benchmark_code'],
            feature_version=feature_version,
            replace=not options['append'],
            include_technical=options['include_technical'],
            skip_existing=options['skip_existing'],
        )
        logger.info('build_model_samples finished: {}', result)
        self.stdout.write(self.style.SUCCESS(str(result)))
