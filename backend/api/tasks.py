from celery import shared_task

from api.services.tushare_sync import (
    sync_daily_basic_data,
    sync_daily_quote_data,
    sync_market_data,
    sync_stock_basic_data,
    sync_trade_cal_data,
)


@shared_task
def ping_task():
    return 'pong'


@shared_task
def sync_tushare_market_data(start_date=None, end_date=None, resume=True):
    return sync_market_data(start_date=start_date, end_date=end_date, resume=resume)


@shared_task
def sync_tushare_stock_basic():
    return sync_stock_basic_data()


@shared_task
def sync_tushare_trade_cal(start_date=None, end_date=None):
    return sync_trade_cal_data(start_date=start_date, end_date=end_date)


@shared_task
def sync_tushare_daily_quote(start_date=None, end_date=None):
    return sync_daily_quote_data(start_date=start_date, end_date=end_date)


@shared_task
def sync_tushare_daily_basic(start_date=None, end_date=None):
    return sync_daily_basic_data(start_date=start_date, end_date=end_date)
