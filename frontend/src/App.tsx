import { Database, FileText, KeyRound, Link2, RefreshCw, Search, Server, Table2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

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
  tables: OverviewTable[];
};

type CustomerRelatedInfo = {
  ok: boolean;
  customer_name: string;
  documents: Record<string, JsonValue>[];
  chunks: Record<string, JsonValue>[];
  audit_logs: Record<string, JsonValue>[];
};

const defaultBackendUrl = "http://127.0.0.1:8001";
const localBackendFallbacks = ["http://127.0.0.1:8001", "http://127.0.0.1:8000"];

function App() {
  const [backendUrl, setBackendUrl] = useState(defaultBackendUrl);
  const [apiKey, setApiKey] = useState("");
  const [query, setQuery] = useState("");
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [activeTableId, setActiveTableId] = useState("");
  const [selectedRowIndex, setSelectedRowIndex] = useState(0);
  const [relatedInfo, setRelatedInfo] = useState<CustomerRelatedInfo | null>(null);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [relatedError, setRelatedError] = useState("");
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
      const response = await fetchOverviewWithFallback(backendUrl, headers);
      const body = (await response.json()) as OverviewResponse;
      setData(body);
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
      const response = await fetchRelatedInfoWithFallback(backendUrl, customerName, headers);
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
          <h1>数据库记录看板</h1>
          <p>查看企业 AI 助手已经记录到业务数据库里的客户、项目、知识库和审计信息。</p>
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
                      <span>{relatedLoading ? "加载中" : "查看客户相关信息"}</span>
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
      <RelatedSection title="知识文档" items={relatedInfo.documents} emptyText="没有匹配知识文档" onJumpToRecord={onJumpToRecord} />
      <RelatedSection title="知识切片" items={relatedInfo.chunks} emptyText="没有匹配知识切片" onJumpToRecord={onJumpToRecord} />
      <RelatedSection title="审计日志" items={relatedInfo.audit_logs} emptyText="没有匹配审计日志" onJumpToRecord={onJumpToRecord} />
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

async function fetchOverviewWithFallback(backendUrl: string, headers: HeadersInit): Promise<Response> {
  const candidates = [backendUrl, ...localBackendFallbacks].filter((url, index, urls) => urls.indexOf(url) === index);
  let lastError = "";

  for (const candidate of candidates) {
    try {
      const response = await fetch(`${candidate.replace(/\/$/, "")}/api/database/overview`, { headers });
      if (response.ok) return response;
      const detail = await readError(response);
      lastError = `${candidate}: ${response.status} ${response.statusText}${detail ? `: ${detail}` : ""}`;
    } catch (error) {
      lastError = `${candidate}: ${error instanceof Error ? error.message : "请求失败"}`;
    }
  }

  throw new Error(lastError || "无法连接后端");
}

async function fetchRelatedInfoWithFallback(backendUrl: string, customerName: string, headers: HeadersInit): Promise<Response> {
  const candidates = [backendUrl, ...localBackendFallbacks].filter((url, index, urls) => urls.indexOf(url) === index);
  let lastError = "";

  for (const candidate of candidates) {
    try {
      const response = await fetch(`${candidate.replace(/\/$/, "")}/api/database/customers/${encodeURIComponent(customerName)}/related`, {
        headers,
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
