"""Turn modality ratings into a page mix for the course being taught.

Ratings are weights, not percentages. Delivery context removes ineligible
formats first. Shares under half a page are dropped, the rest are scaled
again, and integer pages are assigned with the largest-remainder method so
the counts add up to the course length.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

MODALITY_ORDER: Tuple[str, ...] = (
    "tutoring",
    "gaming",
    "reading",
    "presentation",
    "video",
    "live_teacher",
)

MODALITY_LABELS: Dict[str, str] = {
    "tutoring": "Tutoring",
    "gaming": "Gaming",
    "reading": "Reading",
    "presentation": "Presentation",
    "video": "Video",
    "live_teacher": "Live teacher",
}

# Storyboard primary_style vocabulary used by the generic scene builder.
PROFILE_MODE: Dict[str, str] = {
    "tutoring": "auditory",
    "live_teacher": "auditory",
    "reading": "reading",
    "presentation": "visual",
    "video": "visual",
    "gaming": "hands_on",
}

CONTEXTS: Tuple[str, ...] = ("course", "live_group", "on_the_go", "video_game")

_INELIGIBLE: Dict[str, frozenset] = {
    "course": frozenset(),
    "live_group": frozenset({"tutoring"}),
    "on_the_go": frozenset({"video"}),
    "video_game": frozenset({"reading", "presentation", "video", "live_teacher"}),
}

_CONTEXT_ALIASES = {
    "course": "course",
    "in_app": "course",
    "solo": "course",
    "live_group": "live_group",
    "group": "live_group",
    "live": "live_group",
    "on_the_go": "on_the_go",
    "audio": "on_the_go",
    "drive": "on_the_go",
    "video_game": "video_game",
    "game": "video_game",
    "arcade": "video_game",
}

_CONTEXT_DETAIL = {
    "course": "in-app course",
    "live_group": "live group class",
    "on_the_go": "on the go",
    "video_game": "video game",
}

_REASON_TEXT = {
    "below_half_page": "less than half a page",
    "live_group": "not available in this setting: live group",
    "on_the_go": "not available in this setting: on the go",
    "video_game": "not available in this setting: video game",
}

_AUDIO_MODES = frozenset({"audio", "drive", "drive-mode", "drive_mode", "listen"})
_GAME_TOKENS = frozenset({
    "game", "games", "arcade", "gaming", "videogame", "video_game", "video-game",
})


def profile_mode_for(modality: str) -> str:
    return PROFILE_MODE.get((modality or "").strip().lower(), "mixed")


def modality_activity(modality: str, title: str) -> str:
    """The line a learner does on a page of this format."""
    topic = (title or "this idea").strip() or "this idea"
    prompts = {
        "tutoring": f"Tutor: explain {topic} in your own words, then answer one check question.",
        "gaming": f"Game: play a short challenge about {topic} and make the call.",
        "reading": f"Reading: read the passage on {topic} and restate the key line.",
        "presentation": f"Presentation: follow the animated steps for {topic}.",
        "video": f"Video: watch the clip on {topic} and say what changed.",
        "live_teacher": f"Live teacher: your teacher walks through {topic} and asks the next step.",
    }
    return prompts.get((modality or "").strip().lower(), "")


def clean_modality_ratings(raw: Any) -> Dict[str, int]:
    """Keep positive weights for known modalities. Missing keys are omitted."""
    if not isinstance(raw, Mapping):
        return {}
    cleaned: Dict[str, int] = {}
    for key in MODALITY_ORDER:
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        number = int(value)
        if number > 0:
            cleaned[key] = number
    return cleaned


def canonical_context(context: str) -> str:
    key = (context or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key not in _CONTEXT_ALIASES:
        raise ValueError(f"unknown delivery context {context!r}")
    return _CONTEXT_ALIASES[key]


def resolve_delivery_context(
    *,
    class_type: str = "",
    audio_only: bool = False,
    mode: str = "",
    audience: str = "",
    track: str = "",
    delivery: str = "",
    media_format: str = "",
) -> Tuple[str, str]:
    """Map the stored lesson/session delivery onto one mix context.

    Game / arcade wins over audio, and audio wins over a live group class.
    The detail string is the setting name shown in the scoring line.
    """
    if _is_game(mode, audience, track, delivery, media_format):
        return "video_game", "video game (game / arcade)"
    if audio_only or (mode or "").strip().lower() in _AUDIO_MODES:
        return "on_the_go", "on the go (audio / drive)"
    if (class_type or "").strip().lower() == "group":
        return "live_group", "live group class (class type group)"
    return "course", "in-app course"


def allocate_modality_mix(
    ratings: Any,
    page_count: int,
    context: str = "course",
    *,
    context_detail: str = "",
) -> Dict[str, Any]:
    """Allocate integer pages. The counts always sum to ``page_count``."""
    ctx = canonical_context(context)
    pages = max(0, int(page_count))
    weights = clean_modality_ratings(ratings)
    blocked = _INELIGIBLE[ctx]
    detail = (context_detail or "").strip() or _CONTEXT_DETAIL[ctx]

    removed: List[Dict[str, Any]] = []
    eligible: Dict[str, int] = {}
    for key in MODALITY_ORDER:
        rating = weights.get(key, 0)
        if rating <= 0:
            continue
        if key in blocked:
            removed.append(_removed_row(key, rating, ctx, share_pages=None))
        else:
            eligible[key] = rating

    cutoff_total = sum(eligible.values())
    if pages > 0 and cutoff_total > 0:
        small = [
            key for key in list(eligible)
            if 2 * eligible[key] * pages < cutoff_total
        ]
        if small and len(small) == len(eligible):
            keeper = max(
                eligible,
                key=lambda key: (eligible[key], -MODALITY_ORDER.index(key)),
            )
            small = [key for key in small if key != keeper]
        for key in small:
            share = _share_pages(eligible[key], cutoff_total, pages)
            removed.append(_removed_row(key, eligible[key], "below_half_page", share))
            del eligible[key]

    kept_weight = sum(eligible.values())
    fallback = False
    if pages > 0 and not eligible:
        allowed = [key for key in MODALITY_ORDER if key not in blocked]
        if allowed:
            eligible = {allowed[0]: 1}
            fallback = True

    counts = _hamilton(eligible, pages) if pages > 0 else {}
    if pages > 0 and sum(counts.values()) != pages and eligible:
        counts = _fill_to_pages(counts, pages, eligible)

    assignment = _assignment(counts, pages)
    rows = _rows(weights, blocked, removed, counts, eligible)
    lines = _lines(pages, detail, rows, fallback, assignment)
    return {
        "context": ctx,
        "context_label": _CONTEXT_DETAIL[ctx],
        "context_detail": detail,
        "page_count": pages,
        "rating_total": sum(weights.values()),
        "eligible_total": kept_weight,
        "counts": {key: counts.get(key, 0) for key in MODALITY_ORDER if key in counts},
        "assignment": assignment,
        "removed": [
            {
                "modality": row["modality"],
                "reason": row["reason"],
                "reason_text": row["reason_text"],
                "rating": row["rating"],
                "share_pages": row.get("share_pages"),
            }
            for row in rows if row["removed"]
        ],
        "rows": rows,
        "lines": lines,
        "fallback": fallback,
    }


def _is_game(*parts: str) -> bool:
    for part in parts:
        tokens = re.split(r"[^a-z0-9]+", (part or "").lower())
        if any(token in _GAME_TOKENS for token in tokens):
            return True
    return False


def _share_pages(rating: int, total: int, pages: int) -> float:
    if total <= 0:
        return 0.0
    return round(rating * pages / total, 2)


def _percent(rating: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(1000 * rating / total) / 10.0


def _pages_phrase(count: int) -> str:
    return "1 page" if count == 1 else f"{count} pages"


def _removed_row(
    key: str,
    rating: int,
    reason: str,
    share_pages: Optional[float],
) -> Dict[str, Any]:
    return {
        "modality": key,
        "label": MODALITY_LABELS[key],
        "rating": rating,
        "percent": None,
        "pages": 0,
        "removed": True,
        "reason": reason,
        "reason_text": _REASON_TEXT[reason],
        "share_pages": share_pages,
    }


def _hamilton(weights: Mapping[str, int], pages: int) -> Dict[str, int]:
    keys = [key for key in MODALITY_ORDER if weights.get(key, 0) > 0]
    total = sum(weights[key] for key in keys)
    if pages <= 0 or total <= 0 or not keys:
        return {}
    floors: Dict[str, int] = {}
    remainders: Dict[str, int] = {}
    for key in keys:
        numerator = weights[key] * pages
        floors[key] = numerator // total
        remainders[key] = numerator % total
    leftover = pages - sum(floors.values())
    ranked = sorted(
        keys,
        key=lambda key: (
            -remainders[key],
            -weights[key],
            MODALITY_ORDER.index(key),
        ),
    )
    for key in ranked[: max(0, leftover)]:
        floors[key] += 1
    return floors


def _fill_to_pages(
    counts: Mapping[str, int],
    pages: int,
    weights: Mapping[str, int],
) -> Dict[str, int]:
    filled = {key: counts.get(key, 0) for key in weights}
    gap = pages - sum(filled.values())
    if gap == 0:
        return filled
    order = sorted(
        filled,
        key=lambda key: (-weights.get(key, 0), MODALITY_ORDER.index(key)),
    )
    if not order:
        return filled
    index = 0
    while gap > 0:
        filled[order[index % len(order)]] += 1
        gap -= 1
        index += 1
    while gap < 0:
        donor = next((key for key in reversed(order) if filled[key] > 0), "")
        if not donor:
            break
        filled[donor] -= 1
        gap += 1
    return filled


def _assignment(counts: Mapping[str, int], pages: int) -> List[str]:
    sequence: List[str] = []
    for key in MODALITY_ORDER:
        sequence.extend([key] * int(counts.get(key, 0)))
    if pages <= 0:
        return []
    if len(sequence) < pages:
        pad = sequence[0] if sequence else MODALITY_ORDER[0]
        sequence.extend([pad] * (pages - len(sequence)))
    return sequence[:pages]


def _rows(
    weights: Mapping[str, int],
    blocked: frozenset,
    removed: Sequence[Mapping[str, Any]],
    counts: Mapping[str, int],
    eligible: Mapping[str, int],
) -> List[Dict[str, Any]]:
    removed_by_key = {row["modality"]: row for row in removed}
    eligible_total = sum(eligible.values())
    rows: List[Dict[str, Any]] = []
    seen = set(removed_by_key) | set(eligible) | set(counts)
    for key in MODALITY_ORDER:
        if key not in seen and weights.get(key, 0) <= 0:
            continue
        if key in removed_by_key:
            rows.append(dict(removed_by_key[key]))
            continue
        rating = weights.get(key, 0)
        if key in blocked and rating <= 0:
            continue
        pages = int(counts.get(key, 0))
        percent = _percent(rating, eligible_total) if rating and eligible_total else None
        rows.append({
            "modality": key,
            "label": MODALITY_LABELS[key],
            "rating": rating,
            "percent": percent,
            "pages": pages,
            "removed": False,
            "reason": "",
            "reason_text": "",
            "share_pages": _share_pages(rating, eligible_total, sum(counts.values()) or 0)
            if rating and eligible_total else None,
        })
    return rows


def _lines(
    pages: int,
    detail: str,
    rows: Sequence[Mapping[str, Any]],
    fallback: bool,
    assignment: Sequence[str],
) -> List[str]:
    lines = [f"{_pages_phrase(pages).capitalize()} in this course. Setting: {detail}."]
    context_removed = [
        row for row in rows
        if row["removed"] and row["reason"] != "below_half_page"
    ]
    small_removed = [row for row in rows if row["reason"] == "below_half_page"]
    if context_removed:
        bits = [
            f"{row['label']} (rating {row['rating']})"
            for row in context_removed
        ]
        why = context_removed[0]["reason_text"]
        lines.append(
            "Removed before the percentages — "
            f"{why}: {', '.join(bits)}."
        )
    for row in rows:
        if row["removed"]:
            continue
        if fallback and row["rating"] == 0:
            continue
        percent = row["percent"]
        percent_text = f"{percent:.1f}%" if isinstance(percent, float) else "0%"
        lines.append(
            f"{row['label']}: rating {row['rating']}, "
            f"{percent_text} of the eligible total, {_pages_phrase(int(row['pages']))}."
        )
    if small_removed:
        bits = []
        for row in small_removed:
            share = row.get("share_pages")
            share_text = f"{share:.2f} pages" if isinstance(share, float) else "under half a page"
            bits.append(f"{row['label']} (rating {row['rating']}, {share_text})")
        lines.append(
            "Removed, less than half a page: "
            f"{', '.join(bits)}. Remaining ratings were scaled to 100%."
        )
    if fallback and pages > 0:
        used = assignment[0] if assignment else ""
        label = MODALITY_LABELS.get(used, used)
        lines.append(
            "Every rated format was removed for this setting, so all "
            f"{_pages_phrase(pages)} use {label}."
        )
    return lines
