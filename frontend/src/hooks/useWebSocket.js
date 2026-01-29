import { useEffect, useRef, useCallback, useState } from 'react';

/**
 * Hook para conexão WebSocket com reconexão automática
 * @param {number} agentId - ID do agente
 * @param {string} sector - Setor do agente
 * @param {function} onMessage - Callback para mensagens recebidas
 */
export function useWebSocket(agentId, sector, onMessage) {
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);

  const connect = useCallback(() => {
    if (!agentId || !sector) return;

    // Determina o host do WebSocket
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.hostname;
    const wsPort = '8002'; // Backend port
    const wsUrl = `${wsProtocol}//${wsHost}:${wsPort}/ws/${agentId}/${sector}`;

    console.log('[WS] Connecting to:', wsUrl);

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WS] Connected');
        setIsConnected(true);
        
        // Inicia heartbeat
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
        
        ws._pingInterval = pingInterval;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('[WS] Message received:', data);
          setLastMessage(data);
          
          // Chama callback externo
          if (onMessage) {
            onMessage(data);
          }
        } catch (e) {
          console.error('[WS] Error parsing message:', e);
        }
      };

      ws.onclose = (event) => {
        console.log('[WS] Disconnected:', event.code, event.reason);
        setIsConnected(false);
        
        if (ws._pingInterval) {
          clearInterval(ws._pingInterval);
        }

        // Reconecta após 3 segundos
        if (event.code !== 1000) { // Não reconecta se foi fechamento normal
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('[WS] Attempting reconnect...');
            connect();
          }, 3000);
        }
      };

      ws.onerror = (error) => {
        console.error('[WS] Error:', error);
      };

    } catch (error) {
      console.error('[WS] Connection error:', error);
    }
  }, [agentId, sector, onMessage]);

  // Conecta quando agentId e sector estiverem disponíveis
  useEffect(() => {
    connect();

    return () => {
      // Cleanup
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        if (wsRef.current._pingInterval) {
          clearInterval(wsRef.current._pingInterval);
        }
        wsRef.current.close(1000, 'Component unmounting');
      }
    };
  }, [connect]);

  // Função para enviar mensagens
  const sendMessage = useCallback((data) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { isConnected, lastMessage, sendMessage };
}

export default useWebSocket;
