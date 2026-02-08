from __future__ import annotations

from typing import Optional

from common.db import db


def ensure_auto_chat_settings_row(user_id: int, now_iso: str) -> None:
    with db() as con:
        con.execute(
            """
            INSERT OR IGNORE INTO local_user_auto_chat_settings(user_id, ai_instruction, greeting_examples, created_at, updated_at)
            VALUES (?, '', '', ?, ?)
            """,
            (user_id, now_iso, now_iso),
        )


def get_auto_chat_settings(user_id: int) -> Optional[dict]:
    with db() as con:
        row = con.execute(
            """
            SELECT ai_instruction, greeting_examples, created_at, updated_at
            FROM local_user_auto_chat_settings
            WHERE user_id=?
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None

