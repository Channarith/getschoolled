import json
from pathlib import Path

import pytest

from tts_bakeoff.voice_clone import profile, registry


def _speaker(tmp_path, samples, name="Wei Miao", evidence=None, speaker="wei-miao"):
    """Register a consented speaker with fake samples: [(file, lang, seconds, snr, cleaned, snr_clean)]."""
    form = tmp_path / "form.txt"
    form.write_text("signed " * 40, encoding="utf-8")
    registry.record_consent(speaker, name, "employee", form, base=tmp_path, evidence=evidence)
    d = registry.speaker_dir(speaker, tmp_path)
    (d / "samples").mkdir(exist_ok=True)
    for fname, lang, secs, snr, cleaned, snr_clean in samples:
        wav = d / "samples" / fname
        wav.write_bytes(b"RIFF" + fname.encode() * 30)
        extra = {"seconds": secs, "snr_db": snr, "cleaned": cleaned}
        if snr_clean is not None:
            extra["snr_db_clean"] = snr_clean
        registry.add_sample(speaker, wav, f"transcript of {fname}", lang, tmp_path, extra=extra)
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


def test_two_wives_two_ids_two_languages_and_consent_records_stay_apart(tmp_path):
    _speaker(tmp_path, [("en.wav", "en", 60, 30, False, None)], name="Wei Miao", speaker="wei-miao", evidence={"consent_language": "en"})
    _speaker(tmp_path, [("yue.wav", "yue", 60, 30, False, None)], name="Wei", speaker="wei", evidence={"consent_language": "yue"})
    assert profile.speaker_languages("wei-miao", tmp_path) == ["en"] and profile.speaker_languages("wei", tmp_path) == ["yue"]
    assert profile.display_label("wei-miao", "Wei Miao", tmp_path) == "Wei Miao (English)"
    assert profile.display_label("wei", "Wei", tmp_path) == "Wei (Cantonese)"
    assert registry.load_consent("wei", tmp_path)["name"] == "Wei" and registry.load_consent("wei-miao", tmp_path)["name"] == "Wei Miao"
    assert profile.choose_reference("wei", "en", tmp_path).rel == "samples/yue.wav"    # a speaker never borrows the other person's sample
    assert registry.speaker_dir("wei", tmp_path) != registry.speaker_dir("wei-miao", tmp_path)
    registry.revoke("wei", tmp_path)
    assert profile.speaker_languages("wei-miao", tmp_path) == ["en"]                      # revoking one leaves the other untouched
    with pytest.raises(registry.ConsentError):
        profile.speaker_languages("wei", tmp_path)


def test_speaker_languages_orders_by_audio_then_consent_text_language(tmp_path):
    _speaker(tmp_path, [("a.wav", "en", 60, 30, False, None), ("b.wav", "yue", 90, 30, False, None), ("c.wav", "es", 60, 30, False, None)],
             evidence={"consent_language": "es"})
    assert profile.speaker_languages("wei-miao", tmp_path) == ["yue", "es", "en"]          # most audio first; the tie goes to the consent language
    assert profile.primary_language("wei-miao", tmp_path) == "yue"


def test_expand_langs_default_all_and_explicit(tmp_path):
    _speaker(tmp_path, [("yue.wav", "yue", 60, 30, False, None)], speaker="wei", name="Wei")
    assert profile.expand_langs("", "wei", tmp_path) == ["yue"]
    assert profile.expand_langs("all", "wei", tmp_path) == list(profile.ALL_LANGS) and "yue" in profile.ALL_LANGS
    assert profile.expand_langs("en,es", "wei", tmp_path) == ["en", "es"]


@pytest.fixture
def mock_speaks_yue(monkeypatch):
    from tts_bakeoff.adapters.mock import MockAdapter

    monkeypatch.setattr(MockAdapter, "languages", {*MockAdapter.languages, "yue"})


def test_bakeoff_defaults_to_each_speakers_own_language_and_flags_cross_lingual(tmp_path, mock_speaks_yue):
    from tts_bakeoff.voice_clone import bakeoff

    _speaker(tmp_path, [("en.wav", "en", 60, 30, False, None)], name="Wei Miao", speaker="wei-miao")
    _speaker(tmp_path, [("yue.wav", "yue", 60, 30, False, None)], name="Wei", speaker="wei")
    out = tmp_path / "out"
    counts = bakeoff.synthesize_all(out, ["wei", "wei-miao"], ["mock"], None, 1, base=tmp_path, gpu=False)
    assert counts["failed"] == 0 and counts["ok"] == 2
    assert sorted(p.name for p in (out / "mock~wei").iterdir() if p.is_dir()) == ["yue"]          # the Cantonese voice does not speak English
    assert sorted(p.name for p in (out / "mock~wei-miao").iterdir() if p.is_dir()) == ["en"]
    meta = json.loads((out / "mock~wei" / "meta.json").read_text(encoding="utf-8"))
    assert meta["label"].startswith("Wei (Cantonese)") and meta["primary_lang"] == "yue" and meta["langs"] == ["yue"]
    rows = [json.loads(l) for l in (out / "mock~wei" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows and all("cross_lingual" not in r for r in rows)
    asked = tmp_path / "asked"
    bakeoff.synthesize_all(asked, ["wei"], ["mock"], ["yue", "en"], 1, base=tmp_path, gpu=False)   # explicit --langs: English is allowed but labelled
    flags = {json.loads(l)["lang"]: json.loads(l).get("cross_lingual", False) for l in (asked / "mock~wei" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()}
    assert flags == {"yue": False, "en": True}


def test_langs_argument_parsing():
    from tts_bakeoff.voice_clone import bakeoff

    assert bakeoff._langs_arg("") is None and bakeoff._langs_arg("all") == list(profile.ALL_LANGS) and bakeoff._langs_arg("en,yue") == ["en", "yue"]


def test_lab_does_not_list_folders_set_aside_with_an_underscore(tmp_path):
    from tts_bakeoff.lab import list_run

    for d in ("voxcpm2~wei/yue", "_cross-lingual-wei/en", ".raw"):
        (tmp_path / d).mkdir(parents=True)
        (tmp_path / d / "S01.wav").write_bytes(b"RIFF" + b"0" * 100)
    files = [f["path"] for f in list_run(tmp_path)["files"]]
    assert files == ["voxcpm2~wei/yue/S01.wav"]
