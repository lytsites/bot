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

from common.config import TG_API_HASH, TG_API_ID
from common.crypto import decrypt_text
from common.db import db, init_db
from common.logging_setup import get_logger, setup_logging
from ai.prompting import (
    build_auto_chat_system_prompt,
    build_greeting_prompt,
    build_reply_prompt,
)


setup_logging()
logger = get_logger("worker")

POLL_INTERVAL_SEC = 1.5

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


def now_iso() -> str:
    return datetime.utcnow().isoformat()


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
            return state.client

        if state:
            await state.client.disconnect()

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

    async def disconnect_all(self) -> None:
        for state in self._clients.values():
            await state.client.disconnect()
        self._clients.clear()

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
        self._dialog_cache: Dict[int, Tuple[datetime, Dict[int, object]]] = {}
        # account_id -> id(client) to re-register handler if the client instance changes
        self._auto_chat_handler_client: Dict[int, int] = {}
        self._dialog_locks: Dict[int, asyncio.Lock] = {}
        self._http = None
        self._auto_chat_sem: Dict[int, asyncio.Semaphore] = {}

    async def run(self) -> None:
        init_db()
        logger.info("worker started")
        self._listener_task = asyncio.create_task(self._listen_groups_loop())
        self._auto_chat_task = asyncio.create_task(self._auto_chat_loop())
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
            await self.client_manager.disconnect_all()
            if self._http:
                await self._http.aclose()

    def _fetch_next_job(self) -> Optional[dict]:
        with db() as con:
            row = con.execute(
                """
                SELECT id, account_id, type, status, progress
                FROM jobs
                WHERE status=?
                ORDER BY id ASC
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
        with db() as con:
            con.execute(
                """
                UPDATE jobs
                SET status=?, last_error=?, updated_at=?
                WHERE id=?
                """,
                (status, error, now_iso(), job_id),
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
                    await self.client_manager.disconnect_all()
                    await asyncio.sleep(3.0)
                    continue
                active_ids = set(groups_by_account.keys())
                for account_id in active_ids:
                    self._ensure_group_worker_run(account_id)
                self._stop_inactive_group_runs(active_ids)
                for account_id, group_rows in groups_by_account.items():
                    keywords = self._load_keywords_for_account(account_id)
                    if not keywords:
                        continue
                    try:
                        client = await self.client_manager.get_client(account_id)
                    except Exception:
                        continue

                    dialog_map = await self._get_dialog_map(account_id, client, {r["chat_id"] for r in group_rows})
                    for row in group_rows:
                        chat_id = row["chat_id"]
                        entity = dialog_map.get(chat_id)
                        if not entity:
                            continue
                        await self._scan_group_messages(client, account_id, chat_id, entity, row["last_message_id"], keywords)
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
                WHERE gl.is_listening=1 AND s.is_active=1
                """
            ).fetchall()
        grouped: Dict[int, List[dict]] = {}
        for row in rows:
            grouped.setdefault(row["account_id"], []).append(dict(row))
        return grouped

    async def _auto_chat_loop(self) -> None:
        import httpx

        if self._http is None:
            timeout_s = float(os.getenv("AI_HTTP_TIMEOUT", "300"))
            self._http = httpx.AsyncClient(timeout=timeout_s)

        while True:
            try:
                # Ensure event handlers are attached even after a worker restart,
                # so dialogs in WAIT_REPLY/ACTIVE continue to receive messages.
                for account_id in self._load_accounts_with_active_auto_chat_dialogs():
                    try:
                        client = await self.client_manager.get_client(account_id)
                    except Exception:
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
                    except Exception:
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
                JOIN local_user_settings s ON s.user_id = a.local_user_id
                WHERE s.is_active=1
                  AND d.status IN (?, ?, ?)
                """,
                (AUTO_CHAT_STATUS_STARTING, AUTO_CHAT_STATUS_WAIT_REPLY, AUTO_CHAT_STATUS_ACTIVE),
            ).fetchall()
        return [int(r["account_id"]) for r in rows]

    def _load_pending_dialogs(self, limit: int = 80) -> List[dict]:
        with db() as con:
            rows = con.execute(
                """
                SELECT id, account_id, peer_tg_user_id, peer_username, peer_display_name, status
                FROM auto_chat_dialogs
                WHERE pending_incoming=1
                  AND status IN (?, ?)
                ORDER BY updated_at ASC, id ASC
                LIMIT ?
                """,
                (AUTO_CHAT_STATUS_WAIT_REPLY, AUTO_CHAT_STATUS_ACTIVE, limit),
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
            except Exception:
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

    async def _ai_generate(self, prompt: str, max_tokens: int = 300) -> str:
        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": 0.7,  # Lower temperature for more consistent, less random responses
            "top_p": 0.9,        # Slightly lower top_p for better focus
            "frequency_penalty": 0.2,  # Reduce repetition of phrases
            "presence_penalty": 0.1,   # Encourage topic diversity
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
            system_prompt = build_auto_chat_system_prompt(s["ai_instruction"], s["greeting_examples"])
            prompt = build_greeting_prompt(system_prompt, dialog.get("peer_username"), dialog.get("peer_display_name"))

            try:
                text = await self._ai_generate(prompt, max_tokens=250)
                if not text:
                    raise RuntimeError("EMPTY_GREETING")
                msg = await client.send_message(dialog["peer_tg_user_id"], text)
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
                        SET status=?, updated_at=?, last_error=NULL, last_outgoing_tg_message_id=?, pending_incoming=0
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
                        SET updated_at=?, last_incoming_tg_message_id=?, pending_incoming=1
                        WHERE id=?
                        """,
                        (now, tg_mid, dialog_id),
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
                        await client.send_read_acknowledge(sender_id)
                except Exception:
                    pass
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
            except Exception:
                pass

    async def _handle_pending_dialog(self, account_id: int, client: TelegramClient, dialog: dict) -> None:
        dialog_id = dialog["id"]
        lock = self._dialog_locks.setdefault(dialog_id, asyncio.Lock())
        if lock.locked():
            return

        async with lock:
            with db() as con:
                row = con.execute(
                    "SELECT status, pending_incoming, peer_tg_user_id FROM auto_chat_dialogs WHERE id=?",
                    (dialog_id,),
                ).fetchone()
                if not row:
                    return
                if row["status"] not in (AUTO_CHAT_STATUS_WAIT_REPLY, AUTO_CHAT_STATUS_ACTIVE):
                    return
                if int(row["pending_incoming"] or 0) != 1:
                    return

            try:
                s = self._load_auto_chat_settings_for_account(account_id)
                system_prompt = build_auto_chat_system_prompt(s["ai_instruction"], s["greeting_examples"])
                history = self._load_dialog_history(dialog_id, limit=120)
                prompt = build_reply_prompt(system_prompt, history)

                peer_id = int(row["peer_tg_user_id"])

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
                    async with client.action(peer_id, "typing"):
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

                msg2 = await client.send_message(peer_id, text_out)
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
                        SET status=?, last_error=?, pending_incoming=0, updated_at=?
                        WHERE id=?
                        """,
                        (AUTO_CHAT_STATUS_ERROR, f"{type(e).__name__}: {e}", now, dialog_id),
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
        mapping = await self._build_dialog_map(client, ids)
        if mapping:
            self._dialog_cache[account_id] = (datetime.utcnow(), mapping)
        return mapping

    async def _build_dialog_map(self, client: TelegramClient, ids: set) -> Dict[int, object]:
        try:
            dialogs = await client.get_dialogs(limit=300)
        except FloodWaitError as e:
            logger.info("Flood wait on get_dialogs: %ss", e.seconds)
            await asyncio.sleep(min(e.seconds, 30))
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
    ) -> None:
        last_id = last_message_id or 0
        if last_id == 0:
            msgs = await client.get_messages(entity, limit=20)
            max_id = last_id
            for msg in reversed(msgs):
                if not msg or not msg.id:
                    continue
                max_id = max(max_id, msg.id)
                text = getattr(msg, "message", None)
                if not text:
                    continue
                low = text.lower()
                if any(k in low for k in keywords):
                    phone = await self._try_get_sender_phone(client, msg)
                    self._insert_match(account_id, chat_id, msg.id, text, msg.date, phone)
            if max_id:
                self._update_last_message_id(account_id, chat_id, max_id)
            return

        max_id = last_id
        async for msg in client.iter_messages(entity, min_id=last_id, reverse=True):
            if not msg or not msg.id:
                continue
            max_id = max(max_id, msg.id)
            text = getattr(msg, "message", None)
            if not text:
                continue
            low = text.lower()
            if any(k in low for k in keywords):
                phone = await self._try_get_sender_phone(client, msg)
                self._insert_match(account_id, chat_id, msg.id, text, msg.date, phone)
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

    def _insert_match(self, account_id: int, chat_id: int, message_id: int, text: str, dt: datetime, sender_phone: Optional[str]) -> None:
        if not message_id:
            return
        with db() as con:
            con.execute(
                """
                INSERT OR IGNORE INTO group_matches(account_id, chat_id, message_id, message_text, sender_phone, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (account_id, chat_id, message_id, text, sender_phone, dt.isoformat() if dt else now_iso()),
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
        except Exception:
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
