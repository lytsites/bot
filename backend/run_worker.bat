@echo off
cd /d %~dp0
set FRONTEND_ORIGIN=http://localhost:5173
set DB_PATH=%cd%\data.sqlite3

py -3.11 -m worker.main
pause
