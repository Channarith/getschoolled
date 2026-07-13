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
  COSYVOICE_USE_VLLM   1 (default) | 0     - vLLM acceleration
  COSYVOICE_MODEL_ID   iic/CosyVoice2-0.5B - ModelScope id (pulled on first start)
  COSYVOICE_MODEL_DIR  /models/CosyVoice2-0.5B
  COSYVOICE_DEFAULT_SPK                    - built-in speaker for no-reference synth
  COSYVOICE_PORT       9880

Local (no GPU): the server imports without the model; POST /tts only works once
the model loads (GPU). For CPU smoke tests, inject a fake model via build_app().
