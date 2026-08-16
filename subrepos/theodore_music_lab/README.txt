Theodore Music Lab (learn through songs)
========================================

Private quality lab for line-by-line song learning before promoting into
language_learning / content packs.

  • 100+ original / Suno-style educational songs (data/songs.jsonl)
  • Featured MP3 player UI with animation + lyrics (Travel Words, Wheels on
    the Bus learning version, Words This Way) at http://127.0.0.1:8097/
  • Karaoke: a bouncing ball rides the current word, the sung word is colour
    highlighted, finished lines dim to gold, and a ±0.25s sync nudge trims drift
  • Real per-line translation in all 27 languages, shown under every line at
    once (not only the active one) plus key-vocabulary chips and examples
  • Ask the AI about any line at any time — while the track is playing
  • Short lyric clips (chorus-sized line ranges) with lyrics + translation
  • Curated external lyric videos / channels with printed-lyrics links
  • Import schema for additional original packs (JSON/JSONL)

Featured audio: data/audio/*.mp3 + data/featured_songs.jsonl.
Clips: data/clips.jsonl. Video links: data/video_links.jsonl.

Translation tiers (best available wins; every line always resolves)
  curated  reviewed hand-authored line — es, fr, de, it, pt (curated_lines.py)
  cached   an earlier Grok translation persisted to data/i18n_cache/
  llm      Grok/xAI, one request per song+language, only when XAI_API_KEY is set
  lexicon  real target-language words for the line's content words (lexicon.py),
           covering all 27 languages offline — 69 terms, romanized where the
           script differs; km/bn/ur/fa/th/sw/he/ar/hi are flagged for native review

Karaoke timings are syllable-weighted estimates (timing.py); hand-tuned values
win when a line carries start_sec/end_sec or a song carries lead_in_sec.

Ask AI uses Grok when XAI_API_KEY is set and otherwise answers from the lyrics
themselves (line + translation + key words + example), so it works offline.

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
  follow the bouncing ball. Change Translation to any of the 27 codes — every
  line shows its translation immediately. Type a question in "Ask the AI about
  the lyrics" while the song keeps playing.

  Restart the server after pulling changes to this lab; a stale process keeps
  serving the old player UI and the old audio handler (no byte-range = no
  seeking = no clips).

  curl -s http://127.0.0.1:8097/health | python3 -m json.tool
  # ok=true, songs >= 100, featured_songs >= 3, meaning_language_count >= 26,
  # clips >= 6, videos >= 6, karaoke=true, ask_ai=true

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

Step 6 — check the karaoke, translation and Ask-AI APIs

  SONG=en-wheels-bus-audio-v1

  curl -s "http://127.0.0.1:8097/api/music/timing/$SONG?duration=74" \
    | python3 -m json.tool | head -40
  # per-line start/end plus per-word start/end (drives the bouncing ball)

  curl -s -X POST http://127.0.0.1:8097/api/music/translate \
    -H 'content-type: application/json' \
    -d "{\"song_id\":\"$SONG\",\"target_lang\":\"km\",\"allow_llm\":false}" \
    | python3 -m json.tool | head -40
  # every line translated; "tiers" reports how each line was produced

  curl -s -X POST http://127.0.0.1:8097/api/music/ask \
    -H 'content-type: application/json' \
    -d "{\"song_id\":\"$SONG\",\"question\":\"What does this line mean?\",\"line_no\":5,\"target_lang\":\"es\"}" \
    | python3 -m json.tool

  curl -s "http://127.0.0.1:8097/api/music/clips?song_id=$SONG&target_lang=fr" \
    | python3 -m json.tool | head -30
  curl -s http://127.0.0.1:8097/api/music/videos | python3 -m json.tool | head -20

APIs on :8097
  GET  / and /lab          — player UI (karaoke, translations, Ask AI, clips)
  GET  /health
  GET  /api/music/languages         — codes + per-language translation quality
  GET  /api/music/featured
  GET  /api/music/songs
  GET  /api/music/songs/{song_id}
  GET  /api/music/timing/{song_id}  — line + word timings (?duration=&lead_in=)
  GET  /api/music/audio/{filename}  — MP3, honours Range (206) so seeking works
  GET  /api/music/clips             — short lyric clips (?song_id=&target_lang=)
  GET  /api/music/videos            — curated lyric videos (?song_id=)
  POST /api/music/translate         — whole song, one language
  POST /api/music/explain           — one line: meaning, vocabulary, examples
  POST /api/music/ask               — ask the AI about the lyrics
  POST /api/music/meaning
  POST /api/music/import
  POST /api/music/session/start
  GET  /api/music/session/{session_id}
  POST /api/music/session/{session_id}/play
  POST /api/music/session/{session_id}/pause
  (+ repeat / next / meaning endpoints — see /docs)
