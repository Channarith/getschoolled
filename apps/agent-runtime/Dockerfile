# Build context = repo root (needs packages/shared).
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY packages/shared /app/packages/shared
COPY apps/agent-runtime/requirements.txt /app/apps/agent-runtime/requirements.txt
RUN pip install --no-cache-dir -e /app/packages/shared \
    && pip install --no-cache-dir -r /app/apps/agent-runtime/requirements.txt
COPY apps/agent-runtime /app/apps/agent-runtime
WORKDIR /app/apps/agent-runtime
CMD ["python", "-m", "agent_runtime.worker"]
