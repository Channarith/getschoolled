Theodore Music Lab (learn through songs)
========================================

Private quality lab for line-by-line song learning before promoting into
language_learning / content packs.

  • 100+ original / Suno-style educational songs (data/songs.jsonl)
  • Featured MP3 player UI with animation + lyrics (Travel Words, Wheels on
    the Bus learning version, Words This Way) at http://127.0.0.1:8097/
  • Play → pause → restart; lyric lines highlight while the track plays
  • Meaning / translation glosses for 26+ platform languages
  • Import schema for additional original packs (JSON/JSONL)

Featured audio: data/audio/*.mp3 + data/featured_songs.jsonl.

Everything below runs offline for catalog / session smoke checks. The player
UI needs the local MP3 files present under data/audio/.

Screens
  docs/screens/theodore_music_lab.webp
  (also under this subrepo at docs/screens/theodore_music_lab.webp)
  Featured MP3 player with lyric sync + meaning glosses. Regenerate:
    python3 scripts/render_lab_docs_screenshots.py

STEP BY STEP (from repo root)
-----------------------------

Step 0 — activate the project venv (once per shell)

  cd "$(git rev-parse --show-toplevel)"
  . .venv/bin/activate
  # if needed:
  #   python3 -m venv .venv && . .venv/bin/activate
  #   python3 -m pip install -e 'packages/shared' -e 'subrepos/theodore_music_lab[test]'

Step 1 — run the automated tests + catalog smoke

  PYTHONPATH=subrepos/theodore_music_lab/src:packages/shared/src \
    python3 -m pytest subrepos/theodore_music_lab/tests -q

  make music-lab
  # prints song count (>= 100) and meaning-language count (>= 26)

Step 2 — start the lab API + open the player

  PYTHONPATH=subrepos/theodore_music_lab/src:packages/shared/src \
    python3 -m uvicorn theodore_music_lab.main:app --port 8097 --host 127.0.0.1

  Open http://127.0.0.1:8097/ (or /lab). Pick a featured song, hit Play, and
  change Meaning language to any of the 26+ codes.

  curl -s http://127.0.0.1:8097/health | python3 -m json.tool
  # ok=true, songs >= 100, featured_songs >= 3, meaning_language_count >= 26

Step 3 — browse the catalog

  curl -s 'http://127.0.0.1:8097/api/music/songs?limit=5' | python3 -m json.tool
  curl -s http://127.0.0.1:8097/api/music/languages | python3 -m json.tool

  Pick a song_id from the list (example: colors_song_en if present).

Step 4 — start a line-pause session and step through lines

  SONG=$(curl -s 'http://127.0.0.1:8097/api/music/songs?limit=1' \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["songs"][0]["song_id"])')
  echo "using song: $SONG"

  curl -s -X POST http://127.0.0.1:8097/api/music/session/start \
    -H 'content-type: application/json' \
    -d "{\"song_id\":\"$SONG\",\"mode\":\"line_pause\",\"meaning_language\":\"es\"}" \
    | tee /tmp/music-session.json | python3 -m json.tool

  SID=$(python3 -c 'import json;print(json.load(open("/tmp/music-session.json"))["session_id"])')

  curl -s -X POST "http://127.0.0.1:8097/api/music/session/$SID/play" \
    | python3 -m json.tool
  curl -s -X POST "http://127.0.0.1:8097/api/music/session/$SID/pause" \
    | python3 -m json.tool
  curl -s "http://127.0.0.1:8097/api/music/session/$SID" | python3 -m json.tool

Step 5 — (optional) import an extra pack, then promote when ready

  # POST /api/music/import with {"songs":[...]} JSON/JSONL-shaped rows
  # Promote stable songs + meaning glosses into language_learning content packs.

APIs on :8097
  GET  / and /lab          — featured player UI (audio + animation + lyrics)
  GET  /health
  GET  /api/music/languages
  GET  /api/music/featured
  GET  /api/music/songs
  GET  /api/music/songs/{song_id}
  GET  /api/music/audio/{filename}
  POST /api/music/meaning
  POST /api/music/import
  POST /api/music/session/start
  GET  /api/music/session/{session_id}
  POST /api/music/session/{session_id}/play
  POST /api/music/session/{session_id}/pause
  (+ repeat / next / meaning endpoints — see /docs)
