# Build context = repo root (needs packages/shared). 24/7 worker, not an API.
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY packages/shared /app/packages/shared
COPY VERSION /app/VERSION
RUN pip install --no-cache-dir -e /app/packages/shared
COPY services/harvester /app/services/harvester
ENV PYTHONPATH=/app/services/harvester/src:/app/packages/shared/src
CMD ["python3", "services/harvester/src/harvester/run.py", "--checkpoint", "/var/harvester/cp.json"]
