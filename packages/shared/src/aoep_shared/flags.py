"""Administrative feature-flag system.

A central registry (``FLAG_CATALOG``) of product/platform feature flags plus a
runtime ``FlagStore`` that supports the common feature-flag designs:

- master on/off per flag,
- value overrides (boolean, integer, or multivariate string/number),
- percentage rollouts (stable per-subject bucketing for gradual exposure),
- membership-tier targeting (allow-lists),
- per-subject overrides (force a flag on/off for a single account/student).

Mutating the store is an *administrative* action; callers (the memory service)
gate writes behind an admin secret via :func:`require_admin`. Pure/offline and
stdlib-only so it is trivially testable; the service holds the store on
``app.state`` and exposes it over HTTP, mirroring ``legal.py``/``compliance.py``.
"""

from __future__ import annotations

import enum
import hashlib
import hmac
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FlagType(str, enum.Enum):
    BOOL = "bool"          # simple on/off
    PERCENT = "percent"    # gradual rollout; resolves to a bool via bucketing
    STRING = "string"      # multivariate (e.g. user-level variant)
    INT = "int"            # numeric tuning knob


@dataclass(frozen=True)
class FlagSpec:
    key: str
    type: FlagType
    default: Any
    category: str
    description: str
    admin_only: bool = False          # hidden from the public read endpoint
    options: tuple = ()               # allowed values for STRING multivariate


# ---------------------------------------------------------------------------- #
# Comprehensive catalog of feature flags appropriate for this platform.
# Grouped by category; covers engagement, data-mining, access tiers, monetization,
# AI behavior, UX experiments, and operational kill-switches.
# ---------------------------------------------------------------------------- #
FLAG_CATALOG: List[FlagSpec] = [
    # --- engagement / feedback ------------------------------------------------ #
    FlagSpec("engagement.post_class_survey", FlagType.BOOL, False, "engagement",
             "Show an optional one-time survey at the end of a class to gauge how "
             "good the course was; results feed course improvement + data mining."),
    FlagSpec("engagement.nps_survey", FlagType.BOOL, False, "engagement",
             "Periodic Net Promoter Score survey for the platform."),
    FlagSpec("engagement.in_class_polls", FlagType.BOOL, False, "engagement",
             "Live in-class polls/quizzes during a lesson."),
    FlagSpec("engagement.streaks_badges", FlagType.BOOL, True, "engagement",
             "Learning streaks and achievement badges."),
    FlagSpec("engagement.certificates", FlagType.BOOL, True, "engagement",
             "Issue completion certificates."),

    # --- data / analytics / data mining -------------------------------------- #
    FlagSpec("data.multidim_datamart", FlagType.BOOL, False, "data",
             "Write events into a multi-dimensional (OLAP-style) data mart for "
             "data mining and course improvement.", admin_only=True),
    FlagSpec("data.suggestion_mining", FlagType.BOOL, False, "data",
             "Mine free-text survey suggestions for actionable course insights.",
             admin_only=True),
    FlagSpec("data.ab_testing", FlagType.BOOL, False, "data",
             "Enable A/B experiment assignment + metrics capture.", admin_only=True),
    FlagSpec("data.session_replay", FlagType.BOOL, False, "data",
             "Capture anonymized session interaction traces for QA.", admin_only=True),
    FlagSpec("data.telemetry_sampling_pct", FlagType.INT, 100, "data",
             "Percent of sessions emitting detailed telemetry.", admin_only=True),

    # --- access / user levels ------------------------------------------------ #
    FlagSpec("access.user_levels", FlagType.STRING, "standard", "access",
             "Default user access level / capability tier.",
             options=("guest", "standard", "power", "educator", "admin")),
    FlagSpec("access.educator_console", FlagType.BOOL, True, "access",
             "Expose the educator/HIL teaching console."),
    FlagSpec("access.homework_grader", FlagType.BOOL, False, "access",
             "Expose the AI homework grader in navigation (operator-only tool)."),
    FlagSpec("access.parental_controls", FlagType.BOOL, True, "access",
             "Parental controls + content maturity gating for minors."),
    FlagSpec("access.beta_program", FlagType.PERCENT, 0, "access",
             "Gradual rollout of beta features to a percentage of users."),
    FlagSpec("access.max_students_per_account", FlagType.INT, 5, "access",
             "Maximum learner sub-profiles per account."),

    # --- monetization -------------------------------------------------------- #
    FlagSpec("monetization.video_ads", FlagType.BOOL, True, "monetization",
             "Serve pre/mid-roll video ads to ad-supported tiers."),
    FlagSpec("monetization.dynamic_pricing", FlagType.BOOL, False, "monetization",
             "Experiment with dynamic course pricing."),
    FlagSpec("monetization.referral_program", FlagType.BOOL, False, "monetization",
             "Referral rewards for inviting new members."),
    FlagSpec("monetization.gift_subscriptions", FlagType.BOOL, False, "monetization",
             "Allow gifting memberships."),

    # --- AI behavior --------------------------------------------------------- #
    FlagSpec("ai.foresight_recommendations", FlagType.BOOL, True, "ai",
             "Use the Foresight engine for personalized recommendations."),
    FlagSpec("ai.hallucination_guard", FlagType.BOOL, True, "ai",
             "Groundedness/hallucination guard on AI answers."),
    FlagSpec("ai.emotion_engagement", FlagType.BOOL, False, "ai",
             "Emotion-based engagement signals (region-gated by compliance)."),
    FlagSpec("ai.live_translation", FlagType.BOOL, True, "ai",
             "Real-time translation/captioning of class content."),
    FlagSpec("ai.scratch_llm_track", FlagType.BOOL, False, "ai",
             "Route inference to the from-scratch frontier model track.",
             admin_only=True),
    FlagSpec("ai.proctoring", FlagType.BOOL, False, "ai",
             "AI proctoring for graded assessments."),

    # --- UX experiments ------------------------------------------------------ #
    FlagSpec("ux.dark_mode", FlagType.BOOL, True, "ux",
             "Dark-mode theme availability."),
    FlagSpec("ux.netflix_carousels", FlagType.PERCENT, 100, "ux",
             "Personalized Netflix-style browse carousels rollout."),
    FlagSpec("ux.new_player", FlagType.PERCENT, 0, "ux",
             "Rollout of the redesigned video player."),

    # --- operational kill-switches ------------------------------------------- #
    FlagSpec("ops.maintenance_mode", FlagType.BOOL, False, "ops",
             "Put the platform into maintenance (banner + restricted actions).",
             admin_only=True),
    FlagSpec("ops.read_only_mode", FlagType.BOOL, False, "ops",
             "Disable writes platform-wide (incident response).", admin_only=True),
    FlagSpec("ops.new_signups", FlagType.BOOL, True, "ops",
             "Allow new account sign-ups."),
    FlagSpec("ops.strict_rate_limits", FlagType.BOOL, False, "ops",
             "Apply stricter API rate limits.", admin_only=True),
]

CATALOG_BY_KEY: Dict[str, FlagSpec] = {f.key: f for f in FLAG_CATALOG}


class FlagState(BaseModel):
    """Mutable runtime state layered on top of a flag's spec/default."""

    key: str
    enabled: bool = True                      # master switch
    value: Optional[Any] = None              # override of spec.default
    rollout_pct: Optional[int] = None        # for BOOL/PERCENT gradual exposure
    tiers: Optional[List[str]] = None        # membership-tier allow-list
    overrides: Dict[str, Any] = Field(default_factory=dict)  # subject -> value
    updated_at: float = 0.0
    updated_by: str = ""


def _bucket(key: str, subject: str) -> int:
    """Stable 0-99 bucket for a (flag, subject) pair."""
    digest = hashlib.sha256(f"{key}:{subject}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def require_admin(provided: Optional[str], expected: str) -> bool:
    """Constant-time check of an admin secret (empty secret never authorizes)."""
    if not provided or not expected:
        return False
    return hmac.compare_digest(str(provided), str(expected))


class FlagStore:
    """Holds per-flag runtime state and resolves flags for a request context."""

    def __init__(self) -> None:
        self._states: Dict[str, FlagState] = {}

    # -- introspection ----------------------------------------------------- #
    def spec(self, key: str) -> Optional[FlagSpec]:
        return CATALOG_BY_KEY.get(key)

    def state(self, key: str) -> FlagState:
        return self._states.get(key) or FlagState(key=key)

    def describe(self, key: str) -> Dict[str, Any]:
        spec = CATALOG_BY_KEY[key]
        st = self.state(key)
        return {
            "key": spec.key,
            "type": spec.type.value,
            "category": spec.category,
            "description": spec.description,
            "admin_only": spec.admin_only,
            "options": list(spec.options),
            "default": spec.default,
            "enabled": st.enabled,
            "value": st.value if st.value is not None else spec.default,
            "rollout_pct": st.rollout_pct,
            "tiers": st.tiers,
            "overrides": st.overrides,
            "updated_at": st.updated_at,
            "updated_by": st.updated_by,
        }

    def list_specs(self, *, include_admin: bool = True) -> List[Dict[str, Any]]:
        return [self.describe(s.key) for s in FLAG_CATALOG
                if include_admin or not s.admin_only]

    # -- mutation (administrative) ---------------------------------------- #
    def set_flag(
        self,
        key: str,
        *,
        enabled: Optional[bool] = None,
        value: Optional[Any] = None,
        rollout_pct: Optional[int] = None,
        tiers: Optional[List[str]] = None,
        actor: str = "admin",
        clear_value: bool = False,
    ) -> FlagState:
        if key not in CATALOG_BY_KEY:
            raise KeyError(key)
        import time

        st = self._states.get(key) or FlagState(key=key)
        if enabled is not None:
            st.enabled = enabled
        if clear_value:
            st.value = None
        elif value is not None:
            st.value = _coerce(CATALOG_BY_KEY[key], value)
        if rollout_pct is not None:
            st.rollout_pct = max(0, min(100, int(rollout_pct)))
        if tiers is not None:
            st.tiers = tiers or None
        st.updated_at = time.time()
        st.updated_by = actor
        self._states[key] = st
        return st

    def set_override(self, key: str, subject: str, value: Any, *, actor: str = "admin") -> FlagState:
        if key not in CATALOG_BY_KEY:
            raise KeyError(key)
        import time

        st = self._states.get(key) or FlagState(key=key)
        st.overrides[subject] = _coerce(CATALOG_BY_KEY[key], value)
        st.updated_at = time.time()
        st.updated_by = actor
        self._states[key] = st
        return st

    def reset(self, key: str) -> None:
        self._states.pop(key, None)

    # -- evaluation -------------------------------------------------------- #
    def resolve(self, key: str, *, subject: Optional[str] = None,
                tier: Optional[str] = None) -> Any:
        """Resolve a flag's effective value for a request context."""
        spec = CATALOG_BY_KEY.get(key)
        if spec is None:
            raise KeyError(key)
        st = self.state(key)
        falsy = False if spec.type in (FlagType.BOOL, FlagType.PERCENT) else spec.default

        # Per-subject override always wins.
        if subject is not None and subject in st.overrides:
            return st.overrides[subject]

        if not st.enabled:
            return falsy

        # Tier allow-list gating.
        if st.tiers and (tier or "") not in st.tiers:
            return falsy

        base = st.value if st.value is not None else spec.default

        if spec.type is FlagType.PERCENT:
            pct = st.rollout_pct if st.rollout_pct is not None else int(base or 0)
            return _bucket(key, subject or "anon") < pct
        if spec.type is FlagType.BOOL:
            if st.rollout_pct is not None and st.rollout_pct < 100:
                if _bucket(key, subject or "anon") >= st.rollout_pct:
                    return False
            return bool(base)
        return base  # STRING / INT

    def evaluate_all(self, *, subject: Optional[str] = None,
                     tier: Optional[str] = None,
                     include_admin: bool = False) -> Dict[str, Any]:
        return {
            s.key: self.resolve(s.key, subject=subject, tier=tier)
            for s in FLAG_CATALOG if include_admin or not s.admin_only
        }


def _coerce(spec: FlagSpec, value: Any) -> Any:
    if spec.type is FlagType.BOOL:
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if spec.type in (FlagType.INT, FlagType.PERCENT):
        return int(value)
    if spec.type is FlagType.STRING:
        val = str(value)
        if spec.options and val not in spec.options:
            raise ValueError(f"{val!r} not in allowed options {spec.options}")
        return val
    return value
