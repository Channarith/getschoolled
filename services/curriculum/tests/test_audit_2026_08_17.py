"""Regression tests for the 2026-08-17 audit (curriculum service).

- HIGH-45 core_skill search filter ignored the explicit catalog flag (only the
          literal "core_skill" tag was seen).
- MED-49  /courses/search silently clamped limit to 200 with no way to detect
          it; the applied limit and true total are now echoed in headers.
- MED-50  /courses/{id}/view was a no-op for non-CatalogStore content (audio,
          live, languages, games) — views are now recorded and feed popularity.
"""

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


# HIGH-45 ------------------------------------------------------------------ #

def test_core_skill_filter_honours_explicit_flag():
    created = client.post("/courses", json={
        "course_id": "audit-core-skill-1",
        "title": "Audit Core Skill",
        "subject": "testing",
        "core_skill": True,
    })
    assert created.status_code in (200, 201), created.text
    # The catalog store assigns its own id; use the returned one.
    cid = created.json()["course_id"]

    hits = client.get("/courses/search",
                      params={"core_skill": "true", "q": "Audit Core Skill"}).json()
    assert any(c["course_id"] == cid for c in hits), (
        "explicit core_skill=True course invisible to the core_skill filter"
    )
    misses = client.get("/courses/search",
                        params={"core_skill": "false", "q": "Audit Core Skill"}).json()
    assert all(c["course_id"] != cid for c in misses)


# MED-49 ------------------------------------------------------------------- #

def test_search_echoes_applied_limit_and_total():
    r = client.get("/courses/search", params={"limit": "500"})
    assert r.status_code == 200
    assert r.headers["X-Limit"] == "200"          # clamp is now detectable
    total = int(r.headers["X-Total-Count"])
    assert total >= len(r.json())


# MED-50 ------------------------------------------------------------------- #

def test_view_recording_for_audio_course_feeds_popularity():
    cid = "audio-401k-and-retirement-basics"
    first = client.post(f"/courses/{cid}/view")
    assert first.status_code == 200, first.text
    second = client.post(f"/courses/{cid}/view")
    assert second.json()["popularity"] == first.json()["popularity"] + 1

    # The recorded views must show up in the index the rails are built from.
    top = client.get("/courses/search", params={"media_format": "audio", "limit": "5"}).json()
    by_id = {c["course_id"]: c for c in top}
    assert by_id[cid]["popularity"] >= 2
