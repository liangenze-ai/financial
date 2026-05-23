from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from api.models import StockBasicHistory, SyncJob
from api.services.postgres import catalog_for, fields_for, get_job as get_sync_job, model_for
from config.logging_setup import setup_logging


DATE_FORMAT = '%Y%m%d'
JOB_NAME = 'tushare_market_data'
STOCK_BASIC_JOB_NAME = 'tushare_stock_basic'
STK_PREMARKET_JOB_NAME = 'tushare_stk_premarket'
STOCK_ST_JOB_NAME = 'tushare_stock_st'
ST_RISK_JOB_NAME = 'tushare_st_risk_notice'
STOCK_HSGT_JOB_NAME = 'tushare_stock_hsgt'
NAMECHANGE_JOB_NAME = 'tushare_stock_namechange'
STOCK_COMPANY_JOB_NAME = 'tushare_stock_company'
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
STOCK_HSGT_TYPES = ['HK_SH', 'HK_SZ']
STOCK_COMPANY_EXCHANGES = ['SSE', 'SZSE', 'BSE']
DATE_FIELD_BY_TABLE = {
    'trade_cal': 'cal_date',
    'stk_premarket': 'trade_date',
    'stock_st': 'trade_date',
    'stock_hsgt': 'trade_date',
    'daily': 'trade_date',
    'daily_basic': 'trade_date',
}


class TushareSyncError(RuntimeError):
    pass


def log_sync(message):
    setup_logging().info(message)


def get_tushare_client():
    setup_logging()
    token = settings.TUSHARE_TOKEN
    if not token:
        raise TushareSyncError('TUSHARE_TOKEN is empty. Set it in backend/.env first.')

    log_sync('Initializing TuShare client.')
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


def parse_date_text(value):
    return datetime.strptime(value, DATE_FORMAT).date()


def shift_date_text(value, days=1):
    return (parse_date_text(value) + timedelta(days=days)).strftime(DATE_FORMAT)


def default_start_date():
    days_back = settings.TUSHARE_SYNC_DAYS_BACK
    return (timezone.localdate() - timedelta(days=days_back)).strftime(DATE_FORMAT)


def full_start_date():
    return settings.TUSHARE_FULL_SYNC_START_DATE


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


def mark_named_running(name, start_date=None, end_date=None, current_date='', current_step='', reset_progress=False):
    update = {
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
    return save_job(update, set_on_insert={'processed_dates': 0}, name=name)


def mark_named_finished(name, message):
    save_job({'status': STATUS_SUCCESS, 'current_step': 'done', 'message': message}, name=name)


def mark_named_failed(name, message):
    save_job({'status': STATUS_FAILED, 'message': message}, name=name)


def increment_named_processed_dates(name):
    with transaction.atomic():
        job = SyncJob.objects.select_for_update().filter(name=name).first()
        if not job:
            SyncJob.objects.create(name=name, status=STATUS_RUNNING, processed_dates=1, current_step='done')
            return
        job.processed_dates += 1
        job.current_step = 'done'
        job.save(update_fields=['processed_dates', 'current_step', 'updated_at'])


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


def latest_stored_date(table_name):
    date_field = DATE_FIELD_BY_TABLE.get(table_name)
    if not date_field:
        return None

    model = model_for(table_name)
    return model.objects.exclude(**{f'{date_field}__isnull': True}).exclude(**{date_field: ''}).aggregate(
        latest_date=Max(date_field)
    )['latest_date']


def resolve_auto_start_date(table_names, fallback_start_date):
    latest_dates = [latest_stored_date(table_name) for table_name in table_names]
    latest_dates = [value for value in latest_dates if value]
    if not latest_dates:
        return fallback_start_date

    # Use the earliest latest-date in the group so lagging tables can catch up safely via upsert.
    return shift_date_text(min(latest_dates), 1)


def is_empty_date_range(start_date, end_date):
    return parse_date_text(start_date) > parse_date_text(end_date)


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
        log_sync('Starting stock_basic sync.')
        result = sync_stock_basic(pro)
        message = f"stocks={result['stocks']}, changes={result['changes']}"
        log_sync(f'Finished stock_basic sync: {message}.')
        mark_stock_basic_finished(message)
        job = get_sync_job(STOCK_BASIC_JOB_NAME)
        return {
            'status': job.status,
            'message': job.message,
        }
    except Exception as exc:
        mark_stock_basic_failed(str(exc))
        setup_logging().exception(f'stock_basic sync failed: {exc}')
        raise


def resolve_date_range(start_date=None, end_date=None, table_names=None, fallback_start_date=None):
    resolved_end_date = end_date or today_text()
    if start_date:
        return start_date, resolved_end_date

    fallback_start_date = fallback_start_date or settings.TUSHARE_SYNC_START_DATE or default_start_date()
    if not table_names:
        return fallback_start_date, resolved_end_date

    return resolve_auto_start_date(table_names, fallback_start_date), resolved_end_date


def resolve_incremental_date_range(start_date=None, end_date=None, full=False, table_names=None):
    if full:
        return start_date or full_start_date(), end_date or today_text()
    return resolve_date_range(
        start_date=start_date,
        end_date=end_date,
        table_names=table_names,
        fallback_start_date=default_start_date(),
    )


def stock_basic_codes(pro=None):
    model = model_for('stock_basic')
    codes = list(model.objects.order_by('ts_code').values_list('ts_code', flat=True))
    if codes or not pro:
        return codes

    fields = 'ts_code'
    found = set()
    for list_status in ('L', 'D', 'P', 'G'):
        records = dataframe_records(pro.stock_basic(exchange='', list_status=list_status, fields=fields))
        found.update(record['ts_code'] for record in records if record.get('ts_code'))
    return sorted(found)


def sync_trade_cal_data(start_date=None, end_date=None):
    pro = get_tushare_client()
    start_date, end_date = resolve_date_range(start_date, end_date, table_names=['trade_cal'])
    log_sync(f'Starting trade_cal sync: start_date={start_date}, end_date={end_date}.')
    if is_empty_date_range(start_date, end_date):
        log_sync('trade_cal is already up to date.')
        return {
            'status': STATUS_SUCCESS,
            'start_date': start_date,
            'end_date': end_date,
            'open_trade_dates': 0,
            'message': 'already up to date',
        }
    trade_dates = get_trade_dates(pro, start_date, end_date)
    log_sync(f'Finished trade_cal sync: open_trade_dates={len(trade_dates)}.')
    return {
        'status': STATUS_SUCCESS,
        'start_date': start_date,
        'end_date': end_date,
        'open_trade_dates': len(trade_dates),
    }


def sync_daily_quote_data(start_date=None, end_date=None):
    pro = get_tushare_client()
    start_date, end_date = resolve_date_range(start_date, end_date, table_names=['daily'])
    log_sync(f'Starting daily sync: start_date={start_date}, end_date={end_date}.')
    if is_empty_date_range(start_date, end_date):
        log_sync('daily is already up to date.')
        return {
            'status': STATUS_SUCCESS,
            'start_date': start_date,
            'end_date': end_date,
            'daily_quotes': 0,
            'message': 'already up to date',
        }
    trade_dates = get_trade_dates(pro, start_date, end_date)
    quote_count = 0
    for trade_date in trade_dates:
        daily_count = sync_daily_quote(pro, trade_date)
        quote_count += daily_count
        log_sync(f'daily {trade_date}: upserted={daily_count}, total={quote_count}.')
    log_sync(f'Finished daily sync: daily_quotes={quote_count}.')
    return {
        'status': STATUS_SUCCESS,
        'start_date': start_date,
        'end_date': end_date,
        'daily_quotes': quote_count,
    }


def sync_daily_basic_data(start_date=None, end_date=None):
    pro = get_tushare_client()
    start_date, end_date = resolve_date_range(start_date, end_date, table_names=['daily_basic'])
    log_sync(f'Starting daily_basic sync: start_date={start_date}, end_date={end_date}.')
    if is_empty_date_range(start_date, end_date):
        log_sync('daily_basic is already up to date.')
        return {
            'status': STATUS_SUCCESS,
            'start_date': start_date,
            'end_date': end_date,
            'daily_basics': 0,
            'message': 'already up to date',
        }
    trade_dates = get_trade_dates(pro, start_date, end_date)
    basic_count = 0
    for trade_date in trade_dates:
        row_count = sync_daily_basic(pro, trade_date)
        basic_count += row_count
        log_sync(f'daily_basic {trade_date}: upserted={row_count}, total={basic_count}.')
    log_sync(f'Finished daily_basic sync: daily_basics={basic_count}.')
    return {
        'status': STATUS_SUCCESS,
        'start_date': start_date,
        'end_date': end_date,
        'daily_basics': basic_count,
    }


def sync_stk_premarket(pro, trade_date):
    fields = ','.join(fields_for('stk_premarket'))
    records = dataframe_records(pro.stk_premarket(trade_date=trade_date, fields=fields))
    return bulk_upsert('stk_premarket', records, ['ts_code', 'trade_date'])


def sync_stock_st(pro, trade_date):
    fields = ','.join(fields_for('stock_st'))
    records = dataframe_records(pro.stock_st(trade_date=trade_date, fields=fields))
    return bulk_upsert('stock_st', records, ['ts_code', 'trade_date', 'type'])


def sync_stock_hsgt(pro, trade_date):
    fields = ','.join(fields_for('stock_hsgt'))
    count = 0
    for hsgt_type in STOCK_HSGT_TYPES:
        records = dataframe_records(pro.stock_hsgt(trade_date=trade_date, type=hsgt_type, fields=fields))
        count += bulk_upsert('stock_hsgt', records, ['ts_code', 'trade_date', 'type'])
    return count


def sync_date_table_data(table_name, job_name, sync_func, start_date=None, end_date=None, full=False, resume=True):
    pro = get_tushare_client()
    start_date, end_date = resolve_incremental_date_range(
        start_date,
        end_date,
        full=full,
        table_names=[table_name],
    )
    log_sync(
        f'Starting {table_name} sync: start_date={start_date}, end_date={end_date}, '
        f'full={full}, resume={resume}.'
    )
    if is_empty_date_range(start_date, end_date):
        log_sync(f'{table_name} is already up to date.')
        mark_named_finished(job_name, f'{table_name}=0, already up to date')
        job = get_sync_job(job_name)
        return {
            'status': job.status,
            'message': job.message,
            'start_date': start_date,
            'end_date': end_date,
            'processed_dates': job.processed_dates if job else 0,
        }
    existing_job = get_sync_job(job_name)
    reset_progress = not resume or not existing_job or existing_job.status != STATUS_RUNNING
    mark_named_running(job_name, start_date, end_date, current_step=table_name, reset_progress=reset_progress)

    try:
        trade_dates = get_trade_dates(pro, start_date, end_date)
        job = get_sync_job(job_name)
        trade_dates = resume_dates(job, trade_dates)
        row_count = 0
        for trade_date in trade_dates:
            mark_named_running(job_name, start_date, end_date, current_date=trade_date, current_step=table_name)
            current_count = sync_func(pro, trade_date)
            row_count += current_count
            increment_named_processed_dates(job_name)
            log_sync(f'{table_name} {trade_date}: upserted={current_count}, total={row_count}.')

        message = f'{table_name}={row_count}'
        log_sync(f'Finished {table_name} sync: {message}.')
        mark_named_finished(job_name, message)
        job = get_sync_job(job_name)
        return {
            'status': job.status,
            'message': job.message,
            'start_date': job.start_date,
            'end_date': job.end_date,
            'processed_dates': job.processed_dates,
        }
    except Exception as exc:
        mark_named_failed(job_name, str(exc))
        setup_logging().exception(f'{table_name} sync failed: {exc}')
        raise


def sync_stk_premarket_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        'stk_premarket',
        STK_PREMARKET_JOB_NAME,
        sync_stk_premarket,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_stock_st_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        'stock_st',
        STOCK_ST_JOB_NAME,
        sync_stock_st,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_stock_hsgt_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        'stock_hsgt',
        STOCK_HSGT_JOB_NAME,
        sync_stock_hsgt,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_st_risk_data():
    pro = get_tushare_client()
    mark_named_running(ST_RISK_JOB_NAME, current_step='st')
    try:
        log_sync('Starting st sync.')
        fields = ','.join(fields_for('st'))
        count = 0
        for ts_code in stock_basic_codes(pro):
            records = dataframe_records(pro.st(ts_code=ts_code, fields=fields))
            count += bulk_upsert('st', records, ['ts_code', 'pub_date', 'st_tpye'])
        message = f'st={count}'
        log_sync(f'Finished st sync: {message}.')
        mark_named_finished(ST_RISK_JOB_NAME, message)
        job = get_sync_job(ST_RISK_JOB_NAME)
        return {'status': job.status, 'message': job.message}
    except Exception as exc:
        mark_named_failed(ST_RISK_JOB_NAME, str(exc))
        setup_logging().exception(f'st sync failed: {exc}')
        raise


def sync_namechange_data():
    pro = get_tushare_client()
    mark_named_running(NAMECHANGE_JOB_NAME, current_step='namechange')
    try:
        log_sync('Starting namechange sync.')
        fields = ','.join(fields_for('namechange'))
        count = 0
        for ts_code in stock_basic_codes(pro):
            records = dataframe_records(pro.namechange(ts_code=ts_code, fields=fields))
            count += bulk_upsert('namechange', records, ['ts_code', 'name', 'start_date'])
        message = f'namechange={count}'
        log_sync(f'Finished namechange sync: {message}.')
        mark_named_finished(NAMECHANGE_JOB_NAME, message)
        job = get_sync_job(NAMECHANGE_JOB_NAME)
        return {'status': job.status, 'message': job.message}
    except Exception as exc:
        mark_named_failed(NAMECHANGE_JOB_NAME, str(exc))
        setup_logging().exception(f'namechange sync failed: {exc}')
        raise


def sync_stock_company_data():
    pro = get_tushare_client()
    mark_named_running(STOCK_COMPANY_JOB_NAME, current_step='stock_company')
    try:
        log_sync('Starting stock_company sync.')
        fields = ','.join(fields_for('stock_company'))
        count = 0
        for exchange in STOCK_COMPANY_EXCHANGES:
            records = dataframe_records(pro.stock_company(exchange=exchange, fields=fields))
            current_count = bulk_upsert('stock_company', records, ['ts_code'])
            count += current_count
            log_sync(f'stock_company exchange={exchange}: upserted={current_count}, total={count}.')
        message = f'stock_company={count}'
        log_sync(f'Finished stock_company sync: {message}.')
        mark_named_finished(STOCK_COMPANY_JOB_NAME, message)
        job = get_sync_job(STOCK_COMPANY_JOB_NAME)
        return {'status': job.status, 'message': job.message}
    except Exception as exc:
        mark_named_failed(STOCK_COMPANY_JOB_NAME, str(exc))
        setup_logging().exception(f'stock_company sync failed: {exc}')
        raise


def sync_daily_quote(pro, trade_date):
    records = dataframe_records(pro.daily(trade_date=trade_date))
    return bulk_upsert('daily', records, ['ts_code', 'trade_date'])


def sync_daily_basic(pro, trade_date):
    fields = 'ts_code,trade_date,close,turnover_rate,volume_ratio,pe_ttm,pb,ps_ttm,dv_ttm,total_mv,circ_mv'
    records = dataframe_records(pro.daily_basic(trade_date=trade_date, fields=fields))
    return bulk_upsert('daily_basic', records, ['ts_code', 'trade_date'])


def sync_market_data(start_date=None, end_date=None, resume=True):
    pro = get_tushare_client()

    start_date, end_date = resolve_date_range(
        start_date,
        end_date,
        table_names=['trade_cal', 'daily', 'daily_basic'],
    )
    log_sync(f'Starting market_data sync: start_date={start_date}, end_date={end_date}, resume={resume}.')
    if is_empty_date_range(start_date, end_date):
        log_sync('market_data is already up to date.')
        mark_finished('daily_quotes=0, daily_basics=0, already up to date')
        job = get_job()
        return {
            'status': job.status,
            'message': job.message,
            'start_date': start_date,
            'end_date': end_date,
            'processed_dates': job.processed_dates if job else 0,
        }
    existing_job = get_job()
    reset_progress = not resume or not existing_job or existing_job.status != STATUS_RUNNING

    mark_running(start_date, end_date, current_step='trade_cal', reset_progress=reset_progress)

    try:
        trade_dates = get_trade_dates(pro, start_date, end_date)
        job = get_job()
        trade_dates = resume_dates(job, trade_dates)
        log_sync(f'market_data trade dates to process: {len(trade_dates)}.')

        quote_count = 0
        basic_count = 0

        for trade_date in trade_dates:
            mark_running(start_date, end_date, current_date=trade_date, current_step='daily')
            daily_count = sync_daily_quote(pro, trade_date)
            quote_count += daily_count

            mark_running(start_date, end_date, current_date=trade_date, current_step='daily_basic')
            basic_row_count = sync_daily_basic(pro, trade_date)
            basic_count += basic_row_count
            increment_processed_dates()
            log_sync(
                f'market_data {trade_date}: daily_upserted={daily_count}, '
                f'daily_basic_upserted={basic_row_count}, '
                f'daily_total={quote_count}, daily_basic_total={basic_count}.'
            )

        message = f'daily_quotes={quote_count}, daily_basics={basic_count}'
        log_sync(f'Finished market_data sync: {message}.')
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
        setup_logging().exception(f'market_data sync failed: {exc}')
        raise
