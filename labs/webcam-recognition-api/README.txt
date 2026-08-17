===========================================================================
 AOEP Webcam Recognition Lab  (labs/webcam-recognition)
===========================================================================

A self-contained sub-project (a "sub repo" that lives inside the monorepo but
builds, tests, and runs on its own) for developing and testing the camera-driven
classroom features before they graduate into the main platform services:

  * Silhouette detection    - find the whole-body human outline in a frame so
                              "is a person there?" works even when the face is
                              turned away, leaning out, or poorly lit.
  * User absence / presence - a debounced state machine that turns noisy
                              per-frame signals into stable PRESENT / AWAY
                              transitions, with attendance timers.
  * Solo and group classes  - per-learner or per-roster presence + attendance,
                              for Theodore (AI) teaching and learner self-study.
  * xAI (Grok) voice agent  - natural spoken responses to classroom events
                              (welcome, pause on absence, welcome back, nudge),
                              with a graceful offline fallback.
  * Teaching conductor      - turns presence/engagement into teaching actions
                              (pause / resume / greet / nudge / answer), phrased
                              by the voice agent.

Why a separate sub-project?
  It keeps this experimental, camera + external-API feature isolated from the
  production services so it can be iterated and tested independently, then lifted
  into aoep_shared / the perception + orchestrator services once proven. It reuses
  the monorepo's aoep_shared face engine (YuNet + SFace) when importable, and
  degrades cleanly when it (or OpenCV, or a network) is not available.


---------------------------------------------------------------------------
 Layout
---------------------------------------------------------------------------
  pyproject.toml                      installable package metadata (+ extras)
  requirements.txt                    pinned deps (fastapi + opencv + test)
  README.txt                          this file
  src/webcam_recognition/
    config.py                         env-driven LabConfig (xAI key, thresholds)
    silhouette.py                     silhouette geometry core + OpenCV HOG detector
    presence.py                       debounced user-absence state machine
    session.py                        SoloSession + GroupSession (attendance)
    voice_agent.py                    xAI (Grok) agent w/ offline fallback + streaming
    teaching.py                       TeachingConductor (event -> action -> speech)
    app.py                            FastAPI app (analyze, sessions, agent, demo)
    static/demo.html                  in-browser webcam demo (no build step)
  scripts/demo.py                     headless end-to-end demo (no camera)
  tests/                              pytest suite (pure logic + API)


---------------------------------------------------------------------------
 Install
---------------------------------------------------------------------------
From the monorepo root (reuses the repo .venv):

  . .venv/bin/activate
  python3 -m pip install -r labs/webcam-recognition/requirements.txt

Or install just this sub-project:

  python3 -m pip install -e "labs/webcam-recognition[vision,test]"


---------------------------------------------------------------------------
 Run
---------------------------------------------------------------------------
Headless demo (offline, no camera, no key):

  python3 labs/webcam-recognition/scripts/demo.py

Web demo (open http://localhost:8090 in a browser and allow the camera):

  cd labs/webcam-recognition
  PYTHONPATH=src uvicorn webcam_recognition.app:app --port 8090

  The page captures webcam frames locally and posts a JPEG to /analyze; the
  server runs silhouette (and, if available, face) recognition, drives the
  presence state machine, and Theodore speaks via the browser's speech synthesis.


---------------------------------------------------------------------------
 xAI (Grok) voice agent
---------------------------------------------------------------------------
The agent uses xAI's OpenAI-compatible chat-completions API. Configure with:

  export XAI_API_KEY=sk-...              # enables the real agent
  export XAI_MODEL=grok-2-latest         # default
  export XAI_BASE_URL=https://api.x.ai/v1

With no key set, a deterministic, context-grounded fallback is used so the whole
teaching loop still responds (offline / CI safe). "Voice" = the agent produces
the words; a TTS layer (ElevenLabs / edge-tts / on-device, already in the
platform) renders audio -- the reply carries text + an SSML hint + voice/persona.


---------------------------------------------------------------------------
 Test
---------------------------------------------------------------------------
  . .venv/bin/activate
  python3 -m pytest labs/webcam-recognition/tests -q

The pure logic (silhouette geometry, presence, sessions, agent fallback,
conductor) is fully covered without a camera, model download, or network. The
xAI transport is unit-tested via a mocked transport.


---------------------------------------------------------------------------
 Config reference (environment variables)
---------------------------------------------------------------------------
  XAI_API_KEY               xAI key; empty => deterministic fallback
  XAI_BASE_URL              default https://api.x.ai/v1
  XAI_MODEL                 default grok-2-latest
  XAI_TIMEOUT_S             default 30.0
  AGENT_NAME                agent persona; default "Theodore"
  ABSENT_GRACE_S            unseen seconds before AWAY; default 4.0
  PRESENT_GRACE_S           seen seconds before PRESENT; default 1.0
  MIN_SILHOUETTE_COVERAGE   min frame fraction for a valid body box; default 0.03
  HOG_HIT_THRESHOLD         OpenCV HOG hit threshold; default 0.0
