# Dockerfile for D-GRID Worker Node
# Base: Python 3.11 Alpine (lightweight, ~150MB)
FROM python:3.11-alpine

# Metadata
LABEL maintainer="D-GRID"
LABEL description="D-GRID Worker Node - Decentralized Git-Relay Infrastructure"

# Install system dependencies (git, docker-cli, curl, build-essentials for psutil)
RUN apk add --no-cache \
    git \
    docker-cli \
    curl \
    ca-certificates \
    gcc \
    python3-dev \
    musl-dev \
    linux-headers

# Create working directory
WORKDIR /app

# Copia i file dei requirements
COPY worker/requirements.txt .

# Installa le dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice del worker
COPY worker/ .

# Variables di ambiente di default (possono essere sovrascritte)
ENV NODE_ID=default-worker
ENV GIT_USER_NAME="D-GRID Worker"
ENV GIT_USER_EMAIL="worker@d-grid.local"
ENV PULL_INTERVAL=10
ENV HEARTBEAT_INTERVAL=60
ENV LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || ps aux | grep -q "python3 main.py" || exit 1

# Entrypoint
ENTRYPOINT ["python3", "main.py"]
