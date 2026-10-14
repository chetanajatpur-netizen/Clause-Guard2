import { useState } from 'react'

function SearchBar({ onSearch, loading }) {
  const [query, setQuery] = useState('')
  const [isFocused, setIsFocused] = useState(false)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (query.trim()) {
      onSearch(query.trim())
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
      <div
        style={{
          position: 'relative',
          flex: 1,
          display: 'flex',
          alignItems: 'center',
        }}
      >
        <span
          style={{
            position: 'absolute',
            left: '12px',
            color: '#64748b',
            fontSize: '14px',
            pointerEvents: 'none',
          }}
          aria-hidden="true"
        >
          🔍
        </span>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder="Search clauses in plain English (e.g. indemnity cap, non-solicitation)..."
          disabled={loading}
          style={{
            width: '100%',
            padding: '8px 48px 8px 36px',
            backgroundColor: '#ffffff',
            border: isFocused ? '1px solid #4f46e5' : '1px solid #e2e8f0',
            boxShadow: isFocused ? '0 0 0 1px #4f46e5' : 'none',
            borderRadius: '6px',
            fontSize: '13px',
            lineHeight: '20px',
            fontFamily: 'var(--font-family)',
            color: '#0b1c30',
            outline: 'none',
            transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
            minHeight: '44px',
          }}
          aria-label="Search contract clauses"
        />
        <div
          style={{
            position: 'absolute',
            right: '12px',
            pointerEvents: 'none',
          }}
        >
          <span className="kbd-badge" title="Shortcut">⌘K</span>
        </div>
      </div>

      <button
        type="submit"
        className="btn btn-primary"
        disabled={loading || !query.trim()}
        style={{
          padding: '8px 18px',
          fontSize: '13px',
          fontWeight: 600,
          borderRadius: '6px',
          minHeight: '44px',
        }}
      >
        Search
      </button>
    </form>
  )
}

export default SearchBar
