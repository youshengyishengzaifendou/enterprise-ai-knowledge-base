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
const SUPPORT_TOOL_CONTEXT =
  "客服坐席内部知识助手：用于记录客服知识、查询标准答案、生成建议回复、查看历史相似问题；不直接自动回复终端客户。";

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
      content_text: { type: "string", description: "Full客服知识文章正文，后端会切分成答案片段。" },
      project_id: { type: "string", description: "Optional issue/ticket/session topic id scope." },
      customer_id: { type: "string", description: "Optional customer/user/account id scope." },
      summary: { type: "string", description: "Optional short support knowledge summary." },
      source_type: { type: "string", description: "Source type, for example manual, faq, ticket, chat, feishu, meeting, or import." },
      source_url: { type: "string", description: "Optional source URL." },
      source_file_path: { type: "string", description: "Optional local original file path, for example /root/.openclaw/media/inbound/file.docx." },
      source_file_name: { type: "string", description: "Optional original file name." },
      source_file_mime_type: { type: "string", description: "Optional original file MIME type." },
      source_file_size: { type: "number", description: "Optional original file size in bytes." },
      source_file_storage: { type: "string", description: "Optional source file storage kind: openclaw_media, uploaded_copy, or external_url." },
      confirmed: { type: "boolean", description: "Set true when the user explicitly asks to record, save, write, load, import, or ingest the provided content." },
    },
    required: ["title", "content_text"],
  },
  kb_search: {
    type: "object",
    additionalProperties: false,
    properties: {
      query: { type: "string", description: "Knowledge base search query. Use exact customer question words for policies, standard answers, troubleshooting steps, and similar issues." },
      project_id: { type: "string", description: "Optional issue/ticket/session topic id scope." },
      customer_id: { type: "string", description: "Optional customer/user/account id scope." },
      limit: { type: "number", description: "Maximum number of chunks to return." },
    },
    required: ["query"],
  },
  kb_answer: {
    type: "object",
    additionalProperties: false,
    properties: {
      query: { type: "string", description: "Exact customer-service question to answer from the knowledge base, for example: 客户登录失败怎么回复, 退款政策是什么, 有没有历史相似问题." },
      project_id: { type: "string", description: "Optional issue/ticket/session topic id scope. Omit when the user did not specify one." },
      customer_id: { type: "string", description: "Optional customer/user/account id scope." },
      limit: { type: "number", description: "Maximum number of chunks to use." },
    },
    required: ["query"],
  },
  kb_find_source_file: {
    type: "object",
    additionalProperties: false,
    properties: {
      query: { type: "string", description: "File name, knowledge title, or user question used to find the original source file." },
      project_id: { type: "string", description: "Optional issue/ticket/session topic id scope." },
      customer_id: { type: "string", description: "Optional customer/user/account id scope." },
      limit: { type: "number", description: "Maximum number of source files to return." },
    },
    required: ["query"],
  },
  support_unanswered_questions: {
    type: "object",
    additionalProperties: false,
    properties: {
      limit: { type: "number", description: "Maximum number of unanswered support questions to return." },
      status: { type: "string", description: "Optional status filter: pending, resolved, or ignored." },
    },
  },
  support_update_unanswered_status: {
    type: "object",
    additionalProperties: false,
    properties: {
      unanswered_id: { type: "string", description: "Unanswered question id." },
      status: { type: "string", description: "New status: pending, resolved, or ignored." },
    },
    required: ["unanswered_id", "status"],
  },
  support_import_faq: {
    type: "object",
    additionalProperties: false,
    properties: {
      text: { type: "string", description: "CSV or text FAQ content. CSV format should include 问题,答案 columns." },
      source_type: { type: "string", description: "Source type, for example faq_csv, markdown, txt, or support_import." },
      customer_id: { type: "string", description: "Optional customer/user/account id scope." },
      project_id: { type: "string", description: "Optional issue/ticket/session topic id scope." },
    },
    required: ["text"],
  },
} as const;

type ToolDefinition = {
  name: string;
  description: string;
  optional: boolean;
  parameters: Record<string, unknown>;
};

const toolDefinitions: ToolDefinition[] = [
  { name: "customer_search", description: `${SUPPORT_TOOL_CONTEXT} Search accessible customers/users/accounts by name or alias.`, optional: false, parameters: schemas.customer_search },
  { name: "project_search", description: `${SUPPORT_TOOL_CONTEXT} Search accessible issues, tickets, or session topics by name, alias, or customer.`, optional: false, parameters: schemas.project_search },
  { name: "project_extract_update", description: `${SUPPORT_TOOL_CONTEXT} Extract a draft handling note from natural language.`, optional: false, parameters: genericInputSchema },
  { name: "project_add_update", description: `${SUPPORT_TOOL_CONTEXT} Add a confirmed issue/ticket handling note.`, optional: true, parameters: genericInputSchema },
  { name: "task_create", description: `${SUPPORT_TOOL_CONTEXT} Create a confirmed follow-up task for a support issue.`, optional: true, parameters: genericInputSchema },
  { name: "project_get_brief", description: `${SUPPORT_TOOL_CONTEXT} Get issue status, recent handling notes, open tasks, escalation risks, and citations.`, optional: false, parameters: schemas.project_get_brief },
  { name: "confirm_action", description: "Confirm and execute a pending write action.", optional: true, parameters: genericInputSchema },
  {
    name: "kb_ingest_document",
    description:
      `${SUPPORT_TOOL_CONTEXT} Ingest or write a user-provided support knowledge article into the knowledge base. Use when the user explicitly asks to record, remember, note, load, import, write, save, or ingest customer-service knowledge, FAQ, policy, ticket handling steps, or standard reply content. For multiple documents, call once per document. Set confirmed=true when the user has already explicitly instructed the write.`,
    optional: false,
    parameters: schemas.kb_ingest_document,
  },
  {
    name: "record_enterprise_knowledge",
    description:
      `${SUPPORT_TOOL_CONTEXT} Record customer-service knowledge into the database. Use this for natural-language requests like '记录上述内容', '记一下', '保存这些资料', or when the user pastes FAQ, policy, customer/account notes, or issue handling content and asks to record it. This is an alias of kb_ingest_document: for multiple documents, call once per document. Do not write workspace files for this intent.`,
    optional: false,
    parameters: schemas.kb_ingest_document,
  },
  { name: "kb_search", description: `${SUPPORT_TOOL_CONTEXT} Search support knowledge articles and answer fragments for standard answers, policies, troubleshooting steps, and similar issues.`, optional: false, parameters: schemas.kb_search },
  {
    name: "kb_answer",
    description:
      `${SUPPORT_TOOL_CONTEXT} Use first for客服问题、标准答案、建议回复、历史相似问题查询 and short knowledge-base questions, including latest/recent/current handling status questions such as 最新、最近、动态、情况、变化、进展. Answer from data.answer as a concise support-agent draft; include citations only when the user asks for sources.`,
    optional: false,
    parameters: schemas.kb_answer,
  },
  {
    name: "kb_find_source_file",
    description:
      `${SUPPORT_TOOL_CONTEXT} Find the original source file linked to a knowledge article when the user asks for 原文档、原件、附件、文件、源文件, or wants a file sent back. Return source_file_path/source_file_name so the channel can send or expose the original file.`,
    optional: false,
    parameters: schemas.kb_find_source_file,
  },
  {
    name: "support_dashboard",
    description: `${SUPPORT_TOOL_CONTEXT} Show support knowledge operations metrics: knowledge count, answer fragments, hit rate, popular questions, unanswered questions, and recent writes.`,
    optional: false,
    parameters: genericInputSchema,
  },
  {
    name: "support_unanswered_questions",
    description: `${SUPPORT_TOOL_CONTEXT} List unanswered customer questions captured from missed knowledge-base answers so the support manager can fill knowledge gaps.`,
    optional: false,
    parameters: schemas.support_unanswered_questions,
  },
  {
    name: "support_update_unanswered_status",
    description: `${SUPPORT_TOOL_CONTEXT} Mark an unanswered support question as pending, resolved, or ignored after the knowledge gap has been handled.`,
    optional: false,
    parameters: schemas.support_update_unanswered_status,
  },
  {
    name: "support_import_faq",
    description: `${SUPPORT_TOOL_CONTEXT} Import customer-service FAQ content into the support knowledge base from CSV/text, creating searchable knowledge articles and answer fragments.`,
    optional: false,
    parameters: schemas.support_import_faq,
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
