@echo off
cd /d "%~dp0"
rem Frontend origins allowed for CORS (comma-separated).
rem Add both http/https because Cloudflare tunnel may serve either depending on your settings.
set "FRONTEND_ORIGINS=https://prok.services,http://prok.services,https://node.e-qoldau.asia,http://localhost:5173"

rem Optional overrides:
rem set DEEPSEEK_API_KEY=
rem set DEEPSEEK_BASE_URL=https://api.deepseek.com
rem set DEEPSEEK_MODEL=deepseek-chat
rem set DEEPSEEK_HTTP_TIMEOUT=120

set "PY=python"
py -3.11 -V >nul 2>nul && set "PY=py -3.11"

%PY% -m uvicorn ai_api.main:app --host 0.0.0.0 --port 8002
pause
