"""VoxCPM2 stock voices: design mode, the real-person guard, design-once-freeze, the lab grid and the demo render. No model, no GPU."""
import json
import shutil

import pytest

np = pytest.importorskip("numpy")

from tts_bakeoff import adapters
from tts_bakeoff.adapters.base import write_wav
from tts_bakeoff.demo_voice import render
from tts_bakeoff.voice_design import __main__ as cli
from tts_bakeoff.voice_design import design, grid, registry
from tts_bakeoff.voice_design.prompt import DescriptionRejected, TONES, build_description, validate_description

RATE = 24000


def tone_wav(seconds, hz=220.0):
    t = np.arange(int(seconds * RATE)) / RATE
    return (0.3 * np.sin(2 * np.pi * hz * t)).astype("float32")


class FakeModel:
    """generate() records its kwargs; audio is ~13 characters per second of the spoken text. seed_param=False models a voxcpm without seed."""

    sample_rate = RATE

    def __init__(self, seed_param=True, short_if_even=False):
        self.calls = []
        self.short_if_even = short_if_even
        if not seed_param:
            self.generate = self._generate_noseed

    def _spoken(self, text):
        return text.split(")", 1)[1] if text.startswith("(") else text

    def generate(self, text, cfg_value=2.0, inference_timesteps=10, seed=None, **kw):
        self.calls.append({"text": text, "seed": seed, **kw})
        if self.short_if_even and seed is not None and seed % 2 == 0:
            return tone_wav(1.5)
        return tone_wav(max(len(self._spoken(text)) / 13.0, 0.5))

    def _generate_noseed(self, text, cfg_value=2.0, inference_timesteps=10, **kw):
        self.calls.append({"text": text, **kw})
        return tone_wav(max(len(self._spoken(text)) / 13.0, 0.5))


def fake_adapter(model, **options):
    a = adapters.get("voxcpm2", **options)
    a._model = model
    return a


# ---------------------------------------------------------------- prompts and the real-person guard
def test_description_is_built_from_the_closed_vocabulary():
    assert build_description("f", "young", "warm", tone="professional") == (
        "A young adult woman, warm, rounded voice, professional, confident, measured pace")
    for bad in (("x", "young", "warm"), ("f", "tiny", "warm"), ("f", "young", "sparkly")):
        with pytest.raises(ValueError):
            build_description(*bad)
    assert set(TONES) == {"professional", "warm", "calm", "energetic", "cute", "anime", "tough", "heavy", "light"}


@pytest.mark.parametrize("text", [
    "sounds like Morgan Freeman", "a deep voice, like obama", "Taylor Swift singing", "in the style of a famous actor",
    "impersonate my boss", "the voice of a president", "(nested)", "x" * 300, "",
])
def test_guard_rejects_people_and_imitation(text):
    with pytest.raises(DescriptionRejected):
        validate_description(text)


@pytest.mark.parametrize("text", [
    "A young woman, gentle and sweet voice", "calm, soft-spoken, slow and steady", "clear and bright, like a bell", "British English accent, warm",
])
def test_guard_allows_plain_descriptions(text):
    assert validate_description(text)


# ---------------------------------------------------------------- the committed registry
def test_committed_registry_is_valid_and_consistent_with_voices_json():
    assert registry.validate_registry() == []
    stock = {v["id"]: v for v in registry.voices()}
    listed = [v for v in json.loads(render.VOICES.read_text(encoding="utf-8"))["voices"] if v.get("kind") == "stock"]
    assert {v["id"] for v in listed} == set(stock)
    for v in listed:
        assert v["active"] is False, "stock voices ship inactive until the owner has listened"
        assert v["gender"] == stock[v["id"]]["gender"] and v["model"] == "voxcpm2" and "speaker" not in v


def test_registry_validation_catches_a_bad_edit(tmp_path):
    doc = registry.load()
    doc["voices"][0]["description"] = "sounds like someone famous"
    doc["voices"].append({**doc["voices"][1]})
    p = tmp_path / "stock.json"
    p.write_text(json.dumps(doc))
    problems = registry.validate_registry(p)
    assert any("description" in x for x in problems) and any("duplicate" in x for x in problems)


# ---------------------------------------------------------------- adapter: design mode and seed
def test_design_mode_prefixes_the_description_and_sends_no_reference(tmp_path):
    model = FakeModel()
    a = fake_adapter(model, design="A young adult woman, warm", seed=7)
    info = a.synthesize("Hello there.", "en", tmp_path / "a.wav")
    call = model.calls[0]
    assert call["text"] == "(A young adult woman, warm)Hello there."
    assert call["seed"] == 7 and "reference_wav_path" not in call and "prompt_wav_path" not in call
    assert info["ref_mode"] == "design"


def test_seed_is_dropped_not_fatal_when_voxcpm_has_no_seed_argument(tmp_path):
    model = FakeModel(seed_param=False)
    a = fake_adapter(model, design="A calm man", seed=7)
    a.synthesize("Hi.", "en", tmp_path / "a.wav")
    assert "seed" not in model.calls[0]


def test_clone_path_is_untouched_by_design_mode(tmp_path):
    model = FakeModel()
    ref = tmp_path / "r.wav"
    write_wav(ref, tone_wav(8), RATE)
    a = fake_adapter(model, reference_wav=str(ref), ref_mode="reference")
    a.synthesize("Hello.", "en", tmp_path / "a.wav")
    assert model.calls[0]["reference_wav_path"] == str(ref) and model.calls[0]["text"] == "Hello."


# ---------------------------------------------------------------- design once, freeze, clone
def test_freeze_picks_the_usable_take_records_the_seed_and_detects_tampering(tmp_path):
    entry = registry.get("stock-f-young-warm")
    model = FakeModel(short_if_even=True)   # even seeds give a 1.5 s clip: unusable as a reference
    base_seed = registry.seed_for(entry, registry.NEUTRAL)
    assert base_seed % 2 == 0
    factory = lambda description, seed: fake_adapter(model, design=description, seed=seed)   # noqa: E731
    meta = design.freeze("stock-f-young-warm", tmp_path, takes=3, adapter_factory=factory, log=lambda *_: None)
    assert meta["chosen_take"] == 1 and meta["seed"] == base_seed + 1
    assert meta["description"] == registry.description_for(entry) and meta["ai_generated"] is True
    assert [c["text"].startswith("(A young adult woman") for c in model.calls] == [True, True, True]
    wav, side = registry.ref_paths("stock-f-young-warm", tmp_path)
    assert wav.is_file() and registry.frozen_meta("stock-f-young-warm", tmp_path)["sha256"] == registry.sha256_file(wav)
    again = design.freeze("stock-f-young-warm", tmp_path, adapter_factory=lambda *a: pytest.fail("must not re-design"), log=lambda *_: None)
    assert again["sha256"] == meta["sha256"]
    wav.write_bytes(wav.read_bytes()[:-200] + b"\0" * 200)   # tamper
    assert registry.frozen_meta("stock-f-young-warm", tmp_path) is None
    with pytest.raises(registry.StockError):
        registry.require_frozen("stock-f-young-warm", tmp_path)


def test_freeze_refuses_when_every_take_is_unusable(tmp_path):
    model = FakeModel()
    model.generate = lambda text, **k: tone_wav(1.0)
    with pytest.raises(registry.StockError):
        design.freeze("stock-m-adult-deep", tmp_path, takes=2, adapter_factory=lambda d, s: fake_adapter(model, design=d, seed=s), log=lambda *_: None)
    assert registry.frozen_meta("stock-m-adult-deep", tmp_path) is None


def test_unknown_voice_or_tone_is_refused(tmp_path):
    with pytest.raises(registry.StockError):
        design.freeze("stock-nope", tmp_path, adapter_factory=lambda *a: None)
    with pytest.raises(registry.StockError):
        design.freeze("stock-f-young-warm~sparkly", tmp_path, adapter_factory=lambda *a: None)


def test_stock_adapter_needs_a_frozen_reference(tmp_path):
    with pytest.raises(registry.StockError):
        design.build_adapter("stock-f-young-warm", tmp_path, gpu=False)


def fake_freeze(vid, root):
    """A frozen reference without a model: the real sidecar format."""
    wav, side = registry.ref_paths(vid, root)
    write_wav(wav, tone_wav(8), RATE)
    base, tone = registry.split_id(vid)
    side.write_text(json.dumps({"id": vid, "description": registry.description_for(registry.get(base), tone), "seed": 1, "sha256": registry.sha256_file(wav),
                                "sentence": design.DESIGN_SENTENCE}))


class FakeSynth:
    languages = {"en", "es", "km"}

    def __init__(self):
        self.n = 0

    def synthesize(self, text, lang, out_wav):
        self.n += 1
        d = write_wav(out_wav, tone_wav(2.0), RATE)
        return {"duration_s": d, "synth_s": 0.2, "sample_rate": RATE, "rtf": 0.1}


# ---------------------------------------------------------------- the lab grid
def test_grid_writes_the_lab_layout_and_skips_finished_clips(tmp_path):
    out, assets, synth = tmp_path / "run", tmp_path / "assets", FakeSynth()
    args = dict(voices=["stock-f-young-warm"], tones=["neutral", "professional"], langs=["en", "es"], limit=2, assets=assets,
                adapter_factory=lambda vid: synth, freezer=fake_freeze, log=lambda *_: None)
    stats = grid.run(out, **args)
    assert stats["ok"] == 8 and stats["failed"] == 0 and synth.n == 8
    plain = json.loads((out / "voxcpm2-design~stock-f-young-warm" / "meta.json").read_text())
    styled = json.loads((out / "voxcpm2-design~stock-f-young-warm~professional" / "meta.json").read_text())
    assert plain["designed"] and plain["kind"] == "plain" and plain["gender"] == "Female" and plain["ai_generated"]
    assert styled["kind"] == "style" and styled["style"] == "professional" and styled["voice"] == "voxcpm2-design~stock-f-young-warm"
    rows = [json.loads(l) for l in (out / "voxcpm2-design~stock-f-young-warm" / "manifest.jsonl").read_text().splitlines()]
    assert {(r["lang"], r["id"]) for r in rows} == {("en", "S01"), ("en", "M01"), ("es", "S01"), ("es", "M01")}
    assert all(r["status"] == "ok" and r["wav"].endswith(".wav") and (out / r["wav"]).is_file() for r in rows)
    again = grid.run(out, **args)
    assert again["ok"] == 0 and again["skipped_existing"] == 8 and synth.n == 8


def test_grid_skips_languages_the_adapter_does_not_support_and_unfrozen_voices_when_not_asked_to_freeze(tmp_path):
    out, assets = tmp_path / "run", tmp_path / "assets"
    stats = grid.run(out, ["stock-f-young-warm"], ["neutral"], ["en"], 1, freeze_missing=False, assets=assets, adapter_factory=lambda v: FakeSynth(),
                     log=lambda *_: None)
    assert stats["failed"] == 1 and stats["voices"] == 0
    fake_freeze("stock-f-young-warm", assets)
    stats = grid.run(out, ["stock-f-young-warm"], ["neutral"], ["en", "yue"], 1, assets=assets, adapter_factory=lambda v: FakeSynth(), log=lambda *_: None)
    assert stats["ok"] == 1 and stats["skipped_unsupported"] == 1


def test_grid_rejects_unknown_voice_or_tone_before_any_work(tmp_path):
    with pytest.raises(registry.StockError):
        grid.plan(["stock-f-young-warm"], ["sparkly"], ["en"])
    with pytest.raises(registry.StockError):
        grid.plan(["stock-zzz"], ["neutral"], ["en"])


# ---------------------------------------------------------------- the demo render, like Channarith
def test_stock_voice_renders_for_the_demo_without_consent_and_is_gated_on_its_reference(tmp_path, monkeypatch):
    stock = {"id": "stock-f-young-warm", "label": "Sage", "kind": "stock", "stock": "stock-f-young-warm", "model": "voxcpm2", "active": True,
             "primary_lang": "en", "ai_label": registry.AI_LABEL, "gender": "female"}
    clone = {"id": "someone", "label": "Someone", "speaker": "someone", "model": "voxcpm2", "active": True, "primary_lang": "en", "gender": "male"}
    vj = tmp_path / "voices.json"
    vj.write_text(json.dumps({"voices": [stock, clone]}))
    monkeypatch.setattr(render, "VOICES", vj)
    manifest = {"voices": [stock, clone], "clips": [{"hash": "aa11", "lang": "en", "text": "Hello.", "demo": "drivers_ed"}]}
    assets = tmp_path / "assets"
    with pytest.raises(SystemExit):   # not frozen yet
        render.run("stock-f-young-warm", assets, None, None, None, manifest, adapter=FakeSynth(), convert=shutil.copyfile)
    fake_freeze("stock-f-young-warm", assets)
    stats = render.run("stock-f-young-warm", assets, None, None, None, manifest, adapter=FakeSynth(), convert=shutil.copyfile)
    assert stats["ok"] == 1 and stats["failed"] == 0
    side = json.loads((assets / "stock-f-young-warm" / "en" / "aa11.json").read_text())
    assert side["designed"] is True and side["ai_generated"] is True and side["speaker"] == "stock-f-young-warm"
    voices = {v["id"]: v for v in json.loads((assets / "voices.json").read_text())["voices"]}
    assert voices["stock-f-young-warm"]["active"] is True and voices["stock-f-young-warm"]["label"] == "Sage (designed)"
    assert voices["stock-f-young-warm"]["gender"] == "female"
    assert voices["someone"]["active"] is False, "a clone is still gated on consent, a stock voice is not"


def test_stock_voice_is_inactive_without_a_frozen_reference_or_when_switched_off(tmp_path):
    stock = {"id": "stock-m-adult-deep", "label": "Cedar", "kind": "stock", "model": "voxcpm2", "active": True, "gender": "male"}
    doc = render.publish(tmp_path, {"voices": [stock], "clips": []})
    assert doc["voices"][0]["active"] is False
    fake_freeze("stock-m-adult-deep", tmp_path)
    assert render.publish(tmp_path, {"voices": [stock], "clips": []})["voices"][0]["active"] is True
    assert render.publish(tmp_path, {"voices": [{**stock, "active": False}], "clips": []})["voices"][0]["active"] is False


def test_voice_cfg_resolves_a_tone_variant_of_a_stock_voice_only():
    cfg = render.voice_cfg("stock-f-young-warm~professional")
    assert cfg["id"] == "stock-f-young-warm~professional" and cfg["tone"] == "professional" and cfg["kind"] == "stock"
    with pytest.raises(SystemExit):
        render.voice_cfg("channarith~professional")


# ---------------------------------------------------------------- the command line
def test_cli_list_and_check(capsys):
    assert cli.main(["list"]) == 0
    assert "stock-f-young-warm" in capsys.readouterr().out
    assert cli.main(["check", "calm and slow"]) == 0
    assert cli.main(["check", "sounds like a famous singer"]) == 1


def test_lab_has_a_badge_for_designed_voices():
    from pathlib import Path

    js = (Path(render.__file__).parents[1] / "lab" / "static" / "lab.js").read_text(encoding="utf-8")
    assert "voice.meta.designed" in js and "VoxCPM2 designed" in js
