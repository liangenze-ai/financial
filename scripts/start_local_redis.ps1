<#
.SYNOPSIS
  Start a local Redis server for backend development.

.DESCRIPTION
  This script starts redis-server.exe from a local Windows Redis directory. It
  writes a project-specific redis.windows.local.conf file, creates the Redis
  data directory if needed, checks whether Redis is already responding to PING,
  and starts redis-server in a hidden window when needed.

  It is useful for local Django/Celery development when Redis is not installed
  as a Windows Service. If you use Memurai or Redis as a service, you can start
  that service instead and skip this script.

  Defaults:
    RedisDir: D:\software\redis
    Port:     6379
    Config:   RedisDir\redis.windows.local.conf
    Data:     RedisDir\data
    Log:      RedisDir\redis.log
    Bind:     127.0.0.1

  The generated config enables appendonly persistence and stores data/logs
  under RedisDir.

.PARAMETER RedisDir
  Directory containing redis-server.exe and redis-cli.exe.

.PARAMETER Port
  TCP port for Redis and the redis-cli PING check.

.EXAMPLE
  .\scripts\start_local_redis.ps1

  Start Redis from D:\software\redis on port 6379.

.EXAMPLE
  .\scripts\start_local_redis.ps1 -RedisDir D:\tools\redis -Port 16379

  Start Redis from an explicit directory on a non-default port.

.EXAMPLE
  .\scripts\start_local_redis.ps1; cd backend; ..\.venv\Scripts\python.exe -m celery -A config worker -l info

  Start Redis and then run a local Celery worker.

.NOTES
  This script overwrites redis.windows.local.conf in RedisDir each time it
  runs. Keep custom Redis configuration in another file if needed.
#>

Param(
  [string]$RedisDir = "D:\software\redis",
  [int]$Port = 6379
)

$ErrorActionPreference = "Stop"

$redisServer = Join-Path $RedisDir "redis-server.exe"
$redisCli = Join-Path $RedisDir "redis-cli.exe"
$confFile = Join-Path $RedisDir "redis.windows.local.conf"
$dataDir = Join-Path $RedisDir "data"
$logFile = Join-Path $RedisDir "redis.log"
$redisDirConfig = $RedisDir.Replace('\', '/')
$dataDirConfig = $dataDir.Replace('\', '/')
$logFileConfig = $logFile.Replace('\', '/')

if (-not (Test-Path $redisServer)) {
  throw "Redis server not found: $redisServer"
}
if (-not (Test-Path $redisCli)) {
  throw "Redis CLI not found: $redisCli"
}

New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

@"
bind 127.0.0.1
protected-mode yes
port $Port
timeout 0
tcp-keepalive 300
daemonize no
supervised no
loglevel notice
logfile "$logFileConfig"
databases 16
dir "$dataDirConfig"
dbfilename dump.rdb
appendonly yes
appendfilename "appendonly.aof"
"@ | Set-Content -LiteralPath $confFile -Encoding ASCII

function Test-RedisPing {
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    $output = & $redisCli -h 127.0.0.1 -p $Port ping 2>$null
    return ($LASTEXITCODE -eq 0 -and $output -eq "PONG")
  }
  finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
}

if (Test-RedisPing) {
  Write-Host "Redis already running on 127.0.0.1:$Port"
  exit 0
}

Start-Process -FilePath $redisServer -ArgumentList @($confFile) -WorkingDirectory $RedisDir -WindowStyle Hidden
Start-Sleep -Seconds 2

if (-not (Test-RedisPing)) {
  throw "Redis did not start successfully. Check $logFile"
}

Write-Host "Redis started on 127.0.0.1:$Port"
