CosyVoice 2 TTS server (self-hosted, GPU, vLLM-accelerated)
===========================================================

What this is
------------
A thin FastAPI wrapper (server.py) around FunAudioLLM's CosyVoice 2 that exposes
the same HTTP contract the rest of the platform uses:

  POST /tts   JSON {text, language, speaker, instruct, mode, sample_rate,
                    reference_audio_b64?}  ->  audio/wav bytes
  GET  /health

Modes map to CosyVoice 2 calls: instruct2 (natural-language style), zero_shot
(clone from reference_audio_b64), cross_lingual, sft (built-in speaker).

The speech gateway (services/speech) and the teach-&-present presenter
(aoep_shared.meeting.clone_tts) call this via COSYVOICE_URL and prefer it over
ElevenLabs/edge-tts when set.

vLLM acceleration
-----------------
CosyVoice 2/3 support the vLLM inference engine, which dramatically speeds up
generation. That means one GPU serves many concurrent narrations, so you spend
far fewer GPU-hours on Vultr. It is ON by default here (COSYVOICE_USE_VLLM=1);
set it to 0 to fall back to the plain PyTorch path.

Build + push (do this on a GPU box or a large runner; the image is multi-GB)
----------------------------------------------------------------------------
  docker build -f services/cosyvoice/Dockerfile -t sjc.vultrcr.com/salareen/cosyvoice:latest .
  docker push sjc.vultrcr.com/salareen/cosyvoice:latest

Deploy on Vultr VKE
-------------------
  1. Label a GPU node:  kubectl label node <gpu-node> aoep.gpu/pool=true
  2. kubectl apply -k infra/k8s-vke        # includes cosyvoice.yaml + COSYVOICE_URL
  3. kubectl -n aoep rollout status deploy/cosyvoice --timeout=600s   # first start pulls weights
  4. kubectl -n aoep rollout restart deploy/speech    # pick up COSYVOICE_URL

COSYVOICE_URL is already set to http://cosyvoice:9880 in aoep-config, so the
speech + presenter paths use it automatically once the Deployment is healthy.

Env
---
  COSYVOICE_USE_VLLM   0 (local default) | 1  - vLLM acceleration (CosyVoice2/3; often
                         unavailable on aarch64 Spark — leave 0 locally)
  COSYVOICE_FP16       1 (default) | 0
  COSYVOICE_MODEL_ID   iic/CosyVoice2-0.5B - ModelScope id (pulled on first start)
  COSYVOICE_MODEL_DIR  /models/CosyVoice2-0.5B  (local: path to CosyVoice-300M-SFT etc.)
  COSYVOICE_DEFAULT_SPK  英文女 (local) / 中文女 - enrolled speaker for no-reference synth
  COSYVOICE_PORT       9880

Local native GPU (NVIDIA Spark / GB10 — preferred over Docker Desktop)
---------------------------------------------------------------------
Docker Desktop on this host uses context desktop-linux (linuxkit VM, ~8GB, no
nvidia.com/gpu CDI). Native Engine context "default" DOES see the GPU, but
upstream CosyVoice docker/Dockerfile still pulls Miniforge3-Linux-x86_64 — wrong
for aarch64. Use a host venv instead:

  # one-time (already done on Chan's Spark if ~/code/CosyVoice/.venv exists)
  cd ~/code/CosyVoice
  git submodule update --init --recursive
  python3 -m venv .venv
  .venv/bin/pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu130
  # then lean deps from requirements.txt skipping deepspeed/tensorrt/grpcio/pyworld
  # (pyworld needs python3-dev; a tiny stub under site-packages/pyworld is enough
  # for inference). Download CosyVoice-300M-SFT into pretrained_models/.

  # every session
  ./scripts/run_cosyvoice_local.sh
  export COSYVOICE_URL=http://127.0.0.1:9880
  export COSYVOICE_DEFAULT_SPK=英文女

  # smoke
  curl -s http://127.0.0.1:9880/health
  curl -s -X POST http://127.0.0.1:9880/tts \
    -H 'Content-Type: application/json' \
    -d '{"text":"Hello from Salareen.","mode":"sft","speaker":"英文女"}' \
    -o /tmp/cv.wav && file /tmp/cv.wav

Dictionary / read-aloud (docs/dictionary-corpus.txt) uses the same COSYVOICE_URL.
Khmer is NOT a CosyVoice-300M language; EN + zh/ja/yue/ko SFT speakers work.
For Khmer gold audio, record mic takes into the corpus pipeline.

AOEP clients (speech gateway + presenter) already prefer CosyVoice when
COSYVOICE_URL is set — no ElevenLabs key required.

Local (no GPU): the server imports without the model; POST /tts only works once
the model loads (GPU). For CPU smoke tests, inject a fake model via build_app().

Spark fine-tune candidate (does not replace this server)
-------------------------------------------------------
  python3 scripts/spark_cosyvoice_manifest.py \
    --scan-root output --dest output/spark/cosyvoice
  # writes per-language Kaldi lists + TRAIN_HANDOFF.txt for report ok:true
  ./scripts/spark_cosyvoice_km_finetune.sh
  # one LLM epoch on CosyVoice-300M into output/spark/cosyvoice/km/exp
  # takes flock ~/.gs-gpu.lock around torchrun only
  # never copies checkpoints into pretrained_models or this process
