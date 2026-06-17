# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY packages/shared /app/packages/shared
COPY services/orchestrator /app/services/orchestrator
COPY apps/agent-runtime /app/apps/agent-runtime

RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install /app/packages/shared \
    && python3 -m pip install /app/services/orchestrator \
    && python3 -m pip install /app/apps/agent-runtime

CMD ["python3", "-m", "agent_runtime.worker"]
