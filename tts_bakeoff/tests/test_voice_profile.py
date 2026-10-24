import json
from pathlib import Path

import pytest

from tts_bakeoff.voice_clone import profile, registry


def _speaker(tmp_path, samples, name="Wei Miao", evidence=None):
    """Register a consented speaker with fake samples: [(file, lang, seconds, snr, cleaned, snr_clean)]."""
    form = tmp_path / "form.txt"
    form.write_text("signed " * 40, encoding="utf-8")
    registry.record_consent("wei-miao", name, "employee", form, base=tmp_path, evidence=evidence)
    d = registry.speaker_dir("wei-miao", tmp_path)
    (d / "samples").mkdir(exist_ok=True)
    for fname, lang, secs, snr, cleaned, snr_clean in samples:
        wav = d / "samples" / fname
        wav.write_bytes(b"RIFF" + fname.encode() * 30)
        extra = {"seconds": secs, "snr_db": snr, "cleaned": cleaned}
        if snr_clean is not None:
            extra["snr_db_clean"] = snr_clean
        registry.add_sample("wei-miao", wav, f"transcript of {fname}", lang, tmp_path, extra=extra)
    return d


def test_same_language_sample_wins_even_if_another_is_cleaner(tmp_path):
    _speaker(tmp_path, [("en.wav", "en", 60, 40, False, None), ("yue.wav", "yue", 60, 24, False, None)])
    ref = profile.choose_reference("wei-miao", "yue", tmp_path)
    assert ref.rel == "samples/yue.wav" and ref.tier == "same-language" and ref.transcript == "transcript of yue.wav"
    assert profile.choose_reference("wei-miao", "en", tmp_path).rel == "samples/en.wav"
    assert profile.choose_reference("wei-miao", "en-GB", tmp_path).tier == "same-language"


def test_close_language_beats_cross_lingual(tmp_path):
    _speaker(tmp_path, [("en.wav", "en", 60, 40, False, None), ("zh.wav", "zh", 60, 22, False, None)])
    ref = profile.choose_reference("wei-miao", "yue", tmp_path)
    assert (ref.rel, ref.tier) == ("samples/zh.wav", "close-language")
    assert profile.choose_reference("wei-miao", "zh-HK", tmp_path).tier == "close-language"   # zh-HK is Cantonese
    assert profile.choose_reference("wei-miao", "zh-CN", tmp_path).tier == "same-language"
    assert profile.norm_lang("zh-HK") == "yue" and profile.norm_lang("en_US") == "en" and profile.norm_lang("zh-CN") == "zh"


def test_cross_lingual_takes_the_cleanest_then_longest(tmp_path):
    _speaker(tmp_path, [("a.wav", "en", 60, 25, False, None), ("b.wav", "es", 60, 33, False, None), ("c.wav", "es", 90, 33, False, None)])
    ref = profile.choose_reference("wei-miao", "km", tmp_path)
    assert ref.tier == "cross-lingual" and ref.rel == "samples/c.wav"


def test_cleaned_copy_is_judged_by_its_cleaned_snr(tmp_path):
    _speaker(tmp_path, [("raw.wav", "yue", 60, 30, False, None), ("clean.wav", "yue", 60, 22, True, 35)])
    ref = profile.choose_reference("wei-miao", "yue", tmp_path)
    assert ref.rel == "samples/clean.wav" and ref.cleaned and ref.snr_db == 35


def test_consent_is_checked_on_every_pick(tmp_path):
    d = _speaker(tmp_path, [("yue.wav", "yue", 60, 30, False, None)])
    (d / "samples" / "yue.wav").write_bytes(b"swapped")
    with pytest.raises(registry.ConsentError):
        profile.choose_reference("wei-miao", "yue", tmp_path)
    (d / "samples" / "yue.wav").write_bytes(b"RIFF" + b"yue.wav" * 30)
    assert profile.choose_reference("wei-miao", "yue", tmp_path)
    registry.revoke("wei-miao", tmp_path)
    with pytest.raises(registry.ConsentError):
        profile.choose_reference("wei-miao", "yue", tmp_path)


def test_samples_carry_consent_language_and_quality_tags(tmp_path):
    ev = {"consent_language": "en", "consent_text_sha256": "ab" * 32}
    d = _speaker(tmp_path, [("yue.wav", "yue", 61.5, 30.2, True, 36.0)], evidence=ev)
    info = registry.load_consent("wei-miao", tmp_path)["samples"]["samples/yue.wav"]
    assert info["consent_language"] == "en" and info["consent_text_sha256"] == "ab" * 32 and info["enrolled_at"]
    assert info["cleaned"] is True and info["snr_db_clean"] == 36.0 and info["lang"] == "yue"
    assert d.is_dir()


class _Inner:
    name = "fake"
    languages = {"en", "yue"}

    def __init__(self):
        self.options = {"style": "cute"}
        self.calls = []

    def synthesize(self, text, lang, out):
        self.calls.append((text, lang, dict(self.options)))
        return {"ok": True}


def test_profile_adapter_switches_reference_per_sentence_and_keeps_options(tmp_path):
    _speaker(tmp_path, [("en.wav", "en", 60, 30, False, None), ("yue.wav", "yue", 60, 30, False, None)])
    inner = _Inner()
    ad = profile.ProfileAdapter(inner, "wei-miao", tmp_path)
    assert ad.languages == {"en", "yue"} and ad.name == "fake" and ad.options is inner.options
    ad.synthesize("hello", "en", "x.wav")
    ad.synthesize("你好", "yue", "y.wav")
    (_, _, o1), (_, _, o2) = inner.calls
    assert o1["reference_wav"].endswith("en.wav") and o1["prompt_lang"] == "en" and o1["style"] == "cute"
    assert o2["reference_wav"].endswith("yue.wav") and o2["prompt_text"] == "transcript of yue.wav" and o2["prompt_lang"] == "yue"
    assert ad.last_reference.tier == "same-language"


def test_readiness_counts_clean_minutes_per_language(tmp_path):
    _speaker(tmp_path, [("a.wav", "yue", 60, 30, True, 35), ("b.wav", "yue", 60, 28, False, None), ("c.wav", "en", 60, 30, False, None)],
             evidence={"consent_language": "yue"})
    rep = profile.readiness("wei-miao", "voxcpm2", tmp_path)
    yue, en = rep["languages"]["yue"], rep["languages"]["en"]
    assert yue["clean_minutes"] == 2.0 and yue["samples"] == 2 and yue["cleaned_samples"] == 1 and yue["consent_languages"] == ["yue"]
    assert yue["snr_db_min"] == 28 and "3.0 more minutes" in yue["fine_tune"] and en["clean_minutes"] == 1.0
    cosy = profile.readiness("wei-miao", "cosyvoice2", tmp_path)
    assert cosy["languages"]["yue"]["fine_tune"].startswith("unknown")
    assert "5-10 min" in profile.format_report(rep) and "trains nothing" in profile.format_report(rep)


def test_readiness_states_ready_once_the_documented_minutes_are_there(tmp_path):
    _speaker(tmp_path, [(f"s{i}.wav", "yue", 90, 30, False, None) for i in range(7)])   # 10.5 minutes
    assert profile.readiness("wei-miao", "voxcpm2", tmp_path)["languages"]["yue"]["fine_tune"] == "ready"


def test_prep_is_a_manifest_stub_that_refuses_without_enough_audio(tmp_path):
    _speaker(tmp_path, [("yue.wav", "yue", 60, 30, False, None)])
    out = tmp_path / "ft"
    res = profile.prep_finetune("wei-miao", "voxcpm2", out, tmp_path)
    assert res["written"] is False and not out.exists() and any("outside 3-30 s" in f for f in res["flags"])
    forced = profile.prep_finetune("wei-miao", "voxcpm2", out, tmp_path, force=True)
    rows = [json.loads(l) for l in (out / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    assert forced["written"] and rows[0]["text"] == "transcript of yue.wav" and rows[0]["duration"] == 60 and set(rows[0]) >= {"audio", "text", "duration", "dataset_id"}
    registry.revoke("wei-miao", tmp_path)
    with pytest.raises(registry.ConsentError):
        profile.prep_finetune("wei-miao", "voxcpm2", out, tmp_path, force=True)


def test_build_adapter_returns_the_profile_wrapper(tmp_path, monkeypatch):
    from tts_bakeoff.voice_clone import synth

    _speaker(tmp_path, [("yue.wav", "yue", 60, 30, False, None)])
    ad = synth.build_adapter("mock", "wei-miao", tmp_path, gpu=False)
    assert isinstance(ad, profile.ProfileAdapter)
    assert ad.options["reference_wav"].endswith("yue.wav")
