"""Every Theodore browser lab must expose the shared native-audio option."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LABS = (
    "theodore_audio_translation_lab",
    "theodore_children_webcam_lab",
    "theodore_course_studio",
    "theodore_drive_lab",
    "theodore_homework_lab",
    "theodore_music_lab",
    "theodore_rag_lab",
    "theodore_webcam_lab",
)


def _main(lab: str) -> str:
    return (
        ROOT / "subrepos" / lab / "src" / lab / "main.py"
    ).read_text(encoding="utf-8")


def test_every_theodore_lab_installs_and_injects_live_audio():
    for lab in LABS:
        source = _main(lab)
        assert "install_live_audio_routes(app," in source, lab
        assert "inject_client(" in source, lab


def test_tts_pages_yield_to_native_speech_to_speech():
    pages = {
        "children": ROOT
        / "subrepos/theodore_children_webcam_lab/src/"
        "theodore_children_webcam_lab/static/app.js",
        "music": ROOT
        / "subrepos/theodore_music_lab/src/theodore_music_lab/music_page.py",
        "translation": ROOT
        / "subrepos/theodore_audio_translation_lab/src/"
        "theodore_audio_translation_lab/studio_page.py",
        "webcam": ROOT
        / "subrepos/theodore_webcam_lab/src/theodore_webcam_lab/monitor_page.py",
        "course": ROOT
        / "subrepos/theodore_course_studio/src/theodore_course_studio/studio_page.py",
    }
    for name, path in pages.items():
        source = path.read_text(encoding="utf-8")
        assert "__THEODORE_LIVE_AUDIO_ACTIVE__" in source, name
        assert "theodore-live-audio" in source, name
