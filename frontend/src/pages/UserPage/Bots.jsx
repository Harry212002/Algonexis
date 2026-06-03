// src/pages/UserPage/Bots.jsx
import { useState, useEffect } from "react";
import { useAuth } from "../../context/AuthContext";
import { api, botApi } from "../../utils/api";

export default function Bots() {
  const { user } = useAuth();
  const [sectorConfig, setSectorConfig] = useState(null);
  const [isBotRunning, setIsBotRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [formData, setFormData] = useState({
    broker: "angelone",
    expiry_date: "current_month",
    strike_price: 1,
    entry_time: "09:15",
    exit_time: "15:15",
    trades_per_day: 5,
    fund_allocation: 100000,
    target_percentage: 5,
    stoploss_percentage: 2,
    volume_multiplier: 3,
    limit_multiplier: 1,
    sectors_scan: 3,
    stocks_scan: 3,

    phase1_start_time: "09:15",
    phase1_end_time: "09:20",
    phase2_start_time: "09:20",
    phase2_end_time: "15:15",
  });
  const [toast, setToast] = useState({
    show: false,
    message: "",
    type: "success",
  });

  // Fetch configuration on mount
  useEffect(() => {
    fetchConfig();
  }, []);

  // useEffect(() => {
  //   const interval = setInterval(async () => {
  //     try {
  //       const res = await botApi.getBotStatus();

  //       setIsBotRunning(res.is_bot_running);
  //     } catch (err) {}
  //   }, 5000);

  //   return () => clearInterval(interval);
  // }, []);

  const fetchConfig = async () => {
    try {
      setLoading(true);
      const response = await botApi.getSectorMomentumConfig();
      if (response.success) {
        setSectorConfig(response.data);
        setIsBotRunning(response.data.is_bot_running || false);
        setFormData({
          broker: response.data.broker || "angelone",
          expiry_date: response.data.expiry_date || "current_month",
          strike_price: response.data.strike_price || 1,
          entry_time: response.data.entry_time || "09:15",
          exit_time: response.data.exit_time || "15:15",
          trades_per_day: response.data.trades_per_day || 5,
          fund_allocation: response.data.fund_allocation || 100000,
          target_percentage: response.data.target_percentage || 5,
          stoploss_percentage: response.data.stoploss_percentage || 2,
          volume_multiplier: response.data.volume_multiplier || 3,
          limit_multiplier: response.data.limit_multiplier || 1,
          sectors_scan: response.data.sectors_scan || 3,
          stocks_scan: response.data.stocks_scan || 3,
          phase1_start_time: response.data.phase1_start_time || "09:15",
          phase1_end_time: response.data.phase1_end_time || "09:20",
          phase2_start_time: response.data.phase2_start_time || "09:20",
          phase2_end_time: response.data.phase2_end_time || "15:15",
        });
      }
    } catch (error) {
      // Config not found is fine (user hasn't saved yet)
      if (error.status !== 404) {
        showToast("Failed to load configuration", "error");
      }
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async () => {
    try {
      setSaving(true);
      const response = await botApi.saveSectorMomentumConfig(formData);

      if (response.success) {
        showToast("Configuration saved successfully!", "success");
        setShowConfigModal(false);
        fetchConfig();
      } else {
        showToast(response.message || "Failed to save configuration", "error");
      }
    } catch (error) {
      showToast(error.message || "Failed to save configuration", "error");
    } finally {
      setSaving(false);
    }
  };

  const toggleBotRunning = async () => {
    try {
      setToggling(true);
      const newState = !isBotRunning;
      const response = await botApi.toggleSectorMomentumBot(newState);

      if (response.success) {
        if (response.success) {
          await fetchConfig();
          showToast(response.message, "success");
        }
        showToast(
          newState ? "Bot started successfully!" : "Bot stopped successfully!",
          "success",
        );
      } else {
        showToast(response.message || "Failed to toggle bot state", "error");
      }
    } catch (error) {
      showToast(error.message || "Failed to toggle bot", "error");
    } finally {
      setToggling(false);
    }
  };

  const showToast = (message, type = "success") => {
    setToast({ show: true, message, type });
    setTimeout(() => {
      setToast({ show: false, message: "", type: "success" });
    }, 3000);
  };

  const handleInputChange = (e) => {
    const { name, value, type } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "number" ? (value === "" ? "" : Number(value)) : value,
    }));
  };

  const formatExpiryLabel = (value) => {
    const expiryMap = {
      current_month: "Current Month",
      next_month: "Next Month",
      far_month: "Far Month Expiry",
    };
    return expiryMap[value] || value;
  };

  if (loading) {
    return (
      <div
        style={{
          padding: "32px",
          minHeight: "calc(100vh - 70px)",
          background: "var(--bg-primary)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            height: "300px",
          }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 12px",
              borderRadius: "999px",
              fontSize: "0.75rem",
              fontFamily: "var(--font-mono)",
              fontWeight: "700",
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              background: "rgba(0,212,255,0.12)",
              color: "#00d4ff",
              border: "1px solid rgba(0,212,255,0.3)",
            }}
          >
            Loading bots...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        padding: "32px",
        minHeight: "calc(100vh - 70px)",
        background: "var(--bg-primary)",
        position: "relative",
      }}
    >
      {/* Toast Notification */}
      {toast.show && (
        <div
          style={{
            position: "fixed",
            top: "24px",
            right: "24px",
            zIndex: 9999,
            padding: "12px 24px",
            borderRadius: "10px",
            backgroundColor:
              toast.type === "success"
                ? "rgba(0, 255, 136, 0.15)"
                : "rgba(255, 51, 85, 0.15)",
            borderLeft: `3px solid ${toast.type === "success" ? "#00ff88" : "#ff3355"}`,
            backdropFilter: "blur(10px)",
            animation: "fadeIn 0.3s ease",
            fontFamily: "var(--font-body)",
            color: "var(--text-primary)",
          }}
        >
          {toast.message}
        </div>
      )}

      {/* Page Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "32px",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div>
          <h1
            style={{
              fontSize: "clamp(1.5rem, 3vw, 2rem)",
              fontWeight: "700",
              fontFamily: "var(--font-display)",
              background: "linear-gradient(135deg, #00d4ff 0%, #0066ff 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
              margin: 0,
            }}
          >
            Bot Control Center
          </h1>
          <p
            style={{
              color: "var(--text-secondary)",
              marginTop: "8px",
              fontFamily: "var(--font-body)",
            }}
          >
            Manage and monitor your automated trading strategies
          </p>
        </div>
      </div>

      {/* Sector Momentum Strategy Bot Card */}
      <div
        style={{
          background: "linear-gradient(135deg, #0a1628 0%, #060f1e 100%)",
          border: "1px solid rgba(0, 212, 255, 0.1)",
          borderRadius: "16px",
          padding: "28px",
          boxShadow: "0 4px 24px rgba(0, 0, 0, 0.6)",
          transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
          maxWidth: "900px",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = "rgba(0, 212, 255, 0.4)";
          e.currentTarget.style.boxShadow = "0 0 30px rgba(0, 212, 255, 0.2)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = "rgba(0, 212, 255, 0.1)";
          e.currentTarget.style.boxShadow = "0 4px 24px rgba(0, 0, 0, 0.6)";
        }}
      >
        {/* Header with Strategy Name and Badge */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "16px",
            marginBottom: "24px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                width: "48px",
                height: "48px",
                background: "rgba(0, 212, 255, 0.1)",
                borderRadius: "10px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "24px",
              }}
            >
              ⚡
            </div>
            <div>
              <h3
                style={{
                  fontSize: "1.4rem",
                  marginBottom: "4px",
                  fontFamily: "var(--font-display)",
                  color: "var(--text-primary)",
                }}
              >
                Sector Momentum Breakout
              </h3>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "4px 12px",
                    borderRadius: "999px",
                    fontSize: "0.75rem",
                    fontFamily: "var(--font-mono)",
                    fontWeight: "700",
                    letterSpacing: "0.05em",
                    textTransform: "uppercase",
                    background: "rgba(0,212,255,0.12)",
                    color: "#00d4ff",
                    border: "1px solid rgba(0,212,255,0.3)",
                  }}
                >
                  Momentum
                </span>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "4px 12px",
                    borderRadius: "999px",
                    fontSize: "0.75rem",
                    fontFamily: "var(--font-mono)",
                    fontWeight: "700",
                    letterSpacing: "0.05em",
                    textTransform: "uppercase",
                    background: "rgba(0,102,255,0.12)",
                    color: "#0066ff",
                    border: "1px solid rgba(0,102,255,0.3)",
                  }}
                >
                  Options
                </span>
              </div>
            </div>
          </div>

          {/* On/Off Toggle */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "16px",
              background: "rgba(255,255,255,0.03)",
              padding: "8px 20px",
              borderRadius: "40px",
              border: "1px solid rgba(0, 212, 255, 0.1)",
            }}
          >
            <span
              style={{
                fontSize: "0.85rem",
                fontWeight: "500",
                letterSpacing: "0.05em",
                color: "var(--text-secondary)",
                fontFamily: "var(--font-body)",
              }}
            >
              {isBotRunning ? "ACTIVE" : "INACTIVE"}
            </span>
            <button
              onClick={toggleBotRunning}
              disabled={toggling}
              style={{
                width: "52px",
                height: "28px",
                borderRadius: "28px",
                border: "none",
                cursor: toggling ? "wait" : "pointer",
                background: isBotRunning
                  ? "linear-gradient(135deg, #00ff88 0%, #00aaff 100%)"
                  : "rgba(255,255,255,0.15)",
                position: "relative",
                transition: "all 0.25s ease",
                boxShadow: isBotRunning
                  ? "0 0 10px rgba(0,255,136,0.5)"
                  : "none",
              }}
            >
              <div
                style={{
                  width: "22px",
                  height: "22px",
                  borderRadius: "22px",
                  background: "white",
                  position: "absolute",
                  top: "3px",
                  left: isBotRunning ? "27px" : "3px",
                  transition: "left 0.25s ease",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
                }}
              />
            </button>
            <span
              style={{
                fontSize: "0.7rem",
                fontWeight: "600",
                fontFamily: "var(--font-mono)",
                color: isBotRunning ? "#00ff88" : "var(--text-muted)",
              }}
            >
              {isBotRunning ? "ON" : "OFF"}
            </span>
          </div>
        </div>

        {/* Quick Stats Row */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            gap: "16px",
            marginBottom: "24px",
            padding: "16px 0",
            borderTop: "1px solid rgba(0, 212, 255, 0.1)",
            borderBottom: "1px solid rgba(0, 212, 255, 0.1)",
          }}
        >
          <div>
            <div
              style={{
                fontSize: "0.75rem",
                color: "var(--text-muted)",
                letterSpacing: "0.05em",
                fontFamily: "var(--font-body)",
              }}
            >
              BROKER
            </div>
            <div
              style={{
                fontSize: "1rem",
                fontWeight: "600",
                textTransform: "uppercase",
                fontFamily: "var(--font-body)",
                color: "var(--text-primary)",
              }}
            >
              {sectorConfig?.broker || formData.broker}
            </div>
          </div>
          <div>
            <div
              style={{
                fontSize: "0.75rem",
                color: "var(--text-muted)",
                letterSpacing: "0.05em",
                fontFamily: "var(--font-body)",
              }}
            >
              EXPIRY
            </div>
            <div
              style={{
                fontSize: "1rem",
                fontWeight: "600",
                fontFamily: "var(--font-body)",
                color: "var(--text-primary)",
              }}
            >
              {formatExpiryLabel(
                sectorConfig?.expiry_date || formData.expiry_date,
              )}
            </div>
          </div>
          <div>
            <div
              style={{
                fontSize: "0.75rem",
                color: "var(--text-muted)",
                letterSpacing: "0.05em",
                fontFamily: "var(--font-body)",
              }}
            >
              ENTRY → EXIT
            </div>
            <div
              style={{
                fontSize: "1rem",
                fontWeight: "600",
                fontFamily: "var(--font-body)",
                color: "var(--text-primary)",
              }}
            >
              {sectorConfig?.entry_time || formData.entry_time} →{" "}
              {sectorConfig?.exit_time || formData.exit_time}
            </div>
          </div>
          <div>
            <div
              style={{
                fontSize: "0.75rem",
                color: "var(--text-muted)",
                letterSpacing: "0.05em",
                fontFamily: "var(--font-body)",
              }}
            >
              FUNDS
            </div>
            <div
              style={{
                fontSize: "1rem",
                fontWeight: "600",
                fontFamily: "var(--font-body)",
                color: "var(--text-primary)",
              }}
            >
              ₹
              {(
                sectorConfig?.fund_allocation || formData.fund_allocation
              ).toLocaleString()}
            </div>
          </div>
        </div>

        {/* Parameters Preview */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "16px",
            marginBottom: "24px",
          }}
        >
          <div
            style={{
              background: "rgba(0,212,255,0.05)",
              padding: "8px 14px",
              borderRadius: "6px",
            }}
          >
            <span
              style={{
                fontSize: "0.7rem",
                color: "var(--text-muted)",
                fontFamily: "var(--font-body)",
              }}
            >
              Target
            </span>
            <span
              style={{
                marginLeft: "8px",
                color: "#00ff88",
                fontWeight: "600",
                fontFamily: "var(--font-body)",
              }}
            >
              {sectorConfig?.target_percentage || formData.target_percentage}%
            </span>
          </div>
          <div
            style={{
              background: "rgba(0,212,255,0.05)",
              padding: "8px 14px",
              borderRadius: "6px",
            }}
          >
            <span
              style={{
                fontSize: "0.7rem",
                color: "var(--text-muted)",
                fontFamily: "var(--font-body)",
              }}
            >
              Stop Loss
            </span>
            <span
              style={{
                marginLeft: "8px",
                color: "#ff3355",
                fontWeight: "600",
                fontFamily: "var(--font-body)",
              }}
            >
              {sectorConfig?.stoploss_percentage ||
                formData.stoploss_percentage}
              %
            </span>
          </div>
          <div
            style={{
              background: "rgba(0,212,255,0.05)",
              padding: "8px 14px",
              borderRadius: "6px",
            }}
          >
            <span
              style={{
                fontSize: "0.7rem",
                color: "var(--text-muted)",
                fontFamily: "var(--font-body)",
              }}
            >
              Sectors/Stocks
            </span>
            <span
              style={{
                marginLeft: "8px",
                fontWeight: "600",
                fontFamily: "var(--font-body)",
                color: "var(--text-primary)",
              }}
            >
              {sectorConfig?.sectors_scan || formData.sectors_scan} /{" "}
              {sectorConfig?.stocks_scan || formData.stocks_scan}
            </span>
          </div>
          <div
            style={{
              background: "rgba(0,212,255,0.05)",
              padding: "8px 14px",
              borderRadius: "6px",
            }}
          >
            <span
              style={{
                fontSize: "0.7rem",
                color: "var(--text-muted)",
                fontFamily: "var(--font-body)",
              }}
            >
              Trades/Day
            </span>
            <span
              style={{
                marginLeft: "8px",
                fontWeight: "600",
                fontFamily: "var(--font-body)",
                color: "var(--text-primary)",
              }}
            >
              {sectorConfig?.trades_per_day || formData.trades_per_day}
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div
          style={{ display: "flex", gap: "16px", justifyContent: "flex-end" }}
        >
          <button
            onClick={() => setShowConfigModal(true)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 24px",
              borderRadius: "24px",
              fontFamily: "var(--font-display)",
              fontSize: "0.75rem",
              fontWeight: "600",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              cursor: "pointer",
              transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
              background: "transparent",
              color: "var(--text-primary)",
              border: "1px solid rgba(0, 212, 255, 0.4)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(0, 212, 255, 0.08)";
              e.currentTarget.style.borderColor = "#00d4ff";
              e.currentTarget.style.boxShadow =
                "0 0 30px rgba(0, 212, 255, 0.2)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.borderColor = "rgba(0, 212, 255, 0.4)";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            ⚙️ CONFIGURE
          </button>
          <button
            onClick={toggleBotRunning}
            disabled={toggling}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 28px",
              borderRadius: "24px",
              fontFamily: "var(--font-display)",
              fontSize: "0.75rem",
              fontWeight: "600",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              cursor: toggling ? "wait" : "pointer",
              border: "none",
              transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
              background: isBotRunning
                ? "linear-gradient(135deg, #ff3355 0%, #cc1144 100%)"
                : "linear-gradient(135deg, #00d4ff 0%, #0066ff 100%)",
              color: "#000",
              boxShadow: isBotRunning
                ? "0 0 15px rgba(255,51,85,0.3)"
                : "0 0 20px rgba(0,212,255,0.3)",
            }}
            onMouseEnter={(e) => {
              if (!toggling) {
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.boxShadow = isBotRunning
                  ? "0 0 35px rgba(255,51,85,0.5)"
                  : "0 0 35px rgba(0,212,255,0.5)";
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = isBotRunning
                ? "0 0 15px rgba(255,51,85,0.3)"
                : "0 0 20px rgba(0,212,255,0.3)";
            }}
          >
            {toggling ? "..." : isBotRunning ? "⏹️ STOP BOT" : "▶️ START BOT"}
          </button>
        </div>
      </div>

      {/* Configuration Modal */}
      {showConfigModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.85)",
            backdropFilter: "blur(8px)",
            zIndex: 10000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
          onClick={() => !saving && setShowConfigModal(false)}
        >
          <div
            style={{
              background: "var(--bg-card)",
              border: "1px solid rgba(0, 212, 255, 0.4)",
              borderRadius: "16px",
              maxWidth: "700px",
              width: "100%",
              maxHeight: "85vh",
              overflowY: "auto",
              boxShadow: "0 0 60px rgba(0, 212, 255, 0.35)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: "20px 24px",
                borderBottom: "1px solid rgba(0, 212, 255, 0.1)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <h3
                style={{
                  fontSize: "1.3rem",
                  fontFamily: "var(--font-display)",
                  color: "var(--text-primary)",
                  margin: 0,
                }}
              >
                Sector Momentum Configuration
              </h3>
              <button
                onClick={() => !saving && setShowConfigModal(false)}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--text-secondary)",
                  fontSize: "24px",
                  cursor: "pointer",
                  padding: "4px 8px",
                  fontFamily: "var(--font-body)",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "#00d4ff")}
                onMouseLeave={(e) =>
                  (e.currentTarget.style.color = "var(--text-secondary)")
                }
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: "24px" }}>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "16px",
                }}
              >
                {/* Broker */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    BROKER
                  </label>
                  <select
                    name="broker"
                    value={formData.broker}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "#00d4ff";
                      e.target.style.background = "rgba(0, 212, 255, 0.05)";
                      e.target.style.boxShadow =
                        "0 0 0 3px rgba(0,212,255,0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "rgba(0, 212, 255, 0.1)";
                      e.target.style.background = "rgba(255,255,255,0.04)";
                      e.target.style.boxShadow = "none";
                    }}
                  >
                    <option value="angelone">Angel One</option>
                    <option value="zerodha">Zerodha</option>
                    <option value="upstox">Upstox</option>
                  </select>
                </div>

                {/* Expiry Date */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    EXPIRY DATE
                  </label>
                  <select
                    name="expiry_date"
                    value={formData.expiry_date}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "#00d4ff";
                      e.target.style.background = "rgba(0, 212, 255, 0.05)";
                      e.target.style.boxShadow =
                        "0 0 0 3px rgba(0,212,255,0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "rgba(0, 212, 255, 0.1)";
                      e.target.style.background = "rgba(255,255,255,0.04)";
                      e.target.style.boxShadow = "none";
                    }}
                  >
                    <option value="current_month">Current Month</option>
                    <option value="next_month">Next Month</option>
                    <option value="far_month">Far Month Expiry</option>
                  </select>
                </div>

                {/* Strike Price */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    STRIKE PRICE (Lot multiplier)
                  </label>
                  <input
                    type="number"
                    name="strike_price"
                    value={formData.strike_price}
                    onChange={handleInputChange}
                    className="input-field"
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "#00d4ff";
                      e.target.style.background = "rgba(0, 212, 255, 0.05)";
                      e.target.style.boxShadow =
                        "0 0 0 3px rgba(0,212,255,0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "rgba(0, 212, 255, 0.1)";
                      e.target.style.background = "rgba(255,255,255,0.04)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                </div>

                {/* Entry Time */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    ENTRY TIME
                  </label>
                  <input
                    type="time"
                    name="entry_time"
                    value={formData.entry_time}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "#00d4ff";
                      e.target.style.background = "rgba(0, 212, 255, 0.05)";
                      e.target.style.boxShadow =
                        "0 0 0 3px rgba(0,212,255,0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "rgba(0, 212, 255, 0.1)";
                      e.target.style.background = "rgba(255,255,255,0.04)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                </div>

                {/* Exit Time */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    EXIT TIME
                  </label>
                  <input
                    type="time"
                    name="exit_time"
                    value={formData.exit_time}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "#00d4ff";
                      e.target.style.background = "rgba(0, 212, 255, 0.05)";
                      e.target.style.boxShadow =
                        "0 0 0 3px rgba(0,212,255,0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "rgba(0, 212, 255, 0.1)";
                      e.target.style.background = "rgba(255,255,255,0.04)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                </div>

                {/* Trades Per Day */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    TRADES PER DAY
                  </label>
                  <input
                    type="number"
                    name="trades_per_day"
                    value={formData.trades_per_day}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "#00d4ff";
                      e.target.style.background = "rgba(0, 212, 255, 0.05)";
                      e.target.style.boxShadow =
                        "0 0 0 3px rgba(0,212,255,0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "rgba(0, 212, 255, 0.1)";
                      e.target.style.background = "rgba(255,255,255,0.04)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                </div>

                {/* Fund Allocation */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    FUND ALLOCATION (₹)
                  </label>
                  <input
                    type="number"
                    name="fund_allocation"
                    value={formData.fund_allocation}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "#00d4ff";
                      e.target.style.background = "rgba(0, 212, 255, 0.05)";
                      e.target.style.boxShadow =
                        "0 0 0 3px rgba(0,212,255,0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "rgba(0, 212, 255, 0.1)";
                      e.target.style.background = "rgba(255,255,255,0.04)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                </div>

                {/* Target Percentage */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    TARGET (%)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    name="target_percentage"
                    value={formData.target_percentage}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "#00d4ff";
                      e.target.style.background = "rgba(0, 212, 255, 0.05)";
                      e.target.style.boxShadow =
                        "0 0 0 3px rgba(0,212,255,0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "rgba(0, 212, 255, 0.1)";
                      e.target.style.background = "rgba(255,255,255,0.04)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                </div>

                {/* Stop Loss Percentage */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    STOP LOSS (%)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    name="stoploss_percentage"
                    value={formData.stoploss_percentage}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "#00d4ff";
                      e.target.style.background = "rgba(0, 212, 255, 0.05)";
                      e.target.style.boxShadow =
                        "0 0 0 3px rgba(0,212,255,0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "rgba(0, 212, 255, 0.1)";
                      e.target.style.background = "rgba(255,255,255,0.04)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                </div>

                {/* Volume Multiplier */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    VOLUME MULTIPLIER
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    name="volume_multiplier"
                    value={formData.volume_multiplier}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "#00d4ff";
                      e.target.style.background = "rgba(0, 212, 255, 0.05)";
                      e.target.style.boxShadow =
                        "0 0 0 3px rgba(0,212,255,0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "rgba(0, 212, 255, 0.1)";
                      e.target.style.background = "rgba(255,255,255,0.04)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                </div>

                {/* Limit Multiplier */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    LIMIT MULTIPLIER
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    name="limit_multiplier"
                    value={formData.limit_multiplier}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "#00d4ff";
                      e.target.style.background = "rgba(0, 212, 255, 0.05)";
                      e.target.style.boxShadow =
                        "0 0 0 3px rgba(0,212,255,0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "rgba(0, 212, 255, 0.1)";
                      e.target.style.background = "rgba(255,255,255,0.04)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                </div>

                {/* Sectors Scan */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    SECTORS TO SCAN
                  </label>
                  <input
                    type="number"
                    name="sectors_scan"
                    value={formData.sectors_scan}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "#00d4ff";
                      e.target.style.background = "rgba(0, 212, 255, 0.05)";
                      e.target.style.boxShadow =
                        "0 0 0 3px rgba(0,212,255,0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "rgba(0, 212, 255, 0.1)";
                      e.target.style.background = "rgba(255,255,255,0.04)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                </div>

                {/* Stocks Scan */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    STOCKS PER SECTOR
                  </label>
                  <input
                    type="number"
                    name="stocks_scan"
                    value={formData.stocks_scan}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "#00d4ff";
                      e.target.style.background = "rgba(0, 212, 255, 0.05)";
                      e.target.style.boxShadow =
                        "0 0 0 3px rgba(0,212,255,0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "rgba(0, 212, 255, 0.1)";
                      e.target.style.background = "rgba(255,255,255,0.04)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                </div>

                {/* Phase 1 Start Time */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    PHASE 1 START TIME
                  </label>
                  <input
                    type="time"
                    name="phase1_start_time"
                    value={formData.phase1_start_time}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                  />
                </div>

                {/* Phase 1 End Time */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    PHASE 1 END TIME
                  </label>
                  <input
                    type="time"
                    name="phase1_end_time"
                    value={formData.phase1_end_time}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                  />
                </div>

                {/* Phase 2 Start Time */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    PHASE 2 START TIME
                  </label>
                  <input
                    type="time"
                    name="phase2_start_time"
                    value={formData.phase2_start_time}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                  />
                </div>

                {/* Phase 2 End Time */}
                <div>
                  <label
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      display: "block",
                      marginBottom: "6px",
                      fontFamily: "var(--font-body)",
                      letterSpacing: "0.05em",
                    }}
                  >
                    PHASE 2 END TIME
                  </label>
                  <input
                    type="time"
                    name="phase2_end_time"
                    value={formData.phase2_end_time}
                    onChange={handleInputChange}
                    style={{
                      width: "100%",
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(0, 212, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      color: "var(--text-primary)",
                      fontFamily: "var(--font-body)",
                      fontSize: "1rem",
                      transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                      outline: "none",
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div
              style={{
                padding: "16px 24px",
                borderTop: "1px solid rgba(0, 212, 255, 0.1)",
                display: "flex",
                justifyContent: "flex-end",
                gap: "12px",
              }}
            >
              <button
                onClick={() => setShowConfigModal(false)}
                disabled={saving}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "10px 24px",
                  borderRadius: "24px",
                  fontFamily: "var(--font-display)",
                  fontSize: "0.75rem",
                  fontWeight: "600",
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  cursor: saving ? "default" : "pointer",
                  transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                  background: "rgba(255,255,255,0.04)",
                  color: "var(--text-secondary)",
                  border: "1px solid rgba(0, 212, 255, 0.1)",
                }}
                onMouseEnter={(e) => {
                  if (!saving) {
                    e.currentTarget.style.color = "var(--text-primary)";
                    e.currentTarget.style.background = "rgba(255,255,255,0.08)";
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "var(--text-secondary)";
                  e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                }}
              >
                Cancel
              </button>
              <button
                onClick={saveConfig}
                disabled={saving}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "10px 28px",
                  borderRadius: "24px",
                  fontFamily: "var(--font-display)",
                  fontSize: "0.75rem",
                  fontWeight: "600",
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  cursor: saving ? "wait" : "pointer",
                  border: "none",
                  transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                  background:
                    "linear-gradient(135deg, #00d4ff 0%, #0066ff 100%)",
                  color: "#000",
                  boxShadow: "0 0 20px rgba(0,212,255,0.3)",
                }}
                onMouseEnter={(e) => {
                  if (!saving) {
                    e.currentTarget.style.transform = "translateY(-2px)";
                    e.currentTarget.style.boxShadow =
                      "0 0 35px rgba(0,212,255,0.5)";
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "translateY(0)";
                  e.currentTarget.style.boxShadow =
                    "0 0 20px rgba(0,212,255,0.3)";
                }}
              >
                {saving ? "Saving..." : "Save Configuration"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add keyframe animation style for toast */}
      <style>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateX(20px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
      `}</style>
    </div>
  );
}
