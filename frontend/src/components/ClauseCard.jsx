import { useState } from 'react'
import RiskBadge from './RiskBadge'

function ClauseCard({ clause }) {
  const [expanded, setExpanded] = useState(false)

  const riskColors = {
    High: 'var(--risk-high)',
    Medium: 'var(--risk-medium)',
    Low: 'var(--risk-low)',
  }

  const borderColor = riskColors[clause.risk_level] || 'var(--neutral-chip)'

  return (
    <div
      className="clause-card card"
      style={{
        borderLeft: `4px solid ${borderColor}`,
        marginBottom: '12px',
        cursor: 'pointer',
      }}
      onClick={() => setExpanded(!expanded)}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span
            style={{
              background: clause.label === 'No Clause' ? 'var(--neutral-chip)' : 'var(--primary)',
              color: clause.label === 'No Clause' ? 'var(--text)' : 'white',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '12px',
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
          }}
        >
          {(clause.confidence * 100).toFixed(1)}%
        </span>
      </div>
      <p
        style={{
          fontSize: '14px',
          color: 'var(--text)',
          lineHeight: 1.6,
          overflow: expanded ? 'visible' : 'hidden',
          maxHeight: expanded ? 'none' : '4.8em',
          transition: 'max-height 0.3s ease',
        }}
      >
        {clause.text}
      </p>
      {clause.text.length > 200 && (
        <button
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--primary)',
            fontSize: '13px',
            cursor: 'pointer',
            padding: '4px 0',
            fontWeight: 500,
          }}
          onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}
        >
          {expanded ? 'Show less ↑' : 'Show more ↓'}
        </button>
      )}
    </div>
  )
}

export default ClauseCard
