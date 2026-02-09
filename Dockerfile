FROM python:3.12-slim AS builder

WORKDIR /app

# Build deps only for wheels/crypto/argon2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---- Runtime image ----
FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:$PATH"

COPY --from=builder /opt/venv /opt/venv

# Create non-root user and directories first
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && mkdir -p /app/logs /app/data \
    && chmod 755 /app/logs /app/data

COPY . .

# Change ownership of all files to appuser
RUN chown -R appuser:appuser /app

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Entrypoint runs as root to fix permissions, then switches to appuser
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "backend/main.py"]
