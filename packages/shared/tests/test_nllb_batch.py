"""NLLB batching and policy plumbing with a fake tokenizer/model (no torch, no download)."""
from __future__ import annotations

import pytest

from aoep_shared import nllb
from aoep_shared.devices import DevicePolicyError


class FakeTensor:
    def __init__(self, rows):
        self.rows = rows

    def to(self, device):
        return self


class FakeParam:
    class device:
        type = "cpu"


class FakeModel:
    def __init__(self):
        self.calls = []

    def parameters(self):
        yield FakeParam()

    def generate(self, input_ids=None, attention_mask=None, forced_bos_token_id=None, max_length=None, num_beams=None, **_):
        self.calls.append(([r[0] for r in input_ids.rows], num_beams))
        return FakeTensor([[("T:" + str(r[0]))] for r in input_ids.rows])


class FakeTokenizer:
    src_lang = None

    def convert_tokens_to_ids(self, tgt):
        return 7

    def __call__(self, batch, return_tensors=None, truncation=None, max_length=None, padding=None):
        return {"input_ids": FakeTensor([[t] for t in batch]), "attention_mask": FakeTensor([[1] for _ in batch])}

    def batch_decode(self, generated, skip_special_tokens=True):
        return [row[0] for row in generated.rows]


@pytest.fixture
def fakes(monkeypatch):
    model, tok = FakeModel(), FakeTokenizer()
    monkeypatch.setattr(nllb, "_get_model", lambda: (tok, model))
    return model, tok


def test_batches_are_longest_first_and_order_is_restored(fakes):
    model, _ = fakes
    texts = ["aa", "b", "cccc", "ddd", "e"]
    out = nllb.translate_batch(texts, source="en", target="km", batch_size=2, num_beams=3)
    assert out == ["T:aa", "T:b", "T:cccc", "T:ddd", "T:e"]
    # three generate() calls for five segments, longest first
    assert [c[0] for c in model.calls] == [["cccc", "ddd"], ["aa", "b"], ["e"]]
    assert all(c[1] == 3 for c in model.calls)


def test_empty_segments_stay_empty_and_cost_nothing(fakes):
    model, _ = fakes
    assert nllb.translate_batch(["", "x", "  "], source="en", target="km") == ["", "T:x", ""]
    assert len(model.calls) == 1


def test_same_language_is_identity_without_loading(monkeypatch):
    monkeypatch.setattr(nllb, "_get_model", lambda: (_ for _ in ()).throw(AssertionError("must not load")))
    assert nllb.translate_batch(["hello  world"], source="en", target="en") == ["hello world"]


def test_translate_text_keeps_its_api(fakes):
    assert nllb.translate_text("  hello   there ", source="en", target="km") == "T:hello there"
    assert nllb.translate_text("   ", source="en", target="km") == ""


def test_policy_error_is_not_swallowed_by_the_speech_provider(monkeypatch):
    from aoep_shared.providers.speech import LocalSpeechProvider

    def boom():
        raise DevicePolicyError("CUDA is required on this host")

    monkeypatch.setattr(nllb, "_get_model", boom)
    class Cfg:
        speech_base_url = "http://speech"

    provider = LocalSpeechProvider(Cfg())
    with pytest.raises(DevicePolicyError):
        provider.translate("hi", source="en", target="km")


def test_nllb_status_does_not_load_the_model(monkeypatch):
    monkeypatch.setenv("AOEP_HOST_ROLE", "other")
    monkeypatch.setattr(nllb, "_model", None)
    status = nllb.nllb_status()
    assert status["model_loaded"] is False and "cuda_required" in status
