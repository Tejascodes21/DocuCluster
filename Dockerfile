# Production Dockerfile for DocuCluster AI
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy application files
COPY backend/ backend/
COPY frontend/ frontend/
COPY .env.example .env

# Expose server port
EXPOSE 5000

ENV PORT=5000
ENV PYTHONUNBUFFERED=1

# Run with Waitress WSGI server
CMD ["python", "-m", "backend.app"]
