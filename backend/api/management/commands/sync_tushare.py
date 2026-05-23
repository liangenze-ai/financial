from django.core.management.base import BaseCommand

from api.services.tushare_sync import (
    sync_namechange_data,
    sync_daily_basic_data,
    sync_daily_quote_data,
    sync_market_data,
    sync_st_risk_data,
    sync_stk_premarket_data,
    sync_stock_basic_data,
    sync_stock_company_data,
    sync_stock_hsgt_data,
    sync_stock_st_data,
    sync_trade_cal_data,
)
from config.logging_setup import setup_logging


class Command(BaseCommand):
    help = 'Sync A-share market data from TuShare with resumable progress.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--table',
            choices=[
                'all', 'stock_basic', 'trade_cal', 'stk_premarket', 'stock_st', 'st',
                'stock_hsgt', 'namechange', 'stock_company', 'daily', 'daily_basic',
                'market_data',
            ],
            default='market_data',
            help='TuShare table or sync group to sync.',
        )
        parser.add_argument('--start-date', dest='start_date', help='Start date, e.g. 20240101. Omit to continue from the latest stored date.')
        parser.add_argument('--end-date', dest='end_date', help='End date, e.g. 20240501. Omit to sync through today.')
        parser.add_argument('--full', action='store_true', help='Use the earliest configured full-sync start date for date based tables.')
        parser.add_argument('--no-resume', action='store_true', help='Restart from the beginning of the date range.')

    def handle(self, *args, **options):
        logger = setup_logging()
        table = options['table']
        start_date = options.get('start_date')
        end_date = options.get('end_date')
        full = options.get('full')
        resume = not options.get('no_resume')
        logger.info(
            'sync_tushare command started: table={}, start_date={}, end_date={}, full={}, resume={}',
            table,
            start_date,
            end_date,
            full,
            resume,
        )

        try:
            if table == 'stock_basic':
                result = sync_stock_basic_data()
            elif table == 'trade_cal':
                result = sync_trade_cal_data(start_date=start_date, end_date=end_date)
            elif table == 'stk_premarket':
                result = sync_stk_premarket_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == 'stock_st':
                result = sync_stock_st_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == 'st':
                result = sync_st_risk_data()
            elif table == 'stock_hsgt':
                result = sync_stock_hsgt_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
            elif table == 'namechange':
                result = sync_namechange_data()
            elif table == 'stock_company':
                result = sync_stock_company_data()
            elif table == 'daily':
                result = sync_daily_quote_data(start_date=start_date, end_date=end_date)
            elif table == 'daily_basic':
                result = sync_daily_basic_data(start_date=start_date, end_date=end_date)
            elif table == 'all':
                result = {
                    'stock_basic': sync_stock_basic_data(),
                    'trade_cal': sync_trade_cal_data(start_date=start_date, end_date=end_date),
                    'stk_premarket': sync_stk_premarket_data(start_date=start_date, end_date=end_date, full=full, resume=resume),
                    'stock_st': sync_stock_st_data(start_date=start_date, end_date=end_date, full=full, resume=resume),
                    'stock_hsgt': sync_stock_hsgt_data(start_date=start_date, end_date=end_date, full=full, resume=resume),
                    'st': sync_st_risk_data(),
                    'namechange': sync_namechange_data(),
                    'stock_company': sync_stock_company_data(),
                    'market_data': sync_market_data(
                        start_date=start_date,
                        end_date=end_date,
                        resume=resume,
                    ),
                }
            else:
                result = sync_market_data(
                    start_date=start_date,
                    end_date=end_date,
                    resume=resume,
                )
        except Exception as exc:
            logger.exception(f'sync_tushare command failed: {exc}')
            raise

        logger.info('sync_tushare command finished: result={}', result)
        self.stdout.write(self.style.SUCCESS(str(result)))
