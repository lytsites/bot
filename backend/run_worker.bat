@echo off
cd /d "%~dp0"
set "FRONTEND_ORIGIN=http://localhost:5173"
set "DB_PATH=%cd%\var\data.sqlite3"
set "LOG_PATH=%cd%\var\logs\app.log"

py -3.11 -m worker.main
pause
