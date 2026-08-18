"""Line-by-line music learning sessions (pause / repeat / continuous)."""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .catalog import Catalog, Song, SongLine, meaning_for_line


class SessionMode(str, Enum):
    LINE_PAUSE = "line_pause"  # play one line, wait for continue
    CONTINUOUS = "continuous"  # play through without pause gate
    REPEAT = "repeat"  # stay on current line


class SessionState(str, Enum):
    READY = "ready"
    PLAYING = "playing"
    PAUSED = "paused"
    DONE = "done"


class MusicSession(BaseModel):
    session_id: str
    song_id: str
    mode: SessionMode = SessionMode.LINE_PAUSE
    state: SessionState = SessionState.READY
    line_index: int = 0  # 0-based
    meaning_language: str = "en"
    created_ms: int = 0
    events: list[dict[str, Any]] = Field(default_factory=list)

    def snapshot(self, song: Song) -> dict[str, Any]:
        line = song.lines[self.line_index] if song.lines else None
        return {
            "session_id": self.session_id,
            "song_id": self.song_id,
            "mode": self.mode.value,
            "state": self.state.value,
            "line_index": self.line_index,
            "line_no": (line.line_no if line else 0),
            "line_count": song.line_count,
            "current_line": (line.model_dump() if line else None),
            "meaning_language": self.meaning_language,
            "events": list(self.events[-20:]),
        }


class SessionStore:
    # Sessions are in-memory and created by unauthenticated traffic — bound the
    # registry so a long-lived process doesn't grow forever.
    MAX_SESSIONS = 1000

    def __init__(self, catalog: Optional[Catalog] = None) -> None:
        self.catalog = catalog or Catalog()
        self._sessions: dict[str, MusicSession] = {}

    def start(
        self,
        song_id: str,
        *,
        mode: SessionMode = SessionMode.LINE_PAUSE,
        meaning_language: str = "en",
    ) -> dict[str, Any]:
        song = self.catalog.get(song_id)
        if not song.lines:
            raise ValueError(f"Song '{song_id}' has no lines")
        if len(self._sessions) >= self.MAX_SESSIONS:
            # Evict the oldest sessions (dicts keep insertion order).
            for old_sid in list(self._sessions)[: len(self._sessions) // 2]:
                self._sessions.pop(old_sid, None)
        sid = uuid.uuid4().hex[:12]
        sess = MusicSession(
            session_id=sid,
            song_id=song_id,
            mode=mode,
            state=SessionState.READY,
            line_index=0,
            meaning_language=meaning_language.strip().lower() or "en",
            created_ms=int(time.time() * 1000),
        )
        self._sessions[sid] = sess
        return sess.snapshot(song)

    def get(self, session_id: str) -> MusicSession:
        sess = self._sessions.get(session_id)
        if sess is None:
            raise KeyError(session_id)
        return sess

    def _song(self, sess: MusicSession) -> Song:
        return self.catalog.get(sess.song_id)

    def play(self, session_id: str) -> dict[str, Any]:
        sess = self.get(session_id)
        song = self._song(sess)
        line = song.lines[sess.line_index]
        sess.state = SessionState.PLAYING
        evt = {
            "type": "play",
            "line_no": line.line_no,
            "text": line.text,
            "tts_text": line.tts_text or line.text,
            "mode": sess.mode.value,
        }
        sess.events.append(evt)
        if sess.mode is SessionMode.CONTINUOUS:
            # Continuous: auto-advance after play without requiring pause.
            if sess.line_index + 1 < song.line_count:
                sess.line_index += 1
                sess.state = SessionState.READY
            else:
                sess.state = SessionState.DONE
        else:
            # LINE_PAUSE / REPEAT: pause after the line so learner can ask meaning.
            sess.state = SessionState.PAUSED
        return {**sess.snapshot(song), "last_event": evt}

    def pause(self, session_id: str) -> dict[str, Any]:
        sess = self.get(session_id)
        song = self._song(sess)
        sess.state = SessionState.PAUSED
        sess.events.append({"type": "pause", "line_index": sess.line_index})
        return sess.snapshot(song)

    def repeat(self, session_id: str) -> dict[str, Any]:
        sess = self.get(session_id)
        song = self._song(sess)
        sess.mode = SessionMode.REPEAT
        sess.state = SessionState.PLAYING
        line = song.lines[sess.line_index]
        evt = {
            "type": "repeat",
            "line_no": line.line_no,
            "text": line.text,
            "tts_text": line.tts_text or line.text,
        }
        sess.events.append(evt)
        sess.state = SessionState.PAUSED
        return {**sess.snapshot(song), "last_event": evt}

    def continue_(self, session_id: str) -> dict[str, Any]:
        """Advance past pause (skip-pause continue)."""
        sess = self.get(session_id)
        song = self._song(sess)
        if sess.line_index + 1 >= song.line_count:
            sess.state = SessionState.DONE
            sess.events.append({"type": "done"})
            return sess.snapshot(song)
        sess.line_index += 1
        sess.mode = SessionMode.LINE_PAUSE
        sess.state = SessionState.READY
        sess.events.append({"type": "continue", "line_index": sess.line_index})
        return sess.snapshot(song)

    def set_continuous(self, session_id: str, enabled: bool = True) -> dict[str, Any]:
        sess = self.get(session_id)
        song = self._song(sess)
        sess.mode = SessionMode.CONTINUOUS if enabled else SessionMode.LINE_PAUSE
        return sess.snapshot(song)

    def meaning(
        self, session_id: str, *, target_lang: str = "", line_no: Optional[int] = None
    ) -> dict[str, Any]:
        sess = self.get(session_id)
        song = self._song(sess)
        if line_no is not None:
            matches = [ln for ln in song.lines if ln.line_no == line_no]
            if not matches:
                raise ValueError(f"No line_no {line_no}")
            line: SongLine = matches[0]
        else:
            line = song.lines[sess.line_index]
        lang = (target_lang or sess.meaning_language or "en").strip().lower()
        gloss = meaning_for_line(line, lang)
        sess.events.append(
            {"type": "meaning", "line_no": line.line_no, "target_language": lang}
        )
        return {
            "session_id": session_id,
            "song_id": song.song_id,
            "line": line.model_dump(),
            "meaning": gloss,
        }
