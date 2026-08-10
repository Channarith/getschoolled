from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient

from theodore_audio_translation_lab.main import app
from theodore_audio_translation_lab.models import AudienceRole, SessionConfig, TranscriptInput
from theodore_audio_translation_lab.providers import TranslationEngine
from theodore_audio_translation_lab.sessions import TranslationHub


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, payload):
        self.messages.append(payload)


async def _hub_scenario():
    hub = TranslationHub(TranslationEngine())
    await hub.create(
        SessionConfig(session_id="class-1", source_language="en", target_languages=["es"])
    )
    teacher = FakeWebSocket()
    customer = FakeWebSocket()
    await hub.register(
        "class-1", teacher, role=AudienceRole.TEACHER, target_language="es", participant_id="t1"
    )
    await hub.register(
        "class-1", customer, role=AudienceRole.CUSTOMER, target_language="km", participant_id="c1"
    )
    events = await hub.process_transcript(
        "class-1",
        TranscriptInput(text="I need help", source_language="en", speaker_id="learner"),
    )
    return hub, teacher, customer, events


def test_hub_delivers_each_viewer_language():
    hub, teacher, customer, events = asyncio.run(_hub_scenario())
    by_lang = {e.target_language: e for e in events}
    assert by_lang["es"].translated_text == "Necesito ayuda"
    assert by_lang["km"].translated_text == "ខ្ញុំត្រូវការជំនួយ"
    teacher_events = [m for m in teacher.messages if m.get("type") == "translation"][-1]["events"]
    customer_events = [m for m in customer.messages if m.get("type") == "translation"][-1]["events"]
    assert {e["target_language"] for e in teacher_events} == {"es"}
    assert {e["target_language"] for e in customer_events} == {"km"}
    snapshot = asyncio.run(hub.snapshot("class-1"))
    assert snapshot is not None
    assert snapshot.connected == {"teacher": 1, "customer": 1}
    assert len(snapshot.history) == 2


def test_interim_is_not_translated_by_default():
    async def scenario():
        hub = TranslationHub(TranslationEngine())
        await hub.create(SessionConfig(session_id="i", source_language="en", target_languages=["es"]))
        return await hub.process_transcript(
            "i", TranscriptInput(text="hel", source_language="en", is_final=False)
        )

    events = asyncio.run(scenario())
    assert len(events) == 1
    assert events[0].translation_provider == "interim-source"
    assert events[0].translated_text == "hel"
    assert events[0].is_final is False


client = TestClient(app)


def unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_health_languages_and_lab_page():
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["languages"] == 27
    assert "not persisted" in health.json()["privacy"]
    langs = client.get("/api/languages")
    assert langs.status_code == 200
    assert langs.json()["count"] == 27
    assert any(row["code"] == "km" for row in langs.json()["languages"])
    page = client.get("/lab")
    assert page.status_code == 200
    for phrase in (
        "Theodore Audio Translation Lab",
        "Start webcam + translation",
        "Teacher / Theodore / customer feed",
        "Server Whisper chunks",
        "Speak translated audio",
        "Auto-detect needs server Whisper",
        "change anytime",
    ):
        assert phrase in page.text


def test_session_text_translation_api():
    sid = unique("api")
    made = client.post(
        "/api/sessions",
        json={"session_id": sid, "source_language": "en", "target_languages": ["zh", "km"]},
    )
    assert made.status_code == 200
    translated = client.post(
        f"/api/sessions/{sid}/transcript",
        json={"text": "I need help", "source_language": "en", "is_final": True},
    )
    assert translated.status_code == 200
    by_lang = {e["target_language"]: e for e in translated.json()["events"]}
    assert by_lang["zh"]["translated_text"] == "我需要帮助"
    assert by_lang["km"]["translated_text"] == "ខ្ញុំត្រូវការជំនួយ"
    snap = client.get(f"/api/sessions/{sid}")
    assert snap.status_code == 200
    assert len(snap.json()["history"]) == 2


def test_audio_endpoint_is_honest_when_whisper_missing(monkeypatch):
    # The app-level ASR object is unconfigured in tests: return 503, never a fake transcript.
    sid = unique("audio")
    response = client.post(
        f"/api/sessions/{sid}/audio",
        data={"source_language": "en", "speaker_id": "learner"},
        files={"audio": ("chunk.webm", b"not-real-audio", "audio/webm")},
    )
    assert response.status_code == 503
    assert "ASR_BASE_URL" in response.json()["detail"]


def test_websocket_realtime_delivery():
    sid = unique("ws")
    client.post(
        "/api/sessions",
        json={"session_id": sid, "source_language": "en", "target_languages": ["es"]},
    )
    with client.websocket_connect(
        f"/ws/sessions/{sid}?role=teacher&target=es&source=en&participant=teacher"
    ) as ws:
        connected = ws.receive_json()
        assert connected["type"] == "connected"
        presence = ws.receive_json()
        assert presence["type"] == "presence"
        # Submit through HTTP as if browser ASR finalized a phrase; viewer gets WS event.
        response = client.post(
            f"/api/sessions/{sid}/transcript",
            json={"text": "Hello", "source_language": "en", "is_final": True},
        )
        assert response.status_code == 200
        packet = ws.receive_json()
        assert packet["type"] == "translation"
        event = packet["events"][0]
        assert event["target_language"] == "es"
        assert event["translated_text"] == "Hola"


def test_source_language_can_toggle_while_session_is_live():
    sid = unique("toggle")
    made = client.post(
        "/api/sessions",
        json={"session_id": sid, "source_language": "en", "target_languages": ["es"]},
    )
    assert made.status_code == 200
    switched = client.patch(f"/api/sessions/{sid}", json={"source_language": "zh"})
    assert switched.status_code == 200
    assert switched.json()["config"]["source_language"] == "zh"
    auto = client.patch(f"/api/sessions/{sid}", json={"source_language": "auto"})
    assert auto.status_code == 200
    assert auto.json()["config"]["source_language"] == "auto"


def test_auto_audio_is_rejected_when_server_whisper_is_missing():
    sid = unique("auto-audio")
    response = client.post(
        f"/api/sessions/{sid}/audio",
        data={"source_language": "auto", "speaker_id": "learner"},
        files={"audio": ("chunk.webm", b"not-real-audio", "audio/webm")},
    )
    assert response.status_code == 503
    assert "Auto-detect requires server Whisper" in response.json()["detail"]


def test_connected_viewers_are_notified_of_input_toggle():
    from theodore_audio_translation_lab.models import SessionUpdate

    async def scenario():
        hub = TranslationHub(TranslationEngine())
        await hub.create(
            SessionConfig(session_id="cfg-live", source_language="en", target_languages=["es"])
        )
        viewer = FakeWebSocket()
        await hub.register(
            "cfg-live",
            viewer,
            role=AudienceRole.THEODORE,
            target_language="es",
            participant_id="theodore",
        )
        snap = await hub.configure(
            "cfg-live", SessionUpdate(source_language="auto")
        )
        return viewer, snap

    viewer, snap = asyncio.run(scenario())
    assert snap.config.source_language == "auto"
    config_packets = [m for m in viewer.messages if m.get("type") == "config"]
    assert config_packets[-1]["config"]["source_language"] == "auto"
