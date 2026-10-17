"""Offline tests for CosyVoice ingest (segmentation + recipe export)."""

from __future__ import annotations

import json
import math
import struct
import subprocess
from pathlib import Path

import pytest

from aoep_shared.cosyvoice_ingest.export import (
    CosyVoiceUtterance,
    build_spk2utt,
    write_cosyvoice_recipe,
)
from aoep_shared.cosyvoice_ingest.merge import (
    discover_recipe_dirs,
    merge_cosyvoice_recipes,
    merge_language_pool,
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
            merge=False,
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
    merge_into = tmp_path / "cosyvoice_en_merged"
    report = run_ingest(
        IngestConfig(
            media_dir=media,
            output_dir=out,
            language="en",
            speaker="teacher1",
            skip_download=True,
            cosyvoice_repo=tmp_path / "CosyVoice",
            merge_into=merge_into,
            merge_scan_root=tmp_path,
        )
    )
    assert report.ok
    assert report.utterances >= 1
    recipe = Path(report.recipe_dir)
    text = (recipe / "text").read_text(encoding="utf-8")
    assert "fake transcript words" in text
    assert "teacher1" in (recipe / "utt2spk").read_text(encoding="utf-8")
    assert report.merge_utterances >= 1
    assert Path(report.merge_dir).joinpath("wav.scp").is_file()


def test_merge_recipes_combines_channels_and_renames_collisions(tmp_path):
    wav_dir = tmp_path / "wav"
    wav_dir.mkdir()
    w1 = wav_dir / "a.wav"
    w2 = wav_dir / "b.wav"
    w3 = wav_dir / "c.wav"
    write_wav_mono(w1, _tone_pcm(0.4), 24000)
    write_wav_mono(w2, _tone_pcm(0.4), 24000)
    write_wav_mono(w3, _tone_pcm(0.4), 24000)

    ch1 = tmp_path / "cosyvoice_km_a" / "04_cosyvoice"
    ch2 = tmp_path / "cosyvoice_km_b" / "04_cosyvoice"
    write_cosyvoice_recipe(
        [CosyVoiceUtterance("utt1", str(w1), "hello", "spk_a", language="km")],
        ch1,
        language="km",
        split_name="train",
    )
    write_cosyvoice_recipe(
        [
            CosyVoiceUtterance("utt1", str(w2), "សួស្តី", "spk_b", language="km"),
            CosyVoiceUtterance("utt2", str(w3), "ល្អ", "spk_b", language="km"),
        ],
        ch2,
        language="km",
        split_name="train",
    )

    found = discover_recipe_dirs([tmp_path], split_name="train")
    assert len(found) == 2

    merged = merge_language_pool(
        language="km",
        merge_into=tmp_path / "cosyvoice_km_merged",
        scan_roots=[tmp_path],
        split_name="train",
        cosyvoice_repo=tmp_path / "CosyVoice",
    )
    assert merged.ok
    assert merged.utterances == 3
    assert merged.collisions_renamed >= 1
    wav_scp = Path(merged.dest_dir) / "wav.scp"
    lines = wav_scp.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    ids = {line.split()[0] for line in lines}
    assert "utt2" in ids
    assert any("__utt1" in i or i == "utt1" for i in ids)

    # Second merge is idempotent on path duplicates
    again = merge_cosyvoice_recipes(
        [ch1 / "train", ch2 / "train"],
        Path(merged.dest_dir),
        language="km",
    )
    assert again.utterances == 3


def test_download_error_categories_and_cookies(tmp_path, monkeypatch):
    from aoep_shared.cosyvoice_ingest.download import (
        DownloadError,
        build_yt_dlp_command,
        cookies_file,
        download_url,
    )
    from aoep_shared.cosyvoice_ingest.errors import (
        classify_download_error,
        sanitize_process_text,
    )

    assert classify_download_error("Sign in to confirm you're not a bot") == "bot_check"
    assert classify_download_error("ERROR: unable to download video data: HTTP Error 403: Forbidden") == "http_403"
    assert classify_download_error("Private video") == "private"
    assert classify_download_error("Video unavailable") == "unavailable"
    secret = "Cookie: SAPISID=should-not-leak\nERROR: Sign in to confirm you're not a bot"
    clean = sanitize_process_text(secret)
    assert "SAPISID" not in clean
    assert "not a bot" in clean

    monkeypatch.delenv("YT_DLP_COOKIES", raising=False)
    monkeypatch.delenv("COSYVOICE_COOKIES_FILE", raising=False)
    cmd = build_yt_dlp_command(
        "https://www.youtube.com/watch?v=aaaaaaaaaaa",
        tmp_path,
        "src_x",
        sample_rate=24000,
        cookies=None,
    )
    assert "--cookies" not in cmd
    cookie = tmp_path / "cookies.txt"
    cookie.write_text("# Netscape\n", encoding="utf-8")
    cmd = build_yt_dlp_command(
        "https://www.youtube.com/watch?v=aaaaaaaaaaa",
        tmp_path,
        "src_x",
        sample_rate=24000,
        cookies=cookie,
    )
    assert cmd[cmd.index("--cookies") + 1] == str(cookie)
    assert "Netscape" not in " ".join(cmd)

    monkeypatch.setenv("YT_DLP_COOKIES", str(tmp_path / "missing-cookies.txt"))
    assert cookies_file() is None
    monkeypatch.setenv("YT_DLP_MIN_INTERVAL", "0")
    monkeypatch.setenv("YT_DLP_BACKOFF", "0")
    monkeypatch.setenv("YT_DLP_RETRIES", "2")
    monkeypatch.delenv("YT_DLP_COOKIES", raising=False)
    calls = {"n": 0}

    def fake_run(cmd, check, capture_output, timeout, text):
        calls["n"] += 1
        if calls["n"] == 1:
            raise subprocess.CalledProcessError(
                1, cmd, output="", stderr="ERROR: Sign in to confirm you're not a bot"
            )
        dest = Path(cmd[cmd.index("-o") + 1])
        # template is dir/src.%%(ext)s — write the wav beside it
        wav = dest.parent / "src_retry.wav"
        # media id is derived from the URL, so write whatever the command's -o stem is
        stem = dest.name.split(".%(ext)s")[0]
        wav = dest.parent / f"{stem}.wav"
        write_wav_mono(wav, _tone_pcm(0.3), 24000)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("aoep_shared.cosyvoice_ingest.download.subprocess.run", fake_run)
    monkeypatch.setattr("aoep_shared.cosyvoice_ingest.download.yt_dlp_available", lambda: True)
    got = download_url(
        "https://www.youtube.com/watch?v=bbbbbbbbbbb",
        tmp_path / "raw",
        sleep=lambda _seconds: None,
    )
    assert got.audio_path.is_file()
    assert calls["n"] == 2

    def always_private(cmd, check, capture_output, timeout, text):
        raise subprocess.CalledProcessError(1, cmd, output="", stderr="ERROR: Private video")

    monkeypatch.setattr("aoep_shared.cosyvoice_ingest.download.subprocess.run", always_private)
    with pytest.raises(DownloadError) as raised:
        download_url(
            "https://www.youtube.com/watch?v=ccccccccccc",
            tmp_path / "raw2",
            sleep=lambda _seconds: None,
        )
    assert raised.value.category == "private"


def test_quiet_speech_survives_denoise_and_silence_does_not(tmp_path):
    from aoep_shared.dictionary_audio import clean_audio_file

    quiet = tmp_path / "quiet.wav"
    write_wav_mono(quiet, _tone_pcm(2.0, amp=0.02), 24000)
    cleaned = clean_audio_file(quiet, tmp_path / "quiet.crisp.wav")
    assert cleaned.ok, cleaned.reason
    assert cleaned.duration_sec > 1.0

    silent = tmp_path / "silent.wav"
    write_wav_mono(silent, b"\x00\x00" * 24000, 24000)
    rejected = clean_audio_file(silent, tmp_path / "silent.crisp.wav")
    assert rejected.ok is False
    assert rejected.reason in {"silent_source", "near_silent", "too_short"}


def test_partial_download_does_not_discard_export(tmp_path, monkeypatch):
    from aoep_shared.cosyvoice_ingest.download import DownloadError, DownloadedMedia
    from aoep_shared.cosyvoice_ingest import pipeline as pl
    from aoep_shared.cosyvoice_ingest.pipeline import IngestConfig, run_ingest
    from aoep_shared.cosyvoice_ingest.transcribe import TranscriptResult

    monkeypatch.setattr(pl, "asr_available", lambda: True)
    monkeypatch.setattr(
        pl,
        "transcribe_wav",
        lambda *a, **k: TranscriptResult("hello from the clip", "en", "fake", True, "ok"),
    )
    state = {"n": 0}

    def fake_download(url, dest_dir, sample_rate=24000):
        state["n"] += 1
        if state["n"] == 1:
            raise DownloadError(
                "yt-dlp failed",
                category="bot_check",
                stderr="Sign in to confirm you're not a bot\nCookie: SAPISID=nope\n",
            )
        dest_dir.mkdir(parents=True, exist_ok=True)
        wav = dest_dir / "kept.wav"
        write_wav_mono(wav, _tone_pcm(2.5) + _silence_pcm(0.4) + _tone_pcm(2.0), 24000)
        return DownloadedMedia(url=url, media_id="kept", audio_path=wav)

    monkeypatch.setattr(pl, "download_url", fake_download)
    urls = tmp_path / "urls.txt"
    urls.write_text(
        "https://www.youtube.com/watch?v=aaaaaaaaaaa\n"
        "https://www.youtube.com/watch?v=bbbbbbbbbbb\n",
        encoding="utf-8",
    )
    report = run_ingest(
        IngestConfig(
            urls_file=urls,
            output_dir=tmp_path / "out",
            language="en",
            speaker="teacher",
            merge=False,
        )
    )
    assert report.ok is True
    assert report.partial is True
    assert report.utterances >= 1
    assert report.error_counts.get("bot_check") == 1
    sample = report.error_records[0]
    assert sample["category"] == "bot_check"
    assert "not a bot" in sample["stderr"]
    assert "SAPISID" not in sample["stderr"]
    blob = json.dumps(report.to_dict())
    assert "SAPISID" not in blob


def test_language_census_dedupes_and_marks_the_floor(tmp_path):
    from aoep_shared.cosyvoice_ingest.census import language_census
    from aoep_shared.cosyvoice_ingest.export import CosyVoiceUtterance, write_cosyvoice_recipe

    pcm = _tone_pcm(1.2)
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    write_wav_mono(a, pcm, 24000)
    write_wav_mono(b, pcm, 24000)
    write_cosyvoice_recipe(
        [CosyVoiceUtterance("u1", str(a), "one", "spk", language="km")],
        tmp_path / "cosyvoice_km_one" / "04_cosyvoice",
        language="km",
    )
    write_cosyvoice_recipe(
        [CosyVoiceUtterance("u2", str(b), "two", "spk", language="km")],
        tmp_path / "cosyvoice_km_two" / "04_cosyvoice",
        language="km",
    )
    rows = language_census(tmp_path)
    assert len(rows) == 1
    assert rows[0]["language"] == "km"
    assert rows[0]["utterances"] == 1
    assert rows[0]["meets_floor"] is False
    assert rows[0]["minutes"] > 0


def test_download_optional_skip_without_network():
    """Network yt-dlp tests are optional; skip by default."""
    pytest.skip("network download tests are optional; use operator URLs manually")
