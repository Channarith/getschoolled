from __future__ import annotations

from theodore_children_webcam_lab.game_engine import (
    AUDIO_BANK,
    PICTURE_WORDS,
    audio_round_public,
    fun_score,
    is_closed_fist,
    next_oh_behave_timer,
    oh_behave_hit,
    score_audio,
    score_spoken,
    trace_pass,
)


def test_a_to_z_picture_catalog_is_complete():
    from theodore_children_webcam_lab.game_engine import PICTURE_EMOJI

    assert set(PICTURE_WORDS) == set("abcdefghijklmnopqrstuvwxyz")
    assert PICTURE_WORDS["a"] == "apple"
    assert set(PICTURE_EMOJI) == set(PICTURE_WORDS.values())
    assert all(PICTURE_EMOJI[word] for word in PICTURE_WORDS.values())


def test_listening_games_cover_voice_and_understanding():
    assert len(AUDIO_BANK) >= 12
    public = audio_round_public("repeat-after-me", 0)
    assert public["speak"]
    assert "accept" not in public and "require" not in public
    heard = "The cat sat on the mat."
    assert score_audio("repeat-after-me", "cat-mat", heard)["passed"] is True
    assert score_audio("repeat-after-me", "cat-mat", "banana")["passed"] is False
    assert score_audio("pronounce-word", "elephant", "elephant")["passed"] is True
    assert score_audio("rhyme-time", "cat", "hat")["passed"] is True
    assert score_audio("rhyme-time", "cat", "dog")["passed"] is False
    assert score_audio("listen-answer", "banana", "yellow")["passed"] is True
    assert score_audio("missing-word", "star", "star")["passed"] is True
    assert score_audio("opposites", "hot", "cold")["passed"] is True
    assert score_audio("explain-it", "seed", "It needs water and sun")["passed"] is True
    assert score_audio("explain-it", "seed", "It needs water")["passed"] is False
    assert score_audio("sum-it-up", "mia", "She went to school")["passed"] is True
    assert score_audio("prove-it", "ice", "Ice is cold water")["passed"] is True
    assert score_audio("prove-it", "ice", "Ice is cold")["passed"] is False
    assert score_audio("story-order", "first", "the bird built a nest")["passed"] is True
    assert score_audio("how-many", "sounds", "three")["passed"] is True
    assert score_audio("how-many", "sounds", "five")["passed"] is False
    assert score_audio("same-or-different", "cats", "same")["passed"] is True
    assert score_audio("same-or-different", "moon", "same")["passed"] is False
    assert score_audio("finish-the-line", "fish", "water")["passed"] is True
    assert score_audio("spell-aloud", "cat", "see ay tee")["passed"] is True
    assert score_audio("spell-aloud", "cat", "dog")["passed"] is False


def test_letter_aliases_and_noun_plurals_are_child_friendly():
    assert score_spoken("A", "ay", kind="letter")["passed"] is True
    assert score_spoken("apple", "apples", kind="noun")["passed"] is True
    assert score_spoken("apple", "truck", kind="noun")["passed"] is False


def test_fun_score_rewards_success_combo_and_persistence():
    first = fun_score(completed=True, attempts=1, duration_ms=2000, combo=2)
    retry = fun_score(
        completed=True,
        attempts=2,
        duration_ms=5000,
        combo=0,
        kept_going=True,
    )
    skipped = fun_score(completed=False, skipped=True)
    assert first["fun_score"] > retry["fun_score"] > skipped["fun_score"]
    assert set(first["components"]) == {
        "play",
        "spark",
        "giggle",
        "keep_going",
        "drop_off",
    }


def test_oh_behave_requires_expression_and_screen_region():
    args = {
        "expected_expression": "happy",
        "actual_expression": "happy",
        "target_region": "top-left",
        "actual_region": "top-left",
        "confidence": 0.8,
    }
    assert oh_behave_hit(**args) is True
    assert oh_behave_hit(**(args | {"actual_region": "center"})) is False
    assert oh_behave_hit(**(args | {"actual_expression": "surprised"})) is False


def test_oh_behave_timer_ladder_is_age_bounded():
    assert next_oh_behave_timer(8000, hit=True, age_band="7-10") == 6000
    assert next_oh_behave_timer(2000, hit=True, age_band="7-10") == 1500
    assert next_oh_behave_timer(4000, hit=True, age_band="4-6") == 4000
    assert next_oh_behave_timer(4000, hit=False, age_band="4-6") == 6000


def test_resting_hand_is_not_a_closed_fist():
    # Distances are in palms (wrist to middle knuckle), matching vision_math.js.
    assert is_closed_fist(finger_count=0, tip_to_wrist=1.1, palm_span=1.0) is True
    assert is_closed_fist(finger_count=0, tip_to_wrist=2.4, palm_span=1.0) is False
    assert is_closed_fist(finger_count=2, tip_to_wrist=1.0, palm_span=1.0) is False


def test_trace_pass_requires_centered_coverage():
    edge = [(0.05, 0.05 + i * 0.01) for i in range(50)]
    glyph = [(0.25 + (i % 10) * 0.05, 0.22 + (i // 10) * 0.12) for i in range(50)]
    assert trace_pass(edge, age_band="7-10") is False
    assert trace_pass(glyph, age_band="7-10") is True
    assert trace_pass(glyph[:10], age_band="7-10") is False
