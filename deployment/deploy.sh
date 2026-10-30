#!/bin/bash
set -euo pipefail
umask 077

if [[ "$EUID" -ne 0 ]]; then
    echo "Run this script as root."
    exit 1
fi

if [[ "$#" -ne 1 ]]; then
    echo "Usage: deploy.sh ECR_IMAGE_URI_WITH_DIGEST"
    exit 1
fi

export APP_IMAGE="$1"

IMAGE_PATTERN='^[0-9]{12}\.dkr\.ecr\.us-east-1\.amazonaws\.com/progress-tracker@sha256:[a-f0-9]{64}$'

if [[ ! "$APP_IMAGE" =~ $IMAGE_PATTERN ]]; then
    echo "Expected a Progress Tracker ECR image digest in us-east-1."
    exit 1
fi

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$DEPLOY_DIR"

if [[ ! -f compose.yml ]]; then
    echo "compose.yml must be alongside deploy.sh."
    exit 1
fi

# Prevent two deployments from running simultaneously.
exec 9>/run/lock/progress-tracker-deploy.lock
flock -n 9 || {
    echo "Another deployment is already running."
    exit 1
}

# Only generate credentials on the first deployment.
if [[ ! -e .env ]]; then
    python3 - <<'PY'
import os
import secrets

content = "\n".join([
    "DJANGO_SECRET_KEY=" + secrets.token_hex(32),
    "DJANGO_DEBUG=false",
    "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1",
    "POSTGRES_DB=progress_tracker",
    "POSTGRES_USER=progress_tracker",
    "POSTGRES_PASSWORD=" + secrets.token_hex(24),
    "POSTGRES_HOST=db",
    "POSTGRES_PORT=5432",
    "",
])

fd = os.open(
    ".env",
    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
    0o600,
)

with os.fdopen(fd, "w") as file:
    file.write(content)

print("Generated credentials for the new installation.")
PY
fi

chmod 600 .env

REGISTRY="${APP_IMAGE%%/*}"

aws ecr get-login-password --region us-east-1 \
    | docker login \
        --username AWS \
        --password-stdin \
        "$REGISTRY"

docker compose config --quiet

echo "Pulling deployment images..."
docker compose pull

echo "Starting PostgreSQL..."
docker compose up -d --wait --wait-timeout 120 db

echo "Applying database migrations..."
docker compose run --rm --no-deps web \
    python manage.py migrate --noinput

echo "Starting application..."
docker compose up -d --wait --wait-timeout 120 web

echo "Deployment completed successfully."
docker compose ps