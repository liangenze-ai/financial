Param(
  [string]$ProjectRoot = "$(Resolve-Path "$PSScriptRoot\..").Path"
)

$ErrorActionPreference = "Stop"

Write-Host "[1/6] Checking package managers..."
$hasWinget = $null -ne (Get-Command winget -ErrorAction SilentlyContinue)
$hasChoco = $null -ne (Get-Command choco -ErrorAction SilentlyContinue)

if (-not $hasWinget -and -not $hasChoco) {
  throw "Neither winget nor choco found. Install one of them first."
}

Write-Host "[2/6] Installing MongoDB and Redis..."
if ($hasWinget) {
  try {
    winget install -e --id MongoDB.Server --accept-source-agreements --accept-package-agreements
    winget install -e --id Memurai.MemuraiDeveloper --accept-source-agreements --accept-package-agreements
  } catch {
    if ($hasChoco) {
      choco install -y mongodb redis-64
    } else {
      throw "winget install failed and choco not found."
    }
  }
} else {
  choco install -y mongodb redis-64
}

Write-Host "[3/6] Ensuring services are running..."
$mongoService = Get-Service -Name MongoDB -ErrorAction SilentlyContinue
if ($mongoService) {
  Set-Service -Name MongoDB -StartupType Automatic
  Start-Service -Name MongoDB -ErrorAction SilentlyContinue
}

$redisService = Get-Service -Name "Memurai" -ErrorAction SilentlyContinue
if (-not $redisService) {
  $redisService = Get-Service -Name "Redis" -ErrorAction SilentlyContinue
}
if ($redisService) {
  Set-Service -Name $redisService.Name -StartupType Automatic
  Start-Service -Name $redisService.Name -ErrorAction SilentlyContinue
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
