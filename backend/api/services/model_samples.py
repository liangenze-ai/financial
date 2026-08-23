from dataclasses import dataclass

from django.db import connection, transaction


CORE_TABLES = [
    ('stock_basic', 'tushare_stock_basic', 'list_date'),
    ('trade_cal', 'tushare_trade_cal', 'cal_date'),
    ('daily', 'tushare_stock_daily', 'trade_date'),
    ('daily_basic', 'tushare_stock_daily_basic', 'trade_date'),
    ('adj_factor', 'tushare_adj_factor', 'trade_date'),
    ('stk_factor_pro', 'tushare_stk_factor_pro', 'trade_date'),
    ('fina_indicator', 'tushare_fina_indicator', 'ann_date'),
    ('index_daily', 'tushare_index_daily', 'trade_date'),
    ('moneyflow', 'tushare_moneyflow', 'trade_date'),
    ('margin_detail', 'tushare_margin_detail', 'trade_date'),
    ('stock_st', 'tushare_stock_st', 'trade_date'),
    ('stk_limit', 'tushare_stk_limit', 'trade_date'),
    ('pledge_stat', 'tushare_pledge_stat', 'end_date'),
]


@dataclass(frozen=True)
class TableCheck:
    name: str
    table: str
    exists: bool
    sample_count: int
    estimated_rows: int
    min_date: str | None
    max_date: str | None


def check_core_tables():
    checks = []
    with connection.cursor() as cursor:
        for name, table, date_field in CORE_TABLES:
            cursor.execute('select to_regclass(%s)', [table])
            exists = cursor.fetchone()[0] is not None
            if not exists:
                checks.append(TableCheck(name, table, False, 0, 0, None, None))
                continue

            cursor.execute(
                'select coalesce(reltuples::bigint, 0) from pg_class where oid = %s::regclass',
                [table],
            )
            estimated_rows = cursor.fetchone()[0]
            cursor.execute(f'select count(*) from (select 1 from {table} limit 10001) s')
            sample_count = cursor.fetchone()[0]
            cursor.execute(f'select min({date_field}), max({date_field}) from {table}')
            min_date, max_date = cursor.fetchone()
            checks.append(TableCheck(name, table, True, sample_count, estimated_rows, min_date, max_date))
    return checks


def sample_summary(feature_version='v1'):
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            select
                count(*)::bigint,
                min(trade_date),
                max(trade_date),
                count(*) filter (where label_up_20 is not null)::bigint,
                count(*) filter (where label_outperform_20 is not null)::bigint
            from model_sample_v1
            where feature_version = %s
            ''',
            [feature_version],
        )
        rows, min_date, max_date, labeled_up, labeled_outperform = cursor.fetchone()
    return {
        'rows': rows,
        'min_date': min_date,
        'max_date': max_date,
        'labeled_up_20': labeled_up,
        'labeled_outperform_20': labeled_outperform,
    }


def enrich_summary(feature_version='v1', start_date=None, end_date=None):
    where = ['feature_version = %s']
    params = [feature_version]
    if start_date:
        where.append('trade_date >= %s')
        params.append(start_date)
    if end_date:
        where.append('trade_date <= %s')
        params.append(end_date)

    with connection.cursor() as cursor:
        cursor.execute(
            f'''
            select
                count(*)::bigint,
                count(*) filter (where roe is not null)::bigint,
                count(*) filter (where revenue_yoy is not null)::bigint,
                count(*) filter (where pledge_ratio is not null)::bigint
            from model_sample_v1
            where {' and '.join(where)}
            ''',
            params,
        )
        rows, financial_rows, growth_rows, pledge_rows = cursor.fetchone()
    return {
        'rows': rows,
        'financial_rows': financial_rows,
        'growth_rows': growth_rows,
        'pledge_rows': pledge_rows,
    }


def repair_model_sample_core_features(start_date=None, end_date=None, feature_version='v1'):
    where = ['sample.feature_version = %(feature_version)s']
    select_where = ['feature_version = %(feature_version)s']
    params = {
        'feature_version': feature_version,
        'start_date': start_date,
        'end_date': end_date,
    }
    if start_date:
        where.append('sample.trade_date >= %(start_date)s')
        select_where.append('trade_date >= %(start_date)s')
    if end_date:
        where.append('sample.trade_date <= %(end_date)s')
        select_where.append('trade_date <= %(end_date)s')

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('set statement_timeout = 0')
            cursor.execute(
                f'''
                create temporary table tmp_model_sample_repair_targets on commit drop as
                select ts_code, trade_date
                from model_sample_v1
                where {' and '.join(select_where)}
                ''',
                params,
            )
            cursor.execute('create index on tmp_model_sample_repair_targets (ts_code, trade_date)')
            cursor.execute('analyze tmp_model_sample_repair_targets')
            cursor.execute(
                '''
                create temporary table tmp_model_sample_repair_codes on commit drop as
                select distinct ts_code
                from tmp_model_sample_repair_targets
                ''',
            )
            cursor.execute('create index on tmp_model_sample_repair_codes (ts_code)')
            cursor.execute('analyze tmp_model_sample_repair_codes')
            cursor.execute(
                '''
                create temporary table tmp_model_sample_repair_features on commit drop as
            with target_bounds as (
                select min(trade_date) as min_trade_date, max(trade_date) as max_trade_date
                from tmp_model_sample_repair_targets
            ),
            calendar as (
                select cal_date, row_number() over (order by cal_date) as rn
                from tushare_trade_cal
                where is_open = 1
            ),
            date_window as (
                select
                    min(history.cal_date) as history_start,
                    max(targets.cal_date) as history_end
                from target_bounds bounds
                join calendar targets
                  on targets.cal_date between bounds.min_trade_date and bounds.max_trade_date
                join calendar history
                  on history.rn between targets.rn - 80 and targets.rn
            ),
            daily as (
                select
                    dq.ts_code,
                    dq.trade_date,
                    dq.close * nullif(af.adj_factor, 0) as adj_close,
                    dq.amount
                from tushare_stock_daily dq
                join tmp_model_sample_repair_codes target_codes
                  on target_codes.ts_code = dq.ts_code
                left join tushare_adj_factor af on af.ts_code = dq.ts_code and af.trade_date = dq.trade_date
                cross join date_window date_bounds
                where dq.trade_date between date_bounds.history_start and date_bounds.history_end
            ),
            rolled as (
                select
                    ts_code,
                    trade_date,
                    avg(adj_close) over (
                        partition by ts_code order by trade_date rows between 19 preceding and current row
                    ) as ma20,
                    avg(adj_close) over (
                        partition by ts_code order by trade_date rows between 59 preceding and current row
                    ) as ma60,
                    stddev_samp(adj_close / nullif(lag_adj_close, 0) - 1.0) over (
                        partition by ts_code order by trade_date rows between 19 preceding and current row
                    ) as vol_20,
                    avg(amount) over (
                        partition by ts_code order by trade_date rows between 19 preceding and current row
                    ) as amount_ma20
                from (
                    select
                        daily.*,
                        lag(adj_close) over (partition by ts_code order by trade_date) as lag_adj_close
                    from daily
                ) daily_with_lag
            )
            select
                targets.ts_code,
                targets.trade_date,
                rolled.ma20,
                rolled.ma60,
                rolled.vol_20,
                rolled.amount_ma20
            from tmp_model_sample_repair_targets targets
            join rolled on rolled.ts_code = targets.ts_code and rolled.trade_date = targets.trade_date
                ''',
            )
            cursor.execute('create index on tmp_model_sample_repair_features (ts_code, trade_date)')
            cursor.execute('analyze tmp_model_sample_repair_features')
            cursor.execute(
                f'''
                update model_sample_v1 sample
                set
                    ma20_bias = sample.close * nullif(sample.adj_factor, 0) / nullif(features.ma20, 0) - 1.0,
                    ma60_bias = sample.close * nullif(sample.adj_factor, 0) / nullif(features.ma60, 0) - 1.0,
                    vol_20 = features.vol_20,
                    amount_ratio_20 = sample.amount / nullif(features.amount_ma20, 0),
                    days_since_list = case
                        when sample.list_date ~ '^[0-9]{{8}}$'
                        then to_date(sample.trade_date, 'YYYYMMDD') - to_date(sample.list_date, 'YYYYMMDD')
                        else sample.days_since_list
                    end,
                    updated_at = now()
                from tmp_model_sample_repair_features features
                where {' and '.join(where)}
                  and features.ts_code = sample.ts_code
                  and features.trade_date = sample.trade_date
                ''',
                params,
            )
            updated_rows = cursor.rowcount

    return {
        'updated_rows': updated_rows,
        'feature_version': feature_version,
        'start_date': start_date,
        'end_date': end_date,
    }


def repair_model_sample_core_features_staged(start_date=None, end_date=None, feature_version='v1'):
    where = ['sample.feature_version = %(feature_version)s']
    select_where = ['feature_version = %(feature_version)s']
    params = {
        'feature_version': feature_version,
        'start_date': start_date,
        'end_date': end_date,
    }
    if start_date:
        where.append('sample.trade_date >= %(start_date)s')
        select_where.append('trade_date >= %(start_date)s')
    if end_date:
        where.append('sample.trade_date <= %(end_date)s')
        select_where.append('trade_date <= %(end_date)s')

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('set statement_timeout = 0')
            cursor.execute(
                f'''
                create temporary table tmp_repair_targets on commit drop as
                select ts_code, trade_date, close, adj_factor, amount, list_date
                from model_sample_v1
                where {' and '.join(select_where)}
                ''',
                params,
            )
            cursor.execute('create index on tmp_repair_targets (trade_date, ts_code)')
            cursor.execute('create index on tmp_repair_targets (ts_code, trade_date)')
            cursor.execute('analyze tmp_repair_targets')
            cursor.execute(
                '''
                create temporary table tmp_repair_codes on commit drop as
                select distinct ts_code
                from tmp_repair_targets
                ''',
            )
            cursor.execute('create index on tmp_repair_codes (ts_code)')
            cursor.execute('analyze tmp_repair_codes')
            cursor.execute(
                '''
                create temporary table tmp_repair_date_bounds on commit drop as
                with target_bounds as (
                    select min(trade_date) as min_trade_date, max(trade_date) as max_trade_date
                    from tmp_repair_targets
                ),
                calendar as (
                    select cal_date, row_number() over (order by cal_date) as rn
                    from tushare_trade_cal
                    where is_open = 1
                )
                select
                    min(history.cal_date) as history_start,
                    max(targets.cal_date) as history_end
                from target_bounds bounds
                join calendar targets
                  on targets.cal_date between bounds.min_trade_date and bounds.max_trade_date
                join calendar history
                  on history.rn between targets.rn - 80 and targets.rn
                ''',
            )
            cursor.execute(
                '''
                create temporary table tmp_repair_daily on commit drop as
                select
                    sample.ts_code,
                    sample.trade_date,
                    sample.close * nullif(sample.adj_factor, 0) as adj_close,
                    sample.amount
                from tmp_repair_codes codes
                join model_sample_v1 sample on sample.ts_code = codes.ts_code
                cross join tmp_repair_date_bounds bounds
                where sample.feature_version = %(feature_version)s
                  and sample.trade_date between bounds.history_start and bounds.history_end
                  and sample.close is not null
                  and sample.adj_factor is not null
                ''',
                params,
            )
            cursor.execute('create index on tmp_repair_daily (ts_code, trade_date)')
            cursor.execute('analyze tmp_repair_daily')
            cursor.execute(
                '''
                create temporary table tmp_repair_rolled on commit drop as
                select
                    ts_code,
                    trade_date,
                    avg(adj_close) over (
                        partition by ts_code order by trade_date rows between 19 preceding and current row
                    ) as ma20,
                    avg(adj_close) over (
                        partition by ts_code order by trade_date rows between 59 preceding and current row
                    ) as ma60,
                    stddev_samp(adj_close / nullif(lag_adj_close, 0) - 1.0) over (
                        partition by ts_code order by trade_date rows between 19 preceding and current row
                    ) as vol_20,
                    avg(amount) over (
                        partition by ts_code order by trade_date rows between 19 preceding and current row
                    ) as amount_ma20
                from (
                    select
                        daily.*,
                        lag(adj_close) over (partition by ts_code order by trade_date) as lag_adj_close
                    from tmp_repair_daily daily
                ) daily_with_lag
                ''',
            )
            cursor.execute('create index on tmp_repair_rolled (ts_code, trade_date)')
            cursor.execute('analyze tmp_repair_rolled')
            cursor.execute(
                f'''
                update model_sample_v1 sample
                set
                    ma20_bias = target.close * nullif(target.adj_factor, 0) / nullif(rolled.ma20, 0) - 1.0,
                    ma60_bias = target.close * nullif(target.adj_factor, 0) / nullif(rolled.ma60, 0) - 1.0,
                    vol_20 = rolled.vol_20,
                    amount_ratio_20 = target.amount / nullif(rolled.amount_ma20, 0),
                    days_since_list = case
                        when target.list_date ~ '^[0-9]{{8}}$'
                        then to_date(target.trade_date, 'YYYYMMDD') - to_date(target.list_date, 'YYYYMMDD')
                        else sample.days_since_list
                    end,
                    updated_at = now()
                from tmp_repair_targets target
                join tmp_repair_rolled rolled
                  on rolled.ts_code = target.ts_code
                 and rolled.trade_date = target.trade_date
                where {' and '.join(where)}
                  and sample.ts_code = target.ts_code
                  and sample.trade_date = target.trade_date
                ''',
                params,
            )
            updated_rows = cursor.rowcount

    return {
        'updated_rows': updated_rows,
        'feature_version': feature_version,
        'start_date': start_date,
        'end_date': end_date,
        'mode': 'staged',
    }


def repair_model_sample_days_since_list(start_date=None, end_date=None, feature_version='v1'):
    where = ["feature_version = %(feature_version)s", "list_date ~ '^[0-9]{8}$'"]
    params = {
        'feature_version': feature_version,
        'start_date': start_date,
        'end_date': end_date,
    }
    if start_date:
        where.append('trade_date >= %(start_date)s')
    if end_date:
        where.append('trade_date <= %(end_date)s')

    with connection.cursor() as cursor:
        cursor.execute('set statement_timeout = 0')
        cursor.execute(
            f'''
            update model_sample_v1
            set
                days_since_list = to_date(trade_date, 'YYYYMMDD') - to_date(list_date, 'YYYYMMDD'),
                updated_at = now()
            where {' and '.join(where)}
            ''',
            params,
        )
        updated_rows = cursor.rowcount

    return {
        'updated_rows': updated_rows,
        'feature_version': feature_version,
        'start_date': start_date,
        'end_date': end_date,
        'mode': 'days-only',
    }


def repair_model_sample_days_since_list_batch(
    start_date=None,
    end_date=None,
    feature_version='v1',
    batch_size=20,
    stdout=None,
):
    trade_dates = _target_trade_dates(start_date, end_date)
    total_dates = len(trade_dates)
    updated_rows = 0
    processed_dates = 0

    for index in range(0, total_dates, batch_size):
        batch_dates = trade_dates[index:index + batch_size]
        if not batch_dates:
            continue
        with connection.cursor() as cursor:
            cursor.execute('set statement_timeout = 0')
            cursor.execute(
                '''
                update model_sample_v1
                set
                    days_since_list = to_date(trade_date, 'YYYYMMDD') - to_date(list_date, 'YYYYMMDD'),
                    updated_at = now()
                where feature_version = %s
                  and trade_date = any(%s)
                  and list_date ~ '^[0-9]{8}$'
                  and (
                      days_since_list is null
                      or days_since_list <> to_date(trade_date, 'YYYYMMDD') - to_date(list_date, 'YYYYMMDD')
                  )
                ''',
                [feature_version, batch_dates],
            )
            batch_rows = cursor.rowcount
        updated_rows += batch_rows
        processed_dates += len(batch_dates)
        if stdout:
            stdout.write(
                f'repair days_since_list progress: '
                f'{processed_dates}/{total_dates} dates, '
                f'range={batch_dates[0]}..{batch_dates[-1]}, '
                f'batch_rows={batch_rows}, total_rows={updated_rows}'
            )
            stdout.flush()

    return {
        'updated_rows': updated_rows,
        'processed_dates': processed_dates,
        'feature_version': feature_version,
        'start_date': start_date,
        'end_date': end_date,
        'mode': 'days-only-batch',
    }


def build_daily_rolling_features(start_date=None, end_date=None, replace=False):
    history_start, scan_end = _date_window(start_date, end_date, lookback_days=80, forward_days=0)
    target_start = start_date or history_start
    target_end = end_date or scan_end
    if not history_start or not target_start or not target_end:
        raise ValueError("start_date or end_date is required to build rolling features.")

    params = {
        'history_start': history_start,
        'target_start': target_start,
        'target_end': target_end,
    }
    delete_where = []
    if start_date:
        delete_where.append('trade_date >= %(target_start)s')
    if end_date:
        delete_where.append('trade_date <= %(target_end)s')

    with connection.cursor() as cursor:
        cursor.execute('set statement_timeout = 0')
        if replace and delete_where:
            cursor.execute(
                f"delete from model_daily_rolling_features where {' and '.join(delete_where)}",
                params,
            )
        cursor.execute(
            '''
            insert into model_daily_rolling_features (
                created_at,
                updated_at,
                ts_code,
                trade_date,
                ma20,
                ma60,
                vol_20,
                amount_ma20
            )
            with daily as (
                select
                    dq.ts_code,
                    dq.trade_date,
                    dq.close * nullif(af.adj_factor, 0) as adj_close,
                    dq.amount
                from tushare_stock_daily dq
                left join tushare_adj_factor af on af.ts_code = dq.ts_code and af.trade_date = dq.trade_date
                where dq.trade_date between %(history_start)s and %(target_end)s
                  and dq.close is not null
            ),
            rolled as (
                select
                    ts_code,
                    trade_date,
                    avg(adj_close) over (
                        partition by ts_code order by trade_date rows between 19 preceding and current row
                    ) as ma20,
                    avg(adj_close) over (
                        partition by ts_code order by trade_date rows between 59 preceding and current row
                    ) as ma60,
                    stddev_samp(adj_close / nullif(lag_adj_close, 0) - 1.0) over (
                        partition by ts_code order by trade_date rows between 19 preceding and current row
                    ) as vol_20,
                    avg(amount) over (
                        partition by ts_code order by trade_date rows between 19 preceding and current row
                    ) as amount_ma20
                from (
                    select
                        daily.*,
                        lag(adj_close) over (partition by ts_code order by trade_date) as lag_adj_close
                    from daily
                ) daily_with_lag
            )
            select
                now(),
                now(),
                ts_code,
                trade_date,
                ma20,
                ma60,
                vol_20,
                amount_ma20
            from rolled
            where trade_date between %(target_start)s and %(target_end)s
            on conflict (ts_code, trade_date) do update set
                updated_at = excluded.updated_at,
                ma20 = excluded.ma20,
                ma60 = excluded.ma60,
                vol_20 = excluded.vol_20,
                amount_ma20 = excluded.amount_ma20
            ''',
            params,
        )
        upserted_rows = cursor.rowcount

    return {
        'upserted_rows': upserted_rows,
        'history_start': history_start,
        'start_date': target_start,
        'end_date': target_end,
    }


def apply_daily_rolling_features_to_samples(start_date=None, end_date=None, feature_version='v1'):
    where = ['sample.feature_version = %(feature_version)s']
    params = {
        'feature_version': feature_version,
        'start_date': start_date,
        'end_date': end_date,
    }
    if start_date:
        where.append('sample.trade_date >= %(start_date)s')
    if end_date:
        where.append('sample.trade_date <= %(end_date)s')

    with connection.cursor() as cursor:
        cursor.execute('set statement_timeout = 0')
        cursor.execute(
            f'''
            update model_sample_v1 sample
            set
                ma20_bias = sample.close * nullif(sample.adj_factor, 0) / nullif(rolling.ma20, 0) - 1.0,
                ma60_bias = sample.close * nullif(sample.adj_factor, 0) / nullif(rolling.ma60, 0) - 1.0,
                vol_20 = rolling.vol_20,
                amount_ratio_20 = sample.amount / nullif(rolling.amount_ma20, 0),
                updated_at = now()
            from model_daily_rolling_features rolling
            where {' and '.join(where)}
              and rolling.ts_code = sample.ts_code
              and rolling.trade_date = sample.trade_date
            ''',
            params,
        )
        updated_rows = cursor.rowcount

    return {
        'updated_rows': updated_rows,
        'feature_version': feature_version,
        'start_date': start_date,
        'end_date': end_date,
    }


def _date_window(start_date, end_date, lookback_days=80, forward_days=25):
    if not start_date and not end_date:
        return None, None

    with connection.cursor() as cursor:
        history_start = start_date
        scan_end = end_date
        if start_date:
            cursor.execute(
                '''
                select cal_date
                from tushare_trade_cal
                where is_open = 1 and cal_date <= %s
                order by cal_date desc
                offset %s limit 1
                ''',
                [start_date, lookback_days],
            )
            row = cursor.fetchone()
            if row:
                history_start = row[0]

        if end_date:
            cursor.execute(
                '''
                select cal_date
                from tushare_trade_cal
                where is_open = 1 and cal_date >= %s
                order by cal_date
                offset %s limit 1
                ''',
                [end_date, forward_days],
            )
            row = cursor.fetchone()
            if row:
                scan_end = row[0]

    return history_start, scan_end


def _target_trade_dates(start_date=None, end_date=None):
    where = ['is_open = 1']
    params = []
    if start_date:
        where.append('cal_date >= %s')
        params.append(start_date)
    if end_date:
        where.append('cal_date <= %s')
        params.append(end_date)

    with connection.cursor() as cursor:
        cursor.execute(
            f'''
            select cal_date
            from tushare_trade_cal
            where {' and '.join(where)}
            order by cal_date
            ''',
            params,
        )
        return [row[0] for row in cursor.fetchall()]


def _existing_sample_dates(feature_version='v1', start_date=None, end_date=None):
    where = ['feature_version = %s']
    params = [feature_version]
    if start_date:
        where.append('trade_date >= %s')
        params.append(start_date)
    if end_date:
        where.append('trade_date <= %s')
        params.append(end_date)

    with connection.cursor() as cursor:
        cursor.execute(
            f'''
            select trade_date
            from model_sample_v1
            where {' and '.join(where)}
            group by trade_date
            ''',
            params,
        )
        return {row[0] for row in cursor.fetchall()}


def _relative_trade_dates(trade_date):
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            with dates as (
                select cal_date, row_number() over (order by cal_date) as rn
                from tushare_trade_cal
                where is_open = 1
            ),
            current_trade_date as (
                select rn from dates where cal_date = %s
            )
            select
                max(cal_date) filter (where dates.rn = current_trade_date.rn - 5) as d5,
                max(cal_date) filter (where dates.rn = current_trade_date.rn - 20) as d20,
                max(cal_date) filter (where dates.rn = current_trade_date.rn - 60) as d60,
                max(cal_date) filter (where dates.rn = current_trade_date.rn + 20) as f20
            from dates, current_trade_date
            ''',
            [trade_date],
        )
        row = cursor.fetchone()
    return {
        'd5': row[0],
        'd20': row[1],
        'd60': row[2],
        'f20': row[3],
    }


def build_model_samples(
    start_date=None,
    end_date=None,
    benchmark_code='000300.SH',
    feature_version='v1',
    replace=True,
    include_technical=False,
    skip_existing=False,
):
    trade_dates = _target_trade_dates(start_date, end_date)
    requested_trade_dates = len(trade_dates)
    skipped_existing_dates = 0
    if skip_existing and not replace:
        existing_dates = _existing_sample_dates(
            feature_version=feature_version,
            start_date=start_date,
            end_date=end_date,
        )
        trade_dates = [trade_date for trade_date in trade_dates if trade_date not in existing_dates]
        skipped_existing_dates = requested_trade_dates - len(trade_dates)

    build_daily_rolling_features(start_date=start_date, end_date=end_date, replace=replace)

    delete_where = ['feature_version = %(feature_version)s']
    if start_date:
        delete_where.append('trade_date >= %(target_start_date)s')
    if end_date:
        delete_where.append('trade_date <= %(target_end_date)s')
    delete_sql = ' and '.join(delete_where)

    delete_params = {
        'feature_version': feature_version,
        'target_start_date': start_date,
        'target_end_date': end_date,
    }

    if include_technical:
        technical_select_sql = '''
            coalesce(sfp.turnover_rate, db.turnover_rate) as turnover_rate,
            coalesce(sfp.volume_ratio, db.volume_ratio) as volume_ratio,
            coalesce(sfp.pe_ttm, db.pe_ttm) as pe_ttm,
            coalesce(sfp.pb, db.pb) as pb,
            coalesce(sfp.ps_ttm, db.ps_ttm) as ps_ttm,
            coalesce(sfp.dv_ttm, db.dv_ttm) as dv_ttm,
            coalesce(sfp.total_mv, db.total_mv) as total_mv,
            coalesce(sfp.circ_mv, db.circ_mv) as circ_mv,
            sfp.rsi_bfq_6 as rsi_6,
            sfp.rsi_bfq_12 as rsi_12,
            sfp.macd_bfq as macd,
            sfp.macd_dif_bfq as macd_dif,
            sfp.macd_dea_bfq as macd_dea,
            sfp.kdj_k_bfq as kdj_k,
            sfp.kdj_d_bfq as kdj_d,
            sfp.kdj_bfq as kdj_j,
            sfp.boll_mid_bfq as boll_mid,
            sfp.boll_upper_bfq as boll_upper,
            sfp.boll_lower_bfq as boll_lower
        '''
        technical_join_sql = '''
            left join tushare_stk_factor_pro sfp on sfp.ts_code = dq.ts_code and sfp.trade_date = dq.trade_date
        '''
    else:
        technical_select_sql = '''
            db.turnover_rate,
            db.volume_ratio,
            db.pe_ttm,
            db.pb,
            db.ps_ttm,
            db.dv_ttm,
            db.total_mv,
            db.circ_mv,
            null::double precision as rsi_6,
            null::double precision as rsi_12,
            null::double precision as macd,
            null::double precision as macd_dif,
            null::double precision as macd_dea,
            null::double precision as kdj_k,
            null::double precision as kdj_d,
            null::double precision as kdj_j,
            null::double precision as boll_mid,
            null::double precision as boll_upper,
            null::double precision as boll_lower
        '''
        technical_join_sql = ''

    current_rows_sql = f'''
        create temporary table tmp_model_sample_current on commit drop as
        select
            dq.ts_code,
            dq.trade_date,
            sb.name as stock_name,
            sb.industry,
            sb.list_date,
            dq.close,
            dq.pct_chg,
            dq.amount,
            af.adj_factor,
            {technical_select_sql},
            dq.close * nullif(af.adj_factor, 0) as adj_close
        from tushare_stock_daily dq
        left join tushare_stock_basic sb on sb.ts_code = dq.ts_code
        left join tushare_stock_daily_basic db on db.ts_code = dq.ts_code and db.trade_date = dq.trade_date
        left join tushare_adj_factor af on af.ts_code = dq.ts_code and af.trade_date = dq.trade_date
        {technical_join_sql}
        where dq.trade_date = %(trade_date)s
          and dq.close is not null
    '''

    point_prices_sql = '''
        create temporary table tmp_model_sample_points on commit drop as
        select
            dq.ts_code,
            max(dq.close * nullif(af.adj_factor, 0)) filter (where dq.trade_date = %(d5)s) as adj_close_5,
            max(dq.close * nullif(af.adj_factor, 0)) filter (where dq.trade_date = %(d20)s) as adj_close_20,
            max(dq.close * nullif(af.adj_factor, 0)) filter (where dq.trade_date = %(d60)s) as adj_close_60,
            max(dq.close * nullif(af.adj_factor, 0)) filter (where dq.trade_date = %(f20)s) as future_adj_close_20
        from tushare_stock_daily dq
        left join tushare_adj_factor af on af.ts_code = dq.ts_code and af.trade_date = dq.trade_date
        where dq.trade_date in (%(d5)s, %(d20)s, %(d60)s, %(f20)s)
        group by dq.ts_code
    '''
    rolling_features_sql = '''
        create temporary table tmp_model_sample_rolling on commit drop as
        select
            rolling.ts_code,
            rolling.ma20,
            rolling.ma60,
            rolling.vol_20,
            rolling.amount_ma20
        from model_daily_rolling_features rolling
        where rolling.trade_date = %(trade_date)s
    '''

    insert_sql = '''
        insert into model_sample_v1 (
            created_at, updated_at, ts_code, trade_date, stock_name, industry, list_date,
            close, pct_chg, amount, adj_factor, turnover_rate, volume_ratio, pe_ttm, pb,
            ps_ttm, dv_ttm, total_mv, circ_mv, ret_5, ret_20, ret_60, ma20_bias,
            ma60_bias, vol_20, amount_ratio_20, rsi_6, rsi_12, macd, macd_dif, macd_dea,
            kdj_k, kdj_d, kdj_j, boll_mid, boll_upper, boll_lower, roe, roa,
            grossprofit_margin, netprofit_margin, debt_to_assets, ocf_to_profit,
            revenue_yoy, netprofit_yoy, net_mf_amount, net_mf_amount_ratio,
            margin_balance, margin_buy_ratio, hk_hold_ratio, is_st, is_limit_up,
            is_limit_down, pledge_ratio, days_since_list, benchmark_code, benchmark_ret_20,
            future_ret_20, future_excess_ret_20, label_up_20, label_outperform_20,
            feature_version
        )
        with base as (
            select current_rows.*, point_prices.adj_close_5, point_prices.adj_close_20,
                point_prices.adj_close_60, point_prices.future_adj_close_20,
                rolling.ma20,
                rolling.ma60,
                rolling.vol_20,
                rolling.amount_ma20
            from tmp_model_sample_current current_rows
            left join tmp_model_sample_points point_prices on point_prices.ts_code = current_rows.ts_code
            left join tmp_model_sample_rolling rolling on rolling.ts_code = current_rows.ts_code
        ),
        enriched as (
            select
                base.*,
                null::double precision as roe,
                null::double precision as roa,
                null::double precision as grossprofit_margin,
                null::double precision as netprofit_margin,
                null::double precision as debt_to_assets,
                null::double precision as ocf_to_profit,
                null::double precision as revenue_yoy,
                null::double precision as netprofit_yoy,
                mf.net_mf_amount,
                md.rzrqye as margin_balance,
                md.rzmre as margin_buy,
                null::double precision as hk_hold_ratio,
                null::double precision as pledge_ratio,
                st.ts_code is not null as is_st,
                sl.up_limit is not null and base.close >= sl.up_limit as is_limit_up,
                sl.down_limit is not null and base.close <= sl.down_limit as is_limit_down
            from base
            left join tushare_moneyflow mf on mf.ts_code = base.ts_code and mf.trade_date = base.trade_date
            left join tushare_margin_detail md on md.ts_code = base.ts_code and md.trade_date = base.trade_date
            left join tushare_stock_st st on st.ts_code = base.ts_code and st.trade_date = base.trade_date
            left join tushare_stk_limit sl on sl.ts_code = base.ts_code and sl.trade_date = base.trade_date
        ),
        benchmark as (
            select
                current_idx.close,
                future_idx.close as future_close_20
            from tushare_index_daily
                current_idx
            left join tushare_index_daily future_idx
                on future_idx.ts_code = current_idx.ts_code
               and future_idx.trade_date = %(f20)s
            where current_idx.ts_code = %(benchmark_code)s
              and current_idx.trade_date = %(trade_date)s
        )
        select
            now(), now(), e.ts_code, e.trade_date, e.stock_name, e.industry, e.list_date,
            e.close, e.pct_chg, e.amount, e.adj_factor, e.turnover_rate, e.volume_ratio,
            e.pe_ttm, e.pb, e.ps_ttm, e.dv_ttm, e.total_mv, e.circ_mv,
            (e.adj_close / nullif(e.adj_close_5, 0) - 1.0),
            (e.adj_close / nullif(e.adj_close_20, 0) - 1.0),
            (e.adj_close / nullif(e.adj_close_60, 0) - 1.0),
            (e.adj_close / nullif(e.ma20, 0) - 1.0),
            (e.adj_close / nullif(e.ma60, 0) - 1.0),
            e.vol_20,
            (e.amount / nullif(e.amount_ma20, 0)),
            e.rsi_6, e.rsi_12, e.macd, e.macd_dif, e.macd_dea, e.kdj_k, e.kdj_d, e.kdj_j,
            e.boll_mid, e.boll_upper, e.boll_lower, e.roe, e.roa, e.grossprofit_margin,
            e.netprofit_margin, e.debt_to_assets, e.ocf_to_profit, e.revenue_yoy,
            e.netprofit_yoy, e.net_mf_amount,
            (e.net_mf_amount / nullif(e.amount, 0)),
            e.margin_balance,
            (e.margin_buy / nullif(e.amount * 1000.0, 0)),
            e.hk_hold_ratio, coalesce(e.is_st, false), coalesce(e.is_limit_up, false),
            coalesce(e.is_limit_down, false), e.pledge_ratio,
            case
                when e.list_date ~ '^[0-9]{{8}}$'
                then to_date(e.trade_date, 'YYYYMMDD') - to_date(e.list_date, 'YYYYMMDD')
                else null
            end,
            %(benchmark_code)s,
            (b.future_close_20 / nullif(b.close, 0) - 1.0),
            (e.future_adj_close_20 / nullif(e.adj_close, 0) - 1.0),
            (e.future_adj_close_20 / nullif(e.adj_close, 0) - 1.0)
                - (b.future_close_20 / nullif(b.close, 0) - 1.0),
            case when e.future_adj_close_20 is null or e.adj_close is null then null
                 else (e.future_adj_close_20 / nullif(e.adj_close, 0) - 1.0) > 0
            end,
            case when e.future_adj_close_20 is null or e.adj_close is null
                   or b.future_close_20 is null or b.close is null then null
                 else (e.future_adj_close_20 / nullif(e.adj_close, 0) - 1.0)
                    > (b.future_close_20 / nullif(b.close, 0) - 1.0)
            end,
            %(feature_version)s
        from enriched e
        cross join benchmark b
        where e.adj_close is not null
        on conflict (ts_code, trade_date, feature_version) do update set
            updated_at = excluded.updated_at,
            stock_name = excluded.stock_name,
            industry = excluded.industry,
            list_date = excluded.list_date,
            close = excluded.close,
            pct_chg = excluded.pct_chg,
            amount = excluded.amount,
            adj_factor = excluded.adj_factor,
            turnover_rate = excluded.turnover_rate,
            volume_ratio = excluded.volume_ratio,
            pe_ttm = excluded.pe_ttm,
            pb = excluded.pb,
            ps_ttm = excluded.ps_ttm,
            dv_ttm = excluded.dv_ttm,
            total_mv = excluded.total_mv,
            circ_mv = excluded.circ_mv,
            ret_5 = excluded.ret_5,
            ret_20 = excluded.ret_20,
            ret_60 = excluded.ret_60,
            ma20_bias = excluded.ma20_bias,
            ma60_bias = excluded.ma60_bias,
            vol_20 = excluded.vol_20,
            amount_ratio_20 = excluded.amount_ratio_20,
            rsi_6 = excluded.rsi_6,
            rsi_12 = excluded.rsi_12,
            macd = excluded.macd,
            macd_dif = excluded.macd_dif,
            macd_dea = excluded.macd_dea,
            kdj_k = excluded.kdj_k,
            kdj_d = excluded.kdj_d,
            kdj_j = excluded.kdj_j,
            boll_mid = excluded.boll_mid,
            boll_upper = excluded.boll_upper,
            boll_lower = excluded.boll_lower,
            roe = excluded.roe,
            roa = excluded.roa,
            grossprofit_margin = excluded.grossprofit_margin,
            netprofit_margin = excluded.netprofit_margin,
            debt_to_assets = excluded.debt_to_assets,
            ocf_to_profit = excluded.ocf_to_profit,
            revenue_yoy = excluded.revenue_yoy,
            netprofit_yoy = excluded.netprofit_yoy,
            net_mf_amount = excluded.net_mf_amount,
            net_mf_amount_ratio = excluded.net_mf_amount_ratio,
            margin_balance = excluded.margin_balance,
            margin_buy_ratio = excluded.margin_buy_ratio,
            hk_hold_ratio = excluded.hk_hold_ratio,
            is_st = excluded.is_st,
            is_limit_up = excluded.is_limit_up,
            is_limit_down = excluded.is_limit_down,
            pledge_ratio = excluded.pledge_ratio,
            days_since_list = excluded.days_since_list,
            benchmark_code = excluded.benchmark_code,
            benchmark_ret_20 = excluded.benchmark_ret_20,
            future_ret_20 = excluded.future_ret_20,
            future_excess_ret_20 = excluded.future_excess_ret_20,
            label_up_20 = excluded.label_up_20,
            label_outperform_20 = excluded.label_outperform_20
    '''

    inserted = 0
    with connection.cursor() as cursor:
        cursor.execute('set statement_timeout = 0')
        if replace:
            cursor.execute(f'delete from model_sample_v1 where {delete_sql}', delete_params)

    for trade_date in trade_dates:
        related = _relative_trade_dates(trade_date)
        if not related['d60'] or not related['f20']:
            continue
        params = {
            'benchmark_code': benchmark_code,
            'feature_version': feature_version,
            'trade_date': trade_date,
            **related,
        }
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('set local max_parallel_workers_per_gather = 0')
                cursor.execute('drop table if exists tmp_model_sample_current')
                cursor.execute('drop table if exists tmp_model_sample_points')
                cursor.execute('drop table if exists tmp_model_sample_rolling')
                cursor.execute(current_rows_sql, params)
                cursor.execute(point_prices_sql, params)
                cursor.execute(rolling_features_sql, params)
                cursor.execute('create index on tmp_model_sample_current (ts_code)')
                cursor.execute('create index on tmp_model_sample_points (ts_code)')
                cursor.execute('create index on tmp_model_sample_rolling (ts_code)')
                cursor.execute('analyze tmp_model_sample_current')
                cursor.execute('analyze tmp_model_sample_points')
                cursor.execute('analyze tmp_model_sample_rolling')
                cursor.execute(insert_sql, params)
                inserted += cursor.rowcount

    return {
        'inserted_or_updated': inserted,
        'trade_dates': len(trade_dates),
        'requested_trade_dates': requested_trade_dates,
        'skipped_existing_dates': skipped_existing_dates,
        'summary': sample_summary(feature_version=feature_version),
    }


def _enrich_where_sql(start_date=None, end_date=None, feature_version='v1', only_missing=False):
    where = ['feature_version = %(feature_version)s']
    params = {
        'feature_version': feature_version,
        'start_date': start_date,
        'end_date': end_date,
    }
    if start_date:
        where.append('trade_date >= %(start_date)s')
    if end_date:
        where.append('trade_date <= %(end_date)s')
    if only_missing:
        where.append('(roe is null or revenue_yoy is null or pledge_ratio is null)')
    return ' and '.join(where), params


def enrich_trade_dates(start_date=None, end_date=None, feature_version='v1', only_missing=False):
    where_sql, params = _enrich_where_sql(
        start_date=start_date,
        end_date=end_date,
        feature_version=feature_version,
        only_missing=only_missing,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f'''
            select trade_date
            from model_sample_v1
            where {where_sql}
            group by trade_date
            order by trade_date
            ''',
            params,
        )
        return [row[0] for row in cursor.fetchall()]


def _enrich_model_samples_where(where_sql, params):

    update_sql = f'''
        create temporary table tmp_model_sample_targets on commit drop as
        select id, ts_code, trade_date
        from model_sample_v1
        where {where_sql};

        create index on tmp_model_sample_targets (ts_code, trade_date);
        analyze tmp_model_sample_targets;

        update model_sample_v1 sample
        set
            updated_at = now(),
            roe = financial.roe,
            roa = financial.roa,
            grossprofit_margin = financial.grossprofit_margin,
            netprofit_margin = financial.netprofit_margin,
            debt_to_assets = financial.debt_to_assets,
            ocf_to_profit = financial.ocf_to_profit,
            revenue_yoy = financial.revenue_yoy,
            netprofit_yoy = financial.netprofit_yoy,
            hk_hold_ratio = null,
            pledge_ratio = pledge.pledge_ratio
        from tmp_model_sample_targets targets
        left join lateral (
            select
                fi.roe,
                fi.roa,
                fi.grossprofit_margin,
                fi.netprofit_margin,
                fi.debt_to_assets,
                fi.ocf_to_profit,
                fi.or_yoy as revenue_yoy,
                fi.netprofit_yoy
            from tushare_fina_indicator fi
            where fi.ts_code = targets.ts_code
              and fi.ann_date <= targets.trade_date
            order by fi.ann_date desc, fi.end_date desc
            limit 1
        ) financial on true
        left join lateral (
            select ps.pledge_ratio
            from tushare_pledge_stat ps
            where ps.ts_code = targets.ts_code
              and ps.end_date <= targets.trade_date
            order by ps.end_date desc
            limit 1
        ) pledge on true
        where sample.id = targets.id;
    '''

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('set local max_parallel_workers_per_gather = 0')
            cursor.execute(update_sql, params)


def enrich_model_samples(start_date=None, end_date=None, feature_version='v1', only_missing=False):
    where_sql, params = _enrich_where_sql(
        start_date=start_date,
        end_date=end_date,
        feature_version=feature_version,
        only_missing=only_missing,
    )
    _enrich_model_samples_where(where_sql, params)

    return {
        'summary': enrich_summary(feature_version=feature_version, start_date=start_date, end_date=end_date),
    }


def enrich_model_samples_batch(
    start_date=None,
    end_date=None,
    feature_version='v1',
    only_missing=False,
    batch_dates=None,
):
    where_sql, params = _enrich_where_sql(
        start_date=start_date,
        end_date=end_date,
        feature_version=feature_version,
        only_missing=only_missing,
    )
    if batch_dates is not None:
        where_sql = f'{where_sql} and trade_date = any(%(batch_dates)s)'
        params['batch_dates'] = batch_dates

    with connection.cursor() as cursor:
        cursor.execute(
            f'''
            select count(*)::bigint
            from model_sample_v1
            where {where_sql}
            ''',
            params,
        )
        target_rows = cursor.fetchone()[0]

    if target_rows:
        _enrich_model_samples_where(where_sql, params)

    return {
        'target_rows': target_rows,
    }
