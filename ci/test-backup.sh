#!/bin/bash
set -euo pipefail
umask 077

COMPOSE_FILE="ci/compose.backup.yml"
TEST_DIRECTORY="$(mktemp -d)"

cleanup() {
    local result=$?

    if [[ "$result" -ne 0 ]]; then
        docker compose -f "$COMPOSE_FILE" logs || true
    fi

    docker compose -f "$COMPOSE_FILE" \
        down --volumes --remove-orphans || true

    rm -rf -- "$TEST_DIRECTORY"
    exit "$result"
}

trap cleanup EXIT

echo "Generating temporary test keys..."
age-keygen -o "$TEST_DIRECTORY/key.txt"
age-keygen -y "$TEST_DIRECTORY/key.txt" \
    > "$TEST_DIRECTORY/recipient.txt"

echo "Starting isolated PostgreSQL..."
docker compose -f "$COMPOSE_FILE" \
    up -d --wait --wait-timeout 120 db

echo "Creating sample data..."
docker compose -f "$COMPOSE_FILE" exec -T db \
    psql -X -v ON_ERROR_STOP=1 -U backup_test -d backup_source \
    -c "CREATE TABLE backup_probe (
            id integer PRIMARY KEY,
            category text NOT NULL
        );
        INSERT INTO backup_probe VALUES
            (1, 'tennis'), (2, 'gym'), (3, 'posture');"

echo "Testing encrypted backup..."
bash deployment/backup.sh \
    "$COMPOSE_FILE" \
    "$TEST_DIRECTORY/recipient.txt" \
    "$TEST_DIRECTORY/backups"

backups=("$TEST_DIRECTORY"/backups/*.dump.age)
test "${#backups[@]}" -eq 1
test -f "${backups[0]}"
test "$(stat -c '%a' "${backups[0]}")" = "600"

echo "Testing restore..."
bash deployment/restore-test.sh \
    "$COMPOSE_FILE" \
    "$TEST_DIRECTORY/key.txt" \
    "${backups[0]}"

restored_database=$(docker compose -f "$COMPOSE_FILE" exec -T db \
    psql -X -At -v ON_ERROR_STOP=1 -U backup_test -d backup_source \
    -c "SELECT datname FROM pg_database
        WHERE starts_with(datname, 'restore_test_');")

test -n "$restored_database"

echo "Comparing original and restored records..."
for database in backup_source "$restored_database"; do
    docker compose -f "$COMPOSE_FILE" exec -T db \
        psql -X -At -v ON_ERROR_STOP=1 \
        -U backup_test -d "$database" \
        -c "SELECT id, category FROM backup_probe ORDER BY id;" \
        > "$TEST_DIRECTORY/$database.txt"
done

test "$(wc -l < "$TEST_DIRECTORY/backup_source.txt")" -eq 3

cmp "$TEST_DIRECTORY/backup_source.txt" \
    "$TEST_DIRECTORY/$restored_database.txt"

echo "PASS: encrypted backup and restore preserved all sample records."