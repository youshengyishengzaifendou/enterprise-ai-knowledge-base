#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command is not available in this environment" >&2
  exit 1
fi

docker compose -f deploy/docker-compose.yml config

