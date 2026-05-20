from django.conf import settings

from api.models import DailyBasic, DailyQuote, StockBasic, StockBasicHistory, SyncJob, TradeCal


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
