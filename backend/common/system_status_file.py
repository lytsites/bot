from __future__ import annotations

import json
import os
from pathlib import Path

from common.timezone import now_iso


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_STATUS_FILE = ROOT_DIR / "frontend" / "dist" / "system-status.json"
STATUS_FILE_PATH = Path(os.getenv("APP_SYSTEM_STATUS_FILE", str(DEFAULT_STATUS_FILE)))


def write_system_status(*, restarting: bool, reason: str = "", until: str = "") -> None:
    STATUS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "restarting": bool(restarting),
        "reason": str(reason or ""),
        "until": str(until or ""),
        "updated_at": now_iso(),
    }
    tmp_path = STATUS_FILE_PATH.with_suffix(f"{STATUS_FILE_PATH.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(STATUS_FILE_PATH)


def set_system_status_restarting(*, reason: str = "", until: str = "") -> None:
    write_system_status(restarting=True, reason=reason, until=until)


def clear_system_status_restarting() -> None:
    write_system_status(restarting=False, reason="", until="")
