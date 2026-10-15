import React, { useState } from 'react'
import UploadBox from '../components/UploadBox'
import Loader from '../components/Loader'
import ErrorBanner from '../components/ErrorBanner'
import ClauseCard from '../components/ClauseCard'
import RiskBadge from '../components/RiskBadge'
import SearchBar from '../components/SearchBar'
import ViewModeToggle from '../components/ViewModeToggle'
import HeatMap from '../components/HeatMap'
import { analyzeContract, searchDocument } from '../api/client'
import '../styles/landing.css'

export default function Landing({ onSwitchToCockpit }) {
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
  const [viewMode, setViewMode] = useState('lawyer')

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
            <span className="landing-brand-pill">Precision Legal Canvas</span>
          </a>

          <ul className="landing-nav-links">
            <li>
              <a href="#features" className="landing-nav-link">Metrics</a>
            </li>
            <li>
              <a href="#analyzer" className="landing-nav-link">Live Auditor</a>
            </li>
            <li>
              <a href="#cards" className="landing-nav-link">Hazard Library</a>
            </li>
            <li>
              <a href="#design-system" className="landing-nav-link">Design System</a>
            </li>
            <li>
              <a href="#redlines" className="landing-nav-link">Redlines</a>
            </li>
            <li>
              <a href="#forms" className="landing-nav-link">Inputs</a>
            </li>
          </ul>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {onSwitchToCockpit && (
              <button
                type="button"
                onClick={onSwitchToCockpit}
                style={{
                  background: '#0f131d',
                  color: '#c3c0ff',
                  border: '1px solid #464555',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 14px',
                  fontSize: '12px',
                  fontFamily: 'var(--font-mono)',
                  cursor: 'pointer',
                  borderRadius: '6px',
                  fontWeight: 600,
                  transition: 'all 0.2s ease',
                }}
                title="Switch to 3D Spatial Cockpit view"
              >
                <span>🌐</span>
                <span>3D Spatial Cockpit</span>
              </button>
            )}
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
            <span aria-hidden="true">🛡️</span> Precision Legal Canvas • WCAG 2.1 AA Compliant
          </span>

          <h1 id="hero-heading" className="landing-hero-title">
            Spot Hidden Contract Traps Before You Sign.
          </h1>

          <p className="landing-hero-subtitle">
            ClauseGuard couples fine-tuned Legal-BERT with deterministic risk heuristics to automatically 
            flag uncapped liabilities, predatory non-competes, and indemnification traps in seconds.
          </p>

          <div className="landing-hero-actions">
            <a href="#analyzer" className="landing-btn landing-btn-primary" aria-label="Scroll to live contract analyzer">
              Analyze a Contract Free
            </a>
            <a href="#design-system" className="landing-btn landing-btn-secondary" aria-label="Explore the Precision Legal Canvas design system">
              Explore Design System
            </a>
            <a href="#cards" className="landing-btn landing-btn-outline" aria-label="View common clause hazards">
              Clause Hazard Library
            </a>
          </div>

          {/* Key Metric Cards */}
          <div id="features" className="landing-stats-grid" aria-label="Key Performance Metrics">
            <div className="landing-stat-card">
              <div className="landing-stat-num tnum">510+</div>
              <div className="landing-stat-label">CUAD Real Contracts Trained</div>
            </div>
            <div className="landing-stat-card">
              <div className="landing-stat-num tnum">11</div>
              <div className="landing-stat-label">Clause &amp; Risk Categories</div>
            </div>
            <div className="landing-stat-card">
              <div className="landing-stat-num tnum">&lt; 3s</div>
              <div className="landing-stat-label">Average Full Document Scan</div>
            </div>
            <div className="landing-stat-card">
              <div className="landing-stat-num tnum">100%</div>
              <div className="landing-stat-label">Deterministic &amp; Private Inference</div>
            </div>
          </div>
        </section>

        {/* Section: Live Contract Risk Auditor (Embedded directly on this page) */}
        <section id="analyzer" aria-labelledby="analyzer-heading" style={{ scrollMarginTop: '80px' }}>
          <div className="landing-section-header">
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                fontWeight: 600,
                color: '#3525cd',
                backgroundColor: '#e5eeff',
                padding: '2px 8px',
                borderRadius: '4px',
                width: 'fit-content',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                marginBottom: '4px',
              }}
            >
              ⚡ Live Scanner
            </span>
            <h2 id="analyzer-heading" className="landing-section-title">
              Contract Risk Auditor
            </h2>
            <p className="landing-section-subtitle">
              Drop any commercial agreement below to detect high-risk clauses, calculate risk scores, and review fallback negotiation suggestions.
            </p>
          </div>

          <div
            style={{
              backgroundColor: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              padding: '24px',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <UploadBox onUpload={handleUpload} loading={loading} />

            {loading && <Loader />}
            {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

            {result && (
              <div style={{ marginTop: '24px' }}>
                {/* Document Risk Summary Card */}
                <div
                  style={{
                    backgroundColor: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px',
                    padding: '20px',
                    marginBottom: '20px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                    <div>
                      <h3 style={{ margin: '0 0 4px 0', fontSize: '16px', fontWeight: 600, color: '#0b1c30' }}>
                        {result.filename}
                      </h3>
                      <p style={{ margin: 0, fontSize: '13px', color: '#64748b' }}>
                        <span className="tnum">{result.char_count.toLocaleString()}</span> characters &bull;{' '}
                        <span className="tnum">{result.clauses.length}</span> clauses analyzed
                      </p>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '13px', fontWeight: 600, color: '#0b1c30' }}>
                        Overall Document Risk:
                      </span>
                      <RiskBadge level={result.risk_summary.overall_risk} />
                    </div>
                  </div>

                  {/* Risk Breakdown Counts */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
                      gap: '10px',
                      marginTop: '16px',
                    }}
                  >
                    <div style={{ padding: '8px 12px', background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: '6px' }}>
                      <div className="tnum" style={{ fontSize: '18px', fontWeight: 700, color: '#9f1239' }}>
                        {result.risk_summary.high_count}
                      </div>
                      <div style={{ fontSize: '11px', textTransform: 'uppercase', color: '#9f1239', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                        Critical
                      </div>
                    </div>

                    <div style={{ padding: '8px 12px', background: '#fffbeb', border: '1px solid #fef3c7', borderRadius: '6px' }}>
                      <div className="tnum" style={{ fontSize: '18px', fontWeight: 700, color: '#92400e' }}>
                        {result.risk_summary.medium_count}
                      </div>
                      <div style={{ fontSize: '11px', textTransform: 'uppercase', color: '#92400e', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                        Moderate
                      </div>
                    </div>

                    <div style={{ padding: '8px 12px', background: '#f0fdf4', border: '1px solid #dcfce7', borderRadius: '6px' }}>
                      <div className="tnum" style={{ fontSize: '18px', fontWeight: 700, color: '#166534' }}>
                        {result.risk_summary.low_count}
                      </div>
                      <div style={{ fontSize: '11px', textTransform: 'uppercase', color: '#166534', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                        Approved
                      </div>
                    </div>

                    <div style={{ padding: '8px 12px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
                      <div className="tnum" style={{ fontSize: '18px', fontWeight: 700, color: '#475569' }}>
                        {result.risk_summary.none_count}
                      </div>
                      <div style={{ fontSize: '11px', textTransform: 'uppercase', color: '#64748b', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                        Standard
                      </div>
                    </div>
                  </div>
                </div>

                {/* Clause Heat Map (Feature 3) */}
                <HeatMap clauses={result.clauses} />

                {/* Natural Language Semantic Search */}
                <SearchBar onSearch={handleSearch} loading={searchLoading} />

                {/* View Mode Toggle: Lawyer View vs Plain English */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '12px' }}>
                  <ViewModeToggle viewMode={viewMode} onChange={setViewMode} />
                  {searchResults && (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setSearchResults(null)}
                      style={{ padding: '4px 12px', fontSize: '12px', minHeight: '32px' }}
                    >
                      Clear Search Results ({searchResults.length})
                    </button>
                  )}
                </div>

                {/* Extracted Clauses List */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {displayClauses.map((clause) => (
                    <ClauseCard key={clause.id || clause.position} clause={clause} viewMode={viewMode} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Section: Common Hazard Cards */}
        <section id="cards" aria-labelledby="cards-heading" style={{ scrollMarginTop: '80px' }}>
          <div className="landing-section-header">
            <h2 id="cards-heading" className="landing-section-title">
              Common High-Risk Legal Traps
            </h2>
            <p className="landing-section-subtitle">
              Pre-computed risk profiles for the most damaging provisions commonly inserted into technology agreements.
            </p>
          </div>

          <div className="landing-cards-grid">
            {/* Card 1: Uncapped Liability */}
            <article className="landing-content-card" style={{ borderLeft: '3px solid #e11d48' }}>
              <div className="landing-card-image-wrap">
                <span className="landing-card-visual-icon" aria-hidden="true">⚠️</span>
                <span className="landing-card-tag tag-critical">● Critical Risk</span>
              </div>
              <div className="landing-card-body">
                <h3 className="landing-card-title">
                  Uncapped Liability &amp; Consequential Damages
                </h3>
                <p className="landing-card-desc">
                  Exposes your organization to unlimited financial exposure for indirect, punitive, or loss-of-profit damages 
                  with no liability ceiling pegged to contract value.
                </p>
                <div className="landing-card-meta">
                  <div className="landing-card-author">
                    <span className="landing-avatar" aria-hidden="true">CG</span>
                    <span>ClauseGuard Heuristics</span>
                  </div>
                  <span className="tnum">Score: 95/100</span>
                </div>
              </div>
            </article>

            {/* Card 2: Non-Compete */}
            <article className="landing-content-card" style={{ borderLeft: '3px solid #e11d48' }}>
              <div className="landing-card-image-wrap">
                <span className="landing-card-visual-icon" aria-hidden="true">🚫</span>
                <span className="landing-card-tag tag-critical">● Critical Risk</span>
              </div>
              <div className="landing-card-body">
                <h3 className="landing-card-title">
                  Overly Broad Non-Compete Restriction
                </h3>
                <p className="landing-card-desc">
                  Restricts your legal right to work for competing businesses or accept adjacent clients for up to 2 years, 
                  even in the event of termination without cause.
                </p>
                <div className="landing-card-meta">
                  <div className="landing-card-author">
                    <span className="landing-avatar" aria-hidden="true">CG</span>
                    <span>Legal-BERT Classifier</span>
                  </div>
                  <span className="tnum">Score: 90/100</span>
                </div>
              </div>
            </article>

            {/* Card 3: IP Assignment */}
            <article className="landing-content-card" style={{ borderLeft: '3px solid #d97706' }}>
              <div className="landing-card-image-wrap">
                <span className="landing-card-visual-icon" aria-hidden="true">💡</span>
                <span className="landing-card-tag tag-moderate">● Moderate Risk</span>
              </div>
              <div className="landing-card-body">
                <h3 className="landing-card-title">
                  Broad IP Ownership Assignment
                </h3>
                <p className="landing-card-desc">
                  Assigns pre-existing frameworks, developer tooling, and unreleased personal libraries created outside work hours 
                  directly to the client without exclusion carve-outs.
                </p>
                <div className="landing-card-meta">
                  <div className="landing-card-author">
                    <span className="landing-avatar" aria-hidden="true">HR</span>
                    <span>Static Heuristics</span>
                  </div>
                  <span className="tnum">Score: 65/100</span>
                </div>
              </div>
            </article>
          </div>
        </section>

        {/* Section: Precision Legal Canvas Design System Showcase */}
        <section id="design-system" aria-labelledby="design-system-heading" style={{ scrollMarginTop: '80px' }}>
          <div className="landing-section-header">
            <h2 id="design-system-heading" className="landing-section-title">
              Precision Legal Canvas Design System
            </h2>
            <p className="landing-section-subtitle">
              Engineered for high information density, clinical contrast, tabular figures, and strict WCAG 2.1 AA accessibility.
            </p>
          </div>

          <div className="landing-showcase-box">
            {/* 1. Palette Swatches */}
            <div>
              <h3 style={{ fontSize: '15px', fontWeight: 600, margin: '0 0 14px 0', letterSpacing: '-0.005em' }}>
                1. System Color Palette Swatches
              </h3>
              <div className="swatches-grid">
                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#f8f9ff', borderBottom: '1px solid #e2e8f0' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Surface Canvas</div>
                    <div className="swatch-hex">#f8f9ff</div>
                    <div className="swatch-role">Page Background</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#ffffff', borderBottom: '1px solid #e2e8f0' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Container Lowest</div>
                    <div className="swatch-hex">#ffffff</div>
                    <div className="swatch-role">Card Surfaces</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#e5eeff', borderBottom: '1px solid #c7c4d8' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Container</div>
                    <div className="swatch-hex">#e5eeff</div>
                    <div className="swatch-role">Active Highlight</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#cbdbf5' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Surface Dim</div>
                    <div className="swatch-hex">#cbdbf5</div>
                    <div className="swatch-role">Delicate Backing</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#0b1c30' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">On-Surface</div>
                    <div className="swatch-hex">#0b1c30</div>
                    <div className="swatch-role">Primary Text</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#464555' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">On-Surface Variant</div>
                    <div className="swatch-hex">#464555</div>
                    <div className="swatch-role">Secondary Text</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#3525cd' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Primary Cobalt</div>
                    <div className="swatch-hex">#3525cd</div>
                    <div className="swatch-role">Brand Anchor</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#4f46e5' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Primary Container</div>
                    <div className="swatch-hex">#4f46e5</div>
                    <div className="swatch-role">Accent Interactive</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#565e74' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Secondary Slate</div>
                    <div className="swatch-hex">#565e74</div>
                    <div className="swatch-role">Supporting Elements</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#ba1a1a' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Error Crimson</div>
                    <div className="swatch-hex">#ba1a1a</div>
                    <div className="swatch-role">Destructive / Failure</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#fff1f2', borderBottom: '1px solid #fecdd3' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Critical Tint</div>
                    <div className="swatch-hex">#fff1f2</div>
                    <div className="swatch-role">High Hazard Badge</div>
                  </div>
                </div>

                <div className="swatch-item">
                  <div className="swatch-color" style={{ background: '#f0fdf4', borderBottom: '1px solid #dcfce7' }}></div>
                  <div className="swatch-info">
                    <div className="swatch-name">Compliant Tint</div>
                    <div className="swatch-hex">#f0fdf4</div>
                    <div className="swatch-role">Approved Standard</div>
                  </div>
                </div>
              </div>
            </div>

            {/* 2. Inter & JetBrains Mono Typography Scale Table */}
            <div>
              <h3 style={{ fontSize: '15px', fontWeight: 600, margin: '0 0 14px 0', letterSpacing: '-0.005em' }}>
                2. Typography Scale (Inter &bull; JetBrains Mono &bull; Tabular Figures)
              </h3>
              <div style={{ overflowX: 'auto', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
                <table className="type-scale-table" aria-label="Precision Legal Canvas Typography scale">
                  <thead>
                    <tr style={{ backgroundColor: '#f8fafc' }}>
                      <th scope="col">Token</th>
                      <th scope="col">Font Family</th>
                      <th scope="col">Size / Line-Height</th>
                      <th scope="col">Weight / Spacing</th>
                      <th scope="col">Rendered Preview</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <th scope="row"><code style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>display-lg</code></th>
                      <td>Inter</td>
                      <td className="tnum">32px / 40px</td>
                      <td>600 / -0.02em</td>
                      <td className="type-display-lg" style={{ fontSize: '24px', lineHeight: '30px' }}>Spot Hidden Contract Traps</td>
                    </tr>
                    <tr>
                      <th scope="row"><code style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>headline-lg</code></th>
                      <td>Inter</td>
                      <td className="tnum">24px / 32px</td>
                      <td>600 / -0.015em</td>
                      <td className="type-headline-lg" style={{ fontSize: '18px', lineHeight: '24px' }}>Deterministic Clause Classification</td>
                    </tr>
                    <tr>
                      <th scope="row"><code style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>headline-sm</code></th>
                      <td>Inter</td>
                      <td className="tnum">18px / 26px</td>
                      <td>600 / -0.01em</td>
                      <td className="type-headline-sm">Indemnification &amp; Defense Obligations</td>
                    </tr>
                    <tr>
                      <th scope="row"><code style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>title-md</code></th>
                      <td>Inter</td>
                      <td className="tnum">15px / 22px</td>
                      <td>600 / -0.005em</td>
                      <td className="type-title-md">Governing Law and Dispute Venue</td>
                    </tr>
                    <tr>
                      <th scope="row"><code style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>body-lg</code></th>
                      <td>Inter</td>
                      <td className="tnum">15px / 24px</td>
                      <td>400 / 0em</td>
                      <td className="type-body-lg">Analytical contract intelligence designed for enterprise counsel.</td>
                    </tr>
                    <tr>
                      <th scope="row"><code style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>body-md</code></th>
                      <td>Inter</td>
                      <td className="tnum">13px / 20px</td>
                      <td>400 / 0em</td>
                      <td className="type-body-md">Standard clause commentary, metadata labels, and helper descriptions.</td>
                    </tr>
                    <tr>
                      <th scope="row"><code style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>body-sm</code></th>
                      <td>Inter</td>
                      <td className="tnum">12px / 18px</td>
                      <td>400 / 0.01em</td>
                      <td className="type-body-sm">Educational guidance note. Not licensed attorney counsel.</td>
                    </tr>
                    <tr>
                      <th scope="row"><code style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>code-md</code></th>
                      <td>JetBrains Mono</td>
                      <td className="tnum">13px / 22px</td>
                      <td>400 / -0.01em</td>
                      <td className="type-code-md">SECTION 14.2: In no event shall liability exceed total fees.</td>
                    </tr>
                    <tr>
                      <th scope="row"><code style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>code-sm</code></th>
                      <td>JetBrains Mono</td>
                      <td className="tnum">11px / 16px</td>
                      <td>500 / 0em</td>
                      <td className="type-code-sm">CONFIDENCE: 94.8% &bull; RISK: 87/100</td>
                    </tr>
                    <tr>
                      <th scope="row"><code style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>label-sm</code></th>
                      <td>Inter</td>
                      <td className="tnum">11px / 14px</td>
                      <td>500 / 0.04em</td>
                      <td className="type-label-sm" style={{ color: '#464555' }}>STATUTORY COMPLIANCE AUDIT</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* 3. Action Hierarchy Buttons */}
            <div>
              <h3 style={{ fontSize: '15px', fontWeight: 600, margin: '0 0 14px 0', letterSpacing: '-0.005em' }}>
                3. Action &amp; Component Hierarchy (Touch Targets &ge; 44x44px, 6px Radii)
              </h3>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
                <button type="button" className="btn btn-primary">
                  Primary Action (#0f172a)
                </button>
                <button type="button" className="btn btn-secondary">
                  Secondary Action (White)
                </button>
                <button type="button" className="btn btn-accent">
                  Accent Interactive (#4f46e5)
                </button>
                <button type="button" className="btn btn-destructive">
                  Destructive Action (#fff1f2)
                </button>
                <button 
                  type="button" 
                  className="icon-btn" 
                  aria-label="Download Summary Report"
                  title="Download Summary Report"
                >
                  📥
                </button>
              </div>
            </div>

            {/* 4. Redline & Diff Annotations Showcase */}
            <div id="redlines" style={{ scrollMarginTop: '80px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 600, margin: '0 0 14px 0', letterSpacing: '-0.005em' }}>
                4. Redline &amp; Diff Annotations (Contract Term Revision Preview)
              </h3>
              <div className="diff-preview-box">
                <div style={{ marginBottom: '8px', color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Clause 9.3 &bull; Limitation of Liability Redline
                </div>
                <div>
                  "Except with respect to gross negligence or willful misconduct,{' '}
                  <span className="diff-deleted" title="Proposed for Deletion">
                    in no event shall Provider's total aggregate liability under this agreement exceed five hundred dollars ($500.00)
                  </span>
                  {' '}
                  <span className="diff-inserted" title="Recommended Insertion">
                    Provider's total aggregate liability arising out of or related to this agreement shall be capped at the total amount of fees paid by Customer during the twelve (12) months preceding the incident
                  </span>
                  ."
                </div>
                <div style={{ display: 'flex', gap: '16px', marginTop: '12px', fontSize: '11px', color: '#64748b' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ width: '8px', height: '8px', background: '#991b1b', borderRadius: '2px' }}></span>
                    Deleted Text (Strikethrough, #fff1f2)
                  </span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ width: '8px', height: '8px', background: '#10b981', borderRadius: '2px' }}></span>
                    Inserted Text (1px Baseline, #ecfdf5)
                  </span>
                </div>
              </div>
            </div>

            {/* 5. Accessible Form Inputs */}
            <div id="forms" style={{ scrollMarginTop: '80px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 600, margin: '0 0 14px 0', letterSpacing: '-0.005em' }}>
                5. Accessible Inputs (13px Font, 1px Border, ⌘K Badge, 16px Checkbox)
              </h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* Input with ⌘K Badge */}
                <div className="form-group">
                  <label htmlFor="search-demo-input" className="form-label">
                    Contract Search &amp; Clause Filter
                  </label>
                  <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                    <input
                      id="search-demo-input"
                      type="text"
                      className="landing-input"
                      placeholder="Search agreement by term or keyword..."
                      defaultValue="Uncapped indemnity obligation"
                      style={{ paddingRight: '48px' }}
                      aria-describedby="search-helper-desc"
                    />
                    <div style={{ position: 'absolute', right: '12px', pointerEvents: 'none' }}>
                      <span className="kbd-badge">⌘K</span>
                    </div>
                  </div>
                  <span id="search-helper-desc" className="form-helper-text">
                    Instant semantic search across all extracted contract provisions.
                  </span>
                </div>

                {/* Default Input with Label and Helper */}
                <div className="form-group">
                  <label htmlFor="contract-title-input" className="form-label">
                    Contract Title / Reference Code
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
                    Human-readable identifier logged in the local audit history.
                  </span>
                </div>

                {/* Error State Input */}
                <div className="form-group">
                  <label htmlFor="contact-email-input" className="form-label">
                    Counsel Notification Email
                  </label>
                  <input
                    id="contact-email-input"
                    type="email"
                    className={`landing-input ${isEmailError ? 'input-error' : ''}`}
                    placeholder="legal-counsel@enterprise.org"
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
                      Risk audit summaries will be dispatched to this inbox.
                    </span>
                  )}
                  {isEmailError && (
                    <div id="email-error-desc" className="form-error-msg" role="alert">
                      <span aria-hidden="true">⚠️</span>
                      <span>Please enter a valid attorney email address containing '@'.</span>
                    </div>
                  )}
                </div>

                {/* 16px Checkbox with Linked Label */}
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
                      I understand ClauseGuard is an analytical assistive tool and does not constitute formal attorney legal advice.
                    </label>
                  </div>
                  <span id="terms-helper" className="form-helper-text" style={{ marginLeft: '26px' }}>
                    Mandatory acknowledgment before executing risk analysis.
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
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', justifyContent: 'center' }}>
            <a href="#analyzer" className="landing-btn landing-btn-primary">
              Upload Your Contract Free
            </a>
            <a href="#design-system" className="landing-btn landing-btn-secondary">
              Explore Design System
            </a>
          </div>
        </section>
      </main>

      {/* Semantic Footer */}
      <footer className="landing-footer" role="contentinfo">
        <div className="landing-footer-inner">
          <div className="landing-footer-badge">
            <span aria-hidden="true">♿</span> WCAG 2.1 AA Standard Verified &bull; 4.5:1 Contrast &bull; 44px Touch Targets
          </div>
          <p style={{ margin: 0 }}>
            &copy; 2026 ClauseGuard Contract Risk Analyzer. Powered by Precision Legal Canvas.
          </p>
          <p style={{ margin: 0, fontSize: '11px', color: '#64748b' }}>
            Educational tool only. Not licensed legal advice. Always review binding legal instruments with qualified legal counsel.
          </p>
        </div>
      </footer>
    </div>
  )
}
