# Enterprise AI Assistant

第一阶段实现企业级 AI 智能助手的可运行 MVP 垂直切片：OpenClaw 作为入口和工具编排，自建 FastAPI 后端作为企业事实、权限、确认和审计系统。

## 快速开始：OpenClaw 知识库插件

目标用户只需要安装 OpenClaw、克隆本仓库、启动后端并安装插件，就可以通过 OpenClaw 使用企业知识库工具。

### 1. 克隆仓库

```bash
git clone <your-github-repo-url>
cd <repo-name>
```

### 2. 启动后端

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
cp ../.env.example .env
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开一个终端初始化演示数据：

```bash
curl -X POST http://127.0.0.1:8000/api/dev/seed-demo
```

### 3. 安装 OpenClaw 插件

```bash
cd agent/openclaw-plugin
npm install
npm run build
openclaw plugins install --link "$(pwd)"
openclaw plugins enable enterprise-ai-assistant
openclaw plugins doctor
```

如果后端 `.env` 中配置了 `AGENT_TOOL_API_KEY`，OpenClaw 插件也要配置同一个 key：

```bash
openclaw config set plugins.entries.enterprise-ai-assistant.config.backendUrl http://127.0.0.1:8000
openclaw config set plugins.entries.enterprise-ai-assistant.config.apiKey --ref-provider default --ref-source env --ref-id ENTERPRISE_AI_AGENT_TOOL_API_KEY
openclaw gateway restart
```

OpenClaw gateway 运行环境需要能读取 `ENTERPRISE_AI_AGENT_TOOL_API_KEY`。本地快速体验也可以先把 `AGENT_TOOL_API_KEY` 留空，但生产或共享环境必须启用 API key。

### 4. 验证知识库工具

```bash
openclaw agent --session-id enterprise-kb-smoke --message '请使用 kb_answer 工具查询项目 project-demo 的知识库，问题是：商品主数据模板什么时候提交？回答时带来源。' --json
```

如果返回结果使用了 `kb_answer` 工具，并能基于知识库内容回答，说明插件和后端已连通。

## 已实现范围

- Agent Tool API:
  - `customer_search`
  - `project_search`
  - `project_extract_update`
  - `project_add_update`
  - `task_create`
  - `project_get_brief`
  - `confirm_action`
  - `kb_ingest_document`
  - `kb_search`
  - `kb_answer`
- SQLAlchemy 数据模型：
  - 用户、渠道绑定、客户、项目、进展、任务、风险、确认动作、审计日志
  - 知识库文档、知识库切块
- 写入确认机制：
  - 未确认的项目进展和任务创建会返回 `need_confirmation: true`
  - `confirm_action` 执行待确认动作
- OpenClaw 本地插件薄封装
- OpenClaw 知识库工具闭环
- 后端测试覆盖核心链路
- 生产硬化第一批：
  - Agent Tool API 和业务 API 的 Bearer API Key 鉴权
  - OpenClaw 插件通过插件配置传入后端地址和 API key
  - 项目级 RBAC 访问控制
  - 生产环境禁止启动时自动建表
  - 生产环境禁用 demo seed
  - Alembic 初始迁移
  - 统一验证脚本
- 业务 API：
  - `GET /api/customers`
  - `POST /api/customers`
  - `GET /api/projects`
  - `POST /api/projects`
  - `GET /api/projects/{project_id}`

## 后端本地运行

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e '.[test]'
.venv/bin/python -m pytest -q
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

创建本地演示用户、客户和项目：

```bash
curl -X POST http://127.0.0.1:8000/api/dev/seed-demo
```

## 数据库记录看板

数据库记录看板是只读前端页面，用来查看后端数据库已经记录了哪些客户、项目、项目进展、任务、风险、知识文档、确认动作和审计日志。

先启动后端：

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload
```

再启动前端：

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

浏览器打开 Vite 输出的本地地址，默认后端地址为 `http://127.0.0.1:8000`。如果后端配置了 `AGENT_TOOL_API_KEY`，在页面顶部填写同一个 API Key。

## OpenClaw 插件

本地 smoke 可以用 link 安装，企业环境建议安装 root-owned 副本，并显式配置 `plugins.allow`。

```bash
cd agent/openclaw-plugin
npm install
npm run build
openclaw plugins install /home/tzh/project/agent/openclaw-plugin
openclaw plugins enable enterprise-ai-assistant
openclaw plugins doctor
```

后端如果配置了 `AGENT_TOOL_API_KEY`，OpenClaw 插件也必须配置同一个 API key：

推荐用 SecretRef，避免把真实 key 写入 `openclaw.json`：

```bash
openclaw config set plugins.entries.enterprise-ai-assistant.config.backendUrl http://127.0.0.1:8000
openclaw config set plugins.entries.enterprise-ai-assistant.config.apiKey --ref-provider default --ref-source env --ref-id ENTERPRISE_AI_AGENT_TOOL_API_KEY
```

OpenClaw gateway 的运行环境需要能读取 `ENTERPRISE_AI_AGENT_TOOL_API_KEY`。只在隔离测试机上使用下面的明文配置方式：

```bash
openclaw config patch --stdin <<'JSON'
{
  "plugins": {
    "entries": {
      "enterprise-ai-assistant": {
        "enabled": true,
        "config": {
          "backendUrl": "http://127.0.0.1:8000",
          "apiKey": "<agent-tool-api-key>"
        }
      }
    },
    "allow": [
      "enterprise-ai-assistant"
    ]
  }
}
JSON

openclaw gateway restart
```

生产环境不要把真实密钥写进项目文档或 shell 历史；优先使用 OpenClaw SecretRef 或受控的 root-owned 配置文件。后端如果跨机器部署，`backendUrl` 应使用内网 HTTPS 地址。

本地插件默认会用：

```text
channel=openclaw
external_user_id=unknown
```

`/api/dev/seed-demo` 会创建对应的渠道绑定，方便先跑通闭环。真实渠道接入后，应由 OpenClaw 上下文传入真实 channel 和 external user id。

当前 demo 模式下，未绑定的 OpenClaw 用户会兜底使用 demo 用户查询知识库，便于先验证“直接问、直接答”的体验。正式企业上线前应关闭兜底并接入真实用户映射。

知识库工具示例：

```text
把下面这段内容写入恒润项目知识库：
一期先做商品主数据，供应商管理放到二期，导入模板下周三前提交。
```

```text
查询恒润项目知识库：商品主数据模板什么时候提交？
```

简洁问答示例：

```text
问：帮我查看一下商品主数据什么时候提交
答：商品主数据模板5月13日前提交。
```

企业环境验收命令：

```bash
curl http://127.0.0.1:8000/health
openclaw plugins doctor
openclaw plugins list | rg enterprise-ai-assistant
openclaw agent --session-id enterprise-kb-smoke-prod --message '请使用 kb_answer 工具查询项目 project-demo 的知识库，问题是：商品主数据模板什么时候提交？回答时带来源。' --json
openclaw agent --session-id enterprise-kb-short --message '帮我查看一下商品主数据什么时候提交' --json
```

通过标准：

```text
backend health 返回 ok
OpenClaw gateway 日志显示 enterprise-ai-assistant 已加载
agent 结果的 toolSummary.tools 包含 kb_answer
回答包含知识库来源，例如《恒润项目知识纪要》
短问句回答：商品主数据模板5月13日前提交。
```

如果短问句没有触发 `kb_answer`，通常是 OpenClaw 已安装插件里缺少随插件发布的 `skills` 目录。以 root 用户同步插件目录并重启 gateway：

```bash
cd /home/tzh/project/agent/openclaw-plugin
npm run build
cp -a openclaw.plugin.json package.json package-lock.json dist skills /root/.openclaw/extensions/enterprise-ai-assistant/
chown -R root:root /root/.openclaw/extensions/enterprise-ai-assistant
openclaw gateway restart
```

## Docker Compose

```bash
cd deploy
docker compose up --build
```

当前 Compose 使用 PostgreSQL 和 Redis。后端模型已准备好迁移工具接入；第一阶段测试使用 SQLite，以便快速验证业务行为。

当前 WSL 环境没有 `docker` 命令，因此本机尚未完成 Compose 运行验证。可以先用：

```bash
./scripts/check-docker.sh
```

确认 Docker 可用后再启动 Compose。

## 验证

```bash
./scripts/verify.sh
```

当前验证覆盖：

```text
backend pytest
Alembic migration upgrade
OpenClaw plugin TypeScript build
npm audit --audit-level=moderate
```
