"""Offline tests for CosyVoice ingest (segmentation + recipe export)."""

from __future__ import annotations

import math
import struct
from pathlib import Path

import pytest

from aoep_shared.cosyvoice_ingest.export import (
    CosyVoiceUtterance,
    build_spk2utt,
    write_cosyvoice_recipe,
)
from aoep_shared.cosyvoice_ingest.segment import segment_pcm16, slice_pcm16
from aoep_shared.cosyvoice_ingest.urls import is_allowed_media_url, load_url_list
from aoep_shared.dictionary_audio import write_wav_mono


def _tone_pcm(seconds: float, sr: int = 24000, hz: float = 220.0, amp: float = 0.3) -> bytes:
    n = int(seconds * sr)
    samples = [
        int(amp * 32767 * math.sin(2 * math.pi * hz * (i / sr))) for i in range(n)
    ]
    return struct.pack("<" + "h" * n, *samples)


def _silence_pcm(seconds: float, sr: int = 24000) -> bytes:
    n = int(seconds * sr)
    return struct.pack("<" + "h" * n, *([0] * n))


def test_url_allowlist():
    assert is_allowed_media_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert is_allowed_media_url("https://youtu.be/dQw4w9WgXcQ")
    assert is_allowed_media_url("https://vimeo.com/123456")
    assert not is_allowed_media_url("https://example.com/video")
    assert not is_allowed_media_url("ftp://youtube.com/x")


def test_load_url_list(tmp_path):
    p = tmp_path / "urls.txt"
    p.write_text(
        "# comment\n\nhttps://youtube.com/watch?v=abc123\nhttps://vimeo.com/9\n",
        encoding="utf-8",
    )
    assert load_url_list(p) == [
        "https://youtube.com/watch?v=abc123",
        "https://vimeo.com/9",
    ]
    bad = tmp_path / "bad.txt"
    bad.write_text("https://evil.example/x\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_url_list(bad)


def test_segment_splits_on_silence():
    sr = 24000
    pcm = _tone_pcm(2.0, sr) + _silence_pcm(0.6, sr) + _tone_pcm(2.0, sr)
    segs = segment_pcm16(pcm, sr, min_utt_sec=0.5, max_utt_sec=12.0, min_silence_sec=0.35)
    assert len(segs) >= 2
    assert all(s.duration_sec >= 0.5 for s in segs)
    # Slices reconstruct without crash
    piece = slice_pcm16(pcm, segs[0].start_sample, segs[0].end_sample)
    assert len(piece) == (segs[0].end_sample - segs[0].start_sample) * 2


def test_segment_chunks_continuous_speech():
    sr = 24000
    pcm = _tone_pcm(5.0, sr)
    segs = segment_pcm16(pcm, sr, min_utt_sec=1.0, max_utt_sec=2.0)
    assert len(segs) >= 2
    assert all(s.duration_sec <= 2.01 for s in segs)


def test_segment_rejects_too_short():
    sr = 24000
    pcm = _tone_pcm(0.2, sr)
    assert segment_pcm16(pcm, sr, min_utt_sec=1.0) == []


def test_build_spk2utt_and_recipe(tmp_path):
    wav_dir = tmp_path / "wav"
    wav_dir.mkdir()
    w1 = wav_dir / "u1.wav"
    w2 = wav_dir / "u2.wav"
    write_wav_mono(w1, _tone_pcm(0.5), 24000)
    write_wav_mono(w2, _tone_pcm(0.5), 24000)

    rows = [
        CosyVoiceUtterance("u1", str(w1), "hello world", "spk_a", language="en"),
        CosyVoiceUtterance("u2", str(w2), "សួស្តី", "spk_a", language="km"),
        CosyVoiceUtterance("u3", str(w1), "", "spk_b", language="en", qc_ok=True),  # empty → skipped
    ]
    assert build_spk2utt({"u1": "spk_a", "u2": "spk_a"})["spk_a"] == ["u1", "u2"]

    recipe = write_cosyvoice_recipe(
        rows,
        tmp_path / "data",
        language="en",
        instruct="Speak clearly.",
        cosyvoice_repo=Path("/tmp/fake-cosyvoice"),
        split_name="train",
    )
    assert recipe.wav_scp.is_file()
    wav_lines = recipe.wav_scp.read_text(encoding="utf-8").strip().splitlines()
    text_lines = recipe.text.read_text(encoding="utf-8").strip().splitlines()
    assert len(wav_lines) == 2
    assert len(text_lines) == 2
    assert text_lines[0].startswith("u1 ")
    assert "hello world" in text_lines[0]
    utt2spk = recipe.utt2spk.read_text(encoding="utf-8")
    assert "u1 spk_a" in utt2spk
    spk2utt = recipe.spk2utt.read_text(encoding="utf-8")
    assert spk2utt.startswith("spk_a ")
    assert "u1" in spk2utt and "u2" in spk2utt
    assert "u1 en" in recipe.utt2lang.read_text(encoding="utf-8")
    assert "u2 km" in recipe.utt2lang.read_text(encoding="utf-8")
    assert (recipe.data_dir / "instruct").is_file()
    handoff = recipe.train_handoff.read_text(encoding="utf-8")
    assert "cosyvoice/bin/train.py" in handoff
    assert "make_parquet_list.py" in handoff
    meta = (recipe.data_dir / "meta.json").read_text(encoding="utf-8")
    assert "utterance_count" in meta


def test_pipeline_local_media_without_asr(tmp_path, monkeypatch):
    """End-to-end smoke with local WAV; ASR may be absent → empty export ok=False."""
    from aoep_shared.cosyvoice_ingest import pipeline as pl
    from aoep_shared.cosyvoice_ingest.pipeline import IngestConfig, run_ingest
    from aoep_shared.cosyvoice_ingest.transcribe import TranscriptResult

    monkeypatch.setattr(pl, "asr_available", lambda: False)
    monkeypatch.setattr(
        pl,
        "transcribe_wav",
        lambda *a, **k: TranscriptResult("", "en", "none", False, "forced_offline"),
    )

    media = tmp_path / "media"
    media.mkdir()
    # Speech + silence + speech so segmenter yields ≥1 utt
    pcm = _tone_pcm(2.0) + _silence_pcm(0.5) + _tone_pcm(2.0)
    write_wav_mono(media / "clip.wav", pcm, 24000)

    out = tmp_path / "out"
    report = run_ingest(
        IngestConfig(
            media_dir=media,
            output_dir=out,
            language="en",
            skip_download=True,
            allow_empty_transcripts=False,
        )
    )
    assert (out / "01_raw").is_dir()
    assert (out / "02_clean").is_dir()
    assert (out / "03_segments").is_dir()
    assert report.utterances == 0
    assert report.ok is False
    assert any("asr" in e or "export_empty" in e for e in report.errors)


def test_pipeline_with_fake_asr(tmp_path, monkeypatch):
    from aoep_shared.cosyvoice_ingest import pipeline as pl
    from aoep_shared.cosyvoice_ingest.pipeline import IngestConfig, run_ingest
    from aoep_shared.cosyvoice_ingest.transcribe import TranscriptResult

    monkeypatch.setattr(pl, "asr_available", lambda: True)

    def fake_asr(path, *, language="en", **kwargs):
        return TranscriptResult("fake transcript words", language, "fake", True, "ok")

    monkeypatch.setattr(pl, "transcribe_wav", fake_asr)

    media = tmp_path / "media"
    media.mkdir()
    write_wav_mono(media / "talk.wav", _tone_pcm(3.0) + _silence_pcm(0.5) + _tone_pcm(2.5), 24000)
    out = tmp_path / "out"
    report = run_ingest(
        IngestConfig(
            media_dir=media,
            output_dir=out,
            language="en",
            speaker="teacher1",
            skip_download=True,
            cosyvoice_repo=tmp_path / "CosyVoice",
        )
    )
    assert report.ok
    assert report.utterances >= 1
    recipe = Path(report.recipe_dir)
    text = (recipe / "text").read_text(encoding="utf-8")
    assert "fake transcript words" in text
    assert "teacher1" in (recipe / "utt2spk").read_text(encoding="utf-8")


def test_download_optional_skip_without_network():
    """Network yt-dlp tests are optional; skip by default."""
    pytest.skip("network download tests are optional; use operator URLs manually")
