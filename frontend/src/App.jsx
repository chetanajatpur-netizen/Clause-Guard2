import { Routes, Route, NavLink } from 'react-router-dom'
import Analyze from './pages/Analyze'
import History from './pages/History'
import Insights from './pages/Insights'
import './styles/global.css'

function App() {
  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="sidebar-brand">
          <h1 className="brand-title">ClauseGuard</h1>
          <p className="brand-subtitle">Contract Risk Analyzer</p>
        </div>
        <ul className="nav-links">
          <li>
            <NavLink to="/" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              📄 Analyze
            </NavLink>
          </li>
          <li>
            <NavLink to="/history" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              📋 History
            </NavLink>
          </li>
          <li>
            <NavLink to="/insights" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              📊 Insights
            </NavLink>
          </li>
        </ul>
      </nav>
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Analyze />} />
          <Route path="/history" element={<History />} />
          <Route path="/history/:id" element={<Analyze />} />
          <Route path="/insights" element={<Insights />} />
        </Routes>
        <footer className="disclaimer">
          ⚠️ ClauseGuard is an educational tool and not legal advice.
        </footer>
      </main>
    </div>
  )
}

export default App
