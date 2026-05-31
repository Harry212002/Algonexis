import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import "./Navbar.css";

const NAV_LINKS = [
  { label: "Home", to: "/" },
  { label: "Program", to: "/program" },
  { label: "About Us", to: "/about" },
  { label: "Affiliates", to: "/affiliates" },
  { label: "Contact", to: "/contact" },
];

export default function Navbar() {
  const { isAuthenticated, logout, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <nav className="navbar">
      <div className="navbar__inner container">
        {/* Logo */}
        <Link to="/" className="navbar__logo">
          <span className="navbar__logo-icon">◎</span>
          <span className="navbar__logo-text">ALGONEXIS</span>
        </Link>

        {/* Desktop Links */}
        <ul className="navbar__links">
          {NAV_LINKS.map((l) => (
            <li key={l.label}>
              <Link
                to={l.to}
                className={`navbar__link ${location.pathname === l.to ? "active" : ""}`}
              >
                {l.label}
              </Link>
            </li>
          ))}
        </ul>

        {/* Actions */}
        <div className="navbar__actions">
          {isAuthenticated ? (
            <>
              <Link to="/dashboard" className="btn btn-ghost navbar__btn">
                Dashboard
              </Link>
              <button
                onClick={handleLogout}
                className="btn btn-outline navbar__btn"
              >
                Logout
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn btn-ghost navbar__btn">
                Login
              </Link>
              <Link to="/register" className="btn btn-primary navbar__btn">
                Get Started
              </Link>
            </>
          )}
        </div>

        {/* Hamburger */}
        <button
          className={`navbar__hamburger ${open ? "open" : ""}`}
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          <span />
          <span />
          <span />
        </button>
      </div>

      {/* Mobile Menu */}
      <div className={`navbar__mobile ${open ? "open" : ""}`}>
        {NAV_LINKS.map((l) => (
          <Link
            key={l.label}
            to={l.to}
            className="navbar__mobile-link"
            onClick={() => setOpen(false)}
          >
            {l.label}
          </Link>
        ))}
        <div className="navbar__mobile-actions">
          {isAuthenticated ? (
            <>
              <Link
                to="/dashboard"
                className="btn btn-ghost"
                onClick={() => setOpen(false)}
              >
                Dashboard
              </Link>
              <button
                onClick={() => {
                  handleLogout();
                  setOpen(false);
                }}
                className="btn btn-outline"
              >
                Logout
              </button>
            </>
          ) : (
            <>
              <Link
                to="/login"
                className="btn btn-ghost"
                onClick={() => setOpen(false)}
              >
                Login
              </Link>
              <Link
                to="/register"
                className="btn btn-primary"
                onClick={() => setOpen(false)}
              >
                Get Started
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
