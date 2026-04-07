import { usePolling } from "../hooks/usePolling";

interface PipelineItem {
  id: string;
  prospect_name: string;
  stage: string;
  estimated_value_rm: number | null;
  next_followup_at: string | null;
  source: string | null;
  notes: string | null;
  created_at: string;
  days_in_stage: number;
  client_name: string | null;
}

interface PipelineSummary {
  stage: string;
  count: number;
  total_value_rm: number | null;
  avg_days_in_stage: number;
}

const STAGES = ["lead", "contacted", "proposal_sent", "negotiating", "won", "lost"];

const STAGE_COLORS: Record<string, string> = {
  lead: "var(--text-tertiary)",
  contacted: "var(--info)",
  proposal_sent: "var(--warning)",
  negotiating: "var(--accent)",
  won: "var(--success)",
  lost: "var(--danger)",
};

export function PipelinePage() {
  const detail = usePolling<PipelineItem[]>({ url: "v_pipeline_detail" });
  const summary = usePolling<PipelineSummary[]>({ url: "v_pipeline_summary" });

  const byStage = new Map<string, PipelineItem[]>();
  STAGES.forEach((s) => byStage.set(s, []));
  detail.data?.forEach((item) => {
    const list = byStage.get(item.stage);
    if (list) list.push(item);
  });

  const totalValue = summary.data?.reduce((s, p) => s + (p.total_value_rm ?? 0), 0) ?? 0;

  if (detail.loading) return <div className="loading">Loading pipeline...</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Pipeline</h2>
        <p>
          {detail.data?.length ?? 0} prospects · RM {totalValue.toLocaleString()} total value
        </p>
      </div>

      {/* Summary strip */}
      <div className="card-grid" style={{ marginBottom: 24 }}>
        {summary.data
          ?.sort((a, b) => STAGES.indexOf(a.stage) - STAGES.indexOf(b.stage))
          .map((s) => (
            <div key={s.stage} className="metric-card">
              <span className="metric-label" style={{ color: STAGE_COLORS[s.stage] }}>
                {s.stage.replace("_", " ")}
              </span>
              <span className="metric-value">{s.count}</span>
              <span className="metric-sub">
                {s.total_value_rm ? `RM ${Number(s.total_value_rm).toLocaleString()}` : "—"}
                {s.avg_days_in_stage > 0 && ` · ${s.avg_days_in_stage}d avg`}
              </span>
            </div>
          ))}
      </div>

      {/* Kanban board */}
      <div className="kanban">
        {STAGES.map((stage) => {
          const items = byStage.get(stage) ?? [];
          return (
            <div key={stage} className="kanban-column">
              <div
                className="kanban-column-header"
                style={{ borderBottomColor: STAGE_COLORS[stage] }}
              >
                {stage.replace("_", " ")} ({items.length})
              </div>
              {items.map((item) => (
                <div key={item.id} className="kanban-card">
                  <div className="kanban-card-name">{item.prospect_name}</div>
                  <div className="kanban-card-meta">
                    {item.estimated_value_rm
                      ? `RM ${Number(item.estimated_value_rm).toLocaleString()}`
                      : "No estimate"}
                    {item.days_in_stage > 0 && ` · ${Math.round(item.days_in_stage)}d`}
                  </div>
                  {item.source && (
                    <div className="kanban-card-meta">{item.source}</div>
                  )}
                  {item.next_followup_at && (
                    <div className="kanban-card-meta" style={{ color: new Date(item.next_followup_at) < new Date() ? "var(--danger)" : "var(--text-tertiary)" }}>
                      Follow-up: {new Date(item.next_followup_at).toLocaleDateString("en-MY", { month: "short", day: "numeric" })}
                    </div>
                  )}
                </div>
              ))}
              {items.length === 0 && (
                <div style={{ padding: 12, fontSize: 12, color: "var(--text-tertiary)", textAlign: "center" }}>
                  Empty
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
