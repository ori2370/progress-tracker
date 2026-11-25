#!/bin/bash
set -euo pipefail
umask 077

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIRECTORY="$(cd -- "$SCRIPT_DIRECTORY/../.." && pwd)"
CONFIG_DIRECTORY="$HOME/.config/progress-tracker"
STATE_DIRECTORY="$HOME/.local/state/progress-tracker"
BACKUP_DIRECTORY="$HOME/.local/share/progress-tracker/backups"
ENV_FILE="$CONFIG_DIRECTORY/home.env"

IMAGE_REPOSITORY="ghcr.io/ori2370/progress-tracker"
UPDATE_IMAGE="$IMAGE_REPOSITORY:home"

install -d -m 700 "$STATE_DIRECTORY"

exec 9>"$STATE_DIRECTORY/update.lock"
flock -n 9 || exit 0

if [[ -e "$STATE_DIRECTORY/update-blocked" ]]; then
    echo "Automatic updates are paused after an interrupted or failed deployment."
    echo "Inspect the service logs before removing:"
    echo "$STATE_DIRECTORY/update-blocked"
    exit 1
fi

if [[ ! -s "$ENV_FILE" ]]; then
    echo "Missing private configuration: $ENV_FILE" >&2
    exit 1
fi

# This is a trusted, locally managed configuration file.
set -a
source "$ENV_FILE"
set +a

export TRACKER_ENV_FILE="$ENV_FILE"

compose() {
    bash "$SCRIPT_DIRECTORY/compose.sh" "$@"
}

echo "Checking for a published home-server image..."
docker pull "$UPDATE_IMAGE"

TARGET_IMAGE="$(
    docker image inspect "$UPDATE_IMAGE" \
        --format '{{range .RepoDigests}}{{println .}}{{end}}' |
        awk -v prefix="$IMAGE_REPOSITORY@sha256:" \
            'index($0, prefix) == 1 {print; exit}'
)"

if [[ ! "$TARGET_IMAGE" =~ ^ghcr\.io/ori2370/progress-tracker@sha256:[a-f0-9]{64}$ ]]; then
    echo "Could not determine a valid release digest." >&2
    exit 1
fi

WEB_CONTAINER="$(compose ps -q web)"

if [[ -z "$WEB_CONTAINER" ]]; then
    echo "No running web container found. Complete initial deployment first." >&2
    exit 1
fi

CURRENT_IMAGE_ID="$(
    docker inspect --format '{{.Image}}' "$WEB_CONTAINER"
)"
TARGET_IMAGE_ID="$(
    docker image inspect --format '{{.Id}}' "$TARGET_IMAGE"
)"

if [[ "$CURRENT_IMAGE_ID" == "$TARGET_IMAGE_ID" ]]; then
    echo "Application is already up to date."
    exit 0
fi

PREVIOUS_IMAGE="$(
    docker inspect --format '{{.Config.Image}}' "$WEB_CONTAINER"
)"

printf '%s\n' "$PREVIOUS_IMAGE" > "$STATE_DIRECTORY/previous-image"
printf '%s\n' "$TARGET_IMAGE" > "$STATE_DIRECTORY/pending-image"

echo "Creating a backup before deployment..."
flock -w 120 "$CONFIG_DIRECTORY/backup.lock" \
    bash "$PROJECT_DIRECTORY/deployment/backup.sh" \
    "$PROJECT_DIRECTORY/deployment/compose.yml" \
    "$CONFIG_DIRECTORY/backup-recipient.txt" \
    "$BACKUP_DIRECTORY"

export APP_IMAGE="$TARGET_IMAGE"
compose config --quiet

# Leave this marker in place if any later command fails or is interrupted.
printf '%s\n' "$TARGET_IMAGE" > "$STATE_DIRECTORY/update-blocked"

echo "Applying database migrations..."
compose run --rm --no-deps web \
    python manage.py migrate --noinput

echo "Refreshing the exercise catalog..."
compose run --rm --no-deps web \
    python manage.py import_exercise_catalog \
    data/free-exercise-db/exercises.json

echo "Starting the new application image..."
compose up -d --no-deps --wait --wait-timeout 120 web

echo "Checking application readiness..."
curl --fail --show-error --silent --max-time 10 \
    "http://127.0.0.1:${APP_PORT:-18743}/health/ready/"
echo

# Persist the successful digest without replacing other settings.
python3 - "$ENV_FILE" "$TARGET_IMAGE" <<'PY'
import os
import sys
import tempfile
from pathlib import Path

path = Path(sys.argv[1])
image = sys.argv[2]
lines = path.read_text().splitlines()
updated = []
found = False

for line in lines:
    if line.startswith("APP_IMAGE="):
        updated.append(f"APP_IMAGE={image}")
        found = True
    else:
        updated.append(line)

if not found:
    updated.append(f"APP_IMAGE={image}")

fd, temporary = tempfile.mkstemp(
    prefix=".home-env-",
    dir=path.parent,
)

try:
    with os.fdopen(fd, "w") as file:
        file.write("\n".join(updated) + "\n")
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY

printf '%s\n' "$TARGET_IMAGE" > "$STATE_DIRECTORY/current-image"
rm -f "$STATE_DIRECTORY/update-blocked" "$STATE_DIRECTORY/pending-image"

echo "Deployment completed successfully: $TARGET_IMAGE"