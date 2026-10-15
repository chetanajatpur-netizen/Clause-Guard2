import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import UploadBox from '../components/UploadBox'
import Loader from '../components/Loader'
import ErrorBanner from '../components/ErrorBanner'
import ClauseCard from '../components/ClauseCard'
import RiskBadge from '../components/RiskBadge'
import SearchBar from '../components/SearchBar'
import ViewModeToggle from '../components/ViewModeToggle'
import HeatMap from '../components/HeatMap'
import { analyzeContract, searchDocument, getDocument } from '../api/client'

function Analyze() {
  const { id } = useParams()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [searchResults, setSearchResults] = useState(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [viewMode, setViewMode] = useState('lawyer')

  useEffect(() => {
    if (id) {
      loadDocument(id)
    }
  }, [id])

  const loadDocument = async (docId) => {
    setLoading(true)
    setError(null)
    try {
      const data = await getDocument(docId)
      setResult({
        document_id: data.id,
        filename: data.filename,
        char_count: data.char_count,
        risk_summary: data.risk_summary,
        clauses: data.clauses,
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async (file) => {
    setLoading(true)
    setError(null)
    setResult(null)
    setSearchResults(null)
    try {
      const data = await analyzeContract(file)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async (query) => {
    if (!result) return
    setSearchLoading(true)
    try {
      const data = await searchDocument(result.document_id, query)
      setSearchResults(data.results)
    } catch (err) {
      setError(err.message)
    } finally {
      setSearchLoading(false)
    }
  }

  const displayClauses = searchResults || (result ? result.clauses : [])

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: 'var(--space-md)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', marginBottom: '24px' }}>
        <h2 style={{ margin: 0 }}>Analyze Contract</h2>
        {result && (
          <ViewModeToggle viewMode={viewMode} onChange={setViewMode} />
        )}
      </div>

      {!result && !loading && (
        <UploadBox onUpload={handleUpload} loading={loading} />
      )}

      {error && <ErrorBanner message={error} onRetry={() => setError(null)} />}

      {loading && <Loader />}

      {result && !loading && (
        <>
          {/* Summary Strip */}
          <div className="card" style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
              <div>
                <h3 style={{ margin: '0 0 4px 0' }}>{result.filename}</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: 0 }}>
                  <span className="tnum">{result.char_count.toLocaleString()}</span> characters • <span className="tnum">{result.risk_summary.total_clauses}</span> clauses
                </p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
                <RiskBadge level={result.risk_summary.overall_risk} />
                <div style={{ display: 'flex', gap: '12px', fontSize: '13px', fontFamily: 'var(--font-mono)' }}>
                  <span style={{ color: 'var(--risk-high)' }}>⬤ {result.risk_summary.high_count} High</span>
                  <span style={{ color: 'var(--risk-medium)' }}>⬤ {result.risk_summary.medium_count} Med</span>
                  <span style={{ color: 'var(--risk-low)' }}>⬤ {result.risk_summary.low_count} Low</span>
                </div>
              </div>
            </div>
          </div>

          {/* Clause Heat Map (Feature 3) */}
          <HeatMap clauses={result.clauses} />

          {/* Search */}
          <SearchBar onSearch={handleSearch} loading={searchLoading} />

          {searchResults && (() => {
            const top3Results = searchResults.slice(0, 3)
            return (
              <div
                style={{
                  backgroundColor: 'var(--surface-container-low)',
                  border: '1px solid var(--border-delicate)',
                  borderRadius: 'var(--rounded-md)',
                  padding: '10px 14px',
                  marginBottom: '16px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '10px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--on-surface)' }}>
                    Top {top3Results.length} matching clauses highlighted
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    (Non-matching clauses dimmed to 50%)
                  </span>
                  <span
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '11px',
                      color: 'var(--primary)',
                      backgroundColor: 'var(--canvas-pure)',
                      padding: '2px 8px',
                      borderRadius: 'var(--rounded-default)',
                      border: '1px solid var(--border-delicate)',
                    }}
                  >
                    ℹ️ Similarity ranks clauses. It is not a confidence score.
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => setSearchResults(null)}
                  className="btn btn-secondary"
                  style={{ padding: '4px 12px', fontSize: '12px', minHeight: '32px', cursor: 'pointer' }}
                >
                  Clear search
                </button>
              </div>
            )
          })()}

          {/* Clause List (All clauses remain visible; non-matches are dimmed to 50%) */}
          <div>
            {(() => {
              const top3Results = searchResults ? searchResults.slice(0, 3) : []
              const searchMatchMap = new Map()
              top3Results.forEach((r, rank) => {
                if (r.clause_id !== undefined) searchMatchMap.set(r.clause_id, { rank: rank + 1, similarity: r.similarity })
                if (r.position !== undefined) searchMatchMap.set(r.position, { rank: rank + 1, similarity: r.similarity })
              })

              return result.clauses.map((clause, i) => {
                const pos = clause.position !== undefined ? clause.position : i
                const matchInfo = searchResults ? (searchMatchMap.get(clause.id) || searchMatchMap.get(pos)) : null

                return (
                  <ClauseCard
                    key={clause.id || clause.clause_id || i}
                    clause={{
                      ...clause,
                      id: clause.id || clause.clause_id,
                      position: pos,
                      risk_level: clause.risk_level,
                      confidence: clause.confidence || 0,
                    }}
                    viewMode={viewMode}
                    isSearchActive={Boolean(searchResults)}
                    searchMatch={matchInfo}
                  />
                )
              })
            })()}
          </div>

          {/* Upload another */}
          <div style={{ marginTop: '24px' }}>
            <UploadBox onUpload={handleUpload} loading={loading} />
          </div>
        </>
      )}

      {!result && !loading && !error && (
        <p style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: '24px' }}>
          Upload a contract to get started. We'll analyze it for risky clauses.
        </p>
      )}
    </div>
  )
}

export default Analyze
