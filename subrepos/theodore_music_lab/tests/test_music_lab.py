"""Tests for learn-through-music lab."""

from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_music_lab.catalog import MEANING_LANGUAGES, Catalog, import_songs
from theodore_music_lab.main import app
from theodore_music_lab.session import SessionMode, SessionStore


def test_catalog_has_100_plus_original_songs():
    cat = Catalog()
    assert len(cat.songs) >= 100
    assert all(s.license.startswith("original") for s in cat.songs[:50])
    langs = {s.language for s in cat.songs}
    assert len(langs) >= 26


def test_meaning_languages_cover_26_plus():
    assert len(MEANING_LANGUAGES) >= 26


def test_line_pause_repeat_continue_and_meaning():
    cat = Catalog()
    song = cat.songs[0]
    store = SessionStore(cat)
    snap = store.start(song.song_id, mode=SessionMode.LINE_PAUSE, meaning_language="es")
    assert snap["state"] == "ready"
    played = store.play(snap["session_id"])
    assert played["state"] == "paused"
    assert played["last_event"]["type"] == "play"
    repeated = store.repeat(snap["session_id"])
    assert repeated["last_event"]["type"] == "repeat"
    gloss = store.meaning(snap["session_id"], target_lang="ja")
    assert gloss["meaning"]["target_language"] == "ja"
    assert "Meaning:" in gloss["meaning"]["text"]
    cont = store.continue_(snap["session_id"])
    assert cont["line_index"] == 1


def test_continuous_mode_auto_advances():
    cat = Catalog()
    song = next(s for s in cat.songs if s.line_count >= 3)
    store = SessionStore(cat)
    snap = store.start(song.song_id, mode=SessionMode.CONTINUOUS)
    p1 = store.play(snap["session_id"])
    assert p1["line_index"] == 1
    assert p1["state"] == "ready"


def test_import_rejects_copyright_pack():
    try:
        import_songs(
            [
                {
                    "song_id": "bad",
                    "license": "copyright-popular",
                    "lines": [{"line_no": 1, "text": "nope"}],
                }
            ]
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "original" in str(exc).lower() or "refusing" in str(exc).lower()


def test_api_health_and_session_flow():
    with TestClient(app) as client:
        h = client.get("/health")
        assert h.status_code == 200
        body = h.json()
        assert body["ok"] is True
        assert body["songs"] >= 100
        assert body["meaning_language_count"] >= 26

        songs = client.get("/api/music/songs", params={"limit": 5})
        assert songs.status_code == 200
        song_id = songs.json()["songs"][0]["song_id"]

        start = client.post(
            "/api/music/session/start",
            json={"song_id": song_id, "mode": "line_pause", "meaning_language": "fr"},
        )
        assert start.status_code == 200
        sid = start.json()["session_id"]

        play = client.post(f"/api/music/session/{sid}/play")
        assert play.status_code == 200
        assert play.json()["state"] == "paused"

        meaning = client.post(
            f"/api/music/session/{sid}/meaning", json={"target_lang": "de"}
        )
        assert meaning.status_code == 200
        assert meaning.json()["meaning"]["target_language"] == "de"

        cont = client.post(f"/api/music/session/{sid}/continue")
        assert cont.status_code == 200
