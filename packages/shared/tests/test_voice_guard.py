"""Memory and YouTube-limit guards for the voice training queue."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from aoep_shared.cosyvoice_ingest.transcribe import transcribe_wav
from aoep_shared.dictionary_audio import write_wav_mono
from aoep_shared.cosyvoice_ingest.guard import (
    available_mb,
    clamp_workers,
    consume_oom_backoff,
    is_memory_error,
    is_oom_exit,
    limit_backoff_seconds,
    reset_limit_state,
    row_hit_rate_limit,
    should_wait_for_memory,
)
from aoep_shared.cosyvoice_ingest.queue import execute_queue, request_stop


def test_transcribe_refuses_when_memory_is_below_the_floor(tmp_path: Path, monkeypatch):
    pytest.importorskip("faster_whisper")  # the memory check runs after the optional ASR import
    wav = tmp_path / "clip.wav"
    write_wav_mono(wav, struct.pack("<hh", 0, 0), 24000)
    monkeypatch.setenv("AOEP_ASR_MIN_FREE_MB", "99999999")
    result = transcribe_wav(wav, language="km")
    assert result.ok is False
    assert result.reason == "low_memory"


def test_memory_and_limit_classifiers(tmp_path: Path, monkeypatch):
    assert available_mb("MemAvailable:  8388608 kB\nMemFree: 1 kB\n") == 8192
    assert available_mb("MemFree: 1 kB\n") is None
    assert is_oom_exit(-9) and is_oom_exit(137)
    assert not is_oom_exit(1)
    assert is_memory_error("torch.AcceleratorError: CUDA error: out of memory")
    assert is_memory_error("exitcode  : -9 (pid: 1) (SIGKILL)")
    assert not is_memory_error("private video")
    assert limit_backoff_seconds(1, base=30) == 30
    assert limit_backoff_seconds(3, base=30, cap=90) == 90
    assert limit_backoff_seconds(2, base=0) == 0
    assert clamp_workers(3, available=10_000, per_worker_mb=6144, reserve_mb=8192) == 1
    assert clamp_workers(3, available=40_000, per_worker_mb=6144, reserve_mb=8192) == 3
    assert should_wait_for_memory(available=1000, min_mb=8192, active_jobs=0) is False
    assert should_wait_for_memory(available=1000, min_mb=8192, active_jobs=2) is True
    assert should_wait_for_memory(available=1000, min_mb=8192, active_jobs=0, pressure=True) is False
    assert should_wait_for_memory(available=99_000, min_mb=8192, active_jobs=1, pressure=True) is True
    assert row_hit_rate_limit({"error_counts": {"rate_limit": 3, "other": 1}})
    assert not row_hit_rate_limit({"error_counts": {"other": 8, "bot_check": 1}})

    monkeypatch.setenv("AOEP_OOM_BACKOFF_SEC", "12")
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "train-1.log").write_text("healthy epoch\n", encoding="utf-8")
    (log_dir / "last_failure.txt").write_text("CUDA error: out of memory\n", encoding="utf-8")
    assert consume_oom_backoff(log_dir) == 12
    assert not (log_dir / "last_failure.txt").exists()
    (log_dir / "train-2.log").write_text("failed (exitcode: -9) (SIGKILL)\n", encoding="utf-8")
    assert consume_oom_backoff(log_dir) == 12


def test_youtube_limit_streak_pauses_the_next_url(tmp_path, monkeypatch):
    import subprocess

    from aoep_shared.cosyvoice_ingest.download import download_url
    from aoep_shared.dictionary_audio import write_wav_mono

    reset_limit_state()
    monkeypatch.setenv("YT_DLP_MIN_INTERVAL", "0")
    monkeypatch.setenv("YT_DLP_BACKOFF", "0")
    monkeypatch.setenv("YT_DLP_LIMIT_BACKOFF", "0")
    monkeypatch.setenv("YT_DLP_RETRIES", "1")
    monkeypatch.setenv("YT_DLP_LIMIT_STREAK", "2")
    monkeypatch.setenv("YT_DLP_COOLDOWN_SEC", "15")
    monkeypatch.setattr("aoep_shared.cosyvoice_ingest.download.yt_dlp_available", lambda: True)
    slept: list[float] = []

    def fail(cmd, check, capture_output, timeout, text):
        raise subprocess.CalledProcessError(
            1, cmd, output="", stderr="ERROR: [youtube] abc: The page needs to be reloaded."
        )

    monkeypatch.setattr("aoep_shared.cosyvoice_ingest.download.subprocess.run", fail)
    for index in range(2):
        try:
            download_url(
                f"https://www.youtube.com/watch?v=limit{index}",
                tmp_path / f"raw{index}",
                sleep=slept.append,
            )
        except Exception:
            pass
    assert slept == []

    def succeed(cmd, check, capture_output, timeout, text):
        dest = Path(cmd[cmd.index("-o") + 1])
        stem = dest.name.split(".%(ext)s")[0]
        write_wav_mono(dest.parent / f"{stem}.wav", b"\x00\x00" * 800, 24000)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("aoep_shared.cosyvoice_ingest.download.subprocess.run", succeed)
    download_url(
        "https://www.youtube.com/watch?v=limit-ok",
        tmp_path / "raw-ok",
        sleep=slept.append,
    )
    assert any(item > 14 for item in slept)
    reset_limit_state()


def test_queue_retries_a_killed_channel_once(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AOEP_OOM_BACKOFF_SEC", "0")
    monkeypatch.setenv("AOEP_INGEST_MIN_FREE_MB", "0")
    monkeypatch.setenv("AOEP_MEMORY_WAIT_SEC", "0")
    monkeypatch.setenv("YT_DLP_LIMIT_BACKOFF", "0")
    urls = tmp_path / "urls" / "cosyvoice_km"
    urls.mkdir(parents=True)
    (urls / "lesson.txt").write_text("https://www.youtube.com/watch?v=aaaaaaaaaaa\n", encoding="utf-8")
    catalog = urls.parent / "channels.json"
    catalog.write_text(
        json.dumps({"pools": [{"pool_id": "km", "whisper": "km", "label": "Khmer"}]}),
        encoding="utf-8",
    )
    calls: list[int] = []

    def fake(job, max_urls, repo, script):
        calls.append(1)
        code = -9 if len(calls) == 1 else 0
        return {
            "pool_id": job.pool_id,
            "slug": job.slug,
            "videos": job.video_count,
            "returncode": code,
            "elapsed_s": 0,
            "error": "oom" if code else "",
        }

    code = execute_queue(
        catalog_path=catalog,
        urls_root=urls.parent,
        output_root=tmp_path / "output",
        cosyvoice_repo=tmp_path,
        ingest_script=tmp_path / "missing.py",
        pools={"km"},
        workers=2,
        max_urls=None,
        max_channels=None,
        include_news=True,
        min_videos=1,
        run_channel=fake,
        sleeper=lambda _seconds: None,
    )
    assert calls == [1, 1]
    assert code == 0
    status = json.loads(
        (tmp_path / "output" / "cosyvoice_voice_queue_status.json").read_text(encoding="utf-8")
    )
    assert status["ok"] == 1
    assert status["failed"] == 0
    assert any("oom-retry" in line for line in status["log"])


def test_queue_pauses_after_a_rate_limited_channel(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AOEP_INGEST_MIN_FREE_MB", "0")
    monkeypatch.setenv("AOEP_MEMORY_WAIT_SEC", "0")
    monkeypatch.setenv("YT_DLP_LIMIT_BACKOFF", "9")
    urls = tmp_path / "urls" / "cosyvoice_km"
    urls.mkdir(parents=True)
    (urls / "one.txt").write_text("https://www.youtube.com/watch?v=aaaaaaaaaaa\n", encoding="utf-8")
    (urls / "two.txt").write_text("https://www.youtube.com/watch?v=bbbbbbbbbbb\n", encoding="utf-8")
    catalog = urls.parent / "channels.json"
    catalog.write_text(
        json.dumps({"pools": [{"pool_id": "km", "whisper": "km", "label": "Khmer"}]}),
        encoding="utf-8",
    )
    slept: list[float] = []
    seen: list[str] = []

    def fake(job, max_urls, repo, script):
        seen.append(job.slug)
        if len(seen) == 1:
            return {
                "pool_id": job.pool_id,
                "slug": job.slug,
                "videos": 1,
                "returncode": 1,
                "elapsed_s": 0,
                "error": "rate_limit:2",
                "error_counts": {"rate_limit": 2},
            }
        request_stop(tmp_path / "output")
        return {
            "pool_id": job.pool_id,
            "slug": job.slug,
            "videos": 1,
            "returncode": 0,
            "elapsed_s": 0,
        }

    execute_queue(
        catalog_path=catalog,
        urls_root=urls.parent,
        output_root=tmp_path / "output",
        cosyvoice_repo=tmp_path,
        ingest_script=tmp_path / "missing.py",
        pools={"km"},
        workers=1,
        max_urls=None,
        max_channels=None,
        include_news=True,
        min_videos=1,
        run_channel=fake,
        sleeper=slept.append,
    )
    assert seen == ["one", "two"]
    assert any(item >= 8 for item in slept)
