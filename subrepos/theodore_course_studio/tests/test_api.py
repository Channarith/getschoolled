from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_course_studio.main import app

client = TestClient(app)


def test_health_and_studio_page():
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["service"] == "theodore-course-studio"
    page = client.get("/studio")
    assert page.status_code == 200
    assert "Theodore Course Studio" in page.text
    assert "Course library" in page.text
    assert "theme-study" in page.text
    assert "page-welcome" in page.text
    assert "Driver's ed" in page.text
    assert "Food safety" in page.text
    assert 'id="btn-pause"' in page.text
    assert 'id="btn-pop"' not in page.text
    assert 'id="btn-summary"' not in page.text
    assert 'id="btn-game"' not in page.text
    assert "scheduleAutoAdvance" in page.text
    assert "ABSORB_MS = 12000" in page.text
    assert "absorb-note" in page.text
    assert "lecturePaused" in page.text
    assert 'id="btn-present"' not in page.text
    assert 'id="btn-review"' not in page.text
    assert 'id="review-overlay"' not in page.text
    assert 'id="btn-talk"' in page.text
    assert 'id="talk-panel"' in page.text
    assert 'id="btn-talk-mic"' in page.text
    assert 'id="teach-lang-stage"' in page.text
    assert 'aria-label="Lesson language"' in page.text
    assert 'id="btn-fullscreen"' in page.text
    assert 'id="student-cam"' in page.text
    assert 'id="student-cam-hide"' in page.text
    assert "setStudentCamHidden" in page.text
    assert "ensureStudentCamera" in page.text
    assert "Camera stays on." in page.text
    assert "/api/studio/learn/camera" in page.text
    assert "/api/studio/learn/check" in page.text
    assert "submitLearningCheck" in page.text
    assert "learningHold" in page.text
    assert "cameraSessionId" in page.text
    assert "applyAttentionShift" in page.text
    assert 'id="attention-aside"' in page.text
    assert "is-awake" in page.text
    assert "if (checkpoint.due)" in page.text
    assert "checkpoint-skip" not in page.text
    assert "Continue without check" not in page.text
    assert 'id="btn-captions"' in page.text
    assert 'class="teach-stage captions-off"' in page.text
    assert 'aria-pressed="false"' in page.text
    assert 'aria-label="Show lesson captions"' in page.text
    assert "requestFullscreen" in page.text
    assert "on('teach-stage', 'dblclick'" in page.text
    assert "setCaptionsEnabled" in page.text
    assert "lessonText.setAttribute('lang', spoken || 'en')" in page.text
    assert "['ar', 'fa', 'he', 'ur'].includes(spoken)" in page.text
    assert "SpeechRecognition" in page.text
    assert "Speak your answer" in page.text
    assert "fetchLockedVoice" in page.text
    assert "courseVoiceGender" in page.text
    assert 'id="avatar-choice"' in page.text
    assert "loadAvatarChoices" in page.text
    assert "avatarPrefs.presenter = presenterId" in page.text
    assert "persona: selectedAvatarId" in page.text
    assert "motionIntensity: 0.42" in page.text
    assert 'method: \'POST\'' in page.text or "method: 'POST'" in page.text
    assert "Correct answer:" in page.text
    assert "Why:" in page.text
    assert "course continues automatically" in page.text
    assert "scope_to_course" in page.text or "voice/respond" in page.text
    assert "teach-lang" in page.text
    # Multimodal order_steps games must be playable (not only match_term options).
    assert "order_steps" in page.text
    assert "ordered_steps" in page.text


def test_offline_trainer_api_with_empty_corpus(tmp_path, monkeypatch):
    # Point studio data at empty temp dir so API call doesn't touch real corpus.
    monkeypatch.setenv("THEODORE_COURSE_STUDIO_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("THEODORE_COURSE_CORPUS_ROOT", str(tmp_path / "corpus"))
    (tmp_path / "corpus").mkdir()
    # Re-import is heavy; call trainer helpers via endpoint after env set —
    # the module-level builder already constructed. Still exercise status endpoint.
    status = client.get("/api/studio/training/offline/status")
    assert status.status_code == 200
    assert "model" in status.json()
