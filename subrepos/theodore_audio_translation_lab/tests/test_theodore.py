from __future__ import annotations

import asyncio
import json
from io import BytesIO

import pytest

from theodore_audio_translation_lab.languages import SUPPORTED_LANGUAGES
from theodore_audio_translation_lab.models import (
    AudienceRole,
    SessionConfig,
    TheodoreMode,
    TheodoreReplyRequest,
    TranscriptInput,
    TranslationResult,
)
from theodore_audio_translation_lab.providers import TranslationEngine
from theodore_audio_translation_lab.sessions import TranslationHub
from theodore_audio_translation_lab.theodore import TheodoreReplyEngine


class _Resp:
    def __init__(self, payload):
        self.buf = BytesIO(json.dumps(payload).encode())

    def read(self):
        return self.buf.read()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeTranslator:
    def translate(self, text, source, target):
        return TranslationResult(
            text=f"[{target}] {text}",
            source_language=source,
            target_language=target,
            provider="fake-nllb",
            translated=True,
        )


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, payload):
        self.messages.append(payload)


@pytest.fixture(autouse=True)
def clear_xai(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)


def test_xai_theodore_replies_in_requested_language(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    captured = {}

    def fake(req, timeout=None):
        captured["auth"] = req.headers["Authorization"]
        captured["body"] = json.loads(req.data.decode())
        return _Resp(
            {"choices": [{"message": {"content": "Vamos a aprender juntos. ¿Cuál es tu ejemplo?"}}]}
        )

    monkeypatch.setattr("urllib.request.urlopen", fake)
    engine = TheodoreReplyEngine(TranslationEngine())
    reply = engine.reply(
        session_id="s",
        sequence=1,
        learner_text="I don't understand fractions",
        learner_language="en",
        reply_language="es",
        mode=TheodoreMode.TEACH,
    )
    assert reply.language == "es"
    assert reply.provider == "xai-theodore"
    assert "aprender" in reply.text
    assert captured["auth"] == "Bearer test-key"
    system = captured["body"]["messages"][0]["content"]
    assert "Spanish" in system
    assert "Teach one useful idea" in system


def test_fallback_translation_can_cover_all_27_languages():
    engine = TheodoreReplyEngine(FakeTranslator())
    for target in SUPPORTED_LANGUAGES:
        reply = engine.reply(
            session_id="all",
            sequence=1,
            learner_text="Help me",
            learner_language="en",
            reply_language=target,
            mode=TheodoreMode.COACH,
        )
        assert reply.language == target
        if target == "en":
            assert reply.provider == "english-teaching-fallback"
        else:
            assert reply.provider == "translated-teaching-fallback:fake-nllb"
            assert reply.text.startswith(f"[{target}]")


def test_unavailable_target_language_falls_back_to_english_honestly():
    engine = TheodoreReplyEngine(TranslationEngine())
    reply = engine.reply(
        session_id="s",
        sequence=1,
        learner_text="Help me",
        learner_language="km",
        reply_language="fr",
        mode=TheodoreMode.CLARIFY,
    )
    assert reply.language == "en"
    assert reply.provider == "english-teaching-fallback"
    assert "replying in English" in reply.warning


def test_auto_reply_broadcasts_after_browser_end_of_turn():
    async def scenario():
        translator = TranslationEngine()
        hub = TranslationHub(
            translator=translator,
            theodore=TheodoreReplyEngine(FakeTranslator()),
        )
        await hub.create(
            SessionConfig(
                session_id="auto-reply",
                source_language="en",
                target_languages=["es"],
                theodore_auto_reply=True,
                theodore_language="es",
                theodore_mode="teach",
            )
        )
        ws = FakeWebSocket()
        await hub.register(
            "auto-reply",
            ws,
            role=AudienceRole.SPEAKER,
            target_language="es",
            participant_id="learner",
        )
        await hub.process_transcript(
            "auto-reply",
            TranscriptInput(
                text="What is a habitat?",
                source_language="en",
                is_final=True,
                end_of_turn=True,
            ),
        )
        return hub, ws

    hub, ws = asyncio.run(scenario())
    packets = [m for m in ws.messages if m.get("type") == "theodore_reply"]
    assert len(packets) == 1
    assert packets[0]["reply"]["language"] == "es"
    assert packets[0]["reply"]["text"].startswith("[es]")
    snapshot = asyncio.run(hub.snapshot("auto-reply"))
    assert snapshot is not None
    assert len(snapshot.theodore_replies) == 1


def test_server_chunk_does_not_interrupt_every_window():
    async def scenario():
        hub = TranslationHub(
            translator=TranslationEngine(),
            theodore=TheodoreReplyEngine(FakeTranslator()),
        )
        await hub.create(
            SessionConfig(
                session_id="chunks",
                source_language="en",
                target_languages=["es"],
                theodore_auto_reply=True,
            )
        )
        await hub.process_transcript(
            "chunks",
            TranscriptInput(
                text="This is only one short ASR window",
                source_language="en",
                is_final=True,
                end_of_turn=False,
                asr_provider="whisper",
            ),
        )
        return await hub.snapshot("chunks")

    snapshot = asyncio.run(scenario())
    assert snapshot is not None
    assert snapshot.theodore_replies == []
