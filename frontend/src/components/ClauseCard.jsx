import { useState, useEffect } from 'react'
import RiskBadge from './RiskBadge'
import ClauseExplanation from './ClauseExplanation'
import explanations from '../data/clause_explanations.json'

export default function ClauseCard({
  clause,
  viewMode = 'lawyer',
  isSearchActive = false,
  searchMatch = null,
}) {
  const [textExpanded, setTextExpanded] = useState(false)
  const [explanationExpanded, setExplanationExpanded] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)

  const hasSpeech = typeof window !== 'undefined' && 'speechSynthesis' in window

  // Clean up any ongoing speech synthesis on unmount
  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

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

  const handleReadAloud = (e) => {
    e.stopPropagation()
    if (!hasSpeech) return

    if (isSpeaking) {
      window.speechSynthesis.cancel()
      setIsSpeaking(false)
      return
    }

    window.speechSynthesis.cancel()

    const explanationInfo = explanations.clauses[clause.label] || explanations.clauses['No Clause']
    // Read the plain_note from legal layer, or summary, or why_risky, or clause text
    const plainNote =
      clause.legal?.plain_note ||
      explanationInfo?.summary ||
      explanationInfo?.why_risky ||
      (clause.label !== 'No Clause' ? `${clause.label}. ${clause.text}` : clause.text)

    const utterance = new SpeechSynthesisUtterance(plainNote)
    utterance.onend = () => setIsSpeaking(false)
    utterance.onerror = () => setIsSpeaking(false)

    setIsSpeaking(true)
    window.speechSynthesis.speak(utterance)
  }

  // Render the explanation block
  const explanationComponent = (
    <div style={{ marginBottom: viewMode === 'plain' ? '12px' : '0' }}>
      <ClauseExplanation
        clauseLabel={clause.label}
        isExpanded={viewMode === 'plain' ? true : explanationExpanded}
        onToggle={() => setExplanationExpanded((prev) => !prev)}
      />
    </div>
  )

  // Render the raw legal contract text block
  const clauseTextComponent = (
    <div style={{ marginTop: viewMode === 'plain' ? '8px' : '0' }}>
      {viewMode === 'plain' && (
        <div
          style={{
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            textTransform: 'uppercase',
            color: 'var(--text-muted)',
            marginBottom: '4px',
            letterSpacing: '0.03em',
          }}
        >
          Original Contract Clause:
        </div>
      )}
      <div
        className="clause-text"
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '13px',
          lineHeight: '22px',
          color: 'var(--text-primary)',
          letterSpacing: '-0.01em',
          fontVariantNumeric: 'tabular-nums',
          backgroundColor: viewMode === 'plain' ? 'var(--surface-subtle-1)' : '#ffffff',
          padding: viewMode === 'plain' ? '8px 12px' : '0',
          borderRadius: viewMode === 'plain' ? 'var(--rounded-md)' : '0',
          border: viewMode === 'plain' ? '1px solid var(--border-delicate)' : 'none',
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

      {clause.text.length > 200 && (
        <button
          type="button"
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--primary)',
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
    </div>
  )

  return (
    <article
      id={`clause-${clause.position !== undefined ? clause.position : clause.id}`}
      tabIndex={-1}
      className={`clause-card card ${searchMatch ? 'search-match-top' : ''}`}
      onClick={handleCardClick}
      style={{
        scrollMarginTop: '100px',
        backgroundColor: '#ffffff',
        border: searchMatch ? '1px solid var(--primary-container)' : '1px solid var(--border-delicate)',
        borderLeft: searchMatch ? '5px solid var(--primary-container)' : `3px solid ${accentBorderColor}`,
        borderRadius: 'var(--rounded-lg)',
        padding: '16px',
        marginBottom: '12px',
        cursor: isRisky && clause.label !== 'No Clause' ? 'pointer' : 'default',
        boxShadow: searchMatch ? '0 4px 12px rgba(79, 70, 229, 0.15)' : 'var(--shadow-sm)',
        opacity: isSearchActive ? (searchMatch ? 1 : 0.5) : 1,
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease, transform 0.2s ease',
        transform: searchMatch ? 'scale(1.002)' : 'none',
      }}
      aria-label={`Clause: ${clause.label}, Risk: ${clause.risk_level || 'None'}${searchMatch ? `, Search match rank ${searchMatch.rank}` : ''}`}
    >
      {/* Search Result Highlight: Similarity Bar with numerical score (Feature 4) */}
      {searchMatch && (
        <div
          className="search-similarity-bar"
          style={{
            backgroundColor: 'var(--surface-container-low)',
            border: '1px solid var(--border-delicate)',
            borderRadius: 'var(--rounded-md)',
            padding: '8px 12px',
            marginBottom: '12px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px', flexWrap: 'wrap', gap: '4px' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--primary)', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>🎯</span>
              <span>Top Match #{searchMatch.rank}</span>
              <span>•</span>
              <span className="tnum">{(searchMatch.similarity * 100).toFixed(1)}% Similarity</span>
            </span>
            <span className="tnum" style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              Similarity: {searchMatch.similarity.toFixed(4)}
            </span>
          </div>
          <div
            style={{
              width: '100%',
              height: '6px',
              borderRadius: '9999px',
              backgroundColor: 'var(--surface-subtle-2)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${Math.min(100, Math.max(5, searchMatch.similarity * 100))}%`,
                height: '100%',
                backgroundColor: 'var(--primary-container)',
                borderRadius: '9999px',
                transition: 'width 0.3s ease',
              }}
            />
          </div>
        </div>
      )}

      {/* Card Header: Type Tag, Risk Badge, Read-Aloud, Confidence, Risk Score, Uncertainty */}
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
              backgroundColor: clause.label === 'No Clause' ? 'var(--surface-subtle-2)' : 'var(--surface-container)',
              color: clause.label === 'No Clause' ? 'var(--text-secondary)' : 'var(--primary)',
              padding: '2px 8px',
              borderRadius: 'var(--rounded-default)',
              fontSize: '11px',
              fontWeight: 600,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.02em',
              textTransform: 'uppercase',
              border: `1px solid ${clause.label === 'No Clause' ? 'var(--border-delicate)' : 'var(--inverse-primary)'}`,
            }}
          >
            {clause.label}
          </span>
          <RiskBadge level={clause.risk_level} />

          {/* Read Aloud Button (Feature 7) */}
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleReadAloud}
            disabled={!hasSpeech}
            style={{
              padding: '2px 8px',
              fontSize: '11px',
              fontWeight: 600,
              fontFamily: 'var(--font-family)',
              minHeight: '28px',
              borderRadius: 'var(--rounded-default)',
              backgroundColor: isSpeaking ? 'var(--surface-container)' : 'var(--canvas-pure)',
              color: isSpeaking ? 'var(--primary)' : 'var(--on-surface)',
              border: `1px solid ${isSpeaking ? 'var(--primary)' : 'var(--border-delicate)'}`,
              gap: '4px',
            }}
            title={!hasSpeech ? 'Speech synthesis unavailable on this device' : isSpeaking ? 'Stop speaking' : 'Read plain English explanation aloud'}
            aria-label={isSpeaking ? `Stop reading ${clause.label} explanation aloud` : `Read ${clause.label} explanation aloud`}
          >
            <span aria-hidden="true">{isSpeaking ? '⏹' : '🔊'}</span>
            <span>{isSpeaking ? 'Stop' : 'Read aloud'}</span>
          </button>
        </div>

        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
          <span
            className="tnum"
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--text-muted)',
              fontWeight: 500,
              backgroundColor: 'var(--surface-subtle-1)',
              padding: '2px 6px',
              borderRadius: 'var(--rounded-default)',
              border: '1px solid var(--border-delicate)',
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
                color: clause.risk_level === 'High' ? 'var(--risk-critical-text)' : clause.risk_level === 'Medium' ? 'var(--risk-moderate-text)' : clause.risk_level === 'Low' ? 'var(--risk-clean-text)' : 'var(--text-muted)',
                backgroundColor: clause.risk_level === 'High' ? 'var(--risk-critical-bg)' : clause.risk_level === 'Medium' ? 'var(--risk-moderate-bg)' : clause.risk_level === 'Low' ? 'var(--risk-clean-bg)' : 'var(--surface-subtle-1)',
                padding: '2px 6px',
                borderRadius: 'var(--rounded-default)',
                border: `1px solid ${clause.risk_level === 'High' ? 'var(--risk-critical-border)' : clause.risk_level === 'Medium' ? 'var(--risk-moderate-border)' : clause.risk_level === 'Low' ? 'var(--risk-clean-border)' : 'var(--border-delicate)'}`,
              }}
            >
              Risk {clause.risk_score}/100
            </span>
          )}

          {clause.uncertainty !== null && clause.uncertainty !== undefined && (() => {
            const level = clause.uncertainty_level || (clause.uncertainty > 0.5 ? 'High' : clause.uncertainty > 0.2 ? 'Medium' : 'Low')
            const color = level === 'High' ? 'var(--risk-critical-text)' : level === 'Medium' ? 'var(--risk-moderate-text)' : 'var(--risk-clean-text)'
            const bg = level === 'High' ? 'var(--risk-critical-bg)' : level === 'Medium' ? 'var(--risk-moderate-bg)' : 'var(--risk-clean-bg)'
            const border = level === 'High' ? 'var(--risk-critical-border)' : level === 'Medium' ? 'var(--risk-moderate-border)' : 'var(--risk-clean-border)'
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
                  borderRadius: 'var(--rounded-default)',
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

      {/* When viewMode === 'plain', explanation card is placed ABOVE clause text */}
      {viewMode === 'plain' ? (
        <>
          {explanationComponent}
          {clauseTextComponent}
        </>
      ) : (
        <>
          {clauseTextComponent}
          {explanationComponent}
        </>
      )}
    </article>
  )
}
