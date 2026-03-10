from __future__ import annotations

from datetime import timedelta

from common.timezone import almaty_now_naive, now_iso, parse_iso_local


SYSTEM_RESTARTING_FLAG = "system_restarting"
SYSTEM_RESTARTING_TTL_SECONDS = 180


def set_flag(con, key: str, value_text: str = "", ttl_seconds: int | None = None) -> None:
    expires_at = None
    if ttl_seconds is not None and ttl_seconds > 0:
        expires_at = (almaty_now_naive() + timedelta(seconds=ttl_seconds)).isoformat()
    con.execute(
        """
        INSERT INTO system_flags(flag_key, value_text, expires_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(flag_key) DO UPDATE SET
            value_text=excluded.value_text,
            expires_at=excluded.expires_at,
            updated_at=excluded.updated_at
        """,
        (key, str(value_text or ""), expires_at, now_iso()),
    )


def clear_flag(con, key: str) -> None:
    con.execute("DELETE FROM system_flags WHERE flag_key=?", (key,))


def get_flag(con, key: str) -> dict | None:
    row = con.execute(
        "SELECT flag_key, value_text, expires_at, updated_at FROM system_flags WHERE flag_key=?",
        (key,),
    ).fetchone()
    if not row:
        return None
    expires_at = parse_iso_local(row["expires_at"])
    if expires_at is not None and expires_at <= almaty_now_naive():
        clear_flag(con, key)
        return None
    return dict(row)


def set_system_restarting(con, reason: str = "", ttl_seconds: int = SYSTEM_RESTARTING_TTL_SECONDS) -> None:
    set_flag(con, SYSTEM_RESTARTING_FLAG, value_text=reason, ttl_seconds=ttl_seconds)


def clear_system_restarting(con) -> None:
    clear_flag(con, SYSTEM_RESTARTING_FLAG)


def get_system_restarting(con) -> dict | None:
    return get_flag(con, SYSTEM_RESTARTING_FLAG)
