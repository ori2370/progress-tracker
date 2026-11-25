#!/bin/bash
set -euo pipefail

IMAGE="progress-tracker:ci"
NETWORK="progress-tracker-ci"
readiness_response=""

cleanup() {
    local result=$?

    if [[ "$result" -ne 0 ]]; then
        docker logs db 2>/dev/null || true
        docker logs web 2>/dev/null || true
    fi

    if [[ -n "$readiness_response" ]]; then
        rm -f -- "$readiness_response"
    fi

    docker rm -f web db >/dev/null 2>&1 || true
    docker network rm "$NETWORK" >/dev/null 2>&1 || true

    exit "$result"
}

trap cleanup EXIT

wait_for_readiness() {
    for attempt in $(seq 1 30); do
        if curl --fail --silent --max-time 5 \
            --output /dev/null \
            http://127.0.0.1:8080/health/ready/; then
            return 0
        fi

        sleep 2
    done

    echo "Application did not become ready." >&2
    return 1
}

echo "Building the application image..."
docker build -t "$IMAGE" .

echo "Checking that the application runs as a non-root user..."
test "$(docker run --rm "$IMAGE" id -u)" != "0"

echo "Starting PostgreSQL..."
docker network create "$NETWORK"

docker run -d \
    --name db \
    --network "$NETWORK" \
    -e POSTGRES_DB=progress_tracker \
    -e POSTGRES_USER=progress_tracker \
    -e POSTGRES_PASSWORD=ci-only-database-password \
    --health-cmd="pg_isready -U progress_tracker -d progress_tracker" \
    --health-interval=2s \
    --health-timeout=5s \
    --health-retries=30 \
    postgres:17-bookworm

database_ready=false

for attempt in $(seq 1 60); do
    if [[ "$(docker inspect --format='{{.State.Health.Status}}' db)" = healthy ]]; then
        database_ready=true
        break
    fi

    sleep 2
done

if [[ "$database_ready" != true ]]; then
    echo "PostgreSQL did not become healthy." >&2
    exit 1
fi

echo "Starting the application..."
docker run -d \
    --name web \
    --network "$NETWORK" \
    -p 127.0.0.1:8080:8000 \
    -e DJANGO_SECRET_KEY=ci-only-key-not-for-deployment \
    -e DJANGO_DEBUG=false \
    -e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
    -e POSTGRES_DB=progress_tracker \
    -e POSTGRES_USER=progress_tracker \
    -e POSTGRES_PASSWORD=ci-only-database-password \
    -e POSTGRES_HOST=db \
    -e POSTGRES_PORT=5432 \
    "$IMAGE" \
    /bin/sh -c \
    'python manage.py migrate --noinput &&
     python manage.py collectstatic --noinput &&
     exec gunicorn config.wsgi:application \
       --bind 0.0.0.0:8000 \
       --access-logfile - \
       --error-logfile -'

wait_for_readiness

echo "Checking health endpoints, login page, and CSS..."
for endpoint in \
    /health/live/ \
    /health/ready/ \
    /admin/login/ \
    /static/tracking/css/base.css \
    /static/tracking/css/gym.css \
    /static/tracking/css/tennis.css; do

    curl --fail --show-error --silent --max-time 5 \
        --output /dev/null \
        "http://127.0.0.1:8080${endpoint}"
done

echo "Checking behavior while PostgreSQL is stopped..."
docker stop db

curl --fail --show-error --silent --max-time 5 \
    --output /dev/null \
    http://127.0.0.1:8080/health/live/

readiness_response="$(mktemp)"

status=$(curl --show-error --silent --max-time 10 \
    --output "$readiness_response" \
    --write-out "%{http_code}" \
    http://127.0.0.1:8080/health/ready/)

test "$status" = "503"

python3 - "$readiness_response" <<'PY'
import json
import sys

with open(sys.argv[1]) as response:
    assert json.load(response) == {"status": "not_ready"}
PY

echo "Checking recovery after PostgreSQL restarts..."
docker start db
wait_for_readiness

echo "PASS: container checks completed."
