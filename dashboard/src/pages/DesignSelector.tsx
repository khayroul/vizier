import { useState, FormEvent } from "react";

interface SelectorResult {
  systems: string[];
  error?: string;
}

export function DesignSelectorPage() {
  const [clientId, setClientId] = useState("");
  const [artifactFamily, setArtifactFamily] = useState("");
  const [topK, setTopK] = useState(3);
  const [results, setResults] = useState<SelectorResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!clientId.trim()) return;

    setLoading(true);
    try {
      const params = new URLSearchParams({
        client_id: clientId.trim(),
        top_k: String(topK),
      });
      if (artifactFamily) params.set("artifact_family", artifactFamily);

      const resp = await fetch(`/api/rpc/select_design_systems?${params}`);
      if (!resp.ok) {
        // PostgREST doesn't expose Python functions — use the Python API proxy
        const proxyResp = await fetch(
          `http://localhost:8080/design-systems?${params}`
        );
        if (!proxyResp.ok) throw new Error(`HTTP ${proxyResp.status}`);
        const data = await proxyResp.json();
        setResults(data);
      } else {
        const data = await resp.json();
        setResults({ systems: data });
      }
    } catch (err) {
      setResults({
        systems: [],
        error: err instanceof Error ? err.message : "Failed to fetch",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>Design System Selector</h2>
        <p>
          Preview design system scoring — calls contracts/routing.py's
          select_design_systems()
        </p>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <form onSubmit={handleSubmit} className="selector-widget">
          <div className="selector-field">
            <label>Client ID</label>
            <input
              type="text"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="e.g. dmb"
            />
          </div>
          <div className="selector-field">
            <label>Artifact Family</label>
            <select
              value={artifactFamily}
              onChange={(e) => setArtifactFamily(e.target.value)}
            >
              <option value="">Any</option>
              <option value="poster">Poster</option>
              <option value="brochure">Brochure</option>
              <option value="document">Document</option>
              <option value="ebook">E-book</option>
              <option value="childrens_book">Children's Book</option>
              <option value="social">Social Media</option>
            </select>
          </div>
          <div className="selector-field">
            <label>Top K</label>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
            >
              <option value={3}>3</option>
              <option value={5}>5</option>
              <option value={10}>10</option>
            </select>
          </div>
          <button
            type="submit"
            className="filter-btn active"
            style={{ alignSelf: "end", padding: "8px 20px" }}
            disabled={loading || !clientId.trim()}
          >
            {loading ? "Querying..." : "Select"}
          </button>
        </form>
      </div>

      {results && (
        <div className="card">
          {results.error ? (
            <div style={{ color: "var(--danger)", fontSize: 13 }}>
              <strong>Error:</strong> {results.error}
              <p style={{ color: "var(--text-tertiary)", marginTop: 8, fontSize: 12 }}>
                The design system selector requires the Python API proxy running
                at localhost:8080. Start it with: python3.11
                tools/design_selector_api.py
              </p>
            </div>
          ) : (
            <>
              <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
                Top {results.systems.length} Design Systems
              </h4>
              <div className="selector-results">
                {results.systems.map((sys, idx) => (
                  <div key={sys} className="selector-result-card">
                    <div className="score">#{idx + 1}</div>
                    <h4>{sys}</h4>
                  </div>
                ))}
              </div>
              {results.systems.length === 0 && (
                <div style={{ color: "var(--text-tertiary)", fontSize: 13 }}>
                  No matching design systems found for this client.
                </div>
              )}
            </>
          )}
        </div>
      )}

      <div className="card" style={{ marginTop: 24 }}>
        <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
          How It Works
        </h4>
        <p style={{ fontSize: 12, color: "var(--text-tertiary)", lineHeight: 1.6 }}>
          This widget calls <code style={{ fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>select_design_systems()</code> from{" "}
          <code style={{ fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>contracts/routing.py</code>.
          It scores design systems by industry overlap (+2), mood overlap (+1),
          density match (+1), and colour temperature match (+1) against the
          client's configuration. The function is LRU-cached on config file reads.
        </p>
      </div>
    </div>
  );
}
