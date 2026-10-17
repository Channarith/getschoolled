"""Feedback / review store for dictionary vocabulary + inflection corrections.

Mirrors slang_feedback: confirm | correct | reject events persist under
``AOEP_DICTIONARY_DIR/review/feedback.json`` and are folded back into staging.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .dictionary_corpus import (
    apply_human_status,
    dictionary_dir,
    ensure_layout,
    load_staging,
    save_staging,
)


@dataclass
class DictionaryFeedbackEvent:
    entry_id: str
    lemma: str
    action: str = "confirm"  # confirm | correct | reject
    gloss_en: str = ""
    language: str = "en"
    inflections: Dict[str, str] = field(default_factory=dict)
    note: str = ""
    ts: float = field(default_factory=time.time)


class DictionaryFeedbackStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        root = ensure_layout()
        self.path = path or (root / "review" / "feedback.json")
        self._events: List[DictionaryFeedbackEvent] = []
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
                eid = str(row.get("entry_id", "")).strip()
                lemma = str(row.get("lemma", "")).strip()
                if not eid or not lemma:
                    continue
                infl = row.get("inflections") or {}
                self._events.append(
                    DictionaryFeedbackEvent(
                        entry_id=eid,
                        lemma=lemma,
                        action=str(row.get("action", "confirm")),
                        gloss_en=str(row.get("gloss_en", "")),
                        language=str(row.get("language", "en")),
                        inflections={str(k): str(v) for k, v in infl.items()} if isinstance(infl, dict) else {},
                        note=str(row.get("note", "")),
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
        entry_id: str,
        lemma: str,
        action: str = "confirm",
        gloss_en: str = "",
        language: str = "en",
        inflections: Optional[Dict[str, str]] = None,
        note: str = "",
    ) -> DictionaryFeedbackEvent:
        if action not in {"confirm", "correct", "reject"}:
            raise ValueError("action must be confirm|correct|reject")
        ev = DictionaryFeedbackEvent(
            entry_id=entry_id.strip(),
            lemma=lemma.strip(),
            action=action,
            gloss_en=(gloss_en or "").strip(),
            language=language or "en",
            inflections=dict(inflections or {}),
            note=(note or "").strip(),
        )
        if not ev.entry_id or not ev.lemma:
            raise ValueError("entry_id and lemma are required")
        self._events.append(ev)
        self._save()
        return ev

    def apply_to_staging(self, language: str = "en", root: Optional[Path] = None) -> int:
        """Replay latest non-reject/confirm/correct onto staging. Returns updates applied."""
        entries = load_staging(root, language)
        if not entries:
            return 0
        # Latest event per entry_id wins.
        latest: Dict[str, DictionaryFeedbackEvent] = {}
        for ev in self._events:
            latest[ev.entry_id] = ev
        updated = 0
        for eid, ev in latest.items():
            status = {
                "confirm": "approved",
                "correct": "approved",
                "reject": "rejected",
            }.get(ev.action, "queued")
            before = {e.id: e.review_status for e in entries}
            entries = apply_human_status(
                entries,
                entry_id_value=eid,
                status=status,
                gloss_en=ev.gloss_en,
                inflections=ev.inflections or None,
                notes=ev.note,
            )
            after = {e.id: e.review_status for e in entries}
            if before.get(eid) != after.get(eid) or ev.gloss_en or ev.inflections:
                updated += 1
        save_staging(entries, root, language)
        return updated

    def recent(self, limit: int = 25) -> List[dict[str, Any]]:
        rows = self._events[-max(1, limit) :]
        return [asdict(e) for e in reversed(rows)]

    def stats(self) -> dict[str, Any]:
        by_action: Dict[str, int] = {}
        for e in self._events:
            by_action[e.action] = by_action.get(e.action, 0) + 1
        return {
            "events": len(self._events),
            "by_action": by_action,
            "store": str(self.path),
            "dictionary_dir": str(dictionary_dir()),
        }


_STORE: Optional[DictionaryFeedbackStore] = None


def default_dictionary_feedback_store() -> DictionaryFeedbackStore:
    global _STORE
    if _STORE is None:
        _STORE = DictionaryFeedbackStore()
    return _STORE
