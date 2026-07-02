"""Voice profile registry + clone TTS routing."""

import json
from pathlib import Path

import pytest

from aoep_shared.meeting.clone_tts import clone_engine_priority, synthesize_cloned
from aoep_shared.meeting.voice_profiles import (
    CLONE_VOICE_PREFIX,
    VoiceProfile,
    discover_voice_profiles,
    get_voice_profile,
    parse_voice_token,
    save_voice_profile,
)


def test_voice_profile_roundtrip(tmp_path):
    voices_root = tmp_path / "voices"
    sample = voices_root / "demo" / "sample.wav"
    sample.parent.mkdir(parents=True)
    sample.write_bytes(b"RIFF" + b"\0" * 128)
    prof = VoiceProfile(
        id="demo",
        label="Demo Voice",
        sample_path="sample.wav",
        tts_engine="chatterbox",
        present_mode="lewin",
    )
    save_voice_profile(prof, out_root=voices_root)
    loaded = get_voice_profile("demo", repo_root=tmp_path)
    assert loaded is not None
    assert loaded.label == "Demo Voice"
    assert loaded.voice_token == f"{CLONE_VOICE_PREFIX}demo"
    assert loaded.resolved_sample(repo_root=tmp_path) == sample.resolve()


def test_parse_voice_token():
    assert parse_voice_token("clone:bayon") == ("clone", "bayon")
    assert parse_voice_token("en-US-JennyNeural") == ("", None)


def test_discover_multiple_roots(tmp_path):
    a = tmp_path / "voices" / "a"
    a.mkdir(parents=True)
    (a / "profile.json").write_text(json.dumps({
        "id": "a",
        "label": "A",
        "sample_path": "sample.wav",
    }), encoding="utf-8")
    (a / "sample.wav").write_bytes(b"x")
    found = discover_voice_profiles(repo_root=tmp_path)
    assert "a" in found


def test_synthesize_cloned_no_server(tmp_path, monkeypatch):
    sample = tmp_path / "sample.wav"
    sample.write_bytes(b"RIFF" + b"\0" * 200)
    out = tmp_path / "out.mp3"
    monkeypatch.setenv("CLONE_TTS_PRIORITY", "chatterbox,xtts,elevenlabs")
    ok, used = synthesize_cloned("Hello world.", out, sample_path=sample, engine="clone")
    assert ok is False
    assert used == ""
    assert clone_engine_priority()[0] == "chatterbox"
