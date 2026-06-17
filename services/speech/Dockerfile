# Build context = repo root (needs packages/shared).
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY packages/shared /app/packages/shared
COPY services/speech/requirements.txt /app/services/speech/requirements.txt
RUN pip install --no-cache-dir -e /app/packages/shared \
    && pip install --no-cache-dir -r /app/services/speech/requirements.txt
COPY services/speech /app/services/speech
WORKDIR /app/services/speech
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
