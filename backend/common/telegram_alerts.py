from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

import httpx

from common.config import TG_ALERT_BOT_CHAT_IDS, TG_ALERT_BOT_TOKEN
from common.db import db
from common.logging_setup import get_logger


logger = get_logger("telegram.alerts")


def _enabled() -> bool:
    return bool(TG_ALERT_BOT_TOKEN)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def register_subscriber(
    *,
    chat_id: str,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    source: str = "start",
) -> None:
    if not chat_id:
        return
    ts = _now_iso()
    with db() as con:
        con.execute(
            """
            INSERT INTO alert_bot_subscribers(
                chat_id, username, first_name, last_name, is_active, source, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                is_active=1,
                source=excluded.source,
                updated_at=excluded.updated_at
            """,
            (chat_id, username, first_name, last_name, source, ts, ts),
        )


def deactivate_subscriber(chat_id: str) -> None:
    if not chat_id:
        return
    with db() as con:
        con.execute(
            """
            UPDATE alert_bot_subscribers
            SET is_active=0, updated_at=?
            WHERE chat_id=?
            """,
            (_now_iso(), chat_id),
        )


def _load_recipients() -> list[tuple[str, bool]]:
    recipients: list[tuple[str, bool]] = []
    seen: set[str] = set()

    with db() as con:
        rows = con.execute(
            """
            SELECT chat_id
            FROM alert_bot_subscribers
            WHERE is_active=1
            ORDER BY id ASC
            """
        ).fetchall()
    for row in rows:
        chat_id = str(row["chat_id"] or "").strip()
        if not chat_id or chat_id in seen:
            continue
        recipients.append((chat_id, True))
        seen.add(chat_id)

    for chat_id in TG_ALERT_BOT_CHAT_IDS:
        cid = str(chat_id or "").strip()
        if not cid or cid in seen:
            continue
        recipients.append((cid, False))
        seen.add(cid)

    return recipients


def _format_message(
    *,
    source: str,
    message: str,
    context: Optional[str] = None,
    account_id: Optional[int] = None,
    local_user_id: Optional[int] = None,
) -> str:
    parts = [
        "TG WEB AUTH ERROR",
        f"source: {source}",
    ]
    if account_id is not None:
        parts.append(f"account_id: {account_id}")
    if local_user_id is not None:
        parts.append(f"local_user_id: {local_user_id}")
    if context:
        parts.append(f"context: {context}")
    parts.append(f"message: {message or '-'}")
    text = "\n".join(parts)
    if len(text) > 3800:
        text = text[:3800] + "...(truncated)"
    return text


def _send_plain_text(*, text: str) -> None:
    if not _enabled():
        return
    recipients = _load_recipients()
    if not recipients:
        return
    url = f"https://api.telegram.org/bot{TG_ALERT_BOT_TOKEN}/sendMessage"
    for chat_id, managed in recipients:
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "disable_web_page_preview": True,
                    },
                )
            if r.status_code >= 400:
                logger.warning("telegram message failed chat_id=%s code=%s body=%s", chat_id, r.status_code, r.text[:500])
                if managed and r.status_code in (400, 403):
                    deactivate_subscriber(chat_id)
        except Exception as exc:
            logger.warning("telegram message exception chat_id=%s err=%s: %s", chat_id, type(exc).__name__, exc)


def notify_error(
    *,
    source: str,
    message: str,
    context: Optional[str] = None,
    account_id: Optional[int] = None,
    local_user_id: Optional[int] = None,
) -> None:
    if not _enabled():
        return

    text = _format_message(
        source=source,
        message=message,
        context=context,
        account_id=account_id,
        local_user_id=local_user_id,
    )
    _send_plain_text(text=text)


def notify_support_request(
    *,
    ticket_id: int,
    local_user_id: int,
    local_login: str,
    subject: str,
    message: str,
) -> None:
    text = "\n".join(
        [
            "TG WEB AUTH SUPPORT",
            f"ticket_id: {ticket_id}",
            f"local_user_id: {local_user_id}",
            f"local_login: {local_login or '-'}",
            f"subject: {subject or '-'}",
            f"message: {message or '-'}",
        ]
    )
    if len(text) > 3800:
        text = text[:3800] + "...(truncated)"
    _send_plain_text(text=text)
