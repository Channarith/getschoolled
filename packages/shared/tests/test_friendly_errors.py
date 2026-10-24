from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from aoep_shared.friendly_errors import friendly_kind, friendly_message, install_friendly_errors


def _app() -> FastAPI:
    app = FastAPI()
    install_friendly_errors(app, script_url="/static/friendly_error.js")

    @app.get("/missing")
    def missing():
        raise HTTPException(404, "course not found")

    @app.get("/api/missing")
    def api_missing():
        raise HTTPException(404, "nope")

    @app.get("/later")
    def later():
        raise HTTPException(501, "not built yet")

    @app.get("/down")
    def down():
        raise HTTPException(503, {"reason": "identity down"}, headers={"Retry-After": "5"})

    @app.get("/bad")
    def bad():
        raise HTTPException(400, "bad input")

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internals")

    return app


def test_status_mapping():
    assert friendly_kind(404) == "notfound"
    assert friendly_kind(501) == "notimpl"
    for code in (502, 503, 504):
        assert friendly_kind(code) == "network"
    assert friendly_kind(500) == "oops"
    assert friendly_kind(599) == "oops"
    assert friendly_kind(400) is None
    assert friendly_kind(422) is None
    assert "Sala" in (friendly_message(404) or "")
    assert friendly_message(400) is None


def test_json_keeps_detail_and_adds_friendly_message():
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.get("/missing")
    assert r.status_code == 404
    body = r.json()
    assert body["detail"] == "course not found"
    assert body["error"] == "notfound"
    assert "Sala" in body["friendly_message"]
    d = client.get("/down")
    assert d.status_code == 503 and d.headers["retry-after"] == "5"
    assert d.json()["detail"] == {"reason": "identity down"}
    assert client.get("/later").json()["error"] == "notimpl"


def test_other_client_errors_are_untouched():
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.get("/bad")
    assert r.status_code == 400
    assert r.json() == {"detail": "bad input"}


def test_browsers_get_the_mascot_page_but_api_paths_stay_json():
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.get("/missing", headers={"accept": "text/html,application/xhtml+xml"})
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("text/html")
    assert "SalaFriendlyError.show" in r.text and "/static/friendly_error.js" in r.text
    j = client.get("/api/missing", headers={"accept": "text/html"})
    assert j.headers["content-type"].startswith("application/json")


def test_unhandled_exceptions_do_not_leak_internals():
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.get("/boom")
    assert r.status_code == 500
    assert "secret internals" not in r.text
    assert r.json()["error"] == "oops"
    h = client.get("/boom", headers={"accept": "text/html"})
    assert h.status_code == 500 and "text/html" in h.headers["content-type"]
