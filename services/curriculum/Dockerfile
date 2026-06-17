# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CURRICULUM_DIR=/app/sample-curriculum

WORKDIR /app

COPY packages/shared /app/packages/shared
COPY services/curriculum /app/services/curriculum
COPY sample-curriculum /app/sample-curriculum

RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install /app/packages/shared \
    && python3 -m pip install /app/services/curriculum

EXPOSE 8500
CMD ["uvicorn", "curriculum.main:app", "--host", "0.0.0.0", "--port", "8500"]
