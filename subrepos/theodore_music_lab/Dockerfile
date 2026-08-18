FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# edge-tts needs a writable home for its config; uvicorn needs curl for healthchecks.
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install the music lab and its TTS dependency.
COPY subrepos/theodore_music_lab/pyproject.toml ./pyproject.toml
COPY subrepos/theodore_music_lab/src ./src
COPY subrepos/theodore_music_lab/data ./data
COPY subrepos/theodore_music_lab/scripts ./scripts
RUN pip install --no-cache-dir -e ".[server]" edge-tts==6.1.12

# Voice cache lives here; mount a named volume over this path in production
# so the pre-generated clips survive container rebuilds.
ENV MUSIC_LAB_TTS_CACHE=/data/tts-cache
RUN mkdir -p /data/tts-cache

COPY subrepos/theodore_music_lab/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8000/api/music/tts/status | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('available') else 1)" || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
