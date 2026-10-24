"""scripts/nllb_bench.py with an injected translate function (no model needed)."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

from aoep_shared import devices

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "nllb_bench.py"


@pytest.fixture
def bench(monkeypatch):
    for name in ("AOEP_HOST_ROLE", "AOEP_REQUIRE_CUDA", "AOEP_ALLOW_CPU", "NLLB_DEVICE"):
        monkeypatch.delenv(name, raising=False)
    spec = importlib.util.spec_from_file_location("nllb_bench", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    yield mod
    for name in ("NLLB_DEVICE", "AOEP_ALLOW_CPU"):  # the script sets these directly
        os.environ.pop(name, None)


def test_fixed_sentences_are_deterministic(bench):
    assert bench.fixed_sentences(10) == bench.fixed_sentences(10)
    assert len(set(bench.fixed_sentences(20))) == 20


def test_run_reports_timings_and_calls_batched(bench):
    calls = []

    def fake(texts, source, target, batch_size, num_beams):
        calls.append(len(texts))
        return [f"x:{t}" for t in texts]

    out = bench.run("auto", 6, "en", "km", 4, 2, False, translate=fake)
    assert out["sentences"] == 6 and out["batch_size"] == 4 and out["batched_s"] >= 0
    assert calls[0] == 2 and calls[1:7] == [1] * 6 and calls[-1] == 6


def test_cpu_timing_on_a_cuda_required_host_needs_allow_cpu(bench, monkeypatch):
    monkeypatch.setenv("AOEP_HOST_ROLE", "spark")
    with pytest.raises(SystemExit):
        bench.run("cpu", 2, "en", "km", 2, 1, False, translate=lambda *a, **k: ["x"])
    out = bench.run("cpu", 2, "en", "km", 2, 1, True, translate=lambda texts, **k: ["x"] * len(texts))
    assert out["sentences"] == 2 and devices.allow_cpu() is True
