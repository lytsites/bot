@echo off
cd /d "%~dp0"
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%cd%\scripts\watchdog_service.ps1" -BackendDir "%cd%" -ServiceBat "run_main_service.bat" -ProcessPattern "main_api.main:app" -CheckUrl "http://127.0.0.1:8000/openapi.json" -LogName "main_watchdog.log"
