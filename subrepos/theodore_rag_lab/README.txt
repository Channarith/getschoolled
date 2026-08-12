PRIVATE RAG auto-tune lab (Theodore / Salareen)
===============================================

Purpose
  Continuously evaluate and auto-tune the curriculum + training knowledge RAG
  stack for hours a day before promoting knobs into production
  (aoep_shared.rag, knowledge_store, orchestrator Tutor grounding).

What it tunes
  - top_k, min_score, groundedness thresholds
  - lexical vs FTS preference, chunk shaping
  - hours-a-day bakeoff loop with OptimizationLedger promote/revert

Run offline (no keys / no GPU required)
  pip install -e 'subrepos/theodore_rag_lab[test]'
  PYTHONPATH=subrepos/theodore_rag_lab/src:packages/shared/src \
    python3 -m pytest subrepos/theodore_rag_lab/tests -q
  PYTHONPATH=... python3 -m theodore_rag_lab.bakeoff_loop --hours 0.01
  PYTHONPATH=... uvicorn theodore_rag_lab.main:app --port 8095

APIs
  GET  /health
  GET|PATCH /api/rag/tuning  (+ /preset/{name})
  POST /api/rag/eval
  POST /api/rag/train/start   # continuous auto-tune
  GET  /api/rag/train/status
  POST /api/rag/train/stop
  GET  /api/rag/champion
  GET  /api/rag/telemetry

Promote
  Copy champion knobs into orchestrator teaching retrieve() + groundedness
  thresholds after a green multi-hour run.
