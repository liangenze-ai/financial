from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StockBasic(TimestampedModel):
    ts_code = models.CharField(max_length=24, unique=True)
    symbol = models.CharField(max_length=24, blank=True, null=True, db_index=True)
    name = models.CharField(max_length=80, blank=True, null=True, db_index=True)
    area = models.CharField(max_length=80, blank=True, null=True)
    industry = models.CharField(max_length=120, blank=True, null=True)
    fullname = models.CharField(max_length=200, blank=True, null=True)
    enname = models.CharField(max_length=240, blank=True, null=True)
    cnspell = models.CharField(max_length=80, blank=True, null=True)
    market = models.CharField(max_length=40, blank=True, null=True)
    exchange = models.CharField(max_length=16, blank=True, null=True)
    curr_type = models.CharField(max_length=16, blank=True, null=True)
    list_status = models.CharField(max_length=8, blank=True, null=True, db_index=True)
    list_date = models.CharField(max_length=8, blank=True, null=True)
    delist_date = models.CharField(max_length=8, blank=True, null=True)
    is_hs = models.CharField(max_length=8, blank=True, null=True)
    act_name = models.CharField(max_length=160, blank=True, null=True)
    act_ent_type = models.CharField(max_length=80, blank=True, null=True)
    tushare_meta = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'tushare_stock_basic'


class StockBasicHistory(TimestampedModel):
    ts_code = models.CharField(max_length=24, db_index=True)
    field_name = models.CharField(max_length=80, db_index=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    source_date = models.CharField(max_length=8, blank=True, default='')
    raw_record = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'tushare_stock_basic_history'
        indexes = [
            models.Index(fields=['ts_code', 'created_at']),
            models.Index(fields=['field_name', 'created_at']),
        ]


class TradeCal(TimestampedModel):
    exchange = models.CharField(max_length=16)
    cal_date = models.CharField(max_length=8)
    is_open = models.IntegerField(blank=True, null=True, db_index=True)
    pretrade_date = models.CharField(max_length=8, blank=True, null=True)
    tushare_meta = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'tushare_trade_cal'
        constraints = [
            models.UniqueConstraint(fields=['exchange', 'cal_date'], name='uniq_trade_cal_exchange_date'),
        ]
        indexes = [
            models.Index(fields=['is_open', 'cal_date']),
        ]


class DailyQuote(TimestampedModel):
    ts_code = models.CharField(max_length=24)
    trade_date = models.CharField(max_length=8)
    open = models.FloatField(blank=True, null=True)
    high = models.FloatField(blank=True, null=True)
    low = models.FloatField(blank=True, null=True)
    close = models.FloatField(blank=True, null=True)
    pre_close = models.FloatField(blank=True, null=True)
    change = models.FloatField(blank=True, null=True)
    pct_chg = models.FloatField(blank=True, null=True)
    vol = models.FloatField(blank=True, null=True)
    amount = models.FloatField(blank=True, null=True)
    tushare_meta = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'tushare_stock_daily'
        constraints = [
            models.UniqueConstraint(fields=['ts_code', 'trade_date'], name='uniq_daily_ts_code_date'),
        ]
        indexes = [
            models.Index(fields=['trade_date', 'ts_code']),
        ]


class DailyBasic(TimestampedModel):
    ts_code = models.CharField(max_length=24)
    trade_date = models.CharField(max_length=8)
    close = models.FloatField(blank=True, null=True)
    turnover_rate = models.FloatField(blank=True, null=True)
    volume_ratio = models.FloatField(blank=True, null=True)
    pe_ttm = models.FloatField(blank=True, null=True)
    pb = models.FloatField(blank=True, null=True)
    ps_ttm = models.FloatField(blank=True, null=True)
    dv_ttm = models.FloatField(blank=True, null=True)
    total_mv = models.FloatField(blank=True, null=True)
    circ_mv = models.FloatField(blank=True, null=True)
    tushare_meta = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'tushare_stock_daily_basic'
        constraints = [
            models.UniqueConstraint(fields=['ts_code', 'trade_date'], name='uniq_daily_basic_ts_code_date'),
        ]
        indexes = [
            models.Index(fields=['trade_date', 'ts_code']),
        ]


class SyncJob(TimestampedModel):
    name = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=24)
    start_date = models.CharField(max_length=8, blank=True, null=True)
    end_date = models.CharField(max_length=8, blank=True, null=True)
    current_date = models.CharField(max_length=8, blank=True, default='')
    current_step = models.CharField(max_length=40, blank=True, default='')
    processed_dates = models.IntegerField(default=0)
    message = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'system_sync_jobs'
