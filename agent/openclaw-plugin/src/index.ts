import { callAgentTool, type AgentToolClientOptions, type AgentToolRequest } from "./client.js";

type ToolContext = {
  channel?: string;
  externalUserId?: string;
  internalUserId?: string | null;
  conversationId?: string | null;
  messageId?: string | null;
  sourceUrl?: string | null;
};

type OpenClawToolContext = {
  messageChannel?: string;
  requesterSenderId?: string;
  sessionId?: string;
  sessionKey?: string;
  getRuntimeConfig?: () => OpenClawConfig | undefined;
  runtimeConfig?: OpenClawConfig;
  config?: OpenClawConfig;
};

type OpenClawPluginEntry = {
  config?: Record<string, unknown>;
};

type OpenClawConfig = {
  plugins?: {
    entries?: Record<string, OpenClawPluginEntry | undefined>;
  };
};

function toAgentRequest(input: Record<string, unknown>, context: ToolContext = {}): AgentToolRequest {
  return {
    actor: {
      channel: context.channel ?? "openclaw",
      external_user_id: context.externalUserId ?? "unknown",
      internal_user_id: context.internalUserId ?? null,
    },
    trace: {
      conversation_id: context.conversationId ?? null,
      message_id: context.messageId ?? null,
      source_url: context.sourceUrl ?? null,
    },
    input,
  };
}

async function runTool(toolName: string, input: Record<string, unknown>, context: ToolContext | undefined, clientOptions: AgentToolClientOptions) {
  const result = await callAgentTool(toolName, toAgentRequest(input, context), clientOptions);
  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(result),
      },
    ],
  };
}

type RegisteredTool = {
  name: string;
  label?: string;
  description: string;
  parameters: Record<string, unknown>;
  execute: (toolCallId: string, params: Record<string, unknown>) => Promise<{ content: Array<{ type: string; text: string }> }>;
};

type OpenClawPluginApi = {
  config?: OpenClawConfig;
  pluginConfig?: Record<string, unknown>;
  registerTool: (
    tool: RegisteredTool | ((context: OpenClawToolContext) => RegisteredTool),
    options?: { name?: string; names?: string[]; optional?: boolean },
  ) => void;
};

const PLUGIN_ID = "enterprise-ai-assistant";
const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

function readStringConfig(config: Record<string, unknown> | undefined, key: string): string | undefined {
  const value = config?.[key];
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function resolvePluginConfig(api: OpenClawPluginApi, context?: OpenClawToolContext): Record<string, unknown> | undefined {
  const runtimeConfig = context?.getRuntimeConfig?.() ?? context?.runtimeConfig ?? context?.config ?? api.config;
  return runtimeConfig?.plugins?.entries?.[PLUGIN_ID]?.config ?? api.pluginConfig;
}

function resolveClientOptions(api: OpenClawPluginApi, context?: OpenClawToolContext): AgentToolClientOptions {
  const pluginConfig = resolvePluginConfig(api, context);
  return {
    backendUrl: readStringConfig(pluginConfig, "backendUrl") ?? DEFAULT_BACKEND_URL,
    apiKey: readStringConfig(pluginConfig, "apiKey"),
  };
}

function resolveToolContext(context?: OpenClawToolContext): ToolContext {
  return {
    channel: context?.messageChannel ?? "openclaw",
    externalUserId: context?.requesterSenderId ?? "unknown",
    conversationId: context?.sessionId ?? context?.sessionKey ?? null,
  };
}

const genericInputSchema = {
  type: "object",
  additionalProperties: true,
  properties: {},
};

const schemas = {
  customer_search: {
    type: "object",
    additionalProperties: false,
    properties: { query: { type: "string", description: "Customer name or alias to search." } },
    required: ["query"],
  },
  project_search: {
    type: "object",
    additionalProperties: false,
    properties: {
      query: { type: "string", description: "Project name, alias, or customer keyword to search." },
      customer_id: { type: "string", description: "Optional customer id scope." },
    },
    required: ["query"],
  },
  project_get_brief: {
    type: "object",
    additionalProperties: false,
    properties: { project_id: { type: "string", description: "Project id, for example project-demo." } },
    required: ["project_id"],
  },
  kb_ingest_document: {
    type: "object",
    additionalProperties: false,
    properties: {
      title: { type: "string", description: "Knowledge document title." },
      content_text: { type: "string", description: "Full document body to ingest into the enterprise knowledge base." },
      project_id: { type: "string", description: "Optional project id scope. Use project-demo for seeded Hengrun test data." },
      customer_id: { type: "string", description: "Optional customer id scope." },
      summary: { type: "string", description: "Optional short document summary." },
      source_type: { type: "string", description: "Source type, for example manual, feishu, meeting, or import." },
      source_url: { type: "string", description: "Optional source URL." },
      confirmed: { type: "boolean", description: "Set true when the user explicitly asks to record, save, write, load, import, or ingest the provided content." },
    },
    required: ["title", "content_text"],
  },
  kb_search: {
    type: "object",
    additionalProperties: false,
    properties: {
      query: { type: "string", description: "Knowledge base search query. Use exact user words for business/project facts, deadlines, documents, and requirements." },
      project_id: { type: "string", description: "Optional project id scope. Use project-demo for the seeded Hengrun project." },
      customer_id: { type: "string", description: "Optional customer id scope." },
      limit: { type: "number", description: "Maximum number of chunks to return." },
    },
    required: ["query"],
  },
  kb_answer: {
    type: "object",
    additionalProperties: false,
    properties: {
      query: { type: "string", description: "Exact user question to answer from the enterprise knowledge base, for example: 帮我查看一下商品主数据什么时候提交." },
      project_id: { type: "string", description: "Optional project id scope. If the user did not specify one, omit this field so backend defaults can resolve scope. Use project-demo only when explicitly testing the seeded Hengrun project." },
      customer_id: { type: "string", description: "Optional customer id scope." },
      limit: { type: "number", description: "Maximum number of chunks to use." },
    },
    required: ["query"],
  },
} as const;

type ToolDefinition = {
  name: string;
  description: string;
  optional: boolean;
  parameters: Record<string, unknown>;
};

const toolDefinitions: ToolDefinition[] = [
  { name: "customer_search", description: "Search accessible customers by name or alias.", optional: false, parameters: schemas.customer_search },
  { name: "project_search", description: "Search accessible projects by name, alias, or customer.", optional: false, parameters: schemas.project_search },
  { name: "project_extract_update", description: "Extract a project update draft from natural language.", optional: false, parameters: genericInputSchema },
  { name: "project_add_update", description: "Add a confirmed project update.", optional: true, parameters: genericInputSchema },
  { name: "task_create", description: "Create a confirmed project task.", optional: true, parameters: genericInputSchema },
  { name: "project_get_brief", description: "Get project stage, recent updates, open tasks, risks, and citations.", optional: false, parameters: schemas.project_get_brief },
  { name: "confirm_action", description: "Confirm and execute a pending write action.", optional: true, parameters: genericInputSchema },
  {
    name: "kb_ingest_document",
    description:
      "Ingest or write a user-provided document into the enterprise knowledge base. Use when the user explicitly asks to record, remember, note, load, import, write, save, or ingest project/customer knowledge, including short requests like '记录上述内容'. For multiple documents, call once per document. Set confirmed=true when the user has already explicitly instructed the write. If Hengrun/恒润 project data has no project_id, use project-demo.",
    optional: false,
    parameters: schemas.kb_ingest_document,
  },
  {
    name: "record_enterprise_knowledge",
    description:
      "Record enterprise knowledge into the database. Use this for natural-language requests like '记录上述内容', '记一下', '保存这些资料', or when the user pastes project/customer documents and asks to record them. This is an alias of kb_ingest_document: for multiple documents, call once per document. If Hengrun/恒润 project data has no project_id, use project-demo. Do not write workspace files for this intent.",
    optional: false,
    parameters: schemas.kb_ingest_document,
  },
  { name: "kb_search", description: "Search enterprise knowledge base content for project facts, customer documents, requirements, plans, and deadlines.", optional: false, parameters: schemas.kb_search },
  {
    name: "kb_answer",
    description:
      "Use first for enterprise knowledge-base questions and short business fact questions, including latest/recent/current status questions such as 最新、最近、动态、情况、变化、进展, and deadlines such as '帮我查看一下商品主数据什么时候提交', '商品主数据什么时候提交', '模板几号提交', or '恒润项目知识库'. Answer from data.answer as one concise sentence; include citations only when the user asks for sources.",
    optional: false,
    parameters: schemas.kb_answer,
  },
];

export function register(api: OpenClawPluginApi) {
  for (const { name, description, optional, parameters } of toolDefinitions) {
    const backendToolName = name === "record_enterprise_knowledge" ? "kb_ingest_document" : name;
    api.registerTool(
      (context) => ({
        name,
        label: name,
        description,
        parameters,
        execute: async (_toolCallId, params) => runTool(backendToolName, params, resolveToolContext(context), resolveClientOptions(api, context)),
      }),
      { name, optional },
    );
  }
}
