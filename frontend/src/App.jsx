import { useState } from 'react'
import Landing from './pages/Landing'
import SpatialCockpit from './components/SpatialCockpit'
import './styles/tokens.css'
import './styles/global.css'
import './styles/clause-explanation.css'

function App() {
  const [activeView, setActiveView] = useState('canvas')

  if (activeView === 'cockpit') {
    return <SpatialCockpit onSwitchToCanvas={() => setActiveView('canvas')} />
  }

  return <Landing onSwitchToCockpit={() => setActiveView('cockpit')} />
}

export default App
