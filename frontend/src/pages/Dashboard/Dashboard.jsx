import { useState } from "react";
import { Routes, Route } from "react-router-dom";
import Sidebar from "../../components/Sidebar/Sidebar";
import { useAuth } from "../../context/AuthContext";
import AddBrokerCredentials from "../UserPage/AddBrokerCredentials";
import Bots from "../UserPage/Bots";

import "./Dashboard.css";

/* ── Placeholder sub-pages ── */
const ComingSoon = ({ title }) => (
  <div className="coming-soon">
    <span className="coming-soon__icon">◈</span>
    <h3>{title}</h3>
    <p>This section is under construction. Check back soon.</p>
  </div>
);

/* ── Overview / Home ── */
function Overview() {
  const { user } = useAuth();
  const stats = [
    { label: "Account Balance", value: "$0.00", change: "—", up: null },
    { label: "Profit Today", value: "$0.00", change: "0.00%", up: true },
    { label: "Drawdown", value: "0.00%", change: "Safe", up: true },
    { label: "Payout Ready", value: "$0.00", change: "—", up: null },
  ];

  return (
    <div className="overview">
      <div className="overview__welcome">
        <h2>
          Welcome back, <span className="glow-text">{user?.first_name}</span> 👋
        </h2>
        <p>Here's your trading performance overview.</p>
      </div>

      <div className="overview__stats">
        {stats.map((s) => (
          <div key={s.label} className="dash-stat card">
            <span className="dash-stat__label">{s.label}</span>
            <span className="dash-stat__value">{s.value}</span>
            <span
              className={`dash-stat__change ${s.up === true ? "up" : s.up === false ? "down" : ""}`}
            >
              {s.change}
            </span>
          </div>
        ))}
      </div>

      <div className="overview__grid">
        <div className="card overview__chart-placeholder">
          <h4>Performance Chart</h4>
          <p>Chart component will be added here.</p>
          <div className="chart-mock">
            {[40, 55, 45, 70, 60, 80, 75, 90, 85, 95].map((h, i) => (
              <div
                key={i}
                className="chart-mock__bar"
                style={{ height: `${h}%` }}
              />
            ))}
          </div>
        </div>
        <div className="card overview__activity">
          <h4>Recent Activity</h4>
          <div className="activity-empty">
            <span>◉</span>
            <p>No trades yet. Start your first challenge.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Dashboard shell ── */
export default function Dashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="dashboard">
      <Sidebar mobileOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="dashboard__main">
        {/* Top bar */}
        <header className="dashboard__topbar">
          <button
            className="dashboard__menu-btn"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
          >
            ☰
          </button>
          <div className="dashboard__topbar-right">
            <div className="badge badge-green animate-pulse-glow">● Live</div>
          </div>
        </header>

        {/* Content */}
        <main className="dashboard__content">
          <Routes>
            <Route index element={<Overview />} />

            <Route path="accounts" element={<AddBrokerCredentials />} />

            <Route path="bots" element={<Bots />} />

            <Route
              path="analytics"
              element={<ComingSoon title="Analytics" />}
            />
            <Route path="trades" element={<ComingSoon title="Trades" />} />
            <Route path="payouts" element={<ComingSoon title="Payouts" />} />
            <Route
              path="leaderboard"
              element={<ComingSoon title="Leaderboard" />}
            />
            <Route
              path="affiliates"
              element={<ComingSoon title="Affiliates" />}
            />
            <Route path="settings" element={<ComingSoon title="Settings" />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
