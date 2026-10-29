"""Small OpenAI-compatible chat-completions transport; never logs credentials or JD text."""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from typing import Any, Protocol


class ModelClient(Protocol):
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]: ...


class ModelFailure(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


_OK_FINISH = {None, "stop", "eos", "end_turn"}
_REFUSED_FINISH = {"content_filter", "content_policy", "refusal", "refuse", "safety"}


def _is_refused_finish(finish_reason: Any) -> bool:
    if not isinstance(finish_reason, str):
        return False
    return finish_reason.casefold() in _REFUSED_FINISH or "filter" in finish_reason.casefold()


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
        if chunks:
            return "".join(chunks)
    return ""


def _json_object(content: str) -> dict[str, Any] | None:
    if not isinstance(content, str) or not content.strip():
        return None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


class HttpModelClient:
    def __init__(self, *, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None, max_tokens: int | None = None, timeout: float | None = None,
                 require_complete: bool = False) -> None:
        self.require_complete = require_complete
        self._usage_lock = threading.Lock()
        self.usage = {'calls':0, 'prompt_tokens':0, 'completion_tokens':0, 'total_tokens':0}
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
        configured_timeout = timeout if timeout is not None else os.getenv("APPLYGUARD_AI_TIMEOUT", "60")
        try:
            self.timeout = float(configured_timeout)
        except (TypeError, ValueError) as exc:
            raise ValueError("APPLYGUARD_AI_TIMEOUT must be a number") from exc
        if isinstance(configured_timeout, bool) or not 1 <= self.timeout <= 300:
            raise ValueError("APPLYGUARD_AI_TIMEOUT must be between 1 and 300 seconds")
        # DeepSeek reasoning models spend completion budget on thinking; disable for JSON extract.
        thinking_flag = (os.getenv("APPLYGUARD_AI_THINKING") or "").strip().lower()
        if thinking_flag in ("0", "false", "disabled", "off"):
            self.disable_thinking = True
        elif thinking_flag in ("1", "true", "enabled", "on"):
            self.disable_thinking = False
        else:
            self.disable_thinking = "deepseek" in self.base_url.casefold() or "deepseek" in self.model.casefold()

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return self._complete(system_prompt, user_prompt)

    def complete_structured(self, system_prompt: str, user_prompt: str, schema: dict) -> dict[str, Any]:
        result = self._complete(system_prompt, user_prompt, schema=schema)
        from jsonschema import validate, ValidationError
        try:
            validate(result, schema)
        except ValidationError:
            raise ModelFailure('Model output did not match the required schema') from None
        return result

    def _complete(self, system_prompt: str, user_prompt: str, *, schema: dict | None = None) -> dict[str, Any]:
        if not self.api_key:
            raise ModelFailure("Model API key is not configured", retryable=False)
        if not self.base_url.startswith("https://"):
            raise ModelFailure("Model API URL must use HTTPS", retryable=False)
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self.disable_thinking:
            payload["thinking"] = {"type": "disabled"}
        if schema is not None:
            payload['response_format'] = {'type':'json_schema','json_schema':{
                'name':'applyguard_checked_output','strict':True,'schema':schema}}
        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            self.base_url + "/chat/completions", data=body,
            headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"},
        )
        try:
            with self._usage_lock:
                self.usage['calls'] += 1
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
            response_payload = json.loads(raw)
            usage = response_payload.get('usage', {})
            with self._usage_lock:
                for field in ('prompt_tokens','completion_tokens','total_tokens'):
                    if isinstance(usage.get(field),int):self.usage[field] += usage[field]
            choice = response_payload["choices"][0]
            finish_reason = choice.get("finish_reason")
            message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
            content = _message_text(message)
            result = _json_object(content)
        except ModelFailure:
            raise
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ModelFailure("Model returned invalid JSON") from exc
        if result is not None:
            if message.get('refusal') or _is_refused_finish(finish_reason) or ((self.require_complete or schema is not None) and finish_reason not in _OK_FINISH):
                raise ModelFailure(f"Model response was truncated or refused (finish_reason={finish_reason})", retryable=finish_reason == 'length')
            return result
        if not isinstance(content, str) or not content.strip():
            raise ModelFailure("Model returned empty content")
        if finish_reason not in _OK_FINISH and finish_reason is not None:
            raise ModelFailure(
                f"Model response was truncated or refused (finish_reason={finish_reason})",
                retryable=finish_reason == "length",
            )
        raise ModelFailure("Model JSON must be an object")
