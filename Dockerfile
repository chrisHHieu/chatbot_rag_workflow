# Multi-stage Dockerfile for llmops_rag
# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/UI

# Copy frontend package files
COPY UI/package*.json ./

# Install frontend dependencies
RUN npm ci

# Copy frontend source
COPY UI/ ./

# Set build-time environment variable for API URL
# In Docker, frontend will connect to backend via relative URL or same domain
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Build frontend (output to dist/)
RUN npm run build

# Stage 2: Python Backend
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY multi_doc_chat/ ./multi_doc_chat/

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/UI/dist ./UI/dist

# Create directories for data, logs, and indexes
RUN mkdir -p /app/data /app/faiss_index /app/logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "multi_doc_chat.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

