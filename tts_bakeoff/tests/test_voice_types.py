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
