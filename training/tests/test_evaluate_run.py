"""evaluate.run_eval / main with an injected generator (no torch needed)."""

from __future__ import annotations

import json

import evaluate

ABSTAIN = "The passage does not cover that, so I can't answer it from this material."


def rows():
    return [
        {"id": "r1", "context": {"language": "en", "reading_level": "beginner"}, "instruction": "q1",
         "response": "Plants release oxygen.", "tags": ["Science", "recall"]},
        {"id": "a1", "context": {"language": "en", "reading_level": "advanced"}, "instruction": "q2",
         "response": ABSTAIN, "tags": ["Science", "abstain"]},
        {"id": "h1", "context": {"language": "en"}, "instruction": "hint please", "scorer": "hint",
         "answer": "oxygen", "tags": ["hint"]},
        {"id": "m1", "context": {"language": "km"}, "instruction": "explain", "scorer": "language",
         "response": "សូមស្វាគមន៍ នៅក្នុងមេរៀននេះ", "tags": ["multilingual", "km"]},
    ]


def test_run_eval_reports_f1_and_behaviour():
    answers = {"q1": "Plants release oxygen.", "q2": ABSTAIN, "hint please": "What gas do you breathe out?",
               "explain": "សូមស្វាគមន៍ នៅក្នុងមេរៀននេះ"}

    def generate(prompt: str) -> str:
        for question, answer in answers.items():
            if f"### Question:\n{question}\n" in prompt:
                return answer
        raise AssertionError(prompt)

    out = evaluate.run_eval(rows(), generate)
    assert out["accuracy"] == out["token_f1"] > 0.9
    assert out["behaviour"] == {"abstain": 1.0, "grounded": 1.0, "hint": 1.0, "language": 1.0}
    assert out["by_language"]["km"] == 1.0
    assert out["fairness_gap"] == 0.0 or out["fairness_gap"] >= 0


def test_guessing_model_scores_zero_on_abstain_even_with_decent_overlap():
    out = evaluate.run_eval(rows()[:2], lambda p: "Plants release oxygen. It is a gas.")
    assert out["behaviour"]["abstain"] == 0.0
    assert out["behaviour"]["grounded"] == 1.0


def test_behaviour_only_file_uses_behaviour_mean_as_accuracy():
    items = [{"id": "h", "context": {"language": "en"}, "instruction": "hint", "scorer": "hint", "answer": "oxygen"}]
    out = evaluate.run_eval(items, lambda p: "Try thinking about what plants breathe out?")
    assert out["accuracy"] == out["behaviour_mean"] == 1.0 and out["n"] == 1


def test_rows_without_response_or_scorer_are_skipped():
    out = evaluate.run_eval([{"instruction": "x", "context": {}}], lambda p: "y")
    assert out["n"] == 0 and out["skipped"] == 1


def test_main_scores_several_files_with_one_model_and_writes_each(tmp_path):
    a, b = tmp_path / "eval_a.jsonl", tmp_path / "eval_b.jsonl"
    a.write_text("\n".join(json.dumps(r) for r in rows()[:2]) + "\n", encoding="utf-8")
    b.write_text(json.dumps(rows()[2]) + "\n", encoding="utf-8")
    calls = []

    def generate(prompt):
        calls.append(prompt)
        return ABSTAIN if "q2" in prompt else "Plants release oxygen." if "q1" in prompt else "What gas is it?"

    status = evaluate.main(["--eval", str(a), str(b), "--metrics-dir", str(tmp_path / "m")], generator=generate)
    assert status == 0
    assert (tmp_path / "m" / "eval_a.json").is_file() and (tmp_path / "m" / "eval_b.json").is_file()
    saved = json.loads((tmp_path / "m" / "eval_a.json").read_text(encoding="utf-8"))
    assert saved["eval_file"] == "eval_a.jsonl" and saved["behaviour"]["abstain"] == 1.0
    assert len(calls) == 3


def test_main_rejects_metrics_out_with_several_files(tmp_path):
    f = tmp_path / "e.jsonl"
    f.write_text(json.dumps(rows()[0]) + "\n", encoding="utf-8")
    assert evaluate.main(["--eval", str(f), str(f), "--metrics-out", str(tmp_path / "x.json")],
                         generator=lambda p: "x") == 2


def test_main_fails_on_empty_eval_file(tmp_path):
    f = tmp_path / "empty.jsonl"
    f.write_text("", encoding="utf-8")
    assert evaluate.main(["--eval", str(f)], generator=lambda p: "x") == 1
