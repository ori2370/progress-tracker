#!/bin/bash
set -euo pipefail
umask 077

if [[ "$#" -ne 3 ]]; then
    echo "Usage: backup.sh COMPOSE_FILE RECIPIENT_FILE BACKUP_DIRECTORY"
    exit 1
fi

COMPOSE_FILE="$1"
RECIPIENT_FILE="$2"
BACKUP_DIRECTORY="$3"

for command in docker age; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Required command not found: $command" >&2
        exit 1
    fi
done

if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Compose file not found." >&2
    exit 1
fi

if [[ ! -s "$RECIPIENT_FILE" ]]; then
    echo "Public recipient file is missing or empty." >&2
    exit 1
fi

mkdir -p -- "$BACKUP_DIRECTORY"

# Use a private temporary directory on the same filesystem.
WORK_DIRECTORY="$(mktemp -d "$BACKUP_DIRECTORY/.backup-XXXXXXXX")"
trap 'rm -rf -- "$WORK_DIRECTORY"' EXIT

BACKUP_NAME="database-$(date -u +%Y%m%dT%H%M%S)-${WORK_DIRECTORY##*.backup-}.dump.age"
BACKUP_PATH="$BACKUP_DIRECTORY/$BACKUP_NAME"

echo "Creating compressed, encrypted PostgreSQL backup..."

docker compose -f "$COMPOSE_FILE" exec -T db \
    sh -c 'exec pg_dump \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        --format=custom \
        --no-owner \
        --no-acl' \
    | age \
        --recipients-file "$RECIPIENT_FILE" \
        --output "$WORK_DIRECTORY/backup.dump.age"

# Publish the backup only after both commands succeed.
mv -- "$WORK_DIRECTORY/backup.dump.age" "$BACKUP_PATH"

printf 'Backup created: %s\n' "$BACKUP_PATH"
ls -lh -- "$BACKUP_PATH"