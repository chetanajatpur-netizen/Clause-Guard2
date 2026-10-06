function ErrorBanner({ message, onRetry }) {
  return (
    <div style={{
      background: 'var(--risk-high-bg)',
      border: '1px solid var(--risk-high)',
      borderRadius: 'var(--radius-sm)',
      padding: '16px 20px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: '12px',
      marginBottom: '16px',
    }}>
      <p style={{ color: 'var(--risk-high)', fontSize: '14px', fontWeight: 500 }}>
        ❌ {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="btn"
          style={{
            background: 'var(--risk-high)',
            color: 'white',
            padding: '6px 14px',
            fontSize: '13px',
          }}
        >
          Retry
        </button>
      )}
    </div>
  )
}

export default ErrorBanner
