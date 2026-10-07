function ErrorBanner({ message, onRetry }) {
  if (!message) return null

  return (
    <div className="error-banner" role="alert">
      <p className="error-banner-text">
        <span aria-hidden="true" style={{ marginRight: 'var(--space-xs)' }}>❌</span>
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="btn btn-danger"
          style={{
            padding: 'var(--space-xs) var(--space-md)',
            fontSize: '14px',
            minHeight: 'var(--touch-target-min)',
            cursor: 'pointer',
          }}
        >
          Retry
        </button>
      )}
    </div>
  )
}

export default ErrorBanner
