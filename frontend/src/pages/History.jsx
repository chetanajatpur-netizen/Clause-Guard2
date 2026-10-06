import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Loader from '../components/Loader'
import ErrorBanner from '../components/ErrorBanner'
import RiskBadge from '../components/RiskBadge'
import { getDocuments, deleteDocument } from '../api/client'

function History() {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    fetchDocuments()
  }, [])

  const fetchDocuments = async () => {
    setLoading(true)
    try {
      const data = await getDocuments()
      setDocuments(data.documents)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id, e) => {
    e.stopPropagation()
    if (!confirm('Delete this analysis?')) return
    try {
      await deleteDocument(id)
      setDocuments(docs => docs.filter(d => d.id !== id))
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) return <Loader message="Loading history..." />

  return (
    <div>
      <h2 style={{ marginBottom: '24px' }}>Analysis History</h2>
      {error && <ErrorBanner message={error} onRetry={fetchDocuments} />}
      {documents.length === 0 && !error ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <p style={{ fontSize: '16px', color: 'var(--text-muted)' }}>
            No analyses yet. Upload a contract to get started.
          </p>
        </div>
      ) : (
        <div>
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="card"
              style={{ marginBottom: '12px', cursor: 'pointer' }}
              onClick={() => navigate(`/history/${doc.id}`)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ fontSize: '16px', marginBottom: '4px' }}>{doc.filename}</h3>
                  <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                    {doc.file_type.toUpperCase()} • {doc.char_count.toLocaleString()} chars • {new Date(doc.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <RiskBadge level={doc.overall_risk} />
                  <button
                    className="btn btn-danger"
                    style={{ padding: '6px 12px', fontSize: '12px' }}
                    onClick={(e) => handleDelete(doc.id, e)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default History
