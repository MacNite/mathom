# Mathom backend — FastAPI + faster-whisper + FFmpeg
# Build context is the repository root: docker build -f backend/Dockerfile .
FROM python:3.11-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

FROM base AS runtime

RUN groupadd --gid 1000 mathom && useradd --uid 1000 --gid mathom --create-home mathom

WORKDIR /srv/mathom

COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir ".[ml]"

COPY --chown=mathom:mathom prompt-templates ./prompt-templates

ENV MATHOM_DATA_DIR=/data \
    MATHOM_TEMPLATES_DIR=/srv/mathom/prompt-templates \
    HF_HOME=/models/hf

RUN mkdir -p /data /models/hf && chown -R mathom:mathom /data /models

USER mathom

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
