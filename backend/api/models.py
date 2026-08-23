from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StockBasic(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, unique=True, db_comment="TuShare股票代码")
    symbol = models.CharField("股票代码", max_length=24, blank=True, null=True, db_index=True, db_comment="股票代码")
    name = models.CharField("股票名称", max_length=80, blank=True, null=True, db_index=True, db_comment="股票名称")
    area = models.CharField("地域", max_length=80, blank=True, null=True, db_comment="地域")
    industry = models.CharField("所属行业", max_length=120, blank=True, null=True, db_comment="所属行业")
    fullname = models.CharField("股票全称", max_length=200, blank=True, null=True, db_comment="股票全称")
    enname = models.CharField("英文全称", max_length=240, blank=True, null=True, db_comment="英文全称")
    cnspell = models.CharField("拼音缩写", max_length=80, blank=True, null=True, db_comment="拼音缩写")
    market = models.CharField("市场类型", max_length=40, blank=True, null=True, db_comment="市场类型")
    exchange = models.CharField("交易所代码", max_length=16, blank=True, null=True, db_comment="交易所代码")
    curr_type = models.CharField("交易货币", max_length=16, blank=True, null=True, db_comment="交易货币")
    list_status = models.CharField(
        "上市状态",
        max_length=8,
        blank=True,
        null=True,
        db_index=True,
        db_comment="上市状态 L上市 D退市 P暂停上市 G其他",
    )
    list_date = models.CharField("上市日期", max_length=8, blank=True, null=True, db_comment="上市日期 YYYYMMDD")
    delist_date = models.CharField("退市日期", max_length=8, blank=True, null=True, db_comment="退市日期 YYYYMMDD")
    is_hs = models.CharField(
        "是否沪深港通标的", max_length=8, blank=True, null=True, db_comment="是否沪深港通标的 N否 H沪股通 S深股通"
    )
    act_name = models.CharField("实控人名称", max_length=160, blank=True, null=True, db_comment="实控人名称")
    act_ent_type = models.CharField("实控人企业性质", max_length=80, blank=True, null=True, db_comment="实控人企业性质")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_stock_basic"
        db_table_comment = "TuShare股票基础信息"
        indexes = [
            models.Index(fields=["list_status", "exchange"], name="ix_stkb_status_exchange"),
            models.Index(fields=["list_status", "market"], name="ix_stkb_status_market"),
            models.Index(fields=["industry", "area"], name="ix_stkb_industry_area"),
            models.Index(fields=["list_date"], name="ix_stkb_list_date"),
            models.Index(fields=["updated_at"], name="ix_stkb_updated_at"),
        ]


class StockBasicHistory(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_index=True, db_comment="TuShare股票代码")
    field_name = models.CharField("变更字段", max_length=80, db_index=True, db_comment="发生变化的字段名")
    old_value = models.TextField("旧值", blank=True, null=True, db_comment="变更前字段值")
    new_value = models.TextField("新值", blank=True, null=True, db_comment="变更后字段值")
    source_date = models.CharField(
        "来源日期", max_length=8, blank=True, default="", db_index=True, db_comment="同步发现变更日期 YYYYMMDD"
    )
    raw_record = models.JSONField("原始记录", default=dict, blank=True, db_comment="触发变更的TuShare原始记录")

    class Meta:
        db_table = "tushare_stock_basic_history"
        db_table_comment = "TuShare股票基础信息变更历史"
        indexes = [
            models.Index(fields=["ts_code", "created_at"], name="ix_stkbh_code_created"),
            models.Index(fields=["field_name", "created_at"], name="ix_stkbh_field_created"),
            models.Index(fields=["ts_code", "field_name", "created_at"], name="ix_stkbh_code_field"),
            models.Index(fields=["source_date", "ts_code"], name="ix_stkbh_source_code"),
        ]


class TradeCal(TimestampedModel):
    exchange = models.CharField("交易所", max_length=16, db_comment="交易所 SSE上交所 SZSE深交所")
    cal_date = models.CharField("日历日期", max_length=8, db_comment="日历日期 YYYYMMDD")
    is_open = models.IntegerField("是否交易", blank=True, null=True, db_index=True, db_comment="是否交易 0休市 1交易")
    pretrade_date = models.CharField(
        "上一交易日", max_length=8, blank=True, null=True, db_comment="上一交易日 YYYYMMDD"
    )
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_trade_cal"
        db_table_comment = "TuShare交易日历"
        constraints = [
            models.UniqueConstraint(fields=["exchange", "cal_date"], name="uniq_trade_cal_exchange_date"),
        ]
        indexes = [
            models.Index(fields=["is_open", "cal_date"]),
        ]


class StockCapitalPremarket(TimestampedModel):
    trade_date = models.CharField("交易日期", max_length=8, db_comment="交易日期 YYYYMMDD")
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    total_share = models.FloatField("总股本", blank=True, null=True, db_comment="总股本 万股")
    float_share = models.FloatField("流通股本", blank=True, null=True, db_comment="流通股本 万股")
    pre_close = models.FloatField("昨收价", blank=True, null=True, db_comment="昨收价")
    up_limit = models.FloatField("涨停价", blank=True, null=True, db_comment="涨停价")
    down_limit = models.FloatField("跌停价", blank=True, null=True, db_comment="跌停价")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_stk_premarket"
        db_table_comment = "TuShare股本情况盘前"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date"], name="uniq_stk_premarket_ts_code_date"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "ts_code"]),
            models.Index(fields=["ts_code", "trade_date"]),
        ]


class StockSTList(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    name = models.CharField("股票名称", max_length=80, blank=True, null=True, db_comment="股票名称")
    trade_date = models.CharField("交易日期", max_length=8, db_comment="交易日期 YYYYMMDD")
    type = models.CharField(
        "风险类型", max_length=16, blank=True, null=True, db_index=True, db_comment="风险警示类型代码"
    )
    type_name = models.CharField("风险类型名称", max_length=80, blank=True, null=True, db_comment="风险警示类型名称")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_stock_st"
        db_table_comment = "TuShare ST股票列表"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date", "type"], name="uniq_stock_st_code_date_type"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "type"]),
            models.Index(fields=["ts_code", "trade_date"]),
        ]


class StockSTRiskNotice(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    name = models.CharField("股票名称", max_length=80, blank=True, null=True, db_comment="股票名称")
    pub_date = models.CharField("公告日期", max_length=8, db_comment="公告日期 YYYYMMDD")
    imp_date = models.CharField(
        "实施日期", max_length=8, blank=True, null=True, db_index=True, db_comment="实施日期 YYYYMMDD"
    )
    st_tpye = models.CharField("ST类型", max_length=40, blank=True, null=True, db_comment="TuShare接口字段名为st_tpye")
    st_reason = models.TextField("ST原因", blank=True, null=True, db_comment="风险警示原因")
    st_explain = models.TextField("ST说明", blank=True, null=True, db_comment="风险警示说明")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_st_risk_notice"
        db_table_comment = "TuShare ST风险警示板股票"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "pub_date", "st_tpye"], name="uniq_st_risk_code_pub_type"),
        ]
        indexes = [
            models.Index(fields=["pub_date", "ts_code"]),
            models.Index(fields=["ts_code", "imp_date"]),
        ]


class StockHsgt(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    trade_date = models.CharField("交易日期", max_length=8, db_comment="交易日期 YYYYMMDD")
    type = models.CharField("港股通类型", max_length=16, db_index=True, db_comment="沪深港通类型")
    name = models.CharField("股票名称", max_length=80, blank=True, null=True, db_comment="股票名称")
    type_name = models.CharField("港股通类型名称", max_length=80, blank=True, null=True, db_comment="沪深港通类型名称")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_stock_hsgt"
        db_table_comment = "TuShare沪深港通股票列表"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date", "type"], name="uniq_stock_hsgt_code_date_type"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "type"]),
            models.Index(fields=["ts_code", "trade_date"]),
        ]


class StockNameChange(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    name = models.CharField("证券名称", max_length=80, db_comment="证券名称")
    start_date = models.CharField(
        "开始日期", max_length=8, blank=True, null=True, db_index=True, db_comment="开始日期 YYYYMMDD"
    )
    end_date = models.CharField(
        "结束日期", max_length=8, blank=True, null=True, db_index=True, db_comment="结束日期 YYYYMMDD"
    )
    ann_date = models.CharField(
        "公告日期", max_length=8, blank=True, null=True, db_index=True, db_comment="公告日期 YYYYMMDD"
    )
    change_reason = models.CharField("变更原因", max_length=200, blank=True, null=True, db_comment="变更原因")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_stock_namechange"
        db_table_comment = "TuShare股票曾用名"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "name", "start_date"], name="uniq_namechange_code_name_start"),
        ]
        indexes = [
            models.Index(fields=["ts_code", "start_date"]),
            models.Index(fields=["ann_date", "ts_code"]),
        ]


class StockCompany(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, unique=True, db_comment="TuShare股票代码")
    com_name = models.CharField("公司全称", max_length=240, blank=True, null=True, db_index=True, db_comment="公司全称")
    com_id = models.CharField(
        "统一社会信用代码", max_length=64, blank=True, null=True, db_index=True, db_comment="统一社会信用代码"
    )
    exchange = models.CharField(
        "交易所代码", max_length=16, blank=True, null=True, db_index=True, db_comment="交易所代码"
    )
    chairman = models.CharField("法人代表", max_length=80, blank=True, null=True, db_comment="法人代表")
    manager = models.CharField("总经理", max_length=80, blank=True, null=True, db_comment="总经理")
    secretary = models.CharField("董秘", max_length=80, blank=True, null=True, db_comment="董事会秘书")
    reg_capital = models.FloatField("注册资本", blank=True, null=True, db_comment="注册资本 万元")
    setup_date = models.CharField(
        "注册日期", max_length=8, blank=True, null=True, db_index=True, db_comment="注册日期 YYYYMMDD"
    )
    province = models.CharField("所在省份", max_length=80, blank=True, null=True, db_comment="所在省份")
    city = models.CharField("所在城市", max_length=80, blank=True, null=True, db_comment="所在城市")
    introduction = models.TextField("公司介绍", blank=True, null=True, db_comment="公司介绍")
    website = models.CharField("公司主页", max_length=240, blank=True, null=True, db_comment="公司主页")
    email = models.CharField("电子邮件", max_length=160, blank=True, null=True, db_comment="电子邮件")
    office = models.CharField("办公室", max_length=300, blank=True, null=True, db_comment="办公室地址")
    employees = models.IntegerField("员工人数", blank=True, null=True, db_comment="员工人数")
    main_business = models.TextField("主要业务及产品", blank=True, null=True, db_comment="主要业务及产品")
    business_scope = models.TextField("经营范围", blank=True, null=True, db_comment="经营范围")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_stock_company"
        db_table_comment = "TuShare上市公司基本信息"
        indexes = [
            models.Index(fields=["exchange", "ts_code"]),
            models.Index(fields=["province", "city"]),
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
        db_table = "tushare_stock_daily"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date"], name="uniq_daily_ts_code_date"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "ts_code"]),
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
        db_table = "tushare_stock_daily_basic"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date"], name="uniq_daily_basic_ts_code_date"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "ts_code"]),
        ]


def tushare_char_field(verbose_name, max_length=80, **kwargs):
    kwargs.setdefault("blank", True)
    kwargs.setdefault("null", True)
    kwargs.setdefault("db_comment", verbose_name)
    return models.CharField(verbose_name, max_length=max_length, **kwargs)


def tushare_float_field(verbose_name, **kwargs):
    kwargs.setdefault("blank", True)
    kwargs.setdefault("null", True)
    kwargs.setdefault("db_comment", verbose_name)
    return models.FloatField(verbose_name, **kwargs)


class AdjFactor(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    trade_date = models.CharField("交易日期", max_length=8, db_comment="交易日期 YYYYMMDD")
    adj_factor = tushare_float_field("复权因子")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_adj_factor"
        db_table_comment = "TuShare复权因子"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date"], name="uniq_adj_factor_code_date"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "ts_code"], name="ix_adj_factor_date_code"),
            models.Index(fields=["ts_code", "trade_date"], name="ix_adj_factor_code_date"),
        ]


class FinancialIndicator(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    ann_date = tushare_char_field("公告日期", max_length=8, db_index=True)
    end_date = models.CharField("报告期", max_length=8, db_comment="报告期 YYYYMMDD")
    update_flag = tushare_char_field("更新标识", max_length=8)
    eps = tushare_float_field("基本每股收益", db_comment="基本每股收益")
    dt_eps = tushare_float_field("稀释每股收益", db_comment="稀释每股收益")
    total_revenue_ps = tushare_float_field("每股营业总收入", db_comment="每股营业总收入")
    revenue_ps = tushare_float_field("每股营业收入", db_comment="每股营业收入")
    capital_rese_ps = tushare_float_field("每股资本公积", db_comment="每股资本公积")
    surplus_rese_ps = tushare_float_field("每股盈余公积", db_comment="每股盈余公积")
    undist_profit_ps = tushare_float_field("每股未分配利润", db_comment="每股未分配利润")
    extra_item = tushare_float_field("非经常性损益", db_comment="非经常性损益")
    profit_dedt = tushare_float_field(
        "扣除非经常性损益后的净利润（扣非净利润）", db_comment="扣除非经常性损益后的净利润（扣非净利润）"
    )
    gross_margin = tushare_float_field("毛利", db_comment="毛利")
    current_ratio = tushare_float_field("流动比率", db_comment="流动比率")
    quick_ratio = tushare_float_field("速动比率", db_comment="速动比率")
    cash_ratio = tushare_float_field("保守速动比率", db_comment="保守速动比率")
    invturn_days = tushare_float_field("存货周转天数", db_comment="存货周转天数")
    arturn_days = tushare_float_field("应收账款周转天数", db_comment="应收账款周转天数")
    inv_turn = tushare_float_field("存货周转率", db_comment="存货周转率")
    ar_turn = tushare_float_field("应收账款周转率", db_comment="应收账款周转率")
    ca_turn = tushare_float_field("流动资产周转率", db_comment="流动资产周转率")
    fa_turn = tushare_float_field("固定资产周转率", db_comment="固定资产周转率")
    assets_turn = tushare_float_field("总资产周转率", db_comment="总资产周转率")
    op_income = tushare_float_field("经营活动净收益", db_comment="经营活动净收益")
    valuechange_income = tushare_float_field("价值变动净收益", db_comment="价值变动净收益")
    interst_income = tushare_float_field("利息费用", db_comment="利息费用")
    daa = tushare_float_field("折旧与摊销", db_comment="折旧与摊销")
    ebit = tushare_float_field("息税前利润", db_comment="息税前利润")
    ebitda = tushare_float_field("息税折旧摊销前利润", db_comment="息税折旧摊销前利润")
    fcff = tushare_float_field("企业自由现金流量", db_comment="企业自由现金流量")
    fcfe = tushare_float_field("股权自由现金流量", db_comment="股权自由现金流量")
    current_exint = tushare_float_field("无息流动负债", db_comment="无息流动负债")
    noncurrent_exint = tushare_float_field("无息非流动负债", db_comment="无息非流动负债")
    interestdebt = tushare_float_field("带息债务", db_comment="带息债务")
    netdebt = tushare_float_field("净债务", db_comment="净债务")
    tangible_asset = tushare_float_field("有形资产", db_comment="有形资产")
    working_capital = tushare_float_field("营运资金", db_comment="营运资金")
    networking_capital = tushare_float_field("营运流动资本", db_comment="营运流动资本")
    invest_capital = tushare_float_field("全部投入资本", db_comment="全部投入资本")
    retained_earnings = tushare_float_field("留存收益", db_comment="留存收益")
    diluted2_eps = tushare_float_field("期末摊薄每股收益", db_comment="期末摊薄每股收益")
    bps = tushare_float_field("每股净资产", db_comment="每股净资产")
    ocfps = tushare_float_field("每股经营活动产生的现金流量净额", db_comment="每股经营活动产生的现金流量净额")
    retainedps = tushare_float_field("每股留存收益", db_comment="每股留存收益")
    cfps = tushare_float_field("每股现金流量净额", db_comment="每股现金流量净额")
    ebit_ps = tushare_float_field("每股息税前利润", db_comment="每股息税前利润")
    fcff_ps = tushare_float_field("每股企业自由现金流量", db_comment="每股企业自由现金流量")
    fcfe_ps = tushare_float_field("每股股东自由现金流量", db_comment="每股股东自由现金流量")
    netprofit_margin = tushare_float_field("销售净利率", db_comment="销售净利率")
    grossprofit_margin = tushare_float_field("销售毛利率", db_comment="销售毛利率")
    cogs_of_sales = tushare_float_field("销售成本率", db_comment="销售成本率")
    expense_of_sales = tushare_float_field("销售期间费用率", db_comment="销售期间费用率")
    profit_to_gr = tushare_float_field("净利润/营业总收入", db_comment="净利润/营业总收入")
    saleexp_to_gr = tushare_float_field("销售费用/营业总收入", db_comment="销售费用/营业总收入")
    adminexp_of_gr = tushare_float_field("管理费用/营业总收入", db_comment="管理费用/营业总收入")
    finaexp_of_gr = tushare_float_field("财务费用/营业总收入", db_comment="财务费用/营业总收入")
    impai_ttm = tushare_float_field("资产减值损失/营业总收入", db_comment="资产减值损失/营业总收入")
    gc_of_gr = tushare_float_field("营业总成本/营业总收入", db_comment="营业总成本/营业总收入")
    op_of_gr = tushare_float_field("营业利润/营业总收入", db_comment="营业利润/营业总收入")
    ebit_of_gr = tushare_float_field("息税前利润/营业总收入", db_comment="息税前利润/营业总收入")
    roe = tushare_float_field("净资产收益率", db_comment="净资产收益率")
    roe_waa = tushare_float_field("加权平均净资产收益率", db_comment="加权平均净资产收益率")
    roe_dt = tushare_float_field("净资产收益率(扣除非经常损益)", db_comment="净资产收益率(扣除非经常损益)")
    roa = tushare_float_field("总资产报酬率", db_comment="总资产报酬率")
    npta = tushare_float_field("总资产净利润", db_comment="总资产净利润")
    roic = tushare_float_field("投入资本回报率", db_comment="投入资本回报率")
    roe_yearly = tushare_float_field("年化净资产收益率", db_comment="年化净资产收益率")
    roa2_yearly = tushare_float_field("年化总资产报酬率", db_comment="年化总资产报酬率")
    roe_avg = tushare_float_field("平均净资产收益率(增发条件)", db_comment="平均净资产收益率(增发条件)")
    opincome_of_ebt = tushare_float_field("经营活动净收益/利润总额", db_comment="经营活动净收益/利润总额")
    investincome_of_ebt = tushare_float_field("价值变动净收益/利润总额", db_comment="价值变动净收益/利润总额")
    n_op_profit_of_ebt = tushare_float_field("营业外收支净额/利润总额", db_comment="营业外收支净额/利润总额")
    tax_to_ebt = tushare_float_field("所得税/利润总额", db_comment="所得税/利润总额")
    dtprofit_to_profit = tushare_float_field(
        "扣除非经常损益后的净利润/净利润", db_comment="扣除非经常损益后的净利润/净利润"
    )
    salescash_to_or = tushare_float_field(
        "销售商品提供劳务收到的现金/营业收入", db_comment="销售商品提供劳务收到的现金/营业收入"
    )
    ocf_to_or = tushare_float_field(
        "经营活动产生的现金流量净额/营业收入", db_comment="经营活动产生的现金流量净额/营业收入"
    )
    ocf_to_opincome = tushare_float_field(
        "经营活动产生的现金流量净额/经营活动净收益", db_comment="经营活动产生的现金流量净额/经营活动净收益"
    )
    capitalized_to_da = tushare_float_field("资本支出/折旧和摊销", db_comment="资本支出/折旧和摊销")
    debt_to_assets = tushare_float_field("资产负债率", db_comment="资产负债率")
    assets_to_eqt = tushare_float_field("权益乘数", db_comment="权益乘数")
    dp_assets_to_eqt = tushare_float_field("权益乘数(杜邦分析)", db_comment="权益乘数(杜邦分析)")
    ca_to_assets = tushare_float_field("流动资产/总资产", db_comment="流动资产/总资产")
    nca_to_assets = tushare_float_field("非流动资产/总资产", db_comment="非流动资产/总资产")
    tbassets_to_totalassets = tushare_float_field("有形资产/总资产", db_comment="有形资产/总资产")
    int_to_talcap = tushare_float_field("带息债务/全部投入资本", db_comment="带息债务/全部投入资本")
    eqt_to_talcapital = tushare_float_field(
        "归属于母公司的股东权益/全部投入资本", db_comment="归属于母公司的股东权益/全部投入资本"
    )
    currentdebt_to_debt = tushare_float_field("流动负债/负债合计", db_comment="流动负债/负债合计")
    longdeb_to_debt = tushare_float_field("非流动负债/负债合计", db_comment="非流动负债/负债合计")
    ocf_to_shortdebt = tushare_float_field(
        "经营活动产生的现金流量净额/流动负债", db_comment="经营活动产生的现金流量净额/流动负债"
    )
    debt_to_eqt = tushare_float_field("产权比率", db_comment="产权比率")
    eqt_to_debt = tushare_float_field("归属于母公司的股东权益/负债合计", db_comment="归属于母公司的股东权益/负债合计")
    eqt_to_interestdebt = tushare_float_field(
        "归属于母公司的股东权益/带息债务", db_comment="归属于母公司的股东权益/带息债务"
    )
    tangibleasset_to_debt = tushare_float_field("有形资产/负债合计", db_comment="有形资产/负债合计")
    tangasset_to_intdebt = tushare_float_field("有形资产/带息债务", db_comment="有形资产/带息债务")
    tangibleasset_to_netdebt = tushare_float_field("有形资产/净债务", db_comment="有形资产/净债务")
    ocf_to_debt = tushare_float_field(
        "经营活动产生的现金流量净额/负债合计", db_comment="经营活动产生的现金流量净额/负债合计"
    )
    turn_days = tushare_float_field("营业周期", db_comment="营业周期")
    roa_yearly = tushare_float_field("年化总资产净利率", db_comment="年化总资产净利率")
    roa_dp = tushare_float_field("总资产净利率(杜邦分析)", db_comment="总资产净利率(杜邦分析)")
    fixed_assets = tushare_float_field("固定资产合计", db_comment="固定资产合计")
    profit_prefin_exp = tushare_float_field("扣除财务费用前营业利润", db_comment="扣除财务费用前营业利润")
    non_op_profit = tushare_float_field("非营业利润", db_comment="非营业利润")
    op_to_ebt = tushare_float_field("营业利润／利润总额", db_comment="营业利润／利润总额")
    nop_to_ebt = tushare_float_field("非营业利润／利润总额", db_comment="非营业利润／利润总额")
    ocf_to_profit = tushare_float_field(
        "经营活动产生的现金流量净额／营业利润", db_comment="经营活动产生的现金流量净额／营业利润"
    )
    cash_to_liqdebt = tushare_float_field("货币资金／流动负债", db_comment="货币资金／流动负债")
    cash_to_liqdebt_withinterest = tushare_float_field("货币资金／带息流动负债", db_comment="货币资金／带息流动负债")
    op_to_liqdebt = tushare_float_field("营业利润／流动负债", db_comment="营业利润／流动负债")
    op_to_debt = tushare_float_field("营业利润／负债合计", db_comment="营业利润／负债合计")
    roic_yearly = tushare_float_field("年化投入资本回报率", db_comment="年化投入资本回报率")
    total_fa_trun = tushare_float_field("固定资产合计周转率", db_comment="固定资产合计周转率")
    profit_to_op = tushare_float_field("利润总额／营业收入", db_comment="利润总额／营业收入")
    q_opincome = tushare_float_field("经营活动单季度净收益", db_comment="经营活动单季度净收益")
    q_investincome = tushare_float_field("价值变动单季度净收益", db_comment="价值变动单季度净收益")
    q_dtprofit = tushare_float_field("扣除非经常损益后的单季度净利润", db_comment="扣除非经常损益后的单季度净利润")
    q_eps = tushare_float_field("每股收益(单季度)", db_comment="每股收益(单季度)")
    q_netprofit_margin = tushare_float_field("销售净利率(单季度)", db_comment="销售净利率(单季度)")
    q_gsprofit_margin = tushare_float_field("销售毛利率(单季度)", db_comment="销售毛利率(单季度)")
    q_exp_to_sales = tushare_float_field("销售期间费用率(单季度)", db_comment="销售期间费用率(单季度)")
    q_profit_to_gr = tushare_float_field("净利润／营业总收入(单季度)", db_comment="净利润／营业总收入(单季度)")
    q_saleexp_to_gr = tushare_float_field("销售费用／营业总收入 (单季度)", db_comment="销售费用／营业总收入 (单季度)")
    q_adminexp_to_gr = tushare_float_field("管理费用／营业总收入 (单季度)", db_comment="管理费用／营业总收入 (单季度)")
    q_finaexp_to_gr = tushare_float_field("财务费用／营业总收入 (单季度)", db_comment="财务费用／营业总收入 (单季度)")
    q_impair_to_gr_ttm = tushare_float_field(
        "资产减值损失／营业总收入(单季度)", db_comment="资产减值损失／营业总收入(单季度)"
    )
    q_gc_to_gr = tushare_float_field("营业总成本／营业总收入 (单季度)", db_comment="营业总成本／营业总收入 (单季度)")
    q_op_to_gr = tushare_float_field("营业利润／营业总收入(单季度)", db_comment="营业利润／营业总收入(单季度)")
    q_roe = tushare_float_field("净资产收益率(单季度)", db_comment="净资产收益率(单季度)")
    q_dt_roe = tushare_float_field(
        "净资产单季度收益率(扣除非经常损益)", db_comment="净资产单季度收益率(扣除非经常损益)"
    )
    q_npta = tushare_float_field("总资产净利润(单季度)", db_comment="总资产净利润(单季度)")
    q_opincome_to_ebt = tushare_float_field(
        "经营活动净收益／利润总额(单季度)", db_comment="经营活动净收益／利润总额(单季度)"
    )
    q_investincome_to_ebt = tushare_float_field(
        "价值变动净收益／利润总额(单季度)", db_comment="价值变动净收益／利润总额(单季度)"
    )
    q_dtprofit_to_profit = tushare_float_field(
        "扣除非经常损益后的净利润／净利润(单季度)", db_comment="扣除非经常损益后的净利润／净利润(单季度)"
    )
    q_salescash_to_or = tushare_float_field(
        "销售商品提供劳务收到的现金／营业收入(单季度)", db_comment="销售商品提供劳务收到的现金／营业收入(单季度)"
    )
    q_ocf_to_sales = tushare_float_field(
        "经营活动产生的现金流量净额／营业收入(单季度)", db_comment="经营活动产生的现金流量净额／营业收入(单季度)"
    )
    q_ocf_to_or = tushare_float_field(
        "经营活动产生的现金流量净额／经营活动净收益(单季度)",
        db_comment="经营活动产生的现金流量净额／经营活动净收益(单季度)",
    )
    basic_eps_yoy = tushare_float_field("基本每股收益同比增长率(%)", db_comment="基本每股收益同比增长率(%)")
    dt_eps_yoy = tushare_float_field("稀释每股收益同比增长率(%)", db_comment="稀释每股收益同比增长率(%)")
    cfps_yoy = tushare_float_field(
        "每股经营活动产生的现金流量净额同比增长率(%)", db_comment="每股经营活动产生的现金流量净额同比增长率(%)"
    )
    op_yoy = tushare_float_field("营业利润同比增长率(%)", db_comment="营业利润同比增长率(%)")
    ebt_yoy = tushare_float_field("利润总额同比增长率(%)", db_comment="利润总额同比增长率(%)")
    netprofit_yoy = tushare_float_field(
        "归属母公司股东的净利润同比增长率(%)", db_comment="归属母公司股东的净利润同比增长率(%)"
    )
    dt_netprofit_yoy = tushare_float_field(
        "归属母公司股东的净利润-扣除非经常损益同比增长率(%)",
        db_comment="归属母公司股东的净利润-扣除非经常损益同比增长率(%)",
    )
    ocf_yoy = tushare_float_field(
        "经营活动产生的现金流量净额同比增长率(%)", db_comment="经营活动产生的现金流量净额同比增长率(%)"
    )
    roe_yoy = tushare_float_field("净资产收益率(摊薄)同比增长率(%)", db_comment="净资产收益率(摊薄)同比增长率(%)")
    bps_yoy = tushare_float_field("每股净资产相对年初增长率(%)", db_comment="每股净资产相对年初增长率(%)")
    assets_yoy = tushare_float_field("资产总计相对年初增长率(%)", db_comment="资产总计相对年初增长率(%)")
    eqt_yoy = tushare_float_field(
        "归属母公司的股东权益相对年初增长率(%)", db_comment="归属母公司的股东权益相对年初增长率(%)"
    )
    tr_yoy = tushare_float_field("营业总收入同比增长率(%)", db_comment="营业总收入同比增长率(%)")
    or_yoy = tushare_float_field("营业收入同比增长率(%)", db_comment="营业收入同比增长率(%)")
    q_gr_yoy = tushare_float_field("营业总收入同比增长率(%)(单季度)", db_comment="营业总收入同比增长率(%)(单季度)")
    q_gr_qoq = tushare_float_field("营业总收入环比增长率(%)(单季度)", db_comment="营业总收入环比增长率(%)(单季度)")
    q_sales_yoy = tushare_float_field("营业收入同比增长率(%)(单季度)", db_comment="营业收入同比增长率(%)(单季度)")
    q_sales_qoq = tushare_float_field("营业收入环比增长率(%)(单季度)", db_comment="营业收入环比增长率(%)(单季度)")
    q_op_yoy = tushare_float_field("营业利润同比增长率(%)(单季度)", db_comment="营业利润同比增长率(%)(单季度)")
    q_op_qoq = tushare_float_field("营业利润环比增长率(%)(单季度)", db_comment="营业利润环比增长率(%)(单季度)")
    q_profit_yoy = tushare_float_field("净利润同比增长率(%)(单季度)", db_comment="净利润同比增长率(%)(单季度)")
    q_profit_qoq = tushare_float_field("净利润环比增长率(%)(单季度)", db_comment="净利润环比增长率(%)(单季度)")
    q_netprofit_yoy = tushare_float_field(
        "归属母公司股东的净利润同比增长率(%)(单季度)", db_comment="归属母公司股东的净利润同比增长率(%)(单季度)"
    )
    q_netprofit_qoq = tushare_float_field(
        "归属母公司股东的净利润环比增长率(%)(单季度)", db_comment="归属母公司股东的净利润环比增长率(%)(单季度)"
    )
    equity_yoy = tushare_float_field("净资产同比增长率", db_comment="净资产同比增长率")
    rd_exp = tushare_float_field("研发费用", db_comment="研发费用")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_fina_indicator"
        db_table_comment = "TuShare财务指标数据"
        constraints = [
            models.UniqueConstraint(
                fields=["ts_code", "ann_date", "end_date"], name="uniq_fina_indicator_code_ann_end"
            ),
        ]
        indexes = [
            models.Index(fields=["ts_code", "end_date"], name="ix_fina_ind_code_end"),
            models.Index(fields=["ann_date", "ts_code"], name="ix_fina_ind_ann_code"),
        ]


class IncomeStatement(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    ann_date = tushare_char_field("公告日期", max_length=8, db_index=True)
    f_ann_date = tushare_char_field("实际公告日期", max_length=8)
    end_date = models.CharField("报告期", max_length=8, db_comment="报告期 YYYYMMDD")
    report_type = tushare_char_field("报告类型", max_length=16)
    comp_type = tushare_char_field("公司类型", max_length=16)
    end_type = tushare_char_field("报告期类型", max_length=16)
    update_flag = tushare_char_field("更新标识", max_length=8)
    basic_eps = tushare_float_field("基本每股收益", db_comment="基本每股收益")
    diluted_eps = tushare_float_field("稀释每股收益", db_comment="稀释每股收益")
    total_revenue = tushare_float_field("营业总收入", db_comment="营业总收入")
    revenue = tushare_float_field("营业收入", db_comment="营业收入")
    int_income = tushare_float_field("利息收入", db_comment="利息收入")
    prem_earned = tushare_float_field("已赚保费", db_comment="已赚保费")
    comm_income = tushare_float_field("手续费及佣金收入", db_comment="手续费及佣金收入")
    n_commis_income = tushare_float_field("手续费及佣金净收入", db_comment="手续费及佣金净收入")
    n_oth_income = tushare_float_field("其他经营净收益", db_comment="其他经营净收益")
    n_oth_b_income = tushare_float_field("加:其他业务净收益", db_comment="加:其他业务净收益")
    prem_income = tushare_float_field("保险业务收入", db_comment="保险业务收入")
    out_prem = tushare_float_field("减:分出保费", db_comment="减:分出保费")
    une_prem_reser = tushare_float_field("提取未到期责任准备金", db_comment="提取未到期责任准备金")
    reins_income = tushare_float_field("其中:分保费收入", db_comment="其中:分保费收入")
    n_sec_tb_income = tushare_float_field("代理买卖证券业务净收入", db_comment="代理买卖证券业务净收入")
    n_sec_uw_income = tushare_float_field("证券承销业务净收入", db_comment="证券承销业务净收入")
    n_asset_mg_income = tushare_float_field("受托客户资产管理业务净收入", db_comment="受托客户资产管理业务净收入")
    oth_b_income = tushare_float_field("其他业务收入", db_comment="其他业务收入")
    fv_value_chg_gain = tushare_float_field("加:公允价值变动净收益", db_comment="加:公允价值变动净收益")
    invest_income = tushare_float_field("加:投资净收益", db_comment="加:投资净收益")
    ass_invest_income = tushare_float_field(
        "其中:对联营企业和合营企业的投资收益", db_comment="其中:对联营企业和合营企业的投资收益"
    )
    forex_gain = tushare_float_field("加:汇兑净收益", db_comment="加:汇兑净收益")
    total_cogs = tushare_float_field("营业总成本", db_comment="营业总成本")
    oper_cost = tushare_float_field("减:营业成本", db_comment="减:营业成本")
    int_exp = tushare_float_field("减:利息支出", db_comment="减:利息支出")
    comm_exp = tushare_float_field("减:手续费及佣金支出", db_comment="减:手续费及佣金支出")
    biz_tax_surchg = tushare_float_field("减:营业税金及附加", db_comment="减:营业税金及附加")
    sell_exp = tushare_float_field("减:销售费用", db_comment="减:销售费用")
    admin_exp = tushare_float_field("减:管理费用", db_comment="减:管理费用")
    fin_exp = tushare_float_field("减:财务费用", db_comment="减:财务费用")
    assets_impair_loss = tushare_float_field("减:资产减值损失", db_comment="减:资产减值损失")
    prem_refund = tushare_float_field("退保金", db_comment="退保金")
    compens_payout = tushare_float_field("赔付总支出", db_comment="赔付总支出")
    reser_insur_liab = tushare_float_field("提取保险责任准备金", db_comment="提取保险责任准备金")
    div_payt = tushare_float_field("保户红利支出", db_comment="保户红利支出")
    reins_exp = tushare_float_field("分保费用", db_comment="分保费用")
    oper_exp = tushare_float_field("营业支出", db_comment="营业支出")
    compens_payout_refu = tushare_float_field("减:摊回赔付支出", db_comment="减:摊回赔付支出")
    insur_reser_refu = tushare_float_field("减:摊回保险责任准备金", db_comment="减:摊回保险责任准备金")
    reins_cost_refund = tushare_float_field("减:摊回分保费用", db_comment="减:摊回分保费用")
    other_bus_cost = tushare_float_field("其他业务成本", db_comment="其他业务成本")
    operate_profit = tushare_float_field("营业利润", db_comment="营业利润")
    non_oper_income = tushare_float_field("加:营业外收入", db_comment="加:营业外收入")
    non_oper_exp = tushare_float_field("减:营业外支出", db_comment="减:营业外支出")
    nca_disploss = tushare_float_field("其中:减:非流动资产处置净损失", db_comment="其中:减:非流动资产处置净损失")
    total_profit = tushare_float_field("利润总额", db_comment="利润总额")
    income_tax = tushare_float_field("所得税费用", db_comment="所得税费用")
    n_income = tushare_float_field("净利润(含少数股东损益)", db_comment="净利润(含少数股东损益)")
    n_income_attr_p = tushare_float_field("净利润(不含少数股东损益)", db_comment="净利润(不含少数股东损益)")
    minority_gain = tushare_float_field("少数股东损益", db_comment="少数股东损益")
    oth_compr_income = tushare_float_field("其他综合收益", db_comment="其他综合收益")
    t_compr_income = tushare_float_field("综合收益总额", db_comment="综合收益总额")
    compr_inc_attr_p = tushare_float_field(
        "归属于母公司(或股东)的综合收益总额", db_comment="归属于母公司(或股东)的综合收益总额"
    )
    compr_inc_attr_m_s = tushare_float_field("归属于少数股东的综合收益总额", db_comment="归属于少数股东的综合收益总额")
    ebit = tushare_float_field("息税前利润", db_comment="息税前利润")
    ebitda = tushare_float_field("息税折旧摊销前利润", db_comment="息税折旧摊销前利润")
    insurance_exp = tushare_float_field("保险业务支出", db_comment="保险业务支出")
    undist_profit = tushare_float_field("年初未分配利润", db_comment="年初未分配利润")
    distable_profit = tushare_float_field("可分配利润", db_comment="可分配利润")
    rd_exp = tushare_float_field("研发费用", db_comment="研发费用")
    fin_exp_int_exp = tushare_float_field("财务费用:利息费用", db_comment="财务费用:利息费用")
    fin_exp_int_inc = tushare_float_field("财务费用:利息收入", db_comment="财务费用:利息收入")
    transfer_surplus_rese = tushare_float_field("盈余公积转入", db_comment="盈余公积转入")
    transfer_housing_imprest = tushare_float_field("住房周转金转入", db_comment="住房周转金转入")
    transfer_oth = tushare_float_field("其他转入", db_comment="其他转入")
    adj_lossgain = tushare_float_field("调整以前年度损益", db_comment="调整以前年度损益")
    withdra_legal_surplus = tushare_float_field("提取法定盈余公积", db_comment="提取法定盈余公积")
    withdra_legal_pubfund = tushare_float_field("提取法定公益金", db_comment="提取法定公益金")
    withdra_biz_devfund = tushare_float_field("提取企业发展基金", db_comment="提取企业发展基金")
    withdra_rese_fund = tushare_float_field("提取储备基金", db_comment="提取储备基金")
    withdra_oth_ersu = tushare_float_field("提取任意盈余公积金", db_comment="提取任意盈余公积金")
    workers_welfare = tushare_float_field("职工奖金福利", db_comment="职工奖金福利")
    distr_profit_shrhder = tushare_float_field("可供股东分配的利润", db_comment="可供股东分配的利润")
    prfshare_payable_dvd = tushare_float_field("应付优先股股利", db_comment="应付优先股股利")
    comshare_payable_dvd = tushare_float_field("应付普通股股利", db_comment="应付普通股股利")
    capit_comstock_div = tushare_float_field("转作股本的普通股股利", db_comment="转作股本的普通股股利")
    net_after_nr_lp_correct = tushare_float_field(
        "扣除非经常性损益后的净利润（更正前）", db_comment="扣除非经常性损益后的净利润（更正前）"
    )
    credit_impa_loss = tushare_float_field("信用减值损失", db_comment="信用减值损失")
    net_expo_hedging_benefits = tushare_float_field("净敞口套期收益", db_comment="净敞口套期收益")
    oth_impair_loss_assets = tushare_float_field("其他资产减值损失", db_comment="其他资产减值损失")
    total_opcost = tushare_float_field("营业总成本（二）", db_comment="营业总成本（二）")
    amodcost_fin_assets = tushare_float_field(
        "以摊余成本计量的金融资产终止确认收益", db_comment="以摊余成本计量的金融资产终止确认收益"
    )
    oth_income = tushare_float_field("其他收益", db_comment="其他收益")
    asset_disp_income = tushare_float_field("资产处置收益", db_comment="资产处置收益")
    continued_net_profit = tushare_float_field("持续经营净利润", db_comment="持续经营净利润")
    end_net_profit = tushare_float_field("终止经营净利润", db_comment="终止经营净利润")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_income"
        db_table_comment = "TuShare利润表"
        constraints = [
            models.UniqueConstraint(
                fields=["ts_code", "ann_date", "end_date", "report_type"], name="uniq_income_code_ann_end_type"
            ),
        ]
        indexes = [
            models.Index(fields=["ts_code", "end_date"], name="ix_income_code_end"),
            models.Index(fields=["ann_date", "ts_code"], name="ix_income_ann_code"),
        ]


class BalanceSheet(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    ann_date = tushare_char_field("公告日期", max_length=8, db_index=True)
    f_ann_date = tushare_char_field("实际公告日期", max_length=8)
    end_date = models.CharField("报告期", max_length=8, db_comment="报告期 YYYYMMDD")
    report_type = tushare_char_field("报告类型", max_length=16)
    comp_type = tushare_char_field("公司类型", max_length=16)
    end_type = tushare_char_field("报告期类型", max_length=16)
    update_flag = tushare_char_field("更新标识", max_length=8)
    total_share = tushare_float_field("期末总股本", db_comment="期末总股本")
    cap_rese = tushare_float_field("资本公积金", db_comment="资本公积金")
    undistr_porfit = tushare_float_field("未分配利润", db_comment="未分配利润")
    surplus_rese = tushare_float_field("盈余公积金", db_comment="盈余公积金")
    special_rese = tushare_float_field("专项储备", db_comment="专项储备")
    money_cap = tushare_float_field("货币资金", db_comment="货币资金")
    trad_asset = tushare_float_field("交易性金融资产", db_comment="交易性金融资产")
    notes_receiv = tushare_float_field("应收票据", db_comment="应收票据")
    accounts_receiv = tushare_float_field("应收账款", db_comment="应收账款")
    oth_receiv = tushare_float_field("其他应收款", db_comment="其他应收款")
    prepayment = tushare_float_field("预付款项", db_comment="预付款项")
    div_receiv = tushare_float_field("应收股利", db_comment="应收股利")
    int_receiv = tushare_float_field("应收利息", db_comment="应收利息")
    inventories = tushare_float_field("存货", db_comment="存货")
    amor_exp = tushare_float_field("待摊费用", db_comment="待摊费用")
    nca_within_1y = tushare_float_field("一年内到期的非流动资产", db_comment="一年内到期的非流动资产")
    sett_rsrv = tushare_float_field("结算备付金", db_comment="结算备付金")
    loanto_oth_bank_fi = tushare_float_field("拆出资金", db_comment="拆出资金")
    premium_receiv = tushare_float_field("应收保费", db_comment="应收保费")
    reinsur_receiv = tushare_float_field("应收分保账款", db_comment="应收分保账款")
    reinsur_res_receiv = tushare_float_field("应收分保合同准备金", db_comment="应收分保合同准备金")
    pur_resale_fa = tushare_float_field("买入返售金融资产", db_comment="买入返售金融资产")
    oth_cur_assets = tushare_float_field("其他流动资产", db_comment="其他流动资产")
    total_cur_assets = tushare_float_field("流动资产合计", db_comment="流动资产合计")
    fa_avail_for_sale = tushare_float_field("可供出售金融资产", db_comment="可供出售金融资产")
    htm_invest = tushare_float_field("持有至到期投资", db_comment="持有至到期投资")
    lt_eqt_invest = tushare_float_field("长期股权投资", db_comment="长期股权投资")
    invest_real_estate = tushare_float_field("投资性房地产", db_comment="投资性房地产")
    time_deposits = tushare_float_field("定期存款", db_comment="定期存款")
    oth_assets = tushare_float_field("其他资产", db_comment="其他资产")
    lt_rec = tushare_float_field("长期应收款", db_comment="长期应收款")
    fix_assets = tushare_float_field("固定资产", db_comment="固定资产")
    cip = tushare_float_field("在建工程", db_comment="在建工程")
    const_materials = tushare_float_field("工程物资", db_comment="工程物资")
    fixed_assets_disp = tushare_float_field("固定资产清理", db_comment="固定资产清理")
    produc_bio_assets = tushare_float_field("生产性生物资产", db_comment="生产性生物资产")
    oil_and_gas_assets = tushare_float_field("油气资产", db_comment="油气资产")
    intan_assets = tushare_float_field("无形资产", db_comment="无形资产")
    r_and_d = tushare_float_field("研发支出", db_comment="研发支出")
    goodwill = tushare_float_field("商誉", db_comment="商誉")
    lt_amor_exp = tushare_float_field("长期待摊费用", db_comment="长期待摊费用")
    defer_tax_assets = tushare_float_field("递延所得税资产", db_comment="递延所得税资产")
    decr_in_disbur = tushare_float_field("发放贷款及垫款", db_comment="发放贷款及垫款")
    oth_nca = tushare_float_field("其他非流动资产", db_comment="其他非流动资产")
    total_nca = tushare_float_field("非流动资产合计", db_comment="非流动资产合计")
    cash_reser_cb = tushare_float_field("现金及存放中央银行款项", db_comment="现金及存放中央银行款项")
    depos_in_oth_bfi = tushare_float_field("存放同业和其它金融机构款项", db_comment="存放同业和其它金融机构款项")
    prec_metals = tushare_float_field("贵金属", db_comment="贵金属")
    deriv_assets = tushare_float_field("衍生金融资产", db_comment="衍生金融资产")
    rr_reins_une_prem = tushare_float_field("应收分保未到期责任准备金", db_comment="应收分保未到期责任准备金")
    rr_reins_outstd_cla = tushare_float_field("应收分保未决赔款准备金", db_comment="应收分保未决赔款准备金")
    rr_reins_lins_liab = tushare_float_field("应收分保寿险责任准备金", db_comment="应收分保寿险责任准备金")
    rr_reins_lthins_liab = tushare_float_field(
        "应收分保长期健康险责任准备金", db_comment="应收分保长期健康险责任准备金"
    )
    refund_depos = tushare_float_field("存出保证金", db_comment="存出保证金")
    ph_pledge_loans = tushare_float_field("保户质押贷款", db_comment="保户质押贷款")
    refund_cap_depos = tushare_float_field("存出资本保证金", db_comment="存出资本保证金")
    indep_acct_assets = tushare_float_field("独立账户资产", db_comment="独立账户资产")
    client_depos = tushare_float_field("其中：客户资金存款", db_comment="其中：客户资金存款")
    client_prov = tushare_float_field("其中：客户备付金", db_comment="其中：客户备付金")
    transac_seat_fee = tushare_float_field("其中:交易席位费", db_comment="其中:交易席位费")
    invest_as_receiv = tushare_float_field("应收款项类投资", db_comment="应收款项类投资")
    total_assets = tushare_float_field("资产总计", db_comment="资产总计")
    lt_borr = tushare_float_field("长期借款", db_comment="长期借款")
    st_borr = tushare_float_field("短期借款", db_comment="短期借款")
    cb_borr = tushare_float_field("向中央银行借款", db_comment="向中央银行借款")
    depos_ib_deposits = tushare_float_field("吸收存款及同业存放", db_comment="吸收存款及同业存放")
    loan_oth_bank = tushare_float_field("拆入资金", db_comment="拆入资金")
    trading_fl = tushare_float_field("交易性金融负债", db_comment="交易性金融负债")
    notes_payable = tushare_float_field("应付票据", db_comment="应付票据")
    acct_payable = tushare_float_field("应付账款", db_comment="应付账款")
    adv_receipts = tushare_float_field("预收款项", db_comment="预收款项")
    sold_for_repur_fa = tushare_float_field("卖出回购金融资产款", db_comment="卖出回购金融资产款")
    comm_payable = tushare_float_field("应付手续费及佣金", db_comment="应付手续费及佣金")
    payroll_payable = tushare_float_field("应付职工薪酬", db_comment="应付职工薪酬")
    taxes_payable = tushare_float_field("应交税费", db_comment="应交税费")
    int_payable = tushare_float_field("应付利息", db_comment="应付利息")
    div_payable = tushare_float_field("应付股利", db_comment="应付股利")
    oth_payable = tushare_float_field("其他应付款", db_comment="其他应付款")
    acc_exp = tushare_float_field("预提费用", db_comment="预提费用")
    deferred_inc = tushare_float_field("递延收益", db_comment="递延收益")
    st_bonds_payable = tushare_float_field("应付短期债券", db_comment="应付短期债券")
    payable_to_reinsurer = tushare_float_field("应付分保账款", db_comment="应付分保账款")
    rsrv_insur_cont = tushare_float_field("保险合同准备金", db_comment="保险合同准备金")
    acting_trading_sec = tushare_float_field("代理买卖证券款", db_comment="代理买卖证券款")
    acting_uw_sec = tushare_float_field("代理承销证券款", db_comment="代理承销证券款")
    non_cur_liab_due_1y = tushare_float_field("一年内到期的非流动负债", db_comment="一年内到期的非流动负债")
    oth_cur_liab = tushare_float_field("其他流动负债", db_comment="其他流动负债")
    total_cur_liab = tushare_float_field("流动负债合计", db_comment="流动负债合计")
    bond_payable = tushare_float_field("应付债券", db_comment="应付债券")
    lt_payable = tushare_float_field("长期应付款", db_comment="长期应付款")
    specific_payables = tushare_float_field("专项应付款", db_comment="专项应付款")
    estimated_liab = tushare_float_field("预计负债", db_comment="预计负债")
    defer_tax_liab = tushare_float_field("递延所得税负债", db_comment="递延所得税负债")
    defer_inc_non_cur_liab = tushare_float_field("递延收益-非流动负债", db_comment="递延收益-非流动负债")
    oth_ncl = tushare_float_field("其他非流动负债", db_comment="其他非流动负债")
    total_ncl = tushare_float_field("非流动负债合计", db_comment="非流动负债合计")
    depos_oth_bfi = tushare_float_field("同业和其它金融机构存放款项", db_comment="同业和其它金融机构存放款项")
    deriv_liab = tushare_float_field("衍生金融负债", db_comment="衍生金融负债")
    depos = tushare_float_field("吸收存款", db_comment="吸收存款")
    agency_bus_liab = tushare_float_field("代理业务负债", db_comment="代理业务负债")
    oth_liab = tushare_float_field("其他负债", db_comment="其他负债")
    prem_receiv_adva = tushare_float_field("预收保费", db_comment="预收保费")
    depos_received = tushare_float_field("存入保证金", db_comment="存入保证金")
    ph_invest = tushare_float_field("保户储金及投资款", db_comment="保户储金及投资款")
    reser_une_prem = tushare_float_field("未到期责任准备金", db_comment="未到期责任准备金")
    reser_outstd_claims = tushare_float_field("未决赔款准备金", db_comment="未决赔款准备金")
    reser_lins_liab = tushare_float_field("寿险责任准备金", db_comment="寿险责任准备金")
    reser_lthins_liab = tushare_float_field("长期健康险责任准备金", db_comment="长期健康险责任准备金")
    indept_acc_liab = tushare_float_field("独立账户负债", db_comment="独立账户负债")
    pledge_borr = tushare_float_field("其中:质押借款", db_comment="其中:质押借款")
    indem_payable = tushare_float_field("应付赔付款", db_comment="应付赔付款")
    policy_div_payable = tushare_float_field("应付保单红利", db_comment="应付保单红利")
    total_liab = tushare_float_field("负债合计", db_comment="负债合计")
    treasury_share = tushare_float_field("减:库存股", db_comment="减:库存股")
    ordin_risk_reser = tushare_float_field("一般风险准备", db_comment="一般风险准备")
    forex_differ = tushare_float_field("外币报表折算差额", db_comment="外币报表折算差额")
    invest_loss_unconf = tushare_float_field("未确认的投资损失", db_comment="未确认的投资损失")
    minority_int = tushare_float_field("少数股东权益", db_comment="少数股东权益")
    total_hldr_eqy_exc_min_int = tushare_float_field(
        "股东权益合计(不含少数股东权益)", db_comment="股东权益合计(不含少数股东权益)"
    )
    total_hldr_eqy_inc_min_int = tushare_float_field(
        "股东权益合计(含少数股东权益)", db_comment="股东权益合计(含少数股东权益)"
    )
    total_liab_hldr_eqy = tushare_float_field("负债及股东权益总计", db_comment="负债及股东权益总计")
    lt_payroll_payable = tushare_float_field("长期应付职工薪酬", db_comment="长期应付职工薪酬")
    oth_comp_income = tushare_float_field("其他综合收益", db_comment="其他综合收益")
    oth_eqt_tools = tushare_float_field("其他权益工具", db_comment="其他权益工具")
    oth_eqt_tools_p_shr = tushare_float_field("其他权益工具(优先股)", db_comment="其他权益工具(优先股)")
    lending_funds = tushare_float_field("融出资金", db_comment="融出资金")
    acc_receivable = tushare_float_field("应收款项", db_comment="应收款项")
    st_fin_payable = tushare_float_field("应付短期融资款", db_comment="应付短期融资款")
    payables = tushare_float_field("应付款项", db_comment="应付款项")
    hfs_assets = tushare_float_field("持有待售的资产", db_comment="持有待售的资产")
    hfs_sales = tushare_float_field("持有待售的负债", db_comment="持有待售的负债")
    cost_fin_assets = tushare_float_field("以摊余成本计量的金融资产", db_comment="以摊余成本计量的金融资产")
    fair_value_fin_assets = tushare_float_field(
        "以公允价值计量且其变动计入其他综合收益的金融资产",
        db_comment="以公允价值计量且其变动计入其他综合收益的金融资产",
    )
    contract_assets = tushare_float_field("合同资产", db_comment="合同资产")
    contract_liab = tushare_float_field("合同负债", db_comment="合同负债")
    accounts_receiv_bill = tushare_float_field("应收票据及应收账款", db_comment="应收票据及应收账款")
    accounts_pay = tushare_float_field("应付票据及应付账款", db_comment="应付票据及应付账款")
    oth_rcv_total = tushare_float_field("其他应收款(合计)（元）", db_comment="其他应收款(合计)（元）")
    fix_assets_total = tushare_float_field("固定资产(合计)(元)", db_comment="固定资产(合计)(元)")
    cip_total = tushare_float_field("在建工程(合计)(元)", db_comment="在建工程(合计)(元)")
    oth_pay_total = tushare_float_field("其他应付款(合计)(元)", db_comment="其他应付款(合计)(元)")
    long_pay_total = tushare_float_field("长期应付款(合计)(元)", db_comment="长期应付款(合计)(元)")
    debt_invest = tushare_float_field("债权投资(元)", db_comment="债权投资(元)")
    oth_debt_invest = tushare_float_field("其他债权投资(元)", db_comment="其他债权投资(元)")
    oth_eq_invest = tushare_float_field("其他权益工具投资(元)", db_comment="其他权益工具投资(元)")
    oth_illiq_fin_assets = tushare_float_field("其他非流动金融资产(元)", db_comment="其他非流动金融资产(元)")
    oth_eq_ppbond = tushare_float_field("其他权益工具:永续债(元)", db_comment="其他权益工具:永续债(元)")
    receiv_financing = tushare_float_field("应收款项融资", db_comment="应收款项融资")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_balancesheet"
        db_table_comment = "TuShare资产负债表"
        constraints = [
            models.UniqueConstraint(
                fields=["ts_code", "ann_date", "end_date", "report_type"], name="uniq_balancesheet_code_ann_end_type"
            ),
        ]
        indexes = [
            models.Index(fields=["ts_code", "end_date"], name="ix_balance_code_end"),
            models.Index(fields=["ann_date", "ts_code"], name="ix_balance_ann_code"),
        ]


class CashFlowStatement(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    ann_date = tushare_char_field("公告日期", max_length=8, db_index=True)
    f_ann_date = tushare_char_field("实际公告日期", max_length=8)
    end_date = models.CharField("报告期", max_length=8, db_comment="报告期 YYYYMMDD")
    comp_type = tushare_char_field("公司类型", max_length=16)
    report_type = tushare_char_field("报告类型", max_length=16)
    end_type = tushare_char_field("报告期类型", max_length=16)
    update_flag = tushare_char_field("更新标识", max_length=8)
    net_profit = tushare_float_field("净利润", db_comment="净利润")
    finan_exp = tushare_float_field("财务费用", db_comment="财务费用")
    c_fr_sale_sg = tushare_float_field("销售商品、提供劳务收到的现金", db_comment="销售商品、提供劳务收到的现金")
    recp_tax_rends = tushare_float_field("收到的税费返还", db_comment="收到的税费返还")
    n_depos_incr_fi = tushare_float_field("客户存款和同业存放款项净增加额", db_comment="客户存款和同业存放款项净增加额")
    n_incr_loans_cb = tushare_float_field("向中央银行借款净增加额", db_comment="向中央银行借款净增加额")
    n_inc_borr_oth_fi = tushare_float_field(
        "向其他金融机构拆入资金净增加额", db_comment="向其他金融机构拆入资金净增加额"
    )
    prem_fr_orig_contr = tushare_float_field("收到原保险合同保费取得的现金", db_comment="收到原保险合同保费取得的现金")
    n_incr_insured_dep = tushare_float_field("保户储金净增加额", db_comment="保户储金净增加额")
    n_reinsur_prem = tushare_float_field("收到再保业务现金净额", db_comment="收到再保业务现金净额")
    n_incr_disp_tfa = tushare_float_field("处置交易性金融资产净增加额", db_comment="处置交易性金融资产净增加额")
    ifc_cash_incr = tushare_float_field("收取利息和手续费净增加额", db_comment="收取利息和手续费净增加额")
    n_incr_disp_faas = tushare_float_field("处置可供出售金融资产净增加额", db_comment="处置可供出售金融资产净增加额")
    n_incr_loans_oth_bank = tushare_float_field("拆入资金净增加额", db_comment="拆入资金净增加额")
    n_cap_incr_repur = tushare_float_field("回购业务资金净增加额", db_comment="回购业务资金净增加额")
    c_fr_oth_operate_a = tushare_float_field("收到其他与经营活动有关的现金", db_comment="收到其他与经营活动有关的现金")
    c_inf_fr_operate_a = tushare_float_field("经营活动现金流入小计", db_comment="经营活动现金流入小计")
    c_paid_goods_s = tushare_float_field("购买商品、接受劳务支付的现金", db_comment="购买商品、接受劳务支付的现金")
    c_paid_to_for_empl = tushare_float_field(
        "支付给职工以及为职工支付的现金", db_comment="支付给职工以及为职工支付的现金"
    )
    c_paid_for_taxes = tushare_float_field("支付的各项税费", db_comment="支付的各项税费")
    n_incr_clt_loan_adv = tushare_float_field("客户贷款及垫款净增加额", db_comment="客户贷款及垫款净增加额")
    n_incr_dep_cbob = tushare_float_field("存放央行和同业款项净增加额", db_comment="存放央行和同业款项净增加额")
    c_pay_claims_orig_inco = tushare_float_field(
        "支付原保险合同赔付款项的现金", db_comment="支付原保险合同赔付款项的现金"
    )
    pay_handling_chrg = tushare_float_field("支付手续费的现金", db_comment="支付手续费的现金")
    pay_comm_insur_plcy = tushare_float_field("支付保单红利的现金", db_comment="支付保单红利的现金")
    oth_cash_pay_oper_act = tushare_float_field(
        "支付其他与经营活动有关的现金", db_comment="支付其他与经营活动有关的现金"
    )
    st_cash_out_act = tushare_float_field("经营活动现金流出小计", db_comment="经营活动现金流出小计")
    n_cashflow_act = tushare_float_field("经营活动产生的现金流量净额", db_comment="经营活动产生的现金流量净额")
    oth_recp_ral_inv_act = tushare_float_field(
        "收到其他与投资活动有关的现金", db_comment="收到其他与投资活动有关的现金"
    )
    c_disp_withdrwl_invest = tushare_float_field("收回投资收到的现金", db_comment="收回投资收到的现金")
    c_recp_return_invest = tushare_float_field("取得投资收益收到的现金", db_comment="取得投资收益收到的现金")
    n_recp_disp_fiolta = tushare_float_field(
        "处置固定资产、无形资产和其他长期资产收回的现金净额",
        db_comment="处置固定资产、无形资产和其他长期资产收回的现金净额",
    )
    n_recp_disp_sobu = tushare_float_field(
        "处置子公司及其他营业单位收到的现金净额", db_comment="处置子公司及其他营业单位收到的现金净额"
    )
    stot_inflows_inv_act = tushare_float_field("投资活动现金流入小计", db_comment="投资活动现金流入小计")
    c_pay_acq_const_fiolta = tushare_float_field(
        "购建固定资产、无形资产和其他长期资产支付的现金", db_comment="购建固定资产、无形资产和其他长期资产支付的现金"
    )
    c_paid_invest = tushare_float_field("投资支付的现金", db_comment="投资支付的现金")
    n_disp_subs_oth_biz = tushare_float_field(
        "取得子公司及其他营业单位支付的现金净额", db_comment="取得子公司及其他营业单位支付的现金净额"
    )
    oth_pay_ral_inv_act = tushare_float_field("支付其他与投资活动有关的现金", db_comment="支付其他与投资活动有关的现金")
    n_incr_pledge_loan = tushare_float_field("质押贷款净增加额", db_comment="质押贷款净增加额")
    stot_out_inv_act = tushare_float_field("投资活动现金流出小计", db_comment="投资活动现金流出小计")
    n_cashflow_inv_act = tushare_float_field("投资活动产生的现金流量净额", db_comment="投资活动产生的现金流量净额")
    c_recp_borrow = tushare_float_field("取得借款收到的现金", db_comment="取得借款收到的现金")
    proc_issue_bonds = tushare_float_field("发行债券收到的现金", db_comment="发行债券收到的现金")
    oth_cash_recp_ral_fnc_act = tushare_float_field(
        "收到其他与筹资活动有关的现金", db_comment="收到其他与筹资活动有关的现金"
    )
    stot_cash_in_fnc_act = tushare_float_field("筹资活动现金流入小计", db_comment="筹资活动现金流入小计")
    free_cashflow = tushare_float_field("企业自由现金流量", db_comment="企业自由现金流量")
    c_prepay_amt_borr = tushare_float_field("偿还债务支付的现金", db_comment="偿还债务支付的现金")
    c_pay_dist_dpcp_int_exp = tushare_float_field(
        "分配股利、利润或偿付利息支付的现金", db_comment="分配股利、利润或偿付利息支付的现金"
    )
    incl_dvd_profit_paid_sc_ms = tushare_float_field(
        "其中:子公司支付给少数股东的股利、利润", db_comment="其中:子公司支付给少数股东的股利、利润"
    )
    oth_cashpay_ral_fnc_act = tushare_float_field(
        "支付其他与筹资活动有关的现金", db_comment="支付其他与筹资活动有关的现金"
    )
    stot_cashout_fnc_act = tushare_float_field("筹资活动现金流出小计", db_comment="筹资活动现金流出小计")
    n_cash_flows_fnc_act = tushare_float_field("筹资活动产生的现金流量净额", db_comment="筹资活动产生的现金流量净额")
    eff_fx_flu_cash = tushare_float_field("汇率变动对现金的影响", db_comment="汇率变动对现金的影响")
    n_incr_cash_cash_equ = tushare_float_field("现金及现金等价物净增加额", db_comment="现金及现金等价物净增加额")
    c_cash_equ_beg_period = tushare_float_field("期初现金及现金等价物余额", db_comment="期初现金及现金等价物余额")
    c_cash_equ_end_period = tushare_float_field("期末现金及现金等价物余额", db_comment="期末现金及现金等价物余额")
    c_recp_cap_contrib = tushare_float_field("吸收投资收到的现金", db_comment="吸收投资收到的现金")
    incl_cash_rec_saims = tushare_float_field(
        "其中:子公司吸收少数股东投资收到的现金", db_comment="其中:子公司吸收少数股东投资收到的现金"
    )
    uncon_invest_loss = tushare_float_field("未确认投资损失", db_comment="未确认投资损失")
    prov_depr_assets = tushare_float_field("加:资产减值准备", db_comment="加:资产减值准备")
    depr_fa_coga_dpba = tushare_float_field(
        "固定资产折旧、油气资产折耗、生产性生物资产折旧", db_comment="固定资产折旧、油气资产折耗、生产性生物资产折旧"
    )
    amort_intang_assets = tushare_float_field("无形资产摊销", db_comment="无形资产摊销")
    lt_amort_deferred_exp = tushare_float_field("长期待摊费用摊销", db_comment="长期待摊费用摊销")
    decr_deferred_exp = tushare_float_field("待摊费用减少", db_comment="待摊费用减少")
    incr_acc_exp = tushare_float_field("预提费用增加", db_comment="预提费用增加")
    loss_disp_fiolta = tushare_float_field(
        "处置固定、无形资产和其他长期资产的损失", db_comment="处置固定、无形资产和其他长期资产的损失"
    )
    loss_scr_fa = tushare_float_field("固定资产报废损失", db_comment="固定资产报废损失")
    loss_fv_chg = tushare_float_field("公允价值变动损失", db_comment="公允价值变动损失")
    invest_loss = tushare_float_field("投资损失", db_comment="投资损失")
    decr_def_inc_tax_assets = tushare_float_field("递延所得税资产减少", db_comment="递延所得税资产减少")
    incr_def_inc_tax_liab = tushare_float_field("递延所得税负债增加", db_comment="递延所得税负债增加")
    decr_inventories = tushare_float_field("存货的减少", db_comment="存货的减少")
    decr_oper_payable = tushare_float_field("经营性应收项目的减少", db_comment="经营性应收项目的减少")
    incr_oper_payable = tushare_float_field("经营性应付项目的增加", db_comment="经营性应付项目的增加")
    others = tushare_float_field("其他", db_comment="其他")
    im_net_cashflow_oper_act = tushare_float_field(
        "经营活动产生的现金流量净额(间接法)", db_comment="经营活动产生的现金流量净额(间接法)"
    )
    conv_debt_into_cap = tushare_float_field("债务转为资本", db_comment="债务转为资本")
    conv_copbonds_due_within_1y = tushare_float_field(
        "一年内到期的可转换公司债券", db_comment="一年内到期的可转换公司债券"
    )
    fa_fnc_leases = tushare_float_field("融资租入固定资产", db_comment="融资租入固定资产")
    end_bal_cash = tushare_float_field("现金的期末余额", db_comment="现金的期末余额")
    beg_bal_cash = tushare_float_field("减:现金的期初余额", db_comment="减:现金的期初余额")
    end_bal_cash_equ = tushare_float_field("加:现金等价物的期末余额", db_comment="加:现金等价物的期末余额")
    beg_bal_cash_equ = tushare_float_field("减:现金等价物的期初余额", db_comment="减:现金等价物的期初余额")
    im_n_incr_cash_equ = tushare_float_field(
        "现金及现金等价物净增加额(间接法)", db_comment="现金及现金等价物净增加额(间接法)"
    )
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_cashflow"
        db_table_comment = "TuShare现金流量表"
        constraints = [
            models.UniqueConstraint(
                fields=["ts_code", "ann_date", "end_date", "report_type"], name="uniq_cashflow_code_ann_end_type"
            ),
        ]
        indexes = [
            models.Index(fields=["ts_code", "end_date"], name="ix_cashflow_code_end"),
            models.Index(fields=["ann_date", "ts_code"], name="ix_cashflow_ann_code"),
        ]


class IndexBasic(TimestampedModel):
    ts_code = models.CharField("TS指数代码", max_length=24, unique=True, db_comment="TuShare指数代码")
    name = tushare_char_field("指数简称", max_length=120, db_index=True)
    fullname = tushare_char_field("指数全称", max_length=240)
    market = tushare_char_field("市场", max_length=32, db_index=True)
    publisher = tushare_char_field("发布方", max_length=120)
    index_type = tushare_char_field("指数风格", max_length=80)
    category = tushare_char_field("指数类别", max_length=80)
    base_date = tushare_char_field("基期", max_length=8)
    base_point = tushare_float_field("基点")
    list_date = tushare_char_field("发布日期", max_length=8)
    weight_rule = models.TextField("加权方式", blank=True, null=True, db_comment="加权方式")
    desc = models.TextField("指数描述", blank=True, null=True, db_comment="指数描述")
    exp_date = tushare_char_field("终止日期", max_length=8)
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_index_basic"
        db_table_comment = "TuShare指数基础信息"
        indexes = [
            models.Index(fields=["market", "category"], name="ix_idx_basic_market_cat"),
        ]


class IndexDaily(TimestampedModel):
    ts_code = models.CharField("TS指数代码", max_length=24, db_comment="TuShare指数代码")
    trade_date = models.CharField("交易日期", max_length=8, db_comment="交易日期 YYYYMMDD")
    close = tushare_float_field("收盘点位")
    open = tushare_float_field("开盘点位")
    high = tushare_float_field("最高点位")
    low = tushare_float_field("最低点位")
    pre_close = tushare_float_field("昨日收盘点位")
    change = tushare_float_field("涨跌点")
    pct_chg = tushare_float_field("涨跌幅")
    vol = tushare_float_field("成交量")
    amount = tushare_float_field("成交额")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_index_daily"
        db_table_comment = "TuShare指数日线行情"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date"], name="uniq_index_daily_code_date"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "ts_code"], name="ix_idx_daily_date_code"),
            models.Index(fields=["ts_code", "trade_date"], name="ix_idx_daily_code_date"),
        ]


class IndexClassify(TimestampedModel):
    index_code = models.CharField("行业指数代码", max_length=24, db_comment="行业指数代码")
    industry_name = tushare_char_field("行业名称", max_length=120, db_index=True)
    level = tushare_char_field("行业级别", max_length=16, db_index=True)
    industry_code = tushare_char_field("行业编码", max_length=24)
    is_pub = tushare_char_field("是否发布", max_length=8)
    parent_code = tushare_char_field("父级代码", max_length=24)
    src = tushare_char_field("行业分类来源", max_length=16, db_index=True)
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_index_classify"
        db_table_comment = "TuShare行业分类"
        constraints = [
            models.UniqueConstraint(fields=["index_code", "src"], name="uniq_index_classify_code_src"),
        ]
        indexes = [
            models.Index(fields=["src", "level"], name="ix_idx_class_src_level"),
        ]


class IndexMemberAll(TimestampedModel):
    l1_code = tushare_char_field("一级行业代码", max_length=24, db_index=True)
    l1_name = tushare_char_field("一级行业名称", max_length=120)
    l2_code = tushare_char_field("二级行业代码", max_length=24, db_index=True)
    l2_name = tushare_char_field("二级行业名称", max_length=120)
    l3_code = tushare_char_field("三级行业代码", max_length=24, db_index=True)
    l3_name = tushare_char_field("三级行业名称", max_length=120)
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    name = tushare_char_field("股票名称", max_length=120)
    in_date = tushare_char_field("纳入日期", max_length=8, db_index=True)
    out_date = tushare_char_field("剔除日期", max_length=8, db_index=True)
    is_new = tushare_char_field("是否最新", max_length=8, db_index=True)
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_index_member_all"
        db_table_comment = "TuShare申万行业成分全量"
        constraints = [
            models.UniqueConstraint(
                fields=["ts_code", "l1_code", "l2_code", "l3_code", "in_date"], name="uniq_idx_mem_all_code_ind_date"
            ),
        ]
        indexes = [
            models.Index(fields=["ts_code", "is_new"], name="ix_idx_mem_all_code_new"),
            models.Index(fields=["l1_code", "is_new"], name="ix_idx_mem_all_l1_new"),
        ]


class StockMoneyflow(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    trade_date = models.CharField("交易日期", max_length=8, db_comment="交易日期 YYYYMMDD")
    buy_sm_vol = tushare_float_field("小单买入量（手）", db_comment="小单买入量（手）")
    buy_sm_amount = tushare_float_field("小单买入金额（万元）", db_comment="小单买入金额（万元）")
    sell_sm_vol = tushare_float_field("小单卖出量（手）", db_comment="小单卖出量（手）")
    sell_sm_amount = tushare_float_field("小单卖出金额（万元）", db_comment="小单卖出金额（万元）")
    buy_md_vol = tushare_float_field("中单买入量（手）", db_comment="中单买入量（手）")
    buy_md_amount = tushare_float_field("中单买入金额（万元）", db_comment="中单买入金额（万元）")
    sell_md_vol = tushare_float_field("中单卖出量（手）", db_comment="中单卖出量（手）")
    sell_md_amount = tushare_float_field("中单卖出金额（万元）", db_comment="中单卖出金额（万元）")
    buy_lg_vol = tushare_float_field("大单买入量（手）", db_comment="大单买入量（手）")
    buy_lg_amount = tushare_float_field("大单买入金额（万元）", db_comment="大单买入金额（万元）")
    sell_lg_vol = tushare_float_field("大单卖出量（手）", db_comment="大单卖出量（手）")
    sell_lg_amount = tushare_float_field("大单卖出金额（万元）", db_comment="大单卖出金额（万元）")
    buy_elg_vol = tushare_float_field("特大单买入量（手）", db_comment="特大单买入量（手）")
    buy_elg_amount = tushare_float_field("特大单买入金额（万元）", db_comment="特大单买入金额（万元）")
    sell_elg_vol = tushare_float_field("特大单卖出量（手）", db_comment="特大单卖出量（手）")
    sell_elg_amount = tushare_float_field("特大单卖出金额（万元）", db_comment="特大单卖出金额（万元）")
    net_mf_vol = tushare_float_field("净流入量（手）", db_comment="净流入量（手）")
    net_mf_amount = tushare_float_field("净流入额（万元）", db_comment="净流入额（万元）")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_moneyflow"
        db_table_comment = "TuShare个股资金流向"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date"], name="uniq_moneyflow_code_date"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "ts_code"], name="ix_moneyflow_date_code"),
            models.Index(fields=["ts_code", "trade_date"], name="ix_moneyflow_code_date"),
        ]


class MarginDetail(TimestampedModel):
    trade_date = models.CharField("交易日期", max_length=8, db_comment="交易日期 YYYYMMDD")
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    name = tushare_char_field("股票名称", max_length=120)
    exchange_id = tushare_char_field("交易所代码", max_length=16, db_index=True)
    rzye = tushare_float_field("融资余额", db_comment="融资余额，单位元")
    rqye = tushare_float_field("融券余额", db_comment="融券余额，单位元")
    rzmre = tushare_float_field("融资买入额", db_comment="融资买入额，单位元")
    rqyl = tushare_float_field("融券余量", db_comment="融券余量，单位股")
    rzche = tushare_float_field("融资偿还额", db_comment="融资偿还额，单位元")
    rqchl = tushare_float_field("融券偿还量", db_comment="融券偿还量，单位股")
    rqmcl = tushare_float_field("融券卖出量", db_comment="融券卖出量，单位股")
    rzrqye = tushare_float_field("融资融券余额", db_comment="融资融券余额，单位元")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_margin_detail"
        db_table_comment = "TuShare融资融券交易明细"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date"], name="uniq_margin_detail_code_date"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "exchange_id"], name="ix_margin_detail_date_ex"),
            models.Index(fields=["ts_code", "trade_date"], name="ix_margin_detail_code_date"),
        ]


class HkHold(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    trade_date = models.CharField("交易日期", max_length=8, db_comment="交易日期 YYYYMMDD")
    code = tushare_char_field("原始代码", max_length=24)
    name = tushare_char_field("股票名称", max_length=120)
    vol = tushare_float_field("持股数量")
    ratio = tushare_float_field("持股占比")
    exchange = tushare_char_field("交易所", max_length=16, db_index=True)
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_hk_hold"
        db_table_comment = "TuShare沪深股通持股明细"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date", "exchange"], name="uniq_hk_hold_code_date_ex"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "exchange"], name="ix_hk_hold_date_ex"),
            models.Index(fields=["ts_code", "trade_date"], name="ix_hk_hold_code_date"),
        ]


class SuspendDetail(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    suspend_date = models.CharField("停牌日期", max_length=8, db_comment="停牌日期 YYYYMMDD")
    resume_date = tushare_char_field("复牌日期", max_length=8, db_index=True)
    ann_date = tushare_char_field("公告日期", max_length=8, db_index=True)
    suspend_reason = models.TextField("停牌原因", blank=True, null=True, db_comment="停牌原因")
    reason_type = tushare_char_field("停牌原因类别", max_length=120)
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_suspend_d"
        db_table_comment = "TuShare每日停复牌信息"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "suspend_date"], name="uniq_suspend_code_date"),
        ]
        indexes = [
            models.Index(fields=["suspend_date", "ts_code"], name="ix_suspend_date_code"),
            models.Index(fields=["ts_code", "resume_date"], name="ix_suspend_code_resume"),
        ]


class StockLimit(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    trade_date = models.CharField("交易日期", max_length=8, db_comment="交易日期 YYYYMMDD")
    up_limit = tushare_float_field("涨停价")
    down_limit = tushare_float_field("跌停价")
    pre_close = tushare_float_field("昨日收盘价")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_stk_limit"
        db_table_comment = "TuShare每日涨跌停价格"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date"], name="uniq_stk_limit_code_date"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "ts_code"], name="ix_stk_limit_date_code"),
        ]


class ShareFloat(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    ann_date = tushare_char_field("公告日期", max_length=8, db_index=True)
    float_date = models.CharField("解禁日期", max_length=8, db_comment="解禁日期 YYYYMMDD")
    float_share = tushare_float_field("解禁数量")
    float_ratio = tushare_float_field("解禁比例")
    holder_name = tushare_char_field("股东名称", max_length=240, db_index=True)
    share_type = tushare_char_field("股份类型", max_length=120)
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_share_float"
        db_table_comment = "TuShare限售股解禁"
        constraints = [
            models.UniqueConstraint(
                fields=["ts_code", "float_date", "holder_name", "share_type"], name="uniq_share_float_code_date_holder"
            ),
        ]
        indexes = [
            models.Index(fields=["float_date", "ts_code"], name="ix_share_float_date_code"),
            models.Index(fields=["ts_code", "ann_date"], name="ix_share_float_code_ann"),
        ]


class PledgeStat(TimestampedModel):
    ts_code = models.CharField("TS股票代码", max_length=24, db_comment="TuShare股票代码")
    end_date = models.CharField("截止日期", max_length=8, db_comment="截止日期 YYYYMMDD")
    pledge_count = tushare_float_field("质押次数")
    unrest_pledge = tushare_float_field("无限售股质押数量")
    rest_pledge = tushare_float_field("限售股质押数量")
    total_share = tushare_float_field("总股本")
    pledge_ratio = tushare_float_field("质押比例")
    tushare_meta = models.JSONField(
        "TuShare元数据", default=dict, blank=True, db_comment="TuShare分类、接口和目标表元数据"
    )

    class Meta:
        db_table = "tushare_pledge_stat"
        db_table_comment = "TuShare股权质押统计"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "end_date"], name="uniq_pledge_stat_code_end"),
        ]
        indexes = [
            models.Index(fields=["end_date", "ts_code"], name="ix_pledge_stat_end_code"),
        ]


class StockFactorPro(TimestampedModel):
    ts_code = tushare_char_field("股票代码", max_length=24)
    trade_date = tushare_char_field("交易日期", max_length=8)
    open = tushare_float_field("开盘价", db_comment="开盘价")
    open_hfq = tushare_float_field("开盘价（后复权）", db_comment="开盘价（后复权）")
    open_qfq = tushare_float_field("开盘价（前复权）", db_comment="开盘价（前复权）")
    high = tushare_float_field("最高价", db_comment="最高价")
    high_hfq = tushare_float_field("最高价（后复权）", db_comment="最高价（后复权）")
    high_qfq = tushare_float_field("最高价（前复权）", db_comment="最高价（前复权）")
    low = tushare_float_field("最低价", db_comment="最低价")
    low_hfq = tushare_float_field("最低价（后复权）", db_comment="最低价（后复权）")
    low_qfq = tushare_float_field("最低价（前复权）", db_comment="最低价（前复权）")
    close = tushare_float_field("收盘价", db_comment="收盘价")
    close_hfq = tushare_float_field("收盘价（后复权）", db_comment="收盘价（后复权）")
    close_qfq = tushare_float_field("收盘价（前复权）", db_comment="收盘价（前复权）")
    pre_close = tushare_float_field(
        "昨收价(前复权)--为daily接口的pre_close,以当时复权因子计算值跟前一日close_qfq对不上，可不用",
        db_comment="昨收价(前复权)--为daily接口的pre_close,以当时复权因子计算值跟前一日close_qfq对不上，可不用",
    )
    change = tushare_float_field("涨跌额", db_comment="涨跌额")
    pct_chg = tushare_float_field("涨跌幅 （除权后的涨跌幅）", db_comment="涨跌幅 （除权后的涨跌幅）")
    vol = tushare_float_field("成交量 （手）", db_comment="成交量 （手）")
    amount = tushare_float_field("成交额 （千元）", db_comment="成交额 （千元）")
    turnover_rate = tushare_float_field("换手率（%）", db_comment="换手率（%）")
    turnover_rate_f = tushare_float_field("换手率（自由流通股）", db_comment="换手率（自由流通股）")
    volume_ratio = tushare_float_field("量比", db_comment="量比")
    pe = tushare_float_field(
        "市盈率（总市值/净利润， 亏损的PE为空）", db_comment="市盈率（总市值/净利润， 亏损的PE为空）"
    )
    pe_ttm = tushare_float_field("市盈率（TTM，亏损的PE为空）", db_comment="市盈率（TTM，亏损的PE为空）")
    pb = tushare_float_field("市净率（总市值/净资产）", db_comment="市净率（总市值/净资产）")
    ps = tushare_float_field("市销率", db_comment="市销率")
    ps_ttm = tushare_float_field("市销率（TTM）", db_comment="市销率（TTM）")
    dv_ratio = tushare_float_field("股息率 （%）", db_comment="股息率 （%）")
    dv_ttm = tushare_float_field("股息率（TTM）（%）", db_comment="股息率（TTM）（%）")
    total_share = tushare_float_field("总股本 （万股）", db_comment="总股本 （万股）")
    float_share = tushare_float_field("流通股本 （万股）", db_comment="流通股本 （万股）")
    free_share = tushare_float_field("自由流通股本 （万）", db_comment="自由流通股本 （万）")
    total_mv = tushare_float_field("总市值 （万元）", db_comment="总市值 （万元）")
    circ_mv = tushare_float_field("流通市值（万元）", db_comment="流通市值（万元）")
    adj_factor = tushare_float_field("复权因子", db_comment="复权因子")
    asi_bfq = tushare_float_field(
        "振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10",
        db_comment="振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10",
    )
    asi_hfq = tushare_float_field(
        "振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10",
        db_comment="振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10",
    )
    asi_qfq = tushare_float_field(
        "振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10",
        db_comment="振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10",
    )
    asit_bfq = tushare_float_field(
        "振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10",
        db_comment="振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10",
    )
    asit_hfq = tushare_float_field(
        "振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10",
        db_comment="振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10",
    )
    asit_qfq = tushare_float_field(
        "振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10",
        db_comment="振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10",
    )
    atr_bfq = tushare_float_field(
        "真实波动N日平均值-CLOSE, HIGH, LOW, N=20", db_comment="真实波动N日平均值-CLOSE, HIGH, LOW, N=20"
    )
    atr_hfq = tushare_float_field(
        "真实波动N日平均值-CLOSE, HIGH, LOW, N=20", db_comment="真实波动N日平均值-CLOSE, HIGH, LOW, N=20"
    )
    atr_qfq = tushare_float_field(
        "真实波动N日平均值-CLOSE, HIGH, LOW, N=20", db_comment="真实波动N日平均值-CLOSE, HIGH, LOW, N=20"
    )
    bbi_bfq = tushare_float_field(
        "BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=20", db_comment="BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=20"
    )
    bbi_hfq = tushare_float_field(
        "BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=21", db_comment="BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=21"
    )
    bbi_qfq = tushare_float_field(
        "BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=22", db_comment="BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=22"
    )
    bias1_bfq = tushare_float_field(
        "BIAS乖离率-CLOSE, L1=6, L2=12, L3=24", db_comment="BIAS乖离率-CLOSE, L1=6, L2=12, L3=24"
    )
    bias1_hfq = tushare_float_field(
        "BIAS乖离率-CLOSE, L1=6, L2=12, L3=24", db_comment="BIAS乖离率-CLOSE, L1=6, L2=12, L3=24"
    )
    bias1_qfq = tushare_float_field(
        "BIAS乖离率-CLOSE, L1=6, L2=12, L3=24", db_comment="BIAS乖离率-CLOSE, L1=6, L2=12, L3=24"
    )
    bias2_bfq = tushare_float_field(
        "BIAS乖离率-CLOSE, L1=6, L2=12, L3=24", db_comment="BIAS乖离率-CLOSE, L1=6, L2=12, L3=24"
    )
    bias2_hfq = tushare_float_field(
        "BIAS乖离率-CLOSE, L1=6, L2=12, L3=24", db_comment="BIAS乖离率-CLOSE, L1=6, L2=12, L3=24"
    )
    bias2_qfq = tushare_float_field(
        "BIAS乖离率-CLOSE, L1=6, L2=12, L3=24", db_comment="BIAS乖离率-CLOSE, L1=6, L2=12, L3=24"
    )
    bias3_bfq = tushare_float_field(
        "BIAS乖离率-CLOSE, L1=6, L2=12, L3=24", db_comment="BIAS乖离率-CLOSE, L1=6, L2=12, L3=24"
    )
    bias3_hfq = tushare_float_field(
        "BIAS乖离率-CLOSE, L1=6, L2=12, L3=24", db_comment="BIAS乖离率-CLOSE, L1=6, L2=12, L3=24"
    )
    bias3_qfq = tushare_float_field(
        "BIAS乖离率-CLOSE, L1=6, L2=12, L3=24", db_comment="BIAS乖离率-CLOSE, L1=6, L2=12, L3=24"
    )
    boll_lower_bfq = tushare_float_field(
        "BOLL指标，布林带-CLOSE, N=20, P=2", db_comment="BOLL指标，布林带-CLOSE, N=20, P=2"
    )
    boll_lower_hfq = tushare_float_field(
        "BOLL指标，布林带-CLOSE, N=20, P=2", db_comment="BOLL指标，布林带-CLOSE, N=20, P=2"
    )
    boll_lower_qfq = tushare_float_field(
        "BOLL指标，布林带-CLOSE, N=20, P=2", db_comment="BOLL指标，布林带-CLOSE, N=20, P=2"
    )
    boll_mid_bfq = tushare_float_field(
        "BOLL指标，布林带-CLOSE, N=20, P=2", db_comment="BOLL指标，布林带-CLOSE, N=20, P=2"
    )
    boll_mid_hfq = tushare_float_field(
        "BOLL指标，布林带-CLOSE, N=20, P=2", db_comment="BOLL指标，布林带-CLOSE, N=20, P=2"
    )
    boll_mid_qfq = tushare_float_field(
        "BOLL指标，布林带-CLOSE, N=20, P=2", db_comment="BOLL指标，布林带-CLOSE, N=20, P=2"
    )
    boll_upper_bfq = tushare_float_field(
        "BOLL指标，布林带-CLOSE, N=20, P=2", db_comment="BOLL指标，布林带-CLOSE, N=20, P=2"
    )
    boll_upper_hfq = tushare_float_field(
        "BOLL指标，布林带-CLOSE, N=20, P=2", db_comment="BOLL指标，布林带-CLOSE, N=20, P=2"
    )
    boll_upper_qfq = tushare_float_field(
        "BOLL指标，布林带-CLOSE, N=20, P=2", db_comment="BOLL指标，布林带-CLOSE, N=20, P=2"
    )
    brar_ar_bfq = tushare_float_field(
        "BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26", db_comment="BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26"
    )
    brar_ar_hfq = tushare_float_field(
        "BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26", db_comment="BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26"
    )
    brar_ar_qfq = tushare_float_field(
        "BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26", db_comment="BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26"
    )
    brar_br_bfq = tushare_float_field(
        "BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26", db_comment="BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26"
    )
    brar_br_hfq = tushare_float_field(
        "BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26", db_comment="BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26"
    )
    brar_br_qfq = tushare_float_field(
        "BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26", db_comment="BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26"
    )
    cci_bfq = tushare_float_field(
        "顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14", db_comment="顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14"
    )
    cci_hfq = tushare_float_field(
        "顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14", db_comment="顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14"
    )
    cci_qfq = tushare_float_field(
        "顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14", db_comment="顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14"
    )
    cr_bfq = tushare_float_field(
        "CR价格动量指标-CLOSE, HIGH, LOW, N=20", db_comment="CR价格动量指标-CLOSE, HIGH, LOW, N=20"
    )
    cr_hfq = tushare_float_field(
        "CR价格动量指标-CLOSE, HIGH, LOW, N=20", db_comment="CR价格动量指标-CLOSE, HIGH, LOW, N=20"
    )
    cr_qfq = tushare_float_field(
        "CR价格动量指标-CLOSE, HIGH, LOW, N=20", db_comment="CR价格动量指标-CLOSE, HIGH, LOW, N=20"
    )
    dfma_dif_bfq = tushare_float_field(
        "平行线差指标-CLOSE, N1=10, N2=50, M=10", db_comment="平行线差指标-CLOSE, N1=10, N2=50, M=10"
    )
    dfma_dif_hfq = tushare_float_field(
        "平行线差指标-CLOSE, N1=10, N2=50, M=10", db_comment="平行线差指标-CLOSE, N1=10, N2=50, M=10"
    )
    dfma_dif_qfq = tushare_float_field(
        "平行线差指标-CLOSE, N1=10, N2=50, M=10", db_comment="平行线差指标-CLOSE, N1=10, N2=50, M=10"
    )
    dfma_difma_bfq = tushare_float_field(
        "平行线差指标-CLOSE, N1=10, N2=50, M=10", db_comment="平行线差指标-CLOSE, N1=10, N2=50, M=10"
    )
    dfma_difma_hfq = tushare_float_field(
        "平行线差指标-CLOSE, N1=10, N2=50, M=10", db_comment="平行线差指标-CLOSE, N1=10, N2=50, M=10"
    )
    dfma_difma_qfq = tushare_float_field(
        "平行线差指标-CLOSE, N1=10, N2=50, M=10", db_comment="平行线差指标-CLOSE, N1=10, N2=50, M=10"
    )
    dmi_adx_bfq = tushare_float_field(
        "动向指标-CLOSE, HIGH, LOW, M1=14, M2=6", db_comment="动向指标-CLOSE, HIGH, LOW, M1=14, M2=6"
    )
    dmi_adx_hfq = tushare_float_field(
        "动向指标-CLOSE, HIGH, LOW, M1=14, M2=6", db_comment="动向指标-CLOSE, HIGH, LOW, M1=14, M2=6"
    )
    dmi_adx_qfq = tushare_float_field(
        "动向指标-CLOSE, HIGH, LOW, M1=14, M2=6", db_comment="动向指标-CLOSE, HIGH, LOW, M1=14, M2=6"
    )
    dmi_adxr_bfq = tushare_float_field(
        "动向指标-CLOSE, HIGH, LOW, M1=14, M2=6", db_comment="动向指标-CLOSE, HIGH, LOW, M1=14, M2=6"
    )
    dmi_adxr_hfq = tushare_float_field(
        "动向指标-CLOSE, HIGH, LOW, M1=14, M2=6", db_comment="动向指标-CLOSE, HIGH, LOW, M1=14, M2=6"
    )
    dmi_adxr_qfq = tushare_float_field(
        "动向指标-CLOSE, HIGH, LOW, M1=14, M2=6", db_comment="动向指标-CLOSE, HIGH, LOW, M1=14, M2=6"
    )
    dmi_mdi_bfq = tushare_float_field(
        "动向指标-CLOSE, HIGH, LOW, M1=14, M2=6", db_comment="动向指标-CLOSE, HIGH, LOW, M1=14, M2=6"
    )
    dmi_mdi_hfq = tushare_float_field(
        "动向指标-CLOSE, HIGH, LOW, M1=14, M2=6", db_comment="动向指标-CLOSE, HIGH, LOW, M1=14, M2=6"
    )
    dmi_mdi_qfq = tushare_float_field(
        "动向指标-CLOSE, HIGH, LOW, M1=14, M2=6", db_comment="动向指标-CLOSE, HIGH, LOW, M1=14, M2=6"
    )
    dmi_pdi_bfq = tushare_float_field(
        "动向指标-CLOSE, HIGH, LOW, M1=14, M2=6", db_comment="动向指标-CLOSE, HIGH, LOW, M1=14, M2=6"
    )
    dmi_pdi_hfq = tushare_float_field(
        "动向指标-CLOSE, HIGH, LOW, M1=14, M2=6", db_comment="动向指标-CLOSE, HIGH, LOW, M1=14, M2=6"
    )
    dmi_pdi_qfq = tushare_float_field(
        "动向指标-CLOSE, HIGH, LOW, M1=14, M2=6", db_comment="动向指标-CLOSE, HIGH, LOW, M1=14, M2=6"
    )
    downdays = tushare_float_field("连跌天数", db_comment="连跌天数")
    updays = tushare_float_field("连涨天数", db_comment="连涨天数")
    dpo_bfq = tushare_float_field(
        "区间震荡线-CLOSE, M1=20, M2=10, M3=6", db_comment="区间震荡线-CLOSE, M1=20, M2=10, M3=6"
    )
    dpo_hfq = tushare_float_field(
        "区间震荡线-CLOSE, M1=20, M2=10, M3=6", db_comment="区间震荡线-CLOSE, M1=20, M2=10, M3=6"
    )
    dpo_qfq = tushare_float_field(
        "区间震荡线-CLOSE, M1=20, M2=10, M3=6", db_comment="区间震荡线-CLOSE, M1=20, M2=10, M3=6"
    )
    madpo_bfq = tushare_float_field(
        "区间震荡线-CLOSE, M1=20, M2=10, M3=6", db_comment="区间震荡线-CLOSE, M1=20, M2=10, M3=6"
    )
    madpo_hfq = tushare_float_field(
        "区间震荡线-CLOSE, M1=20, M2=10, M3=6", db_comment="区间震荡线-CLOSE, M1=20, M2=10, M3=6"
    )
    madpo_qfq = tushare_float_field(
        "区间震荡线-CLOSE, M1=20, M2=10, M3=6", db_comment="区间震荡线-CLOSE, M1=20, M2=10, M3=6"
    )
    ema_bfq_10 = tushare_float_field("指数移动平均-N=10", db_comment="指数移动平均-N=10")
    ema_bfq_20 = tushare_float_field("指数移动平均-N=20", db_comment="指数移动平均-N=20")
    ema_bfq_250 = tushare_float_field("指数移动平均-N=250", db_comment="指数移动平均-N=250")
    ema_bfq_30 = tushare_float_field("指数移动平均-N=30", db_comment="指数移动平均-N=30")
    ema_bfq_5 = tushare_float_field("指数移动平均-N=5", db_comment="指数移动平均-N=5")
    ema_bfq_60 = tushare_float_field("指数移动平均-N=60", db_comment="指数移动平均-N=60")
    ema_bfq_90 = tushare_float_field("指数移动平均-N=90", db_comment="指数移动平均-N=90")
    ema_hfq_10 = tushare_float_field("指数移动平均-N=10", db_comment="指数移动平均-N=10")
    ema_hfq_20 = tushare_float_field("指数移动平均-N=20", db_comment="指数移动平均-N=20")
    ema_hfq_250 = tushare_float_field("指数移动平均-N=250", db_comment="指数移动平均-N=250")
    ema_hfq_30 = tushare_float_field("指数移动平均-N=30", db_comment="指数移动平均-N=30")
    ema_hfq_5 = tushare_float_field("指数移动平均-N=5", db_comment="指数移动平均-N=5")
    ema_hfq_60 = tushare_float_field("指数移动平均-N=60", db_comment="指数移动平均-N=60")
    ema_hfq_90 = tushare_float_field("指数移动平均-N=90", db_comment="指数移动平均-N=90")
    ema_qfq_10 = tushare_float_field("指数移动平均-N=10", db_comment="指数移动平均-N=10")
    ema_qfq_20 = tushare_float_field("指数移动平均-N=20", db_comment="指数移动平均-N=20")
    ema_qfq_250 = tushare_float_field("指数移动平均-N=250", db_comment="指数移动平均-N=250")
    ema_qfq_30 = tushare_float_field("指数移动平均-N=30", db_comment="指数移动平均-N=30")
    ema_qfq_5 = tushare_float_field("指数移动平均-N=5", db_comment="指数移动平均-N=5")
    ema_qfq_60 = tushare_float_field("指数移动平均-N=60", db_comment="指数移动平均-N=60")
    ema_qfq_90 = tushare_float_field("指数移动平均-N=90", db_comment="指数移动平均-N=90")
    emv_bfq = tushare_float_field(
        "简易波动指标-HIGH, LOW, VOL, N=14, M=9", db_comment="简易波动指标-HIGH, LOW, VOL, N=14, M=9"
    )
    emv_hfq = tushare_float_field(
        "简易波动指标-HIGH, LOW, VOL, N=14, M=9", db_comment="简易波动指标-HIGH, LOW, VOL, N=14, M=9"
    )
    emv_qfq = tushare_float_field(
        "简易波动指标-HIGH, LOW, VOL, N=14, M=9", db_comment="简易波动指标-HIGH, LOW, VOL, N=14, M=9"
    )
    maemv_bfq = tushare_float_field(
        "简易波动指标-HIGH, LOW, VOL, N=14, M=9", db_comment="简易波动指标-HIGH, LOW, VOL, N=14, M=9"
    )
    maemv_hfq = tushare_float_field(
        "简易波动指标-HIGH, LOW, VOL, N=14, M=9", db_comment="简易波动指标-HIGH, LOW, VOL, N=14, M=9"
    )
    maemv_qfq = tushare_float_field(
        "简易波动指标-HIGH, LOW, VOL, N=14, M=9", db_comment="简易波动指标-HIGH, LOW, VOL, N=14, M=9"
    )
    expma_12_bfq = tushare_float_field(
        "EMA指数平均数指标-CLOSE, N1=12, N2=50", db_comment="EMA指数平均数指标-CLOSE, N1=12, N2=50"
    )
    expma_12_hfq = tushare_float_field(
        "EMA指数平均数指标-CLOSE, N1=12, N2=50", db_comment="EMA指数平均数指标-CLOSE, N1=12, N2=50"
    )
    expma_12_qfq = tushare_float_field(
        "EMA指数平均数指标-CLOSE, N1=12, N2=50", db_comment="EMA指数平均数指标-CLOSE, N1=12, N2=50"
    )
    expma_50_bfq = tushare_float_field(
        "EMA指数平均数指标-CLOSE, N1=12, N2=50", db_comment="EMA指数平均数指标-CLOSE, N1=12, N2=50"
    )
    expma_50_hfq = tushare_float_field(
        "EMA指数平均数指标-CLOSE, N1=12, N2=50", db_comment="EMA指数平均数指标-CLOSE, N1=12, N2=50"
    )
    expma_50_qfq = tushare_float_field(
        "EMA指数平均数指标-CLOSE, N1=12, N2=50", db_comment="EMA指数平均数指标-CLOSE, N1=12, N2=50"
    )
    kdj_bfq = tushare_float_field(
        "KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3", db_comment="KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3"
    )
    kdj_hfq = tushare_float_field(
        "KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3", db_comment="KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3"
    )
    kdj_qfq = tushare_float_field(
        "KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3", db_comment="KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3"
    )
    kdj_d_bfq = tushare_float_field(
        "KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3", db_comment="KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3"
    )
    kdj_d_hfq = tushare_float_field(
        "KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3", db_comment="KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3"
    )
    kdj_d_qfq = tushare_float_field(
        "KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3", db_comment="KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3"
    )
    kdj_k_bfq = tushare_float_field(
        "KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3", db_comment="KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3"
    )
    kdj_k_hfq = tushare_float_field(
        "KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3", db_comment="KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3"
    )
    kdj_k_qfq = tushare_float_field(
        "KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3", db_comment="KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3"
    )
    ktn_down_bfq = tushare_float_field(
        "肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
        db_comment="肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
    )
    ktn_down_hfq = tushare_float_field(
        "肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
        db_comment="肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
    )
    ktn_down_qfq = tushare_float_field(
        "肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
        db_comment="肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
    )
    ktn_mid_bfq = tushare_float_field(
        "肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
        db_comment="肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
    )
    ktn_mid_hfq = tushare_float_field(
        "肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
        db_comment="肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
    )
    ktn_mid_qfq = tushare_float_field(
        "肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
        db_comment="肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
    )
    ktn_upper_bfq = tushare_float_field(
        "肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
        db_comment="肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
    )
    ktn_upper_hfq = tushare_float_field(
        "肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
        db_comment="肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
    )
    ktn_upper_qfq = tushare_float_field(
        "肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
        db_comment="肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10",
    )
    lowdays = tushare_float_field(
        "LOWRANGE(LOW)表示当前最低价是近多少周期内最低价的最小值",
        db_comment="LOWRANGE(LOW)表示当前最低价是近多少周期内最低价的最小值",
    )
    topdays = tushare_float_field(
        "TOPRANGE(HIGH)表示当前最高价是近多少周期内最高价的最大值",
        db_comment="TOPRANGE(HIGH)表示当前最高价是近多少周期内最高价的最大值",
    )
    ma_bfq_10 = tushare_float_field("简单移动平均-N=10", db_comment="简单移动平均-N=10")
    ma_bfq_20 = tushare_float_field("简单移动平均-N=20", db_comment="简单移动平均-N=20")
    ma_bfq_250 = tushare_float_field("简单移动平均-N=250", db_comment="简单移动平均-N=250")
    ma_bfq_30 = tushare_float_field("简单移动平均-N=30", db_comment="简单移动平均-N=30")
    ma_bfq_5 = tushare_float_field("简单移动平均-N=5", db_comment="简单移动平均-N=5")
    ma_bfq_60 = tushare_float_field("简单移动平均-N=60", db_comment="简单移动平均-N=60")
    ma_bfq_90 = tushare_float_field("简单移动平均-N=90", db_comment="简单移动平均-N=90")
    ma_hfq_10 = tushare_float_field("简单移动平均-N=10", db_comment="简单移动平均-N=10")
    ma_hfq_20 = tushare_float_field("简单移动平均-N=20", db_comment="简单移动平均-N=20")
    ma_hfq_250 = tushare_float_field("简单移动平均-N=250", db_comment="简单移动平均-N=250")
    ma_hfq_30 = tushare_float_field("简单移动平均-N=30", db_comment="简单移动平均-N=30")
    ma_hfq_5 = tushare_float_field("简单移动平均-N=5", db_comment="简单移动平均-N=5")
    ma_hfq_60 = tushare_float_field("简单移动平均-N=60", db_comment="简单移动平均-N=60")
    ma_hfq_90 = tushare_float_field("简单移动平均-N=90", db_comment="简单移动平均-N=90")
    ma_qfq_10 = tushare_float_field("简单移动平均-N=10", db_comment="简单移动平均-N=10")
    ma_qfq_20 = tushare_float_field("简单移动平均-N=20", db_comment="简单移动平均-N=20")
    ma_qfq_250 = tushare_float_field("简单移动平均-N=250", db_comment="简单移动平均-N=250")
    ma_qfq_30 = tushare_float_field("简单移动平均-N=30", db_comment="简单移动平均-N=30")
    ma_qfq_5 = tushare_float_field("简单移动平均-N=5", db_comment="简单移动平均-N=5")
    ma_qfq_60 = tushare_float_field("简单移动平均-N=60", db_comment="简单移动平均-N=60")
    ma_qfq_90 = tushare_float_field("简单移动平均-N=90", db_comment="简单移动平均-N=90")
    macd_bfq = tushare_float_field(
        "MACD指标-CLOSE, SHORT=12, LONG=26, M=9", db_comment="MACD指标-CLOSE, SHORT=12, LONG=26, M=9"
    )
    macd_hfq = tushare_float_field(
        "MACD指标-CLOSE, SHORT=12, LONG=26, M=9", db_comment="MACD指标-CLOSE, SHORT=12, LONG=26, M=9"
    )
    macd_qfq = tushare_float_field(
        "MACD指标-CLOSE, SHORT=12, LONG=26, M=9", db_comment="MACD指标-CLOSE, SHORT=12, LONG=26, M=9"
    )
    macd_dea_bfq = tushare_float_field(
        "MACD指标-CLOSE, SHORT=12, LONG=26, M=9", db_comment="MACD指标-CLOSE, SHORT=12, LONG=26, M=9"
    )
    macd_dea_hfq = tushare_float_field(
        "MACD指标-CLOSE, SHORT=12, LONG=26, M=9", db_comment="MACD指标-CLOSE, SHORT=12, LONG=26, M=9"
    )
    macd_dea_qfq = tushare_float_field(
        "MACD指标-CLOSE, SHORT=12, LONG=26, M=9", db_comment="MACD指标-CLOSE, SHORT=12, LONG=26, M=9"
    )
    macd_dif_bfq = tushare_float_field(
        "MACD指标-CLOSE, SHORT=12, LONG=26, M=9", db_comment="MACD指标-CLOSE, SHORT=12, LONG=26, M=9"
    )
    macd_dif_hfq = tushare_float_field(
        "MACD指标-CLOSE, SHORT=12, LONG=26, M=9", db_comment="MACD指标-CLOSE, SHORT=12, LONG=26, M=9"
    )
    macd_dif_qfq = tushare_float_field(
        "MACD指标-CLOSE, SHORT=12, LONG=26, M=9", db_comment="MACD指标-CLOSE, SHORT=12, LONG=26, M=9"
    )
    mass_bfq = tushare_float_field(
        "梅斯线-HIGH, LOW, N1=9, N2=25, M=6", db_comment="梅斯线-HIGH, LOW, N1=9, N2=25, M=6"
    )
    mass_hfq = tushare_float_field(
        "梅斯线-HIGH, LOW, N1=9, N2=25, M=6", db_comment="梅斯线-HIGH, LOW, N1=9, N2=25, M=6"
    )
    mass_qfq = tushare_float_field(
        "梅斯线-HIGH, LOW, N1=9, N2=25, M=6", db_comment="梅斯线-HIGH, LOW, N1=9, N2=25, M=6"
    )
    ma_mass_bfq = tushare_float_field(
        "梅斯线-HIGH, LOW, N1=9, N2=25, M=6", db_comment="梅斯线-HIGH, LOW, N1=9, N2=25, M=6"
    )
    ma_mass_hfq = tushare_float_field(
        "梅斯线-HIGH, LOW, N1=9, N2=25, M=6", db_comment="梅斯线-HIGH, LOW, N1=9, N2=25, M=6"
    )
    ma_mass_qfq = tushare_float_field(
        "梅斯线-HIGH, LOW, N1=9, N2=25, M=6", db_comment="梅斯线-HIGH, LOW, N1=9, N2=25, M=6"
    )
    mfi_bfq = tushare_float_field(
        "MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14",
        db_comment="MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14",
    )
    mfi_hfq = tushare_float_field(
        "MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14",
        db_comment="MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14",
    )
    mfi_qfq = tushare_float_field(
        "MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14",
        db_comment="MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14",
    )
    mtm_bfq = tushare_float_field("动量指标-CLOSE, N=12, M=6", db_comment="动量指标-CLOSE, N=12, M=6")
    mtm_hfq = tushare_float_field("动量指标-CLOSE, N=12, M=6", db_comment="动量指标-CLOSE, N=12, M=6")
    mtm_qfq = tushare_float_field("动量指标-CLOSE, N=12, M=6", db_comment="动量指标-CLOSE, N=12, M=6")
    mtmma_bfq = tushare_float_field("动量指标-CLOSE, N=12, M=6", db_comment="动量指标-CLOSE, N=12, M=6")
    mtmma_hfq = tushare_float_field("动量指标-CLOSE, N=12, M=6", db_comment="动量指标-CLOSE, N=12, M=6")
    mtmma_qfq = tushare_float_field("动量指标-CLOSE, N=12, M=6", db_comment="动量指标-CLOSE, N=12, M=6")
    obv_bfq = tushare_float_field("能量潮指标-CLOSE, VOL", db_comment="能量潮指标-CLOSE, VOL")
    obv_hfq = tushare_float_field("能量潮指标-CLOSE, VOL", db_comment="能量潮指标-CLOSE, VOL")
    obv_qfq = tushare_float_field("能量潮指标-CLOSE, VOL", db_comment="能量潮指标-CLOSE, VOL")
    psy_bfq = tushare_float_field(
        "投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6",
        db_comment="投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6",
    )
    psy_hfq = tushare_float_field(
        "投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6",
        db_comment="投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6",
    )
    psy_qfq = tushare_float_field(
        "投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6",
        db_comment="投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6",
    )
    psyma_bfq = tushare_float_field(
        "投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6",
        db_comment="投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6",
    )
    psyma_hfq = tushare_float_field(
        "投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6",
        db_comment="投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6",
    )
    psyma_qfq = tushare_float_field(
        "投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6",
        db_comment="投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6",
    )
    roc_bfq = tushare_float_field("变动率指标-CLOSE, N=12, M=6", db_comment="变动率指标-CLOSE, N=12, M=6")
    roc_hfq = tushare_float_field("变动率指标-CLOSE, N=12, M=6", db_comment="变动率指标-CLOSE, N=12, M=6")
    roc_qfq = tushare_float_field("变动率指标-CLOSE, N=12, M=6", db_comment="变动率指标-CLOSE, N=12, M=6")
    maroc_bfq = tushare_float_field("变动率指标-CLOSE, N=12, M=6", db_comment="变动率指标-CLOSE, N=12, M=6")
    maroc_hfq = tushare_float_field("变动率指标-CLOSE, N=12, M=6", db_comment="变动率指标-CLOSE, N=12, M=6")
    maroc_qfq = tushare_float_field("变动率指标-CLOSE, N=12, M=6", db_comment="变动率指标-CLOSE, N=12, M=6")
    rsi_bfq_12 = tushare_float_field("RSI指标-CLOSE, N=12", db_comment="RSI指标-CLOSE, N=12")
    rsi_bfq_24 = tushare_float_field("RSI指标-CLOSE, N=24", db_comment="RSI指标-CLOSE, N=24")
    rsi_bfq_6 = tushare_float_field("RSI指标-CLOSE, N=6", db_comment="RSI指标-CLOSE, N=6")
    rsi_hfq_12 = tushare_float_field("RSI指标-CLOSE, N=12", db_comment="RSI指标-CLOSE, N=12")
    rsi_hfq_24 = tushare_float_field("RSI指标-CLOSE, N=24", db_comment="RSI指标-CLOSE, N=24")
    rsi_hfq_6 = tushare_float_field("RSI指标-CLOSE, N=6", db_comment="RSI指标-CLOSE, N=6")
    rsi_qfq_12 = tushare_float_field("RSI指标-CLOSE, N=12", db_comment="RSI指标-CLOSE, N=12")
    rsi_qfq_24 = tushare_float_field("RSI指标-CLOSE, N=24", db_comment="RSI指标-CLOSE, N=24")
    rsi_qfq_6 = tushare_float_field("RSI指标-CLOSE, N=6", db_comment="RSI指标-CLOSE, N=6")
    taq_down_bfq = tushare_float_field(
        "唐安奇通道(海龟)交易指标-HIGH, LOW, 20", db_comment="唐安奇通道(海龟)交易指标-HIGH, LOW, 20"
    )
    taq_down_hfq = tushare_float_field(
        "唐安奇通道(海龟)交易指标-HIGH, LOW, 20", db_comment="唐安奇通道(海龟)交易指标-HIGH, LOW, 20"
    )
    taq_down_qfq = tushare_float_field(
        "唐安奇通道(海龟)交易指标-HIGH, LOW, 20", db_comment="唐安奇通道(海龟)交易指标-HIGH, LOW, 20"
    )
    taq_mid_bfq = tushare_float_field(
        "唐安奇通道(海龟)交易指标-HIGH, LOW, 20", db_comment="唐安奇通道(海龟)交易指标-HIGH, LOW, 20"
    )
    taq_mid_hfq = tushare_float_field(
        "唐安奇通道(海龟)交易指标-HIGH, LOW, 20", db_comment="唐安奇通道(海龟)交易指标-HIGH, LOW, 20"
    )
    taq_mid_qfq = tushare_float_field(
        "唐安奇通道(海龟)交易指标-HIGH, LOW, 20", db_comment="唐安奇通道(海龟)交易指标-HIGH, LOW, 20"
    )
    taq_up_bfq = tushare_float_field(
        "唐安奇通道(海龟)交易指标-HIGH, LOW, 20", db_comment="唐安奇通道(海龟)交易指标-HIGH, LOW, 20"
    )
    taq_up_hfq = tushare_float_field(
        "唐安奇通道(海龟)交易指标-HIGH, LOW, 20", db_comment="唐安奇通道(海龟)交易指标-HIGH, LOW, 20"
    )
    taq_up_qfq = tushare_float_field(
        "唐安奇通道(海龟)交易指标-HIGH, LOW, 20", db_comment="唐安奇通道(海龟)交易指标-HIGH, LOW, 20"
    )
    trix_bfq = tushare_float_field(
        "三重指数平滑平均线-CLOSE, M1=12, M2=20", db_comment="三重指数平滑平均线-CLOSE, M1=12, M2=20"
    )
    trix_hfq = tushare_float_field(
        "三重指数平滑平均线-CLOSE, M1=12, M2=20", db_comment="三重指数平滑平均线-CLOSE, M1=12, M2=20"
    )
    trix_qfq = tushare_float_field(
        "三重指数平滑平均线-CLOSE, M1=12, M2=20", db_comment="三重指数平滑平均线-CLOSE, M1=12, M2=20"
    )
    trma_bfq = tushare_float_field(
        "三重指数平滑平均线-CLOSE, M1=12, M2=20", db_comment="三重指数平滑平均线-CLOSE, M1=12, M2=20"
    )
    trma_hfq = tushare_float_field(
        "三重指数平滑平均线-CLOSE, M1=12, M2=20", db_comment="三重指数平滑平均线-CLOSE, M1=12, M2=20"
    )
    trma_qfq = tushare_float_field(
        "三重指数平滑平均线-CLOSE, M1=12, M2=20", db_comment="三重指数平滑平均线-CLOSE, M1=12, M2=20"
    )
    vr_bfq = tushare_float_field("VR容量比率-CLOSE, VOL, M1=26", db_comment="VR容量比率-CLOSE, VOL, M1=26")
    vr_hfq = tushare_float_field("VR容量比率-CLOSE, VOL, M1=26", db_comment="VR容量比率-CLOSE, VOL, M1=26")
    vr_qfq = tushare_float_field("VR容量比率-CLOSE, VOL, M1=26", db_comment="VR容量比率-CLOSE, VOL, M1=26")
    wr_bfq = tushare_float_field(
        "W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6", db_comment="W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6"
    )
    wr_hfq = tushare_float_field(
        "W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6", db_comment="W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6"
    )
    wr_qfq = tushare_float_field(
        "W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6", db_comment="W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6"
    )
    wr1_bfq = tushare_float_field(
        "W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6", db_comment="W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6"
    )
    wr1_hfq = tushare_float_field(
        "W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6", db_comment="W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6"
    )
    wr1_qfq = tushare_float_field(
        "W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6", db_comment="W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6"
    )
    xsii_td1_bfq = tushare_float_field(
        "薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7", db_comment="薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7"
    )
    xsii_td1_hfq = tushare_float_field(
        "薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7", db_comment="薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7"
    )
    xsii_td1_qfq = tushare_float_field(
        "薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7", db_comment="薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7"
    )
    xsii_td2_bfq = tushare_float_field(
        "薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7", db_comment="薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7"
    )
    xsii_td2_hfq = tushare_float_field(
        "薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7", db_comment="薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7"
    )
    xsii_td2_qfq = tushare_float_field(
        "薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7", db_comment="薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7"
    )
    xsii_td3_bfq = tushare_float_field(
        "薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7", db_comment="薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7"
    )
    xsii_td3_hfq = tushare_float_field(
        "薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7", db_comment="薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7"
    )
    xsii_td3_qfq = tushare_float_field(
        "薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7", db_comment="薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7"
    )
    xsii_td4_bfq = tushare_float_field(
        "薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7", db_comment="薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7"
    )
    xsii_td4_hfq = tushare_float_field(
        "薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7", db_comment="薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7"
    )
    xsii_td4_qfq = tushare_float_field(
        "薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7", db_comment="薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7"
    )
    tushare_meta = models.JSONField("TuShare???", default=dict, blank=True, db_comment="TuShare????????????")

    class Meta:
        db_table = "tushare_stk_factor_pro"
        db_table_comment = "TuShare??????????"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date"], name="uniq_stk_factor_pro"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "ts_code"], name="ix_stk_factor_pro_1"),
            models.Index(fields=["ts_code", "trade_date"], name="ix_stk_factor_pro_2"),
        ]


class MarginSummary(TimestampedModel):
    trade_date = tushare_char_field("交易日期", max_length=8)
    exchange_id = tushare_char_field("交易所代码（SSE上交所SZSE深交所BSE北交所）", max_length=16)
    rzye = tushare_float_field("融资余额(元)", db_comment="融资余额(元)")
    rzmre = tushare_float_field("融资买入额(元)", db_comment="融资买入额(元)")
    rzche = tushare_float_field("融资偿还额(元)", db_comment="融资偿还额(元)")
    rqye = tushare_float_field("融券余额(元)", db_comment="融券余额(元)")
    rqmcl = tushare_float_field("融券卖出量(股,份,手)", db_comment="融券卖出量(股,份,手)")
    rzrqye = tushare_float_field("融资融券余额(元)", db_comment="融资融券余额(元)")
    rqyl = tushare_float_field("融券余量(股,份,手)", db_comment="融券余量(股,份,手)")
    tushare_meta = models.JSONField("TuShare???", default=dict, blank=True, db_comment="TuShare????????????")

    class Meta:
        db_table = "tushare_margin"
        db_table_comment = "TuShare????????"
        constraints = [
            models.UniqueConstraint(fields=["trade_date", "exchange_id"], name="uniq_margin"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "exchange_id"], name="ix_margin_1"),
        ]


class PledgeDetail(TimestampedModel):
    ts_code = tushare_char_field("TS股票代码", max_length=24)
    ann_date = tushare_char_field("公告日期", max_length=8)
    holder_name = tushare_char_field("股东名称", max_length=240)
    pledge_amount = tushare_float_field("质押数量（万股）", db_comment="质押数量（万股）")
    start_date = tushare_char_field("质押开始日期", max_length=8)
    end_date = tushare_char_field("质押结束日期", max_length=8)
    is_release = tushare_char_field("是否已解押", max_length=8)
    release_date = tushare_char_field("解押日期", max_length=8)
    pledgor = tushare_char_field("质押方", max_length=240)
    holding_amount = tushare_float_field("持股总数（万股）", db_comment="持股总数（万股）")
    pledged_amount = tushare_float_field("质押总数（万股）", db_comment="质押总数（万股）")
    p_total_ratio = tushare_float_field("本次质押占总股本比例", db_comment="本次质押占总股本比例")
    h_total_ratio = tushare_float_field("持股总数占总股本比例", db_comment="持股总数占总股本比例")
    is_buyback = tushare_char_field("是否回购（0否 1是）", max_length=120)
    tushare_meta = models.JSONField("TuShare???", default=dict, blank=True, db_comment="TuShare????????????")

    class Meta:
        db_table = "tushare_pledge_detail"
        db_table_comment = "TuShare??????"
        constraints = [
            models.UniqueConstraint(
                fields=["ts_code", "ann_date", "holder_name", "start_date"], name="uniq_pledge_detail"
            ),
        ]
        indexes = [
            models.Index(fields=["ann_date", "ts_code"], name="ix_pledge_detail_1"),
            models.Index(fields=["ts_code", "start_date"], name="ix_pledge_detail_2"),
        ]


class PerformanceForecast(TimestampedModel):
    ts_code = tushare_char_field("TS股票代码", max_length=24)
    ann_date = tushare_char_field("公告日期", max_length=8)
    end_date = tushare_char_field("报告期", max_length=8)
    type = tushare_char_field("业绩预告类型(预增/预减/扭亏/首亏/续亏/续盈/略增/略减)", max_length=80)
    p_change_min = tushare_float_field("预告净利润变动幅度下限（%）", db_comment="预告净利润变动幅度下限（%）")
    p_change_max = tushare_float_field("预告净利润变动幅度上限（%）", db_comment="预告净利润变动幅度上限（%）")
    net_profit_min = tushare_float_field("预告净利润下限（万元）", db_comment="预告净利润下限（万元）")
    net_profit_max = tushare_float_field("预告净利润上限（万元）", db_comment="预告净利润上限（万元）")
    last_parent_net = tushare_float_field("上年同期归属母公司净利润", db_comment="上年同期归属母公司净利润")
    first_ann_date = tushare_char_field("首次公告日", max_length=8)
    summary = models.TextField("业绩预告摘要", blank=True, null=True, db_comment="业绩预告摘要")
    change_reason = models.TextField("业绩变动原因", blank=True, null=True, db_comment="业绩变动原因")
    tushare_meta = models.JSONField("TuShare???", default=dict, blank=True, db_comment="TuShare????????????")

    class Meta:
        db_table = "tushare_forecast"
        db_table_comment = "TuShare????"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "ann_date", "end_date", "type"], name="uniq_forecast"),
        ]
        indexes = [
            models.Index(fields=["ann_date", "ts_code"], name="ix_forecast_1"),
            models.Index(fields=["ts_code", "end_date"], name="ix_forecast_2"),
        ]


class PerformanceExpress(TimestampedModel):
    ts_code = tushare_char_field("TS股票代码", max_length=24)
    ann_date = tushare_char_field("公告日期", max_length=8)
    end_date = tushare_char_field("报告期", max_length=8)
    revenue = tushare_float_field("营业收入(元)", db_comment="营业收入(元)")
    operate_profit = tushare_float_field("营业利润(元)", db_comment="营业利润(元)")
    total_profit = tushare_float_field("利润总额(元)", db_comment="利润总额(元)")
    n_income = tushare_float_field("净利润(元)", db_comment="净利润(元)")
    total_assets = tushare_float_field("总资产(元)", db_comment="总资产(元)")
    total_hldr_eqy_exc_min_int = tushare_float_field(
        "股东权益合计(不含少数股东权益)(元)", db_comment="股东权益合计(不含少数股东权益)(元)"
    )
    diluted_eps = tushare_float_field("每股收益(摊薄)(元)", db_comment="每股收益(摊薄)(元)")
    diluted_roe = tushare_float_field("净资产收益率(摊薄)(%)", db_comment="净资产收益率(摊薄)(%)")
    yoy_net_profit = tushare_float_field("去年同期修正后净利润", db_comment="去年同期修正后净利润")
    bps = tushare_float_field("每股净资产", db_comment="每股净资产")
    yoy_sales = tushare_float_field("同比增长率:营业收入", db_comment="同比增长率:营业收入")
    yoy_op = tushare_float_field("同比增长率:营业利润", db_comment="同比增长率:营业利润")
    yoy_tp = tushare_float_field("同比增长率:利润总额", db_comment="同比增长率:利润总额")
    yoy_dedu_np = tushare_float_field(
        "同比增长率:归属母公司股东的净利润", db_comment="同比增长率:归属母公司股东的净利润"
    )
    yoy_eps = tushare_float_field("同比增长率:基本每股收益", db_comment="同比增长率:基本每股收益")
    yoy_roe = tushare_float_field("同比增减:加权平均净资产收益率", db_comment="同比增减:加权平均净资产收益率")
    growth_assets = tushare_float_field("比年初增长率:总资产", db_comment="比年初增长率:总资产")
    yoy_equity = tushare_float_field(
        "比年初增长率:归属母公司的股东权益", db_comment="比年初增长率:归属母公司的股东权益"
    )
    growth_bps = tushare_float_field(
        "比年初增长率:归属于母公司股东的每股净资产", db_comment="比年初增长率:归属于母公司股东的每股净资产"
    )
    or_last_year = tushare_float_field("去年同期营业收入", db_comment="去年同期营业收入")
    op_last_year = tushare_float_field("去年同期营业利润", db_comment="去年同期营业利润")
    tp_last_year = tushare_float_field("去年同期利润总额", db_comment="去年同期利润总额")
    np_last_year = tushare_float_field("去年同期净利润", db_comment="去年同期净利润")
    eps_last_year = tushare_float_field("去年同期每股收益", db_comment="去年同期每股收益")
    open_net_assets = tushare_float_field("期初净资产", db_comment="期初净资产")
    open_bps = tushare_float_field("期初每股净资产", db_comment="期初每股净资产")
    perf_summary = tushare_char_field("业绩简要说明", max_length=120)
    is_audit = models.IntegerField("是否审计： 1是 0否", blank=True, null=True, db_comment="是否审计： 1是 0否")
    remark = tushare_char_field("备注", max_length=120)
    tushare_meta = models.JSONField("TuShare???", default=dict, blank=True, db_comment="TuShare????????????")

    class Meta:
        db_table = "tushare_express"
        db_table_comment = "TuShare????"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "ann_date", "end_date"], name="uniq_express"),
        ]
        indexes = [
            models.Index(fields=["ann_date", "ts_code"], name="ix_express_1"),
            models.Index(fields=["ts_code", "end_date"], name="ix_express_2"),
        ]


class BlockTrade(TimestampedModel):
    ts_code = tushare_char_field("TS代码", max_length=24)
    trade_date = tushare_char_field("交易日历", max_length=8)
    price = tushare_float_field("成交价", db_comment="成交价")
    vol = tushare_float_field("成交量（万股）", db_comment="成交量（万股）")
    amount = tushare_float_field("成交金额", db_comment="成交金额")
    buyer = tushare_char_field("买方营业部", max_length=240)
    seller = tushare_char_field("卖方营业部", max_length=240)
    tushare_meta = models.JSONField("TuShare???", default=dict, blank=True, db_comment="TuShare????????????")

    class Meta:
        db_table = "tushare_block_trade"
        db_table_comment = "TuShare????"
        constraints = [
            models.UniqueConstraint(
                fields=["ts_code", "trade_date", "price", "vol", "buyer", "seller"], name="uniq_block_trade"
            ),
        ]
        indexes = [
            models.Index(fields=["trade_date", "ts_code"], name="ix_block_trade_1"),
            models.Index(fields=["ts_code", "trade_date"], name="ix_block_trade_2"),
        ]


class TopList(TimestampedModel):
    pct_change = tushare_float_field("涨跌幅")
    turnover_rate = tushare_float_field("换手率")
    l_sell = tushare_float_field("龙虎榜卖出额")
    l_buy = tushare_float_field("龙虎榜买入额")
    l_amount = tushare_float_field("龙虎榜成交额")
    net_rate = tushare_float_field("净买入额占总成交比例")
    amount_rate = tushare_float_field("成交额占总成交比例")
    float_values = tushare_float_field("流通市值")
    reason = models.TextField("上榜理由", blank=True, null=True, db_comment="上榜理由")
    trade_date = tushare_char_field("交易日期", max_length=8)
    ts_code = tushare_char_field("股票代码", max_length=24)
    name = tushare_char_field("股票名称", max_length=120)
    close = tushare_float_field("收盘价", db_comment="收盘价")
    change = tushare_float_field("涨跌额", db_comment="涨跌额")
    rank = models.IntegerField("资金排名", blank=True, null=True, db_comment="资金排名")
    market_type = tushare_char_field("市场类型（1：沪市 3：深市）", max_length=16)
    amount = tushare_float_field("成交金额（元）", db_comment="成交金额（元）")
    net_amount = tushare_float_field("净成交金额（元）", db_comment="净成交金额（元）")
    buy = tushare_float_field("买入金额（元）", db_comment="买入金额（元）")
    sell = tushare_float_field("卖出金额（元）", db_comment="卖出金额（元）")
    tushare_meta = models.JSONField("TuShare???", default=dict, blank=True, db_comment="TuShare????????????")

    class Meta:
        db_table = "tushare_top_list"
        db_table_comment = "TuShare?????????"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date", "reason"], name="uniq_top_list"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "ts_code"], name="ix_top_list_1"),
            models.Index(fields=["ts_code", "trade_date"], name="ix_top_list_2"),
        ]


class TopInst(TimestampedModel):
    exalter = tushare_char_field("营业部名称", max_length=240)
    buy = tushare_float_field("买入额")
    buy_rate = tushare_float_field("买入占比")
    sell = tushare_float_field("卖出额")
    sell_rate = tushare_float_field("卖出占比")
    net_buy = tushare_float_field("净买入额")
    side = tushare_char_field("买卖类型", max_length=16)
    reason = models.TextField("上榜理由", blank=True, null=True, db_comment="上榜理由")
    trade_date = tushare_char_field("交易日期", max_length=8)
    ts_code = tushare_char_field("股票代码", max_length=24)
    name = tushare_char_field("股票名称", max_length=120)
    close = tushare_float_field("收盘价", db_comment="收盘价")
    p_change = tushare_float_field("涨跌幅", db_comment="涨跌幅")
    rank = models.IntegerField("资金排名", blank=True, null=True, db_comment="资金排名")
    market_type = tushare_char_field("市场类型 2：港股通（沪） 4：港股通（深）", max_length=16)
    amount = tushare_float_field("累计成交金额（元）", db_comment="累计成交金额（元）")
    net_amount = tushare_float_field("净买入金额（元）", db_comment="净买入金额（元）")
    sh_amount = tushare_float_field("沪市成交金额（元）", db_comment="沪市成交金额（元）")
    sh_net_amount = tushare_float_field("沪市净买入金额（元）", db_comment="沪市净买入金额（元）")
    sh_buy = tushare_float_field("沪市买入金额（元）", db_comment="沪市买入金额（元）")
    sh_sell = tushare_float_field("沪市卖出金额", db_comment="沪市卖出金额")
    sz_amount = tushare_float_field("深市成交金额（元）", db_comment="深市成交金额（元）")
    sz_net_amount = tushare_float_field("深市净买入金额（元）", db_comment="深市净买入金额（元）")
    sz_buy = tushare_float_field("深市买入金额（元）", db_comment="深市买入金额（元）")
    sz_sell = tushare_float_field("深市卖出金额（元）", db_comment="深市卖出金额（元）")
    tushare_meta = models.JSONField("TuShare???", default=dict, blank=True, db_comment="TuShare????????????")

    class Meta:
        db_table = "tushare_top_inst"
        db_table_comment = "TuShare???????"
        constraints = [
            models.UniqueConstraint(
                fields=["ts_code", "trade_date", "exalter", "side", "reason"], name="uniq_top_inst"
            ),
        ]
        indexes = [
            models.Index(fields=["trade_date", "ts_code"], name="ix_top_inst_1"),
            models.Index(fields=["ts_code", "trade_date"], name="ix_top_inst_2"),
        ]


class Dividend(TimestampedModel):
    ts_code = tushare_char_field("TS代码", max_length=24)
    end_date = tushare_char_field("分红年度", max_length=8)
    ann_date = tushare_char_field("预案公告日", max_length=8)
    div_proc = tushare_char_field("实施进度", max_length=80)
    stk_div = tushare_float_field("每股送转", db_comment="每股送转")
    stk_bo_rate = tushare_float_field("每股送股比例", db_comment="每股送股比例")
    stk_co_rate = tushare_float_field("每股转增比例", db_comment="每股转增比例")
    cash_div = tushare_float_field("每股分红（税后）", db_comment="每股分红（税后）")
    cash_div_tax = tushare_float_field("每股分红（税前）", db_comment="每股分红（税前）")
    record_date = tushare_char_field("股权登记日", max_length=8)
    ex_date = tushare_char_field("除权除息日", max_length=8)
    pay_date = tushare_char_field("派息日", max_length=8)
    div_listdate = tushare_char_field("红股上市日", max_length=120)
    imp_ann_date = tushare_char_field("实施公告日", max_length=8)
    base_date = tushare_char_field("基准日", max_length=120)
    base_share = tushare_float_field("基准股本（万）", db_comment="基准股本（万）")
    tushare_meta = models.JSONField("TuShare???", default=dict, blank=True, db_comment="TuShare????????????")

    class Meta:
        db_table = "tushare_dividend"
        db_table_comment = "TuShare????"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "end_date", "ann_date", "div_proc"], name="uniq_dividend"),
        ]
        indexes = [
            models.Index(fields=["ann_date", "ts_code"], name="ix_dividend_1"),
            models.Index(fields=["record_date", "ts_code"], name="ix_dividend_2"),
            models.Index(fields=["ex_date", "ts_code"], name="ix_dividend_3"),
        ]


class Repurchase(TimestampedModel):
    ts_code = tushare_char_field("TS代码", max_length=24)
    ann_date = tushare_char_field("公告日期", max_length=8)
    end_date = tushare_char_field("截止日期", max_length=8)
    proc = tushare_char_field("进度", max_length=80)
    exp_date = tushare_char_field("过期日期", max_length=8)
    vol = tushare_float_field("回购数量", db_comment="回购数量")
    amount = tushare_float_field("回购金额", db_comment="回购金额")
    high_limit = tushare_float_field("回购最高价", db_comment="回购最高价")
    low_limit = tushare_float_field("回购最低价", db_comment="回购最低价")
    tushare_meta = models.JSONField("TuShare???", default=dict, blank=True, db_comment="TuShare????????????")

    class Meta:
        db_table = "tushare_repurchase"
        db_table_comment = "TuShare????"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "ann_date", "end_date", "proc"], name="uniq_repurchase"),
        ]
        indexes = [
            models.Index(fields=["ann_date", "ts_code"], name="ix_repurchase_1"),
            models.Index(fields=["ts_code", "end_date"], name="ix_repurchase_2"),
        ]


class SyncJob(TimestampedModel):
    name = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=24)
    start_date = models.CharField(max_length=8, blank=True, null=True)
    end_date = models.CharField(max_length=8, blank=True, null=True)
    current_date = models.CharField(max_length=8, blank=True, default="")
    current_step = models.CharField(max_length=40, blank=True, default="")
    processed_dates = models.IntegerField(default=0)
    message = models.TextField(blank=True, default="")

    class Meta:
        db_table = "system_sync_jobs"


class ModelDailyRollingFeature(TimestampedModel):
    ts_code = models.CharField(max_length=24)
    trade_date = models.CharField(max_length=8)
    ma20 = models.FloatField(blank=True, null=True)
    ma60 = models.FloatField(blank=True, null=True)
    vol_20 = models.FloatField(blank=True, null=True)
    amount_ma20 = models.FloatField(blank=True, null=True)

    class Meta:
        db_table = "model_daily_rolling_features"
        db_table_comment = "Daily rolling features for quant model samples"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date"], name="uniq_model_daily_rolling_feature"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "ts_code"], name="ix_model_roll_date_code"),
            models.Index(fields=["ts_code", "trade_date"], name="ix_model_roll_code_date"),
        ]


class ModelSampleV1(TimestampedModel):
    ts_code = models.CharField(max_length=24)
    trade_date = models.CharField(max_length=8)
    stock_name = models.CharField(max_length=80, blank=True, null=True)
    industry = models.CharField(max_length=120, blank=True, null=True)
    list_date = models.CharField(max_length=8, blank=True, null=True)

    close = models.FloatField(blank=True, null=True)
    pct_chg = models.FloatField(blank=True, null=True)
    amount = models.FloatField(blank=True, null=True)
    adj_factor = models.FloatField(blank=True, null=True)
    turnover_rate = models.FloatField(blank=True, null=True)
    volume_ratio = models.FloatField(blank=True, null=True)
    pe_ttm = models.FloatField(blank=True, null=True)
    pb = models.FloatField(blank=True, null=True)
    ps_ttm = models.FloatField(blank=True, null=True)
    dv_ttm = models.FloatField(blank=True, null=True)
    total_mv = models.FloatField(blank=True, null=True)
    circ_mv = models.FloatField(blank=True, null=True)

    ret_5 = models.FloatField(blank=True, null=True)
    ret_20 = models.FloatField(blank=True, null=True)
    ret_60 = models.FloatField(blank=True, null=True)
    ma20_bias = models.FloatField(blank=True, null=True)
    ma60_bias = models.FloatField(blank=True, null=True)
    vol_20 = models.FloatField(blank=True, null=True)
    amount_ratio_20 = models.FloatField(blank=True, null=True)

    rsi_6 = models.FloatField(blank=True, null=True)
    rsi_12 = models.FloatField(blank=True, null=True)
    macd = models.FloatField(blank=True, null=True)
    macd_dif = models.FloatField(blank=True, null=True)
    macd_dea = models.FloatField(blank=True, null=True)
    kdj_k = models.FloatField(blank=True, null=True)
    kdj_d = models.FloatField(blank=True, null=True)
    kdj_j = models.FloatField(blank=True, null=True)
    boll_mid = models.FloatField(blank=True, null=True)
    boll_upper = models.FloatField(blank=True, null=True)
    boll_lower = models.FloatField(blank=True, null=True)

    roe = models.FloatField(blank=True, null=True)
    roa = models.FloatField(blank=True, null=True)
    grossprofit_margin = models.FloatField(blank=True, null=True)
    netprofit_margin = models.FloatField(blank=True, null=True)
    debt_to_assets = models.FloatField(blank=True, null=True)
    ocf_to_profit = models.FloatField(blank=True, null=True)
    revenue_yoy = models.FloatField(blank=True, null=True)
    netprofit_yoy = models.FloatField(blank=True, null=True)

    net_mf_amount = models.FloatField(blank=True, null=True)
    net_mf_amount_ratio = models.FloatField(blank=True, null=True)
    margin_balance = models.FloatField(blank=True, null=True)
    margin_buy_ratio = models.FloatField(blank=True, null=True)
    hk_hold_ratio = models.FloatField(blank=True, null=True)

    is_st = models.BooleanField(default=False)
    is_limit_up = models.BooleanField(default=False)
    is_limit_down = models.BooleanField(default=False)
    pledge_ratio = models.FloatField(blank=True, null=True)
    days_since_list = models.IntegerField(blank=True, null=True)

    benchmark_code = models.CharField(max_length=24, default="000300.SH")
    benchmark_ret_20 = models.FloatField(blank=True, null=True)
    future_ret_20 = models.FloatField(blank=True, null=True)
    future_excess_ret_20 = models.FloatField(blank=True, null=True)
    label_up_20 = models.BooleanField(blank=True, null=True)
    label_outperform_20 = models.BooleanField(blank=True, null=True)

    feature_version = models.CharField(max_length=24, default="v1")

    class Meta:
        db_table = "model_sample_v1"
        db_table_comment = "Quant diagnosis model sample table v1"
        constraints = [
            models.UniqueConstraint(fields=["ts_code", "trade_date", "feature_version"], name="uniq_model_sample_v1"),
        ]
        indexes = [
            models.Index(fields=["trade_date", "ts_code"], name="ix_model_sample_v1_date_code"),
            models.Index(fields=["ts_code", "trade_date"], name="ix_model_sample_v1_code_date"),
            models.Index(fields=["industry", "trade_date"], name="ix_model_sample_v1_ind_date"),
            models.Index(fields=["feature_version", "trade_date"], name="ix_model_sample_v1_ver_date"),
        ]
