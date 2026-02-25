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


def _send_plain_text(*, text: str) -> int:
    if not _enabled():
        return 0
    recipients = _load_recipients()
    if not recipients:
        return 0
    url = f"https://api.telegram.org/bot{TG_ALERT_BOT_TOKEN}/sendMessage"
    delivered = 0
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
            else:
                delivered += 1
        except Exception as exc:
            logger.warning("telegram message exception chat_id=%s err=%s: %s", chat_id, type(exc).__name__, exc)
    return delivered


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


def flush_new_incident_alerts(limit: int = 100) -> int:
    """
    Send incident records (the same sources used in Monitoring -> Incidents) to alert bot subscribers.
    Sends each incident only once globally using alert_bot_incident_sent marker table.
    """
    if not _enabled():
        return 0

    recipients = _load_recipients()
    if not recipients:
        return 0

    with db() as con:
        rows = con.execute(
            """
            SELECT *
            FROM (
                SELECT
                    'events' AS source,
                    CAST(e.id AS TEXT) AS source_id,
                    e.created_at AS created_at,
                    e.account_id AS account_id,
                    a.local_user_id AS local_user_id,
                    e.message AS message,
                    NULL AS context
                FROM events e
                LEFT JOIN accounts a ON a.id = e.account_id
                WHERE UPPER(COALESCE(e.level, ''))='ERROR'

                UNION ALL

                SELECT
                    'jobs' AS source,
                    CAST(j.id AS TEXT) AS source_id,
                    j.updated_at AS created_at,
                    j.account_id AS account_id,
                    a.local_user_id AS local_user_id,
                    COALESCE(j.last_error, 'JOB_FAILED') AS message,
                    ('type=' || COALESCE(j.type, '') || '; status=' || COALESCE(j.status, '')) AS context
                FROM jobs j
                LEFT JOIN accounts a ON a.id = j.account_id
                WHERE j.status='FAILED' OR COALESCE(j.last_error, '')<>''

                UNION ALL

                SELECT
                    'group_worker_runs' AS source,
                    CAST(gwr.id AS TEXT) AS source_id,
                    COALESCE(gwr.stopped_at, gwr.started_at) AS created_at,
                    gwr.account_id AS account_id,
                    a.local_user_id AS local_user_id,
                    gwr.last_error AS message,
                    ('status=' || COALESCE(gwr.status, '')) AS context
                FROM group_worker_runs gwr
                LEFT JOIN accounts a ON a.id = gwr.account_id
                WHERE COALESCE(gwr.last_error, '')<>''

                UNION ALL

                SELECT
                    'auto_chat_dialogs' AS source,
                    CAST(d.id AS TEXT) AS source_id,
                    d.updated_at AS created_at,
                    d.account_id AS account_id,
                    a.local_user_id AS local_user_id,
                    COALESCE(d.last_error, 'AUTO_CHAT_ERROR') AS message,
                    (
                        'status=' || COALESCE(d.status, '')
                        || '; peer=' || COALESCE(d.peer_username, CAST(d.peer_tg_user_id AS TEXT), '')
                    ) AS context
                FROM auto_chat_dialogs d
                LEFT JOIN accounts a ON a.id = d.account_id
                WHERE d.status='ERROR' OR COALESCE(d.last_error, '')<>''

                UNION ALL

                SELECT
                    'auth_flows' AS source,
                    COALESCE(af.auth_id, '') AS source_id,
                    af.expires_at AS created_at,
                    af.account_id AS account_id,
                    af.local_user_id AS local_user_id,
                    COALESCE(af.error_message, af.status, 'AUTH_FLOW_ERROR') AS message,
                    (
                        'auth_id=' || COALESCE(af.auth_id, '')
                        || '; method=' || COALESCE(af.method, '')
                        || '; status=' || COALESCE(af.status, '')
                    ) AS context
                FROM auth_flows af
                WHERE af.status='ERROR' OR COALESCE(af.error_message, '')<>''
            ) x
            LEFT JOIN alert_bot_incident_sent s
              ON s.source = x.source AND s.source_id = x.source_id
            WHERE s.source IS NULL
            ORDER BY x.created_at ASC, x.source_id ASC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

        sent = 0
        for row in rows:
            source = str(row["source"] or "")
            source_id = str(row["source_id"] or "")
            if not source or not source_id:
                continue
            text = _format_message(
                source=source,
                message=str(row["message"] or ""),
                context=str(row["context"] or "") or None,
                account_id=row["account_id"],
                local_user_id=row["local_user_id"],
            )
            delivered = _send_plain_text(text=text)
            if delivered <= 0:
                # No successful delivery; do not burn the incident marker.
                continue
            con.execute(
                """
                INSERT OR IGNORE INTO alert_bot_incident_sent(source, source_id, sent_at)
                VALUES (?, ?, ?)
                """,
                (source, source_id, _now_iso()),
            )
            sent += 1
    return sent


def mark_current_incidents_as_sent(limit: int = 100000) -> int:
    """
    Mark currently existing incidents as sent without delivering to bot.
    Used once on worker start to avoid historical spam.
    """
    with db() as con:
        rows = con.execute(
            """
            SELECT source, source_id
            FROM (
                SELECT 'events' AS source, CAST(e.id AS TEXT) AS source_id
                FROM events e
                WHERE UPPER(COALESCE(e.level, ''))='ERROR'

                UNION ALL

                SELECT 'jobs' AS source, CAST(j.id AS TEXT) AS source_id
                FROM jobs j
                WHERE j.status='FAILED' OR COALESCE(j.last_error, '')<>''

                UNION ALL

                SELECT 'group_worker_runs' AS source, CAST(gwr.id AS TEXT) AS source_id
                FROM group_worker_runs gwr
                WHERE COALESCE(gwr.last_error, '')<>''

                UNION ALL

                SELECT 'auto_chat_dialogs' AS source, CAST(d.id AS TEXT) AS source_id
                FROM auto_chat_dialogs d
                WHERE d.status='ERROR' OR COALESCE(d.last_error, '')<>''

                UNION ALL

                SELECT 'auth_flows' AS source, COALESCE(af.auth_id, '') AS source_id
                FROM auth_flows af
                WHERE af.status='ERROR' OR COALESCE(af.error_message, '')<>''
            ) x
            LEFT JOIN alert_bot_incident_sent s
              ON s.source = x.source AND s.source_id = x.source_id
            WHERE s.source IS NULL
              AND COALESCE(x.source_id, '') <> ''
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        marked = 0
        ts = _now_iso()
        for row in rows:
            con.execute(
                """
                INSERT OR IGNORE INTO alert_bot_incident_sent(source, source_id, sent_at)
                VALUES (?, ?, ?)
                """,
                (str(row["source"]), str(row["source_id"]), ts),
            )
            marked += 1
    return marked
