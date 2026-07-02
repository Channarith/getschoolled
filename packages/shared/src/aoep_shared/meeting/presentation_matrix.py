"""Finite presentation-mode matrix — mix-and-match how a course is delivered.

CONTENT vs PRESENTATION
  ``harvest.composition`` scores *what* nodes a course is made of (introduction,
  example, quiz, ...). This module scores *how* those nodes are presented live:
  structure arc, spoken voice, time policy, engagement level, and media emphasis.

MODEL
  Five independent AXES, each with a small finite option set. A presentation mode
  is one choice per axis, addressed by a mixed-radix index::

      mode_index in 0 .. PRESENTATION_MODE_CAPACITY - 1   # default 540 modes

  Same index always decodes to the same ``PresentationProfile`` (recipe fingerprint
  for delivery). Mix axes freely; invalid indices wrap modulo capacity.

  A second matrix ``category_treatment`` maps each pedagogical node category
  (rows = ``NODE_CATEGORIES`` from harvest composition) to a delivery treatment
  for the selected arc (speak | summarize | skip | digress | interact | media).

Pure: numpy + stdlib; offline-testable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from math import prod
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np

from ..harvest.composition import CATEGORY_INDEX, NODE_CATEGORIES, NUM_CATEGORIES

PRESENTATION_MATRIX_VERSION = "1.0"

# --------------------------------------------------------------------------- #
# Axis catalog (order is part of the contract — append only).
# --------------------------------------------------------------------------- #
AXIS_ARC: Tuple[str, ...] = (
    "lecture",    # teach → example → try-it → periodic recap (default class)
    "workshop",   # fewer recaps, more hands-on beats
    "survey",     # concept-forward overview, light practice
    "drill",      # exercise-heavy, short concept beats
    "flipped",    # pre-read emphasis, in-class = examples + discussion
    "lewin",      # Walter Lewin theatrical arc: predict → demo climax → recap
)

AXIS_VOICE: Tuple[str, ...] = (
    "verbatim",   # read slide narration as written
    "smart",      # digressions, techniques, optional RAG asides (default)
    "condensed",  # always compress long spoken segments
)

AXIS_TIME: Tuple[str, ...] = (
    "fixed",      # ignore schedule; deliver full plan
    "adaptive",   # skip / summarize / speed when behind (default)
    "strict",     # hard fit: skip low-priority beats aggressively
)

AXIS_ENGAGE: Tuple[str, ...] = (
    "passive",    # minimal live interaction; defer try-it to self-study
    "guided",     # standard checkpoints and comprehension checks
    "socratic",   # more questions, discussion prompts, think-pair-share cues
)

AXIS_MEDIA: Tuple[str, ...] = (
    "balanced",   # mix text, examples, and media references
    "visual",     # emphasize diagrams / video slides when present
    "demo",       # emphasize worked examples and walkthroughs
    "audio",      # narration-first; shorter on-screen density
)

PRESENTATION_AXES: Tuple[Tuple[str, ...], ...] = (
    AXIS_ARC, AXIS_VOICE, AXIS_TIME, AXIS_ENGAGE, AXIS_MEDIA,
)
AXIS_NAMES: Tuple[str, ...] = ("arc", "voice", "time", "engage", "media")

TREATMENTS: Tuple[str, ...] = (
    "speak", "summarize", "skip", "digress", "interact", "media",
)
_TREATMENT_INDEX: Dict[str, int] = {t: i for i, t in enumerate(TREATMENTS)}
NUM_TREATMENTS: int = len(TREATMENTS)

PRESENTATION_MODE_CAPACITY: int = prod(len(a) for a in PRESENTATION_AXES)

# Per-arc category treatment weights (rows = categories, cols = treatments).
# Highest-weight treatment wins when building a step plan.
_ARC_MATRICES: Dict[str, np.ndarray] = {}


def _row(category: str, **weights: float) -> np.ndarray:
    row = np.zeros(NUM_TREATMENTS, dtype=np.float64)
    idx = CATEGORY_INDEX.get(category, CATEGORY_INDEX["concept"])
    for t, w in weights.items():
        row[_TREATMENT_INDEX[t]] = w
    return row


def _build_arc_matrix(arc: str) -> np.ndarray:
    """Shape (NUM_CATEGORIES, NUM_TREATMENTS) — delivery recipe for an arc."""
    m = np.zeros((NUM_CATEGORIES, NUM_TREATMENTS), dtype=np.float64)
    default = {"speak": 1.0}

    def set_cat(cat: str, **kw: float) -> None:
        if cat in CATEGORY_INDEX:
            m[CATEGORY_INDEX[cat]] = _row(cat, **kw)

    if arc == "lecture":
        set_cat("introduction", digress=1.2, speak=0.8)
        set_cat("history", digress=1.0, speak=0.6)
        set_cat("concept", speak=1.0)
        set_cat("definition", speak=0.9, summarize=0.3)
        set_cat("example", digress=1.1, speak=0.7)
        set_cat("demo", digress=1.0, media=0.8)
        set_cat("video", media=1.2, speak=0.4)
        set_cat("image", media=1.0, speak=0.5)
        set_cat("exercise", interact=1.2, speak=0.3)
        set_cat("quiz", interact=1.0)
        set_cat("qanda", interact=1.1)
        set_cat("discussion", interact=1.2)
        set_cat("case_study", digress=0.9, speak=0.7)
        set_cat("summary", summarize=0.8, speak=0.6)
        set_cat("recap", summarize=1.0)
        set_cat("resources", skip=0.6, speak=0.4)
        set_cat("assessment", interact=0.8, speak=0.5)
        set_cat("project", interact=1.0, digress=0.5)
    elif arc == "workshop":
        set_cat("introduction", digress=0.8, speak=0.7)
        set_cat("concept", speak=0.8, summarize=0.4)
        set_cat("example", digress=1.0, interact=0.5)
        set_cat("demo", digress=1.2, media=1.0, interact=0.6)
        set_cat("exercise", interact=1.4, speak=0.2)
        set_cat("quiz", interact=1.2)
        set_cat("discussion", interact=1.3)
        set_cat("recap", skip=0.8)
        set_cat("summary", summarize=0.7, speak=0.5)
        for cat in NODE_CATEGORIES:
            if m[CATEGORY_INDEX[cat]].sum() == 0:
                m[CATEGORY_INDEX[cat]] = _row(cat, **default)
    elif arc == "survey":
        set_cat("introduction", digress=1.0, speak=0.8)
        set_cat("history", digress=0.9, speak=0.7)
        set_cat("concept", speak=1.0, summarize=0.3)
        set_cat("definition", summarize=0.6, speak=0.5)
        set_cat("example", digress=0.6, speak=0.8)
        set_cat("exercise", skip=0.9, speak=0.2)
        set_cat("quiz", skip=0.7, interact=0.3)
        set_cat("recap", skip=0.8)
        set_cat("summary", summarize=1.0)
        set_cat("resources", speak=0.6)
        for cat in NODE_CATEGORIES:
            if m[CATEGORY_INDEX[cat]].sum() == 0:
                m[CATEGORY_INDEX[cat]] = _row(cat, speak=0.9)
    elif arc == "drill":
        set_cat("introduction", summarize=0.8, speak=0.5)
        set_cat("concept", summarize=0.9, speak=0.6)
        set_cat("example", digress=0.7, interact=0.5)
        set_cat("exercise", interact=1.5, speak=0.2)
        set_cat("quiz", interact=1.3)
        set_cat("demo", interact=0.8, media=0.5)
        set_cat("recap", skip=0.7)
        set_cat("summary", summarize=0.8)
        for cat in NODE_CATEGORIES:
            if m[CATEGORY_INDEX[cat]].sum() == 0:
                m[CATEGORY_INDEX[cat]] = _row(cat, interact=0.5, speak=0.5)
    elif arc == "flipped":
        set_cat("introduction", summarize=0.7, speak=0.5)
        set_cat("concept", skip=0.5, summarize=0.6)
        set_cat("example", digress=1.2, interact=0.8)
        set_cat("demo", digress=1.1, media=0.9)
        set_cat("discussion", interact=1.3)
        set_cat("qanda", interact=1.2)
        set_cat("exercise", interact=1.0)
        set_cat("case_study", digress=1.0, interact=0.6)
        set_cat("summary", summarize=0.8)
        for cat in NODE_CATEGORIES:
            if m[CATEGORY_INDEX[cat]].sum() == 0:
                m[CATEGORY_INDEX[cat]] = _row(cat, speak=0.7)
    elif arc == "lewin":
        set_cat("introduction", digress=1.3, speak=0.7)
        set_cat("concept", speak=0.9, digress=0.8)
        set_cat("definition", speak=0.8)
        set_cat("example", digress=1.0, media=0.7)
        set_cat("demo", digress=1.5, media=1.3, interact=1.2)
        set_cat("video", media=1.4, speak=0.3)
        set_cat("exercise", interact=1.3)
        set_cat("quiz", interact=1.1)
        set_cat("discussion", interact=1.2)
        set_cat("summary", summarize=0.6, speak=0.8)
        set_cat("recap", summarize=0.7, digress=0.5)
        for cat in NODE_CATEGORIES:
            if m[CATEGORY_INDEX[cat]].sum() == 0:
                m[CATEGORY_INDEX[cat]] = _row(cat, speak=0.8, digress=0.5)
    else:
        for cat in NODE_CATEGORIES:
            m[CATEGORY_INDEX[cat]] = _row(cat, **default)
    return m


for _arc in AXIS_ARC:
    _ARC_MATRICES[_arc] = _build_arc_matrix(_arc)


# --------------------------------------------------------------------------- #
# Mixed-radix addressing (same pattern as training_agents.procedural).
# --------------------------------------------------------------------------- #
def _radices() -> List[int]:
    return [len(a) for a in PRESENTATION_AXES]


def _decompose(index: int, radices: Sequence[int]) -> List[int]:
    out: List[int] = []
    idx = int(index) % prod(radices) if radices else 0
    for r in reversed(radices):
        out.append(idx % r)
        idx //= r
    return list(reversed(out))


def decode_presentation_mode(index: int) -> Tuple[str, ...]:
    """Map a mode index to ``(arc, voice, time, engage, media)``."""
    parts = _decompose(index, _radices())
    return tuple(axis[i] for axis, i in zip(PRESENTATION_AXES, parts))


def encode_presentation_mode(
    arc: str,
    voice: str,
    time: str,
    engage: str,
    media: str,
) -> int:
    """Encode axis choices into a single mode index."""
    choices = (arc, voice, time, engage, media)
    idx = 0
    for choice, axis in zip(choices, PRESENTATION_AXES):
        if choice not in axis:
            raise ValueError(f"unknown {AXIS_NAMES[len(idx)]}={choice!r}; one of {axis}")
        idx = idx * len(axis) + axis.index(choice)
    return idx


ModeInput = Union[int, str, Tuple[str, ...], Dict[str, str]]


_DEFAULT_AXIS_VALUES: Tuple[str, str, str, str, str] = (
    "lecture", "smart", "adaptive", "guided", "balanced",
)


def _resolve_axis_parts(parts: Sequence[str]) -> Tuple[str, str, str, str, str]:
    """Fill 1..5 pipe segments onto the five axes (missing slots use defaults)."""
    axes = PRESENTATION_AXES
    out = list(_DEFAULT_AXIS_VALUES)
    if not parts:
        return tuple(out)  # type: ignore[return-value]
    if len(parts) == 1:
        token = parts[0].strip().lower()
        for i, axis in enumerate(axes):
            if token in axis:
                out[i] = token
                return tuple(out)  # type: ignore[return-value]
        raise ValueError(
            f"unknown presentation token {parts[0]!r}; "
            f"one of arc {AXIS_ARC}, voice {AXIS_VOICE}, time {AXIS_TIME}, "
            f"engage {AXIS_ENGAGE}, media {AXIS_MEDIA}, or a preset name",
        )
    for i, part in enumerate(parts[:5]):
        token = part.strip().lower()
        if token not in axes[i]:
            raise ValueError(
                f"unknown {AXIS_NAMES[i]}={part!r}; one of {axes[i]}",
            )
        out[i] = token
    return tuple(out)  # type: ignore[return-value]


def resolve_mode_index(spec: Optional[ModeInput] = None) -> int:
    """Accept index, ``'drill'``, ``'drill|smart'``, full pipe string, or dict."""
    if spec is None:
        return default_presentation_mode_index()
    if isinstance(spec, int):
        return int(spec) % PRESENTATION_MODE_CAPACITY
    if isinstance(spec, dict):
        return encode_presentation_mode(
            spec.get("arc", AXIS_ARC[0]),
            spec.get("voice", AXIS_VOICE[1]),
            spec.get("time", AXIS_TIME[1]),
            spec.get("engage", AXIS_ENGAGE[1]),
            spec.get("media", AXIS_MEDIA[0]),
        )
    if isinstance(spec, (list, tuple)) and len(spec) == 5:
        return encode_presentation_mode(*spec)
    if isinstance(spec, str):
        if spec.isdigit():
            return int(spec) % PRESENTATION_MODE_CAPACITY
        key = spec.strip().lower()
        _PRESETS = {
            "default": default_presentation_mode_index(),
            "lecture": encode_presentation_mode("lecture", "smart", "adaptive", "guided", "balanced"),
            "workshop": encode_presentation_mode("workshop", "smart", "adaptive", "guided", "demo"),
            "survey": encode_presentation_mode("survey", "smart", "adaptive", "guided", "balanced"),
            "drill": encode_presentation_mode("drill", "smart", "adaptive", "guided", "balanced"),
            "flipped": encode_presentation_mode("flipped", "smart", "adaptive", "guided", "balanced"),
            "lewin": encode_presentation_mode("lewin", "smart", "adaptive", "socratic", "demo"),
            "express": encode_presentation_mode("survey", "condensed", "strict", "passive", "audio"),
        }
        if key in _PRESETS:
            return _PRESETS[key]
        parts = [p.strip() for p in spec.split("|")]
        return encode_presentation_mode(*_resolve_axis_parts(parts))
    raise TypeError(f"cannot resolve presentation mode from {type(spec)}")


def default_presentation_mode_index() -> int:
    return encode_presentation_mode("lecture", "smart", "adaptive", "guided", "balanced")


def category_treatment(arc: str, category: str) -> str:
    """Primary delivery treatment for a node category under an arc."""
    cat = category if category in CATEGORY_INDEX else "concept"
    mat = _ARC_MATRICES.get(arc, _ARC_MATRICES["lecture"])
    row = mat[CATEGORY_INDEX[cat]]
    if row.sum() <= 0:
        return "speak"
    return TREATMENTS[int(row.argmax())]


@dataclass
class PresentationProfile:
    """Concrete delivery recipe decoded from the presentation matrix."""

    mode_index: int
    arc: str
    voice: str
    time: str
    engage: str
    media: str
    # Structure (Part 1 harvest / pedagogy)
    include_try_it: bool = True
    include_worked_examples: bool = True
    recap_every_n: int = 4
    hands_on_callouts: bool = False
    fun_facts: bool = True
    # Presenter (Part 3)
    allow_digression: bool = True
    enable_time_budget: bool = True
    auto_summarize: bool = False
    aggressive_time_skip: bool = False
    skip_try_it_live: bool = False
    socratic_prompts: bool = False
    media_first: bool = False
    wpm_factor: float = 1.0
    category_treatment_map: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_index(cls, index: int) -> "PresentationProfile":
        arc, voice, time_policy, engage, media = decode_presentation_mode(index)
        include_try = engage != "passive" and arc not in ("survey",)
        include_examples = arc != "survey" or media == "demo"
        recap_n = 0 if arc in ("workshop", "drill", "survey") else 4
        if arc == "drill":
            recap_n = 0
        hands_on = arc in ("workshop", "drill", "flipped", "lewin")
        fun = arc in ("lecture", "flipped", "lewin")
        digress = voice == "smart" and arc not in ("survey",)
        time_budget = time_policy != "fixed"
        auto_sum = voice == "condensed"
        skip_try_live = engage == "passive" or arc == "survey"
        socratic = engage == "socratic"
        media_first = media in ("visual", "demo", "audio")
        aggressive = time_policy == "strict"
        if arc == "lewin":
            recap_n = 3
            include_try = True
            include_examples = True
            socratic = True
            media_first = True
            aggressive = False
        wpm = 1.15 if voice == "condensed" else (0.92 if media == "audio" else 1.0)
        treat = {cat: category_treatment(arc, cat) for cat in NODE_CATEGORIES}
        return cls(
            mode_index=int(index) % PRESENTATION_MODE_CAPACITY,
            arc=arc,
            voice=voice,
            time=time_policy,
            engage=engage,
            media=media,
            include_try_it=include_try,
            include_worked_examples=include_examples,
            recap_every_n=recap_n,
            hands_on_callouts=hands_on,
            fun_facts=fun,
            allow_digression=digress,
            enable_time_budget=time_budget,
            auto_summarize=auto_sum,
            aggressive_time_skip=aggressive,
            skip_try_it_live=skip_try_live,
            socratic_prompts=socratic,
            media_first=media_first,
            wpm_factor=wpm,
            category_treatment_map=treat,
        )

    @classmethod
    def resolve(cls, spec: Optional[ModeInput] = None) -> "PresentationProfile":
        return cls.from_index(resolve_mode_index(spec))

    def treatment_for(self, category: str) -> str:
        return self.category_treatment_map.get(
            category, category_treatment(self.arc, category),
        )

    def to_dict(self) -> Dict:
        return {
            "version": PRESENTATION_MATRIX_VERSION,
            "mode_index": self.mode_index,
            "arc": self.arc,
            "voice": self.voice,
            "time": self.time,
            "engage": self.engage,
            "media": self.media,
            "capacity": PRESENTATION_MODE_CAPACITY,
            "structure": {
                "include_try_it": self.include_try_it,
                "include_worked_examples": self.include_worked_examples,
                "recap_every_n": self.recap_every_n,
                "hands_on_callouts": self.hands_on_callouts,
                "fun_facts": self.fun_facts,
            },
            "presenter": {
                "allow_digression": self.allow_digression,
                "enable_time_budget": self.enable_time_budget,
                "auto_summarize": self.auto_summarize,
                "aggressive_time_skip": self.aggressive_time_skip,
                "skip_try_it_live": self.skip_try_it_live,
                "socratic_prompts": self.socratic_prompts,
                "media_first": self.media_first,
                "wpm_factor": self.wpm_factor,
            },
            "category_treatment": {
                k: v for k, v in self.category_treatment_map.items()
                if v != "speak"
            },
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def list_presentation_modes(*, limit: int = 0) -> List[Dict]:
    """Enumerate modes (optionally capped) for catalogs and UIs."""
    cap = PRESENTATION_MODE_CAPACITY if limit <= 0 else min(limit, PRESENTATION_MODE_CAPACITY)
    rows: List[Dict] = []
    for i in range(cap):
        p = PresentationProfile.from_index(i)
        rows.append({
            "mode_index": i,
            "arc": p.arc,
            "voice": p.voice,
            "time": p.time,
            "engage": p.engage,
            "media": p.media,
            "label": f"{p.arc}|{p.voice}|{p.time}|{p.engage}|{p.media}",
        })
    return rows


def recommend_presentation_modes(
    composition,
    *,
    top_n: int = 5,
) -> List[Dict]:
    """Rank presentation arcs against a course composition node vector."""
    vec = composition.node_vector() if hasattr(composition, "node_vector") else np.zeros(NUM_CATEGORIES)
    total = float(vec.sum()) or 1.0
    rows: List[Tuple[float, int, PresentationProfile]] = []
    seen: set = set()
    for arc in AXIS_ARC:
        mat = _ARC_MATRICES[arc]
        # Score = dot product of normalized content vector with arc emphasis.
        emphasis = mat.max(axis=1)
        score = float(np.dot(vec / total, emphasis))
        idx = encode_presentation_mode(arc, "smart", "adaptive", "guided", "balanced")
        if idx in seen:
            continue
        seen.add(idx)
        rows.append((score, idx, PresentationProfile.from_index(idx)))
    rows.sort(key=lambda r: r[0], reverse=True)
    return [
        {
            "mode_index": idx,
            "score": round(score, 4),
            "arc": prof.arc,
            "label": f"{prof.arc}|smart|adaptive|guided|balanced",
            "profile": prof.to_dict(),
        }
        for score, idx, prof in rows[:top_n]
    ]


def arc_matrix(arc: str) -> np.ndarray:
    """Expose the (categories x treatments) matrix for an arc."""
    return _ARC_MATRICES.get(arc, _ARC_MATRICES["lecture"]).copy()
