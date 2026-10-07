import { useState, useRef } from 'react'

const MAX_SIZE_BYTES = 10 * 1024 * 1024 // 10 MB
const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt']

function UploadBox({ onUpload, loading }) {
  const [dragActive, setDragActive] = useState(false)
  const [errorMessage, setErrorMessage] = useState(null)
  const inputRef = useRef(null)

  const validateAndUpload = (file) => {
    setErrorMessage(null)
    if (!file) return

    const lowerName = file.name.toLowerCase()
    const isValidExt = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext))
    if (!isValidExt) {
      setErrorMessage(`Unsupported file format. Please upload a PDF, DOCX, or TXT file.`)
      return
    }

    if (file.size > MAX_SIZE_BYTES) {
      setErrorMessage(`File exceeds the maximum limit of 10 MB.`)
      return
    }

    onUpload(file)
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

  const handleChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndUpload(e.target.files[0])
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      inputRef.current?.click()
    }
  }

  return (
    <div style={{ marginBottom: 'var(--space-lg)' }}>
      <div
        className={`upload-box ${dragActive ? 'upload-box--active' : ''} ${errorMessage ? 'upload-box--error' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={loading ? -1 : 0}
        aria-label="Upload contract file (PDF, DOCX, TXT up to 10 MB)"
        style={{
          border: errorMessage
            ? '2px solid var(--risk-high-border)'
            : dragActive
            ? '2px dashed var(--border-focus)'
            : '2px dashed var(--border-strong)',
          borderRadius: 'var(--radius)',
          padding: 'var(--space-2xl) var(--space-lg)',
          textAlign: 'center',
          cursor: loading ? 'not-allowed' : 'pointer',
          backgroundColor: errorMessage
            ? 'var(--risk-high-bg)'
            : dragActive
            ? 'var(--bg-hover)'
            : 'var(--surface)',
          transition: 'all 0.2s ease',
          opacity: loading ? 0.6 : 1,
          minHeight: '220px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 'var(--space-xs)',
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={handleChange}
          style={{ display: 'none' }}
          disabled={loading}
          aria-hidden="true"
        />
        <div style={{ fontSize: '48px', lineHeight: 1 }} aria-hidden="true">
          📄
        </div>
        <p
          style={{
            fontSize: '24px',
            fontWeight: 600,
            color: 'var(--text)',
            lineHeight: 1.3,
            margin: 'var(--space-2xs) 0',
          }}
        >
          Drop your contract here or click to browse
        </p>
        <p
          style={{
            fontSize: '15px',
            color: 'var(--text-muted)',
            fontWeight: 500,
          }}
        >
          Accepted formats: PDF, DOCX, TXT &bull; Max 10 MB
        </p>
      </div>

      {errorMessage && (
        <div
          role="alert"
          style={{
            marginTop: 'var(--space-xs)',
            padding: 'var(--space-sm) var(--space-md)',
            border: '1px solid var(--risk-high-border)',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--risk-high-bg)',
            color: 'var(--risk-high)',
            fontSize: '14px',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-xs)',
          }}
        >
          <span aria-hidden="true">⚠️</span>
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  )
}

export default UploadBox
