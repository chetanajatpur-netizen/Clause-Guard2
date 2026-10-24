import React, { useState, useEffect } from 'react';
import FrontPage from './components/FrontPage';
import DocumentDashboard from './components/DocumentDashboard';
import './styles/tokens.css';
import './styles/global.css';

export default function App() {
  const [view, setView] = useState(() => {
    if (typeof window !== 'undefined') {
      if (window.location.hash === '#cockpit' || window.location.search.includes('view=cockpit')) {
        return 'cockpit';
      }
    }
    return 'home';
  });

  const handleLaunchCockpit = () => {
    setView('cockpit');
    window.location.hash = 'cockpit';
  };

  const handleBackToHome = () => {
    setView('home');
    window.location.hash = '';
  };

  // Listen to hash changes for browser back/forward buttons
  useEffect(() => {
    const handleHashChange = () => {
      if (window.location.hash === '#cockpit') {
        setView('cockpit');
      } else {
        setView('home');
      }
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  if (view === 'cockpit') {
    return <DocumentDashboard onBackToHome={handleBackToHome} />;
  }

  return <FrontPage onLaunchCockpit={handleLaunchCockpit} />;
}
