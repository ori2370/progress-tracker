#!/bin/bash
set -euo pipefail
umask 077

if [[ "$#" -ne 3 ]]; then
    echo "Usage: restore-test.sh COMPOSE_FILE PRIVATE_KEY_FILE BACKUP_FILE"
    exit 1
fi

COMPOSE_FILE="$1"
PRIVATE_KEY_FILE="$2"
BACKUP_FILE="$3"

for command in docker age; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Required command not found: $command" >&2
        exit 1
    fi
done

for file in "$COMPOSE_FILE" "$PRIVATE_KEY_FILE" "$BACKUP_FILE"; do
    if [[ ! -s "$file" ]]; then
        echo "Required file is missing or empty: $file" >&2
        exit 1
    fi
done

TEST_DATABASE="restore_test_$(date -u +%Y%m%d_%H%M%S)_${RANDOM}"

echo "Creating isolated database: $TEST_DATABASE"

docker compose -f "$COMPOSE_FILE" exec -T db \
    sh -c 'exec createdb -U "$POSTGRES_USER" "$1"' \
    sh "$TEST_DATABASE"

echo "Decrypting and restoring backup..."

if ! age --decrypt --identity "$PRIVATE_KEY_FILE" "$BACKUP_FILE" \
    | docker compose -f "$COMPOSE_FILE" exec -T db \
        sh -c 'exec pg_restore \
            -U "$POSTGRES_USER" \
            -d "$1" \
            --no-owner \
            --no-acl \
            --exit-on-error \
            --single-transaction' \
        sh "$TEST_DATABASE"; then

    echo "Restore failed. Removing the newly created test database." >&2

    docker compose -f "$COMPOSE_FILE" exec -T db \
        sh -c 'exec dropdb -U "$POSTGRES_USER" "$1"' \
        sh "$TEST_DATABASE"

    exit 1
fi

docker compose -f "$COMPOSE_FILE" exec -T db \
    sh -c 'exec psql -X -v ON_ERROR_STOP=1 \
        -U "$POSTGRES_USER" -d "$1" -c "\dt"' \
    sh "$TEST_DATABASE"

echo "Restore completed successfully: $TEST_DATABASE"
echo "Test database retained for inspection."
echo "The application database was not changed."