import { useState, useRef } from 'react'

function UploadBox({ onUpload, loading }) {
  const [dragActive, setDragActive] = useState(false)
  const inputRef = useRef(null)

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
      onUpload(e.dataTransfer.files[0])
    }
  }

  const handleChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      onUpload(e.target.files[0])
    }
  }

  return (
    <div
      className={`upload-box ${dragActive ? 'upload-box--active' : ''}`}
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      style={{
        border: `2px dashed ${dragActive ? 'var(--primary)' : 'var(--border)'}`,
        borderRadius: 'var(--radius)',
        padding: '48px 24px',
        textAlign: 'center',
        cursor: loading ? 'not-allowed' : 'pointer',
        background: dragActive ? 'rgba(79, 70, 229, 0.04)' : 'var(--surface)',
        transition: 'all 0.2s ease',
        opacity: loading ? 0.6 : 1,
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        onChange={handleChange}
        style={{ display: 'none' }}
        disabled={loading}
      />
      <div style={{ fontSize: '48px', marginBottom: '16px' }}>📄</div>
      <p style={{ fontSize: '16px', fontWeight: 600, marginBottom: '8px' }}>
        Drop your contract here or click to browse
      </p>
      <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
        Supports PDF, DOCX, TXT (max 10 MB)
      </p>
    </div>
  )
}

export default UploadBox
