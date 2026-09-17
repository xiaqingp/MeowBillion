@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$port=8090;" ^
  "$listeners=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue;" ^
  "if (-not $listeners) { Write-Host ('No MeowBillion server is listening on port ' + $port + '.'); exit 0 }" ^
  "foreach ($listener in $listeners) {" ^
  "  $process=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $listener.OwningProcess);" ^
  "  if (-not $process -or $process.CommandLine -notmatch 'server\.py') { throw ('Port ' + $port + ' belongs to ' + $process.Name + '. Refusing to stop it.') }" ^
  "  Stop-Process -Id $listener.OwningProcess -Force;" ^
  "  Write-Host ('Stopped MeowBillion process ' + $listener.OwningProcess + '.')" ^
  "}"
set "exitCode=%ERRORLEVEL%"
pause
exit /b %exitCode%
