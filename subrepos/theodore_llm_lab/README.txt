Private lab: assemble library + profile + webcam/audio/game/RAG signals into a
portable education LLM training corpus and robot GGUF pack metadata.

Port: 8019 (scripts/run_theodore_lab.sh llm)

Features:
  - POST /api/llm/assemble   — scan fixtures (+ optional sample-curriculum)
  - POST /api/llm/check      — fairness guardrail + finetune --check hints
  - POST /api/llm/robot-pack — GGUF/ONNX humanoid manifest metadata
  - POST /api/llm/robot-turn — offline mock robot teaching beat
  - Live audio agent widget (xAI / Gemini) like other Theodore labs

GPU weight updates still run on a separate CUDA host:
  python3 training/run_finetune.py --offline --base-model /models/education-base ...

See docs/unimplemented-audit.txt #1 and docs/edge-robot-runbook.txt.

Run:
  PYTHONPATH=subrepos/theodore_llm_lab/src:packages/shared/src \
    python3 -m uvicorn theodore_llm_lab.main:app --port 8019

Tests:
  PYTHONPATH=subrepos/theodore_llm_lab/src:packages/shared/src \
    python3 -m pytest subrepos/theodore_llm_lab/tests -q
