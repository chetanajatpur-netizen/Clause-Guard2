import React, { useState } from 'react'

export default function HeatMap({ clauses = [] }) {
  const [hoveredClause, setHoveredClause] = useState(null)

  if (!clauses || clauses.length === 0) {
    return null
  }

  // Calculate total characters to size segments proportionally to clause length
  const totalChars = clauses.reduce((acc, c) => acc + (c.text?.length || 100), 0) || 1

  const scrollToClause = (position) => {
    const el = document.getElementById(`clause-${position}`)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      // Brief focus outline ring to orient the user
      el.style.outline = '3px solid var(--primary-container)'
      el.style.outlineOffset = '2px'
      setTimeout(() => {
        el.style.outline = ''
        el.style.outlineOffset = ''
      }, 1600)
    }
  }

  const getSegmentStyle = (clause) => {
    const level = clause.risk_level
    if (level === 'High') {
      return {
        // High risk gets solid base + diagonal hatched stripes so it is not color alone
        background: 'repeating-linear-gradient(45deg, #e11d48, #e11d48 4px, #9f1239 4px, #9f1239 8px)',
        borderRight: '1px solid #ffffff',
      }
    }
    if (level === 'Medium') {
      return {
        backgroundColor: 'var(--risk-moderate-accent)',
        borderRight: '1px solid #ffffff',
      }
    }
    if (level === 'Low') {
      return {
        backgroundColor: 'var(--risk-clean-accent)',
        borderRight: '1px solid #ffffff',
      }
    }
    return {
      backgroundColor: 'var(--border-subtle)',
      borderRight: '1px solid #ffffff',
    }
  }

  return (
    <section
      aria-label="Contract clause risk heat map"
      className="heatmap-container"
      style={{
        backgroundColor: 'var(--canvas-pure)',
        border: '1px solid var(--border-delicate)',
        borderRadius: 'var(--rounded-lg)',
        padding: '16px',
        marginBottom: '20px',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      {/* Header and Legend */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          marginBottom: '10px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--on-surface)' }}>
            Clause Risk Heat Map
          </span>
          <span
            className="tnum"
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--text-muted)',
              backgroundColor: 'var(--surface-subtle-1)',
              padding: '1px 6px',
              borderRadius: 'var(--rounded-default)',
              border: '1px solid var(--border-delicate)',
            }}
          >
            {clauses.length} segments
          </span>
        </div>

        {/* Legend */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '14px',
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span
              style={{
                width: '12px',
                height: '10px',
                borderRadius: '2px',
                background: 'repeating-linear-gradient(45deg, #e11d48, #e11d48 2px, #9f1239 2px, #9f1239 4px)',
                display: 'inline-block',
              }}
              aria-hidden="true"
            />
            <span style={{ color: 'var(--risk-critical-text)', fontWeight: 600 }}>Critical (Hatched)</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '2px',
                backgroundColor: 'var(--risk-moderate-accent)',
                display: 'inline-block',
              }}
              aria-hidden="true"
            />
            <span style={{ color: 'var(--risk-moderate-text)', fontWeight: 600 }}>Moderate</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '2px',
                backgroundColor: 'var(--risk-clean-accent)',
                display: 'inline-block',
              }}
              aria-hidden="true"
            />
            <span style={{ color: 'var(--risk-clean-text)', fontWeight: 600 }}>Approved</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '2px',
                backgroundColor: 'var(--border-subtle)',
                display: 'inline-block',
              }}
              aria-hidden="true"
            />
            <span style={{ color: 'var(--text-muted)' }}>Standard</span>
          </div>
        </div>
      </div>

      {/* Interactive Proportional Strip */}
      <div
        role="group"
        aria-label="Clause navigation strip"
        style={{
          display: 'flex',
          width: '100%',
          height: '32px',
          borderRadius: 'var(--rounded-md)',
          overflow: 'visible',
          backgroundColor: 'var(--surface-subtle-2)',
          border: '1px solid var(--border-delicate)',
        }}
      >
        {clauses.map((clause, index) => {
          const position = clause.position !== undefined ? clause.position : index
          const len = clause.text?.length || 100
          // Width proportional to length, with minimum 1.5% so tiny clauses remain clickable
          const widthPct = Math.max(1.5, (len / totalChars) * 100)
          const style = getSegmentStyle(clause)
          const isHovered = hoveredClause?.position === position

          return (
            <button
              key={clause.id || position}
              type="button"
              className="heatmap-segment"
              onClick={() => scrollToClause(position)}
              onMouseEnter={() => setHoveredClause({ ...clause, position })}
              onMouseLeave={() => setHoveredClause(null)}
              onFocus={() => setHoveredClause({ ...clause, position })}
              onBlur={() => setHoveredClause(null)}
              aria-label={`Clause ${position + 1}, ${clause.label}, ${clause.risk_level || 'No'} risk`}
              title={`Clause ${position + 1}: ${clause.label} • ${clause.risk_level ? `${clause.risk_level} Risk` : 'Standard'} (${(clause.confidence * 100).toFixed(0)}% conf)`}
              style={{
                ...style,
                width: `${widthPct}%`,
                height: '100%',
                padding: 0,
                margin: 0,
                cursor: 'pointer',
                opacity: isHovered ? 1 : 0.88,
                transform: isHovered ? 'translateY(-2px)' : 'none',
                transformOrigin: 'bottom',
                transition: 'transform var(--dur-fast, 150ms) var(--ease-emphasis), box-shadow var(--dur-fast, 150ms) var(--ease-standard), opacity var(--dur-fast, 150ms) var(--ease-standard)',
                position: 'relative',
                boxShadow: isHovered ? '0 6px 16px -2px rgba(15, 23, 42, 0.25), 0 0 0 2px var(--primary-container)' : 'none',
                zIndex: isHovered ? 10 : 1,
              }}
            />
          )
        })}
      </div>

      {/* Active Inspector / Tooltip Bar */}
      <div
        style={{
          minHeight: '26px',
          marginTop: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '12px',
          color: 'var(--text-secondary)',
          fontFamily: 'var(--font-mono)',
        }}
        aria-live="polite"
      >
        {hoveredClause ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
              Clause #{hoveredClause.position + 1}:
            </span>
            <span style={{ color: 'var(--primary)', fontWeight: 600 }}>
              {hoveredClause.label}
            </span>
            <span>•</span>
            <span
              style={{
                color:
                  hoveredClause.risk_level === 'High'
                    ? 'var(--risk-critical-text)'
                    : hoveredClause.risk_level === 'Medium'
                    ? 'var(--risk-moderate-text)'
                    : hoveredClause.risk_level === 'Low'
                    ? 'var(--risk-clean-text)'
                    : 'var(--text-muted)',
                fontWeight: 600,
              }}
            >
              {hoveredClause.risk_level ? `${hoveredClause.risk_level} Risk` : 'Standard'}
            </span>
            <span>•</span>
            <span className="tnum">
              {(hoveredClause.confidence * 100).toFixed(1)}% confidence
            </span>
            {hoveredClause.risk_score !== null && hoveredClause.risk_score !== undefined && (
              <>
                <span>•</span>
                <span className="tnum">Score: {hoveredClause.risk_score}/100</span>
              </>
            )}
          </div>
        ) : (
          <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
            Hover or press Tab to inspect clauses. Click or press Enter to scroll to clause text.
          </span>
        )}

        <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>
          Width ∝ Clause Length
        </span>
      </div>
    </section>
  )
}
