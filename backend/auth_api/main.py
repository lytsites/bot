from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth_api import telegram_auth
from common.auth import verify_token
from common.config import FRONTEND_ORIGINS
from common.db import db
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


def require_flow_owner(auth_id: str, user_id: int) -> None:
    """
    Prevent any authenticated user from probing/cancelling/submitting password for чужой auth_id.
    auth_id is UUID so hard to guess, but this is still worth enforcing.
    """
    auth_id = (auth_id or "").strip()
    if not auth_id:
        raise HTTPException(400, "AUTH_ID_REQUIRED")
    with db() as con:
        row = con.execute(
            "SELECT local_user_id FROM auth_flows WHERE auth_id=?",
            (auth_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "AUTH_NOT_FOUND")
    if int(row["local_user_id"] or 0) != int(user_id):
        # Return 404 to avoid leaking existence of auth_id.
        raise HTTPException(404, "AUTH_NOT_FOUND")


@app.get("/health")
def health(request: Request):
    require_auth(request)
    logger.info("health")
    return {"ok": True}


@app.post("/auth/password")
def password(req: PassReq, request: Request):
    user_id = require_auth(request)
    auth_id = (req.auth_id or "").strip()
    password = (req.password or "")
    if not auth_id:
        raise HTTPException(400, "AUTH_ID_REQUIRED")
    if not str(password).strip():
        raise HTTPException(400, "PASSWORD_REQUIRED")
    require_flow_owner(auth_id, user_id)
    try:
        logger.info("password endpoint auth_id=%s", auth_id)
        return telegram_auth.submit_password(auth_id, password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError:
        raise HTTPException(404, "AUTH_NOT_FOUND")
    except Exception as e:
        logger.exception("password failed")
        raise HTTPException(400, "PASSWORD_FAILED")


@app.post("/auth/cancel/{auth_id}")
def cancel(auth_id: str, request: Request):
    user_id = require_auth(request)
    require_flow_owner(auth_id, user_id)
    try:
        return telegram_auth.cancel_auth(auth_id)
    except KeyError:
        raise HTTPException(404, "AUTH_NOT_FOUND")


@app.post("/auth/cancel")
def cancel_body(req: CancelReq, request: Request):
    user_id = require_auth(request)
    auth_id = (req.auth_id or "").strip()
    if not auth_id:
        raise HTTPException(400, "AUTH_ID_REQUIRED")
    require_flow_owner(auth_id, user_id)
    try:
        return telegram_auth.cancel_auth(auth_id)
    except KeyError:
        raise HTTPException(404, "AUTH_NOT_FOUND")


@app.post("/auth/qr/start")
def qr_start(req: QrStartReq, request: Request):
    user_id = require_auth(request)
    try:
        return telegram_auth.start_qr_auth(user_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        msg = str(e)
        if "TG_API_ID/TG_API_HASH" in msg:
            raise HTTPException(500, "TG_NOT_CONFIGURED")
        if msg == "QR_START_TIMEOUT":
            raise HTTPException(504, "QR_START_TIMEOUT")
        raise HTTPException(500, "QR_START_FAILED")
    except Exception as e:
        logger.exception("qr start failed")
        raise HTTPException(400, "QR_START_FAILED")


@app.post("/auth/qr/refresh")
def qr_refresh(req: QrRefreshReq, request: Request):
    user_id = require_auth(request)
    auth_id = (req.auth_id or "").strip()
    if not auth_id:
        raise HTTPException(400, "AUTH_ID_REQUIRED")
    require_flow_owner(auth_id, user_id)
    try:
        return telegram_auth.refresh_qr_auth(auth_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError:
        raise HTTPException(404, "AUTH_NOT_FOUND")
    except Exception as e:
        logger.exception("qr refresh failed")
        raise HTTPException(400, "QR_REFRESH_FAILED")


@app.post("/auth/qr/continue")
def qr_continue(req: QrContinueReq, request: Request):
    user_id = require_auth(request)
    auth_id = (req.auth_id or "").strip()
    if not auth_id:
        raise HTTPException(400, "AUTH_ID_REQUIRED")
    require_flow_owner(auth_id, user_id)
    try:
        return telegram_auth.continue_qr_auth(auth_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError:
        raise HTTPException(404, "AUTH_NOT_FOUND")
    except Exception as e:
        logger.exception("qr continue failed")
        raise HTTPException(400, "QR_CONTINUE_FAILED")
