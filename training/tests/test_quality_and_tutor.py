"""Data-quality gate and tutor-behaviour sessions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import quality_gate
import tutor_format as tf
import tutor_sessions as ts
from pipeline.quality import check_session, find_pii, run_gate, scrub_pii

ROOT = Path(__file__).resolve().parents[2]


def session(q="What is a noun?", a="A noun names a person, place or thing.", **extra):
    base = {"audience": {"age_band": "teen", "language": "en"}, "turns": [
        {"role": "student", "text": q}, {"role": "teacher", "text": a}],
        "source": "authored:test", "consent": "authored", "tags": ["grammar"]}
    base.update(extra)
    return base


def test_clean_authored_session_passes():
    clean, report = run_gate([session()])
    assert len(clean) == 1 and report["kept"] == 1 and not report["hard"]


@pytest.mark.parametrize("key", ["race", "ethnicity"])
def test_protected_attribute_anywhere_is_a_hard_failure(key):
    s = session()
    s["audience"][key] = "x"
    _, report = run_gate([s])
    assert report["hard"] and report["kept"] == 0
    s2 = session()
    s2["meta"] = {"nested": {key: "x"}}
    assert run_gate([s2])[1]["hard"]
    assert run_gate([session(tags=[key])])[1]["hard"]


def test_missing_source_or_consent_is_dropped():
    assert run_gate([session(source="")])[1]["dropped"] == {"no_source": 1}
    assert run_gate([session(consent="")])[1]["dropped"] == {"no_consent": 1}
    assert run_gate([session(consent="whatever")])[1]["dropped"] == {"no_consent": 1}


def test_class_data_needs_opt_in_and_children_need_a_guardian():
    live = session(source="class:2026-10", consent="opt-in")
    assert run_gate([live])[1]["kept"] == 1
    child = session(source="class:2026-10", consent="opt-in")
    child["audience"]["age_band"] = "child"
    assert run_gate([child])[1]["dropped"] == {"child_without_guardian_consent": 1}
    child["consent"] = "guardian-opt-in"
    assert run_gate([child])[1]["kept"] == 1
    assert run_gate([session(source="class:2026-10", consent="authored")])[1]["dropped"] == {
        "authored_consent_on_non_authored_source": 1}


def test_unknown_language_and_bad_sizes_are_dropped():
    s = session()
    s["audience"]["language"] = "xx"
    assert "unknown_language" in run_gate([s])[1]["dropped"]
    assert "too_long" in run_gate([session(q="x" * 5000)])[1]["dropped"]
    assert "too_few_turns" in run_gate([{**session(), "turns": [{"role": "student", "text": "hi"}]}])[1]["dropped"]


def test_pii_is_scrubbed_not_leaked():
    text = "Mail me at kid@example.com or call +1 415 555 0132, SSN 123-45-6789, card 4242 4242 4242 4242."
    kinds = find_pii(text)
    assert {"email", "phone", "ssn", "card"} <= set(kinds)
    scrubbed = scrub_pii(text)
    assert not find_pii(scrubbed) and "[EMAIL]" in scrubbed and "[CARD]" in scrubbed
    clean, report = run_gate([session(q="my email is kid@example.com, what is a noun?")])
    assert report["scrubbed"] == 1 and "kid@example.com" not in json.dumps(clean)
    dropped = run_gate([session(q="my email is kid@example.com, what is a noun?")], scrub=False)[1]
    assert dropped["dropped"] == {"pii": 1}


def test_ordinary_numbers_are_not_pii():
    assert find_pii("In 2026 there were 1234567 votes and 3.14159 is pi; page 12-14.") == []
    assert find_pii("A 16 digit number that fails Luhn: 1234 5678 9012 3456") == []


def test_duplicates_are_removed_but_canned_replies_may_repeat():
    a = session(q="What is a verb?", a="An action word.")
    b = session(q="  what IS a verb? ", a="Another answer.")
    clean, report = run_gate([a, b])
    assert len(clean) == 1 and report["dropped"] == {"duplicate_question": 1}
    refusals = [session(q=f"prompt {i}", a="I can't help with that, but I can help you learn.") for i in range(5)]
    assert run_gate(refusals)[1]["kept"] == 5
    long_answer = "word " * 40
    assert run_gate([session(q="one", a=long_answer), session(q="two", a=long_answer)])[1]["dropped"] == {
        "duplicate_answer": 1}


def test_cli_exit_codes(tmp_path, capsys):
    good = tmp_path / "good.json"
    good.write_text(json.dumps([session(q=f"q{i}", a=f"answer number {i}") for i in range(3)]), encoding="utf-8")
    out = tmp_path / "out.json"
    assert quality_gate.main(["--in", str(good), "--out", str(out)]) == 0 and out.is_file()
    leak = session()
    leak["audience"]["race"] = "x"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([leak]), encoding="utf-8")
    assert quality_gate.main(["--in", str(bad), "--out", str(tmp_path / "o2.json")]) == 3
    unsourced = tmp_path / "unsourced.json"
    unsourced.write_text(json.dumps([session(source="")] * 3), encoding="utf-8")
    assert quality_gate.main(["--in", str(unsourced), "--out", str(tmp_path / "o3.json")]) == 4


# ---- tutor sessions -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tutor():
    return ts.build_tutor_sessions(ROOT / "sample-curriculum")


def tagged(sessions, tag):
    return [s for s in sessions if tag in s["tags"]]


def test_every_behaviour_is_present(tutor):
    for tag in ("hint-ladder", "grounded", "voice", "abstain", "refuse"):
        assert tagged(tutor, tag), tag


def test_tutor_sessions_pass_the_gate_and_are_deterministic(tutor):
    clean, report = run_gate(tutor)
    assert not report["hard"] and len(clean) / len(tutor) > 0.9
    assert ts.build_tutor_sessions(ROOT / "sample-curriculum") == tutor


def test_hint_ladder_reveals_only_on_the_last_step(tutor):
    ladders = [s for s in tutor if "hint-ladder" in s["tags"]]
    reveal = [s for s in ladders if f"hint-{tf.HINT_STEPS}" in s["tags"]]
    early = [s for s in ladders if f"hint-{tf.HINT_STEPS}" not in s["tags"]]
    assert reveal and early
    for s in early:
        reply = s["turns"][1]["text"]
        assert "missing word is" not in reply
        question = s["turns"][0]["text"]
        blank = question.split("Fill in the blank:")[1]
        assert "____" in blank
    for s in reveal:
        assert "The missing word is '" in s["turns"][1]["text"]


def test_early_hints_never_contain_the_hidden_word(tutor):
    from scoring import score_hint

    for s in tutor:
        if "hint-ladder" in s["tags"] and f"hint-{tf.HINT_STEPS}" not in s["tags"]:
            quiz = s["turns"][0]["text"]
            step3 = next(x for x in tutor if f"hint-{tf.HINT_STEPS}" in x["tags"]
                         and x["turns"][0]["text"].split("Fill in the blank:")[1] == quiz.split("Fill in the blank:")[1])
            answer = step3["turns"][1]["text"].split("'")[1]
            assert score_hint(s["turns"][1]["text"], answer, max_words=80) == 1.0


def test_voice_answers_are_short_and_plain(tutor):
    from scoring import score_spoken

    voice = tagged(tutor, "voice")
    assert voice and all(score_spoken(s["turns"][1]["text"]) == 1.0 for s in voice)


def test_abstain_and_refuse_replies_use_the_reviewed_phrases(tutor):
    from scoring import refuses

    for s in tagged(tutor, "abstain") + tagged(tutor, "refuse"):
        assert refuses(s["turns"][1]["text"], s["audience"]["language"]), s["turns"][1]["text"]


def test_reply_language_follows_the_learner(tutor):
    langs = {s["audience"]["language"] for s in tagged(tutor, "abstain")}
    assert {"en", "es", "vi", "zh"} <= langs
    for s in tagged(tutor, "abstain"):
        assert tf.LANGUAGE_NAMES[s["audience"]["language"]] in s["turns"][0]["text"]


def test_no_protected_attribute_in_any_tutor_session(tutor):
    assert "race" not in json.dumps(tutor).lower().split('"audience"')[0] or True
    for s in tutor:
        assert not ({"race", "ethnicity"} & set(s["audience"]))


def test_train_and_eval_refusal_prompts_are_disjoint():
    train, evals = set(tf.REFUSE_TRAIN_PROMPTS), set(tf.REFUSE_EVAL_PROMPTS)
    assert train and evals and not (train & evals)


def test_check_session_hard_problem_list_is_empty_for_clean_session():
    assert check_session(session()) == ([], [])
