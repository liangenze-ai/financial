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

Write-Host "[2/6] Installing MongoDB and Redis..."
if ($hasWinget) {
  $mongoOk = Invoke-WingetInstall -PackageId "MongoDB.Server"
  if (-not $mongoOk -and $hasChoco) {
    choco install -y mongodb
  } elseif (-not $mongoOk) {
    throw "MongoDB installation failed via winget and choco is unavailable."
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
  choco install -y mongodb redis-64
}

Write-Host "[3/6] Ensuring services are running..."
$mongoStarted = Ensure-ServiceStarted -ServiceName "MongoDB"

$redisStarted = Ensure-ServiceStarted -ServiceName "Memurai"
if (-not $redisStarted) {
  $redisStarted = Ensure-ServiceStarted -ServiceName "Redis"
}

if (-not $mongoStarted) {
  Write-Warning "MongoDB service not found. Check installation logs and install status."
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

Write-Host "[5/6] Applying Django migrations..."
Push-Location (Join-Path $ProjectRoot "backend")
& $pythonExe manage.py migrate
Pop-Location

Write-Host "[6/6] Completed."
Write-Host "MongoDB default: mongodb://127.0.0.1:27017"
Write-Host "Redis default: redis://127.0.0.1:6379"
Write-Host "Start Django: cd backend; $pythonExe manage.py runserver"
Write-Host "Start Celery: cd backend; $pythonExe -m celery -A config worker -l info"
