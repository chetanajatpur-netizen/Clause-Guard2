import { useState } from 'react'
import Landing from './pages/Landing'
import SpatialCockpit from './components/SpatialCockpit'
import './styles/tokens.css'
import './styles/global.css'
import './styles/clause-explanation.css'

function App() {
  const [activeView, setActiveView] = useState(() => {
    try {
      return localStorage.getItem('clauseguard_view') || 'cockpit'
    } catch {
      return 'cockpit'
    }
  })

  const handleSwitchToCanvas = () => {
    setActiveView('canvas')
    try {
      localStorage.setItem('clauseguard_view', 'canvas')
    } catch {}
  }

  const handleSwitchToCockpit = () => {
    setActiveView('cockpit')
    try {
      localStorage.setItem('clauseguard_view', 'cockpit')
    } catch {}
  }

  if (activeView === 'canvas') {
    return <Landing onSwitchToCockpit={handleSwitchToCockpit} />
  }

  return <SpatialCockpit onSwitchToCanvas={handleSwitchToCanvas} />
}

export default App
