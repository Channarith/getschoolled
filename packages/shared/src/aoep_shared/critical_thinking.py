"""Critical Thinking Trainer Agent.

Trains learners in structured reasoning via Socratic questioning, argument
analysis, evidence evaluation, and counterargument generation.  Pure,
dependency-free, and fully testable offline.

Design principles
-----------------
- Sensitive: adapts question depth to learner stress/wellness state and
  mastery level; never shames an incorrect reasoning step.
- Scaffolded: moves from recognition → analysis → synthesis → evaluation
  following Bloom's revised taxonomy.
- Evidence-grounded: every challenge is anchored to a passage or claim
  so the learner has material to reason with rather than pure abstraction.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


class BloomLevel(str, Enum):
    """Bloom's revised taxonomy levels (ascending complexity)."""
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class ArgumentRole(str, Enum):
    CLAIM = "claim"
    EVIDENCE = "evidence"
    WARRANT = "warrant"
    REBUTTAL = "rebuttal"
    QUALIFIER = "qualifier"


BLOOM_ORDER: Tuple[BloomLevel, ...] = (
    BloomLevel.REMEMBER,
    BloomLevel.UNDERSTAND,
    BloomLevel.APPLY,
    BloomLevel.ANALYZE,
    BloomLevel.EVALUATE,
    BloomLevel.CREATE,
)


@dataclass
class SocraticQuestion:
    """One Socratic question anchored to a passage or claim."""
    question_id: str
    text: str
    bloom_level: BloomLevel
    follow_up: str          # follow-up if learner answers correctly
    challenge: str          # counterpoint to deepen reasoning
    hint: str               # gentle scaffold if learner is struggling
    acceptable_keywords: List[str] = field(default_factory=list)


@dataclass
class ArgumentComponent:
    role: ArgumentRole
    text: str
    strength: float = 0.5   # 0..1


@dataclass
class ArgumentMap:
    """Structured breakdown of an argument for analysis tasks."""
    title: str
    components: List[ArgumentComponent] = field(default_factory=list)
    fallacies_present: List[str] = field(default_factory=list)

    def strong_evidence_count(self) -> int:
        return sum(
            1 for c in self.components
            if c.role is ArgumentRole.EVIDENCE and c.strength >= 0.6
        )

    def has_rebuttal(self) -> bool:
        return any(c.role is ArgumentRole.REBUTTAL for c in self.components)


@dataclass
class CriticalThinkingResponse:
    """Learner's answer to a Socratic question + AI evaluation."""
    question_id: str
    learner_answer: str
    bloom_level: BloomLevel
    keywords_found: List[str]
    score: float            # 0..1
    feedback: str
    next_question: Optional[SocraticQuestion] = None
    reasoning_gap: Optional[str] = None


def _make_id(seed: str) -> str:
    return hashlib.md5(seed.encode()).hexdigest()[:10]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# ---------------------------------------------------------------------------
# Socratic question bank builder
# ---------------------------------------------------------------------------
_BLOOM_TEMPLATES = {
    BloomLevel.REMEMBER: (
        "What does '{term}' mean in this context?",
        "Can you recall the key definition from the passage?",
        "Good recall. Now, why does that matter?",
        "What if the definition were different—how would that change things?",
        "Try re-reading: the passage says '{snippet}'.",
    ),
    BloomLevel.UNDERSTAND: (
        "In your own words, how would you explain '{term}'?",
        "What's the main idea the author is conveying here?",
        "Nice. How does that connect to what you already know?",
        "Could someone interpret this differently? What might they say?",
        "Think about the key phrase '{snippet}'—what is it really saying?",
    ),
    BloomLevel.APPLY: (
        "How would you use '{term}' to solve this problem: {scenario}?",
        "Can you give a real-world example where this principle applies?",
        "Great application! What could go wrong with that approach?",
        "What if the situation changed to {counter_scenario}—would your answer still hold?",
        "Start with what you know about '{term}' and work forward.",
    ),
    BloomLevel.ANALYZE: (
        "What assumptions are hidden in the claim: '{claim}'?",
        "What is the relationship between '{term_a}' and '{term_b}'?",
        "You've identified the pattern. What causes it?",
        "Play devil's advocate—what evidence would disprove that?",
        "Break the claim into its parts. Which part is weakest?",
    ),
    BloomLevel.EVALUATE: (
        "How would you judge the strength of this argument: '{claim}'?",
        "What criteria would you use to decide if '{term}' is a good solution?",
        "Strong evaluation. Now defend the opposing view.",
        "If you had to rate this evidence 1–10, what would you give it and why?",
        "Consider: does the evidence actually support the conclusion?",
    ),
    BloomLevel.CREATE: (
        "How would you redesign this approach to avoid the weakness you identified?",
        "What new rule or framework could you propose based on what you've analyzed?",
        "Excellent synthesis! How would you test whether your new idea works?",
        "What would have to be true for your proposal to fail?",
        "Sketch the core logic of your solution in one or two sentences.",
    ),
}


def build_socratic_question(
    term: str,
    passage_snippet: str,
    bloom_level: BloomLevel,
    *,
    scenario: str = "",
    claim: str = "",
    term_b: str = "",
    counter_scenario: str = "",
) -> SocraticQuestion:
    """Construct a Socratic question for a term + passage at a given Bloom level."""
    templates = _BLOOM_TEMPLATES[bloom_level]
    question_text = templates[0].format(
        term=term,
        snippet=passage_snippet[:80],
        scenario=scenario or "your next task",
        claim=claim or term,
        term_a=term,
        term_b=term_b or "the related concept",
        counter_scenario=counter_scenario or "a more complex situation",
    )
    qid = _make_id(f"{term}:{bloom_level}:{passage_snippet[:30]}")
    return SocraticQuestion(
        question_id=qid,
        text=question_text,
        bloom_level=bloom_level,
        follow_up=templates[2].format(
            term=term, snippet=passage_snippet[:80], scenario=scenario or "this context",
            claim=claim or term, term_a=term,
            term_b=term_b or "the related concept",
            counter_scenario=counter_scenario or "a harder variant",
        ),
        challenge=templates[3].format(
            term=term, snippet=passage_snippet[:80], scenario=scenario or "this context",
            claim=claim or term, term_a=term,
            term_b=term_b or "the related concept",
            counter_scenario=counter_scenario or "a harder variant",
        ),
        hint=templates[4].format(
            term=term, snippet=passage_snippet[:80], scenario=scenario or "this context",
            claim=claim or term, term_a=term,
            term_b=term_b or "the related concept",
            counter_scenario=counter_scenario or "a harder variant",
        ),
        acceptable_keywords=[term.lower()] + [w for w in passage_snippet.lower().split()
                                               if len(w) > 4][:5],
    )


def next_bloom_level(current: BloomLevel) -> BloomLevel:
    """Advance one level up Bloom's taxonomy (clamps at CREATE)."""
    idx = BLOOM_ORDER.index(current)
    return BLOOM_ORDER[min(idx + 1, len(BLOOM_ORDER) - 1)]


def bloom_for_mastery(mastery: float) -> BloomLevel:
    """Map topic mastery (0..1) to an appropriate Bloom level."""
    if mastery < 0.25:
        return BloomLevel.REMEMBER
    if mastery < 0.45:
        return BloomLevel.UNDERSTAND
    if mastery < 0.60:
        return BloomLevel.APPLY
    if mastery < 0.75:
        return BloomLevel.ANALYZE
    if mastery < 0.90:
        return BloomLevel.EVALUATE
    return BloomLevel.CREATE


# ---------------------------------------------------------------------------
# Response evaluation
# ---------------------------------------------------------------------------
LOGICAL_FALLACIES = {
    "ad hominem": ["attack", "personal", "character"],
    "straw man": ["misrepresent", "distort", "exaggerate"],
    "false dichotomy": ["only two", "either or", "black and white"],
    "appeal to authority": ["expert says", "authority says", "because they said"],
    "hasty generalization": ["always", "never", "all", "none", "every time"],
    "circular reasoning": ["because it is", "by definition", "it just is"],
    "slippery slope": ["will lead to", "next thing", "eventually"],
}


def detect_fallacies(text: str) -> List[str]:
    """Detect common logical fallacies in a learner's response."""
    lower = (text or "").lower()
    found = []
    for fallacy, markers in LOGICAL_FALLACIES.items():
        if sum(1 for m in markers if m in lower) >= 2:
            found.append(fallacy)
    return found


def evaluate_response(
    question: SocraticQuestion,
    learner_answer: str,
    *,
    wellness_state: str = "ok",
) -> CriticalThinkingResponse:
    """Score a learner's answer and generate constructive feedback."""
    lower = (learner_answer or "").lower()
    keywords_found = [kw for kw in question.acceptable_keywords if kw in lower]
    keyword_score = _clamp01(len(keywords_found) / max(1, len(question.acceptable_keywords)))

    depth_score = _clamp01(len(learner_answer.split()) / 30.0)
    fallacies = detect_fallacies(learner_answer)
    fallacy_penalty = _clamp01(len(fallacies) * 0.15)

    score = _clamp01(0.55 * keyword_score + 0.35 * depth_score - fallacy_penalty)

    # Sensitive tone: soften feedback when learner is stressed/unwell.
    gentle = wellness_state in ("stressed", "unwell", "low_energy")

    if score >= 0.75:
        feedback = (
            "Great reasoning! " + question.follow_up
            if not gentle else
            "Well done — that's a solid answer. " + question.follow_up
        )
        next_bloom = next_bloom_level(question.bloom_level)
        gap = None
    elif score >= 0.45:
        feedback = (
            "You're on the right track. " + question.challenge
            if not gentle else
            "Good effort — here's something to think about further. " + question.challenge
        )
        next_bloom = question.bloom_level
        gap = "reasoning_depth" if depth_score < 0.4 else "keyword_coverage"
    else:
        feedback = (
            "Let's revisit this. " + question.hint
            if not gentle else
            "No worries — let's approach it another way. " + question.hint
        )
        next_bloom = question.bloom_level
        gap = "foundational_recall"

    if fallacies:
        fallacy_note = f" Watch out for: {', '.join(fallacies)}."
        feedback += fallacy_note

    return CriticalThinkingResponse(
        question_id=question.question_id,
        learner_answer=learner_answer,
        bloom_level=question.bloom_level,
        keywords_found=keywords_found,
        score=round(score, 3),
        feedback=feedback,
        reasoning_gap=gap,
    )


# ---------------------------------------------------------------------------
# Argument analysis task
# ---------------------------------------------------------------------------
def build_argument_map(title: str, claims: List[str]) -> ArgumentMap:
    """Parse a list of plain claims into a structured ArgumentMap."""
    components: List[ArgumentComponent] = []
    fallacies: List[str] = []

    for i, claim in enumerate(claims):
        lower = claim.lower()
        if i == 0:
            role = ArgumentRole.CLAIM
            strength = 0.7
        elif any(w in lower for w in ("because", "since", "evidence", "study", "data", "shows")):
            role = ArgumentRole.EVIDENCE
            strength = 0.8
        elif any(w in lower for w in ("however", "but", "despite", "although", "counter")):
            role = ArgumentRole.REBUTTAL
            strength = 0.6
        elif any(w in lower for w in ("usually", "sometimes", "often", "might", "could")):
            role = ArgumentRole.QUALIFIER
            strength = 0.5
        else:
            role = ArgumentRole.WARRANT
            strength = 0.5
        components.append(ArgumentComponent(role=role, text=claim, strength=strength))
        fallacies.extend(detect_fallacies(claim))

    return ArgumentMap(
        title=title,
        components=components,
        fallacies_present=list(set(fallacies)),
    )


def argument_analysis_feedback(arg_map: ArgumentMap) -> str:
    """Return a coaching narrative for a structured argument map."""
    parts = []
    ec = arg_map.strong_evidence_count()
    if ec == 0:
        parts.append("The argument lacks concrete evidence — try adding data or examples.")
    elif ec >= 2:
        parts.append("The evidence base is solid.")
    else:
        parts.append("You have some evidence, but strengthening it further would help.")

    if not arg_map.has_rebuttal():
        parts.append("Consider adding a rebuttal to show you've thought about objections.")

    if arg_map.fallacies_present:
        parts.append(f"Potential logical issues: {', '.join(arg_map.fallacies_present)}.")

    return " ".join(parts) if parts else "Well-structured argument overall."


# ---------------------------------------------------------------------------
# CriticalThinkingTrainer — the stateless agent interface
# ---------------------------------------------------------------------------
class CriticalThinkingTrainer:
    """Stateless agent: given a context, returns questions and evaluations.

    All state (mastery, wellness, bloom progression) lives in the caller's
    session object; this class is pure-function logic.
    """

    def next_question(
        self,
        term: str,
        passage: str,
        *,
        mastery: float = 0.5,
        wellness_state: str = "ok",
        force_bloom: Optional[BloomLevel] = None,
        scenario: str = "",
        claim: str = "",
    ) -> SocraticQuestion:
        """Return the most appropriate next Socratic question for a learner."""
        if wellness_state in ("stressed", "unwell"):
            # Don't push higher Bloom levels when learner is stressed.
            bloom = BloomLevel.UNDERSTAND if mastery < 0.5 else BloomLevel.APPLY
        else:
            bloom = force_bloom or bloom_for_mastery(mastery)
        return build_socratic_question(
            term, passage, bloom,
            scenario=scenario, claim=claim,
        )

    def evaluate(
        self,
        question: SocraticQuestion,
        learner_answer: str,
        *,
        wellness_state: str = "ok",
    ) -> CriticalThinkingResponse:
        return evaluate_response(question, learner_answer, wellness_state=wellness_state)

    def analyze_argument(self, title: str, claims: List[str]) -> str:
        """Build + evaluate an argument map; return coaching feedback."""
        arg_map = build_argument_map(title, claims)
        return argument_analysis_feedback(arg_map)
