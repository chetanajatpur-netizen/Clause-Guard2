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
      className: 'badge badge-high',
      border: 'var(--risk-high-border)',
      glow: 'var(--glow-high)',
      label: 'High Risk',
    },
    Medium: {
      className: 'badge badge-medium',
      border: 'var(--risk-medium-border)',
      glow: 'var(--glow-medium)',
      label: 'Medium Risk',
    },
    Low: {
      className: 'badge badge-low',
      border: 'var(--risk-low-border)',
      glow: 'var(--glow-low)',
      label: 'Low Risk',
    },
  }

  const config = badgeConfig[level] || badgeConfig.Low

  return (
    <span
      className={`risk-badge ${config.className}`}
      style={{
        boxShadow: config.glow,
        border: `1px solid ${config.border}`,
      }}
    >
      {config.label}
    </span>
  )
}

export default RiskBadge
