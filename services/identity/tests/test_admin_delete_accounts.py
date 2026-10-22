"""Operator admin: delete junk and test accounts."""

from __future__ import annotations

from fastapi.testclient import TestClient

from identity import persistence
from identity.main import app
from identity.store import AccountStore

client = TestClient(app)


def _setup():
    app.state.accounts = AccountStore()
    store = app.state.accounts
    store.seed_admin("admin@salareen.com", "88888888", username="admin")
    store.seed_admin("ops@salareen.com", "88888888", username="ops")
    junk = [store.create(f"junk-{n}@example.com", "Secret123") for n in range(3)]
    token = client.post("/auth/login", json={"email": "admin@salareen.com", "password": "88888888"}).json()["token"]
    return store, junk, {"Authorization": f"Bearer {token}"}


def _delete(headers, ids, confirm="DELETE"):
    return client.post("/admin/accounts/delete", headers=headers, json={"account_ids": ids, "confirm": confirm})


def test_admin_deletes_selected_accounts_and_the_list_drops_them():
    store, junk, headers = _setup()
    done = _delete(headers, [junk[0].id, junk[1].id])
    assert done.status_code == 200, done.text
    assert {row["email"] for row in done.json()["deleted"]} == {"junk-0@example.com", "junk-1@example.com"}
    listed = client.get("/admin/accounts", headers=headers).json()
    emails = {row["email"] for row in listed["accounts"]}
    assert "junk-0@example.com" not in emails and "junk-2@example.com" in emails
    assert store.by_email("junk-0@example.com") is None


def test_it_needs_the_word_delete_and_an_admin():
    store, junk, headers = _setup()
    assert _delete(headers, [junk[0].id], confirm="").status_code == 400
    assert _delete(headers, [junk[0].id], confirm="yes").status_code == 400
    assert store.by_id(junk[0].id) is not None
    token = client.post("/auth/login", json={"email": "junk-1@example.com", "password": "Secret123"}).json()["token"]
    assert _delete({"Authorization": f"Bearer {token}"}, [junk[0].id]).status_code == 403
    signed_out = TestClient(app)
    assert signed_out.post("/admin/accounts/delete", json={"account_ids": [junk[0].id], "confirm": "DELETE"}).status_code == 401
    assert store.by_id(junk[0].id) is not None


def test_operator_accounts_and_yourself_are_never_deleted():
    store, junk, headers = _setup()
    ops = store.by_email("ops@salareen.com")
    me = store.by_email("admin@salareen.com")
    done = _delete(headers, [ops.id, me.id, "missing", junk[2].id]).json()
    assert [row["id"] for row in done["deleted"]] == [junk[2].id]
    reasons = {row["id"]: row["reason"] for row in done["skipped"]}
    assert "operator" in reasons[ops.id]
    assert "own account" in reasons[me.id]
    assert reasons["missing"] == "not found"
    assert store.by_id(ops.id) is not None and store.by_id(me.id) is not None


def test_request_size_is_bounded():
    _store, junk, headers = _setup()
    assert _delete(headers, []).status_code == 422
    assert _delete(headers, [f"id-{n}" for n in range(51)]).status_code == 422


def test_a_replica_forgets_accounts_another_replica_deleted(monkeypatch):
    store = AccountStore()
    kept = store.create("kept@example.com", "Secret123")
    gone = store.create("gone@example.com", "Secret123")
    fresh = store.create("fresh@example.com", "Secret123")
    for acct in (kept, gone):
        store._persisted_blobs[acct.id] = "saved"

    class _Redis:
        def smembers(self, _key):
            return {kept.id.encode()}

    monkeypatch.setattr(persistence, "redis_configured", lambda: True)
    monkeypatch.setattr(persistence, "_redis_client", lambda: _Redis())
    assert persistence.prune_deleted_accounts(store) == 1
    assert store.by_id(gone.id) is None
    assert store.by_id(kept.id) is not None
    assert store.by_id(fresh.id) is not None  # never saved here, so it is new, not deleted


def test_pruning_does_nothing_when_the_shared_index_is_empty_or_unreadable(monkeypatch):
    store = AccountStore()
    acct = store.create("solo@example.com", "Secret123")
    store._persisted_blobs[acct.id] = "saved"

    class _Empty:
        def smembers(self, _key):
            return set()

    monkeypatch.setattr(persistence, "redis_configured", lambda: True)
    monkeypatch.setattr(persistence, "_redis_client", lambda: _Empty())
    assert persistence.prune_deleted_accounts(store) == 0

    class _Broken:
        def smembers(self, _key):
            raise RuntimeError("down")

    monkeypatch.setattr(persistence, "_redis_client", lambda: _Broken())
    assert persistence.prune_deleted_accounts(store) == 0
    assert store.by_id(acct.id) is not None


def test_saved_face_data_is_removed_after_the_account_and_never_blocks_the_delete(monkeypatch):
    from identity import main

    store, junk, headers = _setup()
    student = store.ensure_default_student(junk[0].id)
    student.biometric_setup = {"portrait": {"status": "verified"}}
    plain = store.ensure_default_student(junk[1].id)  # no saved face or voice: not contacted
    order: list[tuple[str, bool]] = []

    def purge(student_id):
        order.append((student_id, store.by_id(junk[0].id) is None))
        raise RuntimeError("perception down")

    monkeypatch.setattr(main, "_perception_delete", purge)
    done = _delete(headers, [junk[0].id, junk[1].id])
    assert done.status_code == 200, done.text
    assert len(done.json()["deleted"]) == 2
    assert order == [(student.id, True)]  # called once, and only after the account was gone
    assert plain.id not in [sid for sid, _ in order]


def test_an_account_only_another_replica_has_loaded_is_found_and_removed(monkeypatch):
    store, junk, headers = _setup()
    target = junk[2]
    hydrated: list[str] = []
    real = persistence.hydrate_account

    def pretend_not_loaded(st, account_id):
        hydrated.append(account_id)
        return real(st, account_id)

    store._by_id.pop(target.id)  # this replica has not loaded it
    monkeypatch.setattr(persistence, "hydrate_account", lambda st, aid: st._by_id.setdefault(aid, target) is target)
    done = _delete(headers, [target.id])
    assert done.json()["deleted"] == [{"id": target.id, "email": target.email}]
    assert target.id not in store._by_id
