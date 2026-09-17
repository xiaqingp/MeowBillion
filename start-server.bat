@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$port=8090;" ^
  "$listener=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1;" ^
  "if ($listener) {" ^
  "  $process=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $listener.OwningProcess);" ^
  "  if (-not $process -or $process.CommandLine -notmatch 'server\.py') { throw ('Port ' + $port + ' is already used by ' + $process.Name + '. Refusing to stop it.') }" ^
  "  Write-Host ('MeowBillion is already listening on port ' + $port + '. Run stop-server.bat first.'); exit 0" ^
  "}" ^
  "$env:HOST='0.0.0.0'; $env:PORT='8090';" ^
  "$tailscaleIp = (& tailscale ip -4 2>$null | Select-Object -First 1);" ^
  "Write-Host 'Starting MeowBillion at http://127.0.0.1:8090';" ^
  "if ($tailscaleIp) { Write-Host ('Tailscale address: http://' + $tailscaleIp + ':8090') };" ^
  "& py server.py"
set "exitCode=%ERRORLEVEL%"
pause
exit /b %exitCode%
