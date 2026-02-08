import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession

from common.config import TG_API_HASH, TG_API_ID
from common.crypto import decrypt_text
from common.db import db, init_db
from common.logging_setup import get_logger, setup_logging


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


class Worker:
    def __init__(self) -> None:
        self.client_manager = ClientManager()
        self._listener_task: Optional[asyncio.Task] = None
        self._dialog_cache: Dict[int, Tuple[datetime, Dict[int, object]]] = {}

    async def run(self) -> None:
        init_db()
        logger.info("worker started")
        self._listener_task = asyncio.create_task(self._listen_groups_loop())
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
            await self.client_manager.disconnect_all()

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

    async def _try_get_sender_phone(self, client: TelegramClient, msg) -> Optional[str]:
        sender_id = getattr(msg, "sender_id", None)
        if not sender_id:
            return None
        try:
            sender = await client.get_entity(sender_id)
            return getattr(sender, "phone", None)
        except Exception:
            return None

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
