# Enterprise AI Knowledge Assistant

可复制的行业知识助手 MVP：OpenClaw 作为入口和工具编排，自建 FastAPI 后端作为事实、权限、确认和审计系统。当前默认行业模板是客服知识助手，保留企业知识库模式，并为后续餐馆、医美等行业配置包预留入口。

## 快速开始：OpenClaw 知识库插件

目标用户只需要安装 OpenClaw、克隆本仓库、启动后端并安装插件，就可以通过 OpenClaw 使用客服知识库工具。

### 1. 克隆仓库

```bash
git clone git@github.com:youshengyishengzaifendou/enterprise-ai-knowledge-base.git
cd enterprise-ai-knowledge-base
```

### 2. 启动后端

推荐先运行本地初始化脚本：

```bash
./scripts/setup-local.sh
```

也可以手动执行：

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
cp ../.env.example .env
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`.env` 只用于本地运行，已被 `.gitignore` 排除。发布或共享代码前不要提交真实的 `AGENT_TOOL_API_KEY`。

另开一个终端初始化演示数据：

```bash
curl -X POST http://127.0.0.1:8000/api/dev/seed-demo
```

### 3. 安装 OpenClaw 插件

```bash
cd agent/openclaw-plugin
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

- 行业配置层：
  - 默认 `support` 客服模式
  - 保留 `enterprise` 企业知识库模式
  - 前端标题、说明、数据表名称、知识分类和工具语义从配置读取
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
  - `support_dashboard`
  - `support_unanswered_questions`
  - `support_update_unanswered_status`
  - `support_import_faq`
- SQLAlchemy 数据模型：
  - 用户、渠道绑定、客户、项目、进展、任务、风险、确认动作、审计日志
  - 知识库文档、知识库切块
  - 客服无答案问题
- 写入确认机制：
  - 未确认的项目进展和任务创建会返回 `need_confirmation: true`
  - `confirm_action` 执行待确认动作
- OpenClaw 本地插件薄封装
- OpenClaw 知识库工具闭环
- 客服知识库看板：
  - 客户/用户/账号
  - 问题/工单
  - 知识文章
  - 答案片段
  - 查询/写入/回复建议记录
  - 知识文章数、答案片段数、今日查询数、查询次数、命中率、无答案问题
  - 待审核知识、解析失败文件、最新上传文件、知识冲突报告
  - FAQ CSV、Markdown、TXT、PDF、Word、Excel、图片 OCR 导入
  - 无答案问题标记为已补充或忽略
  - 客户详情关联知识文章、答案片段、历史相似问题和最近记录
  - 原文档路径复制、按权限下载原件
- 知识运营治理：
  - 新上传文件默认待审核，管理员发布后才进入可检索知识库
  - 知识发布时生成版本记录，回答和搜索结果返回使用的知识版本
  - 相似/冲突知识进入冲突报告
  - PDF、Word、Excel、图片解析失败时保留原件和失败记录
  - 原文档表记录上传人、渠道账号、解析状态和关联知识文章
- 电商售后演示包：
  - 退款、退货、物流、发票、投诉升级等常见客服知识
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

## 客服知识库看板

客服知识库看板是客服知识运营页面，用来查看后端数据库已经记录了哪些客户/用户/账号、问题/工单、处理进展、知识文章、答案片段、无答案问题和查询/写入/回复建议记录。

先启动后端：

```bash
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

再启动前端：

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

浏览器打开 Vite 输出的本地地址，通常是：

```text
http://127.0.0.1:5173/
```

前端默认连接 `http://127.0.0.1:8000`，并兼容回退到 `http://127.0.0.1:8001`。如果后端配置了 `AGENT_TOOL_API_KEY`，在页面顶部填写同一个 API Key。

本地开发时也可以让 Vite 预填页面 API Key：

```bash
cd frontend
VITE_AGENT_TOOL_API_KEY="$(awk -F= '/^AGENT_TOOL_API_KEY=/ {print $2}' ../backend/.env)" npm run dev -- --host 127.0.0.1
```

不要在公开部署中设置 `VITE_AGENT_TOOL_API_KEY`，因为 Vite 变量会进入浏览器端代码。

页面顶部可以切换行业模式：

```text
客服：support，默认模式，显示客户/用户/账号、问题/工单、知识文章、答案片段。
企业知识库：enterprise，保留原客户、项目、知识文档、知识切片文案。
```

在客户列表里双击某个客户，或点击“查看相关信息”，可以查看该客户关联的知识文章、答案片段、历史相似问题和最近查询/写入记录。点击关联记录可以跳转到对应表里的原始记录。

客服模式下页面顶部会显示知识运营区：

```text
知识文章、答案片段、今日查询数、查询次数、命中率、无答案问题
待审核知识、解析失败文件、最新上传文件、知识冲突报告
待补充知识
热门问题
FAQ CSV/Markdown/TXT/PDF/Word/Excel/图片 OCR 导入
```

FAQ 导入示例：

```csv
问题,答案
怎么退款,订单未发货可以直接退款
物流丢件怎么办,先联系快递核实并补发
```

如果 `kb_answer` 没有命中知识库，问题会自动进入“无答案问题”，方便客服主管后续补充知识。
补充知识后，可以在页面把对应无答案问题标记为“已补充”；无效问题可以标记为“忽略”。

文件上传会先保存原件并写入“原文档”表。解析成功的知识默认是“待审核/草稿”，管理员点击“发布”后才会生成可检索切片和知识版本；解析失败的 PDF、Word、Excel 或图片仍会保留原件路径，页面可查看失败原因并下载原件。

知识详情和原文档详情里可以一键复制原件路径或下载原件。下载接口会按当前账号的原文档权限过滤：管理员、全库账号、上传人或被授权用户可以下载。

## OpenClaw 插件

本地 smoke 可以用 link 安装，企业环境建议安装 root-owned 副本，并显式配置 `plugins.allow`。

```bash
cd agent/openclaw-plugin
npm install
npm run build
openclaw plugins install --link "$(pwd)"
openclaw plugins enable enterprise-ai-assistant
openclaw plugins doctor
```

如果 OpenClaw 安装在 root 用户下，可以用仓库脚本同步 root-owned 插件副本：

```bash
sudo bash scripts/sync-openclaw-plugin-root.sh
sudo -H openclaw plugins doctor
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

如果没有安装 gateway service，可以临时以前台方式启动：

```bash
ENTERPRISE_AI_AGENT_TOOL_API_KEY="<agent-tool-api-key>" openclaw gateway
```

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
答：商品主数据模板在知识纪要约定的下周三前提交，并返回《恒润项目知识纪要》作为来源。
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
短问句回答能基于《恒润项目知识纪要》生成。
```

如果短问句没有触发 `kb_answer`，重新构建并同步插件目录后重启 gateway：

```bash
cd agent/openclaw-plugin
npm run build
sudo mkdir -p /root/.openclaw/extensions/enterprise-ai-assistant
sudo cp -a openclaw.plugin.json package.json package-lock.json dist /root/.openclaw/extensions/enterprise-ai-assistant/
sudo chown -R root:root /root/.openclaw/extensions/enterprise-ai-assistant
openclaw gateway restart
```

## Docker Compose

一键启动：

```bash
./scripts/docker-up.sh
```

脚本会自动生成 `deploy/.env`，然后构建并启动整套服务。

手动启动：

```bash
AGENT_TOOL_API_KEY="$(openssl rand -hex 32)" docker compose -f deploy/docker-compose.yml up --build
```

当前 Compose 会启动 PostgreSQL、Redis、后端和前端：

- 后端：`http://127.0.0.1:8000`
- 前端：`http://127.0.0.1:8080`
- 后端启动时会自动执行 Alembic 迁移。
- 上传原文档会保存到 Docker volume `deploy_backend_uploads`。

如果 Docker Hub 拉取基础镜像超时，先配置可用的 registry mirror 或在网络恢复后重试同一条命令。

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
frontend TypeScript/Vite build
frontend npm audit --audit-level=moderate
```
