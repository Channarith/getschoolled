FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY packages/shared /app/shared
RUN pip install --no-cache-dir /app/shared

COPY subrepos/theodore_children_webcam_lab/pyproject.toml /app/pyproject.toml
COPY subrepos/theodore_children_webcam_lab/src /app/src
RUN pip install --no-cache-dir -e . "edge-tts==7.2.8"

EXPOSE 8018
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8018/health >/dev/null || exit 1

CMD ["uvicorn", "theodore_children_webcam_lab.main:app", "--host", "0.0.0.0", "--port", "8018"]
