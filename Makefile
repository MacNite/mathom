.PHONY: help up up-gpu down logs models backup test test-backend test-frontend lint build validate

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

up: ## Start the CPU stack
	docker compose -f compose.yaml up -d --build

up-gpu: ## Start the stack with NVIDIA GPU support
	docker compose -f compose.yaml -f compose.gpu.yaml up -d --build

down: ## Stop the stack
	docker compose -f compose.yaml down

logs: ## Tail logs from every service
	docker compose -f compose.yaml logs -f

models: ## Pull the configured Ollama model into the running stack
	./scripts/pull-model.sh

backup: ## Snapshot the SQLite database and audio files
	./scripts/backup.sh

test: test-backend test-frontend ## Run all tests

test-backend: ## Backend: pytest
	cd backend && python -m pytest

test-frontend: ## Frontend: vitest
	cd frontend && npm test

lint: ## Lint and type-check both apps
	cd backend && python -m ruff check app tests && python -m mypy app
	cd frontend && npm run lint && npm run typecheck

build: ## Build the mathom image
	docker compose -f compose.yaml build

validate: ## Validate both compose stacks
	docker compose -f compose.yaml config -q
	docker compose -f compose.yaml -f compose.gpu.yaml config -q
