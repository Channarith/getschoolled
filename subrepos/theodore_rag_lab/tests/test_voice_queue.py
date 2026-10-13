"""RAG lab voice queue uses the same runner as the CLI."""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient


def _prepare(tmp_path: Path, monkeypatch) -> None:
    urls = tmp_path / "urls"
    pool = urls / "cosyvoice_es"
    pool.mkdir(parents=True)
    (pool / "lesson.txt").write_text(
        "https://www.youtube.com/watch?v=aaaaaaaaaaa\n",
        encoding="utf-8",
    )
    (pool / "second.txt").write_text(
        "https://www.youtube.com/watch?v=bbbbbbbbbbb\n",
        encoding="utf-8",
    )
    catalog = urls / "channels.json"
    catalog.write_text(
        json.dumps(
            {"pools": [{"pool_id": "es", "whisper": "es", "label": "Spanish"}]}
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AOEP_VOICE_CATALOG", str(catalog))
    monkeypatch.setenv("AOEP_VOICE_URLS_ROOT", str(urls))
    monkeypatch.setenv("AOEP_VOICE_OUTPUT", str(tmp_path / "output"))
    monkeypatch.setenv("AOEP_REPO_ROOT", str(tmp_path))
    from theodore_rag_lab.voice_queue import reset_voice_queue

    reset_voice_queue()


def test_voice_queue_start_status_and_stop(tmp_path, monkeypatch):
    _prepare(tmp_path, monkeypatch)
    seen: list[str] = []

    def fake(job, max_urls, repo, script):
        seen.append(job.slug)
        return {
            "pool_id": job.pool_id,
            "slug": job.slug,
            "videos": job.video_count,
            "returncode": 0,
            "elapsed_s": 0.1,
        }

    monkeypatch.setattr(
        "aoep_shared.cosyvoice_ingest.queue.ingest_channel",
        fake,
    )
    from theodore_rag_lab.main import app

    client = TestClient(app)
    health = client.get("/health")
    assert "voice_queue" in health.json()["features"]

    catalog = client.get("/api/voice/queue")
    assert catalog.status_code == 200
    pools = {item["pool_id"]: item for item in catalog.json()["pools"]}
    assert pools["es"]["channels"] == 2
    assert pools["es"]["label"] == "Spanish"

    started = client.post(
        "/api/voice/queue/start",
        json={"pools": ["es"], "workers": 1, "max_urls": 1, "max_channels": 1},
    )
    assert started.status_code == 200, started.text

    deadline = time.time() + 5
    status = {}
    while time.time() < deadline:
        status = client.get("/api/voice/queue").json()["queue"]
        if not status.get("running") and status.get("done"):
            break
        time.sleep(0.05)
    assert status.get("done") == 1
    assert seen == ["lesson"]

    page = client.get("/lab")
    assert page.status_code == 200
    assert "Voice training" in page.text
    assert "btn-vq-start" in page.text
    assert "Check all" in page.text
    assert "A sample" in page.text
    assert "vq-pools" in page.text

    stopped = client.post("/api/voice/queue/stop")
    assert stopped.status_code == 200
