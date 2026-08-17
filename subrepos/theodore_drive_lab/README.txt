PRIVATE Drive Mode fine-tune lab (Theodore / Salareen)
======================================================

Purpose
  Fine-tune Drive Mode hands-free audio agent quality before promoting knobs
  into apps/web /drive, mobile DriveModeScreen, and the speech gateway.

What it tunes
  - Wake-word precision/recall (Hey Sala / Salareen)
  - Echo rejection (narration bleed into mic)
  - Pause-to-submit delay, resume delay
  - TTS prosody hints / engine preference
  - Segment Q&A grounding score

Everything below runs offline. No microphone and no API key are required for
the eval / bakeoff path (it uses fixture utterances).

Screens
  docs/screens/theodore_drive_lab.webp
  (also under this subrepo at docs/screens/theodore_drive_lab.webp)
  Wake/echo/TTS knobs + eval console. Regenerate:
    python3 scripts/render_lab_docs_screenshots.py

STEP BY STEP (from repo root)
-----------------------------

Step 0 — activate the project venv (once per shell)

  cd "$(git rev-parse --show-toplevel)"
  . .venv/bin/activate
  # if needed:
  #   python3 -m venv .venv && . .venv/bin/activate
  #   python3 -m pip install -e 'packages/shared' -e 'subrepos/theodore_drive_lab[test]'

Step 1 — run the automated tests

  PYTHONPATH=subrepos/theodore_drive_lab/src:packages/shared/src \
    python3 -m pytest subrepos/theodore_drive_lab/tests -q

  Expect all tests passed.

Step 2 — start the lab and open the web UI

  PYTHONPATH=subrepos/theodore_drive_lab/src:packages/shared/src \
    python3 -m uvicorn theodore_drive_lab.main:app --port 8096 --host 127.0.0.1

  Open in a browser:
    http://127.0.0.1:8096/     (same page at /lab)

  Use Wake eval, Answer eval, Parse utterance, Bakeoff, Champion, Telemetry.
  Leave the server running for curl too:

  curl -s http://127.0.0.1:8096/health | python3 -m json.tool
  # ok=true, service=theodore-drive-lab, wake_cases + tuning present

Step 3 — evaluate wake-word parsing

  curl -s -X POST http://127.0.0.1:8096/api/drive/wake/eval \
    | python3 -m json.tool

  Expect precision / recall / F1 against the fixture wake utterances
  (data/wake_utterances.jsonl).

  Optional one-off parse:

  curl -s -X POST http://127.0.0.1:8096/api/drive/wake/parse \
    -H 'content-type: application/json' \
    -d '{"text":"Hey Sala, pause the lesson"}' | python3 -m json.tool

Step 4 — evaluate segment Q&A grounding, then bakeoff

  curl -s -X POST http://127.0.0.1:8096/api/drive/answer/eval \
    | python3 -m json.tool

  curl -s -X POST http://127.0.0.1:8096/api/drive/bakeoff \
    -H 'content-type: application/json' \
    -d '{"rounds":8}' | python3 -m json.tool

  Or without the API:

  make drive-lab

Step 5 — read champion + telemetry, then promote when green

  curl -s http://127.0.0.1:8096/api/drive/champion | python3 -m json.tool
  curl -s http://127.0.0.1:8096/api/drive/telemetry | python3 -m json.tool

  Promote champion wake/echo/pause knobs into voiceCommands.ts + DriveModeScreen;
  TTS prefs into speech gateway /tts defaults.

APIs
  GET  /  and /lab          # browser qualification console
  GET  /health
  GET|PATCH /api/drive/tuning (+ /preset/{name})
  POST /api/drive/wake/eval
  POST /api/drive/wake/parse
  POST /api/drive/answer/eval
  POST /api/drive/bakeoff
  GET  /api/drive/champion
  GET  /api/drive/telemetry
