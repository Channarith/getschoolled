"""gpu_burst: short GPU-lock bursts that never stall a long-running worker."""
from __future__ import annotations

import fcntl
import os
import time

import pytest

from aoep_shared import gpu_lock


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("GS_GPU_LOCK", str(tmp_path / "gpu.lock"))
    monkeypatch.delenv("GS_GPU_LOCK_HELD", raising=False)
    monkeypatch.delenv("AOEP_GPU_BURST_LOCK", raising=False)
    monkeypatch.setenv("AOEP_GPU_BURST_WAIT_S", "0.4")
    monkeypatch.setenv("AOEP_GPU_BURST_BACKOFF_S", "30")
    gpu_lock._reset_for_tests()


def hold_lock(path):
    fd = os.open(path, os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def test_free_lock_is_taken_and_released(tmp_path):
    with gpu_lock.gpu_burst("t") as held:
        assert held is True
        other = os.open(str(tmp_path / "gpu.lock"), os.O_RDWR)
        with pytest.raises(OSError):
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)      # really held
        os.close(other)
    fd = hold_lock(str(tmp_path / "gpu.lock"))                      # released: another process can take it now
    os.close(fd)


def test_busy_lock_waits_briefly_then_proceeds_without_it(tmp_path):
    fd = hold_lock(str(tmp_path / "gpu.lock"))
    try:
        t0 = time.monotonic()
        with gpu_lock.gpu_burst("t") as held:
            assert held is False
        assert 0.3 <= time.monotonic() - t0 < 3
    finally:
        os.close(fd)


def test_after_a_busy_wait_the_next_bursts_do_not_wait_again(tmp_path):
    fd = hold_lock(str(tmp_path / "gpu.lock"))
    try:
        with gpu_lock.gpu_burst("t"):
            pass
        t0 = time.monotonic()
        for _ in range(5):
            with gpu_lock.gpu_burst("t") as held:
                assert held is False
        assert time.monotonic() - t0 < 0.5                           # backoff: no 0.4 s wait per segment
    finally:
        os.close(fd)


def test_backoff_clears_once_the_lock_is_free(tmp_path):
    fd = hold_lock(str(tmp_path / "gpu.lock"))
    with gpu_lock.gpu_burst("t"):
        pass
    os.close(fd)
    gpu_lock._reset_for_tests()
    with gpu_lock.gpu_burst("t") as held:
        assert held is True


def test_caller_that_already_holds_the_lock_is_a_noop(monkeypatch, tmp_path):
    monkeypatch.setenv("GS_GPU_LOCK_HELD", "1")
    fd = hold_lock(str(tmp_path / "gpu.lock"))                       # even a busy lock does not matter
    try:
        t0 = time.monotonic()
        with gpu_lock.gpu_burst("t") as held:
            assert held is True
        assert time.monotonic() - t0 < 0.2
    finally:
        os.close(fd)


def test_can_be_switched_off(monkeypatch, tmp_path):
    monkeypatch.setenv("AOEP_GPU_BURST_LOCK", "0")
    fd = hold_lock(str(tmp_path / "gpu.lock"))
    try:
        with gpu_lock.gpu_burst("t") as held:
            assert held is True
    finally:
        os.close(fd)


def test_transcribe_wav_goes_through_the_burst(monkeypatch, tmp_path):
    from aoep_shared.cosyvoice_ingest import transcribe

    seen = {"n": 0}

    import contextlib

    @contextlib.contextmanager
    def fake_burst(name="gpu"):
        seen["n"] += 1
        yield True

    monkeypatch.setattr(transcribe, "gpu_burst", fake_burst)
    res = transcribe.transcribe_wav(tmp_path / "missing.wav")
    assert seen["n"] == 1 and res.reason == "missing_wav"
