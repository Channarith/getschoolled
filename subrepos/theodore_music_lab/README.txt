Theodore Music Lab (learn through songs)
========================================

Private quality lab for line-by-line song learning before promoting into
language_learning / content packs.

  • 100+ original / Suno-style educational songs (data/songs.jsonl)
  • Play → pause → repeat per line; continuous mode skips the pause gate
  • Meaning / translation hints for 26+ platform languages
  • Import schema for additional original packs (JSON/JSONL)

Everything below runs offline. No audio files or API keys are required for
catalog / session smoke checks.

Screens
  docs/screens/theodore_music_lab.webp
  (also under this subrepo at docs/screens/theodore_music_lab.webp)
  Song catalog + line-by-line session console. Regenerate:
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

Step 2 — start the lab API

  PYTHONPATH=subrepos/theodore_music_lab/src:packages/shared/src \
    python3 -m uvicorn theodore_music_lab.main:app --port 8097 --host 127.0.0.1

  Leave that running. From another terminal:

  curl -s http://127.0.0.1:8097/health | python3 -m json.tool
  # ok=true, songs >= 100, meaning_language_count >= 26

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
  GET  /health
  GET  /api/music/languages
  GET  /api/music/songs
  GET  /api/music/songs/{song_id}
  POST /api/music/import
  POST /api/music/session/start
  GET  /api/music/session/{session_id}
  POST /api/music/session/{session_id}/play
  POST /api/music/session/{session_id}/pause
  (+ repeat / next / meaning endpoints — see /docs)
