"""Staff translation review: access, no duplicate work, progress."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from aoep_shared import translation_review as tr
from fastapi.testclient import TestClient
from identity.main import app
from identity.store import AccountStore

LIB = Path(__file__).resolve().parents[3] / "data" / "course_translations"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _library(monkeypatch):
    monkeypatch.setenv("AOEP_COURSE_TRANSLATION_DIR", str(LIB))
    monkeypatch.setenv("TRANSLATION_REVIEWER_EMAILS", "reviewer@example.com")
    tr._machine_for_language.cache_clear()
    app.state.review_store = tr.ReviewStore(tr.MemoryKV())
    app.state.accounts = AccountStore()
    app.state.accounts.seed_admin("admin@salareen.com", "88888888", username="admin")


def _token(email: str, password: str) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _member(email: str) -> dict:
    app.state.accounts.create(email, "Passw0rd!x")
    return _token(email, "Passw0rd!x")


def test_hidden_from_ordinary_members_and_anonymous():
    assert client.get("/admin/translation-review/overview").status_code in (401, 403)
    member = _member("someone@example.com")
    assert client.get("/admin/translation-review/overview", headers=member).status_code == 403


def test_listed_reviewer_and_admin_can_open_it():
    admin = _token("admin@salareen.com", "88888888")
    assert client.get("/admin/translation-review/overview", headers=admin).status_code == 200
    rev = _member("reviewer@example.com")
    assert client.get("/admin/translation-review/overview", headers=rev).status_code == 200


def test_two_reviewers_never_get_the_same_unit_and_a_saved_review_is_final():
    admin = _token("admin@salareen.com", "88888888")
    rev = _member("reviewer@example.com")
    first = client.get("/admin/translation-review/next", params={"lang": "fr"}, headers=admin).json()["unit"]
    second = client.get("/admin/translation-review/next", params={"lang": "fr"}, headers=rev).json()["unit"]
    assert first and second and first["key"] != second["key"]
    assert first["pages"] >= second["pages"]  # most-reused first

    body = {"lang": "fr", "key": first["key"], "verdict": "correct"}
    assert client.post("/admin/translation-review/submit", json=body, headers=admin).status_code == 200
    again = client.post("/admin/translation-review/submit", json=body, headers=rev)
    assert again.status_code == 409 and "admin@salareen.com" in again.json()["detail"]


def test_submitted_units_leave_the_queue_and_progress_counts_pages():
    admin = _token("admin@salareen.com", "88888888")
    before = client.get("/admin/translation-review/next", params={"lang": "fr"}, headers=admin).json()
    unit = before["unit"]
    done = client.post(
        "/admin/translation-review/submit",
        json={"lang": "fr", "key": unit["key"], "verdict": "better", "text": "Texte meilleur."},
        headers=admin,
    ).json()["stats"]
    assert done["units_reviewed"] == 1
    assert done["pages_covered"] == unit["pages"] > 0
    assert done["units_remaining"] == before["stats"]["units_total"] - 1
    nxt = client.get("/admin/translation-review/next", params={"lang": "fr"}, headers=admin).json()["unit"]
    assert nxt["key"] != unit["key"]


def test_a_fix_needs_text_and_a_wrong_source_is_flagged_without_training_text():
    admin = _token("admin@salareen.com", "88888888")
    unit = client.get("/admin/translation-review/next", params={"lang": "fr"}, headers=admin).json()["unit"]
    bad = client.post("/admin/translation-review/submit",
                      json={"lang": "fr", "key": unit["key"], "verdict": "small_fix"}, headers=admin)
    assert bad.status_code == 400
    ok = client.post("/admin/translation-review/submit",
                     json={"lang": "fr", "key": unit["key"], "verdict": "source_wrong", "note": "off topic"},
                     headers=admin)
    assert ok.status_code == 200
    assert client.get("/admin/translation-review/export", params={"lang": "fr"}, headers=admin).json()["pairs"] == []


def test_export_has_the_final_text_for_correct_and_typed_reviews():
    admin = _token("admin@salareen.com", "88888888")
    a = client.get("/admin/translation-review/next", params={"lang": "es"}, headers=admin).json()["unit"]
    client.post("/admin/translation-review/submit", json={"lang": "es", "key": a["key"], "verdict": "correct"}, headers=admin)
    b = client.get("/admin/translation-review/next", params={"lang": "es"}, headers=admin).json()["unit"]
    client.post("/admin/translation-review/submit",
                json={"lang": "es", "key": b["key"], "verdict": "better", "text": "Mejor texto."}, headers=admin)
    pairs = client.get("/admin/translation-review/export", params={"lang": "es"}, headers=admin).json()["pairs"]
    assert {p["verdict"] for p in pairs} == {"correct", "better"}
    assert next(p for p in pairs if p["verdict"] == "better")["target"]["text"] == "Mejor texto."
