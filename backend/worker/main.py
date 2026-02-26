import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import os
import random
import re
from time import monotonic
from typing import Dict, List, Optional, Tuple

from telethon import TelegramClient
from telethon import events
from telethon.errors import FloodWaitError
from telethon.errors.rpcerrorlist import AuthKeyUnregisteredError
from telethon.sessions import StringSession
from telethon.tl.types import PeerUser

from common.config import TG_ALERT_BOT_TOKEN, TG_API_HASH, TG_API_ID
from common.crypto import decrypt_text
from common.db import db, init_db
from common.logging_setup import get_logger, setup_logging
from common.telegram_alerts import (
    flush_new_incident_alerts,
    mark_current_incidents_as_sent,
    notify_error,
    register_subscriber,
)
from ai.prompting import (
    build_auto_chat_system_prompt,
    build_greeting_prompt,
    build_reply_prompt,
)


setup_logging()
logger = get_logger("worker")

POLL_INTERVAL_SEC = 1.5
GROUP_LISTENER_INITIAL_SCAN_LIMIT = int(os.getenv("GROUP_LISTENER_INITIAL_SCAN_LIMIT", "200"))

STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
STATUS_CANCELLED = "CANCELLED"
RUN_STATUS_RUNNING = "RUNNING"
RUN_STATUS_STOPPED = "STOPPED"

TYPE_CONNECT_CHECK = "connect_check"
TYPE_SUBSCRIBE_EVENTS = "subscribe_events"
TYPE_READ_LAST = "read_last_messages"
TYPE_ANALYZE = "analyze_messages"

AUTO_CHAT_STATUS_STARTING = "STARTING"
AUTO_CHAT_STATUS_WAIT_REPLY = "WAIT_REPLY"
AUTO_CHAT_STATUS_ACTIVE = "ACTIVE"
AUTO_CHAT_STATUS_STOPPED = "STOPPED"
AUTO_CHAT_STATUS_ERROR = "ERROR"

AI_API_URL = os.getenv("AI_API_URL", "http://127.0.0.1:8002")
# Small human-like pause before showing "typing...".
AUTO_CHAT_PRE_TYPING_DELAY_MS = int(os.getenv("AUTO_CHAT_PRE_TYPING_DELAY_MS", "1500"))
TG_ALERT_BOT_POLL_TIMEOUT_SEC = int(os.getenv("TG_ALERT_BOT_POLL_TIMEOUT_SEC", "30"))
TG_ALERT_INCIDENTS_FLUSH_INTERVAL_SEC = int(os.getenv("TG_ALERT_INCIDENTS_FLUSH_INTERVAL_SEC", "5"))
TG_ALERT_INCIDENTS_FLUSH_BATCH = int(os.getenv("TG_ALERT_INCIDENTS_FLUSH_BATCH", "100"))
AUTO_CHAT_INCOMING_BUFFER_MS = max(0, int(os.getenv("AUTO_CHAT_INCOMING_BUFFER_MS", "3500")))


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def _buffer_ready_at_iso() -> str:
    return (datetime.utcnow() + timedelta(milliseconds=AUTO_CHAT_INCOMING_BUFFER_MS)).isoformat()


class JobCancelled(Exception):
    pass


@dataclass
class ClientState:
    session_string: str
    client: TelegramClient


class ClientManager:
    def __init__(self) -> None:
        self._clients: Dict[int, ClientState] = {}

    async def get_client(self, account_id: int) -> TelegramClient:
        session_string = self._load_active_session(account_id)
        if not session_string:
            raise RuntimeError("NO_ACTIVE_SESSION")

        state = self._clients.get(account_id)
        if state and state.session_string == session_string:
            try:
                if not state.client.is_connected():
                    await state.client.connect()
                # Validate cached client before reuse; network drops can leave it disconnected.
                await state.client.get_me()
                return state.client
            except AuthKeyUnregisteredError:
                await self._drop_cached_client(account_id)
                self._revoke_active_sessions(account_id)
                raise RuntimeError("SESSION_INVALID")
            except Exception as exc:
                logger.warning(
                    "cached client unusable account_id=%s err=%s: %s; recreating",
                    account_id,
                    type(exc).__name__,
                    exc,
                )
                await self._drop_cached_client(account_id)

        if state:
            await self._drop_cached_client(account_id)

        client = TelegramClient(StringSession(session_string), TG_API_ID, TG_API_HASH)
        await client.connect()
        # Validate auth key early so loops don't spam errors on every request.
        try:
            await client.get_me()
        except AuthKeyUnregisteredError:
            await client.disconnect()
            self._revoke_active_sessions(account_id)
            if account_id in self._clients:
                self._clients.pop(account_id, None)
            raise RuntimeError("SESSION_INVALID")
        self._clients[account_id] = ClientState(session_string=session_string, client=client)
        return client

    async def _drop_cached_client(self, account_id: int) -> None:
        state = self._clients.pop(account_id, None)
        if not state:
            return
        try:
            await state.client.disconnect()
        except Exception as exc:
            logger.warning(
                "drop cached client disconnect failed account_id=%s err=%s: %s",
                account_id,
                type(exc).__name__,
                exc,
            )

    async def disconnect_all(self) -> None:
        for state in self._clients.values():
            await state.client.disconnect()
        self._clients.clear()

    async def invalidate_session(self, account_id: int) -> None:
        """Drop in-memory client and revoke active session(s) in DB for this account."""
        state = self._clients.pop(account_id, None)
        if state:
            try:
                await state.client.disconnect()
            except Exception as exc:
                logger.warning(
                    "invalidate_session disconnect failed account_id=%s err=%s: %s",
                    account_id,
                    type(exc).__name__,
                    exc,
                )
        self._revoke_active_sessions(account_id)

    @staticmethod
    def _load_active_session(account_id: int) -> Optional[str]:
        with db() as con:
            row = con.execute(
                """
                SELECT session_string
                FROM tg_sessions
                WHERE account_id=?
                  AND revoked_at IS NULL
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (account_id,),
            ).fetchone()
        if not row:
            return None
        return decrypt_text(row["session_string"])

    @staticmethod
    def _revoke_active_sessions(account_id: int) -> None:
        with db() as con:
            con.execute(
                "UPDATE tg_sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL",
                (now_iso(), account_id),
            )


class Worker:
    def __init__(self) -> None:
        self.client_manager = ClientManager()
        self._listener_task: Optional[asyncio.Task] = None
        self._auto_chat_task: Optional[asyncio.Task] = None
        self._alert_bot_task: Optional[asyncio.Task] = None
        self._alert_incidents_task: Optional[asyncio.Task] = None
        self._dialog_cache: Dict[int, Tuple[datetime, Dict[int, object]]] = {}
        # account_id -> id(client) to re-register handler if the client instance changes
        self._auto_chat_handler_client: Dict[int, int] = {}
        self._dialog_locks: Dict[int, asyncio.Lock] = {}
        self._http = None
        self._auto_chat_sem: Dict[int, asyncio.Semaphore] = {}

    @staticmethod
    def _is_disconnected_exc(exc: Exception) -> bool:
        if isinstance(exc, ConnectionError):
            return True
        msg = str(exc or "").lower()
        return "disconnected" in msg or "not connected" in msg

    async def _send_message_resilient(
        self,
        account_id: int,
        peer_id: int,
        text: str,
        peer_username: Optional[str] = None,
        attempts: int = 2,
    ):
        last_exc: Optional[Exception] = None
        for i in range(max(1, attempts)):
            try:
                live_client = await self.client_manager.get_client(account_id)
                if not live_client.is_connected():
                    await live_client.connect()
                input_peer = await self._resolve_input_peer(live_client, peer_id, peer_username)
                return await live_client.send_message(input_peer, text)
            except AuthKeyUnregisteredError:
                await self.client_manager.invalidate_session(account_id)
                raise RuntimeError("SESSION_INVALID")
            except Exception as exc:
                last_exc = exc
                if not self._is_disconnected_exc(exc):
                    raise
                logger.warning(
                    "autochat send reconnect account_id=%s attempt=%s err=%s: %s",
                    account_id,
                    i + 1,
                    type(exc).__name__,
                    exc,
                )
                await self.client_manager._drop_cached_client(account_id)
                if i + 1 < attempts:
                    await asyncio.sleep(0.5 * (i + 1))
        if last_exc:
            raise last_exc
        raise RuntimeError("SEND_FAILED")

    async def _resolve_input_peer(
        self,
        client: TelegramClient,
        peer_id: int,
        peer_username: Optional[str] = None,
    ):
        username = (peer_username or "").strip()
        if username.startswith("@"):
            username = username[1:]

        try:
            return await client.get_input_entity(peer_id)
        except Exception:
            pass

        try:
            return await client.get_input_entity(PeerUser(peer_id))
        except Exception:
            pass

        if username:
            try:
                return await client.get_input_entity(username)
            except Exception:
                pass
            try:
                ent = await client.get_entity(username)
                return await client.get_input_entity(ent)
            except Exception:
                pass

        try:
            dialogs = await client.get_dialogs(limit=300)
            for d in dialogs:
                if int(getattr(d, "id", 0) or 0) == int(peer_id):
                    try:
                        return await client.get_input_entity(d.entity)
                    except Exception:
                        break
        except Exception:
            pass

        try:
            ent = await client.get_entity(peer_id)
            return await client.get_input_entity(ent)
        except Exception as e:
            raise RuntimeError(f"PEER_RESOLVE_FAILED:{peer_id}") from e

    async def run(self) -> None:
        init_db()
        logger.info("worker started")
        self._listener_task = asyncio.create_task(self._listen_groups_loop())
        self._auto_chat_task = asyncio.create_task(self._auto_chat_loop())
        if TG_ALERT_BOT_TOKEN:
            self._alert_bot_task = asyncio.create_task(self._alert_bot_loop())
            self._alert_incidents_task = asyncio.create_task(self._alert_incidents_loop())
        try:
            while True:
                job = self._fetch_next_job()
                if not job:
                    await asyncio.sleep(POLL_INTERVAL_SEC)
                    continue
                await self._run_job(job)
        finally:
            if self._listener_task:
                self._listener_task.cancel()
            if self._auto_chat_task:
                self._auto_chat_task.cancel()
            if self._alert_bot_task:
                self._alert_bot_task.cancel()
            if self._alert_incidents_task:
                self._alert_incidents_task.cancel()
            await self.client_manager.disconnect_all()
            if self._http:
                await self._http.aclose()

    async def _ensure_http(self) -> None:
        if self._http is None:
            import httpx

            timeout_s = float(os.getenv("AI_HTTP_TIMEOUT", "300"))
            self._http = httpx.AsyncClient(timeout=timeout_s)

    async def _alert_bot_loop(self) -> None:
        await self._ensure_http()
        assert self._http is not None

        logger.info("alert bot polling enabled")
        updates_url = f"https://api.telegram.org/bot{TG_ALERT_BOT_TOKEN}/getUpdates"
        send_url = f"https://api.telegram.org/bot{TG_ALERT_BOT_TOKEN}/sendMessage"
        webhook_url = f"https://api.telegram.org/bot{TG_ALERT_BOT_TOKEN}/deleteWebhook"
        offset: Optional[int] = None

        try:
            await self._http.post(webhook_url, json={"drop_pending_updates": False})
        except Exception as exc:
            logger.warning("alert bot deleteWebhook failed err=%s: %s", type(exc).__name__, exc)

        while True:
            try:
                params = {
                    "timeout": TG_ALERT_BOT_POLL_TIMEOUT_SEC,
                    "allowed_updates": '["message","edited_message"]',
                }
                if offset is not None:
                    params["offset"] = offset

                r = await self._http.get(updates_url, params=params)
                r.raise_for_status()
                data = r.json()
                if not data.get("ok"):
                    logger.warning("alert bot getUpdates not ok: %s", str(data)[:500])
                    await asyncio.sleep(2.0)
                    continue

                updates = data.get("result") or []
                for upd in updates:
                    upd_id = int(upd.get("update_id", 0))
                    if upd_id > 0:
                        offset = upd_id + 1
                    msg = upd.get("message") or upd.get("edited_message")
                    if not isinstance(msg, dict):
                        continue
                    text = str(msg.get("text") or "").strip()
                    if not text.startswith("/start"):
                        continue

                    chat = msg.get("chat") or {}
                    chat_id = str(chat.get("id") or "").strip()
                    if not chat_id:
                        continue
                    user = msg.get("from") or {}
                    register_subscriber(
                        chat_id=chat_id,
                        username=(user.get("username") or None),
                        first_name=(user.get("first_name") or None),
                        last_name=(user.get("last_name") or None),
                        source="telegram_start",
                    )
                    logger.info("alert bot subscriber upserted chat_id=%s", chat_id)

                    try:
                        await self._http.post(
                            send_url,
                            json={
                                "chat_id": chat_id,
                                "text": "Подписка на ошибки включена.",
                                "disable_web_page_preview": True,
                            },
                        )
                    except Exception as exc:
                        logger.warning(
                            "alert bot start ack failed chat_id=%s err=%s: %s",
                            chat_id,
                            type(exc).__name__,
                            exc,
                        )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("alert bot loop failed err=%s: %s", type(exc).__name__, exc)
                await asyncio.sleep(2.0)

    async def _alert_incidents_loop(self) -> None:
        # Skip historical spam: mark all current incidents as already processed once.
        try:
            mark_current_incidents_as_sent(limit=100000)
        except Exception as exc:
            logger.warning("incident alerts baseline failed err=%s: %s", type(exc).__name__, exc)

        while True:
            try:
                sent = flush_new_incident_alerts(limit=TG_ALERT_INCIDENTS_FLUSH_BATCH)
                if sent > 0:
                    logger.info("incident alerts sent=%s", sent)
                await asyncio.sleep(max(1, TG_ALERT_INCIDENTS_FLUSH_INTERVAL_SEC))
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("incident alerts loop failed err=%s: %s", type(exc).__name__, exc)
                await asyncio.sleep(2.0)

    def _fetch_next_job(self) -> Optional[dict]:
        with db() as con:
            row = con.execute(
                """
                SELECT j.id, j.account_id, j.type, j.status, j.progress
                FROM jobs j
                JOIN accounts a ON a.id = j.account_id
                JOIN local_users u ON u.id = a.local_user_id
                WHERE j.status=?
                  AND u.is_active=1
                  AND COALESCE(u.service_enabled, 1)=1
                ORDER BY j.id ASC
                LIMIT 1
                """,
                (STATUS_PENDING,),
            ).fetchone()
            if not row:
                return None
            con.execute(
                "UPDATE jobs SET status=?, updated_at=? WHERE id=?",
                (STATUS_RUNNING, now_iso(), row["id"]),
            )
        return dict(row)

    async def _run_job(self, job: dict) -> None:
        job_id = job["id"]
        account_id = job["account_id"]
        job_type = job["type"]

        logger.info("job.start id=%s type=%s account_id=%s", job_id, job_type, account_id)
        try:
            if job_type == TYPE_CONNECT_CHECK:
                await self._job_connect_check(account_id, job_id)
            elif job_type == TYPE_SUBSCRIBE_EVENTS:
                await self._job_subscribe_events(account_id, job_id)
            elif job_type == TYPE_READ_LAST:
                await self._job_read_last(account_id, job_id)
            elif job_type == TYPE_ANALYZE:
                await self._job_analyze(account_id, job_id)
            else:
                raise ValueError("UNKNOWN_JOB_TYPE")

            self._finish_job(job_id, STATUS_DONE, None)
            logger.info("job.done id=%s", job_id)
        except JobCancelled:
            self._finish_job(job_id, STATUS_CANCELLED, None)
            logger.info("job.cancelled id=%s", job_id)
        except Exception as exc:
            self._finish_job(job_id, STATUS_FAILED, f"{type(exc).__name__}: {exc}")
            logger.exception("job.failed id=%s", job_id)

    def _finish_job(self, job_id: int, status: str, error: Optional[str]) -> None:
        meta = {"account_id": None, "job_type": None}
        with db() as con:
            row = con.execute(
                "SELECT account_id, type FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()
            if row:
                meta["account_id"] = row["account_id"]
                meta["job_type"] = row["type"]
            con.execute(
                """
                UPDATE jobs
                SET status=?, last_error=?, updated_at=?
                WHERE id=?
                """,
                (status, error, now_iso(), job_id),
            )
        if status == STATUS_FAILED and error:
            notify_error(
                source="jobs",
                account_id=meta["account_id"],
                message=error,
                context=f"job_id={job_id}; type={meta['job_type']}",
            )

    def _update_progress(self, job_id: int, progress: int) -> None:
        with db() as con:
            con.execute(
                "UPDATE jobs SET progress=?, updated_at=? WHERE id=?",
                (progress, now_iso(), job_id),
            )

    def _check_cancelled(self, job_id: int) -> bool:
        with db() as con:
            row = con.execute(
                "SELECT status FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()
        return row and row["status"] == STATUS_CANCELLED

    async def _job_connect_check(self, account_id: int, job_id: int) -> None:
        client = await self.client_manager.get_client(account_id)
        if self._check_cancelled(job_id):
            raise JobCancelled()
        await client.get_me()
        self._update_progress(job_id, 100)

    async def _job_subscribe_events(self, account_id: int, job_id: int) -> None:
        _ = await self.client_manager.get_client(account_id)
        if self._check_cancelled(job_id):
            raise JobCancelled()
        self._update_progress(job_id, 100)

    async def _job_read_last(self, account_id: int, job_id: int, limit: int = 20) -> None:
        client = await self.client_manager.get_client(account_id)
        if self._check_cancelled(job_id):
            raise JobCancelled()
        messages = await client.get_messages("me", limit=limit)
        self._update_progress(job_id, 50)
        _ = len(messages)

    async def _listen_groups_loop(self) -> None:
        while True:
            try:
                groups_by_account = self._load_active_group_listeners()
                if not groups_by_account:
                    self._stop_all_group_runs()
                    # Do not drop all clients while auto-chat may still be active.
                    # Otherwise auto-chat sends can race with disconnects and fail intermittently.
                    active_auto = self._load_accounts_with_active_auto_chat_dialogs()
                    if not active_auto:
                        await self.client_manager.disconnect_all()
                    await asyncio.sleep(3.0)
                    continue
                active_ids = set(groups_by_account.keys())
                for account_id in active_ids:
                    self._ensure_group_worker_run(account_id)
                self._stop_inactive_group_runs(active_ids)
                for account_id, group_rows in groups_by_account.items():
                    try:
                        keywords = self._load_keywords_for_account(account_id)
                        keywords = [(k or "").strip().lower() for k in (keywords or []) if (k or "").strip()]
                        keyword_patterns = self._compile_keyword_patterns(keywords)
                        if not keyword_patterns:
                            continue
                        try:
                            client = await self.client_manager.get_client(account_id)
                        except RuntimeError as e:
                            logger.info("listener skip account_id=%s reason=%s", account_id, e)
                            continue
                        except AuthKeyUnregisteredError:
                            await self.client_manager.invalidate_session(account_id)
                            continue
                        except Exception:
                            logger.exception("listener get_client failed account_id=%s", account_id)
                            continue

                        dialog_map = await self._get_dialog_map(account_id, client, {r["chat_id"] for r in group_rows})
                        for row in group_rows:
                            chat_id = row["chat_id"]
                            entity = dialog_map.get(chat_id)
                            if not entity:
                                continue
                            try:
                                await self._scan_group_messages(
                                    client, account_id, chat_id, entity, row["last_message_id"], keywords, keyword_patterns
                                )
                            except AuthKeyUnregisteredError:
                                await self.client_manager.invalidate_session(account_id)
                                break
                            except Exception:
                                logger.exception("group scan failed account_id=%s chat_id=%s", account_id, chat_id)
                    except AuthKeyUnregisteredError:
                        await self.client_manager.invalidate_session(account_id)
                        continue
                    except Exception:
                        logger.exception("listener account failed account_id=%s", account_id)
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("listener loop failed")
                await asyncio.sleep(2.0)

    def _load_active_group_listeners(self) -> Dict[int, List[dict]]:
        with db() as con:
            rows = con.execute(
                """
                SELECT gl.account_id, gl.chat_id, gl.last_message_id
                FROM group_listeners gl
                JOIN accounts a ON a.id = gl.account_id
                JOIN local_user_settings s ON s.user_id = a.local_user_id
                JOIN local_users u ON u.id = a.local_user_id
                WHERE gl.is_listening=1
                  AND s.is_active=1
                  AND u.is_active=1
                  AND COALESCE(u.service_enabled, 1)=1
                  AND COALESCE(u.feature_group_reading_enabled, 1)=1
                """
            ).fetchall()
        grouped: Dict[int, List[dict]] = {}
        for row in rows:
            grouped.setdefault(row["account_id"], []).append(dict(row))
        return grouped

    async def _auto_chat_loop(self) -> None:
        await self._ensure_http()

        while True:
            try:
                # Ensure event handlers are attached even after a worker restart,
                # so dialogs in WAIT_REPLY/ACTIVE continue to receive messages.
                for account_id in self._load_accounts_with_active_auto_chat_dialogs():
                    try:
                        client = await self.client_manager.get_client(account_id)
                    except RuntimeError as e:
                        logger.info("autochat skip handler account_id=%s reason=%s", account_id, e)
                        continue
                    except AuthKeyUnregisteredError:
                        await self.client_manager.invalidate_session(account_id)
                        continue
                    except Exception:
                        logger.exception("autochat get_client for handler failed account_id=%s", account_id)
                        continue
                    self._ensure_auto_chat_handler(account_id, client)

                starting = self._load_starting_dialogs()
                if not starting:
                    # Still process any pending incoming messages.
                    await self._process_pending_dialogs()
                    await asyncio.sleep(0.5)
                    continue

                by_account: Dict[int, List[dict]] = {}
                for d in starting:
                    by_account.setdefault(d["account_id"], []).append(d)

                for account_id, dialogs in by_account.items():
                    try:
                        client = await self.client_manager.get_client(account_id)
                    except RuntimeError as e:
                        logger.info("autochat skip greetings account_id=%s reason=%s", account_id, e)
                        continue
                    except AuthKeyUnregisteredError:
                        await self.client_manager.invalidate_session(account_id)
                        continue
                    except Exception:
                        logger.exception("autochat get_client for greetings failed account_id=%s", account_id)
                        continue

                    self._ensure_auto_chat_handler(account_id, client)

                    # sequential greetings per account (keeps Telegram rate limits calmer)
                    for d in dialogs:
                        await self._send_greeting(account_id, client, d)

                await self._process_pending_dialogs()
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("auto chat loop failed")
                await asyncio.sleep(2.0)

    def _load_starting_dialogs(self, limit: int = 50) -> List[dict]:
        with db() as con:
            rows = con.execute(
                """
                SELECT id, account_id, peer_tg_user_id, peer_username, peer_display_name
                FROM auto_chat_dialogs
                WHERE status=?
                  AND account_id IN (
                    SELECT a.id
                    FROM accounts a
                    JOIN local_users u ON u.id = a.local_user_id
                    WHERE u.is_active=1
                      AND COALESCE(u.service_enabled, 1)=1
                      AND COALESCE(u.feature_auto_dialogs_enabled, 1)=1
                  )
                ORDER BY updated_at ASC, id ASC
                LIMIT ?
                """,
                (AUTO_CHAT_STATUS_STARTING, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def _load_accounts_with_active_auto_chat_dialogs(self) -> List[int]:
        with db() as con:
            rows = con.execute(
                """
                SELECT DISTINCT d.account_id AS account_id
                FROM auto_chat_dialogs d
                JOIN accounts a ON a.id = d.account_id
                JOIN local_users u ON u.id = a.local_user_id
                WHERE u.is_active=1
                  AND COALESCE(u.service_enabled, 1)=1
                  AND COALESCE(u.feature_auto_dialogs_enabled, 1)=1
                  AND d.status IN (?, ?, ?)
                """,
                (AUTO_CHAT_STATUS_STARTING, AUTO_CHAT_STATUS_WAIT_REPLY, AUTO_CHAT_STATUS_ACTIVE),
            ).fetchall()
        return [int(r["account_id"]) for r in rows]

    def _load_pending_dialogs(self, limit: int = 80) -> List[dict]:
        now = now_iso()
        with db() as con:
            rows = con.execute(
                """
                SELECT id, account_id, peer_tg_user_id, peer_username, peer_display_name, status
                FROM auto_chat_dialogs
                WHERE pending_incoming=1
                  AND (pending_buffer_until_at IS NULL OR pending_buffer_until_at<=?)
                  AND status IN (?, ?)
                  AND account_id IN (
                    SELECT a.id
                    FROM accounts a
                    JOIN local_users u ON u.id = a.local_user_id
                    WHERE u.is_active=1
                      AND COALESCE(u.service_enabled, 1)=1
                      AND COALESCE(u.feature_auto_dialogs_enabled, 1)=1
                  )
                ORDER BY updated_at ASC, id ASC
                LIMIT ?
                """,
                (now, AUTO_CHAT_STATUS_WAIT_REPLY, AUTO_CHAT_STATUS_ACTIVE, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def _get_auto_chat_sem(self, account_id: int) -> asyncio.Semaphore:
        # Limit concurrent DeepSeek calls per account to avoid "everything waits behind one slow request".
        n = int(os.getenv("AUTO_CHAT_AI_CONCURRENCY_PER_ACCOUNT", "3"))
        sem = self._auto_chat_sem.get(account_id)
        if sem is None or getattr(sem, "_value", None) != n:
            sem = asyncio.Semaphore(n)
            self._auto_chat_sem[account_id] = sem
        return sem

    async def _process_pending_dialogs(self) -> None:
        pending = self._load_pending_dialogs()
        if not pending:
            return

        by_account: Dict[int, List[dict]] = {}
        for d in pending:
            by_account.setdefault(d["account_id"], []).append(d)

        for account_id, dialogs in by_account.items():
            try:
                client = await self.client_manager.get_client(account_id)
            except RuntimeError as e:
                logger.info("autochat skip pending account_id=%s reason=%s", account_id, e)
                continue
            except AuthKeyUnregisteredError:
                await self.client_manager.invalidate_session(account_id)
                continue
            except Exception:
                logger.exception("autochat get_client for pending failed account_id=%s", account_id)
                continue

            self._ensure_auto_chat_handler(account_id, client)
            sem = self._get_auto_chat_sem(account_id)

            async def _run_one(dlg: dict):
                async with sem:
                    await self._handle_pending_dialog(account_id, client, dlg)

            # Run up to concurrency in parallel; semaphore controls actual parallelism.
            tasks = [asyncio.create_task(_run_one(d)) for d in dialogs]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    def _ensure_auto_chat_handler(self, account_id: int, client: TelegramClient) -> None:
        prev = self._auto_chat_handler_client.get(account_id)
        if prev is not None and prev == id(client):
            return

        async def _handler(event):
            await self._on_auto_chat_message(account_id, event)

        client.add_event_handler(_handler, events.NewMessage(incoming=True))
        self._auto_chat_handler_client[account_id] = id(client)

    def _load_auto_chat_settings_for_account(self, account_id: int) -> dict:
        with db() as con:
            row = con.execute(
                """
                SELECT s.ai_instruction, s.greeting_examples,
                       s.delay_enabled, s.delay_min_ms, s.delay_max_ms,
                       s.typing_enabled, s.read_enabled
                FROM local_user_auto_chat_settings s
                JOIN accounts a ON a.local_user_id = s.user_id
                WHERE a.id=?
                """,
                (account_id,),
            ).fetchone()
        if not row:
            return {
                "ai_instruction": "",
                "greeting_examples": "",
                "delay_enabled": 0,
                "delay_min_ms": 0,
                "delay_max_ms": 0,
                "typing_enabled": 0,
                "read_enabled": 0,
            }
        return {
            "ai_instruction": row["ai_instruction"] or "",
            "greeting_examples": row["greeting_examples"] or "",
            "delay_enabled": int(row["delay_enabled"] or 0),
            "delay_min_ms": int(row["delay_min_ms"] or 0),
            "delay_max_ms": int(row["delay_max_ms"] or 0),
            "typing_enabled": int(row["typing_enabled"] or 0),
            "read_enabled": int(row["read_enabled"] or 0),
        }

    @staticmethod
    def _shuffle_greeting_examples(raw: str) -> str:
        """
        Lightweight diversity boost:
        shuffle user-provided greeting examples before each greeting generation.
        """
        text = str(raw or "").strip()
        if not text:
            return ""
        lines = [ln.strip() for ln in text.splitlines()]
        # Keep only meaningful lines from user examples.
        items = [ln for ln in lines if ln and ln not in {"-", "—", "*"}]
        if len(items) <= 1:
            return text
        random.shuffle(items)
        return "\n".join(items)

    async def _ai_generate(self, prompt: str, max_tokens: int = 300, is_greeting: bool = False) -> str:
        # Different parameters for greetings vs regular replies
        if is_greeting:
            # Higher temperature and penalties for more diverse greetings
            temperature = 0.9
            top_p = 0.95
            frequency_penalty = 0.5  # Higher penalty to reduce phrase repetition
            presence_penalty = 0.3   # Encourage more topic diversity
        else:
            temperature = 0.7
            top_p = 0.9
            frequency_penalty = 0.2
            presence_penalty = 0.1
            
        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            # Prevent the model from continuing the transcript with role labels.
            "stop": [
                "\nUser:",
                "\nAssistant:",
                "\n\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c:",
                "\n\u0412\u044b:",
            ],
        }
        r = await self._http.post(f"{AI_API_URL}/ai/generate", json=payload)
        r.raise_for_status()
        data = r.json()
        text = (data.get("text") or "").strip()
        # Extra cleanup if the model still returns labels.
        for prefix in (
            "User:",
            "Assistant:",
            "\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c:",
            "\u0412\u044b:",
        ):
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip()
        return text

    async def _send_greeting(self, account_id: int, client: TelegramClient, dialog: dict) -> None:
        dialog_id = dialog["id"]
        # lock per dialog to avoid double-send if worker loops fast
        lock = self._dialog_locks.setdefault(dialog_id, asyncio.Lock())
        if lock.locked():
            return
        async with lock:
            # re-check status
            with db() as con:
                row = con.execute(
                    "SELECT status FROM auto_chat_dialogs WHERE id=?",
                    (dialog_id,),
                ).fetchone()
                if not row or row["status"] != AUTO_CHAT_STATUS_STARTING:
                    return

            s = self._load_auto_chat_settings_for_account(account_id)
            shuffled_examples = self._shuffle_greeting_examples(s.get("greeting_examples") or "")
            system_prompt = build_auto_chat_system_prompt(s["ai_instruction"], shuffled_examples)
            prompt = build_greeting_prompt(system_prompt, dialog.get("peer_username"), dialog.get("peer_display_name"))

            try:
                text = await self._ai_generate(prompt, max_tokens=250, is_greeting=True)
                if not text:
                    raise RuntimeError("EMPTY_GREETING")
                msg = await self._send_message_resilient(
                    account_id,
                    int(dialog["peer_tg_user_id"]),
                    text,
                    peer_username=dialog.get("peer_username"),
                )
                now = now_iso()
                with db() as con:
                    con.execute(
                        """
                        INSERT INTO auto_chat_messages(dialog_id, direction, text, tg_message_id, created_at)
                        VALUES (?, 'OUT', ?, ?, ?)
                        """,
                        (dialog_id, text, getattr(msg, "id", None), now),
                    )
                    con.execute(
                        """
                        UPDATE auto_chat_dialogs
                        SET status=?, updated_at=?, last_error=NULL, last_outgoing_tg_message_id=?, pending_incoming=0, pending_buffer_until_at=NULL
                        WHERE id=?
                        """,
                        (AUTO_CHAT_STATUS_WAIT_REPLY, now, getattr(msg, "id", None), dialog_id),
                    )
            except FloodWaitError as e:
                await asyncio.sleep(int(getattr(e, "seconds", 3)) + 1)
            except Exception as e:
                now = now_iso()
                with db() as con:
                    con.execute(
                        """
                        UPDATE auto_chat_dialogs
                        SET status=?, last_error=?, updated_at=?
                        WHERE id=?
                        """,
                        (AUTO_CHAT_STATUS_ERROR, f"{type(e).__name__}: {e}", now, dialog_id),
                    )
                notify_error(
                    source="auto_chat_dialogs",
                    account_id=account_id,
                    message=f"{type(e).__name__}: {e}",
                    context=f"dialog_id={dialog_id}; stage=send_greeting",
                )

    async def _on_auto_chat_message(self, account_id: int, event) -> None:
        try:
            if not getattr(event, "is_private", False):
                return
            client = event.client
            msg = event.message
            sender_id = getattr(msg, "sender_id", None)
            if not sender_id:
                return

            dialog = self._find_active_dialog(account_id, sender_id)
            if not dialog:
                return

            dialog_id = dialog["id"]
            lock = self._dialog_locks.setdefault(dialog_id, asyncio.Lock())
            async with lock:
                # dedupe by tg message id
                tg_mid = getattr(msg, "id", None)
                with db() as con:
                    row = con.execute(
                        "SELECT status, last_incoming_tg_message_id FROM auto_chat_dialogs WHERE id=?",
                        (dialog_id,),
                    ).fetchone()
                    if not row:
                        return
                    if row["status"] not in (AUTO_CHAT_STATUS_WAIT_REPLY, AUTO_CHAT_STATUS_ACTIVE):
                        return
                    if tg_mid and row["last_incoming_tg_message_id"] and int(row["last_incoming_tg_message_id"]) >= int(tg_mid):
                        return

                text_in = (getattr(msg, "message", "") or "").strip()
                if not text_in:
                    return

                now = now_iso()
                with db() as con:
                    con.execute(
                        """
                        INSERT INTO auto_chat_messages(dialog_id, direction, text, tg_message_id, created_at)
                        VALUES (?, 'IN', ?, ?, ?)
                        """,
                        (dialog_id, text_in, tg_mid, now),
                    )
                    con.execute(
                        """
                        UPDATE auto_chat_dialogs
                        SET updated_at=?, last_incoming_tg_message_id=?, pending_incoming=1, pending_buffer_until_at=?
                        WHERE id=?
                        """,
                        (now, tg_mid, _buffer_ready_at_iso(), dialog_id),
                    )
                    # Сохраняем реквизиты из входящего сообщения
                    self._insert_requisites(
                        account_id=account_id,
                        chat_id=None,
                        dialog_id=dialog_id,
                        message_id=tg_mid,
                        message_text=text_in,
                        sender_phone=None,  # в приватных диалогах телефон не сохраняется
                        sender_username=dialog.get("peer_username"),
                        dt=datetime.utcnow(),
                        con=con,
                    )

                # Optional: mark as read immediately (doesn't block AI queue).
                try:
                    s = self._load_auto_chat_settings_for_account(account_id)
                    if int(s.get("read_enabled") or 0) == 1:
                        ack_peer = getattr(event, "input_sender", None) or sender_id
                        await client.send_read_acknowledge(ack_peer)
                except Exception as exc:
                    logger.debug(
                        "autochat read_ack failed account_id=%s sender_id=%s err=%s: %s",
                        account_id,
                        sender_id,
                        type(exc).__name__,
                        exc,
                    )
        except FloodWaitError as e:
            await asyncio.sleep(int(getattr(e, "seconds", 3)) + 1)
        except Exception as e:
            logger.exception("auto chat handler failed")
            # best-effort mark dialog error if we can
            try:
                dialog_id = dialog["id"] if "dialog" in locals() and dialog else None
                if dialog_id:
                    with db() as con:
                        con.execute(
                            "UPDATE auto_chat_dialogs SET status=?, last_error=?, updated_at=? WHERE id=?",
                            (AUTO_CHAT_STATUS_ERROR, f"{type(e).__name__}: {e}", now_iso(), dialog_id),
                        )
                    notify_error(
                        source="auto_chat_dialogs",
                        account_id=account_id,
                        message=f"{type(e).__name__}: {e}",
                        context=f"dialog_id={dialog_id}; stage=on_message",
                    )
            except Exception as exc:
                logger.warning(
                    "autochat failed to persist dialog error account_id=%s err=%s: %s",
                    account_id,
                    type(exc).__name__,
                    exc,
                )

    async def _handle_pending_dialog(self, account_id: int, client: TelegramClient, dialog: dict) -> None:
        dialog_id = dialog["id"]
        lock = self._dialog_locks.setdefault(dialog_id, asyncio.Lock())
        if lock.locked():
            return

        async with lock:
            with db() as con:
                row = con.execute(
                    """
                    SELECT status, pending_incoming, peer_tg_user_id, pending_buffer_until_at
                    FROM auto_chat_dialogs
                    WHERE id=?
                    """,
                    (dialog_id,),
                ).fetchone()
                if not row:
                    return
                if row["status"] not in (AUTO_CHAT_STATUS_WAIT_REPLY, AUTO_CHAT_STATUS_ACTIVE):
                    return
                if int(row["pending_incoming"] or 0) != 1:
                    return
                ready_at = str(row["pending_buffer_until_at"] or "")
                if ready_at and ready_at > now_iso():
                    # Buffer window still open; wait for possible extra incoming messages.
                    return

            try:
                s = self._load_auto_chat_settings_for_account(account_id)
                system_prompt = build_auto_chat_system_prompt(s["ai_instruction"], s["greeting_examples"])
                history = self._load_dialog_history(dialog_id, limit=120)
                prompt = build_reply_prompt(system_prompt, history)

                peer_id = int(row["peer_tg_user_id"])
                peer_input = await self._resolve_input_peer(client, peer_id, dialog.get("peer_username"))

                # Best-effort "human" pacing: total time includes AI generation.
                delay_ms = 0
                if int(s.get("delay_enabled") or 0) == 1:
                    mn = max(0, int(s.get("delay_min_ms") or 0))
                    mx = max(0, int(s.get("delay_max_ms") or 0))
                    if mx < mn:
                        mx = mn
                    if mx > 0:
                        delay_ms = random.randint(mn, mx)

                t0 = monotonic()
                latency_ms = 0
                if int(s.get("typing_enabled") or 0) == 1:
                    if AUTO_CHAT_PRE_TYPING_DELAY_MS > 0:
                        await asyncio.sleep(AUTO_CHAT_PRE_TYPING_DELAY_MS / 1000.0)
                    async with client.action(peer_input, "typing"):
                        t_req = monotonic()
                        text_out = await self._ai_generate(prompt, max_tokens=300)
                        latency_ms = int((monotonic() - t_req) * 1000)
                        remain = (delay_ms / 1000.0) - (monotonic() - t0)
                        if remain > 0:
                            await asyncio.sleep(remain)
                else:
                    t_req = monotonic()
                    text_out = await self._ai_generate(prompt, max_tokens=300)
                    latency_ms = int((monotonic() - t_req) * 1000)
                    remain = (delay_ms / 1000.0) - (monotonic() - t0)
                    if remain > 0:
                        await asyncio.sleep(remain)
                if not text_out:
                    raise RuntimeError("EMPTY_REPLY")

                msg2 = await self._send_message_resilient(
                    account_id,
                    peer_id,
                    text_out,
                    peer_username=dialog.get("peer_username"),
                )
                now2 = now_iso()

                with db() as con:
                    con.execute(
                        """
                        INSERT INTO auto_chat_messages(dialog_id, direction, text, tg_message_id, created_at)
                        VALUES (?, 'OUT', ?, ?, ?)
                        """,
                        (dialog_id, text_out, getattr(msg2, "id", None), now2),
                    )
                    # Сохраняем реквизиты из исходящего сообщения (ответ ИИ)
                    self._insert_requisites(
                        account_id=account_id,
                        chat_id=None,
                        dialog_id=dialog_id,
                        message_id=getattr(msg2, "id", None),
                        message_text=text_out,
                        sender_phone=None,
                        sender_username=None,  # наш аккаунт
                        dt=datetime.utcnow(),
                        con=con,
                    )
                    con.execute(
                        """
                        UPDATE auto_chat_dialogs
                        SET status=?,
                            pending_incoming=0,
                            pending_buffer_until_at=NULL,
                            updated_at=?,
                            last_error=NULL,
                            last_outgoing_tg_message_id=?,
                            last_ai_request_at=?,
                            last_ai_latency_ms=?
                        WHERE id=?
                        """,
                        (AUTO_CHAT_STATUS_ACTIVE, now2, getattr(msg2, "id", None), now2, latency_ms, dialog_id),
                    )
            except FloodWaitError as e:
                # Keep pending flag, we'll retry after waiting.
                await asyncio.sleep(int(getattr(e, "seconds", 3)) + 1)
            except Exception as e:
                now = now_iso()
                with db() as con:
                    con.execute(
                        """
                        UPDATE auto_chat_dialogs
                        SET status=?, last_error=?, pending_incoming=0, pending_buffer_until_at=NULL, updated_at=?
                        WHERE id=?
                        """,
                        (AUTO_CHAT_STATUS_ERROR, f"{type(e).__name__}: {e}", now, dialog_id),
                    )
                notify_error(
                    source="auto_chat_dialogs",
                    account_id=account_id,
                    message=f"{type(e).__name__}: {e}",
                    context=f"dialog_id={dialog_id}; stage=handle_pending",
                )

    def _find_active_dialog(self, account_id: int, peer_tg_user_id: int) -> Optional[dict]:
        with db() as con:
            row = con.execute(
                """
                SELECT id, account_id, peer_tg_user_id, peer_username, peer_display_name, status
                FROM auto_chat_dialogs
                WHERE account_id=? AND peer_tg_user_id=? AND status IN (?, ?)
                """,
                (account_id, peer_tg_user_id, AUTO_CHAT_STATUS_WAIT_REPLY, AUTO_CHAT_STATUS_ACTIVE),
            ).fetchone()
        return dict(row) if row else None

    def _load_dialog_history(self, dialog_id: int, limit: int = 80) -> List[dict]:
        with db() as con:
            rows = con.execute(
                """
                SELECT direction, text
                FROM auto_chat_messages
                WHERE dialog_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (dialog_id, limit),
            ).fetchall()
        items = [dict(r) for r in rows]
        items.reverse()
        max_chars = int(os.getenv("AUTO_CHAT_MAX_PROMPT_CHARS", "12000"))
        out: List[dict] = []
        total = 0
        # keep most recent messages within budget
        for m in reversed(items):
            t = (m.get("text") or "").strip()
            if not t:
                continue
            sz = len(t) + 8
            if out and total + sz > max_chars:
                break
            out.append({"direction": m.get("direction"), "text": t})
            total += sz
        out.reverse()
        return out

    def _ensure_group_worker_run(self, account_id: int) -> None:
        with db() as con:
            row = con.execute(
                """
                SELECT id FROM group_worker_runs
                WHERE account_id=? AND status=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (account_id, RUN_STATUS_RUNNING),
            ).fetchone()
            if row:
                return
            con.execute(
                """
                INSERT INTO group_worker_runs(account_id, status, started_at)
                VALUES (?, ?, ?)
                """,
                (account_id, RUN_STATUS_RUNNING, now_iso()),
            )

    def _stop_inactive_group_runs(self, active_ids: set) -> None:
        if not active_ids:
            return
        placeholders = ",".join("?" for _ in active_ids)
        with db() as con:
            con.execute(
                f"""
                UPDATE group_worker_runs
                SET status=?, stopped_at=?
                WHERE status=?
                  AND account_id NOT IN ({placeholders})
                """,
                (RUN_STATUS_STOPPED, now_iso(), RUN_STATUS_RUNNING, *active_ids),
            )

    def _stop_all_group_runs(self) -> None:
        with db() as con:
            con.execute(
                """
                UPDATE group_worker_runs
                SET status=?, stopped_at=?
                WHERE status=?
                """,
                (RUN_STATUS_STOPPED, now_iso(), RUN_STATUS_RUNNING),
            )

    @staticmethod
    def _compile_keyword_patterns(keywords: List[str]) -> List[re.Pattern]:
        """
        Match whole words/phrases only (case-insensitive).
        Example: keyword 'сон' matches 'сон.' but NOT 'персонаж'.
        """
        out: List[re.Pattern] = []
        for k in keywords or []:
            k = (k or "").strip()
            if not k:
                continue
            # \w in Python is Unicode-aware (Cyrillic included).
            pat = re.compile(rf"(?<!\w){re.escape(k)}(?!\w)", re.IGNORECASE)
            out.append(pat)
        return out

    @staticmethod
    def _text_matches_keywords(text: str, patterns: List[re.Pattern]) -> bool:
        if not text or not patterns:
            return False
        for p in patterns:
            if p.search(text):
                return True
        return False

    @staticmethod
    def _matched_keywords(text: str, keywords: List[str], patterns: List[re.Pattern]) -> List[str]:
        """Return the keywords that matched (whole word/phrase, case-insensitive)."""
        if not text or not keywords or not patterns:
            return []
        out: List[str] = []
        for k, p in zip(keywords, patterns):
            if p.search(text):
                out.append(k)
        return out

    def _load_keywords_for_account(self, account_id: int) -> List[str]:
        with db() as con:
            row = con.execute(
                """
                SELECT s.keywords
                FROM local_user_settings s
                JOIN accounts a ON a.local_user_id = s.user_id
                WHERE a.id = ?
                """,
                (account_id,),
            ).fetchone()
        if not row or not row["keywords"]:
            return []
        parts = [p.strip().lower() for p in row["keywords"].split(",")]
        return [p for p in parts if p]

    async def _get_dialog_map(self, account_id: int, client: TelegramClient, ids: set) -> Dict[int, object]:
        cached = self._dialog_cache.get(account_id)
        if cached:
            ts, mapping = cached
            if datetime.utcnow() - ts < timedelta(seconds=120):
                # If cache covers all needed ids, reuse
                if ids.issubset(mapping.keys()):
                    return mapping
        try:
            mapping = await self._build_dialog_map(client, ids)
        except AuthKeyUnregisteredError:
            # Session is invalid/revoked on Telegram side. Mark it revoked locally and skip this account.
            await self.client_manager.invalidate_session(account_id)
            return {}
        if mapping:
            self._dialog_cache[account_id] = (datetime.utcnow(), mapping)
        return mapping

    async def _build_dialog_map(self, client: TelegramClient, ids: set) -> Dict[int, object]:
        try:
            dialogs = await client.get_dialogs(limit=300)
        except AuthKeyUnregisteredError:
            raise
        except FloodWaitError as e:
            logger.info("Flood wait on get_dialogs: %ss", e.seconds)
            await asyncio.sleep(min(e.seconds, 30))
            return {}
        except Exception as e:
            # Network hiccups, timeouts, etc. Should not kill the whole listener loop.
            logger.info("get_dialogs failed: %s: %s", type(e).__name__, e)
            return {}
        return {d.id: d.entity for d in dialogs if d.id in ids}

    async def _scan_group_messages(
        self,
        client: TelegramClient,
        account_id: int,
        chat_id: int,
        entity: object,
        last_message_id: Optional[int],
        keywords: List[str],
        keyword_patterns: List[re.Pattern],
    ) -> None:
        last_id = last_message_id or 0
        if last_id == 0:
            limit = GROUP_LISTENER_INITIAL_SCAN_LIMIT
            if limit < 20:
                limit = 20
            if limit > 2000:
                limit = 2000
            msgs = await client.get_messages(entity, limit=limit)
            max_id = last_id
            for msg in reversed(msgs):
                if not msg or not msg.id:
                    continue
                max_id = max(max_id, msg.id)
                text = getattr(msg, "raw_text", None) or getattr(msg, "message", None)
                if not text:
                    continue
                if self._text_matches_keywords(text, keyword_patterns):
                    phone = await self._try_get_sender_phone(client, msg)
                    mk = self._matched_keywords(text, keywords, keyword_patterns)
                    self._insert_match(account_id, chat_id, msg.id, text, msg.date, phone, mk)
            if max_id:
                self._update_last_message_id(account_id, chat_id, max_id)
            return

        max_id = last_id
        async for msg in client.iter_messages(entity, min_id=last_id, reverse=True):
            if not msg or not msg.id:
                continue
            max_id = max(max_id, msg.id)
            text = getattr(msg, "raw_text", None) or getattr(msg, "message", None)
            if not text:
                continue
            if self._text_matches_keywords(text, keyword_patterns):
                phone = await self._try_get_sender_phone(client, msg)
                mk = self._matched_keywords(text, keywords, keyword_patterns)
                self._insert_match(account_id, chat_id, msg.id, text, msg.date, phone, mk)
        if max_id != last_id:
            self._update_last_message_id(account_id, chat_id, max_id)

    def _update_last_message_id(self, account_id: int, chat_id: int, last_id: int) -> None:
        with db() as con:
            con.execute(
                """
                UPDATE group_listeners
                SET last_message_id=?, updated_at=?
                WHERE account_id=? AND chat_id=?
                """,
                (last_id, now_iso(), account_id, chat_id),
            )

    def _insert_match(
        self,
        account_id: int,
        chat_id: int,
        message_id: int,
        text: str,
        dt: datetime,
        sender_phone: Optional[str],
        matched_keywords: Optional[List[str]] = None,
    ) -> None:
        if not message_id:
            return
        mk = ""
        if matched_keywords:
            mk = ", ".join([k.strip().lower() for k in matched_keywords if (k or "").strip()])
        with db() as con:
            con.execute(
                """
                INSERT INTO group_matches(
                    account_id, chat_id, message_id, message_text, sender_phone, matched_keywords, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, chat_id, message_id) DO UPDATE SET
                    matched_keywords=CASE
                        WHEN COALESCE(group_matches.matched_keywords, '')='' THEN excluded.matched_keywords
                        ELSE group_matches.matched_keywords
                    END
                """,
                (account_id, chat_id, message_id, text, sender_phone, mk, dt.isoformat() if dt else now_iso()),
            )
            # Сохраняем реквизиты из сообщения
            self._insert_requisites(
                account_id=account_id,
                chat_id=chat_id,
                dialog_id=None,
                message_id=message_id,
                message_text=text,
                sender_phone=sender_phone,
                sender_username=None,  # в группах username не сохраняется
                dt=dt,
                con=con,
            )

    async def _try_get_sender_phone(self, client: TelegramClient, msg) -> Optional[str]:
        sender_id = getattr(msg, "sender_id", None)
        if not sender_id:
            return None
        try:
            sender = await client.get_entity(sender_id)
            return getattr(sender, "phone", None)
        except Exception as exc:
            logger.debug(
                "sender phone resolve failed sender_id=%s err=%s: %s",
                sender_id,
                type(exc).__name__,
                exc,
            )
            return None

    def _extract_requisites(self, text: str) -> List[dict]:
        if not text:
            return []

        def _digits(s: str) -> str:
            return re.sub(r"\D+", "", s or "")

        def _canon_kz_phone_digits(d: str) -> Optional[str]:
            """
            Возвращает канонические digits для KZ: 11 цифр, начинается на 7 (77...)
            Принимает варианты: 8XXXXXXXXXX -> 7XXXXXXXXXX, +7XXXXXXXXXX -> 7XXXXXXXXXX
            """
            if not d:
                return None
            if len(d) == 11 and d.startswith("8"):
                d = "7" + d[1:]
            if len(d) == 11 and d.startswith("7") and d[1] == "7":
                return d
            return None

        def _norm_phone(raw: str) -> str:
            d = _digits(raw)
            kz = _canon_kz_phone_digits(d)
            if kz:
                return "+7" + kz[1:]
            return raw.strip()

        def _luhn_ok(number_digits: str) -> bool:
            s = 0
            rev = number_digits[::-1]
            for i, ch in enumerate(rev):
                n = ord(ch) - 48
                if i % 2 == 1:
                    n *= 2
                    if n > 9:
                        n -= 9
                s += n
            return (s % 10) == 0

        results: List[dict] = []
        seen_digits = set()  # для phone/card/unknown (цифры)
        seen_iban = set()    # для iban (строка)

        def _add(value: str, requisite_type: str, country: str) -> None:
            v = (value or "").strip()
            if not v:
                return

            if requisite_type == "iban":
                key = v.upper()
                if key in seen_iban:
                    return
                seen_iban.add(key)
                results.append({"value": key, "requisite_type": requisite_type, "country": country})
                return

            d = _digits(v)

            # Для телефонов и unknown — канонизируем KZ 8->7
            if requisite_type in ("phone", "unknown"):
                kz = _canon_kz_phone_digits(d)
                if kz:
                    d = kz

            # Для карт — просто digits (после Luhn)
            key = d or v
            if key in seen_digits:
                return
            seen_digits.add(key)
            results.append({"value": v, "requisite_type": requisite_type, "country": country})

        # --- regex (priority order) ---
        # KZ: +7 7xx xxx xx xx
        rx_phone_kz_plus7 = re.compile(r"(?<!\d)\+7\s*\(?7\d{2}\)?\s*\d{3}[\s\-]?\d{2}[\s\-]?\d{2}(?!\d)")
        # KZ: 8 7xx xxx xx xx
        rx_phone_kz_8 = re.compile(r"(?<!\d)8\s*\(?7\d{2}\)?\s*\d{3}[\s\-]?\d{2}[\s\-]?\d{2}(?!\d)")
        # KZ: 77xxxxxxxxx (11 цифр, без +/8)
        rx_phone_kz_plain = re.compile(r"(?<!\d)77\d{9}(?!\d)")

        # CIS examples (BY/UA)
        rx_phone_by = re.compile(r"(?<!\d)\+375\s*\(?\d{2}\)?\s*\d{3}[\s\-]?\d{2}[\s\-]?\d{2}(?!\d)")
        rx_phone_ua = re.compile(r"(?<!\d)\+380\s*\(?\d{2}\)?\s*\d{3}[\s\-]?\d{2}[\s\-]?\d{2}(?!\d)")

        # Cards (15–19 digits, spaces/dashes allowed)
        rx_card = re.compile(r"(?<!\d)(?:\d[ \-]?){15,19}(?!\d)")

        # IBAN
        rx_iban = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", re.I)

        # Unknown long numbers
        rx_long = re.compile(r"\b\d{10,}\b")

        # --- phones first ---
        for m in rx_phone_kz_plus7.finditer(text):
            _add(_norm_phone(m.group(0)), "phone", "Казахстан")

        for m in rx_phone_kz_8.finditer(text):
            _add(_norm_phone(m.group(0)), "phone", "Казахстан")

        for m in rx_phone_kz_plain.finditer(text):
            _add(_norm_phone(m.group(0)), "phone", "Казахстан")

        for m in rx_phone_by.finditer(text):
            _add(m.group(0).strip(), "phone", "СНГ")

        for m in rx_phone_ua.finditer(text):
            _add(m.group(0).strip(), "phone", "СНГ")

        # --- cards ---
        for m in rx_card.finditer(text):
            raw = m.group(0).strip()
            d = _digits(raw)
            if not (15 <= len(d) <= 19):
                continue
            if _luhn_ok(d):
                _add(raw, "card", "Не определено")

        # --- iban ---
        for m in rx_iban.finditer(text):
            iban = m.group(0).strip().upper()
            cc = iban[:2]
            cis_cc = {"RU", "BY", "UA", "AM", "AZ", "KG", "UZ", "TJ", "TM", "MD", "GE"}
            if cc == "KZ":
                country = "Казахстан"
            elif cc in cis_cc:
                country = "СНГ"
            else:
                country = "Зарубеж"
            _add(iban, "iban", country)

        # --- unknown last (and will not duplicate phones) ---
        for m in rx_long.finditer(text):
            raw = m.group(0).strip()
            d = _digits(raw)
            if not d:
                continue

            # если это KZ телефон в варианте 8/7 — и он уже есть как phone, не добавляем
            kz = _canon_kz_phone_digits(d)
            if kz and kz in seen_digits:
                continue

            if d in seen_digits:
                continue

            country = "Не определено"
            if kz:
                country = "Казахстан"
            elif d.startswith(("375", "380")):
                country = "СНГ"

            _add(raw, "unknown", country)

        return results

    def _insert_requisites(
        self,
        account_id: int,
        chat_id: Optional[int],
        dialog_id: Optional[int],
        message_id: int,
        message_text: str,
        sender_phone: Optional[str],
        sender_username: Optional[str],
        dt: datetime,
        con=None,
    ) -> None:
        """
        Сохраняет найденные реквизиты в таблицу requisites.
        Если передано соединение con (объект sqlite3.Connection), использует его.
        Иначе открывает новое соединение.
        """
        requisites = self._extract_requisites(message_text)
        if not requisites:
            return
        own_con = False
        if con is None:
            con = db()
            own_con = True
        try:
            for req in requisites:
                con.execute(
                    """
                    INSERT OR IGNORE INTO requisites(
                        account_id, chat_id, dialog_id, message_id, message_text,
                        sender_phone, sender_username, requisite_type, country, value, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account_id,
                        chat_id,
                        dialog_id,
                        message_id,
                        message_text,
                        sender_phone,
                        sender_username,
                        req['requisite_type'],
                        req['country'],
                        req['value'],
                        dt.isoformat() if dt else now_iso(),
                    ),
                )
            if own_con:
                con.commit()
        finally:
            if own_con:
                con.close()

    async def _job_analyze(self, account_id: int, job_id: int) -> None:
        client = await self.client_manager.get_client(account_id)
        if self._check_cancelled(job_id):
            raise JobCancelled()
        messages = await client.get_messages("me", limit=20)
        self._update_progress(job_id, 50)
        _ = [m.id for m in messages]
        self._update_progress(job_id, 100)


async def main() -> None:
    if not TG_API_ID or not TG_API_HASH:
        raise RuntimeError("TG_API_ID/TG_API_HASH not set")
    worker = Worker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
