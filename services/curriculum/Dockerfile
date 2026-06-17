# Build context = repo root (needs packages/shared and sample-curriculum).
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY packages/shared /app/packages/shared
COPY services/curriculum/requirements.txt /app/services/curriculum/requirements.txt
RUN pip install --no-cache-dir -e /app/packages/shared \
    && pip install --no-cache-dir -r /app/services/curriculum/requirements.txt
COPY services/curriculum /app/services/curriculum
COPY sample-curriculum /app/sample-curriculum
ENV PYTHONPATH=/app/services/curriculum/src
WORKDIR /app/services/curriculum
EXPOSE 8000
CMD ["uvicorn", "curriculum.main:app", "--host", "0.0.0.0", "--port", "8000"]
