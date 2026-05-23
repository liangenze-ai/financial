# 2026-05-21 TuShare 表接入标准记录

今日将新增 TuShare 表的要求整理为代码仓标准文档：

- `docs/tushare-table-standard.md`

后续新增 TuShare 接口和数据表时，需要默认遵守：

- 先用本地 token 做最小范围权限验证。
- model 覆盖官方全量字段，不只取默认字段。
- 表和字段必须增加中文注释，包含 `verbose_name`、`db_comment`、`db_table_comment`。
- 按同步幂等键和查询场景设计唯一约束、组合索引，索引名保持短名。
- 不使用可能超过 TuShare 单次返回限制的无参全量调用，按交易日、股票代码、交易所、类型等参数拆分。
- 全量同步尽可能从 `TUSHARE_FULL_SYNC_START_DATE` 回补，增量同步按表类型设计。
- 同步入口需要同时覆盖 model、catalog、sync service、management command、Celery task、settings、env example 和 migration。
- 完成后必须执行 `manage.py check`、`makemigrations --check --dry-run`、`migrate`，并做最小范围真实同步验证。

