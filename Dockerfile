# mathom — single image: React frontend + FastAPI backend + nginx in one container.
# The frontend is built, the backend installed, and nginx + uvicorn are run
# together under supervisord as a non-root user.
# Build context is the repository root: docker build -t mathom .

# ---- Stage 1: build the frontend ----
FROM node:22-alpine AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: runtime — Python backend + nginx + supervisord ----
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl nginx \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 mathom && useradd --uid 1000 --gid mathom --create-home mathom

WORKDIR /srv/mathom

# Backend (+ supervisord, which manages the two runtime processes).
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir ".[ml]" supervisor

COPY --chown=mathom:mathom prompt-templates ./prompt-templates

# Built frontend, served directly by nginx from this image.
COPY --from=frontend /build/dist /srv/mathom/web

# nginx + supervisord configuration.
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/supervisord.conf /etc/supervisor/supervisord.conf

ENV MATHOM_DATA_DIR=/data \
    MATHOM_TEMPLATES_DIR=/srv/mathom/prompt-templates \
    HF_HOME=/models/hf

# Writable paths for the non-root user: app data, whisper models, and the
# directories nginx needs for its pid, temp files, and caches.
RUN mkdir -p /data /models/hf /var/cache/nginx \
    && chown -R mathom:mathom /data /models /var/cache/nginx /srv/mathom

USER mathom

EXPOSE 8080

# One check covers the whole image: nginx serves it and proxies to the backend,
# so a healthy /api/health means both processes are up.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/api/health || exit 1

CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
