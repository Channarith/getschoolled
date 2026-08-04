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
- Tunable recognition accuracy: every threshold, calibration and scoring weight is
  a named knob (env, live API, or room preset) - see RECOGNITION TUNING below
- Sobel binary-edge imaging for sharpness/blur and exposure analysis, computed
  on-device or server-side from a posted luminance grid

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
- GET   /api/theodore/voice/tuning                     (read xAI voice knobs)
- PATCH /api/theodore/voice/tuning                     (change voice knobs live)
- POST  /api/theodore/voice/tuning/preset/{name}       (apply a voice preset)
- GET   /api/theodore/vision/tuning                    (read all knobs + presets)
- PATCH /api/theodore/vision/tuning                    (change knobs live)
- POST  /api/theodore/vision/tuning/preset/{name}      (apply a room preset)
- POST  /api/theodore/vision/imaging/analyze           (Sobel + exposure report)

Screens
-------
- docs/screens/theodore_webcam_live_monitor.webp        (live monitor dashboard)
- docs/screens/theodore_webcam_monitor_xss_escaped.webp (escaped-injection check)
- docs/demos/theodore_webcam_live_monitor_demo.mp4      (walkthrough recording)

RECOGNITION TUNING
==================
Nothing about recognition accuracy is hardcoded any more. Every threshold,
calibration constant and scoring weight lives in VisionTuning
(src/theodore_webcam_lab/vision_tuning.py) and can be set three ways:

  1. Environment - AOEP_VISION_<KNOB_NAME_UPPERCASE>, e.g.
       AOEP_VISION_SOBEL_BINARY_THRESHOLD=0.22
       AOEP_VISION_LIGHT_UNDEREXPOSED_LUMA=0.18
       AOEP_VISION_AUDIO_MAX_NOISE_LEVEL_DB=68
     Timing/session knobs use the same prefix via AnalyzerPolicy.from_env(),
     e.g. AOEP_VISION_GAZE_AWAY_GRACE_MS=20000.
  2. Live API - PATCH /api/theodore/vision/tuning with {"knobs": {...}}. Takes
     effect on the next frame; no restart. Unknown knobs and out-of-range values
     are rejected with 422 rather than silently ignored.
  3. Room presets - POST /api/theodore/vision/tuning/preset/{name}:
       balanced            shipping defaults
       low_light           dim rooms: accepts darker, softer frames
       bright_room         backlit rooms: clamps blown highlights
       noisy_room          shared spaces: relaxes the noise ceiling but DEMANDS
                           effective noise suppression, and raises the
                           keyboard-audio bar so chatter is not read as cheating
       high_accuracy       proctoring: crisp, well-lit, well-framed video only
       wide_angle_laptop   laptop FOV: re-calibrates the face-ratio to metres

Knob groups
-----------
Lighting / exposure   light_underexposed_luma, light_overexposed_luma,
                      light_max_clipped_black_ratio, light_max_clipped_white_ratio,
                      light_min_quality, light_default_quality
Sharpness (Sobel)     sobel_binary_threshold, sobel_min_edge_density,
                      sharpness_reference_gradient, sharpness_min_quality,
                      sharpness_gradient_percentile
Distance calibration  distance_reference_face_ratio, distance_reference_metres,
                      distance_min_face_ratio, distance_min_metres,
                      distance_max_metres, distance_too_close_m, distance_too_far_m
Detection thresholds  silhouette_foreground_threshold, silhouette_motion_threshold,
                      silhouette_consecutive_frames, gaze_frontal_min_threshold,
                      gaze_down_min_threshold, typing_activity_min_threshold,
                      keyboard_typing_audio_min_threshold
Detection scoring     image_detection_confidence_weight, image_liveness_weight,
                      image_no_face_penalty, image_default_confidence_with_face,
                      image_default_confidence_no_face, image_min_quality
Behaviour scoring     behavior_happy_weight, behavior_known_expression_weight,
                      behavior_unknown_expression_weight, behavior_focus_weight,
                      behavior_integrity_weight
Audio / noise         audio_snr_floor_db, audio_snr_span_db, audio_noise_clean_db,
                      audio_noise_loud_db, audio_clipping_penalty,
                      audio_min_mic_quality, audio_min_noise_filter_effectiveness,
                      audio_max_noise_level_db, audio_min_snr_db

Sobel binary imaging
--------------------
A 3x3 Sobel Gx/Gy pass produces per-pixel gradient magnitudes, normalised to
0..1 and thresholded by sobel_binary_threshold into an edge mask. edge_density is
the fraction of interior pixels above that threshold. Sharpness reads a HIGH
PERCENTILE of the gradient (sharpness_gradient_percentile, default 95) rather
than the mean, because a mean cannot separate a sharp frame whose detail sits on
a few percent of pixels from an evenly blurred one - measured on synthetic grids,
the mean gave 0.289 vs 0.269 (useless) while the p95 gives a ~5x separation.
Blur and low detail stay SEPARATE verdicts: a sharp but low-contrast frame is
reported as low_edge_detail, not image_blurry.

It runs with numpy when available and falls back to a pure-standard-library
kernel otherwise (both paths produce identical numbers). Send readings yourself
on WebcamSignal (sharpness_score, edge_density, mean_luminance,
underexposed_ratio, overexposed_ratio), or post a luminance_grid (0..1 or 0..255,
auto-scaled) and the server derives them with the active tuning.

Quality gates
-------------
Each frame reports quality_flags plus a 0..1 recognition_confidence, and the
class rolls them up into quality_summary.quality_flag_counts /
avg_recognition_confidence. Gate names: lighting_below_min_quality,
lighting_underexposed, lighting_overexposed, shadow_clipping, highlight_clipping,
image_blurry, low_edge_detail, detection_quality_low, too_close_to_camera,
too_far_from_camera, microphone_quality_low, noise_filter_weak,
high_background_noise, low_audio_snr.

Camera panel (see the video and the knobs together)
---------------------------------------------------
The live monitor puts a Camera panel beside the tuning panel so you can watch the
picture and the knobs at the same time:

  Start camera   getUserMedia preview. Frames are downsampled to a 48x36
                 luminance grid and POSTed to /api/theodore/webcam/evaluate, so
                 the Sobel/exposure knobs you drag are applied to real video.
  Test pattern   Synthetic moving bars for boxes with no camera (servers, CI,
                 VMs). Same analysis path, no device required.
  Stop           Releases the camera and stops sampling.

Under the video: sharpness, edge density, light, image quality and recognition
confidence, plus a "Live gates" line that turns red and names the failing gates.
Drag sharpness_min_quality up and image_blurry appears within a second; drag it
back and it clears. The tuning panel is compact and scrolls internally so the
video never gets pushed off screen.

Camera access needs a secure context: http://127.0.0.1 and https both qualify,
a plain http://<lan-ip> does not (use the test pattern there).


XAI VOICE-AGENT TUNING
======================
The voice agent is tuned the same three ways as vision - environment, live API,
or preset - using the XAI_TUNE_ prefix:

  Reply generation   reply_temperature_fast, reply_temperature_full,
                     reply_max_tokens_fast, reply_max_tokens_full,
                     reply_max_sentences
  Question asking    question_temperature, question_max_tokens
  Answer assessment  assessment_temperature, assessment_max_tokens
  Latency/transport  fast_timeout_s, full_timeout_s, cache_ttl_s,
                     max_history_turns

reply_max_sentences is injected into the system prompt: a reply that reads fine
on screen is tiring to listen to, so spoken turns are capped explicitly.

Presets: balanced, snappy (1-sentence turns, 4s timeout - live back-and-forth),
thorough (longer warmer answers, 8 remembered turns), precise (near-deterministic
for assessment/proctoring), storyteller (expressive, for young learners).

   curl -s http://127.0.0.1:8015/api/theodore/voice/tuning | python3 -m json.tool
   curl -s -X PATCH http://127.0.0.1:8015/api/theodore/voice/tuning \
     -H 'content-type: application/json' \
     -d '{"knobs": {"reply_max_sentences": 1, "reply_temperature_fast": 0.2}}'
   curl -s -X POST http://127.0.0.1:8015/api/theodore/voice/tuning/preset/snappy

Connection settings stay separate as plain env vars (XAI_API_KEY, XAI_BASE_URL,
XAI_MODEL, XAI_FAST_MODEL) since they are deployment config, not per-room tuning.
Timeout/cache/history knobs are re-read when a patch lands, so a change applies
to the very next turn rather than only to newly created agents.


Tuning workflow (what we actually ran)
--------------------------------------
   # 1. reproduce a bad room
   python3 subrepos/theodore_webcam_lab/scripts/seed_demo_session.py --degraded
   # 2. see which gates fail
   curl -s http://127.0.0.1:8015/api/theodore/webcam/live-metrics/demo-session \
     | python3 -c "import json,sys; q=json.load(sys.stdin)['quality_summary']; \
print(q['quality_flag_counts'], q['avg_recognition_confidence'])"
   # 3. tune, then re-post the SAME frames and compare
   curl -s -X POST http://127.0.0.1:8015/api/theodore/vision/tuning/preset/low_light

On the seeded degraded feed that sequence moves 10 failing gates / 0.367
confidence -> 6 gates / 0.436 (the remaining ones are audio and framing, which
the lighting preset is not meant to fix). The live monitor page has the same
controls as sliders under "Recognition Tuning", so you can watch the failed-gate
list change as you drag.


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

   EXPECT: "81 passed". These cover the analyzer, games, voice agent, the API,
   the vision and voice tuning knobs, Sobel imaging, the quality gates,
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
   while you watch it (Ctrl-C to stop). Add --degraded to send dim, soft-focus,
   noisy frames so the recognition quality gates fire and you can practise tuning
   them (see RECOGNITION TUNING above).

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
