from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StockBasic(TimestampedModel):
    ts_code = models.CharField('TS股票代码', max_length=24, unique=True, db_comment='TuShare股票代码')
    symbol = models.CharField('股票代码', max_length=24, blank=True, null=True, db_index=True, db_comment='股票代码')
    name = models.CharField('股票名称', max_length=80, blank=True, null=True, db_index=True, db_comment='股票名称')
    area = models.CharField('地域', max_length=80, blank=True, null=True, db_comment='地域')
    industry = models.CharField('所属行业', max_length=120, blank=True, null=True, db_comment='所属行业')
    fullname = models.CharField('股票全称', max_length=200, blank=True, null=True, db_comment='股票全称')
    enname = models.CharField('英文全称', max_length=240, blank=True, null=True, db_comment='英文全称')
    cnspell = models.CharField('拼音缩写', max_length=80, blank=True, null=True, db_comment='拼音缩写')
    market = models.CharField('市场类型', max_length=40, blank=True, null=True, db_comment='市场类型')
    exchange = models.CharField('交易所代码', max_length=16, blank=True, null=True, db_comment='交易所代码')
    curr_type = models.CharField('交易货币', max_length=16, blank=True, null=True, db_comment='交易货币')
    list_status = models.CharField('上市状态', max_length=8, blank=True, null=True, db_index=True, db_comment='上市状态 L上市 D退市 P暂停上市 G其他')
    list_date = models.CharField('上市日期', max_length=8, blank=True, null=True, db_comment='上市日期 YYYYMMDD')
    delist_date = models.CharField('退市日期', max_length=8, blank=True, null=True, db_comment='退市日期 YYYYMMDD')
    is_hs = models.CharField('是否沪深港通标的', max_length=8, blank=True, null=True, db_comment='是否沪深港通标的 N否 H沪股通 S深股通')
    act_name = models.CharField('实控人名称', max_length=160, blank=True, null=True, db_comment='实控人名称')
    act_ent_type = models.CharField('实控人企业性质', max_length=80, blank=True, null=True, db_comment='实控人企业性质')
    tushare_meta = models.JSONField('TuShare元数据', default=dict, blank=True, db_comment='TuShare分类、接口和目标表元数据')

    class Meta:
        db_table = 'tushare_stock_basic'
        db_table_comment = 'TuShare股票基础信息'
        indexes = [
            models.Index(fields=['list_status', 'exchange'], name='ix_stkb_status_exchange'),
            models.Index(fields=['list_status', 'market'], name='ix_stkb_status_market'),
            models.Index(fields=['industry', 'area'], name='ix_stkb_industry_area'),
            models.Index(fields=['list_date'], name='ix_stkb_list_date'),
            models.Index(fields=['updated_at'], name='ix_stkb_updated_at'),
        ]


class StockBasicHistory(TimestampedModel):
    ts_code = models.CharField('TS股票代码', max_length=24, db_index=True, db_comment='TuShare股票代码')
    field_name = models.CharField('变更字段', max_length=80, db_index=True, db_comment='发生变化的字段名')
    old_value = models.TextField('旧值', blank=True, null=True, db_comment='变更前字段值')
    new_value = models.TextField('新值', blank=True, null=True, db_comment='变更后字段值')
    source_date = models.CharField('来源日期', max_length=8, blank=True, default='', db_index=True, db_comment='同步发现变更日期 YYYYMMDD')
    raw_record = models.JSONField('原始记录', default=dict, blank=True, db_comment='触发变更的TuShare原始记录')

    class Meta:
        db_table = 'tushare_stock_basic_history'
        db_table_comment = 'TuShare股票基础信息变更历史'
        indexes = [
            models.Index(fields=['ts_code', 'created_at'], name='ix_stkbh_code_created'),
            models.Index(fields=['field_name', 'created_at'], name='ix_stkbh_field_created'),
            models.Index(fields=['ts_code', 'field_name', 'created_at'], name='ix_stkbh_code_field'),
            models.Index(fields=['source_date', 'ts_code'], name='ix_stkbh_source_code'),
        ]


class TradeCal(TimestampedModel):
    exchange = models.CharField('交易所', max_length=16, db_comment='交易所 SSE上交所 SZSE深交所')
    cal_date = models.CharField('日历日期', max_length=8, db_comment='日历日期 YYYYMMDD')
    is_open = models.IntegerField('是否交易', blank=True, null=True, db_index=True, db_comment='是否交易 0休市 1交易')
    pretrade_date = models.CharField('上一交易日', max_length=8, blank=True, null=True, db_comment='上一交易日 YYYYMMDD')
    tushare_meta = models.JSONField('TuShare元数据', default=dict, blank=True, db_comment='TuShare分类、接口和目标表元数据')

    class Meta:
        db_table = 'tushare_trade_cal'
        db_table_comment = 'TuShare交易日历'
        constraints = [
            models.UniqueConstraint(fields=['exchange', 'cal_date'], name='uniq_trade_cal_exchange_date'),
        ]
        indexes = [
            models.Index(fields=['is_open', 'cal_date']),
        ]


class StockCapitalPremarket(TimestampedModel):
    trade_date = models.CharField('交易日期', max_length=8, db_comment='交易日期 YYYYMMDD')
    ts_code = models.CharField('TS股票代码', max_length=24, db_comment='TuShare股票代码')
    total_share = models.FloatField('总股本', blank=True, null=True, db_comment='总股本 万股')
    float_share = models.FloatField('流通股本', blank=True, null=True, db_comment='流通股本 万股')
    pre_close = models.FloatField('昨收价', blank=True, null=True, db_comment='昨收价')
    up_limit = models.FloatField('涨停价', blank=True, null=True, db_comment='涨停价')
    down_limit = models.FloatField('跌停价', blank=True, null=True, db_comment='跌停价')
    tushare_meta = models.JSONField('TuShare元数据', default=dict, blank=True, db_comment='TuShare分类、接口和目标表元数据')

    class Meta:
        db_table = 'tushare_stk_premarket'
        db_table_comment = 'TuShare股本情况盘前'
        constraints = [
            models.UniqueConstraint(fields=['ts_code', 'trade_date'], name='uniq_stk_premarket_ts_code_date'),
        ]
        indexes = [
            models.Index(fields=['trade_date', 'ts_code']),
            models.Index(fields=['ts_code', 'trade_date']),
        ]


class StockSTList(TimestampedModel):
    ts_code = models.CharField('TS股票代码', max_length=24, db_comment='TuShare股票代码')
    name = models.CharField('股票名称', max_length=80, blank=True, null=True, db_comment='股票名称')
    trade_date = models.CharField('交易日期', max_length=8, db_comment='交易日期 YYYYMMDD')
    type = models.CharField('风险类型', max_length=16, blank=True, null=True, db_index=True, db_comment='风险警示类型代码')
    type_name = models.CharField('风险类型名称', max_length=80, blank=True, null=True, db_comment='风险警示类型名称')
    tushare_meta = models.JSONField('TuShare元数据', default=dict, blank=True, db_comment='TuShare分类、接口和目标表元数据')

    class Meta:
        db_table = 'tushare_stock_st'
        db_table_comment = 'TuShare ST股票列表'
        constraints = [
            models.UniqueConstraint(fields=['ts_code', 'trade_date', 'type'], name='uniq_stock_st_code_date_type'),
        ]
        indexes = [
            models.Index(fields=['trade_date', 'type']),
            models.Index(fields=['ts_code', 'trade_date']),
        ]


class StockSTRiskNotice(TimestampedModel):
    ts_code = models.CharField('TS股票代码', max_length=24, db_comment='TuShare股票代码')
    name = models.CharField('股票名称', max_length=80, blank=True, null=True, db_comment='股票名称')
    pub_date = models.CharField('公告日期', max_length=8, db_comment='公告日期 YYYYMMDD')
    imp_date = models.CharField('实施日期', max_length=8, blank=True, null=True, db_index=True, db_comment='实施日期 YYYYMMDD')
    st_tpye = models.CharField('ST类型', max_length=40, blank=True, null=True, db_comment='TuShare接口字段名为st_tpye')
    st_reason = models.TextField('ST原因', blank=True, null=True, db_comment='风险警示原因')
    st_explain = models.TextField('ST说明', blank=True, null=True, db_comment='风险警示说明')
    tushare_meta = models.JSONField('TuShare元数据', default=dict, blank=True, db_comment='TuShare分类、接口和目标表元数据')

    class Meta:
        db_table = 'tushare_st_risk_notice'
        db_table_comment = 'TuShare ST风险警示板股票'
        constraints = [
            models.UniqueConstraint(fields=['ts_code', 'pub_date', 'st_tpye'], name='uniq_st_risk_code_pub_type'),
        ]
        indexes = [
            models.Index(fields=['pub_date', 'ts_code']),
            models.Index(fields=['ts_code', 'imp_date']),
        ]


class StockHsgt(TimestampedModel):
    ts_code = models.CharField('TS股票代码', max_length=24, db_comment='TuShare股票代码')
    trade_date = models.CharField('交易日期', max_length=8, db_comment='交易日期 YYYYMMDD')
    type = models.CharField('港股通类型', max_length=16, db_index=True, db_comment='沪深港通类型')
    name = models.CharField('股票名称', max_length=80, blank=True, null=True, db_comment='股票名称')
    type_name = models.CharField('港股通类型名称', max_length=80, blank=True, null=True, db_comment='沪深港通类型名称')
    tushare_meta = models.JSONField('TuShare元数据', default=dict, blank=True, db_comment='TuShare分类、接口和目标表元数据')

    class Meta:
        db_table = 'tushare_stock_hsgt'
        db_table_comment = 'TuShare沪深港通股票列表'
        constraints = [
            models.UniqueConstraint(fields=['ts_code', 'trade_date', 'type'], name='uniq_stock_hsgt_code_date_type'),
        ]
        indexes = [
            models.Index(fields=['trade_date', 'type']),
            models.Index(fields=['ts_code', 'trade_date']),
        ]


class StockNameChange(TimestampedModel):
    ts_code = models.CharField('TS股票代码', max_length=24, db_comment='TuShare股票代码')
    name = models.CharField('证券名称', max_length=80, db_comment='证券名称')
    start_date = models.CharField('开始日期', max_length=8, blank=True, null=True, db_index=True, db_comment='开始日期 YYYYMMDD')
    end_date = models.CharField('结束日期', max_length=8, blank=True, null=True, db_index=True, db_comment='结束日期 YYYYMMDD')
    ann_date = models.CharField('公告日期', max_length=8, blank=True, null=True, db_index=True, db_comment='公告日期 YYYYMMDD')
    change_reason = models.CharField('变更原因', max_length=200, blank=True, null=True, db_comment='变更原因')
    tushare_meta = models.JSONField('TuShare元数据', default=dict, blank=True, db_comment='TuShare分类、接口和目标表元数据')

    class Meta:
        db_table = 'tushare_stock_namechange'
        db_table_comment = 'TuShare股票曾用名'
        constraints = [
            models.UniqueConstraint(fields=['ts_code', 'name', 'start_date'], name='uniq_namechange_code_name_start'),
        ]
        indexes = [
            models.Index(fields=['ts_code', 'start_date']),
            models.Index(fields=['ann_date', 'ts_code']),
        ]


class StockCompany(TimestampedModel):
    ts_code = models.CharField('TS股票代码', max_length=24, unique=True, db_comment='TuShare股票代码')
    com_name = models.CharField('公司全称', max_length=240, blank=True, null=True, db_index=True, db_comment='公司全称')
    com_id = models.CharField('统一社会信用代码', max_length=64, blank=True, null=True, db_index=True, db_comment='统一社会信用代码')
    exchange = models.CharField('交易所代码', max_length=16, blank=True, null=True, db_index=True, db_comment='交易所代码')
    chairman = models.CharField('法人代表', max_length=80, blank=True, null=True, db_comment='法人代表')
    manager = models.CharField('总经理', max_length=80, blank=True, null=True, db_comment='总经理')
    secretary = models.CharField('董秘', max_length=80, blank=True, null=True, db_comment='董事会秘书')
    reg_capital = models.FloatField('注册资本', blank=True, null=True, db_comment='注册资本 万元')
    setup_date = models.CharField('注册日期', max_length=8, blank=True, null=True, db_index=True, db_comment='注册日期 YYYYMMDD')
    province = models.CharField('所在省份', max_length=80, blank=True, null=True, db_comment='所在省份')
    city = models.CharField('所在城市', max_length=80, blank=True, null=True, db_comment='所在城市')
    introduction = models.TextField('公司介绍', blank=True, null=True, db_comment='公司介绍')
    website = models.CharField('公司主页', max_length=240, blank=True, null=True, db_comment='公司主页')
    email = models.CharField('电子邮件', max_length=160, blank=True, null=True, db_comment='电子邮件')
    office = models.CharField('办公室', max_length=300, blank=True, null=True, db_comment='办公室地址')
    employees = models.IntegerField('员工人数', blank=True, null=True, db_comment='员工人数')
    main_business = models.TextField('主要业务及产品', blank=True, null=True, db_comment='主要业务及产品')
    business_scope = models.TextField('经营范围', blank=True, null=True, db_comment='经营范围')
    tushare_meta = models.JSONField('TuShare元数据', default=dict, blank=True, db_comment='TuShare分类、接口和目标表元数据')

    class Meta:
        db_table = 'tushare_stock_company'
        db_table_comment = 'TuShare上市公司基本信息'
        indexes = [
            models.Index(fields=['exchange', 'ts_code']),
            models.Index(fields=['province', 'city']),
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
