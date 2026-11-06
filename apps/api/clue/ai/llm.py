"""LLM provider layer. OpenRouter (free models) is the default; others are plugins.

Frugal by design: content-hash cache, one repair retry on bad JSON, no tight retry
loops, automatic fallback to the next free model on 404/429/empty output.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from abc import ABC, abstractmethod
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from clue.core.settings_store import get_setting
from clue.models import ApiUsage, LlmCache

T = TypeVar("T", bound=BaseModel)
OPENROUTER = "https://openrouter.ai/api/v1"


class LLMError(Exception):
    """User-presentable LLM failure (no key, quota hit, bad output)."""


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def chat(self, model: str, system: str, user: str, json_mode: bool = True) -> tuple[str, int, int]:
        """Return (text, tokens_in, tokens_out). Raise LLMError / httpx errors."""

    @abstractmethod
    def list_models(self) -> list[str]: ...


class OpenRouterProvider(LLMProvider):
    name = "openrouter"
    _models_cache: tuple[float, list[str]] | None = None

    def __init__(self, api_key: str):
        self.key = api_key

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.key}", "HTTP-Referer": "http://localhost:3000", "X-Title": "Clue AI"}

    def list_models(self) -> list[str]:
        """Free model ids, re-checked at most once a day."""
        c = OpenRouterProvider._models_cache
        if c and time.time() - c[0] < 86400:
            return c[1]
        r = httpx.get(f"{OPENROUTER}/models", timeout=20)
        r.raise_for_status()
        ids = [m["id"] for m in r.json().get("data", []) if m["id"].endswith(":free")]
        ids = ["openrouter/free"] + sorted(ids)
        OpenRouterProvider._models_cache = (time.time(), ids)
        return ids

    def key_info(self) -> dict:
        """Quota/usage for the key (GET /key). Raises LLMError on a bad key."""
        r = httpx.get(f"{OPENROUTER}/key", headers=self._headers(), timeout=20)
        if r.status_code in (401, 403):
            raise LLMError("OpenRouter rejected this key. Check it and try again.")
        r.raise_for_status()
        return r.json().get("data", {})

    def chat(self, model, system, user, json_mode=True):
        body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 0.7}
        r = httpx.post(f"{OPENROUTER}/chat/completions", headers=self._headers(), json=body, timeout=120)
        if r.status_code == 429:
            raise LLMError("rate_limited")
        if r.status_code in (404, 400):
            raise LLMError(f"model_unavailable:{model}")
        if r.status_code in (401, 403):
            raise LLMError("OpenRouter rejected the API key.")
        r.raise_for_status()
        data = r.json()
        text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        u = data.get("usage") or {}
        return text, int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))


def get_provider(db: Session) -> LLMProvider:
    key = get_setting(db, "openrouter_api_key")
    if not key:
        raise LLMError("AI is not set up yet. Add your free OpenRouter key at /setup. Non-AI features still work.")
    return OpenRouterProvider(key)


def _extract_json(text: str) -> object:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e > s:
            return json.loads(text[s : e + 1])
        raise


def complete_json(db: Session, schema: type[T], system: str, user: str, *, feature: str, task: str = "smart", user_id: str | None = None) -> T:
    """One structured call: cached by content hash, validated, one repair retry.

    `user` must already wrap untrusted text in delimiters; the system prompt must
    tell the model to treat it as data.
    """
    sys_full = f"{system}\n\nReply with ONLY a JSON object matching this JSON schema, no prose:\n{json.dumps(schema.model_json_schema())}"
    h = hashlib.sha256(f"{schema.__name__}|{sys_full}|{user}".encode()).hexdigest()
    cached = db.get(LlmCache, h)
    if cached:
        return schema.model_validate_json(cached.response)

    prov = get_provider(db)
    pref = get_setting(db, "model_smart" if task == "smart" else "model_fast")
    try:
        models = prov.list_models()
    except Exception:
        models = ["openrouter/free"]
    order = ([pref] if pref else []) + [m for m in models if m != pref]

    last_err = "no model produced valid output"
    tried = 0
    for model in order:
        if tried >= 3:
            break
        tried += 1
        prompt = user
        for attempt in range(2):  # attempt 1 = repair retry on schema failure
            try:
                text, ti, to = prov.chat(model, sys_full, prompt)
            except LLMError as e:
                last_err = str(e)
                if last_err == "rate_limited":
                    raise LLMError("AI quota reached for now (free models allow ~20 requests/min and ~50/day). Try again later; non-AI features still work.")
                break
            except httpx.HTTPError as e:
                last_err = f"network: {e.__class__.__name__}"
                break
            db.add(ApiUsage(user_id=user_id, provider=prov.name, model=model, feature=feature, tokens_in=ti, tokens_out=to, cost_usd_micro=0, ok=bool(text)))
            db.commit()
            if not text.strip():
                break
            try:
                obj = schema.model_validate(_extract_json(text))
                db.merge(LlmCache(hash=h, response=obj.model_dump_json()))
                db.commit()
                return obj
            except (ValidationError, json.JSONDecodeError, ValueError) as e:
                last_err = f"invalid output: {str(e)[:120]}"
                prompt = f"{user}\n\nYour previous reply was invalid ({str(e)[:200]}). Reply again with ONLY valid JSON."
    raise LLMError(f"The AI could not complete this ({last_err}). Please try again shortly.")
