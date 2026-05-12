#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" != "0" ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

SESSION_DIR="/root/.openclaw/agents/main/sessions"

echo "OpenClaw processes:"
pgrep -af "openclaw|node.*openclaw" || true

echo
echo "Session locks:"
if compgen -G "$SESSION_DIR/*.lock" >/dev/null; then
  ls -la "$SESSION_DIR"/*.lock
else
  echo "No session lock files found."
fi

echo
echo "Stopping gateway processes..."
pkill -f "openclaw gateway" || true
sleep 2

echo "Removing stale session locks..."
rm -f "$SESSION_DIR"/*.lock

echo "Starting gateway..."
nohup openclaw gateway --force >/tmp/openclaw-gateway.log 2>&1 &
sleep 10

echo
echo "Gateway log tail:"
tail -120 /tmp/openclaw-gateway.log
