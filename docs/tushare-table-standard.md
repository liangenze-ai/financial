# TuShare 表接入标准

本文档用于约束后续新增 TuShare 数据表的实现方式。新增接口、表、同步任务时，默认按本标准执行；如有例外，需要在代码或开发日志中说明原因。

## 接入前检查

新增 TuShare 接口前，必须先做 token 权限和返回字段验证：

- 使用项目本地 `backend/.env` 中的 `TUSHARE_TOKEN`。
- 使用最小查询范围验证接口可访问性，例如单个交易日、单只股票、单个交易所、单个类型。
- 只输出接口名、状态、行数、字段名和错误摘要，不输出 token，不打印大量业务数据。
- 如果接口无数据，需要换一个已知有数据的日期或股票再次验证，区分“无权限”和“查询窗口无数据”。
- 验证结果需要在最终说明或开发日志中记录。

## 模型标准

新增表必须使用 Django ORM model，并遵守以下规则：

- 表名使用 `tushare_` 前缀，尽量与 TuShare 接口名保持一致。
- 字段必须覆盖 TuShare 官方接口的全量字段，不只使用默认字段。
- 每个字段必须设置中文 `verbose_name`。
- PostgreSQL 字段必须设置中文 `db_comment`。
- 模型 `Meta` 必须设置 `db_table` 和 `db_table_comment`。
- 每个表保留 `tushare_meta = models.JSONField(...)`，记录 TuShare 分类、接口和目标表元数据。
- 日期字段如果来自 TuShare 的 `YYYYMMDD`，优先使用 `CharField(max_length=8)`，保持与现有同步逻辑一致。
- 数值字段按 TuShare 含义选择 `FloatField` 或 `IntegerField`；长文本使用 `TextField`。
- TuShare 官方字段拼写如果存在历史拼写问题，入库字段名默认保持官方字段名，必要时用注释说明，例如 `st_tpye`。

### 字段注释标准

字段的 `verbose_name` 和 `db_comment` 必须使用 TuShare 官方接口文档“输出参数”表中的“描述”内容，不能只写字段名，也不能写“接口字段 xxx”“TuShare字段 xxx”这类占位说明。

例如，`fina_indicator` 接口中：

```python
eps = models.FloatField('基本每股收益', blank=True, null=True, db_comment='基本每股收益')
total_revenue_ps = models.FloatField('每股营业总收入', blank=True, null=True, db_comment='每股营业总收入')
```

不应写成：

```python
eps = models.FloatField('财务指标字段 eps', blank=True, null=True, db_comment='财务指标接口字段 eps')
total_revenue_ps = models.FloatField('TuShare字段 total_revenue_ps', blank=True, null=True, db_comment='TuShare字段 total_revenue_ps')
```

如果官方描述中包含单位、百分号或括号，应尽量原样保留，例如 `小单买入量（手）`、`基本每股收益同比增长率(%)`。如果某个字段在当前官方文档中没有描述，但接口实际返回该字段，需要在代码注释或开发日志中说明来源，并暂时使用清晰的中文业务说明。

## 约束与索引标准

每张表必须按同步主键和查询场景设计唯一约束与索引：

- 股票维表通常用 `ts_code` 唯一或作为主查询索引。
- 日频/交易日数据通常使用 `ts_code + trade_date` 唯一约束。
- 分类名单类数据通常使用 `ts_code + trade_date + type` 唯一约束。
- 公告/历史类数据通常使用 `ts_code + pub_date + type` 或 `ts_code + name + start_date` 作为幂等键。
- 常用筛选字段需要建立组合索引，例如 `trade_date + type`、`list_status + exchange`、`industry + area`。
- 历史变更表需要支持按股票、字段、来源日期查询，例如 `ts_code + created_at`、`field_name + created_at`、`source_date + ts_code`。
- 索引名必须短于 Django/数据库限制，建议使用 `ix_` 前缀和短表名，例如 `ix_stkb_status_market`。

## 同步标准

同步逻辑必须和现有 `stock_basic` 风格保持一致：清洗、补元数据、幂等 upsert、记录同步状态。

### 权限和字段

- 调接口时显式传入 `fields`，并且字段列表来自 `api.services.postgres.fields_for(...)`。
- 字段列表必须和 model 字段保持一致。
- 同步前用 `clean_record(...)` 清洗空值、`nan`、`NaT` 等值。
- 入库前用 `attach_catalog(...)` 或等效逻辑写入 `tushare_meta`。

### 单次访问限制

不得使用可能超过 TuShare 单次返回上限的无参全量调用。

- 日频接口按 `trade_date` 单日拉取。
- 可按日期范围的接口，优先按交易日或小日期窗口拆分。
- 可按类型拆分的接口，需要按类型拆分，例如沪深港通按 `HK_SH`、`HK_SZ`。
- 可按交易所拆分的接口，需要按交易所拆分，例如上市公司信息按 `SSE`、`SZSE`、`BSE`。
- 如果无参调用存在 1000、8000、10000 等截断风险，必须改为按 `ts_code`、日期、交易所或类型循环。

### 全量同步

全量同步要尽可能获取更早的数据：

- 日期型接口使用 `--full` 触发全量回补。
- 全量默认起始日期使用 `TUSHARE_FULL_SYNC_START_DATE`，当前默认值为 `19901219`。
- 对于实际更晚才有数据的接口，允许从早日期开始查询，由接口返回空数据。
- 全量同步必须支持断点续跑，避免长任务失败后从头开始。

### 增量同步

增量同步根据数据类型设计：

- 日频或交易日表：默认同步最近 `TUSHARE_SYNC_DAYS_BACK` 天。
- 静态或准静态表：周期性全量拉取后按唯一键 upsert，例如 `stock_basic`、`stock_company`。
- 历史/公告类表：按股票代码逐只拉取并 upsert，避免无参全量截断，例如 `namechange`、`st`。
- 发生字段变化且业务需要追踪时，增加 history 表或变更记录逻辑。

## 配置与入口标准

新增 TuShare 表时，必须同步更新以下位置：

- `backend/api/models.py`：新增 model、字段注释、表注释、索引和唯一约束。
- `backend/api/services/postgres.py`：新增 `TUSHARE_CATALOG` 和 `MODEL_CONFIG`。
- `backend/api/services/tushare_sync.py`：新增同步函数、全量/增量策略、断点状态。
- `backend/api/tasks.py`：新增 Celery task。
- `backend/config/settings.py`：新增表名映射、同步间隔、Celery beat 配置。
- `backend/.env.example`：新增可配置同步间隔或起始日期。
- `backend/api/management/commands/sync_tushare.py`：新增 `--table` 入口。
- `backend/api/migrations/`：生成并应用迁移。

## 验证清单

新增表完成后必须至少运行：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py check
..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
..\.venv\Scripts\python.exe manage.py migrate
```

还需要做一次最小范围真实同步，例如：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py sync_tushare --table <table_name> --start-date 20240603 --end-date 20240603 --no-resume
```

静态表可以直接跑对应表：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py sync_tushare --table stock_company
```

验证完成后，需要记录：

- token 是否有权限。
- 测试参数。
- 返回行数。
- 入库行数。
- 是否存在接口字段拼写、分页、日期窗口、积分权限等注意事项。
