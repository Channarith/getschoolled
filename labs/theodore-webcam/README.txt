Theodore webcam lab (private sub-repo)
======================================

Webcam image recognition for Theodore's classes: silhouette detection, user
absence, and xAI Grok voice agents for responding and natural communication.

This is a PRIVATE, self-contained sub-repository. It lives inside the monorepo
at labs/theodore-webcam so it is easy to iterate on next to the platform, but
it imports nothing from aoep_shared and depends on no platform service, so it
can be lifted into its own private repository at any time with one command
(see "Splitting into a standalone private repo" below).

Nothing here is wired into the shipping product yet. That is deliberate: this
is where the feature gets built and tested before it is promoted into the
perception service and the live-room presence path.


What it does
------------

1. Silhouette detection (src/theodore_webcam/silhouette.py)

   Answers "is a human-shaped body in front of this camera", without
   recognising WHO it is. Identity stays in the platform's perception service;
   this deliberately never matches a face, so a learner can be tracked for
   attendance without biometric identification, and a learner facing away or
   backlit still counts as present.

   A per-pixel adaptive reference frame ("the empty room") is differenced
   against the live frame. The reference learns fast where nothing is
   happening and almost never underneath a detected body. That one rule
   removes the classic background-subtraction failure where a learner who sits
   still for a minute is absorbed into the background and reported absent
   while looking straight at the camera. test_silhouette.py pins this with a
   150-frame motionless learner.

   Blobs are then scored for human-likeness from four shape cues: how much of
   its bounding box the blob fills (a body leaves gaps, a lighting change does
   not), height/width aspect, whether the top band is narrower than the widest
   band (head over shoulders), and size. A light switching on and a chair
   being moved both score below threshold and are covered by tests.

   Stale-background healing. If calibration runs while the learner is already
   at their desk - the common case, since people sit down and then start the
   class - they get baked into the reference, which inverts the sensor:
   sitting there reads as absent, and standing up leaves a permanent
   person-shaped ghost that reads as present. The tell is that a ghost's
   pixels are the room itself, so it looks like its own surroundings, while a
   real body is visibly distinct from the wall behind it. Every candidate blob
   is checked for local contrast against a ring of current-frame pixels around
   it; blobs that differ from the reference but match their surroundings are
   stale background, so they are rejected AND the reference is healed
   underneath them. A bad calibration then corrects itself within a few frames
   instead of lying for the rest of the lesson. Regression-tested both ways:
   the ghost never reports present, and a genuinely motionless learner is
   still never absorbed.

2. User absence (src/theodore_webcam/presence.py)

   Raw per-frame detection is jittery, so detection is debounced into a state
   machine: calibrating -> present -> drifting -> absent -> stale. Leaning out
   of frame to grab a notebook is a "drift" and raises nothing; only an
   absence that outlives the grace window becomes a departure. Staleness (no
   frames arriving at all, i.e. camera off or tab closed) is tracked
   separately from "in shot but no body".

   The tracker accounts present/absent seconds, absence count, longest
   absence, and an attention ratio, which is what the end-of-class report is
   built from. Someone who never appeared is reported as a no-show rather than
   as an absence.

3. Theodore's reaction (src/theodore_webcam/cues.py, classroom.py)

   Presence events become lesson actions paired with the line Theodore should
   actually say. The rule that matters: Theodore does not narrate to an empty
   chair. Cues raised while the learner is away carry voice_turn=false, so the
   voice agent stays silent and the recap is delivered on return instead.

   Solo self-teaching pauses the lesson for the one learner and bookmarks the
   checkpoint. A group class keeps teaching the room, nudges the individual,
   and only puts the whole class on an attendance hold when the share of
   learners on camera drops under quorum (default 0.6).

4. xAI Grok voice agents (src/theodore_webcam/xai_voice.py)

   Real speech-to-speech, not TTS. The browser opens a WebSocket straight to
   wss://api.x.ai/v1/realtime?model=grok-voice-latest so audio never
   round-trips through this service, which is what keeps turn-taking
   sub-second. The API key stays server-side: the lab mints a short-lived
   ephemeral client secret (POST /v1/realtime/client_secrets) and hands the
   browser the token plus the exact session.update payload to send on open.

   Grok gets four classroom function tools - get_presence_state, pause_lesson,
   resume_lesson, recap_checkpoint - so it can ask whether anyone is actually
   there before it starts talking, and steer the lesson itself. Tool calls are
   executed against live session state via POST /v1/voice/tool.

   Presence-driven lines (the pause and the welcome-back recap) are delivered
   with xAI's force_message extension so they are spoken verbatim instead of
   being improvised by the model.

   With no XAI_API_KEY the agent degrades to a deterministic reply grounded in
   presence state plus the on-device voice, so the whole lab is demonstrable
   offline and the teaching loop never hard-depends on a key.


Running it
----------

    python3 -m venv .venv && . .venv/bin/activate
    pip install -e '.[test]'
    make run                     # or: uvicorn theodore_webcam.main:app --port 8210

Then open http://localhost:8210/demo/

The demo runs against a real webcam or a deterministic simulated classroom, so
the pipeline can be exercised end to end on a machine with no camera. Pick the
mode (solo or a 3-learner group class), press Start session, let the
background calibrate for a couple of seconds with nobody in frame, then sit a
learner at the desk and step them away to watch the pause, the attendance
hold, and the welcome-back recap.

To use the real Grok voice agent:

    export XAI_API_KEY=xai-...
    make run

The voice panel switches from "offline-fallback" to "speech-to-speech", the
Connect button opens the realtime socket, and the exact session.update payload
is visible in the demo under "session.update sent to xAI".


Tests
-----

    make test        # 42 tests, no network, no camera, no API key needed
    make lint

Tests render synthetic rooms and human silhouettes with OpenCV rather than
mocking the detector, so the shape scoring is genuinely exercised. Presence
timing uses an injected clock instead of sleeping.


API
---

    GET    /health
    GET    /v1/config                              (never returns the API key)
    POST   /v1/sessions                            {mode, lesson_title, checkpoint, participants[]}
    GET    /v1/sessions
    GET    /v1/sessions/{id}
    DELETE /v1/sessions/{id}                       ends the class, returns the report
    POST   /v1/sessions/{id}/participants
    POST   /v1/sessions/{id}/frames                {participant_id, image}  server-side OpenCV
    POST   /v1/sessions/{id}/signals               {participant_id, detected, ...} on-device
    POST   /v1/sessions/{id}/tick                  expire grace/staleness without a frame
    POST   /v1/sessions/{id}/recalibrate
    GET    /v1/sessions/{id}/report
    GET    /v1/voice/status
    POST   /v1/voice/session                       mints the ephemeral token + session.update
    POST   /v1/voice/respond                       text turn (falls back offline)
    POST   /v1/voice/tool                          executes a Grok function call

Two ingest paths exist on purpose. /frames runs OpenCV server-side and is the
easiest to iterate and debug on. /signals takes a verdict the client already
computed on-device and is the shape a production rollout should use: no image
ever leaves the learner's machine. Both drive identical presence and cue
behaviour, which is asserted in the tests.

Frames are decoded in memory and dropped. Nothing about a learner's camera is
written to disk, and there is no database.


Configuration
-------------

Every knob has a working default; the lab runs with an empty environment.

  Silhouette   WEBCAM_LAB_WORK_WIDTH, WEBCAM_LAB_WARMUP_FRAMES,
               WEBCAM_LAB_DIFF_THRESHOLD, WEBCAM_LAB_BACKGROUND_ALPHA,
               WEBCAM_LAB_OCCLUDED_ALPHA, WEBCAM_LAB_MIN_AREA_RATIO,
               WEBCAM_LAB_MAX_AREA_RATIO, WEBCAM_LAB_HUMAN_SCORE_THRESHOLD,
               WEBCAM_LAB_MAX_SILHOUETTES

  Presence     WEBCAM_LAB_ARRIVE_CONFIRM_SECONDS,
               WEBCAM_LAB_RETURN_CONFIRM_SECONDS,
               WEBCAM_LAB_ABSENCE_GRACE_SECONDS,
               WEBCAM_LAB_PROLONGED_ABSENCE_SECONDS,
               WEBCAM_LAB_STALE_SECONDS

  Classroom    WEBCAM_LAB_GROUP_MIN_PRESENT_RATIO,
               WEBCAM_LAB_SOLO_PAUSE_ON_ABSENCE,
               WEBCAM_LAB_RECAP_AFTER_ABSENCE_SECONDS

  xAI          XAI_API_KEY, XAI_BASE_URL, XAI_REALTIME_URL, XAI_VOICE_MODEL,
               XAI_TEXT_MODEL, XAI_VOICE, XAI_REASONING_EFFORT,
               XAI_TOKEN_TTL_SECONDS, XAI_VAD_THRESHOLD, XAI_VAD_SILENCE_MS,
               XAI_AUDIO_RATE, XAI_ENABLE_WEB_SEARCH

  Service      WEBCAM_LAB_ALLOW_ORIGINS, WEBCAM_LAB_DEMO,
               WEBCAM_LAB_MAX_FRAME_BYTES


Privacy and consent
-------------------

This watches learners through their cameras, so before any of it is promoted
into the product it must sit behind the platform's existing consent scopes
(attention_tracking, and face_recognition only if identity is ever added) and
the regional gates in aoep_shared. Silhouette presence is a lighter-touch
signal than face matching and should stay that way: the promotion path is to
run detection on-device and send only the /signals verdict.


Splitting into a standalone private repo
----------------------------------------

    ./scripts/split_subrepo.sh git@github.com:<org>/theodore-webcam.git

That runs git subtree split on labs/theodore-webcam, preserving only this
directory's history, and pushes it to the private remote you name. Nothing
else in the monorepo has to change, because nothing here imports from it.


Promotion path (when this graduates)
------------------------------------

  silhouette.py  -> aoep_shared/vision/ next to engagement.py, exposed through
                    VisionProvider so the perception service can serve it
  presence.py    -> reuse behind the existing live-room PresencePolicy in
                    aoep_shared/live_room.py, replacing the mobile
                    camera-on-off proxy with a real silhouette verdict
  cues.py        -> orchestrator Director states (REENGAGING already exists)
  xai_voice.py   -> an LLM/voice provider in aoep_shared/providers/ selected by
                    DEPLOY_MODE, alongside the vLLM and Nemotron providers
