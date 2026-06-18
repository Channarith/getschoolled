# Build context = repo root (needs packages/shared).
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY packages/shared /app/packages/shared
COPY VERSION /app/VERSION
COPY services/identity/requirements.txt /app/services/identity/requirements.txt
RUN pip install --no-cache-dir -e /app/packages/shared \
    && pip install --no-cache-dir -r /app/services/identity/requirements.txt
COPY services/identity /app/services/identity
ENV PYTHONPATH=/app/services/identity/src
WORKDIR /app/services/identity
EXPOSE 8000
CMD ["uvicorn", "identity.main:app", "--host", "0.0.0.0", "--port", "8000"]
