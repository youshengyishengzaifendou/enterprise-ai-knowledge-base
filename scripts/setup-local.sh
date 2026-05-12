#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -e '.[test]'
if [ ! -f .env ]; then
  cp "$ROOT_DIR/.env.example" .env
fi
.venv/bin/alembic upgrade head

cd "$ROOT_DIR/agent/openclaw-plugin"
npm install
npm run build

cd "$ROOT_DIR/frontend"
npm install
npm run build

echo "Local setup complete."
echo "Start backend: cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000"
echo "Install plugin: cd agent/openclaw-plugin && openclaw plugins install --link \"$(pwd)\""
