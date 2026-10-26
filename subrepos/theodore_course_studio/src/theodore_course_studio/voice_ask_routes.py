"""POST /api/studio/voice/ask: a grounded text answer for any lesson, for every voice engine.

The xAI voice agent answered learner questions from the lesson text; the Salane engine (edge-tts, Sage, company voices) only spoke.
This route gives every engine the same brain: the caller sends the question and the lesson text it is standing on, and gets a short
answer back as TEXT, which the page then speaks in the voice the learner picked. It reuses CourseStudioVoiceAgent.respond, so the
provider order (SuperGrok, shared agent, xAI chat, local model, offline fallback) and the course scoping are the same as for Talk.

Safe by construction: no login is needed (the demo and On the Go are anonymous), so it is bounded in layers. A caller first gets a
SERVER-ISSUED signed session (POST /api/studio/voice/session, itself limited per client address) and every ask must carry it; asks are
capped per session, per client address, per signed-in account and by a global daily budget; another site's page is refused; every input
and the answer are length-bounded; and the lesson text it is given is never echoed or logged. See voice_ask_guard.py.
"""
from __future__ import annotations

import os
import re
import threading
import time
import urllib.parse
from collections import OrderedDict, deque
from typing import Any, Callable, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from . import voice_ask_guard as _vg
from .caller_claims import authorization_from, verified_caller

router = APIRouter()

SESSION_ID_RE = _vg.TOKEN_RE   # kept under the old name: the "session id" field now carries a server-issued signed session
MAX_ANSWER_CHARS = 1200
MAX_QUESTION_CHARS = 500
MAX_CONTEXT_CHARS = 8000
MAX_TITLE_CHARS = 200


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, "") or default))
    except ValueError:
        return default


class AskLimiter:
    """Sliding-window caps: N questions a minute and M a session (an hour window) per learner session, and a ceiling per client address.

    Memory is bounded: the least recently used keys are dropped past `max_keys`, so a flood of made-up session ids cannot grow it.
    """

    def __init__(self, per_minute: int = 6, per_session: int = 40, per_ip_hour: int = 120, max_keys: int = 4096,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.per_minute = per_minute
        self.per_session = per_session
        self.per_ip_hour = per_ip_hour
        self.max_keys = max_keys
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: "OrderedDict[str, deque[float]]" = OrderedDict()
        self._ips: "OrderedDict[str, deque[float]]" = OrderedDict()

    @staticmethod
    def _trim(window: "deque[float]", now: float, span: float) -> None:
        while window and now - window[0] >= span:
            window.popleft()

    def _touch(self, table: "OrderedDict[str, deque[float]]", key: str) -> "deque[float]":
        window = table.pop(key, None)
        if window is None:
            window = deque()
        table[key] = window
        while len(table) > self.max_keys:
            table.popitem(last=False)
        return window

    def check(self, session_id: str, ip: str) -> tuple[bool, str, int]:
        """(allowed, reason, retry_after_s). Records the question only when it is allowed."""
        now = self._clock()
        with self._lock:
            sess = self._touch(self._sessions, session_id)
            addr = self._touch(self._ips, ip or "unknown")
            self._trim(sess, now, 3600.0)
            self._trim(addr, now, 3600.0)
            if len(addr) >= self.per_ip_hour:
                return False, "address", int(3600 - (now - addr[0])) + 1
            if len(sess) >= self.per_session:
                return False, "session", int(3600 - (now - sess[0])) + 1
            recent = [t for t in sess if now - t < 60.0]
            if len(recent) >= self.per_minute:
                return False, "rate", int(60 - (now - recent[0])) + 1
            sess.append(now)
            addr.append(now)
            return True, "", 0


_limiter = AskLimiter(
    per_minute=_int_env("VOICE_ASK_PER_MIN", 6),
    per_session=_int_env("VOICE_ASK_PER_SESSION", 40),
    per_ip_hour=_int_env("VOICE_ASK_PER_IP_HOUR", 120),
)


def limiter() -> AskLimiter:
    return _limiter


_guard = _vg.Guard()


def guard() -> "_vg.Guard":
    return _guard


def set_guard(new: "_vg.Guard") -> None:
    """Tests swap in a guard with fake clocks and a tiny budget."""
    global _guard
    _guard = new


STATS: dict[str, int] = {}


def _note(outcome: str, ip: str = "", session: Optional["_vg.AskSession"] = None) -> None:
    """Counts and a log line per outcome: never the question, the lesson text or the raw client address."""
    STATS[outcome] = STATS.get(outcome, 0) + 1
    _vg.log.info("voice_ask outcome=%s kind=%s ip=%s", outcome, "none" if session is None else ("anon" if session.anonymous else "account"),
                 _vg.ip_label(ip))


class VoiceAskRequest(BaseModel):
    session_id: str = Field(..., description="The signed session returned by POST /api/studio/voice/session (not a client-made id)")
    question: str = Field(..., description="What the learner said or a ready-made prompt such as 'explain this more simply'")
    lesson_context: str = Field("", description="The lesson text the learner is on; the answer is grounded in it")
    language: str = "en"
    course_title: str = ""


def _same_origin(request: Request) -> None:
    """Browser callers must come from this site. A browser always sends Origin on a POST; a request with neither Origin nor a
    same-site Sec-Fetch-Site is a script, which is refused unless it carries the native-app header (see voice_ask_guard.app_key_ok)."""
    origin = (request.headers.get("origin") or "").strip()
    if origin:
        host = (request.headers.get("host") or "").split(",")[0].strip()
        if urllib.parse.urlsplit(origin).netloc != host:
            raise HTTPException(status_code=403, detail="That request did not come from this site.")
        return
    site = (request.headers.get("sec-fetch-site") or "").strip().lower()
    if site in ("same-origin", "same-site", "none") or _vg.app_key_ok(request.headers):
        return
    raise HTTPException(status_code=403, detail="That request did not come from this site.")


def _client_ip(request: Request) -> str:
    try:
        from aoep_shared.client_ip import client_ip

        peer = request.client.host if request.client else None
        return client_ip(dict(request.headers), peer) or "unknown"
    except Exception:  # noqa: BLE001 - a missing helper must not turn into an open door: all unknowns share one bucket
        return "unknown"


def _agent() -> Any:
    from .voice_agent import get_voice_agent

    return get_voice_agent()


def clean_context(title: str, context: str) -> str:
    """Bounded, tag-free lesson text for the model. Control characters and runs of blank lines are dropped."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", context or "")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()[:MAX_CONTEXT_CHARS]
    head = (title or "").strip()[:MAX_TITLE_CHARS]
    return f"{head}\n\n{text}".strip() if head else text


def _seconds_to_utc_midnight() -> int:
    now = time.gmtime(_guard.wall())
    return max(60, min(3600, 86400 - (now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec)))


@router.post("/api/studio/voice/session")
def voice_session(request: Request, authorization: str = Header(default="")) -> dict[str, Any]:
    """Issue a signed ask session. Signed-in callers get a longer one bound to their verified account; anonymous callers get one that
    lasts about the free sample, and the number issued per client address is limited so ids cannot be minted in bulk."""
    _same_origin(request)
    ip = _client_ip(request)
    auth = authorization_from(authorization, request.cookies)
    caller = verified_caller(auth) if auth else None
    account = str((caller or {}).get("id") or (caller or {}).get("email") or "")
    ok, retry = _guard.allow_issue(ip, anonymous=not account)
    if not ok:
        _note("issue_limited", ip)
        raise HTTPException(status_code=429, detail={"reason": "issue", "retry_after_s": retry}, headers={"Retry-After": str(retry)})
    token, session = _vg.issue_token(account, now=_guard.wall)
    _note("issued", ip, session)
    return {"session": token, "expires_in": session.expires_at - int(_guard.wall()), "signed_in": bool(account)}


@router.post("/api/studio/voice/ask")
def voice_ask(req: VoiceAskRequest, request: Request) -> dict[str, Any]:
    _same_origin(request)
    ip = _client_ip(request)
    session, why = _vg.verify_token(req.session_id or "", now=_guard.wall)
    if session is None:
        _note(why or "forged", ip)
        raise HTTPException(status_code=401, detail={"reason": why or "forged", "message": "Start a new session and ask again."})
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="Say or type a question.")
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(status_code=422, detail="That question is too long.")
    ok, reason, retry = _limiter.check(session.session_id, ip)
    if not ok:
        _note(f"limited_{reason}", ip, session)
        raise HTTPException(status_code=429, detail={"reason": reason, "retry_after_s": retry}, headers={"Retry-After": str(retry)})
    ok, retry = _guard.allow_account(session.account)
    if not ok:
        _note("limited_account", ip, session)
        raise HTTPException(status_code=429, detail={"reason": "account", "retry_after_s": retry}, headers={"Retry-After": str(retry)})
    ok, _used = _guard.budget.take()
    if not ok:
        retry = _seconds_to_utc_midnight()
        _note("limited_budget", ip, session)
        raise HTTPException(status_code=429, detail={"reason": "budget", "retry_after_s": retry}, headers={"Retry-After": str(retry)})
    context = clean_context(req.course_title, req.lesson_context)
    turn = _agent().respond(
        session_id=f"ask:{session.session_id}",
        learner_message=question,
        language_code=(req.language or "en")[:12],
        lesson_context=context,
        scope_to_course=bool(context),
    )
    _note("answered", ip, session)
    return {
        "answer": (turn.message or "")[:MAX_ANSWER_CHARS],
        "language": turn.language_code,
        "provider": turn.provider,
        "fallback_used": bool(turn.fallback_used),
    }
