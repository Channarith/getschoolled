"""Abuse guards for POST /api/studio/voice/ask: server-issued signed sessions, issuance and account limits, a global daily budget.

The ask route answers with a paid language model and needs no login (the demo and On the Go are anonymous). Its per-session cap used to
be keyed by an id the CLIENT made up, so a script could rotate ids and never hit a session cap. Now:

  * a session is a token the SERVER issued (POST /api/studio/voice/session): HMAC-signed, with an expiry and, for a signed-in caller,
    the verified account id. An unknown, forged or expired token is refused;
  * issuing tokens is itself limited per client address, so ids cannot be minted in bulk either;
  * an anonymous token lives about as long as the free sample (a bounded server-side window, since On the Go's demo clock is client-side);
  * on top of the per-session and per-address caps there is a per-account cap and a GLOBAL daily budget for the whole route.

Config (names only): VOICE_ASK_SIGNING_KEY (falls back to AUTH_SIGNING_KEY; without either a random per-process key is used, which only
works for a single replica), VOICE_ASK_ANON_TTL_MIN, VOICE_ASK_ACCOUNT_TTL_MIN, VOICE_ASK_ISSUE_PER_IP_HOUR, VOICE_ASK_ANON_PER_IP_DAY,
VOICE_ASK_PER_ACCOUNT_HOUR, VOICE_ASK_DAILY_BUDGET, VOICE_ASK_APP_KEY (native apps, see ``app_key_ok``).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Any, Callable, Optional

log = logging.getLogger("theodore_course_studio.voice_ask")

TOKEN_PREFIX = "va1"
TOKEN_RE = re.compile(r"^va1\.[A-Za-z0-9_-]{16,600}\.[0-9a-f]{64}$")
_PROCESS_KEY = secrets.token_hex(32)
_WARNED_KEY = False


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, "") or default))
    except ValueError:
        return default


def sample_minutes() -> int:
    try:
        from aoep_shared.course_studio_access import SAMPLE_MINUTES

        return int(SAMPLE_MINUTES)
    except Exception:  # noqa: BLE001 - the shared package is always there in the image; this keeps unit tests importable alone
        return 4


def anon_ttl_s() -> int:
    """An anonymous session lasts about the free sample plus a short grace, then asks are refused until a new session is issued."""
    default = (sample_minutes() + 2) * 60
    return _int_env("VOICE_ASK_ANON_TTL_MIN", 0, 0) * 60 or default


def account_ttl_s() -> int:
    return _int_env("VOICE_ASK_ACCOUNT_TTL_MIN", 240) * 60


def _signing_key() -> bytes:
    global _WARNED_KEY
    raw = os.environ.get("VOICE_ASK_SIGNING_KEY") or os.environ.get("AUTH_SIGNING_KEY") or ""
    if not raw:
        if not _WARNED_KEY:
            _WARNED_KEY = True
            log.warning("voice_ask: no VOICE_ASK_SIGNING_KEY/AUTH_SIGNING_KEY; using a per-process key (single replica only)")
        raw = _PROCESS_KEY
    return hmac.new(raw.encode("utf-8"), b"salareen-voice-ask-v1", hashlib.sha256).digest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@dataclass(frozen=True)
class AskSession:
    session_id: str        # random id chosen by the server; the key for the per-session caps
    expires_at: int
    account: str = ""      # verified account id when the caller was signed in at issue time, else ""

    @property
    def anonymous(self) -> bool:
        return not self.account


def issue_token(account: str = "", *, now: Callable[[], float] = time.time, ttl_s: Optional[int] = None) -> tuple[str, AskSession]:
    ttl = ttl_s if ttl_s is not None else (account_ttl_s() if account else anon_ttl_s())
    exp = int(now()) + int(ttl)
    session = AskSession(session_id=secrets.token_hex(8), expires_at=exp, account=(account or "")[:80])
    body = _b64(json.dumps({"i": session.session_id, "e": exp, "a": session.account}, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(_signing_key(), f"{TOKEN_PREFIX}.{body}".encode("ascii"), hashlib.sha256).hexdigest()
    return f"{TOKEN_PREFIX}.{body}.{sig}", session


def verify_token(token: str, *, now: Callable[[], float] = time.time) -> tuple[Optional[AskSession], str]:
    """(session, "") when the token is genuine and current; (None, "forged" | "expired") otherwise."""
    if not isinstance(token, str) or not TOKEN_RE.match(token):
        return None, "forged"
    _, body, sig = token.split(".")
    want = hmac.new(_signing_key(), f"{TOKEN_PREFIX}.{body}".encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, want):
        return None, "forged"
    try:
        doc = json.loads(_unb64(body))
        session = AskSession(session_id=str(doc["i"]), expires_at=int(doc["e"]), account=str(doc.get("a") or ""))
    except (ValueError, KeyError, TypeError):
        return None, "forged"
    if session.expires_at <= int(now()):
        return None, "expired"
    return session, ""


class SlidingCounter:
    """N events per key per window, least-recently-used keys dropped past max_keys so a flood of keys cannot grow memory."""

    def __init__(self, max_keys: int = 8192, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._max = max_keys
        self._lock = threading.Lock()
        self._data: "OrderedDict[str, deque[float]]" = OrderedDict()

    def allow(self, key: str, limit: int, span_s: float) -> tuple[bool, int]:
        """Record one event if under `limit` within `span_s`; return (allowed, retry_after_s)."""
        now = self._clock()
        with self._lock:
            window = self._data.pop(key, None)
            if window is None:
                window = deque()
            self._data[key] = window
            while len(self._data) > self._max:
                self._data.popitem(last=False)
            while window and now - window[0] >= span_s:
                window.popleft()
            if len(window) >= limit:
                return False, int(span_s - (now - window[0])) + 1
            window.append(now)
            return True, 0

    def peek_count(self, key: str, span_s: float) -> int:
        now = self._clock()
        with self._lock:
            window = self._data.get(key) or deque()
            return sum(1 for t in window if now - t < span_s)


class DailyBudget:
    """A ceiling on answers per UTC day for the whole route: Redis when the cluster has it (shared by every replica), else memory."""

    def __init__(self, limit: int, *, redis_factory: Optional[Callable[[], Any]] = None, clock: Callable[[], float] = time.time) -> None:
        self.limit = limit
        self._clock = clock
        self._redis_factory = redis_factory
        self._redis: Any = None
        self._retry_at = 0.0
        self._lock = threading.Lock()
        self._mem: dict[str, int] = {}
        self._warned = False

    def _day(self) -> str:
        return time.strftime("%Y%m%d", time.gmtime(self._clock()))

    def _client(self) -> Any:
        if self._redis is not None:
            return self._redis
        if self._redis_factory is None or self._clock() < self._retry_at:
            return None
        try:
            self._redis = self._redis_factory()
        except Exception as exc:  # noqa: BLE001 - no Redis: use memory, try again in a minute
            self._retry_at = self._clock() + 60.0
            if not self._warned:
                self._warned = True
                log.warning("voice_ask: daily budget falls back to per-process memory (%s)", exc)
            return None
        return self._redis

    def take(self) -> tuple[bool, int]:
        """Count one answer; (allowed, used_today). The count includes this one only when it is allowed."""
        day = self._day()
        client = self._client()
        if client is not None:
            key = f"voice-ask:budget:{day}"
            try:
                used = int(client.incr(key))
                if used == 1:
                    client.expire(key, 2 * 86400)
                if used > self.limit:
                    client.decr(key)
                    return False, self.limit
                return True, used
            except Exception as exc:  # noqa: BLE001 - a Redis hiccup must not turn into an open door: fall through to memory
                self._redis = None
                self._retry_at = self._clock() + 30.0
                log.warning("voice_ask: budget Redis error, using memory (%s)", exc)
        with self._lock:
            for old in [d for d in self._mem if d != day]:
                self._mem.pop(old, None)
            used = self._mem.get(day, 0)
            if used >= self.limit:
                return False, used
            self._mem[day] = used + 1
            return True, used + 1


def _redis_open() -> Any:
    from aoep_shared.redis_url import open_redis, runtime_redis_url

    url = runtime_redis_url()
    if not url:
        raise RuntimeError("no redis url")
    return open_redis(url, decode_responses=True)


def app_key_ok(headers: Any) -> bool:
    """Native apps have no browser Origin. They may send X-Salareen-App: <VOICE_ASK_APP_KEY> (a shared value baked into the build).

    It only stands in for the Origin check on SESSION ISSUANCE; every ask still needs a signed session, and every cap still applies.
    Unset key = no app exception: the apps' WebView sends the page's Origin like any browser.
    """
    key = os.environ.get("VOICE_ASK_APP_KEY", "").strip()
    sent = (headers.get("x-salareen-app") or "").strip() if headers else ""
    return bool(key) and bool(sent) and hmac.compare_digest(sent.encode("utf-8"), key.encode("utf-8"))


def ip_label(ip: str) -> str:
    """A short, non-reversible label for logs; raw client addresses are not written."""
    return hashlib.sha256((ip or "unknown").encode("utf-8")).hexdigest()[:8]


class Guard:
    """Everything the two routes share, built once from the environment (tests build their own with fake clocks)."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic, wall: Callable[[], float] = time.time,
                 daily_budget: Optional[int] = None, redis_factory: Optional[Callable[[], Any]] = None) -> None:
        self.wall = wall
        self.issue_per_ip_hour = _int_env("VOICE_ASK_ISSUE_PER_IP_HOUR", 20)
        self.anon_per_ip_day = _int_env("VOICE_ASK_ANON_PER_IP_DAY", 60)
        self.per_account_hour = _int_env("VOICE_ASK_PER_ACCOUNT_HOUR", 300)
        self.issue = SlidingCounter(clock=clock)
        self.accounts = SlidingCounter(clock=clock)
        limit = daily_budget if daily_budget is not None else _int_env("VOICE_ASK_DAILY_BUDGET", 2000)
        self.budget = DailyBudget(limit, redis_factory=redis_factory if redis_factory is not None else _redis_open, clock=wall)

    def allow_issue(self, ip: str, *, anonymous: bool) -> tuple[bool, int]:
        ok, retry = self.issue.allow(f"ip:{ip}", self.issue_per_ip_hour, 3600.0)
        if not ok:
            return False, retry
        if anonymous:
            return self.issue.allow(f"anon:{ip}", self.anon_per_ip_day, 86400.0)
        return True, 0

    def allow_account(self, account: str) -> tuple[bool, int]:
        if not account:
            return True, 0
        return self.accounts.allow(f"acct:{account}", self.per_account_hour, 3600.0)
