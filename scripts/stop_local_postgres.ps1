<#
.SYNOPSIS
  Stop the portable/local PostgreSQL instance used by development scripts.

.DESCRIPTION
  This script stops PostgreSQL through pg_ctl.exe using the configured DataDir.
  It is the companion to scripts/start_local_postgres.ps1 and assumes the same
  portable PostgreSQL directory layout.

  Use it when you started PostgreSQL through start_local_postgres.ps1 or when
  you want to stop that same local pg_ctl-managed instance. Do not use it to
  stop a Windows Service PostgreSQL installation.

.PARAMETER BaseDir
  Directory containing postgresql-17.10\pgsql.

.PARAMETER DataDir
  PostgreSQL data directory passed to pg_ctl -D.

.EXAMPLE
  .\scripts\stop_local_postgres.ps1

  Stop the default local PostgreSQL instance.

.EXAMPLE
  .\scripts\stop_local_postgres.ps1 -BaseDir D:\tools\finance-postgres-local -DataDir D:\data\finance-pgdata

  Stop a local PostgreSQL instance that uses explicit binary and data
  directories.

.NOTES
  If PostgreSQL was started as a Windows Service, stop it through Services,
  pgAdmin, or Stop-Service instead.
#>

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
