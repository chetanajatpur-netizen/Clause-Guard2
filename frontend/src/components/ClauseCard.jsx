import { useState } from 'react'
import RiskBadge from './RiskBadge'
import ClauseExplanation from './ClauseExplanation'

export default function ClauseCard({ clause }) {
  const [textExpanded, setTextExpanded] = useState(false)
  const [explanationExpanded, setExplanationExpanded] = useState(false)

  const riskColors = {
    High: 'var(--risk-high)',
    Medium: 'var(--risk-medium)',
    Low: 'var(--risk-low)',
  }

  const isRisky = clause.risk_level === 'High' || clause.risk_level === 'Medium' || clause.risk_level === 'Low'
  const borderColor = riskColors[clause.risk_level] || 'var(--neutral-chip)'

  const handleCardClick = (e) => {
    // If user clicked inside an interactive button or link, let it handle its own event
    if (e.target.closest('button') || e.target.closest('a')) {
      return
    }
    if (isRisky && clause.label !== 'No Clause') {
      setExplanationExpanded((prev) => !prev)
    }
  }

  return (
    <div
      className={`clause-card card ${isRisky ? 'clause-card--risky' : ''}`}
      onClick={handleCardClick}
      style={{
        borderLeft: `4px solid ${borderColor}`,
        marginBottom: 'var(--space-md)',
        cursor: isRisky && clause.label !== 'No Clause' ? 'pointer' : 'default',
        padding: 'var(--space-lg)',
      }}
    >
      {/* Card Header: Label, RiskBadge, Confidence */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 'var(--space-sm)',
          flexWrap: 'wrap',
          gap: 'var(--space-xs)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
          <span
            style={{
              background: clause.label === 'No Clause' ? 'var(--neutral-chip)' : 'var(--primary)',
              color: clause.label === 'No Clause' ? 'var(--text)' : 'var(--primary-contrast)',
              padding: '4px 10px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '13px',
              fontWeight: 600,
            }}
          >
            {clause.label}
          </span>
          <RiskBadge level={clause.risk_level} />
        </div>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '13px',
            color: 'var(--text-muted)',
            fontWeight: 500,
          }}
        >
          {(clause.confidence * 100).toFixed(1)}% confidence
        </span>
      </div>

      {/* Clause Contract Text */}
      <p
        className="clause-text"
        style={{
          fontSize: '15px',
          color: 'var(--text)',
          lineHeight: 1.6,
          overflow: textExpanded ? 'visible' : 'hidden',
          maxHeight: textExpanded ? 'none' : '4.8em',
          transition: 'max-height 0.25s ease',
          marginBottom: 'var(--space-sm)',
          whiteSpace: 'pre-line',
        }}
      >
        {clause.text}
      </p>

      {/* Show more/less for long clauses */}
      {clause.text.length > 200 && (
        <button
          type="button"
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--primary)',
            fontSize: '14px',
            cursor: 'pointer',
            padding: 'var(--space-2xs) 0',
            fontWeight: 600,
            marginBottom: 'var(--space-sm)',
            display: 'inline-block',
          }}
          onClick={(e) => {
            e.stopPropagation()
            setTextExpanded(!textExpanded)
          }}
          aria-expanded={textExpanded}
        >
          {textExpanded ? 'Show less text ↑' : 'Show full clause text ↓'}
        </button>
      )}

      {/* AI Context Explanation */}
      <ClauseExplanation
        clauseLabel={clause.label}
        isExpanded={explanationExpanded}
        onToggle={() => setExplanationExpanded((prev) => !prev)}
      />
    </div>
  )
}
