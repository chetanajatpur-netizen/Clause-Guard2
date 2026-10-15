function ErrorBanner({ message, onRetry, onDismiss }) {
  if (!message) return null

  return (
    <div className="error-banner" role="alert" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
      <p className="error-banner-text" style={{ margin: 0 }}>
        <span aria-hidden="true" style={{ marginRight: 'var(--space-xs)' }}>❌</span>
        {message}
      </p>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        {onRetry && (
          <button
            onClick={onRetry}
            className="btn btn-secondary"
            style={{
              padding: '4px 12px',
              fontSize: '12px',
              minHeight: '32px',
              cursor: 'pointer',
            }}
          >
            Retry
          </button>
        )}
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="btn btn-secondary"
            style={{
              padding: '4px 12px',
              fontSize: '12px',
              minHeight: '32px',
              cursor: 'pointer',
            }}
            aria-label="Dismiss error"
          >
            Dismiss
          </button>
        )}
      </div>
    </div>
  )
}

export default ErrorBanner
