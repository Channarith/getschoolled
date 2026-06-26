"""Learning experience score persistence."""

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _signup(email="lx@example.com"):
    return client.post("/auth/signup", json={
        "email": email, "password": "S3cretpass", "display_name": "Lx",
    }).json()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _sid(tok):
    return client.get("/students", headers=_auth(tok)).json()["students"][0]["id"]


def test_lx_tick_updates_ema():
    tok = _signup()["token"]
    h = _auth(tok)
    sid = _sid(tok)
    client.post(f"/students/{sid}/adaptation", headers=h, json={
        "event_type": "lx_tick",
        "payload": {"score": 65, "strategy": "worked_examples", "success": False},
    })
    client.post(f"/students/{sid}/adaptation", headers=h, json={
        "event_type": "lx_tick",
        "payload": {"score": 80, "strategy": "worked_examples", "success": True},
    })
    lx = client.get(f"/students/{sid}/learning-experience", headers=h).json()
    assert lx["lx_score_ema"] is not None
    assert len(lx["recent_samples"]) >= 2
    assert "worked_examples" in lx["strategy_bandit"]


def test_lx_session_end_recorded():
    tok = _signup("lxend@example.com")["token"]
    h = _auth(tok)
    sid = _sid(tok)
    client.post(f"/students/{sid}/adaptation", headers=h, json={
        "event_type": "lx_session_end",
        "payload": {"score": 78, "strategy": "gentle_recap", "success": True},
    })
    adapt = client.get(f"/students/{sid}/adaptation", headers=h).json()["adaptation"]
    assert adapt["lx_score_ema"] == 78.0
