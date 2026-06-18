AOEP EDUCATION LLM - TRAINING SUBSYSTEM (next phase)
====================================================

Goal: continuously improve our own open-weight education LLM from the classes we
run and the feedback users give, so answers adapt to the audience (language,
slang/register, professionalism, age, learning behavior, prior mastery).

STATUS: scaffold. The data pipeline (pipeline/) is real and tested; actual
fine-tuning requires GPUs + model weights and is meant to run on a SEPARATE,
long-running cloud agent (not this repo's CI). Nothing here downloads weights or
trains by itself.

WHAT IS HERE
- pipeline/dataset.py   Build instruction/response training examples from class
                        transcripts + audience context + feedback-derived reward.
- pipeline/feedback.py  Feedback schema + reward mapping + aggregation.
- config/finetune.yaml  Base model + LoRA/QLoRA + continuous-training config
                        (no weights; paths/params only).
- tests/                Unit tests for the pipeline and the bias guardrail.

DATA FLOW (continuous loop, to run 24/7 on the training agent)
1. Export: orchestrator class sessions + memory mastery + billing tier ->
   training examples (pipeline.dataset.class_session_to_examples).
2. Reward: user feedback -> reward signal (pipeline.feedback.reward_from_feedback)
   for preference/RL-style weighting.
3. Fine-tune: LoRA/QLoRA on the base model using the exported JSONL
   (config/finetune.yaml). Checkpoints to the object store, never the repo.
4. Validate: held-out eval set + safety/bias checks; only promote a checkpoint
   that beats the current served model on accuracy AND fairness metrics.
5. Serve: promoted checkpoint is loaded by the vLLM LLMProvider (cloud) behind
   the existing provider interface - no app code changes.

CONDITIONING CONTEXT (pedagogically relevant ONLY)
The model is conditioned on: age_band, language, reading_level, learning_style,
professionalism, prior_mastery. These shape tone/register/difficulty.

ETHICS / FAIRNESS GUARDRAIL (important)
- RACE and ETHNICITY are PROTECTED ATTRIBUTES and are NEVER used to condition or
  train the model. Conditioning instruction on protected class would be
  discriminatory (disparate treatment) and is legally/ethically unacceptable in
  education. pipeline.dataset enforces this: conditioning_dict() emits only the
  allowlisted pedagogical features and assert_no_protected() rejects any leak.
- Protected attributes may be retained SEPARATELY and used ONLY for aggregate
  bias MONITORING (does the model serve all groups equally well?), never as a
  model input. Prefer language/reading-level/locale as proxies for genuinely
  pedagogical needs.
- All training data is consent-gated and PII-minimized (no names/face data).

RUN OFFLINE ON LINUX / UBUNTU (no network)
Code: export.py, run_finetune.py, evaluate.py, train.sh, requirements.txt.

  # 0) one-time: get a base model locally (on a networked box), e.g.
  #    huggingface-cli download <model> --local-dir /models/education-base
  # 1) install deps on the training host (GPU box for real runs)
  python3 -m venv .venv && . .venv/bin/activate
  pip install -r training/requirements.txt
  # 2) validate the pipeline with NO GPU/torch needed:
  CHECK_ONLY=1 ./training/train.sh
  # 3) a real offline run against the local base model:
  BASE_MODEL=/models/education-base ./training/train.sh

train.sh exports sessions -> JSONL (export.py), fine-tunes (run_finetune.py:
4-bit QLoRA on CUDA, LoRA/CPU fallback otherwise), and evaluates (evaluate.py).
HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE are exported so nothing touches the
network. Replace training/data/sample_sessions.json with real exported class
sessions (SESSIONS=/path/to/sessions.json).

RUNNING IT CONTINUOUSLY (separate cloud agent)
Fork a dedicated long-running cloud agent with GPU access; it runs the loop
above (export -> fine-tune -> evaluate -> promote) on a schedule/continuously.
This repo provides the pipeline + scripts + config so that agent has a stable,
tested contract to build on.
