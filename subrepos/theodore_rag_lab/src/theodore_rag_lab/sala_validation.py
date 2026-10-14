"""Hear-and-correct checks for the Sala voice agent.

Each check records what Sala said for a dialect and whether that line was
accepted or replaced. A saved correction is what Sala says the next time the
same prompt is asked in that dialect, and it is also appended as a training row.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_STORE: "SalaValidation | None" = None


def _root() -> Path:
    raw = os.environ.get("AOEP_SALA_VALIDATION", "").strip()
    if raw:
        return Path(raw)
    return Path.home() / ".cache" / "aoep" / "sala_validation"


def _key(dialect: str, heard: str) -> str:
    return f"{(dialect or '').strip().lower()}|{(heard or '').strip().lower()}"


class SalaValidation:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or _root()
        self.path = self.root / "checks.json"
        self.training_path = self.root / "sala_voice_training.jsonl"
        self._checks: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        self._checks = []
        try:
            if not self.path.is_file():
                return
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            rows = raw if isinstance(raw, list) else raw.get("checks", [])
            self._checks = [row for row in rows if isinstance(row, dict)]
        except (OSError, json.JSONDecodeError):
            self._checks = []

    def _save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {"checks": self._checks[-2000:]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def correction_for(self, dialect: str, heard: str) -> str:
        """Latest corrected line for this dialect and prompt, if one was saved."""
        want = _key(dialect, heard)
        for row in reversed(self._checks):
            if row.get("action") != "correct":
                continue
            if _key(str(row.get("dialect", "")), str(row.get("heard", ""))) == want:
                text = str(row.get("corrected") or "").strip()
                if text:
                    return text
        return ""

    def record(
        self,
        *,
        action: str,
        heard: str,
        reply: str,
        corrected: str = "",
        dialect: str = "",
        language: str = "en",
        voice: str = "",
    ) -> dict[str, Any]:
        kind = (action or "").strip().lower()
        if kind not in {"pass", "correct"}:
            raise ValueError("action must be pass or correct")
        spoken = (reply or "").strip()
        fixed = (corrected or "").strip()
        if kind == "correct" and not fixed:
            raise ValueError("corrected text is required")
        if not spoken and not fixed:
            raise ValueError("reply text is required")
        row = {
            "action": kind,
            "heard": (heard or "").strip(),
            "reply": spoken,
            "corrected": fixed if kind == "correct" else spoken,
            "dialect": (dialect or "").strip(),
            "language": (language or "en").strip() or "en",
            "voice": (voice or "").strip(),
            "ts": time.time(),
        }
        self._checks.append(row)
        self._save()
        self._append_training(row)
        return {"check": row, "validation": self.summary()}

    def _append_training(self, row: dict[str, Any]) -> None:
        target = row["corrected"] if row["action"] == "correct" else row["reply"]
        example = {
            "dialect": row["dialect"],
            "language": row["language"],
            "voice": row["voice"],
            "prompt": row["heard"],
            "response": target,
            "verdict": row["action"],
        }
        self.root.mkdir(parents=True, exist_ok=True)
        with self.training_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(example, ensure_ascii=False) + "\n")

    def summary(self, limit: int = 8) -> dict[str, Any]:
        passed = sum(1 for row in self._checks if row.get("action") == "pass")
        corrected = sum(1 for row in self._checks if row.get("action") == "correct")
        checks = len(self._checks)
        recent = list(reversed(self._checks[-max(1, limit) :]))
        return {
            "checks": checks,
            "passed": passed,
            "corrected": corrected,
            "pass_rate": round(passed / checks, 3) if checks else 0.0,
            "recent": recent,
            "store": str(self.path),
            "training": str(self.training_path),
        }


def default_validation() -> SalaValidation:
    global _STORE
    if _STORE is None:
        _STORE = SalaValidation()
    return _STORE


def reset_validation() -> None:
    """Test helper. The next lookup builds a store from the current env path."""
    global _STORE
    _STORE = None
