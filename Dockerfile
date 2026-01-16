# Velites Dockerfile
# Multi-stage build for production deployment

# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim as production

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash velites

# Copy Python packages from builder
COPY --from=builder /root/.local /home/velites/.local

# Copy application code
COPY --chown=velites:velites src/ ./src/
COPY --chown=velites:velites data/ ./data/
COPY --chown=velites:velites config/ ./config/

# Create output directories
RUN mkdir -p /app/output/signals /app/logs && \
    chown -R velites:velites /app/output /app/logs

# Switch to non-root user
USER velites

# Add local bin to PATH
ENV PATH=/home/velites/.local/bin:$PATH
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from velites.core.config import settings; print(settings.app_name)" || exit 1

# Default command
CMD ["python", "-m", "velites.main"]
