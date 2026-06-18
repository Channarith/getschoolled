"""Legal notices registry + acceptance store tests."""

from aoep_shared.legal import (
    NOTICES,
    REQUIRED_NOTICE_IDS,
    AcceptanceStore,
    notice_versions,
)


def test_registry_has_core_notices():
    ids = {n.id for n in NOTICES}
    for required in ("license", "terms", "privacy", "aup", "dpa", "security"):
        assert required in ids


def test_acceptance_requires_all_required():
    store = AcceptanceStore()
    assert store.has_accepted_required("u1") is False
    assert set(store.outstanding("u1")) == set(REQUIRED_NOTICE_IDS)

    store.accept("u1", ["terms", "privacy"])
    assert store.has_accepted_required("u1") is False  # aup missing
    assert store.outstanding("u1") == ["aup"]

    store.accept("u1", ["aup"])
    assert store.has_accepted_required("u1") is True
    assert store.outstanding("u1") == []


def test_acceptance_records_versions():
    store = AcceptanceStore()
    rec = store.accept("u2", list(REQUIRED_NOTICE_IDS))
    versions = notice_versions()
    for nid in REQUIRED_NOTICE_IDS:
        assert rec.accepted[nid] == versions[nid]


def test_unknown_notice_ignored():
    store = AcceptanceStore()
    rec = store.accept("u3", ["terms", "bogus"])
    assert "bogus" not in rec.accepted
    assert rec.accepted.get("terms")
