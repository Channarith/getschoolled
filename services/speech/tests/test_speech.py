from fastapi.testclient import TestClient

from speech_gw.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["service"] == "speech"


def test_languages_count_is_26():
    body = client.get("/languages").json()
    assert body["count"] == 26


def test_tts_engine_routing():
    assert client.get("/tts/engine", params={"language": "en"}).json()["engine"] == "xtts"
    assert (
        client.get("/tts/engine", params={"language": "sw"}).json()["engine"]
        == "cloud-tts-fallback"
    )
