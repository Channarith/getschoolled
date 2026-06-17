# Build context = repo root (needs packages/shared and sample-curriculum).
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY packages/shared /app/packages/shared
COPY VERSION /app/VERSION
COPY services/orchestrator/requirements.txt /app/services/orchestrator/requirements.txt
RUN pip install --no-cache-dir -e /app/packages/shared \
    && pip install --no-cache-dir -r /app/services/orchestrator/requirements.txt

COPY services/orchestrator /app/services/orchestrator
COPY sample-curriculum /app/sample-curriculum

ENV PYTHONPATH=/app/services/orchestrator/src
WORKDIR /app/services/orchestrator
EXPOSE 8000
CMD ["uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]
