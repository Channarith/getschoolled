"""Tests for learn-through-music lab."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from theodore_music_lab.ask_ai import ask, explain_line
from theodore_music_lab.catalog import MEANING_LANGUAGES, Catalog, import_songs
from theodore_music_lab.embeds import (
    ask_verse,
    embed_url,
    explain_verse,
    list_embeds,
    load_embeds,
    resolve_embed,
)
from theodore_music_lab.main import app
from theodore_music_lab.media import load_clips, load_videos, resolve_clip
from theodore_music_lab.session import SessionMode, SessionStore
from theodore_music_lab.sing import (
    MAX_RATE,
    MIN_RATE,
    VOICE_TAGS,
    chars_per_second,
    sing_plan,
    speakable,
    speech_rate,
)
from theodore_music_lab.storyboard import (
    BACKDROPS,
    CAMERA_MOVES,
    MOTIONS,
    NARRATION_LANGUAGES,
    SAFE_X_MAX,
    SAFE_X_MIN,
    SPRITE_HEIGHT_PCT,
    SPRITES,
    STORYBOARDS,
    safe_x,
    scene_at,
    storyboard_for,
)
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
        assert health["embeds"] >= 4
        assert health["embed_pause_ask"] >= 4
        assert health["karaoke"] is True
        assert health["ask_ai"] is True

        langs = client.get("/api/music/languages").json()
        assert len(langs["catalog"]) == len(MEANING_LANGUAGES)
        spanish = next(row for row in langs["catalog"] if row["code"] == "es")
        assert spanish["curated"] is True
        assert spanish["curated_coverage"] == 1.0
        # Featured-song full-line pack covers every platform language, not just Romance.
        for row in langs["catalog"]:
            if row["code"] == "en":
                continue
            assert row["curated"] is True, row
            assert row["curated_coverage"] == 1.0, row

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

        board = client.get(
            f"/api/music/storyboard/{song_id}",
            params={"target_lang": "es", "duration": 74},
        ).json()
        assert board["scene_count"] == 6
        assert board["scenes"][0]["narration_tier"] == "curated"

        missing = client.get("/api/music/storyboard/en-song-0001")
        assert missing.status_code == 404
        bad_lang = client.get(
            f"/api/music/storyboard/{song_id}", params={"target_lang": "xx"}
        )
        assert bad_lang.status_code == 422

        plan = client.get(
            f"/api/music/sing/{song_id}",
            params={"target_lang": "es", "duration": 74, "allow_llm": False},
        ).json()
        assert plan["voice_tag"] == "es-ES"
        assert plan["line_count"] == len(plan["lines"])
        assert client.get(
            f"/api/music/sing/{song_id}", params={"target_lang": "xx"}
        ).status_code == 422

        embeds = client.get("/api/music/embeds", params={"target_lang": "es"}).json()
        assert embeds["count"] >= 4
        lesson = next(
            row
            for row in embeds["embeds"]
            if row["has_pause_ask"] and row["kind"] != "local-karaoke"
        )
        detail = client.get(
            f"/api/music/embeds/{lesson['embed_id']}",
            params={"target_lang": "es", "allow_llm": False},
        ).json()
        assert detail["embed_url"].startswith("https://www.youtube-nocookie.com/embed/")
        assert "enablejsapi=1" in detail["embed_url"]
        assert detail["verse_count"] >= 4
        assert detail["verses"][0]["questions"]
        asked = client.post(
            "/api/music/embeds/ask",
            json={
                "embed_id": lesson["embed_id"],
                "question": "Explain the grammar here",
                "verse_no": 1,
                "target_lang": "es",
                "allow_llm": False,
            },
        ).json()
        assert asked["answer"]
        assert asked["cited_verse"]["verse_no"] == 1
        assert client.get("/api/music/embeds/does-not-exist").status_code == 404

        karaoke = client.get(
            "/api/music/embeds/karaoke-love-of-learning-km",
            params={"target_lang": "es", "allow_llm": False},
        ).json()
        assert karaoke["verse_count"] == 60
        assert karaoke["video_url"].endswith("love_of_learning_khmer.mp4")
        assert karaoke["bilingual"] is True

        page = client.get("/").text
        assert 'id="ball"' in page
        assert "Ask the AI about the lyrics" in page
        assert "Short lyric clips" in page
        assert "Lyric videos" in page
        assert "This line, translated" in page
        # Sing-along scrolling: lead the active line, never chase the bottom edge.
        assert "const LOOKAHEAD_LINES = 2;" in page
        assert "keepLineVisible" in page
        assert "scrollIntoView" not in page
        # Full-screen storyboard stage.
        for hook in ('id="camera"', 'id="backdrop"', 'id="cast"', 'id="scene-tag"',
                     'id="cap-narration"', 'id="cap-line"', 'id="cap-ball"',
                     'id="btn-theater"', 'id="narrate"',
                     'id="sing-lang"', 'id="sing-label"',
                     'id="embed-picker"', 'id="yt-host"', 'id="pause-card"',
                     'id="auto-pause"', 'id="embed-ask-send"'):
            assert hook in page, hook
        assert "SpeechSynthesisUtterance" in page
        assert "youtube.com/iframe_api" in page
        assert "Pause at each verse" in page
        assert "YouTube movie lessons" in page
        assert 'id="local-video"' in page
        assert "Continue after ask" in page
        assert "requestFullscreen" in page
        for camera in CAMERA_MOVES:
            assert f".cam-{camera} " in page, camera
        for motion in MOTIONS:
            assert f"m-{motion}" in page, motion


def test_every_song_storyboard_covers_every_line_in_order():
    cat = Catalog()
    assert len(STORYBOARDS) == len(cat.featured())
    for song in cat.featured():
        board = storyboard_for(song, language="en")
        assert board["scene_count"] >= 5
        covered: list[int] = []
        previous_end = 0.0
        for scene in board["scenes"]:
            covered.extend(scene["line_numbers"])
            assert scene["camera"] in CAMERA_MOVES
            assert scene["backdrop"] in BACKDROPS
            assert scene["cast"], f"{scene['scene_id']} has no characters"
            assert scene["start"] == pytest.approx(previous_end, abs=0.01)
            assert scene["end"] > scene["start"]
            previous_end = scene["end"]
            for member in scene["cast"]:
                assert member["kind"] in SPRITES
                assert member["motion"] in MOTIONS
                # Cameras zoom in, so anything at the very edge would leave the
                # frame mid-scene.
                assert SAFE_X_MIN <= member["x"] <= SAFE_X_MAX
                assert 0 <= member["y"] <= 100
                assert member["height_pct"] == SPRITE_HEIGHT_PCT[member["kind"]]
        assert covered == [line.line_no for line in song.lines]
        assert previous_end == pytest.approx(board["duration_sec"], abs=0.05)


def test_khmer_english_karaoke_pauses_every_line(offline):
    from theodore_music_lab.love_of_learning import DURATION_SEC, love_of_learning_embed

    raw = love_of_learning_embed()
    assert raw["video_file"] == "love_of_learning_khmer.mp4"
    assert len(raw["verses"]) == 60
    assert raw["verses"][0]["source_lang"] == "en"
    assert raw["verses"][2]["source_lang"] == "km"
    assert raw["verses"][-1]["text_en"] == "I was born to learn"
    previous = 0.0
    for verse in raw["verses"]:
        assert verse["start_sec"] >= previous - 0.001
        assert verse["pause_sec"] > verse["start_sec"]
        previous = verse["pause_sec"]
    assert previous <= DURATION_SEC

    spanish = resolve_embed(raw, "es", allow_llm=False)
    assert spanish["video_url"] == "/api/music/video/love_of_learning_khmer.mp4"
    assert spanish["bilingual"] is True
    assert spanish["verses"][0]["tier"] == "curated"
    khmer = resolve_embed(raw, "km", allow_llm=False)
    assert khmer["verses"][2]["translation"] == raw["verses"][2]["text_km"]
    english = resolve_embed(raw, "en", allow_llm=False)
    assert english["verses"][2]["translation"] == raw["verses"][2]["text_en"]

    with TestClient(app) as client:
        detail = client.get(
            "/api/music/embeds/karaoke-love-of-learning-km",
            params={"target_lang": "fr", "allow_llm": False},
        ).json()
        assert detail["verse_count"] == 60
        video = client.get(detail["video_url"])
        assert video.status_code == 200
        assert video.headers["accept-ranges"] == "bytes"
        partial = client.get(detail["video_url"], headers={"Range": "bytes=0-1023"})
        assert partial.status_code == 206
        assert len(partial.content) == 1024


def test_youtube_embeds_pause_and_ask_in_curated_languages(offline):
    rows = load_embeds()
    assert len(rows) >= 4
    assert embed_url("2owVccYAIRg").endswith("2owVccYAIRg?enablejsapi=1&rel=0&modestbranding=1")
    pause_ask = [
        r for r in rows if r.get("verses") and r.get("kind") != "local-karaoke"
    ]
    assert len(pause_ask) >= 3
    for raw in pause_ask:
        assert raw["youtube_id"]
        for language in ("en", "es", "fr", "de", "it", "pt"):
            resolved = resolve_embed(raw, language, allow_llm=False)
            assert resolved["verse_count"] >= 4
            for verse in resolved["verses"]:
                assert verse["text"]
                assert verse["translation"]
                assert verse["pause_sec"] > verse["start_sec"]
                assert verse["questions"]
                for question in verse["questions"]:
                    assert question["kind"] in {
                        "vocabulary",
                        "grammar",
                        "comprehension",
                        "pronunciation",
                        "strategy",
                    }
                    assert question["prompt"]
                    assert question["answer"]
            if language != "en":
                assert resolved["verses"][0]["tier"] == "curated"
    catalogue = list_embeds("es", allow_llm=False)
    assert any(row["embed_id"] == "movie-incredibles-lesson-1" for row in catalogue)
    assert any(row["embed_id"] == "karaoke-love-of-learning-km" for row in catalogue)
    explained = explain_verse(
        "legend-cambodia-neang-neak", 1, "es", allow_llm=False
    )
    assert "príncipe" in explained["translation"].lower() or "principe" in explained[
        "translation"
    ].lower()
    answer = ask_verse(
        "movie-incredibles-lesson-1",
        "What does listen for mean?",
        verse_no=1,
        language="es",
        allow_llm=False,
    )
    assert answer["answer"]
    assert answer["cited_verse"]["verse_no"] == 1


def test_cast_is_pulled_into_the_action_safe_band():
    assert safe_x(90) == SAFE_X_MAX
    assert safe_x(4) == SAFE_X_MIN
    assert safe_x(50) == 50.0


def test_storyboard_art_is_self_contained_svg():
    for name, svg in BACKDROPS.items():
        assert svg.startswith("<svg ") and svg.endswith("</svg>"), name
        assert "http://www.w3.org/2000/svg" in svg
        assert "<image" not in svg, f"{name} must not need an external asset"
    for name, svg in SPRITES.items():
        assert svg.startswith("<svg ") and svg.endswith("</svg>"), name
        assert "<image" not in svg, f"{name} must not need an external asset"
        assert name in SPRITE_HEIGHT_PCT


def test_scene_narration_is_translated_for_all_platform_languages():
    cat = Catalog()
    song = cat.get("en-wheels-bus-audio-v1")
    english = storyboard_for(song, language="en")
    for language in NARRATION_LANGUAGES:
        board = storyboard_for(song, language=language)
        for scene, base in zip(board["scenes"], english["scenes"]):
            assert scene["narration_language"] == language
            assert scene["narration"] != base["narration"]
            assert scene["narration_en"] == base["narration"]
    # Khmer (and every other non-Romance language) must no longer fall back to
    # English-only scene notes — that was the "partial language support" bug.
    khmer = storyboard_for(song, language="km")
    assert khmer["scenes"][0]["narration_language"] == "km"
    assert khmer["scenes"][0]["narration"] != english["scenes"][0]["narration"]


def test_scene_at_maps_playback_position_to_a_scene():
    cat = Catalog()
    song = cat.get("en-wheels-bus-audio-v1")
    board = storyboard_for(song, language="en", duration_sec=60.0)
    assert scene_at(board, -5.0)["index"] == 0
    assert scene_at(board, 999.0)["index"] == board["scene_count"] - 1
    for scene in board["scenes"]:
        middle = (scene["start"] + scene["end"]) / 2
        assert scene_at(board, middle)["scene_id"] == scene["scene_id"]


def test_sing_plan_lets_every_language_carry_the_english_recording(offline):
    cat = Catalog()
    song = cat.get("en-wheels-bus-audio-v1")
    for language in MEANING_LANGUAGES:
        plan = sing_plan(song, language, duration_sec=74.0, allow_llm=False)
        assert plan["line_count"] == len(song.lines)
        assert plan["voice_tag"] == VOICE_TAGS[language]
        assert 0.0 < plan["backing_volume"] < 1.0
        for row in plan["lines"]:
            assert row["speak"], f"{language} line {row['line_no']} has nothing to say"
            assert MIN_RATE <= row["rate"] <= MAX_RATE
            # Speech has to start with the line, not after it.
            assert row["start"] < row["end"]
        # A window is only "crowded" when even MAX_RATE overruns it; a nursery
        # rhyme line should never be that dense.
        assert plan["crowded_lines"] == 0, language


def test_sing_speech_drops_the_romanization_shown_on_screen():
    assert speakable("\u4f60\u597d (n\u01d0 h\u01ceo) \u00b7 \u670b\u53cb (p\u00e9ngyou)") == (
        "\u4f60\u597d, \u670b\u53cb"
    )
    assert speakable("Hola amigo") == "Hola amigo"
    assert speakable("") == ""
    cat = Catalog()
    # Featured Chinese lines are now full curated sentences (no romanization),
    # so the singer speaks them whole rather than word-by-word lexicon glosses.
    plan = sing_plan(cat.get("en-wheels-bus-audio-v1"), "zh", allow_llm=False)
    assert plan["word_by_word"] is False
    assert all(row["speak"] for row in plan["lines"])
    assert all("(" not in row["speak"] for row in plan["lines"])
    # Lexicon-only languages still strip romanization before speech.
    lexiconish = speakable("\u1781\u17d2\u1789\u17bb\u17c6 (khnyom) \u00b7 \u1798\u17b7\u178f\u17d2\u178f (mit)")
    assert "(" not in lexiconish


def test_sing_rate_fits_the_line_into_its_window():
    # A dense script gets a faster rate than a roomy Latin script in the same
    # window, because it carries more meaning per character.
    long_line = "x" * 60
    assert speech_rate(long_line, 3.0, "es") > speech_rate(long_line, 12.0, "es")
    assert speech_rate("short", 6.0, "es") == MIN_RATE
    assert speech_rate("", 3.0, "es") == 1.0
    assert speech_rate("anything", 0.0, "es") == 1.0
    assert chars_per_second("zh") < chars_per_second("es")


def test_storyboard_scenes_stretch_with_the_real_audio_duration():
    cat = Catalog()
    song = cat.get("en-travel-words-audio-v1")
    short = storyboard_for(song, language="en", duration_sec=60.0)
    long_board = storyboard_for(song, language="en", duration_sec=180.0)
    assert short["scenes"][-1]["end"] == pytest.approx(60.0, abs=0.05)
    assert long_board["scenes"][-1]["end"] == pytest.approx(180.0, abs=0.05)
    for a, b in zip(short["scenes"], long_board["scenes"]):
        assert a["line_numbers"] == b["line_numbers"]
        assert b["duration"] > a["duration"]
