#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" != "0" ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

SESSION_DIR="/root/.openclaw/agents/main/sessions"

echo "Disabling hermes-collab for low-latency knowledge-base chat..."
openclaw config unset plugins.entries.hermes-collab || true
openclaw config patch --stdin <<'JSON'
{
  "plugins": {
    "allow": [
      "enterprise-ai-assistant",
      "feishu"
    ]
  }
}
JSON

echo "Removing stale session locks..."
rm -f "$SESSION_DIR"/*.lock

echo "Restarting OpenClaw gateway..."
pkill -f "openclaw gateway" || true
sleep 2
nohup openclaw gateway --force >/tmp/openclaw-gateway.log 2>&1 &
sleep 10

echo "Gateway log tail:"
tail -120 /tmp/openclaw-gateway.log
