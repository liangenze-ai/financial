Param(
  [string]$BaseDir = (Join-Path $env:USERPROFILE "finance-postgres-local"),
  [string]$DataDir = "E:\finance-postgres-local\pgdata"
)

$ErrorActionPreference = "Stop"

$pgCtl = Join-Path $BaseDir "postgresql-17.10\pgsql\bin\pg_ctl.exe"

if (-not (Test-Path $pgCtl)) {
  throw "PostgreSQL binary not found: $pgCtl"
}
if (-not (Test-Path $DataDir)) {
  throw "PostgreSQL data directory not found: $DataDir"
}

& $pgCtl -D $DataDir stop
