# Changelog

All notable changes to Mathom are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Initial Mathom stack: FastAPI backend, React + Vite + Tailwind frontend,
  nginx proxy, Ollama and faster-whisper integration, SQLite storage.
- Mathom-house archive: upload → transcribe → summarize pipeline with status
  tracking, tags, favorites, archive, collections, timeline, and exports
  (Markdown / text / JSON).
- Full-text search (SQLite FTS5) with highlighted snippets.
- Follow-up AI chat grounded in each recording's transcript.
- 12 editable prompt templates seeded into SQLite.
- Docker Compose stack (CPU + NVIDIA GPU overlay), health checks, non-root
  containers, persistent volumes; TrueNAS SCALE deployment guide.
- CI: backend and frontend pipelines, compose validation, Docker builds,
  security scanning, GHCR release publishing.
