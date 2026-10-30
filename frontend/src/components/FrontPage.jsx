import React from 'react';
import '../styles/front-page.css';

/**
 * FrontPage: Minimalist Editorial Landing Page matching the user's reference design
 * Summarizes what ClauseWise does in a short, sweet, and elegant presentation.
 */
export default function FrontPage({ onLaunchCockpit }) {
  const scrollToSection = (id) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="fp-container">
      {/* 1. TOP ANNOUNCEMENT BAR */}
      <div className="fp-top-bar">
        <div className="fp-top-announcement">
          <span>✨</span>
          <span>Fine-Tuned Legal-BERT & SBERT • CUAD Verified Contract Intelligence</span>
        </div>

        <div className="fp-top-status">
          <span className="fp-status-dot" />
          <span>100% On-Device & Private • Zero Cloud LLM Leakage</span>
        </div>

        <a href="mailto:contact@clausewise.ai" className="fp-top-contact">
          support@clausewise.ai
        </a>
      </div>

      {/* 2. MAIN NAVIGATION */}
      <nav className="fp-nav">
        <div className="fp-logo" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
          <div className="fp-logo-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div className="fp-logo-text">
            ClauseWise <span>AI</span>
          </div>
        </div>

        <div className="fp-nav-links">
          <span className="fp-nav-link" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            Overview
          </span>
          <span className="fp-nav-link" onClick={() => scrollToSection('what-we-do')}>
            What We Do
          </span>
          <span className="fp-nav-link" onClick={() => scrollToSection('capabilities')}>
            Capabilities
          </span>
          <span className="fp-nav-link" onClick={() => scrollToSection('how-it-works')}>
            How It Works
          </span>
        </div>

        <div className="fp-nav-actions">
          <button className="fp-btn-warm" onClick={onLaunchCockpit}>
            Launch 3D Cockpit
          </button>
        </div>
      </nav>

      {/* 3. HERO SECTION */}
      <section className="fp-hero">
        <div className="fp-hero-glow" />

        <div className="fp-hero-content">
          <div className="fp-hero-kicker">
            <span>+</span> ADVANCED LEGAL RISK INTELLIGENCE & 3D CONTRACT AUDITOR
          </div>

          <h1 className="fp-hero-title">
            <span>Audited with</span>
            <span>Precision.</span>
            <span>Signed with Confidence.</span>
          </h1>

          <p className="fp-hero-description">
            ClauseWise instantly spots hidden liabilities, non-competes, and predatory terms
            across PDF, DOCX, and TXT agreements. Inspected directly on an interactive 3D digital
            paper canvas with plain-English breakdowns and balanced AI redlines.
          </p>

          <div className="fp-hero-cta-group">
            <button className="fp-btn-warm" onClick={onLaunchCockpit}>
              Launch 3D Cockpit
            </button>
            <button className="fp-btn-outline" onClick={() => scrollToSection('what-we-do')}>
              What Does It Do?
            </button>
          </div>

          <div className="fp-hero-badges">
            <div className="fp-badge-item">
              <span className="fp-badge-icon">🛡️</span>
              <span>10 Critical Clause Categories Screened</span>
            </div>
            <div className="fp-badge-item">
              <span className="fp-badge-icon">⚡</span>
              <span>Local Legal-BERT Classification</span>
            </div>
            <div className="fp-badge-item">
              <span className="fp-badge-icon">📄</span>
              <span>Interactive 3D Digital Paper Canvas</span>
            </div>
          </div>
        </div>
      </section>

      {/* 4. WHAT DOES OUR SITE DO SECTION (Short & Sweet & Minimalist) */}
      <section className="fp-summary-section" id="what-we-do">
        <div className="fp-section-header">
          <div className="fp-section-kicker">WHAT DOES CLAUSEWISE DO?</div>
          <h2 className="fp-section-title">Everything you need to sign safely</h2>
          <p className="fp-section-sub">
            Protect your business from predatory legal traps in three seamless steps.
          </p>
        </div>

        <div className="fp-cards-grid">
          <div className="fp-card">
            <div className="fp-card-step">STEP 01</div>
            <h3 className="fp-card-title">Ingest Any Contract</h3>
            <p className="fp-card-text">
              Drop any PDF, DOCX, or TXT document (up to 10MB). ClauseWise parses and segments complex legal language into discrete, verifiable clauses in seconds.
            </p>
            <div className="fp-card-pill">PDF • DOCX • TXT</div>
          </div>

          <div className="fp-card">
            <div className="fp-card-step">STEP 02</div>
            <h3 className="fp-card-title">Detect & Quantify Risk</h3>
            <p className="fp-card-text">
              Our fine-tuned Legal-BERT classifier identifies 10 critical risk classes—including Non-Competes, Uncapped Liability, Exclusivity, and Delay Damages—and scores risk from 0 to 100.
            </p>
            <div className="fp-card-pill">10 Legal Risk Classes</div>
          </div>

          <div className="fp-card">
            <div className="fp-card-step">STEP 03</div>
            <h3 className="fp-card-title">Inspect & Redline in 3D</h3>
            <p className="fp-card-text">
              Review highlighted clauses on a 3D digital paper sheet. Click any flag to read plain-English translations, inspect red flags, and copy balanced counter-clauses with word diffs.
            </p>
            <div className="fp-card-pill">3D Canvas • Word Diff</div>
          </div>
        </div>
      </section>

      {/* 5. CORE CAPABILITIES (All content present, concise & sweet) */}
      <section className="fp-summary-section" id="capabilities" style={{ background: '#0e1015' }}>
        <div className="fp-section-header">
          <div className="fp-section-kicker">CORE CAPABILITIES</div>
          <h2 className="fp-section-title">Minimalist Power, Maximum Protection</h2>
          <p className="fp-section-sub">
            All the legal intelligence of an enterprise audit, presented simply and clearly.
          </p>
        </div>

        <div className="fp-cards-grid">
          <div className="fp-card">
            <h3 className="fp-card-title">🔍 Ask-the-Contract Search</h3>
            <p className="fp-card-text">
              Ask natural language questions like <em>"can I terminate early?"</em> or <em>"what are my liability limits?"</em>. Powered by SBERT semantic vector search to jump straight to relevant sections.
            </p>
          </div>

          <div className="fp-card">
            <h3 className="fp-card-title">💡 Plain-English Translations</h3>
            <p className="fp-card-text">
              Demystify dense legal jargon. Every flagged clause features a plain-English explanation, real-world consequences, and a bulleted checklist of red flags.
            </p>
          </div>

          <div className="fp-card">
            <h3 className="fp-card-title">✏️ AI Balanced Redlines</h3>
            <p className="fp-card-text">
              Never start negotiations from scratch. Access fair, balanced replacement clauses with visual word-level strikethroughs and insertions, complete with rationale.
            </p>
          </div>

          <div className="fp-card">
            <h3 className="fp-card-title">🔊 Audio Read-Aloud</h3>
            <p className="fp-card-text">
              Listen to risk summaries and clause breakdowns on the go using integrated browser speech synthesis for hands-free contract reviews.
            </p>
          </div>

          <div className="fp-card">
            <h3 className="fp-card-title">🗺️ Vertical Clause Minimap</h3>
            <p className="fp-card-text">
              Get an instant visual distribution of high, moderate, and low risks down the document's edge. Click any tick to jump immediately to that section.
            </p>
          </div>

          <div className="fp-card">
            <h3 className="fp-card-title">🔒 100% Private & Local</h3>
            <p className="fp-card-text">
              Your confidential contracts are analyzed using locally loaded neural models. Zero text is sent to third-party generative LLM APIs.
            </p>
          </div>
        </div>
      </section>

      {/* 6. BOTTOM CALLOUT BANNER */}
      <div className="fp-cta-banner" id="how-it-works">
        <div className="fp-cta-text">
          <h3>Ready to inspect your agreement?</h3>
          <p>Drop a contract into the 3D Cockpit and see risk analysis in real time.</p>
        </div>
        <button className="fp-btn-warm" onClick={onLaunchCockpit}>
          Open 3D Cockpit →
        </button>
      </div>

      {/* 7. MINIMAL FOOTER */}
      <footer className="fp-footer">
        <div>© 2026 ClauseWise AI • AI Contract Risk Analyzer. Not legal advice.</div>
        <div className="fp-footer-links">
          <span className="fp-footer-link" onClick={onLaunchCockpit} style={{ cursor: 'pointer' }}>
            3D Cockpit
          </span>
          <a href="#what-we-do" className="fp-footer-link">
            Overview
          </a>
          <a href="#capabilities" className="fp-footer-link">
            Capabilities
          </a>
        </div>
      </footer>
    </div>
  );
}
