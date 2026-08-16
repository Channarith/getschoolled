"""Tests for learn-through-music lab."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from theodore_music_lab.ask_ai import ask, explain_line
from theodore_music_lab.catalog import MEANING_LANGUAGES, Catalog, import_songs
from theodore_music_lab.main import app
from theodore_music_lab.media import load_clips, load_videos, resolve_clip
from theodore_music_lab.session import SessionMode, SessionStore
from theodore_music_lab.timing import song_timings, syllable_count
from theodore_music_lab.translations import translate_song


@pytest.fixture()
def offline(monkeypatch):
    """No LLM key: exercises the offline curated/lexicon + fallback paths."""
    monkeypatch.delenv("XAI_API_KEY", raising=False)


def _featured(cat: Catalog):
    return cat.featured()[0]


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
    # Real target-language text, never a "[Japanese] Meaning: …" placeholder.
    assert gloss["meaning"]["text"]
    assert "Meaning:" not in gloss["meaning"]["text"]
    assert gloss["meaning"]["tier"] in {"curated", "cached", "llm", "lexicon", "english"}
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


def test_import_accepts_string_lines():
    songs = import_songs(
        [
            {
                "song_id": "string-lines-ok",
                "title_en": "String Lines",
                "license": "original-salareen",
                "lines": ["hello", "world"],
            }
        ]
    )
    assert len(songs) == 1
    assert songs[0].line_count == 2
    assert songs[0].lines[0].text == "hello"


def test_player_page_uses_timeupdate_lyric_sync():
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "timeupdate" in page.text
        assert "syncActiveLineFromPlayer" in page.text


def test_api_health_and_session_flow():
    with TestClient(app) as client:
        h = client.get("/health")
        assert h.status_code == 200
        body = h.json()
        assert body["ok"] is True
        assert body["songs"] >= 100
        assert body["meaning_language_count"] >= 26
        assert body.get("featured_songs", 0) >= 3
        assert body.get("player") == "/"

        songs = client.get("/api/music/songs", params={"limit": 5})
        assert songs.status_code == 200
        song_id = songs.json()["songs"][0]["song_id"]

        page = client.get("/")
        assert page.status_code == 200
        assert "Theodore Music Lab" in page.text
        assert "Featured songs" in page.text

        featured = client.get("/api/music/featured")
        assert featured.status_code == 200
        pack = featured.json()
        assert pack["count"] >= 3
        first = pack["songs"][0]
        assert first["audio_url"].startswith("/api/music/audio/")
        assert first["animation"]

        detail = client.get(f"/api/music/songs/{first['song_id']}")
        assert detail.status_code == 200
        assert detail.json()["lines"]
        assert detail.json()["audio_url"]

        audio = client.get(first["audio_url"])
        assert audio.status_code == 200
        assert len(audio.content) > 1000

        meaning = client.post(
            "/api/music/meaning",
            json={
                "song_id": first["song_id"],
                "line_no": 1,
                "target_lang": "es",
            },
        )
        assert meaning.status_code == 200
        assert meaning.json()["meaning"]["target_language"] == "es"

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


def test_word_timings_cover_every_word_in_order():
    song = _featured(Catalog())
    timings = song_timings(song, duration_sec=90.0)
    assert timings["line_count"] == song.line_count
    assert timings["word_count"] >= timings["line_count"]
    previous_end = -1.0
    for row in timings["lines"]:
        assert row["start"] < row["end"]
        assert row["start"] >= previous_end - 0.001
        previous_end = row["end"]
        words = row["words"]
        assert len(words) == len(row["text"].split())
        for index, word in enumerate(words):
            assert word["start"] < word["end"] or word["end"] == word["start"]
            if index:
                assert word["start"] >= words[index - 1]["start"]
        assert words[0]["start"] == pytest.approx(row["start"], abs=0.01)
        assert words[-1]["end"] == pytest.approx(row["end"], abs=0.01)
    assert timings["lines"][-1]["end"] <= 90.0 + 0.01


def test_syllable_counts_are_sane():
    assert syllable_count("bus") == 1
    assert syllable_count("supermarket") == 4
    assert syllable_count("restaurant") in {2, 3}
    assert syllable_count("the") == 1


def test_curated_translation_is_real_target_language(offline):
    song = next(s for s in Catalog().featured() if s.song_id == "en-wheels-bus-audio-v1")
    payload = translate_song(song, "es", allow_llm=False)
    assert payload["language_name"] == "Spanish"
    chorus = next(r for r in payload["lines"] if "Wheels on the bus" in r["text"])
    assert chorus["translation"] == "Las ruedas del autobús giran y giran"
    assert chorus["tier"] == "curated"
    assert "Meaning:" not in chorus["translation"]


def test_every_line_has_a_translation_in_every_language(offline):
    """The comprehensiveness guarantee: no blank cell, in any language."""
    for song in Catalog().featured():
        for code in MEANING_LANGUAGES:
            payload = translate_song(song, code, allow_llm=False)
            assert payload["line_count"] == song.line_count
            assert payload["complete"], f"{song.song_id}/{code} has untranslated lines"
            for row in payload["lines"]:
                assert row["translation"].strip()
                assert row["tier"] in {"curated", "cached", "llm", "lexicon", "english"}
                if code != "en":
                    # Real target-language text offline, never an English echo.
                    assert row["tier"] != "english", (
                        f"{song.song_id}/{code} line {row['line_no']} fell back to English"
                    )


def test_explain_line_gives_vocabulary_and_examples(offline):
    song = next(s for s in Catalog().featured() if s.song_id == "en-wheels-bus-audio-v1")
    detail = explain_line(song, 5, "fr")
    assert detail["translation"] == "Les roues du bus tournent et tournent"
    vocab = {row["en"]: row["target"] for row in detail["vocabulary"]}
    assert vocab.get("wheels") == "roues"
    assert vocab.get("bus") == "bus"
    assert detail["examples"]
    assert detail["pronunciation"].count("(") == len(detail["text"].split())


def test_ask_ai_works_offline_and_stays_grounded(offline):
    song = next(s for s in Catalog().featured() if s.song_id == "en-wheels-bus-audio-v1")
    reply = ask(song, "What does this line mean?", line_no=5, language="es")
    assert reply["fallback_used"] is True
    assert reply["provider"] == "grounded-offline"
    assert "Wheels on the bus go round and round" in reply["answer"]
    assert "Las ruedas del autobús giran y giran" in reply["answer"]
    assert 5 in reply["cited_lines"]

    pronounce = ask(song, "How do I pronounce it?", line_no=5, language="en")
    assert "syllable" in pronounce["answer"].lower() or "(" in pronounce["answer"]


def test_clips_are_windows_of_a_song_with_translations(offline):
    cat = Catalog()
    clips = load_clips()
    assert len(clips) >= 4
    clip = next(c for c in clips if c["clip_id"] == "wheels-chorus")
    song = cat.get(clip["song_id"])
    resolved = resolve_clip(song, clip, "de", duration_sec=74.0)
    assert resolved["line_count"] == 4
    assert 0 < resolved["duration_sec"] < 74.0
    assert resolved["start_sec"] < resolved["end_sec"]
    assert resolved["audio_url"].startswith("/api/music/audio/")
    assert resolved["lines"][0]["translation"]
    assert resolved["lines"][0]["words"]


def test_audio_supports_byte_ranges_so_seeking_works():
    """Seeking drives Restart, clip playback and click-a-line-to-jump."""
    with TestClient(app) as client:
        url = client.get("/api/music/featured").json()["songs"][0]["audio_url"]
        full = client.get(url)
        assert full.status_code == 200
        assert full.headers["accept-ranges"] == "bytes"
        total = len(full.content)

        partial = client.get(url, headers={"Range": "bytes=1000-1999"})
        assert partial.status_code == 206
        assert partial.headers["content-range"] == f"bytes 1000-1999/{total}"
        assert len(partial.content) == 1000
        assert partial.content == full.content[1000:2000]

        tail = client.get(url, headers={"Range": "bytes=1000-"})
        assert tail.status_code == 206
        assert len(tail.content) == total - 1000

        assert client.get(url, headers={"Range": f"bytes={total + 5}-"}).status_code == 416


def test_video_links_all_offer_lyrics():
    videos = load_videos()
    assert len(videos) >= 4
    for row in videos:
        assert row["url"].startswith("https://")
        assert row["has_lyrics"] is True
        assert row["note"]
    assert any(row["embed_url"] for row in videos)


def test_new_apis_and_player_ui(offline):
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["clips"] >= 4
        assert health["videos"] >= 4
        assert health["karaoke"] is True
        assert health["ask_ai"] is True

        langs = client.get("/api/music/languages").json()
        assert len(langs["catalog"]) == len(MEANING_LANGUAGES)
        spanish = next(row for row in langs["catalog"] if row["code"] == "es")
        assert spanish["curated"] is True
        assert spanish["curated_coverage"] == 1.0

        song_id = "en-wheels-bus-audio-v1"
        timing = client.get(f"/api/music/timing/{song_id}", params={"duration": 74}).json()
        assert timing["word_count"] > timing["line_count"]

        translated = client.post(
            "/api/music/translate",
            json={"song_id": song_id, "target_lang": "it", "allow_llm": False},
        ).json()
        assert translated["complete"] is True
        assert all(row["translation"] for row in translated["lines"])

        explained = client.post(
            "/api/music/explain",
            json={"song_id": song_id, "line_no": 5, "target_lang": "pt"},
        ).json()
        assert explained["translation"] == "As rodas do ônibus giram e giram"

        answer = client.post(
            "/api/music/ask",
            json={
                "song_id": song_id,
                "question": "What does this line mean?",
                "line_no": 5,
                "target_lang": "fr",
            },
        ).json()
        assert answer["answer"]
        assert answer["cited_lines"]

        clips = client.get("/api/music/clips", params={"song_id": song_id}).json()
        assert clips["count"] >= 2

        videos = client.get("/api/music/videos", params={"song_id": song_id}).json()
        assert videos["count"] >= 4

        bad = client.post(
            "/api/music/translate",
            json={"song_id": song_id, "target_lang": "xx"},
        )
        assert bad.status_code == 422

        page = client.get("/").text
        assert 'id="ball"' in page
        assert "Ask the AI about the lyrics" in page
        assert "Short lyric clips" in page
        assert "Lyric videos" in page
        assert "This line, translated" in page
