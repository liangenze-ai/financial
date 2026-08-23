import time
from datetime import datetime, timedelta

from api.models import StockBasicHistory, SyncJob
from api.services.postgres import catalog_for, fields_for
from api.services.postgres import get_job as get_sync_job
from api.services.postgres import model_for
from config.logging_setup import logger
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone

DATE_FORMAT = "%Y%m%d"
JOB_NAME = "tushare_market_data"
STOCK_BASIC_JOB_NAME = "tushare_stock_basic"
STK_PREMARKET_JOB_NAME = "tushare_stk_premarket"
STOCK_ST_JOB_NAME = "tushare_stock_st"
ST_RISK_JOB_NAME = "tushare_st_risk_notice"
STOCK_HSGT_JOB_NAME = "tushare_stock_hsgt"
NAMECHANGE_JOB_NAME = "tushare_stock_namechange"
STOCK_COMPANY_JOB_NAME = "tushare_stock_company"
ADJ_FACTOR_JOB_NAME = "tushare_adj_factor"
FINA_INDICATOR_JOB_NAME = "tushare_fina_indicator"
INCOME_JOB_NAME = "tushare_income"
BALANCESHEET_JOB_NAME = "tushare_balancesheet"
CASHFLOW_JOB_NAME = "tushare_cashflow"
INDEX_BASIC_JOB_NAME = "tushare_index_basic"
INDEX_DAILY_JOB_NAME = "tushare_index_daily"
INDEX_CLASSIFY_JOB_NAME = "tushare_index_classify"
INDEX_MEMBER_ALL_JOB_NAME = "tushare_index_member_all"
MONEYFLOW_JOB_NAME = "tushare_moneyflow"
MARGIN_DETAIL_JOB_NAME = "tushare_margin_detail"
HK_HOLD_JOB_NAME = "tushare_hk_hold"
SUSPEND_D_JOB_NAME = "tushare_suspend_d"
STK_LIMIT_JOB_NAME = "tushare_stk_limit"
SHARE_FLOAT_JOB_NAME = "tushare_share_float"
PLEDGE_STAT_JOB_NAME = "tushare_pledge_stat"
STK_FACTOR_PRO_JOB_NAME = "tushare_stk_factor_pro"
MARGIN_JOB_NAME = "tushare_margin"
PLEDGE_DETAIL_JOB_NAME = "tushare_pledge_detail"
FORECAST_JOB_NAME = "tushare_forecast"
EXPRESS_JOB_NAME = "tushare_express"
BLOCK_TRADE_JOB_NAME = "tushare_block_trade"
TOP_LIST_JOB_NAME = "tushare_top_list"
TOP_INST_JOB_NAME = "tushare_top_inst"
DIVIDEND_JOB_NAME = "tushare_dividend"
REPURCHASE_JOB_NAME = "tushare_repurchase"
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
TUSHARE_CALL_INTERVAL_SECONDS = 0.25
TUSHARE_MAX_RETRIES = 5
TUSHARE_RETRY_MESSAGES = (
    "频率超限",
    "Read timed out",
    "Connection aborted",
    "Connection reset",
    "Max retries exceeded",
)
STOCK_BASIC_FIELDS = [
    "ts_code",
    "symbol",
    "name",
    "area",
    "industry",
    "fullname",
    "enname",
    "cnspell",
    "market",
    "exchange",
    "curr_type",
    "list_status",
    "list_date",
    "delist_date",
    "is_hs",
    "act_name",
    "act_ent_type",
]
STOCK_BASIC_CHANGE_FIELDS = [
    "name",
    "fullname",
    "act_name",
    "act_ent_type",
    "industry",
    "area",
    "market",
    "exchange",
    "list_status",
]
STOCK_HSGT_TYPES = ["HK_SH", "HK_SZ"]
STOCK_COMPANY_EXCHANGES = ["SSE", "SZSE", "BSE"]
INDEX_BASIC_MARKETS = ["SSE", "SZSE", "CSI", "CICC", "SW", "OTH"]
INDEX_CLASSIFY_SOURCES = ["SW2021"]
HK_HOLD_EXCHANGES = ["SH", "SZ"]
MARGIN_EXCHANGES = ["SSE", "SZSE"]
DEFAULT_INDEX_CODES = ["000300.SH", "000905.SH", "000906.SH", "000852.SH", "399006.SZ", "000001.SH", "399001.SZ"]
DATE_FIELD_BY_TABLE = {
    "trade_cal": "cal_date",
    "stk_premarket": "trade_date",
    "stock_st": "trade_date",
    "stock_hsgt": "trade_date",
    "daily": "trade_date",
    "daily_basic": "trade_date",
    "adj_factor": "trade_date",
    "index_daily": "trade_date",
    "moneyflow": "trade_date",
    "margin_detail": "trade_date",
    "hk_hold": "trade_date",
    "suspend_d": "suspend_date",
    "stk_limit": "trade_date",
    "share_float": "float_date",
    "pledge_stat": "end_date",
    "fina_indicator": "ann_date",
    "income": "ann_date",
    "balancesheet": "ann_date",
    "cashflow": "ann_date",
    "stk_factor_pro": "trade_date",
    "margin": "trade_date",
    "pledge_detail": "ann_date",
    "forecast": "ann_date",
    "express": "ann_date",
    "block_trade": "trade_date",
    "top_list": "trade_date",
    "top_inst": "trade_date",
    "dividend": "ann_date",
    "repurchase": "ann_date",
}
PERIOD_FIELD_BY_TABLE = {
    'fina_indicator': 'end_date',
    'income': 'end_date',
    'balancesheet': 'end_date',
    'cashflow': 'end_date',
}


class TushareSyncError(RuntimeError):
    pass


def log_sync(message):
    logger.info(message)


def get_tushare_client():
    token = settings.TUSHARE_TOKEN
    if not token:
        raise TushareSyncError("TUSHARE_TOKEN is empty. Set it in backend/.env first.")

    log_sync("Initializing TuShare client.")
    try:
        import tushare as ts
    except ImportError as exc:
        raise TushareSyncError("tushare is not installed. Run pip install -r backend/requirements.txt.") from exc

    return TushareClient(ts.pro_api(token))


class TushareClient:
    def __init__(self, pro):
        self.pro = pro
        self.last_call_at = 0

    def __getattr__(self, name):
        target = getattr(self.pro, name)
        if not callable(target):
            return target

        def call_with_retry(*args, **kwargs):
            for attempt in range(TUSHARE_MAX_RETRIES):
                elapsed = time.monotonic() - self.last_call_at
                if elapsed < TUSHARE_CALL_INTERVAL_SECONDS:
                    time.sleep(TUSHARE_CALL_INTERVAL_SECONDS - elapsed)
                try:
                    result = target(*args, **kwargs)
                    self.last_call_at = time.monotonic()
                    return result
                except Exception as exc:
                    self.last_call_at = time.monotonic()
                    message = str(exc)
                    if not any(text in message for text in TUSHARE_RETRY_MESSAGES):
                        raise
                    if attempt == TUSHARE_MAX_RETRIES - 1:
                        raise
                    wait_seconds = min(60, 2**attempt * 5)
                    log_sync(f"TuShare {name} retry {attempt + 1}/{TUSHARE_MAX_RETRIES}: {message}")
                    time.sleep(wait_seconds)
            return target(*args, **kwargs)

        return call_with_retry


def dataframe_records(frame):
    if frame is None or frame.empty:
        return []
    return frame.where(frame.notna(), None).to_dict("records")


def now():
    return timezone.now()


def today_text():
    return timezone.localdate().strftime(DATE_FORMAT)


def parse_date_text(value):
    return datetime.strptime(value, DATE_FORMAT).date()


def shift_date_text(value, days=1):
    return (parse_date_text(value) + timedelta(days=days)).strftime(DATE_FORMAT)


def calendar_dates(start_date, end_date):
    current = parse_date_text(start_date)
    end = parse_date_text(end_date)
    dates = []
    while current <= end:
        dates.append(current.strftime(DATE_FORMAT))
        current += timedelta(days=1)
    return dates


def quarter_periods(start_date, end_date):
    start = parse_date_text(start_date)
    end = parse_date_text(end_date)
    years = range(start.year, end.year + 1)
    periods = []
    for year in years:
        for month_day in ("0331", "0630", "0930", "1231"):
            period = f"{year}{month_day}"
            if start_date <= period <= end_date:
                periods.append(period)
    return periods


def default_start_date():
    days_back = settings.TUSHARE_SYNC_DAYS_BACK
    return (timezone.localdate() - timedelta(days=days_back)).strftime(DATE_FORMAT)


def full_start_date():
    return settings.TUSHARE_FULL_SYNC_START_DATE


def clean_value(value):
    if value is None:
        return None
    text = str(value)
    if text in ("", "nan", "NaN", "None", "<NA>", "NaT"):
        return None
    return value


def clean_record(record):
    return {key: clean_value(value) for key, value in record.items()}


def attach_catalog(record, catalog_name):
    record["tushare_meta"] = catalog_for(catalog_name)
    return record


def bulk_upsert(table_name, records, key_fields):
    if not records:
        return 0

    model = model_for(table_name)
    allowed_fields = set(fields_for(table_name))
    objects_by_key = {}
    timestamp = now()
    for raw_record in records:
        record = attach_catalog(clean_record(raw_record), table_name)
        if not all(record.get(field) is not None for field in key_fields):
            continue

        values = {field: record.get(field) for field in allowed_fields}
        values["tushare_meta"] = record["tushare_meta"]
        values["created_at"] = timestamp
        values["updated_at"] = timestamp
        key = tuple(record.get(field) for field in key_fields)
        objects_by_key[key] = model(**values)

    if not objects_by_key:
        return 0

    objects = list(objects_by_key.values())

    update_fields = [field for field in fields_for(table_name) if field not in key_fields]
    update_fields.extend(["tushare_meta", "updated_at"])
    model.objects.bulk_create(
        objects,
        batch_size=1000,
        update_conflicts=True,
        update_fields=update_fields,
        unique_fields=key_fields,
    )
    return len(objects)


def sync_paged_api(pro, table_name, api_name, key_fields, params=None, page_size=3000):
    fields = ",".join(fields_for(table_name))
    api = getattr(pro, api_name)
    params = params or {}
    offset = 0
    count = 0
    seen_pages = set()
    while True:
        records = dataframe_records(api(fields=fields, limit=page_size, offset=offset, **params))
        if not records:
            break
        page_key = tuple(tuple(sorted(record.items())) for record in records)
        if page_key in seen_pages:
            log_sync(f"{table_name} repeated page at offset={offset}; stopping pagination.")
            break
        seen_pages.add(page_key)
        count += bulk_upsert(table_name, records, key_fields)
        if len(records) < page_size:
            break
        offset += page_size
    return count


def get_job():
    return get_sync_job(JOB_NAME)


def save_job(update, set_on_insert=None, name=JOB_NAME):
    update = {key: value for key, value in update.items() if key != "name"}
    create_defaults = {**(set_on_insert or {}), **update}
    job, created = SyncJob.objects.get_or_create(name=name, defaults=create_defaults)
    if not created:
        for key, value in update.items():
            setattr(job, key, value)
        job.save()
    return job


def mark_running(start_date, end_date, current_date="", current_step="", reset_progress=False):
    update = {
        "name": JOB_NAME,
        "status": STATUS_RUNNING,
        "start_date": start_date,
        "end_date": end_date,
        "current_step": current_step,
        "message": "",
    }
    if current_date:
        update["current_date"] = current_date
    if reset_progress:
        update["current_date"] = ""
        update["processed_dates"] = 0

    return save_job(update, set_on_insert={"processed_dates": 0})


def mark_finished(message):
    save_job({"status": STATUS_SUCCESS, "current_step": "done", "message": message})


def mark_failed(message):
    save_job({"status": STATUS_FAILED, "message": message})


def mark_stock_basic_running():
    return save_job(
        {
            "status": STATUS_RUNNING,
            "start_date": None,
            "end_date": today_text(),
            "current_date": "",
            "current_step": "stock_basic",
            "processed_dates": 0,
            "message": "",
        },
        name=STOCK_BASIC_JOB_NAME,
    )


def mark_stock_basic_finished(message):
    save_job(
        {"status": STATUS_SUCCESS, "current_step": "done", "message": message},
        name=STOCK_BASIC_JOB_NAME,
    )


def mark_stock_basic_failed(message):
    save_job({"status": STATUS_FAILED, "message": message}, name=STOCK_BASIC_JOB_NAME)


def mark_named_running(name, start_date=None, end_date=None, current_date="", current_step="", reset_progress=False):
    update = {
        "status": STATUS_RUNNING,
        "start_date": start_date,
        "end_date": end_date,
        "current_step": current_step,
        "message": "",
    }
    if current_date:
        update["current_date"] = current_date
    if reset_progress:
        update["current_date"] = ""
        update["processed_dates"] = 0
    return save_job(update, set_on_insert={"processed_dates": 0}, name=name)


def mark_named_finished(name, message):
    save_job({"status": STATUS_SUCCESS, "current_step": "done", "message": message}, name=name)


def mark_named_failed(name, message):
    save_job({"status": STATUS_FAILED, "message": message}, name=name)


def increment_named_processed_dates(name):
    with transaction.atomic():
        job = SyncJob.objects.select_for_update().filter(name=name).first()
        if not job:
            SyncJob.objects.create(name=name, status=STATUS_RUNNING, processed_dates=1, current_step="done")
            return
        job.processed_dates += 1
        job.current_step = "done"
        job.save(update_fields=["processed_dates", "current_step", "updated_at"])


def increment_processed_dates():
    with transaction.atomic():
        job = SyncJob.objects.select_for_update().filter(name=JOB_NAME).first()
        if not job:
            SyncJob.objects.create(name=JOB_NAME, status=STATUS_RUNNING, processed_dates=1, current_step="done")
            return
        job.processed_dates += 1
        job.current_step = "done"
        job.save(update_fields=["processed_dates", "current_step", "updated_at"])


def get_trade_dates(pro, start_date, end_date):
    fields = "exchange,cal_date,is_open,pretrade_date"
    records = dataframe_records(pro.trade_cal(exchange="SSE", start_date=start_date, end_date=end_date, fields=fields))
    bulk_upsert("trade_cal", records, ["exchange", "cal_date"])
    return [record["cal_date"] for record in records if str(record.get("is_open")) == "1"]


def ensure_sync_date_coverage_table():
    with connection.cursor() as cursor:
        cursor.execute("""
            create table if not exists system_sync_date_coverage (
                id bigserial primary key,
                job_name varchar(80) not null,
                trade_date varchar(8) not null,
                status varchar(24) not null default 'success',
                rows_count integer not null default 0,
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now(),
                constraint uniq_sync_date_coverage unique (job_name, trade_date)
            )
            """)
        cursor.execute("""
            create index if not exists ix_sync_date_coverage_job_date
            on system_sync_date_coverage (job_name, trade_date)
            """)


def mark_sync_date_covered(job_name, trade_date, rows_count):
    ensure_sync_date_coverage_table()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into system_sync_date_coverage (
                job_name, trade_date, status, rows_count, created_at, updated_at
            )
            values (%s, %s, 'success', %s, now(), now())
            on conflict (job_name, trade_date) do update set
                status = excluded.status,
                rows_count = excluded.rows_count,
                updated_at = excluded.updated_at
            """,
            [job_name, trade_date, rows_count],
        )


def covered_sync_dates(job_name, start_date, end_date):
    ensure_sync_date_coverage_table()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select trade_date
            from system_sync_date_coverage
            where job_name = %s
              and status = 'success'
              and trade_date >= %s
              and trade_date <= %s
            """,
            [job_name, start_date, end_date],
        )
        return {row[0] for row in cursor.fetchall()}


def existing_table_dates(table_name, start_date, end_date):
    date_field = DATE_FIELD_BY_TABLE.get(table_name)
    if not date_field:
        return set()

    model = model_for(table_name)
    queryset = (
        model.objects.exclude(**{f"{date_field}__isnull": True})
        .exclude(**{date_field: ""})
        .filter(**{f"{date_field}__gte": start_date, f"{date_field}__lte": end_date})
        .values_list(date_field, flat=True)
        .distinct()
    )
    return set(queryset)


def existing_table_dates_for(table_name, dates):
    date_field = DATE_FIELD_BY_TABLE.get(table_name)
    if not date_field or not dates:
        return set()

    model = model_for(table_name)
    queryset = (
        model.objects.exclude(**{f"{date_field}__isnull": True})
        .exclude(**{date_field: ""})
        .filter(**{f"{date_field}__in": dates})
        .values_list(date_field, flat=True)
        .distinct()
    )
    return set(queryset)


def covered_sync_dates_for(job_name, dates):
    if not dates:
        return set()

    ensure_sync_date_coverage_table()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select trade_date
            from system_sync_date_coverage
            where job_name = %s
              and status = 'success'
              and trade_date = any(%s)
            """,
            [job_name, dates],
        )
        return {row[0] for row in cursor.fetchall()}


def existing_table_values(table_name, field_name, start_date, end_date):
    model = model_for(table_name)
    queryset = (
        model.objects
        .exclude(**{f'{field_name}__isnull': True})
        .exclude(**{field_name: ''})
        .filter(**{f'{field_name}__gte': start_date, f'{field_name}__lte': end_date})
        .values_list(field_name, flat=True)
        .distinct()
    )
    return set(queryset)


def missing_trade_dates(table_name, job_name, trade_dates, start_date, end_date):
    covered_dates = covered_sync_dates_for(job_name, trade_dates)
    existing_dates = existing_table_dates_for(table_name, trade_dates)
    known_dates = covered_dates | existing_dates
    return [trade_date for trade_date in trade_dates if trade_date not in known_dates]


def missing_calendar_dates(table_name, job_name, dates, start_date, end_date):
    covered_dates = covered_sync_dates(job_name, start_date, end_date)
    existing_dates = existing_table_dates(table_name, start_date, end_date)
    known_dates = covered_dates | existing_dates
    return [date for date in dates if date not in known_dates]


def missing_periods(table_name, job_name, periods, start_date, end_date):
    covered_periods = covered_sync_dates(job_name, start_date, end_date)
    period_field = PERIOD_FIELD_BY_TABLE.get(table_name, 'end_date')
    existing_periods = existing_table_values(table_name, period_field, start_date, end_date)
    known_periods = covered_periods | existing_periods
    return [period for period in periods if period not in known_periods]


def contiguous_date_ranges(dates):
    if not dates:
        return []

    sorted_dates = sorted(dates)
    ranges = []
    range_start = sorted_dates[0]
    previous = sorted_dates[0]
    for date in sorted_dates[1:]:
        if parse_date_text(date) == parse_date_text(previous) + timedelta(days=1):
            previous = date
            continue
        ranges.append((range_start, previous))
        range_start = date
        previous = date
    ranges.append((range_start, previous))
    return ranges


def resume_dates(job, trade_dates):
    if not job or job.status != STATUS_RUNNING or not job.current_date:
        return trade_dates
    current_date = job.current_date
    if current_date not in trade_dates:
        return trade_dates
    return trade_dates[trade_dates.index(current_date) :]


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
    return (
        model.objects.exclude(**{f"{date_field}__isnull": True})
        .exclude(**{date_field: ""})
        .aggregate(latest_date=Max(date_field))["latest_date"]
    )


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
                ts_code=record["ts_code"],
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
    model = model_for("stock_basic")
    fields = ",".join(STOCK_BASIC_FIELDS)
    synced = 0
    change_count = 0

    for list_status in ("L", "D", "P", "G"):
        records = dataframe_records(pro.stock_basic(exchange="", list_status=list_status, fields=fields))
        for raw_record in records:
            record = clean_record(raw_record)
            ts_code = record.get("ts_code")
            if not ts_code:
                continue

            existing = model.objects.filter(ts_code=ts_code).first()
            record["tushare_meta"] = catalog_for("stock_basic")
            change_count += record_stock_basic_changes(existing, record)

            defaults = {field: record.get(field) for field in fields_for("stock_basic") if field != "ts_code"}
            defaults["tushare_meta"] = record["tushare_meta"]
            model.objects.update_or_create(ts_code=ts_code, defaults=defaults)
            synced += 1

    return {"stocks": synced, "changes": change_count}


def sync_stock_basic_data():
    pro = get_tushare_client()
    mark_stock_basic_running()
    try:
        log_sync("Starting stock_basic sync.")
        result = sync_stock_basic(pro)
        message = f"stocks={result['stocks']}, changes={result['changes']}"
        log_sync(f"Finished stock_basic sync: {message}.")
        mark_stock_basic_finished(message)
        job = get_sync_job(STOCK_BASIC_JOB_NAME)
        return {
            "status": job.status,
            "message": job.message,
        }
    except Exception as exc:
        mark_stock_basic_failed(str(exc))
        logger.exception(f"stock_basic sync failed: {exc}")
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
    model = model_for("stock_basic")
    codes = list(model.objects.order_by("ts_code").values_list("ts_code", flat=True))
    if codes or not pro:
        return codes

    fields = "ts_code"
    found = set()
    for list_status in ("L", "D", "P", "G"):
        records = dataframe_records(pro.stock_basic(exchange="", list_status=list_status, fields=fields))
        found.update(record["ts_code"] for record in records if record.get("ts_code"))
    return sorted(found)


def sync_trade_cal_data(start_date=None, end_date=None):
    pro = get_tushare_client()
    start_date, end_date = resolve_date_range(start_date, end_date, table_names=["trade_cal"])
    log_sync(f"Starting trade_cal sync: start_date={start_date}, end_date={end_date}.")
    if is_empty_date_range(start_date, end_date):
        log_sync("trade_cal is already up to date.")
        return {
            "status": STATUS_SUCCESS,
            "start_date": start_date,
            "end_date": end_date,
            "open_trade_dates": 0,
            "message": "already up to date",
        }
    trade_dates = get_trade_dates(pro, start_date, end_date)
    log_sync(f"Finished trade_cal sync: open_trade_dates={len(trade_dates)}.")
    return {
        "status": STATUS_SUCCESS,
        "start_date": start_date,
        "end_date": end_date,
        "open_trade_dates": len(trade_dates),
    }


def sync_daily_quote_data(start_date=None, end_date=None, full=False, resume=True):
    pro = get_tushare_client()
    start_date, end_date = resolve_date_range(start_date, end_date, table_names=["daily"])
    log_sync(f"Starting daily sync: start_date={start_date}, end_date={end_date}.")
    if is_empty_date_range(start_date, end_date):
        log_sync("daily is already up to date.")
        return {
            "status": STATUS_SUCCESS,
            "start_date": start_date,
            "end_date": end_date,
            "daily_quotes": 0,
            "message": "already up to date",
        }
    trade_dates = get_trade_dates(pro, start_date, end_date)
    requested_dates = len(trade_dates)
    skipped_existing_dates = 0
    if not full and resume:
        missing_dates = missing_trade_dates("daily", JOB_NAME, trade_dates, start_date, end_date)
        skipped_existing_dates = requested_dates - len(missing_dates)
        trade_dates = missing_dates
        log_sync(
            f"daily missing-date scan: requested={requested_dates}, "
            f"missing={len(trade_dates)}, skipped_existing={skipped_existing_dates}."
        )
    quote_count = 0
    for trade_date in trade_dates:
        daily_count = sync_daily_quote(pro, trade_date)
        quote_count += daily_count
        mark_sync_date_covered(JOB_NAME, trade_date, daily_count)
        log_sync(f"daily {trade_date}: upserted={daily_count}, total={quote_count}.")
    log_sync(f"Finished daily sync: daily_quotes={quote_count}.")
    return {
        "status": STATUS_SUCCESS,
        "start_date": start_date,
        "end_date": end_date,
        "daily_quotes": quote_count,
        "requested_dates": requested_dates,
        "processed_dates": len(trade_dates),
        "skipped_existing_dates": skipped_existing_dates,
    }


def sync_daily_basic_data(start_date=None, end_date=None, full=False, resume=True):
    pro = get_tushare_client()
    start_date, end_date = resolve_date_range(start_date, end_date, table_names=["daily_basic"])
    log_sync(f"Starting daily_basic sync: start_date={start_date}, end_date={end_date}.")
    if is_empty_date_range(start_date, end_date):
        log_sync("daily_basic is already up to date.")
        return {
            "status": STATUS_SUCCESS,
            "start_date": start_date,
            "end_date": end_date,
            "daily_basics": 0,
            "message": "already up to date",
        }
    trade_dates = get_trade_dates(pro, start_date, end_date)
    requested_dates = len(trade_dates)
    skipped_existing_dates = 0
    if not full and resume:
        missing_dates = missing_trade_dates("daily_basic", f"{JOB_NAME}_daily_basic", trade_dates, start_date, end_date)
        skipped_existing_dates = requested_dates - len(missing_dates)
        trade_dates = missing_dates
        log_sync(
            f"daily_basic missing-date scan: requested={requested_dates}, "
            f"missing={len(trade_dates)}, skipped_existing={skipped_existing_dates}."
        )
    basic_count = 0
    for trade_date in trade_dates:
        row_count = sync_daily_basic(pro, trade_date)
        basic_count += row_count
        mark_sync_date_covered(f"{JOB_NAME}_daily_basic", trade_date, row_count)
        log_sync(f"daily_basic {trade_date}: upserted={row_count}, total={basic_count}.")
    log_sync(f"Finished daily_basic sync: daily_basics={basic_count}.")
    return {
        "status": STATUS_SUCCESS,
        "start_date": start_date,
        "end_date": end_date,
        "daily_basics": basic_count,
        "requested_dates": requested_dates,
        "processed_dates": len(trade_dates),
        "skipped_existing_dates": skipped_existing_dates,
    }


def sync_stk_premarket(pro, trade_date):
    fields = ",".join(fields_for("stk_premarket"))
    records = dataframe_records(pro.stk_premarket(trade_date=trade_date, fields=fields))
    return bulk_upsert("stk_premarket", records, ["ts_code", "trade_date"])


def sync_stock_st(pro, trade_date):
    fields = ",".join(fields_for("stock_st"))
    records = dataframe_records(pro.stock_st(trade_date=trade_date, fields=fields))
    return bulk_upsert("stock_st", records, ["ts_code", "trade_date", "type"])


def sync_stock_hsgt(pro, trade_date):
    fields = ",".join(fields_for("stock_hsgt"))
    count = 0
    for hsgt_type in STOCK_HSGT_TYPES:
        records = dataframe_records(pro.stock_hsgt(trade_date=trade_date, type=hsgt_type, fields=fields))
        count += bulk_upsert("stock_hsgt", records, ["ts_code", "trade_date", "type"])
    return count


def sync_date_table_data(
    table_name,
    job_name,
    sync_func,
    start_date=None,
    end_date=None,
    full=False,
    resume=True,
    skip_existing=True,
):
    pro = get_tushare_client()
    start_date, end_date = resolve_incremental_date_range(
        start_date,
        end_date,
        full=full,
        table_names=[table_name],
    )
    log_sync(
        f"Starting {table_name} sync: start_date={start_date}, end_date={end_date}, " f"full={full}, resume={resume}."
    )
    if is_empty_date_range(start_date, end_date):
        log_sync(f"{table_name} is already up to date.")
        mark_named_finished(job_name, f"{table_name}=0, already up to date")
        job = get_sync_job(job_name)
        return {
            "status": job.status,
            "message": job.message,
            "start_date": start_date,
            "end_date": end_date,
            "processed_dates": job.processed_dates if job else 0,
        }
    existing_job = get_sync_job(job_name)
    reset_progress = not resume or not existing_job or existing_job.status != STATUS_RUNNING
    mark_named_running(job_name, start_date, end_date, current_step=table_name, reset_progress=reset_progress)

    try:
        trade_dates = get_trade_dates(pro, start_date, end_date)
        requested_dates = len(trade_dates)
        skipped_existing_dates = 0
        if skip_existing and not full and resume:
            missing_dates = missing_trade_dates(table_name, job_name, trade_dates, start_date, end_date)
            skipped_existing_dates = requested_dates - len(missing_dates)
            trade_dates = missing_dates
            log_sync(
                f"{table_name} missing-date scan: requested={requested_dates}, "
                f"missing={len(trade_dates)}, skipped_existing={skipped_existing_dates}."
            )
        job = get_sync_job(job_name)
        trade_dates = resume_dates(job, trade_dates)
        row_count = 0
        for trade_date in trade_dates:
            mark_named_running(job_name, start_date, end_date, current_date=trade_date, current_step=table_name)
            current_count = sync_func(pro, trade_date)
            row_count += current_count
            mark_sync_date_covered(job_name, trade_date, current_count)
            increment_named_processed_dates(job_name)
            log_sync(f"{table_name} {trade_date}: upserted={current_count}, total={row_count}.")

        message = (
            f"{table_name}={row_count}, requested_dates={requested_dates}, "
            f"processed_dates={len(trade_dates)}, skipped_existing_dates={skipped_existing_dates}"
        )
        log_sync(f"Finished {table_name} sync: {message}.")
        mark_named_finished(job_name, message)
        job = get_sync_job(job_name)
        return {
            "status": job.status,
            "message": job.message,
            "start_date": job.start_date,
            "end_date": job.end_date,
            "processed_dates": job.processed_dates,
        }
    except Exception as exc:
        mark_named_failed(job_name, str(exc))
        logger.exception(f"{table_name} sync failed: {exc}")
        raise


def sync_stk_premarket_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "stk_premarket",
        STK_PREMARKET_JOB_NAME,
        sync_stk_premarket,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_stock_st_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "stock_st",
        STOCK_ST_JOB_NAME,
        sync_stock_st,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_stock_hsgt_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "stock_hsgt",
        STOCK_HSGT_JOB_NAME,
        sync_stock_hsgt,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_st_risk_data():
    pro = get_tushare_client()
    mark_named_running(ST_RISK_JOB_NAME, current_step="st")
    try:
        log_sync("Starting st sync.")
        fields = ",".join(fields_for("st"))
        count = 0
        for ts_code in stock_basic_codes(pro):
            records = dataframe_records(pro.st(ts_code=ts_code, fields=fields))
            count += bulk_upsert("st", records, ["ts_code", "pub_date", "st_tpye"])
        message = f"st={count}"
        log_sync(f"Finished st sync: {message}.")
        mark_named_finished(ST_RISK_JOB_NAME, message)
        job = get_sync_job(ST_RISK_JOB_NAME)
        return {"status": job.status, "message": job.message}
    except Exception as exc:
        mark_named_failed(ST_RISK_JOB_NAME, str(exc))
        logger.exception(f"st sync failed: {exc}")
        raise


def sync_namechange_data():
    pro = get_tushare_client()
    mark_named_running(NAMECHANGE_JOB_NAME, current_step="namechange")
    try:
        log_sync("Starting namechange sync.")
        fields = ",".join(fields_for("namechange"))
        count = 0
        for ts_code in stock_basic_codes(pro):
            records = dataframe_records(pro.namechange(ts_code=ts_code, fields=fields))
            count += bulk_upsert("namechange", records, ["ts_code", "name", "start_date"])
        message = f"namechange={count}"
        log_sync(f"Finished namechange sync: {message}.")
        mark_named_finished(NAMECHANGE_JOB_NAME, message)
        job = get_sync_job(NAMECHANGE_JOB_NAME)
        return {"status": job.status, "message": job.message}
    except Exception as exc:
        mark_named_failed(NAMECHANGE_JOB_NAME, str(exc))
        logger.exception(f"namechange sync failed: {exc}")
        raise


def sync_stock_company_data():
    pro = get_tushare_client()
    mark_named_running(STOCK_COMPANY_JOB_NAME, current_step="stock_company")
    try:
        log_sync("Starting stock_company sync.")
        fields = ",".join(fields_for("stock_company"))
        count = 0
        for exchange in STOCK_COMPANY_EXCHANGES:
            records = dataframe_records(pro.stock_company(exchange=exchange, fields=fields))
            current_count = bulk_upsert("stock_company", records, ["ts_code"])
            count += current_count
            log_sync(f"stock_company exchange={exchange}: upserted={current_count}, total={count}.")
        message = f"stock_company={count}"
        log_sync(f"Finished stock_company sync: {message}.")
        mark_named_finished(STOCK_COMPANY_JOB_NAME, message)
        job = get_sync_job(STOCK_COMPANY_JOB_NAME)
        return {"status": job.status, "message": job.message}
    except Exception as exc:
        mark_named_failed(STOCK_COMPANY_JOB_NAME, str(exc))
        logger.exception(f"stock_company sync failed: {exc}")
        raise


def sync_daily_quote(pro, trade_date):
    records = dataframe_records(pro.daily(trade_date=trade_date))
    return bulk_upsert("daily", records, ["ts_code", "trade_date"])


def sync_daily_basic(pro, trade_date):
    fields = "ts_code,trade_date,close,turnover_rate,volume_ratio,pe_ttm,pb,ps_ttm,dv_ttm,total_mv,circ_mv"
    records = dataframe_records(pro.daily_basic(trade_date=trade_date, fields=fields))
    return bulk_upsert("daily_basic", records, ["ts_code", "trade_date"])


def sync_adj_factor(pro, trade_date):
    fields = ",".join(fields_for("adj_factor"))
    records = dataframe_records(pro.adj_factor(trade_date=trade_date, fields=fields))
    return bulk_upsert("adj_factor", records, ["ts_code", "trade_date"])


def sync_moneyflow(pro, trade_date):
    fields = ",".join(fields_for("moneyflow"))
    records = dataframe_records(pro.moneyflow(trade_date=trade_date, fields=fields))
    return bulk_upsert("moneyflow", records, ["ts_code", "trade_date"])


def sync_margin_detail(pro, trade_date):
    fields = ",".join(fields_for("margin_detail"))
    records = dataframe_records(pro.margin_detail(trade_date=trade_date, fields=fields))
    return bulk_upsert("margin_detail", records, ["ts_code", "trade_date"])


def sync_hk_hold(pro, trade_date):
    fields = ",".join(fields_for("hk_hold"))
    count = 0
    for exchange in HK_HOLD_EXCHANGES:
        records = dataframe_records(pro.hk_hold(trade_date=trade_date, exchange=exchange, fields=fields))
        count += bulk_upsert("hk_hold", records, ["ts_code", "trade_date", "exchange"])
    return count


def sync_suspend_d(pro, trade_date):
    fields = ",".join(fields_for("suspend_d"))
    records = dataframe_records(pro.suspend_d(suspend_date=trade_date, fields=fields))
    return bulk_upsert("suspend_d", records, ["ts_code", "suspend_date"])


def sync_stk_limit(pro, trade_date):
    fields = ",".join(fields_for("stk_limit"))
    records = dataframe_records(pro.stk_limit(trade_date=trade_date, fields=fields))
    return bulk_upsert("stk_limit", records, ["ts_code", "trade_date"])


def sync_share_float(pro, trade_date):
    fields = ",".join(fields_for("share_float"))
    records = dataframe_records(pro.share_float(float_date=trade_date, fields=fields))
    return bulk_upsert("share_float", records, ["ts_code", "float_date", "holder_name", "share_type"])


def sync_pledge_stat(pro, trade_date):
    fields = ",".join(fields_for("pledge_stat"))
    records = dataframe_records(pro.pledge_stat(end_date=trade_date, fields=fields))
    return bulk_upsert("pledge_stat", records, ["ts_code", "end_date"])


def sync_adj_factor_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "adj_factor",
        ADJ_FACTOR_JOB_NAME,
        sync_adj_factor,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_moneyflow_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "moneyflow",
        MONEYFLOW_JOB_NAME,
        sync_moneyflow,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_margin_detail_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "margin_detail",
        MARGIN_DETAIL_JOB_NAME,
        sync_margin_detail,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_hk_hold_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "hk_hold",
        HK_HOLD_JOB_NAME,
        sync_hk_hold,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_suspend_d_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "suspend_d",
        SUSPEND_D_JOB_NAME,
        sync_suspend_d,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_stk_limit_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "stk_limit",
        STK_LIMIT_JOB_NAME,
        sync_stk_limit,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_share_float_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "share_float",
        SHARE_FLOAT_JOB_NAME,
        sync_share_float,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_pledge_stat_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "pledge_stat",
        PLEDGE_STAT_JOB_NAME,
        sync_pledge_stat,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_per_stock_table_data(
    table_name,
    job_name,
    api_name,
    key_fields,
    start_date=None,
    end_date=None,
    use_date_range=False,
):
    pro = get_tushare_client()
    mark_named_running(job_name, start_date=start_date, end_date=end_date, current_step=table_name)
    try:
        log_sync(f"Starting {table_name} sync: start_date={start_date}, end_date={end_date}.")
        fields = ",".join(fields_for(table_name))
        count = 0
        api = getattr(pro, api_name)
        for ts_code in stock_basic_codes(pro):
            params = {"ts_code": ts_code, "fields": fields}
            if use_date_range:
                if start_date:
                    params["start_date"] = start_date
                if end_date:
                    params["end_date"] = end_date
            records = dataframe_records(api(**params))
            current_count = bulk_upsert(table_name, records, key_fields)
            count += current_count
            log_sync(f"{table_name} ts_code={ts_code}: upserted={current_count}, total={count}.")
        message = f"{table_name}={count}"
        log_sync(f"Finished {table_name} sync: {message}.")
        mark_named_finished(job_name, message)
        job = get_sync_job(job_name)
        return {"status": job.status, "message": job.message}
    except Exception as exc:
        mark_named_failed(job_name, str(exc))
        logger.exception(f"{table_name} sync failed: {exc}")
        raise


def sync_daily_announcement_table_data(table_name, job_name, api_name, key_fields, start_date=None, end_date=None):
    pro = get_tushare_client()
    start_date, end_date = resolve_incremental_date_range(
        start_date,
        end_date,
        table_names=[table_name],
    )
    mark_named_running(job_name, start_date=start_date, end_date=end_date, current_step=table_name)
    try:
        log_sync(f"Starting {table_name} sync: start_date={start_date}, end_date={end_date}.")
        if is_empty_date_range(start_date, end_date):
            mark_named_finished(job_name, f"{table_name}=0, already up to date")
            job = get_sync_job(job_name)
            return {"status": job.status, "message": job.message}
        dates = calendar_dates(start_date, end_date)
        requested_dates = len(dates)
        dates = missing_calendar_dates(table_name, job_name, dates, start_date, end_date)
        skipped_existing_dates = requested_dates - len(dates)
        log_sync(
            f"{table_name} missing-date scan: requested={requested_dates}, "
            f"missing={len(dates)}, skipped_existing={skipped_existing_dates}."
        )
        count = 0
        for ann_date in dates:
            current_count = sync_paged_api(
                pro,
                table_name,
                api_name,
                key_fields,
                params={"ann_date": ann_date},
            )
            count += current_count
            mark_sync_date_covered(job_name, ann_date, current_count)
            log_sync(f"{table_name} ann_date={ann_date}: upserted={current_count}, total={count}.")
        message = (
            f"{table_name}={count}, requested_dates={requested_dates}, "
            f"processed_dates={len(dates)}, skipped_existing_dates={skipped_existing_dates}"
        )
        log_sync(f"Finished {table_name} sync: {message}.")
        mark_named_finished(job_name, message)
        job = get_sync_job(job_name)
        return {"status": job.status, "message": job.message}
    except Exception as exc:
        mark_named_failed(job_name, str(exc))
        logger.exception(f"{table_name} sync failed: {exc}")
        raise


def sync_window_api_table_data(table_name, job_name, api_name, key_fields, start_date=None, end_date=None):
    pro = get_tushare_client()
    start_date, end_date = resolve_incremental_date_range(
        start_date,
        end_date,
        table_names=[table_name],
    )
    mark_named_running(job_name, start_date=start_date, end_date=end_date, current_step=table_name)
    try:
        log_sync(f"Starting {table_name} sync: start_date={start_date}, end_date={end_date}.")
        if is_empty_date_range(start_date, end_date):
            mark_named_finished(job_name, f"{table_name}=0, already up to date")
            job = get_sync_job(job_name)
            return {"status": job.status, "message": job.message}
        all_dates = set(calendar_dates(start_date, end_date))
        existing_dates = existing_table_dates(table_name, start_date, end_date)
        covered_dates = covered_sync_dates(job_name, start_date, end_date)
        missing_dates = sorted(all_dates - existing_dates - covered_dates)
        if not missing_dates:
            mark_named_finished(job_name, f"{table_name}=0, already up to date")
            job = get_sync_job(job_name)
            return {"status": job.status, "message": job.message}

        count = sync_paged_api(
            pro,
            table_name,
            api_name,
            key_fields,
            params={"start_date": missing_dates[0], "end_date": missing_dates[-1]},
        )
        for date in missing_dates:
            mark_sync_date_covered(job_name, date, 0)
        message = (
            f"{table_name}={count}, requested_dates={len(all_dates)}, "
            f"processed_range={missing_dates[0]}..{missing_dates[-1]}, "
            f"skipped_existing_dates={len(all_dates) - len(missing_dates)}"
        )
        log_sync(f"Finished {table_name} sync: {message}.")
        mark_named_finished(job_name, message)
        job = get_sync_job(job_name)
        return {"status": job.status, "message": job.message}
    except Exception as exc:
        mark_named_failed(job_name, str(exc))
        logger.exception(f"{table_name} sync failed: {exc}")
        raise


def sync_period_api_table_data(table_name, job_name, api_name, key_fields, start_date=None, end_date=None):
    pro = get_tushare_client()
    start_date, end_date = resolve_incremental_date_range(
        start_date,
        end_date,
        table_names=[table_name],
    )
    mark_named_running(job_name, start_date=start_date, end_date=end_date, current_step=table_name)
    try:
        log_sync(f"Starting {table_name} sync: start_date={start_date}, end_date={end_date}.")
        periods = quarter_periods(start_date, end_date)
        if not periods:
            mark_named_finished(job_name, f"{table_name}=0, no report periods")
            job = get_sync_job(job_name)
            return {"status": job.status, "message": job.message}
        requested_periods = len(periods)
        periods = missing_periods(table_name, job_name, periods, start_date, end_date)
        skipped_existing_periods = requested_periods - len(periods)
        log_sync(
            f"{table_name} missing-period scan: requested={requested_periods}, "
            f"missing={len(periods)}, skipped_existing={skipped_existing_periods}."
        )
        count = 0
        for period in periods:
            current_count = sync_paged_api(
                pro,
                table_name,
                api_name,
                key_fields,
                params={"period": period},
            )
            count += current_count
            mark_sync_date_covered(job_name, period, current_count)
            log_sync(f"{table_name} period={period}: upserted={current_count}, total={count}.")
        message = (
            f"{table_name}={count}, requested_periods={requested_periods}, "
            f"processed_periods={len(periods)}, skipped_existing_periods={skipped_existing_periods}"
        )
        log_sync(f"Finished {table_name} sync: {message}.")
        mark_named_finished(job_name, message)
        job = get_sync_job(job_name)
        return {"status": job.status, "message": job.message}
    except Exception as exc:
        mark_named_failed(job_name, str(exc))
        logger.exception(f"{table_name} sync failed: {exc}")
        raise


def sync_fina_indicator_data(start_date=None, end_date=None):
    if start_date or end_date:
        return sync_period_api_table_data(
            "fina_indicator",
            FINA_INDICATOR_JOB_NAME,
            "fina_indicator_vip",
            ["ts_code", "ann_date", "end_date"],
            start_date=start_date,
            end_date=end_date,
        )
    return sync_per_stock_table_data(
        "fina_indicator",
        FINA_INDICATOR_JOB_NAME,
        "fina_indicator",
        ["ts_code", "ann_date", "end_date"],
        start_date=start_date,
        end_date=end_date,
        use_date_range=True,
    )


def sync_income_data(start_date=None, end_date=None):
    if start_date or end_date:
        return sync_period_api_table_data(
            "income",
            INCOME_JOB_NAME,
            "income_vip",
            ["ts_code", "ann_date", "end_date", "report_type"],
            start_date=start_date,
            end_date=end_date,
        )
    return sync_per_stock_table_data(
        "income",
        INCOME_JOB_NAME,
        "income",
        ["ts_code", "ann_date", "end_date", "report_type"],
        start_date=start_date,
        end_date=end_date,
        use_date_range=True,
    )


def sync_balancesheet_data(start_date=None, end_date=None):
    if start_date or end_date:
        return sync_period_api_table_data(
            "balancesheet",
            BALANCESHEET_JOB_NAME,
            "balancesheet_vip",
            ["ts_code", "ann_date", "end_date", "report_type"],
            start_date=start_date,
            end_date=end_date,
        )
    return sync_per_stock_table_data(
        "balancesheet",
        BALANCESHEET_JOB_NAME,
        "balancesheet",
        ["ts_code", "ann_date", "end_date", "report_type"],
        start_date=start_date,
        end_date=end_date,
        use_date_range=True,
    )


def sync_cashflow_data(start_date=None, end_date=None):
    if start_date or end_date:
        return sync_period_api_table_data(
            "cashflow",
            CASHFLOW_JOB_NAME,
            "cashflow_vip",
            ["ts_code", "ann_date", "end_date", "report_type"],
            start_date=start_date,
            end_date=end_date,
        )
    return sync_per_stock_table_data(
        "cashflow",
        CASHFLOW_JOB_NAME,
        "cashflow",
        ["ts_code", "ann_date", "end_date", "report_type"],
        start_date=start_date,
        end_date=end_date,
        use_date_range=True,
    )


def sync_index_basic_data():
    pro = get_tushare_client()
    mark_named_running(INDEX_BASIC_JOB_NAME, current_step="index_basic")
    try:
        log_sync("Starting index_basic sync.")
        fields = ",".join(fields_for("index_basic"))
        count = 0
        for market in INDEX_BASIC_MARKETS:
            records = dataframe_records(pro.index_basic(market=market, fields=fields))
            current_count = bulk_upsert("index_basic", records, ["ts_code"])
            count += current_count
            log_sync(f"index_basic market={market}: upserted={current_count}, total={count}.")
        message = f"index_basic={count}"
        log_sync(f"Finished index_basic sync: {message}.")
        mark_named_finished(INDEX_BASIC_JOB_NAME, message)
        job = get_sync_job(INDEX_BASIC_JOB_NAME)
        return {"status": job.status, "message": job.message}
    except Exception as exc:
        mark_named_failed(INDEX_BASIC_JOB_NAME, str(exc))
        logger.exception(f"index_basic sync failed: {exc}")
        raise


def index_codes():
    return DEFAULT_INDEX_CODES


def sync_index_daily_data(start_date=None, end_date=None, full=False):
    pro = get_tushare_client()
    start_date, end_date = resolve_incremental_date_range(
        start_date,
        end_date,
        full=full,
        table_names=["index_daily"],
    )
    mark_named_running(INDEX_DAILY_JOB_NAME, start_date=start_date, end_date=end_date, current_step="index_daily")
    try:
        log_sync(f"Starting index_daily sync: start_date={start_date}, end_date={end_date}.")
        if is_empty_date_range(start_date, end_date):
            mark_named_finished(INDEX_DAILY_JOB_NAME, "index_daily=0, already up to date")
            job = get_sync_job(INDEX_DAILY_JOB_NAME)
            return {"status": job.status, "message": job.message}
        fields = ",".join(fields_for("index_daily"))
        all_dates = set(calendar_dates(start_date, end_date))
        existing_dates = existing_table_dates("index_daily", start_date, end_date)
        covered_dates = covered_sync_dates(INDEX_DAILY_JOB_NAME, start_date, end_date)
        missing_dates = sorted(all_dates - existing_dates - covered_dates)
        if not full and missing_dates:
            date_ranges = contiguous_date_ranges(missing_dates)
        elif full:
            date_ranges = [(start_date, end_date)]
        else:
            mark_named_finished(INDEX_DAILY_JOB_NAME, "index_daily=0, already up to date")
            job = get_sync_job(INDEX_DAILY_JOB_NAME)
            return {"status": job.status, "message": job.message}

        count = 0
        for range_start, range_end in date_ranges:
            range_count = 0
            for ts_code in index_codes():
                records = dataframe_records(
                    pro.index_daily(ts_code=ts_code, start_date=range_start, end_date=range_end, fields=fields)
                )
                current_count = bulk_upsert("index_daily", records, ["ts_code", "trade_date"])
                count += current_count
                range_count += current_count
                log_sync(
                    f"index_daily ts_code={ts_code} range={range_start}..{range_end}: "
                    f"upserted={current_count}, total={count}."
                )
            for date in calendar_dates(range_start, range_end):
                mark_sync_date_covered(INDEX_DAILY_JOB_NAME, date, range_count)
        message = (
            f"index_daily={count}, requested_dates={len(all_dates)}, "
            f"processed_ranges={len(date_ranges)}, skipped_existing_dates={len(all_dates) - len(missing_dates)}"
        )
        log_sync(f"Finished index_daily sync: {message}.")
        mark_named_finished(INDEX_DAILY_JOB_NAME, message)
        job = get_sync_job(INDEX_DAILY_JOB_NAME)
        return {"status": job.status, "message": job.message}
    except Exception as exc:
        mark_named_failed(INDEX_DAILY_JOB_NAME, str(exc))
        logger.exception(f"index_daily sync failed: {exc}")
        raise


def sync_index_classify_data():
    pro = get_tushare_client()
    mark_named_running(INDEX_CLASSIFY_JOB_NAME, current_step="index_classify")
    try:
        log_sync("Starting index_classify sync.")
        fields = ",".join(fields_for("index_classify"))
        count = 0
        for src in INDEX_CLASSIFY_SOURCES:
            records = dataframe_records(pro.index_classify(src=src, fields=fields))
            for record in records:
                record.setdefault("src", src)
            current_count = bulk_upsert("index_classify", records, ["index_code", "src"])
            count += current_count
            log_sync(f"index_classify src={src}: upserted={current_count}, total={count}.")
        message = f"index_classify={count}"
        mark_named_finished(INDEX_CLASSIFY_JOB_NAME, message)
        return {"status": STATUS_SUCCESS, "message": message}
    except Exception as exc:
        mark_named_failed(INDEX_CLASSIFY_JOB_NAME, str(exc))
        logger.exception(f"index_classify sync failed: {exc}")
        raise


def sync_index_member_all_data():
    pro = get_tushare_client()
    mark_named_running(INDEX_MEMBER_ALL_JOB_NAME, current_step="index_member_all")
    try:
        log_sync("Starting index_member_all sync.")
        fields = ",".join(fields_for("index_member_all"))
        count = 0
        offset = 0
        limit = 3000
        seen_pages = set()
        while True:
            records = dataframe_records(pro.index_member_all(is_new="Y", fields=fields, limit=limit, offset=offset))
            if not records:
                break
            page_key = tuple(
                (
                    record.get("ts_code"),
                    record.get("l1_code"),
                    record.get("l2_code"),
                    record.get("l3_code"),
                    record.get("in_date"),
                )
                for record in records
            )
            if page_key in seen_pages:
                log_sync(f"index_member_all repeated page at offset={offset}; stopping pagination.")
                break
            seen_pages.add(page_key)
            current_count = bulk_upsert(
                "index_member_all",
                records,
                ["ts_code", "l1_code", "l2_code", "l3_code", "in_date"],
            )
            count += current_count
            log_sync(f"index_member_all offset={offset}: upserted={current_count}, total={count}.")
            if len(records) < limit:
                break
            offset += limit
        message = f"index_member_all={count}"
        mark_named_finished(INDEX_MEMBER_ALL_JOB_NAME, message)
        return {"status": STATUS_SUCCESS, "message": message}
    except Exception as exc:
        mark_named_failed(INDEX_MEMBER_ALL_JOB_NAME, str(exc))
        logger.exception(f"index_member_all sync failed: {exc}")
        raise


def sync_stk_factor_pro(pro, trade_date):
    fields = ",".join(fields_for("stk_factor_pro"))
    records = dataframe_records(pro.stk_factor_pro(trade_date=trade_date, fields=fields))
    return bulk_upsert("stk_factor_pro", records, ["ts_code", "trade_date"])


def sync_stk_factor_pro_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "stk_factor_pro",
        STK_FACTOR_PRO_JOB_NAME,
        sync_stk_factor_pro,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_margin(pro, trade_date):
    fields = ",".join(fields_for("margin"))
    count = 0
    for exchange_id in MARGIN_EXCHANGES:
        records = dataframe_records(pro.margin(trade_date=trade_date, exchange_id=exchange_id, fields=fields))
        count += bulk_upsert("margin", records, ["trade_date", "exchange_id"])
    return count


def sync_margin_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "margin", MARGIN_JOB_NAME, sync_margin, start_date=start_date, end_date=end_date, full=full, resume=resume
    )


def sync_pledge_detail_data(start_date=None, end_date=None):
    return sync_window_api_table_data(
        "pledge_detail",
        PLEDGE_DETAIL_JOB_NAME,
        "pledge_detail",
        ["ts_code", "ann_date", "holder_name", "start_date"],
        start_date=start_date,
        end_date=end_date,
    )


def sync_forecast_data(start_date=None, end_date=None):
    return sync_daily_announcement_table_data(
        "forecast",
        FORECAST_JOB_NAME,
        "forecast",
        ["ts_code", "ann_date", "end_date", "type"],
        start_date=start_date,
        end_date=end_date,
    )


def sync_express_data(start_date=None, end_date=None):
    return sync_window_api_table_data(
        "express",
        EXPRESS_JOB_NAME,
        "express",
        ["ts_code", "ann_date", "end_date"],
        start_date=start_date,
        end_date=end_date,
    )


def sync_block_trade(pro, trade_date):
    fields = ",".join(fields_for("block_trade"))
    records = dataframe_records(pro.block_trade(trade_date=trade_date, fields=fields))
    return bulk_upsert("block_trade", records, ["ts_code", "trade_date", "price", "vol", "buyer", "seller"])


def sync_block_trade_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "block_trade",
        BLOCK_TRADE_JOB_NAME,
        sync_block_trade,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_top_list(pro, trade_date):
    fields = ",".join(fields_for("top_list"))
    records = dataframe_records(pro.top_list(trade_date=trade_date, fields=fields))
    return bulk_upsert("top_list", records, ["ts_code", "trade_date", "reason"])


def sync_top_list_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "top_list", TOP_LIST_JOB_NAME, sync_top_list, start_date=start_date, end_date=end_date, full=full, resume=resume
    )


def sync_top_inst(pro, trade_date):
    fields = ",".join(fields_for("top_inst"))
    records = dataframe_records(pro.top_inst(trade_date=trade_date, fields=fields))
    return bulk_upsert("top_inst", records, ["ts_code", "trade_date", "exalter", "side", "reason"])


def sync_top_inst_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "top_inst", TOP_INST_JOB_NAME, sync_top_inst, start_date=start_date, end_date=end_date, full=full, resume=resume
    )


def sync_dividend_data(start_date=None, end_date=None):
    return sync_daily_announcement_table_data(
        "dividend",
        DIVIDEND_JOB_NAME,
        "dividend",
        ["ts_code", "end_date", "ann_date", "div_proc"],
        start_date=start_date,
        end_date=end_date,
    )


def sync_repurchase(pro, trade_date):
    fields = ",".join(fields_for("repurchase"))
    records = dataframe_records(pro.repurchase(ann_date=trade_date, fields=fields))
    return bulk_upsert("repurchase", records, ["ts_code", "ann_date", "end_date", "proc"])


def sync_repurchase_data(start_date=None, end_date=None, full=False, resume=True):
    return sync_date_table_data(
        "repurchase",
        REPURCHASE_JOB_NAME,
        sync_repurchase,
        start_date=start_date,
        end_date=end_date,
        full=full,
        resume=resume,
    )


def sync_market_data(start_date=None, end_date=None, resume=True, full=False):
    pro = get_tushare_client()

    start_date, end_date = resolve_date_range(
        start_date,
        end_date,
        table_names=["trade_cal", "daily", "daily_basic"],
    )
    log_sync(f"Starting market_data sync: start_date={start_date}, end_date={end_date}, resume={resume}.")
    if is_empty_date_range(start_date, end_date):
        log_sync("market_data is already up to date.")
        mark_finished("daily_quotes=0, daily_basics=0, already up to date")
        job = get_job()
        return {
            "status": job.status,
            "message": job.message,
            "start_date": start_date,
            "end_date": end_date,
            "processed_dates": job.processed_dates if job else 0,
        }
    existing_job = get_job()
    reset_progress = not resume or not existing_job or existing_job.status != STATUS_RUNNING

    mark_running(start_date, end_date, current_step="trade_cal", reset_progress=reset_progress)

    try:
        log_sync("market_data loading trade calendar.")
        trade_dates = get_trade_dates(pro, start_date, end_date)
        requested_dates = len(trade_dates)
        log_sync(f"market_data trade calendar loaded: requested_dates={requested_dates}.")
        skipped_existing_dates = 0
        if not full and resume:
            log_sync("market_data scanning missing daily dates.")
            daily_missing_dates = missing_trade_dates("daily", JOB_NAME, trade_dates, start_date, end_date)
            log_sync(f"market_data daily missing dates: {len(daily_missing_dates)}.")
            log_sync("market_data scanning missing daily_basic dates.")
            daily_basic_missing_dates = missing_trade_dates(
                "daily_basic",
                f"{JOB_NAME}_daily_basic",
                trade_dates,
                start_date,
                end_date,
            )
            log_sync(f"market_data daily_basic missing dates: {len(daily_basic_missing_dates)}.")
            missing_dates = sorted(set(daily_missing_dates) | set(daily_basic_missing_dates))
            skipped_existing_dates = requested_dates - len(missing_dates)
            trade_dates = missing_dates
            log_sync(
                f"market_data missing-date scan: requested={requested_dates}, "
                f"missing={len(trade_dates)}, skipped_existing={skipped_existing_dates}."
            )
        job = get_job()
        trade_dates = resume_dates(job, trade_dates)
        log_sync(f"market_data trade dates to process: {len(trade_dates)}.")

        quote_count = 0
        basic_count = 0

        for trade_date in trade_dates:
            mark_running(start_date, end_date, current_date=trade_date, current_step="daily")
            daily_count = sync_daily_quote(pro, trade_date)
            quote_count += daily_count
            mark_sync_date_covered(JOB_NAME, trade_date, daily_count)

            mark_running(start_date, end_date, current_date=trade_date, current_step="daily_basic")
            basic_row_count = sync_daily_basic(pro, trade_date)
            basic_count += basic_row_count
            mark_sync_date_covered(f"{JOB_NAME}_daily_basic", trade_date, basic_row_count)
            increment_processed_dates()
            log_sync(
                f"market_data {trade_date}: daily_upserted={daily_count}, "
                f"daily_basic_upserted={basic_row_count}, "
                f"daily_total={quote_count}, daily_basic_total={basic_count}."
            )

        message = (
            f"daily_quotes={quote_count}, daily_basics={basic_count}, "
            f"requested_dates={requested_dates}, processed_dates={len(trade_dates)}, "
            f"skipped_existing_dates={skipped_existing_dates}"
        )
        log_sync(f"Finished market_data sync: {message}.")
        mark_finished(message)
        job = get_job()
        return {
            "status": job.status,
            "message": job.message,
            "start_date": job.start_date,
            "end_date": job.end_date,
            "processed_dates": job.processed_dates,
        }
    except Exception as exc:
        mark_failed(str(exc))
        logger.exception(f"market_data sync failed: {exc}")
        raise
