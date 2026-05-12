#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" != "0" ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_DIR="$ROOT_DIR/agent/openclaw-plugin"
INSTALL_DIR="/root/.openclaw/extensions/enterprise-ai-assistant"
WORKSPACE_TOOLS="/root/.openclaw/workspace/TOOLS.md"

cd "$PLUGIN_DIR"
npm run build

rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -a openclaw.plugin.json package.json package-lock.json dist skills "$INSTALL_DIR"/
chown -R root:root "$INSTALL_DIR"

node --input-type=module <<'NODE'
const plugin = await import("file:///root/.openclaw/extensions/enterprise-ai-assistant/dist/index.js");
const tools = [];
plugin.register({
  registerTool(_tool, options = {}) {
    tools.push({ name: options.name, optional: options.optional });
  },
});

const ingest = tools.find((tool) => tool.name === "kb_ingest_document");
if (!ingest) {
  console.error("kb_ingest_document is not registered in installed plugin.");
  process.exit(2);
}
if (ingest.optional !== false) {
  console.error(`kb_ingest_document must be non-optional, got optional=${ingest.optional}`);
  process.exit(3);
}
const record = tools.find((tool) => tool.name === "record_enterprise_knowledge");
if (!record) {
  console.error("record_enterprise_knowledge is not registered in installed plugin.");
  process.exit(4);
}
if (record.optional !== false) {
  console.error(`record_enterprise_knowledge must be non-optional, got optional=${record.optional}`);
  process.exit(5);
}

console.log("Installed plugin tools:");
for (const tool of tools) {
  console.log(`- ${tool.name} optional=${tool.optional}`);
}
NODE

mkdir -p "$(dirname "$WORKSPACE_TOOLS")"
touch "$WORKSPACE_TOOLS"
if ! grep -q "Enterprise AI Assistant Database Routing" "$WORKSPACE_TOOLS"; then
  cat >>"$WORKSPACE_TOOLS" <<'EOF'

## Enterprise AI Assistant Database Routing

When the user provides enterprise/customer/project资料 and says 记录、保存、记一下、写入、导入、加载, default to writing the content into the enterprise knowledge-base database using `record_enterprise_knowledge` or `kb_ingest_document`.

Do not save such business/project facts to workspace markdown files unless the user explicitly asks for a local file, 工作区文件, markdown, or 文档.

If the content mentions 恒润 and no project is specified, use `project_id="project-demo"`.

For multiple pasted documents, call the ingest tool once per document with `confirmed=true` and `source_type="manual"`.
EOF
fi
if ! grep -q "Enterprise AI Assistant Knowledge Source Order" "$WORKSPACE_TOOLS"; then
  cat >>"$WORKSPACE_TOOLS" <<'EOF'

## Enterprise AI Assistant Knowledge Source Order

For enterprise, customer, project, organization, partner, or account questions, especially questions containing 最新、最近、动态、情况、变化、进展:

1. First call `kb_answer` with the user's original question.
2. If the knowledge base has no useful result, search internal OpenClaw workspace, memory, and session context.
3. Only after knowledge base and internal workspace do not answer, use web search if available.

Do not answer "实时网络检索不可用" before trying `kb_answer`.
EOF
fi
chown root:root "$WORKSPACE_TOOLS"

echo "OpenClaw plugin synced to $INSTALL_DIR"
