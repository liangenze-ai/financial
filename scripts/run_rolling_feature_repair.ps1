<#
.SYNOPSIS
  Build persistent rolling features and apply them to model_sample_v1 month by month.

.DESCRIPTION
  This script repairs derived rolling features used by the quant baseline model:
  ma20_bias, ma60_bias, vol_20, and amount_ratio_20.

  It runs one calendar month at a time so long repairs can be resumed safely.
  Completed months are recorded in backend/logs/rolling_feature_repair_completed.txt.

.EXAMPLE
  .\scripts\run_rolling_feature_repair.ps1 -StartMonth 202401 -EndMonth 202401

.EXAMPLE
  .\scripts\run_rolling_feature_repair.ps1 -StartMonth 201401 -EndMonth 202604 -SkipPostgresStart

.EXAMPLE
  .\scripts\run_rolling_feature_repair.ps1 -WhatIfMonth
#>

Param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [string]$StartMonth = "201401",
  [string]$EndMonth = "202604",
  [string]$FeatureVersion = "v1",
  [switch]$ReplaceRolling,
  [switch]$SkipPostgresStart,
  [switch]$SkipMigrate,
  [switch]$Force,
  [switch]$WhatIfMonth
)

$ErrorActionPreference = "Stop"

function ConvertTo-MonthStart {
  Param([string]$Month)
  if ($Month -notmatch '^[0-9]{6}$') {
    throw "Month must use yyyyMM format: $Month"
  }
  return [datetime]::ParseExact($Month + "01", "yyyyMMdd", $null)
}

function Get-Months {
  Param(
    [string]$FromMonth,
    [string]$ToMonth
  )
  $current = ConvertTo-MonthStart $FromMonth
  $end = ConvertTo-MonthStart $ToMonth
  if ($current -gt $end) {
    throw "StartMonth must be <= EndMonth."
  }

  $months = @()
  while ($current -le $end) {
    $monthStart = $current.ToString("yyyyMMdd")
    $monthEnd = $current.AddMonths(1).AddDays(-1).ToString("yyyyMMdd")
    $months += [pscustomobject]@{
      Month = $current.ToString("yyyyMM")
      StartDate = $monthStart
      EndDate = $monthEnd
    }
    $current = $current.AddMonths(1)
  }
  return $months
}

function Invoke-Step {
  Param(
    [string]$Name,
    [scriptblock]$Action
  )
  $started = Get-Date
  Write-Host "[$($started.ToString('yyyy-MM-dd HH:mm:ss'))] START $Name"
  & $Action
  $elapsed = (Get-Date) - $started
  Write-Host "[$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))] DONE $Name in $([math]::Round($elapsed.TotalSeconds, 1))s"
}

$backendDir = Join-Path $ProjectRoot "backend"
$logsDir = Join-Path $backendDir "logs"
$progressFile = Join-Path $logsDir "rolling_feature_repair_completed.txt"
$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
  throw "Python venv not found: $python"
}

New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
if (-not (Test-Path $progressFile)) {
  New-Item -ItemType File -Path $progressFile -Force | Out-Null
}

$months = Get-Months -FromMonth $StartMonth -ToMonth $EndMonth
if ($WhatIfMonth) {
  $months | Format-Table -AutoSize
  exit 0
}

if (-not $SkipPostgresStart) {
  Invoke-Step -Name "Start local PostgreSQL" -Action {
    & (Join-Path $ProjectRoot "scripts\start_local_postgres.ps1")
  }
}

if (-not $SkipMigrate) {
  Invoke-Step -Name "Apply Django migrations" -Action {
    Push-Location $backendDir
    try {
      & $python manage.py migrate
      if ($LASTEXITCODE -ne 0) {
        throw "Django migrate failed with exit code $LASTEXITCODE"
      }
    }
    finally {
      Pop-Location
    }
  }
}

$completed = Get-Content -Path $progressFile -ErrorAction SilentlyContinue

foreach ($item in $months) {
  $progressKey = "$($item.Month)|$FeatureVersion"
  if ((-not $Force) -and ($completed -contains $progressKey)) {
    Write-Host "SKIP $progressKey already completed"
    continue
  }

  Push-Location $backendDir
  try {
    $buildArgs = @(
      "manage.py", "build_daily_rolling_features",
      "--start-date", $item.StartDate,
      "--end-date", $item.EndDate
    )
    if ($ReplaceRolling) {
      $buildArgs += "--replace"
    }

    Invoke-Step -Name "Build rolling features $($item.Month)" -Action {
      & $python @buildArgs
      if ($LASTEXITCODE -ne 0) {
        throw "build_daily_rolling_features failed for $($item.Month) with exit code $LASTEXITCODE"
      }
    }

    Invoke-Step -Name "Apply rolling features $($item.Month)" -Action {
      & $python manage.py apply_daily_rolling_features `
        --start-date $item.StartDate `
        --end-date $item.EndDate `
        --feature-version $FeatureVersion
      if ($LASTEXITCODE -ne 0) {
        throw "apply_daily_rolling_features failed for $($item.Month) with exit code $LASTEXITCODE"
      }
    }
  }
  finally {
    Pop-Location
  }

  Add-Content -Path $progressFile -Value $progressKey
  $completed += $progressKey
  Write-Host "COMPLETED $progressKey"
}

Write-Host "Rolling feature repair done. Progress file: $progressFile"
