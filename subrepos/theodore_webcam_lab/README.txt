Theodore Webcam Lab (private-ready subproject)
==============================================

Purpose
-------
This subproject isolates webcam-recognition and natural voice-agent prototyping
for Theodore AI teaching and self-teaching flows, without changing production
classroom services.

Feature scope
-------------
- Solo and group class webcam evaluation
- Silhouette detection
- Learner absence detection with grace periods
- xAI voice-agent response integration (OpenAI-compatible API), plus local
  fallback when keys/network are unavailable
- Realtime-optimized chat/audio turn handling with short-session memory, fast
  response mode, response caching, and latency metadata for low-lag conversations
- 26-language voice-agent support for multilingual teaching
- Webcam-audio transcript absorption for answer understanding + feedback
- Webcam reinforcement games/challenges scored from live signals:
  focus streak, confidence smile, and integrity guard
- Group-lesson student window monitoring with per-student intervention severity
  and lesson alerts/messages for missing or cheating learners
- Live quality metrics + chart-ready series for every student window (distance,
  light, image quality, expression/behavior, mic quality, noise filtering)

API highlights
--------------
- POST /api/theodore/webcam/evaluate
- GET  /api/theodore/webcam/live-metrics/{session_id}
- GET  /theodore/webcam/live-monitor/{session_id}
- POST /api/theodore/voice/respond
- GET  /api/theodore/voice/languages
- POST /api/theodore/voice/ask-question
- POST /api/theodore/voice/absorb-audio-answer
- POST /api/theodore/webcam/games/challenge
- POST /api/theodore/webcam/games/attempt

Screens
-------
- docs/screens/theodore_webcam_live_monitor.webp        (live monitor dashboard)
- docs/screens/theodore_webcam_monitor_xss_escaped.webp (escaped-injection check)
- docs/demos/theodore_webcam_live_monitor_demo.mp4      (walkthrough recording)

HOW TO TEST
===========
Every command below is run from the REPO ROOT and is copy-pasteable. Nothing here
needs an API key, a GPU, or a webcam: the lab ships a deterministic frame seeder
and the voice agent falls back locally when XAI_API_KEY is unset.

Step 0 - prerequisites (once)
-----------------------------
   . .venv/bin/activate
   python3 -m pip install "fastapi>=0.111,<0.116" "pydantic>=2.7,<3" \
       "uvicorn[standard]>=0.30,<0.35" "pytest>=8.2,<9" "httpx>=0.27,<0.28"

Step 1 - automated tests (fastest confidence check, ~1 second)
--------------------------------------------------------------
   python3 -m pytest subrepos/theodore_webcam_lab/tests -q

   EXPECT: "54 passed". These cover the analyzer, games, voice agent, the API,
   the 24/7 training orchestrator, and one regression test per audited bug fix
   (see tests/test_audit_regressions.py).

Optional lint gate (matches repo CI config):
   python3 -m ruff check subrepos/theodore_webcam_lab      # EXPECT: All checks passed!

Step 2 - start the lab API
--------------------------
   python3 -m uvicorn theodore_webcam_lab.main:app \
       --app-dir subrepos/theodore_webcam_lab/src --host 0.0.0.0 --port 8015

   Leave this running in its own terminal. Confirm it is up from another shell:
   curl -s http://127.0.0.1:8015/health        # EXPECT: {"service":"theodore-webcam-lab","status":"ok"}

   Port 8015 already taken? Pass a different --port and reuse it below via
   --base-url http://127.0.0.1:<port>.

Step 3 - seed demo webcam frames
--------------------------------
   python3 subrepos/theodore_webcam_lab/scripts/seed_demo_session.py

   EXPECT: "Seeded 'demo-session' with 60 frames." plus the monitor URL.
   Add --rolling to keep posting one frame per second so the dashboard animates
   while you watch it (Ctrl-C to stop).

   Keep the default 60 frames: student-b's cheating signal only trips after the
   sustained gaze-away window (45s of simulated time), so a shorter seed will
   correctly show no cheating alert yet.

Step 4 - open the live monitor in a browser
-------------------------------------------
   http://127.0.0.1:8015/theodore/webcam/live-monitor/demo-session

   EXPECT (compare against docs/screens/theodore_webcam_live_monitor.webp):
   - Top-left summary cards: avg distance (m), light quality, image quality,
     behavior score, mic quality, noise filter. Values refresh every second.
   - Top-right "Lesson Alerts": one [medium] group-intervention alert and one
     [high] cheating alert naming student-b.
   - "Student Windows (Live Metrics)": TWO windows side by side, each with
     quality bars plus a live line chart (green=light, blue=image, amber=mic).
   - Window #1 student-a: State present, Cheating false, and Mic quality / Noise
     filter showing "n/a" on dropout frames. That "n/a" is the point: a missing
     sample stays a gap in the chart instead of being dropped and shifting later
     points onto the wrong timestamp.
   - Window #2 student-b: Cheating true (eyes down + phone + typing audio).

   Prefer to check the raw numbers instead of the UI:
   curl -s http://127.0.0.1:8015/api/theodore/webcam/live-metrics/demo-session | python3 -m json.tool

   Every metric series is index-aligned with timestamps_ms; missing samples are
   null. To assert that alignment in one line:
   curl -s http://127.0.0.1:8015/api/theodore/webcam/live-metrics/demo-session \
     | python3 -c "import json,sys; p=json.load(sys.stdin)['participants'][0]; \
print('aligned:', len(p['timestamps_ms'])==len(p['microphone_quality_score']))"

Step 5 - verify the injection (XSS) fix
---------------------------------------
   curl -s "http://127.0.0.1:8015/theodore/webcam/live-monitor/%3Cimg%20src=x%20onerror=alert(1)%3E" \
     | grep -o "Theodore Live Monitor - [^<]*"

   EXPECT: "Theodore Live Monitor - &lt;img src=x onerror=alert(1)&gt;"
   (escaped). In a browser, open the same path un-encoded and confirm NO alert
   dialog appears and the payload shows as literal text - see
   docs/screens/theodore_webcam_monitor_xss_escaped.webp.

Step 6 - chat / audio conversation endpoints
--------------------------------------------
   curl -s -X POST http://127.0.0.1:8015/api/theodore/voice/respond \
     -H 'content-type: application/json' \
     -d '{"class_mode":"solo","learner_message":"Explain photosynthesis",
          "language_code":"en","session_id":"chat-1","fast_mode":true}' \
     | python3 -m json.tool

   EXPECT: provider "local-fallback" without XAI_API_KEY (set the key for real
   xAI replies), plus latency_ms, cache_hit, and should_stream_audio. Re-send the
   exact same request in the same session and cache_hit flips to true - that is
   the realtime dedup cache (default 20s TTL). The local fallback answers in
   under a millisecond so latency_ms reads 0 either way; with a real key the
   cached path is what skips the network round-trip. Replies are scoped per
   session_id, so a different session never receives another learner's reply.

   List supported teaching languages (EXPECT 26):
   curl -s http://127.0.0.1:8015/api/theodore/voice/languages | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"

   Ask a question, then score a spoken answer transcript:
   curl -s -X POST http://127.0.0.1:8015/api/theodore/voice/ask-question \
     -H 'content-type: application/json' \
     -d '{"class_mode":"solo","language_code":"es","topic":"gravity"}' | python3 -m json.tool
   curl -s -X POST http://127.0.0.1:8015/api/theodore/voice/absorb-audio-answer \
     -H 'content-type: application/json' \
     -d '{"class_mode":"solo","language_code":"es","question":"What is gravity?",
          "audio_transcript":"Gravity pulls objects toward each other."}' | python3 -m json.tool

Step 7 - webcam reinforcement games
-----------------------------------
   Create a challenge (returns challenge_id), then post frames as an attempt:
   curl -s -X POST http://127.0.0.1:8015/api/theodore/webcam/games/challenge \
     -H 'content-type: application/json' \
     -d '{"session_id":"game-1","mode":"solo","learning_prompt":"Explain inertia",
          "preferred_game_type":"focus_streak"}' | python3 -m json.tool

   EXPECT: a challenge_id plus instruction and target_duration_ms. Feed that id
   to /api/theodore/webcam/games/attempt with webcam signals to get passed,
   score_delta, total_score and streak. tests/test_games.py shows worked
   payloads for the pass, fail, and paused-training cases.

Step 8 - 24/7 training orchestrator (dry run, no side effects)
-------------------------------------------------------------
   PYTHONPATH=subrepos/theodore_webcam_lab/src python3 -m theodore_webcam_lab.training_orchestrator \
     --runbook subrepos/theodore_webcam_lab/training/vision_training_runbook.json \
     --state /tmp/theodore_training_state.json --dry-run --iterations 1

   EXPECT: one JSON line for the due "quality-heartbeat" task with exit_code 0.
   Drop --dry-run to actually execute tasks; see VISION_TRAINING_OPERATIONS.txt
   for the continuous 24/7 launch procedure.

Troubleshooting
---------------
- "No metrics yet. Start posting /evaluate frames." on the monitor page: the
  session has no data. Run Step 3 (session id in the URL must match).
- Address already in use: another process holds the port. Choose a new --port
  and reuse it via --base-url; find the owner with `lsof -ti :8015` and kill
  that specific PID only.
- ModuleNotFoundError for fastapi/pytest: re-run Step 0 inside the venv.
- Charts look flat: seed with --rolling so new frames keep arriving.

Reference
---------
- VISION_TRAINING_OPERATIONS.txt - SOTA/proprietary training blueprint and the
  continuous 24/7 launch procedure (Step 8 above is the dry run only).
- training/vision_training_runbook.json - the 24/7 agent runbook. Enable tasks by
  flipping "enabled": true as each training script lands.
- scripts/seed_demo_session.py - the demo frame seeder used in Step 3.
- tests/ - executable specifications; test_audit_regressions.py documents each
  fixed bug with a reproduction.
