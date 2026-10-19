import React, { useState, useEffect, useRef } from 'react'
import { analyzeContract, searchDocument, getClauseRedline } from '../api/client'
import HeatMap from './HeatMap'
import explanations from '../data/clause_explanations.json'
import '../styles/spatial-cockpit.css'

export default function SpatialCockpit({ liveResult: initialLiveResult }) {
  // Ambient Mouse Spotlight
  const [spotlightPos, setSpotlightPos] = useState({ x: -1000, y: -1000 })
  // Toast notifications
  const [toasts, setToasts] = useState([])
  // Interactive Simulation
  const [scoreVal, setScoreVal] = useState(72)
  const [isResolving, setIsResolving] = useState(false)
  const [resolved, setResolved] = useState(false)
  const [radarActive, setRadarActive] = useState(true)
  const [activeTab, setActiveTab] = useState('playbooks')
  const [filterCategory, setFilterCategory] = useState('all')
  const [activeJurisdiction, setActiveJurisdiction] = useState('delaware')
  const [sliderMultiplier, setSliderMultiplier] = useState(2)
  const [sliderSeverity, setSliderSeverity] = useState(2)

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

  // Card 3D tilt helper
  const handleTiltMove = (e) => {
    const card = e.currentTarget
    const rect = card.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    const centerX = rect.width / 2
    const centerY = rect.height / 2
    const rotateX = ((y - centerY) / centerY) * -3
    const rotateY = ((x - centerX) / centerX) * 3
    card.style.transform = `perspective(800px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.015, 1.015, 1.015)`
  }

  const handleTiltLeave = (e) => {
    e.currentTarget.style.transform = 'perspective(800px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)'
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
      const data = await analyzeContract(file)
      setLiveResult(data)
      setSearchResults(null)
      setSearchQuery('')
      setClauseRedlines({})

      // Update cockpit stats based on real contract
      const overall = data.risk_summary?.overall_risk
      const newScore = overall === 'High' ? 88 : overall === 'Medium' ? 64 : 32
      setScoreVal(newScore)

      showToast(`Audit Complete: ${data.clauses?.length || 0} clauses parsed from ${file.name}`, 'secondary', 'verified')

      setTimeout(() => {
        const el = document.getElementById('contract-audit-results')
        if (el) el.scrollIntoView({ behavior: 'smooth' })
      }, 350)
    } catch (err) {
      const msg = err.message || 'Failed to analyze contract'
      setUploadError(msg)
      showToast(msg, 'error', 'error')
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

  const handleSearch = async (e) => {
    if (e) e.preventDefault()
    if (!liveResult || !searchQuery.trim()) return

    setSearchLoading(true)
    try {
      const res = await searchDocument(liveResult.document_id, searchQuery.trim())
      setSearchResults(res.results || [])
      showToast(`Found ${res.results?.length || 0} matches for query`, 'secondary', 'search')
    } catch (err) {
      showToast(err.message || 'Search failed', 'error', 'error')
    } finally {
      setSearchLoading(false)
    }
  }

  const handleClearSearch = () => {
    setSearchResults(null)
    setSearchQuery('')
  }

  const handleToggleRedline = async (clause, idx) => {
    if (clauseRedlines[idx]) {
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
      setClauseRedlines((prev) => ({ ...prev, [idx]: data || { empty: true } }))
      showToast('Safer wording redline generated', 'secondary', 'edit_document')
    } catch (err) {
      setClauseRedlines((prev) => ({ ...prev, [idx]: { error: err.message || 'Failed to generate redline' } }))
      showToast('No redline available for this clause', 'error', 'error')
    } finally {
      setRedlineLoading((prev) => ({ ...prev, [idx]: false }))
    }
  }

  const handleReadAloud = (clause, idx) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      showToast('Speech synthesis unavailable on this device', 'error', 'volume_off')
      return
    }

    if (speakingIdx === idx) {
      window.speechSynthesis.cancel()
      setSpeakingIdx(null)
      return
    }

    window.speechSynthesis.cancel()
    const expInfo = explanations.clauses[clause.label] || explanations.clauses['No Clause']
    const textToRead = clause.legal?.plain_note || expInfo?.summary || expInfo?.why_risky || `${clause.label}. ${clause.text}`

    const utterance = new SpeechSynthesisUtterance(textToRead)
    utterance.onend = () => setSpeakingIdx(null)
    utterance.onerror = () => setSpeakingIdx(null)

    setSpeakingIdx(idx)
    window.speechSynthesis.speak(utterance)
  }

  const handleBatchResolve = () => {
    setIsResolving(true)
    setTimeout(() => {
      setIsResolving(false)
      setResolved(true)
      setScoreVal(48)
      showToast('Precedent clauses verified and injected successfully', 'secondary', 'verified')
      setTimeout(() => {
        setResolved(false)
      }, 4000)
    }, 1200)
  }

  const multiplierLabels = {
    1: '6 Months Fees ($700k Cap)',
    2: '12 Months Fees ($1.4M Cap)',
    3: '18 Months Fees ($2.1M Cap)',
    4: '24 Months Fees ($2.8M Cap)',
    5: 'Uncapped ($14.2M Total Portfolio At Risk)',
  }

  const impactLabels = {
    1: '-28% Projected Risk Exposure (Optimal Defense)',
    2: '-18% Projected Risk Exposure ($680k potential savings)',
    3: '-4% Neutral Benchmark Posture',
    4: '+14% Elevated Risk Exposure',
    5: '+42% Critical Catastrophic Exposure',
  }

  const severityLabels = {
    1: 'None (Strict Exclusion)',
    2: 'Strict 2x Multiplier',
    3: '5x Super-Cap Carveout',
    4: 'Unlimited Consequential Damages',
  }

  // Audit contracts list
  const contracts = [
    {
      id: 1,
      title: 'CloudScale Enterprise MSA 2025',
      category: 'critical',
      tag: '3 CRITICAL BLOCKERS',
      icon: 'gavel',
      val: '$380,000 ACV',
      juris: 'California (Tech Bias)',
      highlight: 'Sec 8.2 Uncapped Liability',
      status: 'Review Pending',
      btnText: 'Jump to 3D View',
      btnIcon: 'visibility',
    },
    {
      id: 2,
      title: 'Apex Logistics Master Service Agreement',
      category: 'pending',
      tag: '1 MODERATE',
      icon: 'local_shipping',
      val: '$1,200,000 ACV',
      juris: 'Delaware Commercial Court',
      highlight: 'Sec 11.4 Net 60 Terms',
      status: 'Redline Sent',
      btnText: 'Audit Diffs',
      btnIcon: 'contract_edit',
    },
    {
      id: 3,
      title: 'QuantumCore Enterprise Data License',
      category: 'remediated',
      tag: 'COMPLIANT (0 CRITICAL)',
      icon: 'database',
      val: '$620,000 ACV',
      juris: 'New York Commercial',
      highlight: 'Full IP Carve-out clean',
      status: 'Pre-Approved',
      btnText: 'Telemetry',
      btnIcon: 'history',
    },
    {
      id: 4,
      title: 'Hyperion Global Managed Cloud Services',
      category: 'critical',
      tag: '4 CRITICAL REDLINES',
      icon: 'notification_important',
      val: '$2,100,000 ACV',
      juris: 'UK Cross-Border Data Hub',
      highlight: 'Broad Consequential Damages',
      status: 'High Alert Escalated',
      btnText: 'Engage Shield',
      btnIcon: 'security',
    },
  ]

  const filteredContracts = contracts.filter(
    (c) => filterCategory === 'all' || c.category === filterCategory
  )

  return (
    <div className="spatial-cockpit">
      {/* Ambient Mouse Follower Spotlight */}
      <div
        className="sc-spotlight"
        style={{ left: `${spotlightPos.x}px`, top: `${spotlightPos.y}px` }}
      />

      {/* Toast Notification Container */}
      <div style={{ position: 'fixed', top: '24px', right: '24px', zIndex: 100, display: 'flex', flexDirection: 'column', gap: '8px', pointerEvents: 'none' }}>
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
              border: '1px solid rgba(76, 215, 246, 0.4)',
              background: 'rgba(10, 14, 24, 0.9)',
              color: '#4cd7f6',
              boxShadow: '0 20px 40px rgba(0,0,0,0.8)',
              backdropFilter: 'blur(12px)',
              fontSize: '12px',
              fontFamily: 'JetBrains Mono, monospace',
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>{t.icon}</span>
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
            display: 'grid',
            gridTemplateColumns: 'repeat(12, minmax(0, 1fr))',
            borderBottom: '1px solid rgba(70, 69, 85, 0.3)',
            background: 'var(--sc-surface-lowest)',
          }}
        >
          {/* Brand Box */}
          <div
            style={{
              gridColumn: 'span 12 / span 12',
              padding: '16px 24px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: '1px solid rgba(70, 69, 85, 0.3)',
              background: 'var(--sc-surface-low)',
            }}
            className="md:col-span-5 lg:col-span-4"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
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
                ClauseGuard<span style={{ color: 'var(--sc-outline)', fontFamily: 'sans-serif', marginLeft: '2px', fontSize: '16px' }}>.</span>
              </div>
              <span
                style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: '10px',
                  letterSpacing: '0.1em',
                  color: 'var(--sc-on-surface-variant)',
                  background: 'var(--sc-surface-high)',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  border: '1px solid rgba(70, 69, 85, 0.3)',
                }}
              >
                / RISK ENGINE
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '9999px', background: 'var(--sc-outline-variant)' }} />
              <span style={{ fontSize: '12px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--sc-outline)' }}>v4.8</span>
            </div>
          </div>

          {/* Navigation & View Switching Actions */}
          <div
            style={{
              gridColumn: 'span 12 / span 12',
              padding: '14px 24px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '16px',
              background: 'var(--sc-surface-lowest)',
            }}
            className="md:col-span-7 lg:col-span-8"
          >
            <nav style={{ display: 'flex', alignItems: 'center', gap: '20px', fontSize: '11px', fontFamily: 'JetBrains Mono, monospace', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              {['services', 'playbooks', 'risk', 'precedents'].map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => {
                    setActiveTab(tab)
                    showToast(`Switched view to ${tab.toUpperCase()}`, 'primary', 'view_agenda')
                  }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: activeTab === tab ? '#4cd7f6' : 'var(--sc-outline)',
                    fontWeight: activeTab === tab ? 700 : 500,
                    borderBottom: activeTab === tab ? '2px solid #4cd7f6' : '2px solid transparent',
                    paddingBottom: '2px',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                >
                  {tab}
                </button>
              ))}
              <button
                type="button"
                onClick={() => {
                  setActiveTab('audit')
                  showToast('Viewing 24 Active Audit Entries', 'primary', 'rule')
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: activeTab === 'audit' ? '#4cd7f6' : 'var(--sc-outline)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                }}
              >
                <span>Audit</span>
                <span style={{ padding: '1px 6px', borderRadius: '4px', background: 'var(--sc-surface-highest)', color: 'var(--sc-outline)', fontSize: '10px', fontWeight: 700, border: '1px solid rgba(70, 69, 85, 0.3)' }}>
                  24
                </span>
              </button>
            </nav>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {/* Quick Contract Upload trigger button */}
              <button
                type="button"
                onClick={() => {
                  const dropZone = document.getElementById('contract-drop-zone')
                  if (dropZone) {
                    dropZone.scrollIntoView({ behavior: 'smooth' })
                  } else {
                    fileInputRef.current?.click()
                  }
                }}
                style={{
                  background: 'rgba(76, 215, 246, 0.1)',
                  border: '1px solid rgba(76, 215, 246, 0.4)',
                  color: '#4cd7f6',
                  padding: '6px 14px',
                  borderRadius: '8px',
                  fontSize: '12px',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
                title="Attach or drop a contract file below for AI risk analysis"
              >
                <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>attach_file</span>
                <span>Attach Contract</span>
              </button>

              {/* Radar Toggle Button */}
              <button
                type="button"
                onClick={() => {
                  setRadarActive(!radarActive)
                  showToast(!radarActive ? 'Neural Radar Sweep Online' : 'Neural Radar Suspended', 'secondary', 'radar')
                }}
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  border: `1px solid ${radarActive ? 'rgba(76, 215, 246, 0.5)' : 'rgba(70, 69, 85, 0.4)'}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: radarActive ? '#4cd7f6' : 'var(--sc-outline)',
                  background: 'var(--sc-surface-low)',
                  cursor: 'pointer',
                }}
                title="Toggle Radar Mode"
              >
                <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>radar</span>
              </button>
            </div>
          </div>
        </header>

        {/* Main Editorial Canvas */}
        <main className="sc-grid-mesh" style={{ display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}>
          {/* Top Command & Status Deck */}
          <div
            style={{
              width: '100%',
              background: 'rgba(10, 14, 24, 0.9)',
              backdropFilter: 'blur(12px)',
              borderBottom: '1px solid rgba(70, 69, 85, 0.2)',
              padding: '14px 24px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '16px',
              zIndex: 20,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  background: 'var(--sc-surface)',
                  padding: '6px 12px',
                  borderRadius: '8px',
                  border: '1px solid rgba(70, 69, 85, 0.3)',
                }}
              >
                <span style={{ width: '8px', height: '8px', borderRadius: '9999px', background: '#4cd7f6', display: 'inline-block' }} />
                <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: 'var(--sc-on-surface)', textTransform: 'uppercase', fontWeight: 500 }}>
                  3D Quant Engine Online
                </span>
                <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: 'var(--sc-outline-variant)' }}>
                  | 14ms latency
                </span>
              </div>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  background: 'var(--sc-surface-high)',
                  padding: '6px 12px',
                  borderRadius: '8px',
                  border: '1px solid rgba(70, 69, 85, 0.2)',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
                onClick={() => showToast('Opening Q1 Enterprise Commitments portfolio...', 'secondary', 'folder')}
              >
                <span className="material-symbols-outlined" style={{ fontSize: '16px', color: 'var(--sc-outline)' }}>folder_open</span>
                <span>Q1 Enterprise Commitments</span>
                <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--sc-on-surface-variant)' }}>
                  ($14.2M TCV · 48 Contracts)
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <button
                type="button"
                className="sc-tilt-card"
                onClick={() => showToast('Playbook Simulator aligned to Series-2025 Standard', 'primary', 'tune')}
                style={{
                  background: 'var(--sc-surface-high)',
                  border: '1px solid rgba(70, 69, 85, 0.3)',
                  color: 'var(--sc-on-surface)',
                  padding: '6px 14px',
                  borderRadius: '8px',
                  fontSize: '12px',
                  fontWeight: 500,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: '16px', color: 'var(--sc-outline)' }}>tune</span>
                <span>Playbook Simulator</span>
              </button>

              <button
                type="button"
                className="sc-tilt-card"
                onClick={() => showToast('Generating Signed Audit PDF & JSON Telemetry...', 'secondary', 'download')}
                style={{
                  background: 'var(--sc-surface-high)',
                  border: '1px solid rgba(70, 69, 85, 0.3)',
                  color: 'var(--sc-on-surface)',
                  padding: '6px 14px',
                  borderRadius: '8px',
                  fontSize: '12px',
                  fontWeight: 500,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: '16px', color: 'var(--sc-outline)' }}>download</span>
                <span>Export Audit</span>
              </button>

              <button
                type="button"
                className="sc-tilt-card"
                onClick={() => {
                  fileInputRef.current?.click()
                }}
                style={{
                  background: 'linear-gradient(135deg, rgba(76, 215, 246, 0.2), rgba(79, 70, 229, 0.3))',
                  border: '1px solid rgba(76, 215, 246, 0.5)',
                  color: '#4cd7f6',
                  padding: '6px 16px',
                  borderRadius: '8px',
                  fontSize: '12px',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
                title="Upload or attach contract file for instant analysis"
              >
                <span className="material-symbols-outlined" style={{ fontSize: '16px', color: '#4cd7f6' }}>cloud_upload</span>
                <span>Upload & Audit</span>
              </button>
            </div>
          </div>

          {/* Hero 3D Spatial Risk Hub */}
          <div style={{ padding: '24px', zIndex: 10 }}>
            <div
              style={{
                borderRadius: '16px',
                background: 'var(--sc-surface-lowest)',
                border: '1px solid rgba(70, 69, 85, 0.3)',
                padding: '24px',
                position: 'relative',
                overflow: 'hidden',
                boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
              }}
            >
              {/* Header Row */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '12px',
                  borderBottom: '1px solid rgba(70, 69, 85, 0.2)',
                  paddingBottom: '16px',
                  marginBottom: '20px',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', textTransform: 'uppercase', padding: '2px 8px', borderRadius: '4px', background: 'var(--sc-surface-high)', color: 'var(--sc-outline)', fontWeight: 600, border: '1px solid rgba(70, 69, 85, 0.3)' }}>
                      PORTFOLIO COCKPIT
                    </span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: 'var(--sc-outline-variant)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '9999px', background: 'var(--sc-outline)' }} />
                      NEURAL PARSER V4.8
                    </span>
                  </div>
                  <h1 style={{ fontSize: '24px', fontWeight: 700, color: 'var(--sc-on-surface)', margin: '6px 0 0 0', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    Spatial Clause Risk Engine
                    <span style={{ fontSize: '12px', fontFamily: 'JetBrains Mono, monospace', fontWeight: 400, color: 'var(--sc-outline)', background: 'var(--sc-surface)', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(70, 69, 85, 0.3)' }}>
                      Interactive Node Mesh
                    </span>
                  </h1>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: 'var(--sc-outline-variant)' }}>
                    Real-time Node Projection
                  </span>
                  <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '6px 12px', borderRadius: '8px', background: 'var(--sc-surface-high)', border: '1px solid rgba(70, 69, 85, 0.4)', color: 'var(--sc-on-surface)', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', fontWeight: 500 }}>
                    <span className="material-symbols-outlined" style={{ fontSize: '16px', color: '#4cd7f6' }}>view_in_ar</span>
                    <span>3D ACTIVE</span>
                  </div>
                </div>
              </div>

              {/* Core Spatial Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, minmax(0, 1fr))', gap: '20px' }}>
                {/* Left: Risk Score Telemetry Matrix */}
                <div style={{ gridColumn: 'span 12 / span 12' }} className="lg:col-span-3">
                  <div
                    className="sc-tilt-card"
                    onMouseMove={handleTiltMove}
                    onMouseLeave={handleTiltLeave}
                    style={{
                      background: 'rgba(28, 31, 42, 0.8)',
                      backdropFilter: 'blur(12px)',
                      border: '1px solid rgba(70, 69, 85, 0.3)',
                      borderRadius: '12px',
                      padding: '16px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '12px',
                      marginBottom: '16px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: 'var(--sc-outline-variant)', textTransform: 'uppercase', fontWeight: 600 }}>
                        Exposure Index
                      </span>
                      <div style={{ width: '24px', height: '24px', borderRadius: '6px', background: 'var(--sc-surface-high)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#4cd7f6' }}>
                        <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>crisis_alert</span>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                      <span style={{ fontSize: '42px', fontWeight: 800, color: resolved ? '#4cd7f6' : 'var(--sc-on-surface)', letterSpacing: '-0.02em', transition: 'all 0.5s ease' }}>
                        {scoreVal}
                      </span>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '18px', color: 'var(--sc-outline-variant)' }}>/100</span>
                      <span style={{ marginLeft: 'auto', fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: 'var(--sc-outline)', padding: '2px 8px', borderRadius: '4px', background: 'var(--sc-surface-high)', display: 'flex', alignItems: 'center', gap: '2px', fontWeight: 600, border: '1px solid rgba(70, 69, 85, 0.3)' }}>
                        <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>trending_up</span> +4 pts
                      </span>
                    </div>

                    <p style={{ fontSize: '12px', color: 'var(--sc-outline-variant)', lineHeight: 1.5, margin: 0 }}>
                      Elevated risk threshold breached across indemnification and governing law parameters.
                    </p>

                    <div style={{ width: '100%', background: 'var(--sc-surface-highest)', height: '8px', borderRadius: '9999px', overflow: 'hidden', display: 'flex', gap: '4px', padding: '2px', border: '1px solid rgba(70, 69, 85, 0.2)' }}>
                      <div style={{ background: '#4cd7f6', height: '100%', borderRadius: '9999px', width: '45%' }} />
                      <div style={{ background: 'var(--sc-outline-variant)', height: '100%', borderRadius: '9999px', width: '25%' }} />
                      <div style={{ background: 'var(--sc-error)', height: '100%', borderRadius: '9999px', width: '30%' }} />
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'JetBrains Mono, monospace', fontSize: '10px', color: 'var(--sc-outline-variant)' }}>
                      <span>Minimal (45%)</span>
                      <span>Baseline (25%)</span>
                      <span style={{ color: 'var(--sc-error)' }}>Critical (30%)</span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div
                      className="sc-tilt-card"
                      onMouseMove={handleTiltMove}
                      onMouseLeave={handleTiltLeave}
                      style={{ background: 'rgba(28, 31, 42, 0.7)', border: '1px solid rgba(70, 69, 85, 0.3)', padding: '12px', borderRadius: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                      onClick={() => showToast('Filtered view to Critical Blockers', 'error', 'warning')}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '9999px', background: 'var(--sc-error)' }} />
                        <span style={{ fontSize: '12px', fontWeight: 500 }}>Critical Blockers</span>
                      </div>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: 'var(--sc-surface-high)', color: 'var(--sc-error)', fontWeight: 600, border: '1px solid rgba(70, 69, 85, 0.3)' }}>
                        3 Clauses
                      </span>
                    </div>

                    <div
                      className="sc-tilt-card"
                      onMouseMove={handleTiltMove}
                      onMouseLeave={handleTiltLeave}
                      style={{ background: 'rgba(28, 31, 42, 0.7)', border: '1px solid rgba(70, 69, 85, 0.3)', padding: '12px', borderRadius: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                      onClick={() => showToast('Filtered view to Moderate Exposure', 'secondary', 'info')}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '9999px', background: 'var(--sc-outline-variant)' }} />
                        <span style={{ fontSize: '12px', fontWeight: 500 }}>Moderate Exposure</span>
                      </div>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: 'var(--sc-surface-high)', color: 'var(--sc-outline)', fontWeight: 600, border: '1px solid rgba(70, 69, 85, 0.3)' }}>
                        5 Clauses
                      </span>
                    </div>

                    <div
                      className="sc-tilt-card"
                      onMouseMove={handleTiltMove}
                      onMouseLeave={handleTiltLeave}
                      style={{ background: 'rgba(28, 31, 42, 0.7)', border: '1px solid rgba(70, 69, 85, 0.3)', padding: '12px', borderRadius: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
                      onClick={() => showToast('Filtered view to Compliant Clauses', 'primary', 'check_circle')}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '9999px', background: 'var(--sc-surface-bright)' }} />
                        <span style={{ fontSize: '12px', fontWeight: 500 }}>Compliant Clauses</span>
                      </div>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: 'var(--sc-surface-high)', color: 'var(--sc-outline-variant)', fontWeight: 600, border: '1px solid rgba(70, 69, 85, 0.3)' }}>
                        18 Clauses
                      </span>
                    </div>
                  </div>
                </div>

                {/* Center: 3D Scene Viewport with HUD Overlays */}
                <div
                  style={{
                    gridColumn: 'span 12 / span 12',
                    position: 'relative',
                    minHeight: '440px',
                    borderRadius: '16px',
                    background: 'var(--sc-surface-lowest)',
                    border: '1px solid rgba(70, 69, 85, 0.3)',
                    overflow: 'hidden',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                  className="lg:col-span-6"
                >
                  {/* Radar Sweep Ring Accent Overlay */}
                  <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none', opacity: 0.25 }}>
                    <div className="sc-animate-orbit" style={{ width: '380px', height: '380px', borderRadius: '9999px', border: '1px solid rgba(70, 69, 85, 0.4)', position: 'relative' }}>
                      <div style={{ position: 'absolute', top: 0, left: '50%', width: '8px', height: '8px', transform: 'translate(-50%, -50%)', background: '#4cd7f6', borderRadius: '9999px' }} />
                      <div style={{ position: 'absolute', bottom: '24px', left: '48px', width: '6px', height: '6px', background: 'var(--sc-outline-variant)', borderRadius: '9999px' }} />
                    </div>
                    <div style={{ width: '240px', height: '240px', borderRadius: '9999px', border: '1px solid rgba(70, 69, 85, 0.3)', position: 'absolute' }} />
                    <div style={{ width: '120px', height: '120px', borderRadius: '9999px', border: '1px solid rgba(70, 69, 85, 0.2)', position: 'absolute' }} />
                  </div>

                  {/* Radar Scanner Beam */}
                  {radarActive && (
                    <div
                      className="sc-animate-radar"
                      style={{
                        position: 'absolute',
                        width: '440px',
                        height: '440px',
                        borderRadius: '9999px',
                        pointerEvents: 'none',
                        opacity: 0.15,
                        background: 'conic-gradient(from 0deg, transparent 0deg, transparent 270deg, rgba(76, 215, 246, 0.5) 360deg)',
                      }}
                    />
                  )}

                  {/* 3D Component Canvas Stage / Geometric Visualizer */}
                  <div style={{ position: 'relative', zIndex: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', height: '100%' }}>
                    <svg width="220" height="220" viewBox="0 0 100 100" style={{ filter: 'drop-shadow(0 0 16px rgba(76, 215, 246, 0.3))' }}>
                      <polygon points="50,15 90,38 90,82 50,95 10,82 10,38" fill="none" stroke="rgba(76, 215, 246, 0.6)" strokeWidth="1.2" />
                      <polygon points="50,28 78,44 78,74 50,85 22,74 22,44" fill="rgba(3, 181, 211, 0.08)" stroke="rgba(195, 192, 255, 0.4)" strokeWidth="1" />
                      <circle cx="50" cy="50" r="14" fill="rgba(79, 70, 229, 0.3)" stroke="#4cd7f6" strokeWidth="1.5" />
                      <circle cx="50" cy="15" r="3" fill="#ffb4ab" />
                      <circle cx="90" cy="38" r="3" fill="#4cd7f6" />
                      <circle cx="90" cy="82" r="3" fill="#c3c0ff" />
                      <circle cx="10" cy="82" r="3" fill="#ffb4ab" />
                      <circle cx="10" cy="38" r="3" fill="#4cd7f6" />
                      <line x1="50" y1="50" x2="50" y2="15" stroke="rgba(255, 180, 171, 0.6)" strokeDasharray="2,2" />
                      <line x1="50" y1="50" x2="90" y2="38" stroke="rgba(76, 215, 246, 0.6)" strokeDasharray="2,2" />
                      <line x1="50" y1="50" x2="10" y2="82" stroke="rgba(255, 180, 171, 0.6)" strokeDasharray="2,2" />
                    </svg>
                  </div>

                  {/* Understated Floating HUD Overlays */}
                  <div
                    className="sc-animate-float"
                    style={{ position: 'absolute', top: '20px', left: '20px', zIndex: 20, cursor: 'pointer' }}
                    onClick={() => showToast('Selected Node: Sec 8.2 • Unlimited Indemnity', 'error', 'token')}
                  >
                    <div style={{ background: 'rgba(23, 27, 38, 0.95)', backdropFilter: 'blur(12px)', padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(70, 69, 85, 0.5)', display: 'flex', alignItems: 'center', gap: '10px', boxShadow: '0 8px 24px rgba(0,0,0,0.5)' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '9999px', background: 'var(--sc-error)' }} />
                      <div>
                        <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: 'var(--sc-on-surface)', fontWeight: 600 }}>Sec 8.2 • Unlimited Indemnity</div>
                        <div style={{ fontSize: '10px', color: 'var(--sc-outline-variant)', fontFamily: 'JetBrains Mono, monospace' }}>Zero aggregate cap · CloudScale MSA</div>
                      </div>
                    </div>
                  </div>

                  <div
                    className="sc-animate-float-reverse"
                    style={{ position: 'absolute', bottom: '24px', left: '24px', zIndex: 20, cursor: 'pointer' }}
                    onClick={() => showToast('Selected Node: Sec 11.4 • Auto-Renewal Penalty', 'secondary', 'token')}
                  >
                    <div style={{ background: 'rgba(23, 27, 38, 0.95)', backdropFilter: 'blur(12px)', padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(70, 69, 85, 0.5)', display: 'flex', alignItems: 'center', gap: '10px', boxShadow: '0 8px 24px rgba(0,0,0,0.5)' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '9999px', background: 'var(--sc-outline-variant)' }} />
                      <div>
                        <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: 'var(--sc-on-surface)', fontWeight: 600 }}>Sec 11.4 • Auto-Renewal Penalty</div>
                        <div style={{ fontSize: '10px', color: 'var(--sc-outline-variant)', fontFamily: 'JetBrains Mono, monospace' }}>60-day notice + 18% exit fee</div>
                      </div>
                    </div>
                  </div>

                  <div
                    className="sc-animate-float"
                    style={{ position: 'absolute', top: '30px', right: '20px', zIndex: 20, cursor: 'pointer' }}
                    onClick={() => showToast('Selected Node: Sec 14.1 • IP Carve-Out Clean', 'primary', 'token')}
                  >
                    <div style={{ background: 'rgba(23, 27, 38, 0.95)', backdropFilter: 'blur(12px)', padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(70, 69, 85, 0.5)', display: 'flex', alignItems: 'center', gap: '10px', boxShadow: '0 8px 24px rgba(0,0,0,0.5)' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '9999px', background: 'var(--sc-surface-bright)' }} />
                      <div>
                        <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: 'var(--sc-on-surface)', fontWeight: 600 }}>Sec 14.1 • IP Carve-Out Clean</div>
                        <div style={{ fontSize: '10px', color: 'var(--sc-outline-variant)', fontFamily: 'JetBrains Mono, monospace' }}>Standard enterprise retention verified</div>
                      </div>
                    </div>
                  </div>

                  {/* Interaction Prompt Strip */}
                  <div style={{ position: 'absolute', bottom: '12px', right: '16px', zIndex: 20, display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(10, 14, 24, 0.9)', border: '1px solid rgba(70, 69, 85, 0.3)', backdropFilter: 'blur(6px)', padding: '6px 12px', borderRadius: '8px', fontSize: '11px' }}>
                    <span className="material-symbols-outlined" style={{ fontSize: '14px', color: '#4cd7f6' }}>drag_pan</span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--sc-outline-variant)' }}>Drag to Orbit · Click Node to Inspect</span>
                  </div>
                </div>

                {/* Right: AI Decision Telemetry & Action Panel */}
                <div style={{ gridColumn: 'span 12 / span 12' }} className="lg:col-span-3">
                  <div
                    className="sc-tilt-card"
                    onMouseMove={handleTiltMove}
                    onMouseLeave={handleTiltLeave}
                    style={{
                      background: 'rgba(28, 31, 42, 0.8)',
                      backdropFilter: 'blur(12px)',
                      border: '1px solid rgba(70, 69, 85, 0.3)',
                      borderRadius: '12px',
                      padding: '16px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '12px',
                      marginBottom: '16px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: 'var(--sc-outline-variant)', textTransform: 'uppercase', fontWeight: 600 }}>
                        AI Decision Engine
                      </span>
                      <span className="material-symbols-outlined" style={{ color: '#4cd7f6', fontSize: '18px' }}>auto_awesome</span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div>
                        <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--sc-on-surface)' }}>
                          98.4<span style={{ color: '#4cd7f6', fontSize: '16px' }}>%</span>
                        </div>
                        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: 'var(--sc-outline-variant)' }}>
                          Synthesis Confidence
                        </span>
                      </div>

                      <div style={{ width: '48px', height: '48px', borderRadius: '9999px', background: 'var(--sc-surface-high)', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
                        <svg style={{ width: '100%', height: '100%', transform: 'rotate(-90deg)' }} viewBox="0 0 36 36">
                          <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="var(--sc-surface-highest)" strokeWidth="2.5" />
                          <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#4cd7f6" strokeDasharray="98.4, 100" strokeWidth="2.5" />
                        </svg>
                        <span className="material-symbols-outlined" style={{ position: 'absolute', fontSize: '16px', color: '#4cd7f6' }}>verified</span>
                      </div>
                    </div>

                    <div style={{ background: 'rgba(38, 42, 53, 0.7)', padding: '10px', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', border: '1px solid rgba(70, 69, 85, 0.2)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span className="material-symbols-outlined" style={{ fontSize: '16px', color: 'var(--sc-outline)' }}>flag</span>
                        <span style={{ fontSize: '12px', fontWeight: 500 }}>Queued Redlines</span>
                      </div>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', fontWeight: 600, background: 'var(--sc-surface-highest)', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(70, 69, 85, 0.3)' }}>
                        14 Flagged
                      </span>
                    </div>

                    <div style={{ background: 'rgba(38, 42, 53, 0.7)', padding: '10px', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', border: '1px solid rgba(70, 69, 85, 0.2)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span className="material-symbols-outlined" style={{ fontSize: '16px', color: 'var(--sc-outline)' }}>history_edu</span>
                        <span style={{ fontSize: '12px', fontWeight: 500 }}>Delaware Standard</span>
                      </div>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', fontWeight: 600, color: '#4cd7f6' }}>
                        v2025.2
                      </span>
                    </div>
                  </div>

                  <div
                    style={{
                      background: 'rgba(28, 31, 42, 0.8)',
                      backdropFilter: 'blur(12px)',
                      border: '1px solid rgba(70, 69, 85, 0.3)',
                      borderRadius: '12px',
                      padding: '16px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '10px',
                    }}
                  >
                    <span style={{ fontSize: '12px', color: 'var(--sc-outline-variant)', fontWeight: 500 }}>
                      Automated Remediation
                    </span>
                    <button
                      type="button"
                      disabled={isResolving}
                      onClick={handleBatchResolve}
                      style={{
                        width: '100%',
                        background: resolved ? '#03b5d3' : 'var(--sc-primary-container)',
                        color: resolved ? '#001f26' : '#ffffff',
                        border: '1px solid rgba(70, 69, 85, 0.4)',
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: '12px',
                        fontWeight: 600,
                        padding: '10px 16px',
                        borderRadius: '8px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px',
                        cursor: isResolving ? 'not-allowed' : 'pointer',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      {isResolving ? (
                        <>
                          <span className="material-symbols-outlined sc-animate-spin" style={{ fontSize: '16px' }}>refresh</span>
                          <span>Injecting Precedent Fallbacks...</span>
                        </>
                      ) : resolved ? (
                        <>
                          <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>check_circle</span>
                          <span>3 Criticals Auto-Remediated</span>
                        </>
                      ) : (
                        <>
                          <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>bolt</span>
                          <span>Auto-Resolve 3 Criticals</span>
                        </>
                      )}
                    </button>
                    <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '10px', color: 'var(--sc-outline-variant)', textAlign: 'center', margin: 0 }}>
                      Applies pre-approved Series-2025 fallback language
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Key Analytical KPI Cards Grid */}
          <div style={{ padding: '0 24px 24px 24px', zIndex: 10 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
              <div className="sc-tilt-card" onMouseMove={handleTiltMove} onMouseLeave={handleTiltLeave} style={{ background: 'rgba(23, 27, 38, 0.9)', border: '1px solid rgba(70, 69, 85, 0.3)', borderRadius: '12px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px', cursor: 'pointer' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: 'var(--sc-outline)', fontWeight: 500, textTransform: 'uppercase' }}>Contract Exposure</span>
                  <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--sc-surface-high)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#4cd7f6' }}>
                    <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>shield_with_heart</span>
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--sc-on-surface)' }}>$2.4M</div>
                  <div style={{ fontSize: '12px', color: 'var(--sc-outline-variant)', marginTop: '4px', lineHeight: 1.4 }}>Uncapped liability mitigated across 12 MSA reviews this cycle.</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: '#4cd7f6', fontWeight: 500 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>verified_user</span> 100% Risk Deflection Rate
                </div>
              </div>

              <div className="sc-tilt-card" onMouseMove={handleTiltMove} onMouseLeave={handleTiltLeave} style={{ background: 'rgba(23, 27, 38, 0.9)', border: '1px solid rgba(70, 69, 85, 0.3)', borderRadius: '12px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px', cursor: 'pointer' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: 'var(--sc-outline)', fontWeight: 500, textTransform: 'uppercase' }}>Negotiation Velocity</span>
                  <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--sc-surface-high)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#4cd7f6' }}>
                    <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>speed</span>
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--sc-on-surface)' }}>4.2 Days</div>
                  <div style={{ fontSize: '12px', color: 'var(--sc-outline-variant)', marginTop: '4px', lineHeight: 1.4 }}>Average turnaround from intake to signature stage.</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: 'var(--sc-outline)', fontWeight: 500 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>trending_down</span> 62% faster than manual audit
                </div>
              </div>

              <div className="sc-tilt-card" onMouseMove={handleTiltMove} onMouseLeave={handleTiltLeave} style={{ background: 'rgba(23, 27, 38, 0.9)', border: '1px solid rgba(70, 69, 85, 0.3)', borderRadius: '12px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px', cursor: 'pointer' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: 'var(--sc-outline)', fontWeight: 500, textTransform: 'uppercase' }}>Adherence Rate</span>
                  <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--sc-surface-high)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#4cd7f6' }}>
                    <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>checklist_rtl</span>
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--sc-on-surface)' }}>88.6%</div>
                  <div style={{ fontSize: '12px', color: 'var(--sc-outline-variant)', marginTop: '4px', lineHeight: 1.4 }}>Direct compliance with Standard Series 2025 guidelines.</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: 'var(--sc-outline)', fontWeight: 500 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>balance</span> 11 Fallbacks Exercised
                </div>
              </div>

              <div className="sc-tilt-card" onMouseMove={handleTiltMove} onMouseLeave={handleTiltLeave} style={{ background: 'rgba(23, 27, 38, 0.9)', border: '1px solid rgba(70, 69, 85, 0.3)', borderRadius: '12px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px', cursor: 'pointer' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: 'var(--sc-outline)', fontWeight: 500, textTransform: 'uppercase' }}>High-Risk Vendors</span>
                  <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--sc-surface-high)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ffb4ab' }}>
                    <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>warning</span>
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--sc-on-surface)' }}>3 Vendors</div>
                  <div style={{ fontSize: '12px', color: 'var(--sc-outline-variant)', marginTop: '4px', lineHeight: 1.4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>CloudScale Inc, NovaFlow Data, VertexAI.</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: '#ffb4ab', fontWeight: 500 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>priority_high</span> GC Sign-off Mandatory
                </div>
              </div>
            </div>
          </div>

          {/* Real-time Flagged Contracts & Clause Review Stream */}
          <div style={{ padding: '0 24px 24px 24px', zIndex: 10 }}>
            <div style={{ background: 'rgba(10, 14, 24, 0.8)', backdropFilter: 'blur(16px)', border: '1px solid rgba(70, 69, 85, 0.3)', borderRadius: '16px', padding: '24px', boxShadow: '0 20px 40px rgba(0,0,0,0.6)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', borderBottom: '1px solid rgba(70, 69, 85, 0.2)', paddingBottom: '16px' }}>
                <div>
                  <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--sc-on-surface)', margin: 0 }}>Active Audit Pipeline</h2>
                  <p style={{ fontSize: '12px', color: 'var(--sc-outline-variant)', margin: '4px 0 0 0' }}>Live extraction and 3D node cross-referencing against active repositories.</p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                  {[
                    { key: 'all', label: 'All Contracts (48)' },
                    { key: 'critical', label: 'Critical Alerts (7)' },
                    { key: 'pending', label: 'Pending Approval (12)' },
                    { key: 'remediated', label: 'Auto-Remediated (29)' },
                  ].map((filter) => (
                    <button
                      key={filter.key}
                      type="button"
                      onClick={() => setFilterCategory(filter.key)}
                      style={{
                        padding: '6px 12px',
                        borderRadius: '8px',
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: '11px',
                        fontWeight: filterCategory === filter.key ? 700 : 500,
                        background: filterCategory === filter.key ? '#c3c0ff' : 'var(--sc-surface-high)',
                        color: filterCategory === filter.key ? '#0f0069' : 'var(--sc-outline)',
                        border: '1px solid rgba(70, 69, 85, 0.3)',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {filter.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Contract Cards Stream */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
                {filteredContracts.map((c) => (
                  <div
                    key={c.id}
                    className="sc-tilt-card"
                    onMouseMove={handleTiltMove}
                    onMouseLeave={handleTiltLeave}
                    style={{
                      background: 'rgba(28, 31, 42, 0.7)',
                      border: '1px solid rgba(70, 69, 85, 0.3)',
                      borderRadius: '12px',
                      padding: '16px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      gap: '16px',
                      cursor: 'pointer',
                    }}
                    onClick={() => showToast(`Selected: ${c.title}`, 'secondary', 'description')}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '14px', minWidth: 0 }}>
                      <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: 'var(--sc-surface-highest)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#4cd7f6', border: '1px solid rgba(70, 69, 85, 0.3)', flexShrink: 0 }}>
                        <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>{c.icon}</span>
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--sc-on-surface)' }}>{c.title}</span>
                          <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '10px', padding: '2px 8px', borderRadius: '4px', background: 'var(--sc-surface-high)', color: c.category === 'critical' ? '#ffb4ab' : '#4cd7f6', fontWeight: 600, border: '1px solid rgba(70, 69, 85, 0.3)' }}>
                            {c.tag}
                          </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px', fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: 'var(--sc-outline-variant)', flexWrap: 'wrap' }}>
                          <span>Value: {c.val}</span>
                          <span>•</span>
                          <span>Jurisdiction: {c.juris}</span>
                          <span>•</span>
                          <span style={{ color: '#ffb4ab', fontWeight: 500 }}>{c.highlight}</span>
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', padding: '4px 10px', borderRadius: '4px', background: 'var(--sc-surface-highest)', color: 'var(--sc-on-surface-variant)', border: '1px solid rgba(70, 69, 85, 0.3)' }}>
                        {c.status}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          showToast('Aligning 3D Spatial Vector to selected clause node...', 'secondary', 'center_focus_strong')
                        }}
                        style={{
                          background: 'var(--sc-surface-high)',
                          border: '1px solid rgba(70, 69, 85, 0.3)',
                          color: 'var(--sc-on-surface)',
                          padding: '6px 14px',
                          borderRadius: '8px',
                          fontFamily: 'JetBrains Mono, monospace',
                          fontSize: '11px',
                          fontWeight: 500,
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          cursor: 'pointer',
                        }}
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: '16px', color: '#4cd7f6' }}>{c.btnIcon}</span>
                        <span>{c.btnText}</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Interactive Simulation Drawer / Bottom Command Deck */}
          <div style={{ padding: '0 24px 32px 24px', zIndex: 10 }}>
            <div style={{ background: 'rgba(23, 27, 38, 0.9)', backdropFilter: 'blur(16px)', border: '1px solid rgba(70, 69, 85, 0.3)', borderRadius: '16px', padding: '24px', boxShadow: '0 20px 40px rgba(0,0,0,0.6)', display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', borderBottom: '1px solid rgba(70, 69, 85, 0.2)', paddingBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ width: '36px', height: '36px', borderRadius: '8px', background: 'var(--sc-surface-highest)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#4cd7f6', border: '1px solid rgba(70, 69, 85, 0.3)' }}>
                    <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>model_training</span>
                  </div>
                  <div>
                    <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--sc-on-surface)', margin: 0 }}>Scenario Playbook Stress Tester</h3>
                    <p style={{ fontSize: '12px', color: 'var(--sc-outline-variant)', margin: '2px 0 0 0' }}>Simulate fallback posture and liability caps against corporate balance sheet thresholds.</p>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: 'var(--sc-outline)' }}>Jurisdiction Preset:</span>
                  <div style={{ display: 'flex', borderRadius: '8px', background: 'var(--sc-surface)', padding: '4px', gap: '4px', border: '1px solid rgba(70, 69, 85, 0.3)' }}>
                    {[
                      { key: 'delaware', label: 'Delaware Chancery' },
                      { key: 'ny', label: 'New York' },
                      { key: 'uk', label: 'England & Wales' },
                    ].map((j) => (
                      <button
                        key={j.key}
                        type="button"
                        onClick={() => {
                          setActiveJurisdiction(j.key)
                          showToast(`Jurisdiction preset updated to ${j.label}`, 'secondary', 'gavel')
                        }}
                        style={{
                          padding: '4px 10px',
                          borderRadius: '6px',
                          background: activeJurisdiction === j.key ? 'var(--sc-primary-container)' : 'transparent',
                          color: activeJurisdiction === j.key ? '#ffffff' : 'var(--sc-outline)',
                          fontFamily: 'JetBrains Mono, monospace',
                          fontSize: '11px',
                          fontWeight: activeJurisdiction === j.key ? 700 : 500,
                          border: 'none',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        {j.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Parameter Sliders */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px', background: 'rgba(28, 31, 42, 0.7)', border: '1px solid rgba(70, 69, 85, 0.3)', padding: '20px', borderRadius: '12px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '12px', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '9999px', background: '#4cd7f6' }} />
                      Aggregate Liability Cap Multiplier
                    </span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', fontWeight: 600, color: '#4cd7f6' }}>
                      {multiplierLabels[sliderMultiplier]}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="5"
                    value={sliderMultiplier}
                    onChange={(e) => setSliderMultiplier(Number(e.target.value))}
                    style={{ width: '100%', accentColor: '#4cd7f6', cursor: 'pointer' }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'JetBrains Mono, monospace', fontSize: '10px', color: 'var(--sc-outline-variant)' }}>
                    <span>6 Mo</span>
                    <span style={{ color: 'var(--sc-on-surface)', fontWeight: 500 }}>12 Mo (Standard)</span>
                    <span>24 Mo</span>
                    <span style={{ color: 'var(--sc-error)' }}>Uncapped</span>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '12px', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '9999px', background: 'var(--sc-outline-variant)' }} />
                      Indemnity Super-Cap Carve-out Severity
                    </span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', fontWeight: 600, color: '#ffb4ab' }}>
                      {severityLabels[sliderSeverity]}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="4"
                    value={sliderSeverity}
                    onChange={(e) => setSliderSeverity(Number(e.target.value))}
                    style={{ width: '100%', accentColor: '#ffb4ab', cursor: 'pointer' }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'JetBrains Mono, monospace', fontSize: '10px', color: 'var(--sc-outline-variant)' }}>
                    <span>None</span>
                    <span style={{ color: 'var(--sc-on-surface)', fontWeight: 500 }}>Strict 2x</span>
                    <span>5x Fee</span>
                    <span style={{ color: 'var(--sc-error)' }}>Unlimited</span>
                  </div>
                </div>
              </div>

              {/* Simulator Output Bar */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', background: 'rgba(10, 14, 24, 0.9)', border: '1px solid rgba(70, 69, 85, 0.3)', padding: '16px', borderRadius: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--sc-surface-high)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#4cd7f6' }}>
                    <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>insights</span>
                  </div>
                  <span style={{ fontSize: '12px', color: 'var(--sc-on-surface)' }}>
                    Simulated Portfolio Risk Impact:{' '}
                    <span style={{ color: '#4cd7f6', fontWeight: 600, fontFamily: 'JetBrains Mono, monospace' }}>
                      {impactLabels[sliderMultiplier]}
                    </span>
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => showToast('Simulated parameters synced to Active Drafting Playbook', 'primary', 'check_circle')}
                  style={{
                    background: 'var(--sc-surface-highest)',
                    border: '1px solid rgba(70, 69, 85, 0.4)',
                    color: 'var(--sc-on-surface)',
                    padding: '8px 16px',
                    borderRadius: '8px',
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: '11px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  Apply to Drafting Playbook
                </button>
              </div>
            </div>
          </div>

          {/* Real Contract Ingestion & Drop Box Zone */}
            <section
              id="contract-drop-zone"
              style={{
                marginTop: '32px',
                padding: '28px',
                borderRadius: '16px',
                background: 'rgba(10, 14, 24, 0.85)',
                border: '1px solid rgba(70, 69, 85, 0.35)',
                backdropFilter: 'blur(16px)',
                position: 'relative',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'rgba(76, 215, 246, 0.1)', border: '1px solid rgba(76, 215, 246, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#4cd7f6' }}>
                    <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>upload_file</span>
                  </div>
                  <div>
                    <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--sc-on-surface)', margin: 0 }}>
                      Contract Ingestion &amp; Neural Risk Engine
                    </h2>
                    <p style={{ fontSize: '11px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--sc-outline)', margin: '2px 0 0 0' }}>
                      Drag and drop PDF, DOCX, or TXT agreements for real-time risk classification &amp; semantic indexing
                    </p>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '11px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--sc-outline-variant)' }}>
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
                className={`sc-drop-box ${dragActive ? 'drag-active' : ''} ${uploadError ? 'has-error' : ''}`}
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
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px', padding: '24px 0' }}>
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
                      <p style={{ fontSize: '15px', fontWeight: 600, color: '#4cd7f6', marginBottom: '4px' }}>
                        Analyzing Contract with Legal-BERT &amp; SBERT...
                      </p>
                      <p style={{ fontSize: '12px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--sc-outline)' }}>
                        Segmenting clauses, categorizing risk tiers, and computing high-dimensional vectors
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
                        boxShadow: dragActive ? '0 0 30px rgba(76, 215, 246, 0.5)' : 'none',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: '32px' }}>
                        cloud_upload
                      </span>
                    </div>

                    <div style={{ textAlign: 'center' }}>
                      <p style={{ fontSize: '16px', fontWeight: 700, color: 'var(--sc-on-surface)', marginBottom: '4px' }}>
                        Drop Contract File Here to Ingest
                      </p>
                      <p style={{ fontSize: '13px', color: 'var(--sc-outline)' }}>
                        Drag &amp; drop your agreement, or{' '}
                        <span style={{ color: '#4cd7f6', textDecoration: 'underline', fontWeight: 600 }}>
                          browse local device
                        </span>
                      </p>
                    </div>

                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center' }}>
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
                    <span className="material-symbols-outlined" style={{ color: '#ffb4ab', fontSize: '18px' }}>
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
                    }}
                    title="Dismiss error"
                  >
                    ✕
                  </button>
                </div>
              )}
            </section>

            {/* Live Contract Audit Results Stream */}
            {liveResult && (
              <section
                id="contract-audit-results"
                style={{
                  marginTop: '28px',
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
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                      <span className="material-symbols-outlined" style={{ color: '#4cd7f6', fontSize: '22px' }}>
                        description
                      </span>
                      <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--sc-on-surface)', margin: 0 }}>
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
                              ? '#fef3c7'
                              : '#d1fae5',
                          border: `1px solid ${
                            liveResult.risk_summary?.overall_risk === 'High'
                              ? 'rgba(220, 38, 38, 0.5)'
                              : liveResult.risk_summary?.overall_risk === 'Medium'
                              ? 'rgba(217, 119, 6, 0.5)'
                              : 'rgba(5, 150, 105, 0.5)'
                          }`,
                        }}
                      >
                        {liveResult.risk_summary?.overall_risk || 'Low'} Risk
                      </span>
                    </div>
                    <p style={{ fontSize: '12px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--sc-outline)', margin: 0 }}>
                      {liveResult.char_count?.toLocaleString()} characters • {liveResult.clauses?.length || 0} extracted clauses • Document ID: {liveResult.document_id?.slice(0, 8)}...
                    </p>
                  </div>

                  <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <button
                      type="button"
                      onClick={() => {
                        setLiveResult(null)
                        setSearchResults(null)
                        setSearchQuery('')
                      }}
                      style={{
                        background: 'rgba(70, 69, 85, 0.3)',
                        border: '1px solid rgba(70, 69, 85, 0.5)',
                        color: 'var(--sc-on-surface)',
                        padding: '8px 14px',
                        borderRadius: '8px',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      Audit Another Contract
                    </button>
                  </div>
                </div>

                {/* Clause Heat-Map (Feature 3) */}
                {liveResult.clauses && liveResult.clauses.length > 0 && (
                  <HeatMap clauses={liveResult.clauses} />
                )}

                {/* Ask-the-Contract Semantic Search Bar (Feature 4) */}
                <div
                  style={{
                    background: 'rgba(23, 27, 38, 0.85)',
                    border: '1px solid rgba(70, 69, 85, 0.35)',
                    padding: '16px 20px',
                    borderRadius: '12px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                    backdropFilter: 'blur(12px)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className="material-symbols-outlined" style={{ color: '#4cd7f6', fontSize: '18px' }}>
                        search
                      </span>
                      <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--sc-on-surface)' }}>
                        Ask-the-Contract (Semantic Search)
                      </span>
                    </div>
                    <span style={{ fontSize: '11px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--sc-outline)' }}>
                      Similarity ranks clauses. It is not a confidence score.
                    </span>
                  </div>

                  <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px' }}>
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Ask a question (e.g. 'when can I terminate?', 'what is the liability cap?')"
                      style={{
                        flex: 1,
                        background: 'rgba(10, 14, 24, 0.8)',
                        border: '1px solid rgba(70, 69, 85, 0.5)',
                        borderRadius: '8px',
                        padding: '10px 14px',
                        color: 'var(--sc-on-surface)',
                        fontSize: '13px',
                        outline: 'none',
                      }}
                    />
                    <button
                      type="submit"
                      disabled={searchLoading || !searchQuery.trim()}
                      style={{
                        background: '#4f46e5',
                        border: 'none',
                        color: '#ffffff',
                        padding: '10px 18px',
                        borderRadius: '8px',
                        fontSize: '13px',
                        fontWeight: 600,
                        cursor: searchLoading || !searchQuery.trim() ? 'not-allowed' : 'pointer',
                        opacity: searchLoading || !searchQuery.trim() ? 0.6 : 1,
                      }}
                    >
                      {searchLoading ? 'Searching...' : 'Search'}
                    </button>
                    {searchResults && (
                      <button
                        type="button"
                        onClick={handleClearSearch}
                        style={{
                          background: 'rgba(70, 69, 85, 0.4)',
                          border: '1px solid rgba(70, 69, 85, 0.6)',
                          color: 'var(--sc-on-surface)',
                          padding: '10px 14px',
                          borderRadius: '8px',
                          fontSize: '13px',
                          cursor: 'pointer',
                        }}
                      >
                        Clear
                      </button>
                    )}
                  </form>

                  {searchResults && (
                    <div style={{ fontSize: '12px', color: '#4cd7f6', fontFamily: 'JetBrains Mono, monospace' }}>
                      Showing top {searchResults.length} ranked clauses matching &quot;{searchQuery}&quot; (top 3 highlighted, non-matches dimmed to 50%)
                    </div>
                  )}
                </div>

                {/* Clause Cards Stream */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--sc-on-surface)', margin: 0 }}>
                      Audited Contract Clauses ({liveResult.clauses?.length || 0})
                    </h3>
                    <span style={{ fontSize: '11px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--sc-outline)' }}>
                      Scroll to any clause via Heat-Map or search
                    </span>
                  </div>

                  {liveResult.clauses?.map((clause, idx) => {
                    const searchMatch = searchResults?.find(
                      (r) => r.clause_id === clause.id || r.position === clause.position
                    )
                    const isTop3 = searchResults && searchResults.slice(0, 3).some(
                      (r) => r.clause_id === clause.id || r.position === clause.position
                    )
                    const isDimmed = searchResults && searchResults.length > 0 && !isTop3
                    const expInfo = explanations.clauses?.[clause.label]
                    const redlineKey = clause.id !== undefined ? clause.id : idx
                    const redline = clauseRedlines[redlineKey]
                    const isRedlineLoading = redlineLoading[redlineKey]

                    return (
                      <article
                        key={clause.id || idx}
                        id={`clause-${clause.position}`}
                        className="sc-clause-card"
                        style={{
                          opacity: isDimmed ? 0.5 : 1,
                          borderLeft: isTop3 ? '4px solid #4cd7f6' : undefined,
                          boxShadow: isTop3 ? '0 0 24px rgba(76, 215, 246, 0.25)' : undefined,
                        }}
                      >
                        {/* Search Similarity Bar (Feature 4) */}
                        {isTop3 && searchMatch && (
                          <div
                            style={{
                              marginBottom: '12px',
                              padding: '8px 12px',
                              background: 'rgba(76, 215, 246, 0.12)',
                              border: '1px solid rgba(76, 215, 246, 0.3)',
                              borderRadius: '6px',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              fontSize: '11px',
                              fontFamily: 'JetBrains Mono, monospace',
                              color: '#4cd7f6',
                            }}
                          >
                            <span>
                              Top Match • Similarity: {(searchMatch.similarity * 100).toFixed(1)}% ({searchMatch.similarity.toFixed(4)})
                            </span>
                            <span style={{ fontSize: '10px', color: 'var(--sc-outline)' }}>
                              Ranked Result
                            </span>
                          </div>
                        )}

                        {/* Header row: Clause index, Label, Risk Badge, Confidence, Read-Aloud */}
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
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span
                              style={{
                                fontFamily: 'JetBrains Mono, monospace',
                                fontSize: '11px',
                                fontWeight: 700,
                                color: 'var(--sc-outline)',
                              }}
                            >
                              #{clause.position + 1}
                            </span>
                            <span
                              style={{
                                fontSize: '13px',
                                fontWeight: 700,
                                color: 'var(--sc-on-surface)',
                              }}
                            >
                              {clause.label}
                            </span>
                            {clause.risk_level && (
                              <span
                                style={{
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  fontSize: '10px',
                                  fontFamily: 'JetBrains Mono, monospace',
                                  fontWeight: 700,
                                  background:
                                    clause.risk_level === 'High'
                                      ? 'rgba(220, 38, 38, 0.2)'
                                      : clause.risk_level === 'Medium'
                                      ? 'rgba(217, 119, 6, 0.2)'
                                      : 'rgba(5, 150, 105, 0.2)',
                                  color:
                                    clause.risk_level === 'High'
                                      ? '#ffb4ab'
                                      : clause.risk_level === 'Medium'
                                      ? '#fef3c7'
                                      : '#d1fae5',
                                  border: `1px solid ${
                                    clause.risk_level === 'High'
                                      ? 'rgba(220, 38, 38, 0.4)'
                                      : clause.risk_level === 'Medium'
                                      ? 'rgba(217, 119, 6, 0.4)'
                                      : 'rgba(5, 150, 105, 0.4)'
                                  }`,
                                }}
                              >
                                {clause.risk_level} Risk
                              </span>
                            )}
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <span
                              style={{
                                fontSize: '11px',
                                fontFamily: 'JetBrains Mono, monospace',
                                color: 'var(--sc-outline)',
                              }}
                            >
                              {(clause.confidence * 100).toFixed(1)}% confidence
                            </span>

                            {/* Read-Aloud Button (Feature 7) */}
                            <button
                              type="button"
                              onClick={() => handleReadAloud(clause, idx)}
                              disabled={!('speechSynthesis' in window)}
                              style={{
                                background: speakingIdx === idx ? 'rgba(76, 215, 246, 0.2)' : 'none',
                                border: `1px solid ${speakingIdx === idx ? '#4cd7f6' : 'rgba(70, 69, 85, 0.4)'}`,
                                color: speakingIdx === idx ? '#4cd7f6' : 'var(--sc-outline)',
                                padding: '4px 8px',
                                borderRadius: '6px',
                                fontSize: '11px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                cursor: 'speechSynthesis' in window ? 'pointer' : 'not-allowed',
                              }}
                              title="Read plain-English explanation aloud"
                            >
                              <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>
                                {speakingIdx === idx ? 'volume_up' : 'volume_mute'}
                              </span>
                              <span>{speakingIdx === idx ? 'Stop' : 'Read'}</span>
                            </button>
                          </div>
                        </div>

                        {/* Plain English Explanation Box */}
                        {expInfo && (
                          <div
                            style={{
                              background: 'rgba(10, 14, 24, 0.6)',
                              border: '1px solid rgba(70, 69, 85, 0.25)',
                              borderRadius: '8px',
                              padding: '12px 14px',
                              marginBottom: '12px',
                            }}
                          >
                            <div style={{ fontSize: '11px', fontWeight: 600, color: '#4cd7f6', marginBottom: '4px' }}>
                              Plain English Explanation
                            </div>
                            <p style={{ fontSize: '12px', color: 'var(--sc-on-surface-variant)', lineHeight: 1.5, margin: '0 0 6px 0' }}>
                              {clause.legal?.plain_note || expInfo.summary || expInfo.why_risky}
                            </p>
                            {expInfo.what_to_negotiate?.[0] && (
                              <p style={{ fontSize: '11px', color: '#ffb3ad', margin: 0 }}>
                                <strong>Negotiation Tip:</strong> {expInfo.what_to_negotiate[0]}
                              </p>
                            )}
                          </div>
                        )}

                        {/* Original Clause Legal Text */}
                        <div
                          style={{
                            background: 'rgba(10, 14, 24, 0.8)',
                            border: '1px solid rgba(70, 69, 85, 0.2)',
                            borderRadius: '8px',
                            padding: '12px 14px',
                            fontSize: '12px',
                            fontFamily: 'JetBrains Mono, monospace',
                            color: 'var(--sc-on-surface)',
                            lineHeight: 1.6,
                            whiteSpace: 'pre-wrap',
                            marginBottom: '12px',
                          }}
                        >
                          {clause.text}
                        </div>

                        {/* Redline Action & Diff Container (Feature 1) */}
                        <div>
                          <button
                            type="button"
                            onClick={() => handleToggleRedline(clause, redlineKey)}
                            disabled={isRedlineLoading}
                            style={{
                              background: 'rgba(79, 70, 229, 0.15)',
                              border: '1px solid rgba(79, 70, 229, 0.4)',
                              color: '#c3c0ff',
                              padding: '6px 12px',
                              borderRadius: '6px',
                              fontSize: '11px',
                              fontWeight: 600,
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                              cursor: isRedlineLoading ? 'not-allowed' : 'pointer',
                            }}
                          >
                            <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>
                              edit_note
                            </span>
                            <span>
                              {isRedlineLoading
                                ? 'Evaluating redline...'
                                : redline
                                ? 'Hide safer wording'
                                : 'Suggest safer wording'}
                            </span>
                          </button>

                          {/* Rendered Redline Diff */}
                          {redline && (
                            <div
                              style={{
                                marginTop: '12px',
                                padding: '14px',
                                background: 'rgba(10, 14, 24, 0.9)',
                                border: '1px solid rgba(70, 69, 85, 0.4)',
                                borderRadius: '8px',
                              }}
                            >
                              {redline.error ? (
                                <p style={{ color: '#ffb4ab', fontSize: '12px', margin: 0 }}>
                                  {redline.error}
                                </p>
                              ) : (
                                <>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                    <span style={{ fontSize: '11px', fontWeight: 600, color: '#4cd7f6' }}>
                                      Safer Redline Proposal
                                    </span>
                                    {redline.verify_status && (
                                      <span
                                        style={{
                                          fontSize: '10px',
                                          fontFamily: 'JetBrains Mono, monospace',
                                          padding: '1px 6px',
                                          borderRadius: '4px',
                                          background: 'rgba(70, 69, 85, 0.4)',
                                          color: 'var(--sc-outline)',
                                        }}
                                      >
                                        {redline.verify_status}
                                      </span>
                                    )}
                                  </div>

                                  {/* Diff Segments with WCAG accessible prefixes */}
                                  <div
                                    style={{
                                      fontFamily: 'JetBrains Mono, monospace',
                                      fontSize: '12px',
                                      lineHeight: 1.7,
                                      padding: '10px',
                                      background: 'rgba(0, 0, 0, 0.4)',
                                      borderRadius: '6px',
                                      marginBottom: '10px',
                                    }}
                                  >
                                    {redline.diff_segments?.map((seg, sIdx) => {
                                      if (seg.type === 'delete') {
                                        return (
                                          <del
                                            key={sIdx}
                                            style={{
                                              color: '#ffb4ab',
                                              backgroundColor: 'rgba(147, 0, 10, 0.35)',
                                              textDecoration: 'line-through',
                                              padding: '1px 3px',
                                              borderRadius: '2px',
                                            }}
                                          >
                                            <span style={{ position: 'absolute', width: '1px', height: '1px', padding: 0, margin: '-1px', overflow: 'hidden', clip: 'rect(0,0,0,0)', border: 0 }}>
                                              removed: 
                                            </span>
                                            {seg.text}
                                          </del>
                                        )
                                      }
                                      if (seg.type === 'insert') {
                                        return (
                                          <ins
                                            key={sIdx}
                                            style={{
                                              color: '#d1fae5',
                                              backgroundColor: 'rgba(5, 150, 105, 0.35)',
                                              textDecoration: 'underline',
                                              fontWeight: 'bold',
                                              padding: '1px 3px',
                                              borderRadius: '2px',
                                            }}
                                          >
                                            <span style={{ position: 'absolute', width: '1px', height: '1px', padding: 0, margin: '-1px', overflow: 'hidden', clip: 'rect(0,0,0,0)', border: 0 }}>
                                              added: 
                                            </span>
                                            {seg.text}
                                          </ins>
                                        )
                                      }
                                      return <span key={sIdx} style={{ color: 'var(--sc-on-surface)' }}>{seg.text}</span>
                                    })}
                                  </div>

                                  {redline.rationale && (
                                    <p style={{ fontSize: '11px', color: 'var(--sc-on-surface-variant)', margin: 0 }}>
                                      <strong style={{ color: '#c3c0ff' }}>Rationale:</strong> {redline.rationale}
                                    </p>
                                  )}
                                </>
                              )}
                            </div>
                          )}
                        </div>
                      </article>
                    )
                  })}
                </div>
              </section>
            )}
        </main>
      </div>
    </div>
  )
}
