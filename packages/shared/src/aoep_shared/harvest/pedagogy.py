"""Build teachable, engaging slides from normalized source sections.

Turns raw extracted text into structured lesson slides: opener, concept slides
with key ideas and examples, try-it checkpoints, periodic recaps, and a closing
call-to-action. Speaker notes carry a full teaching script (presentation-skills
enriched) so the PPTX is usable even without a live tutor.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from ..presentation_skills import build_skill_plan, enrich_narration, sanitize_point
from .composition import classify_section
from .examples import extract_worked_examples
from .section_normalize import clean_heading

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

# Short on-slide prompts by pedagogical category (keeps decks lively offline).
_CATEGORY_CALLOUTS = {
    "introduction": "Why this matters",
    "history": "Story time",
    "concept": "Key idea",
    "definition": "Terms to know",
    "example": "Watch this",
    "demo": "Walkthrough",
    "exercise": "Your turn",
    "quiz": "Quick check",
    "qanda": "Think about it",
    "summary": "Takeaway",
    "recap": "Remember",
    "case_study": "Real world",
    "project": "Challenge",
}


def _split_sentences(text: str) -> List[str]:
    parts = _SENTENCE_RE.split((text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _fun_fact(topic: str) -> str:
    try:
        from ..training_agents.knowledge_store import KnowledgeStore
        hits = KnowledgeStore().search(q=topic[:120], limit=1)
        if hits:
            return hits[0].get("fact", "")
    except Exception:
        pass
    return ""


def _expand_thin_content(title: str, sentences: List[str], category: str) -> List[str]:
    """Add teaching scaffolding when the source section is only a sentence or two."""
    if len(sentences) >= 4:
        return sentences
    seed = sentences[0] if sentences else title
    extras: List[str] = []
    if category in ("concept", "definition", "introduction"):
        extras.append(f"Why it matters: this connects to problems you will solve next.")
        extras.append(f"Think of it like: a puzzle piece named \"{title[:60]}\".")
    elif category in ("example", "demo"):
        extras.append("Watch each step — copy the pattern, not just the answer.")
        extras.append("Pause and predict the next step before reading on.")
    elif category in ("history", "case_study"):
        extras.append("Story hook: how did people first discover this idea?")
    elif category in ("exercise", "quiz", "qanda"):
        extras.append("Tip: say your reasoning out loud; it catches gaps fast.")
    else:
        extras.append(f"Key connection: link \"{title[:50]}\" to what you learned earlier.")
    extras.append("Quick check: could you teach this to a friend in one minute?")
    return sentences + extras


def _concept_body(heading: str, sentences: List[str], category: str) -> str:
    callout = _CATEGORY_CALLOUTS.get(category, "Key idea")
    sentences = _expand_thin_content(heading, sentences, category)
    lines: List[str] = []
    if sentences:
        lines.append(f"{callout}: {sentences[0]}")
        for s in sentences[1:6]:
            if len(s) >= 12 and not s.startswith(f"{callout}:"):
                lines.append(s)
    if len(sentences) > 6:
        lines.append(f"More depth: {sentences[6]}")
    return "\n".join(lines) if lines else heading


def _try_it_body(heading: str, sentences: List[str], *, subject: str = "general") -> str:
    subj = (subject or "").lower()
    if any(k in subj for k in ("math", "algebra", "equation")):
        return (
            "Your turn — same pattern, new numbers:\n"
            "  x + y = 9\n"
            "  x − y = 1\n"
            "Find x and y (add the equations: 2x = 10, x = 5, y = 4)."
        )
    seed = sentences[0][:80] if sentences else heading[:80]
    return (
        f"Your turn — apply \"{heading[:60]}\":\n"
        f"1. Use one fact from the slide: {seed}\n"
        f"2. Change one number and redo the step.\n"
        f"3. Verify: does your answer satisfy the original statement?"
    )


def _recap_body(recent_titles: List[str]) -> str:
    items = "\n".join(f"• {t}" for t in recent_titles[-4:])
    return f"What we covered:\n{items}\n\nWhich point clicked for you? Say it aloud once."


def _opening_body(title: str, outline: List[str]) -> str:
    preview = ", ".join(outline[:5])
    tail = "" if len(outline) <= 5 else ", and more"
    return (
        f"Welcome to {title}.\n"
        f"You will learn: {preview}{tail}.\n"
        f"Stick with the checkpoints — they turn reading into real skill."
    )


def _closing_body(title: str) -> str:
    return (
        f"You made it through {title}.\n"
        f"Pick one idea to practice today.\n"
        f"Come back anytime for a refresher — spaced review is how it sticks."
    )


def build_teaching_slides(
    sections: List[Tuple[str, str]],
    *,
    course_title: str,
    fmt: str = "lecture",
    subject: str = "general",
    profile=None,
) -> List["GeneratedSlide"]:
    """Build a full lesson deck from normalized (heading, body) sections."""
    from .generate import GeneratedSlide
    from ..meeting.presentation_matrix import PresentationProfile

    prof = profile or PresentationProfile.resolve(
        fmt if fmt in ("lecture", "workshop", "survey", "drill", "flipped", "lewin") else None,
    )
    use_lewin = prof.arc == "lewin"

    if not sections:
        return []

    headings = [clean_heading(h) for h, _ in sections]
    skill_plan = {p["slide_index"]: p for p in build_skill_plan(headings, topic=course_title)}

    slides: List[GeneratedSlide] = []

    if use_lewin:
        from .lewin_pedagogy import enrich_lewin_narration, lewin_closing, lewin_opening

        opener_body = lewin_opening(course_title, headings)
        opener_narr = enrich_lewin_narration(
            opener_body.replace("\n", " "),
            topic=course_title,
            heading=headings[0] if headings else course_title,
            category="introduction",
            phase="opening",
        )
    else:
        opener_body = _opening_body(course_title, headings)
        opener_narr = opener_body.replace("\n", " ")

    slides.append(GeneratedSlide(
        title=f"Welcome to {course_title[:80]}",
        body=opener_body,
        narration=opener_narr,
        category="introduction",
    ))

    concept_count = 0
    for i, (heading, text) in enumerate(sections):
        title = clean_heading(heading)
        sentences = _split_sentences(text)
        category = classify_section(title, text)

        body = _concept_body(title, sentences, category)
        point = sanitize_point(sentences[0] if sentences else title, topic=course_title)
        plan = skill_plan.get(i, {})
        techniques = plan.get("techniques") if plan else None
        narr = enrich_narration(
            " ".join(sentences[:10]),
            topic=course_title,
            point=point,
            techniques=techniques,
        )
        if plan.get("opening"):
            narr = f"{plan['opening']} {narr}"
        if use_lewin:
            from .lewin_pedagogy import enrich_lewin_narration
            narr = enrich_lewin_narration(
                narr,
                topic=course_title,
                heading=title,
                category=category,
                phase="build",
            )

        fact = _fun_fact(title)
        if prof.fun_facts and fact and concept_count % 3 == 1:
            body += f"\nDid you know? {fact[:180]}"

        if prof.hands_on_callouts and category in ("concept", "example", "demo"):
            body += "\nHands-on: pause and try the step before advancing."

        slides.append(GeneratedSlide(title=title, body=body, narration=narr, category=category))
        concept_count += 1

        # Worked example slide (skip if this section was already an example/demo).
        skip_example = category in ("example", "demo", "exercise", "summary", "recap")
        skip_example = skip_example or "acknowledgment" in title.lower()
        if prof.include_worked_examples and not skip_example:
            for ex in extract_worked_examples(text, title, subject=subject):
                ex_narr = enrich_narration(
                    ex.narration,
                    topic=course_title,
                    point=title,
                    techniques=["worked_example", "check_understanding"],
                )
                slides.append(GeneratedSlide(
                    title=ex.title,
                    body=ex.body,
                    narration=ex_narr,
                    category="example",
                ))
                break  # one worked example per section

        if use_lewin and concept_count >= 1 and category not in (
            "summary", "recap", "exercise",
        ):
            from .lewin_pedagogy import lewin_demo_slide
            concrete = ""
            if slides and slides[-1].category == "example":
                concrete = slides[-1].body[:300]
            demo_title, demo_body, demo_narr = lewin_demo_slide(
                title, subject=subject, concrete_data=concrete, section_text=text,
            )
            slides.append(GeneratedSlide(
                title=demo_title,
                body=demo_body,
                narration=demo_narr,
                category="demo",
            ))

        # Try-it checkpoint after each teaching beat (skip boilerplate sections).
        skip_try = category in ("summary", "recap", "introduction") or "acknowledgment" in title.lower()
        if prof.include_try_it and not skip_try:
            if use_lewin:
                from .lewin_pedagogy import lewin_try_it
                try_body = lewin_try_it(title, subject=subject)
            else:
                try_body = _try_it_body(title, sentences, subject=subject)
            try_narr = enrich_narration(
                try_body.replace("\n", " "),
                topic=course_title,
                point=title,
                techniques=["rhetorical_question", "check_understanding", "call_to_action"],
            )
            slides.append(GeneratedSlide(
                title=f"Try it: {title[:90]}",
                body=try_body,
                narration=try_narr,
                category="exercise",
            ))

        # Recap every N teaching beats (0 = disabled).
        if prof.recap_every_n and concept_count % prof.recap_every_n == 0:
            recent = [s.title for s in slides if s.category not in ("exercise", "recap")][-4:]
            recap_body = _recap_body(recent)
            slides.append(GeneratedSlide(
                title="Quick recap",
                body=recap_body,
                narration=enrich_narration(
                    recap_body.replace("\n", " "),
                    topic=course_title,
                    point="what we just covered",
                    techniques=["recap", "summary_close"],
                ),
                category="recap",
            ))

    if use_lewin:
        from .lewin_pedagogy import lewin_closing
        close_body = lewin_closing(course_title, headings[0] if headings else "")
        close_narr = close_body.replace("\n", " ")
    else:
        close_body = _closing_body(course_title)
        close_narr = close_body.replace("\n", " ")
    slides.append(GeneratedSlide(
        title="You did it!",
        body=close_body,
        narration=close_narr,
        category="summary",
    ))
    return slides
