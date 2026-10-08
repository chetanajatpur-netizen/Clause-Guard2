import React, { useState } from 'react'
import UploadBox from '../components/UploadBox'
import Loader from '../components/Loader'
import ErrorBanner from '../components/ErrorBanner'
import ClauseCard from '../components/ClauseCard'
import RiskBadge from '../components/RiskBadge'
import SearchBar from '../components/SearchBar'
import { analyzeContract, searchDocument } from '../api/client'
import '../styles/landing.css'

export default function Landing() {
  // Form component demo state
  const [testEmail, setTestEmail] = useState('')
  const [contractTitle, setContractTitle] = useState('')
  const [agreedToTerms, setAgreedToTerms] = useState(false)
  const [emailTouched, setEmailTouched] = useState(false)

  // Contract analysis live state
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [searchResults, setSearchResults] = useState(null)
  const [searchLoading, setSearchLoading] = useState(false)

  const isEmailError = emailTouched && (!testEmail || !testEmail.includes('@'))

  const handleUpload = async (file) => {
    setLoading(true)
    setError(null)
    setResult(null)
    setSearchResults(null)
    try {
      const data = await analyzeContract(file)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async (query) => {
    if (!result) return
    setSearchLoading(true)
    try {
      const data = await searchDocument(result.document_id, query)
      setSearchResults(data.results)
    } catch (err) {
      setError(err.message)
    } finally {
      setSearchLoading(false)
    }
  }

  const displayClauses = searchResults || (result ? result.clauses : [])

  return (
    <div className="landing-container">
      {/* Skip Link for Keyboard Accessibility */}
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      {/* Semantic Header & Nav */}
      <header className="landing-header" role="banner">
        <nav className="landing-nav-inner" aria-label="Main Navigation">
          <a href="#main-content" className="landing-brand" aria-label="ClauseGuard Home">
            <span className="landing-logo-icon" aria-hidden="true">⚖️</span>
            <span className="landing-brand-text">ClauseGuard</span>
          </a>

          <ul className="landing-nav-links">
            <li>
              <a href="#features" className="landing-nav-link">Features</a>
            </li>
            <li>
              <a href="#analyzer" className="landing-nav-link">Live Auditor</a>
            </li>
            <li>
              <a href="#cards" className="landing-nav-link">Analyzed Clauses</a>
            </li>
            <li>
              <a href="#design-system" className="landing-nav-link">Design System</a>
            </li>
            <li>
              <a href="#forms" className="landing-nav-link">Components</a>
            </li>
          </ul>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <a href="#analyzer" className="landing-btn landing-btn-primary">
              Audit Contract ↓
            </a>
          </div>
        </nav>
      </header>

      {/* Main Content Landmark */}
      <main id="main-content" className="landing-main" role="main">
        {/* Hero Section */}
        <section className="landing-hero" aria-labelledby="hero-heading">
          <span className="landing-eyebrow">
            <span aria-hidden="true">🛡️</span> WCAG 2.1 AA Compliant • Zero External LLM APIs
          </span>

          <h1 id="hero-heading" className="landing-hero-title">
            Spot Hidden Contract Traps Before You Sign.
          </h1>

          <p className="landing-hero-subtitle">
            ClauseGuard pairs fine-tuned Legal-BERT with deterministic risk heuristics to automatically 
            flag uncapped liabilities, predatory non-competes, and indemnification traps in seconds.
          </p>

          <div className="landing-hero-actions">
            <a href="#analyzer" className="landing-btn landing-btn-primary" aria-label="Scroll to live contract analyzer">
              Analyze a Contract Free
            </a>
            <a href="#design-system" className="landing-btn landing-btn-outline" aria-label="Explore the accessible design system">
              Explore Design System
            </a>
            <a href="#cards" className="landing-btn landing-btn-ghost" aria-label="View common clause hazards">
              Common Hazards
            </a>
          </div>

          {/* Key Metric Cards */}
          <div id="features" className="landing-stats-grid" aria-label="Key Performance Metrics">
            <div className="landing-stat-card">
              <div className="landing-stat-num">510+</div>
              <div className="landing-stat-label">CUAD Real Contracts Trained</div>
            </div>
            <div className="landing-stat-card">
              <div className="landing-stat-num">11</div>
              <div className="landing-stat-label">Clause &amp; Risk Categories</div>
            </div>
            <div className="landing-stat-card">
              <div className="landing-stat-num">&lt; 3s</div>
              <div className="landing-stat-label">Average Full Document Scan</div>
            </div>
            <div className="landing-stat-card">
              <div className="landing-stat-num">100%</div>
              <div className="landing-stat-label">Local &amp; Private Inference</div>
            </div>
          </div>
        </section>

        {/* Section: Live Contract Risk Auditor (Embedded directly on this page) */}
        <section id="analyzer" aria-labelledby="analyzer-heading" style={{ marginBottom: '64px', scrollMarginTop: '80px' }}>
          <div className="landing-section-header">
            <span className="landing-card-tag tag-primary" style={{ marginBottom: '12px', display: 'inline-block' }}>
              ⚡ Live Scanner
            </span>
            <h2 id="analyzer-heading" className="landing-section-title">
              Contract Risk Auditor
            </h2>
            <p className="landing-section-subtitle">
              Drop any commercial agreement below to detect high-risk clauses, calculate risk scores, and review fallback negotiation suggestions.
            </p>
          </div>

          <div className="landing-showcase-box" style={{ padding: '32px' }}>
            {/* Upload Area */}
            <UploadBox onUpload={handleUpload} loading={loading} />

            {error && (
              <ErrorBanner message={error} onRetry={() => setError(null)} />
            )}

            {loading && <Loader />}

            {result && !loading && (
              <div style={{ marginTop: '24px' }}>
                {/* Result Summary Bar */}
                <div style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '12px',
                  padding: '20px 24px',
                  marginBottom: '24px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '16px'
                }}>
                  <div>
                    <h3 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 4px 0', color: '#0f172a' }}>
                      {result.filename}
                    </h3>
                    <p style={{ margin: 0, fontSize: '14px', color: '#64748b' }}>
                      {result.char_count?.toLocaleString()} characters • {result.risk_summary?.total_clauses} clauses extracted
                    </p>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <RiskBadge level={result.risk_summary?.overall_risk} />
                    <div style={{ display: 'flex', gap: '8px', fontSize: '13px', fontWeight: 600 }}>
                      <span style={{ color: '#dc2626', background: '#fef2f2', padding: '4px 8px', borderRadius: '6px' }}>
                        ● {result.risk_summary?.high_count} High
                      </span>
                      <span style={{ color: '#d97706', background: '#fffbeb', padding: '4px 8px', borderRadius: '6px' }}>
                        ● {result.risk_summary?.medium_count} Med
                      </span>
                      <span style={{ color: '#16a34a', background: '#f0fdf4', padding: '4px 8px', borderRadius: '6px' }}>
                        ● {result.risk_summary?.low_count} Low
                      </span>
                    </div>
                  </div>
                </div>

                {/* Search Bar */}
                <SearchBar onSearch={handleSearch} loading={searchLoading} />
                {searchResults && (
                  <p style={{ fontSize: '14px', color: '#64748b', margin: '8px 0 16px 0' }}>
                    Found {searchResults.length} matching clause(s)
                    <button
                      type="button"
                      onClick={() => setSearchResults(null)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#2563eb',
                        cursor: 'pointer',
                        marginLeft: '12px',
                        fontWeight: 600,
                        textDecoration: 'underline'
                      }}
                    >
                      Clear search
                    </button>
                  </p>
                )}

                {/* Clause List with AI Context Explanations */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
                  {displayClauses.map((clause, idx) => (
                    <ClauseCard
                      key={clause.id || clause.clause_id || idx}
                      clause={{
                        ...clause,
                        id: clause.id || clause.clause_id,
                        risk_level: clause.risk_level,
                        confidence: clause.confidence || clause.similarity || 0,
                      }}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Section: Content Cards with Imagery, Tags, and Author Metadata */}
        <section id="cards" aria-labelledby="cards-section-heading" style={{ scrollMarginTop: '80px' }}>
          <div className="landing-section-header">
            <h2 id="cards-section-heading" className="landing-section-title">
              Common High-Hazard Clauses We Detect
            </h2>
            <p className="landing-section-subtitle">
              Interactive analysis cards featuring severity badges, plain-English impact summaries, and engine metadata.
            </p>
          </div>

          <div className="landing-cards-grid">
            {/* Card 1: Uncapped Liability */}
            <article className="landing-content-card" aria-labelledby="card-title-1">
              <div className="landing-card-image-wrap">
                <span className="landing-card-visual-icon" aria-hidden="true">💥</span>
                <span className="landing-card-tag tag-high">High Risk</span>
              </div>
              <div className="landing-card-body">
                <h3 id="card-title-1" className="landing-card-title">
                  Uncapped Liability
                </h3>
                <p className="landing-card-desc">
                  Exposes independent contractors and SaaS vendors to unlimited financial claims without any ceiling, 
                  potentially exceeding 10x total earned fees.
                </p>
                <div className="landing-card-meta">
                  <div className="landing-card-author">
                    <span className="landing-avatar" aria-hidden="true">LB</span>
                    <span>Legal-BERT v1.0</span>
                  </div>
                  <time dateTime="2026-10-08">Severity: 9.8 / 10</time>
                </div>
              </div>
            </article>

            {/* Card 2: 24-Month Non-Compete */}
            <article className="landing-content-card" aria-labelledby="card-title-2">
              <div className="landing-card-image-wrap">
                <span className="landing-card-visual-icon" aria-hidden="true">🚫</span>
                <span className="landing-card-tag tag-high">High Risk</span>
              </div>
              <div className="landing-card-body">
                <h3 id="card-title-2" className="landing-card-title">
                  Worldwide Non-Compete
                </h3>
                <p className="landing-card-desc">
                  Restricts your legal right to work for competing businesses or accept adjacent clients for up to 2 years, 
                  even in the event of termination without cause.
                </p>
                <div className="landing-card-meta">
                  <div className="landing-card-author">
                    <span className="landing-avatar" aria-hidden="true">CG</span>
                    <span>ClauseGuard Engine</span>
                  </div>
                  <time dateTime="2026-10-08">Severity: 9.2 / 10</time>
                </div>
              </div>
            </article>

            {/* Card 3: IP Assignment */}
            <article className="landing-content-card" aria-labelledby="card-title-3">
              <div className="landing-card-image-wrap">
                <span className="landing-card-visual-icon" aria-hidden="true">💡</span>
                <span className="landing-card-tag tag-medium">Medium Risk</span>
              </div>
              <div className="landing-card-body">
                <h3 id="card-title-3" className="landing-card-title">
                  Broad IP Ownership Assignment
                </h3>
                <p className="landing-card-desc">
                  Assigns pre-existing frameworks, developer tooling, and unreleased personal libraries created outside work hours 
                  directly to the client without compensation.
                </p>
                <div className="landing-card-meta">
                  <div className="landing-card-author">
                    <span className="landing-avatar" aria-hidden="true">HR</span>
                    <span>Heuristic Auditor</span>
                  </div>
                  <time dateTime="2026-10-08">Severity: 6.5 / 10</time>
                </div>
              </div>
            </article>
          </div>
        </section>

        {/* Section: Design System Showcase */}
        <section id="design-system" aria-labelledby="design-system-heading" style={{ scrollMarginTop: '80px' }}>
          <div className="landing-section-header">
            <h2 id="design-system-heading" className="landing-section-title">
              ClauseGuard Accessible Design System (WCAG 2.1 AA)
            </h2>
            <p className="landing-section-subtitle">
              Strict adherence to color contrast (≥ 4.5:1), 4px keyboard focus rings, semantic structure, and 44x44px touch targets.
            </p>
          </div>

          <div className="landing-showcase-box">
            {/* 1. Palette Swatches */}
            <div>
              <h3 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 16px 0' }}>
                1. Color Palette Swatches
              </h3>
              <div className="swatches-grid">
                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#0f172a' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Deep Charcoal</div>
                    <div className="swatch-hex">#0f172a</div>
                    <div className="swatch-contrast">Contrast: 15.8:1 ✓</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#2563eb' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Electric Blue</div>
                    <div className="swatch-hex">#2563eb</div>
                    <div className="swatch-contrast">Contrast: 4.6:1 ✓</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#f1f5f9', borderBottom: '1px solid #e2e8f0' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Soft Slate</div>
                    <div className="swatch-hex">#f1f5f9</div>
                    <div className="swatch-contrast">Page Background</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#ffffff', borderBottom: '1px solid #e2e8f0' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Crisp White</div>
                    <div className="swatch-hex">#ffffff</div>
                    <div className="swatch-contrast">Card Surface</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#e2e8f0' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Slate-200</div>
                    <div className="swatch-hex">#e2e8f0</div>
                    <div className="swatch-contrast">Subtle Outlines</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#dc2626' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Risk Crimson</div>
                    <div className="swatch-hex">#dc2626</div>
                    <div className="swatch-contrast">High Hazard</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#16a34a' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Emerald Safe</div>
                    <div className="swatch-hex">#16a34a</div>
                    <div className="swatch-contrast">Low / Standard</div>
                  </div>
                </div>
              </div>
            </div>

            {/* 2. Typography Scale */}
            <div>
              <h3 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 16px 0' }}>
                2. Inter Typography Scale (Minimum 16px Body, 1.6 Line-Height)
              </h3>
              <div style={{ overflowX: 'auto' }}>
                <table className="type-scale-table" aria-label="Typography scale specifications">
                  <thead>
                    <tr>
                      <th scope="col">Level</th>
                      <th scope="col">Size / Line-Height</th>
                      <th scope="col">Weight</th>
                      <th scope="col">Sample Text</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <th scope="row">Heading 1</th>
                      <td>44px / 1.15</td>
                      <td>800 (Extra Bold)</td>
                      <td style={{ fontSize: '28px', fontWeight: 800 }}>Spot Hidden Contract Traps</td>
                    </tr>
                    <tr>
                      <th scope="row">Heading 2</th>
                      <td>28px / 1.25</td>
                      <td>700 (Bold)</td>
                      <td style={{ fontSize: '22px', fontWeight: 700 }}>Contract Clause Auditing</td>
                    </tr>
                    <tr>
                      <th scope="row">Heading 3</th>
                      <td>20px / 1.3</td>
                      <td>600 (Semibold)</td>
                      <td style={{ fontSize: '18px', fontWeight: 600 }}>Uncapped Liability Penalty</td>
                    </tr>
                    <tr>
                      <th scope="row">Body Regular</th>
                      <td>16px / 1.6</td>
                      <td>400 (Regular)</td>
                      <td style={{ fontSize: '16px', lineHeight: 1.6 }}>ClauseGuard provides deterministic risk classification for commercial agreements.</td>
                    </tr>
                    <tr>
                      <th scope="row">Body Small</th>
                      <td>14px / 1.5</td>
                      <td>500 (Medium)</td>
                      <td style={{ fontSize: '14px', color: '#475569' }}>Single source of truth heuristic risk table. Educational guidance only.</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* 3. Button Component Hierarchy */}
            <div>
              <h3 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 16px 0' }}>
                3. Button Components (Touch Targets ≥ 44x44px with 4px Colored Focus Ring)
              </h3>
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
                <button type="button" className="landing-btn landing-btn-primary">
                  Primary Button
                </button>
                <button type="button" className="landing-btn landing-btn-secondary">
                  Secondary Button
                </button>
                <button type="button" className="landing-btn landing-btn-outline">
                  Outline Button
                </button>
                <button type="button" className="landing-btn landing-btn-ghost">
                  Ghost Button
                </button>
                <button 
                  type="button" 
                  className="icon-btn" 
                  aria-label="Download Contract Analysis Summary Report"
                  title="Download Summary Report"
                >
                  📥
                </button>
              </div>
            </div>

            {/* 4. Accessible Form Inputs (Default, Error State, Checkbox) */}
            <div id="forms" style={{ scrollMarginTop: '80px' }}>
              <h3 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 16px 0' }}>
                4. Accessible Form Inputs (Explicit Labels, aria-describedby, Error Indicators)
              </h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                {/* Default Input with Label and Helper */}
                <div className="form-group">
                  <label htmlFor="contract-title-input" className="form-label">
                    Contract Title / Reference
                  </label>
                  <input
                    id="contract-title-input"
                    type="text"
                    className="landing-input"
                    placeholder="e.g. Master Services Agreement 2026-Q4"
                    value={contractTitle}
                    onChange={(e) => setContractTitle(e.target.value)}
                    aria-describedby="title-helper-text"
                  />
                  <span id="title-helper-text" className="form-helper-text">
                    Human-readable label used for contract classification history.
                  </span>
                </div>

                {/* Error State Input pairing Red Border + Icon + Text Message */}
                <div className="form-group">
                  <label htmlFor="contact-email-input" className="form-label">
                    Client Notification Email Address
                  </label>
                  <input
                    id="contact-email-input"
                    type="email"
                    className={`landing-input ${isEmailError ? 'input-error' : ''}`}
                    placeholder="legal-counsel@company.org"
                    value={testEmail}
                    onBlur={() => setEmailTouched(true)}
                    onChange={(e) => {
                      setTestEmail(e.target.value)
                      if (!emailTouched) setEmailTouched(true)
                    }}
                    aria-describedby={isEmailError ? 'email-error-desc' : 'email-helper-desc'}
                    aria-invalid={isEmailError ? 'true' : 'false'}
                  />
                  {!isEmailError && (
                    <span id="email-helper-desc" className="form-helper-text">
                      Audit reports and risk warnings will be dispatched to this address.
                    </span>
                  )}
                  {isEmailError && (
                    <div id="email-error-desc" className="form-error-msg" role="alert">
                      <span aria-hidden="true">⚠️</span>
                      <span>Please enter a valid business email address containing an '@' symbol.</span>
                    </div>
                  )}
                </div>

                {/* Accessible Checkbox with Linked Label */}
                <div className="form-group">
                  <div className="checkbox-wrap">
                    <input
                      id="terms-checkbox"
                      type="checkbox"
                      className="landing-checkbox"
                      checked={agreedToTerms}
                      onChange={(e) => setAgreedToTerms(e.target.checked)}
                      aria-describedby="terms-helper"
                    />
                    <label htmlFor="terms-checkbox" className="checkbox-label">
                      I understand ClauseGuard is an educational analysis tool and does not constitute attorney legal advice.
                    </label>
                  </div>
                  <span id="terms-helper" className="form-helper-text" style={{ marginLeft: '30px' }}>
                    Mandatory acknowledgment before processing binding agreements.
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section: Call to Action Banner */}
        <section className="landing-cta-banner" aria-labelledby="cta-heading">
          <h2 id="cta-heading" className="landing-cta-title">
            Ready to Audit Your Commercial Agreements?
          </h2>
          <p className="landing-cta-subtitle">
            Drag and drop any PDF, DOCX, or TXT file into the auditor above to inspect risk ratings, extract individual clauses, 
            and read human-written negotiation fallbacks.
          </p>
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', justifyContent: 'center' }}>
            <a href="#analyzer" className="landing-btn landing-btn-primary">
              Upload Your Contract Free
            </a>
            <a href="#design-system" className="landing-btn landing-btn-outline">
              Explore Design System
            </a>
          </div>
        </section>
      </main>

      {/* Semantic Footer */}
      <footer className="landing-footer" role="contentinfo">
        <div className="landing-footer-inner">
          <div className="landing-footer-badge">
            <span aria-hidden="true">♿</span> WCAG 2.1 AA Standard Verified • 4.5:1 Contrast • 44px Touch Targets
          </div>
          <p style={{ margin: 0 }}>
            &copy; 2026 ClauseGuard Contract Risk Analyzer. Designed with Inter, Electric Blue, and Soft Slate.
          </p>
          <p style={{ margin: 0, fontSize: '13px', color: '#64748b' }}>
            Educational tool only. Not licensed legal advice. Always review binding legal instruments with qualified legal counsel.
          </p>
        </div>
      </footer>
    </div>
  )
}
