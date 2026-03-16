from datetime import datetime, timedelta
import os
import asyncio
import sqlite3
import re
import json
from typing import Optional

import httpx

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from common.auth import create_session, hash_password, revoke_token, verify_token
from common.config import FRONTEND_ORIGINS, TG_API_HASH, TG_API_ID
from common.crypto import decrypt_text
from common.db import db, init_db
from common.timezone import almaty_now_naive, now_iso, parse_iso_local
from common.users import (
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
    ROLE_USER,
    can_create_admins,
    can_delete_target,
    create_local_user,
    get_user_role,
    role_to_str,
)
from common.logging_setup import get_logger, request_id_middleware, setup_logging
from common.service_restarts import (
    RESTARTABLE_SERVICES,
    RESTARTABLE_SERVICES_BY_KEY,
    RESTART_COOLDOWN_SECONDS,
)
from common.system_flags import get_system_restarting
from common.telegram_alerts import notify_support_request
from ai.defaults import load_support_site_structure_instruction
from telethon import TelegramClient
from telethon.errors import UsernameInvalidError, UsernameNotOccupiedError
from telethon.errors.rpcerrorlist import AuthKeyUnregisteredError
from telethon.tl.types import User
from telethon.sessions import StringSession


setup_logging()
logger = get_logger("main.api")

app = FastAPI(title="Main Backend")
app.middleware("http")(request_id_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
def _compile_keywords_patterns_csv(raw: str) -> list[re.Pattern]:
    parts = [p.strip() for p in str(raw or "").split(",")]
    parts = [p for p in parts if p]
    seen = set()
    out = []
    for p in parts:
        k = p.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    # Whole word/phrase match (case-insensitive), Unicode-aware.
    return [re.compile(rf"(?<!\w){re.escape(p)}(?!\w)", re.IGNORECASE) for p in out if p]


def _sync_group_matches_home_hidden(con: sqlite3.Connection, account_id: int, patterns: list[re.Pattern]) -> None:
    """
    Ensure Home -> "Чтение групп" can hide stale matches that no longer match keywords,
    while Monitoring history keeps full data.
    """
    if not patterns:
        con.execute("UPDATE group_matches SET home_hidden=1 WHERE account_id=?", (account_id,))
        return
    rows = con.execute(
        "SELECT id, message_text FROM group_matches WHERE account_id=?",
        (account_id,),
    ).fetchall()
    for r in rows:
        text = r["message_text"] or ""
        ok = any(p.search(text) for p in patterns)
        con.execute(
            "UPDATE group_matches SET home_hidden=? WHERE id=?",
            (0 if ok else 1, r["id"]),
        )


AI_API_URL = os.getenv("AI_API_URL", "http://127.0.0.1:8002").rstrip("/")
LOGIN_RATE_WINDOW_MINUTES = int(os.getenv("LOGIN_RATE_WINDOW_MINUTES", "15"))
LOGIN_RATE_MAX_FAILS_PER_LOGIN = int(os.getenv("LOGIN_RATE_MAX_FAILS_PER_LOGIN", "12"))
LOGIN_RATE_MAX_FAILS_PER_IP = int(os.getenv("LOGIN_RATE_MAX_FAILS_PER_IP", "40"))
SUPPORT_ASSISTANT_SYSTEM_PROMPT = (
    "Ты ассистент поддержки TG Web Auth. "
    "Твоя задача: понять, можно ли дать точный и полезный ответ сразу в чате. "
    "Если запрос про баг, падение, сбой, потерю данных, возмущение, доступы/инцидент или ты не уверен — эскалируй. "
    "Если это навигация по интерфейсу, базовая инструкция, доступный функционал по роли — отвечай сам. "
    "Верни строго JSON формата: "
    "{\"decision\":\"self_answer\"|\"escalate\",\"assistant_reply\":\"...\",\"reason\":\"...\"}. "
    "Если decision=escalate, assistant_reply может быть пустым."
)

SUPPORT_NOTICE_TITLE = "Новая линия поддержки"
SUPPORT_NOTICE_TEXT = (
    "Теперь вы можете отправлять обращения напрямую в поддержку через кнопку в левом нижнем углу. "
    "Мы стараемся обрабатывать запросы максимально быстро."
)

SUPPORT_STATUS_OPEN = "OPEN"
SUPPORT_STATUS_ESCALATED = "ESCALATED"
SUPPORT_STATUS_RESOLVED = "RESOLVED"
SUPPORT_ROUTE_PENDING = "PENDING"
SUPPORT_ROUTE_SELF = "SELF_SERVICE"
SUPPORT_ROUTE_ESCALATED = "ESCALATED"
INCIDENT_SOURCES = {"events", "jobs", "group_worker_runs", "auto_chat_dialogs", "auth_flows", "support_tickets"}


def _client_ip(request: Request) -> str:
    xfwd = (request.headers.get("x-forwarded-for") or "").strip()
    if xfwd:
        first = xfwd.split(",")[0].strip()
        if first:
            return first[:128]
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip[:128]
    if request.client and request.client.host:
        return str(request.client.host)[:128]
    return ""


def _user_agent(request: Request) -> str:
    return (request.headers.get("user-agent") or "").strip()[:512]


def _current_login_fail_counts(con: sqlite3.Connection, login: str, ip: str) -> tuple[int, int]:
    since = (almaty_now_naive() - timedelta(minutes=LOGIN_RATE_WINDOW_MINUTES)).isoformat()
    login_fail_count = con.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM local_login_attempts
        WHERE success=0
          AND LOWER(login)=LOWER(?)
          AND created_at>=?
        """,
        (login, since),
    ).fetchone()["cnt"]
    ip_fail_count = 0
    if ip:
        ip_fail_count = con.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM local_login_attempts
            WHERE success=0
              AND ip=?
              AND created_at>=?
            """,
            (ip, since),
        ).fetchone()["cnt"]
    return int(login_fail_count or 0), int(ip_fail_count or 0)


def _is_rate_limited(con: sqlite3.Connection, login: str, ip: str) -> bool:
    login_fail_count, ip_fail_count = _current_login_fail_counts(con, login, ip)
    return (
        login_fail_count >= LOGIN_RATE_MAX_FAILS_PER_LOGIN
        or ip_fail_count >= LOGIN_RATE_MAX_FAILS_PER_IP
    )


def _record_login_attempt(
    con: sqlite3.Connection,
    *,
    login: str,
    user_id: Optional[int],
    ip: str,
    user_agent: str,
    success: bool,
    reason: str,
) -> None:
    con.execute(
        """
        INSERT INTO local_login_attempts(user_id, login, ip, user_agent, success, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            login,
            ip,
            user_agent,
            1 if success else 0,
            reason,
            now_iso(),
        ),
    )


@app.get("/health")
def health(request: Request):
    require_auth(request)
    logger.info("health")
    return {"ok": True}


@app.get("/ai/status")
def ai_status(request: Request, probe: bool = Query(False)):
    require_auth(request)
    with db() as con:
        restart_flag = get_system_restarting(con)
    restart_payload = {
        "system_restarting": bool(restart_flag),
        "system_restart_reason": (restart_flag or {}).get("value_text", ""),
        "system_restart_until": (restart_flag or {}).get("expires_at"),
    }
    try:
        r = httpx.get(
            f"{AI_API_URL}/ai/health",
            params={"probe": "true" if probe else "false"},
            timeout=4.0,
        )
        if r.status_code >= 400:
            code = ""
            try:
                data = r.json()
                code = str(data.get("detail") or data.get("error") or "").strip()
            except Exception:
                code = ""
            return {"ok": False, "error": code or "AI_UNAVAILABLE", **restart_payload}
        data = r.json()
        return {"ok": True, **data, **restart_payload}
    except Exception as e:
        logger.info("ai status failed: %s: %s", type(e).__name__, e)
        return {"ok": False, "error": "AI_UNAVAILABLE", **restart_payload}


class LoginReq(BaseModel):
    login: str
    password: str


@app.post("/local/login")
def local_login(req: LoginReq, request: Request):
    login = (req.login or "").strip()
    password = req.password or ""
    if not login or not str(password).strip():
        raise HTTPException(400, "MISSING_FIELDS")
    password_hash = hash_password(password)
    ip = _client_ip(request)
    ua = _user_agent(request)
    with db() as con:
        if _is_rate_limited(con, login, ip):
            _record_login_attempt(
                con,
                login=login,
                user_id=None,
                ip=ip,
                user_agent=ua,
                success=False,
                reason="LOGIN_RATE_LIMITED",
            )
            raise HTTPException(429, "LOGIN_RATE_LIMITED")
        try:
            row = con.execute(
                """
                SELECT id, is_active, is_admin, role FROM local_users
                WHERE login=? AND password_hash=?
                """,
                (login, password_hash),
            ).fetchone()
        except Exception:
            row = con.execute(
                """
                SELECT id, is_active, is_admin FROM local_users
                WHERE login=? AND password_hash=?
                """,
                (login, password_hash),
            ).fetchone()
    if not row or row["is_active"] != 1:
        with db() as con:
            _record_login_attempt(
                con,
                login=login,
                user_id=int(row["id"]) if row else None,
                ip=ip,
                user_agent=ua,
                success=False,
                reason="BAD_CREDENTIALS",
            )
        raise HTTPException(401, "BAD_CREDENTIALS")
    with db() as con:
        _record_login_attempt(
            con,
            login=login,
            user_id=int(row["id"]),
            ip=ip,
            user_agent=ua,
            success=True,
            reason="OK",
        )
    session = create_session(row["id"])
    role = int(row["role"] or (1 if row["is_admin"] else 0)) if "role" in row.keys() else (1 if row["is_admin"] else 0)
    return {
        "token": session["token"],
        "expires_at": session["expires_at"],
        "is_admin": bool(row["is_admin"]) or role >= ROLE_ADMIN,
        "is_super_admin": role >= ROLE_SUPER_ADMIN,
    }


@app.post("/local/logout")
def local_logout(request: Request):
    user_id = require_auth(request, allow_disabled=True)
    token = request.headers.get("X-Auth-Token")
    revoke_token(token)
    return {"ok": True, "user_id": user_id}


@app.get("/local/me")
def local_me(request: Request):
    user_id = require_auth(request, allow_disabled=True)
    with db() as con:
        try:
            row = con.execute(
                """
                SELECT id, login, is_admin, role, is_active, created_at,
                       service_enabled, feature_group_reading_enabled, feature_auto_dialogs_enabled, disabled_comment
                FROM local_users
                WHERE id=?
                """,
                (user_id,),
            ).fetchone()
        except Exception:
            row = con.execute(
                "SELECT id, login, is_admin, is_active, created_at FROM local_users WHERE id=?",
                (user_id,),
            ).fetchone()
    if not row:
        raise HTTPException(404, "USER_NOT_FOUND")
    d = dict(row)
    role = int(d.get("role") or (1 if d.get("is_admin") else 0))
    d["role"] = role_to_str(role)
    d["is_admin"] = bool(d.get("is_admin")) or role >= ROLE_ADMIN
    d["is_super_admin"] = role >= ROLE_SUPER_ADMIN
    # capabilities (older DBs may not have these columns)
    d["service_enabled"] = bool(_int01(d.get("service_enabled"), default=1))
    d["feature_group_reading_enabled"] = bool(_int01(d.get("feature_group_reading_enabled"), default=1))
    d["feature_auto_dialogs_enabled"] = bool(_int01(d.get("feature_auto_dialogs_enabled"), default=1))
    d["disabled_comment"] = (d.get("disabled_comment") or "").strip()
    return d


class SettingsReq(BaseModel):
    keywords: Optional[str] = None
    is_active: Optional[bool] = None


class AutoChatUsernamesReq(BaseModel):
    usernames: list[str]


class AutoChatSettingsReq(BaseModel):
    ai_instruction: Optional[str] = None
    greeting_examples: Optional[str] = None
    delay_enabled: Optional[bool] = None
    delay_min_ms: Optional[int] = Field(default=None, ge=0, le=60 * 60 * 1000)
    delay_max_ms: Optional[int] = Field(default=None, ge=0, le=60 * 60 * 1000)
    typing_enabled: Optional[bool] = None
    read_enabled: Optional[bool] = None


class AutoChatStartReq(BaseModel):
    tg_user_ids: list[int]


class AutoChatStopReq(BaseModel):
    dialog_id: int


AUTO_CHAT_STATUS_STARTING = "STARTING"
AUTO_CHAT_STATUS_WAIT_REPLY = "WAIT_REPLY"
AUTO_CHAT_STATUS_ACTIVE = "ACTIVE"
AUTO_CHAT_STATUS_STOPPED = "STOPPED"
AUTO_CHAT_STATUS_ERROR = "ERROR"

AUTO_CHAT_ACTIVE_STATUSES = (
    AUTO_CHAT_STATUS_STARTING,
    AUTO_CHAT_STATUS_WAIT_REPLY,
    AUTO_CHAT_STATUS_ACTIVE,
)

AUTO_CHAT_MAX_ACTIVE_PER_ACCOUNT = int(os.getenv("AUTO_CHAT_MAX_ACTIVE_PER_ACCOUNT", "10"))


@app.get("/local/settings")
def get_settings(request: Request):
    user_id = require_feature(request, FEATURE_GROUP_READING)
    with db() as con:
        row = con.execute(
            """
            SELECT keywords, is_active, created_at, updated_at
            FROM local_user_settings
            WHERE user_id=?
            """,
            (user_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "SETTINGS_NOT_FOUND")
    return dict(row)


@app.patch("/local/settings")
def update_settings(req: SettingsReq, request: Request):
    user_id = require_feature(request, FEATURE_GROUP_READING)
    fields = []
    values = []
    changed_keywords = False
    if req.keywords is not None:
        # Normalize comma-separated keywords: trim, drop empties, de-dupe case-insensitively.
        parts = [p.strip() for p in str(req.keywords or "").split(",")]
        parts = [p for p in parts if p]
        seen = set()
        out = []
        for p in parts:
            k = p.lower()
            if k in seen:
                continue
            seen.add(k)
            out.append(p)
        norm = ", ".join(out)
        fields.append("keywords=?")
        values.append(norm)
        changed_keywords = True
    if req.is_active is not None:
        fields.append("is_active=?")
        values.append(1 if req.is_active else 0)
    if not fields:
        return {"ok": True}
    values.append(now_iso())
    values.append(user_id)
    with db() as con:
        con.execute(
            f"UPDATE local_user_settings SET {', '.join(fields)}, updated_at=? WHERE user_id=?",
            values,
        )
        if changed_keywords:
            # Recompute home_hidden so Home -> "Чтение групп" only shows matches that still match current keywords.
            # Monitoring history must keep the full record, so we hide/unhide via a flag instead of deleting.
            account_rows = con.execute(
                "SELECT id FROM accounts WHERE local_user_id=?",
                (user_id,),
            ).fetchall()
            account_ids = [int(r["id"]) for r in account_rows]
            if account_ids:
                placeholders = ",".join("?" for _ in account_ids)
                kw = [k.lower() for k in out if k]
                # Force a re-scan for listened groups so recent messages are re-evaluated under the new keywords.
                # This is important when user changes keywords after the worker already advanced last_message_id.
                con.execute(
                    f"""
                    UPDATE group_listeners
                    SET last_message_id=NULL, updated_at=?
                    WHERE account_id IN ({placeholders}) AND is_listening=1
                    """,
                    (now_iso(), *account_ids),
                )
                if not kw:
                    con.execute(
                        f"""
                        UPDATE group_matches
                        SET home_hidden=1
                        WHERE account_id IN ({placeholders})
                        """,
                        (*account_ids,),
                    )
                else:
                    # Whole-word/phrase match (case-insensitive), Unicode-aware.
                    patterns = [re.compile(rf"(?<!\\w){re.escape(k)}(?!\\w)", re.IGNORECASE) for k in kw]
                    rows = con.execute(
                        f"""
                        SELECT id, message_text
                        FROM group_matches
                        WHERE account_id IN ({placeholders})
                        """,
                        (*account_ids,),
                    ).fetchall()
                    for r in rows:
                        text = r["message_text"] or ""
                        ok = any(p.search(text) for p in patterns)
                        con.execute(
                            "UPDATE group_matches SET home_hidden=? WHERE id=?",
                            (0 if ok else 1, r["id"]),
                        )
    return {"ok": True}


def _normalize_username(value: str) -> str:
    if not value:
        return ""
    return value.strip().lstrip("@").lower()


@app.get("/local/auto_chat/usernames")
def list_auto_chat_usernames(request: Request):
    user_id = require_feature(request, FEATURE_AUTO_DIALOGS)
    with db() as con:
        rows = con.execute(
            """
            SELECT id, username, created_at, tg_user_id, display_name, status
            FROM local_user_auto_chat_usernames
            WHERE user_id=?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/local/auto_chat/usernames")
def add_auto_chat_usernames(req: AutoChatUsernamesReq, request: Request):
    user_id = require_feature(request, FEATURE_AUTO_DIALOGS)
    usernames = [_normalize_username(u) for u in (req.usernames or [])]
    usernames = [u for u in usernames if u]
    usernames = list(dict.fromkeys(usernames))
    if not usernames:
        return {"ok": True}
    account_id, session_string = _get_active_account_session(user_id)
    if not account_id or not session_string:
        raise HTTPException(400, "NO_ACTIVE_ACCOUNT")

    async def _resolve():
        client = TelegramClient(StringSession(session_string), TG_API_ID, TG_API_HASH)
        await client.connect()
        results = []
        try:
            for username in usernames:
                try:
                    ent = await client.get_entity(username)
                    if isinstance(ent, User):
                        name = " ".join([p for p in [ent.first_name, ent.last_name] if p]) or ""
                        results.append(
                            {
                                "username": username,
                                "tg_user_id": ent.id,
                                "display_name": name,
                                "status": "OK",
                            }
                        )
                    else:
                        title = getattr(ent, "title", "") or ""
                        ent_id = getattr(ent, "id", None)
                        results.append(
                            {
                                "username": username,
                                "tg_user_id": ent_id,
                                "display_name": title,
                                "status": "NOT_USER",
                            }
                        )
                except (UsernameInvalidError, UsernameNotOccupiedError):
                    results.append(
                        {
                            "username": username,
                            "tg_user_id": None,
                            "display_name": None,
                            "status": "NOT_FOUND",
                        }
                    )
                except AuthKeyUnregisteredError:
                    raise
                except Exception:
                    results.append(
                        {
                            "username": username,
                            "tg_user_id": None,
                            "display_name": None,
                            "status": "NOT_FOUND",
                        }
                    )
            return results
        finally:
            await client.disconnect()

    try:
        import asyncio
        try:
            resolved = asyncio.run(_resolve())
        except RuntimeError:
            loop = asyncio.get_event_loop()
            resolved = loop.run_until_complete(_resolve())
    except AuthKeyUnregisteredError:
        _handle_tg_session_expired(user_id, account_id)

    now = now_iso()
    with db() as con:
        for item in resolved:
            con.execute(
                """
                INSERT INTO local_user_auto_chat_usernames(user_id, username, created_at, tg_user_id, display_name, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, username) DO UPDATE SET
                    tg_user_id=excluded.tg_user_id,
                    display_name=excluded.display_name,
                    status=excluded.status
                """,
                (
                    user_id,
                    item["username"],
                    now,
                    item["tg_user_id"],
                    item["display_name"],
                    item["status"],
                ),
            )
    return {"ok": True}


@app.post("/local/auto_chat/usernames/delete")
def delete_auto_chat_usernames(req: AutoChatUsernamesReq, request: Request):
    user_id = require_feature(request, FEATURE_AUTO_DIALOGS)
    usernames = [_normalize_username(u) for u in (req.usernames or [])]
    usernames = [u for u in usernames if u]
    if not usernames:
        return {"ok": True}
    placeholders = ",".join(["?"] * len(usernames))
    with db() as con:
        con.execute(
            f"""
            DELETE FROM local_user_auto_chat_usernames
            WHERE user_id=? AND username IN ({placeholders})
            """,
            (user_id, *usernames),
        )
    return {"ok": True}


@app.post("/local/auto_chat/usernames/clear")
def clear_auto_chat_usernames(request: Request):
    user_id = require_feature(request, FEATURE_AUTO_DIALOGS)
    with db() as con:
        con.execute(
            "DELETE FROM local_user_auto_chat_usernames WHERE user_id=?",
            (user_id,),
        )
    return {"ok": True}


@app.get("/local/auto_chat/settings")
def get_auto_chat_settings(request: Request):
    user_id = require_feature(request, FEATURE_AUTO_DIALOGS)
    with db() as con:
        row = con.execute(
            """
            SELECT ai_instruction, greeting_examples,
                   delay_enabled, delay_min_ms, delay_max_ms, typing_enabled, read_enabled,
                   created_at, updated_at
            FROM local_user_auto_chat_settings
            WHERE user_id=?
            """,
            (user_id,),
        ).fetchone()
        if not row:
            now = now_iso()
            con.execute(
                """
                INSERT OR IGNORE INTO local_user_auto_chat_settings(user_id, ai_instruction, greeting_examples, created_at, updated_at)
                VALUES (?, '', '', ?, ?)
                """,
                (user_id, now, now),
            )
            row = con.execute(
                """
                SELECT ai_instruction, greeting_examples,
                       delay_enabled, delay_min_ms, delay_max_ms, typing_enabled, read_enabled,
                       created_at, updated_at
                FROM local_user_auto_chat_settings
                WHERE user_id=?
                """,
                (user_id,),
            ).fetchone()
    return dict(row)


@app.patch("/local/auto_chat/settings")
def update_auto_chat_settings(req: AutoChatSettingsReq, request: Request):
    user_id = require_feature(request, FEATURE_AUTO_DIALOGS)
    fields = []
    values = []
    if req.ai_instruction is not None:
        fields.append("ai_instruction=?")
        values.append(req.ai_instruction)
    if req.greeting_examples is not None:
        fields.append("greeting_examples=?")
        values.append(req.greeting_examples)
    if req.delay_enabled is not None:
        fields.append("delay_enabled=?")
        values.append(1 if req.delay_enabled else 0)
    if req.delay_min_ms is not None:
        fields.append("delay_min_ms=?")
        values.append(int(req.delay_min_ms))
    if req.delay_max_ms is not None:
        fields.append("delay_max_ms=?")
        values.append(int(req.delay_max_ms))
    if req.typing_enabled is not None:
        fields.append("typing_enabled=?")
        values.append(1 if req.typing_enabled else 0)
    if req.read_enabled is not None:
        fields.append("read_enabled=?")
        values.append(1 if req.read_enabled else 0)

    # Normalize delay bounds if both provided.
    if req.delay_min_ms is not None and req.delay_max_ms is not None:
        if int(req.delay_min_ms) > int(req.delay_max_ms):
            raise HTTPException(400, "DELAY_MIN_GT_MAX")
    if not fields:
        return {"ok": True}
    values.append(now_iso())
    values.append(user_id)
    with db() as con:
        con.execute(
            f"UPDATE local_user_auto_chat_settings SET {', '.join(fields)}, updated_at=? WHERE user_id=?",
            values,
        )
    return {"ok": True}


@app.get("/auto_chat/dialogs")
def list_auto_chat_dialogs(request: Request):
    user_id = require_feature(request, FEATURE_AUTO_DIALOGS)
    account_id, _ = _get_active_account_session(user_id)
    if not account_id:
        return {"account_id": None, "limit": AUTO_CHAT_MAX_ACTIVE_PER_ACCOUNT, "active_count": 0, "items": []}
    with db() as con:
        rows = con.execute(
            """
            SELECT id, account_id, peer_tg_user_id, peer_username, peer_display_name,
                   status, last_error, pending_incoming, last_ai_request_at, last_ai_latency_ms,
                   created_at, updated_at, started_at, stopped_at
            FROM auto_chat_dialogs
            WHERE account_id=?
            ORDER BY updated_at DESC, id DESC
            """,
            (account_id,),
        ).fetchall()
        active_count = con.execute(
            f"""
            SELECT COUNT(*) AS cnt
            FROM auto_chat_dialogs
            WHERE account_id=? AND status IN ({",".join(["?"]*len(AUTO_CHAT_ACTIVE_STATUSES))})
            """,
            (account_id, *AUTO_CHAT_ACTIVE_STATUSES),
        ).fetchone()["cnt"]
    return {
        "account_id": account_id,
        "limit": AUTO_CHAT_MAX_ACTIVE_PER_ACCOUNT,
        "active_count": active_count,
        "items": [dict(r) for r in rows],
    }


@app.get("/auto_chat/dialogs/{dialog_id}/messages")
def list_auto_chat_messages(
    dialog_id: int,
    request: Request,
    limit: int = Query(200, ge=1, le=2000),
    since: Optional[str] = Query(None),
    after_id: Optional[int] = Query(None, ge=0),
):
    user_id = require_feature(request, FEATURE_AUTO_DIALOGS)
    account_id, _ = _get_active_account_session(user_id)
    if not account_id:
        raise HTTPException(400, "NO_ACTIVE_ACCOUNT")
    with db() as con:
        row = con.execute(
            "SELECT id FROM auto_chat_dialogs WHERE id=? AND account_id=?",
            (dialog_id, account_id),
        ).fetchone()
        if not row:
            raise HTTPException(404, "DIALOG_NOT_FOUND")
        where = ["dialog_id=?"]
        params: list[object] = [dialog_id]
        if since:
            where.append("created_at>=?")
            params.append(since)
        if after_id is not None:
            where.append("id>?")
            params.append(int(after_id))

        if after_id is not None:
            # Incremental: return in ascending order for easy append.
            rows = con.execute(
                f"""
                SELECT id, direction, text, tg_message_id, created_at
                FROM auto_chat_messages
                WHERE {' AND '.join(where)}
                ORDER BY id ASC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        else:
            # Initial load: grab last N and reverse to chronological.
            rows = con.execute(
                f"""
                SELECT id, direction, text, tg_message_id, created_at
                FROM auto_chat_messages
                WHERE {' AND '.join(where)}
                ORDER BY id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
    items = [dict(r) for r in rows]
    if after_id is None:
        items.reverse()
    return {"dialog_id": dialog_id, "items": items}


@app.post("/auto_chat/dialogs/start")
def start_auto_chat(req: AutoChatStartReq, request: Request):
    user_id = require_feature(request, FEATURE_AUTO_DIALOGS)
    account_id, _ = _get_active_account_session(user_id)
    if not account_id:
        raise HTTPException(400, "NO_ACTIVE_ACCOUNT")
    tg_ids = [int(x) for x in (req.tg_user_ids or []) if int(x) > 0]
    tg_ids = list(dict.fromkeys(tg_ids))
    if not tg_ids:
        return {"ok": True, "started": 0}

    now = now_iso()
    with db() as con:
        active_count = con.execute(
            f"""
            SELECT COUNT(*) AS cnt
            FROM auto_chat_dialogs
            WHERE account_id=? AND status IN ({",".join(["?"]*len(AUTO_CHAT_ACTIVE_STATUSES))})
            """,
            (account_id, *AUTO_CHAT_ACTIVE_STATUSES),
        ).fetchone()["cnt"]

        available = max(0, AUTO_CHAT_MAX_ACTIVE_PER_ACCOUNT - int(active_count))
        if available <= 0:
            raise HTTPException(400, "AUTO_CHAT_LIMIT_REACHED")

        to_start = tg_ids[:available]

        # Map metadata from saved usernames (optional).
        meta_rows = con.execute(
            f"""
            SELECT username, tg_user_id, display_name
            FROM local_user_auto_chat_usernames
            WHERE user_id=? AND tg_user_id IN ({",".join(["?"]*len(to_start))})
            """,
            (user_id, *to_start),
        ).fetchall()
        meta = {r["tg_user_id"]: r for r in meta_rows}

        started = 0
        for peer_id in to_start:
            m = meta.get(peer_id)
            username = m["username"] if m else None
            display_name = m["display_name"] if m else None
            con.execute(
                """
                INSERT INTO auto_chat_dialogs(
                    account_id, peer_tg_user_id, peer_username, peer_display_name,
                    status, last_error, pending_incoming, created_at, updated_at, started_at
                )
                VALUES (?, ?, ?, ?, ?, NULL, 0, ?, ?, ?)
                ON CONFLICT(account_id, peer_tg_user_id) DO UPDATE SET
                    peer_username=COALESCE(excluded.peer_username, auto_chat_dialogs.peer_username),
                    peer_display_name=COALESCE(excluded.peer_display_name, auto_chat_dialogs.peer_display_name),
                    status=excluded.status,
                    last_error=NULL,
                    pending_incoming=0,
                    updated_at=excluded.updated_at,
                    started_at=excluded.started_at,
                    stopped_at=NULL
                """,
                (
                    account_id,
                    peer_id,
                    username,
                    display_name,
                    AUTO_CHAT_STATUS_STARTING,
                    now,
                    now,
                    now,
                ),
            )
            started += 1
    return {"ok": True, "started": started, "limit": AUTO_CHAT_MAX_ACTIVE_PER_ACCOUNT}


@app.post("/auto_chat/dialogs/stop")
def stop_auto_chat(req: AutoChatStopReq, request: Request):
    user_id = require_feature(request, FEATURE_AUTO_DIALOGS)
    account_id, _ = _get_active_account_session(user_id)
    if not account_id:
        raise HTTPException(400, "NO_ACTIVE_ACCOUNT")
    now = now_iso()
    with db() as con:
        row = con.execute(
            "SELECT id FROM auto_chat_dialogs WHERE id=? AND account_id=?",
            (req.dialog_id, account_id),
        ).fetchone()
        if not row:
            raise HTTPException(404, "DIALOG_NOT_FOUND")
        con.execute(
            """
            UPDATE auto_chat_dialogs
            SET status=?, stopped_at=?, updated_at=?, pending_incoming=0
            WHERE id=? AND account_id=?
            """,
            (AUTO_CHAT_STATUS_STOPPED, now, now, req.dialog_id, account_id),
        )
    return {"ok": True}


class AccountCreateReq(BaseModel):
    display_name: str
    phone: Optional[str] = None
    tags: Optional[str] = None


class AccountPatchReq(BaseModel):
    display_name: Optional[str] = None
    tags: Optional[str] = None


class SessionSwitchReq(BaseModel):
    session_id: int


class SessionRevokeReq(BaseModel):
    session_id: Optional[int] = None


class GroupListenReq(BaseModel):
    is_listening: bool
    title: Optional[str] = None


class GroupMatchesReq(BaseModel):
    messages: list[str]

class RequisitesFilter(BaseModel):
    requisite_type: Optional[str] = None
    country: Optional[str] = None
    limit: int = Query(100, ge=1, le=1000)
    offset: int = Query(0, ge=0)


@app.get("/accounts")
def list_accounts(request: Request):
    user_id = require_auth(request)
    with db() as con:
        rows = con.execute(
            """
            SELECT id, display_name, phone, user_id, username, tags,
                   created_at, updated_at, is_active
            FROM accounts
            WHERE local_user_id=?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/accounts")
def create_account(req: AccountCreateReq, request: Request):
    user_id = require_auth(request)
    with db() as con:
        try:
            con.execute(
                """
                INSERT INTO accounts(display_name, phone, tags, created_at, updated_at, is_active, local_user_id)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (req.display_name, req.phone, req.tags, now_iso(), now_iso(), user_id),
            )
        except sqlite3.IntegrityError as e:
            # Most common: phone must be unique.
            if "UNIQUE constraint failed: accounts.phone" in str(e):
                raise HTTPException(409, "PHONE_EXISTS")
            raise HTTPException(400, "CREATE_FAILED")
        except Exception as e:
            logger.exception("account create failed")
            raise HTTPException(400, "CREATE_FAILED")
        row = con.execute("SELECT last_insert_rowid() AS id").fetchone()
    return {"id": row["id"]}


@app.patch("/accounts/{account_id}")
def update_account(account_id: int, req: AccountPatchReq, request: Request):
    user_id = require_auth(request)
    fields = []
    values = []
    if req.display_name is not None:
        fields.append("display_name=?")
        values.append(req.display_name)
    if req.tags is not None:
        fields.append("tags=?")
        values.append(req.tags)
    if not fields:
        return {"ok": True}
    values.append(now_iso())
    values.append(account_id)
    values.append(user_id)
    with db() as con:
        res = con.execute(
            f"UPDATE accounts SET {', '.join(fields)}, updated_at=? WHERE id=? AND local_user_id=?",
            tuple(values),
        )
    if res.rowcount == 0:
        raise HTTPException(404, "ACCOUNT_NOT_FOUND")
    return {"ok": True}


@app.post("/accounts/{account_id}/activate")
def activate_account(account_id: int, request: Request):
    user_id = require_auth(request)
    with db() as con:
        res = con.execute(
            "UPDATE accounts SET is_active=1, updated_at=? WHERE id=? AND local_user_id=?",
            (now_iso(), account_id, user_id),
        )
    if res.rowcount == 0:
        raise HTTPException(404, "ACCOUNT_NOT_FOUND")
    return {"ok": True}


@app.post("/accounts/{account_id}/deactivate")
def deactivate_account(account_id: int, request: Request):
    user_id = require_auth(request)
    with db() as con:
        res = con.execute(
            "UPDATE accounts SET is_active=0, updated_at=? WHERE id=? AND local_user_id=?",
            (now_iso(), account_id, user_id),
        )
    if res.rowcount == 0:
        raise HTTPException(404, "ACCOUNT_NOT_FOUND")
    return {"ok": True}


@app.delete("/accounts/{account_id}")
def delete_account(request: Request, account_id: int, confirm: bool = Query(False)):
    user_id = require_auth(request)
    if not confirm:
        raise HTTPException(400, "CONFIRM_REQUIRED")
    with db() as con:
        row = con.execute(
            "SELECT id, phone FROM accounts WHERE id=? AND local_user_id=?",
            (account_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(404, "ACCOUNT_NOT_FOUND")
        con.execute("DELETE FROM tg_sessions WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM auth_flows WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM events WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM jobs WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM accounts WHERE id=?", (account_id,))
    return {"ok": True}


@app.get("/accounts/{account_id}/sessions")
def list_sessions(account_id: int, request: Request):
    user_id = require_auth(request)
    with db() as con:
        owner = con.execute(
            "SELECT id FROM accounts WHERE id=? AND local_user_id=?",
            (account_id, user_id),
        ).fetchone()
        if not owner:
            raise HTTPException(404, "ACCOUNT_NOT_FOUND")
        rows = con.execute(
            """
            SELECT id, account_id, updated_at, revoked_at, dc_id, user_id
            FROM tg_sessions
            WHERE account_id=?
            ORDER BY updated_at DESC
            """,
            (account_id,),
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/accounts/{account_id}/sessions/revoke")
def revoke_session(account_id: int, req: SessionRevokeReq, request: Request):
    user_id = require_auth(request)
    with db() as con:
        owner = con.execute(
            "SELECT id FROM accounts WHERE id=? AND local_user_id=?",
            (account_id, user_id),
        ).fetchone()
        if not owner:
            raise HTTPException(404, "ACCOUNT_NOT_FOUND")
        if req.session_id is not None:
            res = con.execute(
                """
                UPDATE tg_sessions SET revoked_at=?
                WHERE id=? AND account_id=? AND revoked_at IS NULL
                """,
                (now_iso(), req.session_id, account_id),
            )
        else:
            res = con.execute(
                """
                UPDATE tg_sessions SET revoked_at=?
                WHERE account_id=? AND revoked_at IS NULL
                """,
                (now_iso(), account_id),
            )
    if res.rowcount == 0:
        raise HTTPException(404, "SESSION_NOT_FOUND")
    return {"ok": True}


@app.post("/accounts/{account_id}/sessions/switch")
def switch_session(account_id: int, req: SessionSwitchReq, request: Request):
    user_id = require_auth(request)
    with db() as con:
        owner = con.execute(
            "SELECT id FROM accounts WHERE id=? AND local_user_id=?",
            (account_id, user_id),
        ).fetchone()
        if not owner:
            raise HTTPException(404, "ACCOUNT_NOT_FOUND")
        row = con.execute(
            """
            SELECT id FROM tg_sessions
            WHERE id=? AND account_id=?
            """,
            (req.session_id, account_id),
        ).fetchone()
        if not row:
            raise HTTPException(404, "SESSION_NOT_FOUND")
        con.execute(
            "UPDATE tg_sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL AND id!=?",
            (now_iso(), account_id, req.session_id),
        )
        con.execute(
            "UPDATE tg_sessions SET revoked_at=NULL, updated_at=? WHERE id=?",
            (now_iso(), req.session_id),
        )
    return {"ok": True}


@app.get("/sessions/active")
def active_sessions(request: Request):
    user_id = require_auth(request)
    with db() as con:
        rows = con.execute(
            """
            SELECT s.id AS session_id, s.account_id, s.updated_at, a.display_name, a.phone
            FROM tg_sessions s
            JOIN accounts a ON a.id = s.account_id
            WHERE s.revoked_at IS NULL
              AND a.local_user_id=?
              AND a.is_active=1
            ORDER BY s.updated_at DESC
            """,
            (user_id,),
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.get("/dialogs")
def list_dialogs(request: Request, type: str = Query("groups")):
    user_id = require_auth(request)
    account_id, session_string = _get_active_account_session(user_id)
    if not account_id or not session_string:
        return {"items": []}

    if type not in ("groups", "private"):
        raise HTTPException(400, "BAD_TYPE")

    async def _run():
        client = TelegramClient(StringSession(session_string), TG_API_ID, TG_API_HASH)
        await client.connect()
        try:
            dialogs = await client.get_dialogs(limit=200)
            items = []
            for d in dialogs:
                ent = d.entity
                if type == "private":
                    if getattr(ent, "bot", False):
                        continue
                    if ent.__class__.__name__ != "User":
                        continue
                    items.append(
                        {
                            "id": d.id,
                            "title": d.name or "",
                            "type": "private",
                        }
                    )
                else:
                    is_group = ent.__class__.__name__ in ("Chat", "Channel")
                    if not is_group:
                        continue
                    items.append(
                        {
                            "id": d.id,
                            "title": d.name or "",
                            "type": "group",
                        }
                    )
            return items
        finally:
            await client.disconnect()

    try:
        import asyncio
        try:
            items = asyncio.run(_run())
        except RuntimeError:
            loop = asyncio.get_event_loop()
            items = loop.run_until_complete(_run())
    except AuthKeyUnregisteredError:
        _handle_tg_session_expired(user_id, account_id)

    return {"account_id": account_id, "items": items}


@app.get("/groups")
def list_groups(request: Request):
    user_id = require_feature(request, FEATURE_GROUP_READING)
    account_id, session_string = _get_active_account_session(user_id)
    if not account_id or not session_string:
        return {"account_id": None, "worker_id": None, "items": []}

    cached_items = _get_cached_groups(account_id, max_age_sec=60)
    if cached_items is None:
        async def _run():
            client = TelegramClient(StringSession(session_string), TG_API_ID, TG_API_HASH)
            await client.connect()
            try:
                dialogs = await client.get_dialogs(limit=300)
                items = []
                for d in dialogs:
                    ent = d.entity
                    is_group = ent.__class__.__name__ in ("Chat", "Channel")
                    if not is_group:
                        continue
                    items.append(
                        {
                            "id": d.id,
                            "title": d.name or "",
                            "type": "group",
                        }
                    )
                return items
            finally:
                await client.disconnect()

        try:
            try:
                items = asyncio.run(_run())
            except RuntimeError:
                loop = asyncio.get_event_loop()
                items = loop.run_until_complete(_run())
        except AuthKeyUnregisteredError:
            _handle_tg_session_expired(user_id, account_id)
        _upsert_group_catalog(account_id, items)
    else:
        async def _validate_session():
            client = TelegramClient(StringSession(session_string), TG_API_ID, TG_API_HASH)
            await client.connect()
            try:
                await client.get_me()
            finally:
                await client.disconnect()

        try:
            try:
                asyncio.run(_validate_session())
            except RuntimeError:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(_validate_session())
        except AuthKeyUnregisteredError:
            _handle_tg_session_expired(user_id, account_id)
        items = cached_items

    # Keep Home counters/history consistent with current keywords (whole-word matching),
    # even if DB still contains older substring-based matches.
    with db() as con:
        srow = con.execute(
            "SELECT keywords FROM local_user_settings WHERE user_id=?",
            (user_id,),
        ).fetchone()
        patterns = _compile_keywords_patterns_csv(srow["keywords"] if srow else "")
        _sync_group_matches_home_hidden(con, account_id, patterns)

    with db() as con:
        rows = con.execute(
            """
            SELECT
              gl.chat_id,
              gl.is_listening,
              gl.title,
              COUNT(DISTINCT CASE WHEN COALESCE(gm.home_hidden, 0)=0 THEN gm.message_id END) AS match_count
            FROM group_listeners gl
            LEFT JOIN group_matches gm
              ON gm.account_id = gl.account_id AND gm.chat_id = gl.chat_id
            WHERE gl.account_id=?
            GROUP BY gl.chat_id
            """,
            (account_id,),
        ).fetchall()
    listen_map = {row["chat_id"]: row for row in rows}
    for item in items:
        row = listen_map.get(item["id"])
        if row:
            item["is_listening"] = bool(row["is_listening"])
            item["match_count"] = row["match_count"] or 0
            if row["title"]:
                item["title"] = row["title"]
        else:
            item["is_listening"] = False
            item["match_count"] = 0
    with db() as con:
        run_row = con.execute(
            """
            SELECT id FROM group_worker_runs
            WHERE account_id=? AND status='RUNNING'
            ORDER BY id DESC
            LIMIT 1
            """,
            (account_id,),
        ).fetchone()
    return {"account_id": account_id, "worker_id": run_row["id"] if run_row else None, "items": items}


@app.get("/group_workers")
def list_group_workers(request: Request, limit: int = Query(100, ge=1, le=500)):
    user_id = require_auth(request)
    account_id, _ = _get_active_account_session(user_id)
    if not account_id:
        return {"account_id": None, "items": []}
    with db() as con:
        rows = con.execute(
            """
            SELECT id, account_id, status, started_at, stopped_at, last_error
            FROM group_worker_runs
            WHERE account_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (account_id, limit),
        ).fetchall()
    return {"account_id": account_id, "items": [dict(r) for r in rows]}


@app.post("/groups/{chat_id}/listen")
def set_group_listen(chat_id: int, req: GroupListenReq, request: Request):
    user_id = require_feature(request, FEATURE_GROUP_READING)
    account_id, _ = _get_active_account_session(user_id)
    if not account_id:
        raise HTTPException(400, "NO_ACTIVE_ACCOUNT")
    with db() as con:
        con.execute(
            """
            INSERT INTO group_listeners(account_id, chat_id, title, is_listening, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id, chat_id) DO UPDATE SET
                is_listening=excluded.is_listening,
                title=COALESCE(excluded.title, group_listeners.title),
                updated_at=excluded.updated_at
            """,
            (
                account_id,
                chat_id,
                req.title,
                1 if req.is_listening else 0,
                now_iso(),
                now_iso(),
            ),
        )
    return {"ok": True, "chat_id": chat_id, "is_listening": req.is_listening}


@app.get("/groups/{chat_id}/matches")
def list_group_matches(chat_id: int, request: Request, limit: int = Query(50, ge=1, le=500)):
    user_id = require_feature(request, FEATURE_GROUP_READING)
    account_id, _ = _get_active_account_session(user_id)
    if not account_id:
        return {"items": []}
    with db() as con:
        srow = con.execute(
            "SELECT keywords FROM local_user_settings WHERE user_id=?",
            (user_id,),
        ).fetchone()
        patterns = _compile_keywords_patterns_csv(srow["keywords"] if srow else "")
        # Sync only for this chat (cheaper) so modal is always correct.
        rows = con.execute(
            "SELECT id, message_text FROM group_matches WHERE account_id=? AND chat_id=?",
            (account_id, chat_id),
        ).fetchall()
        if not patterns:
            con.execute(
                "UPDATE group_matches SET home_hidden=1 WHERE account_id=? AND chat_id=?",
                (account_id, chat_id),
            )
        else:
            for r in rows:
                text = r["message_text"] or ""
                ok = any(p.search(text) for p in patterns)
                con.execute(
                    "UPDATE group_matches SET home_hidden=? WHERE id=?",
                    (0 if ok else 1, r["id"]),
                )
    with db() as con:
        rows = con.execute(
            """
            SELECT
              message_id,
              message_text,
              sender_phone,
              MAX(matched_keywords) AS matched_keywords,
              MAX(created_at) AS created_at
            FROM group_matches
            WHERE account_id=? AND chat_id=? AND COALESCE(home_hidden, 0)=0
            GROUP BY message_id, message_text, sender_phone
            ORDER BY MAX(id) DESC
            LIMIT ?
            """,
            (account_id, chat_id, limit),
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.get("/groups/{chat_id}/matches/count")
def count_group_matches(chat_id: int, request: Request):
    user_id = require_feature(request, FEATURE_GROUP_READING)
    account_id, _ = _get_active_account_session(user_id)
    if not account_id:
        return {"count": 0}
    with db() as con:
        srow = con.execute(
            "SELECT keywords FROM local_user_settings WHERE user_id=?",
            (user_id,),
        ).fetchone()
        patterns = _compile_keywords_patterns_csv(srow["keywords"] if srow else "")
        # Keep counter consistent with modal list.
        rows = con.execute(
            "SELECT id, message_text FROM group_matches WHERE account_id=? AND chat_id=?",
            (account_id, chat_id),
        ).fetchall()
        if not patterns:
            con.execute(
                "UPDATE group_matches SET home_hidden=1 WHERE account_id=? AND chat_id=?",
                (account_id, chat_id),
            )
        else:
            for r in rows:
                text = r["message_text"] or ""
                ok = any(p.search(text) for p in patterns)
                con.execute(
                    "UPDATE group_matches SET home_hidden=? WHERE id=?",
                    (0 if ok else 1, r["id"]),
                )
    with db() as con:
        row = con.execute(
            """
            SELECT COUNT(DISTINCT message_id) AS cnt
            FROM group_matches
            WHERE account_id=? AND chat_id=? AND COALESCE(home_hidden, 0)=0
            """,
            (account_id, chat_id),
        ).fetchone()
    return {"count": row["cnt"]}


@app.post("/groups/{chat_id}/matches/hide_home")
def hide_group_matches_home(chat_id: int, request: Request):
    """
    Hide found matches from Home -> "Чтение групп" without deleting them from Monitoring history.
    """
    user_id = require_feature(request, FEATURE_GROUP_READING)
    account_id, _ = _get_active_account_session(user_id)
    if not account_id:
        raise HTTPException(400, "NO_ACTIVE_ACCOUNT")
    with db() as con:
        con.execute(
            """
            UPDATE group_matches
            SET home_hidden=1
            WHERE account_id=? AND chat_id=? AND COALESCE(home_hidden, 0)=0
            """,
            (account_id, chat_id),
        )
        row = con.execute("SELECT changes() AS n").fetchone()
    return {"ok": True, "hidden": int(row["n"] or 0)}


@app.get("/group_matches")
def list_group_matches_history(
    request: Request,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    User-facing "listening history": matches found across all chats for the ACTIVE telegram account only.
    Admins have a separate endpoint that can list matches across all accounts.
    """
    user_id = require_feature(request, FEATURE_GROUP_READING)
    account_id, _ = _get_active_account_session(user_id)
    if not account_id:
        return {"account_id": None, "items": []}
    with db() as con:
        rows = con.execute(
            """
            SELECT
              MAX(gm.id) AS id,
              gm.chat_id,
              COALESCE(gl.title, '') AS chat_title,
              gm.message_id,
              gm.message_text,
              gm.sender_phone,
              MAX(gm.matched_keywords) AS matched_keywords,
              MAX(gm.created_at) AS created_at
            FROM group_matches gm
            LEFT JOIN group_listeners gl
              ON gl.account_id = gm.account_id AND gl.chat_id = gm.chat_id
            WHERE gm.account_id=?
            GROUP BY gm.chat_id, gm.message_id, gm.message_text, gm.sender_phone
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (account_id, limit, offset),
        ).fetchall()
    return {"account_id": account_id, "items": [dict(r) for r in rows]}


@app.post("/groups/{chat_id}/matches")
def add_group_matches(chat_id: int, req: GroupMatchesReq, request: Request):
    user_id = require_feature(request, FEATURE_GROUP_READING)
    account_id, _ = _get_active_account_session(user_id)
    if not account_id:
        raise HTTPException(400, "NO_ACTIVE_ACCOUNT")
    now = now_iso()
    with db() as con:
        for text in req.messages:
            con.execute(
                """
                INSERT INTO group_matches(account_id, chat_id, message_text, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (account_id, chat_id, text, now),
            )
    return {"ok": True, "inserted": len(req.messages)}


@app.get("/stats")
def stats(request: Request):
    user_id = require_auth(request)
    with db() as con:
        accounts_total = con.execute(
            "SELECT COUNT(*) AS cnt FROM accounts WHERE local_user_id=?",
            (user_id,),
        ).fetchone()["cnt"]
        job_workers_active = con.execute(
            """
            SELECT COUNT(*) AS cnt FROM jobs
            WHERE status='RUNNING'
              AND account_id IN (SELECT id FROM accounts WHERE local_user_id=?)
            """,
            (user_id,),
        ).fetchone()["cnt"]
        group_workers_active = con.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM group_worker_runs gwr
            JOIN accounts a ON a.id = gwr.account_id
            WHERE gwr.status='RUNNING'
              AND a.local_user_id=?
            """,
            (user_id,),
        ).fetchone()["cnt"]
        queue_total = con.execute(
            """
            SELECT COUNT(*) AS cnt FROM jobs
            WHERE status='QUEUED'
              AND account_id IN (SELECT id FROM accounts WHERE local_user_id=?)
            """,
            (user_id,),
        ).fetchone()["cnt"]
    return {
        "accounts_total": accounts_total,
        "workers_active": job_workers_active + group_workers_active,
        "queue_total": queue_total,
    }


@app.get("/logs")
def logs(request: Request, account_id: Optional[int] = None, limit: int = Query(100, ge=1, le=500)):
    user_id = require_auth(request)
    with db() as con:
        if account_id is None:
            rows = con.execute(
                """
                SELECT id, account_id, level, message, created_at
                FROM events
                WHERE account_id IN (SELECT id FROM accounts WHERE local_user_id=?)
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        else:
            owner = con.execute(
                "SELECT id FROM accounts WHERE id=? AND local_user_id=?",
                (account_id, user_id),
            ).fetchone()
            if not owner:
                raise HTTPException(404, "ACCOUNT_NOT_FOUND")
            rows = con.execute(
                """
                SELECT id, account_id, level, message, created_at
                FROM events
                WHERE account_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (account_id, limit),
            ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.get("/jobs")
def list_jobs(request: Request, account_id: Optional[int] = None, limit: int = Query(100, ge=1, le=500)):
    user_id = require_auth(request)
    with db() as con:
        if account_id is None:
            rows = con.execute(
                """
                SELECT id, account_id, type, status, progress, last_error, created_at, updated_at
                FROM jobs
                WHERE account_id IN (SELECT id FROM accounts WHERE local_user_id=?)
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        else:
            owner = con.execute(
                "SELECT id FROM accounts WHERE id=? AND local_user_id=?",
                (account_id, user_id),
            ).fetchone()
            if not owner:
                raise HTTPException(404, "ACCOUNT_NOT_FOUND")
            rows = con.execute(
                """
                SELECT id, account_id, type, status, progress, last_error, created_at, updated_at
                FROM jobs
                WHERE account_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (account_id, limit),
            ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: int, request: Request):
    user_id = require_auth(request)
    with db() as con:
        row = con.execute(
            """
            SELECT j.status FROM jobs j
            JOIN accounts a ON a.id = j.account_id
            WHERE j.id=? AND a.local_user_id=?
            """,
            (job_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(404, "JOB_NOT_FOUND")
        if row["status"] in ("DONE", "FAILED", "CANCELLED"):
            return {"ok": True}
        con.execute(
            "UPDATE jobs SET status=?, updated_at=? WHERE id=?",
            ("CANCELLED", now_iso(), job_id),
        )
    return {"ok": True}
FEATURE_GROUP_READING = "group_reading"
FEATURE_AUTO_DIALOGS = "auto_dialogs"


def _get_user_caps(con: sqlite3.Connection, user_id: int) -> dict:
    """
    Returns local user capability flags.
    Be defensive for older DBs that don't have these columns yet.
    """
    try:
        row = con.execute(
            """
            SELECT service_enabled, feature_group_reading_enabled, feature_auto_dialogs_enabled, disabled_comment
            FROM local_users
            WHERE id=?
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return {
                "service_enabled": 1,
                "feature_group_reading_enabled": 1,
                "feature_auto_dialogs_enabled": 1,
                "disabled_comment": None,
            }
        return dict(row)
    except Exception:
        return {
            "service_enabled": 1,
            "feature_group_reading_enabled": 1,
            "feature_auto_dialogs_enabled": 1,
            "disabled_comment": None,
        }


def _int01(value, default: int = 1) -> int:
    """Convert SQLite-ish booleans (0/1/None/True/False/'0'/'1') to 0/1."""
    if value is None:
        return 1 if int(default) == 1 else 0
    try:
        return 1 if int(value) == 1 else 0
    except Exception:
        return 1 if bool(value) else 0


def require_auth(request: Request, *, allow_disabled: bool = False) -> int:
    token = request.headers.get("X-Auth-Token")
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(401, "UNAUTHORIZED")
    if allow_disabled:
        return user_id
    with db() as con:
        caps = _get_user_caps(con, user_id)
        if _int01(caps.get("service_enabled"), default=1) != 1:
            comment = (caps.get("disabled_comment") or "").strip()
            raise HTTPException(403, f"SERVICE_DISABLED{': ' + comment if comment else ''}")
    return user_id


def require_feature(request: Request, feature: str) -> int:
    user_id = require_auth(request)
    with db() as con:
        caps = _get_user_caps(con, user_id)
    if feature == FEATURE_GROUP_READING and _int01(caps.get("feature_group_reading_enabled"), default=0) != 1:
        raise HTTPException(403, "FEATURE_DISABLED: group_reading")
    if feature == FEATURE_AUTO_DIALOGS and _int01(caps.get("feature_auto_dialogs_enabled"), default=0) != 1:
        raise HTTPException(403, "FEATURE_DISABLED: auto_dialogs")
    return user_id


def require_admin(request: Request) -> int:
    user_id = require_auth(request)
    with db() as con:
        role = get_user_role(con, user_id)
    if role < ROLE_ADMIN:
        raise HTTPException(403, "ADMIN_ONLY")
    return user_id


def require_super_admin(request: Request) -> int:
    user_id = require_auth(request)
    with db() as con:
        role = get_user_role(con, user_id)
    if role < ROLE_SUPER_ADMIN:
        raise HTTPException(403, "SUPER_ADMIN_ONLY")
    return user_id


def _service_restart_row(con: sqlite3.Connection, service_key: str):
    return con.execute(
        """
        SELECT
            r.id,
            r.service_key,
            r.system_unit,
            r.requested_by_user_id,
            r.requested_at,
            r.status,
            r.processed_at,
            r.error_message,
            u.login AS requested_by_login
        FROM service_restart_requests r
        LEFT JOIN local_users u ON u.id = r.requested_by_user_id
        WHERE r.service_key=?
        ORDER BY r.requested_at DESC, r.id DESC
        LIMIT 1
        """,
        (service_key,),
    ).fetchone()


def _serialize_service_restart(service, row) -> dict:
    payload = {
        "service_key": service.key,
        "label": service.label,
        "system_unit": service.unit,
        "cooldown_seconds": RESTART_COOLDOWN_SECONDS,
        "can_request": True,
        "cooldown_until": None,
        "last_request": None,
    }
    if not row:
        return payload
    requested_at = parse_iso_local(row["requested_at"])
    cooldown_until = None
    can_request = True
    if requested_at is not None:
        cooldown_until_dt = requested_at + timedelta(seconds=RESTART_COOLDOWN_SECONDS)
        cooldown_until = cooldown_until_dt.isoformat()
        can_request = cooldown_until_dt <= almaty_now_naive()
    payload["can_request"] = can_request
    payload["cooldown_until"] = cooldown_until
    payload["last_request"] = {
        "id": row["id"],
        "requested_by_user_id": row["requested_by_user_id"],
        "requested_by_login": row["requested_by_login"],
        "requested_at": row["requested_at"],
        "status": row["status"],
        "processed_at": row["processed_at"],
        "error_message": row["error_message"],
    }
    return payload


def _safe_parse_triage_json(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        pass
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def _support_user_context(con: sqlite3.Connection, user_id: int) -> dict:
    row = con.execute(
        """
        SELECT id, login, is_admin, role,
               service_enabled, feature_group_reading_enabled, feature_auto_dialogs_enabled
        FROM local_users
        WHERE id=?
        """,
        (user_id,),
    ).fetchone()
    if not row:
        return {"id": user_id, "login": "", "role": "user"}
    d = dict(row)
    role_int = int(d.get("role") or (1 if d.get("is_admin") else 0))
    return {
        "id": int(d["id"]),
        "login": str(d.get("login") or ""),
        "role": role_to_str(role_int),
        "service_enabled": bool(int(d.get("service_enabled") or 0)),
        "feature_group_reading_enabled": bool(int(d.get("feature_group_reading_enabled") or 0)),
        "feature_auto_dialogs_enabled": bool(int(d.get("feature_auto_dialogs_enabled") or 0)),
    }


def _support_triage(
    *,
    user_ctx: dict,
    subject: str,
    message: str,
    history: Optional[list[dict]] = None,
) -> dict:
    site_structure = load_support_site_structure_instruction()
    payload = {
        "system": SUPPORT_ASSISTANT_SYSTEM_PROMPT,
        "ui_site_structure_instruction": site_structure,
        "user_context": user_ctx,
        "ticket_subject": subject,
        "ticket_message": message,
        "history": history or [],
        "constraints": {
            "language": "ru",
            "max_reply_chars": 1500,
        },
    }
    prompt = (
        "Проанализируй обращение и верни строго JSON.\n"
        f"INPUT:\n{json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        r = httpx.post(
            f"{AI_API_URL}/ai/generate",
            json={
                "prompt": prompt,
                "max_tokens": 450,
                "temperature": 0.2,
                "top_p": 0.9,
            },
            timeout=25.0,
        )
        if r.status_code >= 400:
            return {"decision": "escalate", "assistant_reply": "", "reason": "AI_UNAVAILABLE"}
        text = str((r.json() or {}).get("text") or "")
        parsed = _safe_parse_triage_json(text)
        decision = str(parsed.get("decision") or "").strip().lower()
        if decision not in ("self_answer", "escalate"):
            return {"decision": "escalate", "assistant_reply": "", "reason": "AI_BAD_DECISION"}
        reply = str(parsed.get("assistant_reply") or "").strip()
        reason = str(parsed.get("reason") or "").strip()[:500]
        if decision == "self_answer" and not reply:
            return {"decision": "escalate", "assistant_reply": "", "reason": "AI_EMPTY_REPLY"}
        return {"decision": decision, "assistant_reply": reply[:1500], "reason": reason}
    except Exception as e:
        logger.info("support triage failed: %s: %s", type(e).__name__, e)
        return {"decision": "escalate", "assistant_reply": "", "reason": "AI_EXCEPTION"}


def _support_add_message(
    con: sqlite3.Connection,
    *,
    ticket_id: int,
    sender_type: str,
    message: str,
    meta: Optional[dict] = None,
) -> None:
    con.execute(
        """
        INSERT INTO support_messages(ticket_id, sender_type, message, meta_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            ticket_id,
            sender_type,
            message,
            (json.dumps(meta, ensure_ascii=False) if meta else None),
            now_iso(),
        ),
    )


def _support_escalate_ticket(
    con: sqlite3.Connection,
    *,
    ticket_id: int,
    user_id: int,
    subject: str,
    user_message: str,
    reason: str,
) -> dict:
    now = now_iso()
    login_row = con.execute("SELECT login FROM local_users WHERE id=?", (user_id,)).fetchone()
    local_login = str((login_row["login"] if login_row else "") or "")
    con.execute(
        """
        UPDATE support_tickets
        SET status=?, route=?, escalated_at=?, updated_at=?, last_message_preview=?
        WHERE id=? AND user_id=?
        """,
        (
            SUPPORT_STATUS_ESCALATED,
            SUPPORT_ROUTE_ESCALATED,
            now,
            now,
            (user_message or "")[:240],
            ticket_id,
            user_id,
        ),
    )
    _support_add_message(
        con,
        ticket_id=ticket_id,
        sender_type="SYSTEM",
        message="Обращение передано в поддержку.",
        meta={"event": "ESCALATED", "reason": reason or "UNKNOWN"},
    )
    con.execute(
        """
        INSERT INTO events(account_id, level, message, created_at)
        VALUES (NULL, 'WARN', ?, ?)
        """,
        (f"SUPPORT_ESCALATED: ticket_id={ticket_id}; user_id={user_id}; subject={subject}", now),
    )
    return {
        "ticket_id": ticket_id,
        "local_user_id": user_id,
        "local_login": local_login,
        "subject": subject,
        "message": user_message,
    }


def _support_ticket_row(con: sqlite3.Connection, ticket_id: int, user_id: int):
    return con.execute(
        """
        SELECT id, user_id, subject, status, route, last_message_preview, created_at, updated_at, resolved_at, escalated_at
        FROM support_tickets
        WHERE id=? AND user_id=?
        """,
        (ticket_id, user_id),
    ).fetchone()


def _support_ticket_row_admin(con: sqlite3.Connection, ticket_id: int):
    return con.execute(
        """
        SELECT id, user_id, subject, status, route, last_message_preview, created_at, updated_at, resolved_at, escalated_at
        FROM support_tickets
        WHERE id=?
        """,
        (ticket_id,),
    ).fetchone()


class SupportTicketCreateReq(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=3, max_length=6000)


class SupportTicketChatReq(BaseModel):
    message: str = Field(min_length=1, max_length=6000)


@app.get("/support/notice")
def support_notice(request: Request):
    user_id = require_auth(request)
    with db() as con:
        row = con.execute("SELECT support_notice_seen_at FROM local_users WHERE id=?", (user_id,)).fetchone()
    seen = bool(row and row["support_notice_seen_at"])
    return {
        "show": not seen,
        "title": SUPPORT_NOTICE_TITLE,
        "text": SUPPORT_NOTICE_TEXT,
    }


@app.post("/support/notice/ack")
def support_notice_ack(request: Request):
    user_id = require_auth(request)
    with db() as con:
        con.execute(
            "UPDATE local_users SET support_notice_seen_at=? WHERE id=?",
            (now_iso(), user_id),
        )
    return {"ok": True}


@app.get("/support/tickets")
def support_list_tickets(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    user_id = require_auth(request)
    with db() as con:
        total = con.execute(
            "SELECT COUNT(*) AS cnt FROM support_tickets WHERE user_id=?",
            (user_id,),
        ).fetchone()["cnt"]
        rows = con.execute(
            """
            SELECT id, user_id, subject, status, route, last_message_preview, created_at, updated_at, resolved_at, escalated_at
            FROM support_tickets
            WHERE user_id=?
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        ).fetchall()
    return {"items": [dict(r) for r in rows], "total": int(total or 0), "limit": limit, "offset": offset}


@app.get("/support/tickets/{ticket_id}/messages")
def support_ticket_messages(
    ticket_id: int,
    request: Request,
    limit: int = Query(200, ge=1, le=1000),
):
    user_id = require_auth(request)
    with db() as con:
        owner = _support_ticket_row(con, ticket_id, user_id)
        if not owner:
            raise HTTPException(404, "SUPPORT_TICKET_NOT_FOUND")
        rows = con.execute(
            """
            SELECT id, ticket_id, sender_type, message, meta_json, created_at
            FROM support_messages
            WHERE ticket_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (ticket_id, limit),
        ).fetchall()
    items = [dict(r) for r in rows][::-1]
    return {"items": items}


@app.post("/support/tickets")
def support_create_ticket(req: SupportTicketCreateReq, request: Request):
    user_id = require_auth(request)
    subject = (req.subject or "").strip()
    message = (req.message or "").strip()
    if len(subject) < 3 or len(message) < 3:
        raise HTTPException(400, "INVALID_SUPPORT_MESSAGE")

    escalated_payload = None
    with db() as con:
        now = now_iso()
        cur = con.execute(
            """
            INSERT INTO support_tickets(user_id, subject, status, route, last_message_preview, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                subject[:200],
                SUPPORT_STATUS_OPEN,
                SUPPORT_ROUTE_PENDING,
                message[:240],
                now,
                now,
            ),
        )
        ticket_id = int(cur.lastrowid)
        _support_add_message(con, ticket_id=ticket_id, sender_type="USER", message=message)

        user_ctx = _support_user_context(con, user_id)
        triage = _support_triage(user_ctx=user_ctx, subject=subject, message=message)
        if triage["decision"] == "self_answer":
            reply = triage["assistant_reply"]
            _support_add_message(
                con,
                ticket_id=ticket_id,
                sender_type="ASSISTANT",
                message=reply,
                meta={"reason": triage.get("reason", "")},
            )
            con.execute(
                """
                UPDATE support_tickets
                SET route=?, updated_at=?, last_message_preview=?
                WHERE id=? AND user_id=?
                """,
                (SUPPORT_ROUTE_SELF, now_iso(), reply[:240], ticket_id, user_id),
            )
            ticket = _support_ticket_row(con, ticket_id, user_id)
            return {"ticket": dict(ticket), "action": "self_answer", "assistant_message": reply}

        escalated_payload = _support_escalate_ticket(
            con,
            ticket_id=ticket_id,
            user_id=user_id,
            subject=subject,
            user_message=message,
            reason=str(triage.get("reason") or ""),
        )
        ticket = _support_ticket_row(con, ticket_id, user_id)

    if escalated_payload:
        notify_support_request(**escalated_payload)
    return {"ticket": dict(ticket), "action": "escalated"}


@app.post("/support/tickets/{ticket_id}/chat")
def support_ticket_chat(ticket_id: int, req: SupportTicketChatReq, request: Request):
    user_id = require_auth(request)
    message = (req.message or "").strip()
    if not message:
        raise HTTPException(400, "EMPTY_MESSAGE")
    escalated_payload = None
    with db() as con:
        ticket = _support_ticket_row(con, ticket_id, user_id)
        if not ticket:
            raise HTTPException(404, "SUPPORT_TICKET_NOT_FOUND")
        route = str(ticket["route"] or "")
        if route == SUPPORT_ROUTE_ESCALATED:
            raise HTTPException(409, "SUPPORT_ALREADY_ESCALATED")
        if str(ticket["status"] or "") == SUPPORT_STATUS_RESOLVED:
            raise HTTPException(409, "SUPPORT_TICKET_RESOLVED")

        _support_add_message(con, ticket_id=ticket_id, sender_type="USER", message=message)
        con.execute(
            "UPDATE support_tickets SET updated_at=?, last_message_preview=? WHERE id=? AND user_id=?",
            (now_iso(), message[:240], ticket_id, user_id),
        )
        hist_rows = con.execute(
            """
            SELECT sender_type, message
            FROM support_messages
            WHERE ticket_id=?
            ORDER BY id DESC
            LIMIT 20
            """,
            (ticket_id,),
        ).fetchall()
        history = []
        for r in reversed(hist_rows):
            role = "user" if str(r["sender_type"]) == "USER" else "assistant"
            history.append({"role": role, "message": str(r["message"] or "")[:1200]})

        user_ctx = _support_user_context(con, user_id)
        triage = _support_triage(
            user_ctx=user_ctx,
            subject=str(ticket["subject"] or ""),
            message=message,
            history=history,
        )
        if triage["decision"] == "self_answer":
            reply = triage["assistant_reply"]
            _support_add_message(
                con,
                ticket_id=ticket_id,
                sender_type="ASSISTANT",
                message=reply,
                meta={"reason": triage.get("reason", "")},
            )
            con.execute(
                """
                UPDATE support_tickets
                SET route=?, updated_at=?, last_message_preview=?
                WHERE id=? AND user_id=?
                """,
                (SUPPORT_ROUTE_SELF, now_iso(), reply[:240], ticket_id, user_id),
            )
            ticket2 = _support_ticket_row(con, ticket_id, user_id)
            return {"ticket": dict(ticket2), "action": "self_answer", "assistant_message": reply}

        escalated_payload = _support_escalate_ticket(
            con,
            ticket_id=ticket_id,
            user_id=user_id,
            subject=str(ticket["subject"] or ""),
            user_message=message,
            reason=str(triage.get("reason") or ""),
        )
        ticket2 = _support_ticket_row(con, ticket_id, user_id)

    if escalated_payload:
        notify_support_request(**escalated_payload)
    return {"ticket": dict(ticket2), "action": "escalated"}


@app.post("/support/tickets/{ticket_id}/resolve")
def support_ticket_resolve(ticket_id: int, request: Request):
    user_id = require_auth(request)
    with db() as con:
        row = _support_ticket_row(con, ticket_id, user_id)
        if not row:
            raise HTTPException(404, "SUPPORT_TICKET_NOT_FOUND")
        now = now_iso()
        con.execute(
            """
            UPDATE support_tickets
            SET status=?, resolved_at=?, updated_at=?
            WHERE id=? AND user_id=?
            """,
            (SUPPORT_STATUS_RESOLVED, now, now, ticket_id, user_id),
        )
        _support_add_message(
            con,
            ticket_id=ticket_id,
            sender_type="SYSTEM",
            message="Пользователь пометил обращение как решенное.",
            meta={"event": "RESOLVED_BY_USER"},
        )
        row2 = _support_ticket_row(con, ticket_id, user_id)
    return {"ticket": dict(row2), "ok": True}


class AdminUserCreateReq(BaseModel):
    login: str
    password: str
    # Backward-compatible: UI used to pass is_admin. Now role is preferred.
    role: Optional[str] = None  # "user" | "admin"
    is_admin: Optional[bool] = False
    is_active: Optional[bool] = True
    service_enabled: Optional[bool] = True
    feature_group_reading_enabled: Optional[bool] = True
    feature_auto_dialogs_enabled: Optional[bool] = True
    disabled_comment: Optional[str] = None


class AdminUserUpdateReq(BaseModel):
    # NOTE: role changes are restricted by actor permissions (see handler).
    role: Optional[str] = None  # "user" | "admin"
    is_active: Optional[bool] = None
    service_enabled: Optional[bool] = None
    feature_group_reading_enabled: Optional[bool] = None
    feature_auto_dialogs_enabled: Optional[bool] = None
    disabled_comment: Optional[str] = None


@app.get("/admin/users")
def admin_list_users(request: Request):
    require_admin(request)
    with db() as con:
        try:
            rows = con.execute(
                """
                SELECT
                    u.id,
                    u.login,
                    u.is_admin,
                    u.role,
                    u.is_active,
                    u.created_at,
                    u.updated_at,
                    u.service_enabled,
                    u.feature_group_reading_enabled,
                    u.feature_auto_dialogs_enabled,
                    u.disabled_comment,
                    (
                        SELECT MAX(lla.created_at)
                        FROM local_login_attempts lla
                        WHERE (lla.user_id = u.id OR LOWER(lla.login) = LOWER(u.login))
                          AND lla.success = 1
                    ) AS last_online_at
                FROM local_users u
                ORDER BY id DESC
                """,
            ).fetchall()
            items = []
            for r in rows:
                d = dict(r)
                role = int(d.get("role") or (1 if d.get("is_admin") else 0))
                d["role"] = role_to_str(role)
                d["is_admin"] = bool(d.get("is_admin")) or role >= ROLE_ADMIN
                d["is_super_admin"] = role >= ROLE_SUPER_ADMIN
                d["service_enabled"] = bool(_int01(d.get("service_enabled"), default=1))
                d["feature_group_reading_enabled"] = bool(_int01(d.get("feature_group_reading_enabled"), default=1))
                d["feature_auto_dialogs_enabled"] = bool(_int01(d.get("feature_auto_dialogs_enabled"), default=1))
                d["disabled_comment"] = (d.get("disabled_comment") or "").strip()
                items.append(d)
            return {"items": items}
        except Exception:
            rows = con.execute(
                """
                SELECT
                    u.id,
                    u.login,
                    u.is_admin,
                    u.is_active,
                    u.created_at,
                    u.updated_at,
                    (
                        SELECT MAX(lla.created_at)
                        FROM local_login_attempts lla
                        WHERE (lla.user_id = u.id OR LOWER(lla.login) = LOWER(u.login))
                          AND lla.success = 1
                    ) AS last_online_at
                FROM local_users u
                ORDER BY id DESC
                """,
            ).fetchall()
            return {"items": [dict(r) for r in rows]}


@app.get("/admin/users/{user_id}/login_history")
def admin_user_login_history(
    user_id: int,
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    require_admin(request)
    with db() as con:
        user = con.execute(
            "SELECT id, login FROM local_users WHERE id=?",
            (user_id,),
        ).fetchone()
        if not user:
            raise HTTPException(404, "USER_NOT_FOUND")
        total = con.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM local_login_attempts
            WHERE user_id=? OR LOWER(login)=LOWER(?)
            """,
            (user_id, user["login"]),
        ).fetchone()["cnt"]
        rows = con.execute(
            """
            SELECT id, user_id, login, ip, user_agent, success, reason, created_at
            FROM local_login_attempts
            WHERE user_id=? OR LOWER(login)=LOWER(?)
            ORDER BY id DESC
            LIMIT ?
            OFFSET ?
            """,
            (user_id, user["login"], limit, offset),
        ).fetchall()
    return {"user_id": user_id, "total": int(total or 0), "limit": limit, "offset": offset, "items": [dict(r) for r in rows]}


@app.get("/admin/system/restarts")
def admin_list_service_restarts(request: Request):
    require_admin(request)
    with db() as con:
        items = []
        for service in RESTARTABLE_SERVICES:
            row = _service_restart_row(con, service.key)
            items.append(_serialize_service_restart(service, row))
    return {"items": items}


@app.post("/admin/system/restarts/{service_key}")
def admin_request_service_restart(service_key: str, request: Request):
    actor_id = require_admin(request)
    service = RESTARTABLE_SERVICES_BY_KEY.get(str(service_key or "").strip())
    if not service:
        raise HTTPException(404, "SERVICE_NOT_FOUND")
    with db() as con:
        latest = _service_restart_row(con, service.key)
        if latest:
            requested_at = parse_iso_local(latest["requested_at"])
            if requested_at is not None:
                cooldown_until = requested_at + timedelta(seconds=RESTART_COOLDOWN_SECONDS)
                if cooldown_until > almaty_now_naive():
                    raise HTTPException(429, "RESTART_COOLDOWN_ACTIVE")
        con.execute(
            """
            INSERT INTO service_restart_requests(service_key, system_unit, requested_by_user_id, requested_at, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (service.key, service.unit, actor_id, now_iso(), "PENDING"),
        )
        row = _service_restart_row(con, service.key)
    return {"ok": True, "item": _serialize_service_restart(service, row)}


@app.post("/admin/system/auth/clear_all")
def admin_clear_all_auths(request: Request):
    require_admin(request)
    token = request.headers.get("X-Auth-Token")
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                "http://127.0.0.1:8001/admin/auth/clear_all",
                headers={"X-Auth-Token": token or ""},
            )
    except httpx.HTTPError:
        raise HTTPException(502, "AUTH_SERVICE_UNAVAILABLE")
    if resp.status_code >= 400:
        detail = None
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = None
        raise HTTPException(resp.status_code, detail or "CLEAR_ALL_AUTHS_FAILED")
    try:
        return resp.json()
    except Exception:
        raise HTTPException(502, "AUTH_SERVICE_BAD_RESPONSE")


@app.post("/admin/users")
def admin_create_user(req: AdminUserCreateReq, request: Request):
    actor_id = require_admin(request)
    if not req.login or not req.password:
        raise HTTPException(400, "MISSING_FIELDS")
    password_hash = hash_password(req.password)
    desired_role = ROLE_USER
    if req.role:
        if req.role.strip().lower() not in ("user", "admin"):
            raise HTTPException(400, "INVALID_ROLE")
        desired_role = ROLE_ADMIN if req.role.strip().lower() == "admin" else ROLE_USER
    elif req.is_admin:
        desired_role = ROLE_ADMIN

    if desired_role == ROLE_ADMIN:
        with db() as con:
            actor_role = get_user_role(con, actor_id)
        if not can_create_admins(actor_role):
            raise HTTPException(403, "SUPER_ADMIN_ONLY")

    with db() as con:
        try:
            # If service is disabled, also disable both features.
            service_enabled = bool(req.service_enabled) if req.service_enabled is not None else True
            fg = bool(req.feature_group_reading_enabled) if req.feature_group_reading_enabled is not None else True
            fa = bool(req.feature_auto_dialogs_enabled) if req.feature_auto_dialogs_enabled is not None else True
            comment = (req.disabled_comment or "").strip() or None
            if not service_enabled:
                fg = False
                fa = False
            user_id = create_local_user(
                con,
                login=req.login,
                password_hash=password_hash,
                role=desired_role,
                is_active=bool(req.is_active),
                service_enabled=service_enabled,
                feature_group_reading_enabled=fg,
                feature_auto_dialogs_enabled=fa,
                disabled_comment=comment,
            )
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: local_users.login" in str(e):
                raise HTTPException(409, "LOGIN_EXISTS")
            raise HTTPException(400, "CREATE_FAILED")
        except Exception as e:
            logger.exception("admin user create failed")
            raise HTTPException(400, "CREATE_FAILED")
    return {"id": user_id}


@app.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: int, request: Request, confirm: bool = Query(False)):
    actor_id = require_admin(request)
    if not confirm:
        raise HTTPException(400, "CONFIRM_REQUIRED")
    with db() as con:
        owner = con.execute("SELECT id FROM local_users WHERE id=?", (user_id,)).fetchone()
        if not owner:
            raise HTTPException(404, "USER_NOT_FOUND")
        actor_role = get_user_role(con, actor_id)
        target_role = get_user_role(con, user_id)
        if not can_delete_target(actor_role, target_role):
            raise HTTPException(403, "FORBIDDEN")
        account_rows = con.execute(
            "SELECT id FROM accounts WHERE local_user_id=?",
            (user_id,),
        ).fetchall()
        for acc in account_rows:
            account_id = acc["id"]
            con.execute("DELETE FROM tg_sessions WHERE account_id=?", (account_id,))
            con.execute("DELETE FROM auth_flows WHERE account_id=?", (account_id,))
            con.execute("DELETE FROM events WHERE account_id=?", (account_id,))
            con.execute("DELETE FROM jobs WHERE account_id=?", (account_id,))
            con.execute("DELETE FROM group_listeners WHERE account_id=?", (account_id,))
            con.execute("DELETE FROM group_matches WHERE account_id=?", (account_id,))
            con.execute("DELETE FROM group_catalog WHERE account_id=?", (account_id,))
            con.execute("DELETE FROM group_worker_runs WHERE account_id=?", (account_id,))
            con.execute(
                "DELETE FROM auto_chat_messages WHERE dialog_id IN (SELECT id FROM auto_chat_dialogs WHERE account_id=?)",
                (account_id,),
            )
            con.execute("DELETE FROM auto_chat_dialogs WHERE account_id=?", (account_id,))
            con.execute("DELETE FROM accounts WHERE id=?", (account_id,))
        con.execute("DELETE FROM local_sessions WHERE user_id=?", (user_id,))
        con.execute("DELETE FROM local_user_settings WHERE user_id=?", (user_id,))
        con.execute("DELETE FROM local_user_auto_chat_usernames WHERE user_id=?", (user_id,))
        con.execute("DELETE FROM local_user_auto_chat_settings WHERE user_id=?", (user_id,))
        con.execute("DELETE FROM local_users WHERE id=?", (user_id,))
    return {"ok": True}


@app.patch("/admin/users/{user_id}")
def admin_update_user(user_id: int, req: AdminUserUpdateReq, request: Request):
    actor_id = require_admin(request)
    with db() as con:
        actor_role = get_user_role(con, actor_id)
        target = con.execute(
            """
            SELECT id, is_admin, role
            FROM local_users
            WHERE id=?
            """,
            (user_id,),
        ).fetchone()
        if not target:
            raise HTTPException(404, "USER_NOT_FOUND")
        target_role = get_user_role(con, user_id)
        if not can_delete_target(actor_role, target_role):
            raise HTTPException(403, "FORBIDDEN")

        fields = []
        values: list[object] = []

        if req.is_active is not None:
            fields.append("is_active=?")
            values.append(1 if bool(req.is_active) else 0)

        if req.role is not None:
            desired = req.role.strip().lower()
            if desired not in ("user", "admin"):
                raise HTTPException(400, "INVALID_ROLE")
            desired_role = ROLE_ADMIN if desired == "admin" else ROLE_USER
            if desired_role == ROLE_ADMIN and not can_create_admins(actor_role):
                raise HTTPException(403, "SUPER_ADMIN_ONLY")
            # never allow setting superadmin via this endpoint
            fields.append("role=?")
            values.append(int(desired_role))
            fields.append("is_admin=?")
            values.append(1 if int(desired_role) >= ROLE_ADMIN else 0)

        # Capabilities
        service_enabled = None
        if req.service_enabled is not None:
            service_enabled = bool(req.service_enabled)
            fields.append("service_enabled=?")
            values.append(1 if service_enabled else 0)

        if req.feature_group_reading_enabled is not None:
            fields.append("feature_group_reading_enabled=?")
            values.append(1 if bool(req.feature_group_reading_enabled) else 0)

        if req.feature_auto_dialogs_enabled is not None:
            fields.append("feature_auto_dialogs_enabled=?")
            values.append(1 if bool(req.feature_auto_dialogs_enabled) else 0)

        if req.disabled_comment is not None:
            fields.append("disabled_comment=?")
            values.append((req.disabled_comment or "").strip() or None)

        if not fields:
            return {"ok": True}

        fields.append("updated_at=?")
        values.append(now_iso())
        values.append(user_id)

        # Apply update.
        con.execute(
            f"UPDATE local_users SET {', '.join(fields)} WHERE id=?",
            values,
        )

        # Stop feature activity if the user lost access to it (service disabled or feature disabled).
        caps_row = con.execute(
            """
            SELECT service_enabled, feature_group_reading_enabled, feature_auto_dialogs_enabled
            FROM local_users
            WHERE id=?
            """,
            (user_id,),
        ).fetchone()
        caps = dict(caps_row) if caps_row else {}
        svc_on = _int01(caps.get("service_enabled", 1), default=1) == 1
        gr_on = _int01(caps.get("feature_group_reading_enabled", 1), default=1) == 1
        au_on = _int01(caps.get("feature_auto_dialogs_enabled", 1), default=1) == 1

        if not svc_on or not gr_on or not au_on:
            acc_rows = con.execute("SELECT id FROM accounts WHERE local_user_id=?", (user_id,)).fetchall()
            account_ids = [int(r["id"]) for r in acc_rows]
            if account_ids:
                ph = ",".join("?" for _ in account_ids)
                if not svc_on or not gr_on:
                    con.execute(
                        f"UPDATE group_listeners SET is_listening=0, updated_at=? WHERE account_id IN ({ph})",
                        (now_iso(), *account_ids),
                    )
                if not svc_on or not au_on:
                    con.execute(
                        f"""
                        UPDATE auto_chat_dialogs
                        SET status=?, last_error=?, pending_incoming=0, updated_at=?, stopped_at=COALESCE(stopped_at, ?)
                        WHERE account_id IN ({ph}) AND status IN (?, ?, ?)
                        """,
                        (
                            AUTO_CHAT_STATUS_STOPPED,
                            "FEATURE_DISABLED" if svc_on else "SERVICE_DISABLED",
                            now_iso(),
                            now_iso(),
                            *account_ids,
                            AUTO_CHAT_STATUS_STARTING,
                            AUTO_CHAT_STATUS_WAIT_REPLY,
                            AUTO_CHAT_STATUS_ACTIVE,
                        ),
                    )

    return {"ok": True}


@app.get("/admin/accounts")
def admin_list_accounts(request: Request):
    require_admin(request)
    with db() as con:
        rows = con.execute(
            """
            SELECT a.id, a.display_name, a.phone, a.user_id, a.username, a.tags,
                   a.created_at, a.updated_at, a.is_active, a.local_user_id,
                   u.login AS local_login
            FROM accounts a
            LEFT JOIN local_users u ON u.id = a.local_user_id
            ORDER BY a.id DESC
            """,
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@app.delete("/admin/accounts/{account_id}")
def admin_delete_account(account_id: int, request: Request, confirm: bool = Query(False)):
    require_admin(request)
    if not confirm:
        raise HTTPException(400, "CONFIRM_REQUIRED")
    with db() as con:
        row = con.execute("SELECT id FROM accounts WHERE id=?", (account_id,)).fetchone()
        if not row:
            raise HTTPException(404, "ACCOUNT_NOT_FOUND")
        con.execute("DELETE FROM tg_sessions WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM auth_flows WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM events WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM jobs WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM group_listeners WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM group_matches WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM group_catalog WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM group_worker_runs WHERE account_id=?", (account_id,))
        con.execute(
            "DELETE FROM auto_chat_messages WHERE dialog_id IN (SELECT id FROM auto_chat_dialogs WHERE account_id=?)",
            (account_id,),
        )
        con.execute("DELETE FROM auto_chat_dialogs WHERE account_id=?", (account_id,))
        con.execute("DELETE FROM accounts WHERE id=?", (account_id,))
    return {"ok": True}


@app.get("/admin/group_workers")
def admin_group_workers(request: Request, account_id: Optional[int] = None, limit: int = Query(200, ge=1, le=1000)):
    require_admin(request)
    require_feature(request, FEATURE_GROUP_READING)
    with db() as con:
        if account_id:
            rows = con.execute(
                """
                SELECT id, account_id, status, started_at, stopped_at, last_error
                FROM group_worker_runs
                WHERE account_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (account_id, limit),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT id, account_id, status, started_at, stopped_at, last_error
                FROM group_worker_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return {"items": [dict(r) for r in rows]}


@app.get("/admin/errors")
def admin_errors(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    require_super_admin(request)
    with db() as con:
        total = con.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM (
                SELECT e.id
                FROM events e
                WHERE UPPER(COALESCE(e.level, ''))='ERROR'
                UNION ALL
                SELECT j.id
                FROM jobs j
                WHERE j.status='FAILED' OR COALESCE(j.last_error, '')<>''
                UNION ALL
                SELECT gwr.id
                FROM group_worker_runs gwr
                WHERE COALESCE(gwr.last_error, '')<>''
                UNION ALL
                SELECT d.id
                FROM auto_chat_dialogs d
                WHERE d.status='ERROR' OR COALESCE(d.last_error, '')<>''
                UNION ALL
                SELECT af.auth_id
                FROM auth_flows af
                WHERE af.status='ERROR' OR COALESCE(af.error_message, '')<>''
                UNION ALL
                SELECT st.id
                FROM support_tickets st
                WHERE st.route='ESCALATED' OR st.status='ESCALATED'
            ) t
            """
        ).fetchone()["cnt"]

        rows = con.execute(
            """
            SELECT
                x.*,
                COALESCE(ir.is_resolved, 0) AS is_resolved,
                ir.resolved_at AS incident_resolved_at
            FROM (
                SELECT
                    e.id AS source_id,
                    e.created_at AS created_at,
                    'events' AS source,
                    e.account_id AS account_id,
                    a.local_user_id AS local_user_id,
                    u.login AS local_login,
                    UPPER(COALESCE(e.level, 'ERROR')) AS level,
                    e.message AS message,
                    NULL AS context,
                    NULL AS ticket_status
                FROM events e
                LEFT JOIN accounts a ON a.id = e.account_id
                LEFT JOIN local_users u ON u.id = a.local_user_id
                WHERE UPPER(COALESCE(e.level, ''))='ERROR'

                UNION ALL

                SELECT
                    j.id AS source_id,
                    j.updated_at AS created_at,
                    'jobs' AS source,
                    j.account_id AS account_id,
                    a.local_user_id AS local_user_id,
                    u.login AS local_login,
                    CASE WHEN j.status='FAILED' THEN 'ERROR' ELSE 'WARN' END AS level,
                    COALESCE(j.last_error, 'JOB_FAILED') AS message,
                    ('type=' || COALESCE(j.type, '') || '; status=' || COALESCE(j.status, '')) AS context,
                    NULL AS ticket_status
                FROM jobs j
                LEFT JOIN accounts a ON a.id = j.account_id
                LEFT JOIN local_users u ON u.id = a.local_user_id
                WHERE j.status='FAILED' OR COALESCE(j.last_error, '')<>''

                UNION ALL

                SELECT
                    gwr.id AS source_id,
                    COALESCE(gwr.stopped_at, gwr.started_at) AS created_at,
                    'group_worker_runs' AS source,
                    gwr.account_id AS account_id,
                    a.local_user_id AS local_user_id,
                    u.login AS local_login,
                    'ERROR' AS level,
                    gwr.last_error AS message,
                    ('status=' || COALESCE(gwr.status, '')) AS context,
                    NULL AS ticket_status
                FROM group_worker_runs gwr
                LEFT JOIN accounts a ON a.id = gwr.account_id
                LEFT JOIN local_users u ON u.id = a.local_user_id
                WHERE COALESCE(gwr.last_error, '')<>''

                UNION ALL

                SELECT
                    d.id AS source_id,
                    d.updated_at AS created_at,
                    'auto_chat_dialogs' AS source,
                    d.account_id AS account_id,
                    a.local_user_id AS local_user_id,
                    u.login AS local_login,
                    CASE WHEN d.status='ERROR' THEN 'ERROR' ELSE 'WARN' END AS level,
                    COALESCE(d.last_error, 'AUTO_CHAT_ERROR') AS message,
                    (
                        'status=' || COALESCE(d.status, '')
                        || '; peer=' || COALESCE(d.peer_username, CAST(d.peer_tg_user_id AS TEXT), '')
                    ) AS context,
                    NULL AS ticket_status
                FROM auto_chat_dialogs d
                LEFT JOIN accounts a ON a.id = d.account_id
                LEFT JOIN local_users u ON u.id = a.local_user_id
                WHERE d.status='ERROR' OR COALESCE(d.last_error, '')<>''

                UNION ALL

                SELECT
                    af.auth_id AS source_id,
                    af.expires_at AS created_at,
                    'auth_flows' AS source,
                    af.account_id AS account_id,
                    af.local_user_id AS local_user_id,
                    u.login AS local_login,
                    CASE WHEN af.status='ERROR' THEN 'ERROR' ELSE 'WARN' END AS level,
                    COALESCE(af.error_message, af.status, 'AUTH_FLOW_ERROR') AS message,
                    (
                        'auth_id=' || COALESCE(af.auth_id, '')
                        || '; method=' || COALESCE(af.method, '')
                        || '; status=' || COALESCE(af.status, '')
                    ) AS context,
                    NULL AS ticket_status
                FROM auth_flows af
                LEFT JOIN local_users u ON u.id = af.local_user_id
                WHERE af.status='ERROR' OR COALESCE(af.error_message, '')<>''

                UNION ALL

                SELECT
                    st.id AS source_id,
                    st.updated_at AS created_at,
                    'support_tickets' AS source,
                    NULL AS account_id,
                    st.user_id AS local_user_id,
                    u.login AS local_login,
                    'WARN' AS level,
                    ('SUPPORT: ' || COALESCE(st.subject, '')) AS message,
                    ('status=' || COALESCE(st.status, '') || '; route=' || COALESCE(st.route, '')) AS context,
                    st.status AS ticket_status
                FROM support_tickets st
                LEFT JOIN local_users u ON u.id = st.user_id
                WHERE st.route='ESCALATED' OR st.status='ESCALATED'
            ) x
            LEFT JOIN incident_resolution ir
              ON ir.source = x.source AND ir.source_id = CAST(x.source_id AS TEXT)
            ORDER BY x.created_at DESC, x.source_id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        is_resolved = int(d.get("is_resolved") or 0)
        if str(d.get("source") or "") == "support_tickets" and str(d.get("ticket_status") or "") == SUPPORT_STATUS_RESOLVED:
            is_resolved = 1
        d["is_resolved"] = bool(is_resolved)
        d.pop("ticket_status", None)
        items.append(d)
    return {
        "items": items,
        "total": int(total or 0),
        "limit": int(limit),
        "offset": int(offset),
    }


@app.post("/admin/errors/{source}/{source_id}/resolve")
def admin_resolve_error(source: str, source_id: str, request: Request):
    admin_user_id = require_super_admin(request)
    src = str(source or "").strip().lower()
    sid = str(source_id or "").strip()
    if src not in INCIDENT_SOURCES or not sid:
        raise HTTPException(400, "INVALID_INCIDENT_SOURCE")

    now = now_iso()
    with db() as con:
        exists = False
        if src == "events":
            exists = con.execute(
                "SELECT 1 FROM events WHERE id=? AND UPPER(COALESCE(level,''))='ERROR'",
                (sid,),
            ).fetchone() is not None
        elif src == "jobs":
            exists = con.execute(
                "SELECT 1 FROM jobs WHERE id=? AND (status='FAILED' OR COALESCE(last_error,'')<>'')",
                (sid,),
            ).fetchone() is not None
        elif src == "group_worker_runs":
            exists = con.execute(
                "SELECT 1 FROM group_worker_runs WHERE id=? AND COALESCE(last_error,'')<>''",
                (sid,),
            ).fetchone() is not None
        elif src == "auto_chat_dialogs":
            exists = con.execute(
                "SELECT 1 FROM auto_chat_dialogs WHERE id=? AND (status='ERROR' OR COALESCE(last_error,'')<>'')",
                (sid,),
            ).fetchone() is not None
        elif src == "auth_flows":
            exists = con.execute(
                "SELECT 1 FROM auth_flows WHERE auth_id=? AND (status='ERROR' OR COALESCE(error_message,'')<>'')",
                (sid,),
            ).fetchone() is not None
        elif src == "support_tickets":
            try:
                ticket_id = int(sid)
            except Exception:
                raise HTTPException(400, "INVALID_INCIDENT_SOURCE")
            row = _support_ticket_row_admin(con, ticket_id)
            exists = row is not None
            if row and str(row["status"] or "") != SUPPORT_STATUS_RESOLVED:
                con.execute(
                    """
                    UPDATE support_tickets
                    SET status=?, resolved_at=?, updated_at=?
                    WHERE id=?
                    """,
                    (SUPPORT_STATUS_RESOLVED, now, now, ticket_id),
                )
                _support_add_message(
                    con,
                    ticket_id=ticket_id,
                    sender_type="SYSTEM",
                    message="Супер-администратор пометил обращение как решенное.",
                    meta={"event": "RESOLVED_BY_SUPERADMIN", "resolved_by_user_id": admin_user_id},
                )
        if not exists:
            raise HTTPException(404, "INCIDENT_NOT_FOUND")

        con.execute(
            """
            INSERT INTO incident_resolution(source, source_id, is_resolved, resolved_at, resolved_by_user_id, updated_at)
            VALUES (?, ?, 1, ?, ?, ?)
            ON CONFLICT(source, source_id) DO UPDATE SET
                is_resolved=1,
                resolved_at=excluded.resolved_at,
                resolved_by_user_id=excluded.resolved_by_user_id,
                updated_at=excluded.updated_at
            """,
            (src, sid, now, admin_user_id, now),
        )
    return {"ok": True, "source": src, "source_id": sid, "is_resolved": True}


@app.post("/admin/errors/resolve_all")
def admin_resolve_all_errors(request: Request):
    admin_user_id = require_super_admin(request)
    now = now_iso()
    with db() as con:
        rows = con.execute(
            """
            SELECT source, source_id
            FROM (
                SELECT 'events' AS source, CAST(e.id AS TEXT) AS source_id
                FROM events e
                WHERE UPPER(COALESCE(e.level, ''))='ERROR'

                UNION

                SELECT 'jobs' AS source, CAST(j.id AS TEXT) AS source_id
                FROM jobs j
                WHERE j.status='FAILED' OR COALESCE(j.last_error, '')<>''

                UNION

                SELECT 'group_worker_runs' AS source, CAST(gwr.id AS TEXT) AS source_id
                FROM group_worker_runs gwr
                WHERE COALESCE(gwr.last_error, '')<>''

                UNION

                SELECT 'auto_chat_dialogs' AS source, CAST(d.id AS TEXT) AS source_id
                FROM auto_chat_dialogs d
                WHERE d.status='ERROR' OR COALESCE(d.last_error, '')<>''

                UNION

                SELECT 'auth_flows' AS source, COALESCE(af.auth_id, '') AS source_id
                FROM auth_flows af
                WHERE af.status='ERROR' OR COALESCE(af.error_message, '')<>''

                UNION

                SELECT 'support_tickets' AS source, CAST(st.id AS TEXT) AS source_id
                FROM support_tickets st
                WHERE st.route='ESCALATED' OR st.status='ESCALATED'
            ) x
            LEFT JOIN incident_resolution ir
              ON ir.source = x.source AND ir.source_id = x.source_id
            WHERE COALESCE(x.source_id, '')<>''
              AND COALESCE(ir.is_resolved, 0)=0
            """
        ).fetchall()

        resolved = 0
        for row in rows:
            src = str(row["source"] or "").strip().lower()
            sid = str(row["source_id"] or "").strip()
            if src not in INCIDENT_SOURCES or not sid:
                continue

            exists = False
            if src == "events":
                exists = con.execute(
                    "SELECT 1 FROM events WHERE id=? AND UPPER(COALESCE(level,''))='ERROR'",
                    (sid,),
                ).fetchone() is not None
            elif src == "jobs":
                exists = con.execute(
                    "SELECT 1 FROM jobs WHERE id=? AND (status='FAILED' OR COALESCE(last_error,'')<>'')",
                    (sid,),
                ).fetchone() is not None
            elif src == "group_worker_runs":
                exists = con.execute(
                    "SELECT 1 FROM group_worker_runs WHERE id=? AND COALESCE(last_error,'')<>''",
                    (sid,),
                ).fetchone() is not None
            elif src == "auto_chat_dialogs":
                exists = con.execute(
                    "SELECT 1 FROM auto_chat_dialogs WHERE id=? AND (status='ERROR' OR COALESCE(last_error,'')<>'')",
                    (sid,),
                ).fetchone() is not None
            elif src == "auth_flows":
                exists = con.execute(
                    "SELECT 1 FROM auth_flows WHERE auth_id=? AND (status='ERROR' OR COALESCE(error_message,'')<>'')",
                    (sid,),
                ).fetchone() is not None
            elif src == "support_tickets":
                try:
                    ticket_id = int(sid)
                except Exception:
                    continue
                row_ticket = _support_ticket_row_admin(con, ticket_id)
                exists = row_ticket is not None
                if row_ticket and str(row_ticket["status"] or "") != SUPPORT_STATUS_RESOLVED:
                    con.execute(
                        """
                        UPDATE support_tickets
                        SET status=?, resolved_at=?, updated_at=?
                        WHERE id=?
                        """,
                        (SUPPORT_STATUS_RESOLVED, now, now, ticket_id),
                    )
                    _support_add_message(
                        con,
                        ticket_id=ticket_id,
                        sender_type="SYSTEM",
                        message="РЎСѓРїРµСЂ-Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ РїРѕРјРµС‚РёР» РѕР±СЂР°С‰РµРЅРёРµ РєР°Рє СЂРµС€РµРЅРЅРѕРµ.",
                        meta={"event": "RESOLVED_BY_SUPERADMIN", "resolved_by_user_id": admin_user_id},
                    )
            if not exists:
                continue

            con.execute(
                """
                INSERT INTO incident_resolution(source, source_id, is_resolved, resolved_at, resolved_by_user_id, updated_at)
                VALUES (?, ?, 1, ?, ?, ?)
                ON CONFLICT(source, source_id) DO UPDATE SET
                    is_resolved=1,
                    resolved_at=excluded.resolved_at,
                    resolved_by_user_id=excluded.resolved_by_user_id,
                    updated_at=excluded.updated_at
                """,
                (src, sid, now, admin_user_id, now),
            )
            resolved += 1
    return {"ok": True, "resolved": resolved}


@app.get("/admin/group_matches")
def admin_group_matches(
    request: Request,
    account_id: Optional[int] = None,
    chat_id: Optional[int] = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    require_admin(request)
    require_feature(request, FEATURE_GROUP_READING)
    params = []
    filters = []
    if account_id is not None:
        filters.append("account_id=?")
        params.append(account_id)
    if chat_id is not None:
        filters.append("chat_id=?")
        params.append(chat_id)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    with db() as con:
        rows = con.execute(
            f"""
            SELECT id, account_id, chat_id, message_id, message_text, sender_phone, matched_keywords, created_at
            FROM group_matches
            {where}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@app.delete("/admin/group_matches/{match_id}")
def admin_delete_group_match(match_id: int, request: Request):
    require_super_admin(request)
    with db() as con:
        row = con.execute("SELECT id FROM group_matches WHERE id=?", (match_id,)).fetchone()
        if not row:
            raise HTTPException(404, "MATCH_NOT_FOUND")
        con.execute("DELETE FROM group_matches WHERE id=?", (match_id,))
    return {"ok": True}


@app.get("/admin/auto_chat/dialogs")
def admin_list_auto_chat_dialogs(
    request: Request,
    account_id: Optional[int] = None,
):
    require_admin(request)
    require_feature(request, FEATURE_AUTO_DIALOGS)
    with db() as con:
        if account_id is not None:
            rows = con.execute(
                """
                SELECT id, account_id, peer_tg_user_id, peer_username, peer_display_name,
                       status, last_error, pending_incoming, last_ai_request_at, last_ai_latency_ms,
                       created_at, updated_at, started_at, stopped_at
                FROM auto_chat_dialogs
                WHERE account_id=?
                ORDER BY updated_at DESC, id DESC
                """,
                (account_id,),
            ).fetchall()
            active_count = con.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM auto_chat_dialogs
                WHERE account_id=? AND status IN ({",".join(["?"]*len(AUTO_CHAT_ACTIVE_STATUSES))})
                """,
                (account_id, *AUTO_CHAT_ACTIVE_STATUSES),
            ).fetchone()["cnt"]
        else:
            rows = con.execute(
                """
                SELECT id, account_id, peer_tg_user_id, peer_username, peer_display_name,
                       status, last_error, pending_incoming, last_ai_request_at, last_ai_latency_ms,
                       created_at, updated_at, started_at, stopped_at
                FROM auto_chat_dialogs
                ORDER BY updated_at DESC, id DESC
                """,
            ).fetchall()
            active_count = con.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM auto_chat_dialogs
                WHERE status IN ({",".join(["?"]*len(AUTO_CHAT_ACTIVE_STATUSES))})
                """,
                (*AUTO_CHAT_ACTIVE_STATUSES,),
            ).fetchone()["cnt"]
    return {
        "account_id": account_id,
        "limit": AUTO_CHAT_MAX_ACTIVE_PER_ACCOUNT,
        "active_count": int(active_count or 0),
        "items": [dict(r) for r in rows],
    }


@app.get("/admin/auto_chat/dialogs/{dialog_id}/messages")
def admin_list_auto_chat_messages(
    dialog_id: int,
    request: Request,
    limit: int = Query(200, ge=1, le=2000),
    since: Optional[str] = Query(None),
    after_id: Optional[int] = Query(None, ge=0),
):
    require_admin(request)
    require_feature(request, FEATURE_AUTO_DIALOGS)
    with db() as con:
        where = ["dialog_id=?"]
        params: list[object] = [dialog_id]
        if since:
            where.append("created_at>=?")
            params.append(since)
        if after_id is not None:
            where.append("id>?")
            params.append(int(after_id))

        if after_id is not None:
            rows = con.execute(
                f"""
                SELECT id, direction, text, tg_message_id, created_at
                FROM auto_chat_messages
                WHERE {' AND '.join(where)}
                ORDER BY id ASC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        else:
            rows = con.execute(
                f"""
                SELECT id, direction, text, tg_message_id, created_at
                FROM auto_chat_messages
                WHERE {' AND '.join(where)}
                ORDER BY id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
    items = [dict(r) for r in rows]
    if after_id is None:
        items.reverse()
    return {"dialog_id": dialog_id, "items": items}


@app.delete("/admin/auto_chat/dialogs/{dialog_id}")
def admin_delete_auto_chat_dialog(dialog_id: int, request: Request):
    require_super_admin(request)
    with db() as con:
        row = con.execute("SELECT id FROM auto_chat_dialogs WHERE id=?", (dialog_id,)).fetchone()
        if not row:
            raise HTTPException(404, "DIALOG_NOT_FOUND")
        con.execute("DELETE FROM auto_chat_messages WHERE dialog_id=?", (dialog_id,))
        con.execute("DELETE FROM auto_chat_dialogs WHERE id=?", (dialog_id,))
    return {"ok": True}


@app.get("/requisites")
def list_requisites(
    request: Request,
    requisite_type: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    user_id = require_auth(request)
    account_id, _ = _get_active_account_session(user_id)
    if not account_id:
        return {"items": []}
    params = [account_id]
    filters = ["account_id=?"]
    if requisite_type:
        filters.append("requisite_type=?")
        params.append(requisite_type)
    if country:
        filters.append("country=?")
        params.append(country)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    with db() as con:
        rows = con.execute(
            f"""
            SELECT id, account_id, chat_id, dialog_id, message_id, message_text,
                   sender_phone, sender_username, requisite_type, country, value, created_at
            FROM requisites
            {where}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@app.get("/admin/requisites")
def admin_list_requisites(
    request: Request,
    account_id: Optional[int] = None,
    requisite_type: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    require_admin(request)
    params = []
    filters = []
    if account_id is not None:
        filters.append("account_id=?")
        params.append(account_id)
    if requisite_type:
        filters.append("requisite_type=?")
        params.append(requisite_type)
    if country:
        filters.append("country=?")
        params.append(country)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    with db() as con:
        rows = con.execute(
            f"""
            SELECT id, account_id, chat_id, dialog_id, message_id, message_text,
                   sender_phone, sender_username, requisite_type, country, value, created_at
            FROM requisites
            {where}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@app.delete("/admin/requisites/{requisite_id}")
def admin_delete_requisite(requisite_id: int, request: Request):
    require_super_admin(request)
    with db() as con:
        row = con.execute("SELECT id FROM requisites WHERE id=?", (requisite_id,)).fetchone()
        if not row:
            raise HTTPException(404, "REQUISITE_NOT_FOUND")
        con.execute("DELETE FROM requisites WHERE id=?", (requisite_id,))
    return {"ok": True}


def _get_active_account_session(local_user_id: int):
    with db() as con:
        row = con.execute(
            """
            SELECT s.account_id, s.session_string
            FROM tg_sessions s
            JOIN accounts a ON a.id = s.account_id
            WHERE s.revoked_at IS NULL
              AND a.local_user_id=?
              AND a.is_active=1
            ORDER BY s.updated_at DESC
            LIMIT 1
            """,
            (local_user_id,),
        ).fetchone()
    if not row:
        return None, None
    return row["account_id"], decrypt_text(row["session_string"])


def _delete_account_related_data(con: sqlite3.Connection, account_id: int) -> None:
    con.execute("DELETE FROM tg_sessions WHERE account_id=?", (account_id,))
    con.execute("DELETE FROM auth_flows WHERE account_id=?", (account_id,))
    con.execute("DELETE FROM events WHERE account_id=?", (account_id,))
    con.execute("DELETE FROM jobs WHERE account_id=?", (account_id,))
    con.execute("DELETE FROM group_listeners WHERE account_id=?", (account_id,))
    con.execute("DELETE FROM group_matches WHERE account_id=?", (account_id,))
    con.execute("DELETE FROM group_catalog WHERE account_id=?", (account_id,))
    con.execute("DELETE FROM group_worker_runs WHERE account_id=?", (account_id,))
    con.execute(
        "DELETE FROM auto_chat_messages WHERE dialog_id IN (SELECT id FROM auto_chat_dialogs WHERE account_id=?)",
        (account_id,),
    )
    con.execute("DELETE FROM auto_chat_dialogs WHERE account_id=?", (account_id,))
    con.execute("DELETE FROM accounts WHERE id=?", (account_id,))


def _unlink_expired_telegram_account(local_user_id: int, account_id: int) -> bool:
    with db() as con:
        row = con.execute(
            "SELECT id FROM accounts WHERE id=? AND local_user_id=?",
            (account_id, local_user_id),
        ).fetchone()
        if not row:
            return False
        _delete_account_related_data(con, account_id)
        return True


def _handle_tg_session_expired(local_user_id: int, account_id: int) -> None:
    logger.warning(
        "Telegram session expired: local_user_id=%s account_id=%s",
        local_user_id,
        account_id,
    )
    try:
        _unlink_expired_telegram_account(local_user_id, account_id)
    except Exception:
        logger.exception(
            "Failed to cleanup expired Telegram account: local_user_id=%s account_id=%s",
            local_user_id,
            account_id,
        )
    raise HTTPException(401, "TG_SESSION_EXPIRED")


def _get_cached_groups(account_id: int, max_age_sec: int):
    with db() as con:
        row = con.execute(
            "SELECT MAX(updated_at) AS last_update FROM group_catalog WHERE account_id=?",
            (account_id,),
        ).fetchone()
        if not row or not row["last_update"]:
            return None
        last_update = parse_iso_local(row["last_update"])
        if not last_update:
            return None
        if almaty_now_naive() - last_update > timedelta(seconds=max_age_sec):
            return None
        rows = con.execute(
            """
            SELECT chat_id, title
            FROM group_catalog
            WHERE account_id=?
            ORDER BY title
            """,
            (account_id,),
        ).fetchall()
    return [
        {"id": r["chat_id"], "title": r["title"] or "", "type": "group"}
        for r in rows
    ]


def _upsert_group_catalog(account_id: int, items: list[dict]) -> None:
    now = now_iso()
    with db() as con:
        for item in items:
            con.execute(
                """
                INSERT INTO group_catalog(account_id, chat_id, title, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(account_id, chat_id) DO UPDATE SET
                    title=excluded.title,
                    updated_at=excluded.updated_at
                """,
                (account_id, item["id"], item.get("title"), now),
            )
