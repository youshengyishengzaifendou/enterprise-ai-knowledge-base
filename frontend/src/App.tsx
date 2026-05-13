import { AlertCircle, BarChart3, Database, FileText, KeyRound, Link2, RefreshCw, Search, Server, Table2, Upload } from "lucide-react";
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
          onFaqTextChange={setFaqText}
          onFaqSourceTypeChange={setFaqSourceType}
          onImportFaq={() => void importFaq()}
          onUpdateUnansweredStatus={(id, status) => void updateUnansweredStatus(id, status)}
        />
      ) : null}

      <section className="summary-grid">
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

function SupportOperationsPanel({
  dashboard,
  faqText,
  faqSourceType,
  importMessage,
  importingFaq,
  onFaqTextChange,
  onFaqSourceTypeChange,
  onImportFaq,
  onUpdateUnansweredStatus,
}: {
  dashboard: SupportDashboard | null;
  faqText: string;
  faqSourceType: string;
  importMessage: string;
  importingFaq: boolean;
  onFaqTextChange: (value: string) => void;
  onFaqSourceTypeChange: (value: string) => void;
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

        <section className="ops-section import-section">
          <h2>
            <Upload size={16} />
            导入客服 FAQ
          </h2>
          <label className="inline-select">
            <span>格式</span>
            <select value={faqSourceType} onChange={(event) => onFaqSourceTypeChange(event.target.value)}>
              <option value="faq_csv">CSV FAQ</option>
              <option value="markdown">Markdown</option>
              <option value="txt">TXT</option>
            </select>
          </label>
          <textarea
            value={faqText}
            onChange={(event) => onFaqTextChange(event.target.value)}
            placeholder={"问题,答案\n怎么退款,订单未发货可以直接退款\n物流丢件怎么办,先联系快递核实并补发"}
          />
          <button className="secondary-button" onClick={onImportFaq} disabled={importingFaq || !faqText.trim()}>
            <Upload size={16} />
            <span>{importingFaq ? "导入中" : "导入 FAQ"}</span>
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
  const candidates = [backendUrl, ...localBackendFallbacks].filter((url, index, urls) => urls.indexOf(url) === index);
  let lastError = "";

  for (const candidate of candidates) {
    try {
      const response = await fetch(`${candidate.replace(/\/$/, "")}/api/database/overview?industry=${encodeURIComponent(industry)}`, { headers });
      if (response.ok) return response;
      const detail = await readError(response);
      lastError = `${candidate}: ${response.status} ${response.statusText}${detail ? `: ${detail}` : ""}`;
    } catch (error) {
      lastError = `${candidate}: ${error instanceof Error ? error.message : "请求失败"}`;
    }
  }

  throw new Error(lastError || "无法连接后端");
}

async function fetchRelatedInfoWithFallback(backendUrl: string, customerName: string, headers: HeadersInit, industry: string): Promise<Response> {
  const candidates = [backendUrl, ...localBackendFallbacks].filter((url, index, urls) => urls.indexOf(url) === index);
  let lastError = "";

  for (const candidate of candidates) {
    try {
      const response = await fetch(
        `${candidate.replace(/\/$/, "")}/api/database/customers/${encodeURIComponent(customerName)}/related?industry=${encodeURIComponent(industry)}`,
        { headers },
      );
      if (response.ok) return response;
      const detail = await readError(response);
      lastError = `${candidate}: ${response.status} ${response.statusText}${detail ? `: ${detail}` : ""}`;
    } catch (error) {
      lastError = `${candidate}: ${error instanceof Error ? error.message : "请求失败"}`;
    }
  }

  throw new Error(lastError || "无法连接后端");
}

async function fetchSupportDashboardWithFallback(backendUrl: string, headers: HeadersInit): Promise<Response> {
  const candidates = [backendUrl, ...localBackendFallbacks].filter((url, index, urls) => urls.indexOf(url) === index);
  let lastError = "";

  for (const candidate of candidates) {
    try {
      const response = await fetch(`${candidate.replace(/\/$/, "")}/api/database/support/dashboard`, { headers });
      if (response.ok) return response;
      const detail = await readError(response);
      lastError = `${candidate}: ${response.status} ${response.statusText}${detail ? `: ${detail}` : ""}`;
    } catch (error) {
      lastError = `${candidate}: ${error instanceof Error ? error.message : "请求失败"}`;
    }
  }

  throw new Error(lastError || "无法连接后端");
}

async function fetchImportFaqWithFallback(backendUrl: string, headers: HeadersInit, text: string, sourceType: string): Promise<Response> {
  const candidates = [backendUrl, ...localBackendFallbacks].filter((url, index, urls) => urls.indexOf(url) === index);
  let lastError = "";

  for (const candidate of candidates) {
    try {
      const response = await fetch(`${candidate.replace(/\/$/, "")}/api/database/support/import-faq`, {
        method: "POST",
        headers,
        body: JSON.stringify({ text, source_type: sourceType }),
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

async function fetchUpdateUnansweredStatusWithFallback(
  backendUrl: string,
  headers: HeadersInit,
  unansweredId: string,
  status: "resolved" | "ignored",
): Promise<Response> {
  const candidates = [backendUrl, ...localBackendFallbacks].filter((url, index, urls) => urls.indexOf(url) === index);
  let lastError = "";

  for (const candidate of candidates) {
    try {
      const response = await fetch(`${candidate.replace(/\/$/, "")}/api/database/support/unanswered/${encodeURIComponent(unansweredId)}/status`, {
        method: "POST",
        headers,
        body: JSON.stringify({ status }),
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
