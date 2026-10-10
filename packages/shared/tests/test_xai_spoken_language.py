"""Khmer must not be sent to xAI as Thai. Cantonese is not Mandarin."""

from __future__ import annotations

import json

from aoep_shared.meeting.natural_tts import neural_voice_for
from aoep_shared.voice_catalog import resolve_voice
from aoep_shared.xai_realtime import build_voice_session
from aoep_shared.xai_spoken_language import (
    CANTONESE_EDGE_VOICE,
    KHMER_EDGE_VOICE,
    MANDARIN_EDGE_VOICE,
    plan_spoken_language,
)


def _hint(event: dict) -> str:
    transcription = event["session"]["audio"]["input"].get("transcription") or {}
    return str(transcription.get("language_hint") or "")


def test_khmer_is_not_sent_as_thai():
    plan = plan_spoken_language("km")
    assert plan.requested == "km"
    assert plan.use_xai is False
    assert plan.engine == "edge-tts"
    assert plan.xai_language == ""
    assert plan.xai_language != "th"
    assert plan.edge_voice == KHMER_EDGE_VOICE
    assert "km-KH" in plan.edge_voice
    assert "th-TH" not in plan.edge_voice
    blob = json.dumps(plan.to_dict())
    assert '"th"' not in blob
    assert "th-TH" not in blob
    assert "Khmer" in plan.instructions or "Cambod" in plan.instructions
    assert "Speak Thai" not in plan.instructions

    regional = plan_spoken_language("km-KH")
    assert regional.requested == "km"
    assert regional.use_xai is False
    assert regional.xai_language != "th"

    session = build_voice_session("solo", language="km")
    assert session.use_xai is False
    assert session.xai_language == ""
    event = session.session_update_event()
    assert _hint(event) == ""
    dumped = json.dumps(event)
    assert "th-TH" not in dumped
    assert "language_hint" not in dumped
    assert "Speak Thai" not in event["session"]["instructions"]


def test_cantonese_is_distinct_from_mandarin():
    mandarin = plan_spoken_language("zh")
    cantonese = plan_spoken_language("yue")
    hong_kong = plan_spoken_language("zh-HK")

    assert mandarin.use_xai is True
    assert mandarin.xai_language == "zh"
    assert mandarin.edge_voice == MANDARIN_EDGE_VOICE

    # yue is an xAI speech-to-text code, not a speech-to-speech code.
    # Sending it is ignored and the realtime voice auto-detects Mandarin.
    assert cantonese.use_xai is False
    assert cantonese.requested == "yue"
    assert cantonese.engine == "edge-tts"
    assert cantonese.xai_language == ""
    assert cantonese.xai_language != mandarin.xai_language
    assert cantonese.edge_voice == CANTONESE_EDGE_VOICE
    assert "zh-HK" in cantonese.edge_voice
    assert cantonese.edge_voice != mandarin.edge_voice

    assert hong_kong.requested == "yue"
    assert hong_kong.use_xai is False
    assert hong_kong.xai_language == ""
    assert hong_kong.xai_language != "zh"
    assert hong_kong.edge_voice == CANTONESE_EDGE_VOICE

    zh_event = build_voice_session("solo", language="zh").session_update_event()
    yue_session = build_voice_session("solo", language="yue")
    assert yue_session.use_xai is False
    yue_event = yue_session.session_update_event()
    assert _hint(zh_event) == "zh"
    assert _hint(yue_event) == ""
    assert "language_hint" not in json.dumps(yue_event)
    assert "Speak Mandarin Chinese" in zh_event["session"]["instructions"]
    assert "Speak only Hong Kong Cantonese" in yue_event["session"]["instructions"]
    assert "Do not speak Cantonese" in zh_event["session"]["instructions"]
    assert "Do not speak Mandarin" in yue_event["session"]["instructions"]

    assert neural_voice_for("km") == "km-KH-SreymomNeural"
    assert not neural_voice_for("km").startswith("th-")
    assert neural_voice_for("zh") == "zh-CN-XiaoxiaoNeural"
    assert neural_voice_for("yue") == "zh-HK-HiuMaanNeural"
    assert neural_voice_for("zh-HK") == "zh-HK-HiuMaanNeural"
    assert resolve_voice("", language="zh").locale == "zh-CN"
    assert resolve_voice("", language="yue").locale == "zh-HK"
    assert resolve_voice("", language="zh-HK").edge_voice.startswith("zh-HK")
    # A saved Mandarin or Thai accent must not win over the spoken language.
    assert resolve_voice("zh_bj_f", language="yue").edge_voice.startswith("zh-HK")
    assert resolve_voice("zh_cn_f", language="zh-HK").locale == "zh-HK"
    khmer_voice = resolve_voice("th_th_f", language="km")
    assert khmer_voice is not None
    assert khmer_voice.edge_voice.startswith("km-KH")
    assert not khmer_voice.edge_voice.startswith("th-")
