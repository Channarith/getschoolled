# Build context = repo root (needs packages/shared).
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY packages/shared /app/packages/shared
COPY VERSION /app/VERSION
COPY services/integrations/requirements.txt /app/services/integrations/requirements.txt
RUN pip install --no-cache-dir -e /app/packages/shared \
    && pip install --no-cache-dir -r /app/services/integrations/requirements.txt
COPY services/integrations /app/services/integrations
ENV PYTHONPATH=/app/services/integrations/src
WORKDIR /app/services/integrations
EXPOSE 8000
CMD ["uvicorn", "integrations.main:app", "--host", "0.0.0.0", "--port", "8000"]
