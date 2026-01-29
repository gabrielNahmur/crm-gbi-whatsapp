"""
WebSocket para comunicação em tempo real.
"""

import json
import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.postgres import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Gerencia conexões WebSocket"""
    
    def __init__(self):
        # Mapa de agent_id -> WebSocket
        self.active_connections: Dict[int, WebSocket] = {}
        # Mapa de sector -> Set de agent_ids
        self.sector_agents: Dict[str, Set[int]] = {}
    
    async def connect(self, websocket: WebSocket, agent_id: int, sector: str):
        """Registra nova conexão"""
        await websocket.accept()
        self.active_connections[agent_id] = websocket
        
        if sector not in self.sector_agents:
            self.sector_agents[sector] = set()
        self.sector_agents[sector].add(agent_id)
        
        logger.info(f"Agent {agent_id} connected to WebSocket (sector: {sector})")
    
    def disconnect(self, agent_id: int, sector: str):
        """Remove conexão"""
        if agent_id in self.active_connections:
            del self.active_connections[agent_id]
        
        if sector in self.sector_agents:
            self.sector_agents[sector].discard(agent_id)
        
        logger.info(f"Agent {agent_id} disconnected from WebSocket")
    
    async def send_to_agent(self, agent_id: int, message: dict):
        """Envia mensagem para um agente específico"""
        if agent_id in self.active_connections:
            websocket = self.active_connections[agent_id]
            await websocket.send_json(message)
    
    async def broadcast_to_sector(self, sector: str, message: dict):
        """Envia mensagem para todos os agentes de um setor"""
        if sector in self.sector_agents:
            for agent_id in self.sector_agents[sector]:
                await self.send_to_agent(agent_id, message)
    
    async def broadcast_all(self, message: dict):
        """Envia mensagem para todos os agentes conectados"""
        for agent_id in self.active_connections:
            await self.send_to_agent(agent_id, message)


# Instância global
manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Retorna o gerenciador de conexões"""
    return manager


@router.websocket("/{agent_id}/{sector}")
async def websocket_endpoint(
    websocket: WebSocket,
    agent_id: int,
    sector: str
):
    """
    Endpoint WebSocket para atendentes.
    
    Conecta com: ws://host/ws/{agent_id}/{sector}
    
    Mensagens recebidas (cliente -> servidor):
    - {"type": "ping"} - Heartbeat
    - {"type": "typing", "conversation_id": 123} - Indica que está digitando
    
    Mensagens enviadas (servidor -> cliente):
    - {"type": "new_message", "conversation_id": 123, "message": {...}}
    - {"type": "new_conversation", "conversation": {...}}
    - {"type": "queue_update", "queue_sizes": {...}}
    - {"type": "pong"} - Resposta ao heartbeat
    """
    await manager.connect(websocket, agent_id, sector)
    
    try:
        while True:
            # Recebe mensagem do cliente
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif message_type == "typing":
                # Notifica outros agentes que este está digitando
                conversation_id = data.get("conversation_id")
                await manager.broadcast_to_sector(sector, {
                    "type": "agent_typing",
                    "agent_id": agent_id,
                    "conversation_id": conversation_id
                })
            
            else:
                logger.warning(f"Unknown WebSocket message type: {message_type}")
    
    except WebSocketDisconnect:
        manager.disconnect(agent_id, sector)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(agent_id, sector)


# Funções para notificar eventos (chamadas de outras partes do código)
async def notify_new_message(conversation_id: int, sector: str, message: dict):
    """Notifica novo mensagem para TODOS os agentes conectados"""
    logger.info(f"[WS] notify_new_message: conv_id={conversation_id}, sector={sector}, active_connections={list(manager.active_connections.keys())}")
    
    # Broadcast para TODOS os agentes (não apenas do setor para garantir entrega)
    await manager.broadcast_all({
        "type": "new_message",
        "conversation_id": conversation_id,
        "message": message
    })
    logger.info(f"[WS] Message broadcast to {len(manager.active_connections)} agents")


async def notify_new_conversation(sector: str, conversation: dict):
    """Notifica nova conversa na fila"""
    await manager.broadcast_to_sector(sector, {
        "type": "new_conversation",
        "conversation": conversation
    })


async def notify_queue_update():
    """Notifica atualização nas filas para TODOS os agentes"""
    from app.database.redis_client import QueueManager
    from app.database.redis_client import get_redis
    
    try:
        r = get_redis()
        qm = QueueManager(r)
        
        # Busca tamanho de todas as filas
        queue_sizes = await qm.get_all_queues()
        
        # Envia para todos (não apenas um setor, pois o badge é global)
        await manager.broadcast_all({
            "type": "queue_update",
            "queue_sizes": queue_sizes
        })
        logger.info(f"[WS] Queue update broadcast: {queue_sizes}")
        
    except Exception as e:
        logger.error(f"Erro ao notificar atualização de fila: {e}")
