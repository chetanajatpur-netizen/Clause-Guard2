import { useState } from 'react'
import explanations from '../data/clause_explanations.json'

export default function ClauseExplanation({
  clauseLabel,
  isExpanded: controlledExpanded,
  onToggle,
}) {
  const [internalExpanded, setInternalExpanded] = useState(false)
  const isExpanded = controlledExpanded !== undefined ? controlledExpanded : internalExpanded

  if (!clauseLabel || clauseLabel === 'No Clause') return null
  const data = explanations[clauseLabel]
  if (!data) return null

  const toggleExpand = (e) => {
    if (e) e.stopPropagation()
    if (onToggle) {
      onToggle()
    } else {
      setInternalExpanded((prev) => !prev)
    }
  }

  return (
    <div
      className={`clause-explanation-box ${isExpanded ? 'clause-explanation-box--expanded' : ''}`}
      onClick={(e) => {
        // Toggle on header/box click if not already interacting with other elements
        if (e.target.tagName !== 'A') {
          toggleExpand(e)
        }
      }}
    >
      {/* Header & Summary (Always Visible) */}
      <div className="clause-explanation-header">
        <div className="clause-explanation-summary-wrap">
          <span className="clause-explanation-icon" aria-hidden="true">💡</span>
          <div className="clause-explanation-summary-content">
            <span className="clause-explanation-badge">AI Risk Context &amp; Impact</span>
            <p className="clause-explanation-summary">{data.summary}</p>
          </div>
        </div>

        <button
          type="button"
          onClick={toggleExpand}
          className="clause-explanation-toggle-btn"
          aria-expanded={isExpanded}
          aria-label={isExpanded ? 'Collapse context explanation' : 'Expand full negotiation guidance and real examples'}
        >
          {isExpanded ? 'Hide Details ▲' : 'Why This Matters & Tips ▼'}
        </button>
      </div>

      {/* Expanded Sections */}
      {isExpanded && (
        <div className="clause-explanation-body" onClick={(e) => e.stopPropagation()}>
          {/* Why This Matters */}
          <section className="clause-explanation-section">
            <h4 className="clause-explanation-heading">Why This Matters</h4>
            <p className="clause-explanation-text">{data.why_it_matters}</p>
          </section>

          {/* Real Example */}
          {data.real_world_example && (
            <section className="clause-explanation-section clause-explanation-example-box">
              <h4 className="clause-explanation-heading">Real Example</h4>
              <p className="clause-explanation-example-text">
                <em>{data.real_world_example}</em>
              </p>
            </section>
          )}

          {/* Red Flags to Watch For */}
          {data.red_flags && data.red_flags.length > 0 && (
            <section className="clause-explanation-section">
              <h4 className="clause-explanation-heading">Red Flags to Watch For</h4>
              <ul className="clause-explanation-list red-flags-list">
                {data.red_flags.map((flag, idx) => (
                  <li key={idx} className="clause-explanation-list-item">
                    <span className="list-icon" aria-hidden="true">⚠️</span>
                    <span>{flag}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Negotiation Tips */}
          {data.negotiation_tips && data.negotiation_tips.length > 0 && (
            <section className="clause-explanation-section">
              <h4 className="clause-explanation-heading">Negotiation Tips</h4>
              <ul className="clause-explanation-list negotiation-tips-list">
                {data.negotiation_tips.map((tip, idx) => (
                  <li key={idx} className="clause-explanation-list-item">
                    <span className="list-icon icon-success" aria-hidden="true">✓</span>
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Legal Disclaimer */}
          <footer className="clause-explanation-disclaimer">
            <span aria-hidden="true">⚠️</span>
            <span>Educational guidance only. Not legal advice. Consult licensed legal counsel for binding contracts.</span>
          </footer>
        </div>
      )}
    </div>
  )
}
