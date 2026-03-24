import hashlib
import uuid

from common.db import db
from common.timezone import add_minutes_iso, now_iso, parse_iso_local, almaty_now_naive


SESSION_TTL_HOURS = 24


def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_session(user_id: int) -> dict:
    token = str(uuid.uuid4())
    now = now_iso()
    expires_at = add_minutes_iso(SESSION_TTL_HOURS * 60)
    with db() as con:
        con.execute(
            """
            INSERT INTO local_sessions(token, user_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (token, user_id, now, expires_at),
        )
        con.execute("UPDATE local_users SET last_online_at=? WHERE id=?", (now, user_id))
    return {"token": token, "expires_at": expires_at}


def verify_token(token: str | None) -> int | None:
    if not token:
        return None
    with db() as con:
        row = con.execute(
            """
            SELECT user_id, expires_at
            FROM local_sessions
            WHERE token = ?
            """,
            (token,),
        ).fetchone()
    if not row:
        return None
    expires_at = parse_iso_local(row["expires_at"])
    if not expires_at or almaty_now_naive() >= expires_at:
        return None
    return row["user_id"]


def revoke_token(token: str) -> None:
    with db() as con:
        con.execute("DELETE FROM local_sessions WHERE token = ?", (token,))
