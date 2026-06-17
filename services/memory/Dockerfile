# Build context = repo root (needs packages/shared).
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY packages/shared /app/packages/shared
COPY VERSION /app/VERSION
COPY services/memory/requirements.txt /app/services/memory/requirements.txt
RUN pip install --no-cache-dir -e /app/packages/shared \
    && pip install --no-cache-dir -r /app/services/memory/requirements.txt
COPY services/memory /app/services/memory
ENV PYTHONPATH=/app/services/memory/src
WORKDIR /app/services/memory
EXPOSE 8000
CMD ["uvicorn", "memory.main:app", "--host", "0.0.0.0", "--port", "8000"]
