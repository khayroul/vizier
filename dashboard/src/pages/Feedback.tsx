import { useState } from "react";
import { usePolling } from "../hooks/usePolling";

interface FeedbackRow {
  id: string;
  job_id: string;
  artifact_id: string | null;
  client_id: string;
  feedback_status: string;
  delivered_at: string | null;
  feedback_received_at: string | null;
  operator_rating: number | null;
  operator_notes: string | null;
  raw_text: string | null;
  anchor_set: boolean;
  response_time_hours: number | null;
  created_at: string;
}

interface FeedbackSummary {
  status: string;
  count: number;
  avg_approved_rating: number | null;
  avg_response_hours: number | null;
}

const STATUS_BADGE: Record<string, string> = {
  awaiting: "badge-info",
  explicitly_approved: "badge-success",
  revision_requested: "badge-warning",
  rejected: "badge-danger",
  silence_flagged: "badge-neutral",
  prompted: "badge-info",
  responded: "badge-success",
  unresponsive: "badge-neutral",
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-MY", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function FeedbackPage() {
  const [filter, setFilter] = useState<string | null>(null);
  const summary = usePolling<FeedbackSummary[]>({ url: "v_feedback_summary" });

  const queryParts = ["order=created_at.desc", "limit=100", "anchor_set=eq.false"];
  if (filter) queryParts.push(`feedback_status=eq.${filter}`);
  const feedbackList = usePolling<FeedbackRow[]>({
    url: "feedback",
    queryParams: queryParts.join("&"),
  });

  const allStatuses = [
    "awaiting",
    "explicitly_approved",
    "revision_requested",
    "rejected",
    "silence_flagged",
    "prompted",
    "responded",
    "unresponsive",
  ];

  return (
    <div>
      <div className="page-header">
        <h2>Feedback</h2>
        <p>Client feedback state machine — excludes anchor set records</p>
      </div>

      {/* Summary cards */}
      <div className="card-grid">
        {summary.data?.map((s) => (
          <div key={s.status} className="metric-card" style={{ cursor: "pointer" }} onClick={() => setFilter(filter === s.status ? null : s.status)}>
            <span className="metric-label">{s.status.replace("_", " ")}</span>
            <span className="metric-value">{s.count}</span>
            {s.avg_approved_rating != null && (
              <span className="metric-sub">avg rating: {s.avg_approved_rating.toFixed(1)}/5</span>
            )}
            {s.avg_response_hours != null && (
              <span className="metric-sub">{s.avg_response_hours.toFixed(1)}h avg response</span>
            )}
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <button
          className={`filter-btn ${filter === null ? "active" : ""}`}
          onClick={() => setFilter(null)}
        >
          All
        </button>
        {allStatuses.map((s) => (
          <button
            key={s}
            className={`filter-btn ${filter === s ? "active" : ""}`}
            onClick={() => setFilter(filter === s ? null : s)}
          >
            {s.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Status</th>
              <th>Job</th>
              <th>Rating</th>
              <th>Response Time</th>
              <th>Delivered</th>
              <th>Received</th>
            </tr>
          </thead>
          <tbody>
            {feedbackList.data?.map((f) => (
              <tr key={f.id}>
                <td>
                  <span className={`badge ${STATUS_BADGE[f.feedback_status] ?? "badge-neutral"}`}>
                    {f.feedback_status}
                  </span>
                </td>
                <td>{f.job_id.slice(0, 8)}</td>
                <td>
                  {f.operator_rating != null ? (
                    <span style={{ color: f.operator_rating >= 4 ? "var(--success)" : f.operator_rating >= 3 ? "var(--warning)" : "var(--danger)" }}>
                      {f.operator_rating}/5
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td>{f.response_time_hours != null ? `${f.response_time_hours.toFixed(1)}h` : "—"}</td>
                <td>{formatDate(f.delivered_at)}</td>
                <td>{formatDate(f.feedback_received_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {feedbackList.loading && <div className="loading">Loading...</div>}
      </div>
    </div>
  );
}
