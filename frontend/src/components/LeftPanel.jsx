import React, { useRef, useState } from 'react';

/**
 * LeftPanel component matching Screenshot 2:
 * - Dotted drop box for uploading contracts
 * - Storage / Document statistics bar
 * - Uploaded Documents list with active state, size, date, download, and delete actions
 */
export default function LeftPanel({
  documents = [],
  activeDocId,
  onSelectDoc,
  onUpload,
  onDeleteDoc,
  isUploading = false,
  uploadError = null,
  isCollapsed = false,
  onToggleCollapse,
  sensitivity = 'balanced',
  onSensitivityChange,
}) {
  const fileInputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (file) => {
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!['.pdf', '.docx', '.txt'].includes(ext)) {
      alert('Only .pdf, .docx, and .txt files are supported.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      alert('File exceeds maximum size of 10MB.');
      return;
    }
    if (onUpload) {
      onUpload(file, sensitivity);
    }
  };

  const formatFileSize = (charCount) => {
    if (!charCount && charCount !== 0) return '0 KB';
    // Approximation if only char_count is available (1 char ~ 1 byte)
    const kb = (charCount / 1024).toFixed(1);
    return `${kb} KB`;
  };

  const formatDate = (isoString) => {
    if (!isoString) return '';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return '';
    }
  };

  const getFileIcon = (fileType) => {
    const type = (fileType || '').toLowerCase();
    if (type.includes('pdf')) return '📕';
    if (type.includes('docx') || type.includes('doc')) return '📘';
    return '📄';
  };

  const handleDownload = (e, doc) => {
    e.stopPropagation();
    // Create text file download for the contract
    const blob = new Blob([doc.text || `Contract: ${doc.filename}\nRisk: ${doc.overall_risk || 'N/A'}`], {
      type: 'text/plain;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = doc.filename.endsWith('.txt') ? doc.filename : `${doc.filename}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleDelete = (e, docId) => {
    e.stopPropagation();
    if (window.confirm('Delete this analyzed document?')) {
      if (onDeleteDoc) onDeleteDoc(docId);
    }
  };

  return (
    <aside className={`dd-left-panel ${isCollapsed ? 'collapsed' : ''}`}>
      {/* Sensitivity Preset Control */}
      <div className="dd-sensitivity-card" style={{ marginBottom: '14px', padding: '12px', background: 'rgba(255, 255, 255, 0.04)', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8' }}>Sensitivity Preset</span>
          <span style={{ fontSize: '11px', color: '#38bdf8', fontWeight: 600 }}>{sensitivity.toUpperCase()}</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '4px', marginBottom: '8px' }}>
          {[
            { key: 'strict', label: 'Strict (3)', fa: 3 },
            { key: 'balanced', label: 'Balanced (8)', fa: 8 },
            { key: 'thorough', label: 'Thorough (12)', fa: 12 },
          ].map((preset) => (
            <button
              key={preset.key}
              type="button"
              title={`${preset.fa} false alarms per contract (measured on 77 held-out CUAD contracts)`}
              onClick={() => onSensitivityChange && onSensitivityChange(preset.key)}
              style={{
                padding: '6px 4px',
                fontSize: '11px',
                fontWeight: sensitivity === preset.key ? 700 : 500,
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                background: sensitivity === preset.key ? '#38bdf8' : 'rgba(255, 255, 255, 0.06)',
                color: sensitivity === preset.key ? '#0f172a' : '#cbd5e1',
                transition: 'all 0.15s ease',
              }}
            >
              {preset.label}
            </button>
          ))}
        </div>
        <p style={{ margin: 0, fontSize: '11px', color: '#94a3b8', lineHeight: 1.4 }}>
          {sensitivity === 'strict' && 'Strict: 3 false alarms per contract (measured on 77 held-out CUAD contracts).'}
          {sensitivity === 'balanced' && 'Balanced: 8 false alarms per contract (measured on 77 held-out CUAD contracts).'}
          {sensitivity === 'thorough' && 'Thorough: 12 false alarms per contract (measured on 77 held-out CUAD contracts).'}
        </p>
        <p style={{ margin: '6px 0 0 0', fontSize: '10px', color: '#64748b', fontStyle: 'italic', lineHeight: 1.3 }}>
          Trade-off: Higher sensitivity catches more risky clauses (higher recall) at the cost of reviewing more non-risky units (more false alarms).
        </p>
      </div>

      {/* Upload Drop Box */}
      <div
        className={`dd-drop-box ${dragActive ? 'drag-active' : ''} ${isUploading ? 'uploading' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            fileInputRef.current?.click();
          }
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={handleChange}
          style={{ display: 'none' }}
        />
        <div className="dd-drop-box-icon">
          {isUploading ? (
            <span className="dd-spinner" />
          ) : (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          )}
        </div>
        <p className="dd-drop-box-title">
          {isUploading ? (
            'Analyzing contract with Legal-BERT…'
          ) : (
            <>
              Drop documents here or <span>browse</span>
            </>
          )}
        </p>
        <p className="dd-drop-box-sub">
          PDF, DOCX, TXT up to 10MB each
        </p>
      </div>

      {uploadError && (
        <div className="dd-upload-error">
          <span>⚠️ {uploadError}</span>
        </div>
      )}

      {/* Uploaded Documents List */}
      <div className="dd-section-header">
        <h3 className="dd-section-title">Uploaded Documents</h3>
        <span className="dd-doc-count-badge">{documents.length}</span>
      </div>

      <div className="dd-doc-list">
        {documents.length === 0 ? (
          <div className="dd-doc-empty">
            <p>No documents uploaded yet.</p>
            <small>Drop a file above to begin risk analysis.</small>
          </div>
        ) : (
          documents.map((doc) => {
            const isActive = doc.id === activeDocId;
            return (
              <div
                key={doc.id}
                className={`dd-doc-card ${isActive ? 'active' : ''}`}
                onClick={() => onSelectDoc && onSelectDoc(doc.id)}
              >
                <div className="dd-doc-info">
                  <div className="dd-doc-icon">
                    {getFileIcon(doc.file_type || doc.filename)}
                  </div>
                  <div className="dd-doc-meta">
                    <div className="dd-doc-name" title={doc.filename}>
                      {doc.filename}
                    </div>
                    <div className="dd-doc-sub">
                      <span>{formatFileSize(doc.char_count)}</span>
                      <span>•</span>
                      <span>{formatDate(doc.created_at)}</span>
                      {doc.overall_risk && (
                        <>
                          <span>•</span>
                          <span
                            className={`dd-risk-tag ${doc.overall_risk.toLowerCase()}`}
                          >
                            {doc.overall_risk}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="dd-doc-actions">
                  <button
                    className="dd-doc-btn"
                    title="Download text"
                    onClick={(e) => handleDownload(e, doc)}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                  </button>
                  <button
                    className="dd-doc-btn delete"
                    title="Delete document"
                    onClick={(e) => handleDelete(e, doc.id)}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
