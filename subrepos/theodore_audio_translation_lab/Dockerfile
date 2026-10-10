# Build context = repo root (needs packages/shared and this lab).
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY packages/shared /app/packages/shared
RUN pip install --no-cache-dir /app/packages/shared

COPY subrepos/theodore_audio_translation_lab/pyproject.toml /app/pyproject.toml
COPY subrepos/theodore_audio_translation_lab/src /app/src
# speech extra is edge-tts, so Theodore still speaks when the speech gateway
# is down. The page falls back to the device voice only if that fails too.
RUN pip install --no-cache-dir -e ".[speech]"

EXPOSE 8041
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8041/health >/dev/null || exit 1

CMD ["uvicorn", "theodore_audio_translation_lab.main:app", "--host", "0.0.0.0", "--port", "8041"]
