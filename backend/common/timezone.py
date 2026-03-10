from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


ALMATY_TZ = ZoneInfo("Asia/Almaty")


def almaty_now() -> datetime:
    return datetime.now(ALMATY_TZ)


def almaty_now_naive() -> datetime:
    return almaty_now().replace(tzinfo=None)


def now_iso() -> str:
    return almaty_now_naive().isoformat()


def add_minutes_iso(minutes: int) -> str:
    return (almaty_now_naive() + timedelta(minutes=minutes)).isoformat()


def add_seconds_iso(seconds: int) -> str:
    return (almaty_now_naive() + timedelta(seconds=seconds)).isoformat()


def parse_iso_local(value: str | None) -> datetime | None:
    try:
        if not value:
            return None
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is not None:
            dt = dt.astimezone(ALMATY_TZ).replace(tzinfo=None)
        return dt
    except Exception:
        return None
