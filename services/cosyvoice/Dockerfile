# CosyVoice 2 GPU inference server (vLLM-accelerated) for Vultr GPU nodes.
#
# Heavy image (CUDA + torch + vLLM + CosyVoice). Build on a machine with enough
# disk (a Vultr GPU instance or a large runner), push to the registry, then the
# infra/k8s/cosyvoice.yaml Deployment runs it. See services/cosyvoice/README.txt.
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip python3-venv git git-lfs ffmpeg sox libsox-dev \
    && rm -rf /var/lib/apt/lists/* && git lfs install

WORKDIR /app

# CosyVoice source (FunAudioLLM). Pin to a commit in production for reproducibility.
RUN git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git /app/CosyVoice

# Python deps: CosyVoice requirements + vLLM (acceleration) + this server's deps.
RUN pip3 install --upgrade pip \
    && pip3 install -r /app/CosyVoice/requirements.txt \
    && pip3 install vllm \
    && pip3 install fastapi "uvicorn[standard]" modelscope

# Our thin HTTP wrapper.
COPY services/cosyvoice/server.py /app/server.py

# CosyVoice must be importable (repo root + third_party Matcha-TTS).
ENV PYTHONPATH=/app/CosyVoice:/app/CosyVoice/third_party/Matcha-TTS
ENV COSYVOICE_USE_VLLM=1 \
    COSYVOICE_MODEL_ID=iic/CosyVoice2-0.5B \
    COSYVOICE_MODEL_DIR=/models/CosyVoice2-0.5B \
    COSYVOICE_PORT=9880

EXPOSE 9880
CMD ["python3", "/app/server.py"]
