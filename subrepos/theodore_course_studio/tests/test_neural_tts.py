"""Light neural_tts status / empty-text coverage (no live edge-tts)."""

from __future__ import annotations

import os
import shutil
import subprocess
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


def test_every_supported_language_has_its_own_voice():
    from theodore_course_studio.studio_languages import SUPPORTED_LANGUAGES

    assert set(neural_tts.VOICES) == set(SUPPORTED_LANGUAGES)
    for code, (female, male) in neural_tts.VOICES.items():
        assert female.endswith("Neural")
        assert male.endswith("Neural")
        if code != "en":
            assert not female.startswith("en-")
            assert not male.startswith("en-")


def test_status_reports_languages_and_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("COURSE_STUDIO_TTS_CACHE", str(tmp_path))
    monkeypatch.setenv("COURSE_STUDIO_TTS", "off")
    st = neural_tts.status()
    assert st["languages"] == len(neural_tts.VOICES)
    assert st["cache_dir"] == str(tmp_path)
    assert st["cached_clips"] == 0
    assert st["engine"] in {"none", "cache-only", neural_tts.ENGINE}
    assert isinstance(st["gapless_stitch"], bool)
    assert "km" in st["voices"]
    assert st["voices"]["km"] == "km-KH-SreymomNeural"


def test_course_narration_keeps_one_voice_on_long_pages(monkeypatch, tmp_path):
    voices: list[str] = []
    monkeypatch.setenv("COURSE_STUDIO_TTS_CACHE", str(tmp_path))

    def fake(text, language, *, rate=1.0, gender="female", voice=""):
        voices.append(voice)
        return b"ID3" + text[:12].encode("utf-8")

    monkeypatch.setattr(neural_tts, "synthesize", fake)
    monkeypatch.setattr(
        neural_tts,
        "stitch_mp3_chunks",
        lambda chunks: b"".join(chunks),
    )
    long = "A red octagon means a complete stop. " * 80
    assert len(neural_tts.split_for_speech(long)) > 1
    audio = neural_tts.synthesize_course(long, "en", gender="female")
    assert audio.startswith(b"ID3")
    assert voices
    assert set(voices) == {"en-US-AriaNeural"}
    rendered_calls = len(voices)
    assert neural_tts.synthesize_course(long, "en", gender="female") == audio
    assert len(voices) == rendered_calls


def test_split_for_speech_understands_non_latin_sentence_marks():
    text = ("这是第一句话。" * 90) + ("នេះជាប្រយោគ។" * 90)
    chunks = neural_tts.split_for_speech(text, limit=160)
    assert len(chunks) > 2
    assert all(0 < len(chunk) <= 160 for chunk in chunks)
    assert "".join(chunks) == text


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is required")
def test_stitch_mp3_chunks_outputs_one_decodable_file(tmp_path):
    chunks: list[bytes] = []
    for index, frequency in enumerate((440, 660)):
        path = tmp_path / f"tone-{index}.mp3"
        subprocess.run(
            [
                shutil.which("ffmpeg") or "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:duration=0.12",
                "-codec:a",
                "libmp3lame",
                "-y",
                str(path),
            ],
            check=True,
        )
        chunks.append(path.read_bytes())
    combined = neural_tts.stitch_mp3_chunks(chunks)
    output = tmp_path / "combined.mp3"
    output.write_bytes(combined)
    probe = subprocess.run(
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(output),
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
    )
    assert probe.returncode == 0
    assert len(combined) > max(map(len, chunks))


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
