@echo off
cd /d "%~dp0"
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%cd%\scripts\watchdog_service.ps1" -BackendDir "%cd%" -ServiceBat "run_auth_service.bat" -ProcessPattern "auth_api.main:app" -CheckUrl "http://127.0.0.1:8001/openapi.json" -LogName "auth_watchdog.log"
