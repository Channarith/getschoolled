"""Walter Lewin pedagogical tactics — theatrical, demo-driven lectures.

Inspired by MIT 8.01-style delivery and lectures such as
"For the Love of Physics" (2011): https://youtu.be/sJG-rXBbmCc

Documented tactics (sources: MIT Technology Review, NYT, The Tech, Lewin interviews):
  - Theatrical arc: foundation → build → demo climax → dénouement
  - Live demonstrations with predict-before-reveal tension
  - Equations paired with visceral demos (never abstract-only)
  - Everyday phenomena anchors (blue sky, red sunsets, pendulums)
  - Countdown timing and 5-minute lecture marks (never rush the demo)
  - Clarity + humor + contagious enthusiasm
  - Visual motion narrative ("dotted line" = trajectory over time)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

LEWIN_REFERENCE_URL = "https://youtu.be/sJG-rXBbmCc"


@dataclass(frozen=True)
class LewinTactic:
    id: str
    name: str
    strategy: str
    narration_template: str

    def apply(self, *, topic: str = "", point: str = "", data: str = "") -> str:
        try:
            return self.narration_template.format(
                topic=topic or "physics",
                point=point or "this idea",
                data=data or "",
            )
        except (KeyError, IndexError):
            return self.narration_template


# Canonical tactic catalog — maps to slide/presenter behavior.
LEWIN_TACTICS: Tuple[LewinTactic, ...] = (
    LewinTactic(
        "theatrical_arc",
        "Theatrical lecture arc",
        "Structure each class like a play: setup, rising action, climax demo, resolution.",
        "Today builds like a story — we lay the foundation, then a demonstration you will not forget.",
    ),
    LewinTactic(
        "everyday_anchor",
        "Everyday phenomenon hook",
        "Start from something the learner has seen (sky color, sunsets, pendulums).",
        "You have seen this your whole life: {point}. Today we explain it with numbers.",
    ),
    LewinTactic(
        "predict_before_reveal",
        "Predict before reveal",
        "Stop and force a prediction before showing the outcome (Lewin pendulum tension).",
        "Before I show you — predict: what will happen? Write down your guess. Three… two… one…",
    ),
    LewinTactic(
        "demo_climax",
        "Demonstration climax",
        "Place the memorable demo after setup; never rush the explanation.",
        "Watch carefully — this is the moment the equations come alive. {data}",
    ),
    LewinTactic(
        "equation_plus_demo",
        "Equation + demo pairing",
        "Every key equation is immediately tied to a observable outcome.",
        "The formula on screen is not decoration — it predicts what you are about to see.",
    ),
    LewinTactic(
        "visual_trajectory",
        "Visual motion narrative",
        "Trace change over time (Lewin's dotted lines) on the slide.",
        "Follow the dotted path — that is how {point} evolves step by step in time.",
    ),
    LewinTactic(
        "countdown_timing",
        "Countdown timing",
        "Use countdown marks; protect demo time (Lewin 50→0 clock).",
        "We have time for this demo — I will not rush. Breathe. Here we go.",
    ),
    LewinTactic(
        "enthusiasm",
        "Contagious enthusiasm",
        "Radiate love for the subject; humor without losing clarity.",
        "I love {topic} — and if you pay attention for the next few minutes, you will too.",
    ),
    LewinTactic(
        "student_stakes",
        "Emotional stakes",
        "Brief tension or humor so the moment sticks (without real danger in AI class).",
        "If our prediction is wrong, the equation lied — and that is the best kind of surprise.",
    ),
    LewinTactic(
        "denouement_recap",
        "Dénouement recap",
        "Close by tying the demo back to the opening question.",
        "Remember the question we opened with? Now you can answer it with physics, not guesswork.",
    ),
)

_TACTIC_BY_ID: Dict[str, LewinTactic] = {t.id: t for t in LEWIN_TACTICS}


def apply_lewin_tactic(tactic_id: str, **kwargs) -> str:
    t = _TACTIC_BY_ID.get(tactic_id)
    return t.apply(**kwargs) if t else ""


def lewin_technique_ids() -> List[str]:
    """Presentation-skills-compatible technique ids for Lewin delivery."""
    return [t.id for t in LEWIN_TACTICS]


def analyze_lewin_lecture() -> List[Dict[str, str]]:
    """Return a structured breakdown of Lewin tactics for docs/UI."""
    return [
        {
            "id": t.id,
            "name": t.name,
            "strategy": t.strategy,
            "reference": LEWIN_REFERENCE_URL,
        }
        for t in LEWIN_TACTICS
    ]


def _is_physicsish(subject: str, text: str) -> bool:
    hay = f"{subject} {text}".lower()
    return any(k in hay for k in (
        "physics", "science", "force", "energy", "wave", "light", "optics",
        "mechanics", "pendulum", "electric", "magnet", "motion",
    ))


def lewin_opening(course_title: str, outline: List[str]) -> str:
    preview = ", ".join(outline[:4])
    return (
        f"{apply_lewin_tactic('enthusiasm', topic=course_title)}\n"
        f"{apply_lewin_tactic('theatrical_arc')}\n"
        f"Today's path: {preview}.\n"
        f"{apply_lewin_tactic('everyday_anchor', point=outline[0] if outline else course_title)}"
    )


def lewin_demo_slide(
    concept_title: str,
    *,
    subject: str,
    concrete_data: str = "",
    section_text: str = "",
) -> Tuple[str, str, str]:
    """Return (title, body, narration) for a predict-before-reveal demo beat."""
    hay = f"{concept_title} {section_text}".lower()
    if _is_physicsish(subject, hay):
        if any(k in hay for k in (
            "sky", "color", "light", "sun", "scatter", "rayleigh", "sunset", "optics",
        )):
            data = (
                "White sunlight hits air molecules.\n"
                "Blue scatters more (Rayleigh) → sky looks blue.\n"
                "At sunset, light travels farther → red dominates."
            )
            title = "Demo: why the sky is blue, sunsets red"
        elif "pendulum" in hay or "period" in hay:
            data = (
                "Pendulum length L = 1.0 m → period T ≈ 2.0 s.\n"
                "Add mass 0.5 kg vs 5.0 kg → T stays 2.0 s.\n"
                "Only length and gravity set the period."
            )
            title = "Demo: pendulum period vs mass"
        elif "energy" in hay or "conservation" in hay:
            data = (
                "Height h = 3.0 m, mass m = 5.0 kg, g = 9.8 m/s².\n"
                "Potential energy mgh = 147 J.\n"
                "At the bottom, kinetic energy = 147 J (ignoring air drag)."
            )
            title = "Demo: energy bookkeeping"
        else:
            data = concrete_data or "Measure before and after — numbers must match the equation."
            title = f"Demo: {concept_title[:70]}"
    else:
        data = concrete_data or "Change one variable, measure the outcome, compare to prediction."
        title = f"Demo: {concept_title[:70]}"

    body = (
        f"▶ PREDICT FIRST\n"
        f"{apply_lewin_tactic('predict_before_reveal')}\n\n"
        f"▶ THEN OBSERVE\n{data}\n\n"
        f"▶ VISUAL TRACE\n{apply_lewin_tactic('visual_trajectory', point=concept_title)}"
    )
    narr = " ".join([
        apply_lewin_tactic("predict_before_reveal"),
        apply_lewin_tactic("demo_climax", data=data.replace(chr(10), " ")[:200]),
        apply_lewin_tactic("equation_plus_demo"),
    ])
    return title, body, narr


def lewin_try_it(concept_title: str, *, subject: str) -> str:
    if _is_physicsish(subject, concept_title):
        return (
            "Your turn — predict, then calculate:\n"
            "  A 2.0 m pendulum on Earth (g = 9.8 m/s²).\n"
            "  T = 2π√(L/g) ≈ 2.84 s.\n"
            "  Predict: if L doubles to 4.0 m, does T double? (Compute: ≈ 4.01 s.)"
        )
    return (
        f"Predict first: what changes if you alter one input to \"{concept_title[:50]}\"?\n"
        f"Run the numbers, then check against the rule on the previous slide."
    )


def enrich_lewin_narration(
    narration: str,
    *,
    topic: str,
    heading: str,
    category: str,
    phase: str = "build",
) -> str:
    """Wrap narration with Lewin delivery beats."""
    parts: List[str] = []
    if category == "introduction" or phase == "opening":
        parts.append(apply_lewin_tactic("enthusiasm", topic=topic))
        parts.append(apply_lewin_tactic("everyday_anchor", point=heading))
    elif category == "demo":
        parts.append(apply_lewin_tactic("predict_before_reveal"))
        parts.append(apply_lewin_tactic("countdown_timing"))
    elif category == "example":
        parts.append(apply_lewin_tactic("equation_plus_demo"))
    elif phase == "climax":
        parts.append(apply_lewin_tactic("demo_climax", data=heading))
    if category not in ("summary", "recap") and phase == "build":
        if re.search(r"\d", narration):
            parts.append(apply_lewin_tactic("visual_trajectory", point=heading))
    parts.append(narration.strip())
    if category in ("summary", "recap"):
        parts.append(apply_lewin_tactic("denouement_recap"))
    return " ".join(p for p in parts if p).strip()


def lewin_closing(course_title: str, opening_question: str = "") -> str:
    q = opening_question or f"what {course_title} is really about"
    return (
        f"{apply_lewin_tactic('denouement_recap')}\n"
        f"You can now answer: {q}.\n"
        f"{apply_lewin_tactic('enthusiasm', topic=course_title)}"
    )
