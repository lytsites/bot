@echo off
cd /d "%~dp0"
rem Frontend origins allowed for CORS (comma-separated).
rem Add both http/https because Cloudflare tunnel may serve either depending on your settings.
set "FRONTEND_ORIGINS=https://prok.services,http://prok.services,https://node.e-qoldau.asia,http://localhost:5173"
set "DB_PATH=%cd%\var\data.sqlite3"
set "LOG_PATH=%cd%\var\logs\app.log"

py -3.11 -m uvicorn main_api.main:app --host 0.0.0.0 --port 8000
pause
