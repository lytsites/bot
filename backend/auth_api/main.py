from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth_api import telegram_auth
from common.auth import verify_token
from common.config import FRONTEND_ORIGINS
from common.db import init_db
from common.logging_setup import get_logger, request_id_middleware, setup_logging


setup_logging()
logger = get_logger("auth.api")

app = FastAPI(title="TG Auth Service")
app.middleware("http")(request_id_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


def require_auth(request: Request) -> int:
    token = request.headers.get("X-Auth-Token")
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(401, "UNAUTHORIZED")
    return user_id


class StartReq(BaseModel):
    # Some clients may send null/empty; validate explicitly to avoid Telethon crashing.
    phone: str | None = None


class CodeReq(BaseModel):
    auth_id: str | None = None
    code: str | None = None


class PassReq(BaseModel):
    auth_id: str | None = None
    password: str | None = None


class CancelReq(BaseModel):
    auth_id: str | None = None


class QrStartReq(BaseModel):
    label: str | None = None


class QrRefreshReq(BaseModel):
    auth_id: str | None = None


class QrContinueReq(BaseModel):
    auth_id: str | None = None


@app.get("/health")
def health(request: Request):
    require_auth(request)
    logger.info("health")
    return {"ok": True}


@app.post("/auth/start")
def start(req: StartReq, request: Request):
    user_id = require_auth(request)
    phone = (req.phone or "").strip()
    if not phone:
        raise HTTPException(400, "PHONE_REQUIRED")
    try:
        return telegram_auth.start_auth(phone, user_id)
    except Exception as e:
        logger.exception("start failed")
        raise HTTPException(400, f"START_FAILED: {type(e).__name__}: {e}")


@app.post("/auth/code")
def code(req: CodeReq, request: Request):
    require_auth(request)
    auth_id = (req.auth_id or "").strip()
    code = (req.code or "").strip()
    if not auth_id:
        raise HTTPException(400, "AUTH_ID_REQUIRED")
    if not code:
        raise HTTPException(400, "CODE_REQUIRED")
    try:
        return telegram_auth.submit_code(auth_id, code)
    except KeyError:
        raise HTTPException(404, "AUTH_NOT_FOUND")
    except Exception as e:
        logger.exception("code failed")
        raise HTTPException(400, f"CODE_FAILED: {type(e).__name__}: {e}")


@app.post("/auth/password")
def password(req: PassReq, request: Request):
    require_auth(request)
    auth_id = (req.auth_id or "").strip()
    password = (req.password or "")
    if not auth_id:
        raise HTTPException(400, "AUTH_ID_REQUIRED")
    if not str(password).strip():
        raise HTTPException(400, "PASSWORD_REQUIRED")
    try:
        logger.info("password endpoint auth_id=%s", auth_id)
        return telegram_auth.submit_password(auth_id, password)
    except KeyError:
        raise HTTPException(404, "AUTH_NOT_FOUND")
    except Exception as e:
        logger.exception("password failed")
        raise HTTPException(400, f"PASSWORD_FAILED: {type(e).__name__}: {e}")


@app.get("/auth/status/{auth_id}")
def status(auth_id: str, request: Request):
    require_auth(request)
    try:
        return telegram_auth.get_status(auth_id)
    except KeyError:
        raise HTTPException(404, "AUTH_NOT_FOUND")


@app.post("/auth/cancel/{auth_id}")
def cancel(auth_id: str, request: Request):
    require_auth(request)
    try:
        return telegram_auth.cancel_auth(auth_id)
    except KeyError:
        raise HTTPException(404, "AUTH_NOT_FOUND")


@app.post("/auth/cancel")
def cancel_body(req: CancelReq, request: Request):
    require_auth(request)
    auth_id = (req.auth_id or "").strip()
    if not auth_id:
        raise HTTPException(400, "AUTH_ID_REQUIRED")
    try:
        return telegram_auth.cancel_auth(auth_id)
    except KeyError:
        raise HTTPException(404, "AUTH_NOT_FOUND")


@app.post("/auth/qr/start")
def qr_start(req: QrStartReq, request: Request):
    user_id = require_auth(request)
    try:
        return telegram_auth.start_qr_auth(user_id)
    except Exception as e:
        logger.exception("qr start failed")
        raise HTTPException(400, f"QR_START_FAILED: {type(e).__name__}: {e}")


@app.post("/auth/qr/refresh")
def qr_refresh(req: QrRefreshReq, request: Request):
    require_auth(request)
    auth_id = (req.auth_id or "").strip()
    if not auth_id:
        raise HTTPException(400, "AUTH_ID_REQUIRED")
    try:
        return telegram_auth.refresh_qr_auth(auth_id)
    except KeyError:
        raise HTTPException(404, "AUTH_NOT_FOUND")
    except Exception as e:
        logger.exception("qr refresh failed")
        raise HTTPException(400, f"QR_REFRESH_FAILED: {type(e).__name__}: {e}")


@app.post("/auth/qr/continue")
def qr_continue(req: QrContinueReq, request: Request):
    require_auth(request)
    auth_id = (req.auth_id or "").strip()
    if not auth_id:
        raise HTTPException(400, "AUTH_ID_REQUIRED")
    try:
        return telegram_auth.continue_qr_auth(auth_id)
    except KeyError:
        raise HTTPException(404, "AUTH_NOT_FOUND")
    except Exception as e:
        logger.exception("qr continue failed")
        raise HTTPException(400, f"QR_CONTINUE_FAILED: {type(e).__name__}: {e}")
