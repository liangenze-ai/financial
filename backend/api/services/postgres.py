from django.conf import settings

from api.models import (
    DailyBasic,
    DailyQuote,
    StockBasic,
    StockBasicHistory,
    StockCapitalPremarket,
    StockCompany,
    StockHsgt,
    StockNameChange,
    StockSTList,
    StockSTRiskNotice,
    SyncJob,
    TradeCal,
)


TABLES = settings.POSTGRES_TUSHARE_TABLES

TUSHARE_CATALOG = {
    'stock_basic': {
        'category': '股票数据',
        'section': '基础数据',
        'interface': 'stock_basic',
        'table': TABLES['stock_basic'],
    },
    'trade_cal': {
        'category': '股票数据',
        'section': '基础数据',
        'interface': 'trade_cal',
        'table': TABLES['trade_cal'],
    },
    'stk_premarket': {
        'category': '股票数据',
        'section': '基础数据',
        'interface': 'stk_premarket',
        'table': TABLES['stk_premarket'],
    },
    'stock_st': {
        'category': '股票数据',
        'section': '基础数据',
        'interface': 'stock_st',
        'table': TABLES['stock_st'],
    },
    'st': {
        'category': '股票数据',
        'section': '基础数据',
        'interface': 'st',
        'table': TABLES['st'],
    },
    'stock_hsgt': {
        'category': '股票数据',
        'section': '基础数据',
        'interface': 'stock_hsgt',
        'table': TABLES['stock_hsgt'],
    },
    'namechange': {
        'category': '股票数据',
        'section': '基础数据',
        'interface': 'namechange',
        'table': TABLES['namechange'],
    },
    'stock_company': {
        'category': '股票数据',
        'section': '基础数据',
        'interface': 'stock_company',
        'table': TABLES['stock_company'],
    },
    'daily': {
        'category': '股票数据',
        'section': '行情数据',
        'interface': 'daily',
        'table': TABLES['daily'],
    },
    'daily_basic': {
        'category': '股票数据',
        'section': '行情数据',
        'interface': 'daily_basic',
        'table': TABLES['daily_basic'],
    },
}

MODEL_CONFIG = {
    'stock_basic': {
        'model': StockBasic,
        'fields': [
            'ts_code', 'symbol', 'name', 'area', 'industry', 'fullname', 'enname', 'cnspell',
            'market', 'exchange', 'curr_type', 'list_status', 'list_date', 'delist_date',
            'is_hs', 'act_name', 'act_ent_type',
        ],
    },
    'stock_basic_history': {
        'model': StockBasicHistory,
        'fields': ['ts_code', 'field_name', 'old_value', 'new_value', 'source_date', 'raw_record'],
    },
    'trade_cal': {
        'model': TradeCal,
        'fields': ['exchange', 'cal_date', 'is_open', 'pretrade_date'],
    },
    'stk_premarket': {
        'model': StockCapitalPremarket,
        'fields': ['trade_date', 'ts_code', 'total_share', 'float_share', 'pre_close', 'up_limit', 'down_limit'],
    },
    'stock_st': {
        'model': StockSTList,
        'fields': ['ts_code', 'name', 'trade_date', 'type', 'type_name'],
    },
    'st': {
        'model': StockSTRiskNotice,
        'fields': ['ts_code', 'name', 'pub_date', 'imp_date', 'st_tpye', 'st_reason', 'st_explain'],
    },
    'stock_hsgt': {
        'model': StockHsgt,
        'fields': ['ts_code', 'trade_date', 'type', 'name', 'type_name'],
    },
    'namechange': {
        'model': StockNameChange,
        'fields': ['ts_code', 'name', 'start_date', 'end_date', 'ann_date', 'change_reason'],
    },
    'stock_company': {
        'model': StockCompany,
        'fields': [
            'ts_code', 'com_name', 'com_id', 'exchange', 'chairman', 'manager', 'secretary',
            'reg_capital', 'setup_date', 'province', 'city', 'introduction', 'website', 'email',
            'office', 'employees', 'main_business', 'business_scope',
        ],
    },
    'daily': {
        'model': DailyQuote,
        'fields': ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_chg', 'vol', 'amount'],
    },
    'daily_basic': {
        'model': DailyBasic,
        'fields': ['ts_code', 'trade_date', 'close', 'turnover_rate', 'volume_ratio', 'pe_ttm', 'pb', 'ps_ttm', 'dv_ttm', 'total_mv', 'circ_mv'],
    },
}


def catalog_for(name):
    return TUSHARE_CATALOG[name]


def model_for(name):
    return MODEL_CONFIG[name]['model']


def fields_for(name):
    return MODEL_CONFIG[name]['fields']


def get_job(name):
    return SyncJob.objects.filter(name=name).first()
