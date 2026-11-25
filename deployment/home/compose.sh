#!/bin/bash
set -euo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIRECTORY="$(cd -- "$SCRIPT_DIRECTORY/../.." && pwd)"

ENV_FILE="${TRACKER_ENV_FILE:-$HOME/.config/progress-tracker/home.env}"

if [[ ! -s "$ENV_FILE" ]]; then
    echo "Home configuration is missing or empty: $ENV_FILE" >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required. Run this on the server or in Ubuntu WSL." >&2
    exit 1
fi

exec docker compose \
    --env-file "$ENV_FILE" \
    -f "$PROJECT_DIRECTORY/deployment/compose.yml" \
    -f "$SCRIPT_DIRECTORY/compose.override.yml" \
    "$@"