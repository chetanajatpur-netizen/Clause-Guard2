import React, { useState, useEffect, useRef } from 'react'
import {
  analyzeContract,
  searchDocument,
  getClauseRedline,
  getDocuments,
  getDocument,
  deleteDocument,
  getInsights,
} from '../api/client'
import HeatMap from './HeatMap'
import explanations from '../data/clause_explanations.json'
import '../styles/spatial-cockpit.css'

export default function SpatialCockpit({ liveResult: initialLiveResult }) {
  // Ambient Mouse Spotlight
  const [spotlightPos, setSpotlightPos] = useState({ x: -1000, y: -1000 })
  // Toast notifications
  const [toasts, setToasts] = useState([])

  // View Navigation: 'analyze' | 'history' | 'insights'
  const [currentView, setCurrentView] = useState('analyze')

  // Real Contract Ingestion & Audit States
  const [liveResult, setLiveResult] = useState(initialLiveResult || null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef(null)

  // Natural Language Search inside Audited Contract
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searchLoading, setSearchLoading] = useState(false)

  // Redline Suggestions & Read-Aloud per Clause
  const [clauseRedlines, setClauseRedlines] = useState({})
  const [redlineLoading, setRedlineLoading] = useState({})
  const [speakingIdx, setSpeakingIdx] = useState(null)

  // History State
  const [historyDocs, setHistoryDocs] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState(null)

  // Insights State
  const [insightsMetrics, setInsightsMetrics] = useState(null)
  const [insightsLoading, setInsightsLoading] = useState(false)
  const [insightsError, setInsightsError] = useState(null)

  const showToast = (message, type = 'secondary', icon = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((prev) => [...prev, { id, message, type, icon }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 3500)
  }

  // Mouse move for ambient spotlight
  useEffect(() => {
    const handleMouseMove = (e) => {
      setSpotlightPos({ x: e.clientX, y: e.clientY })
    }
    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  // Clean up any speech on unmount
  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  // Fetch History documents from real API
  const fetchHistory = async () => {
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      const data = await getDocuments()
      setHistoryDocs(data.documents || [])
    } catch (err) {
      setHistoryError(err.message || 'Failed to fetch history')
      showToast(err.message || 'Failed to fetch history', 'error', 'error')
    } finally {
      setHistoryLoading(false)
    }
  }

  // Load a document from history into the audit view
  const handleOpenHistoricalDoc = async (id) => {
    showToast('Loading document audit...', 'secondary', 'hourglass_top')
    try {
      const doc = await getDocument(id)
      setLiveResult(doc)
      setCurrentView('analyze')
      setSearchResults(null)
      setSearchQuery('')
      showToast(`Loaded ${doc.filename}`, 'secondary', 'check_circle')
    } catch (err) {
      showToast(err.message || 'Failed to load document', 'error', 'error')
    }
  }

  // Delete a document from history
  const handleDeleteDoc = async (id, e) => {
    e.stopPropagation()
    if (!window.confirm('Delete this analyzed document?')) return
    try {
      await deleteDocument(id)
      setHistoryDocs((prev) => prev.filter((d) => d.id !== id))
      if (liveResult?.id === id || liveResult?.document_id === id) {
        setLiveResult(null)
      }
      showToast('Document deleted', 'secondary', 'delete')
    } catch (err) {
      showToast(err.message || 'Failed to delete document', 'error', 'error')
    }
  }

  // Fetch Insights from real API
  const fetchInsightsData = async () => {
    setInsightsLoading(true)
    setInsightsError(null)
    try {
      const data = await getInsights()
      setInsightsMetrics(data.metrics || {})
    } catch (err) {
      setInsightsError(err.message || 'Failed to load insights')
      showToast(err.message || 'Failed to load insights', 'error', 'error')
    } finally {
      setInsightsLoading(false)
    }
  }

  const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt']
  const MAX_SIZE_BYTES = 10 * 1024 * 1024

  const validateAndUpload = async (file) => {
    if (!file) return
    setUploadError(null)

    const lowerName = file.name.toLowerCase()
    const isValidExt = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext))
    if (!isValidExt) {
      const err = 'Unsupported file format. Please upload a PDF, DOCX, or TXT file.'
      setUploadError(err)
      showToast(err, 'error', 'error')
      return
    }

    if (file.size > MAX_SIZE_BYTES) {
      const err = 'File exceeds the maximum limit of 10 MB.'
      setUploadError(err)
      showToast(err, 'error', 'error')
      return
    }

    setIsUploading(true)
    showToast(`Uploading and scanning ${file.name}...`, 'secondary', 'cloud_upload')

    try {
      const result = await analyzeContract(file)
      setLiveResult(result)
      setSearchResults(null)
      setSearchQuery('')
      setCurrentView('analyze')
      showToast(
        `Audit Complete: ${result.risk_summary?.total_clauses || 0} clauses classified`,
        'secondary',
        'task_alt'
      )
      setTimeout(() => {
        const resultsEl = document.getElementById('contract-audit-results')
        if (resultsEl) {
          resultsEl.scrollIntoView({ behavior: 'smooth' })
        }
      }, 200)
    } catch (err) {
      const errMsg = err.message || 'Analysis failed. Please check backend status.'
      setUploadError(errMsg)
      showToast(errMsg, 'error', 'error')
    } finally {
      setIsUploading(false)
    }
  }

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndUpload(e.dataTransfer.files[0])
    }
  }

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndUpload(e.target.files[0])
    }
  }

  // Ask-the-Contract Semantic Search Handler
  const handleSearchSubmit = async (e) => {
    e.preventDefault()
    const docId = liveResult?.document_id || liveResult?.id
    if (!docId) {
      showToast('Please upload or select a contract first', 'secondary', 'info')
      return
    }
    if (!searchQuery.trim()) return

    setSearchLoading(true)
    showToast(`Searching for "${searchQuery.trim()}"...`, 'secondary', 'search')

    try {
      const res = await searchDocument(docId, searchQuery.trim(), 5)
      setSearchResults(res.results || [])
      showToast(
        `Found ${res.results?.length || 0} matching clause${res.results?.length === 1 ? '' : 's'}`,
        'secondary',
        'manage_search'
      )
    } catch (err) {
      showToast(err.message || 'Search failed', 'error', 'error')
    } finally {
      setSearchLoading(false)
    }
  }

  const handleClearSearch = () => {
    setSearchQuery('')
    setSearchResults(null)
  }

  // AI Redline Generator Handler
  const handleGetRedline = async (clause, idx) => {
    if (clauseRedlines[idx]) {
      // Toggle off if already showing
      setClauseRedlines((prev) => {
        const copy = { ...prev }
        delete copy[idx]
        return copy
      })
      return
    }

    setRedlineLoading((prev) => ({ ...prev, [idx]: true }))
    try {
      const data = await getClauseRedline(clause.text, clause.label)
      setClauseRedlines((prev) => ({ ...prev, [idx]: data }))
      showToast(`Redline generated for ${clause.label}`, 'secondary', 'draw')
    } catch (err) {
      showToast(err.message || 'Failed to generate redline', 'error', 'error')
    } finally {
      setRedlineLoading((prev) => ({ ...prev, [idx]: false }))
    }
  }

  // Read-Aloud Handler (Web Speech API)
  const handleSpeak = (clause, idx) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      showToast('Speech synthesis not supported in this browser', 'secondary', 'volume_off')
      return
    }

    if (speakingIdx === idx) {
      window.speechSynthesis.cancel()
      setSpeakingIdx(null)
      return
    }

    window.speechSynthesis.cancel()

    const expInfo = explanations[clause.label]
    const textToRead =
      clause.legal?.plain_note ||
      expInfo?.summary ||
      expInfo?.why_risky ||
      `${clause.label}. ${clause.text}`

    const utterance = new SpeechSynthesisUtterance(textToRead)
    utterance.onend = () => setSpeakingIdx(null)
    utterance.onerror = () => setSpeakingIdx(null)

    setSpeakingIdx(idx)
    window.speechSynthesis.speak(utterance)
  }

  return (
    <div className="spatial-cockpit">
      {/* Ambient Mouse Follower Spotlight */}
      <div
        className="sc-spotlight"
        style={{
          left: `${spotlightPos.x}px`,
          top: `${spotlightPos.y}px`,
        }}
      />

      {/* Floating System Toasts */}
      <div
        style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          pointerEvents: 'none',
        }}
        aria-live="polite"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            style={{
              pointerEvents: 'auto',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '10px 16px',
              borderRadius: '12px',
              border:
                t.type === 'error'
                  ? '1px solid rgba(255, 180, 171, 0.4)'
                  : '1px solid rgba(76, 215, 246, 0.4)',
              background: 'rgba(10, 14, 24, 0.95)',
              color: t.type === 'error' ? 'var(--sc-error)' : '#4cd7f6',
              boxShadow: '0 20px 40px rgba(0,0,0,0.8)',
              backdropFilter: 'blur(12px)',
              fontSize: '12px',
              fontFamily: 'JetBrains Mono, monospace',
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
              {t.icon}
            </span>
            <span>{t.message}</span>
          </div>
        ))}
      </div>

      {/* Main Container Wrapper */}
      <div
        style={{
          width: '100%',
          maxWidth: '1480px',
          margin: '0 auto',
          background: 'var(--sc-surface-lowest)',
          border: '1px solid rgba(70, 69, 85, 0.4)',
          borderRadius: '16px',
          overflow: 'hidden',
          boxShadow: '0 20px 60px -15px rgba(0,0,0,0.8)',
          position: 'relative',
          zIndex: 10,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* TopBar / Header */}
        <header
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 24px',
            borderBottom: '1px solid rgba(70, 69, 85, 0.3)',
            background: 'var(--sc-surface-low)',
            flexWrap: 'wrap',
            gap: '16px',
          }}
        >
          {/* Brand Box */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                cursor: 'pointer',
              }}
              onClick={() => setCurrentView('analyze')}
            >
              <div
                style={{
                  background: 'var(--sc-surface-highest)',
                  border: '1px solid rgba(70, 69, 85, 0.4)',
                  color: 'var(--sc-on-surface)',
                  padding: '6px 14px',
                  fontFamily: 'Cinzel, serif',
                  letterSpacing: '0.05em',
                  fontWeight: 700,
                  fontSize: '18px',
                  lineHeight: 1,
                  display: 'flex',
                  alignItems: 'center',
                  borderRadius: '8px',
                }}
              >
                ClauseWise
                <span
                  style={{
                    color: '#4cd7f6',
                    fontFamily: 'sans-serif',
                    marginLeft: '2px',
                    fontSize: '16px',
                  }}
                >
                  .
                </span>
              </div>
              <span
                style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: '11px',
                  color: 'var(--sc-outline)',
                  display: 'none',
                }}
                className="md:inline"
              >
                AI Contract Risk Analyzer
              </span>
            </div>

            {/* View Switcher Tabs: Analyze | History | Insights */}
            <nav
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                background: 'var(--sc-surface-high)',
                padding: '4px',
                borderRadius: '8px',
                border: '1px solid rgba(70, 69, 85, 0.3)',
              }}
              aria-label="Main Navigation"
            >
              <button
                type="button"
                onClick={() => setCurrentView('analyze')}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: currentView === 'analyze' ? 700 : 500,
                  background:
                    currentView === 'analyze'
                      ? 'rgba(76, 215, 246, 0.15)'
                      : 'transparent',
                  color:
                    currentView === 'analyze' ? '#4cd7f6' : 'var(--sc-outline)',
                  border:
                    currentView === 'analyze'
                      ? '1px solid rgba(76, 215, 246, 0.35)'
                      : '1px solid transparent',
                  cursor: 'pointer',
                  minHeight: '44px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
                  description
                </span>
                <span>Analyze</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setCurrentView('history')
                  fetchHistory()
                }}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: currentView === 'history' ? 700 : 500,
                  background:
                    currentView === 'history'
                      ? 'rgba(76, 215, 246, 0.15)'
                      : 'transparent',
                  color:
                    currentView === 'history' ? '#4cd7f6' : 'var(--sc-outline)',
                  border:
                    currentView === 'history'
                      ? '1px solid rgba(76, 215, 246, 0.35)'
                      : '1px solid transparent',
                  cursor: 'pointer',
                  minHeight: '44px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
                  history
                </span>
                <span>History</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setCurrentView('insights')
                  fetchInsightsData()
                }}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: currentView === 'insights' ? 700 : 500,
                  background:
                    currentView === 'insights'
                      ? 'rgba(76, 215, 246, 0.15)'
                      : 'transparent',
                  color:
                    currentView === 'insights' ? '#4cd7f6' : 'var(--sc-outline)',
                  border:
                    currentView === 'insights'
                      ? '1px solid rgba(76, 215, 246, 0.35)'
                      : '1px solid transparent',
                  cursor: 'pointer',
                  minHeight: '44px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
                  query_stats
                </span>
                <span>Insights</span>
              </button>
            </nav>
          </div>

          {/* Single Primary Action: Upload Contract */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              type="button"
              onClick={() => {
                if (currentView !== 'analyze') {
                  setCurrentView('analyze')
                }
                const dropZone = document.getElementById('contract-drop-zone')
                if (dropZone) {
                  dropZone.scrollIntoView({ behavior: 'smooth' })
                }
                fileInputRef.current?.click()
              }}
              style={{
                background: 'rgba(76, 215, 246, 0.12)',
                border: '1px solid rgba(76, 215, 246, 0.45)',
                color: '#4cd7f6',
                padding: '8px 18px',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                cursor: 'pointer',
                minHeight: '44px',
                transition: 'all 0.2s ease',
              }}
              title="Upload or attach contract file for instant analysis"
            >
              <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
                upload_file
              </span>
              <span>Upload Contract</span>
            </button>
          </div>
        </header>

        {/* Main Content Area */}
        <main
          className="sc-grid-mesh"
          style={{
            display: 'flex',
            flexDirection: 'column',
            position: 'relative',
            overflow: 'hidden',
            padding: '24px',
            minHeight: '75vh',
          }}
        >
          {/* VIEW 1: ANALYZE (DROP ZONE + AUDIT RESULTS STREAM) */}
          {currentView === 'analyze' && (
            <div>
              {/* Real Contract Ingestion & Drop Box Zone */}
              <section
                id="contract-drop-zone"
                style={{
                  padding: '28px',
                  borderRadius: '16px',
                  background: 'rgba(10, 14, 24, 0.85)',
                  border: '1px solid rgba(70, 69, 85, 0.35)',
                  backdropFilter: 'blur(16px)',
                  position: 'relative',
                  marginBottom: '28px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '12px',
                    marginBottom: '20px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div
                      style={{
                        width: '36px',
                        height: '36px',
                        borderRadius: '10px',
                        background: 'rgba(76, 215, 246, 0.1)',
                        border: '1px solid rgba(76, 215, 246, 0.3)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#4cd7f6',
                      }}
                    >
                      <span
                        className="material-symbols-outlined"
                        style={{ fontSize: '20px' }}
                      >
                        upload_file
                      </span>
                    </div>
                    <div>
                      <h2
                        style={{
                          fontSize: '16px',
                          fontWeight: 700,
                          color: 'var(--sc-on-surface)',
                          margin: 0,
                        }}
                      >
                        Contract Ingestion &amp; Risk Classifier
                      </h2>
                      <p
                        style={{
                          fontSize: '11px',
                          fontFamily: 'JetBrains Mono, monospace',
                          color: 'var(--sc-outline)',
                          margin: '2px 0 0 0',
                        }}
                      >
                        Upload PDF, DOCX, or TXT agreements for real-time risk classification &amp; semantic search
                      </p>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      style={{
                        fontSize: '11px',
                        fontFamily: 'JetBrains Mono, monospace',
                        color: 'var(--sc-outline-variant)',
                      }}
                    >
                      POST /api/v1/analyze
                    </span>
                  </div>
                </div>

                {/* Hidden File Input */}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={handleFileInputChange}
                  style={{ display: 'none' }}
                  aria-label="Upload contract file"
                />

                {/* Drop Box UI */}
                <div
                  className={`sc-drop-box ${dragActive ? 'drag-active' : ''} ${
                    uploadError ? 'has-error' : ''
                  }`}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      fileInputRef.current?.click()
                    }
                  }}
                  aria-label="Drop contract file to analyze, or press Enter to browse"
                >
                  {isUploading ? (
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '14px',
                        padding: '24px 0',
                      }}
                    >
                      <div
                        style={{
                          width: '52px',
                          height: '52px',
                          borderRadius: '50%',
                          border: '3px solid rgba(76, 215, 246, 0.2)',
                          borderTopColor: '#4cd7f6',
                          animation: 'sc-spin 0.8s linear infinite',
                        }}
                      />
                      <div style={{ textAlign: 'center' }}>
                        <p
                          style={{
                            fontSize: '15px',
                            fontWeight: 600,
                            color: '#4cd7f6',
                            marginBottom: '4px',
                          }}
                        >
                          Analyzing Contract with Legal-BERT &amp; SBERT...
                        </p>
                        <p
                          style={{
                            fontSize: '12px',
                            fontFamily: 'JetBrains Mono, monospace',
                            color: 'var(--sc-outline)',
                          }}
                        >
                          Segmenting clauses, categorizing risk tiers, and computing embeddings
                        </p>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div
                        style={{
                          width: '64px',
                          height: '64px',
                          borderRadius: '16px',
                          background: 'rgba(76, 215, 246, 0.1)',
                          border: '1px solid rgba(76, 215, 246, 0.35)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#4cd7f6',
                          boxShadow: dragActive
                            ? '0 0 30px rgba(76, 215, 246, 0.5)'
                            : 'none',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        <span
                          className="material-symbols-outlined"
                          style={{ fontSize: '32px' }}
                        >
                          cloud_upload
                        </span>
                      </div>

                      <div style={{ textAlign: 'center' }}>
                        <p
                          style={{
                            fontSize: '16px',
                            fontWeight: 700,
                            color: 'var(--sc-on-surface)',
                            marginBottom: '4px',
                          }}
                        >
                          Drop Contract File Here to Ingest
                        </p>
                        <p
                          style={{
                            fontSize: '13px',
                            color: 'var(--sc-outline)',
                          }}
                        >
                          Drag &amp; drop your agreement, or{' '}
                          <span
                            style={{
                              color: '#4cd7f6',
                              textDecoration: 'underline',
                              fontWeight: 600,
                            }}
                          >
                            browse local device
                          </span>
                        </p>
                      </div>

                      <div
                        style={{
                          display: 'flex',
                          gap: '8px',
                          flexWrap: 'wrap',
                          justifyContent: 'center',
                        }}
                      >
                        {['PDF', 'DOCX', 'TXT'].map((ext) => (
                          <span
                            key={ext}
                            style={{
                              padding: '3px 8px',
                              borderRadius: '6px',
                              background: 'rgba(70, 69, 85, 0.4)',
                              border: '1px solid rgba(70, 69, 85, 0.6)',
                              fontSize: '10px',
                              fontFamily: 'JetBrains Mono, monospace',
                              color: 'var(--sc-on-surface-variant)',
                              fontWeight: 700,
                            }}
                          >
                            .{ext}
                          </span>
                        ))}
                        <span
                          style={{
                            padding: '3px 8px',
                            borderRadius: '6px',
                            background: 'rgba(70, 69, 85, 0.2)',
                            fontSize: '10px',
                            fontFamily: 'JetBrains Mono, monospace',
                            color: 'var(--sc-outline)',
                          }}
                        >
                          Max 10 MB
                        </span>
                      </div>
                    </>
                  )}
                </div>

                {/* Error Alert */}
                {uploadError && (
                  <div
                    style={{
                      marginTop: '14px',
                      padding: '12px 16px',
                      borderRadius: '8px',
                      background: 'rgba(147, 0, 10, 0.25)',
                      border: '1px solid #ffb4ab',
                      color: '#ffdad6',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '12px',
                      fontSize: '13px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        className="material-symbols-outlined"
                        style={{ color: '#ffb4ab', fontSize: '18px' }}
                      >
                        error
                      </span>
                      <span>{uploadError}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setUploadError(null)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#ffdad6',
                        cursor: 'pointer',
                        fontSize: '16px',
                        minHeight: '44px',
                        minWidth: '44px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                      title="Dismiss error"
                    >
                      ✕
                    </button>
                  </div>
                )}
              </section>

              {/* Live Contract Audit Results Stream */}
              {liveResult ? (
                <section
                  id="contract-audit-results"
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '24px',
                  }}
                >
                  {/* Document Overview Header */}
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      gap: '16px',
                      background: 'rgba(23, 27, 38, 0.85)',
                      border: '1px solid rgba(70, 69, 85, 0.35)',
                      padding: '18px 20px',
                      borderRadius: '12px',
                      backdropFilter: 'blur(12px)',
                    }}
                  >
                    <div>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          marginBottom: '6px',
                        }}
                      >
                        <span
                          className="material-symbols-outlined"
                          style={{ color: '#4cd7f6', fontSize: '22px' }}
                        >
                          description
                        </span>
                        <h2
                          style={{
                            fontSize: '18px',
                            fontWeight: 700,
                            color: 'var(--sc-on-surface)',
                            margin: 0,
                          }}
                        >
                          {liveResult.filename}
                        </h2>
                        <span
                          style={{
                            padding: '2px 8px',
                            borderRadius: '6px',
                            fontSize: '11px',
                            fontFamily: 'JetBrains Mono, monospace',
                            fontWeight: 700,
                            background:
                              liveResult.risk_summary?.overall_risk === 'High'
                                ? 'rgba(220, 38, 38, 0.25)'
                                : liveResult.risk_summary?.overall_risk === 'Medium'
                                ? 'rgba(217, 119, 6, 0.25)'
                                : 'rgba(5, 150, 105, 0.25)',
                            color:
                              liveResult.risk_summary?.overall_risk === 'High'
                                ? '#ffb4ab'
                                : liveResult.risk_summary?.overall_risk === 'Medium'
                                ? '#ffcc00'
                                : '#4cd7f6',
                            border: `1px solid ${
                              liveResult.risk_summary?.overall_risk === 'High'
                                ? 'rgba(255, 180, 171, 0.4)'
                                : liveResult.risk_summary?.overall_risk === 'Medium'
                                ? 'rgba(255, 204, 0, 0.4)'
                                : 'rgba(76, 215, 246, 0.4)'
                            }`,
                          }}
                        >
                          {liveResult.risk_summary?.overall_risk || 'Low'} Risk Document
                        </span>
                      </div>
                      <p
                        style={{
                          margin: 0,
                          fontSize: '12px',
                          fontFamily: 'JetBrains Mono, monospace',
                          color: 'var(--sc-outline)',
                        }}
                      >
                        {liveResult.char_count?.toLocaleString()} characters •{' '}
                        {liveResult.clauses?.length || 0} clauses extracted
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => {
                        setLiveResult(null)
                        setSearchResults(null)
                        setSearchQuery('')
                        const dropZone = document.getElementById('contract-drop-zone')
                        if (dropZone) dropZone.scrollIntoView({ behavior: 'smooth' })
                      }}
                      style={{
                        background: 'var(--sc-surface-high)',
                        border: '1px solid rgba(70, 69, 85, 0.35)',
                        color: 'var(--sc-on-surface)',
                        padding: '6px 14px',
                        borderRadius: '8px',
                        fontSize: '12px',
                        fontWeight: 500,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        cursor: 'pointer',
                        minHeight: '44px',
                      }}
                    >
                      <span
                        className="material-symbols-outlined"
                        style={{ fontSize: '16px', color: 'var(--sc-outline)' }}
                      >
                        refresh
                      </span>
                      <span>Analyze New Document</span>
                    </button>
                  </div>

                  {/* Real Risk Summary Cards (Real metrics only) */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                      gap: '12px',
                    }}
                  >
                    <div
                      style={{
                        background: 'rgba(23, 27, 38, 0.85)',
                        border: '1px solid rgba(220, 38, 38, 0.35)',
                        borderRadius: '12px',
                        padding: '16px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <span
                          style={{
                            fontSize: '12px',
                            fontWeight: 600,
                            color: '#ffb4ab',
                          }}
                        >
                          High Risk Clauses
                        </span>
                        <span
                          className="material-symbols-outlined"
                          style={{ fontSize: '18px', color: '#ffb4ab' }}
                        >
                          warning
                        </span>
                      </div>
                      <div
                        style={{
                          fontSize: '28px',
                          fontWeight: 700,
                          color: '#ffb4ab',
                          fontFamily: 'JetBrains Mono, monospace',
                        }}
                      >
                        {liveResult.risk_summary?.high_count || 0}
                      </div>
                    </div>

                    <div
                      style={{
                        background: 'rgba(23, 27, 38, 0.85)',
                        border: '1px solid rgba(217, 119, 6, 0.35)',
                        borderRadius: '12px',
                        padding: '16px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <span
                          style={{
                            fontSize: '12px',
                            fontWeight: 600,
                            color: '#ffcc00',
                          }}
                        >
                          Medium Risk Clauses
                        </span>
                        <span
                          className="material-symbols-outlined"
                          style={{ fontSize: '18px', color: '#ffcc00' }}
                        >
                          info
                        </span>
                      </div>
                      <div
                        style={{
                          fontSize: '28px',
                          fontWeight: 700,
                          color: '#ffcc00',
                          fontFamily: 'JetBrains Mono, monospace',
                        }}
                      >
                        {liveResult.risk_summary?.medium_count || 0}
                      </div>
                    </div>

                    <div
                      style={{
                        background: 'rgba(23, 27, 38, 0.85)',
                        border: '1px solid rgba(5, 150, 105, 0.35)',
                        borderRadius: '12px',
                        padding: '16px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <span
                          style={{
                            fontSize: '12px',
                            fontWeight: 600,
                            color: '#4cd7f6',
                          }}
                        >
                          Low Risk Clauses
                        </span>
                        <span
                          className="material-symbols-outlined"
                          style={{ fontSize: '18px', color: '#4cd7f6' }}
                        >
                          check_circle
                        </span>
                      </div>
                      <div
                        style={{
                          fontSize: '28px',
                          fontWeight: 700,
                          color: '#4cd7f6',
                          fontFamily: 'JetBrains Mono, monospace',
                        }}
                      >
                        {liveResult.risk_summary?.low_count || 0}
                      </div>
                    </div>

                    <div
                      style={{
                        background: 'rgba(23, 27, 38, 0.85)',
                        border: '1px solid rgba(70, 69, 85, 0.35)',
                        borderRadius: '12px',
                        padding: '16px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <span
                          style={{
                            fontSize: '12px',
                            fontWeight: 600,
                            color: 'var(--sc-outline)',
                          }}
                        >
                          Total Clauses Scanned
                        </span>
                        <span
                          className="material-symbols-outlined"
                          style={{ fontSize: '18px', color: 'var(--sc-outline)' }}
                        >
                          segment
                        </span>
                      </div>
                      <div
                        style={{
                          fontSize: '28px',
                          fontWeight: 700,
                          color: 'var(--sc-on-surface)',
                          fontFamily: 'JetBrains Mono, monospace',
                        }}
                      >
                        {liveResult.risk_summary?.total_clauses || 0}
                      </div>
                    </div>
                  </div>

                  {/* HeatMap Segmented Risk Bar */}
                  {liveResult.clauses && liveResult.clauses.length > 0 && (
                    <div style={{ marginTop: '4px' }}>
                      <HeatMap clauses={liveResult.clauses} />
                    </div>
                  )}

                  {/* Ask-the-Contract Semantic Search Bar */}
                  <div
                    style={{
                      background: 'rgba(23, 27, 38, 0.85)',
                      border: '1px solid rgba(70, 69, 85, 0.35)',
                      borderRadius: '12px',
                      padding: '16px 20px',
                      backdropFilter: 'blur(12px)',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        marginBottom: '10px',
                      }}
                    >
                      <span
                        className="material-symbols-outlined"
                        style={{ fontSize: '18px', color: '#4cd7f6' }}
                      >
                        psychology
                      </span>
                      <h3
                        style={{
                          margin: 0,
                          fontSize: '14px',
                          fontWeight: 600,
                          color: 'var(--sc-on-surface)',
                        }}
                      >
                        Ask-the-Contract Semantic Search
                      </h3>
                      <span
                        style={{
                          fontSize: '11px',
                          fontFamily: 'JetBrains Mono, monospace',
                          color: 'var(--sc-outline)',
                        }}
                      >
                        (Sentence-BERT Cosine Embeddings)
                      </span>
                    </div>

                    <form
                      onSubmit={handleSearchSubmit}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        flexWrap: 'wrap',
                      }}
                    >
                      <div style={{ position: 'relative', flex: 1, minWidth: '240px' }}>
                        <span
                          className="material-symbols-outlined"
                          style={{
                            position: 'absolute',
                            left: '12px',
                            top: '50%',
                            transform: 'translateY(-50%)',
                            color: 'var(--sc-outline)',
                            fontSize: '18px',
                          }}
                        >
                          search
                        </span>
                        <input
                          type="text"
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          placeholder="Search in plain English: e.g. 'Can I terminate early?' or 'What happens on breach?'"
                          style={{
                            width: '100%',
                            boxSizing: 'border-box',
                            background: 'var(--sc-surface-high)',
                            border: '1px solid rgba(70, 69, 85, 0.4)',
                            borderRadius: '8px',
                            padding: '10px 14px 10px 38px',
                            fontSize: '13px',
                            color: 'var(--sc-on-surface)',
                            outline: 'none',
                            fontFamily: 'Inter, sans-serif',
                            minHeight: '44px',
                          }}
                        />
                      </div>

                      <button
                        type="submit"
                        disabled={searchLoading || !searchQuery.trim()}
                        style={{
                          background: 'rgba(76, 215, 246, 0.15)',
                          border: '1px solid rgba(76, 215, 246, 0.45)',
                          color: '#4cd7f6',
                          padding: '10px 18px',
                          borderRadius: '8px',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor:
                            searchLoading || !searchQuery.trim()
                              ? 'not-allowed'
                              : 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          minHeight: '44px',
                        }}
                      >
                        {searchLoading ? (
                          <>
                            <span
                              className="material-symbols-outlined sc-animate-spin"
                              style={{ fontSize: '16px' }}
                            >
                              refresh
                            </span>
                            <span>Searching...</span>
                          </>
                        ) : (
                          <>
                            <span
                              className="material-symbols-outlined"
                              style={{ fontSize: '16px' }}
                            >
                              search
                            </span>
                            <span>Search</span>
                          </>
                        )}
                      </button>

                      {searchResults && (
                        <button
                          type="button"
                          onClick={handleClearSearch}
                          style={{
                            background: 'transparent',
                            border: '1px solid rgba(70, 69, 85, 0.4)',
                            color: 'var(--sc-outline)',
                            padding: '10px 14px',
                            borderRadius: '8px',
                            fontSize: '12px',
                            cursor: 'pointer',
                            minHeight: '44px',
                          }}
                        >
                          Clear
                        </button>
                      )}
                    </form>

                    {/* Search Results Drawer */}
                    {searchResults && (
                      <div
                        style={{
                          marginTop: '16px',
                          paddingTop: '16px',
                          borderTop: '1px solid rgba(70, 69, 85, 0.3)',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: '10px',
                          }}
                        >
                          <span
                            style={{
                              fontSize: '12px',
                              fontWeight: 600,
                              color: '#4cd7f6',
                            }}
                          >
                            Top Matches for &quot;{searchQuery}&quot; (
                            {searchResults.length})
                          </span>
                        </div>

                        {searchResults.length === 0 ? (
                          <p
                            style={{
                              fontSize: '12px',
                              color: 'var(--sc-outline)',
                              margin: 0,
                            }}
                          >
                            No matching clauses found. Try different keywords.
                          </p>
                        ) : (
                          <div
                            style={{
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '8px',
                            }}
                          >
                            {searchResults.map((res) => (
                              <div
                                key={res.clause_id}
                                onClick={() => {
                                  const el = document.getElementById(
                                    `sc-clause-${res.position}`
                                  )
                                  if (el) {
                                    el.scrollIntoView({
                                      behavior: 'smooth',
                                      block: 'center',
                                    })
                                  }
                                }}
                                style={{
                                  background: 'rgba(38, 42, 53, 0.6)',
                                  border: '1px solid rgba(70, 69, 85, 0.3)',
                                  padding: '10px 14px',
                                  borderRadius: '8px',
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                  gap: '12px',
                                  cursor: 'pointer',
                                }}
                              >
                                <div style={{ minWidth: 0 }}>
                                  <div
                                    style={{
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: '8px',
                                      marginBottom: '4px',
                                    }}
                                  >
                                    <span
                                      style={{
                                        fontSize: '11px',
                                        fontWeight: 700,
                                        color: '#4cd7f6',
                                      }}
                                    >
                                      Clause #{res.position + 1}: {res.label}
                                    </span>
                                    <span
                                      style={{
                                        fontSize: '10px',
                                        padding: '1px 6px',
                                        borderRadius: '4px',
                                        background: 'var(--sc-surface-highest)',
                                        color: 'var(--sc-outline)',
                                        fontFamily: 'JetBrains Mono, monospace',
                                      }}
                                    >
                                      {Math.round(res.similarity * 100)}% match
                                    </span>
                                  </div>
                                  <p
                                    style={{
                                      fontSize: '12px',
                                      color: 'var(--sc-on-surface)',
                                      margin: 0,
                                      overflow: 'hidden',
                                      textOverflow: 'ellipsis',
                                      whiteSpace: 'nowrap',
                                    }}
                                  >
                                    {res.text}
                                  </p>
                                </div>

                                <span
                                  className="material-symbols-outlined"
                                  style={{
                                    fontSize: '16px',
                                    color: '#4cd7f6',
                                    flexShrink: 0,
                                  }}
                                >
                                  arrow_forward
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Real Analyzed Clauses Stream */}
                  <div>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: '16px',
                      }}
                    >
                      <h3
                        style={{
                          margin: 0,
                          fontSize: '16px',
                          fontWeight: 700,
                          color: 'var(--sc-on-surface)',
                        }}
                      >
                        All Analyzed Clauses ({liveResult.clauses?.length || 0})
                      </h3>
                      <span
                        style={{
                          fontSize: '11px',
                          fontFamily: 'JetBrains Mono, monospace',
                          color: 'var(--sc-outline)',
                        }}
                      >
                        Legal-BERT Classified
                      </span>
                    </div>

                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '16px',
                      }}
                    >
                      {liveResult.clauses?.map((clause, idx) => {
                        const exp = explanations[clause.label]
                        const isHigh = clause.risk_level === 'High'
                        const isMed = clause.risk_level === 'Medium'
                        const isLow = clause.risk_level === 'Low'

                        return (
                          <div
                            key={clause.id || idx}
                            id={`sc-clause-${clause.position}`}
                            className="sc-clause-card"
                            style={{
                              borderLeft: `4px solid ${
                                isHigh
                                  ? '#ffb4ab'
                                  : isMed
                                  ? '#ffcc00'
                                  : isLow
                                  ? '#4cd7f6'
                                  : 'rgba(70, 69, 85, 0.4)'
                              }`,
                            }}
                          >
                            <div
                              style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                flexWrap: 'wrap',
                                gap: '10px',
                                marginBottom: '12px',
                              }}
                            >
                              <div
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '10px',
                                }}
                              >
                                <span
                                  style={{
                                    fontFamily: 'JetBrains Mono, monospace',
                                    fontSize: '11px',
                                    padding: '2px 8px',
                                    borderRadius: '4px',
                                    background: 'var(--sc-surface-high)',
                                    color: 'var(--sc-outline)',
                                    border: '1px solid rgba(70, 69, 85, 0.3)',
                                  }}
                                >
                                  Clause #{clause.position + 1}
                                </span>
                                <span
                                  style={{
                                    fontSize: '14px',
                                    fontWeight: 700,
                                    color: 'var(--sc-on-surface)',
                                  }}
                                >
                                  {clause.label}
                                </span>
                                <span
                                  style={{
                                    fontFamily: 'JetBrains Mono, monospace',
                                    fontSize: '10px',
                                    padding: '2px 8px',
                                    borderRadius: '4px',
                                    background: isHigh
                                      ? 'rgba(220, 38, 38, 0.2)'
                                      : isMed
                                      ? 'rgba(217, 119, 6, 0.2)'
                                      : isLow
                                      ? 'rgba(5, 150, 105, 0.2)'
                                      : 'rgba(70, 69, 85, 0.3)',
                                    color: isHigh
                                      ? '#ffb4ab'
                                      : isMed
                                      ? '#ffcc00'
                                      : isLow
                                      ? '#4cd7f6'
                                      : 'var(--sc-outline)',
                                    fontWeight: 700,
                                    border: `1px solid ${
                                      isHigh
                                        ? 'rgba(255, 180, 171, 0.3)'
                                        : isMed
                                        ? 'rgba(255, 204, 0, 0.3)'
                                        : isLow
                                        ? 'rgba(76, 215, 246, 0.3)'
                                        : 'rgba(70, 69, 85, 0.3)'
                                    }`,
                                  }}
                                >
                                  {clause.risk_level || 'No'} Risk
                                </span>
                              </div>

                              <div
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '10px',
                                }}
                              >
                                <span
                                  style={{
                                    fontFamily: 'JetBrains Mono, monospace',
                                    fontSize: '11px',
                                    color: 'var(--sc-outline-variant)',
                                  }}
                                >
                                  Confidence: {Math.round((clause.confidence || 0) * 100)}%
                                </span>

                                {/* Read-Aloud Button */}
                                <button
                                  type="button"
                                  onClick={() => handleSpeak(clause, idx)}
                                  style={{
                                    background: 'var(--sc-surface-high)',
                                    border: '1px solid rgba(70, 69, 85, 0.4)',
                                    color:
                                      speakingIdx === idx
                                        ? '#4cd7f6'
                                        : 'var(--sc-on-surface)',
                                    padding: '6px 10px',
                                    borderRadius: '6px',
                                    fontSize: '11px',
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '4px',
                                    minHeight: '44px',
                                  }}
                                  title="Read clause explanation aloud"
                                >
                                  <span
                                    className="material-symbols-outlined"
                                    style={{ fontSize: '16px' }}
                                  >
                                    {speakingIdx === idx ? 'volume_up' : 'volume_down'}
                                  </span>
                                  <span>{speakingIdx === idx ? 'Stop' : 'Read'}</span>
                                </button>

                                {/* AI Redline Generator Trigger */}
                                {clause.label !== 'No Clause' && (
                                  <button
                                    type="button"
                                    onClick={() => handleGetRedline(clause, idx)}
                                    disabled={redlineLoading[idx]}
                                    style={{
                                      background: clauseRedlines[idx]
                                        ? 'rgba(76, 215, 246, 0.2)'
                                        : 'var(--sc-surface-high)',
                                      border: '1px solid rgba(76, 215, 246, 0.4)',
                                      color: '#4cd7f6',
                                      padding: '6px 12px',
                                      borderRadius: '6px',
                                      fontSize: '11px',
                                      fontWeight: 600,
                                      cursor: redlineLoading[idx]
                                        ? 'not-allowed'
                                        : 'pointer',
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: '4px',
                                      minHeight: '44px',
                                    }}
                                    title="Generate safer balanced language"
                                  >
                                    <span
                                      className="material-symbols-outlined"
                                      style={{ fontSize: '15px' }}
                                    >
                                      draw
                                    </span>
                                    <span>
                                      {redlineLoading[idx]
                                        ? 'Generating...'
                                        : clauseRedlines[idx]
                                        ? 'Hide Redline'
                                        : 'Redline'}
                                    </span>
                                  </button>
                                )}
                              </div>
                            </div>

                            {/* Clause Full Text */}
                            <p
                              style={{
                                fontSize: '13px',
                                lineHeight: 1.6,
                                color: 'var(--sc-on-surface)',
                                background: 'rgba(10, 14, 24, 0.6)',
                                border: '1px solid rgba(70, 69, 85, 0.2)',
                                borderRadius: '8px',
                                padding: '12px 14px',
                                margin: '0 0 12px 0',
                                whiteSpace: 'pre-wrap',
                              }}
                            >
                              {clause.text}
                            </p>

                            {/* Plain-English Explanation Note */}
                            {exp && (
                              <div
                                style={{
                                  background: 'rgba(38, 42, 53, 0.4)',
                                  border: '1px solid rgba(70, 69, 85, 0.25)',
                                  borderRadius: '8px',
                                  padding: '12px 14px',
                                  display: 'flex',
                                  flexDirection: 'column',
                                  gap: '6px',
                                }}
                              >
                                <div
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    color: '#4cd7f6',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.05em',
                                  }}
                                >
                                  <span
                                    className="material-symbols-outlined"
                                    style={{ fontSize: '14px' }}
                                  >
                                    lightbulb
                                  </span>
                                  <span>Plain-English Breakdown</span>
                                </div>
                                <p
                                  style={{
                                    fontSize: '12px',
                                    lineHeight: 1.5,
                                    color: 'var(--sc-on-surface-variant)',
                                    margin: 0,
                                  }}
                                >
                                  {exp.summary}
                                </p>
                                {exp.why_risky && isHigh && (
                                  <p
                                    style={{
                                      fontSize: '12px',
                                      lineHeight: 1.5,
                                      color: '#ffb4ab',
                                      margin: '4px 0 0 0',
                                    }}
                                  >
                                    <strong>Risk Factor:</strong> {exp.why_risky}
                                  </p>
                                )}
                              </div>
                            )}

                            {/* Redline Diff View */}
                            {clauseRedlines[idx] && (
                              <div
                                style={{
                                  marginTop: '12px',
                                  background: 'rgba(15, 19, 29, 0.85)',
                                  border: '1px solid rgba(76, 215, 246, 0.35)',
                                  borderRadius: '8px',
                                  padding: '14px',
                                }}
                              >
                                <div
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    marginBottom: '8px',
                                  }}
                                >
                                  <div
                                    style={{
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: '6px',
                                      fontSize: '12px',
                                      fontWeight: 700,
                                      color: '#4cd7f6',
                                    }}
                                  >
                                    <span
                                      className="material-symbols-outlined"
                                      style={{ fontSize: '16px' }}
                                    >
                                      edit_note
                                    </span>
                                    <span>Recommended Balanced Redline</span>
                                  </div>
                                  <span
                                    style={{
                                      fontSize: '10px',
                                      fontFamily: 'JetBrains Mono, monospace',
                                      color: 'var(--sc-outline)',
                                    }}
                                  >
                                    {clauseRedlines[idx].changes_count} changes
                                  </span>
                                </div>

                                <p
                                  style={{
                                    fontSize: '12px',
                                    color: 'var(--sc-outline-variant)',
                                    marginBottom: '10px',
                                  }}
                                >
                                  {clauseRedlines[idx].summary}
                                </p>

                                <div
                                  style={{
                                    fontSize: '12px',
                                    lineHeight: 1.6,
                                    padding: '10px',
                                    background: 'rgba(23, 27, 38, 0.7)',
                                    borderRadius: '6px',
                                    border: '1px solid rgba(70, 69, 85, 0.3)',
                                  }}
                                  dangerouslySetInnerHTML={{
                                    __html: clauseRedlines[idx].diff_html,
                                  }}
                                />
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </section>
              ) : (
                <div
                  style={{
                    textAlign: 'center',
                    padding: '40px 20px',
                    color: 'var(--sc-outline)',
                  }}
                >
                  <span
                    className="material-symbols-outlined"
                    style={{ fontSize: '40px', color: 'var(--sc-outline-variant)' }}
                  >
                    draft
                  </span>
                  <p style={{ marginTop: '12px', fontSize: '14px' }}>
                    No document active. Drop a contract above or click &quot;Upload Contract&quot; to begin audit.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* VIEW 2: HISTORY (REAL AUDITED CONTRACTS ARCHIVE) */}
          {currentView === 'history' && (
            <div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '20px',
                }}
              >
                <div>
                  <h2
                    style={{
                      margin: 0,
                      fontSize: '18px',
                      fontWeight: 700,
                      color: 'var(--sc-on-surface)',
                    }}
                  >
                    Analysis History
                  </h2>
                  <p
                    style={{
                      margin: '2px 0 0 0',
                      fontSize: '12px',
                      color: 'var(--sc-outline)',
                    }}
                  >
                    Previously uploaded and audited contracts stored in local database
                  </p>
                </div>
                <button
                  type="button"
                  onClick={fetchHistory}
                  disabled={historyLoading}
                  style={{
                    background: 'var(--sc-surface-high)',
                    border: '1px solid rgba(70, 69, 85, 0.35)',
                    color: 'var(--sc-on-surface)',
                    padding: '6px 14px',
                    borderRadius: '8px',
                    fontSize: '12px',
                    fontWeight: 500,
                    cursor: historyLoading ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    minHeight: '44px',
                  }}
                >
                  <span
                    className={`material-symbols-outlined ${
                      historyLoading ? 'sc-animate-spin' : ''
                    }`}
                    style={{ fontSize: '16px' }}
                  >
                    refresh
                  </span>
                  <span>Refresh</span>
                </button>
              </div>

              {historyLoading ? (
                <div
                  style={{
                    textAlign: 'center',
                    padding: '60px 0',
                    color: 'var(--sc-outline)',
                  }}
                >
                  <span
                    className="material-symbols-outlined sc-animate-spin"
                    style={{ fontSize: '32px', color: '#4cd7f6' }}
                  >
                    refresh
                  </span>
                  <p style={{ marginTop: '12px', fontSize: '13px' }}>
                    Loading history archive...
                  </p>
                </div>
              ) : historyError ? (
                <div
                  style={{
                    padding: '16px',
                    borderRadius: '8px',
                    background: 'rgba(147, 0, 10, 0.25)',
                    border: '1px solid #ffb4ab',
                    color: '#ffdad6',
                    fontSize: '13px',
                  }}
                >
                  {historyError}
                </div>
              ) : historyDocs.length === 0 ? (
                <div
                  style={{
                    textAlign: 'center',
                    padding: '60px 0',
                    background: 'rgba(23, 27, 38, 0.6)',
                    borderRadius: '12px',
                    border: '1px solid rgba(70, 69, 85, 0.3)',
                  }}
                >
                  <span
                    className="material-symbols-outlined"
                    style={{ fontSize: '48px', color: 'var(--sc-outline)' }}
                  >
                    folder_open
                  </span>
                  <p
                    style={{
                      fontSize: '15px',
                      color: 'var(--sc-on-surface)',
                      marginTop: '12px',
                      fontWeight: 600,
                    }}
                  >
                    No historical analyses found
                  </p>
                  <p style={{ fontSize: '13px', color: 'var(--sc-outline)' }}>
                    Uploaded contracts will appear here automatically.
                  </p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {historyDocs.map((doc) => {
                    const isHigh = doc.overall_risk === 'High'
                    const isMed = doc.overall_risk === 'Medium'

                    return (
                      <div
                        key={doc.id}
                        onClick={() => handleOpenHistoricalDoc(doc.id)}
                        className="sc-tilt-card"
                        style={{
                          background: 'rgba(23, 27, 38, 0.85)',
                          border: '1px solid rgba(70, 69, 85, 0.35)',
                          borderRadius: '12px',
                          padding: '16px 20px',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          flexWrap: 'wrap',
                          gap: '12px',
                          cursor: 'pointer',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '14px',
                            minWidth: 0,
                          }}
                        >
                          <div
                            style={{
                              width: '40px',
                              height: '40px',
                              borderRadius: '8px',
                              background: 'var(--sc-surface-highest)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: '#4cd7f6',
                            }}
                          >
                            <span
                              className="material-symbols-outlined"
                              style={{ fontSize: '20px' }}
                            >
                              description
                            </span>
                          </div>
                          <div>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                flexWrap: 'wrap',
                              }}
                            >
                              <span
                                style={{
                                  fontSize: '14px',
                                  fontWeight: 600,
                                  color: 'var(--sc-on-surface)',
                                }}
                              >
                                {doc.filename}
                              </span>
                              <span
                                style={{
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  fontSize: '10px',
                                  fontFamily: 'JetBrains Mono, monospace',
                                  fontWeight: 700,
                                  background: isHigh
                                    ? 'rgba(220, 38, 38, 0.25)'
                                    : isMed
                                    ? 'rgba(217, 119, 6, 0.25)'
                                    : 'rgba(5, 150, 105, 0.25)',
                                  color: isHigh
                                    ? '#ffb4ab'
                                    : isMed
                                    ? '#ffcc00'
                                    : '#4cd7f6',
                                }}
                              >
                                {doc.overall_risk || 'Low'} Risk
                              </span>
                            </div>
                            <div
                              style={{
                                fontSize: '11px',
                                fontFamily: 'JetBrains Mono, monospace',
                                color: 'var(--sc-outline)',
                                marginTop: '4px',
                              }}
                            >
                              {doc.char_count?.toLocaleString()} chars •{' '}
                              {new Date(doc.created_at).toLocaleString()}
                            </div>
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleOpenHistoricalDoc(doc.id)
                            }}
                            style={{
                              background: 'rgba(76, 215, 246, 0.1)',
                              border: '1px solid rgba(76, 215, 246, 0.35)',
                              color: '#4cd7f6',
                              padding: '6px 12px',
                              borderRadius: '6px',
                              fontSize: '11px',
                              fontWeight: 600,
                              cursor: 'pointer',
                              minHeight: '44px',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <span
                              className="material-symbols-outlined"
                              style={{ fontSize: '15px' }}
                            >
                              visibility
                            </span>
                            <span>Open Audit</span>
                          </button>

                          <button
                            type="button"
                            onClick={(e) => handleDeleteDoc(doc.id, e)}
                            style={{
                              background: 'transparent',
                              border: '1px solid rgba(255, 180, 171, 0.3)',
                              color: '#ffb4ab',
                              padding: '6px 10px',
                              borderRadius: '6px',
                              fontSize: '11px',
                              cursor: 'pointer',
                              minHeight: '44px',
                              display: 'flex',
                              alignItems: 'center',
                            }}
                            title="Delete record"
                          >
                            <span
                              className="material-symbols-outlined"
                              style={{ fontSize: '16px' }}
                            >
                              delete
                            </span>
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* VIEW 3: INSIGHTS (REAL LEGAL-BERT VS BASELINE TEST METRICS) */}
          {currentView === 'insights' && (
            <div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '20px',
                }}
              >
                <div>
                  <h2
                    style={{
                      margin: 0,
                      fontSize: '18px',
                      fontWeight: 700,
                      color: 'var(--sc-on-surface)',
                    }}
                  >
                    Model Evaluation Insights
                  </h2>
                  <p
                    style={{
                      margin: '2px 0 0 0',
                      fontSize: '12px',
                      color: 'var(--sc-outline)',
                    }}
                  >
                    Empirical metrics sourced from ml/artifacts/metrics.json on CUAD test split
                  </p>
                </div>
                <button
                  type="button"
                  onClick={fetchInsightsData}
                  disabled={insightsLoading}
                  style={{
                    background: 'var(--sc-surface-high)',
                    border: '1px solid rgba(70, 69, 85, 0.35)',
                    color: 'var(--sc-on-surface)',
                    padding: '6px 14px',
                    borderRadius: '8px',
                    fontSize: '12px',
                    fontWeight: 500,
                    cursor: insightsLoading ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    minHeight: '44px',
                  }}
                >
                  <span
                    className={`material-symbols-outlined ${
                      insightsLoading ? 'sc-animate-spin' : ''
                    }`}
                    style={{ fontSize: '16px' }}
                  >
                    refresh
                  </span>
                  <span>Refresh</span>
                </button>
              </div>

              {insightsLoading ? (
                <div
                  style={{
                    textAlign: 'center',
                    padding: '60px 0',
                    color: 'var(--sc-outline)',
                  }}
                >
                  <span
                    className="material-symbols-outlined sc-animate-spin"
                    style={{ fontSize: '32px', color: '#4cd7f6' }}
                  >
                    refresh
                  </span>
                  <p style={{ marginTop: '12px', fontSize: '13px' }}>
                    Loading model metrics...
                  </p>
                </div>
              ) : insightsError ? (
                <div
                  style={{
                    padding: '16px',
                    borderRadius: '8px',
                    background: 'rgba(147, 0, 10, 0.25)',
                    border: '1px solid #ffb4ab',
                    color: '#ffdad6',
                    fontSize: '13px',
                  }}
                >
                  {insightsError}
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {/* Test Set Comparison Table */}
                  <div
                    style={{
                      background: 'rgba(23, 27, 38, 0.85)',
                      border: '1px solid rgba(70, 69, 85, 0.35)',
                      borderRadius: '12px',
                      padding: '20px',
                      backdropFilter: 'blur(12px)',
                    }}
                  >
                    <h3
                      style={{
                        margin: '0 0 16px 0',
                        fontSize: '15px',
                        fontWeight: 600,
                        color: 'var(--sc-on-surface)',
                      }}
                    >
                      Model Comparison (CUAD Test Split)
                    </h3>

                    {insightsMetrics?.baseline?.test &&
                    insightsMetrics?.legal_bert?.test ? (
                      <div style={{ overflowX: 'auto' }}>
                        <table
                          style={{
                            width: '100%',
                            borderCollapse: 'collapse',
                            fontSize: '13px',
                            fontFamily: 'Inter, sans-serif',
                          }}
                        >
                          <thead>
                            <tr
                              style={{
                                borderBottom: '1px solid rgba(70, 69, 85, 0.4)',
                                color: 'var(--sc-outline)',
                                fontSize: '11px',
                                textTransform: 'uppercase',
                                letterSpacing: '0.05em',
                              }}
                            >
                              <th style={{ textAlign: 'left', padding: '10px 8px' }}>
                                Metric
                              </th>
                              <th style={{ textAlign: 'right', padding: '10px 8px' }}>
                                Baseline (TF-IDF + LogReg)
                              </th>
                              <th style={{ textAlign: 'right', padding: '10px 8px' }}>
                                Legal-BERT (Fine-Tuned)
                              </th>
                              <th style={{ textAlign: 'right', padding: '10px 8px' }}>
                                Δ Delta
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {[
                              'accuracy',
                              'macro_f1',
                              'macro_precision',
                              'macro_recall',
                            ].map((metric) => {
                              const b = insightsMetrics.baseline.test[metric] || 0
                              const l = insightsMetrics.legal_bert.test[metric] || 0
                              const delta = l - b
                              const isPositive = delta > 0

                              return (
                                <tr
                                  key={metric}
                                  style={{
                                    borderBottom: '1px solid rgba(70, 69, 85, 0.2)',
                                  }}
                                >
                                  <td
                                    style={{
                                      padding: '12px 8px',
                                      fontWeight: 500,
                                      color: 'var(--sc-on-surface)',
                                    }}
                                  >
                                    {metric
                                      .replace('_', ' ')
                                      .replace(/\b\w/g, (c) => c.toUpperCase())}
                                  </td>
                                  <td
                                    style={{
                                      padding: '12px 8px',
                                      textAlign: 'right',
                                      fontFamily: 'JetBrains Mono, monospace',
                                      color: 'var(--sc-outline)',
                                    }}
                                  >
                                    {(b * 100).toFixed(1)}%
                                  </td>
                                  <td
                                    style={{
                                      padding: '12px 8px',
                                      textAlign: 'right',
                                      fontFamily: 'JetBrains Mono, monospace',
                                      color: '#4cd7f6',
                                      fontWeight: 600,
                                    }}
                                  >
                                    {(l * 100).toFixed(1)}%
                                  </td>
                                  <td
                                    style={{
                                      padding: '12px 8px',
                                      textAlign: 'right',
                                      fontFamily: 'JetBrains Mono, monospace',
                                      color: isPositive
                                        ? '#4cd7f6'
                                        : delta < 0
                                        ? '#ffb4ab'
                                        : 'var(--sc-outline)',
                                      fontWeight: 600,
                                    }}
                                  >
                                    {isPositive ? '+' : ''}
                                    {(delta * 100).toFixed(1)}%
                                  </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p
                        style={{
                          fontSize: '13px',
                          color: 'var(--sc-outline)',
                          margin: 0,
                        }}
                      >
                        Metrics data not yet populated.
                      </p>
                    )}
                  </div>

                  {/* Per-Class Breakdown Table */}
                  {insightsMetrics?.legal_bert?.test?.per_class && (
                    <div
                      style={{
                        background: 'rgba(23, 27, 38, 0.85)',
                        border: '1px solid rgba(70, 69, 85, 0.35)',
                        borderRadius: '12px',
                        padding: '20px',
                      }}
                    >
                      <h3
                        style={{
                          margin: '0 0 16px 0',
                          fontSize: '15px',
                          fontWeight: 600,
                          color: 'var(--sc-on-surface)',
                        }}
                      >
                        Legal-BERT Per-Clause Type Performance
                      </h3>
                      <div style={{ overflowX: 'auto' }}>
                        <table
                          style={{
                            width: '100%',
                            borderCollapse: 'collapse',
                            fontSize: '12px',
                          }}
                        >
                          <thead>
                            <tr
                              style={{
                                borderBottom: '1px solid rgba(70, 69, 85, 0.4)',
                                color: 'var(--sc-outline)',
                                fontSize: '11px',
                                textTransform: 'uppercase',
                              }}
                            >
                              <th style={{ textAlign: 'left', padding: '8px' }}>Clause Type</th>
                              <th style={{ textAlign: 'right', padding: '8px' }}>Precision</th>
                              <th style={{ textAlign: 'right', padding: '8px' }}>Recall</th>
                              <th style={{ textAlign: 'right', padding: '8px' }}>F1-Score</th>
                              <th style={{ textAlign: 'right', padding: '8px' }}>Support</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(
                              insightsMetrics.legal_bert.test.per_class
                            ).map(([clauseName, stats]) => (
                              <tr
                                key={clauseName}
                                style={{
                                  borderBottom: '1px solid rgba(70, 69, 85, 0.15)',
                                }}
                              >
                                <td
                                  style={{
                                    padding: '8px',
                                    fontWeight: 500,
                                    color: 'var(--sc-on-surface)',
                                  }}
                                >
                                  {clauseName}
                                </td>
                                <td
                                  style={{
                                    padding: '8px',
                                    textAlign: 'right',
                                    fontFamily: 'JetBrains Mono, monospace',
                                    color: 'var(--sc-outline)',
                                  }}
                                >
                                  {(stats.precision * 100).toFixed(1)}%
                                </td>
                                <td
                                  style={{
                                    padding: '8px',
                                    textAlign: 'right',
                                    fontFamily: 'JetBrains Mono, monospace',
                                    color: 'var(--sc-outline)',
                                  }}
                                >
                                  {(stats.recall * 100).toFixed(1)}%
                                </td>
                                <td
                                  style={{
                                    padding: '8px',
                                    textAlign: 'right',
                                    fontFamily: 'JetBrains Mono, monospace',
                                    color: '#4cd7f6',
                                    fontWeight: 600,
                                  }}
                                >
                                  {(stats.f1 * 100).toFixed(1)}%
                                </td>
                                <td
                                  style={{
                                    padding: '8px',
                                    textAlign: 'right',
                                    fontFamily: 'JetBrains Mono, monospace',
                                    color: 'var(--sc-outline-variant)',
                                  }}
                                >
                                  {stats.support}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
