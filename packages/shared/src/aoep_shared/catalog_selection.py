"""Privacy-safe, profile-aware selection over the unified learnable catalog."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .learning_profile import decode_profile_score
from .learnable.models import LearnableItem

SESSION_BUDGET_MINUTES = {"short": 10, "medium": 18, "long": 30}
DEVICE_MODES = frozenset({"browse", "class", "drive", "offline"})
NETWORK_QUALITIES = frozenset({"high", "standard", "low", "offline"})


def resolve_session_budget(
    session_length: str = "medium",
    *,
    explicit_minutes: int | None = None,
    observed_pace: str = "",
) -> int:
    """Resolve a safe 5–90 minute budget from survey and observed pace."""
    if explicit_minutes is not None:
        return max(5, min(90, int(explicit_minutes)))
    budget = SESSION_BUDGET_MINUTES.get(session_length, 18)
    if observed_pace == "fast":
        budget = max(10, budget - 5)
    elif observed_pace == "slow":
        budget = min(90, budget + 5)
    return budget


def profile_dimensions(profile_score: str = "", **declared: str) -> Dict[str, str]:
    """Prefer a valid encoded profile, falling back to declared canonical fields."""
    values = {key: value for key, value in declared.items() if value}
    if profile_score:
        decoded = decode_profile_score(profile_score)
        values = {**values, **decoded}
    return values


def _allowed_for_device(
    item: LearnableItem,
    *,
    device_mode: str,
    network_quality: str,
) -> bool:
    if device_mode == "drive":
        return item.format == "audio" and item.drive_safe
    if device_mode == "class" and item.format not in {"live_class", "interactive", "video"}:
        return False
    if device_mode == "offline" or network_quality == "offline":
        return item.format != "live_class"
    return True


def _style_formats(style: str) -> set[str]:
    return {
        "visual": {"video", "interactive", "live_class"},
        "auditory": {"audio", "live_class"},
        "reading_writing": {"program", "interactive"},
        "hands_on": {"interactive", "game", "live_class"},
        "mixed": set(),
    }.get(style, set())


def select_learnable(
    items: Iterable[LearnableItem],
    *,
    profile_score: str = "",
    session_length: str = "medium",
    session_budget_min: int | None = None,
    observed_pace: str = "",
    primary_style: str = "",
    group_preference: str = "",
    language: str = "en",
    device_mode: str = "browse",
    network_quality: str = "standard",
    limit: int = 20,
) -> Dict[str, Any]:
    """Filter and rank catalog items without using network/device fingerprints."""
    if device_mode not in DEVICE_MODES:
        raise ValueError(f"unsupported device_mode: {device_mode}")
    if network_quality not in NETWORK_QUALITIES:
        raise ValueError(f"unsupported network_quality: {network_quality}")

    dimensions = profile_dimensions(
        profile_score,
        primary_style=primary_style,
        group_preference=group_preference,
        session_length=session_length,
    )
    session_length = dimensions.get("session_length", session_length)
    budget = resolve_session_budget(
        session_length,
        explicit_minutes=session_budget_min,
        observed_pace=observed_pace,
    )
    style = dimensions.get("primary_style", primary_style)
    group = dimensions.get("group_preference", group_preference)
    preferred_formats = _style_formats(style)
    ranked: List[tuple[float, LearnableItem, List[str]]] = []

    for item in items:
        if not _allowed_for_device(
            item, device_mode=device_mode, network_quality=network_quality,
        ):
            continue
        reasons: List[str] = []
        score = min(20.0, float(item.popularity) / 10.0)
        if item.language == language or item.audio_language == language:
            score += 20
            reasons.append("language_match")
        elif item.language == "en":
            score += 2
            reasons.append("language_fallback")
        if not item.duration_min or item.duration_min <= budget:
            score += 16
            reasons.append("fits_session")
        else:
            # Longer lessons remain eligible because the orchestrator can build
            # a shorter path from the same canonical course.
            score += max(0, 10 - ((item.duration_min - budget) / 5))
            reasons.append("adaptive_duration")
        if item.format in preferred_formats:
            score += 10
            reasons.append("learning_style")
        if group == "solo" and item.format != "live_class":
            score += 5
            reasons.append("solo_preference")
        elif group == "group" and item.format == "live_class":
            score += 8
            reasons.append("group_preference")
        if device_mode == "drive" and item.drive_safe:
            score += 20
            reasons.append("drive_safe")
        if network_quality == "low" and item.format in {"audio", "program"}:
            score += 8
            reasons.append("low_bandwidth")
        ranked.append((score, item, reasons))

    ranked.sort(key=lambda row: (-row[0], row[1].title.lower(), row[1].id))
    selections = []
    for score, item, reasons in ranked[: max(1, min(100, int(limit)))]:
        selections.append({
            "item": item.model_dump(),
            "match_score": round(score, 2),
            "reasons": reasons,
            "session_budget_min": budget,
            "planned_duration_min": min(item.duration_min or budget, budget),
        })
    return {
        "items": selections,
        "session_budget_min": budget,
        "profile_score_version": "1.0" if profile_score else "",
        "device_mode": device_mode,
        "network_quality": network_quality,
        "privacy": {
            "learner_identity": "account/student id",
            "mac_address_used": False,
            "ip_address_used_for_personalization": False,
        },
    }
