"""Light neural_tts status / empty-text coverage (no live edge-tts)."""

from __future__ import annotations

import pytest

from theodore_course_studio import neural_tts
from theodore_course_studio.neural_tts import TTSUnavailable


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
