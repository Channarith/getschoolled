FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/tmp

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# MediaPipe vision library, wasm and the two landmark models, served from this origin
# (/vendor/vision) so a phone on a flaky or filtered network does not depend on
# jsdelivr or storage.googleapis.com. app.js tries these first and falls back to the CDN.
# A short file means a failed download, so the build fails rather than shipping a broken lab.
ARG MEDIAPIPE_VERSION=0.10.14
RUN mkdir -p /app/vision /tmp/mp \
    && curl -fsSL --retry 3 -o /tmp/mp/tv.tgz "https://registry.npmjs.org/@mediapipe/tasks-vision/-/tasks-vision-${MEDIAPIPE_VERSION}.tgz" \
    && tar -xzf /tmp/mp/tv.tgz -C /tmp/mp \
    && cp /tmp/mp/package/vision_bundle.mjs /app/vision/tasks-vision.mjs \
    && cp -r /tmp/mp/package/wasm /app/vision/wasm \
    && curl -fsSL --retry 3 -o /app/vision/face_landmarker.task "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task" \
    && curl -fsSL --retry 3 -o /app/vision/hand_landmarker.task "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task" \
    && test "$(wc -c < /app/vision/face_landmarker.task)" -gt 3000000 \
    && test "$(wc -c < /app/vision/hand_landmarker.task)" -gt 7000000 \
    && test "$(wc -c < /app/vision/tasks-vision.mjs)" -gt 100000 \
    && ls /app/vision/wasm | grep -q wasm \
    && rm -rf /tmp/mp
ENV AOEP_VISION_ASSET_DIR=/app/vision

COPY packages/shared /app/shared
RUN pip install --no-cache-dir /app/shared

COPY subrepos/theodore_children_webcam_lab/pyproject.toml /app/pyproject.toml
COPY subrepos/theodore_children_webcam_lab/src /app/src
RUN pip install --no-cache-dir -e . "edge-tts>=7.3.1,<8"

EXPOSE 8018
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8018/health >/dev/null || exit 1

CMD ["uvicorn", "theodore_children_webcam_lab.main:app", "--host", "0.0.0.0", "--port", "8018"]
