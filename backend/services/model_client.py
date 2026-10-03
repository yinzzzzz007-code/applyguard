"""Small OpenAI-compatible chat-completions transport; never logs credentials or JD text."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Protocol


class ModelClient(Protocol):
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]: ...


class ModelFailure(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class HttpModelClient:
    def __init__(self, *, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None, max_tokens: int | None = None, timeout: float = 12) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("APPLYGUARD_AI_API_KEY", "")
        self.base_url = (base_url or os.getenv("APPLYGUARD_AI_BASE_URL", "https://api.chatanywhere.tech/v1")).rstrip("/")
        self.model = model if model is not None else os.getenv("APPLYGUARD_AI_MODEL", "gpt-4o-mini")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("APPLYGUARD_AI_MODEL must be a non-empty model name")
        configured_tokens = max_tokens if max_tokens is not None else os.getenv("APPLYGUARD_AI_MAX_TOKENS", "2048")
        try:
            self.max_tokens = int(configured_tokens)
        except (TypeError, ValueError) as exc:
            raise ValueError("APPLYGUARD_AI_MAX_TOKENS must be an integer") from exc
        if isinstance(configured_tokens, bool) or not 1 <= self.max_tokens <= 16384:
            raise ValueError("APPLYGUARD_AI_MAX_TOKENS must be between 1 and 16384")
        self.timeout = timeout

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise ModelFailure("Model API key is not configured", retryable=False)
        if not self.base_url.startswith("https://"):
            raise ModelFailure("Model API URL must use HTTPS", retryable=False)
        body = json.dumps({"model": self.model, "temperature": 0, "max_tokens": self.max_tokens,
                           "response_format": {"type": "json_object"},
                           "messages": [{"role": "system", "content": system_prompt},
                                        {"role": "user", "content": user_prompt}]}).encode()
        request = urllib.request.Request(
            self.base_url + "/chat/completions", data=body,
            headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(262145)
        except urllib.error.HTTPError as exc:
            raise ModelFailure(f"Model service returned HTTP {exc.code}",
                               retryable=exc.code == 429 or exc.code >= 500) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ModelFailure("Model request failed or timed out") from exc
        if len(raw) > 262144:
            raise ModelFailure("Model response exceeded size limit")
        try:
            payload = json.loads(raw)
            if payload["choices"][0].get("finish_reason") not in (None, "stop"):
                raise ModelFailure("Model response was truncated or refused")
            content = payload["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ModelFailure("Model returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise ModelFailure("Model JSON must be an object")
        return result
