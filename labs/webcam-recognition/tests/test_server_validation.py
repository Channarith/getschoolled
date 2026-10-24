from fastapi.testclient import TestClient

from webcam_lab.server import app

client = TestClient(app, raise_server_exceptions=False)


def test_unknown_class_mode_is_422_not_500():
    r = client.post("/sessions", json={"session_id": "bad-mode", "class_mode": "nonsense"})
    assert r.status_code == 422


def test_valid_class_modes_still_create_sessions():
    for mode in ("solo", "GROUP"):
        r = client.post("/sessions", json={"session_id": f"ok-{mode}", "class_mode": mode})
        assert r.status_code == 200, r.text
