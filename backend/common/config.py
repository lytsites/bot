import os
from pathlib import Path

from dotenv import load_dotenv


def _load_env():
    # Try a few likely locations to make deployment less fragile:
    # - current working directory
    # - parent of current working directory
    # - repo root (two levels above backend/common)
    candidates = []
    try:
        candidates.extend([Path.cwd() / ".env", Path.cwd().parent / ".env"])
    except Exception:
        pass
    try:
        repo_root = Path(__file__).resolve().parents[2]
        candidates.append(repo_root / ".env")
    except Exception:
        pass
    for env_path in candidates:
        if env_path and env_path.exists():
            load_dotenv(env_path)


_load_env()

_REPO_ROOT = None
try:
    # backend/common/config.py -> common -> backend -> repo root
    _REPO_ROOT = Path(__file__).resolve().parents[2]
except Exception:
    _REPO_ROOT = None

TG_API_ID_RAW = os.getenv("TG_API_ID")
TG_API_HASH = os.getenv("TG_API_HASH")

TG_API_ID = None
if TG_API_ID_RAW:
    TG_API_ID = int(TG_API_ID_RAW)

_db_path = os.getenv("DB_PATH")
if _db_path:
    p = Path(_db_path)
    if _REPO_ROOT and not p.is_absolute():
        DB_PATH = str((_REPO_ROOT / p).resolve())
    else:
        DB_PATH = _db_path
else:
    if _REPO_ROOT:
        DB_PATH = str((_REPO_ROOT / "backend" / "var" / "data.sqlite3").resolve())
    else:
        DB_PATH = "data.sqlite3"

_origins = os.getenv("FRONTEND_ORIGINS") or os.getenv("FRONTEND_ORIGIN") or "http://localhost:5173"
FRONTEND_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]
FRONTEND_ORIGIN = FRONTEND_ORIGINS[0] if FRONTEND_ORIGINS else "http://localhost:5173"

_log_path = os.getenv("LOG_PATH")
if _log_path:
    p = Path(_log_path)
    if _REPO_ROOT and not p.is_absolute():
        LOG_PATH = str((_REPO_ROOT / p).resolve())
    else:
        LOG_PATH = _log_path
else:
    if _REPO_ROOT:
        LOG_PATH = str((_REPO_ROOT / "backend" / "var" / "logs" / "app.log").resolve())
    else:
        LOG_PATH = "logs/app.log"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

SESSION_ENC_KEY = os.getenv("SESSION_ENC_KEY")

AUTH_FLOW_TTL_MINUTES = int(os.getenv("AUTH_FLOW_TTL_MINUTES", "10"))

QR_TTL_SECONDS = int(os.getenv("QR_TTL_SECONDS", "180"))
QR_REFRESH_AFTER_SECONDS = int(os.getenv("QR_REFRESH_AFTER_SECONDS", "120"))
QR_START_TIMEOUT_SECONDS = int(os.getenv("QR_START_TIMEOUT_SECONDS", "20"))
