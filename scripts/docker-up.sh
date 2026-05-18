#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/deploy/.env"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command is not available. Install Docker Engine first: https://docs.docker.com/engine/install/" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose is not available. Install the Docker Compose plugin first." >&2
  exit 1
fi

mkdir -p "$ROOT_DIR/deploy"
if [ ! -f "$ENV_FILE" ]; then
  if command -v openssl >/dev/null 2>&1; then
    API_KEY="$(openssl rand -hex 32)"
  else
    API_KEY="$(date +%s)-replace-with-random-key"
  fi
  cat > "$ENV_FILE" <<EOF
AGENT_TOOL_API_KEY=$API_KEY
POSTGRES_PASSWORD=enterprise_ai
ALLOW_UNBOUND_AGENT_ACTOR_FALLBACK=false
EOF
  echo "Created deploy/.env with a generated AGENT_TOOL_API_KEY."
fi

cd "$ROOT_DIR"
docker compose --env-file "$ENV_FILE" -f deploy/docker-compose.yml config >/dev/null
docker compose --env-file "$ENV_FILE" -f deploy/docker-compose.yml up --build
