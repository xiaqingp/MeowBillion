param(
    [switch]$Restart
)

$ErrorActionPreference = 'Stop'
$port = 8090
$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1

if ($listener) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    if ($process.CommandLine -notmatch 'server\.py') {
        throw "Port $port is already used by $($process.Name). Refusing to stop it."
    }
    if (-not $Restart) {
        Write-Host "MeowBillion is already listening on port $port. Use -Restart to restart it."
        exit 0
    }
    Stop-Process -Id $listener.OwningProcess -Force
    Start-Sleep -Milliseconds 500
}

$env:HOST = '0.0.0.0'
$env:PORT = "$port"
$tailscaleIp = (& tailscale ip -4 2>$null | Select-Object -First 1)
Write-Host "Starting MeowBillion at http://127.0.0.1:$port"
if ($tailscaleIp) {
    Write-Host "Tailscale address: http://${tailscaleIp}:$port"
}
& py server.py
