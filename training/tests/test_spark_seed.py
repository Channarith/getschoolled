"""STEM seed sessions and the Spark timer contract (no GPU)."""

import json
from pathlib import Path

import export
import spark_seed_sessions as seed


def test_stem_allowlist_skips_non_stem():
    assert seed.is_stem_course("geometry")
    assert seed.is_stem_course("python-01-getting-started")
    assert seed.is_stem_course("host-host-math-deck-abc")
    assert not seed.is_stem_course("workplace-ethics")
    assert not seed.is_stem_course("nursing-judgment")


def test_parse_lesson_uses_narration():
    text = "\n".join([
        "LESSON: Fractions",
        "LANGUAGE: en",
        "SLIDE 1 | Numerator",
        "The top number.",
        "NARRATION: The numerator is the top number.",
        "FACT: Denominators are not zero.",
    ])
    lesson, language, slides = seed.parse_lesson(text)
    assert lesson == "Fractions"
    assert language == "en"
    assert slides == [("Numerator", "The numerator is the top number.")]


def test_build_sessions_exports_without_protected_attributes(tmp_path: Path):
    course = tmp_path / "curriculum" / "geometry"
    course.mkdir(parents=True)
    (course / "lesson.txt").write_text(
        "LESSON: Geometry\nLANGUAGE: en\n"
        "SLIDE 1 | Triangles\nA triangle has three sides.\n"
        "NARRATION: A triangle has three sides.\n",
        encoding="utf-8",
    )
    other = tmp_path / "curriculum" / "workplace-ethics"
    other.mkdir(parents=True)
    (other / "lesson.txt").write_text(
        "LESSON: Ethics\nSLIDE 1 | Honesty\nBe honest.\nNARRATION: Be honest.\n",
        encoding="utf-8",
    )
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps([
        {
            "audience": {"language": "en", "reading_level": "beginner", "race": "redacted-by-export"},
            "turns": [
                {"role": "student", "text": "what gas do plants release?"},
                {"role": "teacher", "text": "Plants release oxygen."},
            ],
            "rewards": [1.0],
            "tags": ["intro-to-photosynthesis"],
        }
    ]), encoding="utf-8")

    sessions = seed.build_sessions(tmp_path / "curriculum", sample, seed=1)
    titles = [s["turns"][0]["text"] for s in sessions]
    assert any("Triangles" in t for t in titles)
    assert all("Honesty" not in t for t in titles)
    geometry = next(s for s in sessions if "Triangles" in s["turns"][0]["text"])
    assert "race" not in geometry["audience"]
    assert "ethnicity" not in geometry["audience"]
    # The sample row may still carry a protected field; export must drop it.

    raw = tmp_path / "sessions.json"
    raw.write_text(json.dumps(sessions), encoding="utf-8")
    out = tmp_path / "train.jsonl"
    rc = export.main(["--in", str(raw), "--out", str(out), "--eval-out", str(tmp_path / "eval.jsonl"),
                      "--eval-split", "0.5"])
    assert rc == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert rows
    for row in rows:
        assert "race" not in row["context"]
        assert "ethnicity" not in row["context"]


def test_spark_timer_contract():
    root = Path(__file__).resolve().parents[1]
    service = (root / "systemd" / "aoep-spark-train.service").read_text(encoding="utf-8")
    timer = (root / "systemd" / "aoep-spark-train.timer").read_text(encoding="utf-8")
    install = (root / "systemd" / "install-user-timer.sh").read_text(encoding="utf-8")
    nightly = (root / "spark_nightly.sh").read_text(encoding="utf-8")
    assert "@REPO@" in service
    assert "OnCalendar=" in timer
    assert "--enable" in install
    assert ".gs-gpu.lock" in nightly
    assert "stem-qlora" in nightly
