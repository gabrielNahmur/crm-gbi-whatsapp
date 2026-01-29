import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Agents from './pages/Agents';
import './index.css';

function App() {
  const [agent, setAgent] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Verifica se há um agente logado
    const storedAgent = localStorage.getItem('agent');
    const token = localStorage.getItem('token');
    
    if (storedAgent && token) {
      try {
        setAgent(JSON.parse(storedAgent));
      } catch {
        localStorage.removeItem('agent');
        localStorage.removeItem('token');
      }
    }
    setLoading(false);
  }, []);

  const handleLogin = (agentData) => {
    setAgent(agentData);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('agent');
    setAgent(null);
  };

  if (loading) {
    return (
      <div className="login-page">
        <div className="loading">
          <div className="spinner"></div>
        </div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            agent ? (
              <Navigate to="/" replace />
            ) : (
              <Login onLogin={handleLogin} />
            )
          }
        />
        <Route
          path="/dashboard"
          element={
            agent ? (
              <Dashboard agent={agent} onLogout={handleLogout} />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
        <Route
          path="/agents"
          element={
            agent ? (
              <Agents />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
        <Route
          path="/"
          element={
            agent ? (
              <Navigate to="/dashboard" replace />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
