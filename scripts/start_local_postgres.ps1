<#
.SYNOPSIS
  Start the portable/local PostgreSQL instance used by development scripts.

.DESCRIPTION
  This script starts PostgreSQL through pg_ctl.exe from a local PostgreSQL
  directory. It first checks pg_isready on 127.0.0.1:Port; if PostgreSQL is
  already accepting connections, it prints the readiness output and exits.

  It is designed for the portable local PostgreSQL layout used by this project,
  not for managing a Windows Service installation. If PostgreSQL is installed
  as a service, use the service manager or install_windows.ps1 instead.

  Defaults:
    BaseDir: %USERPROFILE%\finance-postgres-local
    Pg root: BaseDir\postgresql-17.10\pgsql
    DataDir: E:\finance-postgres-local\pgdata
    Log:     BaseDir\postgresql.log
    Host:    127.0.0.1
    User:    finance_app for readiness checks

  Use this script before running data pipeline scripts when you rely on the
  portable PostgreSQL instance and it is not already running.

.PARAMETER BaseDir
  Directory containing postgresql-17.10\pgsql and the PostgreSQL log file.

.PARAMETER DataDir
  PostgreSQL data directory passed to pg_ctl -D.

.PARAMETER Port
  TCP port to listen on and check with pg_isready.

.EXAMPLE
  .\scripts\start_local_postgres.ps1

  Start the default local PostgreSQL instance on port 5432.

.EXAMPLE
  .\scripts\start_local_postgres.ps1 -Port 15432

  Start/check PostgreSQL on a non-default port.

.EXAMPLE
  .\scripts\start_local_postgres.ps1 -BaseDir D:\tools\finance-postgres-local -DataDir D:\data\finance-pgdata

  Use explicit PostgreSQL binary and data directories.

.NOTES
  This script does not initialize a new PostgreSQL data directory. The DataDir
  must already exist and be initialized.
#>

Param(
  [string]$BaseDir = (Join-Path $env:USERPROFILE "finance-postgres-local"),
  [string]$DataDir = "E:\finance-postgres-local\pgdata",
  [int]$Port = 5432
)

$ErrorActionPreference = "Stop"

$pgRoot = Join-Path $BaseDir "postgresql-17.10\pgsql"
$logFile = Join-Path $BaseDir "postgresql.log"
$pgCtl = Join-Path $pgRoot "bin\pg_ctl.exe"
$pgReady = Join-Path $pgRoot "bin\pg_isready.exe"
$postmasterPidFile = Join-Path $DataDir "postmaster.pid"

if (-not (Test-Path $pgCtl)) {
  throw "PostgreSQL binary not found: $pgCtl"
}
if (-not (Test-Path $DataDir)) {
  throw "PostgreSQL data directory not found: $DataDir"
}

function Invoke-NativeCommand {
  Param(
    [string]$FilePath,
    [string[]]$Arguments
  )

  $previousErrorActionPreference = $ErrorActionPreference
  $hasNativePreference = Test-Path Variable:\PSNativeCommandUseErrorActionPreference
  if ($hasNativePreference) {
    $previousNativePreference = $PSNativeCommandUseErrorActionPreference
    $PSNativeCommandUseErrorActionPreference = $false
  }

  try {
    $ErrorActionPreference = "Continue"
    $output = & $FilePath @Arguments 2>&1 | ForEach-Object { $_.ToString() }
    $exitCode = $LASTEXITCODE
  }
  finally {
    $ErrorActionPreference = $previousErrorActionPreference
    if ($hasNativePreference) {
      $PSNativeCommandUseErrorActionPreference = $previousNativePreference
    }
  }

  [pscustomobject]@{
    ExitCode = $exitCode
    Output = $output
  }
}

function Invoke-NativeCommandDirect {
  Param(
    [string]$FilePath,
    [string[]]$Arguments
  )

  $previousErrorActionPreference = $ErrorActionPreference
  $hasNativePreference = Test-Path Variable:\PSNativeCommandUseErrorActionPreference
  if ($hasNativePreference) {
    $previousNativePreference = $PSNativeCommandUseErrorActionPreference
    $PSNativeCommandUseErrorActionPreference = $false
  }

  try {
    $ErrorActionPreference = "Continue"
    & $FilePath @Arguments
    return $LASTEXITCODE
  }
  finally {
    $ErrorActionPreference = $previousErrorActionPreference
    if ($hasNativePreference) {
      $PSNativeCommandUseErrorActionPreference = $previousNativePreference
    }
  }
}

function Invoke-NativeCommandDetached {
  Param(
    [string]$FilePath,
    [string]$Arguments
  )

  $process = Start-Process `
    -FilePath $FilePath `
    -ArgumentList $Arguments `
    -WindowStyle Hidden `
    -PassThru `
    -Wait
  return $process.ExitCode
}

function Test-PostgresReady {
  Param([switch]$Quiet)

  $readyResult = Invoke-NativeCommand -FilePath $pgReady -Arguments @(
    "-h", "127.0.0.1",
    "-p", "$Port",
    "-U", "finance_app"
  )
  if ((-not $Quiet) -and $readyResult.Output) {
    Write-Host ($readyResult.Output -join [Environment]::NewLine)
  }
  return ($readyResult.ExitCode -eq 0)
}

function Wait-PostgresReady {
  Param([int]$TimeoutSeconds = 30)

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-PostgresReady -Quiet) {
      Test-PostgresReady | Out-Null
      return $true
    }
    Start-Sleep -Seconds 1
  }
  return $false
}

function Remove-StalePostmasterPid {
  if (-not (Test-Path $postmasterPidFile)) {
    return
  }

  $pidLines = Get-Content -Path $postmasterPidFile -Encoding UTF8 -ErrorAction SilentlyContinue
  if (-not $pidLines -or -not $pidLines[0]) {
    return
  }

  [int]$postgresPid = 0
  if (-not [int]::TryParse($pidLines[0], [ref]$postgresPid)) {
    return
  }

  $process = Get-Process -Id $postgresPid -ErrorAction SilentlyContinue
  if ($process) {
    return
  }

  Write-Host "Removing stale postmaster.pid for missing PID $postgresPid"
  Remove-Item -LiteralPath $postmasterPidFile -Force
}

if (Test-PostgresReady) {
  exit 0
}

$statusResult = Invoke-NativeCommand -FilePath $pgCtl -Arguments @("-D", $DataDir, "status")
if ($statusResult.ExitCode -eq 0) {
  Write-Host ($statusResult.Output -join [Environment]::NewLine)
  if (Wait-PostgresReady -TimeoutSeconds 30) {
    exit 0
  }
  throw "PostgreSQL process is running, but it is not accepting connections on 127.0.0.1:$Port."
}

Remove-StalePostmasterPid

$pgOptions = '"-h" "127.0.0.1" "-p" "{0}"' -f $Port
$startArguments = '-D "{0}" -l "{1}" -o "{2}" start' -f $DataDir, $logFile, $pgOptions
$startExitCode = Invoke-NativeCommandDetached -FilePath $pgCtl -Arguments $startArguments
if ($startExitCode -ne 0) {
  throw "pg_ctl start failed with exit code $startExitCode. See log: $logFile"
}

if (-not (Wait-PostgresReady -TimeoutSeconds 30)) {
  throw "PostgreSQL did not become ready on 127.0.0.1:$Port within 30 seconds. See log: $logFile"
}
