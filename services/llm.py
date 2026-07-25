"""Groq client with strict JSON handling, rate-limit awareness, and a rules fallback.

Three deliberate behaviours:
  - responses are cached on disk, keyed on model + prompt, so re-running an
    evaluation after a routing change costs nothing
  - rate limits are retried with the delay the API asks for, and reported
    distinctly from malformed output
  - anything unrecoverable degrades to keyword classification, which the router
    then holds for a human
"""
import hashlib
import json
import os
import pathlib
import re
import time
from typing import Any, Dict, Optional

import config


class LLMUnavailable(Exception):
    """The model could not be reached at all."""


class RateLimited(LLMUnavailable):
    """The provider refused the call because a quota was exhausted."""


_client = None
CACHE_DIR = pathlib.Path(os.getenv("LLM_CACHE_DIR", ".llm_cache"))
CACHE_ENABLED = os.getenv("LLM_CACHE", "1") != "0"


def _get_client():
    global _client
    if _client is None:
        if config.LLM_PROVIDER == "nvidia":
            if not config.NVIDIA_API_KEY:
                raise LLMUnavailable("NVIDIA_API_KEY is not set")
            from openai import OpenAI
            _client = OpenAI(api_key=config.NVIDIA_API_KEY, base_url=config.NVIDIA_BASE_URL)
        else:
            if not config.GROQ_API_KEY:
                raise LLMUnavailable("GROQ_API_KEY is not set")
            from groq import Groq
            _client = Groq(api_key=config.GROQ_API_KEY)
    return _client


def _cache_key(system: str, user: str, temperature: float) -> str:
    blob = f"{config.LLM_PROVIDER}|{config.active_model()}|{temperature}|{system}|{user}"
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def _cache_read(key: str) -> Optional[str]:
    if not CACHE_ENABLED:
        return None
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())["response"]
        except Exception:
            return None
    return None


def _cache_write(key: str, response: str) -> None:
    if not CACHE_ENABLED:
        return
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        (CACHE_DIR / f"{key}.json").write_text(json.dumps({"response": response}))
    except Exception:
        pass


_RETRY_AFTER = re.compile(r"try again in ([\d.]+)m([\d.]+)s|try again in ([\d.]+)s")


def _retry_delay(message: str) -> float:
    m = _RETRY_AFTER.search(message)
    if not m:
        return 0.0
    if m.group(1):
        return float(m.group(1)) * 60 + float(m.group(2))
    return float(m.group(3))


def complete(system: str, user: str, temperature: float = 0.2, max_tokens: int = 900,
             max_wait: float = 30.0) -> str:
    key = _cache_key(system, user, temperature)
    cached = _cache_read(key)
    if cached is not None:
        return cached

    client = _get_client()
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=config.active_model(),
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
            )
            text = resp.choices[0].message.content or ""
            _cache_write(key, text)
            return text
        except Exception as exc:
            message = str(exc)
            if "rate_limit" in message or "429" in message:
                delay = _retry_delay(message)
                # Only wait out short windows. A daily quota is not worth blocking on.
                if 0 < delay <= max_wait and attempt < 2:
                    time.sleep(delay + 0.5)
                    continue
                raise RateLimited(message[:300]) from exc
            raise
    raise LLMUnavailable("exhausted retries")


def _extract_json(text: str) -> str:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return text


def complete_json(system: str, user: str, temperature: float = 0.0) -> Optional[Dict[str, Any]]:
    """Return a parsed dict, or None if the model never produced valid JSON.

    Rate limits propagate rather than returning None, so the caller can report
    'quota exhausted' instead of the misleading 'model returned bad JSON'.
    """
    last_error = ""
    for attempt in range(config.LLM_MAX_ATTEMPTS):
        prompt = user if attempt == 0 else (
            f"{user}\n\nYour previous reply was not valid JSON ({last_error}). "
            "Reply with a single JSON object and nothing else."
        )
        try:
            return json.loads(_extract_json(complete(system, prompt, temperature=temperature)))
        except LLMUnavailable:
            raise
        except Exception as exc:
            last_error = str(exc)[:120]
    return None


def cache_stats() -> Dict[str, int]:
    if not CACHE_DIR.exists():
        return {"entries": 0}
    return {"entries": len(list(CACHE_DIR.glob("*.json")))}