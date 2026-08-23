<#
.SYNOPSIS
  Install and prepare local Windows dependencies for the finance backend.

.DESCRIPTION
  This script is intended for first-time Windows setup. It installs PostgreSQL
  and a Redis-compatible service, installs Python dependencies into the
  repository .venv, and applies Django migrations.

  It requires an elevated PowerShell session because package installation and
  service startup need Administrator permissions.

  Package manager behavior:
    - Prefer winget when available.
    - Fall back to choco for PostgreSQL or Redis when winget fails and choco
      is available.
    - Redis is installed through Memurai Developer with winget, or redis-64
      with Chocolatey.

  Database/user behavior:
    - The script prints the expected database settings:
      database finance_db, user finance_app, password finance_app.
    - It does not fully automate PostgreSQL role/database creation on Windows,
      because installer defaults and admin credentials vary by machine.
    - If migrations fail because the database or role is missing, create them
      manually in pgAdmin/psql and rerun this script.

  Use this script for system-level dependency setup. Use
  start_local_postgres.ps1/start_local_redis.ps1 for portable local services
  after they have already been installed or unpacked.

.PARAMETER ProjectRoot
  Repository root. Defaults to the parent directory of scripts/.

.EXAMPLE
  Start-Process powershell -Verb RunAs

  Open an elevated PowerShell window before running the install script.

.EXAMPLE
  .\scripts\install_windows.ps1

  Install PostgreSQL/Redis-compatible service, install backend Python
  dependencies, and run Django migrations.

.EXAMPLE
  .\scripts\install_windows.ps1 -ProjectRoot D:\projects\理财项目设计

  Run setup for an explicit repository path.

.NOTES
  Expected Python virtual environment:
    .venv\Scripts\python.exe

  Expected backend requirements file:
    backend\requirements.txt
#>

Param(
  [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\.." | Select-Object -ExpandProperty Path)
)

$ErrorActionPreference = "Stop"

function Test-IsAdmin {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-WingetInstall {
  param(
    [Parameter(Mandatory = $true)][string]$PackageId
  )

  winget install -e --id $PackageId --accept-source-agreements --accept-package-agreements
  return ($LASTEXITCODE -eq 0)
}

function Ensure-ServiceStarted {
  param(
    [Parameter(Mandatory = $true)][string]$ServiceName
  )

  $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
  if (-not $svc) {
    return $false
  }

  try {
    Set-Service -Name $ServiceName -StartupType Automatic
    Start-Service -Name $ServiceName -ErrorAction SilentlyContinue
    return $true
  } catch {
    Write-Warning "Cannot set/start service '$ServiceName'. Run this script as Administrator."
    return $false
  }
}

if (-not (Test-IsAdmin)) {
  throw "Please run this script in an elevated PowerShell window (Run as Administrator)."
}

Write-Host "[1/6] Checking package managers..."
$hasWinget = $null -ne (Get-Command winget -ErrorAction SilentlyContinue)
$hasChoco = $null -ne (Get-Command choco -ErrorAction SilentlyContinue)

if (-not $hasWinget -and -not $hasChoco) {
  throw "Neither winget nor choco found. Install one of them first."
}

Write-Host "[2/6] Installing PostgreSQL and Redis..."
if ($hasWinget) {
  $postgresOk = Invoke-WingetInstall -PackageId "PostgreSQL.PostgreSQL"
  if (-not $postgresOk -and $hasChoco) {
    choco install -y postgresql
  } elseif (-not $postgresOk) {
    throw "PostgreSQL installation failed via winget and choco is unavailable."
  }

  $redisOk = Invoke-WingetInstall -PackageId "Memurai.MemuraiDeveloper"
  if (-not $redisOk) {
    $hasMemurai = $null -ne (Get-Service -Name "Memurai" -ErrorAction SilentlyContinue)
    if ($hasMemurai) {
      Write-Warning "Memurai installer returned a non-zero code, but Memurai service exists. Continuing."
    } elseif ($hasChoco) {
      choco install -y redis-64
    } else {
      Write-Warning "Redis install via winget failed and choco is unavailable."
      Write-Warning "You can install Redis compatible service manually (e.g. Memurai) and rerun this script."
    }
  }
} else {
  choco install -y postgresql redis-64
}

Write-Host "[3/6] Ensuring services are running..."
$postgresStarted = Ensure-ServiceStarted -ServiceName "postgresql*"

$redisStarted = Ensure-ServiceStarted -ServiceName "Memurai"
if (-not $redisStarted) {
  $redisStarted = Ensure-ServiceStarted -ServiceName "Redis"
}

if (-not $postgresStarted) {
  Write-Warning "PostgreSQL service not found. Check installation logs and install status."
}
if (-not $redisStarted) {
  Write-Warning "Redis/Memurai service not found. Check installation logs and install status."
}

Write-Host "[4/6] Installing Python packages in .venv..."
$pythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
  throw "Python venv not found at $pythonExe"
}
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $ProjectRoot "backend\requirements.txt")

Write-Host "PostgreSQL database/user setup:"
Write-Host "  Create database: finance_db"
Write-Host "  Create user: finance_app"
Write-Host "  Password: finance_app"
Write-Host "If PostgreSQL asks for an admin password during installation, create these manually in pgAdmin or psql."

Write-Host "[5/6] Applying Django migrations..."
Push-Location (Join-Path $ProjectRoot "backend")
& $pythonExe manage.py migrate
Pop-Location

Write-Host "[6/6] Completed."
Write-Host "PostgreSQL default: postgresql://finance_app:finance_app@127.0.0.1:5432/finance_db"
Write-Host "Redis default: redis://127.0.0.1:6379"
Write-Host "Start Django: cd backend; $pythonExe manage.py runserver"
Write-Host "Start Celery: cd backend; $pythonExe -m celery -A config worker -l info"
