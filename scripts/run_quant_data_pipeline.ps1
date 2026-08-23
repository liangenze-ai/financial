<#
用途：
  统一的 TuShare 数据回填与量化模型样本流水线脚本。

说明：
  这是本地数据准备的主入口。它可以执行完整 TuShare 回填、较小的历史兼容回填分组，
  也可以在数据同步后执行模型样本构建和样本补充。

  脚本会把日志写入 backend/logs/ 下的带时间戳文件，并把命令输出同时打印到控制台
  和日志文件。默认流程为：启动本地 PostgreSQL、执行 Django 迁移、显示当前数据状态、
  同步所选 TuShare 表、显示最终数据状态。

模式：
  quant-model：
    量化诊断流程使用的完整必要数据集。此模式为默认模式。默认检查缺口并只下载缺少日期，
    避免重复下载已有历史数据；需要强制历史全量重拉时传入 -UseFull。

  full：
    quant-model 的历史兼容别名。

  core：
    历史核心回填分组，包含：
    market_data, adj_factor, fina_indicator, income, balancesheet, cashflow。

  remaining：
    历史剩余表回填分组，包含：
    adj_factor, fina_indicator, income, balancesheet, cashflow。
    保留该模式是为了兼容早期的较小范围运维脚本。

  quant-plan：
    量化计划回填分组，包含：
    stk_factor_pro, moneyflow, margin, block_trade, top_list, top_inst,
    repurchase, pledge_detail, forecast, express, dividend。
    该模式默认会构建并补充训练/实时两个样本窗口，除非传入 -SkipSampleBuild。

数据区间规则：
  - 默认从 CheckMissingFromDate 到 EndDate 检查缺口，只下载缺少的日期。
  - 显式传入 -StartDate 时，会覆盖 CheckMissingFromDate，用于指定缺口检查起点。
  - -UseFull 会向 sync_tushare 传入 --full，用于强制历史全量重拉。
  - -IncrementalOnly 会省略 --start-date，并传入 --no-resume，用于把各表按最新已存储状态更新到 EndDate。
  - 基础快照表在本地已有数据时默认跳过；需要刷新时传入 -UseFull。

样本构建规则：
  - -BuildSamples 使用 SampleStartDate 和 SampleEndDate 执行单窗口构建、补充和检查。
    如果未指定这两个日期，则默认使用 StartDate 和 EndDate。
    默认会追加并跳过已生成样本的交易日，适合中断后继续执行。
  - quant-plan 模式默认使用训练/实时两个样本窗口。传入 -SkipSampleBuild 时只同步数据表。

参数说明：
  ProjectRoot：
    仓库根目录。默认是 scripts/ 的父目录。

  Mode：
    要运行的流水线场景，可选值为 full、core、remaining、quant-plan。

  StartDate：
    日期型表同步的开始日期，格式为 yyyyMMdd。未显式传入时只作为样本构建默认起点，
    不会用于 TuShare 同步。

  CheckMissingFromDate：
    未显式传入 StartDate 时，数据缺口检查的默认起点。

  EndDate：
    日期型表同步的结束日期，格式为 yyyyMMdd。默认是运行脚本当天。

  FeatureVersion：
    传给 build_model_samples 和 enrich_model_samples 的特征版本。

  SampleStartDate：
    使用 -BuildSamples 执行单窗口样本构建时的开始日期。默认等于 StartDate。

  SampleEndDate：
    使用 -BuildSamples 执行单窗口样本构建时的结束日期。默认等于 EndDate。

  SampleTrainStartDate：
    quant-plan 分段样本构建中的训练窗口开始日期。

  SampleTrainEndDate：
    quant-plan 分段样本构建中的训练窗口结束日期。

  SampleLiveStartDate：
    quant-plan 分段样本构建中的实时/评估窗口开始日期。

  SampleLiveEndDate：
    quant-plan 分段样本构建中的实时/评估窗口结束日期。未指定时默认等于 EndDate。

  IncrementalOnly：
    不传 --start-date，并传入 --no-resume，用于日常增量更新到 EndDate。

  BuildSamples：
    数据同步完成后，构建并补充一个模型样本窗口。

  SkipSampleBuild：
    在 quant-plan 模式下只同步数据，跳过默认的训练/实时样本构建与补充。

  IncludeTechnical：
    构建样本时加入技术指标特征。

  ReplaceSamples：
    单窗口样本构建时替换已有样本，而不是追加续跑；用于底层数据或特征逻辑变化后的强制重算。

  SkipPostgresStart：
    不调用 scripts/start_local_postgres.ps1。适用于 PostgreSQL 已经启动，
    或者使用了其他数据库服务的情况。

  SkipMigrate：
    同步数据前不执行 Django 迁移。

  SkipStatus：
    不执行同步前后的状态检查。

  UseFull：
    向 sync_tushare 传入 --full，并刷新基础快照表。用于强制历史全量重拉。

  NoFull：
    历史兼容参数；当前默认不会传入 --full。

  PostgresBaseDir：
    本地便携 PostgreSQL 安装目录的根路径。

  PostgresUser：
    状态查询使用的 PostgreSQL 用户。

  PostgresPassword：
    状态查询使用的 PostgreSQL 密码。

  PostgresDatabase：
    状态查询使用的 PostgreSQL 数据库。

  PostgresPort：
    PostgreSQL 启动和状态检查使用的端口。

使用示例：
  .\scripts\run_quant_data_pipeline.ps1
    运行默认完整数据流水线，按本地最新日期增量同步到当天，包括启动 PostgreSQL、
    执行迁移、数据状态检查和 full 模式下的全部表。

  .\scripts\run_quant_data_pipeline.ps1 -EndDate 20260531
    按本地最新日期增量同步到固定截止日期。

  .\scripts\run_quant_data_pipeline.ps1 -UseFull -StartDate 20140101 -EndDate 20260531
    强制执行历史全量回填，并使用固定日期区间。

  .\scripts\run_quant_data_pipeline.ps1 -IncrementalOnly
    执行日常增量更新到当天。

  .\scripts\run_quant_data_pipeline.ps1 -Mode core -StartDate 20140101 -EndDate 20260531
    执行历史核心表分组回填，并指定固定日期区间。

  .\scripts\run_quant_data_pipeline.ps1 -Mode remaining -EndDate 20260531
    执行历史剩余表分组回填。

  .\scripts\run_quant_data_pipeline.ps1 -Mode quant-plan -EndDate 20260531
    同步 quant-plan 表，并构建/补充默认训练和实时样本窗口。

  .\scripts\run_quant_data_pipeline.ps1 -Mode quant-plan -SkipSampleBuild
    只同步 quant-plan 表，不构建样本。

  .\scripts\run_quant_data_pipeline.ps1 -BuildSamples -SampleStartDate 20240101 -SampleEndDate 20251231
    执行完整数据同步后，构建并补充一个模型样本窗口。

  .\scripts\run_quant_data_pipeline.ps1 -SkipPostgresStart -SkipMigrate -SkipStatus -Mode core
    只执行表同步步骤，适用于数据库服务和表结构已经准备好的场景。

注意：
  本脚本会在 backend/ 目录下通过 .venv/Scripts/python.exe 调用 Django 管理命令。
  它会真实写入数据库；当日期范围较大时，运行时间可能很长。
#>

Param(
  # 本地 TuShare 回填与量化样本构建的统一流水线。
  #
  # 常见用法：
  #   .\scripts\run_quant_data_pipeline.ps1
  #   .\scripts\run_quant_data_pipeline.ps1 -Mode core -EndDate 20260531
  #   .\scripts\run_quant_data_pipeline.ps1 -Mode quant-plan -SkipPostgresStart -SkipMigrate -SkipStatus
  #   .\scripts\run_quant_data_pipeline.ps1 -BuildSamples -SampleStartDate 20240101 -SampleEndDate 20251231
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [ValidateSet("quant-model", "full", "core", "remaining", "quant-plan")]
  [string]$Mode = "quant-model",
  [string]$StartDate = "20140101",
  [string]$CheckMissingFromDate = "20140101",
  [string]$EndDate = (Get-Date -Format "yyyyMMdd"),
  [string]$FeatureVersion = "v1",
  [string]$SampleStartDate = "",
  [string]$SampleEndDate = "",
  [string]$SampleTrainStartDate = "20140101",
  [string]$SampleTrainEndDate = "20251231",
  [string]$SampleLiveStartDate = "20260101",
  [string]$SampleLiveEndDate = "",
  [switch]$IncrementalOnly,
  [switch]$BuildSamples,
  [switch]$SkipSampleBuild,
  [switch]$IncludeTechnical,
  [switch]$ReplaceSamples,
  [switch]$SkipPostgresStart,
  [switch]$SkipMigrate,
  [switch]$SkipStatus,
  [switch]$UseFull,
  [switch]$NoFull,
  [string]$PostgresBaseDir = (Join-Path $env:USERPROFILE "finance-postgres-local"),
  [string]$PostgresUser = "finance_app",
  [string]$PostgresPassword = "finance_app",
  [string]$PostgresDatabase = "finance_db",
  [int]$PostgresPort = 5432
)

$ErrorActionPreference = "Stop"

$backendDir = Join-Path $ProjectRoot "backend"
$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$startPostgresScript = Join-Path $ProjectRoot "scripts\start_local_postgres.ps1"
$psql = Join-Path $PostgresBaseDir "postgresql-17.10\pgsql\bin\psql.exe"
$logDir = Join-Path $backendDir "logs"
$logFile = Join-Path $logDir ("quant_data_pipeline_{0}_{1}.log" -f $Mode, (Get-Date -Format "yyyyMMdd_HHmmss"))
$syncStartDateSpecified = $PSBoundParameters.ContainsKey("StartDate")
$syncStartDate = if ($syncStartDateSpecified) { $StartDate } else { $CheckMissingFromDate }

if (-not $SampleStartDate) {
  $SampleStartDate = $StartDate
}
if (-not $SampleEndDate) {
  $SampleEndDate = $EndDate
}
if (-not $SampleLiveEndDate) {
  $SampleLiveEndDate = $EndDate
}

if (-not (Test-Path $python)) {
  throw "Python not found: $python"
}
if (-not (Test-Path $backendDir)) {
  throw "Backend directory not found: $backendDir"
}
if ((-not $SkipPostgresStart) -and (-not (Test-Path $startPostgresScript))) {
  throw "PostgreSQL start script not found: $startPostgresScript"
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$skipExistingSnapshotTables = @(
  "stock_basic",
  "index_classify",
  "index_member_all"
)

$syncTableSets = @{
  "core" = @(
    "market_data",
    "adj_factor",
    "fina_indicator",
    "income",
    "balancesheet",
    "cashflow"
  )
  "remaining" = @(
    "adj_factor",
    "fina_indicator",
    "income",
    "balancesheet",
    "cashflow"
  )
  "quant-plan" = @(
    "stk_factor_pro",
    "moneyflow",
    "margin",
    "block_trade",
    "top_list",
    "top_inst",
    "repurchase",
    "pledge_detail",
    "forecast",
    "express",
    "dividend"
  )
  "quant-model" = @(
    "stock_basic",
    "trade_cal",
    "market_data",
    "adj_factor",
    "index_daily",
    "index_classify",
    "index_member_all",
    "moneyflow",
    "margin_detail",
    "stock_st",
    "suspend_d",
    "stk_limit",
    "share_float",
    "pledge_stat",
    "fina_indicator",
    "income",
    "balancesheet",
    "cashflow",
    "stk_factor_pro",
    "margin",
    "pledge_detail",
    "forecast",
    "express",
    "block_trade",
    "top_list",
    "top_inst",
    "dividend",
    "repurchase"
  )
}

$syncTableSets["full"] = $syncTableSets["quant-model"]

$syncTables = $syncTableSets[$Mode]
$runSplitSamples = ($Mode -eq "quant-plan" -and -not $SkipSampleBuild)
$runSingleSamples = ($BuildSamples -and -not $runSplitSamples)

$totalSteps = $syncTables.Count
if (-not $SkipPostgresStart) {
  $totalSteps += 1
}
if (-not $SkipMigrate) {
  $totalSteps += 1
}
if (-not $SkipStatus) {
  $totalSteps += 2
}
if ($runSingleSamples) {
  $totalSteps += 3
}
if ($runSplitSamples) {
  $totalSteps += 4
}
$script:currentStep = 0

function Write-PipelineLog {
  Param([string]$Message)

  $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
  Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
}

function Invoke-PipelineStep {
  Param(
    [string]$Name,
    [scriptblock]$Action
  )

  $script:currentStep += 1
  $percent = [math]::Floor(($script:currentStep - 1) * 100 / $totalSteps)
  Write-Progress -Activity "Quant data pipeline" -Status $Name -PercentComplete $percent
  Write-Host ("[{0}/{1}] {2}" -f $script:currentStep, $totalSteps, $Name)
  Write-PipelineLog "START $Name"

  try {
    & $Action
    Write-PipelineLog "DONE $Name"
  }
  catch {
    Write-PipelineLog "FAILED $Name :: $($_.Exception.Message)"
    throw
  }
}

function Invoke-ManageCommand {
  Param(
    [string]$Name,
    [string[]]$CommandArgs
  )

  Write-PipelineLog ("COMMAND {0}: {1}" -f $Name, ($CommandArgs -join " "))
  Push-Location $backendDir
  try {
    & $python @CommandArgs 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
      throw "$Name failed with exit code $LASTEXITCODE"
    }
  }
  finally {
    Pop-Location
  }
}

function Get-ExistingTableRows {
  Param([string]$Table)

  if (-not (Test-Path $psql)) {
    Write-PipelineLog "SKIP row count check: psql not found at $psql"
    return 0
  }

  $env:PGPASSWORD = $PostgresPassword
  $tableName = "tushare_$Table"
  $query = "select case when to_regclass('$tableName') is null then 0 else (select count(*) from $tableName) end;"
  $output = & $psql `
    -h 127.0.0.1 `
    -p $PostgresPort `
    -U $PostgresUser `
    -d $PostgresDatabase `
    -t `
    -A `
    -P pager=off `
    -c $query 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-PipelineLog ("SKIP row count check failed for {0}: {1}" -f $Table, ($output -join " "))
    return 0
  }

  $lastLine = ($output | Where-Object { $_ -match "\S" } | Select-Object -Last 1)
  [long]$rows = 0
  if ([int64]::TryParse($lastLine, [ref]$rows)) {
    return $rows
  }
  return 0
}

function Test-SkipExistingSnapshotTable {
  Param([string]$Table)

  if ($UseFull) {
    return $false
  }
  if ($syncStartDateSpecified) {
    return $false
  }
  if ($skipExistingSnapshotTables -notcontains $Table) {
    return $false
  }

  $rows = Get-ExistingTableRows -Table $Table
  if ($rows -le 0) {
    return $false
  }

  Write-Host ("Skip {0}: local snapshot table already has {1} rows. Use -UseFull to refresh." -f $Table, $rows)
  Write-PipelineLog ("SKIP sync_tushare {0}: existing rows={1}" -f $Table, $rows)
  return $true
}

function Invoke-SyncTable {
  Param([string]$Table)

  if (Test-SkipExistingSnapshotTable -Table $Table) {
    return
  }

  $args = @("manage.py", "sync_tushare", "--table", $Table, "--end-date", $EndDate)
  if ($IncrementalOnly) {
    $args += "--no-resume"
  }
  else {
    if ($syncStartDate) {
      $args += @("--start-date", $syncStartDate)
    }
    if ((-not $NoFull) -and $UseFull) {
      $args += "--full"
    }
  }
  Invoke-ManageCommand -Name "sync_tushare $Table" -CommandArgs $args
}

function Show-CurrentDataStatus {
  Invoke-ManageCommand -Name "build_model_samples check" -CommandArgs @(
    "manage.py", "build_model_samples", "--check", "--feature-version", $FeatureVersion
  )

  if (Test-Path $psql) {
    $env:PGPASSWORD = $PostgresPassword
    $query = @"
select name, status, start_date, end_date, current_date, processed_dates, left(message, 90) as message
from system_sync_jobs
order by updated_at desc
limit 40;
"@
    Write-PipelineLog "COMMAND psql sync job status"
    & $psql -h 127.0.0.1 -p $PostgresPort -U $PostgresUser -d $PostgresDatabase -P pager=off -c $query 2>&1 |
      Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
      throw "psql sync job status failed with exit code $LASTEXITCODE"
    }
  }
  else {
    Write-PipelineLog "SKIP psql sync job status: psql not found at $psql"
    Write-Host "Skip sync job status: psql not found at $psql"
  }
}

function Invoke-SampleBuild {
  Param(
    [string]$Name,
    [string]$BuildStartDate,
    [string]$BuildEndDate,
    [switch]$Append
  )

  $buildArgs = @(
    "manage.py", "build_model_samples",
    "--start-date", $BuildStartDate,
    "--end-date", $BuildEndDate,
    "--feature-version", $FeatureVersion,
    "--skip-integrity"
  )
  if ($Append) {
    $buildArgs += "--append"
    $buildArgs += "--skip-existing"
  }
  if ($IncludeTechnical) {
    $buildArgs += "--include-technical"
  }
  Invoke-ManageCommand -Name $Name -CommandArgs $buildArgs
}

function Invoke-SampleEnrich {
  Param(
    [string]$Name,
    [string]$EnrichStartDate,
    [string]$EnrichEndDate
  )

  Invoke-ManageCommand -Name $Name -CommandArgs @(
    "manage.py", "enrich_model_samples",
    "--start-date", $EnrichStartDate,
    "--end-date", $EnrichEndDate,
    "--feature-version", $FeatureVersion,
    "--only-missing",
    "--batch-size", "20"
  )
}

Write-PipelineLog "PIPELINE START mode=$Mode project=$ProjectRoot start_date=$StartDate end_date=$EndDate incremental_only=$IncrementalOnly build_samples=$BuildSamples"
Write-Host "Pipeline mode: $Mode"
Write-Host "Pipeline log: $logFile"

if (-not $SkipPostgresStart) {
  Invoke-PipelineStep -Name "Start local PostgreSQL" -Action {
    Write-PipelineLog "COMMAND start_local_postgres: $startPostgresScript -Port $PostgresPort"
    & $startPostgresScript -Port $PostgresPort
    if ($LASTEXITCODE -ne 0) {
      throw "start_local_postgres failed with exit code $LASTEXITCODE"
    }
  }
}

if (-not $SkipMigrate) {
  Invoke-PipelineStep -Name "Run Django migrations" -Action {
    Invoke-ManageCommand -Name "migrate" -CommandArgs @("manage.py", "migrate", "--noinput")
  }
}

if (-not $SkipStatus) {
  Invoke-PipelineStep -Name "Show current data status" -Action {
    Show-CurrentDataStatus
  }
}

foreach ($table in $syncTables) {
  Invoke-PipelineStep -Name "Sync $table to $EndDate" -Action {
    Invoke-SyncTable -Table $table
  }
}

if ($runSingleSamples) {
  Invoke-PipelineStep -Name "Build model samples $SampleStartDate-$SampleEndDate" -Action {
    Invoke-SampleBuild -Name "build_model_samples" -BuildStartDate $SampleStartDate -BuildEndDate $SampleEndDate -Append:(-not $ReplaceSamples)
  }
  Invoke-PipelineStep -Name "Enrich model samples $SampleStartDate-$SampleEndDate" -Action {
    Invoke-SampleEnrich -Name "enrich_model_samples" -EnrichStartDate $SampleStartDate -EnrichEndDate $SampleEndDate
  }
  Invoke-PipelineStep -Name "Check model sample status" -Action {
    Invoke-ManageCommand -Name "enrich_model_samples check" -CommandArgs @(
      "manage.py", "enrich_model_samples", "--check",
      "--start-date", $SampleStartDate,
      "--end-date", $SampleEndDate,
      "--feature-version", $FeatureVersion
    )
  }
}

if ($runSplitSamples) {
  Invoke-PipelineStep -Name "Build train samples $SampleTrainStartDate-$SampleTrainEndDate" -Action {
    Invoke-SampleBuild -Name "build_model_samples train" -BuildStartDate $SampleTrainStartDate -BuildEndDate $SampleTrainEndDate
  }
  Invoke-PipelineStep -Name "Build live samples $SampleLiveStartDate-$SampleLiveEndDate" -Action {
    Invoke-SampleBuild -Name "build_model_samples live" -BuildStartDate $SampleLiveStartDate -BuildEndDate $SampleLiveEndDate -Append
  }
  Invoke-PipelineStep -Name "Enrich train samples $SampleTrainStartDate-$SampleTrainEndDate" -Action {
    Invoke-SampleEnrich -Name "enrich_model_samples train" -EnrichStartDate $SampleTrainStartDate -EnrichEndDate $SampleTrainEndDate
  }
  Invoke-PipelineStep -Name "Enrich live samples $SampleLiveStartDate-$SampleLiveEndDate" -Action {
    Invoke-SampleEnrich -Name "enrich_model_samples live" -EnrichStartDate $SampleLiveStartDate -EnrichEndDate $SampleLiveEndDate
  }
}

if (-not $SkipStatus) {
  Invoke-PipelineStep -Name "Show final data status" -Action {
    Show-CurrentDataStatus
  }
}

Write-Progress -Activity "Quant data pipeline" -Completed
Write-PipelineLog "PIPELINE DONE"
Write-Host "Quant data pipeline done."
Write-Host "Log file: $logFile"
