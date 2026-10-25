"""8 GB NLLB profiles: selection, batch autotune and the CTranslate2 path with fakes (no torch, no GPU, no download)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from aoep_shared import nllb, nllb_profile


def test_no_profile_keeps_old_behavior(monkeypatch):
    monkeypatch.delenv("NLLB_PROFILE", raising=False)
    assert nllb_profile.active() is None
    monkeypatch.setenv("NLLB_PROFILE", "default")
    assert nllb_profile.active() is None


def test_known_profiles_and_unknown_name(monkeypatch):
    monkeypatch.setenv("NLLB_PROFILE", "8GB")
    p = nllb_profile.active()
    assert p.name == "8gb" and p.backend == "hf" and "1.3B" in p.model and p.dtype == "fp16"
    monkeypatch.setenv("NLLB_PROFILE", "8gb-ct2")
    assert nllb_profile.active().backend == "ct2"
    monkeypatch.setenv("NLLB_PROFILE", "24gb")
    with pytest.raises(ValueError, match="unknown NLLB_PROFILE"):
        nllb_profile.active()


def test_every_profile_estimate_fits_the_budget():
    for p in nllb_profile.PROFILES.values():
        assert p.est_peak_gb <= p.budget_gb <= 7.0  # leaves room on an 8 GiB card for the CUDA context


def test_autotune_picks_largest_batch_under_budget():
    peaks = {4: 3.0, 8: 4.0, 16: 5.5, 32: 7.2, 64: 12.0}
    assert nllb_profile.autotune_batch_size(lambda b: peaks[b], budget_gb=6.5) == 16
    assert nllb_profile.autotune_batch_size(lambda b: 99.0, budget_gb=6.5) == 1  # even the first batch is too big


def test_autotune_treats_oom_as_over_budget_and_reraises_other_errors():
    def peak(b):
        if b >= 16:
            raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")
        return 2.0

    assert nllb_profile.autotune_batch_size(peak, budget_gb=6.5) == 8

    def broken(b):
        raise RuntimeError("device-side assert triggered")

    with pytest.raises(RuntimeError, match="assert"):
        nllb_profile.autotune_batch_size(broken)


class FakeTok:
    src_lang = None

    def encode(self, text, truncation=True, max_length=512):
        return [ord(c) for c in text[:6]]

    def convert_ids_to_tokens(self, ids):
        return [chr(i) for i in ids]

    def convert_tokens_to_ids(self, toks):
        return [ord(t) for t in toks]

    def decode(self, ids, skip_special_tokens=True):
        return "".join(chr(i) for i in ids)


class FakeCT2:
    def __init__(self):
        self.calls = []

    def translate_batch(self, sources, target_prefix=None, beam_size=None, **kw):
        self.calls.append((len(sources), beam_size, target_prefix[0]))
        return [SimpleNamespace(hypotheses=[[target_prefix[0][0]] + list(src)[::-1]]) for src in sources]


def test_ct2_backend_keeps_order_batches_longest_first_and_strips_the_language_tag(monkeypatch):
    monkeypatch.setenv("NLLB_PROFILE", "8gb-ct2")
    fake = FakeCT2()
    monkeypatch.setattr(nllb, "_get_ct2", lambda prof: (FakeTok(), fake))
    out = nllb.translate_batch(["abc", "", "hello world", "xyz"], source="en", target="km", batch_size=2)
    assert out[0] == "cba" and out[1] == "" and out[3] == "zyx"
    assert out[2] == "olleh"  # fake tokenizer keeps 6 chars ("hello "), the fake translator reverses, the result is stripped
    assert [c[0] for c in fake.calls] == [2, 1]  # three non-empty segments in batches of 2
    assert all(c[2] == ["khm_Khmr"] for c in fake.calls)


def test_ct2_backend_error_names_the_conversion_command(monkeypatch, tmp_path):
    monkeypatch.setenv("NLLB_PROFILE", "8gb-ct2")
    monkeypatch.setenv("NLLB_CT2_DIR", str(tmp_path / "missing"))
    monkeypatch.setattr(nllb, "_ct2", None)
    pytest.importorskip("ctranslate2")
    pytest.importorskip("transformers")
    monkeypatch.setattr("aoep_shared.devices.pick_device", lambda *a, **k: "cuda")
    with pytest.raises(RuntimeError, match="ct2-transformers-converter"):
        nllb._get_ct2(nllb_profile.PROFILES["8gb-ct2"])
