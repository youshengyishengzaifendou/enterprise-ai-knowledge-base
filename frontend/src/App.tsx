import { AlertCircle, BarChart3, Copy, Database, FileText, KeyRound, Link2, RefreshCw, Search, Server, Table2, Upload } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

type OverviewTable = {
  id: string;
  label: string;
  count: number;
  columns: string[];
  rows: Record<string, JsonValue>[];
};

type OverviewResponse = {
  ok: boolean;
  industry?: IndustryConfig;
  title?: string;
  description?: string;
  labels?: Record<string, string>;
  tables: OverviewTable[];
};

type IndustryConfig = {
  key: string;
  title: string;
  description: string;
  labels: Record<string, string>;
  knowledge_tags: string[];
  tool_description: string;
  example_prompts: string[];
};

type CustomerRelatedInfo = {
  ok: boolean;
  customer_name: string;
  industry?: IndustryConfig;
  labels?: Record<string, string>;
  documents: Record<string, JsonValue>[];
  chunks: Record<string, JsonValue>[];
  similar_cases: Record<string, JsonValue>[];
  audit_logs: Record<string, JsonValue>[];
};

type SupportDashboard = {
  ok: boolean;
  metrics: Record<string, number>;
  popular_questions: Record<string, JsonValue>[];
  recent_unanswered: Record<string, JsonValue>[];
  recent_documents: Record<string, JsonValue>[];
};

const defaultBackendUrl = "http://127.0.0.1:8000";
const localBackendFallbacks = ["http://127.0.0.1:8001", "http://127.0.0.1:8000"];
const defaultApiKey = import.meta.env.VITE_AGENT_TOOL_API_KEY ?? "";
const defaultIndustry = "support";

function App() {
  const [backendUrl, setBackendUrl] = useState(defaultBackendUrl);
  const [apiKey, setApiKey] = useState(defaultApiKey);
  const [industry, setIndustry] = useState(defaultIndustry);
  const [query, setQuery] = useState("");
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [activeTableId, setActiveTableId] = useState("");
  const [selectedRowIndex, setSelectedRowIndex] = useState(0);
  const [relatedInfo, setRelatedInfo] = useState<CustomerRelatedInfo | null>(null);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [relatedError, setRelatedError] = useState("");
  const [supportDashboard, setSupportDashboard] = useState<SupportDashboard | null>(null);
  const [faqText, setFaqText] = useState("");
  const [faqSourceType, setFaqSourceType] = useState("faq_csv");
  const [importingFaq, setImportingFaq] = useState(false);
  const [importMessage, setImportMessage] = useState("");
  const [loadingFaqFile, setLoadingFaqFile] = useState(false);
  const [permissionUserId, setPermissionUserId] = useState("");
  const [sourceFilePermissionUserId, setSourceFilePermissionUserId] = useState("");
  const [batchPermissionUserId, setBatchPermissionUserId] = useState("");
  const [groupName, setGroupName] = useState("");
  const [groupDocumentId, setGroupDocumentId] = useState("");
  const [projectPermissionUserId, setProjectPermissionUserId] = useState("");
  const [channelAccountIds, setChannelAccountIds] = useState("");
  const [channelAccountAliasUserId, setChannelAccountAliasUserId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const activeTable = useMemo(() => {
    return data?.tables.find((table) => table.id === activeTableId) ?? data?.tables[0] ?? null;
  }, [activeTableId, data]);

  const filteredRows = useMemo(() => {
    if (!activeTable) return [];
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return activeTable.rows;
    return activeTable.rows.filter((row) => JSON.stringify(row).toLowerCase().includes(normalizedQuery));
  }, [activeTable, query]);

  const selectedRow = filteredRows[selectedRowIndex] ?? filteredRows[0] ?? null;

  async function loadOverview() {
    setLoading(true);
    setError("");
    try {
      const headers: HeadersInit = {};
      if (apiKey.trim()) {
        headers.Authorization = `Bearer ${apiKey.trim()}`;
      }
      const response = await fetchOverviewWithFallback(backendUrl, headers, industry);
      const body = (await response.json()) as OverviewResponse;
      setData(body);
      if (industry === "support") {
        const dashboardResponse = await fetchSupportDashboardWithFallback(backendUrl, headers);
        setSupportDashboard((await dashboardResponse.json()) as SupportDashboard);
      } else {
        setSupportDashboard(null);
      }
      setActiveTableId((current) => current || body.tables[0]?.id || "");
      setSelectedRowIndex(0);
      setRelatedInfo(null);
      setRelatedError("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadOverview();
  }, []);

  async function importFaq() {
    const text = faqText.trim();
    if (!text) return;
    setImportingFaq(true);
    setImportMessage("");
    setError("");
    try {
      const headers: HeadersInit = { "Content-Type": "application/json" };
      if (apiKey.trim()) {
        headers.Authorization = `Bearer ${apiKey.trim()}`;
      }
      const response = await fetchImportFaqWithFallback(backendUrl, headers, text, faqSourceType);
      const body = (await response.json()) as { imported_count?: number };
      setImportMessage(`已导入 ${body.imported_count ?? 0} 条 FAQ`);
      setFaqText("");
      await loadOverview();
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : "导入失败");
    } finally {
      setImportingFaq(false);
    }
  }

  async function loadFaqFile(file: File | null) {
    if (!file) return;
    setLoadingFaqFile(true);
    setImportMessage("");
    setError("");
    try {
      const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
      if (!["csv", "txt", "md", "markdown", "pdf", "docx", "xlsx", "png", "jpg", "jpeg", "webp", "bmp"].includes(extension)) {
        throw new Error("当前支持 CSV、TXT、Markdown、PDF、Word(docx)、Excel(xlsx)、图片(png/jpg/webp/bmp)。");
      }
      if (["pdf", "docx", "xlsx", "png", "jpg", "jpeg", "webp", "bmp"].includes(extension)) {
        await importKnowledgeFile(file, extension);
        return;
      }
      const text = await file.text();
      setFaqText(text);
      if (extension === "csv") {
        setFaqSourceType("faq_csv");
      } else if (extension === "md" || extension === "markdown") {
        setFaqSourceType("markdown");
      } else {
        setFaqSourceType("txt");
      }
      setImportMessage(`已加载 ${file.name}，确认内容后点击导入 FAQ`);
    } catch (fileError) {
      setError(fileError instanceof Error ? fileError.message : "加载 FAQ 文档失败");
    } finally {
      setLoadingFaqFile(false);
    }
  }

  async function importKnowledgeFile(file: File, extension: string) {
    const headers: HeadersInit = {};
    if (apiKey.trim()) {
      headers.Authorization = `Bearer ${apiKey.trim()}`;
    }
    const formData = new FormData();
    formData.append("file", file);
    formData.append("source_type", extension);
    formData.append("user_id", "user-demo");
    const response = await fetchImportFileWithFallback(backendUrl, headers, formData);
    const body = (await response.json()) as { imported_count?: number; documents?: Array<{ title?: string }> };
    const title = body.documents?.[0]?.title;
    setImportMessage(`已导入 ${body.imported_count ?? 0} 个文档${title ? `：${title}` : ""}`);
    setFaqText("");
    await loadOverview();
  }

  async function updateUnansweredStatus(unansweredId: JsonValue, status: "resolved" | "ignored") {
    if (typeof unansweredId !== "string") return;
    setError("");
    try {
      const headers: HeadersInit = { "Content-Type": "application/json" };
      if (apiKey.trim()) {
        headers.Authorization = `Bearer ${apiKey.trim()}`;
      }
      await fetchUpdateUnansweredStatusWithFallback(backendUrl, headers, unansweredId, status);
      await loadOverview();
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "更新无答案问题失败");
    }
  }

  async function rebuildIndex(documentId: JsonValue) {
    if (typeof documentId !== "string") return;
    setError("");
    try {
      const headers: HeadersInit = {};
      if (apiKey.trim()) {
        headers.Authorization = `Bearer ${apiKey.trim()}`;
      }
      await fetchRebuildIndexWithFallback(backendUrl, headers, documentId);
      await loadOverview();
    } catch (rebuildError) {
      setError(rebuildError instanceof Error ? rebuildError.message : "重建索引失败");
    }
  }

  async function updateUserKnowledgePolicy(userId: JsonValue, policy: "all" | "own") {
    if (typeof userId !== "string") return;
    setError("");
    try {
      const headers: HeadersInit = { "Content-Type": "application/json" };
      if (apiKey.trim()) {
        headers.Authorization = `Bearer ${apiKey.trim()}`;
      }
      await fetchUpdateUserKnowledgePolicyWithFallback(backendUrl, headers, userId, policy);
      await loadOverview();
    } catch (policyError) {
      setError(policyError instanceof Error ? policyError.message : "更新用户知识权限失败");
    }
  }

  async function grantKnowledgePermission(documentId: JsonValue) {
    if (typeof documentId !== "string") return;
    const userId = permissionUserId.trim();
    if (!userId) return;
    setError("");
    try {
      const headers: HeadersInit = { "Content-Type": "application/json" };
      if (apiKey.trim()) {
        headers.Authorization = `Bearer ${apiKey.trim()}`;
      }
      await fetchGrantKnowledgePermissionWithFallback(backendUrl, headers, documentId, userId);
      setPermissionUserId("");
      await loadOverview();
    } catch (permissionError) {
      setError(permissionError instanceof Error ? permissionError.message : "授权知识文档失败");
    }
  }

  async function grantSourceFilePermission(sourceFileId: JsonValue) {
    if (typeof sourceFileId !== "string") return;
    const userId = sourceFilePermissionUserId.trim();
    if (!userId) return;
    setError("");
    try {
      await fetchPostWithFallback(backendUrl, jsonHeaders(apiKey), `/api/database/source-files/${encodeURIComponent(sourceFileId)}/permissions`, {
        user_id: userId,
      });
      setSourceFilePermissionUserId("");
      await loadOverview();
    } catch (permissionError) {
      setError(permissionError instanceof Error ? permissionError.message : "授权原文档失败");
    }
  }

  async function batchGrantVisibleDocuments() {
    const userId = batchPermissionUserId.trim();
    const documentIds = filteredRows.map((row) => row.id).filter((id): id is string => typeof id === "string");
    if (!userId || activeTable?.id !== "knowledge_documents" || documentIds.length === 0) return;
    setError("");
    try {
      await fetchPostWithFallback(backendUrl, jsonHeaders(apiKey), "/api/database/knowledge/batch-permissions", {
        user_id: userId,
        document_ids: documentIds,
      });
      setBatchPermissionUserId("");
      await loadOverview();
    } catch (permissionError) {
      setError(permissionError instanceof Error ? permissionError.message : "批量授权失败");
    }
  }

  async function createKnowledgeGroup() {
    const name = groupName.trim();
    if (!name) return;
    setError("");
    try {
      await fetchPostWithFallback(backendUrl, jsonHeaders(apiKey), "/api/database/knowledge/groups", { name, created_by: "user-demo" });
      setGroupName("");
      await loadOverview();
    } catch (groupError) {
      setError(groupError instanceof Error ? groupError.message : "创建分组失败");
    }
  }

  async function addDocumentToGroup(groupId: JsonValue) {
    if (typeof groupId !== "string") return;
    const documentId = groupDocumentId.trim();
    if (!documentId) return;
    setError("");
    try {
      await fetchPostWithFallback(backendUrl, jsonHeaders(apiKey), `/api/database/knowledge/groups/${encodeURIComponent(groupId)}/documents`, {
        document_id: documentId,
      });
      setGroupDocumentId("");
      await loadOverview();
    } catch (groupError) {
      setError(groupError instanceof Error ? groupError.message : "添加分组文档失败");
    }
  }

  async function grantProjectKnowledgePermission(projectId: JsonValue) {
    if (typeof projectId !== "string") return;
    const userId = projectPermissionUserId.trim();
    if (!userId) return;
    setError("");
    try {
      await fetchPostWithFallback(backendUrl, jsonHeaders(apiKey), `/api/database/projects/${encodeURIComponent(projectId)}/knowledge-permissions`, {
        user_id: userId,
      });
      setProjectPermissionUserId("");
      await loadOverview();
    } catch (permissionError) {
      setError(permissionError instanceof Error ? permissionError.message : "授权项目知识失败");
    }
  }

  async function disableSelectedUser(userId: JsonValue) {
    if (typeof userId !== "string") return;
    setError("");
    try {
      await fetchPostWithFallback(backendUrl, jsonHeaders(apiKey), `/api/database/users/${encodeURIComponent(userId)}/disable`, {
        actor_user_id: "user-demo",
      });
      await loadOverview();
    } catch (disableError) {
      setError(disableError instanceof Error ? disableError.message : "禁用用户失败");
    }
  }

  async function syncWeixinChannelAccounts() {
    const accountIds = channelAccountIds
      .split(/[\s,，]+/)
      .map((item) => item.trim())
      .filter(Boolean);
    if (accountIds.length === 0) return;
    const aliasUserId = channelAccountAliasUserId.trim();
    setError("");
    try {
      const payload: Record<string, JsonValue> = aliasUserId
        ? { channel: "openclaw-weixin", accounts: accountIds.map((accountId) => ({ account_id: accountId, user_id: aliasUserId })) }
        : { channel: "openclaw-weixin", account_ids: accountIds };
      const response = await fetchPostWithFallback(backendUrl, jsonHeaders(apiKey), "/api/database/users/channel-accounts/sync", payload);
      const body = (await response.json()) as { synced_count?: number };
      setImportMessage(`已同步 ${body.synced_count ?? 0} 个微信账号到知识库用户`);
      setChannelAccountIds("");
      setChannelAccountAliasUserId("");
      await loadOverview();
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : "同步微信账号失败");
    }
  }

  async function loadCustomerRelatedInfo(row: Record<string, JsonValue>) {
    const customerName = typeof row.name === "string" ? row.name : "";
    if (!customerName) return;
    setRelatedLoading(true);
    setRelatedError("");
    try {
      const headers: HeadersInit = {};
      if (apiKey.trim()) {
        headers.Authorization = `Bearer ${apiKey.trim()}`;
      }
      const response = await fetchRelatedInfoWithFallback(backendUrl, customerName, headers, industry);
      setRelatedInfo((await response.json()) as CustomerRelatedInfo);
    } catch (loadError) {
      setRelatedError(loadError instanceof Error ? loadError.message : "加载客户相关信息失败");
    } finally {
      setRelatedLoading(false);
    }
  }

  async function copyText(value: JsonValue) {
    if (typeof value !== "string" || !value.trim()) return;
    await navigator.clipboard.writeText(value);
  }

  function jumpToRecord(tableId: string, recordId: JsonValue) {
    if (typeof recordId !== "string") return;
    const table = data?.tables.find((candidate) => candidate.id === tableId);
    if (!table) return;
    const rowIndex = table.rows.findIndex((row) => row.id === recordId);
    setActiveTableId(tableId);
    setSelectedRowIndex(rowIndex >= 0 ? rowIndex : 0);
    setRelatedInfo(null);
    setRelatedError("");
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>{data?.title ?? "客服知识库看板"}</h1>
          <p>{data?.description ?? "查看客服坐席知识助手记录的客户、问题工单、知识文章、答案片段和查询记录。"}</p>
        </div>
        <button className="primary-button" onClick={loadOverview} disabled={loading} title="刷新数据">
          <RefreshCw size={18} />
          <span>{loading ? "加载中" : "刷新"}</span>
        </button>
      </header>

      <section className="connection-bar">
        <label>
          <Server size={16} />
          <span>后端地址</span>
          <input value={backendUrl} onChange={(event) => setBackendUrl(event.target.value)} />
        </label>
        <label>
          <Table2 size={16} />
          <span>行业模式</span>
          <select
            value={industry}
            onChange={(event) => {
              setIndustry(event.target.value);
              setData(null);
              setRelatedInfo(null);
            }}
          >
            <option value="support">客服</option>
            <option value="enterprise">企业知识库</option>
          </select>
        </label>
        <label>
          <KeyRound size={16} />
          <span>API Key</span>
          <input
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder="未配置时可留空"
            type="password"
          />
        </label>
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      {industry === "support" ? (
        <SupportOperationsPanel
          dashboard={supportDashboard}
          faqText={faqText}
          faqSourceType={faqSourceType}
          importMessage={importMessage}
          importingFaq={importingFaq}
          loadingFaqFile={loadingFaqFile}
          onFaqTextChange={setFaqText}
          onFaqSourceTypeChange={setFaqSourceType}
          onFaqFileChange={(file) => void loadFaqFile(file)}
          onImportFaq={() => void importFaq()}
          onUpdateUnansweredStatus={(id, status) => void updateUnansweredStatus(id, status)}
        />
      ) : null}

      <section className="summary-grid">
        <div className="summary-card utility-card">
          <span>新建文档分组</span>
          <input value={groupName} onChange={(event) => setGroupName(event.target.value)} placeholder="分组名称" />
          <button className="secondary-button compact-button" onClick={() => void createKnowledgeGroup()} disabled={!groupName.trim()}>
            创建
          </button>
        </div>
        {(data?.tables ?? []).map((table) => (
          <button
            key={table.id}
            className={table.id === activeTable?.id ? "summary-card active" : "summary-card"}
            onClick={() => {
              setActiveTableId(table.id);
              setSelectedRowIndex(0);
            }}
          >
            <span>{table.label}</span>
            <strong>{table.count}</strong>
          </button>
        ))}
      </section>

      <section className="viewer-layout">
        <aside className="table-list" aria-label="数据库表">
          <div className="panel-title">
            <Database size={18} />
            <span>数据表</span>
          </div>
          {(data?.tables ?? []).map((table) => (
            <button
              key={table.id}
              className={table.id === activeTable?.id ? "table-button active" : "table-button"}
              onClick={() => {
                setActiveTableId(table.id);
                setSelectedRowIndex(0);
              }}
            >
              <span>{table.label}</span>
              <small>{table.id}</small>
            </button>
          ))}
        </aside>

        <section className="records-panel">
          <div className="panel-header">
            <div>
              <div className="panel-title">
                <Table2 size={18} />
                <span>{activeTable?.label ?? "暂无数据"}</span>
              </div>
              <p>{activeTable ? `${activeTable.count} 条记录，当前显示最近 ${activeTable.rows.length} 条` : "后端没有返回表数据"}</p>
            </div>
            <label className="search-box">
              <Search size={16} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索当前表" />
            </label>
          </div>

          <div className="content-grid">
            <div className="row-list">
              {filteredRows.length === 0 ? (
                <div className="empty-state">没有匹配记录</div>
              ) : (
                filteredRows.map((row, index) => (
                  <button
                    key={`${activeTable?.id}-${index}`}
                    className={index === selectedRowIndex ? "record-card active" : "record-card"}
                    onClick={() => {
                      setSelectedRowIndex(index);
                      setRelatedInfo(null);
                      setRelatedError("");
                    }}
                    onDoubleClick={() => {
                      if (activeTable?.id === "customers") {
                        void loadCustomerRelatedInfo(row);
                      }
                    }}
                  >
                    <strong>{recordTitle(row)}</strong>
                    <span>{recordSubtitle(row)}</span>
                    {activeTable?.id === "customers" ? (
                      <span
                        className="inline-action"
                        role="button"
                        tabIndex={0}
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedRowIndex(index);
                          void loadCustomerRelatedInfo(row);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            event.stopPropagation();
                            setSelectedRowIndex(index);
                            void loadCustomerRelatedInfo(row);
                          }
                        }}
                      >
                        <FileText size={14} />
                        查看相关信息
                      </span>
                    ) : null}
                  </button>
                ))
              )}
            </div>

            <div className="detail-panel">
              {relatedInfo ? (
                <CustomerRelatedPanel relatedInfo={relatedInfo} onJumpToRecord={jumpToRecord} />
              ) : selectedRow ? (
                <>
                  <div className="detail-header">记录详情</div>
                  {activeTable?.id === "customers" ? (
                    <button className="secondary-button" onClick={() => void loadCustomerRelatedInfo(selectedRow)} disabled={relatedLoading}>
                      <FileText size={16} />
                      <span>{relatedLoading ? "加载中" : `查看${data?.labels?.customer ?? "客户"}相关信息`}</span>
                    </button>
                  ) : null}
                  {activeTable?.id === "knowledge_documents" && selectedRow.source_file_path ? (
                    <SourceFileActions row={selectedRow} onCopy={(value) => void copyText(value)} />
                  ) : null}
                  {activeTable?.id === "knowledge_documents" ? (
                    <button className="secondary-button" onClick={() => void rebuildIndex(selectedRow.id)}>
                      <RefreshCw size={16} />
                      <span>重建索引</span>
                    </button>
                  ) : null}
                  {activeTable?.id === "knowledge_documents" ? (
                    <PermissionGrantPanel
                      label="授权指定用户查看这篇知识"
                      userId={permissionUserId}
                      onUserIdChange={setPermissionUserId}
                      onGrant={() => void grantKnowledgePermission(selectedRow.id)}
                    />
                  ) : null}
                  {activeTable?.id === "knowledge_documents" ? (
                    <BulkGrantPanel userId={batchPermissionUserId} onUserIdChange={setBatchPermissionUserId} onGrant={() => void batchGrantVisibleDocuments()} />
                  ) : null}
                  {activeTable?.id === "knowledge_source_files" ? (
                    <PermissionGrantPanel
                      label="授权指定用户查看这个原文档"
                      userId={sourceFilePermissionUserId}
                      onUserIdChange={setSourceFilePermissionUserId}
                      onGrant={() => void grantSourceFilePermission(selectedRow.id)}
                    />
                  ) : null}
                  {activeTable?.id === "users" ? (
                    <ChannelAccountSyncPanel
                      accountIds={channelAccountIds}
                      aliasUserId={channelAccountAliasUserId}
                      onAccountIdsChange={setChannelAccountIds}
                      onAliasUserIdChange={setChannelAccountAliasUserId}
                      onSync={() => void syncWeixinChannelAccounts()}
                    />
                  ) : null}
                  {activeTable?.id === "users" ? (
                    <UserPolicyActions
                      row={selectedRow}
                      onUpdate={(policy) => void updateUserKnowledgePolicy(selectedRow.id, policy)}
                      onDisable={() => void disableSelectedUser(selectedRow.id)}
                    />
                  ) : null}
                  {activeTable?.id === "knowledge_document_groups" ? (
                    <GroupMembershipPanel documentId={groupDocumentId} onDocumentIdChange={setGroupDocumentId} onAdd={() => void addDocumentToGroup(selectedRow.id)} />
                  ) : null}
                  {activeTable?.id === "projects" ? (
                    <PermissionGrantPanel
                      label="授权指定用户查看这个项目下的知识"
                      userId={projectPermissionUserId}
                      onUserIdChange={setProjectPermissionUserId}
                      onGrant={() => void grantProjectKnowledgePermission(selectedRow.id)}
                    />
                  ) : null}
                  {relatedError ? <div className="error-banner compact">{relatedError}</div> : null}
                <dl>
                  {Object.entries(selectedRow).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key}</dt>
                      <dd>{formatValue(value)}</dd>
                    </div>
                  ))}
                </dl>
                </>
              ) : (
                <div className="empty-state">选择一条记录查看详情</div>
              )}
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}

function SourceFileActions({ row, onCopy }: { row: Record<string, JsonValue>; onCopy: (value: JsonValue) => void }) {
  return (
    <div className="source-file-panel">
      <div>
        <strong>{formatValue(row.source_file_name ?? "原始文件")}</strong>
        <span>{formatValue(row.source_file_storage ?? "未标注存储")}</span>
      </div>
      <button className="secondary-button compact-button" onClick={() => onCopy(row.source_file_path)} title="复制原件路径">
        <Copy size={16} />
        <span>复制路径</span>
      </button>
    </div>
  );
}

function ChannelAccountSyncPanel({
  accountIds,
  aliasUserId,
  onAccountIdsChange,
  onAliasUserIdChange,
  onSync,
}: {
  accountIds: string;
  aliasUserId: string;
  onAccountIdsChange: (value: string) => void;
  onAliasUserIdChange: (value: string) => void;
  onSync: () => void;
}) {
  return (
    <div className="permission-panel">
      <span>同步 OpenClaw 微信账号到知识库用户</span>
      <div className="permission-form">
        <input value={accountIds} onChange={(event) => onAccountIdsChange(event.target.value)} placeholder="实际账号 ID，例如 3f81836398cd-im-bot" />
        <input value={aliasUserId} onChange={(event) => onAliasUserIdChange(event.target.value)} placeholder="业务用户 ID，例如 wx-wangsuzhen" />
        <button className="secondary-button compact-button" onClick={onSync} disabled={!accountIds.trim()}>
          同步账号
        </button>
      </div>
    </div>
  );
}

function UserPolicyActions({
  row,
  onUpdate,
  onDisable,
}: {
  row: Record<string, JsonValue>;
  onUpdate: (policy: "all" | "own") => void;
  onDisable: () => void;
}) {
  const currentPolicy = row.knowledge_access_policy === "all" ? "all" : "own";
  return (
    <div className="permission-panel">
      <span>知识权限：{currentPolicy === "all" ? "全库可见" : "仅自己文档"}</span>
      <div className="permission-actions">
        <button className="secondary-button compact-button" onClick={() => onUpdate("all")}>
          全库可见
        </button>
        <button className="secondary-button compact-button" onClick={() => onUpdate("own")}>
          仅自己文档
        </button>
        <button className="secondary-button compact-button danger-button" onClick={onDisable} disabled={row.status === "disabled"}>
          禁用账号
        </button>
      </div>
    </div>
  );
}

function PermissionGrantPanel({
  label,
  userId,
  onUserIdChange,
  onGrant,
}: {
  label: string;
  userId: string;
  onUserIdChange: (value: string) => void;
  onGrant: () => void;
}) {
  return (
    <div className="permission-panel">
      <span>{label}</span>
      <div className="permission-form">
        <input value={userId} onChange={(event) => onUserIdChange(event.target.value)} placeholder="输入用户 ID" />
        <button className="secondary-button compact-button" onClick={onGrant} disabled={!userId.trim()}>
          授权
        </button>
      </div>
    </div>
  );
}

function BulkGrantPanel({ userId, onUserIdChange, onGrant }: { userId: string; onUserIdChange: (value: string) => void; onGrant: () => void }) {
  return (
    <div className="permission-panel">
      <span>批量授权当前筛选出的知识文档</span>
      <div className="permission-form">
        <input value={userId} onChange={(event) => onUserIdChange(event.target.value)} placeholder="输入用户 ID" />
        <button className="secondary-button compact-button" onClick={onGrant} disabled={!userId.trim()}>
          批量授权
        </button>
      </div>
    </div>
  );
}

function GroupMembershipPanel({
  documentId,
  onDocumentIdChange,
  onAdd,
}: {
  documentId: string;
  onDocumentIdChange: (value: string) => void;
  onAdd: () => void;
}) {
  return (
    <div className="permission-panel">
      <span>把知识文档加入这个分组</span>
      <div className="permission-form">
        <input value={documentId} onChange={(event) => onDocumentIdChange(event.target.value)} placeholder="输入知识文档 ID" />
        <button className="secondary-button compact-button" onClick={onAdd} disabled={!documentId.trim()}>
          加入分组
        </button>
      </div>
    </div>
  );
}

function SupportOperationsPanel({
  dashboard,
  faqText,
  faqSourceType,
  importMessage,
  importingFaq,
  loadingFaqFile,
  onFaqTextChange,
  onFaqSourceTypeChange,
  onFaqFileChange,
  onImportFaq,
  onUpdateUnansweredStatus,
}: {
  dashboard: SupportDashboard | null;
  faqText: string;
  faqSourceType: string;
  importMessage: string;
  importingFaq: boolean;
  loadingFaqFile: boolean;
  onFaqTextChange: (value: string) => void;
  onFaqSourceTypeChange: (value: string) => void;
  onFaqFileChange: (file: File | null) => void;
  onImportFaq: () => void;
  onUpdateUnansweredStatus: (id: JsonValue, status: "resolved" | "ignored") => void;
}) {
  const metrics = dashboard?.metrics ?? {};
  return (
    <section className="operations-panel">
      <div className="operations-header">
        <div className="panel-title">
          <BarChart3 size={18} />
          <span>客服知识运营</span>
        </div>
        <p>跟踪知识覆盖、无答案问题和客服 FAQ 导入情况。</p>
      </div>

      <div className="operations-grid">
        <MetricCard label="知识文章" value={metrics.knowledge_documents} />
        <MetricCard label="答案片段" value={metrics.answer_fragments} />
        <MetricCard label="已解析文档" value={metrics.parsed_documents} />
        <MetricCard label="已索引文档" value={metrics.indexed_documents} />
        <MetricCard label="查询次数" value={metrics.total_queries} />
        <MetricCard label="命中率" value={typeof metrics.hit_rate === "number" ? `${Math.round(metrics.hit_rate * 100)}%` : "0%"} />
        <MetricCard label="无答案问题" value={metrics.unanswered_questions} tone="warning" />
      </div>

      <div className="operations-content">
        <section className="ops-section">
          <h2>
            <AlertCircle size={16} />
            待补充知识
          </h2>
          <CompactList
            items={dashboard?.recent_unanswered ?? []}
            titleKey="question"
            emptyText="暂无无答案问题"
            actions={(item) => (
              <div className="compact-actions">
                <button type="button" onClick={() => onUpdateUnansweredStatus(item.id, "resolved")}>
                  已补充
                </button>
                <button type="button" onClick={() => onUpdateUnansweredStatus(item.id, "ignored")}>
                  忽略
                </button>
              </div>
            )}
          />
        </section>

        <section className="ops-section">
          <h2>
            <Search size={16} />
            热门问题
          </h2>
          <CompactList items={dashboard?.popular_questions ?? []} titleKey="question" subtitleKey="count" emptyText="暂无查询记录" />
        </section>

        <section className="ops-section">
          <h2>
            <FileText size={16} />
            最近知识
          </h2>
          <CompactList items={dashboard?.recent_documents ?? []} titleKey="title" subtitleKey="index_status" emptyText="暂无知识文档" />
        </section>

        <section className="ops-section import-section">
          <h2>
            <Upload size={16} />
            导入知识文档
          </h2>
          <div className="format-tags" aria-label="支持的导入格式">
            <span>CSV</span>
            <span>TXT</span>
            <span>Markdown</span>
            <span>PDF</span>
            <span>Word</span>
            <span>Excel</span>
            <span>Image OCR</span>
          </div>
          <label className="inline-select">
            <span>文本格式</span>
            <select value={faqSourceType} onChange={(event) => onFaqSourceTypeChange(event.target.value)}>
              <option value="faq_csv">CSV FAQ</option>
              <option value="markdown">Markdown</option>
              <option value="txt">TXT</option>
            </select>
          </label>
          <label className="file-input">
            <Upload size={16} />
            <span>{loadingFaqFile ? "加载中" : "选择知识文档"}</span>
            <input
              type="file"
              accept=".csv,.txt,.md,.markdown,.pdf,.docx,.xlsx,.png,.jpg,.jpeg,.webp,.bmp,text/csv,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,image/png,image/jpeg,image/webp,image/bmp"
              disabled={loadingFaqFile || importingFaq}
              onChange={(event) => {
                onFaqFileChange(event.target.files?.[0] ?? null);
                event.currentTarget.value = "";
              }}
            />
          </label>
          <textarea
            value={faqText}
            onChange={(event) => onFaqTextChange(event.target.value)}
            placeholder={"问题,答案\n怎么退款,订单未发货可以直接退款\n物流丢件怎么办,先联系快递核实并补发"}
          />
          <button className="secondary-button" onClick={onImportFaq} disabled={importingFaq || !faqText.trim()}>
            <Upload size={16} />
            <span>{importingFaq ? "导入中" : "导入文本内容"}</span>
          </button>
          {importMessage ? <p className="success-text">{importMessage}</p> : null}
        </section>
      </div>
    </section>
  );
}

function MetricCard({ label, value, tone }: { label: string; value: JsonValue | undefined; tone?: "warning" }) {
  return (
    <div className={tone === "warning" ? "metric-card warning" : "metric-card"}>
      <span>{label}</span>
      <strong>{formatMetricValue(value)}</strong>
    </div>
  );
}

function formatMetricValue(value: JsonValue | undefined): string {
  if (value === undefined || value === null) return "0";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function CompactList({
  items,
  titleKey,
  subtitleKey,
  emptyText,
  actions,
}: {
  items: Record<string, JsonValue>[];
  titleKey: string;
  subtitleKey?: string;
  emptyText: string;
  actions?: (item: Record<string, JsonValue>) => ReactNode;
}) {
  if (items.length === 0) {
    return <div className="empty-state small">{emptyText}</div>;
  }
  return (
    <div className="compact-list">
      {items.slice(0, 5).map((item, index) => (
        <div className="compact-row" key={`${String(item[titleKey])}-${index}`}>
          <strong>{formatValue(item[titleKey] ?? "未命名")}</strong>
          {subtitleKey ? <span>{formatValue(item[subtitleKey] ?? "")}</span> : <span>{formatValue(item.status ?? item.created_at ?? "")}</span>}
          {actions ? actions(item) : null}
        </div>
      ))}
    </div>
  );
}

function CustomerRelatedPanel({
  relatedInfo,
  onJumpToRecord,
}: {
  relatedInfo: CustomerRelatedInfo;
  onJumpToRecord: (tableId: string, recordId: JsonValue) => void;
}) {
  return (
    <div className="related-panel">
      <div className="detail-header">{relatedInfo.customer_name} 相关信息</div>
      <RelatedSection
        title={relatedInfo.labels?.documents ?? "知识文档"}
        items={relatedInfo.documents}
        emptyText={`没有匹配${relatedInfo.labels?.documents ?? "知识文档"}`}
        onJumpToRecord={onJumpToRecord}
      />
      <RelatedSection
        title={relatedInfo.labels?.chunks ?? "知识切片"}
        items={relatedInfo.chunks}
        emptyText={`没有匹配${relatedInfo.labels?.chunks ?? "知识切片"}`}
        onJumpToRecord={onJumpToRecord}
      />
      <RelatedSection
        title={relatedInfo.labels?.similar_cases ?? "相关项目"}
        items={relatedInfo.similar_cases ?? []}
        emptyText={`没有匹配${relatedInfo.labels?.similar_cases ?? "相关项目"}`}
        onJumpToRecord={onJumpToRecord}
      />
      <RelatedSection
        title={relatedInfo.labels?.audit_logs ?? "审计日志"}
        items={relatedInfo.audit_logs}
        emptyText={`没有匹配${relatedInfo.labels?.audit_logs ?? "审计日志"}`}
        onJumpToRecord={onJumpToRecord}
      />
    </div>
  );
}

function RelatedSection({
  title,
  items,
  emptyText,
  onJumpToRecord,
}: {
  title: string;
  items: Record<string, JsonValue>[];
  emptyText: string;
  onJumpToRecord: (tableId: string, recordId: JsonValue) => void;
}) {
  return (
    <section className="related-section">
      <h2>{title}</h2>
      {items.length === 0 ? (
        <div className="empty-state small">{emptyText}</div>
      ) : (
        items.map((item) => (
          <button
            key={`${item.table_id}-${item.id}`}
            className="related-card"
            onClick={() => {
              if (typeof item.table_id === "string") {
                onJumpToRecord(item.table_id, item.id);
              }
            }}
          >
            <div>
              <strong>{recordTitle(item)}</strong>
              <span>{recordSubtitle(item)}</span>
            </div>
            <Link2 size={16} />
          </button>
        ))
      )}
    </section>
  );
}

async function fetchOverviewWithFallback(backendUrl: string, headers: HeadersInit, industry: string): Promise<Response> {
  return fetchWithFallback(backendUrl, `/api/database/overview?industry=${encodeURIComponent(industry)}`, { headers });
}

async function fetchRelatedInfoWithFallback(backendUrl: string, customerName: string, headers: HeadersInit, industry: string): Promise<Response> {
  return fetchWithFallback(backendUrl, `/api/database/customers/${encodeURIComponent(customerName)}/related?industry=${encodeURIComponent(industry)}`, { headers });
}

async function fetchSupportDashboardWithFallback(backendUrl: string, headers: HeadersInit): Promise<Response> {
  return fetchWithFallback(backendUrl, "/api/database/support/dashboard", { headers });
}

async function fetchImportFaqWithFallback(backendUrl: string, headers: HeadersInit, text: string, sourceType: string): Promise<Response> {
  return fetchWithFallback(backendUrl, "/api/database/support/import-faq", {
    method: "POST",
    headers,
    body: JSON.stringify({ text, source_type: sourceType }),
  });
}

async function fetchImportFileWithFallback(backendUrl: string, headers: HeadersInit, formData: FormData): Promise<Response> {
  return fetchWithFallback(backendUrl, "/api/database/support/import-file", {
    method: "POST",
    headers,
    body: formData,
  });
}

async function fetchRebuildIndexWithFallback(backendUrl: string, headers: HeadersInit, documentId: string): Promise<Response> {
  return fetchWithFallback(backendUrl, `/api/database/knowledge/${encodeURIComponent(documentId)}/rebuild-index`, {
    method: "POST",
    headers,
  });
}

async function fetchUpdateUserKnowledgePolicyWithFallback(
  backendUrl: string,
  headers: HeadersInit,
  userId: string,
  policy: "all" | "own",
): Promise<Response> {
  return fetchWithFallback(backendUrl, `/api/database/users/${encodeURIComponent(userId)}/knowledge-policy`, {
    method: "POST",
    headers,
    body: JSON.stringify({ knowledge_access_policy: policy }),
  });
}

async function fetchGrantKnowledgePermissionWithFallback(
  backendUrl: string,
  headers: HeadersInit,
  documentId: string,
  userId: string,
): Promise<Response> {
  return fetchWithFallback(backendUrl, `/api/database/knowledge/${encodeURIComponent(documentId)}/permissions`, {
    method: "POST",
    headers,
    body: JSON.stringify({ user_id: userId, access_level: "read" }),
  });
}

function jsonHeaders(apiKey: string): HeadersInit {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (apiKey.trim()) {
    headers.Authorization = `Bearer ${apiKey.trim()}`;
  }
  return headers;
}

async function fetchPostWithFallback(backendUrl: string, headers: HeadersInit, path: string, payload: Record<string, JsonValue>): Promise<Response> {
  return fetchWithFallback(backendUrl, path, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
}

async function fetchUpdateUnansweredStatusWithFallback(
  backendUrl: string,
  headers: HeadersInit,
  unansweredId: string,
  status: "resolved" | "ignored",
): Promise<Response> {
  return fetchWithFallback(backendUrl, `/api/database/support/unanswered/${encodeURIComponent(unansweredId)}/status`, {
    method: "POST",
    headers,
    body: JSON.stringify({ status }),
  });
}

async function fetchWithFallback(backendUrl: string, path: string, init: RequestInit): Promise<Response> {
  const candidates = [backendUrl, ...localBackendFallbacks].filter((url, index, urls) => urls.indexOf(url) === index);
  let lastError = "";

  for (const candidate of candidates) {
    try {
      const response = await fetch(`${candidate.replace(/\/$/, "")}${path}`, {
        ...init,
      });
      if (response.ok) return response;
      const detail = await readError(response);
      lastError = `${candidate}: ${response.status} ${response.statusText}${detail ? `: ${detail}` : ""}`;
    } catch (error) {
      lastError = `${candidate}: ${error instanceof Error ? error.message : "请求失败"}`;
    }
  }

  throw new Error(lastError || "无法连接后端");
}

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? "";
  } catch {
    return "";
  }
}

function recordTitle(row: Record<string, JsonValue>): string {
  for (const key of ["title", "name", "risk_title", "action", "id"]) {
    const value = row[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return "未命名记录";
}

function recordSubtitle(row: Record<string, JsonValue>): string {
  for (const key of ["summary", "description", "content_text", "status", "created_at", "updated_at"]) {
    const value = row[key];
    if (typeof value === "string" && value.trim()) return truncate(value, 96);
  }
  return truncate(JSON.stringify(row), 96);
}

function formatValue(value: JsonValue): string {
  if (value === null) return "-";
  if (Array.isArray(value) || typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}

function truncate(value: string, maxLength: number): string {
  return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;
}

export default App;
