# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Shared library first (changes least often) then the service.
COPY packages/shared /app/packages/shared
COPY services/orchestrator /app/services/orchestrator

RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install /app/packages/shared \
    && python3 -m pip install /app/services/orchestrator

EXPOSE 8000
CMD ["uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]
