# syntax=docker/dockerfile:1.6
# Multi-stage build for Python FastAPI application

# Stage 1: Build stage
ARG PY_BASE_IMAGE=python:3.11-slim-bookworm
FROM ${PY_BASE_IMAGE} AS builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update -o Acquire::Retries=5 && \
    apt-get install -y --no-install-recommends \
    gcc \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

## Copy requirements and install Python dependencies in cache-friendly layers
# 1) Upgrade pip tooling (cached unless this line changes)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --user -U pip setuptools wheel

# 2) Install Torch from the CPU wheel index first (let pip pick a compatible version)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip --default-timeout=180 install --no-cache-dir --user \
    --index-url https://download.pytorch.org/whl/cpu \
    torch \
    --extra-index-url https://pypi.org/simple

# 3) Install heavy ML/userland libs separately for better caching
COPY requirements-ml.txt ./requirements-ml.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip --default-timeout=180 install --no-cache-dir --user --prefer-binary -r requirements-ml.txt

# 4) Then install the rest; prefer wheels and extend timeout
COPY requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip --default-timeout=180 install --no-cache-dir --user --prefer-binary -r requirements.txt

# Configure model caches and defaults; warm up CrossEncoder to avoid runtime downloads
ENV HF_HOME=/root/.cache/huggingface \
    TRANSFORMERS_CACHE=/root/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/root/.cache/sentence-transformers \
    HF_HUB_TIMEOUT=120 \
    HF_HUB_ENABLE_HF_TRANSFER=1 \
    RERANK_CROSS_ENCODER=cross-encoder/ms-marco-MiniLM-L6-v2

# Ensure cache directories exist (copy will succeed even without warmup)
RUN mkdir -p /root/.cache/huggingface /root/.cache/sentence-transformers

# Optional: Prewarm model caches (CrossEncoder, etc.) to speed first run
ARG PREWARM_MODELS=false
RUN python - <<'PY' || true
import os
if os.environ.get('PREWARM_MODELS', 'false').lower() == 'true':
    os.environ.setdefault('HF_HOME', '/root/.cache/huggingface')
    os.environ.setdefault('TRANSFORMERS_CACHE', '/root/.cache/huggingface')
    os.environ.setdefault('SENTENCE_TRANSFORMERS_HOME', '/root/.cache/sentence-transformers')
    model = os.environ.get('RERANK_CROSS_ENCODER', 'cross-encoder/ms-marco-MiniLM-L6-v2')
    try:
        from sentence_transformers import CrossEncoder
        ce = CrossEncoder(model)
        print('CrossEncoder prewarmed:', model)
    except Exception as e:
        print('CrossEncoder prewarm failed:', e)
else:
    print('Skipping model prewarm')
PY

# Stage 2: Production stage
ARG PY_RUN_IMAGE=python:3.11-slim-bookworm
FROM ${PY_RUN_IMAGE}

# Create non-root user (with home directory)
RUN groupadd -r appuser && useradd -m -r -g appuser appuser

# Set working directory
WORKDIR /app

# Install runtime system dependencies (tini for PID1)
RUN apt-get update -o Acquire::Retries=5 && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    tini \
    tesseract-ocr \
    tesseract-ocr-eng && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Copy warmed caches from builder
COPY --from=builder /root/.cache /home/appuser/.cache

# Copy application code
COPY src/ ./src/

# Create logs directory
RUN mkdir -p logs /home/appuser/.cache && chown -R appuser:appuser /app /home/appuser/.cache /home/appuser/.local

# Switch to non-root user
USER appuser

# Set Python path to include application source
ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1
ENV PATH=/home/appuser/.local/bin:$PATH
ENV HF_HOME=/home/appuser/.cache/huggingface \
    TRANSFORMERS_CACHE=/home/appuser/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/home/appuser/.cache/sentence-transformers \
    HF_HUB_TIMEOUT=120 \
    HF_HUB_ENABLE_HF_TRANSFER=1 \
    RERANK_CROSS_ENCODER=cross-encoder/ms-marco-MiniLM-L6-v2

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/v1/health || exit 1

# Entrypoint with tini for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]
# Start the application (module path matches PYTHONPATH)
CMD ["uvicorn", "ai_core.main:app", "--host", "0.0.0.0", "--port", "8000"]
