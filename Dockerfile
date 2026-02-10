FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ffmpeg \
    zlib1g-dev \
    libjpeg-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/* \
    && git config --global --add safe.directory '*'

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install uv && \
    uv pip install --system -e .

COPY blocks/ ./blocks/
COPY workflows/ ./workflows/
COPY config/ ./config/
COPY scripts/ ./scripts/

ENV PYTHONPATH=/app
