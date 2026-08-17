Theodore Music Lab (learn through songs)
========================================

Private quality lab for line-by-line song learning before promoting into
language_learning / content packs.

  • 100+ original / Suno-style educational songs (data/songs.jsonl)
  • Featured MP3 player UI with animation + lyrics (Travel Words, Wheels on
    the Bus learning version, Words This Way) at http://127.0.0.1:8097/
  • Full-screen storyboard theater: every featured song is a sequence of scenes
    (22 in all) with drawn characters on a drawn background, a movie camera move
    per scene, and the scene's narration on screen under the sung line — press
    "Full screen" (or F) to fill the window, Esc to come back
  • Karaoke: a bouncing ball rides the current word, the sung word is colour
    highlighted, finished lines dim to gold, and a ±0.25s sync nudge (remembered
    per song) trims any residual drift
  • Lyrics measured against the recording: the words wait out the instrumental
    intro, hold through the rests between sections, and stop at the last sung
    line instead of being spread evenly from 0.0s to the final sample
  • Sing-along scrolling: the lyric box keeps two upcoming lines below the sung
    line, so you read the next line before you have to sing it
  • Real per-line translation in all 27 languages, shown under every line at
    once (not only the active one) plus key-vocabulary chips and examples
  • Sing in another language: tick "Sing in <language>" and a neural voice speaks
    each translated line inside that line's own window while the English
    recording drops to a backing-track level — the same MP3 in any of the 27.
    The voice is rendered by the server, so Khmer/Chinese/Thai sing on a device
    whose OS ships no such voice (see "Neural voices" below)
  • Ask the AI about any line at any time — while the track is playing
  • Say / sing this line: hear a model reading, speak into the mic (or type),
    get a 0–100 score with missed/wrong-word corrections and mouth tips
    (POST /api/music/pronounce) — practice English lyric or the translation
  • Short lyric clips (chorus-sized line ranges) with lyrics + translation
  • Curated external lyric videos / channels with printed-lyrics links
  • YouTube movie lessons embedded on the page: pause at each verse, answer
    grammar/vocabulary prompts, ask the AI about the line, and read the verse in
    any of 27 languages (Cambodia & Laos legends + Learn English with Movies)
  • Local Khmer/English karaoke (សេចក្ដីស្រឡាញ់ការរៀនសូត្រ — Love of Learning):
    60 timed lines, pause on every line, translate Khmer+English into any of 27
    languages, then ask about the line before continuing
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

Neural voices (all 27 languages, no OS voice needed)
"Sing in Khmer" used to refuse: the player spoke with window.speechSynthesis, so a
language only worked if the listener's OS had a voice for it, and macOS has none
for Khmer. The server now renders each line with a Microsoft Edge neural voice
(tts.py, one verified voice pair per language — km-KH-SreymomNeural for Khmer) and
the browser plays the MP3:

  pip install -e '.[voices]'                 # edge-tts==6.1.12
  GET /api/music/tts?lang=km&rate=0.86&text=…  -> audio/mpeg (501 = no engine)
  GET /api/music/tts/status                    -> {available, engine, languages}

Clips are cached on disk by (voice, rate, text) — default
~/.cache/theodore-music-lab/tts, override with MUSIC_LAB_TTS_CACHE — so a line is
rendered once and then replays offline. Warm a whole song ahead of a lesson:

  python3 scripts/prefetch_voices.py --lang km --lang zh
  python3 scripts/prefetch_voices.py --dry-run    # count what is missing

Rendering needs network once per clip (Microsoft's voice service). With no engine
and an empty cache the endpoint answers 501 and the player falls back to the
device voice, saying so once. MUSIC_LAB_TTS=off forces that fallback.

Karaoke timings for the featured MP3s are measured against the recording itself
(vocal_align.py). Vocals sit in the centre of the stereo image, so the centre
estimate "mid - side" in the 300-3500 Hz band tracks where someone is singing;
each lyric line is then assigned a run of those sung phrases, which keeps the
instrumental intro, the rests between sections and the outro out of the lyrics.
The result is committed to data/alignment.jsonl and read at request time (no
ffmpeg needed to serve). Regenerate after adding or replacing an MP3:

  python3 scripts/align_songs.py            # writes data/alignment.jsonl
  python3 scripts/align_songs.py --report   # print the timings, write nothing

To answer "is this song actually in sync?" without listening to all of it,
verify_alignment.py re-measures the audio and audits what the app serves — a
stale alignment.jsonl, a replaced MP3 or a bad scale becomes a number:

  python3 scripts/verify_alignment.py       # exits 1 when a song is off
  python3 scripts/verify_alignment.py --song en-travel-words-audio-v1 --report

Nothing is highlighted before the first sung word: the intro queues line 1 in a
muted "upcoming" state, hides the ball, and counts in ("Singing starts in 3...")
so a 3.1s instrumental opening does not read as lyrics running early.

Songs with no measured alignment fall back to a syllable-weighted estimate
(timing.py). Hand-tuned values still win when a line carries start_sec/end_sec
or a song carries lead_in_sec. A listener's ±0.25s sync nudge is remembered per
song, so a device with slow audio output keeps its correction.

Storyboard (storyboard.py, no external art assets)
  scenes    hand-authored per song, each pinned to a lyric line range, so the
            cuts land on line boundaries at any real audio duration
  backdrops 15 layered SVG sets (town street, park, bus interior, market row,
            airport hall, cafe, sunrise hill, stage lights, night map, …)
  cast      23 SVG characters and props (kids, grown-up, dog, bus, car, train,
            plane, sun, clouds, rain, tree, signs, arrows, food, ticket, …) with
            their own motion: wave, walk, hop, sway, drive, spinning wheels,
            opening doors, falling rain
  camera    push-in, pull-out, pan-left/right, tilt-up, ken-burns, zoom-punch,
            dolly-shake — the move runs for exactly the scene's length
  narration English scene notes, hand-translated for es/fr/de/it/pt; other
            languages show the English note (narration_tier says which) while
            the sung line underneath stays translated in all 27
  motion     everything is CSS on inline SVG, pauses with the audio, and honours
            prefers-reduced-motion
  framing   cameras zoom up to ~1.26x, so cast x is clamped into the action-safe
            band (SAFE_X_MIN..SAFE_X_MAX); only "drive"/"cross-*" leave the frame
            on purpose

Tick "Narrate scenes" to have the device voice read the scene note; the music
ducks while it speaks and comes back up afterwards.

Sing-along (sing.py)
  plan      one row per line: the translated text, the line's start/end window,
            a BCP-47 voice tag, and the speech rate that makes the sentence fit
  rate      chars / (chars-per-second budget × window), clamped 0.85–1.8 so a
            dense script (zh/ja/ko) speeds up instead of overrunning the line
  speech    romanization hints shown on screen ("你好 (nǐ hǎo)") are stripped
            before speaking, and "·" between glosses becomes a comma pause
  backing   the English MP3 drops to backing_volume (0.22) while singing and is
            restored when the toggle goes off, on pause, and on song change
  device    the voice comes from the OS/browser; with no voice for that language
            installed the toggle refuses and says so rather than failing silently

YouTube embeds (embeds.py + data/embeds.jsonl)
  player    privacy-friendly youtube-nocookie iframe with the IFrame API so the
            page can pause, seek and poll the playhead
  verses    each lesson has timed start/pause points with English teaching text,
            focus (grammar/vocabulary/comprehension), key terms and 2 prepared
            questions per verse
  i18n      curated es/fr/de/it/pt for every verse + prompt + answer; other
            languages use the same lexicon/LLM/cache stack as song lyrics
  ask       POST /api/music/embeds/ask answers grammar/vocab questions about the
            paused verse (Grok when keyed, otherwise the prepared Q&A)
  examples  Preah Thong & Neang Neak, Sang Sinxay, The Incredibles movie lesson,
            plus the Learn English with Movies playlist pointer
  karaoke   local MP4 Love of Learning (Khmer+English, 60 pause lines) served
            from /api/music/video/ with Range seeking; bilingual text_en/text_km
            so any target language translates from the English gloss while Khmer
            display stays the source script

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
  # clips >= 6, videos >= 6, karaoke=true, ask_ai=true,
  # vocal_aligned_songs == featured_songs (every MP3 aligned to its vocals)

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
  # per-line start/end plus per-word start/end (drives the bouncing ball).
  # aligned=true and source="measured vocal alignment" mean the timings came
  # from the audio; lead_in_sec is where the singing starts.

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

  curl -s "http://127.0.0.1:8097/api/music/storyboard/$SONG?target_lang=es&duration=74" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); [print(s["index"], s["camera"], s["backdrop"], s["narration"]) for s in d["scenes"]]'
  # timed scenes with their backdrop, camera move, cast and narration

  curl -s "http://127.0.0.1:8097/api/music/sing/$SONG?target_lang=es&duration=74" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["voice_tag"]); [print(r["start"], r["rate"], r["speak"]) for r in d["lines"][:6]]'
  # sing the English recording in another language: what to say, when, how fast

  curl -s "http://127.0.0.1:8097/api/music/embeds?target_lang=es" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); [print(e["embed_id"], e["verse_count"], e["title"]) for e in d["embeds"]]'
  curl -s "http://127.0.0.1:8097/api/music/embeds/movie-incredibles-lesson-1?target_lang=fr&allow_llm=false" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); [print(v["verse_no"], v["pause_sec"], v["translation"]) for v in d["verses"]]'
  curl -s -X POST http://127.0.0.1:8097/api/music/embeds/ask \
    -H 'content-type: application/json' \
    -d '{"embed_id":"legend-cambodia-neang-neak","question":"What does sailed across the sea mean?","verse_no":1,"target_lang":"es","allow_llm":false}' \
    | python3 -m json.tool

APIs on :8097
  GET  / and /lab          — player UI (storyboard theater, karaoke, Ask AI)
  GET  /health
  GET  /api/music/languages         — codes + per-language translation quality
  GET  /api/music/featured
  GET  /api/music/songs
  GET  /api/music/songs/{song_id}
  GET  /api/music/timing/{song_id}  — line + word timings (?duration=&lead_in=)
  GET  /api/music/storyboard/{song_id} — timed scenes + SVG art + narration
                                         (?target_lang=&duration=)
  GET  /api/music/sing/{song_id}    — sing plan: per-line text, window, voice
                                      tag and speech rate (?target_lang=&duration=)
  GET  /api/music/embeds            — YouTube movie/legend lessons (?target_lang=)
  GET  /api/music/embeds/{embed_id} — verses, translations, questions, embed URL
  GET  /api/music/video/{filename}  — local karaoke MP4, honours Range (206)
  POST /api/music/embeds/explain    — one verse: meaning, vocab, prepared Q&A
  POST /api/music/embeds/ask        — ask grammar/vocab about the paused verse
  GET  /api/music/audio/{filename}  — MP3, honours Range (206) so seeking works
  GET  /api/music/clips             — short lyric clips (?song_id=&target_lang=)
  GET  /api/music/videos            — curated lyric videos (?song_id=)
  POST /api/music/translate         — whole song, one language
  POST /api/music/explain           — one line: meaning, vocabulary, examples
  POST /api/music/ask               — ask the AI about the lyrics
  POST /api/music/pronounce         — score a spoken/typed attempt at a lyric line
                                      (practice=english|translation; returns score,
                                      missed/wrong words, corrections, mouth tip)
  POST /api/music/meaning
  POST /api/music/import
  POST /api/music/session/start
  GET  /api/music/session/{session_id}
  POST /api/music/session/{session_id}/play
  POST /api/music/session/{session_id}/pause
  (+ repeat / next / meaning endpoints — see /docs)
