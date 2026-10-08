"""Lesson playback follows a manifest clip, and Talk stays an on-demand Q&A."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from theodore_course_studio.generate import CourseBuilder
from theodore_course_studio.studio_page import STUDIO_JS, render_studio_page
from theodore_course_studio.teach import TeachEngine
from theodore_course_studio.types import CategoryId, CourseSlide, StudioCourse
from theodore_course_studio.voice_agent import VoiceTurn


def _course(builder: CourseBuilder, course_id: str = "gapless-mini") -> StudioCourse:
    course = StudioCourse(
        course_id=course_id,
        title="Gapless Mini",
        category=CategoryId.OTHER,
        slides=[
            CourseSlide(
                index=0,
                slide_key=f"{course_id}.alpha",
                title="Alpha",
                body="Alpha is the first point.",
                narration="Alpha is the first point.",
            ),
            CourseSlide(
                index=1,
                slide_key=f"{course_id}.beta",
                title="Beta",
                body="Beta is the second point.",
                narration="Beta is the second point.",
            ),
        ],
        status="ready",
    )
    builder.save_course(course)
    return course


def _slice(source: str, start: str, end: str) -> str:
    body = source.split(start, 1)[1]
    return body.split(end, 1)[0]


def test_playback_and_talk_markup_contracts():
    page = render_studio_page()
    assert STUDIO_JS in page
    assert 'id="btn-talk"' in page
    assert 'id="talk-panel"' in page
    assert 'id="talk-reply"' in page
    assert 'id="btn-talk-close"' in page
    assert 'id="teach-narr"' in page
    js = STUDIO_JS
    assert "ABSORB_MS = 12000" in js
    assert "scheduleAutoAdvance(narrationDwellMs(spoken))" in js
    assert "scheduleAutoAdvance(narrationDwellMs(spoken) + ABSORB_MS)" not in js
    assert "function manifestClip" in js
    assert "ttsMeta.audio_url" in js
    assert "ttsMeta.duration_ms" in js
    assert "next_audio_url" in js
    assert "function preloadNextSlideAudio" in js
    assert "function armDurationWatchdog" in js
    assert "function renderVisualTimeline" in js
    assert "function syncVisualTimeline" in js
    assert "audio.currentTime" in js
    assert "if (!holdLesson) syncVisualTimeline" in js
    assert "presentActivityCheckpoint" in js
    assert "summaryQuizInteractive" in js
    synced_summary = _slice(
        js, "async function summaryQuizInteractive", "async function playGame"
    )
    assert "speakText(spokenQuestion" in synced_summary
    assert "data-sync-choice" in synced_summary
    variety = _slice(js, "function pickLearnVariety", "function pctLabel")
    assert "Math.random" not in variety
    assert "'quiz'" not in variety
    assert "'game'" not in variety
    assert "WATCHDOG_GRACE_MS" in js
    assert "attempt < 1" in js
    assert "fetch('/api/studio/tts'" in js
    assert "kind === 'talk'" in js
    assert js.count("revokeObjectURL") == 1
    release = _slice(js, "function releaseAudioUrl", "function detachServerAudio")
    assert "isBlobUrl" in release
    assert "blob:" in js
    speak = _slice(js, "function speakText", "function fetchLockedVoice")
    assert "holdLesson ? null : manifestClip" in speak
    assert "playManifest" in speak
    assert "playOnDemand" in speak
    assert "playDevice" in speak
    assert "gen !== speechGen" in speak
    assert "finishUtterance" in speak
    open_talk = _slice(js, "function openTalk()", "function closeTalk()")
    ask = _slice(js, "async function askTheodore()", "function clearAutoAdvance()")
    question = _slice(js, "function speakQuestion()", "async function askTheodore()")
    for body in (open_talk, ask, question):
        assert "lessonTurnLoaded()" in body
        assert "if (!teachSession)" not in body
    close = _slice(js, "function closeTalk()", "function speechCtor()")
    assert "readCurrentAloud" not in close
    assert "slideCaptionText()" in close
    assert "scheduleAutoAdvance(ABSORB_MS)" in close
    assert "restoreLessonAvatar" in ask
    assert "setState('thinking')" in ask
    assert "data.avatar" in ask
    assert "'talk'" in ask
    render = _slice(js, "function renderTeach(payload)", "function readCurrentAloud()")
    assert "teachEpoch" in render
    assert "talk-reply" in render
    assert "stopStudentMic()" in render
    mic = _slice(js, "function stopStudentMic()", "async function ensureMic()")
    assert "rec.abort()" in mic
    assert "releaseMicStream()" in mic


def test_live_voice_moves_the_lesson_screen():
    assert "theodore-live-audio-action" in STUDIO_JS
    assert "applyLiveAudioAction" in STUDIO_JS
    assert "armSpokenActivity" in STUDIO_JS
    assert "applySpokenActivity" in STUDIO_JS
    assert "cycleLessonAnimation" in STUDIO_JS
    assert "showSpokenExample" in STUDIO_JS
    assert "event.detail.command" in STUDIO_JS
    assert "data.dynamic" in STUDIO_JS
    assert "showQuestionSources" in STUDIO_JS


def test_studio_script_parses():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    page = render_studio_page()
    extracted = page.rsplit("<script>", 1)[-1].split("</script>", 1)[0]
    assert extracted.strip() == STUDIO_JS.strip()
    result = subprocess.run(
        [node, "--input-type=module", "--check"],
        input=extracted,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_voice_respond_is_qa_payload_not_full_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "theodore_course_studio.tts_client.tts_status",
        lambda timeout_s=1.5: {
            "available": False,
            "engine": "device",
            "speech_base_url": "http://127.0.0.1:8002",
            "offline_fallback": "device",
        },
    )
    builder = CourseBuilder(data_dir=tmp_path / "data")
    engine = TeachEngine(builder)
    _course(builder)
    engine.start(
        session_id="gapless-engine",
        course_id="gapless-mini",
        use_voice_agent=False,
        language="en",
    )
    session = engine._sessions["gapless-engine"]
    history_before = len(session.history)
    path_before = session.path_pos

    def fail_turn(*_args, **_kwargs):
        raise AssertionError("voice_respond must not build the full lesson payload")

    monkeypatch.setattr(engine, "_turn_payload", fail_turn)

    def fake_respond(**kwargs):
        assert kwargs["scope_to_course"] is True
        assert "Alpha" in kwargs["lesson_context"]
        return VoiceTurn(
            provider="local-fallback",
            message="Alpha is the first point on this page.",
            language_code="en",
            fallback_used=True,
        )

    monkeypatch.setattr(engine._voice, "respond", fake_respond)
    payload = engine.voice_respond("gapless-engine", "What is alpha?")
    assert session.path_pos == path_before
    assert len(session.history) == history_before
    assert "turn" not in payload
    assert "checkpoint" not in payload
    assert "progress" not in payload
    assert "path" not in payload
    assert payload["slide_index"] == 0
    assert payload["spoken_language"] == "en"
    assert payload["voice"]["message"].startswith("Alpha")
    assert payload["avatar"]["state"] == "presenting"
    assert payload["avatar"]["duration_s"] > 0
    assert payload["tts"]["language"] == "en"
    assert payload["tts"]["voice_gender"] == "female"
    assert "audio_url" not in payload["tts"]
    assert "duration_ms" not in payload["tts"]


def test_automatic_activity_is_only_due_at_lesson_checkpoint(tmp_path):
    builder = CourseBuilder(data_dir=tmp_path / "data")
    engine = TeachEngine(builder)
    _course(builder)
    first = engine.start(
        session_id="checkpoint-engine",
        course_id="gapless-mini",
        use_voice_agent=False,
        language="en",
    )
    assert first["activity_checkpoint"]["due"] is False
    assert first["activity_checkpoint"]["activity"] == "reflection"
    second = engine.advance("checkpoint-engine")
    assert second["activity_checkpoint"]["due"] is True
    assert second["activity_checkpoint"]["scope"] == "lesson"
    assert second["activity_checkpoint"]["activity"] == "game"


def test_teach_payload_uses_manifest_clip_and_preloads_next(tmp_path, monkeypatch):
    from theodore_course_studio.narration_runtime import clear_manifest_cache

    builder = CourseBuilder(data_dir=tmp_path / "data")
    engine = TeachEngine(builder)
    _course(builder)
    records = []
    for key in ("gapless-mini.alpha", "gapless-mini.beta"):
        records.append(
            {
                "version": 2,
                "slide_key": key,
                "language": "en",
                "gender": "female",
                "audio_url": f"https://cdn.example/{key}.mp3",
                "duration": 2.0,
                "segments": [
                    {
                        "index": 0,
                        "text": "A sentence.",
                        "start_s": 0.0,
                        "duration_s": 2.0,
                    }
                ],
            }
        )
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"version": 2, "complete": True, "records": records}),
        encoding="utf-8",
    )
    monkeypatch.setenv("COURSE_AUDIO_MANIFEST", str(path))
    clear_manifest_cache()
    payload = engine.start(
        session_id="manifest-engine",
        course_id="gapless-mini",
        use_voice_agent=False,
        language="en",
    )
    assert payload["tts"]["audio_url"].endswith("alpha.mp3")
    assert payload["tts"]["duration_ms"] == 2000
    assert payload["tts"]["next_audio_url"].endswith("beta.mp3")
    assert payload["tts"]["segments"][0]["start_s"] == 0


def test_voice_respond_api(monkeypatch):
    monkeypatch.setattr(
        "theodore_course_studio.tts_client.tts_status",
        lambda timeout_s=1.5: {
            "available": False,
            "engine": "device",
            "speech_base_url": "http://127.0.0.1:8002",
            "offline_fallback": "device",
        },
    )
    from fastapi.testclient import TestClient

    from theodore_course_studio.main import _builder, _teach, app

    course_path = _builder._courses_dir / "gapless-api-mini.course.json"
    knowledge_path = _teach._knowledge._path("gapless-learner", "gapless-api-mini")
    course_path.unlink(missing_ok=True)
    knowledge_path.unlink(missing_ok=True)
    try:
        _course(_builder, "gapless-api-mini")

        def fake_respond(**_kwargs):
            return VoiceTurn(
                provider="local-fallback",
                message="Beta follows alpha.",
                language_code="en",
                fallback_used=True,
            )

        monkeypatch.setattr(_teach._voice, "respond", fake_respond)
        client = TestClient(app)
        started = client.post(
            "/api/studio/teach/start",
            json={
                "session_id": "gapless-api",
                "course_id": "gapless-api-mini",
                "learner_id": "gapless-learner",
                "use_voice_agent": False,
                "language": "en",
            },
        )
        assert started.status_code == 200, started.text
        history_before = len(_teach._sessions["gapless-api"].history)

        def fail_turn(*_args, **_kwargs):
            raise AssertionError("voice_respond must not build the full lesson payload")

        monkeypatch.setattr(_teach, "_turn_payload", fail_turn)
        replied = client.post(
            "/api/studio/teach/voice/respond",
            json={"session_id": "gapless-api", "message": "What comes after alpha?"},
        )
        assert replied.status_code == 200, replied.text
        body = replied.json()
        assert body["voice"]["message"] == "Beta follows alpha."
        assert body["avatar"]["state"] == "presenting"
        assert body["tts"]["language"] == "en"
        assert "audio_url" not in body["tts"]
        assert "turn" not in body
        assert "checkpoint" not in body
        assert len(_teach._sessions["gapless-api"].history) == history_before
    finally:
        course_path.unlink(missing_ok=True)
        knowledge_path.unlink(missing_ok=True)
        _teach._sessions.pop("gapless-api", None)
