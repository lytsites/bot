from __future__ import annotations

import os
from typing import Any, Optional

import httpx


class DeepSeekError(RuntimeError):
    pass


def _deepseek_base_url() -> str:
    # DeepSeek is OpenAI-compatible. Keep configurable for deployments.
    return (os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")


def _deepseek_model() -> str:
    return (os.getenv("DEEPSEEK_MODEL") or "deepseek-chat").strip()


def _deepseek_api_key() -> str:
    key = (os.getenv("DEEPSEEK_API_KEY") or os.getenv("AI_API_KEY") or "").strip()
    if not key:
        raise DeepSeekError("DEEPSEEK_API_KEY is not set")
    return key


def generate_text(
    prompt: str,
    max_tokens: int = 256,
    temperature: float = 0.7,
    top_p: float = 0.95,
    stop: Optional[list[str]] = None,
    timeout_s: Optional[float] = None,
) -> dict[str, Any]:
    """
    Minimal OpenAI-compatible chat.completions call.
    Returns: {text: str, usage: dict}
    """
    stop = stop or []

    payload: dict[str, Any] = {
        "model": _deepseek_model(),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }
    if stop:
        payload["stop"] = stop

    headers = {
        "Authorization": f"Bearer {_deepseek_api_key()}",
        "Content-Type": "application/json",
    }

    if timeout_s is None:
        timeout_s = float(os.getenv("DEEPSEEK_HTTP_TIMEOUT", "120"))
    with httpx.Client(timeout=timeout_s) as client:
        r = client.post(f"{_deepseek_base_url()}/v1/chat/completions", json=payload, headers=headers)

    if r.status_code >= 400:
        # Do not leak API key; include response text for debugging.
        raise DeepSeekError(f"HTTP {r.status_code}: {r.text[:1000]}")

    data = r.json()
    choices = data.get("choices") or []
    msg = (choices[0].get("message") or {}) if choices else {}
    text = (msg.get("content") or "").strip()
    usage = data.get("usage") or {}
    return {"text": text, "usage": usage}
