"""Light neural_tts status / empty-text coverage (no live edge-tts)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from theodore_course_studio import neural_tts
from theodore_course_studio.neural_tts import TTSUnavailable

needs_unprivileged = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root ignores directory permissions",
)


def _read_only_cache(tmp_path: Path) -> Path:
    """A cache path under a directory we are not allowed to create clips in."""
    jail = tmp_path / "jail"
    jail.mkdir()
    jail.chmod(0o500)
    return jail / "tts"


def test_status_reports_languages_and_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("COURSE_STUDIO_TTS_CACHE", str(tmp_path))
    monkeypatch.setenv("COURSE_STUDIO_TTS", "off")
    st = neural_tts.status()
    assert st["languages"] == len(neural_tts.VOICES)
    assert st["cache_dir"] == str(tmp_path)
    assert st["cached_clips"] == 0
    assert st["engine"] in {"none", "cache-only", neural_tts.ENGINE}
    assert "km" in st["voices"]
    assert st["voices"]["km"] == "km-KH-SreymomNeural"


def test_synthesize_empty_text_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("COURSE_STUDIO_TTS_CACHE", str(tmp_path))
    monkeypatch.setenv("COURSE_STUDIO_TTS", "off")
    with pytest.raises(TTSUnavailable, match="nothing to speak"):
        neural_tts.synthesize("", "km")
    with pytest.raises(TTSUnavailable, match="nothing to speak"):
        neural_tts.synthesize("   ", "en")


@needs_unprivileged
def test_cacheable_path_declines_an_unwritable_directory(tmp_path):
    assert neural_tts.cacheable_path(tmp_path / "clip.mp3") == tmp_path / "clip.mp3"
    assert neural_tts.cacheable_path(_read_only_cache(tmp_path) / "clip.mp3") is None


@needs_unprivileged
def test_synthesize_still_renders_when_the_cache_is_unwritable(monkeypatch, tmp_path):
    """A sandboxed HOME must degrade to uncached audio, not raise (was a 500)."""
    monkeypatch.setenv("COURSE_STUDIO_TTS_CACHE", str(_read_only_cache(tmp_path)))
    monkeypatch.setattr(neural_tts, "engine_available", lambda: True)
    monkeypatch.setattr(
        neural_tts,
        "_render",
        lambda text, path, *, voice, rate: path.write_bytes(b"ID3-km-audio"),
    )
    assert neural_tts.synthesize("សូស្តី", "km") == b"ID3-km-audio"


@needs_unprivileged
def test_studio_tts_endpoint_survives_an_unwritable_cache(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from theodore_course_studio.main import app

    monkeypatch.setenv("COURSE_STUDIO_TTS_CACHE", str(_read_only_cache(tmp_path)))
    monkeypatch.setattr(neural_tts, "engine_available", lambda: True)
    monkeypatch.setattr(
        neural_tts,
        "_render",
        lambda text, path, *, voice, rate: path.write_bytes(b"ID3-en-audio"),
    )
    resp = TestClient(app, raise_server_exceptions=False).get(
        "/api/studio/tts", params={"text": "Hello", "language": "en", "gender": "female"}
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == b"ID3-en-audio"
