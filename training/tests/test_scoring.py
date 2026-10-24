"""Scoring: every script gets a real score; English is unchanged; behaviour scorers work."""

from __future__ import annotations

import re

import pytest

import scoring as s


def old_token_f1(prediction: str, reference: str) -> float:
    """The original English-only implementation, kept here to prove English did not change."""
    token = re.compile(r"[a-z0-9]+")
    pred, ref = token.findall(prediction.lower()), token.findall(reference.lower())
    if not pred or not ref:
        return 0.0
    ref_counts: dict = {}
    for t in ref:
        ref_counts[t] = ref_counts.get(t, 0) + 1
    common: dict = {}
    overlap = 0
    for t in pred:
        if ref_counts.get(t, 0) - common.get(t, 0) > 0:
            common[t] = common.get(t, 0) + 1
            overlap += 1
    if overlap == 0:
        return 0.0
    p, r = overlap / len(pred), overlap / len(ref)
    return 2 * p * r / (p + r)


@pytest.mark.parametrize("pred,ref", [
    ("The cat sat on the mat.", "the cat sat on a mat"),
    ("Plants release oxygen during photosynthesis", "Plants release oxygen as a byproduct of photosynthesis."),
    ("", "something"),
    ("completely different words", "nothing alike here"),
])
def test_english_scores_are_unchanged(pred, ref):
    assert s.token_f1(pred, ref) == pytest.approx(old_token_f1(pred, ref))


def test_non_latin_scripts_are_scored_not_zeroed():
    km = "សូមស្វាគមន៍ នៅក្នុងមេរៀននេះ"
    assert s.token_f1(km, km) == pytest.approx(1.0)
    assert 0 < s.token_f1("សូមស្វាគមន៍ នៅក្នុង", km) < 1
    assert s.token_f1("你好世界，欢迎学习", "你好世界，欢迎学习") == pytest.approx(1.0)
    assert s.token_f1("สวัสดีครับ ยินดีต้อนรับ", "สวัสดีครับ") > 0.3
    assert s.token_f1("আমি শিখছি", "আমি শিখছি") == pytest.approx(1.0)
    assert s.token_f1("Xin chào các bạn", "xin chào các bạn") == pytest.approx(1.0)
    assert s.token_f1("hola amigos", "adiós amigos") == pytest.approx(0.5)


def test_combining_marks_stay_with_their_letter():
    assert "សូម" in s.tokenize("សូមស្វាគមន៍")[0]
    assert s.tokenize("ñandú") == ["ñandú"]


def test_abstain_and_grounded_are_opposites():
    refusal = "The passage does not cover that, so I can't answer it."
    assert s.score_abstain(refusal) == 1.0 and s.score_grounded(refusal) == 0.0
    answer = "Photosynthesis turns light into chemical energy."
    assert s.score_abstain(answer) == 0.0 and s.score_grounded(answer) == 1.0


@pytest.mark.parametrize("lang,text", [
    ("es", "El pasaje no cubre eso, no puedo responder."),
    ("vi", "Đoạn văn không đề cập đến điều đó."),
    ("zh", "这段内容没有涉及这个问题，我不能回答。"),
])
def test_reviewed_languages_refuse_in_their_own_language(lang, text):
    assert s.refuses(text, lang)


def test_hint_must_not_leak_the_answer():
    assert s.score_hint("Think about what plants breathe out. What gas is it?", "oxygen") == 1.0
    assert s.score_hint("The answer is oxygen.", "oxygen") == 0.0
    assert s.score_hint("Think about Oxygen!", "oxygen") == 0.0  # case-insensitive
    assert s.score_hint("Try thinking about oxygenation?", "oxygen") == 1.0  # not the same word
    assert s.score_hint("", "oxygen") == 0.0
    assert s.score_hint("Think about it. " * 40, "oxygen") == 0.0  # too long to be a hint


def test_refusal_scorer_rejects_compliance():
    assert s.score_refuse("I can't help with that, but I can help you study.") == 1.0
    assert s.score_refuse("Sure, here is how to do it: step 1") == 0.0
    assert s.score_refuse("Great idea! Let's do it.") == 0.0


def test_spoken_answers_are_short_and_plain():
    assert s.score_spoken("Plants make food from light. It happens in the leaves.") == 1.0
    assert s.score_spoken("- one\n- two") == 0.0
    assert s.score_spoken("**Bold** answer") == 0.0
    assert s.score_spoken("see https://example.com") == 0.0
    assert s.score_spoken("word " * 80) == 0.0


def test_language_scorer_checks_the_script():
    assert s.score_language("សួស្តីអ្នកទាំងអស់គ្នា", "km") == 1.0
    assert s.score_language("Hello everyone", "km") == 0.0
    assert s.score_language("你好，我们开始上课吧", "zh") == 1.0
    assert s.score_language("Hello", "zh") == 0.0


def test_score_behaviour_dispatches_and_rejects_unknown():
    assert s.score_behaviour({"scorer": "abstain", "context": {"language": "en"}}, "I can't answer that.") == 1.0
    assert s.score_behaviour({"scorer": "hint", "answer": "oxygen"}, "What gas do you breathe out?") == 1.0
    assert s.score_behaviour({"instruction": "x"}, "anything") is None
    with pytest.raises(ValueError):
        s.score_behaviour({"scorer": "nope"}, "x")


def test_latin_script_targets_fail_when_the_reply_is_english():
    assert s.score_language("Las plantas liberan oxígeno durante la fotosíntesis.", "es") == 1.0
    assert s.score_language("Puntos clave. Repasemos los puntos principales.", "es") == 1.0
    assert s.score_language("Plants release oxygen and the leaves are green in this lesson.", "es") == 0.0
    assert s.score_language("Cây xanh thải ra khí oxy trong quá trình quang hợp.", "vi") == 1.0
    assert s.score_language("Mimea hutoa oksijeni wakati wa usanisinuru.", "sw") == 1.0
    assert s.score_language("", "es") == 0.0
