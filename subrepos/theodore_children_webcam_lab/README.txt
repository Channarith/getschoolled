THEODORE CHILDREN WEBCAM LAB

Ages 4–10. The lab combines live face/hand landmarks, finger tracing,
music-lab speech, movement games, cute/hero animation themes, success
fireworks, loving miss gags, and a local-first Fun Score.

The 22 games (Learn / Face & hands / Move) are listed in one catalog
(`game_engine.GAME_MENU`) so the page menu, `/api/child/content`, and the
browser loop cannot drift. Trace a picture has a real glyph for every
A–Z word. Pointer demo (`?demo=1`, or the setup button) drives a
synthetic hand + face on the stage: index finger by default, Alt for a
fist, Shift for a second hand, click for a mouth-O.

START

From the repository root:

  . .venv/bin/activate
  PYTHONPATH=subrepos/theodore_children_webcam_lab/src:packages/shared/src \
    python3 -m uvicorn theodore_children_webcam_lab.main:app --port 8018

Open http://127.0.0.1:8018/

Or use the shared launcher:

  scripts/run_theodore_lab.sh children

PRIVACY

Camera frames, raw audio, face landmarks, hand landmarks, and speech
transcripts are never posted to this lab. MediaPipe inference runs in the
browser. SpeechRecognition is the same browser API used by the music lab;
its vendor handling depends on the browser/OS. Only typed transcript text is
sent to /api/child/pronounce for scoring.

Fun analytics are stored in localStorage by default. An adult must enable
"Share anonymous lab stats" before aggregate-only events are sent. Events
contain activity, age band, timing, outcome, and score; no name, account,
recording, landmarks, or transcript.

VISION ASSETS

By default, MediaPipe Tasks Vision and models load from their pinned public
CDNs. The lab always provides pointer fallback. For self-hosted/offline use,
set AOEP_VISION_ASSET_DIR to a directory containing:

  tasks-vision.mjs
  wasm/
  face_landmarker.task
  hand_landmarker.task

TEST

  cd subrepos/theodore_children_webcam_lab
  PYTHONPATH=src:../../packages/shared/src python3 -m pytest -q

The camera view should use HTTPS or localhost. Camera permissions are commonly
blocked on plain HTTP from a non-local host.

FRESH CONTAINER BUILD

From the repository root (never reuse cached installer/container artifacts):

  docker build --no-cache \
    -f subrepos/theodore_children_webcam_lab/Dockerfile \
    -t theodore-children-webcam-lab:0.49.0 .
