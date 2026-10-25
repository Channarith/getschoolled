"""The 8 GB profile benchmark: chrF, sentence loading, memory sampling, scoring and the recommendation, all with fakes."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
spec = importlib.util.spec_from_file_location("nllb_profile_bench", REPO / "scripts" / "nllb_profile_bench.py")
bench = importlib.util.module_from_spec(spec)
sys.modules["nllb_profile_bench"] = bench
spec.loader.exec_module(bench)


def test_chrf_identity_difference_and_edges():
    assert bench.chrf("សួស្តី", "សួស្តី") == 100.0
    assert bench.chrf("hello world", "hello  world") == 100.0  # whitespace ignored
    assert 0 < bench.chrf("hello wrld", "hello world") < 100
    assert bench.chrf("abc", "xyz") == 0.0
    assert bench.chrf("", "") == 100.0 and bench.chrf("a", "") == 0.0
    assert bench.chrf("hello world", "hello word") > bench.chrf("hello world", "goodbye")


def test_load_sentences_prefers_manifest_english_lines_and_pads(tmp_path):
    m = tmp_path / "m.json"
    m.write_text(json.dumps({"clips": [
        {"lang": "en", "text": "Welcome to the lesson on fractions and decimals."},
        {"lang": "es", "text": "Bienvenido a la lección sobre fracciones."},
        {"lang": "en", "text": "Welcome to the lesson on fractions and decimals."},  # duplicate
        {"lang": "en", "text": "short"},  # too short
    ]}))
    got = bench.load_sentences(5, m)
    assert got[0] == "Welcome to the lesson on fractions and decimals." and len(got) == 5
    assert bench.load_sentences(2, tmp_path / "missing.json")  # falls back to the built-in sentences


class FakeSampler:
    def __init__(self, peak):
        self.peak = peak

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def make_translate(suffix):
    def tr(texts, *, source, target, batch_size=None):
        return [f"{t}|{target}{suffix}" for t in texts]
    return tr


def test_run_profile_times_and_collects_outputs(monkeypatch):
    monkeypatch.setenv("NLLB_PROFILE", "stale")
    res = bench.run_profile("default", ["km", "th"], ["a b", "c d"], make_translate(""), sampler_factory=lambda: FakeSampler(4.2))
    assert "NLLB_PROFILE" not in __import__("os").environ  # 'default' clears the profile
    assert res["peak_gb"] == 4.2 and res["outputs"]["km"] == ["a b|km", "c d|km"] and res["sentences_per_s"] > 0
    bench.run_profile("8gb", ["km"], ["x"], make_translate(""), sampler_factory=lambda: FakeSampler(1))
    assert __import__("os").environ["NLLB_PROFILE"] == "8gb"
    monkeypatch.delenv("NLLB_PROFILE")


def test_score_against_reference_and_recommendation_respects_the_memory_budget():
    ref = {"km": ["hello world", "good morning"]}
    good = {"profile": "8gb", "langs": ["km"], "outputs": {"km": ["hello world", "good morning"]}, "peak_gb": 4.5, "sentences_per_s": 5.0}
    better_but_big = {"profile": "3b-fp16", "langs": ["km"], "outputs": {"km": ["hello world", "good morning"]}, "peak_gb": 7.8, "sentences_per_s": 9.0}
    worse = {"profile": "8gb-ct2", "langs": ["km"], "outputs": {"km": ["hullo wurld", "good mourning"]}, "peak_gb": 5.5, "sentences_per_s": 7.0}
    bench.score([good, better_but_big, worse], ref)
    assert good["chrf_mean"] == 100.0 and worse["chrf_mean"] < 100 and good["quality_basis"] == "reference"
    rec = bench.recommend([good, better_but_big, worse], 6.5)
    assert rec["profile"] == "8gb" and rec["within_budget"]  # the 3B profile is equally good but does not fit
    too_big = bench.recommend([better_but_big], 6.5)
    assert not too_big["within_budget"] and too_big["note"]


def test_score_without_reference_is_labelled_weak_agreement():
    a = {"profile": "a", "langs": ["km"], "outputs": {"km": ["same"]}, "peak_gb": 1, "sentences_per_s": 1}
    b = {"profile": "b", "langs": ["km"], "outputs": {"km": ["same"]}, "peak_gb": 1, "sentences_per_s": 1}
    bench.score([a, b], None)
    assert a["chrf_mean"] == 100.0 and "weak" in a["quality_basis"]


def test_peak_sampler_keeps_the_maximum():
    values = iter([1.0, 6.2, 3.0] + [3.0] * 50)
    with bench.PeakSampler(interval=0.001, query=lambda: next(values)) as s:
        import time
        time.sleep(0.05)
    assert s.peak == 6.2
