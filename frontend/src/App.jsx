import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';

// Mock Pages for now
const Placeholder = ({ name }) => (
  <div style={{ padding: '2rem' }}>
    <h1>{name} Page</h1>
    <p style={{ color: 'var(--text-muted)' }}>Work in progress...</p>
  </div>
);

const App = () => {
  return (
    <Router>
      <div className="app-container">
        {/* SHARED SIDEBAR */}
        <aside className="sidebar">
          <div style={{ padding: '0 1rem 2rem 1rem', fontSize: '1.2rem', fontWeight: 'bold', color: 'var(--color-accent)' }}>
            VISION OS
          </div>
          <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <Link to="/" className="nav-link">Dashboard</Link>
            <Link to="/analytics" className="nav-link">Analytics</Link>
            <Link to="/logs" className="nav-link">Events & Logs</Link>
            <Link to="/settings" className="nav-link">Settings</Link>
          </nav>
        </aside>

        {/* MAIN AREA */}
        <main className="main-content">
          <header className="navbar">
            <div style={{ fontWeight: '600' }}>System Console v1.0</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--color-accent)' }}>● ONLINE</span>
            </div>
          </header>

          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/analytics" element={<Placeholder name="Analytics" />} />
            <Route path="/logs" element={<Placeholder name="Logs" />} />
            <Route path="/settings" element={<Placeholder name="Settings" />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
};

export default App;
