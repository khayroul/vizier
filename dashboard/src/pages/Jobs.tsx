import { useState, useCallback } from "react";
import { usePolling } from "../hooks/usePolling";

interface JobTrace {
  id: string;
  client_id: string;
  client_name: string;
  job_type: string;
  status: string;
  priority: string;
  posture: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  step_count: number;
  total_tokens: number | null;
  total_cost_usd: number | null;
  last_step: string | null;
  raw_trace: {
    steps?: StepTrace[];
    started_at?: string;
    completed_at?: string;
  } | null;
  goal_chain: Record<string, unknown> | null;
}

interface StepTrace {
  step_name: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  duration_ms: number;
  trace_id: string;
  timestamp: string;
  error: string | null;
  proof: Record<string, unknown> | null;
}

interface FeedbackRow {
  id: string;
  job_id: string;
  feedback_status: string;
  operator_rating: number | null;
}

interface ArtifactRow {
  id: string;
  job_id: string;
  artifact_type: string;
  role: string;
  status: string;
  version_number: number;
}

const STATUS_BADGE: Record<string, string> = {
  received: "badge-info",
  routing: "badge-info",
  in_progress: "badge-warning",
  completed: "badge-success",
  delivered: "badge-success",
  failed: "badge-danger",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("en-MY", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function JobsPage() {
  const [expandedJob, setExpandedJob] = useState<string | null>(null);
  const [expandedStep, setExpandedStep] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [jobDetail, setJobDetail] = useState<{
    feedback: FeedbackRow[];
    artifacts: ArtifactRow[];
  } | null>(null);

  const queryParts: string[] = ["order=created_at.desc", "limit=50"];
  if (statusFilter) queryParts.push(`status=eq.${statusFilter}`);

  const { data: jobs, loading } = usePolling<JobTrace[]>({
    url: "v_job_traces",
    queryParams: queryParts.join("&"),
  });

  const toggleJob = useCallback(async (jobId: string) => {
    if (expandedJob === jobId) {
      setExpandedJob(null);
      setExpandedStep(null);
      setJobDetail(null);
      return;
    }
    setExpandedJob(jobId);
    setExpandedStep(null);

    const [fbResp, artResp] = await Promise.all([
      fetch(`/api/feedback?job_id=eq.${jobId}`),
      fetch(`/api/artifacts?job_id=eq.${jobId}`),
    ]);
    const [feedback, artifacts] = await Promise.all([fbResp.json(), artResp.json()]);
    setJobDetail({ feedback, artifacts });
  }, [expandedJob]);

  const statuses = ["received", "routing", "in_progress", "completed", "delivered", "failed"];

  if (loading) return <div className="loading">Loading jobs...</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Jobs</h2>
        <p>Click any row to inspect. Pull deeper into trace steps.</p>
      </div>

      <div className="filter-bar">
        <button
          className={`filter-btn ${statusFilter === null ? "active" : ""}`}
          onClick={() => setStatusFilter(null)}
        >
          All
        </button>
        {statuses.map((s) => (
          <button
            key={s}
            className={`filter-btn ${statusFilter === s ? "active" : ""}`}
            onClick={() => setStatusFilter(s)}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Client</th>
              <th>Type</th>
              <th>Status</th>
              <th>Steps</th>
              <th>Tokens</th>
              <th>Cost</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {jobs?.map((job) => (
              <>
                {/* Level 1: Job row */}
                <tr
                  key={job.id}
                  className={`clickable ${expandedJob === job.id ? "expanded" : ""}`}
                  onClick={() => toggleJob(job.id)}
                >
                  <td style={{ color: "var(--text-primary)" }}>{job.client_name}</td>
                  <td>{job.job_type}</td>
                  <td>
                    <span className={`badge ${STATUS_BADGE[job.status] ?? "badge-neutral"}`}>
                      {job.status}
                    </span>
                  </td>
                  <td>{job.step_count ?? "—"}</td>
                  <td>{job.total_tokens?.toLocaleString() ?? "—"}</td>
                  <td>{job.total_cost_usd != null ? `$${Number(job.total_cost_usd).toFixed(4)}` : "—"}</td>
                  <td>{formatDate(job.created_at)}</td>
                </tr>

                {/* Level 2: Job detail (inline expansion) */}
                {expandedJob === job.id && (
                  <tr key={`${job.id}-detail`} className="expand-row">
                    <td colSpan={7}>
                      <div className="expand-content">
                        {/* Goal chain */}
                        {job.goal_chain && (
                          <div style={{ marginBottom: 16 }}>
                            <h4>Goal Chain</h4>
                            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                              {Object.entries(job.goal_chain).map(([k, v]) => (
                                <div key={k} style={{ padding: "4px 10px", background: "var(--bg-primary)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
                                  <span style={{ fontSize: 10, color: "var(--text-tertiary)", textTransform: "uppercase" }}>{k}: </span>
                                  <span style={{ fontSize: 12, fontFamily: "var(--font-mono)" }}>{String(v)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Artifacts */}
                        {jobDetail?.artifacts && jobDetail.artifacts.length > 0 && (
                          <div style={{ marginBottom: 16 }}>
                            <h4>Artifacts</h4>
                            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                              {jobDetail.artifacts.map((a) => (
                                <span key={a.id} className="badge badge-info">
                                  {a.artifact_type} v{a.version_number} — {a.status}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Feedback */}
                        {jobDetail?.feedback && jobDetail.feedback.length > 0 && (
                          <div style={{ marginBottom: 16 }}>
                            <h4>Feedback</h4>
                            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                              {jobDetail.feedback.map((f) => (
                                <span
                                  key={f.id}
                                  className={`badge ${
                                    f.feedback_status === "explicitly_approved"
                                      ? "badge-success"
                                      : f.feedback_status === "revision_requested"
                                      ? "badge-warning"
                                      : f.feedback_status === "awaiting"
                                      ? "badge-info"
                                      : "badge-neutral"
                                  }`}
                                >
                                  {f.feedback_status}
                                  {f.operator_rating != null && ` (${f.operator_rating}/5)`}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Production trace timeline */}
                        <h4>Production Trace</h4>
                        {job.raw_trace?.steps && job.raw_trace.steps.length > 0 ? (
                          <div className="timeline">
                            {job.raw_trace.steps.map((step, idx) => (
                              <div key={idx}>
                                <div
                                  className="timeline-step"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setExpandedStep(expandedStep === idx ? null : idx);
                                  }}
                                >
                                  <div
                                    className="timeline-dot"
                                    style={{
                                      background: step.error
                                        ? "var(--danger)"
                                        : "var(--accent)",
                                    }}
                                  />
                                  <div className="timeline-info">
                                    <div className="timeline-name">{step.step_name}</div>
                                    <div className="timeline-meta">
                                      {step.model} · {(step.input_tokens + step.output_tokens).toLocaleString()} tok · ${step.cost_usd.toFixed(4)} · {step.duration_ms.toFixed(1)}ms
                                    </div>
                                  </div>
                                </div>

                                {/* Level 3: Step detail */}
                                {expandedStep === idx && (
                                  <div className="step-detail">
                                    <div className="step-detail-grid">
                                      <div className="step-detail-item">
                                        <label>Model</label>
                                        <span>{step.model}</span>
                                      </div>
                                      <div className="step-detail-item">
                                        <label>Input Tokens</label>
                                        <span>{step.input_tokens.toLocaleString()}</span>
                                      </div>
                                      <div className="step-detail-item">
                                        <label>Output Tokens</label>
                                        <span>{step.output_tokens.toLocaleString()}</span>
                                      </div>
                                      <div className="step-detail-item">
                                        <label>Cost</label>
                                        <span>${step.cost_usd.toFixed(6)}</span>
                                      </div>
                                      <div className="step-detail-item">
                                        <label>Duration</label>
                                        <span>{step.duration_ms.toFixed(2)} ms</span>
                                      </div>
                                      <div className="step-detail-item">
                                        <label>Trace ID</label>
                                        <span>{step.trace_id}</span>
                                      </div>
                                      <div className="step-detail-item">
                                        <label>Timestamp</label>
                                        <span>{step.timestamp}</span>
                                      </div>
                                      <div className="step-detail-item">
                                        <label>Error</label>
                                        <span style={{ color: step.error ? "var(--danger)" : "var(--text-tertiary)" }}>
                                          {step.error ?? "none"}
                                        </span>
                                      </div>
                                    </div>
                                    {step.proof && (
                                      <div style={{ marginTop: 12 }}>
                                        <label style={{ display: "block", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-tertiary)", marginBottom: 4 }}>
                                          Proof
                                        </label>
                                        <pre style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-secondary)", background: "var(--bg-secondary)", padding: 8, borderRadius: "var(--radius-sm)", overflow: "auto", maxHeight: 200 }}>
                                          {JSON.stringify(step.proof, null, 2)}
                                        </pre>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{ fontSize: 12, color: "var(--text-tertiary)", padding: "8px 0" }}>
                            No trace steps recorded yet
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
        {jobs?.length === 0 && (
          <div className="empty-state">
            <h3>Welcome to Vizier</h3>
            <p>No jobs found. Let's set up your first deployment.</p>
          </div>
        )}
      </div>
    </div>
  );
}
