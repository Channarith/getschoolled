Theodore Course Studio (experiment subrepo)
===========================================

EARLY LEARNING (DEFAULT)
------------------------
The studio now focuses first on simple Pre-K through Grade 2 classes:
  - Pre-K: first colors; circles/squares/triangles
  - Kindergarten: counting 1-10; A/B/C letter sounds
  - Grade 1: five sight words; addition within 10
  - Grade 2: story sequence; animal habitats

Open /studio, choose a level + lesson in "Make a children's lesson", then click
"Make & teach". Every lesson uses:
  - one short idea per screen (large child-friendly words)
  - an offline colorful SVG picture
  - an offline animated motion/video card
  - carefully leveled read-aloud narration (not paraphrased by xAI)
  - a movement or point-and-say activity
  - Pop/Summary quiz and game controls

Theodore reads each screen automatically when auto-speak is checked. "Read
aloud" repeats it; "Watch video" switches from the still picture to the
self-contained animated visual. No network, media downloads, or API key is
needed. The xAI agent remains available for the child's explicit "Ask Theodore"
questions, but it does not rewrite the curated child narration into harder text.

Adult PDF/PPTX corpus generation is still available under the collapsed
"Advanced: build from adult Good/Better source files" panel.

TEACHING IN OTHER LANGUAGES
---------------------------
Choosing a language changes the WORDS, not just the voice. Sending English text
to a Spanish voice only mispronounces English at the child, so the studio keeps
text and audio in the same language and tells you which one you are getting:

  curated  Hand-written per language. Spanish (es), Khmer (km), and Mandarin
           Chinese (zh) each ship all eight lessons. Khmer and Mandarin are
           marked "pending native-speaker review" in the UI until a native
           teacher signs off.
  xai      Real Grok translation, constrained to tiny child vocabulary and
           cached under data/i18n/ so later runs need no network. Needs
           XAI_API_KEY. Shown as "review before classroom use".
  english  Honest fallback. Words AND audio stay English, and the UI says so.

Phonics and sight words are never machine translated: "A is for apple" cannot
become "A is for manzana", because manzana starts with M. Those lessons carry
properly localized variants instead, and each language teaches its OWN script:
  - Spanish teaches Spanish phonics: A de avion, B de bota, C de casa
  - Khmer teaches Khmer consonants with their own picture symbols: ក, ខ, គ
  - Mandarin teaches pictographic characters: 人, 山, 水 (and sight characters
    我, 你, 好, 是, 大)
A curated lesson may override the picture symbol so the visual matches the
native script instead of the English A/B/C card.

Audio itself never comes from xAI. Grok writes/translates text; speech comes
from the gateway chain (ElevenLabs -> edge-tts) or the device voice, using the
language of the words actually on screen.

Screens
-------
docs/screens/theodore_course_studio.webp
  (also copied under this subrepo at docs/screens/theodore_course_studio.webp)
  Early-learning Make & teach panel, teach stage, corpus review, studio tuning.

Regenerate after UI changes:
  python3 scripts/render_lab_docs_screenshots.py

STEP BY STEP — early-learning Make & teach (from repo root)
-----------------------------------------------------------
No corpus download and no API key required for this path.

Step 0 — activate the project venv

  cd "$(git rev-parse --show-toplevel)"
  . .venv/bin/activate
  python3 -m pip install -e 'subrepos/theodore_course_studio[all]'

Step 1 — run the automated tests

  PYTHONPATH=subrepos/theodore_course_studio/src \
    python3 -m pytest subrepos/theodore_course_studio/tests -q

Step 2 — start the studio UI

  PYTHONPATH=subrepos/theodore_course_studio/src python3 -m uvicorn \
    theodore_course_studio.main:app --app-dir subrepos/theodore_course_studio/src \
    --port 8040 --host 127.0.0.1

  Check:  curl -s http://127.0.0.1:8040/health
  Open:   http://127.0.0.1:8040/studio

Step 3 — make a children's lesson

  In the orange "Make a children's lesson" panel:
    1. Choose Level (e.g. Kindergarten)
    2. Choose Topic (e.g. Counting 1-10)
    3. Choose Language (en / es / km / zh …)
    4. Click "Make & teach"

  Expect a teach stage with large kid words, an offline SVG picture, narration,
  and a movement / point-and-say activity. Compare against
  docs/screens/theodore_course_studio.webp.

Step 4 — teach the lesson

  - Auto-speak (checked) → Theodore reads each screen
  - "Read aloud" → repeat the current narration
  - "Watch video" → switch to the animated motion card
  - Pop / Summary quiz and Play game when offered
  - "Ask Theodore" → xAI if XAI_API_KEY is set, else local fallback

Step 5 — (optional) adult corpus / certification path

  Collapse "Advanced: build from adult Good/Better source files" for PDF/PPTX
  training, or use the Certification prep panel for CA DMV / food-handler
  short lessons. Every cert segment ships a full multimodal kit: offline SVG
  picture, animated motion/"Watch video" clip, friendly examples, curated
  multiple-choice quiz, and a short game, plus read-aloud narration. Tune
  learner profile preferences (images / text / video / examples / quiz / games)
  so Theodore nudges the paths that fit how the person learns. Ask Theodore
  anytime — it interrupts speech and answers from the current page. Full
  copy/paste for that path is under SETUP & RUN below.

SETUP & RUN (copy/paste — full / adult corpus)
----------------------------------------------
Prereqs: Python 3.11+ (3.12 fine). Everything below works OFFLINE.

  # 0) from the repo root (/workspace in cloud, ~/getschoolled on your Mac)
  cd "$(git rev-parse --show-toplevel)"

  # 1) make + activate a virtualenv (one time)
  python3 -m venv .venv
  . .venv/bin/activate            # Windows: .venv\Scripts\activate

  # 2) install the studio (pdf+pptx+test extras)
  python3 -m pip install -e 'subrepos/theodore_course_studio[all]'

  # 3) point at your labeled corpus (folders of Good/Bad/Moderate PDFs+PPTX)
  export THEODORE_COURSE_CORPUS_ROOT=~/Downloads/drive-download-20260807T154004Z-1-001
  export THEODORE_COURSE_STUDIO_DATA="$PWD/subrepos/theodore_course_studio/data"

  # 4) (optional) natural voice — xAI Grok + neural TTS. Skip = offline fallback.
  export XAI_API_KEY=xai-...           # put this in config/local.env, NOT in git
  export SPEECH_BASE_URL=http://127.0.0.1:8002

  # 5) START THE STUDIO UI
  PYTHONPATH=subrepos/theodore_course_studio/src python3 -m uvicorn \
    theodore_course_studio.main:app --app-dir subrepos/theodore_course_studio/src \
    --port 8040 --host 127.0.0.1
  # then open  http://127.0.0.1:8040/studio

In the browser (top-to-bottom in the page):
  1. Run training scan       — indexes + extracts your corpus
  2. Offline long trainer    — (optional) learns Good-vs-Bad quality model
  3. Review pages            — Keep / Reject (⌀ = circle+line), add comments
  4. Build course            — pick a language, generate a ranked lesson
  5. Start teach             — Theodore presents; Pop/Summary quiz; Play game;
                               Ask Theodore (xAI or offline); auto-speak TTS

Long OFFLINE training (hours) without the UI:
  python3 subrepos/theodore_course_studio/scripts/run_offline_trainer.py --hours 8
  # resume later:
  python3 subrepos/theodore_course_studio/scripts/run_offline_trainer.py \
      --resume-run-id offline-<id> --hours 4 --no-scan

Run the tests:
  PYTHONPATH=subrepos/theodore_course_studio/src python3 -m pytest \
    subrepos/theodore_course_studio/tests -q

Note on docs: this project convention is plain text (no new .md files), so this
README.txt is the canonical guide — there is no README.md.

TROUBLESHOOTING
---------------
"I don't see the language picker or the xAI voice"
  Your checkout predates them. They shipped in v0.46.33. Update and restart:
      git pull origin main
      # restart uvicorn (step 5 above), then HARD-refresh the browser
  Confirm with:
      curl -s http://127.0.0.1:8040/health          # -> "languages": 27
      curl -s http://127.0.0.1:8040/api/studio/voice/status
  voice.provider is "xai" only when XAI_API_KEY is exported in the SAME shell
  that runs uvicorn; otherwise it reads "local-fallback" (still works).

"The generated course is full of junk slides"
  Cover pages, tables of contents, reference lists and running headers are
  filtered out at build time (see content_quality.py). Rebuild the course after
  updating. The build side-car lists what was dropped:
      cat subrepos/theodore_course_studio/data/courses/<course_id>.build.json
  Anything still bad: mark those pages Reject (⌀) in step 3 and rebuild, then
  run the offline trainer so the quality model learns your preferences.

"Audio is silent / robotic"
  Without a speech gateway on SPEECH_BASE_URL the browser's built-in voice is
  used. Start the speech service (:8002) for neural ElevenLabs/edge-tts audio.


Purpose
-------
Sandbox for building Theodore-taught courses from the manually labeled
Good / Bad / Moderate / Better corpus (Communication, Leadership, Sexual
Harassment). Page-level rejects (circle + line-through) and free-form review
comments feed training. Profile scoring reshapes teach/present delivery.
Promising pieces graduate into the main web/mobile app later — this subrepo
stays an experiment lab like theodore_webcam_lab.

Labeled corpus (default)
------------------------
  ~/Downloads/drive-download-20260807T154004Z-1-001/
    3. Communication/
    Leadership/
    Sexual Harassment/

Override with:
  export THEODORE_COURSE_CORPUS_ROOT=/path/to/labeled/folders
  export THEODORE_COURSE_STUDIO_DATA=/path/to/studio/data   # optional

Filename quality tokens (underscores OK): Good, Better, Moderate, Bad.
Policy: Good/Better → incorporate; Bad → reject; Moderate/Unlabeled → review queue.

Page marks
----------
In the studio UI, Reject ⌀ = the circle+line "we don't like this page" mark.
Keep = like / unmarked. Comments on a source or page are stored for training.

Quick start
-----------
  cd /Users/cvanthin/getschoolled   # or /workspace in cloud agents
  . .venv/bin/activate
  python3 -m pip install -e 'subrepos/theodore_course_studio[all]'

  # Index + extract training pass (writes data/training_runs/…)
  python3 subrepos/theodore_course_studio/scripts/run_training.py

  # Offline LONG trainer (no network / no LLM) — run for hours on the labeled corpus:
  export THEODORE_COURSE_CORPUS_ROOT=~/Downloads/drive-download-20260807T154004Z-1-001
  export THEODORE_COURSE_STUDIO_DATA=subrepos/theodore_course_studio/data
  python3 subrepos/theodore_course_studio/scripts/run_offline_trainer.py --hours 8
  # Resume later:
  python3 subrepos/theodore_course_studio/scripts/run_offline_trainer.py \
      --resume-run-id offline-<id> --hours 4 --no-scan

  # Studio UI
  PYTHONPATH=subrepos/theodore_course_studio/src python3 -m uvicorn \
    theodore_course_studio.main:app --app-dir subrepos/theodore_course_studio/src \
    --port 8040 --host 127.0.0.1

Open: http://127.0.0.1:8040/studio

Offline long trainer
--------------------
Fully offline quality loop:
  1) Scan/extract labeled PDFs/PPTXs (or reuse cached extracts).
  2) Build a page bank labeled Good/Better (+1) vs Bad/reject (-1).
  3) For many epochs: fit a local quality model → assemble a scored course →
     mutate generation policy → checkpoint under data/offline_training/.
  4) CourseBuilder loads data/models/quality_model.json and ranks pages by score.

No GPU, no API keys, no network required after the corpus is local.
Use --hours for overnight runs; --epochs for fixed budgets; --resume-run-id to continue.

Languages + xAI voice
---------------------
All 27 platform languages (aoep_shared.languages, including Khmer) are available
in the studio language picker and on StudioCourse.language.

Theodore voice agent:
  - Uses XAI_API_KEY / Grok when configured (aoep_shared TeacherVoiceAgent or
    direct chat completions).
  - Always degrades to deterministic local-fallback text offline.
  - Spoken audio: speech gateway (:8002) GET/POST /tts when available, else
    browser/device speechSynthesis. Chain: ElevenLabs → edge-tts → device.

Env:
  XAI_API_KEY, XAI_BASE_URL, XAI_MODEL, XAI_TIMEOUT_S
  SPEECH_BASE_URL (default http://127.0.0.1:8002)

Where to put XAI_API_KEY (never commit it)
------------------------------------------
  - Local Mac: config/local.env (gitignored; copy from config/local.env.example)
      XAI_API_KEY=xai-...
    then: set -a; . config/local.env; set +a
  - Cloud agents: Cursor Dashboard -> Cloud Agents -> Secrets (injected as env).
  - Cluster: the aoep-secrets k8s Secret (see release-and-deploy skill).

Verify the key is live:
  curl -sS https://api.x.ai/v1/models -H "Authorization: Bearer $XAI_API_KEY"
  curl -sS http://127.0.0.1:8040/api/studio/voice/status

`voice.provider` reports "xai" once the key is set. If the xAI API is
unreachable (blocked egress, rate limit, bad key) the agent still answers with
deterministic local-fallback text — teaching never hard-fails.

Workflow
--------
1. Run training scan — walks all pdf/pptx, parses labels, extracts pages.
2. Run offline long trainer (hours/epochs) to improve page ranking + course picks.
3. Review pages — Keep / Reject; add comments for Theodore training.
4. Build course — from Good/Better sources, ranked by the learned model (pick language).
5. Teach / present — Theodore (xAI or offline fallback) narrates; TTS speaks;
   Ask Theodore for conversational help; quizzes/games; profile knobs.

API (high level)
----------------
  GET  /health
  GET  /studio
  GET  /api/studio/languages
  GET  /api/studio/voice/status
  GET  /api/studio/tts/url
  GET  /api/studio/corpus
  GET  /api/studio/sources/{source_id}
  POST /api/studio/training/run
  POST /api/studio/training/offline
  GET  /api/studio/training/offline/status
  POST /api/studio/pages/verdict
  POST /api/studio/comments
  GET  /api/studio/courses
  POST /api/studio/courses/build
  POST /api/studio/teach/start
  POST /api/studio/teach/advance
  POST /api/studio/teach/profile
  POST /api/studio/teach/language
  POST /api/studio/teach/voice/respond
  POST /api/studio/teach/voice/present
  GET  /api/studio/tuning
  PATCH /api/studio/tuning
  POST /api/studio/tuning/preset/{name}
  GET  /api/studio/telemetry

Tuning and telemetry
--------------------
studio_tuning.StudioTuning is one frozen dataclass of 30+ pipeline knobs
(quiz/game pass scores, slide/narration shaping, checkpoint pacing, course-size
caps, content-quality thresholds, voice/TTS behaviour, engagement-game rotation).
It loads from AOEP_STUDIO_* env vars, supports live PATCH, and ships named
presets (balanced, kids_fast, cert_strict, adult_deep). quality_telemetry
records teach/build signals (courses built, slides taught, quiz/game starts +
passes by kind, voice/TTS turns, checkpoint pauses, review keep/reject, offline
epochs, quality rejects) and a blended engagement_score at GET
/api/studio/telemetry. Engagement games rotate match_term -> order_steps ->
spot_gap via engagement.pick_game_for_slide.

Tests
-----
  PYTHONPATH=subrepos/theodore_course_studio/src python3 -m pytest \
    subrepos/theodore_course_studio/tests -q

Promotion note
--------------
Keep studio logic self-contained. When stable, lift adapters into
aoep_shared / orchestrator / apps/web / apps/mobile — do not fork production
paths inside this experiment. Realtime S2S can use aoep_shared.xai_realtime
ephemeral tokens when promoting.

Teach / present (gap-focused)
-----------------------------
Theodore sessions diagnose prior knowledge (self-reported known objectives +
stored mastery), then prioritize gap slides. Pop quizzes, summary quizzes,
match-term games, fade animations, and video/audio media hooks are available
in the studio UI. Pass threshold for summary quizzes is 70% by default.
