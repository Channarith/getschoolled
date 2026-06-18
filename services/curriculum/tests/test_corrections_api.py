"""Corrections review API: submit, bulk upload, list, approve/reject."""

import json

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def test_submit_and_get_correction():
    r = client.post("/corrections", json={
        "target_kind": "deck", "target_id": "d1", "locator": "0",
        "corrected": "Plants release oxygen.", "rationale": "was wrong", "author": "ada"})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert r.json()["status"] == "submitted"
    assert client.get(f"/corrections/{cid}").json()["corrected"] == "Plants release oxygen."


def test_bulk_upload_jsonl():
    blob = "\n".join([
        json.dumps({"target_kind": "model", "locator": "what gas?", "corrected": "oxygen"}),
        json.dumps({"target_kind": "deck", "target_id": "d2", "corrected": "fixed"}),
    ])
    r = client.post("/corrections/bulk",
                    files={"file": ("c.jsonl", blob, "application/jsonl")},
                    data={"fmt": "jsonl"})
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 2


def test_approve_and_reject_flow():
    cid = client.post("/corrections", json={"corrected": "x"}).json()["id"]
    assert client.post(f"/corrections/{cid}/approve").json()["status"] == "approved"
    assert client.post(f"/corrections/{cid}/reject").json()["status"] == "rejected"


def test_list_filter_by_status():
    a = client.post("/corrections", json={"corrected": "a"}).json()["id"]
    client.post(f"/corrections/{a}/approve")
    approved = client.get("/corrections", params={"status": "approved"}).json()
    assert any(c["id"] == a for c in approved)
    assert all(c["status"] == "approved" for c in approved)


def test_bulk_bad_format_422():
    r = client.post("/corrections/bulk",
                    files={"file": ("c.xml", "x", "text/xml")}, data={"fmt": "xml"})
    assert r.status_code == 422


def test_unknown_correction_404():
    assert client.get("/corrections/nope").status_code == 404
