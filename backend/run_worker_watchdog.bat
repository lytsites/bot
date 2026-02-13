@echo off
cd /d "%~dp0"
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%cd%\scripts\watchdog_service.ps1" -BackendDir "%cd%" -ServiceBat "run_worker_service.bat" -ProcessPattern "worker.main" -LogName "worker_watchdog.log"
