"""The Cantonese listening sentences for the stock-voice bake-off.

Three lines Wei (native speaker) reviewed (tts_manifest/translations/yue.json, status ok or fixed), one short, one medium, one long, plus a
tone-contrast line: 詩史試時市事 are six different words that differ only in tone, so a voice with wrong tones says the wrong word.
Only pure Chinese lines are picked (no Latin letters or digits), because an English word inside the line tests something else. The choice is
deterministic (sorted by key), so every machine and every run listens to the same sentences.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
YUE = ROOT / "tts_manifest" / "translations" / "yue.json"
TONE_CONTRAST = "請跟我讀：詩、史、試、時、市、事。"
# (id, category, min chars, max chars)
BANDS = (("Y01", "short", 8, 18), ("Y02", "medium", 24, 48), ("Y03", "long", 60, 120))
_LATIN = re.compile(r"[A-Za-z0-9]")


def reviewed_lines(path: Path = YUE) -> list[tuple[str, str, str]]:
    """[(key, text, status)] of reviewed pure-Chinese lines, sorted by key."""
    items = json.loads(Path(path).read_text(encoding="utf-8")).get("items", {})
    rows = []
    for key in sorted(items):
        it = items[key]
        text = " ".join(str(it.get("text", "")).split())
        if it.get("status") in ("ok", "fixed") and text and not _LATIN.search(text):
            rows.append((key, text, it["status"]))
    return rows


def load(limit: int | None = None, path: Path = YUE) -> list[dict]:
    """Order: short, tone-contrast, medium, long, so --limit 2 gives the two most telling sentences (a short line and the six-tone line)."""
    lines = reviewed_lines(path)
    picked: dict[str, dict] = {}
    for sid, category, lo, hi in BANDS:
        for key, text, status in lines:
            if lo <= len(text) <= hi and all(p["text"] != text for p in picked.values()):
                picked[sid] = {"id": sid, "lang": "yue", "category": category, "text": text, "source": f"yue.json#{key}", "review_status": status}
                break
    tone = {"id": "T01", "lang": "yue", "category": "tone-contrast", "text": TONE_CONTRAST, "source": "Wei's enrollment prompt", "review_status": "ok"}
    rows = [x for x in (picked.get("Y01"), tone, picked.get("Y02"), picked.get("Y03")) if x]
    return rows[:limit] if limit else rows
