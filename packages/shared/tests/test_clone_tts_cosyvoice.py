"""CosyVoice 2 in the presenter/clone TTS chain (aoep_shared.meeting.clone_tts)."""

from __future__ import annotations

import json
from pathlib import Path

from aoep_shared.meeting import clone_tts


def _wav(n: int = 4000) -> bytes:
    return b"RIFF" + b"\x00" * n


def test_cosyvoice_in_engines_and_priority(monkeypatch):
    assert "cosyvoice" in clone_tts.CLONE_ENGINES
    monkeypatch.delenv("CLONE_TTS_PRIORITY", raising=False)
    prio = clone_tts.clone_engine_priority()
    assert prio[0] == "cosyvoice"   # preferred by default


def test_engine_status_reports_cosyvoice_url(monkeypatch):
    monkeypatch.setenv("COSYVOICE_URL", "http://cosy:9880")
    assert clone_tts.engine_status()["cosyvoice_url"] == "http://cosy:9880"


def test_synthesize_cosyvoice_posts_and_writes(monkeypatch, tmp_path):
    monkeypatch.setenv("COSYVOICE_URL", "http://cosy:9880")
    monkeypatch.delenv("COSYVOICE_MODE", raising=False)
    captured = {}

    def fake_post(url, payload, *, headers=None, timeout=120):
        captured["url"] = url
        captured["payload"] = payload
        return _wav()

    monkeypatch.setattr(clone_tts, "_http_post_json", fake_post)
    out = tmp_path / "narr.mp3"
    ok = clone_tts.synthesize_cosyvoice("Welcome to class", out, language="es")
    assert ok is True
    assert captured["url"] == "http://cosy:9880/tts"
    assert captured["payload"]["text"] == "Welcome to class"
    assert captured["payload"]["language"] == "es"
    assert captured["payload"]["mode"] == "cross_lingual"   # no reference sample


def test_synthesize_cosyvoice_zero_shot_with_sample(monkeypatch, tmp_path):
    monkeypatch.setenv("COSYVOICE_URL", "http://cosy:9880")
    monkeypatch.delenv("COSYVOICE_MODE", raising=False)
    sample = tmp_path / "ref.wav"
    sample.write_bytes(b"RIFF" + b"\x01" * 2000)
    captured = {}

    def fake_post(url, payload, *, headers=None, timeout=120):
        captured["payload"] = payload
        return _wav()

    monkeypatch.setattr(clone_tts, "_http_post_json", fake_post)
    ok = clone_tts.synthesize_cosyvoice("hi", tmp_path / "o.mp3", sample_path=sample)
    assert ok is True
    assert captured["payload"]["mode"] == "zero_shot"
    assert captured["payload"]["reference_audio_b64"]


def test_synthesize_cloned_uses_cosyvoice_first(monkeypatch, tmp_path):
    monkeypatch.setenv("COSYVOICE_URL", "http://cosy:9880")
    monkeypatch.delenv("CLONE_TTS_PRIORITY", raising=False)
    monkeypatch.setattr(
        clone_tts, "synthesize_cosyvoice",
        lambda text, out, **kw: Path(out).write_bytes(_wav()) or True,
    )
    sample = tmp_path / "ref.wav"
    sample.write_bytes(b"RIFF" + b"\x01" * 2000)
    ok, used = clone_tts.synthesize_cloned(
        "teach this", tmp_path / "out.mp3", sample_path=sample, engine="clone",
    )
    assert ok is True and used == "cosyvoice"


def test_synthesize_cosyvoice_no_url_returns_false(monkeypatch, tmp_path):
    monkeypatch.delenv("COSYVOICE_URL", raising=False)
    assert clone_tts.synthesize_cosyvoice("hi", tmp_path / "o.mp3") is False
