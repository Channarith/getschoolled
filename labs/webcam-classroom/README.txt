Salareen Webcam Classroom (private lab / sub-repo)
==================================================

Purpose
-------
A self-contained sub-repo for building and testing the webcam image-recognition
feature that powers solo and group classes, for BOTH Theodore-led (AI teacher)
sessions and user self-teaching sessions. It adds two capabilities on top of the
platform's existing self-hosted face engine (aoep_shared.vision):

  1. Silhouette detection  - is a human silhouette present in the webcam frame,
                             how much of the frame do they occupy, and where.
  2. User absence tracking - a time-based state machine (present -> looking away
                             -> briefly absent -> absent -> back) that drives the
                             class pacing (pause/resume, or coach nudges).

And it wires xAI's Grok voice agents for responding and natural communication:

  3. xAI (Grok) voice agent - Theodore's spoken replies via Grok chat completions
                             (OpenAI-compatible, streaming) PLUS the Realtime
                             speech-to-speech "Voice Agent" session config
                             (wss://api.x.ai/v1/realtime). Degrades to a grounded,
                             deterministic fallback line when no XAI_API_KEY is set,
                             so the class always "speaks" offline.

Everything is offline-safe: no GPU, no network, and no API key are required to run
the code or the tests. Heavy paths (real frame decode, live Grok) activate only
when the optional deps / keys are present.

Why "sub-repo"
--------------
It ships its own pyproject.toml, tests, and CHANGELOG so it can be developed,
tested, and later extracted independently. It intentionally does NOT change the
production services; instead it exposes a bridge (ClassroomSession.presence_report)
that maps its output straight onto the orchestrator's existing group-class
presence-hold API (LiveRoomStore.report_presence).

Layout
------
  src/webcam_classroom/
    config.py      - env-driven configuration (thresholds + xAI endpoints/models)
    silhouette.py  - single-frame silhouette detection (cv2 / numpy / pure-python)
    absence.py     - per-user absence state machine + group aggregation
    xai_voice.py   - Grok chat voice agent + Realtime voice-agent session builder
    session.py     - ClassroomSession: solo/group x Theodore/self-teaching glue
    demo.py        - offline simulation you can run to see it react
  tests/           - pytest suite (runs with no network/GPU/key)

Install + test
--------------
From the repo root, using the repo venv (see AGENTS.md):

  . .venv/bin/activate
  pip install -e 'labs/webcam-classroom[test]'
  python3 -m pytest labs/webcam-classroom/tests -q

Run the offline demo (prints Theodore / self-coach reactions to a scripted
present -> absent -> back sequence, for solo and group):

  python3 -m webcam_classroom.demo

Configuration (all optional; sensible offline defaults)
-------------------------------------------------------
  XAI_API_KEY        xAI API key. When unset, the voice agent uses the grounded
                     fallback (no network) - tests and the demo still work.
  XAI_BASE_URL       default https://api.x.ai/v1  (OpenAI-compatible chat)
  XAI_REALTIME_URL   default wss://api.x.ai/v1/realtime  (Voice Agent API)
  XAI_TEXT_MODEL     default grok-4.5
  XAI_VOICE_MODEL    default grok-voice-latest
  XAI_VOICE          default eve

  WEBCAM_PRESENT_COVERAGE   default 0.10  (>= this frame coverage = present)
  WEBCAM_PARTIAL_COVERAGE   default 0.03  (>= this but < present = partial)
  WEBCAM_LOOKING_AWAY_AFTER default 4.0   (s of low attention while present)
  WEBCAM_BRIEF_ABSENT_AFTER default 6.0   (s with no silhouette)
  WEBCAM_ABSENT_AFTER       default 20.0  (s with no silhouette -> absent/hold)
