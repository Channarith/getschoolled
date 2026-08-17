"""Feedback learning for slang/idioms — corrections reinforce the lexicon.

Learners (or lab operators) can confirm, correct, or reject a phrase meaning.
Accepted corrections are persisted under ``AOEP_FEEDBACK_DIR`` (default
``~/.cache/aoep/slang_feedback``) and folded into :func:`aoep_shared.slang.default_lexicon`
so regurgitation drills and Tutor normalization mature over time.

Offline, dependency-free, and safe: corrupt files are ignored.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .slang import SlangEntry


def _feedback_dir() -> Path:
    raw = os.environ.get("AOEP_FEEDBACK_DIR", "").strip()
    if raw:
        return Path(raw)
    return Path.home() / ".cache" / "aoep" / "slang_feedback"


def _store_path() -> Path:
    return _feedback_dir() / "learned.json"


@dataclass
class FeedbackEvent:
    """One learner/operator feedback action."""

    phrase: str
    meaning: str
    language: str = "en"
    region: str = "global"
    kind: str = "idiom"
    action: str = "confirm"  # confirm | correct | reject
    dialect: str = ""
    note: str = ""
    weight: float = 1.0
    ts: float = field(default_factory=time.time)

    def to_entry(self) -> SlangEntry:
        return SlangEntry(
            phrase=self.phrase.strip(),
            meaning=self.meaning.strip(),
            language=self.language or "en",
            region=self.region or "global",
            kind=self.kind or "idiom",
            register="learned",
        )


class FeedbackStore:
    """JSON-backed store of slang feedback used to grow the dictionary."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or _store_path()
        self._events: List[FeedbackEvent] = []
        self._load()

    def _load(self) -> None:
        self._events = []
        try:
            if not self.path.is_file():
                return
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            rows = raw if isinstance(raw, list) else raw.get("events", [])
            for row in rows:
                if not isinstance(row, dict):
                    continue
                phrase = str(row.get("phrase", "")).strip()
                meaning = str(row.get("meaning", "")).strip()
                if not phrase or not meaning:
                    continue
                self._events.append(
                    FeedbackEvent(
                        phrase=phrase,
                        meaning=meaning,
                        language=str(row.get("language", "en")),
                        region=str(row.get("region", "global")),
                        kind=str(row.get("kind", "idiom")),
                        action=str(row.get("action", "confirm")),
                        dialect=str(row.get("dialect", "")),
                        note=str(row.get("note", "")),
                        weight=float(row.get("weight", 1.0) or 1.0),
                        ts=float(row.get("ts", time.time())),
                    )
                )
        except Exception:
            self._events = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"events": [asdict(e) for e in self._events[-5000:]]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def record(
        self,
        *,
        phrase: str,
        meaning: str,
        language: str = "en",
        region: str = "global",
        kind: str = "idiom",
        action: str = "confirm",
        dialect: str = "",
        note: str = "",
        weight: float = 1.0,
    ) -> FeedbackEvent:
        ev = FeedbackEvent(
            phrase=phrase.strip(),
            meaning=meaning.strip(),
            language=language or "en",
            region=region or "global",
            kind=kind or "idiom",
            action=action or "confirm",
            dialect=dialect or "",
            note=note or "",
            weight=max(0.1, float(weight or 1.0)),
        )
        if not ev.phrase or not ev.meaning:
            raise ValueError("phrase and meaning are required")
        if ev.action not in {"confirm", "correct", "reject"}:
            raise ValueError("action must be confirm|correct|reject")
        self._events.append(ev)
        self._save()
        # Invalidate slang singleton so learned entries are picked up.
        try:
            from . import slang as slang_mod

            slang_mod._default = None
            slang_mod._default_fingerprint = None
        except Exception:
            pass
        return ev

    def learned_entries(self) -> List[SlangEntry]:
        """Aggregate non-rejected feedback into slang entries (latest meaning wins)."""
        rejected = {
            (e.language, e.region, e.phrase.lower())
            for e in self._events
            if e.action == "reject"
        }
        latest: Dict[tuple, FeedbackEvent] = {}
        for e in self._events:
            if e.action == "reject":
                continue
            key = (e.language, e.region, e.phrase.lower())
            if key in rejected:
                continue
            latest[key] = e
        return [e.to_entry() for e in latest.values()]

    def stats(self) -> dict[str, Any]:
        by_action: Dict[str, int] = {}
        by_region: Dict[str, int] = {}
        for e in self._events:
            by_action[e.action] = by_action.get(e.action, 0) + 1
            by_region[e.region] = by_region.get(e.region, 0) + 1
        return {
            "events": len(self._events),
            "learned_entries": len(self.learned_entries()),
            "by_action": by_action,
            "by_region": by_region,
            "store": str(self.path),
        }

    def recent(self, limit: int = 25) -> List[dict[str, Any]]:
        rows = self._events[-max(1, limit) :]
        return [asdict(e) for e in reversed(rows)]


_STORE: Optional[FeedbackStore] = None


def default_feedback_store() -> FeedbackStore:
    global _STORE
    if _STORE is None:
        _STORE = FeedbackStore()
    return _STORE


def learned_slang_entries() -> List[SlangEntry]:
    return default_feedback_store().learned_entries()
