# 一期模型样本表设计

## 目标

`model_sample_v1` 是量化诊股一期基线样本表，粒度为 `ts_code + trade_date + feature_version`。

一期先服务两件事：

- 规则评分/解释型诊股 API。
- 后续 Elastic Net Logistic Regression 或 LightGBM 的训练样本。

## 主键与标签

- 样本主键：`ts_code`、`trade_date`、`feature_version`。
- 默认基准：沪深 300，`000300.SH`。
- 预测窗口：未来 20 个交易日。
- 标签：
  - `label_up_20`：未来 20 交易日复权收益是否大于 0。
  - `label_outperform_20`：未来 20 交易日收益是否跑赢基准。

## 一期特征

- 基础信息：股票名称、行业、上市日期、上市天数。
- 行情动量：收盘价、涨跌幅、成交额、复权因子、5/20/60 日收益、MA20/MA60 偏离、20 日波动率、成交额放大倍数。
- 估值：PE TTM、PB、PS TTM、股息率、总市值、流通市值。
- 技术指标：RSI、MACD、KDJ、BOLL，优先取 `stk_factor_pro`。
- 财务质量与成长：ROE、ROA、毛利率、净利率、资产负债率、经营现金流/利润、营收同比、净利同比。
- 资金行为：主力净流入、主力净流入/成交额、融资融券余额、融资买入/成交额、沪深港通持股比例。
- 风险事件：ST、涨停、跌停、质押比例。

## 构建命令

只检查核心表完整性：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py build_model_samples --check
```

构建指定日期窗口：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py build_model_samples --start-date 20240501 --end-date 20240531
```

默认会先删除同一 `feature_version` 和日期范围内的旧样本，再重新插入，保证可重复构建。

默认构建使用快速核心模式，不读取 `stk_factor_pro` 技术指标表；这能显著提升本地批量构建速度。需要补 RSI、MACD、KDJ、BOLL 等技术指标时可显式启用：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py build_model_samples --start-date 20240501 --end-date 20240531 --include-technical
```

当前本地库中 `stk_factor_pro` 读取较慢，建议先用默认模式生成可训练的核心样本，再单独规划技术指标增量补全。

补全低频特征：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py enrich_model_samples --start-date 20240501 --end-date 20240531
```

检查低频特征覆盖：

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py enrich_model_samples --check --start-date 20240501 --end-date 20240531
```

`enrich_model_samples` 会补充：

- 财务质量：ROE、ROA、毛利率、净利率、资产负债率、经营现金流/利润。
- 成长：营收同比、净利同比。
- 资金持仓：沪深港通持股比例。
- 风险：股权质押比例。

这些字段按 `trade_date` 之前最近可见记录向前填充，避免使用未来公告数据。
