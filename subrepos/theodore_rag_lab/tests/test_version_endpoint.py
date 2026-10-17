"""GET /version reports the repo VERSION file."""

from pathlib import Path

from fastapi.testclient import TestClient

from theodore_rag_lab.main import app

ROOT = Path(__file__).resolve().parents[3]


def test_version_matches_repo_file():
    expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    body = TestClient(app).get("/version").json()
    assert body["service"] == "theodore-rag-lab"
    assert body["version"] == expected
