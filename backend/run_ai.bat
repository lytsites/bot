@echo off
cd /d %~dp0
set FRONTEND_ORIGINS=https://node.e-qoldau.asia,http://localhost:5173

rem Optional overrides:
rem set DEEPSEEK_API_KEY=
rem set DEEPSEEK_BASE_URL=https://api.deepseek.com
rem set DEEPSEEK_MODEL=deepseek-chat
rem set DEEPSEEK_HTTP_TIMEOUT=120

py -3.11 -m uvicorn ai_api.main:app --host 0.0.0.0 --port 8002
pause
