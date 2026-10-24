PRIVATE RAG auto-tune lab (Theodore / Salareen)
===============================================

Purpose
  Continuously evaluate and auto-tune the curriculum + training knowledge RAG
  stack for hours a day before promoting knobs into production
  (aoep_shared.rag, knowledge_store, orchestrator Tutor grounding).

  Also hosts an extensive slang/idiom dictionary, EN+Khmer dictionary corpus
  (ingest / review / CosyVoice crisp audio / read-aloud pronunciation),
  the multi-language YouTube voice-training queue (same runner as
  scripts/cosyvoice_batch_ingest.py), world-dialect rehearsal,
  regurgitation drills, and feedback learning.
  Approved dictionary rows export into llm_training.assemble (source=dictionary).

What it tunes
  - top_k, min_score, groundedness thresholds
  - lexical vs FTS preference, chunk shaping
  - hours-a-day bakeoff loop with OptimizationLedger promote/revert
  - dialect/slang dictionary growth via confirm/correct/reject feedback
  - dictionary corpus train-update + read-aloud difficulty ramp

Everything below runs offline. No API key and no GPU are required.

Screens
  docs/screens/theodore_rag_lab.webp
  (also under this subrepo at docs/screens/theodore_rag_lab.webp)
  Live tuning knobs + bakeoff console. Regenerate:
    python3 scripts/render_lab_docs_screenshots.py

STEP BY STEP (from repo root)
-----------------------------

Step 0 — activate the project venv (once per shell)

  cd "$(git rev-parse --show-toplevel)"
  . .venv/bin/activate            # Windows: .venv\Scripts\activate
  # if the venv is missing:
  #   python3 -m venv .venv && . .venv/bin/activate
  #   python3 -m pip install -e 'packages/shared' -e 'subrepos/theodore_rag_lab[test]'

Step 1 — run the automated tests (fastest confidence check)

  PYTHONPATH=subrepos/theodore_rag_lab/src:packages/shared/src \
    python3 -m pytest subrepos/theodore_rag_lab/tests -q

  Expect all tests passed. ModuleNotFoundError → finish Step 0.

Step 2 — start the lab and open the web UI

  PYTHONPATH=subrepos/theodore_rag_lab/src:packages/shared/src \
    python3 -m uvicorn theodore_rag_lab.main:app --port 8095 --host 127.0.0.1

  Open in a browser:
    http://127.0.0.1:8095/     (same page at /lab)

  Tabs:
    RAG tuning — eval / sweep / bakeoff / champion
    Corpus + read-aloud — train-update, review queue, LLM JSONL export, sentence drills
    Voice training — YouTube channel queue for every language pool (UI or CLI)
    Drop training — drag links, videos, audio, channels, Vimeo, news, notes, or databases
    Dictionary — search 300+ slang/idiom entries by language & region
    Dialects — humanize sample text in Southern / NYC / Beijing / Cantonese / …
    Regurgitation — recall plain meanings; hits reinforce feedback learning
    Feedback learning — confirm / correct / reject entries into the live lexicon

  Corpus CLI (also via scripts/dictionary/* shims):
    theodore-rag-corpus-update
    theodore-rag-read-aloud --heard "She walked to school."
  Voice queue CLI (same job as the Voice training tab):
    theodore-rag-voice-queue --status
    theodore-rag-voice-queue --pool es,fr --workers 2 --max-urls 2 --max-channels 1
    python3 scripts/cosyvoice_batch_ingest.py --pool es --workers 2 --max-urls 2
    theodore-rag-voice-queue --stop
  Drop intake (same as the Drop training tab; drag paths onto the command):
    python3 scripts/training_drop.py ./clip.wav ./notes.db https://vimeo.com/123
    theodore-rag-drop --stdin
    python3 scripts/training_drop.py --train --max-urls 2 https://www.youtube.com/watch?v=abcdefghijk
  See docs/dictionary-corpus.txt.

  Leave the server running for curl too:

  curl -s http://127.0.0.1:8095/health | python3 -m json.tool
  # ok=true, lexicon_total, dialects, features include dictionary + regurgitation

  Port busy? Use --port 8099 and swap the port below.

Step 3 — run one evaluation

  curl -s -X POST 'http://127.0.0.1:8095/api/rag/eval?details=false' \
    | python3 -m json.tool

  Expect a report with groundedness / recall metrics plus the active tuning dict.

Step 4 — peek at tuning, then try a short bakeoff

  curl -s http://127.0.0.1:8095/api/rag/tuning | python3 -m json.tool
  curl -s -X POST http://127.0.0.1:8095/api/rag/train/run-blocking \
    -H 'content-type: application/json' \
    -d '{"hours":0.01}' | python3 -m json.tool
  # Answers 202 with a status_url; poll it (GET /api/rag/jobs/{job_id}) until state is done.

  Or without the API (CI-style smoke):

  make rag-lab
  # runs bakeoff_loop --hours 0.01

  Answer quality for small models uses the same harness in-process. It does
  not POST /api/rag/eval, so the running lab's telemetry is unchanged:

  make rag-small-evals
  # RAG_EVAL_MODELS, RAG_EVAL_HOST, RAG_EVAL_PORT, RAG_EVAL_BACKEND, RAG_EVAL_MARGIN
  # One model on its own port: RAG_EVAL_MODELS=qwen2.5-0.5b@127.0.0.1:18001
  # writes output/spark/rag-small-evals/

Step 5 — dictionary + dialect + regurgitation

  curl -s 'http://127.0.0.1:8095/api/dictionary?region=us-south&limit=10' | python3 -m json.tool
  curl -s -X POST http://127.0.0.1:8095/api/dialects/probe \
    -H 'content-type: application/json' \
    -d '{"dialect":"en_sg","text":"Welcome! We will walk through the lesson."}' | python3 -m json.tool
  curl -s 'http://127.0.0.1:8095/api/regurgitate/deck?dialect=zh_yue_gz&n=5' | python3 -m json.tool

Step 6 — read champion + telemetry, then promote when green

  curl -s http://127.0.0.1:8095/api/rag/champion | python3 -m json.tool
  curl -s http://127.0.0.1:8095/api/rag/telemetry | python3 -m json.tool

  After a green multi-hour run, copy champion knobs into orchestrator teaching
  retrieve() + groundedness thresholds.

APIs
  GET  /  and /lab          # browser qualification console (multi-tab)
  GET  /health
  GET|PATCH /api/rag/tuning  (+ /preset/{name})
  POST /api/rag/eval
  GET  /api/rag/sweep
  POST /api/rag/train/start   # continuous auto-tune
  POST /api/rag/train/run-blocking   (202 + job; poll GET /api/rag/jobs/{job_id})
  GET  /api/rag/train/status
  POST /api/rag/train/stop
  GET  /api/rag/champion
  GET  /api/rag/telemetry
  GET  /api/dictionary
  GET  /api/dialects
  POST /api/dialects/probe
  GET  /api/regurgitate/deck
  POST /api/regurgitate/grade
  GET|POST /api/feedback
