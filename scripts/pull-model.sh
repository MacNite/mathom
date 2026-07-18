#!/usr/bin/env bash
# Pull the configured Ollama model inside the running stack.
set -euo pipefail

cd "$(dirname "$0")/.."

MODEL="${OLLAMA_MODEL:-}"
if [[ -z "$MODEL" && -f .env ]]; then
  MODEL="$(grep -E '^OLLAMA_MODEL=' .env | tail -1 | cut -d= -f2- || true)"
fi
MODEL="${MODEL:-llama3.2}"

echo "Pulling Ollama model: $MODEL"
docker compose -f compose.yaml exec ollama ollama pull "$MODEL"
echo "Done. Mathom will use $MODEL for summaries and chat."
