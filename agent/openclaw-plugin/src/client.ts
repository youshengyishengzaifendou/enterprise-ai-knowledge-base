export type AgentToolRequest = {
  actor: {
    channel: string;
    external_user_id: string;
    internal_user_id?: string | null;
  };
  trace?: {
    conversation_id?: string | null;
    message_id?: string | null;
    source_url?: string | null;
  };
  input: Record<string, unknown>;
};

export type AgentToolResponse = {
  ok: boolean;
  data: Record<string, unknown> | null;
  citations: Array<Record<string, unknown>>;
  need_confirmation: boolean;
  confirmation: Record<string, unknown> | null;
  message: string;
  error_code?: string | null;
  details?: Record<string, unknown>;
};

export type AgentToolClientOptions = {
  backendUrl?: string;
  apiKey?: string;
};

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

function normalizeBackendUrl(value?: string): string {
  const normalized = value?.trim() || DEFAULT_BACKEND_URL;
  return normalized.replace(/\/+$/, "");
}

export async function callAgentTool(
  toolName: string,
  request: AgentToolRequest,
  options: AgentToolClientOptions = {},
): Promise<AgentToolResponse> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  const apiKey = options.apiKey?.trim();
  if (apiKey) {
    headers.authorization = `Bearer ${apiKey}`;
  }

  const response = await fetch(`${normalizeBackendUrl(options.backendUrl)}/api/agent-tools/${toolName}`, {
    method: "POST",
    headers,
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const body = (await response.text()).slice(0, 500);
    throw new Error(`Agent tool ${toolName} failed with HTTP ${response.status}: ${body}`);
  }

  return (await response.json()) as AgentToolResponse;
}
