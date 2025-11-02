# === Base image ===
FROM python:3.12-slim

# === Set working directory ===
WORKDIR /app

# === Copy requirements first and install ===
COPY server/requirements.txt .

# Add PyTorch CPU wheel index before install
RUN pip install --no-cache-dir torch==2.3.0 --extra-index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# === Copy all backend files ===
COPY server/ .

# === Environment variables ===
ENV PYTHONUNBUFFERED=1 \
    CELERY_BROKER_URL=redis://redis:6379/0 \
    CELERY_RESULT_BACKEND=redis://redis:6379/0

# === Expose FastAPI port ===
EXPOSE 8001

# === Default command ===
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
