import React from 'react';
import { Activity, Camera } from 'lucide-react';
import { BrowserRouter as Router, Navigate, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';

const App = () => {
  return (
    <Router>
      <div className="app-shell">
        <header className="nav">
          <div className="nav-brand">Industrial Safety Vision</div>
          <div className="nav-cell">
            <Camera size={14} strokeWidth={1.5} />
            Cam 01
          </div>
          <div className="nav-cell live">
            <Activity size={14} strokeWidth={1.5} />
            Live
          </div>
        </header>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/home" element={<Dashboard />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </Router>
  );
};

export default App;
