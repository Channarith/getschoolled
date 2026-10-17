"""Launcher ports stay aligned with each lab README."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "scripts" / "run_theodore_lab.sh"

README_PORTS = {
    "audio_translation": 8041,
    "course_studio": 8040,
    "webcam": 8015,
    "children": 8018,
    "homework": 8098,
    "music": 8097,
    "drive": 8096,
    "rag": 8095,
    "llm": 8019,
}


def test_launcher_ports_match_readme():
    text = LAUNCHER.read_text(encoding="utf-8")
    for name, port in README_PORTS.items():
        assert f"[{name}]={port}" in text
    assert "[course_studio]=theodore_course_studio\n" in text
    assert "theodore_course_studio_lab" not in text
    for name, pkg in {
        "audio_translation": "theodore_audio_translation_lab",
        "course_studio": "theodore_course_studio",
        "webcam": "theodore_webcam_lab",
        "rag": "theodore_rag_lab",
    }.items():
        src = ROOT / "subrepos" / pkg / "src" / pkg
        assert src.is_dir(), name
