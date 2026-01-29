import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { conversationsService, messagesService } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';

function Dashboard({ agent, onLogout }) {
  const navigate = useNavigate();
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [activeTab, setActiveTab] = useState('all'); // 'all', 'queue', 'mine'
  const [queueSizes, setQueueSizes] = useState({});
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);
  const selectedConversationRef = useRef(null);

  // Mantém ref atualizada da conversa selecionada para uso no callback
  useEffect(() => {
    selectedConversationRef.current = selectedConversation;
  }, [selectedConversation]);

  // Handler para mensagens recebidas via WebSocket
  const handleWebSocketMessage = useCallback((data) => {
    console.log('[Dashboard] WebSocket message received:', data);
    
    if (data.type === 'new_message') {
      const currentConvId = selectedConversationRef.current?.id;
      const messageConvId = data.conversation_id;
      
      console.log('[Dashboard] Comparing IDs:', { currentConvId, messageConvId, match: String(currentConvId) === String(messageConvId) });
      
      // Se for da conversa atualmente aberta, adiciona à lista de mensagens
      // Usa String() para garantir comparação correta
      if (currentConvId && String(currentConvId) === String(messageConvId)) {
        console.log('[Dashboard] Adding message to current conversation');
        setMessages(prev => {
          // Evita duplicatas
          const exists = prev.some(m => m.id === data.message.id);
          if (exists) {
            console.log('[Dashboard] Message already exists, skipping');
            return prev;
          }
          console.log('[Dashboard] New message added:', data.message);
          return [...prev, data.message];
        });
      } else {
        console.log('[Dashboard] Message is for different conversation');
      }
      // Também atualiza a lista de conversas
      loadConversations();
    } else if (data.type === 'new_conversation') {
      loadConversations();
    } else if (data.type === 'queue_update') {
      setQueueSizes(data.queue_sizes || {});
    }
  }, []);

  // Conexão WebSocket
  const { isConnected: wsConnected } = useWebSocket(
    agent?.id,
    agent?.sector || 'comercial',
    handleWebSocketMessage
  );

  // Carrega conversas
  useEffect(() => {
    loadConversations();
    const interval = setInterval(loadConversations, 10000); // Atualiza a cada 10s
    return () => clearInterval(interval);
  }, [activeTab]);

  // Carrega mensagens quando seleciona conversa
  useEffect(() => {
    if (selectedConversation) {
      loadMessages(selectedConversation.id);
    }
  }, [selectedConversation]);

  // Polling de mensagens a cada 3 segundos quando uma conversa está aberta
  useEffect(() => {
    if (!selectedConversation) return;
    
    const interval = setInterval(() => {
      loadMessages(selectedConversation.id);
    }, 3000);
    
    return () => clearInterval(interval);
  }, [selectedConversation]);

  // Scroll para última mensagem
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadConversations = async () => {
    setError(null);
    try {
      let data;
      if (activeTab === 'queue') {
        data = await conversationsService.getQueue();
        setQueueSizes(data.queue_sizes || {});
        setConversations(data.queue || []);
      } else {
        const params = activeTab === 'mine' ? { status: 'in_progress' } : {};
        data = await conversationsService.list(params);
        setConversations(data.conversations || []);
      }
    } catch (err) {
      console.error('Erro ao carregar conversas:', err);
      const msg = err.response?.data?.detail || err.message || 'Erro deconhecido';
      setError(`Erro: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async (conversationId) => {
    try {
      const data = await messagesService.getByConversation(conversationId);
      setMessages(data.messages || []);
    } catch (error) {
      console.error('Erro ao carregar mensagens:', error);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !selectedConversation || sending) return;

    setSending(true);
    try {
      await messagesService.send(selectedConversation.id, newMessage);
      setNewMessage('');
      await loadMessages(selectedConversation.id);
    } catch (error) {
      console.error('Erro ao enviar mensagem:', error);
      alert('Erro ao enviar mensagem');
    } finally {
      setSending(false);
    }
  };

  const handleAcceptConversation = async (conversation) => {
    try {
      await conversationsService.accept(conversation.id);
      setSelectedConversation({ ...conversation, status: 'in_progress' });
      await loadConversations();
    } catch (error) {
      console.error('Erro ao aceitar conversa:', error);
      alert(error.response?.data?.detail || 'Erro ao aceitar conversa');
    }
  };

  const handleResolveConversation = async () => {
    if (!selectedConversation) return;
    
    if (!confirm('Tem certeza que deseja marcar como resolvido?')) return;
    
    try {
      await conversationsService.resolve(selectedConversation.id);
      setSelectedConversation(null);
      await loadConversations();
    } catch (error) {
      console.error('Erro ao resolver conversa:', error);
    }
  };

  const formatTime = (date) => {
    if (!date) return '';
    try {
      return format(new Date(date), 'HH:mm', { locale: ptBR });
    } catch {
      return '';
    }
  };

  const formatDate = (date) => {
    if (!date) return '';
    try {
      return format(new Date(date), "dd 'de' MMM, HH:mm", { locale: ptBR });
    } catch {
      return '';
    }
  };

  const getInitials = (name) => {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
  };

  const getStatusLabel = (status) => {
    const labels = {
      bot_handling: 'Bot',
      waiting_queue: 'Fila',
      in_progress: 'Em Atendimento',
      resolved: 'Resolvido',
      closed: 'Fechado',
    };
    return labels[status] || status;
  };

  const getSectorLabel = (sector) => {
    const labels = {
      'contas_pagar': 'Contas a Pagar',
      'contas_receber': 'Contas a Receber',
      'comercial': 'Comercial',
      'compras': 'Compras',
      'rh': 'RH',
      'atendimento_humano': 'Atendimento Humano',
      'geral': 'Dúvida Geral',
      'outros': 'Outros'
    };
    return labels[sector] || sector;
  };

  const totalQueue = Object.values(queueSizes).reduce((a, b) => a + b, 0);

  return (
    <div className="app">
      {/* SIDEBAR */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="sidebar-logo-icon">💬</div>
            <span>GBI CRM</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section">
            <div className="nav-section-title">Atendimento</div>
            
            <div
              className={`nav-item ${activeTab === 'all' ? 'active' : ''}`}
              onClick={() => setActiveTab('all')}
            >
              <span className="nav-item-icon">📋</span>
              <span>Todas</span>
            </div>
            
            <div
              className={`nav-item ${activeTab === 'queue' ? 'active' : ''}`}
              onClick={() => setActiveTab('queue')}
            >
              <span className="nav-item-icon">⏳</span>
              <span>Fila de Espera</span>
              {totalQueue > 0 && (
                <span className="nav-item-badge">{totalQueue}</span>
              )}
            </div>
            
            <div
              className={`nav-item ${activeTab === 'mine' ? 'active' : ''}`}
              onClick={() => setActiveTab('mine')}
            >
              <span className="nav-item-icon">👤</span>
              <span>Meus Atendimentos</span>
            </div>
          </div>

          {agent?.is_admin && (
            <div className="nav-section">
              <div className="nav-section-title">Administração</div>
              <div
                className="nav-item"
                onClick={() => navigate('/agents')}
              >
                <span className="nav-item-icon">👥</span>
                <span>Gerenciar Atendentes</span>
              </div>
            </div>
          )}

          {activeTab === 'queue' && (
            <div className="nav-section">
              <div className="nav-section-title">Filas por Setor</div>
              {Object.entries(queueSizes).map(([sector, count]) => (
                <div key={sector} className="nav-item" style={{ cursor: 'default' }}>
                  <span className={`queue-badge ${sector}`}>{getSectorLabel(sector)}</span>
                  <span style={{ marginLeft: 'auto' }}>{count}</span>
                </div>
              ))}
            </div>
          )}
        </nav>

        <div className="user-info">
          <div className="user-avatar">{getInitials(agent?.name)}</div>
          <div className="user-details">
            <div className="user-name">{agent?.name}</div>
            <div className="user-sector">{getSectorLabel(agent?.sector)}</div>
          </div>
          <div className="user-status" title="Online"></div>
          <button
            className="btn btn-secondary btn-icon"
            onClick={onLogout}
            title="Sair"
            style={{ marginLeft: 'auto' }}
          >
            🚪
          </button>
        </div>
      </aside>

      {/* MAIN CONTENT */}
      <main className="main-content">
        <div className="content-area">
          {/* CONVERSATIONS LIST */}
          <div className="conversations-panel">
            <div className="conversations-header">
              <h2 className="conversations-title">
                {activeTab === 'queue' ? 'Fila de Espera' : 
                 activeTab === 'mine' ? 'Meus Atendimentos' : 'Conversas'}
              </h2>
              <div className="conversations-search">
                <span className="conversations-search-icon">🔍</span>
                <input type="text" placeholder="Buscar conversa..." />
              </div>
            </div>



            {error && (
              <div style={{ padding: '10px', backgroundColor: '#fee2e2', color: '#dc2626', marginBottom: '10px', borderRadius: '4px', fontSize: '14px', textAlign: 'center' }}>
                🚫 {error}
              </div>
            )}

            <div className="conversations-list">
              {loading ? (
                <div className="loading">
                  <div className="spinner"></div>
                </div>
              ) : conversations.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-icon">📭</div>
                  <div className="empty-state-title">Nenhuma conversa</div>
                  <div className="empty-state-text">
                    {activeTab === 'queue' 
                      ? 'Nenhum cliente na fila de espera'
                      : 'Nenhuma conversa encontrada'}
                  </div>
                </div>
              ) : (
                conversations.map((conv) => (
                  <div
                    key={conv.id}
                    className={`conversation-item ${selectedConversation?.id === conv.id ? 'active' : ''}`}
                    onClick={() => setSelectedConversation(conv)}
                  >
                    <div className="conversation-header">
                      <div className="contact-avatar">
                        {getInitials(conv.lead?.name || conv.lead?.phone)}
                      </div>
                      <div className="contact-info">
                        <div className="contact-name">
                          {conv.lead?.name || conv.lead?.phone || 'Desconhecido'}
                        </div>
                        <div className="contact-phone">{conv.lead?.phone}</div>
                      </div>
                      <div className="conversation-time">
                        {formatTime(conv.started_at)}
                      </div>
                    </div>
                    
                    <div className="conversation-meta">
                      <span className={`status-badge ${conv.status}`}>
                        {getStatusLabel(conv.status)}
                      </span>
                      {conv.sector && (
                        <span className={`queue-badge ${conv.sector}`}>
                          {getSectorLabel(conv.sector)}
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* CHAT PANEL */}
          <div className="chat-panel">
            {selectedConversation ? (
              <>
                <div className="chat-header">
                  <div className="chat-contact-info">
                    <div className="contact-avatar" style={{ width: 48, height: 48, fontSize: '1rem' }}>
                      {getInitials(selectedConversation.lead?.name || selectedConversation.lead?.phone)}
                    </div>
                    <div className="chat-contact-details">
                      <h3>{selectedConversation.lead?.name || 'Desconhecido'}</h3>
                      <span>{selectedConversation.lead?.phone}</span>
                    </div>
                  </div>
                  
                  <div className="chat-actions">
                    {selectedConversation.status === 'waiting_queue' && (
                      <button
                        className="btn btn-success"
                        onClick={() => handleAcceptConversation(selectedConversation)}
                      >
                        ✓ Aceitar da Fila
                      </button>
                    )}
                    {selectedConversation.status === 'bot_handling' && (
                      <button
                        className="btn btn-warning"
                        onClick={() => handleAcceptConversation(selectedConversation)}
                      >
                        🤖 Assumir do Bot
                      </button>
                    )}
                    {selectedConversation.status === 'in_progress' && (
                      <button
                        className="btn btn-primary"
                        onClick={handleResolveConversation}
                      >
                        ✓ Resolver
                      </button>
                    )}
                  </div>
                </div>

                <div className="chat-messages">
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`message fade-in ${
                        msg.sender_type === 'customer' ? 'received' :
                        msg.sender_type === 'bot' ? 'bot' : 'sent'
                      }`}
                    >
                      {msg.sender_type !== 'customer' && (
                        <div className="message-sender">
                          {msg.sender_type === 'bot' ? '🤖 Bot' : '👤 ' + agent?.name}
                        </div>
                      )}
                      {msg.content}
                      <div className="message-time">{formatTime(msg.created_at)}</div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>

                {(selectedConversation.status === 'in_progress' || 
                  selectedConversation.status === 'bot_handling') && (
                  <form className="chat-input-area" onSubmit={handleSendMessage}>
                    <div className="chat-input-container">
                      <textarea
                        className="chat-input"
                        placeholder="Digite sua mensagem..."
                        value={newMessage}
                        onChange={(e) => setNewMessage(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            handleSendMessage(e);
                          }
                        }}
                        rows={1}
                      />
                      <button
                        type="submit"
                        className="btn btn-primary btn-icon"
                        disabled={sending || !newMessage.trim()}
                      >
                        {sending ? '⏳' : '➤'}
                      </button>
                    </div>
                  </form>
                )}
              </>
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon">💬</div>
                <div className="empty-state-title">Selecione uma conversa</div>
                <div className="empty-state-text">
                  Escolha uma conversa na lista ao lado para visualizar as mensagens
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default Dashboard;
