CosyVoice → Audio2Face (Omniverse ACE) on this machine
======================================================

What works on NVIDIA Spark (aarch64 / GB10)
------------------------------------------
1. CosyVoice TTS sidecar (native GPU venv) on :9880
2. Protocol-compatible A2F gRPC stub on :52000
   (real Audio2Face-3D NIM is linux/amd64-only — Multi-Arch Support: No)
3. Orchestrated loop: CosyVoice WAV → 16 kHz PCM → A2F ProcessAudioStream
4. Pipecat config wrapper: scripts/pipecat_cosyvoice/pipeline_config.py
5. Cloned samples:
   ~/code/Audio2Face-3D-Samples
   ~/code/voice-agent-examples

NGC key (gitignored)
--------------------
Stored in config/local.env as NGC_API_KEY / NVIDIA_API_KEY / NVAPI_KEY.
Rotate it — it was pasted in chat.

Quick start (Spark)
-------------------
  ./scripts/a2f_cosyvoice_loop/run_stack.sh           # stub + one smoke utterance
  ./scripts/a2f_cosyvoice_loop/run_stack.sh --loop    # keep routing phrases
  # stop stub: kill $(cat /tmp/a2f_cosyvoice_stack/a2f_stub.pid)

Real Omniverse A2F-3D NIM (x86_64 GPU host only)
------------------------------------------------
  export A2F_USE_NIM=1
  # on an amd64 machine with GPU + NGC_API_KEY:
  ./scripts/a2f_cosyvoice_loop/run_stack.sh --stub-only
  # or: cd ~/code/Audio2Face-3D-Samples/quick-start && docker compose up

Then point this Spark's loop at that host:
  export A2F_GRPC_URL=<amd64-host>:52000   # or NIM's published port
  python3 scripts/a2f_cosyvoice_loop/cosyvoice_a2f_loop.py --once --text "Hello."
