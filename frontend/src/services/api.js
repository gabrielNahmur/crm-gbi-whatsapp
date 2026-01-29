import axios from 'axios';

// Production uses relative URL (nginx proxies /api), development uses localhost:8002
const API_URL = import.meta.env.PROD ? '' : 'http://localhost:8002';

// Cria instância do axios
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para adicionar token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Interceptor para lidar com erros - SEM redirect automático
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.status, error.response?.data);
    // NÃO faz redirect automático para evitar loops
    // O componente que chamou a API deve lidar com o erro
    return Promise.reject(error);
  }
);

// Auth
export const authService = {
  async login(email, password) {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);
    
    const response = await api.post('/api/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return response.data;
  },
  
  async logout() {
    try {
      await api.post('/api/auth/logout');
    } catch (e) {
      console.log('Logout error (ignored):', e);
    }
    localStorage.removeItem('token');
    localStorage.removeItem('agent');
  },
  
  async getMe() {
    const response = await api.get('/api/auth/me');
    return response.data;
  },
};

// Conversations
export const conversationsService = {
  async list(params = {}) {
    const response = await api.get('/api/conversations', { params });
    return response.data;
  },
  
  async getQueue(sector) {
    const response = await api.get('/api/conversations/queue', {
      params: sector ? { sector } : {},
    });
    return response.data;
  },
  
  async get(id) {
    const response = await api.get(`/api/conversations/${id}`);
    return response.data;
  },
  
  async accept(id) {
    const response = await api.post(`/api/conversations/${id}/accept`);
    return response.data;
  },
  
  async resolve(id) {
    const response = await api.post(`/api/conversations/${id}/resolve`);
    return response.data;
  },
  
  async close(id) {
    const response = await api.post(`/api/conversations/${id}/close`);
    return response.data;
  },
  
  async getStats() {
    try {
      const response = await api.get('/api/conversations/stats/summary');
      return response.data;
    } catch (error) {
      console.error('Error getting stats:', error);
      return { by_status: {}, by_sector: {}, queues: {} };
    }
  },
};

// Messages
export const messagesService = {
  async getByConversation(conversationId, params = {}) {
    try {
      const response = await api.get(`/api/messages/conversation/${conversationId}`, { params });
      return response.data;
    } catch (error) {
      console.error('Error getting messages:', error);
      return { messages: [] };
    }
  },
  
  async send(conversationId, content) {
    const response = await api.post('/api/messages/send', {
      conversation_id: conversationId,
      content,
    });
    return response.data;
  },
  
  async markAsRead(messageId) {
    const response = await api.put(`/api/messages/${messageId}/read`);
    return response.data;
  },
};

// Agents
export const agentsService = {
  async list(sector) {
    try {
      const response = await api.get('/api/agents', {
        params: sector ? { sector } : {},
      });
      return response.data;
    } catch (error) {
      console.error('Error listing agents:', error);
      return { agents: [] };
    }
  },
  
  async getOnline() {
    try {
      const response = await api.get('/api/agents/online');
      return response.data;
    } catch (error) {
      console.error('Error getting online agents:', error);
      return { agents: [] };
    }
  },
};

export default api;
