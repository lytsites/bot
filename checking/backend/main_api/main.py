from datetime import datetime, timedelta
import asyncio
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from common.auth import create_session, hash_password, revoke_token, verify_token
from common.config import FRONTEND_ORIGINS, TG_API_HASH, TG_API_ID
from common.crypto import decrypt_text
from common.db import db, init_db
from common.logging_setup import get_logger, request_id_middleware, setup_logging
from telethon import TelegramClient
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


def now_iso() -> str:
    return datetime.utcnow().isoformat()


@app.get("/health")
def health(request: Request):
    require_auth(request)
    logger.info("health")
    return {"ok": True}


class LoginReq(BaseModel):
    login: str
    password: str


@app.post("/local/login")
def local_login(req: LoginReq):
    password_hash = hash_password(req.password)
    with db() as con:
        row = con.execute(
            """
            SELECT id, is_active, is_admin FROM local_users
            WHERE login=? AND password_hash=?
            """,
            (req.login, password_hash),
        ).fetchone()
    if not row or row["is_active"] != 1:
        raise HTTPException(401, "BAD_CREDENTIALS")
    session = create_session(row["id"])
    return {
        "token": session["token"],
        "expires_at": session["expires_at"],
        "is_admin": bool(row["is_admin"]),
    }


@app.post("/local/logout")
def local_logout(request: Request):
    user_id = require_auth(request)
    token = request.headers.get("X-Auth-Token")
    revoke_token(token)
    return {"ok": True, "user_id": user_id}


@app.get("/local/me")
def local_me(request: Request):
    user_id = require_auth(request)
    with db() as con:
        row = con.execute(
            "SELECT id, login, is_admin, is_active, created_at FROM local_users WHERE id=?",
            (user_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "USER_NOT_FOUND")
    return dict(row)


class SettingsReq(BaseModel):
    keywords: Optional[str] = None
    is_active: Optional[bool] = None


@app.get("/local/settings")
def get_settings(request: Request):
    user_id = require_auth(request)
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
    user_id = require_auth(request)
    fields = []
    values = []
    if req.keywords is not None:
        fields.append("keywords=?")
        values.append(req.keywords)
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
        except Exception as e:
            raise HTTPException(400, f"CREATE_FAILED: {type(e).__name__}: {e}")
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
        items = asyncio.run(_run())
    except RuntimeError:
        loop = asyncio.get_event_loop()
        items = loop.run_until_complete(_run())

    return {"account_id": account_id, "items": items}


@app.get("/groups")
def list_groups(request: Request):
    user_id = require_auth(request)
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
            items = asyncio.run(_run())
        except RuntimeError:
            loop = asyncio.get_event_loop()
            items = loop.run_until_complete(_run())
        _upsert_group_catalog(account_id, items)
    else:
        items = cached_items

    with db() as con:
        rows = con.execute(
            """
            SELECT gl.chat_id, gl.is_listening, gl.title, COUNT(DISTINCT gm.message_id) AS match_count
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
    user_id = require_auth(request)
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
    user_id = require_auth(request)
    account_id, _ = _get_active_account_session(user_id)
    if not account_id:
        return {"items": []}
    with db() as con:
        rows = con.execute(
            """
            SELECT message_id, message_text, sender_phone, MAX(created_at) AS created_at
            FROM group_matches
            WHERE account_id=? AND chat_id=?
            GROUP BY message_id, message_text, sender_phone
            ORDER BY MAX(id) DESC
            LIMIT ?
            """,
            (account_id, chat_id, limit),
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.get("/groups/{chat_id}/matches/count")
def count_group_matches(chat_id: int, request: Request):
    user_id = require_auth(request)
    account_id, _ = _get_active_account_session(user_id)
    if not account_id:
        return {"count": 0}
    with db() as con:
        row = con.execute(
            """
            SELECT COUNT(DISTINCT message_id) AS cnt
            FROM group_matches
            WHERE account_id=? AND chat_id=?
            """,
            (account_id, chat_id),
        ).fetchone()
    return {"count": row["cnt"]}


@app.post("/groups/{chat_id}/matches")
def add_group_matches(chat_id: int, req: GroupMatchesReq, request: Request):
    user_id = require_auth(request)
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
def require_auth(request: Request) -> int:
    token = request.headers.get("X-Auth-Token")
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(401, "UNAUTHORIZED")
    return user_id


def require_admin(request: Request) -> int:
    user_id = require_auth(request)
    with db() as con:
        row = con.execute(
            "SELECT is_admin FROM local_users WHERE id=?",
            (user_id,),
        ).fetchone()
    if not row or row["is_admin"] != 1:
        raise HTTPException(403, "ADMIN_ONLY")
    return user_id


class AdminUserCreateReq(BaseModel):
    login: str
    password: str
    is_admin: Optional[bool] = False
    is_active: Optional[bool] = True


@app.get("/admin/users")
def admin_list_users(request: Request):
    require_admin(request)
    with db() as con:
        rows = con.execute(
            """
            SELECT id, login, is_admin, is_active, created_at, updated_at
            FROM local_users
            ORDER BY id DESC
            """,
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@app.post("/admin/users")
def admin_create_user(req: AdminUserCreateReq, request: Request):
    require_admin(request)
    if not req.login or not req.password:
        raise HTTPException(400, "MISSING_FIELDS")
    password_hash = hash_password(req.password)
    with db() as con:
        try:
            con.execute(
                """
                INSERT INTO local_users(login, password_hash, is_active, is_admin, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    req.login,
                    password_hash,
                    1 if req.is_active else 0,
                    1 if req.is_admin else 0,
                    now_iso(),
                    now_iso(),
                ),
            )
        except Exception as e:
            raise HTTPException(400, f"CREATE_FAILED: {type(e).__name__}: {e}")
        user_row = con.execute("SELECT last_insert_rowid() AS id").fetchone()
        con.execute(
            """
            INSERT OR IGNORE INTO local_user_settings(user_id, keywords, is_active, created_at, updated_at)
            VALUES (?, '', 1, ?, ?)
            """,
            (user_row["id"], now_iso(), now_iso()),
        )
    return {"id": user_row["id"]}


@app.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: int, request: Request, confirm: bool = Query(False)):
    require_admin(request)
    if not confirm:
        raise HTTPException(400, "CONFIRM_REQUIRED")
    with db() as con:
        owner = con.execute("SELECT id FROM local_users WHERE id=?", (user_id,)).fetchone()
        if not owner:
            raise HTTPException(404, "USER_NOT_FOUND")
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
            con.execute("DELETE FROM accounts WHERE id=?", (account_id,))
        con.execute("DELETE FROM local_sessions WHERE user_id=?", (user_id,))
        con.execute("DELETE FROM local_user_settings WHERE user_id=?", (user_id,))
        con.execute("DELETE FROM local_users WHERE id=?", (user_id,))
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
        con.execute("DELETE FROM accounts WHERE id=?", (account_id,))
    return {"ok": True}


@app.get("/admin/group_workers")
def admin_group_workers(request: Request, account_id: Optional[int] = None, limit: int = Query(200, ge=1, le=1000)):
    require_admin(request)
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


@app.get("/admin/group_matches")
def admin_group_matches(
    request: Request,
    account_id: Optional[int] = None,
    chat_id: Optional[int] = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    require_admin(request)
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
            SELECT id, account_id, chat_id, message_id, message_text, sender_phone, created_at
            FROM group_matches
            {where}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


def _get_active_account_session(local_user_id: int):
    with db() as con:
        row = con.execute(
            """
            SELECT s.account_id, s.session_string
            FROM tg_sessions s
            JOIN accounts a ON a.id = s.account_id
            WHERE s.revoked_at IS NULL
              AND a.local_user_id=?
            ORDER BY s.updated_at DESC
            LIMIT 1
            """,
            (local_user_id,),
        ).fetchone()
    if not row:
        return None, None
    return row["account_id"], decrypt_text(row["session_string"])


def _get_cached_groups(account_id: int, max_age_sec: int):
    with db() as con:
        row = con.execute(
            "SELECT MAX(updated_at) AS last_update FROM group_catalog WHERE account_id=?",
            (account_id,),
        ).fetchone()
        if not row or not row["last_update"]:
            return None
        last_update = datetime.fromisoformat(row["last_update"])
        if datetime.utcnow() - last_update > timedelta(seconds=max_age_sec):
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
