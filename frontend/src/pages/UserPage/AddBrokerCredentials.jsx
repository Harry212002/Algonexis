import { useState, useEffect, useCallback, useRef, memo } from "react";
import { brokerApi } from "../../utils/api";

// Separate component for better performance
const LoadingSpinner = memo(() => (
  <div className="spinner-container">
    <div className="spinner" />
  </div>
));

const StatusIndicator = memo(({ hasCredentials }) => (
  <div className="status-row">
    <span className="status-label">Status</span>
    <span
      className={`status-value ${hasCredentials ? "connected" : "disconnected"}`}
    >
      <span className={`status-dot ${hasCredentials ? "pulse" : ""}`} />
      {hasCredentials ? "Connected" : "Not Connected"}
    </span>
  </div>
));

const BrokerCard = memo(
  ({
    title,
    subtitle,
    icon,
    description,
    hasCredentials,
    onAction,
    actionText,
    isDisabled = false,
    gradient = "angel",
  }) => (
    <div className="card">
      <div className="card-header">
        <div className={`card-icon ${gradient}`}>{icon}</div>
        <div>
          <h3 className="card-title">{title}</h3>
          <p className="card-subtitle">{subtitle}</p>
        </div>
      </div>

      <p className="card-description">{description}</p>

      <StatusIndicator hasCredentials={hasCredentials} />

      <button
        onClick={onAction}
        className={`card-button ${hasCredentials ? "outline" : "primary"} ${isDisabled ? "disabled" : ""}`}
        disabled={isDisabled}
      >
        {hasCredentials ? "View / Update Credentials" : "+ Add Credentials"}
      </button>
    </div>
  ),
);

export default function AddBrokerCredentials() {
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const [message, setMessage] = useState({ text: "", type: "" });
  const [showModal, setShowModal] = useState(false);
  const [hasCredentials, setHasCredentials] = useState(false);
  const [existingData, setExistingData] = useState(null);

  const [angelForm, setAngelForm] = useState({
    angel_api_key: "",
    angel_client_code: "",
    angel_password: "",
    angel_totp_secret: "",
  });

  const modalRef = useRef(null);
  const formRef = useRef(null);
  const animationFrameRef = useRef(null);

  // Fetch existing credentials on mount
  const fetchAngelCredentials = useCallback(async () => {
    try {
      setFetching(true);
      const response = await brokerApi.getAngelOneCredentials();

      console.log("API Response:", response); // Debug log

      // Check if credentials exist based on API response structure
      if (response && response.success === true && response.data) {
        setHasCredentials(true);
        setExistingData(response.data);
        setAngelForm({
          angel_api_key: response.data.angel_api_key || "",
          angel_client_code: response.data.angel_client_code || "",
          angel_password: "", // Never populate password for security
          angel_totp_secret: response.data.angel_totp_secret || "",
        });
      } else if (response && response.has_credentials === true) {
        // Alternative response structure
        setHasCredentials(true);
        setExistingData(response.data);
        setAngelForm({
          angel_api_key: response.data?.angel_api_key || "",
          angel_client_code: response.data?.angel_client_code || "",
          angel_password: "",
          angel_totp_secret: response.data?.angel_totp_secret || "",
        });
      } else {
        setHasCredentials(false);
        setExistingData(null);
        // Reset form for new credentials
        setAngelForm({
          angel_api_key: "",
          angel_client_code: "",
          angel_password: "",
          angel_totp_secret: "",
        });
      }
    } catch (error) {
      console.error("Error fetching credentials:", error);
      // If error status is 404, no credentials exist
      if (error.status === 404) {
        setHasCredentials(false);
        setExistingData(null);
      } else {
        // For other errors, assume no credentials
        setHasCredentials(false);
        setExistingData(null);
      }
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    fetchAngelCredentials();
  }, [fetchAngelCredentials]);

  const handleAngelChange = useCallback((e) => {
    const { name, value } = e.target;
    setAngelForm((prev) => ({ ...prev, [name]: value }));
  }, []);

  const openAngelModal = useCallback(() => {
    setShowModal(true);
    setMessage({ text: "", type: "" });
    document.body.style.overflow = "hidden";
  }, []);

  const closeModal = useCallback(() => {
    requestAnimationFrame(() => {
      setShowModal(false);
      setMessage({ text: "", type: "" });
      setLoading(false);
      document.body.style.overflow = "";
    });
  }, []);

  // Handle click outside modal
  useEffect(() => {
    if (!showModal) return;

    const handleClickOutside = (e) => {
      if (modalRef.current && !modalRef.current.contains(e.target)) {
        closeModal();
      }
    };

    const handleEscape = (e) => {
      if (e.key === "Escape") closeModal();
    };

    document.addEventListener("mousedown", handleClickOutside, {
      capture: true,
    });
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside, {
        capture: true,
      });
      document.removeEventListener("keydown", handleEscape);
    };
  }, [showModal, closeModal]);

  const handleAngelSubmit = async (e) => {
    e.preventDefault();

    // For update, password is optional (only require if user entered new password)
    if (hasCredentials) {
      // When updating, only require fields that are filled
      if (
        !angelForm.angel_api_key ||
        !angelForm.angel_client_code ||
        !angelForm.angel_totp_secret
      ) {
        setMessage({
          text: "API Key, Client Code, and TOTP Secret are required",
          type: "error",
        });
        return;
      }
    } else {
      // For new credentials, all fields are required including password
      if (
        !angelForm.angel_api_key ||
        !angelForm.angel_client_code ||
        !angelForm.angel_password ||
        !angelForm.angel_totp_secret
      ) {
        setMessage({ text: "All fields are required", type: "error" });
        return;
      }
    }

    try {
      setLoading(true);
      setMessage({ text: "", type: "" });

      // Prepare data for submission
      const submitData = {
        angel_api_key: angelForm.angel_api_key,
        angel_client_code: angelForm.angel_client_code,
        angel_totp_secret: angelForm.angel_totp_secret,
      };

      // Only include password if it's provided (for updates)
      if (angelForm.angel_password) {
        submitData.angel_password = angelForm.angel_password;
      }

      const response = await brokerApi.saveAngelOneCredentials(submitData);

      setMessage({
        text: response.message || "Credentials saved successfully!",
        type: "success",
      });

      // Refresh credentials data
      await fetchAngelCredentials();

      // Clear only the password field
      setAngelForm((prev) => ({ ...prev, angel_password: "" }));

      // Smooth auto-close after success
      setTimeout(() => {
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current);
        }
        animationFrameRef.current = requestAnimationFrame(closeModal);
      }, 1500);
    } catch (error) {
      setMessage({
        text: error.message || "Failed to save Angel One credentials",
        type: "error",
      });
    } finally {
      setLoading(false);
    }
  };

  if (fetching) {
    return <LoadingSpinner />;
  }

  return (
    <div className="container">
      <div className="header">
        <div className="logo">
          <span className="logo-main">ALGONEXIS</span>
          <span className="logo-lite">LITE</span>
        </div>
        <h1 className="title">Broker Account Management</h1>
        <p className="subtitle">
          Connect your broker accounts to AlgoNexis for automated trading
        </p>
      </div>

      <div className="cards-grid">
        <BrokerCard
          title="Angel One"
          subtitle="Smart API Broker"
          icon="🔷"
          description="Connect your Angel One trading account for seamless automated trading with advanced order types and real-time market data."
          hasCredentials={hasCredentials}
          onAction={openAngelModal}
          actionText={
            hasCredentials ? "View / Update Credentials" : "+ Add Credentials"
          }
          gradient="angel"
        />

        <BrokerCard
          title="Zerodha"
          subtitle="India's Largest Broker"
          icon="💠"
          description="Connect your Zerodha Kite account for lightning-fast execution and powerful trading features with our advanced algorithms."
          hasCredentials={false}
          onAction={() => {}}
          actionText="Coming Soon"
          isDisabled={true}
          gradient="zerodha"
        />
      </div>

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay">
          <div className="modal" ref={modalRef}>
            <div className="modal-header">
              <div>
                <h3 className="modal-title">
                  {hasCredentials ? "Update" : "Add"} Angel One Credentials
                </h3>
                <p className="modal-subtitle">
                  {hasCredentials
                    ? "Update your API credentials (leave password blank to keep current)"
                    : "Enter your API credentials to connect"}
                </p>
              </div>
              <button
                onClick={closeModal}
                className="modal-close"
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              <form ref={formRef} onSubmit={handleAngelSubmit}>
                <div className="form-group">
                  <input
                    type="text"
                    name="angel_api_key"
                    placeholder="Angel API Key"
                    value={angelForm.angel_api_key}
                    onChange={handleAngelChange}
                    required
                    className="form-input"
                    autoComplete="off"
                  />
                  <input
                    type="text"
                    name="angel_client_code"
                    placeholder="Angel Client Code"
                    value={angelForm.angel_client_code}
                    onChange={handleAngelChange}
                    required
                    className="form-input"
                    autoComplete="off"
                  />
                  <input
                    type="password"
                    name="angel_password"
                    placeholder={
                      hasCredentials
                        ? "Angel Password (optional - leave blank to keep current)"
                        : "Angel Password"
                    }
                    value={angelForm.angel_password}
                    onChange={handleAngelChange}
                    required={!hasCredentials}
                    className="form-input"
                    autoComplete="new-password"
                  />
                  <input
                    type="text"
                    name="angel_totp_secret"
                    placeholder="Angel TOTP Secret"
                    value={angelForm.angel_totp_secret}
                    onChange={handleAngelChange}
                    required
                    className="form-input"
                    autoComplete="off"
                  />
                </div>

                {message.text && (
                  <div className={`message ${message.type}`}>
                    {message.text}
                  </div>
                )}

                <div className="modal-actions">
                  <button
                    type="button"
                    onClick={closeModal}
                    className="btn-cancel"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={loading}
                    className="btn-submit"
                  >
                    {loading
                      ? "Saving..."
                      : hasCredentials
                        ? "Update Credentials"
                        : "Save Credentials"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        /* Container */
        .container {
          min-height: 100vh;
          padding: 40px;
          background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%);
        }

        /* Header */
        .header {
          text-align: center;
          margin-bottom: 40px;
          animation: fadeInUp 0.4s cubic-bezier(0.2, 0, 0, 1);
        }

        .logo {
          margin-bottom: 20px;
        }

        .logo-main {
          font-size: 28px;
          font-weight: 700;
          background: linear-gradient(135deg, #00ff88, #00b8ff);
          -webkit-background-clip: text;
          background-clip: text;
          color: transparent;
          letter-spacing: 2px;
        }

        .logo-lite {
          font-size: 28px;
          font-weight: 700;
          color: rgba(255, 255, 255, 0.3);
          margin-left: 5px;
        }

        .title {
          font-size: clamp(24px, 5vw, 32px);
          font-weight: 700;
          color: #fff;
          margin-bottom: 12px;
          letter-spacing: -0.02em;
        }

        .subtitle {
          color: #a0aec0;
          font-size: clamp(14px, 4vw, 16px);
        }

        /* Cards Grid */
        .cards-grid {
          display: grid;
          grid-template-columns: repeat(
            auto-fit,
            minmax(min(100%, 380px), 1fr)
          );
          gap: 30px;
          max-width: 1200px;
          margin: 0 auto;
        }

        /* Card Styles */
        .card {
          background: rgba(26, 31, 58, 0.8);
          backdrop-filter: blur(10px);
          border-radius: 24px;
          padding: 28px;
          transition: all 0.2s cubic-bezier(0.2, 0, 0, 1);
          cursor: pointer;
        }

        .card:hover {
          transform: translateY(-4px);
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
        }

        .card-header {
          display: flex;
          align-items: center;
          gap: 16px;
          margin-bottom: 20px;
        }

        .card-icon {
          width: 56px;
          height: 56px;
          border-radius: 16px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 28px;
          flex-shrink: 0;
        }

        .card-icon.angel {
          background: linear-gradient(135deg, #00ff88, #00b8ff);
        }

        .card-icon.zerodha {
          background: linear-gradient(135deg, #00b8ff, #0066ff);
        }

        .card-title {
          font-size: 24px;
          font-weight: 600;
          color: #fff;
          margin: 0;
        }

        .card-subtitle {
          color: #00ff88;
          font-size: 14px;
          margin: 4px 0 0 0;
        }

        .card-description {
          color: #cbd5e0;
          line-height: 1.6;
          margin-bottom: 24px;
        }

        /* Status */
        .status-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
          padding: 12px 0;
          border-top: 1px solid rgba(255, 255, 255, 0.1);
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .status-label {
          color: #a0aec0;
          font-size: 14px;
          font-weight: 500;
        }

        .status-value {
          font-size: 14px;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .status-value.connected {
          color: #00ff88;
        }

        .status-value.disconnected {
          color: #ffaa00;
        }

        .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          display: inline-block;
        }

        .status-value.connected .status-dot {
          background: #00ff88;
        }

        .status-value.disconnected .status-dot {
          background: #ffaa00;
        }

        .status-dot.pulse {
          animation: pulse 2s ease-in-out infinite;
        }

        /* Buttons */
        .card-button {
          width: 100%;
          padding: 14px;
          border: none;
          border-radius: 12px;
          font-size: 16px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s cubic-bezier(0.2, 0, 0, 1);
        }

        .card-button.primary {
          background: linear-gradient(135deg, #00ff88, #00b8ff);
          color: #0a0e27;
        }

        .card-button.outline {
          background: rgba(0, 255, 136, 0.1);
          border: 1px solid rgba(0, 255, 136, 0.3);
          color: #00ff88;
        }

        .card-button.disabled {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          color: #a0aec0;
          cursor: not-allowed;
        }

        .card-button:not(.disabled):hover {
          transform: scale(1.01);
        }

        /* Modal */
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.8);
          backdrop-filter: blur(8px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          animation: fadeIn 0.15s cubic-bezier(0.2, 0, 0, 1);
        }

        .modal {
          background: linear-gradient(135deg, #1a1f3a, #0f1327);
          border-radius: 28px;
          max-width: 500px;
          width: 90%;
          max-height: 85vh;
          overflow: auto;
          border: 1px solid rgba(0, 255, 136, 0.3);
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
          animation: scaleIn 0.2s cubic-bezier(0.2, 0, 0, 1);
        }

        .modal-header {
          padding: 24px 28px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .modal-title {
          font-size: 24px;
          font-weight: 600;
          color: #fff;
          margin: 0;
        }

        .modal-subtitle {
          color: #a0aec0;
          font-size: 14px;
          margin: 4px 0 0 0;
        }

        .modal-close {
          background: rgba(255, 255, 255, 0.1);
          border: none;
          border-radius: 12px;
          width: 36px;
          height: 36px;
          font-size: 20px;
          cursor: pointer;
          color: #fff;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: background 0.15s ease;
          flex-shrink: 0;
        }

        .modal-close:hover {
          background: rgba(255, 255, 255, 0.2);
        }

        .modal-body {
          padding: 28px;
        }

        /* Form */
        .form-group {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .form-input {
          padding: 14px 16px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          color: #fff;
          font-size: 14px;
          outline: none;
          transition: all 0.15s ease;
          width: 100%;
          box-sizing: border-box;
        }

        .form-input:focus {
          border-color: #00ff88;
          box-shadow: 0 0 0 2px rgba(0, 255, 136, 0.1);
        }

        .form-input:hover {
          border-color: rgba(255, 255, 255, 0.2);
        }

        /* Message */
        .message {
          margin-top: 20px;
          padding: 12px;
          border-radius: 10px;
          font-size: 14px;
          text-align: center;
          animation: slideIn 0.2s cubic-bezier(0.2, 0, 0, 1);
        }

        .message.success {
          background: rgba(0, 255, 136, 0.1);
          color: #00ff88;
        }

        .message.error {
          background: rgba(255, 68, 68, 0.1);
          color: #ff4444;
        }

        /* Modal Actions */
        .modal-actions {
          display: flex;
          gap: 12px;
          margin-top: 24px;
        }

        .btn-cancel {
          flex: 1;
          padding: 12px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          color: #fff;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: background 0.15s ease;
        }

        .btn-cancel:hover {
          background: rgba(255, 255, 255, 0.1);
        }

        .btn-submit {
          flex: 1;
          padding: 12px;
          background: linear-gradient(135deg, #00ff88, #00b8ff);
          border: none;
          border-radius: 12px;
          color: #0a0e27;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .btn-submit:hover:not(:disabled) {
          transform: scale(1.01);
        }

        .btn-submit:disabled {
          opacity: 0.7;
          cursor: not-allowed;
        }

        /* Spinner */
        .spinner-container {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%);
        }

        .spinner {
          width: 40px;
          height: 40px;
          border: 3px solid rgba(0, 255, 136, 0.2);
          border-top-color: #00ff88;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        /* Animations */
        @keyframes pulse {
          0%,
          100% {
            opacity: 1;
            transform: scale(1);
          }
          50% {
            opacity: 0.5;
            transform: scale(1.2);
          }
        }

        @keyframes fadeIn {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }

        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes scaleIn {
          from {
            opacity: 0;
            transform: scale(0.95);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }

        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateY(-5px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
          width: 6px;
        }

        ::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.05);
          border-radius: 3px;
        }

        ::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.2);
          border-radius: 3px;
        }

        ::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.3);
        }

        /* Autofill fix */
        input:-webkit-autofill,
        input:-webkit-autofill:focus {
          transition:
            background-color 600000s 0s,
            color 600000s 0s;
        }
      `}</style>
    </div>
  );
}
