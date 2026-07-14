"""CLI tests for the homework worker (mirrors services/harvester/tests/test_harvester_run.py)."""

import io
import json
from contextlib import redirect_stderr, redirect_stdout

from homework.run import main


def _run(argv):
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        rc = main(argv)
    return rc, out_buf.getvalue(), err_buf.getvalue()


def test_instructions():
    rc, out, _ = _run(["--instructions"])
    assert rc == 0
    assert "Homework CLI" in out


def test_generate_from_text_file(tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text(
        "Mitochondria: the powerhouse of the cell that produces ATP.\n\n"
        "Photosynthesis: how plants convert light into chemical energy.\n\n"
        "Osmosis: diffusion of water across a semipermeable membrane.\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    rc, out, err = _run([
        "--generate", str(src), "--title", "Bio HW", "--subject", "biology",
        "--num-questions", "5", "--out-dir", str(out_dir),
    ])
    assert rc == 0
    # stdout is the assignment JSON; a file artifact is written too.
    data = json.loads(out)
    assert data["title"] == "Bio HW"
    assert data["subject"] == "biology"
    assert len(data["questions"]) >= 1
    files = list(out_dir.glob("*.assignment.json"))
    assert len(files) == 1
    assert "Wrote" in err


def test_generate_from_inline_content(tmp_path):
    rc, out, _ = _run([
        "--content", "Gravity: the force that attracts masses.\nInertia: resistance to change in motion.",
        "--title", "Physics HW", "--subject", "physics", "--out-dir", str(tmp_path),
    ])
    assert rc == 0
    data = json.loads(out)
    assert data["subject"] == "physics"
    assert data["questions"]


def test_generate_from_json_slides(tmp_path):
    deck = tmp_path / "deck.json"
    deck.write_text(json.dumps({"slides": [
        {"title": "Variables", "body": "A named container for a value."},
        {"title": "Loops", "body": "Repeat a block of code."},
    ]}), encoding="utf-8")
    rc, out, _ = _run([
        "--generate", str(deck), "--source-type", "slides",
        "--title", "CS HW", "--subject", "programming", "--out-dir", str(tmp_path),
    ])
    assert rc == 0
    data = json.loads(out)
    assert data["questions"]


def test_scan_offline_mock(tmp_path):
    sub = tmp_path / "answers.txt"
    sub.write_text("1. Paris\n2. 42\n3. Because photosynthesis.\n", encoding="utf-8")
    rc, out, _ = _run(["--scan", str(sub), "--expected", "3"])
    assert rc == 0
    data = json.loads(out)
    assert "raw_text" in data
    assert len(data["segments"]) == 3


def test_authorship(tmp_path):
    sub = tmp_path / "essay.txt"
    sub.write_text(
        "The mitochondria is the powerhouse of the cell. It makes energy. "
        "Cells need energy to live. Energy comes from food. This is important.",
        encoding="utf-8",
    )
    rc, out, _ = _run(["--authorship", "--submission-file", str(sub)])
    assert rc == 0
    data = json.loads(out)
    assert data["label"] in {"human", "ai", "uncertain"}
    assert 0.0 <= data["ai_probability"] <= 1.0


def test_generate_then_grade_roundtrip(tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text(
        "Mitochondria: the powerhouse of the cell that produces ATP.\n\n"
        "Photosynthesis: how plants convert light into chemical energy.\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    rc, _, _ = _run([
        "--generate", str(src), "--title", "Bio", "--subject", "biology",
        "--out-dir", str(out_dir),
    ])
    assert rc == 0
    assignment_file = next(out_dir.glob("*.assignment.json"))

    rc, out, err = _run([
        "--grade", str(assignment_file),
        "--answers", "the powerhouse of the cell that produces ATP",
        "plants convert light into chemical energy", "an essay about biology",
        "--subject", "biology",
    ])
    assert rc == 0
    grade = json.loads(out)
    assert grade["max_score"] >= 1
    assert "percentage" in grade
    assert "Graded" in err


def test_no_mode_errors():
    try:
        _run([])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit for no mode")
