"""RAG lab drop endpoint matches the CLI intake."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_drop_links_and_upload(tmp_path, monkeypatch):
    monkeypatch.setenv("AOEP_TRAINING_INTAKE", str(tmp_path / "intake"))
    monkeypatch.setattr(
        "aoep_shared.training_intake.expand_media_source",
        lambda url, limit: [],
    )
    from theodore_rag_lab.main import app

    client = TestClient(app)
    dropped = client.post(
        "/api/training/drop",
        json={
            "links": [
                "https://www.youtube.com/watch?v=abcdefghijk",
                "https://example.com/news/story",
            ],
            "language": "th",
            "expand_limit": 0,
        },
    )
    assert dropped.status_code == 200, dropped.text
    body = dropped.json()
    assert body["voice_urls"] == 1
    assert body["resource_links"] == 1
    assert body["language"] == "th"

    uploaded = client.post(
        "/api/training/drop/upload",
        data={"links": "", "language": "th", "expand_limit": "0", "fetch_pages": "false"},
        files=[("files", ("lesson.txt", b"Driver's ed uses a turn signal.", "text/plain"))],
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["rag_docs"] >= 1

    page = client.get("/lab")
    assert "Drop training" in page.text
    assert "drop-zone" in page.text
    assert 'id="drop-lang" class="lang-select"' in page.text
    catalog = client.get("/api/dialects")
    assert catalog.status_code == 200
    names = [row["label"] for row in catalog.json()["languages"]]
    assert len(names) >= 45
    assert "Khmer — Cambodia" in names
    assert "Cantonese — Hong Kong" in names
    assert "English — California" in names
    health = client.get("/health")
    assert "training_drop" in health.json()["features"]
