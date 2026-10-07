import React, { useState } from 'react';
import explanations from '../data/clause_explanations.json';

/**
 * ClauseExplanation - displays AI-generated context about why a clause is risky
 * Shows: summary, real-world example, red flags, negotiation tips
 * No external LLM API - all text is human-written and static
 */
export default function ClauseExplanation({ clauseLabel, isExpanded: controlledExpanded, onToggle }) {
  const [internalExpanded, setIsExpanded] = useState(false);

  const isExpanded = controlledExpanded !== undefined ? controlledExpanded : internalExpanded;

  const toggle = (e) => {
    if (e && e.stopPropagation) e.stopPropagation();
    if (onToggle) {
      onToggle();
    } else {
      setIsExpanded(!internalExpanded);
    }
  };

  const info = explanations.clauses[clauseLabel] || explanations.clauses['No Clause'];
  if (!info) return null;

  return (
    <div className="clause-explanation" onClick={(e) => e.stopPropagation()}>
      {/* Summary line (always visible) */}
      <div className="explanation-header">
        <button 
          className="explanation-toggle"
          onClick={toggle}
          aria-expanded={isExpanded}
          aria-label={`Toggle details for ${clauseLabel}`}
        >
          <span className="toggle-icon">{isExpanded ? '▼' : '▶'}</span>
          <span className="explanation-summary">{info.summary}</span>
        </button>
      </div>

      {/* Expanded section */}
      {isExpanded && (
        <div className="explanation-details">
          
          {/* Why it's risky */}
          <div className="explanation-section">
            <h4>Why This Matters</h4>
            <p className="explanation-text">{info.why_risky}</p>
          </div>

          {/* Real-world example */}
          {info.real_example && (
            <div className="explanation-section">
              <h4>Real Example</h4>
              <div className="explanation-example">
                <p>{info.real_example}</p>
              </div>
            </div>
          )}

          {/* Red flags to watch for */}
          {info.red_flags && info.red_flags.length > 0 && (
            <div className="explanation-section">
              <h4>🚩 Red Flags to Watch For</h4>
              <ul className="red-flags-list">
                {info.red_flags.map((flag, idx) => (
                  <li key={idx}>{flag}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Negotiation tips */}
          {info.what_to_negotiate && info.what_to_negotiate.length > 0 && (
            <div className="explanation-section">
              <h4>💡 How to Negotiate</h4>
              <ul className="negotiation-tips">
                {info.what_to_negotiate.map((tip, idx) => (
                  <li key={idx}>{tip}</li>
                ))}
              </ul>
            </div>
          )}

          <p className="explanation-disclaimer">
            ⚠️ This is educational information, not legal advice. Always consult a lawyer before signing.
          </p>
        </div>
      )}
    </div>
  );
}
