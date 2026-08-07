Theodore Course Studio (experiment subrepo)
===========================================

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
