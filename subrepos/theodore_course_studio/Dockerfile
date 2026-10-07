# Build context = repo root (needs packages/shared and the studio package).
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    THEODORE_COURSE_STUDIO_DATA=/tmp/course-studio

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY packages/shared /app/packages/shared
RUN pip install --no-cache-dir /app/packages/shared

COPY subrepos/theodore_course_studio/pyproject.toml /app/pyproject.toml
COPY subrepos/theodore_course_studio/src /app/src
# voices extra is edge-tts, so narration still speaks when the speech gateway
# is down. The demo page falls back to the device voice only if that fails too.
RUN pip install --no-cache-dir -e ".[voices]"

EXPOSE 8040
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8040/health >/dev/null || exit 1

CMD ["uvicorn", "theodore_course_studio.main:app", "--host", "0.0.0.0", "--port", "8040"]
