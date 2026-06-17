# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY packages/shared /app/packages/shared
COPY services/memory /app/services/memory

RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install /app/packages/shared \
    && python3 -m pip install /app/services/memory

EXPOSE 8400
CMD ["uvicorn", "memory.main:app", "--host", "0.0.0.0", "--port", "8400"]
