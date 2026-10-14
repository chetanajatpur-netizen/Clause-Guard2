import { useState } from 'react'
import RiskBadge from './RiskBadge'
import ClauseExplanation from './ClauseExplanation'

export default function ClauseCard({ clause }) {
  const [textExpanded, setTextExpanded] = useState(false)
  const [explanationExpanded, setExplanationExpanded] = useState(false)

  // 3px solid left-border accent matching severity
  const leftBorderAccents = {
    High: '#e11d48',    // Critical
    Medium: '#d97706',  // Moderate
    Low: '#16a34a',     // Approved
  }

  const isRisky = clause.risk_level === 'High' || clause.risk_level === 'Medium' || clause.risk_level === 'Low'
  const accentBorderColor = leftBorderAccents[clause.risk_level] || '#e2e8f0'

  const handleCardClick = (e) => {
    // If user clicked inside an interactive button, link, or input, do not toggle explanation
    if (e.target.closest('button') || e.target.closest('a') || e.target.closest('input')) {
      return
    }
    if (isRisky && clause.label !== 'No Clause') {
      setExplanationExpanded((prev) => !prev)
    }
  }

  return (
    <article
      className="clause-card card"
      onClick={handleCardClick}
      style={{
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        borderLeft: `3px solid ${accentBorderColor}`,
        borderRadius: '8px',
        padding: '16px',
        marginBottom: '12px',
        cursor: isRisky && clause.label !== 'No Clause' ? 'pointer' : 'default',
        boxShadow: 'var(--shadow-sm)',
        transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
      }}
      aria-label={`Clause: ${clause.label}, Risk: ${clause.risk_level || 'None'}`}
    >
      {/* Card Header: Type Tag, Risk Badge, Confidence, Risk Score, Uncertainty */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '10px',
          flexWrap: 'wrap',
          gap: '8px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span
            style={{
              backgroundColor: clause.label === 'No Clause' ? '#f1f5f9' : '#e5eeff',
              color: clause.label === 'No Clause' ? '#475569' : '#3525cd',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 600,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.02em',
              textTransform: 'uppercase',
              border: `1px solid ${clause.label === 'No Clause' ? '#e2e8f0' : '#c3c0ff'}`,
            }}
          >
            {clause.label}
          </span>
          <RiskBadge level={clause.risk_level} />
        </div>

        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
          <span
            className="tnum"
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: '#64748b',
              fontWeight: 500,
              backgroundColor: '#f8fafc',
              padding: '2px 6px',
              borderRadius: '4px',
              border: '1px solid #e2e8f0',
            }}
          >
            {(clause.confidence * 100).toFixed(1)}% conf
          </span>

          {clause.risk_score !== null && clause.risk_score !== undefined && (
            <span
              className="tnum"
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                fontWeight: 600,
                color: clause.risk_level === 'High' ? '#9f1239' : clause.risk_level === 'Medium' ? '#92400e' : clause.risk_level === 'Low' ? '#166534' : '#64748b',
                backgroundColor: clause.risk_level === 'High' ? '#fff1f2' : clause.risk_level === 'Medium' ? '#fffbeb' : clause.risk_level === 'Low' ? '#f0fdf4' : '#f8fafc',
                padding: '2px 6px',
                borderRadius: '4px',
                border: `1px solid ${clause.risk_level === 'High' ? '#fecdd3' : clause.risk_level === 'Medium' ? '#fef3c7' : clause.risk_level === 'Low' ? '#dcfce7' : '#e2e8f0'}`,
              }}
            >
              Risk {clause.risk_score}/100
            </span>
          )}

          {clause.uncertainty !== null && clause.uncertainty !== undefined && (() => {
            const level = clause.uncertainty_level || (clause.uncertainty > 0.5 ? 'High' : clause.uncertainty > 0.2 ? 'Medium' : 'Low')
            const color = level === 'High' ? '#9f1239' : level === 'Medium' ? '#92400e' : '#166534'
            const bg = level === 'High' ? '#fff1f2' : level === 'Medium' ? '#fffbeb' : '#f0fdf4'
            const border = level === 'High' ? '#fecdd3' : level === 'Medium' ? '#fef3c7' : '#dcfce7'
            return (
              <span
                className="tnum"
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  fontWeight: 500,
                  color: color,
                  backgroundColor: bg,
                  padding: '2px 6px',
                  borderRadius: '4px',
                  border: `1px solid ${border}`,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '3px',
                }}
                title={`Uncertainty Level: ${level}`}
              >
                <span style={{ fontSize: '7px' }} aria-hidden="true">●</span>
                Uncertainty {(clause.uncertainty * 100).toFixed(0)}%
              </span>
            )
          })()}
        </div>
      </div>

      {/* Raw Contract Legal Text (code-md: JetBrains Mono, 13px, 22px line-height) */}
      <div
        className="clause-text"
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '13px',
          lineHeight: '22px',
          color: '#0f172a',
          letterSpacing: '-0.01em',
          fontVariantNumeric: 'tabular-nums',
          backgroundColor: '#ffffff',
          overflow: textExpanded ? 'visible' : 'hidden',
          maxHeight: textExpanded ? 'none' : '4.6em',
          transition: 'max-height 0.2s ease-out',
          marginBottom: '8px',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {clause.text}
      </div>

      {/* Expand/Collapse Toggle for long clauses */}
      {clause.text.length > 200 && (
        <button
          type="button"
          style={{
            background: 'none',
            border: 'none',
            color: '#3525cd',
            fontSize: '12px',
            fontFamily: 'var(--font-family)',
            cursor: 'pointer',
            padding: '4px 0',
            fontWeight: 600,
            marginBottom: '8px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            minHeight: 'auto',
            boxShadow: 'none',
          }}
          onClick={(e) => {
            e.stopPropagation()
            setTextExpanded(!textExpanded)
          }}
          aria-expanded={textExpanded}
        >
          {textExpanded ? 'Show less text ↑' : 'Show full legal text ↓'}
        </button>
      )}

      {/* AI Legal Explanation & Negotiation Tips */}
      <ClauseExplanation
        clauseLabel={clause.label}
        isExpanded={explanationExpanded}
        onToggle={() => setExplanationExpanded((prev) => !prev)}
      />
    </article>
  )
}
