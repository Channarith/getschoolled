from __future__ import annotations

import importlib.util
import pathlib

from aoep_shared import prerender_audio as pa


def test_key_ignores_whitespace_and_separates_languages():
    assert pa.audio_key("Hello   world", "en") == pa.audio_key(" Hello world ", "en")
    assert pa.audio_key("Hello world", "en") != pa.audio_key("Hello world", "es")


def test_lookup_finds_stored_audio_and_misses_cleanly(tmp_path):
    line = pa.narration_line("Intro", "Hello there")
    assert pa.lookup(line, "en", tmp_path) is None
    (tmp_path / f"{pa.audio_key(line, 'en')}.wav").write_bytes(b"RIFF" + b"x" * 400)
    audio, ctype = pa.lookup(line, "en", tmp_path)
    assert ctype == "audio/wav" and audio.startswith(b"RIFF")
    assert pa.lookup(line, "es", tmp_path) is None


def test_no_dir_means_disabled(monkeypatch):
    monkeypatch.delenv(pa.ENV_DIR, raising=False)
    assert pa.lookup("anything", "en") is None


def test_script_dry_run_render_and_resume(tmp_path, monkeypatch, capsys):
    path = pathlib.Path(__file__).resolve().parents[3] / "scripts" / "prerender_course_audio.py"
    spec = importlib.util.spec_from_file_location("prerender_script", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    course = ["--course", "audio-intro-to-machine-learning"]
    assert mod.main(["--dry-run", "--out", str(tmp_path), *course]) == 0
    assert "to render" in capsys.readouterr().out

    monkeypatch.setenv("COSYVOICE_URL", "http://cosy.test")
    monkeypatch.setattr(mod.cosyvoice_tts, "synthesize", lambda *a, **k: (b"RIFF" + b"x" * 400, "audio/wav"))
    args = ["--out", str(tmp_path), *course, "--limit", "2"]
    assert mod.main(args) == 0
    assert len(list(tmp_path.glob("*.wav"))) == 2
    assert len((tmp_path / "manifest.jsonl").read_text().splitlines()) == 2
    assert mod.main(args) == 0
    assert len(list(tmp_path.glob("*.wav"))) == 4
