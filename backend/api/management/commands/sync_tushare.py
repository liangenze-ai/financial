from django.core.management.base import BaseCommand

from api.services.tushare_sync import (
    sync_daily_basic_data,
    sync_daily_quote_data,
    sync_market_data,
    sync_stock_basic_data,
    sync_trade_cal_data,
)


class Command(BaseCommand):
    help = 'Sync A-share market data from TuShare with resumable progress.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--table',
            choices=['all', 'stock_basic', 'trade_cal', 'daily', 'daily_basic', 'market_data'],
            default='market_data',
            help='TuShare table or sync group to sync.',
        )
        parser.add_argument('--start-date', dest='start_date', help='Start date, e.g. 20240101')
        parser.add_argument('--end-date', dest='end_date', help='End date, e.g. 20240501')
        parser.add_argument('--no-resume', action='store_true', help='Restart from the beginning of the date range.')

    def handle(self, *args, **options):
        table = options['table']
        start_date = options.get('start_date')
        end_date = options.get('end_date')

        if table == 'stock_basic':
            result = sync_stock_basic_data()
        elif table == 'trade_cal':
            result = sync_trade_cal_data(start_date=start_date, end_date=end_date)
        elif table == 'daily':
            result = sync_daily_quote_data(start_date=start_date, end_date=end_date)
        elif table == 'daily_basic':
            result = sync_daily_basic_data(start_date=start_date, end_date=end_date)
        elif table == 'all':
            result = {
                'stock_basic': sync_stock_basic_data(),
                'market_data': sync_market_data(
                    start_date=start_date,
                    end_date=end_date,
                    resume=not options.get('no_resume'),
                ),
            }
        else:
            result = sync_market_data(
                start_date=start_date,
                end_date=end_date,
                resume=not options.get('no_resume'),
            )
        self.stdout.write(self.style.SUCCESS(str(result)))
