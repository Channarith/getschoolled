"""Identity profile avatar catalog + persistence."""

from identity.main import app
from identity.store import AccountStore

client = __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(app)


def _reset():
    app.state.accounts = AccountStore()


def _signup(email: str = "avatar@example.com"):
    r = client.post(
        "/auth/signup",
        json={"email": email, "password": "Secret123!", "display_name": "Ava"},
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_avatars_catalog_public():
    _reset()
    r = client.get("/avatars/catalog")
    assert r.status_code == 200
    body = r.json()
    assert body["default_id"]
    assert {s["id"] for s in body["styles"]} == {"realistic", "cute"}
    assert len(body["avatars"]) >= 16
    assert any(a["style"] == "realistic" for a in body["avatars"])
    assert any(a["style"] == "cute" for a in body["avatars"])
    cute = client.get("/avatars/catalog?style=cute").json()["avatars"]
    assert cute and all(a["style"] == "cute" for a in cute)


def test_set_account_avatar_persists_and_migrates_legacy():
    _reset()
    tok = _signup()
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post("/account/avatar", headers=h, json={"avatar_id": "c-peach"})
    assert r.status_code == 200, r.text
    assert r.json()["avatar_id"] == "c-peach"
    me = client.get("/auth/me", headers=h).json()
    assert me["avatar_id"] == "c-peach"

    # Legacy logo id migrates to a cute catalog entry.
    r2 = client.post("/account/avatar", headers=h, json={"avatar_id": "logo"})
    assert r2.status_code == 200
    assert r2.json()["avatar_id"] == "c-sunny"
    assert client.get("/account/avatar", headers=h).json()["id"] == "c-sunny"


def test_onboarding_profile_accepts_avatar():
    _reset()
    tok = _signup("onboard-avatar@example.com")
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post(
        "/onboarding/profile",
        headers=h,
        json={"display_name": "Pat", "avatar_id": "r-amir"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["avatar_id"] == "r-amir"
    assert client.get("/auth/me", headers=h).json()["avatar_id"] == "r-amir"
