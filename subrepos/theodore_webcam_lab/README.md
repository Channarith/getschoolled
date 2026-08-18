# Theodore Webcam Lab

A self-contained sandbox for Theodore's webcam recognition and voice agents:
presence and silhouette detection, expression and distraction signals, live
quality metrics, Sobel image analysis, tunable accuracy knobs, and a 26-language
voice agent.

Everything below runs offline. **No API key, no GPU and no webcam are required** —
the lab ships a frame seeder and a synthetic camera source, and the voice agent
falls back to a local responder when `XAI_API_KEY` is unset.

> Something not working? Jump to **[Step 5: check every part](#step-5-check-every-part)** —
> one command tells you exactly which piece is broken and how to fix it.

---

## Step 1 — Install what it needs

From the **repo root**, use the project venv (recommended):

```bash
source .venv/bin/activate
```

Or install into whatever `python3` you use:

```bash
python3 -m pip install "fastapi>=0.111,<0.116" "pydantic>=2.7,<3" \
    "uvicorn[standard]>=0.30,<0.35" "pytest>=8.2,<9" "httpx>=0.27,<0.28"
```

**Check it worked**

```bash
python3 -m pytest subrepos/theodore_webcam_lab/tests -q
```

You should see `228 passed` (or higher as new tests are added). If you see `ModuleNotFoundError`, the install above
did not run in the Python you are using. On macOS, bare `python3` is often
Homebrew 3.14 with no packages — activate `.venv` first (selfcheck does this
automatically when the venv exists).

---

## Step 2 — Start it

```bash
python3 -m uvicorn theodore_webcam_lab.main:app \
    --app-dir subrepos/theodore_webcam_lab/src --port 8015
```

Leave that running. **Check it worked**, from another terminal:

```bash
curl -s http://127.0.0.1:8015/health
# {"service":"theodore-webcam-lab","status":"ok"}
```

Port already taken? Use `--port 8016` and swap the port in the commands below.

---

## Step 3 — Give it something to look at

```bash
python3 subrepos/theodore_webcam_lab/scripts/seed_demo_session.py
```

This posts 60 frames for two simulated students: one healthy learner (whose
microphone drops out periodically, so you can see how missing data is handled)
and one distracted learner who trips the cheating signals.

Add `--rolling` to keep feeding a frame a second so the dashboard animates, or
`--degraded` to simulate a dim, out-of-focus, noisy room.

---

## Step 4 — Open the dashboard

<http://127.0.0.1:8015/theodore/webcam/live-monitor/demo-session>

![Live camera preview beside the tuning panel, with sharpness, edge density, light and confidence readings under the video](docs/screens/monitor-camera-and-tuning.webp)

**Left — Camera.** Press **Start camera** for your real webcam, **Test
pattern** if this machine has no camera, or **Silhouette demo** to see the
person-outline overlay trip silhouette detection. Camera samples no longer
overwrite the group demo metrics. Use **Load solo demo** / **Load group demo** /
**Start live feed**
at the top of the page to populate and animate student windows without a second
terminal.

**Test pattern** is the camera-free way to prove the image gates work. It sweeps
six stages, about two seconds each, and each one is calibrated against the
default `VisionTuning` to trip exactly the flags it names:

    sharp · well lit    no flags (baseline)         sharpness 0.90  edge 0.50  light 93%
    mild blur           no flags, sharpness drops   sharpness 0.56  edge 0.50  light 93%
    heavy blur          image_blurry, low_edge_detail   sharpness 0.22  edge 0.00
    low contrast        low_edge_detail             sharpness 0.36  edge 0.00
    underexposed        lighting_underexposed + lighting_below_min_quality   light 0%
    overexposed         lighting_overexposed + lighting_below_min_quality    light 0%

Watch *Tuning → live webcam* while it runs: each stage flips the matching gate
red and the next one clears it. Drag `sharpness_min_quality` or
`light_min_quality` and you move the point where a stage starts failing.

### Original-owner face lock (anti-substitution)

With two people in frame the lab used to mesh whoever MediaPipe returned as
`faces[0]` (often the wrong person). It now detects up to four faces, enrolls the
largest stable face for ~1.5s, keeps meshing that owner, draws secondary faces as
yellow dashed ovals, and pauses solo training on a real face mismatch. An empty
frame is treated as absence — not substitution. **Shut down server** clears the
metrics poll before wiping the page so DevTools stays quiet.

### Stare geometry lab — measuring the phone-vs-lesson angle

Looking at a phone and looking at a low-mounted laptop webcam both pitch the head
down, so an absolute angle cannot tell them apart. What can is the angle *this
screen* needs from *this seat*: the lesson band sits `y_screen` metres below the
webcam, so from `D` metres away it is `theta_screen = atan(y_screen / D)` degrees
down. Tilt past that is a **residual** the screen does not explain.

The **Stare geometry lab** under the camera is the instrument:

1. Start the camera and sit as you normally do. After about a second of tracking
   the gauge takes your resting pose as neutral (chip reads `neutral … (auto)`),
   which cancels out however low the laptop sits. Press **Set neutral** to pin it
   yourself; that overrides the automatic one.
2. Pick your **Device layout** (or type a measured `y_screen`). Look at
   mid-screen: residual should read near 0. If it is systematically off, edit
   `y_screen` until it is — that number is the calibration.
3. Run trials. **Reset peaks**, hold a pose, and read *peak down* and *residual*.
   A phone glance and a mid-screen glance separate by a wide margin.

The gauge on the right of the video shows degrees below neutral, an indigo
**screen** band at `theta_screen` for the live distance, a red dashed **trip
line** you can move with the number input, and an amber caret at the peak of the
current trial. Nothing here is enforced — `phone_stare` and `screen_match` are
readings, not gates, and `phone_visible` / cheating logic is untouched.

### Trajectory attention + record-only music / held objects

Face and hand landmark history (~2.5 s) feed three soft scores that *do* affect
attention and behaviour labels:

- **excitement** — short burst of face-local + hand energy that settles (soft
  attention boost; observatory curiosity).
- **interest** — sustained lean / frontal gaze with moderate brow activity and
  low global fidget (soft attention boost; observatory engagement).
- **dozing** — head-sag drift + low face motion; held dozing can label `drowsy`
  before full eyes-closed.

Separately, **outside music** (`external_music_score`) and **held object /
phone-in-hand** scores are **record-only**: integrity HUD chips + live metrics,
no toast, no spoken coaching, and they do **not** inflate distraction or
`suspected_cheating`. Ringtone detection stays the narrow stationary-tone path;
broadband / high-flux audio is music, not a ring. The existing 5 s
`phone_visible` cheating path is unchanged.

Pitch itself is a ratio of the face's own spans (how much of hairline-to-chin
sits above the eye line), so sitting closer cannot masquerade as tilt, and
`gaze_down` is scored from the residual rather than from the nose sitting below
the eye line — otherwise every seated learner reads as "looking down". The
formulas live in `stare_geometry.py`; the browser copy is pinned against it by
`tests/test_stare_geometry.py`.

**Right — Tuning.** Every accuracy threshold is a slider. Drag one and the gates
respond within a second. The **Vision** tab holds lighting, sharpness, distance
and audio knobs; the **Voice (xAI)** tab holds the conversation knobs. The
preset dropdown applies a whole room profile at once (`low_light`,
`bright_room`, `noisy_room`, `high_accuracy`, `wide_angle_laptop`).

Scroll down for per-student detail:

![Two student windows showing state, distance, light, image quality, behaviour, microphone and noise-filter readings](docs/screens/monitor-student-windows.webp)

**Try this:** drag `sharpness_min_quality` to the right and watch `image_blurry`
appear in Live gates; drag it back and it clears. That is the whole tuning loop.

---

## Step 5 — Check every part

When something does not work, run this instead of guessing:

```bash
python3 subrepos/theodore_webcam_lab/scripts/selfcheck.py
```

It walks the same path the product takes and prints one line per step:

```text
Theodore webcam lab — self check
============================================================

Offline (no server needed)
  [PASS] Python 3.11+
         running 3.12.3
  [PASS] Python dependencies
         fastapi, pydantic, uvicorn present
  [PASS] Lab package imports
  [PASS] Webcam analysis
         distance=1.0m confidence=0.85
  [PASS] Sobel imaging
         backend=python sharp=0.81 blurred=0.08
  [PASS] Tuning knobs in range
         53 vision knobs, 13 voice knobs, presets: balanced, bright_room, ...
  [PASS] Tuning knobs change scoring
         53/53 knobs change a scoring decision across 15 frame scenarios

API (http://127.0.0.1:8015)
  [PASS] API reachable
  [PASS] Frame evaluation
         confidence=0.87 gates=none
  [PASS] Live metrics
         series aligned with timestamps
  [PASS] Live monitor page
         camera panel and tuning sliders present
  [PASS] Tuning API
         53 knobs live
  [PASS] Tuning re-scores live session
         light_min_quality 0.35->0.99 flags [none]->[lighting_below_min_quality],
         ->0.0 clears to [none]
  [PASS] Voice agent
         provider=local-fallback (set XAI_API_KEY for real xAI replies)
  [PASS] Webcam games

============================================================
All 15 checks passed.
```

### Does the self check actually check the knobs?

Yes — that was a real gap, and it is now closed. The check used to confirm only
that the presets held in-range values and that `GET /vision/tuning` returned a
non-empty dict. A knob wired to nothing passes both, so the sliders could look
inert while every step was green.

Two steps now prove the knobs do something:

- **Tuning knobs change scoring** (offline) perturbs each of the 53 knobs on its
  own and re-scores a matrix of frames, failing on any knob that cannot move an
  output. Scenarios exist because a knob is only observable when a frame reaches
  its branch — silhouette knobs need a face-less filled frame, exposure knobs a
  blown-out one, audio knobs audio. One frame cannot exercise all 53.
- **Tuning re-scores live session** (API) PATCHes a knob and confirms the frames
  the server already holds are re-scored, so the change reaches the dashboard
  instead of only moving the slider.

Note what a knob actually changes. Almost all of them are **thresholds**, so they
flip **gate flags and behaviour labels** rather than the score numbers. Raising
`light_min_quality` above a frame's light score does not change `0.80`; it adds
`lighting_below_min_quality`. Watch **Failed gates (class)** and the per-student
badges, not the raw scores.

When a step fails it tells you what to do about it:

```text
  [FAIL] API reachable
         http://127.0.0.1:8015: [Errno 111] Connection refused
         fix: python3 -m uvicorn theodore_webcam_lab.main:app \
              --app-dir subrepos/theodore_webcam_lab/src --port 8015
```

Useful flags:

| Flag | Why |
| --- | --- |
| `--serve` | Starts the API itself, checks it, then shuts it down. One command, no setup. |
| `--base-url URL` | Point at a lab running elsewhere. |
| `--port N` | Port for `--serve`. |

It exits `0` when everything passes and `1` otherwise, so CI can gate on it.

---

## If it still does not work

| Symptom | Cause and fix |
| --- | --- |
| `ModuleNotFoundError: fastapi` | Step 1 installed into a different Python. Re-run it with the same `python3` you start the server with. |
| `Address already in use` | Something else holds the port. Use `--port 8016`, or find the owner with `lsof -ti :8015` and stop that specific process. |
| Dashboard says "No metrics yet" | Click **Load solo demo** or **Load group demo**, or run Step 3. Session id in the URL must match (`demo-session`). |
| Confused by 3 student windows | Group demo is synthetic (not 3 webcams). Use **Load solo demo (1 student)** or **Start camera**. |
| Charts are flat | Click **Start live feed**, or re-seed with `--rolling`. |
| Camera stays black, status "camera unavailable" | No camera, or permission denied. Use **Test pattern** or **Silhouette demo**. |
| Starting the camera wiped student windows | Fixed: camera posts with `persist_live_metrics=false`. Reload demo data if an older lab build already clobbered the session. |
| No cheating / silhouette | Click **Load group demo (3 students)**. student-b cheats; student-c is silhouette-only. |
| Lesson alerts do nothing | Click **Run lesson action** — Theodore now appears in an animated action stage, says the intervention aloud (when Auto-speak is checked), offers **Say it again**, acknowledges the alert, and jumps to the student window. |
| Applying a tuning preset changes nothing | Load a demo (solo or group) first, stay on the **Vision** tab, then change a knob/preset. The lab re-scores open sessions immediately — watch **Failed gates (class)** and student distance/quality flags. Voice presets only affect Theodore replies. |
| Knobs seem to do nothing on screen | Most knobs are thresholds: they flip **gate flags and behaviour labels**, not the score numbers, and many only apply to frames that reach their branch (silhouette knobs need no face, audio knobs need audio). Run Step 5 — **Tuning knobs change scoring** proves all 50 move a decision, and **Tuning re-scores live session** proves a PATCH reaches the dashboard. |
| No facial contours / mood, or "smiling/neutral" stopped showing | The green contour mesh and its mood colour come from MediaPipe FaceLandmarker, loaded from the jsdelivr CDN by default. Check the **detector badge** on the Camera panel: `face mesh (accurate)` means it loaded; `coarse` means it did not (blocked CDN, offline, or a strict content-security setup) and the lab now draws an approximate oval + mood from the luminance grid instead. To restore the full mesh offline, self-host the assets (`tasks-vision.mjs`, `wasm/`, `face_landmarker.task`) under the lab's `src/theodore_webcam_lab/vendor/vision/` dir, or point `AOEP_VISION_ASSET_DIR` at them and restart — the page then loads the mesh locally first. |
| Camera blocked on another machine | `getUserMedia` needs a secure context. `127.0.0.1` and `https` work; a plain `http://<lan-ip>` does not. |
| Voice replies say `local-fallback` | Expected without a key. Set `XAI_API_KEY` for real xAI replies. |
| Everything looks broken | Run Step 5. It isolates the failing piece. |

---

## What else is in here

| Path | What it is |
| --- | --- |
| `README.txt` | The full reference: every API endpoint, every tuning knob, the quality gates, and the detailed test procedure. |
| `VISION_TRAINING_OPERATIONS.txt` | The proprietary training programme and the 24/7 agent operations runbook. |
| `scripts/selfcheck.py` | The step-by-step health check from Step 5. |
| `scripts/seed_demo_session.py` | The demo frame seeder from Step 3. |
| `training/vision_training_runbook.json` | Job definitions for the continuous training loop. |
| `tests/` | Executable specifications. `test_audit_regressions.py` documents each fixed bug with a reproduction. |

### The endpoints, in short

```text
POST /api/theodore/webcam/evaluate                 analyse a batch of frames
POST /api/theodore/webcam/demo/seed                load healthy/cheating/silhouette demo
POST /api/theodore/webcam/demo/roll/start          animate demo metrics in-process
POST /api/theodore/webcam/demo/roll/stop           stop the in-process demo feed
POST /api/theodore/webcam/alerts/acknowledge       mark a lesson alert as handled
POST /api/theodore/webcam/alerts/action            execute the lesson alert action
GET  /api/theodore/webcam/live-metrics/{session}   chart-ready metric series
GET  /theodore/webcam/live-monitor/{session}       the dashboard above
GET  /api/theodore/vision/tuning                   read accuracy knobs
PATCH/api/theodore/vision/tuning                   change them live
POST /api/theodore/vision/tuning/preset/{name}     apply a room preset
GET  /api/theodore/vision/policy                   read timing/session policy knobs
PATCH/api/theodore/vision/policy                   change grace windows live
GET  /api/theodore/voice/tuning                    read xAI conversation knobs
PATCH/api/theodore/voice/tuning                    change voice knobs live
POST /api/theodore/voice/tuning/preset/{name}      apply a voice preset
POST /api/theodore/voice/respond                   talk to Theodore
POST /api/theodore/voice/ask-question              generate a practice question
POST /api/theodore/vision/imaging/analyze          Sobel + exposure report
POST /api/theodore/webcam/games/challenge          issue a reinforcement game
POST /api/theodore/webcam/games/attempt            score a game attempt
```

Full parameter detail for each is in `README.txt`.
