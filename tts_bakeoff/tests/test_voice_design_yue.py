"""Cantonese stock voices: the bigger registry, adult-only tones, the two design methods, the Cantonese sentences, the review sheet and clearing.
No model, no GPU."""
import json
import shutil

import pytest

np = pytest.importorskip("numpy")

from tts_bakeoff.demo_voice import render
from tts_bakeoff.tests.test_voice_design import RATE, FakeModel, FakeSynth, fake_adapter, fake_freeze, tone_wav
from tts_bakeoff.voice_design import __main__ as cli
from tts_bakeoff.voice_design import design, grid, prompt, registry, review, yue_sentences
from tts_bakeoff.voice_design.prompt import DescriptionRejected, build_description, validate_description


class CjkModel(FakeModel):
    """Chinese runs at ~4.3 characters a second, like the speech-rate check expects."""

    def generate(self, text, cfg_value=2.0, inference_timesteps=10, seed=None, **kw):
        self.calls.append({"text": text, "seed": seed, **kw})
        return tone_wav(max(len(self._spoken(text)) / 4.3, 0.5))


class YueSynth(FakeSynth):
    languages = {"yue"}


@pytest.fixture
def stock_copy(tmp_path):
    p = tmp_path / "stock_voices.json"
    shutil.copy(registry.STOCK, p)
    return p


# ---------------------------------------------------------------- adults only, real people never
@pytest.mark.parametrize("bad", ["a child's voice", "a kid reading a story", "a little girl", "a cheerful young girl", "a little boy", "a teenager",
                                 "toddler voice", "sounds like Taylor Swift", "Barack Obama", "in the style of a famous actor"])
def test_the_guard_still_rejects_child_like_descriptions_and_real_people(bad):
    with pytest.raises(DescriptionRejected):
        validate_description(bad)


def test_adult_descriptions_pass():
    for good in ("an adult woman, warm", "A young adult man, crisp, articulate voice", "calm and slow"):
        assert validate_description(good)


def test_no_word_in_the_vocabulary_makes_a_voice_child_like():
    texts = [*prompt.TONES.values(), *prompt.TIMBRES.values(), *prompt.ACCENTS.values(), *prompt.GENDERS.values()]
    assert not [t for t in texts if prompt._CHILDLIKE.search(t)]
    assert "adult" in prompt.TONES["cute"] and "adult" in prompt.TONES["anime"]
    assert "high-pitched" not in prompt.TONES["anime"]   # pitch pushed up reads as a child and flattens Cantonese tones


def test_registry_has_more_adult_voices_with_the_three_requested_tones():
    voices = registry.voices()
    assert 12 <= len(voices) <= 16
    assert sum(v["g"] == "f" for v in voices) == sum(v["g"] == "m" for v in voices)
    assert all(v["age"] in ("young", "adult", "older") for v in voices)
    assert all({"professional", "cute", "anime"} <= set(v["tones"]) for v in voices)
    assert registry.validate_registry() == []
    assert len({v["label"] for v in voices}) == len(voices)
    for v in voices:
        assert prompt.validate_description(registry.description_for(v, "cute")) and "adult" in registry.description_for(v, "anime")


def test_a_child_voice_is_still_rejected_by_the_registry_check(stock_copy):
    doc = registry.load(stock_copy)
    doc["voices"][0]["age"] = "child"
    registry.save(doc, stock_copy)
    assert any("child" in p for p in registry.validate_registry(stock_copy))


def test_descriptions_use_an_before_a_vowel():
    assert build_description("m", "adult", "rich").startswith("An adult man")
    assert build_description("f", "older", "soft").startswith("An older, mature woman")
    assert build_description("f", "young", "warm").startswith("A young adult woman")


# ---------------------------------------------------------------- ids, seeds, methods
def test_variant_ids_carry_the_design_language_and_the_tone():
    assert registry.variant_id("stock-f-young-warm", "cute", "yue") == "stock-f-young-warm.yue~cute"
    assert registry.variant_id("stock-f-young-warm", None, "yue") == "stock-f-young-warm.yue"
    assert registry.variant_id("stock-f-young-warm", "cute", "en") == "stock-f-young-warm~cute"
    assert registry.split_full("stock-f-young-warm.yue~cute") == ("stock-f-young-warm", "cute", "yue")
    assert registry.split_id("stock-f-young-warm.yue~cute") == ("stock-f-young-warm", "cute")
    with pytest.raises(registry.StockError):
        registry.split_full("stock-f-young-warm.fr")


def test_a_cantonese_design_gets_its_own_seed():
    e = registry.get("stock-f-young-warm")
    assert registry.seed_for(e, "cute", "yue") == registry.seed_for(e, "cute") + 50


def test_freeze_in_cantonese_designs_on_a_cantonese_sentence_into_its_own_folder(tmp_path):
    model = CjkModel()
    factory = lambda d, s: fake_adapter(model, design=d, seed=s)   # noqa: E731
    meta = design.freeze("stock-f-young-warm.yue~cute", tmp_path, takes=2, adapter_factory=factory, log=lambda *_: None)
    assert meta["lang"] == "yue" and meta["sentence"] == design.DESIGN_SENTENCES["yue"] and meta["tone"] == "cute" and meta["base"] == "stock-f-young-warm"
    assert all(c["text"].endswith(design.DESIGN_SENTENCES["yue"]) for c in model.calls)
    assert "cute" in meta["description"] and "adult" in meta["description"]
    wav, _ = registry.ref_paths("stock-f-young-warm.yue~cute", tmp_path)
    assert wav.parent.name == "stock-f-young-warm.yue--cute" and registry.frozen_meta("stock-f-young-warm.yue~cute", tmp_path)
    assert registry.frozen_meta("stock-f-young-warm~cute", tmp_path) is None, "the English-designed reference is a different file"


# ---------------------------------------------------------------- the Cantonese sentences
def test_cantonese_sentences_are_reviewed_pure_chinese_lines_plus_the_tone_line():
    rows = yue_sentences.load()
    assert [r["id"] for r in rows] == ["Y01", "T01", "Y02", "Y03"]
    assert rows[1]["text"] == yue_sentences.TONE_CONTRAST and all(ch in rows[1]["text"] for ch in "詩史試時市事")
    items = json.loads(yue_sentences.YUE.read_text(encoding="utf-8"))["items"]
    for r in (rows[0], rows[2], rows[3]):
        assert r["lang"] == "yue" and r["review_status"] in ("ok", "fixed")
        assert not yue_sentences._LATIN.search(r["text"])
        assert any(it["text"] == r["text"] and it["status"] in ("ok", "fixed") for it in items.values())
    assert [len(r["text"]) for r in (rows[0], rows[2], rows[3])] == sorted(len(r["text"]) for r in (rows[0], rows[2], rows[3]))
    assert [r["id"] for r in yue_sentences.load(2)] == ["Y01", "T01"]


def test_unreviewed_lines_are_never_picked(tmp_path):
    p = tmp_path / "yue.json"
    p.write_text(json.dumps({"items": {"a": {"text": "你好嗎，今日點呀？", "status": "unreviewed"}, "b": {"text": "你好嗎，今日點呀？", "status": "needs_fix"}}}))
    assert [r["id"] for r in yue_sentences.load(path=p)] == ["T01"]


# ---------------------------------------------------------------- the grid, both methods
def test_presets_have_the_requested_shape():
    small, full = grid.PRESETS["cantonese-small"], grid.PRESETS["cantonese-full"]
    assert len(small["voices"]) == 4 and small["tones"] == ["neutral", "professional", "cute", "anime"] and small["methods"] == ["en-ref", "yue-ref"]
    assert small["langs"] == ["yue"] and small["limit"] == 2 and small["sentences"] == "yue"
    assert full["voices"] is None and full["limit"] == 4 and full["tones"] == small["tones"]
    assert set(small["voices"]) <= {v["id"] for v in registry.voices()}
    assert len({registry.get(v)["g"] for v in small["voices"]}) == 2


def test_grid_makes_both_methods_with_cantonese_sentences_and_lab_metadata(tmp_path):
    out, assets, synth = tmp_path / "run", tmp_path / "assets", YueSynth()
    stats = grid.run(out, ["stock-f-young-warm"], ["neutral", "cute"], ["yue"], 2, assets=assets, adapter_factory=lambda vid: synth,
                     freezer=fake_freeze, log=lambda *_: None, methods=("en-ref", "yue-ref"), sentences="yue")
    assert stats["ok"] == 8 and stats["failed"] == 0 and stats["voices"] == 4
    folders = sorted(p.name for p in out.glob("voxcpm2-design~*"))
    assert folders == ["voxcpm2-design~stock-f-young-warm", "voxcpm2-design~stock-f-young-warm.yue",
                       "voxcpm2-design~stock-f-young-warm.yue~cute", "voxcpm2-design~stock-f-young-warm~cute"]
    en_plain = json.loads((out / "voxcpm2-design~stock-f-young-warm" / "meta.json").read_text())
    yue_plain = json.loads((out / "voxcpm2-design~stock-f-young-warm.yue" / "meta.json").read_text())
    yue_cute = json.loads((out / "voxcpm2-design~stock-f-young-warm.yue~cute" / "meta.json").read_text())
    assert en_plain["method"] == "en-ref" and yue_plain["method"] == "yue-ref" and yue_plain["design_lang"] == "yue"
    assert yue_cute["kind"] == "style" and yue_cute["voice"] == "voxcpm2-design~stock-f-young-warm.yue" and "Cantonese ref" in yue_cute["label"]
    rows = [json.loads(l) for l in (out / "voxcpm2-design~stock-f-young-warm.yue" / "manifest.jsonl").read_text().splitlines()]
    assert [r["id"] for r in rows] == ["Y01", "T01"] and rows[1]["text"] == yue_sentences.TONE_CONTRAST


def test_grid_default_is_still_the_english_design_and_the_standard_sentences(tmp_path):
    out, assets, synth = tmp_path / "run", tmp_path / "assets", FakeSynth()
    grid.run(out, ["stock-f-young-warm"], ["neutral"], ["en"], 1, assets=assets, adapter_factory=lambda vid: synth, freezer=fake_freeze, log=lambda *_: None)
    assert [p.name for p in out.glob("voxcpm2-design~*")] == ["voxcpm2-design~stock-f-young-warm"]


def test_grid_rejects_an_unknown_method(tmp_path):
    with pytest.raises(registry.StockError):
        grid.run(tmp_path, ["stock-f-young-warm"], ["neutral"], ["yue"], 1, methods=("klingon-ref",), freezer=fake_freeze)


# ---------------------------------------------------------------- clearing, the review sheet, apply
def test_clear_needs_a_native_speaker_and_valid_tones(stock_copy):
    with pytest.raises(registry.StockError):
        registry.clear("stock-f-young-warm", "yue", " ", path=stock_copy)
    with pytest.raises(registry.StockError):
        registry.clear("stock-f-young-warm", "yue", "Wei", tones=["sparkly"], path=stock_copy)
    with pytest.raises(registry.StockError):
        registry.clear("stock-f-young-warm", "yue", "Wei", method="magic", path=stock_copy)
    rec = registry.clear("stock-f-young-warm", "yue", "Wei", tones=["professional", "cute", "neutral"], method="yue-ref", note="tones good", path=stock_copy,
                         today="2026-10-25")
    assert rec == {"by": "Wei", "on": "2026-10-25", "method": "yue-ref", "tones": ["professional", "cute"], "note": "tones good"}
    e = registry.get("stock-f-young-warm", stock_copy)
    assert e["langs"] == ["en", "yue"] and e["cleared"]["yue"]["by"] == "Wei" and e["quality"]["yue"] == "tones good"
    assert registry.validate_registry(stock_copy) == []
    assert registry.unclear("stock-f-young-warm", "yue", stock_copy) is True
    e = registry.get("stock-f-young-warm", stock_copy)
    assert e["langs"] == ["en"] and "yue" not in e.get("cleared", {})
    assert registry.unclear("stock-f-young-warm", "yue", stock_copy) is False


def test_the_picker_cannot_activate_a_voice_nobody_cleared(stock_copy, tmp_path):
    vj = tmp_path / "voices.json"
    vj.write_text(json.dumps({"voices": [{"id": "stock-f-young-warm", "active": False}]}))
    with pytest.raises(registry.StockError):
        registry.activate("stock-f-young-warm", vj, stock_copy)
    registry.clear("stock-f-young-warm", "yue", "Wei", path=stock_copy)
    registry.activate("stock-f-young-warm", vj, stock_copy)
    assert json.loads(vj.read_text())["voices"][0]["active"] is True


def test_the_committed_voices_are_all_inactive_until_someone_clears_them():
    cleared = {v["id"] for v in registry.voices() if v.get("cleared")}
    vj = json.loads(registry.VOICES_JSON.read_text())["voices"]
    for v in vj:
        if v.get("kind") == "stock" and v.get("active"):
            assert v["id"] in cleared, f"{v['id']} is active but no native speaker has cleared it"
    assert {v["id"] for v in registry.voices()} <= {v["id"] for v in vj}, "every registry voice has a voices.json entry"


def test_reference_id_uses_the_cantonese_design_only_when_cleared_that_way_and_frozen(stock_copy, tmp_path):
    assets = tmp_path / "assets"
    fake_freeze("stock-f-young-warm", assets)
    fake_freeze("stock-f-young-warm.yue", assets)
    ref = lambda lang: registry.reference_id("stock-f-young-warm", lang, stock_copy, assets)   # noqa: E731
    assert ref("yue") == "stock-f-young-warm"
    registry.clear("stock-f-young-warm", "yue", "Wei", method="en-ref", path=stock_copy)
    assert ref("yue") == "stock-f-young-warm"
    registry.clear("stock-f-young-warm", "yue", "Wei", method="yue-ref", path=stock_copy)
    assert ref("yue") == "stock-f-young-warm.yue" and ref("en") == "stock-f-young-warm"
    shutil.rmtree(registry.ref_dir("stock-f-young-warm.yue", assets))
    assert ref("yue") == "stock-f-young-warm", "falls back when the Cantonese reference is not on this machine"


def run_grid_for_review(tmp_path):
    out, assets = tmp_path / "run", tmp_path / "assets"
    for vid in ("stock-f-young-warm", "stock-m-adult-deep"):
        grid.run(out, [vid], ["neutral", "cute"], ["yue"], 2, assets=assets, adapter_factory=lambda v: YueSynth(), freezer=fake_freeze,
                 log=lambda *_: None, methods=("en-ref", "yue-ref"), sentences="yue")
    return out


def test_review_page_lists_every_voice_tone_and_method_with_relative_audio(tmp_path):
    out = run_grid_for_review(tmp_path)
    rows = review.collect(out, "yue")
    assert len(rows) == 8 and {r["method"] for r in rows} == {"en-ref", "yue-ref"}
    html = review.page(out, "yue")
    assert html.count("class='cell'") == 8 and 'src="voxcpm2-design~stock-f-young-warm.yue~cute/yue/Y01.wav"' in html
    assert "Download my decisions" in html and "詩、史、試、時、市、事" in html and "ADULT" in html
    assert "http://" not in html.split("<script>")[0] and "https://" not in html
    with pytest.raises(SystemExit):
        review.page(out, "th")


def test_apply_review_clears_only_voices_whose_neutral_variant_is_ok(stock_copy, tmp_path):
    d = lambda voice, tone, method, status, note="": {"voice": voice, "tone": tone, "method": method, "status": status, "note": note}   # noqa: E731
    f = tmp_path / "decisions.json"
    f.write_text(json.dumps({"lang": "yue", "reviewer": "Wei", "decisions": [
        d("stock-f-young-warm", "neutral", "yue-ref", "ok"), d("stock-f-young-warm", "cute", "yue-ref", "ok"),
        d("stock-f-young-warm", "anime", "yue-ref", "not_ok", "sounds like a child"), d("stock-f-young-warm", "professional", "en-ref", "ok"),
        d("stock-f-young-warm", "neutral", "en-ref", "ok"),
        d("stock-m-adult-deep", "neutral", "en-ref", "not_ok", "tones are wrong"), d("stock-m-adult-deep", "neutral", "yue-ref", "unsure"),
        d("stock-m-adult-deep", "cute", "en-ref", "ok"),
    ]}), encoding="utf-8")
    summary = review.apply(f, path=stock_copy, today="2026-10-25")
    assert summary["cleared"] == {"stock-f-young-warm": {"method": "yue-ref", "tones": ["cute"]}}
    assert summary["not_cleared"] == ["stock-m-adult-deep"] and summary["reviewer"] == "Wei"
    e = registry.get("stock-f-young-warm", stock_copy)
    assert e["cleared"]["yue"]["by"] == "Wei" and e["cleared"]["yue"]["tones"] == ["cute"] and "yue" in e["langs"]
    m = registry.get("stock-m-adult-deep", stock_copy)
    assert "yue" not in m["langs"] and "tones are wrong" in m["quality"]["yue"] and "Wei" in m["quality"]["yue"]
    assert registry.validate_registry(stock_copy) == []


def test_apply_review_needs_a_reviewer_name(stock_copy, tmp_path):
    f = tmp_path / "d.json"
    f.write_text(json.dumps({"lang": "yue", "reviewer": "", "decisions": []}))
    with pytest.raises(registry.StockError):
        review.apply(f, path=stock_copy)


# ---------------------------------------------------------------- the demo render respects clearing
def test_publish_lists_a_designed_voice_only_in_cleared_languages(tmp_path, monkeypatch):
    stock = {"id": "stock-f-young-warm", "label": "Sage", "kind": "stock", "model": "voxcpm2", "active": True, "gender": "female"}
    fake_freeze("stock-f-young-warm", tmp_path)
    for lang in ("en", "yue"):
        (tmp_path / "stock-f-young-warm" / lang).mkdir(parents=True, exist_ok=True)
        (tmp_path / "stock-f-young-warm" / lang / "aa.mp3").write_bytes(b"x" * 600)
    render.publish(tmp_path, {"voices": [stock], "clips": []})
    index = json.loads((tmp_path / "stock-f-young-warm" / "index.json").read_text())
    assert set(index["clips"]) == {"en"}, "Cantonese is not cleared: nothing is published for it"
    voices = registry.voices()
    patched = [{**v, "langs": [*v["langs"], "yue"]} if v["id"] == "stock-f-young-warm" else v for v in voices]
    monkeypatch.setattr(registry, "voices", lambda path=registry.STOCK: patched)
    render.publish(tmp_path, {"voices": [stock], "clips": []})
    index = json.loads((tmp_path / "stock-f-young-warm" / "index.json").read_text())
    assert set(index["clips"]) == {"en", "yue"}


def test_render_clones_from_the_cantonese_reference_for_languages_cleared_that_way(tmp_path, monkeypatch):
    stock = {"id": "stock-f-young-warm", "label": "Sage", "kind": "stock", "stock": "stock-f-young-warm", "model": "voxcpm2", "active": True,
             "primary_lang": "en", "ai_label": registry.AI_LABEL, "gender": "female"}
    vj = tmp_path / "voices.json"
    vj.write_text(json.dumps({"voices": [stock]}))
    monkeypatch.setattr(render, "VOICES", vj)
    assets = tmp_path / "assets"
    fake_freeze("stock-f-young-warm", assets)
    fake_freeze("stock-f-young-warm.yue", assets)
    patched = [{**v, "langs": ["en", "yue"], "cleared": {"yue": {"by": "Wei", "on": "2026-10-25", "method": "yue-ref", "tones": [], "note": ""}}}
               if v["id"] == "stock-f-young-warm" else v for v in registry.voices()]
    monkeypatch.setattr(registry, "voices", lambda path=registry.STOCK: patched)
    built = []

    class Marker(YueSynth):
        languages = {"en", "yue"}

        def __init__(self, tag):
            super().__init__()
            self.tag = tag

        def synthesize(self, text, lang, out_wav):
            built.append((self.tag, lang))
            return super().synthesize(text, lang, out_wav)

    def fake_build(voice_id, root=None, gpu=True, lang=None, path=registry.STOCK, **kw):
        return Marker(registry.reference_id(voice_id, lang, path, root))

    monkeypatch.setattr(design, "build_adapter", fake_build)
    manifest = {"voices": [stock], "clips": [{"hash": "aa11", "lang": "en", "text": "Hello.", "demo": "drivers_ed"},
                                             {"hash": "bb22", "lang": "yue", "text": "你好。", "demo": "drivers_ed"}]}
    stats = render.run("stock-f-young-warm", assets, None, {"en", "yue"}, None, manifest, convert=shutil.copyfile)
    assert stats["ok"] == 2 and stats["failed"] == 0
    assert ("stock-f-young-warm", "en") in built and ("stock-f-young-warm.yue", "yue") in built


# ---------------------------------------------------------------- the command line
def test_cli_clear_review_page_and_apply(stock_copy, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(registry, "STOCK", stock_copy)
    out = run_grid_for_review(tmp_path)
    page = tmp_path / "sheet.html"
    assert cli.main(["review-page", "--run", str(out), "--lang", "yue", "--out", str(page)]) == 0 and page.is_file()
    assert cli.main(["clear", "--id", "stock-f-young-warm", "--lang", "yue", "--by", ""]) == 1   # an empty reviewer name is refused
    assert "FAILED" in capsys.readouterr().err
    assert cli.main(["unclear", "--id", "stock-f-young-warm", "--lang", "yue"]) == 0
    # nothing is frozen on this machine and --freeze-missing is not given: every unit is skipped and the exit code says so (no GPU needed)
    assert cli.main(["grid", "--out", str(tmp_path / "x"), "--preset", "cantonese-small", "--assets", str(tmp_path / "none")]) == 1
    assert cli.main(["grid", "--out", str(tmp_path / "y"), "--voices", "stock-nope", "--langs", "yue", "--assets", str(tmp_path / "none")]) == 1
    assert "FAILED" in capsys.readouterr().err


def test_cli_list_shows_who_cleared_what(stock_copy, monkeypatch, capsys):
    registry.clear("stock-m-adult-deep", "yue", "Wei", tones=["cute"], method="yue-ref", path=stock_copy)
    monkeypatch.setattr(registry, "voices", lambda path=registry.STOCK: registry.load(stock_copy)["voices"])
    assert cli.main(["list"]) == 0
    line = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("stock-m-adult-deep"))
    assert "yue cleared by Wei" in line and "yue-ref" in line and "cute" in line
