# Development Log

## 2026-05-02 诊股系统量化数据底座

### 目标

为小程序“诊股系统”设计后端量化数据基础能力：

- 选择适合 A 股诊股的量化投资方法。
- 判断 TuShare 是否适合作为数据源。
- 在 Django 后端实现 TuShare 数据获取。
- 支持定时同步和断点继续同步。

### 量化方法选择

诊股系统建议采用“多因子评分 + 后续机器学习排序”的路线。

第一阶段使用可解释的多因子评分，适合在小程序页面展示诊断结论：

- 质量因子：盈利能力、现金流、ROE、负债水平。
- 估值因子：PE、PB、PS、股息率。
- 动量因子：20/60/120 日收益、均线趋势。
- 风险因子：波动率、最大回撤、换手异常。
- 红利因子：股息率、分红稳定性。

后续数据积累后，可以升级为机器学习横截面排序模型，例如 Random Forest、LightGBM 或 LambdaRank。模型输出可以继续映射为小程序中的“综合评分、基本面、技术面、估值面、风险面”。

### TuShare 数据源判断

TuShare 可以作为当前项目的数据源，适合日频/盘后量化诊股。

已规划使用接口：

- `stock_basic`：A 股股票基础信息。
- `daily`：日线行情。
- `daily_basic`：每日指标，包括估值、换手率、市值、股息率等。
- `trade_cal`：交易日历，用于按交易日同步和断点恢复。

注意事项：

- TuShare Pro 需要配置 token。
- 部分接口有积分要求，`daily_basic` 等接口可能需要足够积分。
- 当前方案更适合日频诊股，不适合高频实时交易。

### 已完成后端改动

新增依赖：

- `backend/requirements.txt` 新增 `tushare`。

配置改动：

- `backend/config/settings.py`
  - 增加 `.env` 文件加载。
  - 增加 `TUSHARE_TOKEN`、`TUSHARE_SYNC_START_DATE`、`TUSHARE_SYNC_DAYS_BACK`、`TUSHARE_SYNC_INTERVAL_SECONDS`。
  - 增加 Celery beat 定时任务 `sync-tushare-market-data`。

环境变量模板：

- `backend/.env.example`
  - 新增 TuShare 相关配置项。
- `backend/.env`
  - 新增 TuShare 相关配置项，当前 `TUSHARE_TOKEN` 需要手动填写。

数据库模型：

- `backend/api/models.py`
  - `Stock`：股票基础信息。
  - `DailyQuote`：日线行情。
  - `DailyBasic`：每日估值和交易指标。
  - `SyncJob`：同步任务进度，用于断点继续。

迁移文件：

- `backend/api/migrations/0001_market_data.py`

同步服务：

- `backend/api/services/tushare_sync.py`
  - 初始化 TuShare client。
  - 同步股票基础信息。
  - 按交易日同步 `daily`。
  - 按交易日同步 `daily_basic`。
  - 使用 `SyncJob.current_date` 和 `SyncJob.current_step` 记录同步进度。
  - 支持失败后重新执行时从当前交易日继续。

Celery 任务：

- `backend/api/tasks.py`
  - 新增 `sync_tushare_market_data`。

管理命令：

- `backend/api/management/commands/sync_tushare.py`
  - 支持手动同步。
  - 支持 `--start-date`、`--end-date`、`--no-resume` 参数。

状态接口：

- `backend/api/views.py`
  - 新增 `tushare_sync_status`。
- `backend/api/urls.py`
  - 新增 `/api/tushare/sync/status/`。

### 已执行验证

安装依赖：

```powershell
cd backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

执行迁移：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py migrate
```

Django 检查：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py check
```

检查结果：

- 依赖安装成功。
- 数据库迁移成功。
- `manage.py check` 通过。
- 同步状态接口可访问，初始返回 idle。
- 未配置 `TUSHARE_TOKEN` 时，手动同步命令会明确提示需要先配置 token。

### 使用方式

先在 `backend/.env` 中填写：

```env
TUSHARE_TOKEN=你的token
```

手动同步：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py sync_tushare --start-date 20240501 --end-date 20240531
```

断点继续：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py sync_tushare --start-date 20240501 --end-date 20240531
```

强制重跑：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py sync_tushare --start-date 20240501 --end-date 20240531 --no-resume
```

查看同步状态：

```text
http://127.0.0.1:8000/api/tushare/sync/status/
```

启动 Celery worker：

```powershell
cd backend
$env:PYTHONIOENCODING='utf-8'
..\.venv\Scripts\python.exe -m celery -A config worker -l info --pool=solo
```

启动 Celery beat：

```powershell
cd backend
$env:PYTHONIOENCODING='utf-8'
..\.venv\Scripts\python.exe -m celery -A config beat -l info
```

### 后续建议

- 增加诊股评分 API，将 `Stock`、`DailyQuote`、`DailyBasic` 转换成前端需要的综合评分。
- 增加多因子计算服务，先实现规则评分。
- 增加历史收益回测模块，验证因子有效性。
- 后续接入 LightGBM 或 Random Forest，训练 A 股横截面排序模型。
- 将小程序当前 mock 数据替换为后端诊股接口。

## 2026-05-02 MongoDB-first 数据结构调整

### 调整原因

项目业务数据需要整体面向 MongoDB，而不是 Django ORM/SQLite。TuShare 同步获取的数据也需要直接写入 MongoDB，并且数据库 collection 设计要与 TuShare 官网的数据分类保持一致。

### 设计原则

- Django 只作为 API 服务框架。
- 项目业务数据统一使用 MongoDB。
- TuShare 数据按官网分类映射到 collection。
- 同步进度也存入 MongoDB，避免出现一部分数据在 MongoDB、一部分进度在 SQL 表中的割裂。

### MongoDB collection 设计

当前已实现的 TuShare 分类映射：

| TuShare 分类 | 子分类 | 接口 | MongoDB collection |
| --- | --- | --- | --- |
| 股票数据 | 基础数据 | `stock_basic` | `tushare_stock_basic` |
| 股票数据 | 基础数据 | `trade_cal` | `tushare_trade_cal` |
| 股票数据 | 行情数据 | `daily` | `tushare_stock_daily` |
| 股票数据 | 行情数据 | `daily_basic` | `tushare_stock_daily_basic` |
| 系统数据 | 同步任务 | `sync_jobs` | `system_sync_jobs` |

每条 TuShare 入库数据会附带 `_tushare` 元数据，例如：

```json
{
  "_tushare": {
    "category": "股票数据",
    "section": "行情数据",
    "interface": "daily",
    "collection": "tushare_stock_daily"
  }
}
```

### 已完成后端改动

- `backend/config/settings.py`
  - 将 `DATABASES.default` 调整为 `django.db.backends.dummy`。
  - 移除 Django admin/auth/session/messages 等 SQL 依赖组件。
  - 新增 `MONGODB_TUSHARE_COLLECTIONS`，集中配置 TuShare collection 映射。

- `backend/config/urls.py`
  - 移除 `/admin/` 路由。

- `backend/api/models.py`
  - 清空 Django ORM 业务模型。
  - 明确说明项目业务数据通过 `pymongo` 服务写入 MongoDB。

- `backend/api/migrations/0001_market_data.py`
  - 删除原 SQL 迁移文件，避免后续环境继续创建 SQL 行情表。

- `backend/api/services/mongo.py`
  - 新增 MongoDB 连接和 collection 管理。
  - 新增 TuShare 分类元数据 `TUSHARE_CATALOG`。
  - 新增 MongoDB 索引创建逻辑。

- `backend/api/services/tushare_sync.py`
  - 移除 Django ORM 依赖。
  - 使用 `pymongo.UpdateOne` 批量 upsert TuShare 数据。
  - `stock_basic`、`trade_cal`、`daily`、`daily_basic` 全部写入 MongoDB。
  - 同步任务进度写入 `system_sync_jobs`。

- `backend/api/views.py`
  - `/api/health/` 返回当前数据库为 MongoDB。
  - `/api/tushare/sync/status/` 从 MongoDB 查询同步状态。
  - 新增 `/api/tushare/catalog/`，返回 TuShare 分类与 MongoDB collection 映射。

### 已验证

执行 Django 检查：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py check
```

结果：

```text
System check identified no issues (0 silenced).
```

创建 MongoDB 索引：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py shell -c "from api.services.mongo import ensure_market_data_indexes; ensure_market_data_indexes(); print('mongo indexes ok')"
```

结果：

```text
mongo indexes ok
```

接口验证：

```text
GET /api/health/
GET /api/tushare/catalog/
GET /api/tushare/sync/status/
```

结果：

- `/api/health/` 返回 `database: mongodb`。
- `/api/tushare/catalog/` 返回 TuShare 分类与 collection 映射。
- `/api/tushare/sync/status/` 返回 MongoDB 中的同步任务状态，初始为 `idle`。

## 2026-05-18 PostgreSQL 后端迁移简记

今日开发工作：确认后端原先以 MongoDB/pymongo 存储 TuShare 业务数据，并将项目配置、依赖、Django ORM 模型、迁移文件、同步写入逻辑、健康检查接口、安装脚本和文档切换为 PostgreSQL。

后续可能任务：安装并启动本地 PostgreSQL 或 Docker 环境后执行数据库迁移，随后验证 TuShare 同步、接口读取和前端诊股页面的数据联通。

## 2026-05-19 PostgreSQL 本地环境安装简记

今日开发工作：在无 Docker、无管理员权限的 Windows 环境下改用 PostgreSQL 17.10 官方 binaries 完成本地数据库安装与初始化，创建 `finance_db`，安装后端依赖，执行 Django 迁移，并补充本地 PostgreSQL 启停脚本。

后续可能任务：继续验证 TuShare 数据同步、Redis/Celery 后台任务、接口读取和小程序诊股页面的数据联通，并考虑将本地 PostgreSQL 启动流程整理进 README。

## 2026-05-20 PostgreSQL TuShare 同步与接口整理简记
今日开发工作：围绕 PostgreSQL 方案补齐 TuShare 业务表 ORM 模型、迁移文件、同步服务与 Celery 定时任务，并完善健康检查、同步状态和数据目录接口。
后续可能任务：继续跑通本地 PostgreSQL 中的 TuShare 全量/增量同步，联调前端诊股页面的数据读取，并补充同步异常处理、接口测试和部署文档。
