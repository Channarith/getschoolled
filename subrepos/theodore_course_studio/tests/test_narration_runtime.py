from __future__ import annotations

import json

from theodore_course_studio.narration_runtime import (
    clear_manifest_cache,
    clip_hints,
)


def test_runtime_manifest_supplies_clip_segments_and_preload(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    rows = []
    for key, url in (("course.one", "one.mp3"), ("course.two", "two.mp3")):
        rows.append(
            {
                "version": 2,
                "slide_key": key,
                "language": "en",
                "gender": "female",
                "audio_url": f"https://cdn.example/{url}",
                "duration": 3.5,
                "segments": [
                    {
                        "index": 0,
                        "text": "One sentence.",
                        "start_s": 0.0,
                        "duration_s": 3.5,
                    }
                ],
            }
        )
    manifest.write_text(
        json.dumps({"version": 2, "complete": True, "records": rows}),
        encoding="utf-8",
    )
    monkeypatch.setenv("COURSE_AUDIO_MANIFEST", str(manifest))
    clear_manifest_cache()
    hints = clip_hints(
        "course.one", "en-US", "female", next_slide_key="course.two"
    )
    assert hints["duration_ms"] == 3500
    assert hints["segments"][0]["text"] == "One sentence."
    assert hints["next_audio_url"].endswith("two.mp3")


def test_runtime_manifest_missing_row_preserves_dynamic_tts(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"version": 2, "complete": True, "records": []}),
        encoding="utf-8",
    )
    monkeypatch.setenv("COURSE_AUDIO_MANIFEST", str(manifest))
    clear_manifest_cache()
    assert clip_hints("missing", "en", "female") == {}
