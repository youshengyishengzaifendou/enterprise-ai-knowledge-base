#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR/backend"
.venv/bin/python -m pytest -q
TMP_DB="$(mktemp /tmp/enterprise-ai-assistant-alembic-XXXXXX.db)"
trap 'rm -f "$TMP_DB"' EXIT
DATABASE_URL="sqlite:///$TMP_DB" .venv/bin/alembic upgrade head

cd "$ROOT_DIR/agent/openclaw-plugin"
npm run build
npm audit --audit-level=moderate

cd "$ROOT_DIR/frontend"
npm run build
npm audit --audit-level=moderate
