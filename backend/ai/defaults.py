from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common.logging_setup import get_logger


_DEFAULTS_DIR = Path(__file__).resolve().parent / "defaults"
_DEFAULTS_JSON = _DEFAULTS_DIR / "new_local_user.json"
_DEFAULTS_INSTRUCTION = _DEFAULTS_DIR / "new_local_user_instruction.txt"
_DEFAULTS_GREETINGS = _DEFAULTS_DIR / "new_local_user_greeting_examples.txt"
_SUPPORT_SITE_STRUCTURE = _DEFAULTS_DIR / "support_site_structure_instruction.txt"

logger = get_logger("ai.defaults")


@dataclass(frozen=True)
class NewLocalUserDefaults:
    ai_instruction: str
    greeting_examples: str
    delay_enabled: int
    delay_min_ms: int
    delay_max_ms: int
    typing_enabled: int
    read_enabled: int


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception as e:
        logger.info("defaults read failed path=%s err=%s: %s", str(p), type(e).__name__, e)
        return ""


def _as_int(v: Any, default: int = 0) -> int:
    try:
        if isinstance(v, bool):
            return 1 if v else 0
        return int(v)
    except Exception:
        return default


def load_new_local_user_defaults() -> NewLocalUserDefaults:
    data: dict[str, Any] = {}
    try:
        if _DEFAULTS_JSON.exists():
            data = json.loads(_DEFAULTS_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        logger.info("defaults json parse failed path=%s err=%s: %s", str(_DEFAULTS_JSON), type(e).__name__, e)
        data = {}

    delay_enabled = 1 if bool(data.get("delay_enabled", False)) else 0
    typing_enabled = 1 if bool(data.get("typing_enabled", False)) else 0
    read_enabled = 1 if bool(data.get("read_enabled", False)) else 0
    delay_min_ms = max(0, _as_int(data.get("delay_min_ms", 0), 0))
    delay_max_ms = max(0, _as_int(data.get("delay_max_ms", 0), 0))
    if delay_max_ms and delay_min_ms and delay_max_ms < delay_min_ms:
        delay_min_ms, delay_max_ms = delay_max_ms, delay_min_ms

    ai_instruction = _read_text(_DEFAULTS_INSTRUCTION).strip()
    greeting_examples = _read_text(_DEFAULTS_GREETINGS).strip()

    return NewLocalUserDefaults(
        ai_instruction=ai_instruction,
        greeting_examples=greeting_examples,
        delay_enabled=delay_enabled,
        delay_min_ms=delay_min_ms,
        delay_max_ms=delay_max_ms,
        typing_enabled=typing_enabled,
        read_enabled=read_enabled,
    )


def load_support_site_structure_instruction() -> str:
    return _read_text(_SUPPORT_SITE_STRUCTURE).strip()
