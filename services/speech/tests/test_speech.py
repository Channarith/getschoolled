from fastapi.testclient import TestClient

from speech_gw.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["service"] == "speech"


def test_languages_count_is_27():
    body = client.get("/languages").json()
    # 26 base languages + Khmer (km) - brand-required for Salareen.
    assert body["count"] == 27
    assert "km" in body["languages"]


def test_tts_engine_routing():
    assert client.get("/tts/engine", params={"language": "en"}).json()["engine"] == "xtts"
    assert (
        client.get("/tts/engine", params={"language": "sw"}).json()["engine"]
        == "cloud-tts-fallback"
    )
