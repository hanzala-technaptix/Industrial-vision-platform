import React from 'react';
import { BrowserRouter as Router, Navigate, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';

const App = () => {
  return (
    <Router>
      <div className="app-container">
        <main className="main-content" style={{ marginLeft: 0 }}>
          <header className="navbar">
            <div style={{ fontWeight: 600 }}>Industrial Safety Vision</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--color-accent)' }}>Live showcase</div>
          </header>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/home" element={<Dashboard />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
};

export default App;
