from celery import shared_task

from api.services.tushare_sync import (
    sync_repurchase_data,
    sync_dividend_data,
    sync_top_inst_data,
    sync_top_list_data,
    sync_block_trade_data,
    sync_express_data,
    sync_forecast_data,
    sync_pledge_detail_data,
    sync_margin_data,
    sync_stk_factor_pro_data,
    sync_adj_factor_data,
    sync_balancesheet_data,
    sync_cashflow_data,
    sync_daily_basic_data,
    sync_daily_quote_data,
    sync_fina_indicator_data,
    sync_hk_hold_data,
    sync_income_data,
    sync_index_basic_data,
    sync_index_classify_data,
    sync_index_daily_data,
    sync_index_member_all_data,
    sync_margin_detail_data,
    sync_market_data,
    sync_moneyflow_data,
    sync_namechange_data,
    sync_pledge_stat_data,
    sync_share_float_data,
    sync_st_risk_data,
    sync_stk_premarket_data,
    sync_stk_limit_data,
    sync_stock_basic_data,
    sync_stock_company_data,
    sync_stock_hsgt_data,
    sync_stock_st_data,
    sync_suspend_d_data,
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
def sync_tushare_stk_premarket(start_date=None, end_date=None, full=False, resume=True):
    return sync_stk_premarket_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_stock_st(start_date=None, end_date=None, full=False, resume=True):
    return sync_stock_st_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_st_risk():
    return sync_st_risk_data()


@shared_task
def sync_tushare_stock_hsgt(start_date=None, end_date=None, full=False, resume=True):
    return sync_stock_hsgt_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_namechange():
    return sync_namechange_data()


@shared_task
def sync_tushare_stock_company():
    return sync_stock_company_data()


@shared_task
def sync_tushare_daily_quote(start_date=None, end_date=None):
    return sync_daily_quote_data(start_date=start_date, end_date=end_date)


@shared_task
def sync_tushare_daily_basic(start_date=None, end_date=None):
    return sync_daily_basic_data(start_date=start_date, end_date=end_date)


@shared_task
def sync_tushare_adj_factor(start_date=None, end_date=None, full=False, resume=True):
    return sync_adj_factor_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_fina_indicator(start_date=None, end_date=None):
    return sync_fina_indicator_data(start_date=start_date, end_date=end_date)


@shared_task
def sync_tushare_income(start_date=None, end_date=None):
    return sync_income_data(start_date=start_date, end_date=end_date)


@shared_task
def sync_tushare_balancesheet(start_date=None, end_date=None):
    return sync_balancesheet_data(start_date=start_date, end_date=end_date)


@shared_task
def sync_tushare_cashflow(start_date=None, end_date=None):
    return sync_cashflow_data(start_date=start_date, end_date=end_date)


@shared_task
def sync_tushare_index_basic():
    return sync_index_basic_data()


@shared_task
def sync_tushare_index_daily(start_date=None, end_date=None, full=False):
    return sync_index_daily_data(start_date=start_date, end_date=end_date, full=full)


@shared_task
def sync_tushare_index_classify():
    return sync_index_classify_data()


@shared_task
def sync_tushare_index_member_all():
    return sync_index_member_all_data()


@shared_task
def sync_tushare_moneyflow(start_date=None, end_date=None, full=False, resume=True):
    return sync_moneyflow_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_margin_detail(start_date=None, end_date=None, full=False, resume=True):
    return sync_margin_detail_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_hk_hold(start_date=None, end_date=None, full=False, resume=True):
    return sync_hk_hold_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_suspend_d(start_date=None, end_date=None, full=False, resume=True):
    return sync_suspend_d_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_stk_limit(start_date=None, end_date=None, full=False, resume=True):
    return sync_stk_limit_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_share_float(start_date=None, end_date=None, full=False, resume=True):
    return sync_share_float_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_pledge_stat(start_date=None, end_date=None, full=False, resume=True):
    return sync_pledge_stat_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_stk_factor_pro(start_date=None, end_date=None, full=False, resume=True):
    return sync_stk_factor_pro_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_pledge_detail(start_date=None, end_date=None):
    return sync_pledge_detail_data(start_date=start_date, end_date=end_date)


@shared_task
def sync_tushare_forecast(start_date=None, end_date=None):
    return sync_forecast_data(start_date=start_date, end_date=end_date)


@shared_task
def sync_tushare_express(start_date=None, end_date=None):
    return sync_express_data(start_date=start_date, end_date=end_date)


@shared_task
def sync_tushare_block_trade(start_date=None, end_date=None, full=False, resume=True):
    return sync_block_trade_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_top_list(start_date=None, end_date=None, full=False, resume=True):
    return sync_top_list_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_top_inst(start_date=None, end_date=None, full=False, resume=True):
    return sync_top_inst_data(start_date=start_date, end_date=end_date, full=full, resume=resume)


@shared_task
def sync_tushare_dividend(start_date=None, end_date=None):
    return sync_dividend_data(start_date=start_date, end_date=end_date)


@shared_task
def sync_tushare_repurchase(start_date=None, end_date=None, full=False, resume=True):
    return sync_repurchase_data(start_date=start_date, end_date=end_date, full=full, resume=resume)
