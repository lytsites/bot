from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai.deepseek_client import DeepSeekError, generate_text
from common.config import FRONTEND_ORIGINS
from common.logging_setup import get_logger, request_id_middleware, setup_logging


setup_logging()
logger = get_logger("ai.api")

app = FastAPI(title="AI Backend")
app.middleware("http")(request_id_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_probe_state = {
    "last_at": 0.0,
    "ok": None,  # type: ignore[assignment]
    "error": "",
}
_PROBE_TTL_S = float(30)


class GenerateReq(BaseModel):
    prompt: str = Field(min_length=1)
    max_tokens: int = Field(default=256, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)
    stop: list[str] = Field(default_factory=list)


@app.get("/ai/health")
def health(probe: bool = Query(False)):
    """
    Lightweight health endpoint.

    If probe=true, performs a tiny DeepSeek request at most once per PROBE_TTL_S,
    and returns cached result to avoid spamming the provider.
    """
    base = {"ok": True, "provider": "deepseek"}

    if not probe:
        return {**base, "deepseek_ok": None, "deepseek_error": ""}

    now = time.time()
    if _probe_state["last_at"] and (now - float(_probe_state["last_at"])) < _PROBE_TTL_S:
        return {**base, "deepseek_ok": _probe_state["ok"], "deepseek_error": _probe_state["error"]}

    try:
        # Minimal request: 1 token, short timeout.
        generate_text(prompt="ping", max_tokens=1, temperature=0.0, top_p=1.0, stop=["\n"], timeout_s=6.0)
        _probe_state["ok"] = True
        _probe_state["error"] = ""
    except DeepSeekError:
        _probe_state["ok"] = False
        _probe_state["error"] = "AI_PROVIDER_ERROR"
    except Exception:
        _probe_state["ok"] = False
        _probe_state["error"] = "AI_ERROR"
    finally:
        _probe_state["last_at"] = now

    return {**base, "deepseek_ok": _probe_state["ok"], "deepseek_error": _probe_state["error"]}

@app.post("/ai/generate")
def generate(req: GenerateReq):
    try:
        result = generate_text(
            prompt=req.prompt,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            top_p=req.top_p,
            stop=req.stop,
        )
        return {"ok": True, **result}
    except DeepSeekError as e:
        # Do not leak provider/internal details to clients.
        logger.info("deepseek error: %s", e)
        raise HTTPException(503, "AI_PROVIDER_ERROR")
    except Exception as e:
        logger.exception("ai generate failed")
        raise HTTPException(500, "AI_ERROR")


@app.post("/ai/reload")
def reload_model():
    # No local model to reload for DeepSeek; endpoint kept for compatibility.
    return {"ok": True}
