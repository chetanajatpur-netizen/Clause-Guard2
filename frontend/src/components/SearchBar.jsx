import { useState } from 'react'

function SearchBar({ onSearch, loading }) {
  const [query, setQuery] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (query.trim()) {
      onSearch(query.trim())
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search contract in plain English..."
        disabled={loading}
        style={{
          flex: 1,
          padding: '12px 16px',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-sm)',
          fontSize: '15px',
          fontFamily: 'var(--font-body)',
          outline: 'none',
          transition: 'border-color 0.15s ease',
        }}
        onFocus={(e) => e.target.style.borderColor = 'var(--primary)'}
        onBlur={(e) => e.target.style.borderColor = 'var(--border)'}
      />
      <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>
        🔍 Search
      </button>
    </form>
  )
}

export default SearchBar
