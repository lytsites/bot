@echo off
cd /d "%~dp0"
set "FRONTEND_ORIGIN=http://localhost:5173"
set "DB_PATH=%cd%\var\data.sqlite3"
set "LOG_PATH=%cd%\var\logs\app.log"

set "PY=python"
py -3.11 -V >nul 2>nul && set "PY=py -3.11"

%PY% -m worker.main
pause
