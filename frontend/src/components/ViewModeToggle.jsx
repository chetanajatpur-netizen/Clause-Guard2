import React from 'react'

export default function ViewModeToggle({ viewMode, onChange }) {
  return (
    <div
      role="radiogroup"
      aria-label="Perspective view mode"
      className="view-mode-toggle"
      style={{
        display: 'inline-flex',
        backgroundColor: 'var(--surface-container-low)',
        border: '1px solid var(--border-delicate)',
        borderRadius: 'var(--rounded-md)',
        padding: '3px',
        gap: '4px',
        marginBottom: '16px',
        maxWidth: '100%',
        flexWrap: 'wrap',
      }}
    >
      <button
        type="button"
        role="radio"
        aria-checked={viewMode === 'lawyer'}
        onClick={() => onChange('lawyer')}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '6px',
          padding: '8px 14px',
          fontSize: '12px',
          fontWeight: 600,
          fontFamily: 'var(--font-family)',
          borderRadius: 'var(--rounded-default)',
          border: 'none',
          cursor: 'pointer',
          backgroundColor: viewMode === 'lawyer' ? 'var(--canvas-pure)' : 'transparent',
          color: viewMode === 'lawyer' ? 'var(--on-surface)' : 'var(--text-muted)',
          boxShadow: viewMode === 'lawyer' ? 'var(--shadow-sm)' : 'none',
          minHeight: 'var(--touch-target-min)',
          transition: 'all 0.15s ease',
        }}
      >
        <span aria-hidden="true">⚖️</span>
        <span>Lawyer view</span>
      </button>

      <button
        type="button"
        role="radio"
        aria-checked={viewMode === 'plain'}
        onClick={() => onChange('plain')}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '6px',
          padding: '8px 14px',
          fontSize: '12px',
          fontWeight: 600,
          fontFamily: 'var(--font-family)',
          borderRadius: 'var(--rounded-default)',
          border: 'none',
          cursor: 'pointer',
          backgroundColor: viewMode === 'plain' ? 'var(--canvas-pure)' : 'transparent',
          color: viewMode === 'plain' ? 'var(--on-surface)' : 'var(--text-muted)',
          boxShadow: viewMode === 'plain' ? 'var(--shadow-sm)' : 'none',
          minHeight: 'var(--touch-target-min)',
          transition: 'all 0.15s ease',
        }}
      >
        <span aria-hidden="true">💡</span>
        <span>Plain English</span>
      </button>
    </div>
  )
}
