import React, { useState, useEffect, useRef } from 'react';
import explanationsData from '../data/clause_explanations.json';
import { getClauseRedline } from '../api/client';

/**
 * RiskPanel component matching Screenshot 1 (Right Sidebar):
 * - "Risks" header with count badge
 * - Filter tabs (All, High, Moderate, Low)
 * - Findings accordion with colored left accent bars
 * - "> Recommendation" toggle button
 * - Plain English breakdown, Red Flags, Negotiation strategies
 * - AI Redline diff viewer & replacement suggestion with copy
 * - Speech synthesis read-aloud and "Mark as reviewed" tracker
 */
export default function RiskPanel({
  clauses = [],
  activeClauseId,
  onSelectClause,
  isCollapsed = false,
  onToggleCollapse,
}) {
  const [activeFilter, setActiveFilter] = useState('ALL');
  const [expandedId, setExpandedId] = useState(null);
  const [reviewedIds, setReviewedIds] = useState(new Set());
  const [redlineCache, setRedlineCache] = useState({});
  const [loadingRedline, setLoadingRedline] = useState({});
  const [speakingClauseId, setSpeakingClauseId] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  const cardRefs = useRef({});

  // Only show clauses that have risk (or classified label != 'No Clause')
  const riskyClauses = clauses.filter(
    (c) => c.label !== 'No Clause' && c.risk_level
  );

  const filteredRisks = riskyClauses.filter((c) => {
    if (activeFilter === 'HIGH') return c.risk_level === 'High';
    if (activeFilter === 'MODERATE') return c.risk_level === 'Medium';
    if (activeFilter === 'LOW') return c.risk_level === 'Low';
    return true;
  });

  // When activeClauseId changes externally, expand that card and scroll to it
  useEffect(() => {
    if (activeClauseId) {
      setExpandedId(activeClauseId);
      setTimeout(() => {
        const el = cardRefs.current[activeClauseId];
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }, 100);
    }
  }, [activeClauseId]);

  // Toggle card expansion
  const toggleExpand = (clauseId) => {
    const next = expandedId === clauseId ? null : clauseId;
    setExpandedId(next);
    if (next && onSelectClause) {
      onSelectClause(next);
    }
  };

  // Toggle reviewed status
  const toggleReviewed = (clauseId, e) => {
    e.stopPropagation();
    setReviewedIds((prev) => {
      const next = new Set(prev);
      if (next.has(clauseId)) {
        next.delete(clauseId);
      } else {
        next.add(clauseId);
      }
      return next;
    });
  };

  // Fetch or retrieve AI Redline for clause
  const handleLoadRedline = async (clause, e) => {
    if (e) e.stopPropagation();
    if (redlineCache[clause.id] || loadingRedline[clause.id]) return;

    setLoadingRedline((prev) => ({ ...prev, [clause.id]: true }));
    try {
      const res = await getClauseRedline(clause.text, clause.label);
      setRedlineCache((prev) => ({ ...prev, [clause.id]: res }));
    } catch (err) {
      console.error('Failed to fetch redline:', err);
    } finally {
      setLoadingRedline((prev) => ({ ...prev, [clause.id]: false }));
    }
  };

  // Web Speech API Read Aloud
  const handleReadAloud = (clause, e) => {
    e.stopPropagation();
    if (!('speechSynthesis' in window)) {
      alert('Speech synthesis is not supported in this browser.');
      return;
    }

    if (speakingClauseId === clause.id) {
      window.speechSynthesis.cancel();
      setSpeakingClauseId(null);
      return;
    }

    window.speechSynthesis.cancel();
    const explanation = explanationsData.clauses[clause.label];
    const textToRead = `${clause.label} clause. Risk level ${clause.risk_level}. ${
      explanation ? explanation.summary : ''
    } Clause text: ${clause.text}`;

    const utterance = new SpeechSynthesisUtterance(textToRead);
    utterance.rate = 1.0;
    utterance.onend = () => setSpeakingClauseId(null);
    utterance.onerror = () => setSpeakingClauseId(null);

    setSpeakingClauseId(clause.id);
    window.speechSynthesis.speak(utterance);
  };

  // Copy replacement text
  const handleCopyReplacement = (text, clauseId, e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopiedId(clauseId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getRiskClass = (level) => {
    if (level === 'High') return 'risk-high';
    if (level === 'Medium') return 'risk-medium';
    if (level === 'Low') return 'risk-low';
    return '';
  };

  return (
    <aside className={`dd-right-panel ${isCollapsed ? 'collapsed' : ''}`}>
      {/* Panel Header */}
      <div className="dd-right-header">
        <div className="dd-right-title-group">
          <h2 className="dd-right-title">Risks</h2>
          <span className="dd-risk-badge-total">{riskyClauses.length}</span>
        </div>
        <div className="dd-reviewed-count">
          {reviewedIds.size} / {riskyClauses.length} Reviewed
        </div>
      </div>

      {/* Filter Tabs (All, High, Moderate, Low) */}
      <div className="dd-risk-tabs">
        <button
          className={`dd-risk-tab ${activeFilter === 'ALL' ? 'active' : ''}`}
          onClick={() => setActiveFilter('ALL')}
        >
          All ({riskyClauses.length})
        </button>
        <button
          className={`dd-risk-tab ${activeFilter === 'HIGH' ? 'active' : ''}`}
          onClick={() => setActiveFilter('HIGH')}
        >
          High ({riskyClauses.filter((c) => c.risk_level === 'High').length})
        </button>
        <button
          className={`dd-risk-tab ${activeFilter === 'MODERATE' ? 'active' : ''}`}
          onClick={() => setActiveFilter('MODERATE')}
        >
          Mod ({riskyClauses.filter((c) => c.risk_level === 'Medium').length})
        </button>
        <button
          className={`dd-risk-tab ${activeFilter === 'LOW' ? 'active' : ''}`}
          onClick={() => setActiveFilter('LOW')}
        >
          Low ({riskyClauses.filter((c) => c.risk_level === 'Low').length})
        </button>
      </div>

      {/* Findings Accordion List */}
      <div className="dd-findings-list">
        {filteredRisks.length === 0 ? (
          <div className="dd-findings-empty">
            <p>No risks detected matching filter.</p>
          </div>
        ) : (
          filteredRisks.map((clause) => {
            const isExpanded = expandedId === clause.id;
            const isReviewed = reviewedIds.has(clause.id);
            const riskClass = getRiskClass(clause.risk_level);
            const explanation = explanationsData.clauses[clause.label];
            const redlineData = redlineCache[clause.id];
            const isLoadingRedline = loadingRedline[clause.id];

            return (
              <div
                key={clause.id}
                ref={(el) => (cardRefs.current[clause.id] = el)}
                className={`dd-finding-card risk-card ${clause.risk_level?.toLowerCase()} ${riskClass} ${isExpanded ? 'expanded' : ''} ${isReviewed ? 'reviewed' : ''}`}
                onClick={() => {
                  if (onSelectClause) onSelectClause(clause.id);
                }}
              >
                {/* Header row with Title and Badges */}
                <div className="dd-finding-top">
                  <div className="dd-finding-title-row">
                    <span className="dd-finding-num">§ {clause.position + 1}</span>
                    <h4 className="dd-finding-title">{clause.label}</h4>
                  </div>
                  <span className={`risk-score-badge ${clause.risk_level?.toLowerCase()} ${riskClass}`}>
                    {clause.risk_score ? `${clause.risk_score}/100` : clause.risk_level}
                  </span>
                </div>

                {/* Excerpt */}
                <p className="dd-finding-excerpt">
                  "{clause.text.slice(0, 140)}
                  {clause.text.length > 140 ? '…' : ''}"
                </p>

                {/* Recommendation Pill button (from Screenshot 1) */}
                <div className="dd-rec-pill-row">
                  <button
                    className={`dd-rec-pill ${isExpanded ? 'active' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleExpand(clause.id);
                      if (!redlineCache[clause.id]) {
                        handleLoadRedline(clause);
                      }
                    }}
                  >
                    <span>{isExpanded ? '▾' : '▸'}</span>
                    <span>Recommendation & Redline</span>
                  </button>

                  <label
                    className="dd-review-checkbox-label"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      type="checkbox"
                      checked={isReviewed}
                      onChange={(e) => toggleReviewed(clause.id, e)}
                    />
                    <span>{isReviewed ? 'Reviewed' : 'Mark reviewed'}</span>
                  </label>
                </div>

                {/* Expanded Details / Recommendation Drawer */}
                {isExpanded && (
                  <div className="dd-finding-drawer">
                    {/* Summary & Why Risky */}
                    {explanation ? (
                      <div className="dd-legal-context">
                        <div className="dd-legal-section">
                          <h5>PLAIN ENGLISH MEANING</h5>
                          <p>{explanation.summary}</p>
                        </div>

                        <div className="dd-legal-section">
                          <h5>WHY IT MATTERS</h5>
                          <p>{explanation.why_risky}</p>
                        </div>

                        {explanation.red_flags && explanation.red_flags.length > 0 && (
                          <div className="dd-legal-section">
                            <h5>RED FLAGS TO CHECK</h5>
                            <ul className="dd-red-flags-list">
                              {explanation.red_flags.map((flag, idx) => (
                                <li key={idx}>{flag}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {explanation.what_to_negotiate && explanation.what_to_negotiate.length > 0 && (
                          <div className="dd-legal-section">
                            <h5>WHAT TO NEGOTIATE</h5>
                            <ul className="dd-negotiate-list">
                              {explanation.what_to_negotiate.map((item, idx) => (
                                <li key={idx}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="dd-legal-context">
                        <p className="dd-text-muted">
                          Legal context guidelines: Review clause scope, liability limits, and termination provisions.
                        </p>
                      </div>
                    )}

                    {/* AI Redline Section */}
                    <div className="dd-redline-container">
                      <div className="dd-redline-header">
                        <h5>AI BALANCED REDLINE</h5>
                        {!redlineData && !isLoadingRedline && (
                          <button
                            className="dd-btn-subtle"
                            onClick={(e) => handleLoadRedline(clause, e)}
                          >
                            Load AI Redline
                          </button>
                        )}
                      </div>

                      {isLoadingRedline && (
                        <div className="dd-redline-loading">
                          <span className="dd-spinner-small" />
                          <span>Generating balanced replacement…</span>
                        </div>
                      )}

                      {redlineData && (
                        <div className="dd-redline-body">
                          {/* Replacement text */}
                          <div className="dd-replacement-box">
                            <div className="dd-replacement-header">
                              <span>Suggested Replacement</span>
                              <button
                                className="dd-copy-btn"
                                onClick={(e) =>
                                  handleCopyReplacement(
                                    redlineData.replacement,
                                    clause.id,
                                    e
                                  )
                                }
                              >
                                {copiedId === clause.id ? '✓ Copied' : 'Copy'}
                              </button>
                            </div>
                            <p className="dd-replacement-text">
                              {redlineData.replacement}
                            </p>
                          </div>

                          {/* Rationale */}
                          {redlineData.rationale && (
                            <div className="dd-rationale-box">
                              <strong>Why this change:</strong> {redlineData.rationale}
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Actions Toolbar (Read Aloud, Jump to Clause) */}
                    <div className="dd-drawer-actions">
                      <button
                        className="dd-action-btn"
                        onClick={(e) => handleReadAloud(clause, e)}
                        title="Read clause aloud using text-to-speech"
                      >
                        {speakingClauseId === clause.id ? '⏹ Stop' : '🔊 Read Aloud'}
                      </button>
                      <button
                        className="dd-action-btn secondary"
                        onClick={() => onSelectClause && onSelectClause(clause.id)}
                      >
                        View in Paper Sheet
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
