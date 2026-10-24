"""Held-out training pool: exam format, frozen passages excluded, no repeat cycle."""

import json
from pathlib import Path

import build_eval_set
import train_pool


ROOT = Path(__file__).resolve().parents[2]


def _lesson(course: Path, slides: list[tuple[str, str]]) -> None:
    course.mkdir(parents=True, exist_ok=True)
    lines = ["LESSON: Sample", "LANGUAGE: en"]
    for index, (title, body) in enumerate(slides, start=1):
        lines.append(f"SLIDE {index} | {title}")
        lines.append(body)
        lines.append(f"NARRATION: {body}")
    (course / "lesson.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_held_out_pool_drops_frozen_passages_and_uses_the_exam_task(tmp_path: Path):
    curriculum = tmp_path / "curriculum"
    frozen_text = (
        "A derivative is the instantaneous rate of change of a function at a point. "
        "The slope of the tangent line is that rate."
    )
    fresh_text = (
        "A file object remembers the path and the mode it was opened with. "
        "Closing the file flushes buffered writes and releases the handle."
    )
    _lesson(curriculum / "calculus-1", [("Derivative", frozen_text)])
    _lesson(curriculum / "python-11-files-and-exceptions", [("Closing files", fresh_text)])
    _lesson(curriculum / "workplace-ethics", [("Honesty", "Be honest with the people who depend on you today.")])
    exam = tmp_path / "frozen.jsonl"
    exam.write_text(json.dumps({
        "id": "stem-recall-calculus-1-00",
        "instruction": f"Passage from the lesson 'Sample':\n{frozen_text}\n\nExplain 'Derivative' using only this passage.",
        "response": "A derivative is the instantaneous rate of change of a function at a point.",
        "passage": frozen_text,
        "tags": ["calculus-1", "recall"],
    }) + "\n", encoding="utf-8")

    sections, dropped = train_pool.held_out_sections(
        curriculum, [exam], include_audio=False,
    )
    assert dropped >= 1
    assert {section.category for section in sections} == {"python-11-files-and-exceptions"}
    rows = train_pool.build_rows(sections, seed=1)
    again = train_pool.build_rows(sections, seed=1)
    assert rows == again
    kinds = [row["tags"][1] for row in rows]
    assert kinds.count("recall") == kinds.count("abstain") == 1
    assert all(row["instruction"].startswith("Passage from the lesson") for row in rows)
    assert all(not row["instruction"].startswith("Explain:") for row in rows)
    blob = "\n".join(row["instruction"] for row in rows)
    assert "instantaneous rate of change" not in blob
    assert "Closing the file flushes" in blob
    abstain = next(row for row in rows if row["tags"][1] == "abstain")
    assert abstain["response"] == build_eval_set.ABSTAIN_REFERENCE
    assert "race" not in json.dumps(rows)


def test_real_exams_share_no_eight_word_window_with_the_pool():
    curriculum = ROOT / "sample-curriculum"
    exams = [
        ROOT / "training" / "data" / "eval_frozen.jsonl",
        ROOT / "training" / "data" / "eval_frozen_stem.jsonl",
    ]
    exact, windows, _sequences = train_pool.load_exam_block(exams)
    sections, dropped = train_pool.held_out_sections(curriculum, exams, include_audio=True)
    assert dropped > 0
    assert len(sections) > 373
    categories = {section.category for section in sections}
    assert "Health & Wellness" in categories
    assert "calculus-1" in categories
    assert "linear-algebra" in categories
    assert "python-11-files-and-exceptions" in categories
    for section in sections:
        assert " ".join(section.text.split()) not in exact
        assert not (train_pool.word_ngrams(section.text) & windows)
    rows = train_pool.build_rows(sections, seed=20261024)
    instructions = {row["instruction"] for row in rows}
    for path in exams:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                assert json.loads(line)["instruction"] not in instructions
    train_rows, eval_rows = train_pool.split_rows(rows, 0.1)
    assert len(train_rows) > 373
    assert eval_rows
    assert train_pool.fingerprint(train_rows) == train_pool.fingerprint(list(train_rows))


def test_unchanged_fingerprint_does_not_train_again():
    digest = "abc123"
    assert train_pool.should_train(digest, None, scored=True)
    assert train_pool.should_train(digest, "other", scored=True)
    assert train_pool.should_train(digest, digest, scored=False)
    assert not train_pool.should_train(digest, digest, scored=True)
    assert not train_pool.should_train("", None, scored=False)


def test_nightly_uses_the_pool_and_skips_an_unchanged_fingerprint():
    nightly = (ROOT / "training" / "spark_nightly.sh").read_text(encoding="utf-8")
    assert "training/train_pool.py" in nightly
    assert "--should-train" in nightly
    assert "last_train_fingerprint.txt" in nightly
    assert "spark_seed_sessions.py" not in nightly
