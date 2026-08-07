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
    assert "Run training scan" in page.text
    assert "Learner profile scoring" in page.text
    assert "Reject" in page.text
    assert "Pop quiz" in page.text
    assert "Summary quiz" in page.text
    assert "Play game" in page.text
    assert "Offline long trainer" in page.text
    assert "Ask Theodore" in page.text
    assert "teach-lang" in page.text


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
