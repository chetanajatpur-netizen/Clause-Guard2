import React from 'react'

function RiskBadge({ level }) {
  if (!level) {
    return (
      <span className="risk-badge badge badge-none">
        No Risk
      </span>
    )
  }

  const badgeConfig = {
    High: {
      className: 'badge badge-critical',
      glyph: '●',
      label: 'Critical Risk',
      border: 'var(--risk-critical-border)',
      bg: 'var(--risk-critical-bg)',
      color: 'var(--risk-critical-text)',
    },
    Medium: {
      className: 'badge badge-moderate',
      glyph: '●',
      label: 'Moderate Risk',
      border: 'var(--risk-moderate-border)',
      bg: 'var(--risk-moderate-bg)',
      color: 'var(--risk-moderate-text)',
    },
    Low: {
      className: 'badge badge-compliant',
      glyph: '✓',
      label: 'Approved',
      border: 'var(--risk-clean-border)',
      bg: 'var(--risk-clean-bg)',
      color: 'var(--risk-clean-text)',
    },
  }

  const config = badgeConfig[level] || badgeConfig.Low

  return (
    <span
      className={`risk-badge ${config.className}`}
      style={{
        backgroundColor: config.bg,
        border: `1px solid ${config.border}`,
        color: config.color,
      }}
    >
      <span aria-hidden="true" style={{ fontSize: '9px', lineHeight: 1 }}>{config.glyph}</span>
      <span>{config.label}</span>
    </span>
  )
}

export default RiskBadge
