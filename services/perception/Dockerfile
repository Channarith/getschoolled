# Build context = repo root (needs packages/shared).
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# OpenCV runtime needs libGL/libglib even for the headless wheel's deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY packages/shared /app/packages/shared
COPY services/perception/requirements.txt /app/services/perception/requirements.txt
RUN pip install --no-cache-dir -e /app/packages/shared \
    && pip install --no-cache-dir -r /app/services/perception/requirements.txt
COPY services/perception /app/services/perception
ENV PYTHONPATH=/app/services/perception/src
WORKDIR /app/services/perception
EXPOSE 8000
CMD ["uvicorn", "perception.main:app", "--host", "0.0.0.0", "--port", "8000"]
