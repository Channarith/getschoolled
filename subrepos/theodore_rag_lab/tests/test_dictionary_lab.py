"""Tests for dictionary / dialect / regurgitation / feedback in the RAG lab."""

from __future__ import annotations

import os
from pathlib import Path

import theodore_rag_lab.bakeoff_loop as bl
from fastapi.testclient import TestClient

from aoep_shared.dialect import DIALECTS, normalize_dialect
from aoep_shared.slang import default_lexicon, lexicon_stats
from theodore_rag_lab.bakeoff_loop import RagBakeoffRunner
from theodore_rag_lab.eval_harness import build_demo_index, load_golden
from theodore_rag_lab.main import app


REQUIRED_DIALECTS = {
    "us_south",
    "us_ny",
    "us_ne",
    "us_ca",
    "en_ca",
    "en_gb",
    "en_au",
    "en_sg",
    "zh_bj",
    "zh_sh",
    "zh_yue_gz",
    "zh_min_fj",
}


def test_world_dialects_registered():
    assert REQUIRED_DIALECTS <= set(DIALECTS)
    assert normalize_dialect("singaporean") == "en_sg"
    assert normalize_dialect("beijing") == "zh_bj"
    assert normalize_dialect("cantonese") == "zh_yue_gz"
    assert normalize_dialect("fujianese") == "zh_min_fj"
    assert normalize_dialect("newyork") == "us_ny"
    assert normalize_dialect("new_england") == "us_ne"


def test_lexicon_is_extensive():
    stats = lexicon_stats()
    assert stats["total"] >= 300
    assert stats["from_packs"] >= 250
    regions = set(stats["regions"])
    for need in ("us-south", "us-ny", "us-ne", "sg", "cn-bj", "cn-sh", "cn-gz", "cn-fj", "ca", "au", "uk"):
        assert need in regions, need


def test_dictionary_and_dialect_apis(tmp_path, monkeypatch):
    monkeypatch.setenv("AOEP_FEEDBACK_DIR", str(tmp_path / "fb"))
    # Reset feedback singleton
    import aoep_shared.slang_feedback as sf
    import aoep_shared.slang as slang_mod

    sf._STORE = None
    slang_mod._default = None

    bl._RUNNER = RagBakeoffRunner()
    bl._RUNNER.index = build_demo_index()
    bl._RUNNER.examples = load_golden()[:5]
    bl._RUNNER._seed_champion()

    with TestClient(app) as client:
        h = client.get("/health")
        assert h.status_code == 200
        body = h.json()
        assert body["ok"] is True
        assert body["lexicon_total"] >= 300
        assert "dictionary" in body["features"]
        assert "regurgitation" in body["features"]
        assert "feedback_learning" in body["features"]

        d = client.get("/api/dictionary", params={"region": "us-south", "limit": 20})
        assert d.status_code == 200
        assert d.json()["count"] >= 5

        cat = client.get("/api/dialects")
        assert cat.status_code == 200
        ids = {row["id"] for row in cat.json()["dialects"]}
        assert REQUIRED_DIALECTS <= ids

        probe = client.post(
            "/api/dialects/probe",
            json={"dialect": "en_sg", "text": "Welcome! We will walk through the lesson."},
        )
        assert probe.status_code == 200
        assert "lah" in probe.json()["humanized"].lower() or "go through" in probe.json()["humanized"].lower()

        bj = client.post("/api/dialects/probe", json={"dialect": "zh_bj", "text": "Welcome"})
        assert bj.status_code == 200
        assert bj.json()["dialect"]["id"] == "zh_bj"

        deck = client.get("/api/regurgitate/deck", params={"dialect": "us_south", "n": 5})
        assert deck.status_code == 200
        cards = deck.json()["cards"]
        assert len(cards) >= 3
        card = cards[0]
        # Look up meaning and grade a strong answer
        entry = default_lexicon().lookup(card["phrase"], language=card["language"], region=card["region"])
        assert entry is not None
        grade = client.post(
            "/api/regurgitate/grade",
            json={
                "phrase": card["phrase"],
                "answer": entry.meaning,
                "language": card["language"],
                "region": card["region"],
                "dialect": "us_south",
                "learn": True,
            },
        )
        assert grade.status_code == 200
        assert grade.json()["ok"] is True
        assert grade.json()["score"] >= 0.45

        fb = client.post(
            "/api/feedback",
            json={
                "phrase": "lab only phrase xyz",
                "meaning": "a test-only idiom meaning",
                "language": "en",
                "region": "global",
                "action": "correct",
            },
        )
        assert fb.status_code == 200
        assert fb.json()["stats"]["learned_entries"] >= 1

        snap = client.get("/api/feedback")
        assert snap.status_code == 200
        assert snap.json()["stats"]["events"] >= 1

        page = client.get("/")
        assert page.status_code == 200
        assert "Dictionary" in page.text
        assert "Regurgitation" in page.text
        assert "Feedback learning" in page.text
        assert "Beijing" in page.text or "zh_bj" in page.text
        assert "btn-dialect-listen" in page.text
        assert "Hear Sala" in page.text
        assert "Ask Sala" in page.text
        assert "Replay" in page.text
        assert "Sounds right" in page.text
        assert "Save correction" in page.text
        assert "fillDialectMenu" in page.text
        names = [row["label"] for row in cat.json()["languages"]]
        assert len(names) >= 45
        for label in ("Cambodian — Khmer", "Tagalog — Philippines", "Thai — Thailand", "Vietnamese — Vietnam"):
            assert label in names


def _isolate_sala(monkeypatch, tmp_path):
    monkeypatch.setenv("AOEP_SALA_VALIDATION", str(tmp_path / "sala"))
    from theodore_rag_lab.sala_validation import reset_validation

    reset_validation()


def test_sala_replies_in_the_selected_dialect(tmp_path, monkeypatch):
    _isolate_sala(monkeypatch, tmp_path)
    from theodore_rag_lab.dictionary_lab import sala_reply

    south = sala_reply("What is a right of way?", "us_south", language="en")
    assert south["heard"] == "What is a right of way?"
    folded = south["reply"].lower()
    assert "y'all" in folded
    assert "gonna" not in folded
    assert "ain't" not in folded
    assert "holler" not in folded
    assert south["dialect"]["id"] == "us_south"
    assert south["voice"]["edge_voice"] == "en-US-EmmaNeural"

    khmer = sala_reply("សួស្តី", "km_kh", language="km", voice="km_kh_f")
    assert "សួស្តី" in khmer["reply"]
    assert "អត់បញ្ហា" in khmer["reply"]
    assert khmer["language"] == "km"
    assert khmer["voice"]["id"] == "km_kh_f"

    from_english = sala_reply(
        "Welcome! We will walk through the lesson. Take your time. Nice work.",
        "km_kh",
        language="km",
    )
    assert "Welcome" not in from_english["reply"]
    assert "walk through" not in from_english["reply"].lower()
    assert "អត់បញ្ហា" in from_english["reply"]
    assert "យឺតៗ" in from_english["reply"]
    assert "ល្អណាស់" in from_english["reply"]
    assert "No problem" in from_english["gloss"]

    tagalog = sala_reply("Kumusta", "tl_ph", language="tl")
    assert "Kumusta" in tagalog["reply"] or "Narinig" in tagalog["reply"]
    assert tagalog["voice"]["locale"] == "fil-PH"

    thai = sala_reply("สวัสดี", "th_th", language="th")
    assert "สวัสดี" in thai["reply"]
    vietnamese = sala_reply("Xin chào", "vi_vn", language="vi")
    assert "Xin chào" in vietnamese["reply"]

    canto = sala_reply("你好", "zh_yue_gz", language="zh", voice="zh_yue_gz_f")
    assert canto["language"] == "zh"
    assert "我哋" in canto["reply"] or "唔该" in canto["reply"]
    assert canto["voice"]["id"] == "zh_yue_gz_f"
    assert canto["locale"].lower().startswith("zh-hk")


def test_voice_agent_turn_endpoint(tmp_path, monkeypatch):
    _isolate_sala(monkeypatch, tmp_path)
    with TestClient(app) as client:
        res = client.post(
            "/api/voice-agent/turn",
            json={"text": "Hello class", "dialect": "en_gb", "language": "en", "voice": "en_gb_f"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["heard"] == "Hello class"
    assert body["reply"]
    assert body["dialect"]["id"] == "en_gb"
    assert body["voice"]["id"] == "en_gb_f"
    assert body["from_correction"] is False


def test_saved_correction_is_what_sala_says_next(tmp_path, monkeypatch):
    """A hear-and-correct check replaces the next reply and lands in the training file."""
    _isolate_sala(monkeypatch, tmp_path)
    with TestClient(app) as client:
        first = client.post(
            "/api/voice-agent/turn",
            json={"text": "Explain a right of way", "dialect": "us_south", "language": "en"},
        )
        assert first.status_code == 200
        original = first.json()["reply"]
        saved = client.post(
            "/api/voice-agent/validation",
            json={
                "action": "correct",
                "heard": "Explain a right of way",
                "reply": original,
                "corrected": "A right of way means you may go first.",
                "dialect": "us_south",
                "language": "en",
                "voice": "en_us_f",
            },
        )
        assert saved.status_code == 200
        summary = saved.json()["validation"]
        assert summary["checks"] == 1
        assert summary["corrected"] == 1
        assert summary["passed"] == 0

        again = client.post(
            "/api/voice-agent/turn",
            json={"text": "Explain a right of way", "dialect": "us_south", "language": "en"},
        )
        assert again.json()["reply"] == "A right of way means you may go first."
        assert again.json()["from_correction"] is True

        passed = client.post(
            "/api/voice-agent/validation",
            json={
                "action": "pass",
                "heard": "Explain a right of way",
                "reply": again.json()["reply"],
                "dialect": "us_south",
                "language": "en",
            },
        )
        assert passed.status_code == 200
        assert passed.json()["validation"]["passed"] == 1
        assert passed.json()["validation"]["pass_rate"] == 0.5

        empty = client.post(
            "/api/voice-agent/validation",
            json={"action": "correct", "heard": "x", "reply": "y", "corrected": ""},
        )
        assert empty.status_code == 422

    training = Path(tmp_path / "sala" / "sala_voice_training.jsonl").read_text(encoding="utf-8")
    assert "A right of way means you may go first." in training
    assert '"verdict": "pass"' in training


def test_speaker_preview_plays_dialect_and_sala(monkeypatch):
    """Listen and Hear Sala render audio without calling xAI."""
    seen = {}

    def fake_synthesize(text, *, language="en", style="warm", voice=""):
        seen["text"] = text
        seen["language"] = language
        seen["voice"] = voice
        return b"ID3" + b"x" * 300, "audio/mpeg", "edge-tts"

    monkeypatch.setattr("theodore_rag_lab.main.lab_tts.synthesize", fake_synthesize)
    monkeypatch.setattr(
        "aoep_shared.cosyvoice_tts.cosyvoice_configured",
        lambda *_a, **_k: False,
    )

    with TestClient(app) as client:
        empty = client.post("/api/tts", json={"text": "  "})
        assert empty.status_code == 422

        british = client.post(
            "/api/tts",
            json={"text": "Welcome. Take your time.", "language": "en", "voice": "en_gb_f"},
        )
        assert british.status_code == 200
        assert british.headers["x-tts-engine"] == "edge-tts"
        assert british.headers["x-tts-voice"] == "en_gb_f"
        assert seen["voice"] == "en_gb_f"
        assert british.content.startswith(b"ID3")

        sala = client.post(
            "/api/tts",
            json={"text": "Welcome. Take your time.", "voice": "sala"},
        )
        assert sala.status_code == 200
        assert sala.headers["x-tts-voice"] == "sala"
        assert seen["voice"] == "en_us_f"
        assert "retired" in sala.headers["x-tts-note"]

        khmer_voice = client.post(
            "/api/tts",
            json={"text": "សួស្តី។ អត់បញ្ហាទេ។", "language": "km", "voice": "sala"},
        )
        assert khmer_voice.status_code == 200
        assert seen["language"] == "km"
        assert seen["voice"] == "km_kh_f"
        assert "សួស្តី" in seen["text"]

        status = client.get("/api/tts/status")
        assert status.status_code == 200
        assert status.json()["speaker_preview"] is True


def test_speaker_preview_uses_macos_voice_when_neural_speech_is_down(monkeypatch):
    from aoep_shared.lab_tts import ProviderUnavailable

    def boom(*_args, **_kwargs):
        raise ProviderUnavailable("neural speech is offline")

    monkeypatch.setattr("theodore_rag_lab.main.lab_tts.synthesize", boom)
    monkeypatch.setattr(
        "theodore_rag_lab.main._macos_preview",
        lambda text, voice_id, language: (b"RIFF" + b"x" * 300, "audio/wav", "Daniel"),
    )
    with TestClient(app) as client:
        res = client.post(
            "/api/tts",
            json={"text": "Welcome.", "language": "en", "voice": "en_gb_m"},
        )
    assert res.status_code == 200
    assert res.headers["x-tts-engine"] == "macos-say"
    assert res.headers["x-tts-note"] == "macOS Daniel"
    assert res.content.startswith(b"RIFF")


def test_say_voice_names_follow_the_dialect():
    from theodore_rag_lab.main import _say_voice_name

    assert _say_voice_name("en_gb_f") == "Shelley"
    assert _say_voice_name("en_gb_m") == "Daniel"
    assert _say_voice_name("en_au_f") == "Karen"
    assert _say_voice_name("zh_yue_gz_f") == "Sinji"
    assert _say_voice_name("en_us_f") == "Samantha"
    assert _say_voice_name("en_us_south_f") == "Flo (English (US))"
    assert _say_voice_name("km_kh_f") == ""
    assert _say_voice_name("th_th_f") == "Kanya"
    assert _say_voice_name("vi_vn_f") == "Linh"
