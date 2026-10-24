import re

from tts_bakeoff import voice_types as vt
from tts_bakeoff.adapters import REGISTRY


def test_no_macos_say_adapter():
    assert "macos_say" not in REGISTRY and "edge_tts" in REGISTRY


def test_accent_and_style_plan():
    plan = list(vt.jobs({"accents", "styles"}))
    models = {j["model"] for j in plan}
    assert len(models) == len(plan)
    voices = {j["voice"] for j in plan}
    for needed in ("zh-HK-HiuMaanNeural", "zh-HK-WanLungNeural", "en-GB-SoniaNeural", "en-SG-LunaNeural", "en-AU-NatashaNeural"):
        assert needed in voices
    styles = {j["model"].split("~")[1] for j in plan if "~" in j["model"]}
    assert {"professional", "cute", "anime", "tough", "heavy", "light"} <= styles
    assert all(j["text"].strip() for j in plan)


def test_singlish_and_cantonese_texts():
    assert "lah" in vt.text_for("en", "en-SG-LunaNeural")
    assert "lah" not in vt.text_for("en", "en-GB-SoniaNeural")
    assert vt.text_for("zh", "zh-TW-HsiaoChenNeural") != vt.text_for("zh", "zh-CN-XiaoxiaoNeural")
    assert "唔" in vt.text_for("yue", "zh-HK-HiuMaanNeural")


def test_presets_are_valid_prosody_strings():
    for rate, pitch, volume in vt.PRESETS.values():
        assert re.fullmatch(r"[+-]\d+%", rate) and re.fullmatch(r"[+-]\d+Hz", pitch) and re.fullmatch(r"[+-]\d+%", volume)


def test_blend_is_a_weighted_average_of_presets():
    assert vt.blend({"professional": 1}) == vt.PRESETS["professional"]
    assert vt.blend({"cute": 50, "anime": 50}) == ("+13%", "+35Hz", "+5%")
    assert vt.blend({"professional": 75, "cute": 25}) == ("+0%", "+8Hz", "+0%")
    assert len(vt.BLEND_WEIGHTS) == 13
    assert all(sum(w.values()) == 100 for w in vt.BLEND_WEIGHTS.values())


def test_every_language_gets_every_preset_and_blend_on_both_defaults():
    import json
    from tts_bakeoff.edge_all import build_plan
    from tts_bakeoff.edge_catalog import SNAPSHOT, load_voices

    doc = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    plan, models = build_plan(doc["catalog"], load_voices())
    n_blend = len(vt.BLEND_WEIGHTS)
    for code, e in doc["catalog"].items():
        if e["status"] != "voice":
            continue
        for voice in (e["default"]["female"], e["default"]["male"]):
            if not voice:
                continue
            styles = {m["style"] for k, m in models.items() if m["lang"] == code and k.startswith(voice + "~")}
            assert set(vt.PRESETS) <= styles
            assert sum(1 for s in styles if s.startswith("blend-")) == n_blend
