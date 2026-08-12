"""Generate lab homework items across 50+ methodologies."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .methodologies import METHODOLOGY_IDS, get_methodology, list_methodologies
from .models import LabAssignment, LabItem, MediaRef

_WORD = re.compile(r"[A-Za-z0-9']+")


def _tokens(text: str) -> List[str]:
    return [t.lower() for t in _WORD.findall(text or "")]


def _pick_term(passages: Sequence[str], fallback: str = "concept") -> tuple[str, str]:
    for p in passages:
        if ":" in p:
            left, right = p.split(":", 1)
            term, definition = left.strip(), right.strip()
            if term and definition:
                return term, definition
    if passages:
        words = _tokens(passages[0])
        term = words[0] if words else fallback
        return term, passages[0].strip()
    return fallback, f"A key idea about {fallback}."


def _seed(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:8], 16)


def _distractors(term: str, definition: str, n: int = 3) -> List[str]:
    base = [
        f"unrelated to {term}",
        "a measurement of temperature only",
        "a type of punctuation mark",
        f"the opposite of {term}",
        "a historical date with no link",
    ]
    out = []
    for i, d in enumerate(base):
        if len(out) >= n:
            break
        if d.lower() != definition.lower():
            out.append(d)
    while len(out) < n:
        out.append(f"distractor-{len(out)+1}")
    return out[:n]


def _verse_line(context: Dict[str, Any], passages: Sequence[str]) -> tuple[str, str]:
    verse = str(context.get("verse") or context.get("line") or "").strip()
    if verse:
        return verse, str(context.get("meaning_en") or verse)
    if passages:
        return passages[0].strip(), passages[0].strip()
    return "Count with me one two three", "Practice counting one through three."


def generate_item(
    methodology: str,
    *,
    passages: Sequence[str],
    subject: str = "general",
    locale: str = "en",
    context: Optional[Dict[str, Any]] = None,
    difficulty: str = "medium",
) -> LabItem:
    """Build one item for ``methodology`` from curriculum / verse / media context."""
    m = get_methodology(methodology)
    ctx = dict(context or {})
    term, definition = _pick_term(passages, fallback=subject or "topic")
    verse, meaning = _verse_line(ctx, passages)
    media_uri = str(ctx.get("media_uri") or f"lab://{m.family}/{term.lower().replace(' ', '-')}")
    media_kind = {
        "media": "image",
        "audio": "audio",
        "game": "none",
        "interactive": "diagram",
    }.get(m.family, "none")
    if methodology.startswith("video"):
        media_kind = "video"
    if methodology.startswith("listen") or methodology in {
        "pronunciation", "minimal_pairs", "echo_repeat", "oral_response"
    }:
        media_kind = "audio"

    media = MediaRef(
        kind=media_kind,
        uri=media_uri,
        alt=str(ctx.get("alt") or f"Illustration of {term}"),
        transcript=str(ctx.get("transcript") or definition),
        duration_s=float(ctx.get("duration_s") or 12.0),
        meta={"term": term},
    )

    prompt = ""
    options: List[str] = []
    answer_key: Any = None
    rubric: List[str] = []
    pairs: List[Dict[str, str]] = []
    blanks: List[str] = []
    meta: Dict[str, Any] = {"subject": subject}

    mid = m.id

    if mid == "mcq":
        options = [definition] + _distractors(term, definition)
        answer_key = 0
        prompt = f"What best describes '{term}'?"
    elif mid == "multi_select":
        options = [definition, f"{term} relates to {subject}", *_distractors(term, definition, 2)]
        answer_key = [0, 1]
        prompt = f"Select all statements that correctly apply to '{term}'."
    elif mid == "true_false":
        options = ["true", "false"]
        answer_key = "true"
        prompt = f"True or false: {term} — {definition}"
    elif mid == "yes_no_explain":
        options = ["yes", "no"]
        answer_key = {"choice": "yes", "must_include": _tokens(definition)[:3]}
        rubric = ["answers yes/no", "justifies with key idea", "uses own words"]
        prompt = f"Does this passage support that {term} matters in {subject}? Explain."
    elif mid == "short_answer":
        answer_key = definition
        prompt = f"In your own words, explain: {term}."
    elif mid == "essay":
        answer_key = definition
        rubric = ["covers key idea", "coherent", "uses subject terminology"]
        prompt = f"Write a short paragraph connecting ideas about {term} in {subject}."
    elif mid == "fill_blank":
        blanked = definition
        for w in _tokens(term)[:1] or _tokens(definition)[:1]:
            blanked = re.sub(re.escape(w), "____", blanked, count=1, flags=re.I)
        blanks = [term.split()[0] if term.split() else _tokens(definition)[0]]
        answer_key = blanks[0]
        prompt = f"Fill in the blank: {blanked}"
    elif mid == "cloze":
        words = _tokens(definition)[:3] or ["idea", "learn", "practice"]
        blanks = words
        answer_key = "|".join(words)
        prompt = f"Cloze: complete the missing words for '{term}' (join with |)."
    elif mid in ("matching", "definition_match", "memory_match"):
        pairs = [
            {"left": term, "right": definition},
            {"left": f"{term}-related", "right": subject},
            {"left": "unrelated", "right": "punctuation mark"},
        ]
        answer_key = {p["left"]: p["right"] for p in pairs[:2]}
        prompt = f"Match each term to its meaning ({mid})."
    elif mid == "ordering":
        steps = [f"Define {term}", f"Give an example of {term}", f"Check understanding of {term}"]
        answer_key = steps
        options = list(reversed(steps))
        prompt = f"Put these learning steps about {term} in order."
    elif mid == "categorize":
        answer_key = {term: "core-concept", "comma": "mechanics"}
        prompt = f"Categorize: '{term}' and 'comma' into core-concept or mechanics."
    elif mid == "picture_id":
        answer_key = term.lower()
        prompt = f"Identify what this picture shows (hint: {subject})."
        media.kind = "image"
    elif mid == "picture_label":
        answer_key = {"A": term, "B": subject}
        prompt = f"Label parts A and B of the diagram about {term}."
        media.kind = "diagram"
    elif mid == "image_describe":
        answer_key = definition
        rubric = ["names the subject", "notes one detail", "clear language"]
        prompt = f"Describe the image related to {term}."
    elif mid == "hotspot":
        options = ["region-a", "region-b", "region-c"]
        answer_key = "region-a"
        prompt = f"Click the hotspot that highlights {term}."
    elif mid == "video_comprehension":
        answer_key = definition
        prompt = f"After the video about {term}, explain the key idea."
        media.kind = "video"
    elif mid == "video_timestamp":
        options = ["0:05", "0:20", "0:45"]
        answer_key = "0:20"
        prompt = f"At which timestamp is {term} introduced?"
        media.kind = "video"
    elif mid == "listen_comprehension":
        answer_key = definition
        prompt = f"Listen to the clip, then explain {term}."
        media.kind = "audio"
        media.transcript = definition
    elif mid == "listen_dictation":
        answer_key = verse if ctx.get("verse") else definition
        prompt = "Listen and write exactly what you hear."
        media.kind = "audio"
        media.transcript = str(answer_key)
    elif mid == "listen_choose":
        options = [definition] + _distractors(term, definition)
        answer_key = 0
        prompt = f"Listen, then choose the best meaning of {term}."
        media.kind = "audio"
    elif mid == "pronunciation":
        answer_key = term
        prompt = f"Say this aloud clearly: {term}"
        media.kind = "audio"
    elif mid == "minimal_pairs":
        options = [term, term[::-1] if len(term) > 2 else term + "x"]
        answer_key = 0
        prompt = "Which word did you hear?"
        media.kind = "audio"
    elif mid == "echo_repeat":
        answer_key = verse
        prompt = f"Echo this line: {verse}"
        media.kind = "audio"
        media.transcript = verse
    elif mid == "spelling":
        answer_key = term.lower().replace(" ", "")
        prompt = f"Spell the word for: {definition[:80]}"
    elif mid == "grammar_correct":
        broken = f"{term} are important idea"
        answer_key = f"{term} is an important idea"
        prompt = f"Correct the grammar: {broken}"
    elif mid == "grammar_error_id":
        options = [
            f"{term} is an important idea",
            f"{term} are important idea",
            f"{term} be important idea",
        ]
        answer_key = 1
        prompt = "Which sentence has a grammar error?"
    elif mid == "punctuation_fix":
        answer_key = f"{term} is essential."
        prompt = f"Add punctuation: {term} is essential"
    elif mid == "capitalization":
        answer_key = term[:1].upper() + term[1:] if term else "Topic"
        prompt = f"Capitalize properly: {term.lower()}"
    elif mid == "sentence_reorder":
        words = _tokens(f"{term} is important") or ["this", "is", "important"]
        options = list(reversed(words))
        answer_key = words
        prompt = "Reorder the words into a correct sentence."
    elif mid == "vocabulary_context":
        options = [definition] + _distractors(term, definition)
        answer_key = 0
        prompt = f"In context of {subject}, '{term}' most nearly means:"
    elif mid == "idiom_meaning":
        answer_key = meaning
        prompt = f"What does this expression mean in context: '{verse[:60]}'?"
    elif mid == "translate_phrase":
        answer_key = meaning
        prompt = f"Translate/explain this phrase into {locale}: '{term}'"
        meta["target_lang"] = locale
    elif mid == "translate_verse":
        answer_key = meaning
        prompt = f"Translate the meaning of this verse line into {locale}: «{verse}»"
        meta["verse"] = verse
        meta["target_lang"] = locale
        media.transcript = verse
    elif mid == "paraphrase":
        answer_key = definition
        rubric = ["same meaning", "different wording", "complete thought"]
        prompt = f"Paraphrase: {definition}"
    elif mid == "summarize":
        answer_key = definition
        rubric = ["main point", "concise", "accurate"]
        prompt = f"Summarize this passage about {term}: {definition}"
    elif mid == "main_idea":
        answer_key = term
        prompt = f"What is the main idea of: {definition}"
    elif mid == "detail_find":
        answer_key = definition
        prompt = f"Find one supporting detail about {term}."
    elif mid == "inference":
        answer_key = definition
        rubric = ["supported by text", "goes beyond copy", "plausible"]
        prompt = f"What can you infer about {term} from the lesson?"
    elif mid == "reading_comprehension":
        answer_key = definition
        prompt = f"Read and answer: Why does {term} matter in {subject}?"
    elif mid == "identification":
        answer_key = term
        prompt = f"Identify the concept: {definition}"
    elif mid == "analogy":
        answer_key = term
        prompt = f"Leaf is to plant as {definition[:20]}… is to ? (expect related to {term})"
    elif mid == "cause_effect":
        answer_key = definition
        prompt = f"What is an effect related to {term}?"
    elif mid == "compare_contrast":
        answer_key = definition
        rubric = ["names both sides", "states a similarity or difference", "clear"]
        prompt = f"Compare and contrast {term} with a related idea in {subject}."
    elif mid == "claim_evidence":
        answer_key = definition
        rubric = ["states a claim", "cites evidence", "links claim to evidence"]
        prompt = f"Make a claim about {term} and support it with evidence."
    elif mid == "problem_solve":
        answer_key = "42"
        prompt = f"If a class has 40 students and 2 join late, how many learners study {term}? (40+2)"
        meta["expression"] = "40+2"
    elif mid == "show_work":
        answer_key = "42"
        rubric = ["shows steps", "correct arithmetic", "states final answer"]
        prompt = f"Show your work: 40 + 2 while counting peers learning {term}."
    elif mid == "graph_interpret":
        answer_key = "rising"
        prompt = f"A chart of interest in {term} goes 2,4,8 — is the trend rising, flat, or falling?"
    elif mid == "data_table":
        answer_key = "8"
        prompt = f"Table: week1=2, week2=4, week3=8 for {term} practice. What is week3?"
    elif mid == "formula_apply":
        answer_key = "12"
        prompt = f"Apply speed = distance/time. Distance 24, time 2. What is speed? (about {term} demo)"
    elif mid == "procedure_steps":
        steps = ["gather materials", f"demonstrate {term}", "check safety", "reflect"]
        answer_key = steps
        options = list(reversed(steps))
        prompt = f"Order the lab procedure involving {term}."
    elif mid == "code_trace":
        answer_key = "3"
        prompt = "What does this print? x=1; x=x+2; print(x)"
    elif mid == "code_complete":
        answer_key = "return"
        prompt = "Complete: def add(a,b): ____ a+b"
    elif mid == "timeline_place":
        options = ["before", "during", "after"]
        answer_key = "during"
        prompt = f"Where on the lesson timeline do we introduce {term}?"
    elif mid == "map_locate":
        options = ["north", "south", "east", "west"]
        answer_key = "north"
        prompt = f"On the study map, {term} examples are marked — which region?"
    elif mid == "cite_source":
        answer_key = subject
        prompt = f"Cite the lesson source topic for {term} (subject name)."
    elif mid == "debate_stance":
        answer_key = definition
        rubric = ["clear stance", "two reasons", "respectful tone"]
        prompt = f"Argue whether every student should study {term}."
    elif mid == "roleplay_dialogue":
        answer_key = term
        rubric = ["two speaker turns", "on-topic", "polite"]
        prompt = f"Write a short teacher-student dialogue about {term}."
    elif mid == "reflection_journal":
        answer_key = term
        rubric = ["what I learned", "what was hard", "next step"]
        prompt = f"Reflect on learning {term} today."
    elif mid == "peer_review":
        answer_key = "complete"
        rubric = ["checks clarity", "checks accuracy", "gives one suggestion"]
        prompt = f"Peer-review a classmate explanation of {term} using the checklist."
    elif mid == "flashcard_recall":
        answer_key = definition
        prompt = f"Flashcard front: {term}. Produce the back."
    elif mid == "flashcard_recognize":
        options = [definition] + _distractors(term, definition)
        answer_key = 0
        prompt = f"Flashcard: choose the back for '{term}'."
    elif mid == "word_scramble":
        letters = "".join(reversed(term.replace(" ", ""))) or "idea"
        answer_key = term.lower().replace(" ", "")
        prompt = f"Unscramble: {letters}"
    elif mid == "timed_quiz":
        options = [definition] + _distractors(term, definition)
        answer_key = 0
        prompt = f"[Timed] What is {term}?"
        meta["time_limit_s"] = 20
    elif mid == "hangman_style":
        answer_key = term.lower().replace(" ", "")
        prompt = f"Guess the word (hangman) for: {definition[:60]}"
        meta["max_attempts"] = 8
    elif mid == "karaoke_fill":
        words = verse.split()
        missing = words[min(2, len(words) - 1)] if words else "beat"
        shown = " ".join("_" if w == missing else w for w in words) if words else "____"
        answer_key = missing
        blanks = [missing]
        prompt = f"Fill the missing lyric: {shown}"
        meta["verse"] = verse
    elif mid == "syllable_count":
        # rough vowel-group count
        answer_key = str(max(1, len(re.findall(r"[aeiouy]+", term.lower()))))
        prompt = f"How many syllables are in '{term}'?"
    elif mid == "tone_mark":
        answer_key = "1"
        prompt = f"Mark the primary stress/tone unit for '{term}' (enter 1 for first syllable stress in this lab)."
    elif mid == "oral_response":
        answer_key = definition
        rubric = ["on-topic", "complete sentence", "clear"]
        prompt = f"Speak your answer: What is {term}?"
        media.kind = "audio"
    elif mid == "media_caption":
        answer_key = term
        rubric = ["names subject", "one detail", "concise"]
        prompt = f"Write a caption for media about {term}."
    elif mid == "alt_text":
        answer_key = term
        rubric = ["identifies subject", "no fluff", "under 125 chars preferred"]
        prompt = f"Write accessibility alt text for an image of {term}."
    elif mid == "safety_check":
        options = ["wear goggles", "run in lab", "taste chemicals", "ignore spills"]
        answer_key = 0
        prompt = f"Safety: before a demo involving {term}, you should:"
    elif mid == "drag_drop":
        answer_key = {"slot-1": term, "slot-2": subject}
        prompt = f"Drag labels into slots for a {term} diagram."
        media.kind = "diagram"
    elif mid == "crossword_clue":
        answer_key = term.lower().replace(" ", "")
        prompt = f"Crossword clue ({len(answer_key)} letters): {definition[:70]}"
    else:
        # Should be unreachable if registry and branches stay in sync.
        answer_key = definition
        prompt = f"[{mid}] Respond about {term}."

    return LabItem(
        methodology=mid,
        family=m.family,
        grading_mode=m.grading_mode.value,
        prompt=prompt,
        topic=term,
        difficulty=difficulty,
        options=options,
        answer_key=answer_key,
        rubric=rubric,
        media=media,
        pairs=pairs,
        blanks=blanks,
        locale=locale,
        source_ref=str(ctx.get("source_ref") or ctx.get("song_id") or ""),
        meta=meta,
    )


def generate_assignment(
    *,
    title: str,
    passages: Sequence[str],
    subject: str = "general",
    source: str = "",
    locale: str = "en",
    methodologies: Optional[Sequence[str]] = None,
    max_items: int = 12,
    context: Optional[Dict[str, Any]] = None,
    difficulty: str = "medium",
    include_classic_shared: bool = True,
) -> LabAssignment:
    """Generate a mixed-methodology assignment.

    When ``methodologies`` is None, samples a diverse spread across families
    (always including classic mcq/short/essay when include_classic_shared).
    """
    ctx = dict(context or {})
    if methodologies:
        chosen = [get_methodology(m).id for m in methodologies]
    else:
        # Diverse spread: one from many families, capped by max_items.
        by_family: Dict[str, List[str]] = {}
        for m in list_methodologies():
            by_family.setdefault(m.family, []).append(m.id)
        chosen = []
        if include_classic_shared:
            for classic in ("mcq", "short_answer", "essay"):
                if classic not in chosen:
                    chosen.append(classic)
        # Round-robin families for diversity.
        families = sorted(by_family.keys())
        idx = 0
        while len(chosen) < max_items and families:
            fam = families[idx % len(families)]
            bucket = by_family[fam]
            if bucket:
                mid = bucket[_seed(title, fam, str(len(chosen))) % len(bucket)]
                if mid not in chosen:
                    chosen.append(mid)
            idx += 1
            if idx > max_items * len(families) + 5:
                break
        # Fill remaining from full registry if still short.
        for mid in METHODOLOGY_IDS:
            if len(chosen) >= max_items:
                break
            if mid not in chosen:
                chosen.append(mid)
    chosen = chosen[: max(1, max_items)]

    items = [
        generate_item(
            mid,
            passages=passages,
            subject=subject,
            locale=locale,
            context=ctx,
            difficulty=difficulty,
        )
        for mid in chosen
    ]
    return LabAssignment(
        title=title,
        subject=subject,
        source=source,
        locale=locale,
        items=items,
        meta={
            "methodology_count": len(chosen),
            "requested": list(chosen),
        },
    )


def generate_full_battery(
    *,
    passages: Sequence[str],
    subject: str = "general",
    locale: str = "en",
    context: Optional[Dict[str, Any]] = None,
    title: str = "Full methodology battery",
) -> LabAssignment:
    """One item per registered methodology (for quality sweeps / CI)."""
    return generate_assignment(
        title=title,
        passages=passages,
        subject=subject,
        locale=locale,
        methodologies=METHODOLOGY_IDS,
        max_items=len(METHODOLOGY_IDS),
        context=context,
        include_classic_shared=False,
    )


def wrap_shared_classic(
    passages: Sequence[str],
    *,
    title: str,
    subject: str = "general",
    locale: str = "en",
) -> LabAssignment:
    """Also exercise production aoep_shared.homework generate (mcq/short/essay)."""
    try:
        from aoep_shared.homework import generate_assignment as shared_generate
        from aoep_shared.homework import QuestionType
    except Exception:
        return generate_assignment(
            title=title,
            passages=passages,
            subject=subject,
            locale=locale,
            methodologies=["mcq", "short_answer", "essay"],
            max_items=6,
        )

    shared = shared_generate(
        list(passages), title=title, subject=subject, locale=locale, num_questions=4
    )
    items: List[LabItem] = []
    for q in shared.questions:
        if q.type == QuestionType.MCQ:
            mid = "mcq"
            key: Any = q.answer_index
        elif q.type == QuestionType.ESSAY:
            mid = "essay"
            key = q.answer_key or ""
        else:
            mid = "short_answer"
            key = q.answer_key or ""
        items.append(
            LabItem(
                methodology=mid,
                prompt=q.prompt,
                topic=q.topic,
                options=list(q.options or []),
                answer_key=key,
                rubric=list(q.rubric or []),
                locale=locale,
                meta={"from_shared": True, "shared_type": q.type.value},
            )
        )
    return LabAssignment(
        title=title,
        subject=subject,
        source="aoep_shared.homework",
        locale=locale,
        items=items,
        meta={"shared_assignment_id": shared.assignment_id},
    )
