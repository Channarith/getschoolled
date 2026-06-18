"""Memory store retention purge + API."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from aoep_shared.schemas import ConsentRecord, ConsentScope, Region
from memory.main import app
from memory.store import MemoryStore

client = TestClient(app)


def _old(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def test_purge_expired_consent_and_student():
    store = MemoryStore()
    store.upsert_student("s1", "Sam")
    # Expired consent (recorded 100 days ago, 30-day retention).
    store.record_consent(ConsentRecord(
        student_id="s1", scope=ConsentScope.FACE_RECOGNITION, granted=True,
        region=Region.US, retention_days=30, recorded_at=_old(100)))
    store.update_mastery("s1", "fractions", True)

    report = store.purge_expired()
    assert report["consent_records_purged"] == 1
    assert report["students_purged"] == 1
    assert store.get("s1") is None  # data deleted on retention expiry


def test_active_consent_is_kept():
    store = MemoryStore()
    store.upsert_student("s2", "Kai")
    store.record_consent(ConsentRecord(
        student_id="s2", scope=ConsentScope.RECORDING, granted=True,
        region=Region.US, retention_days=365, recorded_at=_old(10)))
    report = store.purge_expired()
    assert report["consent_records_purged"] == 0
    assert store.get("s2") is not None


def test_default_window_applies_when_unset():
    store = MemoryStore()
    store.upsert_student("s3", "Lee")
    store.record_consent(ConsentRecord(
        student_id="s3", scope=ConsentScope.RECORDING, granted=True,
        region=Region.US, retention_days=None, recorded_at=_old(400)))
    # No explicit retention -> kept by default...
    assert store.purge_expired()["consent_records_purged"] == 0
    # ...but purged when a default window is enforced.
    assert store.purge_expired(default_retention_days=180)["consent_records_purged"] == 1


def test_retention_purge_endpoint():
    body = client.post("/retention/purge", json={}).json()
    assert "consent_records_purged" in body and "students_purged" in body
