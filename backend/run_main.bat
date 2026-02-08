@echo off
cd /d "%~dp0"
set "FRONTEND_ORIGINS=https://node.e-qoldau.asia,http://localhost:5173"
set "DB_PATH=%cd%\data.sqlite3"

py -3.11 -m uvicorn main_api.main:app --host 0.0.0.0 --port 8000
pause
