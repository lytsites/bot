import asyncio
import base64
import concurrent.futures
import threading
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional
import time

from telethon import TelegramClient
from telethon.errors import FloodWaitError, PasswordHashInvalidError, SessionPasswordNeededError
from telethon.sessions import StringSession

from common.config import (
    AUTH_FLOW_TTL_MINUTES,
    QR_REFRESH_AFTER_SECONDS,
    QR_START_TIMEOUT_SECONDS,
    QR_TTL_SECONDS,
    TG_API_HASH,
    TG_API_ID,
)
from common.crypto import decrypt_text, encrypt_text
from common.db import db
from common.logging_setup import get_logger
from common.phone import normalize_phone_digits, phone_variants
from common.telegram_alerts import notify_error
from common.timezone import add_minutes_iso, add_seconds_iso, almaty_now_naive, now_iso, parse_iso_local
import qrcode


logger = get_logger("auth.telegram")

STATUS_NEW = "NEW"
STATUS_CODE_SENT = "CODE_SENT"
STATUS_WAIT_PASSWORD = "WAIT_PASSWORD"
STATUS_READY = "READY"
STATUS_ERROR = "ERROR"
STATUS_EXPIRED = "EXPIRED"
STATUS_CANCELLED = "CANCELLED"

STATUS_QR_INIT = "QR_INIT"
STATUS_QR_READY = "QR_READY"
STATUS_QR_WAIT_CONFIRM = "QR_WAIT_CONFIRM"

METHOD_CODE = "code"
METHOD_QR = "qr"
QR_CONNECT_TIMEOUT_SECONDS = 12
QR_LOGIN_CREATE_TIMEOUT_SECONDS = 12
QR_REFRESH_TIMEOUT_SECONDS = 12

def expires_at_iso(minutes: int = AUTH_FLOW_TTL_MINUTES) -> str:
    return add_minutes_iso(minutes)

def qr_expires_at_iso(seconds: int = QR_TTL_SECONDS) -> str:
    return add_seconds_iso(seconds)


def qr_refresh_after_iso(seconds: int = QR_REFRESH_AFTER_SECONDS) -> str:
    return add_seconds_iso(seconds)


def _is_expired(expires_at: str) -> bool:
    dt = parse_iso_local(expires_at)
    return dt is None or almaty_now_naive() >= dt


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    return parse_iso_local(ts)


def _mark_expired(auth_id: str) -> None:
    with db() as con:
        con.execute(
            "UPDATE auth_flows SET status=? WHERE auth_id=?",
            (STATUS_EXPIRED, auth_id),
        )


def _with_db_retry(fn, attempts: int = 5, delay: float = 0.2):
    last_exc = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if "locked" not in str(exc).lower():
                raise
            time.sleep(delay * (i + 1))
    raise last_exc


def _db_write_with_retry(action, attempts: int = 5, delay: float = 0.2):
    def _run():
        acquired = _db_lock.acquire(timeout=10)
        if not acquired:
            logger.error("db lock timeout")
            raise RuntimeError("DB_LOCK_TIMEOUT")
        try:
            logger.info("db_write start")
            with db() as con:
                action(con)
            logger.info("db_write done")
        finally:
            _db_lock.release()
    return _with_db_retry(_run, attempts=attempts, delay=delay)


async def _db_write_with_timeout(action, timeout: float = 10.0):
    def _sync():
        return _db_write_with_retry(action)
    return await asyncio.wait_for(asyncio.to_thread(_sync), timeout=timeout)


def _log_event(account_id: Optional[int], level: str, message: str) -> None:
    def _run(con):
        con.execute(
            """
            INSERT INTO events(account_id, level, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (account_id, level, message, now_iso()),
        )

    _db_write_with_retry(_run)
    if str(level or "").upper() == "ERROR":
        notify_error(
            source="events",
            account_id=account_id,
            message=message,
            context="auth_api",
        )


def _active_flow_exists(con, phone: str) -> bool:
    row = con.execute(
        """
        SELECT 1
        FROM auth_flows
        WHERE phone = ?
          AND status IN (?, ?, ?, ?, ?, ?)
          AND expires_at > ?
        """,
        (
            phone,
            STATUS_NEW,
            STATUS_CODE_SENT,
            STATUS_WAIT_PASSWORD,
            STATUS_QR_INIT,
            STATUS_QR_READY,
            STATUS_QR_WAIT_CONFIRM,
            now_iso(),
        ),
    ).fetchone()
    return row is not None


def _active_qr_flow_exists(con, local_user_id: int) -> bool:
    rows = con.execute(
        """
        SELECT auth_id, status, expires_at, qr_expires_at
        FROM auth_flows
        WHERE local_user_id=?
          AND method=?
          AND status IN (?, ?, ?)
        """,
        (
            local_user_id,
            METHOD_QR,
            STATUS_QR_READY,
            STATUS_QR_WAIT_CONFIRM,
            STATUS_WAIT_PASSWORD,
        ),
    ).fetchall()
    now = almaty_now_naive()
    for row in rows:
        status = str(row["status"] or "")
        flow_expires = _parse_iso(row["expires_at"])
        if status in (STATUS_QR_READY, STATUS_QR_WAIT_CONFIRM):
            qr_expires = _parse_iso(row["qr_expires_at"])
            effective_expires = qr_expires or flow_expires
        else:
            # WAIT_PASSWORD can still be completed without QR refresh.
            effective_expires = flow_expires
        if effective_expires and effective_expires > now:
            return True
    return False


def _set_error(auth_id: str, message: str) -> None:
    meta = {"account_id": None, "local_user_id": None}

    def _run(con):
        row = con.execute(
            "SELECT account_id, local_user_id FROM auth_flows WHERE auth_id=?",
            (auth_id,),
        ).fetchone()
        if row:
            meta["account_id"] = row["account_id"]
            meta["local_user_id"] = row["local_user_id"]
        con.execute(
            "UPDATE auth_flows SET status=?, error_message=? WHERE auth_id=?",
            (STATUS_ERROR, message, auth_id),
        )

    _db_write_with_retry(_run)
    notify_error(
        source="auth_flows",
        account_id=meta["account_id"],
        local_user_id=meta["local_user_id"],
        message=message,
        context=f"auth_id={auth_id}",
    )


def _account_by_phone(con, phone: str):
    return con.execute(
        "SELECT id FROM accounts WHERE phone = ?",
        (phone,),
    ).fetchone()


def _has_active_session(con, account_id: int) -> bool:
    row = con.execute(
        """
        SELECT 1 FROM tg_sessions
        WHERE account_id = ?
          AND revoked_at IS NULL
        """,
        (account_id,),
    ).fetchone()
    return row is not None


def _is_account_busy(con, account_id: int) -> bool:
    row = con.execute(
        """
        SELECT 1 FROM jobs
        WHERE account_id = ?
          AND status IN ('RUNNING', 'QUEUED')
        """,
        (account_id,),
    ).fetchone()
    return row is not None


def start_auth(phone: str | None, local_user_id: int) -> dict:
    if not TG_API_ID or not TG_API_HASH:
        raise RuntimeError("TG_API_ID/TG_API_HASH not set")

    # Normalize to digits-only to match existing DB conventions and avoid Telethon TypeErrors.
    digits = normalize_phone_digits(phone)
    variants = phone_variants(digits)

    auth_id = str(uuid.uuid4())
    enc_empty = encrypt_text("")

    async def _run():
        with db() as con:
            # Avoid parallel flows for the same phone, including legacy '+'-prefixed storage.
            if _active_flow_exists(con, variants[0]) or _active_flow_exists(con, variants[1]):
                raise ValueError("AUTH_IN_PROGRESS")

            # If account already exists under a legacy representation, keep using that representation
            # to prevent inserting a duplicate row with a different phone string.
            db_phone = variants[0]
            account_row = _account_by_phone(con, variants[0])
            if not account_row:
                account_row = _account_by_phone(con, variants[1])
                if account_row:
                    db_phone = variants[1]
            if account_row:
                account_id = account_row["id"]
                if _has_active_session(con, account_id):
                    raise ValueError("ACTIVE_SESSION_EXISTS")
                if _is_account_busy(con, account_id):
                    raise ValueError("ACCOUNT_BUSY")

            con.execute(
                """
                INSERT INTO auth_flows(auth_id, phone, status, temp_session, phone_code_hash, expires_at, method, error_message, local_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (auth_id, db_phone, STATUS_NEW, enc_empty, None, expires_at_iso(), METHOD_CODE, None, local_user_id),
            )

        client = TelegramClient(StringSession(""), TG_API_ID, TG_API_HASH)
        await client.connect()
        try:
            # Telethon accepts digits-only phone numbers; keep consistent with db_phone above.
            sent = await client.send_code_request(db_phone)
            session_string = client.session.save()
            enc_session = encrypt_text(session_string)

            with db() as con:
                con.execute(
                    """
                    UPDATE auth_flows
                    SET status=?, temp_session=?, phone_code_hash=?
                    WHERE auth_id=?
                    """,
                    (STATUS_CODE_SENT, enc_session, sent.phone_code_hash, auth_id),
                )
            return {"auth_id": auth_id, "status": STATUS_CODE_SENT}
        except Exception:
            logger.exception("auth.start failed auth_id=%s", auth_id)
            _set_error(auth_id, "START_FAILED")
            raise
        finally:
            await client.disconnect()

    import asyncio

    logger.info("auth.start phone=%s", variants[0])
    return asyncio.run(_run())


def submit_code(auth_id: str, code: str) -> dict:
    auth_id = (auth_id or "").strip()
    code = (code or "").strip()
    if not auth_id:
        raise ValueError("AUTH_ID_REQUIRED")
    if not code:
        raise ValueError("CODE_REQUIRED")
    async def _run():
        with db() as con:
            row = con.execute(
                "SELECT * FROM auth_flows WHERE auth_id = ?",
                (auth_id,),
            ).fetchone()
        if not row:
            raise KeyError("AUTH_NOT_FOUND")
        if row["method"] != METHOD_CODE:
            raise ValueError("BAD_METHOD")
        if row["status"] != STATUS_CODE_SENT:
            raise ValueError("BAD_STATE")
        if _is_expired(row["expires_at"]):
            _mark_expired(auth_id)
            raise ValueError("AUTH_EXPIRED")

        phone = row["phone"]
        session_string = decrypt_text(row["temp_session"])
        phone_code_hash = row["phone_code_hash"]

        client = TelegramClient(StringSession(session_string), TG_API_ID, TG_API_HASH)
        await client.connect()
        try:
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                new_session = client.session.save()
                enc_session = encrypt_text(new_session)
                with db() as con:
                    con.execute(
                        """
                        UPDATE auth_flows SET status=?, temp_session=? WHERE auth_id=?
                        """,
                        (STATUS_WAIT_PASSWORD, enc_session, auth_id),
                    )
                return {"auth_id": auth_id, "status": STATUS_WAIT_PASSWORD}

            me = await client.get_me()
            final_session = client.session.save()
            enc_final_session = encrypt_text(final_session)
            with db() as con:
                con.execute(
                    """
                    INSERT INTO accounts(display_name, phone, created_at, updated_at, is_active, user_id, username, local_user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(phone) DO UPDATE SET
                        updated_at=excluded.updated_at,
                        user_id=excluded.user_id,
                        username=excluded.username,
                        local_user_id=excluded.local_user_id
                    """,
                    (
                        getattr(me, "first_name", None),
                        phone,
                        now_iso(),
                        now_iso(),
                        1,
                        getattr(me, "id", None),
                        getattr(me, "username", None),
                        row["local_user_id"],
                    ),
                )
                account_row = con.execute(
                    "SELECT id FROM accounts WHERE phone = ?",
                    (phone,),
                ).fetchone()
                account_id = account_row["id"]
                con.execute(
                    """
                    UPDATE auth_flows SET status=?, temp_session=?, account_id=? WHERE auth_id=?
                    """,
                    (STATUS_READY, enc_final_session, account_id, auth_id),
                )
                con.execute(
                    """
                    UPDATE tg_sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL
                    """,
                    (now_iso(), account_id),
                )
                con.execute(
                    """
                    INSERT INTO tg_sessions(account_id, session_string, updated_at, revoked_at)
                    VALUES (?, ?, ?, NULL)
                    """,
                    (account_id, enc_final_session, now_iso()),
                )
                _log_event(account_id, "INFO", "auth READY via code")

            return {"auth_id": auth_id, "status": STATUS_READY}
        except Exception:
            logger.exception("auth.code failed auth_id=%s", auth_id)
            _set_error(auth_id, "CODE_FAILED")
            account_id = row["account_id"] if row and "account_id" in row.keys() else None
            _log_event(account_id, "ERROR", "auth code failed")
            raise
        finally:
            await client.disconnect()

    import asyncio

    logger.info("auth.code auth_id=%s", auth_id)
    return asyncio.run(_run())


def submit_password(auth_id: str, password: str) -> dict:
    auth_id = (auth_id or "").strip()
    if not auth_id:
        raise ValueError("AUTH_ID_REQUIRED")
    if password is None or not str(password).strip():
        raise ValueError("PASSWORD_REQUIRED")
    async def _run_code(row):
        phone = row["phone"]
        session_string = decrypt_text(row["temp_session"])

        client = TelegramClient(StringSession(session_string), TG_API_ID, TG_API_HASH)
        await client.connect()
        try:
            await client.sign_in(password=password)
            me = await client.get_me()
            final_session = client.session.save()
            enc_final_session = encrypt_text(final_session)

            with db() as con:
                con.execute(
                    """
                    INSERT INTO accounts(display_name, phone, created_at, updated_at, is_active, user_id, username, local_user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(phone) DO UPDATE SET
                        updated_at=excluded.updated_at,
                        user_id=excluded.user_id,
                        username=excluded.username,
                        local_user_id=excluded.local_user_id
                    """,
                    (
                        getattr(me, "first_name", None),
                        phone,
                        now_iso(),
                        now_iso(),
                        1,
                        getattr(me, "id", None),
                        getattr(me, "username", None),
                        row["local_user_id"],
                    ),
                )
                account_row = con.execute(
                    "SELECT id FROM accounts WHERE phone = ?",
                    (phone,),
                ).fetchone()
                account_id = account_row["id"]
                con.execute(
                    """
                    UPDATE auth_flows SET status=?, temp_session=?, account_id=? WHERE auth_id=?
                    """,
                    (STATUS_READY, enc_final_session, account_id, auth_id),
                )
                con.execute(
                    "UPDATE tg_sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL",
                    (now_iso(), account_id),
                )
                con.execute(
                    """
                    INSERT INTO tg_sessions(account_id, session_string, updated_at, revoked_at)
                    VALUES (?, ?, ?, NULL)
                    """,
                    (account_id, enc_final_session, now_iso()),
                )
                _log_event(account_id, "INFO", "auth READY via 2FA")

            return {"auth_id": auth_id, "status": STATUS_READY}
        finally:
            await client.disconnect()

    async def _run_qr_password(row):
        with _qr_lock:
            state = _qr_flows.get(auth_id)
        if not state:
            raise RuntimeError("QR_FLOW_NOT_FOUND")
        if state.wait_task and not state.wait_task.done():
            state.wait_task.cancel()
        try:
            logger.info("auth.password.qr start auth_id=%s", auth_id)
            try:
                logger.info("auth.password.qr sign_in auth_id=%s", auth_id)
                await asyncio.wait_for(state.client.sign_in(password=password), timeout=30)
                logger.info("auth.password.qr get_me auth_id=%s", auth_id)
                me = await asyncio.wait_for(state.client.get_me(), timeout=30)
                logger.info("auth.password.qr save_session auth_id=%s", auth_id)
                final_session = state.client.session.save()
                enc_final_session = encrypt_text(final_session)
            except PasswordHashInvalidError:
                _set_error(auth_id, "PASSWORD_INVALID")
                logger.exception("auth.password.qr invalid password auth_id=%s", auth_id)
                raise
            except FloodWaitError as e:
                _set_error(auth_id, f"FLOOD_WAIT_{e.seconds}")
                logger.exception("auth.password.qr flood wait auth_id=%s", auth_id)
                raise
            except asyncio.TimeoutError:
                _set_error(auth_id, "PASSWORD_TIMEOUT")
                logger.exception("auth.password.qr timeout auth_id=%s", auth_id)
                raise
            except Exception:
                _set_error(auth_id, "PASSWORD_FAILED")
                logger.exception("auth.password.qr failed auth_id=%s", auth_id)
                raise

            def _write(con):
                phone = getattr(me, "phone", None)
                con.execute(
                    """
                    INSERT INTO accounts(display_name, phone, created_at, updated_at, is_active, user_id, username, local_user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(phone) DO UPDATE SET
                        updated_at=excluded.updated_at,
                        user_id=excluded.user_id,
                        username=excluded.username,
                        local_user_id=excluded.local_user_id
                    """,
                    (
                        getattr(me, "first_name", None),
                        phone,
                        now_iso(),
                        now_iso(),
                        1,
                        getattr(me, "id", None),
                        getattr(me, "username", None),
                        row["local_user_id"],
                    ),
                )
                account_row = con.execute(
                    "SELECT id FROM accounts WHERE phone = ?",
                    (phone,),
                ).fetchone() if phone else None
                account_id = account_row["id"] if account_row else None
                con.execute(
                    """
                    UPDATE auth_flows SET status=?, temp_session=?, account_id=? WHERE auth_id=?
                    """,
                    (STATUS_READY, enc_final_session, account_id, auth_id),
                )
                if account_id:
                    con.execute(
                        "UPDATE tg_sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL",
                        (now_iso(), account_id),
                    )
                    con.execute(
                        """
                        INSERT INTO tg_sessions(account_id, session_string, updated_at, revoked_at)
                        VALUES (?, ?, ?, NULL)
                        """,
                        (account_id, enc_final_session, now_iso()),
                    )
                    con.execute(
                        """
                        INSERT INTO events(account_id, level, message, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (account_id, "INFO", "auth READY via 2FA", now_iso()),
                    )
            await _db_write_with_timeout(_write, timeout=10.0)
            logger.info("auth.password.qr db_write done auth_id=%s", auth_id)
        finally:
            await _qr_disconnect_async(auth_id)

        return {"auth_id": auth_id, "status": STATUS_READY}

    lock = _get_flow_lock(auth_id)
    with lock:
        with db() as con:
            row = con.execute(
                "SELECT * FROM auth_flows WHERE auth_id = ?",
                (auth_id,),
            ).fetchone()
        if not row:
            raise KeyError("AUTH_NOT_FOUND")
        if row["status"] in (STATUS_READY, STATUS_CANCELLED, STATUS_EXPIRED, STATUS_ERROR):
            return {"auth_id": auth_id, "status": row["status"]}
        if row["status"] != STATUS_WAIT_PASSWORD:
            raise ValueError("BAD_STATE")
        if _is_expired(row["expires_at"]):
            _mark_expired(auth_id)
            raise ValueError("AUTH_EXPIRED")

        logger.info("auth.password auth_id=%s", auth_id)
        try:
            if row["method"] == METHOD_QR:
                return _run_qr(_run_qr_password(row))
            return asyncio.run(_run_code(row))
        except Exception:
            logger.exception("auth.password failed auth_id=%s method=%s", auth_id, row["method"])
            _set_error(auth_id, "PASSWORD_FAILED")
            account_id = row["account_id"] if row and "account_id" in row.keys() else None
            _log_event(account_id, "ERROR", "auth password failed")
            raise


def get_status(auth_id: str) -> dict:
    with db() as con:
        row = con.execute(
            "SELECT auth_id, status, expires_at, error_message FROM auth_flows WHERE auth_id = ?",
            (auth_id,),
        ).fetchone()
    if not row:
        raise KeyError("AUTH_NOT_FOUND")
    if row["status"] not in (STATUS_READY, STATUS_ERROR, STATUS_EXPIRED) and _is_expired(row["expires_at"]):
        _mark_expired(auth_id)
        return {"auth_id": row["auth_id"], "status": STATUS_EXPIRED, "expires_at": row["expires_at"]}
    return {
        "auth_id": row["auth_id"],
        "status": row["status"],
        "expires_at": row["expires_at"],
        "error_message": row["error_message"],
    }


def cancel_auth(auth_id: str) -> dict:
    with db() as con:
        row = con.execute(
            "SELECT auth_id, status, account_id FROM auth_flows WHERE auth_id = ?",
            (auth_id,),
        ).fetchone()
    if not row:
        raise KeyError("AUTH_NOT_FOUND")
    if row["status"] in (STATUS_READY, STATUS_EXPIRED, STATUS_CANCELLED):
        return {"auth_id": row["auth_id"], "status": row["status"]}

    with db() as con:
        con.execute(
            "UPDATE auth_flows SET status=? WHERE auth_id=?",
            (STATUS_CANCELLED, auth_id),
        )
    _log_event(row["account_id"], "INFO", "auth cancelled")
    _qr_disconnect(auth_id)
    return {"auth_id": row["auth_id"], "status": STATUS_CANCELLED}


class QRFlowState:
    def __init__(self, client: TelegramClient, qr_login, auth_id: str):
        self.client = client
        self.qr_login = qr_login
        self.auth_id = auth_id
        self.wait_task: Optional[asyncio.Task] = None


_qr_lock = threading.Lock()
_db_lock = threading.RLock()
_flow_locks: dict[str, threading.Lock] = {}
_qr_flows: dict[str, QRFlowState] = {}
_qr_loop = asyncio.new_event_loop()


def _qr_loop_runner() -> None:
    asyncio.set_event_loop(_qr_loop)
    _qr_loop.run_forever()


_qr_thread = threading.Thread(target=_qr_loop_runner, daemon=True)
_qr_thread.start()


def _run_qr(coro, timeout: Optional[float] = None):
    future = asyncio.run_coroutine_threadsafe(coro, _qr_loop)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        future.cancel()
        raise


def _get_flow_lock(auth_id: str) -> threading.Lock:
    with _qr_lock:
        lock = _flow_locks.get(auth_id)
        if not lock:
            lock = threading.Lock()
            _flow_locks[auth_id] = lock
        return lock


def _qr_disconnect(auth_id: str) -> None:
    _run_qr(_qr_disconnect_async(auth_id))


async def _qr_disconnect_async(auth_id: str) -> None:
    with _qr_lock:
        state = _qr_flows.pop(auth_id, None)
    if not state:
        return
    if state.wait_task and not state.wait_task.done():
        state.wait_task.cancel()
    await state.client.disconnect()


def _qr_make_png_data_url(url: str) -> str:
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


async def _qr_wait_for_login(auth_id: str) -> None:
    with _qr_lock:
        state = _qr_flows.get(auth_id)
    if not state:
        return

    try:
        with db() as con:
            row = con.execute(
                "SELECT expires_at, qr_expires_at, local_user_id FROM auth_flows WHERE auth_id=?",
                (auth_id,),
            ).fetchone()
        flow_expires = _parse_iso(row["expires_at"]) if row else None
        qr_expires = _parse_iso(row["qr_expires_at"]) if row else None
        local_user_id = row["local_user_id"] if row else None
        target_expires = flow_expires
        if qr_expires and (not flow_expires or qr_expires < flow_expires):
            target_expires = qr_expires
        if not target_expires:
            target_expires = almaty_now_naive() + timedelta(seconds=QR_TTL_SECONDS)
        timeout = max(1, int((target_expires - almaty_now_naive()).total_seconds()))
        await state.qr_login.wait(timeout=timeout)
    except SessionPasswordNeededError:
        with db() as con:
            con.execute(
                "UPDATE auth_flows SET status=? WHERE auth_id=?",
                (STATUS_WAIT_PASSWORD, auth_id),
            )
        return
    except asyncio.TimeoutError:
        _mark_expired(auth_id)
        _qr_disconnect(auth_id)
        return
    except Exception:
        logger.exception("auth.qr wait failed auth_id=%s", auth_id)
        _set_error(auth_id, "QR_WAIT_FAILED")
        await _qr_disconnect_async(auth_id)
        return

    try:
        me = await state.client.get_me()
        final_session = state.client.session.save()
        enc_final_session = encrypt_text(final_session)
        def _write(con):
            phone = getattr(me, "phone", None)
            account_row = _account_by_phone(con, phone) if phone else None
            if account_row:
                account_id = account_row["id"]
                if _has_active_session(con, account_id):
                    _set_error(auth_id, "ACTIVE_SESSION_EXISTS")
                    return
                if _is_account_busy(con, account_id):
                    _set_error(auth_id, "ACCOUNT_BUSY")
                    return

            con.execute(
                """
                INSERT INTO accounts(display_name, phone, created_at, updated_at, is_active, user_id, username, local_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(phone) DO UPDATE SET
                    updated_at=excluded.updated_at,
                    user_id=excluded.user_id,
                    username=excluded.username,
                    local_user_id=excluded.local_user_id
                """,
                (
                    getattr(me, "first_name", None),
                    phone,
                    now_iso(),
                    now_iso(),
                    1,
                    getattr(me, "id", None),
                    getattr(me, "username", None),
                    local_user_id,
                ),
            )
            if phone:
                account_row = con.execute(
                    "SELECT id FROM accounts WHERE phone = ?",
                    (phone,),
                ).fetchone()
                account_id = account_row["id"] if account_row else None
            else:
                account_id = con.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            con.execute(
                """
                UPDATE auth_flows SET status=?, temp_session=?, account_id=? WHERE auth_id=?
                """,
                (STATUS_READY, enc_final_session, account_id, auth_id),
            )
            if account_id:
                con.execute(
                    "UPDATE tg_sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL",
                    (now_iso(), account_id),
                )
                con.execute(
                    """
                    INSERT INTO tg_sessions(account_id, session_string, updated_at, revoked_at)
                    VALUES (?, ?, ?, NULL)
                    """,
                    (account_id, enc_final_session, now_iso()),
                )
                con.execute(
                    """
                    INSERT INTO events(account_id, level, message, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (account_id, "INFO", "auth READY via QR", now_iso()),
                )
        await _db_write_with_timeout(_write, timeout=10.0)
    except Exception:
        logger.exception("auth.qr finalize failed auth_id=%s", auth_id)
        _set_error(auth_id, "QR_FINALIZE_FAILED")
    finally:
        await _qr_disconnect_async(auth_id)


async def _qr_create_flow(auth_id: str, local_user_id: int) -> dict:
    client = TelegramClient(StringSession(""), TG_API_ID, TG_API_HASH)
    try:
        await asyncio.wait_for(client.connect(), timeout=QR_CONNECT_TIMEOUT_SECONDS)
        qr_login = await asyncio.wait_for(client.qr_login(), timeout=QR_LOGIN_CREATE_TIMEOUT_SECONDS)
        qr_url = qr_login.url
        qr_png = _qr_make_png_data_url(qr_url)
        temp_session = client.session.save()
        enc_temp = encrypt_text(temp_session)
        enc_token = encrypt_text(qr_url)
        qr_expires_at = parse_iso_local(qr_login.expires.isoformat()).isoformat()

        with db() as con:
            con.execute(
                """
                INSERT INTO auth_flows(auth_id, phone, status, temp_session, phone_code_hash, expires_at, method,
                                       qr_token, qr_expires_at, qr_refresh_after, error_message, local_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    auth_id,
                    None,
                    STATUS_QR_READY,
                    enc_temp,
                    None,
                    expires_at_iso(),
                    METHOD_QR,
                    enc_token,
                    qr_expires_at,
                    qr_refresh_after_iso(),
                    None,
                    local_user_id,
                ),
            )

        state = QRFlowState(client=client, qr_login=qr_login, auth_id=auth_id)
        with _qr_lock:
            _qr_flows[auth_id] = state
            state.wait_task = asyncio.create_task(_qr_wait_for_login(auth_id))

        return {
            "auth_id": auth_id,
            "status": STATUS_QR_READY,
            "qr_data_url": qr_png,
            "expires_at": qr_expires_at,
            "refresh_after": qr_refresh_after_iso(),
        }
    except asyncio.TimeoutError:
        await client.disconnect()
        raise RuntimeError("QR_START_TIMEOUT")
    except Exception:
        await client.disconnect()
        raise


async def _qr_refresh_flow(auth_id: str) -> dict:
    with _qr_lock:
        state = _qr_flows.get(auth_id)
    if not state:
        raise RuntimeError("QR_FLOW_NOT_FOUND")

    await asyncio.wait_for(state.qr_login.recreate(), timeout=QR_REFRESH_TIMEOUT_SECONDS)
    qr_url = state.qr_login.url
    qr_png = _qr_make_png_data_url(qr_url)
    enc_token = encrypt_text(qr_url)
    qr_expires_at = parse_iso_local(state.qr_login.expires.isoformat()).isoformat()

    with db() as con:
        con.execute(
            """
            UPDATE auth_flows SET status=?, qr_token=?, qr_expires_at=?, qr_refresh_after=?, error_message=NULL
            WHERE auth_id=?
            """,
            (STATUS_QR_READY, enc_token, qr_expires_at, qr_refresh_after_iso(), auth_id),
        )

    if state.wait_task and not state.wait_task.done():
        state.wait_task.cancel()
    state.wait_task = asyncio.create_task(_qr_wait_for_login(auth_id))

    return {
        "auth_id": auth_id,
        "status": STATUS_QR_READY,
        "qr_data_url": qr_png,
        "expires_at": qr_expires_at,
        "refresh_after": qr_refresh_after_iso(),
    }


def start_qr_auth(local_user_id: int) -> dict:
    if not TG_API_ID or not TG_API_HASH:
        raise RuntimeError("TG_API_ID/TG_API_HASH not set")
    with db() as con:
        # Expire abandoned QR flows whose QR token is already stale.
        con.execute(
            """
            UPDATE auth_flows
            SET status=?, error_message=?
            WHERE local_user_id=?
              AND method=?
              AND status IN (?, ?)
              AND qr_expires_at IS NOT NULL
              AND qr_expires_at <= ?
            """,
            (
                STATUS_EXPIRED,
                "QR_TOKEN_EXPIRED",
                local_user_id,
                METHOD_QR,
                STATUS_QR_READY,
                STATUS_QR_WAIT_CONFIRM,
                now_iso(),
            ),
        )
        # After service restarts, in-memory QR states are lost; clean stale DB flows first.
        rows = con.execute(
            """
            SELECT auth_id
            FROM auth_flows
            WHERE local_user_id=?
              AND method=?
              AND status IN (?, ?, ?)
              AND expires_at > ?
            """,
            (
                local_user_id,
                METHOD_QR,
                STATUS_QR_READY,
                STATUS_QR_WAIT_CONFIRM,
                STATUS_WAIT_PASSWORD,
                now_iso(),
            ),
        ).fetchall()
        with _qr_lock:
            active_mem_ids = set(_qr_flows.keys())
        for row in rows:
            stale_auth_id = str(row["auth_id"] or "")
            if stale_auth_id and stale_auth_id not in active_mem_ids:
                con.execute(
                    "UPDATE auth_flows SET status=?, error_message=? WHERE auth_id=?",
                    (STATUS_ERROR, "QR_STALE_FLOW_CLEANED", stale_auth_id),
                )
        # Prevent resource exhaustion: allow only one active QR auth flow per local user at a time.
        if _active_qr_flow_exists(con, local_user_id):
            raise ValueError("AUTH_IN_PROGRESS")
    auth_id = str(uuid.uuid4())
    try:
        return _run_qr(_qr_create_flow(auth_id, local_user_id), timeout=QR_START_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError:
        logger.exception("auth.qr start timeout auth_id=%s", auth_id)
        raise RuntimeError("QR_START_TIMEOUT")


def refresh_qr_auth(auth_id: str) -> dict:
    with db() as con:
        row = con.execute(
            "SELECT status, expires_at, method FROM auth_flows WHERE auth_id=?",
            (auth_id,),
        ).fetchone()
    if not row:
        raise KeyError("AUTH_NOT_FOUND")
    if row["method"] != METHOD_QR:
        raise ValueError("BAD_METHOD")
    if row["status"] in (STATUS_READY, STATUS_EXPIRED, STATUS_CANCELLED):
        raise ValueError("BAD_STATE")
    if _is_expired(row["expires_at"]):
        _mark_expired(auth_id)
        raise ValueError("AUTH_EXPIRED")
    return _run_qr(_qr_refresh_flow(auth_id))


def continue_qr_auth(auth_id: str) -> dict:
    with db() as con:
        row = con.execute(
            "SELECT status, expires_at, error_message, method FROM auth_flows WHERE auth_id=?",
            (auth_id,),
        ).fetchone()
    if not row:
        raise KeyError("AUTH_NOT_FOUND")
    if row["method"] != METHOD_QR:
        raise ValueError("BAD_METHOD")
    if _is_expired(row["expires_at"]) and row["status"] not in (STATUS_READY, STATUS_ERROR, STATUS_EXPIRED):
        _mark_expired(auth_id)
        return {"auth_id": auth_id, "status": STATUS_EXPIRED, "expires_at": row["expires_at"]}
    status = row["status"]
    if status == STATUS_QR_READY:
        status = STATUS_QR_WAIT_CONFIRM
    return {
        "auth_id": auth_id,
        "status": status,
        "error_message": row["error_message"],
        "expires_at": row["expires_at"],
    }
