import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "../../utils/api";
import "./Auth.css";

export default function Register() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    mobile_number: "",
    email: "",
    password: "",
    confirm_password: "",
  });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const onChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setError("");
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    if (form.password !== form.confirm_password) {
      setError("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      await authApi.register(form);
      setSuccess("Account created! Redirecting to login…");
      setTimeout(() => navigate("/login"), 1800);
    } catch (err) {
      setError(err.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-bg" />
      <div className="auth-card auth-card--wide card animate-fade-up">
        {/* Header */}
        <div className="auth-card__header">
          <Link to="/" className="auth-logo">
            <span className="auth-logo-icon">◎</span>
            <span>AlgoNexis</span>
          </Link>
          <h2 className="auth-card__title">Create Account</h2>
          <p className="auth-card__subtitle">
            Start your funded trading journey today
          </p>
        </div>

        {error && <div className="auth-error">{error}</div>}
        {success && <div className="auth-success">{success}</div>}

        <form className="auth-form" onSubmit={onSubmit}>
          <div className="auth-row">
            <div className="auth-field">
              <label htmlFor="first_name">First Name</label>
              <input
                id="first_name"
                name="first_name"
                type="text"
                className="input-field"
                placeholder="John"
                value={form.first_name}
                onChange={onChange}
                required
              />
            </div>
            <div className="auth-field">
              <label htmlFor="last_name">Last Name</label>
              <input
                id="last_name"
                name="last_name"
                type="text"
                className="input-field"
                placeholder="Doe"
                value={form.last_name}
                onChange={onChange}
                required
              />
            </div>
          </div>

          <div className="auth-field">
            <label htmlFor="email">Email Address</label>
            <input
              id="email"
              name="email"
              type="email"
              className="input-field"
              placeholder="trader@example.com"
              value={form.email}
              onChange={onChange}
              required
            />
          </div>

          <div className="auth-field">
            <label htmlFor="mobile_number">Mobile Number</label>
            <input
              id="mobile_number"
              name="mobile_number"
              type="tel"
              className="input-field"
              placeholder="+91 98765 43210"
              value={form.mobile_number}
              onChange={onChange}
              required
            />
          </div>

          <div className="auth-row">
            <div className="auth-field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                name="password"
                type="password"
                className="input-field"
                placeholder="••••••••"
                value={form.password}
                onChange={onChange}
                required
              />
            </div>
            <div className="auth-field">
              <label htmlFor="confirm_password">Confirm Password</label>
              <input
                id="confirm_password"
                name="confirm_password"
                type="password"
                className="input-field"
                placeholder="••••••••"
                value={form.confirm_password}
                onChange={onChange}
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary auth-submit"
            disabled={loading}
          >
            {loading ? <span className="auth-spinner" /> : "Create Account →"}
          </button>
        </form>

        <p className="auth-card__footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
