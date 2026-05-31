import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import "./Sidebar.css";

const MENU = [
  { icon: "⬡", label: "Overview", to: "/dashboard" },
  { icon: "◈", label: "My Accounts", to: "/dashboard/accounts" },
  { icon: "◉", label: "Analytics", to: "/dashboard/analytics" },
  { icon: "◫", label: "Trades", to: "/dashboard/trades" },
  { icon: "◬", label: "Payouts", to: "/dashboard/payouts" },
  { icon: "◧", label: "Leaderboard", to: "/dashboard/leaderboard" },
  { icon: "◪", label: "Affiliates", to: "/dashboard/affiliates" },
  { icon: "◩", label: "Settings", to: "/dashboard/settings" },
];

export default function Sidebar({ mobileOpen, onClose }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <>
      {mobileOpen && <div className="sidebar__overlay" onClick={onClose} />}
      <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
        {/* Brand */}
        <div className="sidebar__brand">
          <Link to="/" className="sidebar__logo">
            <span className="sidebar__logo-icon">◎</span>
            <span>ALGONEXIS</span>
          </Link>
        </div>

        {/* User info */}
        <div className="sidebar__user">
          <div className="sidebar__avatar">
            {user?.first_name?.[0]}
            {user?.last_name?.[0]}
          </div>
          <div className="sidebar__user-info">
            <span className="sidebar__user-name">
              {user?.first_name} {user?.last_name}
            </span>
            <span className="badge badge-cyan">{user?.role || "TRADER"}</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="sidebar__nav">
          {MENU.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`sidebar__link ${location.pathname === item.to ? "active" : ""}`}
              onClick={onClose}
            >
              <span className="sidebar__link-icon">{item.icon}</span>
              <span className="sidebar__link-label">{item.label}</span>
              {location.pathname === item.to && (
                <span className="sidebar__active-dot" />
              )}
            </Link>
          ))}
        </nav>

        {/* Logout */}
        <button className="sidebar__logout" onClick={handleLogout}>
          <span>⏻</span>
          <span>Logout</span>
        </button>
      </aside>
    </>
  );
}
