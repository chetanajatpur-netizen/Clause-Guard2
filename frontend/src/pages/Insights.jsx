import { useState, useEffect } from 'react'
import Loader from '../components/Loader'
import ErrorBanner from '../components/ErrorBanner'
import { getInsights } from '../api/client'

function Insights() {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchInsights()
  }, [])

  const fetchInsights = async () => {
    setLoading(true)
    try {
      const data = await getInsights()
      setMetrics(data.metrics)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <Loader message="Loading insights..." />

  const baseline = metrics?.baseline?.test || {}
  const legalBert = metrics?.legal_bert?.test || {}

  return (
    <div>
      <h2 style={{ marginBottom: '24px' }}>Model Insights</h2>
      {error && <ErrorBanner message={error} onRetry={fetchInsights} />}

      {metrics && Object.keys(metrics).length > 0 ? (
        <>
          {/* Comparison Table */}
          <div className="card" style={{ marginBottom: '24px' }}>
            <h3 style={{ marginBottom: '16px' }}>Model Comparison (Test Set)</h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  <th style={{ textAlign: 'left', padding: '12px 8px', color: 'var(--text-muted)' }}>Metric</th>
                  <th style={{ textAlign: 'right', padding: '12px 8px', color: 'var(--text-muted)' }}>Baseline</th>
                  <th style={{ textAlign: 'right', padding: '12px 8px', color: 'var(--text-muted)' }}>Legal-BERT</th>
                  <th style={{ textAlign: 'right', padding: '12px 8px', color: 'var(--text-muted)' }}>Δ</th>
                </tr>
              </thead>
              <tbody>
                {['accuracy', 'macro_f1', 'macro_precision', 'macro_recall'].map((metric) => {
                  const b = baseline[metric] || 0
                  const l = legalBert[metric] || 0
                  const delta = l - b
                  return (
                    <tr key={metric} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '10px 8px', fontWeight: 500 }}>{metric.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}</td>
                      <td style={{ padding: '10px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{(b * 100).toFixed(1)}%</td>
                      <td style={{ padding: '10px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{(l * 100).toFixed(1)}%</td>
                      <td style={{ padding: '10px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', color: delta > 0 ? 'var(--risk-low)' : delta < 0 ? 'var(--risk-high)' : 'var(--text-muted)' }}>
                        {delta > 0 ? '+' : ''}{(delta * 100).toFixed(1)}%
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Per-class metrics for Legal-BERT */}
          {legalBert.per_class && (
            <div className="card" style={{ marginBottom: '24px' }}>
              <h3 style={{ marginBottom: '16px' }}>Per-Class Performance (Legal-BERT)</h3>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border)' }}>
                    <th style={{ textAlign: 'left', padding: '12px 8px', color: 'var(--text-muted)' }}>Class</th>
                    <th style={{ textAlign: 'right', padding: '12px 8px', color: 'var(--text-muted)' }}>Precision</th>
                    <th style={{ textAlign: 'right', padding: '12px 8px', color: 'var(--text-muted)' }}>Recall</th>
                    <th style={{ textAlign: 'right', padding: '12px 8px', color: 'var(--text-muted)' }}>F1</th>
                    <th style={{ textAlign: 'right', padding: '12px 8px', color: 'var(--text-muted)' }}>Support</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(legalBert.per_class)
                    .sort(([, a], [, b]) => (b.f1 || 0) - (a.f1 || 0))
                    .map(([className, m]) => (
                      <tr key={className} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '10px 8px', fontWeight: 500 }}>{className}</td>
                        <td style={{ padding: '10px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{((m.precision || 0) * 100).toFixed(1)}%</td>
                        <td style={{ padding: '10px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{((m.recall || 0) * 100).toFixed(1)}%</td>
                        <td style={{ padding: '10px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{((m.f1 || 0) * 100).toFixed(1)}%</td>
                        <td style={{ padding: '10px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{m.support || 0}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Confusion Matrix Image */}
          <div className="card">
            <h3 style={{ marginBottom: '16px' }}>Confusion Matrix</h3>
            <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: '300px' }}>
                <h4 style={{ fontSize: '14px', color: 'var(--text-muted)', marginBottom: '8px' }}>Legal-BERT</h4>
                <img
                  src="/api/v1/static/confusion_matrix_legal_bert.png"
                  alt="Legal-BERT Confusion Matrix"
                  style={{ width: '100%', borderRadius: 'var(--radius-sm)' }}
                  onError={(e) => { e.target.style.display = 'none' }}
                />
              </div>
              <div style={{ flex: 1, minWidth: '300px' }}>
                <h4 style={{ fontSize: '14px', color: 'var(--text-muted)', marginBottom: '8px' }}>Baseline</h4>
                <img
                  src="/api/v1/static/confusion_matrix_baseline.png"
                  alt="Baseline Confusion Matrix"
                  style={{ width: '100%', borderRadius: 'var(--radius-sm)' }}
                  onError={(e) => { e.target.style.display = 'none' }}
                />
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <p style={{ fontSize: '16px', color: 'var(--text-muted)' }}>
            No model metrics available yet. Train the models first.
          </p>
        </div>
      )}
    </div>
  )
}

export default Insights
