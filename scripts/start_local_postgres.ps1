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

if (-not (Test-Path $pgCtl)) {
  throw "PostgreSQL binary not found: $pgCtl"
}
if (-not (Test-Path $DataDir)) {
  throw "PostgreSQL data directory not found: $DataDir"
}

$readyOutput = & $pgReady -h 127.0.0.1 -p $Port -U finance_app 2>$null
if ($LASTEXITCODE -eq 0) {
  Write-Host $readyOutput
  exit 0
}

& $pgCtl -D $DataDir -l $logFile -o "-h 127.0.0.1 -p $Port" start
Start-Sleep -Seconds 2
& $pgReady -h 127.0.0.1 -p $Port -U finance_app
