"""AI presentation skills — a registry of teaching/presenting techniques.

Presentation quality is more than reading slides. This module provides a registry
of named techniques (signposting, analogy, rhetorical questions, recaps, worked
examples, contrast, storytelling hooks, comprehension checks, ...) that the
lesson/presenter layer can apply to narration to make delivery engaging and
pedagogically effective.

Each technique has a deterministic ``template`` with ``{topic}`` / ``{point}``
placeholders so it works offline; an LLM polish layer can sit behind the same
``apply`` signature. The registry is extensible via content packs of kind
``presentation`` (records: {id, name, description, category, template, tags}).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class PresentationTechnique:
    id: str
    name: str
    description: str
    category: str            # opening | structure | engagement | clarity | retention | closing
    template: str
    tags: tuple = ()

    def apply(self, *, topic: str = "", point: str = "") -> str:
        try:
            return self.template.format(topic=topic or "this topic", point=point or "the key idea")
        except (KeyError, IndexError):
            return self.template


_BUILTIN: List[PresentationTechnique] = [
    PresentationTechnique(
        "hook_question", "Opening hook (question)", "Open with a question that sparks curiosity.",
        "opening", "Have you ever wondered {point}? Let's find out.", ("opening", "engagement")),
    PresentationTechnique(
        "hook_story", "Story hook", "Open with a short relatable scenario.",
        "opening", "Picture this: {point}. That's exactly what {topic} helps us with.", ("opening",)),
    PresentationTechnique(
        "agenda_signpost", "Agenda signpost", "Tell the audience what is coming.",
        "structure", "Here's our plan: first we'll cover {point}, then build on it step by step.",
        ("structure",)),
    PresentationTechnique(
        "signpost", "Section signpost", "Mark transitions between sections.",
        "structure", "Now that we've set the stage, let's turn to {point}.", ("structure",)),
    PresentationTechnique(
        "transition", "Smooth transition", "Bridge from the previous idea to the next.",
        "structure", "That leads us naturally to {point}.", ("structure",)),
    PresentationTechnique(
        "analogy", "Analogy", "Explain with a familiar comparison.",
        "clarity", "Think of {topic} like a familiar everyday system: {point}.",
        ("clarity", "engagement")),
    PresentationTechnique(
        "contrast", "Compare and contrast", "Clarify by contrasting two ideas.",
        "clarity", "It helps to compare: on one hand {point}; on the other, the opposite case.",
        ("clarity",)),
    PresentationTechnique(
        "chunking", "Chunking", "Break a big idea into small steps.",
        "clarity", "Let's break {point} into a few small, manageable steps.", ("clarity",)),
    PresentationTechnique(
        "worked_example", "Worked example", "Show a concrete example end to end.",
        "clarity", "Here's a concrete example of {point}, worked through start to finish.",
        ("clarity", "retention")),
    PresentationTechnique(
        "real_world_link", "Real-world link", "Connect to a real-world application.",
        "engagement", "In the real world, {point} shows up whenever you {topic} in practice.",
        ("engagement",)),
    PresentationTechnique(
        "rhetorical_question", "Rhetorical question", "Prompt the audience to think.",
        "engagement", "So what would happen if {point}? Take a second to consider.",
        ("engagement",)),
    PresentationTechnique(
        "callback", "Callback", "Refer back to an earlier point to build cohesion.",
        "retention", "Remember {point} from earlier? Here's where it pays off.", ("retention",)),
    PresentationTechnique(
        "emphasis", "Emphasis", "Flag the single most important idea.",
        "retention", "If you remember one thing, make it this: {point}.", ("retention",)),
    PresentationTechnique(
        "check_understanding", "Comprehension check", "Pause to confirm understanding.",
        "engagement", "Quick check: can you explain {point} in your own words?",
        ("engagement", "assessment")),
    PresentationTechnique(
        "pause", "Strategic pause", "Insert a deliberate pause for emphasis or processing.",
        "engagement", "(pause) Let that idea about {point} settle for a moment.", ("engagement",)),
    PresentationTechnique(
        "recap", "Recap", "Summarize what was just covered.",
        "retention", "To recap: the heart of {point} is what we just walked through.",
        ("retention", "closing")),
    PresentationTechnique(
        "summary_close", "Summary close", "Close by tying everything together.",
        "closing", "Putting it together: {topic} comes down to {point}.", ("closing",)),
    PresentationTechnique(
        "call_to_action", "Call to action", "End with a concrete next step.",
        "closing", "Your next step: practice {point} on a small example today.", ("closing",)),
    PresentationTechnique(
        "storytelling_arc", "Storytelling arc", "Frame content as a problem-journey-resolution.",
        "engagement", "There was a problem with {topic}; here's the journey to solving {point}.",
        ("engagement",)),
    PresentationTechnique(
        "scaffolding", "Scaffolding", "Build from what the learner already knows.",
        "clarity", "You already know the basics; we'll build from there toward {point}.",
        ("clarity",)),
]

_BUILTIN_BY_ID: Dict[str, PresentationTechnique] = {t.id: t for t in _BUILTIN}

_cache: dict = {"fingerprint": None, "by_id": None}


def _pack_techniques() -> Dict[str, PresentationTechnique]:
    try:
        from .content_packs import load_records, pack_fingerprint

        fp = pack_fingerprint("presentation")
    except Exception:  # pragma: no cover
        return dict(_BUILTIN_BY_ID)
    if _cache["fingerprint"] == fp and _cache["by_id"] is not None:
        return _cache["by_id"]
    merged: Dict[str, PresentationTechnique] = dict(_BUILTIN_BY_ID)
    for rec in load_records("presentation"):
        tid = rec.get("id")
        template = rec.get("template")
        if not (tid and template):
            continue
        merged[str(tid)] = PresentationTechnique(
            id=str(tid),
            name=str(rec.get("name", tid)),
            description=str(rec.get("description", "")),
            category=str(rec.get("category", "engagement")),
            template=str(template),
            tags=tuple(rec.get("tags", ()) or ()),
        )
    _cache["fingerprint"] = fp
    _cache["by_id"] = merged
    return merged


def list_techniques(*, category: Optional[str] = None) -> List[PresentationTechnique]:
    techs = list(_pack_techniques().values())
    if category:
        techs = [t for t in techs if t.category == category]
    return techs


def get_technique(technique_id: str) -> Optional[PresentationTechnique]:
    return _pack_techniques().get(technique_id)


def technique_count() -> int:
    return len(_pack_techniques())


def apply_technique(technique_id: str, *, topic: str = "", point: str = "") -> str:
    tech = get_technique(technique_id)
    if tech is None:
        return ""
    return tech.apply(topic=topic, point=point)


# A sensible default delivery arc for a single slide/segment.
DEFAULT_ARC = ("signpost", "analogy", "worked_example", "check_understanding", "recap")


def enrich_narration(
    narration: str,
    *,
    topic: str = "",
    point: str = "",
    techniques: Optional[List[str]] = None,
) -> str:
    """Wrap raw narration with presentation-technique phrasing."""
    arc = techniques if techniques is not None else list(DEFAULT_ARC)
    point = point or (narration.split(".")[0][:80] if narration else "the key idea")
    opener = apply_technique(arc[0], topic=topic, point=point) if arc else ""
    closer = apply_technique(arc[-1], topic=topic, point=point) if len(arc) > 1 else ""
    body = narration.strip()
    parts = [p for p in (opener, body, closer) if p]
    return " ".join(parts).strip()


def build_skill_plan(headings: List[str], *, topic: str = "") -> List[dict]:
    """Assign a rotating set of techniques across a deck for varied delivery."""
    arcs = [
        ["hook_question", "analogy", "worked_example", "recap"],
        ["hook_story", "chunking", "real_world_link", "check_understanding"],
        ["agenda_signpost", "contrast", "emphasis", "summary_close"],
        ["signpost", "scaffolding", "rhetorical_question", "call_to_action"],
    ]
    plan: List[dict] = []
    for i, heading in enumerate(headings):
        arc = arcs[i % len(arcs)]
        plan.append({
            "slide_index": i,
            "heading": heading,
            "techniques": arc,
            "opening": apply_technique(arc[0], topic=topic or heading, point=heading),
            "closing": apply_technique(arc[-1], topic=topic or heading, point=heading),
        })
    return plan
