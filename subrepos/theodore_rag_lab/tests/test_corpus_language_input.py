"""The corpus language becomes part of file names: only a plain tag may pass."""

from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_rag_lab.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_unsafe_language_is_rejected_with_422():
    for bad in ("x\x00y", "../etc", "a/b", "", "héllo"):
        r = client.post("/api/corpus/train-update", json={"language": bad})
        assert r.status_code == 422, repr(bad)


def test_plain_language_tags_are_accepted():
    for good in ("en", "km", "zh-Hans", "pt-BR"):
        r = client.post("/api/corpus/train-update", json={"language": good})
        assert r.status_code == 200, good
