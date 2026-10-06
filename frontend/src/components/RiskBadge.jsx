function RiskBadge({ level }) {
  if (!level) return <span className="risk-badge risk-badge--none">No Risk</span>

  const styles = {
    High: { bg: 'var(--risk-high-bg)', color: 'var(--risk-high)', label: 'High Risk' },
    Medium: { bg: 'var(--risk-medium-bg)', color: 'var(--risk-medium)', label: 'Medium Risk' },
    Low: { bg: 'var(--risk-low-bg)', color: 'var(--risk-low)', label: 'Low Risk' },
  }

  const s = styles[level] || styles.Low

  return (
    <span
      className="risk-badge"
      style={{
        display: 'inline-block',
        padding: '4px 12px',
        borderRadius: '20px',
        fontSize: '13px',
        fontWeight: 600,
        background: s.bg,
        color: s.color,
      }}
    >
      {s.label}
    </span>
  )
}

export default RiskBadge
