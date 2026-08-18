"""Regression tests for the 2026-08-17 audit (music lab backend).

- load_songs skipped corrupt JSONL lines instead of crashing the catalog.
- Catalog.list(limit=0) returns zero rows (was clamped to 1).
- SessionStore evicts old sessions instead of growing unboundedly.
- song_timings keeps hand-timed lines' spans out of the estimate budget.
"""

import json

from theodore_music_lab.catalog import Catalog, load_songs
from theodore_music_lab.session import SessionStore
from theodore_music_lab.timing import song_timings


def test_load_songs_skips_corrupt_jsonl_lines(tmp_path):
    good = {"song_id": "ok-1", "title_en": "OK", "lines": [{"text": "hello world"}]}
    bad = '{"song_id": "broken", '
    path = tmp_path / "songs.jsonl"
    path.write_text(json.dumps(good) + "\n" + bad + "\n", encoding="utf-8")
    songs = load_songs(path)  # must not raise on the corrupt line
    assert "ok-1" in [s.song_id for s in songs]


def test_catalog_list_limit_zero_returns_no_rows():
    cat = Catalog()
    assert cat.list(limit=0) == []


def test_session_store_evicts_oldest_at_capacity():
    store = SessionStore()
    store.MAX_SESSIONS = 10
    first_id = None
    for _ in range(12):
        snap = store.start(store.catalog.songs[0].song_id)
        first_id = first_id or snap["session_id"]
    assert len(store._sessions) <= 10
    assert first_id not in store._sessions  # oldest evicted


def test_song_timings_mixed_pinned_and_estimated_stay_in_duration():
    catalog = Catalog()
    song = catalog.songs[0]
    n = len(song.lines)
    assert n >= 3
    # Pin the first line to the first 30s of a 60s render; the rest estimate.
    song.lines[0].start_sec = 0.0
    song.lines[0].end_sec = 30.0
    try:
        timings = song_timings(song, duration_sec=60.0)
    finally:
        song.lines[0].start_sec = None
        song.lines[0].end_sec = None
    last_end = max(row["end"] for row in timings["lines"])
    assert last_end <= 60.0 + 1e-6, f"estimated lines overran the duration ({last_end})"
