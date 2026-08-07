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
  cd /Users/cvanthin/getschoolled
  . .venv/bin/activate
  python3 -m pip install -e 'subrepos/theodore_course_studio[all]'

  # Index + extract training pass (writes data/training_runs/…)
  python3 subrepos/theodore_course_studio/scripts/run_training.py

  # Studio UI
  PYTHONPATH=subrepos/theodore_course_studio/src python3 -m uvicorn \
    theodore_course_studio.main:app --app-dir subrepos/theodore_course_studio/src \
    --port 8040 --host 127.0.0.1

Open: http://127.0.0.1:8040/studio

Workflow
--------
1. Run training scan — walks all pdf/pptx, parses labels, extracts pages.
2. Review pages — Keep / Reject; add comments for Theodore training.
3. Build course — from Good/Better sources, skipping rejected pages (~20 slides).
4. Teach / present — Theodore narrates slides; tweak learner profile knobs
   (engagement, literacy, attention, fatigue, confusion, pace, accessibility).

API (high level)
----------------
  GET  /health
  GET  /studio
  GET  /api/studio/corpus
  GET  /api/studio/sources/{source_id}
  POST /api/studio/training/run
  POST /api/studio/pages/verdict
  POST /api/studio/comments
  GET  /api/studio/courses
  POST /api/studio/courses/build
  POST /api/studio/teach/start
  POST /api/studio/teach/advance
  POST /api/studio/teach/profile

Tests
-----
  PYTHONPATH=subrepos/theodore_course_studio/src python3 -m pytest \
    subrepos/theodore_course_studio/tests -q

Promotion note
--------------
Keep studio logic self-contained. When stable, lift adapters into
aoep_shared / orchestrator / apps/web / apps/mobile — do not fork production
paths inside this experiment.

Teach / present (gap-focused)
-----------------------------
Theodore sessions diagnose prior knowledge (self-reported known objectives +
stored mastery), then prioritize gap slides. Pop quizzes, summary quizzes,
match-term games, fade animations, and video/audio media hooks are available
in the studio UI. Pass threshold for summary quizzes is 70% by default.
