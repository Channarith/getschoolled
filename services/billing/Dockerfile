# Build context = repo root (needs packages/shared).
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY packages/shared /app/packages/shared
COPY services/billing/requirements.txt /app/services/billing/requirements.txt
RUN pip install --no-cache-dir -e /app/packages/shared \
    && pip install --no-cache-dir -r /app/services/billing/requirements.txt
COPY services/billing /app/services/billing
WORKDIR /app/services/billing
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
