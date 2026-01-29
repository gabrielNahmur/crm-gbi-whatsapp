import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import './Agents.css';

const SECTORS = [
  { value: 'comercial', label: 'Comercial' },
  { value: 'compras', label: 'Compras' },
  { value: 'contas_pagar', label: 'Contas a Pagar' },
  { value: 'contas_receber', label: 'Contas a Receber' },
  { value: 'rh', label: 'RH' },
  { value: 'atendimento_humano', label: 'Atendimento Humano' },
  { value: 'geral', label: 'Geral' },
];

export default function Agents() {
  const navigate = useNavigate();
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    sector: 'comercial'
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    try {
      const response = await api.get('/api/agents');
      setAgents(response.data.agents || []);
    } catch (err) {
      console.error('Erro ao carregar atendentes:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      await api.post('/api/agents', formData);
      setSuccess('Atendente criado com sucesso!');
      setShowForm(false);
      setFormData({ name: '', email: '', password: '', sector: 'comercial' });
      loadAgents();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao criar atendente');
    }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Deseja realmente desativar ${name}?`)) return;

    try {
      await api.delete(`/api/agents/${id}`);
      setSuccess('Atendente desativado!');
      loadAgents();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao desativar');
    }
  };

  const handleToggleAdmin = async (id, name, currentIsAdmin) => {
    const action = currentIsAdmin ? 'remover permissão de admin de' : 'promover a admin';
    if (!window.confirm(`Deseja ${action} ${name}?`)) return;

    try {
      const response = await api.put(`/api/agents/${id}/admin`);
      setSuccess(response.data.message);
      loadAgents();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao alterar permissão');
    }
  };

  const getSectorLabel = (sector) => {
    const found = SECTORS.find(s => s.value === sector);
    return found ? found.label : sector;
  };

  if (loading) {
    return <div className="agents-container"><div className="loading">Carregando...</div></div>;
  }

  return (
    <div className="agents-container">
      <header className="agents-header">
        <div className="header-left">
          <button className="back-btn" onClick={() => navigate('/dashboard')}>
            ← Voltar
          </button>
          <h1>👥 Gerenciar Atendentes</h1>
        </div>
        <button className="add-btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? '✕ Cancelar' : '+ Novo Atendente'}
        </button>
      </header>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {showForm && (
        <form className="agent-form" onSubmit={handleSubmit}>
          <h2>Cadastrar Novo Atendente</h2>
          <div className="form-grid">
            <div className="form-group">
              <label>Nome</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Nome completo"
                required
              />
            </div>
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="email@empresa.com"
                required
              />
            </div>
            <div className="form-group">
              <label>Senha</label>
              <input
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                placeholder="Senha de acesso"
                required
                minLength={6}
              />
            </div>
            <div className="form-group">
              <label>Setor</label>
              <select
                value={formData.sector}
                onChange={(e) => setFormData({ ...formData, sector: e.target.value })}
              >
                {SECTORS.map(s => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
          </div>
          <button type="submit" className="submit-btn">Cadastrar Atendente</button>
        </form>
      )}

      <div className="agents-list">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Nome</th>
              <th>Email</th>
              <th>Setor</th>
              <th>Admin</th>
              <th>Status</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {agents.length === 0 ? (
              <tr>
                <td colSpan="7" className="empty">Nenhum atendente cadastrado</td>
              </tr>
            ) : (
              agents.map(agent => (
                <tr key={agent.id}>
                  <td>{agent.id}</td>
                  <td>{agent.name}</td>
                  <td>{agent.email}</td>
                  <td>
                    <span className={`sector-badge ${agent.sector}`}>
                      {getSectorLabel(agent.sector)}
                    </span>
                  </td>
                  <td>
                    {agent.is_admin ? (
                      <span className="admin-badge">👑 Admin</span>
                    ) : (
                      <span className="user-badge">👤 Usuário</span>
                    )}
                  </td>
                  <td>
                    <span className={`status-badge ${agent.is_online ? 'online' : 'offline'}`}>
                      {agent.is_online ? '🟢 Online' : '⚪ Offline'}
                    </span>
                  </td>
                  <td className="actions-cell">
                    <button
                      className={agent.is_admin ? 'demote-btn' : 'promote-btn'}
                      onClick={() => handleToggleAdmin(agent.id, agent.name, agent.is_admin)}
                    >
                      {agent.is_admin ? 'Remover Admin' : 'Promover'}
                    </button>
                    <button
                      className="delete-btn"
                      onClick={() => handleDelete(agent.id, agent.name)}
                    >
                      Desativar
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
