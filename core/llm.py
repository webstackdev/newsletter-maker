from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
from django.conf import settings

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(slots=True)
class OpenRouterJSONResponse:
    payload: dict[str, Any]
    model: str
    latency_ms: int


def openrouter_chat_json(*, model: str, system_prompt: str, user_prompt: str) -> OpenRouterJSONResponse:
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY must be configured for OpenRouter chat completions.")

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    if settings.OPENROUTER_APP_URL:
        headers["HTTP-Referer"] = settings.OPENROUTER_APP_URL
    if settings.OPENROUTER_APP_NAME:
        headers["X-OpenRouter-Title"] = settings.OPENROUTER_APP_NAME

    started_at = time.perf_counter()
    response = httpx.post(
        f"{settings.OPENROUTER_API_BASE.rstrip('/')}/chat/completions",
        headers=headers,
        json={
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
    )
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    response.raise_for_status()

    message_content = response.json()["choices"][0]["message"]["content"]
    return OpenRouterJSONResponse(
        payload=_extract_json_object(message_content),
        model=model,
        latency_ms=latency_ms,
    )


def _extract_json_object(message_content: str) -> dict[str, Any]:
    try:
        payload = json.loads(message_content)
    except json.JSONDecodeError:
        match = JSON_OBJECT_PATTERN.search(message_content)
        if not match:
            raise ValueError("Model response did not contain a JSON object.")
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Model response JSON must be an object.")
    return payload
