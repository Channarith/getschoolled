"""The assemble endpoint must never write to a client-chosen path, and must not 500."""

from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_llm_lab.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_path_traversal_and_absolute_out_are_rejected():
    for bad in ("../x.jsonl", "/etc/passwd", "a/b.jsonl", "..", "x\x00y"):
        r = client.post("/api/llm/assemble", json={"out": bad})
        assert r.status_code == 400, bad


def test_plain_file_name_is_written_under_the_output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_LAB_OUT_DIR", str(tmp_path))
    r = client.post("/api/llm/assemble", json={"out": "train.jsonl"})
    assert r.status_code == 200
    assert r.json()["out"] == "train.jsonl"
    assert (tmp_path / "train.jsonl").exists()
