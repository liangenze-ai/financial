from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from api.models import StockBasicHistory, SyncJob
from api.services.postgres import catalog_for, fields_for, get_job as get_sync_job, model_for


DATE_FORMAT = '%Y%m%d'
JOB_NAME = 'tushare_market_data'
STOCK_BASIC_JOB_NAME = 'tushare_stock_basic'
STATUS_RUNNING = 'running'
STATUS_SUCCESS = 'success'
STATUS_FAILED = 'failed'
STOCK_BASIC_FIELDS = [
    'ts_code', 'symbol', 'name', 'area', 'industry', 'fullname', 'enname', 'cnspell',
    'market', 'exchange', 'curr_type', 'list_status', 'list_date', 'delist_date',
    'is_hs', 'act_name', 'act_ent_type',
]
STOCK_BASIC_CHANGE_FIELDS = [
    'name', 'fullname', 'act_name', 'act_ent_type', 'industry', 'area',
    'market', 'exchange', 'list_status',
]


class TushareSyncError(RuntimeError):
    pass


def get_tushare_client():
    token = settings.TUSHARE_TOKEN
    if not token:
        raise TushareSyncError('TUSHARE_TOKEN is empty. Set it in backend/.env first.')

    try:
        import tushare as ts
    except ImportError as exc:
        raise TushareSyncError('tushare is not installed. Run pip install -r backend/requirements.txt.') from exc

    ts.set_token(token)
    return ts.pro_api()


def dataframe_records(frame):
    if frame is None or frame.empty:
        return []
    return frame.where(frame.notna(), None).to_dict('records')


def now():
    return timezone.now()


def today_text():
    return timezone.localdate().strftime(DATE_FORMAT)


def default_start_date():
    days_back = settings.TUSHARE_SYNC_DAYS_BACK
    return (timezone.localdate() - timedelta(days=days_back)).strftime(DATE_FORMAT)


def clean_value(value):
    if value is None:
        return None
    text = str(value)
    if text in ('', 'nan', 'NaN', 'None', '<NA>', 'NaT'):
        return None
    return value


def clean_record(record):
    return {key: clean_value(value) for key, value in record.items()}


def attach_catalog(record, catalog_name):
    record['tushare_meta'] = catalog_for(catalog_name)
    return record


def bulk_upsert(table_name, records, key_fields):
    if not records:
        return 0

    model = model_for(table_name)
    allowed_fields = set(fields_for(table_name))
    count = 0
    for raw_record in records:
        record = attach_catalog(clean_record(raw_record), table_name)
        if not all(record.get(field) is not None for field in key_fields):
            continue
        lookup = {field: record[field] for field in key_fields}
        defaults = {
            field: record.get(field)
            for field in allowed_fields
            if field not in key_fields
        }
        defaults['tushare_meta'] = record['tushare_meta']
        model.objects.update_or_create(defaults=defaults, **lookup)
        count += 1

    return count


def get_job():
    return get_sync_job(JOB_NAME)


def save_job(update, set_on_insert=None, name=JOB_NAME):
    update = {key: value for key, value in update.items() if key != 'name'}
    create_defaults = {**(set_on_insert or {}), **update}
    job, created = SyncJob.objects.get_or_create(name=name, defaults=create_defaults)
    if not created:
        for key, value in update.items():
            setattr(job, key, value)
        job.save()
    return job


def mark_running(start_date, end_date, current_date='', current_step='', reset_progress=False):
    update = {
        'name': JOB_NAME,
        'status': STATUS_RUNNING,
        'start_date': start_date,
        'end_date': end_date,
        'current_step': current_step,
        'message': '',
    }
    if current_date:
        update['current_date'] = current_date
    if reset_progress:
        update['current_date'] = ''
        update['processed_dates'] = 0

    return save_job(update, set_on_insert={'processed_dates': 0})


def mark_finished(message):
    save_job({'status': STATUS_SUCCESS, 'current_step': 'done', 'message': message})


def mark_failed(message):
    save_job({'status': STATUS_FAILED, 'message': message})


def mark_stock_basic_running():
    return save_job(
        {
            'status': STATUS_RUNNING,
            'start_date': None,
            'end_date': today_text(),
            'current_date': '',
            'current_step': 'stock_basic',
            'processed_dates': 0,
            'message': '',
        },
        name=STOCK_BASIC_JOB_NAME,
    )


def mark_stock_basic_finished(message):
    save_job(
        {'status': STATUS_SUCCESS, 'current_step': 'done', 'message': message},
        name=STOCK_BASIC_JOB_NAME,
    )


def mark_stock_basic_failed(message):
    save_job({'status': STATUS_FAILED, 'message': message}, name=STOCK_BASIC_JOB_NAME)


def increment_processed_dates():
    with transaction.atomic():
        job = SyncJob.objects.select_for_update().filter(name=JOB_NAME).first()
        if not job:
            SyncJob.objects.create(name=JOB_NAME, status=STATUS_RUNNING, processed_dates=1, current_step='done')
            return
        job.processed_dates += 1
        job.current_step = 'done'
        job.save(update_fields=['processed_dates', 'current_step', 'updated_at'])


def get_trade_dates(pro, start_date, end_date):
    fields = 'exchange,cal_date,is_open,pretrade_date'
    records = dataframe_records(
        pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date, fields=fields)
    )
    bulk_upsert('trade_cal', records, ['exchange', 'cal_date'])
    return [record['cal_date'] for record in records if str(record.get('is_open')) == '1']


def resume_dates(job, trade_dates):
    if not job or job.status != STATUS_RUNNING or not job.current_date:
        return trade_dates
    current_date = job.current_date
    if current_date not in trade_dates:
        return trade_dates
    return trade_dates[trade_dates.index(current_date):]


def value_to_text(value):
    cleaned = clean_value(value)
    if cleaned is None:
        return None
    return str(cleaned)


def record_stock_basic_changes(existing, record):
    if not existing:
        return 0

    changes = []
    for field in STOCK_BASIC_CHANGE_FIELDS:
        old_value = value_to_text(getattr(existing, field))
        new_value = value_to_text(record.get(field))
        if old_value == new_value:
            continue
        changes.append(
            StockBasicHistory(
                ts_code=record['ts_code'],
                field_name=field,
                old_value=old_value,
                new_value=new_value,
                source_date=today_text(),
                raw_record=record,
            )
        )

    if not changes:
        return 0
    StockBasicHistory.objects.bulk_create(changes)
    return len(changes)


def sync_stock_basic(pro):
    model = model_for('stock_basic')
    fields = ','.join(STOCK_BASIC_FIELDS)
    synced = 0
    change_count = 0

    for list_status in ('L', 'D', 'P', 'G'):
        records = dataframe_records(pro.stock_basic(exchange='', list_status=list_status, fields=fields))
        for raw_record in records:
            record = clean_record(raw_record)
            ts_code = record.get('ts_code')
            if not ts_code:
                continue

            existing = model.objects.filter(ts_code=ts_code).first()
            record['tushare_meta'] = catalog_for('stock_basic')
            change_count += record_stock_basic_changes(existing, record)

            defaults = {
                field: record.get(field)
                for field in fields_for('stock_basic')
                if field != 'ts_code'
            }
            defaults['tushare_meta'] = record['tushare_meta']
            model.objects.update_or_create(ts_code=ts_code, defaults=defaults)
            synced += 1

    return {'stocks': synced, 'changes': change_count}


def sync_stock_basic_data():
    pro = get_tushare_client()
    mark_stock_basic_running()
    try:
        result = sync_stock_basic(pro)
        message = f"stocks={result['stocks']}, changes={result['changes']}"
        mark_stock_basic_finished(message)
        job = get_sync_job(STOCK_BASIC_JOB_NAME)
        return {
            'status': job.status,
            'message': job.message,
        }
    except Exception as exc:
        mark_stock_basic_failed(str(exc))
        raise


def resolve_date_range(start_date=None, end_date=None):
    return (
        start_date or settings.TUSHARE_SYNC_START_DATE or default_start_date(),
        end_date or today_text(),
    )


def sync_trade_cal_data(start_date=None, end_date=None):
    pro = get_tushare_client()
    start_date, end_date = resolve_date_range(start_date, end_date)
    trade_dates = get_trade_dates(pro, start_date, end_date)
    return {
        'status': STATUS_SUCCESS,
        'start_date': start_date,
        'end_date': end_date,
        'open_trade_dates': len(trade_dates),
    }


def sync_daily_quote_data(start_date=None, end_date=None):
    pro = get_tushare_client()
    start_date, end_date = resolve_date_range(start_date, end_date)
    trade_dates = get_trade_dates(pro, start_date, end_date)
    quote_count = 0
    for trade_date in trade_dates:
        quote_count += sync_daily_quote(pro, trade_date)
    return {
        'status': STATUS_SUCCESS,
        'start_date': start_date,
        'end_date': end_date,
        'daily_quotes': quote_count,
    }


def sync_daily_basic_data(start_date=None, end_date=None):
    pro = get_tushare_client()
    start_date, end_date = resolve_date_range(start_date, end_date)
    trade_dates = get_trade_dates(pro, start_date, end_date)
    basic_count = 0
    for trade_date in trade_dates:
        basic_count += sync_daily_basic(pro, trade_date)
    return {
        'status': STATUS_SUCCESS,
        'start_date': start_date,
        'end_date': end_date,
        'daily_basics': basic_count,
    }


def sync_daily_quote(pro, trade_date):
    records = dataframe_records(pro.daily(trade_date=trade_date))
    return bulk_upsert('daily', records, ['ts_code', 'trade_date'])


def sync_daily_basic(pro, trade_date):
    fields = 'ts_code,trade_date,close,turnover_rate,volume_ratio,pe_ttm,pb,ps_ttm,dv_ttm,total_mv,circ_mv'
    records = dataframe_records(pro.daily_basic(trade_date=trade_date, fields=fields))
    return bulk_upsert('daily_basic', records, ['ts_code', 'trade_date'])


def sync_market_data(start_date=None, end_date=None, resume=True):
    pro = get_tushare_client()

    start_date = start_date or settings.TUSHARE_SYNC_START_DATE or default_start_date()
    end_date = end_date or today_text()
    existing_job = get_job()
    reset_progress = not resume or not existing_job or existing_job.status != STATUS_RUNNING

    mark_running(start_date, end_date, current_step='trade_cal', reset_progress=reset_progress)

    try:
        trade_dates = get_trade_dates(pro, start_date, end_date)
        job = get_job()
        trade_dates = resume_dates(job, trade_dates)

        quote_count = 0
        basic_count = 0

        for trade_date in trade_dates:
            mark_running(start_date, end_date, current_date=trade_date, current_step='daily')
            quote_count += sync_daily_quote(pro, trade_date)

            mark_running(start_date, end_date, current_date=trade_date, current_step='daily_basic')
            basic_count += sync_daily_basic(pro, trade_date)
            increment_processed_dates()

        message = f'daily_quotes={quote_count}, daily_basics={basic_count}'
        mark_finished(message)
        job = get_job()
        return {
            'status': job.status,
            'message': job.message,
            'start_date': job.start_date,
            'end_date': job.end_date,
            'processed_dates': job.processed_dates,
        }
    except Exception as exc:
        mark_failed(str(exc))
        raise
