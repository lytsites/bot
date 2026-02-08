@echo off
cd /d "%~dp0"
rem Set secrets via .env or here before запуск
rem set TG_API_ID=
rem set TG_API_HASH=
set "FRONTEND_ORIGINS=https://node.e-qoldau.asia,http://localhost:5173"
set "DB_PATH=%cd%\data.sqlite3"

py -3.11 -m uvicorn auth_api.main:app --host 0.0.0.0 --port 8001
pause
