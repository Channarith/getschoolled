# syntax=docker/dockerfile:1
FROM node:22-slim AS deps
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
# npm ci installs exactly what the lockfile specifies, including platform-specific
# optional binaries (e.g. @next/swc-linux-x64-gnu) for the BUILD target OS/CPU.
# npm install resolves against the host OS that generated the lockfile (macOS) and
# skips Linux-only optionals, causing "Failed to load SWC binary" on every fresh build.
RUN npm ci

FROM node:22-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web ./
# YuNet (~230 KB) and SFace (~37 MB) are gitignored. Face Check loads them from
# /vision-models on this origin, the same way opencv.js is served from /opencv.
# URLs match aoep_shared.vision.models. A short file is a failed download.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p public/vision-models \
    && curl -fsSL --retry 3 -o public/vision-models/face_detection_yunet_2023mar.onnx \
        https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx \
    && curl -fsSL --retry 3 -o public/vision-models/face_recognition_sface_2021dec.onnx \
        https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx \
    && test "$(wc -c < public/vision-models/face_detection_yunet_2023mar.onnx)" -gt 150000 \
    && test "$(wc -c < public/vision-models/face_recognition_sface_2021dec.onnx)" -gt 30000000
# next.config.mjs rewrites are frozen into .next by `next build`. The public
# demos proxy to the in-cluster lab Services. Local `next dev` leaves these
# unset and keeps the 127.0.0.1 defaults.
ARG COURSE_STUDIO_ORIGIN=http://course-studio:8040
ARG CHILDREN_LAB_ORIGIN=http://children-lab:8018
ARG AUDIO_LAB_ORIGIN=http://audio-lab:8041
ARG MUSIC_ORIGIN=http://music:8000
ENV COURSE_STUDIO_ORIGIN=$COURSE_STUDIO_ORIGIN
ENV CHILDREN_LAB_ORIGIN=$CHILDREN_LAB_ORIGIN
ENV AUDIO_LAB_ORIGIN=$AUDIO_LAB_ORIGIN
ENV MUSIC_ORIGIN=$MUSIC_ORIGIN
# Pre-rendered demo narration (consented company voices) lives in Vultr Object Storage; NEXT_PUBLIC_* is frozen in at build.
ARG NEXT_PUBLIC_VOICE_ASSETS_URL=https://salareen-prod.sjc1.vultrobjects.com/voice-assets
ENV NEXT_PUBLIC_VOICE_ASSETS_URL=$NEXT_PUBLIC_VOICE_ASSETS_URL
RUN npm run build

FROM node:22-slim AS run
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/public ./public
# Legal pages (privacy/terms/data-deletion) read plain-text docs at runtime.
COPY --from=build /app/content ./content
EXPOSE 3000
CMD ["npm", "start"]
