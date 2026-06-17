# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY packages/shared /app/packages/shared
COPY services/billing /app/services/billing

RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install /app/packages/shared \
    && python3 -m pip install /app/services/billing

EXPOSE 8600
CMD ["uvicorn", "billing.main:app", "--host", "0.0.0.0", "--port", "8600"]
