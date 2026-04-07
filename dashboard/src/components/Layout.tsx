import { ReactNode } from "react";
import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { path: "/", label: "Surface", icon: "◈" },
  { path: "/jobs", label: "Jobs", icon: "▦" },
  { path: "/token-spend", label: "Token Spend", icon: "◎" },
  { path: "/feedback", label: "Feedback", icon: "◇" },
  { path: "/pipeline", label: "Pipeline", icon: "▸" },
  { path: "/design-selector", label: "Design Systems", icon: "◆" },
];

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>Vizier</h1>
          <span>operator dashboard</span>
        </div>
        <nav>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 14 }}>
                {item.icon}
              </span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div style={{ padding: "12px 20px", borderTop: "1px solid var(--border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--text-tertiary)" }}>
            <span className="pulse" />
            PostgREST connected
          </div>
        </div>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}
