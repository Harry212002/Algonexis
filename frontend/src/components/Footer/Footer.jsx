import { Link } from "react-router-dom";
import "./Footer.css";

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer__grid container">
        {/* Brand */}
        <div className="footer__brand">
          <div className="footer__logo">
            <span className="footer__logo-icon">◎</span>
            <span>ALGONEXIS</span>
          </div>
          <p className="footer__tagline">
            Your trusted partner in prop trading. Trade simulated funds, earn
            real profits.
          </p>
          <div className="footer__socials">
            {["𝕏", "in", "tg"].map((s) => (
              <a key={s} href="#" className="footer__social-btn">
                {s}
              </a>
            ))}
          </div>
        </div>

        {/* Links */}
        <div className="footer__col">
          <h4>Platform</h4>
          <Link to="/program">Programs</Link>
          <Link to="/dashboard">Dashboard</Link>
          <Link to="/affiliates">Affiliates</Link>
        </div>

        <div className="footer__col">
          <h4>Company</h4>
          <Link to="/about">About Us</Link>
          <Link to="/contact">Contact</Link>
          <a href="#">Blog</a>
        </div>

        <div className="footer__col">
          <h4>Legal</h4>
          <a href="#">Privacy Policy</a>
          <a href="#">Terms of Service</a>
          <a href="#">Risk Disclosure</a>
        </div>
      </div>

      <div className="footer__bottom container">
        <p>
          © {new Date().getFullYear()} ALGONEXIS Trading. All rights reserved.
        </p>
        <span className="badge badge-cyan">Live Platform</span>
      </div>
    </footer>
  );
}
