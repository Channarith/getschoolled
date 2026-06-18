"""AI-vs-human authorship detection tests (Phase 8)."""

from aoep_shared.homework import detect_authorship

# Uniform, machine-like sentence structure (low burstiness).
AI_LIKE = (
    "The mitochondria produces energy for the cell. "
    "The nucleus stores the genetic material safely. "
    "The ribosome assembles proteins from amino acids. "
    "The membrane controls what enters the cell."
)

# Human-like: mix of very short and long sentences (high burstiness).
HUMAN_LIKE = (
    "Cells are tiny. "
    "But honestly the mitochondria is the part I always remember because my teacher "
    "kept calling it the powerhouse and it stuck with me forever. "
    "Yeah. "
    "The nucleus though, that one holds all the important genetic instructions that the "
    "cell needs to copy itself and keep going day after day."
)


def test_ai_like_text_scores_ai():
    v = detect_authorship(AI_LIKE)
    assert v.label == "ai"
    assert v.ai_probability >= 0.6


def test_human_like_text_scores_human():
    v = detect_authorship(HUMAN_LIKE)
    assert v.label == "human"
    assert v.ai_probability <= 0.4


def test_handwriting_shifts_toward_human():
    typed = detect_authorship(AI_LIKE, handwritten=False)
    hand = detect_authorship(AI_LIKE, handwritten=True)
    assert hand.ai_probability < typed.ai_probability
    assert hand.label in ("human", "uncertain")


def test_too_short_is_uncertain_or_human():
    v = detect_authorship("Yes.")
    assert v.label in ("uncertain", "human")
    assert "sentence_count" in v.signals
