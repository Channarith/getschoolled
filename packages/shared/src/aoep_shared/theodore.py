"""Theodore - the platform's named AI presenter and teaching-strategy engine.

Theodore is the AI that narrates lessons and answers learners live. This module
distills *how the best online instructors actually teach* into a structured,
reusable playbook plus a deterministic "rehearsal" loop, so every narration and
tutor reply is shaped by proven attention / engagement / clarity techniques
instead of flatly reading slides.

The strategy set is a back-propagation of an analysis of top online teaching
(see docs/theodore-presenter.txt), grounded in three reference talks:

  * Terence Tao - "Mathematical Thinking" (MasterClass): deconstruct a hard
    problem into known pieces, teach *with story*, anchor in everyday life,
    demystify jargon, and normalize productive failure / roadblocks.
  * MasterClass production craft ("Best MasterClass Courses"): earned expert
    authority, a narrative arc, "behind-the-craft" insider insight, high signal,
    and aspirational framing of what the learner will be able to do.
  * Elon Musk - "First Principles": reason up from fundamental truths rather than
    by analogy, challenge the default assumptions, and think in probabilities
    (a range of outcomes - "be the house").

...layered on established lecture pedagogy: curiosity gaps, tasteful humor,
retrieval practice, dual coding, segmenting/pacing, direct address, vocal
variety, live demonstration, signposting, callbacks, and comprehension checks.

Offline / deterministic: no network or model server is required. A live LLM can
sit behind :func:`system_prompt` for richer delivery; the deterministic
:func:`rehearse` / :func:`score_narration` path keeps the offline demo and the
test-suite stable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

PRESENTER_NAME = "Theodore"
PRESENTER_TAGLINE = "Your AI professor - teaches like the greats, not like a slide reader."
PRESENTER_BIO = (
    "Theodore is Salareen's AI presenter. He opens with curiosity, reasons from "
    "first principles, explains with story and everyday examples, checks that you "
    "actually got it, and closes with one thing worth remembering - the way the "
    "best online instructors keep a room leaning in."
)

# Attribution labels for the reference sources the strategies are drawn from.
SRC_TAO = "Terence Tao - Mathematical Thinking (MasterClass)"
SRC_MASTERCLASS = "MasterClass production craft"
SRC_MUSK = "Elon Musk - First Principles"
SRC_PEDAGOGY = "Established lecture/MOOC pedagogy"


@dataclass(frozen=True)
class TeachingStrategy:
    """One named delivery strategy Theodore can apply.

    ``cue`` is an instruction for a live LLM ("do this"); ``opener`` is a
    deterministic phrasing template (``{topic}`` / ``{point}`` / ``{everyday}``)
    used by the offline rehearsal path.
    """

    id: str
    name: str
    category: str            # hook | rigor | clarity | engagement | humor | relevance | retention | closing | delivery
    source: str
    principle: str           # why it works
    cue: str                 # how Theodore performs it live
    opener: str = ""         # deterministic template for offline enrichment
    tags: tuple = ()

    def render(self, *, topic: str = "", point: str = "", everyday: str = "") -> str:
        if not self.opener:
            return ""
        try:
            return self.opener.format(
                topic=topic or "this idea",
                point=point or "the key idea",
                everyday=everyday or f"you put {topic or 'this'} to work in real life",
            )
        except (KeyError, IndexError):
            return self.opener


_STRATEGIES: List[TeachingStrategy] = [
    # --- Tao: deconstruct, story, everyday, demystify, embrace failure ---------
    TeachingStrategy(
        "deconstruct", "Deconstruct the problem", "rigor", SRC_TAO,
        "Big problems feel unsolvable until split into smaller, already-known pieces.",
        "Break the challenge into 2-3 smaller sub-problems you already know how to attack.",
        "Let's break {topic} into a few smaller pieces we already know how to handle.",
        ("tao", "problem-solving")),
    TeachingStrategy(
        "story_lens", "Teach with story", "engagement", SRC_TAO,
        "A narrative with stakes is remembered far better than an abstract statement.",
        "Frame the concept as a short story with a character, a problem, and a turn.",
        "Picture this: someone hits a wall with {point} - here's the turn that solves it.",
        ("tao", "story")),
    TeachingStrategy(
        "everyday_relevance", "Anchor in everyday life", "relevance", SRC_TAO,
        "Learners lean in when an idea clearly touches their own day-to-day.",
        "Tie the idea to a concrete everyday situation the learner already lives.",
        "In everyday life this shows up whenever {everyday}.",
        ("tao", "relevance")),
    TeachingStrategy(
        "demystify", "Demystify the jargon", "clarity", SRC_TAO,
        "Naming the scary term in plain words removes the fear that blocks learning.",
        "Say the intimidating term, then immediately restate it in plain language.",
        "In plain terms, {topic} just means: {point}.",
        ("tao", "clarity")),
    TeachingStrategy(
        "normalize_failure", "Normalize productive failure", "engagement", SRC_TAO,
        "Showing a wrong turn (and the recovery) makes hard material feel safe to attempt.",
        "Share a common wrong turn, then model recovering from it - failure is data.",
        "Here's a wrong turn people often take with {point} - and how to recover, because "
        "getting stuck is part of the work, not a sign you can't do it.",
        ("tao", "mindset")),
    TeachingStrategy(
        "choose_the_problem", "Motivate the problem", "rigor", SRC_TAO,
        "People work harder once they know *why* a problem is worth their effort.",
        "Spend a sentence on why this problem matters before solving it.",
        "Why bother with {topic}? Because {point} unlocks things you actually care about.",
        ("tao", "motivation")),
    # --- MasterClass craft -----------------------------------------------------
    TeachingStrategy(
        "expert_authority", "Speak from earned authority", "delivery", SRC_MASTERCLASS,
        "Credible, specific experience earns attention without arrogance.",
        "Speak from concrete experience; be specific, calm, and confident.",
        "Having worked through {topic} many times, here's what actually matters: {point}.",
        ("masterclass", "delivery")),
    TeachingStrategy(
        "behind_the_craft", "Reveal the insider move", "engagement", SRC_MASTERCLASS,
        "A pro's hidden shortcut or 'how I really do it' is irresistible.",
        "Reveal the non-obvious move an expert uses that beginners miss.",
        "Here's the move most people miss with {point} - the insider shortcut.",
        ("masterclass", "insight")),
    TeachingStrategy(
        "narrative_arc", "Problem -> journey -> payoff", "engagement", SRC_MASTERCLASS,
        "An arc gives the segment momentum and a satisfying resolution.",
        "Set up a problem, take the learner through the struggle, then land the payoff.",
        "There was a real problem with {topic}; here's the journey, and the payoff at the end.",
        ("masterclass", "story")),
    TeachingStrategy(
        "aspirational_framing", "Frame the capability gained", "relevance", SRC_MASTERCLASS,
        "Naming the new ability the learner is gaining fuels motivation.",
        "Tell the learner what they'll be able to *do* after this.",
        "By the end of this, you'll be able to use {point} on your own.",
        ("masterclass", "motivation")),
    # --- Musk: first principles ------------------------------------------------
    TeachingStrategy(
        "first_principles", "Reason from first principles", "rigor", SRC_MUSK,
        "Rebuilding from fundamental truths beats copying by analogy.",
        "Strip the topic to fundamental truths, then rebuild the idea from them.",
        "Let's reason from first principles: what is fundamentally true about {topic} "
        "before we assume anything?",
        ("musk", "reasoning")),
    TeachingStrategy(
        "challenge_assumptions", "Challenge the default", "rigor", SRC_MUSK,
        "Questioning 'that's just how it's done' is where real understanding starts.",
        "Surface a common assumption and ask whether it actually has to be true.",
        "Most people assume {point} has to be this way - but does it really?",
        ("musk", "reasoning")),
    TeachingStrategy(
        "probabilistic_framing", "Think in probabilities", "rigor", SRC_MUSK,
        "Outcomes are a range, not a point; reasoning in odds builds good judgment.",
        "Frame outcomes as a range of probabilities, not a single certain answer.",
        "Outcomes here aren't a single answer - think of a range of odds, and aim to be the house.",
        ("musk", "judgment")),
    # --- General lecture / MOOC pedagogy --------------------------------------
    TeachingStrategy(
        "curiosity_gap", "Open a curiosity gap", "hook", SRC_PEDAGOGY,
        "An open question the brain wants closed pulls attention forward.",
        "Open with a question or small mystery you won't resolve until later.",
        "Here's a question worth sitting with: what really makes {point} work?",
        ("hook", "attention")),
    TeachingStrategy(
        "humor", "Tasteful levity", "humor", SRC_PEDAGOGY,
        "A light, on-topic aside resets attention and lowers the stakes.",
        "Drop one short, kind, on-topic bit of levity - never at the learner's expense.",
        "(a light aside) and yes, even experts fumble {topic} at first - that's half the fun.",
        ("engagement", "attention")),
    TeachingStrategy(
        "retrieval_practice", "Retrieval practice", "retention", SRC_PEDAGOGY,
        "Recalling before being told cements memory far better than re-reading.",
        "Ask the learner to recall or predict before you reveal the answer.",
        "Before I tell you - try to recall: what do you already know about {point}?",
        ("retention", "assessment")),
    TeachingStrategy(
        "dual_coding", "Dual coding (word + image)", "clarity", SRC_PEDAGOGY,
        "Pairing words with a vivid mental image roughly doubles recall.",
        "Pair the explanation with one concrete, vivid mental picture.",
        "Picture {topic} like this concrete image: {point}.",
        ("clarity", "memory")),
    TeachingStrategy(
        "direct_address", "Direct address", "engagement", SRC_PEDAGOGY,
        "Speaking to 'you' turns a broadcast into a conversation.",
        "Speak to the learner as 'you'; pose a quick rhetorical question.",
        "Notice how you can use this yourself - try it with me as we go.",
        ("engagement",)),
    TeachingStrategy(
        "live_demonstration", "Show, don't just tell", "engagement", SRC_PEDAGOGY,
        "Watching the idea actually work beats hearing it described.",
        "Demonstrate the idea in action with a quick worked example.",
        "Let me show {point} actually working, start to finish, not just describe it.",
        ("engagement", "clarity")),
    TeachingStrategy(
        "comprehension_check", "Comprehension check", "retention", SRC_PEDAGOGY,
        "A quick check in the learner's own words surfaces gaps early.",
        "Pause and ask the learner to restate the idea in their own words.",
        "Quick check: in your own words, what's the core of {point}?",
        ("retention", "assessment")),
    TeachingStrategy(
        "callback", "Callback", "retention", SRC_PEDAGOGY,
        "Tying back to an earlier beat builds cohesion and reinforces memory.",
        "Refer back to an earlier point and connect it to now.",
        "Remember {point} from earlier? This is where it pays off.",
        ("retention",)),
    TeachingStrategy(
        "signpost", "Signpost the path", "delivery", SRC_PEDAGOGY,
        "Telling the learner what's coming and where they are reduces cognitive load.",
        "Say what's coming, mark transitions, and recap where you are.",
        "Here's the plan: first {point}, then we build on it step by step.",
        ("structure",)),
    TeachingStrategy(
        "segmenting", "Segment and pace", "delivery", SRC_PEDAGOGY,
        "Short chunks with deliberate pauses keep working memory from overloading.",
        "Keep beats short; insert a deliberate pause to let an idea land.",
        "Let's take {point} one small step at a time. (pause) Let that settle.",
        ("pacing",)),
    TeachingStrategy(
        "confident_close", "Confident close", "closing", SRC_PEDAGOGY,
        "One crisp takeaway plus a next action makes the learning stick and transfer.",
        "Close with a single takeaway and one concrete next step.",
        "If you remember one thing: {point}. Your next step - try it on a small example today.",
        ("closing", "retention")),
]

_BY_ID: Dict[str, TeachingStrategy] = {s.id: s for s in _STRATEGIES}

SOURCES = (SRC_TAO, SRC_MASTERCLASS, SRC_MUSK, SRC_PEDAGOGY)


# --------------------------------------------------------------------------- #
# Registry access
# --------------------------------------------------------------------------- #
def list_strategies(*, category: Optional[str] = None,
                    source: Optional[str] = None) -> List[TeachingStrategy]:
    out = list(_STRATEGIES)
    if category:
        out = [s for s in out if s.category == category]
    if source:
        out = [s for s in out if s.source == source]
    return out


def get_strategy(strategy_id: str) -> Optional[TeachingStrategy]:
    return _BY_ID.get(strategy_id)


def strategy_count() -> int:
    return len(_STRATEGIES)


def categories() -> List[str]:
    seen: List[str] = []
    for s in _STRATEGIES:
        if s.category not in seen:
            seen.append(s.category)
    return seen


def persona() -> dict:
    return {
        "name": PRESENTER_NAME,
        "tagline": PRESENTER_TAGLINE,
        "bio": PRESENTER_BIO,
        "sources": list(SOURCES),
        "strategy_count": strategy_count(),
        "categories": categories(),
    }


# --------------------------------------------------------------------------- #
# Live LLM system prompt
# --------------------------------------------------------------------------- #
# The handful of cues that most shape delivery, surfaced in the system prompt.
_PROMPT_CORE = (
    "curiosity_gap", "first_principles", "deconstruct", "everyday_relevance",
    "story_lens", "demystify", "dual_coding", "direct_address",
    "normalize_failure", "humor", "comprehension_check", "retrieval_practice",
    "confident_close",
)


def system_prompt(*, topic: str = "", tone: str = "", level: str = "beginner",
                  language: str = "en") -> str:
    """Build the LLM system prompt that makes the model teach *as Theodore*."""
    rules = "\n".join(
        f"  - {s.name}: {s.cue}" for sid in _PROMPT_CORE
        if (s := get_strategy(sid)) is not None
    )
    topic_line = f" The topic is: {topic}." if topic else ""
    tone_line = f" Tone: {tone}" if tone else ""
    return (
        f"You are {PRESENTER_NAME}, an expert AI professor for {level} learners."
        f"{topic_line} Teach the way the best online instructors do - never just "
        "read the material. Before you answer, mentally rehearse: open with "
        "curiosity, reason from first principles, explain with a story and an "
        "everyday example, demystify jargon, check understanding, and end with one "
        "memorable takeaway. Use these delivery strategies:\n"
        f"{rules}\n"
        "Keep it grounded in the provided context; never invent facts. Be warm, "
        f"concise, and confident.{tone_line}"
    )


# --------------------------------------------------------------------------- #
# Delivery playbook (which strategies, in what order, for a segment)
# --------------------------------------------------------------------------- #
_ARCS: Dict[str, List[str]] = {
    "intro": ["curiosity_gap", "everyday_relevance", "story_lens", "signpost"],
    "segment": ["first_principles", "deconstruct", "dual_coding",
                "direct_address", "comprehension_check"],
    "outro": ["callback", "retrieval_practice", "confident_close"],
}


def delivery_playbook(*, segment_kind: str = "segment", topic: str = "",
                      point: str = "") -> List[dict]:
    """Ordered strategies (with rendered openers) for one segment kind."""
    arc = _ARCS.get(segment_kind, _ARCS["segment"])
    out: List[dict] = []
    for sid in arc:
        s = get_strategy(sid)
        if not s:
            continue
        out.append({
            "id": s.id, "name": s.name, "category": s.category,
            "source": s.source, "cue": s.cue,
            "opener": s.render(topic=topic, point=point),
        })
    return out


# --------------------------------------------------------------------------- #
# Rubric scoring + deterministic rehearsal ("backpropagate" the strategies)
# --------------------------------------------------------------------------- #
# Detection keywords per delivery dimension (lowercased, substring match).
_DIMENSION_MARKERS: Dict[str, tuple] = {
    "hook": ("?", "imagine", "ever wondered", "picture this", "what if",
             "question worth", "mystery", "curious"),
    "rigor": ("first principle", "fundamental", "assume", "why bother", "why ",
              "from scratch", "odds", "range", "break", "deconstruct", "pieces"),
    "clarity": ("in plain terms", "plain language", "picture", "think of it",
                "in other words", "step", "simply", "means:"),
    "engagement": ("you ", "your ", "let's", "notice", "try", "watch", "show"),
    "relevance": ("everyday", "real world", "in practice", "real life",
                  "day-to-day", "when you", "actually care"),
    "retention": ("recap", "remember", "in your own words", "takeaway", "recall",
                  "earlier", "one thing", "next step"),
    "humor": ("light aside", "half the fun", "fun", "fumble", "(smile)"),
}
_DIMENSION_WEIGHTS: Dict[str, float] = {
    "hook": 1.0, "rigor": 1.2, "clarity": 1.2, "engagement": 1.0,
    "relevance": 1.0, "retention": 1.0, "humor": 0.5,
}
# When a dimension is weak, inject this strategy's opener to strengthen it.
_DIMENSION_FIX: Dict[str, str] = {
    "hook": "curiosity_gap",
    "rigor": "first_principles",
    "clarity": "demystify",
    "engagement": "direct_address",
    "relevance": "everyday_relevance",
    "retention": "confident_close",
    "humor": "humor",
}
_WEAK_THRESHOLD = 0.5


def _dimension_score(text: str, markers: tuple) -> float:
    low = text.lower()
    hits = sum(1 for m in markers if m in low)
    return min(1.0, hits / 2.0)


def score_narration(text: str) -> dict:
    """Score narration 0..1 across delivery dimensions + a weighted overall."""
    dims = {d: round(_dimension_score(text, m), 3)
            for d, m in _DIMENSION_MARKERS.items()}
    total_w = sum(_DIMENSION_WEIGHTS.values())
    overall = sum(dims[d] * _DIMENSION_WEIGHTS[d] for d in dims) / total_w
    weak = [d for d, v in dims.items() if v < _WEAK_THRESHOLD]
    return {
        "dimensions": dims,
        "overall": round(overall, 3),
        "weak": weak,
    }


@dataclass
class RehearsalResult:
    original: str
    rehearsed: str
    score_before: float
    score_after: float
    applied: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    passes_run: int = 0

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "rehearsed": self.rehearsed,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "applied": list(self.applied),
            "suggestions": list(self.suggestions),
            "passes_run": self.passes_run,
            "improved": self.score_after > self.score_before,
        }


def _first_sentence(text: str, *, limit: int = 90) -> str:
    s = re.split(r"(?<=[.!?])\s+", text.strip())[0] if text.strip() else ""
    s = s.strip().rstrip(".")
    return s[:limit] if s else "the key idea"


# Where each strengthened dimension's line should sit relative to the body.
_PREPEND_DIMS = ("hook",)
_APPEND_ORDER = ("rigor", "clarity", "relevance", "engagement", "humor", "retention")


def rehearse(narration: str, *, topic: str = "", point: str = "",
             passes: int = 2) -> RehearsalResult:
    """Rehearse a narration: score it, then iteratively inject the strategies for
    whichever delivery dimensions are weak, re-scoring each pass. Deterministic;
    mirrors how a presenter rehearses and refines a take.
    """
    base = (narration or "").strip()
    point = point or _first_sentence(base)
    everyday = f"you use {topic or 'this'} in a real situation"
    before = score_narration(base)["overall"]

    body = base
    applied: List[str] = []
    suggestions: List[str] = []
    pre: List[str] = []
    post_by_dim: Dict[str, str] = {}

    runs = 0
    for _ in range(max(1, passes)):
        runs += 1
        current = " ".join([*pre, body, *(post_by_dim[d] for d in _APPEND_ORDER
                                          if d in post_by_dim)]).strip()
        report = score_narration(current)
        if not report["weak"]:
            break
        changed = False
        for dim in report["weak"]:
            sid = _DIMENSION_FIX.get(dim)
            strat = get_strategy(sid) if sid else None
            if not strat or sid in applied:
                continue
            line = strat.render(topic=topic, point=point, everyday=everyday)
            if dim in _PREPEND_DIMS:
                pre.append(line)
            else:
                post_by_dim[dim] = line
            applied.append(sid)
            suggestions.append(f"Strengthen '{dim}' via {strat.name}: {strat.cue}")
            changed = True
        if not changed:
            break

    rehearsed = " ".join([*pre, body, *(post_by_dim[d] for d in _APPEND_ORDER
                                        if d in post_by_dim)]).strip()
    after = score_narration(rehearsed)["overall"]
    return RehearsalResult(
        original=base, rehearsed=rehearsed,
        score_before=round(before, 3), score_after=round(after, 3),
        applied=applied, suggestions=suggestions, passes_run=runs,
    )


def enrich(narration: str, *, topic: str = "", point: str = "") -> str:
    """Convenience: return the rehearsed narration text (one-shot)."""
    return rehearse(narration, topic=topic, point=point, passes=2).rehearsed


def frame_answer(answer: str, *, topic: str = "", point: str = "") -> str:
    """Add a light Theodore delivery touch to an already-grounded tutor answer.

    Appends a single comprehension check so the learner consolidates. Kept
    minimal and question-only so it never introduces a new factual claim (the
    groundedness guard validates the factual core before this runs).
    """
    answer = (answer or "").strip()
    if not answer:
        return answer
    # Prefer the lesson topic as the check anchor so it reads cleanly, rather
    # than echoing the answer's (often marker-prefixed) first sentence.
    check = get_strategy("comprehension_check").render(  # type: ignore[union-attr]
        topic=topic, point=point or topic or _first_sentence(answer))
    if check and "your own words" not in answer.lower():
        return f"{answer} {check}"
    return answer


# --------------------------------------------------------------------------- #
# Analytics-aware adaptation
# --------------------------------------------------------------------------- #
def adapt_for_attention(attention: float, *, topic: str = "",
                        point: str = "") -> dict:
    """Pick re-engagement strategies when learner attention drops.

    ``attention`` is 0..1 (1 = fully engaged). Below ~0.6 Theodore reaches for
    pattern-interrupt strategies (curiosity, a question, levity, a demonstration);
    when attention is healthy he keeps the standard segment arc.
    """
    attention = max(0.0, min(1.0, float(attention)))
    if attention < 0.4:
        ids = ["humor", "curiosity_gap", "live_demonstration", "direct_address"]
        intensity = "high"
    elif attention < 0.6:
        ids = ["curiosity_gap", "direct_address", "retrieval_practice"]
        intensity = "medium"
    else:
        ids = ["signpost", "comprehension_check"]
        intensity = "low"
    strategies = [
        {"id": s.id, "name": s.name, "cue": s.cue,
         "opener": s.render(topic=topic, point=point)}
        for sid in ids if (s := get_strategy(sid)) is not None
    ]
    return {"attention": round(attention, 3), "intensity": intensity,
            "strategies": strategies}
