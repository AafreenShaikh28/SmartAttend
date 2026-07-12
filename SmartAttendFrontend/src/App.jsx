import { useState } from 'react';
import RegisterStudentTab from './RegisterStudentTab';

// Easily extensible tab configuration for future features (e.g. Mark Attendance, View Students)
const TABS = [
  {
    id: 'register',
    label: 'Register Student',
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <line x1="19" y1="8" x2="19" y2="14" />
        <line x1="22" y1="11" x2="16" y2="11" />
      </svg>
    ),
    component: RegisterStudentTab,
  },
];

function App() {
  const [activeTabId, setActiveTabId] = useState(TABS[0].id);

  const activeTab = TABS.find(tab => tab.id === activeTabId) || TABS[0];
  const ActiveTabComponent = activeTab.component;

  return (
    <div className="app-container">
      {/* App Header */}
      <header className="app-header">
        <div className="logo-container">
          <div className="logo-icon-wrapper">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="logo-svg">
              <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
              <path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5" />
            </svg>
          </div>
          <div className="logo-text-group">
            <h1>SmartAttend</h1>
            <span className="logo-tagline">FastAPI & React Testing Portal</span>
          </div>
        </div>
        <div className="backend-indicator">
          <span className="indicator-dot"></span>
          <span>API: http://127.0.0.1:8000</span>
        </div>
      </header>

      {/* Tab Switcher Navigation */}
      <nav className="tab-navigation">
        <div className="tabs-list">
          {TABS.map((tab) => {
            const isActive = tab.id === activeTabId;
            return (
              <button
                key={tab.id}
                type="button"
                className={`tab-btn ${isActive ? 'active' : ''}`}
                onClick={() => setActiveTabId(tab.id)}
              >
                {tab.icon}
                <span>{tab.label}</span>
                {isActive && <span className="active-indicator-bar" />}
              </button>
            );
          })}
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="main-content">
        <ActiveTabComponent />
      </main>

      {/* Simple, Clean Footer */}
      <footer className="app-footer">
        <p>&copy; {new Date().getFullYear()} SmartAttend Portal. Built for testing Face Recognition Attendance APIs.</p>
      </footer>
    </div>
  );
}

export default App;
