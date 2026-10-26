"""Translate a course the first time someone asks for it in a new language.

The request is never made to wait: the learner hears English right away, a
background job translates the whole course, and the next request gets the saved
copy. Cantonese is the exception: it is not in the fleet files, so the audio
course is translated on that request and then cached. NLLB (the speech service
/translate, when TRANSLATION_BASE_URL or SPEECH_BASE_URL points at one that
really translates) is tried first and Grok is the failover. Results are shared
through Redis so every replica sees them.

Off unless AOEP_ON_DEMAND_TRANSLATION=1, and capped per day, so it cannot spend
money by surprise.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_PREFIX = "aoep:ct:v1"
LOCK_SECONDS = 1800
CHUNK_WORDS = 160

Translator = Callable[[str, str, str], Optional[str]]


def enabled() -> bool:
    return os.environ.get("AOEP_ON_DEMAND_TRANSLATION", "").strip().lower() in {"1", "true", "yes"}


def daily_limit() -> int:
    try:
        return max(0, int(os.environ.get("AOEP_ON_DEMAND_DAILY_LIMIT", "40")))
    except ValueError:
        return 40


# ---- Storage: Redis when configured, memory otherwise -------------------------

class _MemoryKV:
    def __init__(self) -> None:
        self.data: Dict[str, str] = {}
        self.counters: Dict[str, int] = {}
        self.locks: Dict[str, float] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[str]:
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value

    def lock(self, key: str, seconds: int) -> bool:
        with self._lock:
            if self.locks.get(key, 0) > time.time():
                return False
            self.locks[key] = time.time() + seconds
            return True

    def unlock(self, key: str) -> None:
        self.locks.pop(key, None)

    def incr(self, key: str) -> int:
        with self._lock:
            self.counters[key] = self.counters.get(key, 0) + 1
            return self.counters[key]


class _RedisKV:
    def __init__(self, client: Any) -> None:
        self._r = client

    def get(self, key: str) -> Optional[str]:
        value = self._r.get(key)
        return value.decode() if isinstance(value, bytes) else value

    def set(self, key: str, value: str) -> None:
        self._r.set(key, value)

    def lock(self, key: str, seconds: int) -> bool:
        return bool(self._r.set(key, "1", nx=True, ex=seconds))

    def unlock(self, key: str) -> None:
        self._r.delete(key)

    def incr(self, key: str) -> int:
        count = int(self._r.incr(key))
        if count == 1:
            self._r.expire(key, 172800)
        return count


_kv: Any = None


def _store() -> Any:
    global _kv
    if _kv is None:
        client = None
        try:
            from .redis_url import open_redis, runtime_redis_url

            url = runtime_redis_url()
            client = open_redis(url) if url else None
        except Exception:  # noqa: BLE001 - Redis is optional
            client = None
        _kv = _RedisKV(client) if client is not None else _MemoryKV()
    return _kv


def set_store_for_tests(kv: Any) -> None:
    global _kv
    _kv = kv


def _key(course_id: str, lang: str) -> str:
    return f"{_PREFIX}:{course_id}:{lang}"


def remember_course(course_id: str, lang: str, record: dict) -> None:
    """Keep one finished translation for the next request of the same course."""
    try:
        _store().set(_key(course_id, lang), json.dumps(record, ensure_ascii=False))
    except Exception:  # noqa: BLE001 - a cache miss just translates again
        return


def get_cached(course_id: str, lang: str, expected_segments: int) -> Optional[dict]:
    """The saved translation, only if it has the same number of segments."""
    try:
        raw = _store().get(_key(course_id, lang))
        record = json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001
        return None
    if record and len(record.get("segments") or []) == expected_segments:
        return record
    return None


# ---- Translators ----------------------------------------------------------------

def _post_json(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"content-type": "application/json", **headers},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured service URLs
        return json.loads(response.read().decode())


def nllb_translate(text: str, source: str, target: str) -> Optional[str]:
    """The speech service /translate, accepted only when it really translated."""
    base = (os.environ.get("TRANSLATION_BASE_URL") or os.environ.get("SPEECH_BASE_URL") or "").rstrip("/")
    if not base:
        return None
    try:
        body = _post_json(f"{base}/translate", {"text": text, "source": source, "target": target}, {}, 90.0)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if body.get("engine") == "provider" and not body.get("degraded"):
        return (body.get("text") or "").strip() or None
    return None


def grok_translate(text: str, source: str, target: str) -> Optional[str]:
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        return None
    base = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
    model = os.environ.get("XAI_TEXT_MODEL", "grok-3-latest")
    prompt = (
        f"Translate this lesson narration from {source} to {target}. Keep proper nouns, numbers and "
        "meaning. Output only the translation, with no notes."
    )
    try:
        body = _post_json(
            f"{base}/chat/completions",
            {"model": model, "temperature": 0, "messages": [
                {"role": "system", "content": prompt}, {"role": "user", "content": text}]},
            {"authorization": f"Bearer {key}"},
            60.0,
        )
        return (body["choices"][0]["message"]["content"] or "").strip() or None
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError):
        return None


def chain_translate(text: str, source: str, target: str) -> Optional[str]:
    return nllb_translate(text, source, target) or grok_translate(text, source, target)


# ---- The background job ---------------------------------------------------------

def _chunks(text: str) -> List[str]:
    from .course_translation_batch import split_translation_text

    return split_translation_text(text, CHUNK_WORDS) or [text]


def translate_course(
    course_id: str, title: str, segments: List[dict], lang: str,
    translator: Translator = chain_translate, source: str = "en",
) -> Optional[dict]:
    """Translate every segment. Any failure abandons the course: a half-translated
    lesson would mix languages, so nothing is saved."""
    rows = []
    for seg in segments:
        heading = translator(seg["heading"], source, lang)
        parts = [translator(chunk, source, lang) for chunk in _chunks(seg["text"])]
        if not heading or not all(parts):
            return None
        rows.append({"heading": heading, "text": " ".join(parts), "kind": seg.get("kind", "narration")})
    new_title = translator(title, source, lang) or title
    return {"course_id": course_id, "title": new_title, "source_language": source, "language": lang,
            "source": "on-demand", "segments": rows}


def request_course_translation(
    course_id: str, title: str, segments: List[dict], lang: str,
    translator: Translator = chain_translate, background: bool = True,
) -> bool:
    """Start a translation if none is saved, running, or over the daily cap."""
    if not enabled() or lang == "en" or not segments:
        return False
    kv = _store()
    try:
        if get_cached(course_id, lang, len(segments)):
            return False
        if not kv.lock(f"{_key(course_id, lang)}:lock", LOCK_SECONDS):
            return False
        if kv.incr(f"{_PREFIX}:day:{time.strftime('%Y%m%d', time.gmtime())}") > daily_limit():
            kv.unlock(f"{_key(course_id, lang)}:lock")
            logger.info("on-demand translation: daily limit reached")
            return False
    except Exception:  # noqa: BLE001 - never break a page load
        return False

    def run() -> None:
        try:
            record = translate_course(course_id, title, segments, lang, translator)
            if record:
                kv.set(_key(course_id, lang), json.dumps(record, ensure_ascii=False))
        except Exception:  # noqa: BLE001
            logger.exception("on-demand translation failed for %s/%s", course_id, lang)
        finally:
            kv.unlock(f"{_key(course_id, lang)}:lock")

    if background:
        threading.Thread(target=run, daemon=True, name=f"ct-{course_id}-{lang}").start()
    else:
        run()
    return True
