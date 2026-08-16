Theodore Homework Lab (75 methodologies)
=========================================

Private quality lab wrapping and extending aoep_shared.homework before
promoting richer item types into services/homework.

Registered methodologies (must stay >= 50; currently 75)
  choice, open, match, media, audio, language, reading, concept, stem,
  social, metacog, drill, game, phonics, speaking, interactive
  — see GET /api/homework/methodologies

Includes
  · multiple choice / multi-select / true-false
  · picture ID, hotspot, video comprehension / timestamps
  · listen & learn, dictation, pronunciation, minimal pairs
  · grammar, spelling, punctuation, vocabulary, idioms
  · translate phrase + translate verse line
  · summarize / paraphrase / inference / claim-evidence
  · matching, ordering, categorize, drag-drop
  · games: scramble, memory match, timed quiz, karaoke fill, hangman
  · classic shared generate path (mcq/short/essay) via /generate/shared-classic

Everything below runs offline. No API key is required.

Screens
  docs/screens/theodore_homework_lab.webp
  (also under this subrepo at docs/screens/theodore_homework_lab.webp)
  Methodology roster + generate/grade console. Regenerate:
    python3 scripts/render_lab_docs_screenshots.py

STEP BY STEP (from repo root)
-----------------------------

Step 0 — activate the project venv (once per shell)

  cd "$(git rev-parse --show-toplevel)"
  . .venv/bin/activate
  # if needed:
  #   python3 -m venv .venv && . .venv/bin/activate
  #   python3 -m pip install -e 'packages/shared' -e 'subrepos/theodore_homework_lab[test]'

Step 1 — run the automated tests + gold battery

  PYTHONPATH=subrepos/theodore_homework_lab/src:packages/shared/src \
    python3 -m pytest subrepos/theodore_homework_lab/tests -q

  make homework-lab
  # prints methodology_count and gold-battery percentage (expect >= 50 methods)

Step 2 — start the lab API

  PYTHONPATH=subrepos/theodore_homework_lab/src:packages/shared/src \
    python3 -m uvicorn theodore_homework_lab.main:app --port 8098 --host 127.0.0.1

  Leave that running. From another terminal:

  curl -s http://127.0.0.1:8098/health | python3 -m json.tool
  # ok=true, methodologies >= 50

Step 3 — list methodologies

  curl -s 'http://127.0.0.1:8098/api/homework/methodologies' \
    | python3 -m json.tool | head -80

  Optional filter: ?family=game  or  ?family=audio

Step 4 — generate a short assignment, then grade it

  curl -s -X POST http://127.0.0.1:8098/api/homework/generate \
    -H 'content-type: application/json' \
    -d '{
      "title": "Photosynthesis practice",
      "passages": ["plants make food using light water and carbon dioxide"],
      "subject": "science",
      "max_items": 6,
      "difficulty": "medium"
    }' | tee /tmp/hw-assignment.json | python3 -m json.tool | head -60

  python3 - <<'PY'
import json, urllib.request
assignment = json.load(open("/tmp/hw-assignment.json"))["assignment"]
# empty answers → report shape; fill item answer keys for a real score
body = json.dumps({"assignment": assignment, "answers": []}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8098/api/homework/grade",
    data=body,
    headers={"content-type": "application/json"},
)
print(json.load(urllib.request.urlopen(req)))
PY

  # Optional gold battery via API:
  #   curl -s -X POST http://127.0.0.1:8098/api/homework/eval/gold | python3 -m json.tool

Step 5 — check tuning + telemetry, then promote when ready

  curl -s http://127.0.0.1:8098/api/homework/tuning | python3 -m json.tool
  curl -s http://127.0.0.1:8098/api/homework/telemetry | python3 -m json.tool

  Promote richer item types into services/homework / curriculum /homework/*
  after the gold battery stays green.

APIs on :8098
  GET  /health
  GET  /api/homework/methodologies
  POST /api/homework/generate
  POST /api/homework/grade
  GET|PATCH /api/homework/tuning
  GET  /api/homework/telemetry
