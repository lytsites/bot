import os
from pathlib import Path

from dotenv import load_dotenv


for env_path in (Path.cwd() / ".env", Path.cwd().parent / ".env"):
    if env_path.exists():
        load_dotenv(env_path)

TG_API_ID_RAW = os.getenv("TG_API_ID")
TG_API_HASH = os.getenv("TG_API_HASH")

TG_API_ID = None
if TG_API_ID_RAW:
    TG_API_ID = int(TG_API_ID_RAW)

DB_PATH = os.getenv("DB_PATH", "data.sqlite3")
_origins = os.getenv("FRONTEND_ORIGINS") or os.getenv("FRONTEND_ORIGIN") or "http://localhost:5173"
FRONTEND_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]
FRONTEND_ORIGIN = FRONTEND_ORIGINS[0] if FRONTEND_ORIGINS else "http://localhost:5173"

LOG_PATH = os.getenv("LOG_PATH", "logs/app.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

SESSION_ENC_KEY = os.getenv("SESSION_ENC_KEY")

AUTH_FLOW_TTL_MINUTES = int(os.getenv("AUTH_FLOW_TTL_MINUTES", "10"))

QR_TTL_SECONDS = int(os.getenv("QR_TTL_SECONDS", "180"))
QR_REFRESH_AFTER_SECONDS = int(os.getenv("QR_REFRESH_AFTER_SECONDS", "120"))
