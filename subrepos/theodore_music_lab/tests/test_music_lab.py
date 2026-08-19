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
    watch_url,
)
from theodore_music_lab.main import app
from theodore_music_lab.media import load_clips, load_videos, resolve_clip
from theodore_music_lab.practice import (
    build_memory_drill,
    build_quiz,
    check_song_singing,
    grade_memory,
    grade_quiz,
    paraphrase_line,
    practice_menu,
)
from theodore_music_lab.pronounce import check_pronunciation, score_attempt
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
from theodore_music_lab.timing import alignment_for, song_timings, syllable_count
from theodore_music_lab.tts import (
    ENGINE,
    VOICES,
    TTSUnavailable,
    clip_path,
    rate_percent,
    speak,
    synthesize,
    tts_status,
    voice_candidates,
    voice_for,
)
from theodore_music_lab.translations import translate_song
from theodore_music_lab.vocal_align import (
    VocalSpan,
    align_lines_to_spans,
    align_weights_to_spans,
)


@pytest.fixture()
def offline(monkeypatch):
    """No LLM key: exercises the offline curated/lexicon + fallback paths."""
    monkeypatch.delenv("XAI_API_KEY", raising=False)


@pytest.fixture()
def tts_cache(monkeypatch, tmp_path):
    """An empty clip cache, so a test never depends on the developer's real one."""
    monkeypatch.setenv("MUSIC_LAB_TTS_CACHE", str(tmp_path / "tts"))
    monkeypatch.delenv("MUSIC_LAB_TTS", raising=False)
    return tmp_path / "tts"


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


def test_language_picker_offers_every_language_grouped_by_quality():
    """A tick beside six names read as "only six supported"; groups say it plainly."""
    with TestClient(app) as client:
        page = client.get("/").text
        assert "<optgroup" in page
        assert "Full-line translations" in page
        assert "Word-by-word glosses" in page
        catalog = client.get("/api/music/languages").json()
        assert catalog["count"] >= 26
        curated = {row["code"] for row in catalog["catalog"] if row["curated"]}
        # Chinese and Khmer must be full-line, not lexicon glosses.
        assert {"zh", "km"} <= curated
        for code in ("zh", "km"):
            row = next(r for r in catalog["catalog"] if r["code"] == code)
            assert row["curated_coverage"] == pytest.approx(1.0, abs=0.001)


def test_every_translation_language_has_a_neural_voice():
    """Device voices are why "Sing in Khmer" failed; the server must cover all 27."""
    assert set(VOICES) == set(MEANING_LANGUAGES)
    for code in MEANING_LANGUAGES:
        female, male = VOICES[code]
        locale = VOICE_TAGS[code]
        for voice in (female, male):
            assert voice.startswith(f"{locale}-"), (code, voice)
            assert voice.endswith("Neural"), (code, voice)
    assert voice_for("km") == "km-KH-SreymomNeural"
    assert voice_for("km", gender="male") == "km-KH-PisethNeural"
    assert voice_for("zh") == "zh-CN-XiaoxiaoNeural"
    # An unknown code still speaks rather than crashing the sing toggle.
    assert voice_for("xx").startswith("en-US-")


def test_speech_rate_is_quantised_so_two_visits_reuse_one_clip():
    # The rate follows the audio duration the browser reports, which wobbles by a
    # fraction of a percent between encodes; neighbours share a 5% bucket.
    assert rate_percent(1.11) == rate_percent(1.12) == "+10%"
    assert rate_percent(1.23) == rate_percent(1.24) == "+25%"
    for multiplier in (0.9, 1.03, 1.27, 1.68, 1.8):
        assert int(rate_percent(multiplier).rstrip("%")) % 5 == 0
    assert rate_percent(1.0) == "+0%"
    assert rate_percent(1.5) == "+50%"
    assert rate_percent(0.85) == "-15%"
    # Absurd values are clamped, not passed to the voice service.
    assert rate_percent(9.0) == "+100%"
    assert rate_percent("nonsense") == "+0%"


def test_a_cached_clip_is_served_without_any_engine(tts_cache, monkeypatch):
    """Prefetched clips make every language work offline."""
    monkeypatch.setenv("MUSIC_LAB_TTS", "off")
    text = "ខ្ញុំទៅធ្វើការ"
    path = clip_path(text, voice=voice_for("km"), rate=rate_percent(1.0))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ID3-fake-khmer-clip")
    assert synthesize(text, "km") == b"ID3-fake-khmer-clip"
    with TestClient(app) as client:
        got = client.get("/api/music/tts", params={"text": text, "lang": "km"})
    assert got.status_code == 200
    assert got.headers["content-type"] == "audio/mpeg"
    assert got.content == b"ID3-fake-khmer-clip"


def test_tts_answers_501_so_the_player_falls_back_to_the_device(tts_cache, monkeypatch):
    monkeypatch.setenv("MUSIC_LAB_TTS", "off")
    with TestClient(app) as client:
        got = client.get("/api/music/tts", params={"text": "hola", "lang": "es"})
        status = client.get("/api/music/tts/status").json()
    # 501, not 500: the client treats it as "use the device voice", not an error.
    assert got.status_code == 501
    assert status["available"] is False
    assert status["languages"] == len(MEANING_LANGUAGES)


def test_tts_status_is_the_platform_name_and_reports_the_engine_chain(
    tts_cache, monkeypatch
):
    """Every lab exposes `tts.tts_status`; main.py and /api/tts/status use it."""
    from theodore_music_lab import tts as tts_module

    assert tts_module.tts_status is tts_status
    assert tts_module.status is tts_status  # older in-lab callers

    monkeypatch.setenv("MUSIC_LAB_TTS", "off")
    off = tts_status()
    assert off["available"] is False
    assert off["engines"] == []
    assert off["engine"] == "none"
    assert off["cached_clips"] == 0

    path = clip_path("hola", voice=voice_for("es"), rate=rate_percent(1.0))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ID3-fake-spanish-clip")
    cached = tts_status()
    assert cached["available"] is True
    assert cached["engines"] == ["cache"]
    assert cached["engine"] == "cache-only"
    assert cached["cached_clips"] == 1

    monkeypatch.setattr("theodore_music_lab.tts.engine_available", lambda: True)
    live = tts_status()
    assert live["engines"] == [ENGINE]
    assert live["languages"] == len(VOICES)


def test_api_tts_speaks_with_the_platform_shape(tts_cache, monkeypatch):
    """/api/tts is the cross-lab endpoint: (audio, mime, engine) + style presets."""
    monkeypatch.setenv("MUSIC_LAB_TTS", "off")
    # "deep" must reach for the male half of the pair at a slower rate, so a
    # style change is a different clip, not the same one relabelled.
    deep = clip_path("hello", voice=voice_for("en", gender="male"), rate=rate_percent(0.95))
    deep.parent.mkdir(parents=True, exist_ok=True)
    deep.write_bytes(b"ID3-fake-deep-clip")
    audio, mime, engine = speak("hello", language="en", style="deep")
    assert (audio, mime, engine) == (b"ID3-fake-deep-clip", "audio/mpeg", "cache")

    with TestClient(app) as client:
        got = client.get("/api/tts", params={"text": "hello", "language": "en", "style": "deep"})
        assert got.status_code == 200
        assert got.content == b"ID3-fake-deep-clip"
        assert got.headers["content-type"] == "audio/mpeg"
        assert got.headers["X-TTS-Engine"] == "cache"
        # Empty text is the caller's mistake (422), not a missing engine (501).
        assert client.get("/api/tts", params={"text": "  "}).status_code == 422
        # Nothing cached for warm/female Polish and no engine: 501 => device voice.
        assert client.get(
            "/api/tts", params={"text": "dzień dobry", "language": "pl"}
        ).status_code == 501
        assert client.get("/api/tts/status").json()["engines"] == ["cache"]


def test_rendered_clips_are_cached_once_and_reused(tts_cache, monkeypatch):
    calls: list[tuple[str, str, str]] = []

    def fake_render(text, path, *, voice, rate):
        calls.append((text, voice, rate))
        path.write_bytes(b"rendered-mp3")

    monkeypatch.setattr("theodore_music_lab.tts._render", fake_render)
    monkeypatch.setattr("theodore_music_lab.tts.engine_available", lambda: True)
    assert synthesize("你好", "zh", rate=1.2) == b"rendered-mp3"
    assert synthesize("你好", "zh", rate=1.2) == b"rendered-mp3"
    assert calls == [("你好", "zh-CN-XiaoxiaoNeural", "+20%")]


def test_polish_turkish_arabic_have_alternate_voices_for_flaky_renders():
    # Primary female first; same-language male next; Polish/Arabic extras after.
    assert voice_candidates("pl")[0] == "pl-PL-AgnieszkaNeural"
    assert "pl-PL-ZofiaNeural" in voice_candidates("pl")
    assert voice_candidates("tr")[:2] == ["tr-TR-EmelNeural", "tr-TR-AhmetNeural"]
    assert "ar-EG-SalmaNeural" in voice_candidates("ar")
    # An explicit voice short-circuits the candidate list.
    assert voice_candidates("pl", voice="pl-PL-ZofiaNeural") == ["pl-PL-ZofiaNeural"]


def test_transient_empty_audio_retries_then_falls_back_to_alternate_voice(
    tts_cache, monkeypatch
):
    attempts: list[str] = []

    def flaky(text, path, *, voice, rate):
        attempts.append(voice)
        if voice in {"pl-PL-AgnieszkaNeural", "pl-PL-MarekNeural"}:
            raise RuntimeError("No audio was received. Please verify that your parameters are correct.")
        path.write_bytes(b"zofia-mp3")

    monkeypatch.setattr("theodore_music_lab.tts._render", flaky)
    monkeypatch.setattr("theodore_music_lab.tts.engine_available", lambda: True)
    monkeypatch.setattr("theodore_music_lab.tts.time.sleep", lambda _s: None)
    assert synthesize("dzień dobry", "pl") == b"zofia-mp3"
    assert attempts.count("pl-PL-AgnieszkaNeural") == 3
    assert attempts.count("pl-PL-MarekNeural") == 3
    assert "pl-PL-ZofiaNeural" in attempts


def test_a_failed_render_leaves_no_truncated_clip(tts_cache, monkeypatch):
    def boom(text, path, *, voice, rate):
        path.write_bytes(b"half")
        raise RuntimeError("connection reset")

    monkeypatch.setattr("theodore_music_lab.tts._render", boom)
    monkeypatch.setattr("theodore_music_lab.tts.engine_available", lambda: True)
    monkeypatch.setattr("theodore_music_lab.tts.time.sleep", lambda _s: None)
    with pytest.raises(TTSUnavailable):
        synthesize("bonjour", "fr")
    assert not clip_path("bonjour", voice=voice_for("fr"), rate="+0%").exists()
    assert list(tts_cache.glob("*.mp3")) == []
    assert list(tts_cache.glob("*.part")) == []


def test_the_player_speaks_through_the_server_and_can_fall_back():
    with TestClient(app) as client:
        page = client.get("/").text
    assert "probeServerVoices" in page
    assert "/api/music/tts?lang=" in page
    # One cancel path must stop device speech AND server audio.
    assert "function cancelSpeech" in page
    assert "speakOnDevice" in page
    body = page.split("function cancelSpeech", 1)[1].split("\n  function ", 1)[0]
    assert "window.speechSynthesis.cancel()" in body
    # It must stop the device engine, not recurse into itself (it did once, and
    # the stack overflow left the player stuck on "Choose a song").
    assert "cancelSpeech()" not in body
    # The old dead end: refusing a language because the OS had no voice.
    assert "voice installed on this device" not in page
    # Pausing must not be followed by another sung line from the next tick.
    sing = page.split("function speakLine", 1)[1].split("\n  function ", 1)[0]
    assert 'if ($("player").paused) return;' in sing


def test_the_page_carries_an_icon_and_favicon_ico_is_served():
    """An undeclared icon makes every visit log a 404 for /favicon.ico."""
    with TestClient(app) as client:
        page = client.get("/")
        assert 'rel="icon"' in page.text
        assert "data:image/svg+xml," in page.text
        icon = client.get("/favicon.ico")
        assert icon.status_code == 200
        assert icon.headers["content-type"].startswith("image/svg+xml")
        assert icon.text.startswith("<svg")


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
        assert "xai_configured" in body
        assert "speech" in body
        assert "engines" in body["speech"]

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


def test_every_featured_song_is_aligned_to_its_own_vocals():
    """A featured MP3 without measured alignment drifts, so guard the data file."""
    for song in Catalog().featured():
        record = alignment_for(song.song_id)
        assert record, f"{song.song_id} has no entry in data/alignment.jsonl"
        assert record["duration_sec"] > 0
        assert [row["line_no"] for row in record["lines"]] == [
            line.line_no for line in song.lines
        ]


def test_lyrics_wait_for_the_intro_and_stop_before_the_outro():
    for song in Catalog().featured():
        record = alignment_for(song.song_id)
        timings = song_timings(song, duration_sec=record["duration_sec"])
        assert timings["aligned"] is True
        assert timings["source"] == "measured vocal alignment"
        first = timings["lines"][0]
        last = timings["lines"][-1]
        # The old estimate started line 1 at 0.0s, ahead of every intro.
        assert first["start"] > 0.5
        assert first["start"] == pytest.approx(timings["lead_in_sec"], abs=0.01)
        assert last["end"] < timings["duration_sec"] - 0.2
        previous_end = 0.0
        for row in timings["lines"]:
            assert row["start"] >= previous_end - 0.001
            assert row["end"] > row["start"]
            previous_end = row["end"]


def test_no_line_is_sung_faster_than_a_human_can():
    """A line squeezed into a fraction of its syllables means a slipped mapping."""
    for song in Catalog().featured():
        timings = song_timings(song)
        for row in timings["lines"]:
            syllables = sum(syllable_count(w) for w in row["text"].split())
            span = row["end"] - row["start"]
            assert syllables / span <= 8.0, f"{song.song_id} line {row['line_no']}"


def test_alignment_stretches_to_a_different_encode_of_the_same_song():
    song = Catalog().get("en-wheels-bus-audio-v1")
    reference = alignment_for(song.song_id)["duration_sec"]
    native = song_timings(song, duration_sec=reference)
    stretched = song_timings(song, duration_sec=reference * 1.1)
    ratio = stretched["lines"][0]["start"] / native["lines"][0]["start"]
    assert ratio == pytest.approx(1.1, abs=0.01)
    assert stretched["lines"][-1]["end"] < reference * 1.1


def test_hand_tuned_line_timing_still_wins_over_the_measurement():
    song = Catalog().get("en-wheels-bus-audio-v1").model_copy(deep=True)
    song.lines[0].start_sec = 9.5
    song.lines[0].end_sec = 12.5
    timings = song_timings(song, duration_sec=74.76)
    assert timings["lines"][0]["start"] == 9.5
    assert timings["lines"][0]["end"] == 12.5
    assert timings["lines"][0]["words"][0]["start"] == pytest.approx(9.5, abs=0.01)


def test_a_song_without_measured_alignment_falls_back_to_the_estimate():
    song = next(s for s in Catalog().songs if not alignment_for(s.song_id))
    timings = song_timings(song, duration_sec=60.0)
    assert timings["aligned"] is False
    assert timings["source"] == "syllable-weighted estimate"
    assert timings["line_count"] == song.line_count


def test_replacing_an_mp3_without_realigning_falls_back_to_the_estimate(monkeypatch):
    """Stale timings against a new encode would drift, so they are discarded."""
    import theodore_music_lab.timing as timing_module

    song = Catalog().get("en-wheels-bus-audio-v1")
    assert song_timings(song)["aligned"] is True
    record = dict(alignment_for(song.song_id))
    record["audio_bytes"] = int(record["audio_bytes"]) + 1024
    monkeypatch.setattr(
        timing_module, "alignment_for", lambda song_id: record, raising=True
    )
    timings = song_timings(song)
    assert timings["aligned"] is False
    assert timings["source"] == "syllable-weighted estimate"


def test_phrase_segmentation_puts_every_line_boundary_on_a_measured_onset():
    spans = [
        VocalSpan(2.0, 3.0),
        VocalSpan(3.4, 4.4),
        VocalSpan(8.0, 9.0),
        VocalSpan(9.3, 10.5),
    ]
    placed = align_lines_to_spans([4.0, 4.0], spans)
    starts = {span.start for span in spans}
    ends = {span.end for span in spans}
    assert len(placed) == 2
    for start, end in placed:
        assert start in starts
        assert end in ends
    # The instrumental bar between 4.4s and 8.0s belongs to neither line.
    assert placed[0][1] <= 4.4
    assert placed[1][0] >= 8.0


def test_phrase_segmentation_declines_when_there_are_fewer_phrases_than_lines():
    assert align_lines_to_spans([1.0, 1.0, 1.0], [VocalSpan(0.0, 4.0)]) == []


def test_sung_time_share_skips_the_instrumental_break():
    spans = [VocalSpan(1.0, 5.0), VocalSpan(20.0, 24.0)]
    placed = align_weights_to_spans([1.0, 1.0, 1.0, 1.0], spans)
    assert len(placed) == 4
    assert placed[0][0] == 1.0
    assert placed[-1][1] == 24.0
    for start, end in placed:
        # No line may live inside 5.0s-20.0s, where nobody is singing.
        assert not (5.0 < start < 20.0)
        assert not (5.0 < end < 20.0)


def test_sing_along_speech_may_run_through_the_instrumental_rest(offline):
    song = Catalog().get("en-wheels-bus-audio-v1")
    plan = sing_plan(song, "es", allow_llm=False)
    timings = song_timings(song)
    starts = [row["start"] for row in timings["lines"]]
    stretched = 0
    for index, row in enumerate(plan["lines"]):
        assert row["end"] >= row["sung_end"]
        if index + 1 < len(starts):
            assert row["end"] == pytest.approx(
                max(row["sung_end"], starts[index + 1]), abs=0.01
            )
        if row["end"] > row["sung_end"] + 0.01:
            stretched += 1
    assert stretched, "measured timings leave rests a translated line can use"


def test_the_stage_never_goes_blank_during_intro_or_outro():
    for song in Catalog().featured():
        board = storyboard_for(song, language="en")
        assert board["scenes"][0]["start"] == 0.0
        assert board["scenes"][-1]["end"] == pytest.approx(
            board["duration_sec"], abs=0.05
        )
        for index in range(len(board["scenes"]) - 1):
            assert board["scenes"][index]["end"] == pytest.approx(
                board["scenes"][index + 1]["start"], abs=0.001
            )


def test_no_lyric_line_starts_before_the_singing_does():
    """The complaint was line 1 lighting up during an instrumental intro."""
    for song in Catalog().featured():
        timings = song_timings(song)
        first = min(float(row["start"]) for row in timings["lines"])
        assert first == pytest.approx(float(timings["lead_in_sec"]), abs=0.01)
        if timings["source"] == "measured vocal alignment":
            # Every featured song opens on instrumental bars; lyrics must wait.
            assert first > 1.0


def test_the_intro_counts_in_instead_of_highlighting_the_first_line():
    with TestClient(app) as client:
        page = client.get("/").text
    assert "showCountIn" in page
    assert "Singing starts in" in page
    assert "line.upcoming" in page
    # The old behaviour marked line 1 active through the intro.
    assert "setActiveLine(first.line_no, false, false)" not in page


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


def test_chinese_and_khmer_have_full_line_translations_offline(offline):
    for song in Catalog().featured():
        for code in ("zh", "km"):
            payload = translate_song(song, code, allow_llm=False)
            assert payload["language_name"] in {"Chinese", "Khmer"}
            assert payload["tiers"] == {"curated": song.line_count}
            for row in payload["lines"]:
                assert row["tier"] == "curated"
                assert row["translation"] != row["text"]
                assert " · " not in row["translation"]

    travel = next(s for s in Catalog().featured() if s.song_id == "en-travel-words-audio-v1")
    chinese = translate_song(travel, "zh", allow_llm=False)
    khmer = translate_song(travel, "km", allow_llm=False)
    assert chinese["lines"][0]["translation"] == "我去上班"
    assert khmer["lines"][0]["translation"] == "ខ្ញុំទៅធ្វើការ"


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


def test_pronunciation_check_scores_and_coaches(offline):
    perfect = score_attempt("Wheels on the bus go round and round",
                            "wheels on the bus go round and round")
    assert perfect["score"] >= 95
    assert perfect["passed"] is True
    assert perfect["missed_words"] == []

    partial = score_attempt(
        "Wheels on the bus go round and round",
        "wheels on the bus go around",
    )
    assert 40 <= partial["score"] < 95
    assert "round" in partial["missed_words"] or partial["wrong_words"]
    assert partial["corrections"]
    assert partial["mouth_tip"]

    song = next(s for s in Catalog().featured() if s.song_id == "en-wheels-bus-audio-v1")
    result = check_pronunciation(
        song,
        line_no=5,
        heard="wheels on the bus go round and round",
        language="es",
        practice="english",
    )
    assert result["passed"] is True
    assert result["practice"] == "english"
    assert result["recognition_lang"] == "en-US"
    assert result["syllables"]

    spanish = check_pronunciation(
        song,
        line_no=5,
        heard="Las ruedas del autobus giran y giran",
        language="es",
        practice="translation",
    )
    assert spanish["practice"] == "translation"
    assert spanish["language"] == "es"
    assert spanish["score"] >= 70
    assert spanish["recognition_lang"].startswith("es")


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
    for row in videos:
        if row["embed_url"]:
            assert row["embed_url"].startswith("https://www.youtube.com/embed/")
            assert "youtube-nocookie" not in row["embed_url"]
            assert "modestbranding" not in row["embed_url"]


def test_new_apis_and_player_ui(offline):
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["clips"] >= 4
        assert health["videos"] >= 4
        assert health["embeds"] >= 4
        assert health["embed_pause_ask"] >= 4
        assert health["karaoke"] is True
        assert health["ask_ai"] is True
        assert health["pronunciation_check"] is True

        langs = client.get("/api/music/languages").json()
        assert len(langs["catalog"]) == len(MEANING_LANGUAGES)
        spanish = next(row for row in langs["catalog"] if row["code"] == "es")
        assert spanish["curated"] is True
        assert spanish["curated_coverage"] == 1.0
        # Full-line curated pack is Romance + Chinese + Khmer; other languages
        # are lexicon glosses (see CURATED_LANGUAGES / language picker groups).
        curated_codes = {
            row["code"] for row in langs["catalog"] if row["curated"] and row["code"] != "en"
        }
        assert {"es", "fr", "de", "it", "pt", "zh", "km"} <= curated_codes
        for code in ("es", "zh", "km"):
            row = next(r for r in langs["catalog"] if r["code"] == code)
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

        pronounced = client.post(
            "/api/music/pronounce",
            json={
                "song_id": song_id,
                "line_no": 5,
                "heard": "wheels on the bus go round and round",
                "target_lang": "es",
                "practice": "english",
            },
        ).json()
        assert pronounced["passed"] is True
        assert pronounced["score"] >= 90
        assert pronounced["corrections"] is not None
        assert client.post(
            "/api/music/pronounce",
            json={"song_id": song_id, "heard": "x", "practice": "nope"},
        ).status_code == 422

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
        assert detail["embed_url"].startswith("https://www.youtube.com/embed/")
        assert "youtube-nocookie" not in detail["embed_url"]
        assert "enablejsapi=1" in detail["embed_url"]
        assert "modestbranding" not in detail["embed_url"]
        assert "playsinline=1" in detail["embed_url"]
        assert detail["watch_url"].startswith("https://www.youtube.com/watch?v=")
        assert detail["watch_url"] == watch_url(detail["youtube_id"])
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
        assert "Learn &amp; practice this song" in page
        assert "Say / sing line" in page
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
                     'id="auto-pause"', 'id="embed-ask-send"',
                     'id="speak-verse"', 'id="btn-hear-verse"',
                     'id="btn-mic"', 'id="btn-hear-model"', 'id="pronounce-result"',
                     'id="practice-en"', 'id="practice-tr"',
                     'id="practice-modes"', 'id="pane-quiz"', 'id="pane-memory"',
                     'id="pane-paraphrase"', 'id="pane-sing"', 'id="btn-sing-start"'):
            assert hook in page, hook
        assert "SpeechRecognition" in page or "webkitSpeechRecognition" in page
        assert "SpeechSynthesisUtterance" in page
        assert "/api/music/pronounce" in page
        assert "youtube.com/iframe_api" in page
        assert "https://www.youtube.com/embed/" in page
        assert "buildYtIframe" in page
        assert "yt-frame" in page
        assert "referrerPolicy" in page
        assert 'referrerpolicy="strict-origin-when-cross-origin"' in page
        assert "autoplay; encrypted-media; picture-in-picture; fullscreen; clipboard-write" in page
        assert "hardenYtIframeAttributes" in page
        assert "ytFrameAllow" in page
        assert "onError" in page
        assert "Open on YouTube" in page
        assert "degradeToStudyMode" in page
        assert "clockMediaAdapter" in page
        assert "embedGen" in page
        assert "getIframe" in page
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


def test_embed_url_uses_youtube_host_not_nocookie():
    assert embed_url("") == ""
    assert embed_url("   ") == ""
    assert embed_url("abc") == ""  # not an 11-char YouTube id
    assert embed_url("2owVccYAIRg/evil") == ""
    assert watch_url("") == ""
    url = embed_url("2owVccYAIRg")
    assert url.startswith("https://www.youtube.com/embed/2owVccYAIRg?")
    assert "youtube-nocookie" not in url
    assert "enablejsapi=1" in url
    assert "rel=0" in url
    assert "playsinline=1" in url
    assert "modestbranding" not in url
    quiet = embed_url("2owVccYAIRg", jsapi=False)
    assert "enablejsapi" not in quiet
    assert quiet.startswith("https://www.youtube.com/embed/2owVccYAIRg?")
    with_origin = embed_url("2owVccYAIRg", origin="https://lab.example")
    assert "origin=https%3A%2F%2Flab.example" in with_origin
    assert "widget_referrer=https%3A%2F%2Flab.example" in with_origin
    assert watch_url("2owVccYAIRg") == "https://www.youtube.com/watch?v=2owVccYAIRg"
    assert watch_url("2owVccYAIRg", start=12) == "https://www.youtube.com/watch?v=2owVccYAIRg&t=12"


def test_youtube_player_owns_iframe_and_study_mode():
    """Pause-and-ask player builds its own iframe; lyric Play-here is not nocookie."""
    with TestClient(app) as client:
        page = client.get("/").text
        assert "https://www.youtube.com/embed/" in page
        assert "buildYtIframe" in page
        assert "hardenYtIframeAttributes" in page
        assert "embedGen" in page
        assert "yt-frame" in page
        assert "referrerPolicy" in page
        assert 'referrerpolicy="strict-origin-when-cross-origin"' in page
        assert "autoplay; encrypted-media; picture-in-picture; fullscreen; clipboard-write" in page
        assert "onError" in page
        assert "getIframe" in page
        assert "Open on YouTube" in page
        assert "degradeToStudyMode" in page
        assert "clockMediaAdapter" in page
        assert "getPlayerState" in page
        videos = client.get("/api/music/videos").json()["videos"]
        for row in videos:
            if row.get("embed_url"):
                assert row["embed_url"].startswith("https://www.youtube.com/embed/")
                assert "youtube-nocookie" not in row["embed_url"]


def test_youtube_embeds_pause_and_ask_in_curated_languages(offline):
    rows = load_embeds()
    assert len(rows) >= 4
    assert embed_url("2owVccYAIRg").endswith("2owVccYAIRg?rel=0&playsinline=1&enablejsapi=1")
    pause_ask = [
        r for r in rows if r.get("verses") and r.get("kind") != "local-karaoke"
    ]
    assert len(pause_ask) >= 3
    for raw in pause_ask:
        assert raw["youtube_id"]
        for language in ("en", "es", "fr", "de", "it", "pt"):
            resolved = resolve_embed(raw, language, allow_llm=False)
            assert resolved["watch_url"] == f"https://www.youtube.com/watch?v={raw['youtube_id']}"
            assert resolved["embed_url"].startswith("https://www.youtube.com/embed/")
            assert "youtube-nocookie" not in resolved["embed_url"]
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


def test_every_video_line_reads_and_speaks_in_khmer_and_chinese(offline):
    """A learner who picks Khmer must get Khmer on every video line — text and voice.

    The lyric panel was curated for zh/km while the video verses were not, so the
    song translated and the video below it stayed in English.
    """
    videos = [row for row in load_embeds() if row.get("verses")]
    assert len(videos) >= 4
    for raw in videos:
        for language, tag in (("km", "km-KH"), ("zh", "zh-CN")):
            resolved = resolve_embed(raw, language, allow_llm=False)
            assert resolved["voice_tag"] == tag
            assert resolved["spoken_lines"] == resolved["verse_count"]
            for verse in resolved["verses"]:
                where = f"{raw['embed_id']} line {verse['verse_no']} ({language})"
                assert verse["tier"] == "curated", where
                assert verse["translation"] != verse["text_en"], where
                # The voice reads exactly what the line shows, in that language.
                assert verse["speak_lang"] == language, where
                assert verse["voice_tag"] == tag, where
                assert verse["speak_text"], where
                assert "\u00b7" not in verse["speak_text"], where
                for question in verse["questions"]:
                    assert question["prompt_tier"] == "curated", where
                    assert question["answer_tier"] == "curated", where
                    assert question["prompt_translation"] != question["prompt"], where


def test_an_untranslated_line_is_never_read_by_the_wrong_voice(offline):
    invented = {
        "embed_id": "test-uncurated",
        "kind": "video",
        "youtube_id": "abc12345678",
        "verses": [
            {
                "verse_no": 1,
                "text": "Zebras juggled spare umbrellas politely.",
                "start_sec": 0.0,
                "pause_sec": 5.0,
                "questions": [],
            }
        ],
    }
    verse = resolve_embed(invented, "km", allow_llm=False)["verses"][0]
    assert verse["tier"] == "english"
    assert verse["speak_lang"] == "en"
    assert verse["voice_tag"] == "en-US"
    assert resolve_embed(invented, "km", allow_llm=False)["spoken_lines"] == 0


def test_the_player_speaks_each_video_line_in_the_picked_language():
    with TestClient(app) as client:
        page = client.get("/").text
    assert 'id="speak-verse"' in page
    assert 'id="btn-hear-verse"' in page
    assert 'id="pause-voice"' in page
    # Verse speech follows the server's per-line voice, not the song's sing plan.
    assert "lang: verse.speak_lang" in page
    assert "tag: verse.voice_tag" in page
    # Only a paused video is silent, so speech never overlaps the soundtrack.
    assert 'if (locked && $("speak-verse").checked) speakVerse(verse);' in page
    assert "pauseMedia();\n    speakVerse(verse);" in page
    # Embeds now translate like the lyric panel does instead of falling to English.
    assert "allow_llm=false" not in page
    assert "allow_llm=true" in page


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
    assert all(row["tier"] == "curated" for row in plan["lines"])
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


def test_song_practice_quiz_memory_paraphrase_and_full_sing(offline):
    """Learning a song covers quiz, memory, other ways to say it, and whole-song sing."""
    cat = Catalog()
    song = cat.featured()[0]
    menu = practice_menu(song, "es")
    assert [m["id"] for m in menu["modes"]] == [
        "pronounce",
        "quiz",
        "memory",
        "ask",
        "paraphrase",
        "sing",
    ]

    quiz = build_quiz(song, "es", count=6, seed="unit-quiz")
    assert quiz["count"] >= 4
    assert "answer_key" in quiz
    assert all("answer" not in q for q in quiz["questions"])
    perfect = grade_quiz(
        song,
        language="es",
        answers=quiz["answer_key"],
        count=6,
        seed="unit-quiz",
    )
    assert perfect["score"] == 100
    assert perfect["passed"] is True
    blank = grade_quiz(
        song, language="es", answers={}, count=6, seed="unit-quiz"
    )
    assert blank["score"] == 0
    assert blank["passed"] is False

    mem = build_memory_drill(
        song, "es", direction="en_to_target", count=4, seed="unit-mem"
    )
    assert mem["count"] >= 2
    mem_ok = grade_memory(
        song,
        language="es",
        direction="en_to_target",
        answers=mem["answer_key"],
        count=4,
        seed="unit-mem",
    )
    assert mem_ok["passed"] is True
    assert mem_ok["score"] >= 60

    para = paraphrase_line(song, line_no=1, language="es", allow_llm=False)
    assert para["line_no"] == 1
    assert len(para["alternatives"]) >= 2
    assert para["alternatives"][0]["source"] == "song"

    from theodore_music_lab.translations import translate_song as _tr

    rows = _tr(song, "es", allow_llm=False)["lines"]
    sung = check_song_singing(
        song,
        language="es",
        practice="translation",
        lines=[{"line_no": r["line_no"], "heard": r["translation"]} for r in rows],
    )
    assert sung["line_count"] == len(song.lines)
    assert sung["score"] == 100
    assert sung["passed"] is True
    empty = check_song_singing(
        song, language="es", practice="translation", lines=[]
    )
    assert empty["score"] == 0
    assert empty["passed"] is False


def test_practice_apis_keep_answer_keys_off_the_wire(offline):
    cat = Catalog()
    song = cat.featured()[0]
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["song_practice"] is True
        assert "quiz" in health["practice_modes"]

        menu = client.get(
            f"/api/music/practice/{song.song_id}",
            params={"target_lang": "es"},
        ).json()
        assert len(menu["modes"]) == 6

        quiz = client.get(
            f"/api/music/practice/{song.song_id}/quiz",
            params={"target_lang": "es", "count": 5, "seed": "api-quiz"},
        ).json()
        assert "answer_key" not in quiz
        assert quiz["seed"] == "api-quiz"
        # Rebuild the key server-side the same way /grade does.
        key = build_quiz(song, "es", count=5, seed="api-quiz")["answer_key"]
        graded = client.post(
            "/api/music/practice/quiz/grade",
            json={
                "song_id": song.song_id,
                "target_lang": "es",
                "answers": key,
                "count": 5,
                "seed": "api-quiz",
            },
        ).json()
        assert graded["score"] == 100

        mem = client.get(
            f"/api/music/practice/{song.song_id}/memory",
            params={
                "target_lang": "es",
                "direction": "en_to_target",
                "count": 3,
                "seed": "api-mem",
            },
        ).json()
        assert "answer_key" not in mem
        mem_key = build_memory_drill(
            song, "es", direction="en_to_target", count=3, seed="api-mem"
        )["answer_key"]
        mem_graded = client.post(
            "/api/music/practice/memory/grade",
            json={
                "song_id": song.song_id,
                "target_lang": "es",
                "direction": "en_to_target",
                "answers": mem_key,
                "count": 3,
                "seed": "api-mem",
            },
        ).json()
        assert mem_graded["passed"] is True

        para = client.post(
            "/api/music/practice/paraphrase",
            json={
                "song_id": song.song_id,
                "line_no": 1,
                "target_lang": "es",
                "allow_llm": False,
            },
        ).json()
        assert len(para["alternatives"]) >= 2

        rows = translate_song(song, "es", allow_llm=False)["lines"]
        sung = client.post(
            "/api/music/practice/sing",
            json={
                "song_id": song.song_id,
                "target_lang": "es",
                "practice": "translation",
                "lines": [
                    {"line_no": r["line_no"], "heard": r["translation"]} for r in rows
                ],
            },
        ).json()
        assert sung["passed"] is True
        assert sung["score"] == 100

        # Ask prompt about other ways stays grounded offline.
        asked = ask(
            song,
            "Other ways to say the same thing?",
            line_no=1,
            language="es",
        )
        assert "another way" in asked["answer"].lower() or "manera" in asked[
            "answer"
        ].lower() or "say" in asked["answer"].lower()


def test_the_player_wires_all_six_practice_modes():
    with TestClient(app) as client:
        page = client.get("/").text
    assert "setPracticeMode" in page
    assert "startQuiz" in page
    assert "startMemory" in page
    assert "loadParaphrases" in page
    assert "startSingCheck" in page
    assert "finishSingCheck" in page
    assert "Other ways to say the same thing?" in page
