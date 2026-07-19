#!/usr/bin/env bash
# Snapshot the SQLite database (consistent copy) and the audio directory
# from the mathom-data volume into ./backups/.
set -euo pipefail

cd "$(dirname "$0")/.."

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="backups/mathom-$STAMP"
mkdir -p "$BACKUP_DIR"

echo "Creating consistent SQLite snapshot…"
docker compose -f compose.yaml exec app \
  python -c "import sqlite3; src = sqlite3.connect('/data/mathom.db'); dst = sqlite3.connect('/data/mathom-backup.db'); src.backup(dst); dst.close(); src.close()"

echo "Copying database and audio out of the volume…"
CONTAINER="$(docker compose -f compose.yaml ps -q app)"
docker cp "$CONTAINER:/data/mathom-backup.db" "$BACKUP_DIR/mathom.db"
docker cp "$CONTAINER:/data/audio" "$BACKUP_DIR/audio"
docker compose -f compose.yaml exec app rm -f /data/mathom-backup.db

echo "Backup complete: $BACKUP_DIR"
