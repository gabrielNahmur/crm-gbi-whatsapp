"""
Cliente Redis para cache e gerenciamento de contexto.
Inclui fallback para memória quando Redis não está disponível.
"""

import redis.asyncio as redis
import json
import logging
import hashlib
from typing import Optional, List, Dict, Any
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Cliente Redis global
redis_client: Optional[redis.Redis] = None
_use_memory_fallback = False

# Fallback em memória quando Redis não está disponível
_memory_store: Dict[str, Any] = {}


async def init_redis():
    """Inicializa conexão com Redis"""
    global redis_client, _use_memory_fallback
    
    try:
        redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        # Testa conexão
        await redis_client.ping()
        logger.info("✅ Redis conectado com sucesso")
    except Exception as e:
        logger.warning(f"⚠️ Redis não disponível: {e}. Usando fallback em memória.")
        _use_memory_fallback = True
        redis_client = None


async def close_redis():
    """Fecha conexão com Redis"""
    global redis_client
    if redis_client:
        await redis_client.close()


def get_redis() -> Optional[redis.Redis]:
    """Retorna cliente Redis ou None se usando fallback"""
    return redis_client


def is_using_memory_fallback() -> bool:
    """Retorna True se está usando fallback em memória"""
    return _use_memory_fallback


class ContextManager:
    """Gerencia contexto de conversas para a IA"""
    
    PREFIX = "context:"
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.max_messages = settings.max_context_messages
        self.ttl = settings.context_ttl_hours * 3600
    
    async def get_context(self, phone: str) -> List[Dict[str, str]]:
        """Recupera contexto da conversa de um telefone"""
        key = f"{self.PREFIX}{phone}"
        
        if self.redis:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
        else:
            # Fallback memória
            if key in _memory_store:
                return _memory_store[key]
        
        return []
    
    async def add_message(self, phone: str, role: str, content: str):
        """Adiciona mensagem ao contexto"""
        key = f"{self.PREFIX}{phone}"
        
        # Recupera contexto atual
        context = await self.get_context(phone)
        
        # Adiciona nova mensagem
        context.append({"role": role, "content": content})
        
        # Mantém apenas as últimas N mensagens
        if len(context) > self.max_messages:
            context = context[-self.max_messages:]
        
        if self.redis:
            await self.redis.setex(key, self.ttl, json.dumps(context))
        else:
            # Fallback memória
            _memory_store[key] = context
    
    async def clear_context(self, phone: str):
        """Limpa contexto de um telefone"""
        key = f"{self.PREFIX}{phone}"
        
        if self.redis:
            await self.redis.delete(key)
        else:
            _memory_store.pop(key, None)


class QueueManager:
    """Gerencia filas de atendimento por setor"""
    
    PREFIX = "queue:"
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
    
    async def add_to_queue(self, sector: str, conversation_id: int):
        """Adiciona conversa à fila do setor"""
        key = f"{self.PREFIX}{sector}"
        
        if self.redis:
            await self.redis.rpush(key, conversation_id)
        else:
            if key not in _memory_store:
                _memory_store[key] = []
            _memory_store[key].append(conversation_id)
            
    async def get_all_queues(self) -> dict:
        """Retorna contagem de todas as filas"""
        queues = {}
        # Lista hardcoded de setores conhecidos (na v2 pode ser dinâmico)
        sectors = ["comercial", "financeiro", "fiscal", "suporte", "outras"]
        
        for s in sectors:
            key = f"{self.PREFIX}{s}"
            count = 0
            if self.redis:
                count = await self.redis.llen(key)
            else:
                count = len(_memory_store.get(key, []))
            queues[s] = count
            
        return queues

    async def remove_from_queue(self, sector: str, conversation_id: int):
        """Remove conversa específica da fila (usado quando muda de setor)"""
        key = f"{self.PREFIX}{sector}"
        
        if self.redis:
            # LREM remove elementos com valor igual
            await self.redis.lrem(key, 0, conversation_id)
        else:
            if key in _memory_store:
                try:
                    # Remove todas as ocorrências do ID
                    _memory_store[key] = [
                        x for x in _memory_store[key] 
                        if x != conversation_id
                    ]
                except ValueError:
                    pass
    
    async def get_next(self, sector: str) -> Optional[int]:
        """Remove e retorna próxima conversa da fila"""
        key = f"{self.PREFIX}{sector}"
        
        if self.redis:
            result = await self.redis.lpop(key)
            return int(result) if result else None
        else:
            if key in _memory_store and _memory_store[key]:
                return _memory_store[key].pop(0)
            return None
    
    async def get_queue_size(self, sector: str) -> int:
        """Retorna tamanho da fila do setor"""
        key = f"{self.PREFIX}{sector}"
        
        if self.redis:
            return await self.redis.llen(key)
        else:
            return len(_memory_store.get(key, []))
    
    async def get_all_queues(self) -> Dict[str, int]:
        """Retorna tamanho de todas as filas"""
        from app.config import SETORES
        queues = {}
        for sector in SETORES:
            queues[sector] = await self.get_queue_size(sector)
        return queues


class OnlineAgentsManager:
    """Gerencia atendentes online"""
    
    KEY = "online_agents"
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
    
    async def set_online(self, agent_id: int):
        """Marca atendente como online"""
        if self.redis:
            await self.redis.sadd(self.KEY, agent_id)
        else:
            if self.KEY not in _memory_store:
                _memory_store[self.KEY] = set()
            _memory_store[self.KEY].add(agent_id)
    
    async def set_offline(self, agent_id: int):
        """Marca atendente como offline"""
        if self.redis:
            await self.redis.srem(self.KEY, agent_id)
        else:
            if self.KEY in _memory_store:
                _memory_store[self.KEY].discard(agent_id)
    
    async def is_online(self, agent_id: int) -> bool:
        """Verifica se atendente está online"""
        if self.redis:
            return await self.redis.sismember(self.KEY, agent_id)
        else:
            return agent_id in _memory_store.get(self.KEY, set())
    
    async def get_online_agents(self) -> List[int]:
        """Retorna lista de IDs de atendentes online"""
        if self.redis:
            members = await self.redis.smembers(self.KEY)
            return [int(m) for m in members]
        else:
            return list(_memory_store.get(self.KEY, set()))


class DebounceManager:
    """Gerencia delay de respostas para agrupar mensagens"""
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.PREFIX = "debounce:"
        
    async def set_last_message_time(self, phone: str, timestamp: float):
        """Define timestamp da última mensagem recebida"""
        key = f"{self.PREFIX}{phone}"
        if self.redis:
            await self.redis.set(key, str(timestamp), ex=60) # Expira em 1 min
        else:
            _memory_store[key] = str(timestamp)
            
    async def get_last_message_time(self, phone: str) -> float:
        """Obtém timestamp da última mensagem"""
        key = f"{self.PREFIX}{phone}"
        val = None
        if self.redis:
            val = await self.redis.get(key)
        else:
            val = _memory_store.get(key)
            
        return float(val) if val else 0.0

    async def check_duplicate_response(self, phone: str, response_text: str, ttl: int = 15) -> bool:
        """
        Verifica se a resposta é duplicada.
        ttl: Tempo em segundos para considerar duplicata (default 15s).
        """
        if not response_text:
            return False

        try:
            # Gera hash do texto para economizar espaço
            content_hash = hashlib.md5(response_text.encode('utf-8')).hexdigest()
            key = f"{self.PREFIX}last_resp:{phone}"
            
            # Tenta pegar valor antigo
            old_hash = None
            if self.redis:
                old_hash = await self.redis.get(key)
                if old_hash:
                    old_hash = old_hash.decode('utf-8')
            else:
                old_hash = _memory_store.get(key)
                
            if old_hash and old_hash == content_hash:
                return True # É duplicada
                
            # Salva novo hash com TTL
            if self.redis:
                await self.redis.set(key, content_hash, ex=ttl)
            else:
                _memory_store[key] = content_hash
                
            return False
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Erro no check_duplicate_response: {e}")
            return False
