import React, { useState, useRef, useEffect } from 'react';
import { getRiskyClauses, getUnflaggedClauses } from '../utils/risks';

/**
 * DocumentViewer3D component matching Screenshot 1:
 * - Digital paper sheet with subtle 3D depth, perspective, and mouse-tilt
 * - Top Toolbar: page nav, risk count pills, zoom controls, 3D toggle, semantic search
 * - Paper sheet with exact inline text highlights (Red = High, Yellow = Medium, Teal/Cream = Low)
 * - Vertical minimap tick strip showing clause risk distribution
 * - Bidirectional selection: clicking clause highlights it and opens right finding
 */
export default function DocumentViewer3D({
  documentData,
  activeClauseId,
  onSelectClause,
  searchQuery,
  onSearch,
  searchResults = [],
  isSearching = false,
}) {
  const [zoomLevel, setZoomLevel] = useState(100);
  const [is3DMode, setIs3DMode] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [mouseTilt, setMouseTilt] = useState({ rotateX: 0, rotateY: 0 });
  const [filterRisk, setFilterRisk] = useState(null); // 'High', 'Medium', 'Low', or null
  const [hoveredClauseId, setHoveredClauseId] = useState(null);
  const [searchInputValue, setSearchInputValue] = useState('');
  const [showUnflagged, setShowUnflagged] = useState(false);

  const stageRef = useRef(null);
  const paperRef = useRef(null);
  const clauseRefs = useRef({});

  const clauses = documentData?.clauses || [];
  const riskSummary = documentData?.risk_summary || {
    overall_risk: 'Low',
    high_count: 0,
    medium_count: 0,
    low_count: 0,
    none_count: 0,
    total_clauses: clauses.length,
  };

  // Reset risk filter when active document changes
  useEffect(() => {
    setFilterRisk(null);
    setCurrentPage(1);
    setShowUnflagged(false);
  }, [documentData?.id, documentData?.filename]);

  // Partition clauses: show flagged units first, group unflagged into expander
  const flaggedClauses = getRiskyClauses(clauses);
  const unflaggedClauses = getUnflaggedClauses(clauses);

  const displayFlagged = filterRisk
    ? flaggedClauses.filter((c) => (c.risk_tier || c.risk_level) === filterRisk)
    : flaggedClauses;

  // Pagination for flagged clauses: 6 per page
  const CLAUSES_PER_PAGE = 6;
  const totalPages = Math.max(1, Math.ceil(displayFlagged.length / CLAUSES_PER_PAGE));
  const pageClauses = displayFlagged.slice(
    (currentPage - 1) * CLAUSES_PER_PAGE,
    currentPage * CLAUSES_PER_PAGE
  );

  // Synchronize page when activeClauseId changes
  useEffect(() => {
    if (activeClauseId) {
      const idx = displayFlagged.findIndex((c) => c.id === activeClauseId);
      if (idx !== -1) {
        const targetPage = Math.floor(idx / CLAUSES_PER_PAGE) + 1;
        if (targetPage !== currentPage) {
          setCurrentPage(targetPage);
        }
        setTimeout(() => {
          const el = clauseRefs.current[activeClauseId];
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }, 100);
      }
    }
  }, [activeClauseId, displayFlagged]);

  // Subtle 3D mouse tilt over stage (max 3 degrees, respects prefers-reduced-motion)
  const handleMouseMove = (e) => {
    if (!is3DMode) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    if (!stageRef.current) return;
    const rect = stageRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    // Subtle pitch and yaw (max ~2.5 deg)
    const rotateY = ((x - centerX) / centerX) * 2.5;
    const rotateX = -((y - centerY) / centerY) * 2.5;

    setMouseTilt({ rotateX, rotateY });
  };

  const handleMouseLeave = () => {
    setMouseTilt({ rotateX: 0, rotateY: 0 });
  };

  // Zoom handlers
  const handleZoomIn = () => setZoomLevel((z) => Math.min(160, z + 10));
  const handleZoomOut = () => setZoomLevel((z) => Math.max(70, z - 10));
  const handleResetZoom = () => setZoomLevel(100);

  // Search submission
  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (onSearch && searchInputValue.trim()) {
      onSearch(searchInputValue.trim());
    }
  };

  const clearSearch = () => {
    setSearchInputValue('');
    if (onSearch) onSearch('');
  };

  const getRiskClass = (riskLevel) => {
    if (riskLevel === 'High') return 'risk-high';
    if (riskLevel === 'Medium') return 'risk-medium';
    if (riskLevel === 'Low') return 'risk-low';
    return '';
  };

  return (
    <section className="dd-center">
      {/* Document Top Toolbar */}
      <div className="dd-toolbar">
        {/* Left: Page Navigation */}
        <div className="dd-toolbar-left">
          <div className="dd-page-nav">
            <button
              className="dd-nav-arrow"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              title="Previous Page"
            >
              ‹
            </button>
            <span className="dd-page-indicator">
              Page {currentPage} of {totalPages}
            </span>
            <button
              className="dd-nav-arrow"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
              title="Next Page"
            >
              ›
            </button>
          </div>

          <div className="dd-toolbar-divider" />

          {/* Risk Level Count Pills from Screenshot 1 */}
          <div className="dd-risk-pills">
            <span
              className={`dd-pill dd-pill-red ${filterRisk === 'High' ? 'selected' : ''}`}
              onClick={() => {
                setFilterRisk(filterRisk === 'High' ? null : 'High');
                setCurrentPage(1);
              }}
              title="Filter High Risk clauses"
              role="button"
              tabIndex={0}
            >
              ● {riskSummary.high_count} High
            </span>
            <span
              className={`dd-pill dd-pill-yellow ${filterRisk === 'Medium' ? 'selected' : ''}`}
              onClick={() => {
                setFilterRisk(filterRisk === 'Medium' ? null : 'Medium');
                setCurrentPage(1);
              }}
              title="Filter Medium Risk clauses"
              role="button"
              tabIndex={0}
            >
              ● {riskSummary.medium_count} Medium
            </span>
            <span
              className={`dd-pill dd-pill-teal ${filterRisk === 'Low' ? 'selected' : ''}`}
              onClick={() => {
                setFilterRisk(filterRisk === 'Low' ? null : 'Low');
                setCurrentPage(1);
              }}
              title="Filter Low Risk clauses"
              role="button"
              tabIndex={0}
            >
              ● {riskSummary.low_count} Low
            </span>
            {filterRisk && (
              <button
                className="dd-pill-clear"
                onClick={() => setFilterRisk(null)}
                title="Clear risk filter"
              >
                Clear filter
              </button>
            )}
          </div>
        </div>

        {/* Center: Semantic Natural Language Search */}
        <div className="dd-toolbar-center">
          <form className="dd-search-form" onSubmit={handleSearchSubmit}>
            <div className="dd-search-bar">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                placeholder="Search contract concepts (e.g. 'can I terminate early?')..."
                value={searchInputValue}
                onChange={(e) => setSearchInputValue(e.target.value)}
              />
              {searchInputValue && (
                <button
                  type="button"
                  className="dd-search-clear"
                  onClick={clearSearch}
                >
                  ✕
                </button>
              )}
              {isSearching && <span className="dd-search-spinner" />}
            </div>
          </form>
        </div>

        {/* Right: Zoom controls and 3D mode switch */}
        <div className="dd-toolbar-right">
          <div className="dd-zoom-controls">
            <button className="dd-zoom-btn" onClick={handleZoomOut} title="Zoom out">
              −
            </button>
            <span
              className="dd-zoom-level"
              onClick={handleResetZoom}
              title="Click to reset zoom"
              role="button"
              tabIndex={0}
            >
              {zoomLevel}%
            </span>
            <button className="dd-zoom-btn" onClick={handleZoomIn} title="Zoom in">
              +
            </button>
          </div>

          <button
            className={`dd-view-toggle ${is3DMode ? 'active' : ''}`}
            onClick={() => setIs3DMode(!is3DMode)}
            title="Toggle between 3D paper perspective and 2D flat reading"
          >
            {is3DMode ? '3D Sheet' : 'Flat View'}
          </button>
        </div>
      </div>

      {/* Center Stage: 3D Document Paper Canvas */}
      <div
        className="dd-center-stage dd-stage"
        ref={stageRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        {/* Left Vertical Minimap Strip */}
        <div className="dd-minimap-strip" title="Contract Minimap: click any tick to jump to clause">
          <div className="dd-minimap-header">MAP</div>
          <div className="dd-minimap-track">
            {clauses.map((c) => {
              const isMatch = searchResults.some((sr) => sr.clause_id === c.id);
              const isActive = c.id === activeClauseId;
              let tickClass = 'tick-none';
              if (c.risk_level === 'High') tickClass = 'tick-high';
              else if (c.risk_level === 'Medium') tickClass = 'tick-med';
              else if (c.risk_level === 'Low') tickClass = 'tick-low';

              return (
                <div
                  key={c.id}
                  className={`dd-minimap-tick ${tickClass} ${isActive ? 'tick-active' : ''} ${isMatch ? 'tick-match' : ''}`}
                  onClick={() => onSelectClause && onSelectClause(c.id)}
                  title={`#${c.position + 1}: ${c.label} (${c.risk_level || 'No Risk'})`}
                />
              );
            })}
          </div>
        </div>

        {/* 3D Perspective Viewport */}
        <div
          className={`dd-viewport-3d ${is3DMode ? 'mode-3d' : 'mode-flat'}`}
          style={{
            transform: `scale(${zoomLevel / 100})`,
          }}
        >
          <div
            className="dd-paper-sheet"
            ref={paperRef}
            style={
              is3DMode
                ? {
                    transform: `rotateX(${mouseTilt.rotateX}deg) rotateY(${mouseTilt.rotateY}deg)`,
                  }
                : undefined
            }
          >
            {/* Paper Header / Document Title */}
            <div className="dd-paper-header">
              <div className="dd-paper-title-row">
                <h1 className="dd-paper-title">
                  {documentData?.filename || 'No Document Selected'}
                </h1>
                <div className="dd-paper-badge">
                  Overall Risk: <strong>{riskSummary.overall_risk}</strong>
                </div>
              </div>
              <div className="dd-paper-meta-sub">
                <span>{clauses.length} extracted clauses</span>
                <span>•</span>
                <span>{documentData?.char_count?.toLocaleString() || 0} characters</span>
                {filterRisk && <span>• Filtered by {filterRisk} risk</span>}
              </div>
              {documentData?.warnings && documentData.warnings.length > 0 && (
                <div
                  className="dd-document-warning-banner"
                  style={{
                    marginTop: '12px',
                    marginBottom: '6px',
                    padding: '10px 14px',
                    backgroundColor: '#fffbeb',
                    border: '1px solid #fcd34d',
                    borderRadius: '6px',
                    color: '#92400e',
                    fontSize: '13px',
                    lineHeight: '1.4',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '10px',
                    textAlign: 'left',
                  }}
                >
                  <span style={{ fontSize: '16px', lineHeight: '1.2' }}>⚠️</span>
                  <div>
                    {documentData.warnings.map((w, idx) => (
                      <div key={idx}><strong>Notice:</strong> {w}</div>
                    ))}
                  </div>
                </div>
              )}
              <hr className="dd-paper-rule" />
            </div>

            {/* Document Body / Clauses with inline highlights */}
            <div className="dd-paper-body">
              {pageClauses.length === 0 ? (
                <div className="dd-paper-empty">
                  {clauses.length === 0 ? (
                    <p>No document loaded. Upload a contract to begin analysis.</p>
                  ) : (
                    <p>No clauses match the current filter.</p>
                  )}
                </div>
              ) : (
                pageClauses.map((clause) => {
                  const isActive = clause.id === activeClauseId;
                  const isHovered = clause.id === hoveredClauseId;
                  const riskClass = getRiskClass(clause.risk_level);
                  const searchMatch = searchResults.find(
                    (sr) => sr.clause_id === clause.id
                  );

                  return (
                    <div
                      key={clause.id}
                      ref={(el) => (clauseRefs.current[clause.id] = el)}
                      className={`dd-clause-block ${isActive ? 'active' : ''} ${riskClass ? 'has-risk' : ''}`}
                      onMouseEnter={() => setHoveredClauseId(clause.id)}
                      onMouseLeave={() => setHoveredClauseId(null)}
                      onClick={() => onSelectClause && onSelectClause(clause.id)}
                    >
                      {/* Clause Meta Strip */}
                      <div className="dd-clause-header">
                        <span className="dd-clause-num" style={{ whiteSpace: 'nowrap' }}>
                          § {clause.position + 1}
                        </span>
                        {clause.label !== 'No Clause' && (
                          <span className={`dd-clause-badge ${riskClass}`} style={{ whiteSpace: 'nowrap' }}>
                            {clause.label}
                          </span>
                        )}
                        {(clause.risk_level || clause.risk_tier) && (
                          <span className={`dd-risk-indicator ${riskClass}`} style={{ whiteSpace: 'nowrap' }}>
                            {(clause.risk_tier || clause.risk_level)} Risk • Model Conf: {Math.round((clause.calibrated_probability || clause.confidence || 0) * 100)}%
                          </span>
                        )}
                        {clause.type_uncertain && (
                          <span
                            className="dd-badge-type-uncertain"
                            title="The clause type may be wrong"
                            style={{
                              backgroundColor: '#fef3c7',
                              color: '#92400e',
                              border: '1px solid #fcd34d',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              fontWeight: '600',
                              whiteSpace: 'nowrap',
                              cursor: 'help',
                            }}
                          >
                            ⚠️ Type uncertain
                          </span>
                        )}
                        {searchMatch && (
                          <span className="dd-search-similarity" style={{ whiteSpace: 'nowrap' }}>
                            🎯 {(searchMatch.similarity * 100).toFixed(0)}% match
                          </span>
                        )}
                      </div>

                      {/* In-Text Clause Risk Highlights */}
                      <div
                        className={`dd-clause-text clause-highlight ${clause.risk_level ? `risk-${clause.risk_level.toLowerCase()}` : ''} ${isActive ? 'active' : ''}`}
                      >
                        {clause.text}
                      </div>

                      {/* Quick Action bar if active */}
                      {isActive && (
                        <div className="dd-clause-quick-actions">
                          <span>👉 Selected — review recommendations in the right panel</span>
                        </div>
                      )}
                    </div>
                  );
                })
              )}

              {/* Expander for Unflagged / Harmless Units */}
              {unflaggedClauses.length > 0 && (
                <div className="dd-unflagged-container" style={{ marginTop: '24px', borderTop: '1px dashed rgba(255, 255, 255, 0.15)', paddingTop: '16px' }}>
                  <button
                    type="button"
                    className="dd-unflagged-expander-btn"
                    onClick={() => setShowUnflagged(!showUnflagged)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 14px',
                      background: 'rgba(255, 255, 255, 0.05)',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      borderRadius: '6px',
                      color: '#cbd5e1',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      width: '100%',
                      justifyContent: 'center',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <span>{showUnflagged ? '▼ Hide Unflagged Units' : '▶ Show Unflagged Units'}</span>
                    <span style={{ background: 'rgba(255, 255, 255, 0.1)', padding: '2px 8px', borderRadius: '10px', fontSize: '11px', color: '#94a3b8' }}>
                      {unflaggedClauses.length} harmless / boilerplate units
                    </span>
                  </button>
                  {showUnflagged && (
                    <div className="dd-unflagged-list" style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {unflaggedClauses.map((clause) => (
                        <div
                          key={clause.id}
                          className="dd-clause-block dd-unflagged-block"
                          style={{ opacity: 0.7, padding: '10px 14px', background: 'rgba(255, 255, 255, 0.02)', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.05)' }}
                        >
                          <div className="dd-clause-header" style={{ marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span className="dd-clause-num">§ {clause.position + 1}</span>
                            <span style={{ fontSize: '11px', color: '#64748b', fontWeight: 500 }}>Unflagged (Harmless Unit)</span>
                          </div>
                          <div className="dd-clause-text" style={{ fontSize: '12px', color: '#94a3b8', lineHeight: 1.5 }}>
                            {clause.text}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Paper Footer with Page numbering */}
            <div className="dd-paper-footer">
              <span>ClauseWise AI • Document Risk Inspection</span>
              <span>
                Page {currentPage} of {totalPages}
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
