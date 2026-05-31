import { Link } from "react-router-dom";
import "./Home.css";

/* ── Data ── */
const STATS = [
  { label: "Active Traders", value: "12,400+" },
  { label: "Total Payouts", value: "$4.2M" },
  { label: "Max Funding", value: "$200K" },
  { label: "Payout Rate", value: "1-Day" },
];

const PROGRAMS = [
  {
    name: "Starter",
    price: "$49",
    capital: "$10,000",
    highlighted: false,
    features: [
      "5% Profit Target",
      "4% Max Drawdown",
      "Unlimited Days",
      "80% Profit Split",
    ],
    perks: [
      "Beginner Friendly",
      "Basic Strategies",
      "Single Broker Connection",
      "Daily Watchlist",
      "Market Scanner Access",
    ],
  },
  {
    name: "Pro",
    price: "$199",
    capital: "$50,000",
    highlighted: true,
    features: [
      "8% Profit Target",
      "5% Max Drawdown",
      "Unlimited Days",
      "85% Profit Split",
    ],
    perks: [
      "Advanced Strategies",
      "Multiple Broker Connections",
      "AI Recommendations",
      "Portfolio Analytics",
      "Real-Time Alerts",
    ],
  },
  {
    name: "Elite",
    price: "$399",
    capital: "$100,000",
    highlighted: false,
    features: [
      "10% Profit Target",
      "6% Max Drawdown",
      "Unlimited Days",
      "90% Profit Split",
    ],
    perks: [
      "All Premium Features",
      "Unlimited Brokers",
      "Priority Support",
      "Advanced Risk Management",
      "Early Feature Access",
      "Custom Strategy Alerts",
    ],
  },
];

const WHY_CHOOSE = [
  {
    icon: "⬡",
    title: "Multi-Broker Support",
    desc: "Connect with Angel One, Zerodha, Upstox, Dhan, Fyers and more leading brokers.",
  },
  {
    icon: "◈",
    title: "Advanced Trading Strategies",
    desc: "Professionally designed strategies for Intraday, Swing, Momentum, Breakout, and Sector Analysis.",
  },
  {
    icon: "◉",
    title: "AI-Powered Recommendations",
    desc: "Intelligent stock picks using technical indicators, market trends, volume analysis, and sector strength.",
  },
  {
    icon: "◫",
    title: "Real-Time Alerts",
    desc: "Never miss an opportunity with instant buy/sell alerts and strategy notifications.",
  },
  {
    icon: "◬",
    title: "Secure & Reliable",
    desc: "Industry-standard encryption keeps your broker credentials safe at all times.",
  },
];

const FEATURES = [
  {
    icon: "📈",
    title: "Live Market Analysis",
    desc: "Monitor market trends, sector performance, and stock movements in real-time.",
  },
  {
    icon: "🤖",
    title: "AI Recommendation Engine",
    desc: "High-probability trading opportunities generated through advanced analytics.",
  },
  {
    icon: "🔔",
    title: "Smart Notifications",
    desc: "Alerts through dashboard, email, and mobile notifications — never miss a move.",
  },
  {
    icon: "📊",
    title: "Portfolio Tracking",
    desc: "Track profits, losses, win rates, and overall trading performance at a glance.",
  },
  {
    icon: "⚡",
    title: "Fast Execution",
    desc: "Connect directly with supported brokers for seamless, low-latency trading.",
  },
  {
    icon: "📚",
    title: "Strategy Marketplace",
    desc: "Access multiple ready-to-use trading strategies from a single dashboard.",
  },
];

const STRATEGIES = [
  {
    name: "Sector Momentum",
    desc: "Identify sectors showing strong momentum and discover potential breakout stocks.",
  },
  {
    name: "Volume Breakout",
    desc: "Detect stocks experiencing unusual volume activity before major price movements.",
  },
  {
    name: "Trend Following",
    desc: "Capture long-term trends using technical indicators and price action.",
  },
  {
    name: "Pattern Detection",
    desc: "Automatically detect Triangle, Flag, Pennant, Double Top, Double Bottom, and more.",
  },
  {
    name: "Swing Trading",
    desc: "Find medium-term opportunities with favorable risk-to-reward setups.",
  },
  {
    name: "Scalping",
    desc: "Generate quick intraday opportunities for active traders.",
  },
];

const BROKERS = [
  "Angel One",
  "Zerodha",
  "Upstox",
  "Dhan",
  "Fyers",
  "Groww",
  "Alice Blue",
  "Shoonya",
  "Kotak Securities",
  "ICICI Direct",
];

const HOW_IT_WORKS = [
  {
    step: "01",
    title: "Create Account",
    desc: "Sign up for your AlgoNexis account in minutes.",
  },
  {
    step: "02",
    title: "Choose a Plan",
    desc: "Select the subscription plan that fits your goals.",
  },
  {
    step: "03",
    title: "Connect Your Broker",
    desc: "Securely link your existing broker account.",
  },
  {
    step: "04",
    title: "Unlock Strategies",
    desc: "Access premium strategies and scanners instantly.",
  },
  {
    step: "05",
    title: "Get Recommendations",
    desc: "Receive AI-powered alerts and trade signals.",
  },
  {
    step: "06",
    title: "Execute & Grow",
    desc: "Execute trades directly through your broker.",
  },
];

const PERF_METRICS = [
  { value: "50,000+", label: "Trade Signals Generated" },
  { value: "20+", label: "Active Trading Strategies" },
  { value: "10+", label: "Broker Integrations" },
  { value: "95%", label: "Platform Uptime" },
  { value: "1M+", label: "Market Data Points / Day" },
  { value: "15,000+", label: "Active Traders" },
];

const FAQS = [
  {
    q: "Can I connect my existing broker account?",
    a: "Yes, AlgoNexis supports multiple popular Indian brokers including Zerodha, Angel One, Upstox, and more.",
  },
  {
    q: "Do I need trading experience?",
    a: "No. Beginners can start with Starter plans and learn using guided strategies with built-in risk management.",
  },
  {
    q: "Are recommendations generated automatically?",
    a: "Yes. Our analytics engine continuously scans the market and generates high-probability opportunities.",
  },
  {
    q: "Can I use multiple brokers?",
    a: "Yes. Pro and Elite plans support multiple broker integrations simultaneously.",
  },
  {
    q: "Can I cancel my subscription anytime?",
    a: "Yes. You can manage or cancel your subscription directly from your account dashboard.",
  },
];

/* ── Component ── */
export default function Home() {
  return (
    <div className="home">
      {/* ═══ HERO ═══ */}
      <section className="hero">
        <div className="hero__bg" />
        <div className="hero__globe" />
        {/* <div className="hero__ticker">
          <div className="hero__ticker-track">
            {[
              "NIFTY +0.84%",
              "SENSEX +0.76%",
              "BANKNIFTY +1.2%",
              "RELIANCE +2.1%",
              "TCS -0.3%",
              "INFY +1.4%",
              "HDFC +0.9%",
              "WIPRO -0.5%",
              "ICICI +1.8%",
              "AAPL +0.6%",
              "TSLA +3.2%",
              "GOLD -0.2%",
            ].map((t, i) => (
              <span
                key={i}
                className={`hero__tick ${t.includes("-") ? "down" : "up"}`}
              >
                {t}
              </span>
            ))}
            {[
              "NIFTY +0.84%",
              "SENSEX +0.76%",
              "BANKNIFTY +1.2%",
              "RELIANCE +2.1%",
              "TCS -0.3%",
              "INFY +1.4%",
              "HDFC +0.9%",
              "WIPRO -0.5%",
              "ICICI +1.8%",
            ].map((t, i) => (
              <span
                key={"b" + i}
                className={`hero__tick ${t.includes("-") ? "down" : "up"}`}
              >
                {t}
              </span>
            ))}
          </div>
        </div> */}
        <div className="hero__content container">
          <div
            className="badge badge-cyan hero__badge animate-fade-up"
            style={{ animationDelay: "0.1s" }}
          >
            <span className="hero__badge-dot" /> MTS AVAILABLE
          </div>
          <h1
            className="hero__title animate-fade-up"
            style={{ animationDelay: "0.2s" }}
          >
            Your Trusted Partner
            <br />
            <span className="glow-text">in Prop Trading</span>
          </h1>
          <p
            className="hero__subtitle animate-fade-up"
            style={{ animationDelay: "0.35s" }}
          >
            Trade simulated funds and earn real profits fast. Enjoy one-day
            payouts backed by our 5-Star Customer Promise.
          </p>
          <div
            className="hero__actions animate-fade-up"
            style={{ animationDelay: "0.5s" }}
          >
            <Link to="/program" className="btn btn-outline">
              View Program Now
            </Link>
            <Link to="/register" className="btn btn-primary">
              Get Funded
            </Link>
          </div>
        </div>
      </section>

      {/* ═══ STATS ═══ */}
      <section className="stats container">
        {STATS.map((s) => (
          <div key={s.label} className="stats__card card">
            <span className="stats__value">{s.value}</span>
            <span className="stats__label">{s.label}</span>
          </div>
        ))}
      </section>

      {/* ═══ WHY CHOOSE ═══ */}
      <section className="why section-pad">
        <div className="container">
          <div className="section-header">
            <div className="badge badge-cyan">Why AlgoNexis</div>
            <h2>
              Why Traders <span className="glow-text">Choose Us</span>
            </h2>
            <p>
              Everything you need to trade smarter, backed by robust technology
              and deep market intelligence.
            </p>
          </div>
          <div className="why__grid">
            {WHY_CHOOSE.map((w) => (
              <div key={w.title} className="why__card card">
                <div className="why__icon">{w.icon}</div>
                <h4>{w.title}</h4>
                <p>{w.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ PROGRAMS ═══ */}
      <section className="programs section-pad">
        <div className="container">
          <div className="section-header">
            <div className="badge badge-cyan">Our Programs</div>
            <h2>
              Choose Your <span className="glow-text">Challenge</span>
            </h2>
            <p>
              Start trading with simulated capital and graduate to a funded
              account.
            </p>
          </div>
          <div className="programs__grid">
            {PROGRAMS.map((p) => (
              <div
                key={p.name}
                className={`programs__card card ${p.highlighted ? "highlighted" : ""}`}
              >
                {p.highlighted && (
                  <div className="programs__popular">Most Popular</div>
                )}
                <div className="programs__name">{p.name}</div>
                <div className="programs__capital">{p.capital}</div>
                <div className="programs__price">
                  {p.price}
                  <span>/challenge</span>
                </div>
                <hr className="divider" />
                <ul className="programs__features">
                  {p.features.map((f) => (
                    <li key={f}>
                      <span className="programs__check">✓</span>
                      {f}
                    </li>
                  ))}
                </ul>
                <hr className="divider" />
                <ul className="programs__perks">
                  {p.perks.map((k) => (
                    <li key={k}>
                      <span className="programs__perk-dot">◆</span>
                      {k}
                    </li>
                  ))}
                </ul>
                <Link
                  to="/register"
                  className={`btn ${p.highlighted ? "btn-primary" : "btn-outline"} programs__cta`}
                >
                  Start Challenge
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FEATURES ═══ */}
      <section className="features section-pad">
        <div className="container">
          <div className="section-header">
            <div className="badge badge-cyan">Platform Features</div>
            <h2>
              Everything You Need To{" "}
              <span className="glow-text">Trade Smarter</span>
            </h2>
            <p>
              A complete suite of tools designed for serious traders at every
              level.
            </p>
          </div>
          <div className="features__grid">
            {FEATURES.map((f) => (
              <div key={f.title} className="features__card card">
                <span className="features__icon">{f.icon}</span>
                <h4>{f.title}</h4>
                <p>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ STRATEGIES ═══ */}
      <section className="strategies section-pad">
        <div className="container">
          <div className="section-header">
            <div className="badge badge-cyan">Strategy Marketplace</div>
            <h2>
              Available <span className="glow-text">Trading Strategies</span>
            </h2>
            <p>
              Battle-tested strategies for every market condition and trading
              style.
            </p>
          </div>
          <div className="strategies__grid">
            {STRATEGIES.map((s, i) => (
              <div key={s.name} className="strategies__card card">
                <div className="strategies__num">0{i + 1}</div>
                <h4>{s.name} Strategy</h4>
                <p>{s.desc}</p>
                <div className="strategies__tag">Active</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ BROKERS ═══ */}
      <section className="brokers section-pad">
        <div className="container">
          <div className="section-header">
            <div className="badge badge-cyan">Integrations</div>
            <h2>
              Trade Through Your{" "}
              <span className="glow-text">Preferred Broker</span>
            </h2>
            <p>
              Seamlessly connect your existing broker account — no switching
              required.
            </p>
          </div>
          <div className="brokers__grid">
            {BROKERS.map((b) => (
              <div key={b} className="brokers__chip card">
                {b}
              </div>
            ))}
            <div className="brokers__chip brokers__chip--more card">
              + More coming soon
            </div>
          </div>
        </div>
      </section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section className="how section-pad">
        <div className="container">
          <div className="section-header">
            <div className="badge badge-cyan">Process</div>
            <h2>
              How <span className="glow-text">AlgoNexis</span> Works
            </h2>
            <p>Get up and trading in six simple steps.</p>
          </div>
          <div className="how__steps">
            {HOW_IT_WORKS.map((s, i) => (
              <div key={s.step} className="how__step">
                <div className="how__step-num">{s.step}</div>
                <div className="how__step-line" />
                <div className="how__step-body">
                  <h4>{s.title}</h4>
                  <p>{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ PERFORMANCE METRICS ═══ */}
      <section className="perf section-pad">
        <div className="perf__bg" />
        <div className="container">
          <div className="section-header">
            <div className="badge badge-cyan">Performance</div>
            <h2>
              Numbers That <span className="glow-text">Speak</span>
            </h2>
          </div>
          <div className="perf__grid">
            {PERF_METRICS.map((m) => (
              <div key={m.label} className="perf__card">
                <span className="perf__value">{m.value}</span>
                <span className="perf__label">{m.label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FAQ ═══ */}
      <section className="faq section-pad">
        <div className="container faq__inner">
          <div className="section-header faq__header">
            <div className="badge badge-cyan">FAQ</div>
            <h2>
              Common <span className="glow-text">Questions</span>
            </h2>
          </div>
          <div className="faq__list">
            {FAQS.map((f, i) => (
              <details key={i} className="faq__item card">
                <summary className="faq__q">
                  {f.q}
                  <span className="faq__arrow">›</span>
                </summary>
                <p className="faq__a">{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FINAL CTA ═══ */}
      <section className="final-cta">
        <div className="final-cta__glow" />
        <div className="container final-cta__inner">
          <div className="badge badge-cyan" style={{ margin: "0 auto 20px" }}>
            Get Started Today
          </div>
          <h2>
            Ready To Transform
            <br />
            <span className="glow-text">Your Trading?</span>
          </h2>
          <p>
            Join thousands of traders using AlgoNexis to discover opportunities,
            automate market analysis, and make smarter decisions.
          </p>
          <ul className="final-cta__perks">
            {[
              "Connect Your Broker",
              "Access Premium Strategies",
              "Receive AI Recommendations",
              "Track Performance In Real-Time",
            ].map((p) => (
              <li key={p}>
                <span className="programs__check">✓</span>
                {p}
              </li>
            ))}
          </ul>
          <Link to="/register" className="btn btn-primary final-cta__btn">
            Start Free Registration →
          </Link>
        </div>
      </section>
    </div>
  );
}
