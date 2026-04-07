import { usePolling } from "../hooks/usePolling";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

interface TokenDay {
  day: string;
  tokens: number;
  cost_usd: number;
  job_count: number;
}

interface TokenByModel {
  model: string;
  day: string;
  tokens: number;
  cost_usd: number;
  step_count: number;
}

function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString("en", { month: "short", day: "numeric" });
}

export function TokenSpendPage() {
  const daily = usePolling<TokenDay[]>({
    url: "v_token_spend_daily",
    queryParams: "limit=30&order=day.desc",
  });
  const byModel = usePolling<TokenByModel[]>({
    url: "v_token_spend_by_model",
    queryParams: "order=day.desc&limit=20",
  });

  const today = daily.data?.[0];
  const totalWeek = daily.data?.slice(0, 7).reduce((s, d) => s + d.tokens, 0) ?? 0;
  const costWeek = daily.data?.slice(0, 7).reduce((s, d) => s + Number(d.cost_usd), 0) ?? 0;

  const chartData = daily.data
    ? [...daily.data].reverse().map((d) => ({
        day: formatDay(d.day),
        tokens: d.tokens,
        cost: Number(d.cost_usd),
        jobs: d.job_count,
      }))
    : [];

  // Aggregate by model
  const modelTotals = new Map<string, { tokens: number; cost: number; steps: number }>();
  byModel.data?.forEach((row) => {
    const existing = modelTotals.get(row.model) ?? { tokens: 0, cost: 0, steps: 0 };
    existing.tokens += row.tokens;
    existing.cost += Number(row.cost_usd);
    existing.steps += row.step_count;
    modelTotals.set(row.model, existing);
  });

  if (daily.loading) return <div className="loading">Loading token data...</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Token Spend</h2>
        <p>Daily usage and cost breakdown</p>
      </div>

      <div className="card-grid">
        <div className="metric-card">
          <span className="metric-label">Today</span>
          <span className="metric-value">
            {today?.tokens?.toLocaleString() ?? "0"}
          </span>
          <span className="metric-sub">
            ${Number(today?.cost_usd ?? 0).toFixed(4)} USD · {today?.job_count ?? 0} jobs
          </span>
        </div>

        <div className="metric-card">
          <span className="metric-label">7-Day Total</span>
          <span className="metric-value">{totalWeek.toLocaleString()}</span>
          <span className="metric-sub">${costWeek.toFixed(4)} USD</span>
        </div>

        <div className="metric-card">
          <span className="metric-label">30-Day Jobs</span>
          <span className="metric-value">
            {daily.data?.reduce((s, d) => s + d.job_count, 0).toLocaleString() ?? "0"}
          </span>
          <span className="metric-sub">with traces</span>
        </div>
      </div>

      {/* Daily chart */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
          Daily Token Usage
        </h4>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="day"
                tick={{ fontSize: 11, fill: "#71717a", fontFamily: "JetBrains Mono" }}
                axisLine={{ stroke: "#27272a" }}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "#71717a", fontFamily: "JetBrains Mono" }}
                axisLine={{ stroke: "#27272a" }}
                tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
              />
              <Tooltip
                contentStyle={{
                  background: "#18181b",
                  border: "1px solid #27272a",
                  borderRadius: 6,
                  fontSize: 12,
                  fontFamily: "JetBrains Mono",
                }}
                labelStyle={{ color: "#fafafa" }}
                formatter={(value: unknown, name: unknown) =>
                  name === "tokens"
                    ? [Number(value).toLocaleString(), "Tokens"]
                    : [`$${Number(value).toFixed(4)}`, "Cost USD"]
                }
              />
              <Bar dataKey="tokens" fill="#6366f1" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Model breakdown */}
      <div className="card">
        <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
          Breakdown by Model
        </h4>
        <table className="data-table">
          <thead>
            <tr>
              <th>Model</th>
              <th>Tokens</th>
              <th>Cost USD</th>
              <th>Steps</th>
            </tr>
          </thead>
          <tbody>
            {Array.from(modelTotals.entries())
              .sort((a, b) => b[1].tokens - a[1].tokens)
              .map(([model, data]) => (
                <tr key={model}>
                  <td style={{ color: "var(--text-primary)" }}>{model}</td>
                  <td>{data.tokens.toLocaleString()}</td>
                  <td>${data.cost.toFixed(4)}</td>
                  <td>{data.steps}</td>
                </tr>
              ))}
            {modelTotals.size === 0 && (
              <tr>
                <td colSpan={4} style={{ textAlign: "center", color: "var(--text-tertiary)" }}>
                  No model data available
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
