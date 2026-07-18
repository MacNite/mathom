#!/usr/bin/env bash
# Local development without Docker: backend on :8000, frontend dev server on :5173.
# Requires: python3.11+, node 20+, ffmpeg, and an Ollama instance
# (set MATHOM_OLLAMA_BASE_URL, default http://ollama:11434).
set -euo pipefail

cd "$(dirname "$0")/.."

(
  cd backend
  [[ -d .venv ]] || python3 -m venv .venv
  .venv/bin/pip install -q -e ".[dev]"
  MATHOM_TEMPLATES_DIR=../prompt-templates .venv/bin/uvicorn app.main:app --reload --port 8000
) &
BACKEND_PID=$!
trap 'kill $BACKEND_PID' EXIT

cd frontend
[[ -d node_modules ]] || npm install
npm run dev
