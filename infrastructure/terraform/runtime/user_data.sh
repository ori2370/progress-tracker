#!/bin/bash
set -euo pipefail

COMPOSE_VERSION="v5.6.1"

dnf install -y docker curl python3

systemctl enable --now docker
systemctl enable --now amazon-ssm-agent

COMPOSE_INSTALL_DIR="$(mktemp -d)"
trap 'rm -rf "$COMPOSE_INSTALL_DIR"' EXIT

cd "$COMPOSE_INSTALL_DIR"

curl -fSL \
  "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
  -o docker-compose-linux-x86_64

curl -fSL \
  "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64.sha256" \
  -o docker-compose-linux-x86_64.sha256

sha256sum -c docker-compose-linux-x86_64.sha256

install -d -m 0755 /usr/local/lib/docker/cli-plugins

install -m 0755 docker-compose-linux-x86_64 \
  /usr/local/lib/docker/cli-plugins/docker-compose

install -d -m 0750 /opt/progress-tracker

docker compose version