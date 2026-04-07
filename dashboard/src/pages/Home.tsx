import { usePolling } from "../hooks/usePolling";

interface SystemHealth {
  current_version: string;
  active_clients: number;
  active_jobs: number;
  jobs_completed_24h: number;
  cost_24h_usd: number;
}

interface TokenDay {
  day: string;
  tokens: number;
  cost_usd: number;
  job_count: number;
}

interface FeedbackSummary {
  status: string;
  count: number;
  avg_approved_rating: number | null;
}

interface PipelineSummary {
  stage: string;
  count: number;
  total_value_rm: number | null;
}

interface ClientHealth {
  id: string;
  name: string;
  last_job_at: string | null;
  total_jobs: number;
  total_approved: number;
  total_revision: number;
  feedback_collection_rate_pct: number;
}

interface OverdueInvoice {
  id: string;
  client_name: string;
  invoice_number: string;
  amount_rm: number;
  overdue_by: string;
}

const STAGE_ORDER = ["lead", "contacted", "proposal_sent", "negotiating", "won"];

export function HomePage() {
  const health = usePolling<SystemHealth[]>({ url: "v_system_health" });
  const tokens = usePolling<TokenDay[]>({ url: "v_token_spend_daily", queryParams: "limit=7&order=day.desc" });
  const feedbackSummary = usePolling<FeedbackSummary[]>({ url: "v_feedback_summary" });
  const pipeline = usePolling<PipelineSummary[]>({ url: "v_pipeline_summary" });
  const overdue = usePolling<OverdueInvoice[]>({ url: "v_overdue_invoices" });
  const clientHealth = usePolling<ClientHealth[]>({ url: "v_client_health", queryParams: "order=total_jobs.desc&limit=5" });

  const sys = health.data?.[0];
  const todayTokens = tokens.data?.[0];
  const awaitingCount = feedbackSummary.data?.find((f) => f.status === "awaiting")?.count ?? 0;
  const totalPipelineValue = pipeline.data?.reduce((sum, p) => sum + (p.total_value_rm ?? 0), 0) ?? 0;

  if (health.loading) return <div className="loading">Loading dashboard...</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Surface</h2>
        <p>
          {health.lastUpdated && (
            <span>Last updated {health.lastUpdated.toLocaleTimeString()}</span>
          )}
        </p>
      </div>

      <div className="card-grid">
        <div className="metric-card">
          <span className="metric-label">Tokens Today</span>
          <span className="metric-value">
            {todayTokens ? todayTokens.tokens.toLocaleString() : "0"}
          </span>
          <span className="metric-sub">
            ${todayTokens?.cost_usd?.toFixed(4) ?? "0.00"} USD
          </span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Active Jobs</span>
          <span className="metric-value">{sys?.active_jobs ?? 0}</span>
          <span className="metric-sub">
            {sys?.jobs_completed_24h ?? 0} completed 24h
          </span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Feedback Pending</span>
          <span className="metric-value">{awaitingCount}</span>
          <span className="metric-sub">awaiting response</span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Pipeline Value</span>
          <span className="metric-value">
            RM {totalPipelineValue.toLocaleString()}
          </span>
          <span className="metric-sub">
            {pipeline.data?.reduce((s, p) => s + p.count, 0) ?? 0} prospects
          </span>
        </div>
      </div>

      {/* Token trend sparkline (last 7 days) */}
      {tokens.data && tokens.data.length > 1 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
            Token Spend — 7 Day Trend
          </h4>
          <div style={{ display: "flex", alignItems: "end", gap: 4, height: 60 }}>
            {[...tokens.data].reverse().map((day) => {
              const max = Math.max(...tokens.data!.map((d) => d.tokens));
              const pct = max > 0 ? (day.tokens / max) * 100 : 0;
              return (
                <div
                  key={day.day}
                  title={`${day.day}: ${day.tokens.toLocaleString()} tokens`}
                  style={{
                    flex: 1,
                    height: `${Math.max(pct, 4)}%`,
                    background: "var(--accent)",
                    borderRadius: "3px 3px 0 0",
                    opacity: 0.7,
                    transition: "height 0.3s",
                  }}
                />
              );
            })}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
            {[...tokens.data].reverse().map((day) => (
              <span key={day.day} style={{ flex: 1, textAlign: "center", fontSize: 10, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>
                {new Date(day.day).toLocaleDateString("en", { weekday: "short" })}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Pipeline funnel */}
      {pipeline.data && pipeline.data.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
            Pipeline Stages
          </h4>
          <div style={{ display: "flex", gap: 2 }}>
            {STAGE_ORDER.map((stage) => {
              const item = pipeline.data?.find((p) => p.stage === stage);
              const total = pipeline.data?.reduce((s, p) => s + p.count, 0) ?? 1;
              const pct = item ? (item.count / total) * 100 : 0;
              return (
                <div
                  key={stage}
                  style={{
                    flex: Math.max(pct, 5),
                    padding: "8px 12px",
                    background: "var(--bg-tertiary)",
                    borderRadius: "var(--radius-sm)",
                    textAlign: "center",
                  }}
                >
                  <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                    {item?.count ?? 0}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-tertiary)", textTransform: "uppercase" }}>
                    {stage.replace("_", " ")}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Client health + overdue */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="card">
          <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
            Top Clients
          </h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>Client</th>
                <th>Jobs</th>
                <th>Approved</th>
              </tr>
            </thead>
            <tbody>
              {clientHealth.data?.map((c) => (
                <tr key={c.id}>
                  <td style={{ color: "var(--text-primary)" }}>{c.name}</td>
                  <td>{c.total_jobs}</td>
                  <td>{c.total_approved}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
            Overdue Invoices
          </h4>
          {overdue.data && overdue.data.length > 0 ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Client</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {overdue.data.map((inv) => (
                  <tr key={inv.id}>
                    <td>
                      <span className="badge badge-danger">{inv.invoice_number}</span>
                    </td>
                    <td>{inv.client_name}</td>
                    <td>RM {Number(inv.amount_rm).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-state" style={{ padding: 20 }}>
              <span style={{ color: "var(--success)" }}>All clear</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
