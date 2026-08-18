"""xAI Grok voice agent client for AOEP.

Wraps xAI's OpenAI-compatible REST API (https://api.x.ai/v1) for:
- Text responses (default model grok-4.3; override with XAI_MODEL)
- Vision analysis of webcam frames (grok-2-vision-1212)
- Persona-aware teaching responses as Theodore AI

The xAI API is fully OpenAI-compatible so this uses the same stdlib urllib
pattern as ``elevenlabs_tts.py`` — no extra dependencies.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

XAI_DEFAULT_BASE_URL = "https://api.x.ai/v1"
XAI_DEFAULT_MODEL = "grok-4.3"
XAI_VISION_MODEL = "grok-2-vision-1212"

# Theodore's persona system prompt (injected once per session).
THEODORE_SYSTEM_PROMPT = (
    "You are Theodore, the AI teaching assistant for Salareen — an adaptive online "
    "education platform. You are calm, warm, encouraging, and direct. You adapt to "
    "each learner: beginner-friendly analogies for novices, technical depth for "
    "advanced students. You celebrate effort, not just answers. Keep responses "
    "concise (1–3 sentences) unless the student asks for detail. When you notice "
    "the student is absent or distracted, gently invite them back. Never scold; "
    "always motivate. You support both solo self-study sessions and group classes "
    "where multiple students attend simultaneously."
)

# Prompt used when analysing a webcam frame for engagement feedback.
FRAME_ANALYSIS_PROMPT = (
    "Briefly describe the student's engagement (1 sentence). "
    "Note if they appear focused, distracted, confused, or absent. "
    "Suggest one concrete encouragement for Theodore to say. "
    "Do not include any personal biometric details or identity guesses."
)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class GrokMessage:
    role: str      # "system" | "user" | "assistant"
    content: Any   # str or list[dict] for vision


@dataclass
class GrokResponse:
    text: str
    model: str
    usage_prompt_tokens: int
    usage_completion_tokens: int
    latency_ms: float


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def xai_available(api_key: str) -> bool:
    """Return True when the xAI API key is present and non-empty."""
    return bool(api_key and api_key.strip())


# ---------------------------------------------------------------------------
# Low-level HTTP (isolated for mocking in tests)
# ---------------------------------------------------------------------------

def _http_post(url: str, payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """POST JSON to xAI and return the parsed response dict.

    Raises ``urllib.error.HTTPError`` on 4xx/5xx or ``NotImplementedError``
    when the API key is absent.
    """
    if not xai_available(api_key):
        raise NotImplementedError(
            "XAI_API_KEY is not set. Set it to enable the xAI Grok voice agent."
        )
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


# ---------------------------------------------------------------------------
# Voice agent
# ---------------------------------------------------------------------------

class GrokVoiceAgent:
    """Theodore-persona voice agent backed by xAI Grok.

    One instance per teaching session. Maintains a lightweight conversation
    history so follow-up questions retain context (capped at ``max_history``
    turns to keep token usage bounded).

    Parameters
    ----------
    api_key:
        xAI API key (XAI_API_KEY env).
    base_url:
        xAI API base URL (defaults to https://api.x.ai/v1).
    model:
        Text model slug (default grok-2-1212).
    vision_model:
        Vision model slug (default grok-2-vision-1212).
    session_context:
        Optional dict with session metadata (class_type, lesson_title,
        student_name) to inject into the system prompt.
    max_history:
        Maximum number of user/assistant turn pairs to retain.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = XAI_DEFAULT_BASE_URL,
        model: str = XAI_DEFAULT_MODEL,
        vision_model: str = XAI_VISION_MODEL,
        session_context: Optional[Dict[str, str]] = None,
        max_history: int = 10,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._vision_model = vision_model
        self._max_history = max_history
        self._history: List[GrokMessage] = []
        self._system = self._build_system_prompt(session_context or {})

    # ---- public API ------------------------------------------------------- #

    def respond_to_query(
        self,
        student_query: str,
        *,
        language: str = "en",
    ) -> GrokResponse:
        """Generate a teaching response to a student's text or voice query.

        Parameters
        ----------
        student_query:
            The student's question or statement (transcribed from speech or typed).
        language:
            BCP-47 language tag; appended to the system prompt so Theodore
            responds in the student's language when non-English.
        """
        system = self._system
        if language and language.lower() not in ("en", "en-us", "en-gb"):
            system += f" Respond in language: {language}."

        messages = self._build_messages(
            system=system,
            user_content=student_query,
        )
        return self._call(messages, model=self._model)

    def respond_to_frame(
        self,
        frame_bytes: bytes,
        *,
        presence_state: str = "present_face",
        face_count: int = 0,
        attention: float = 0.0,
    ) -> GrokResponse:
        """Analyse a webcam frame and generate an engagement-aware response.

        The raw frame is sent to Grok Vision (grok-2-vision-1212) so Theodore
        can comment on visible engagement cues without needing the perception
        service's structured output. The frame is base64-encoded in the request;
        no biometric identification is requested.

        Parameters
        ----------
        frame_bytes:
            JPEG or PNG bytes of the current webcam frame.
        presence_state:
            PresenceState string from the presence tracker.
        face_count:
            Number of faces detected (from the perception service).
        attention:
            Average attention score (0..1) from the perception service.
        """
        b64 = base64.b64encode(frame_bytes).decode()
        context_hint = (
            f"[Session context: presence={presence_state}, "
            f"face_count={face_count}, attention_score={attention:.2f}]"
        )
        user_content = [
            {
                "type": "text",
                "text": f"{context_hint}\n{FRAME_ANALYSIS_PROMPT}",
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            },
        ]
        messages = self._build_messages(
            system=self._system,
            user_content=user_content,
        )
        return self._call(messages, model=self._vision_model)

    def generate_absence_prompt(
        self,
        absence_duration_s: float,
        *,
        lesson_title: str = "",
    ) -> GrokResponse:
        """Generate a gentle prompt to invite the student back after absence.

        Parameters
        ----------
        absence_duration_s:
            How long the student has been absent (seconds).
        lesson_title:
            Current lesson title for context (optional).
        """
        lesson_ctx = f" We're in the middle of '{lesson_title}'." if lesson_title else ""
        msg = (
            f"The student has been away for {absence_duration_s:.0f} seconds.{lesson_ctx} "
            "Write a single warm, non-judgmental sentence to invite them back to the lesson."
        )
        messages = self._build_messages(system=self._system, user_content=msg)
        # Do NOT pollute conversation history with absence prompts (they are
        # context-specific one-shots, not part of the Q&A thread). Restore the
        # exact prior history — _call trims at capacity, so popping only the
        # new pair used to silently delete the oldest real Q&A exchange.
        prior_history = list(self._history)
        resp = self._call(messages, model=self._model)
        self._history = prior_history
        return resp

    def clear_history(self) -> None:
        """Clear the conversation history (e.g. when the lesson topic changes)."""
        self._history = []

    # ---- internal --------------------------------------------------------- #

    def _build_system_prompt(self, ctx: Dict[str, str]) -> str:
        parts = [THEODORE_SYSTEM_PROMPT]
        if ctx.get("class_type") == "group":
            parts.append(
                "This is a GROUP class; multiple students may be visible. "
                "Address the group collectively unless singling someone out is warranted."
            )
        elif ctx.get("class_type") == "solo":
            parts.append("This is a SOLO session; address the single student directly.")
        if ctx.get("lesson_title"):
            parts.append(f"Current lesson: {ctx['lesson_title']}.")
        if ctx.get("student_name"):
            parts.append(f"Student name: {ctx['student_name']}.")
        return " ".join(parts)

    def _build_messages(
        self, *, system: str, user_content: Any
    ) -> List[Dict[str, Any]]:
        msgs: List[Dict[str, Any]] = [{"role": "system", "content": system}]
        for h in self._history[-self._max_history * 2:]:
            msgs.append({"role": h.role, "content": h.content})
        msgs.append({"role": "user", "content": user_content})
        return msgs

    def _call(
        self, messages: List[Dict[str, Any]], *, model: str
    ) -> GrokResponse:
        t0 = time.monotonic()
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 300,
            "temperature": 0.7,
            "stream": False,
        }
        data = _http_post(
            f"{self._base_url}/chat/completions",
            payload,
            self._api_key,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        choice = data["choices"][0]["message"]
        text = choice.get("content") or ""
        usage = data.get("usage", {})
        resp = GrokResponse(
            text=text.strip(),
            model=data.get("model", model),
            usage_prompt_tokens=usage.get("prompt_tokens", 0),
            usage_completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=round(latency_ms, 1),
        )
        # Append to rolling history (text-only content for efficiency).
        user_text = (
            messages[-1]["content"]
            if isinstance(messages[-1]["content"], str)
            else "[frame]"
        )
        self._history.append(GrokMessage(role="user", content=user_text))
        self._history.append(GrokMessage(role="assistant", content=text))
        if len(self._history) > self._max_history * 2:
            self._history = self._history[-(self._max_history * 2):]
        return resp
