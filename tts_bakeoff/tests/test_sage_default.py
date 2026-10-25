"""Sage (stock-f-young-warm) as the default Salane Voice: the registry flag, the published voices.json, the fixed spoken lines and the render
path. No model, no GPU."""
import json
import shutil

import pytest

np = pytest.importorskip("numpy")

from tts_bakeoff.demo_voice import fixed_lines, manifest as demo_manifest, render
from tts_bakeoff.demo_voice.clip_hash import clip_hash, normalize
from tts_bakeoff.tests.test_voice_design import FakeSynth, fake_freeze
from tts_bakeoff.voice_design import registry

SAGE = "stock-f-young-warm"


@pytest.fixture
def copies(tmp_path):
    stock, voices = tmp_path / "stock_voices.json", tmp_path / "voices.json"
    shutil.copy(registry.STOCK, stock)
    shutil.copy(registry.VOICES_JSON, voices)
    return stock, voices


def repo_voices():
    return json.loads(registry.VOICES_JSON.read_text(encoding="utf-8"))["voices"]


# ---------------------------------------------------------------- the committed state
def test_sage_is_the_one_default_and_the_owner_cleared_english():
    defaults = [v for v in repo_voices() if v.get("default")]
    assert [v["id"] for v in defaults] == [SAGE]
    sage = defaults[0]
    assert sage["active"] is True and sage["gender"] == "female" and sage["primary_lang"] == "en" and sage["kind"] == "stock"
    assert "designed with VoxCPM2" in sage["ai_label"]
    rec = registry.get(SAGE)["cleared"]["en"]
    assert rec["by"].startswith("Channarith") and rec["method"] == "en-ref" and rec["on"]
    assert list(registry.get(SAGE)["cleared"]) == ["en"], "no other language is cleared for the default voice"
    assert registry.validate_voices_json() == [] and registry.validate_registry() == []


def test_other_stock_voices_stay_inactive():
    for v in repo_voices():
        if v.get("kind") == "stock" and v["id"] != SAGE:
            assert v["active"] is False and not v.get("default")


# ---------------------------------------------------------------- set_default
def test_set_default_moves_the_flag_and_needs_english_clearance_and_activation(copies):
    stock, voices = copies
    registry.clear("stock-m-adult-deep", "en", "Owner", path=stock)
    with pytest.raises(registry.StockError, match="switch it on"):
        registry.set_default("stock-m-adult-deep", voices, stock)
    registry.activate("stock-m-adult-deep", voices, stock)
    registry.set_default("stock-m-adult-deep", voices, stock)
    doc = json.loads(voices.read_text())["voices"]
    assert [v["id"] for v in doc if v.get("default")] == ["stock-m-adult-deep"]
    assert registry.validate_voices_json(voices, stock) == []


def test_set_default_refuses_a_voice_nobody_cleared(copies):
    stock, voices = copies
    with pytest.raises(registry.StockError, match="not cleared in English"):
        registry.set_default("stock-f-adult-crisp", voices, stock)


def test_validate_voices_json_catches_two_defaults_inactive_default_and_missing_gender(copies):
    stock, voices = copies
    doc = json.loads(voices.read_text())
    for v in doc["voices"]:
        if v["id"] in ("channarith", "stock-f-adult-crisp"):
            v["default"] = True
    voices.write_text(json.dumps(doc))
    problems = " | ".join(registry.validate_voices_json(voices, stock))
    assert "more than one default" in problems and "must be active" in problems and "not cleared" in problems
    doc = json.loads(voices.read_text())
    for v in doc["voices"]:
        v.pop("default", None)
        if v["id"] == SAGE:
            v["default"] = True
            v.pop("gender")
    voices.write_text(json.dumps(doc))
    assert any("needs a gender" in p for p in registry.validate_voices_json(voices, stock))


# ---------------------------------------------------------------- publish
def test_publish_marks_only_an_active_default_and_keeps_gender_and_language(tmp_path, monkeypatch):
    sage = next(v for v in repo_voices() if v["id"] == SAGE)
    clone = {"id": "someone", "label": "Someone", "speaker": "someone", "model": "voxcpm2", "active": True, "primary_lang": "en", "gender": "male"}
    assets = tmp_path / "assets"
    fake_freeze(SAGE, assets)
    doc = render.publish(assets, {"voices": [sage, clone], "clips": []}, check_consent=lambda s: True)
    by = {v["id"]: v for v in doc["voices"]}
    assert by[SAGE]["default"] is True and by[SAGE]["name"] == "Sage" and by[SAGE]["kind"] == "stock"
    assert by[SAGE]["gender"] == "female" and by[SAGE]["primary_lang"] == "en" and by[SAGE]["label"] == "Sage (designed)"
    assert "default" not in by["someone"] and by["someone"]["gender"] == "male" and by["someone"]["name"] == "Someone"
    # without a frozen reference on this machine the default is not offered at all
    doc = render.publish(tmp_path / "empty", {"voices": [sage, clone], "clips": []}, check_consent=lambda s: True)
    assert not any(v.get("default") for v in doc["voices"]) and doc["voices"][0]["active"] is False


def test_publish_never_writes_two_defaults(tmp_path):
    a = {"id": "stock-f-young-warm", "label": "Sage", "kind": "stock", "stock": SAGE, "model": "voxcpm2", "active": True, "primary_lang": "en",
         "gender": "female", "default": True}
    b = {**a, "id": "stock-f-young-bright", "stock": "stock-f-young-bright", "label": "Lark"}
    assets = tmp_path / "assets"
    fake_freeze(SAGE, assets)
    fake_freeze("stock-f-young-bright", assets)
    doc = render.publish(assets, {"voices": [a, b], "clips": []})
    assert [v["id"] for v in doc["voices"] if v.get("default")] == [SAGE]


def test_the_default_publishes_only_in_its_cleared_language(tmp_path):
    sage = next(v for v in repo_voices() if v["id"] == SAGE)
    assets = tmp_path / "assets"
    fake_freeze(SAGE, assets)
    for lang in ("en", "es"):
        (assets / SAGE / lang).mkdir(parents=True)
        (assets / SAGE / lang / "aa11.mp3").write_bytes(b"x" * 600)
    render.publish(assets, {"voices": [sage], "clips": []})
    index = json.loads((assets / SAGE / "index.json").read_text())
    assert list(index["clips"]) == ["en"], "Spanish clips exist but Spanish is not cleared: they must not be offered"


# ---------------------------------------------------------------- fixed spoken lines
def test_every_key_the_on_the_go_page_speaks_is_accounted_for():
    assert fixed_lines.spoken_keys_in_source() - fixed_lines.known_keys() == set()
    assert fixed_lines.spoken_keys_in_source() >= {"drive.pausedAnswer", "drive.speedAnswer", "drive.limitRate", "drive.limitSession", "drive.backToCourse",
                                                   "drive.coursePlaying", "drive.courseNextIs", "drive.courseList", "drive.courseUnknown"}


def test_committed_fixed_lines_are_the_ones_the_code_builds():
    doc = json.loads(fixed_lines.FIXED.read_text(encoding="utf-8"))
    assert doc["lines"] == fixed_lines.build(doc["titles"]), "re-run: python3 -m tts_bakeoff.demo_voice.fixed_lines --capture"
    assert set(doc["titles"]) == set(fixed_lines.demo_course_ids()) and len(doc["titles"]) == 16


def test_expansions_cover_every_speed_every_retry_second_and_every_course():
    rows = fixed_lines.build({cid: f"Course {i} (audio)" for i, cid in enumerate(fixed_lines.demo_course_ids())})
    texts = {r["text"] for r in rows}
    assert "Speed set to 0.7 times." in texts and "Speed set to 1 times." in texts and "Speed set to 1.6 times." in texts
    assert "Speed set to 1.15 times." in texts and "Speed set to 0.85 times." in texts
    assert "That was a lot of questions at once. Please ask again in 1 seconds." in texts
    assert "That was a lot of questions at once. Please ask again in 60 seconds." in texts
    assert "Playing Course 0." in texts and "Next course: Course 15." in texts
    assert "A few courses: Course 0, Course 1, Course 2, Course 3, Course 4. Say play, then the name." in texts
    assert "Paused. Say or tap Resume when you want to continue." in texts
    assert all("{" not in t for t in texts), "a placeholder was left in a spoken line"
    assert len(texts) == len(rows), "duplicates must collapse"


def test_js_number_matches_how_javascript_prints_the_speed():
    assert [fixed_lines.js_number(x) for x in (1.0, 0.85, 1.5, 0.7, 1.6)] == ["1", "0.85", "1.5", "0.7", "1.6"]


def test_the_manifest_contains_every_fixed_line_and_the_counts_per_demo():
    m = json.loads(demo_manifest.MANIFEST.read_text(encoding="utf-8"))
    have = {(c["lang"], c["hash"]) for c in m["clips"]}
    for row in fixed_lines.load():
        assert ("en", clip_hash("en", normalize(row["text"]))) in have, row["text"]
    by = {}
    for c in m["clips"]:
        by[(c["demo"], c["lang"])] = by.get((c["demo"], c["lang"]), 0) + 1
    assert by[("on_the_go_fixed", "en")] == len(fixed_lines.load())
    assert by[("drivers_ed", "en")] == 84 and by[("landing", "en")] == 3
    assert {v["id"] for v in m["voices"] if v.get("default")} == {SAGE}


def test_refresh_offline_keeps_the_fixed_lines_without_the_network(tmp_path):
    out = demo_manifest.refresh_offline()
    assert sum(1 for c in out["clips"] if c["demo"] == "on_the_go_fixed") == len(fixed_lines.load())


# ---------------------------------------------------------------- Sage renders every English line, resumably
def test_sage_renders_every_english_line_and_a_second_run_skips_them(tmp_path):
    sage = next(v for v in repo_voices() if v["id"] == SAGE)
    clips = [{"hash": f"{i:014x}", "lang": "en", "text": f"Line {i}.", "demo": d} for i, d in enumerate(["drivers_ed", "landing", "on_the_go_fixed", "vision_play"])]
    clips.append({"hash": "ff" * 7, "lang": "es", "text": "Hola.", "demo": "on_the_go"})
    manifest = {"voices": [sage], "clips": clips}
    assets = tmp_path / "assets"
    fake_freeze(SAGE, assets)
    synth = FakeSynth()
    stats = render.run(SAGE, assets, None, render.own_langs(sage), None, manifest, adapter=synth, convert=shutil.copyfile)
    assert stats["ok"] == 4 and stats["failed"] == 0, "English lines only: Spanish is not a language Sage is cleared for"
    again = render.run(SAGE, assets, None, render.own_langs(sage), None, manifest, adapter=synth, convert=shutil.copyfile)
    assert again["ok"] == 0 and again["skipped_existing"] == 4 and synth.n == 4
    voices = {v["id"]: v for v in json.loads((assets / "voices.json").read_text())["voices"]}
    assert voices[SAGE]["default"] is True and voices[SAGE]["active"] is True
