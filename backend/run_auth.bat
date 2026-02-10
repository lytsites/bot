@echo off
cd /d "%~dp0"
rem Set secrets via .env or here before запуск
rem set TG_API_ID=
rem set TG_API_HASH=
rem Frontend origins allowed for CORS (comma-separated).
rem Add both http/https because Cloudflare tunnel may serve either depending on your settings.
set "FRONTEND_ORIGINS=https://prok.services,http://prok.services,https://node.e-qoldau.asia,http://localhost:5173"
set "DB_PATH=%cd%\var\data.sqlite3"
set "LOG_PATH=%cd%\var\logs\app.log"

set "PY=python"
py -3.11 -V >nul 2>nul && set "PY=py -3.11"

%PY% -m uvicorn auth_api.main:app --host 0.0.0.0 --port 8001
pause
