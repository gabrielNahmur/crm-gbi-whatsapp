"""
Rotas de conversas.
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload

from app.database.postgres import get_db
from app.database.redis_client import get_redis, QueueManager
from app.models import Conversation, CONVERSATION_STATUS, Lead, Agent, VALID_SECTORS
from app.api.routes.auth import get_current_agent

router = APIRouter()


class ConversationUpdate(BaseModel):
    status: Optional[str] = None
    sector: Optional[str] = None


@router.get("")
async def list_conversations(
    status: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista conversas. Filtra por setor do atendente se não for admin.
    """
    query = select(Conversation).options(
        selectinload(Conversation.lead),
        selectinload(Conversation.agent)
    )
    
    # Filtro por status
    if status:
        if status not in CONVERSATION_STATUS:
            raise HTTPException(status_code=400, detail=f"Status inválido. Opções: {CONVERSATION_STATUS}")
        query = query.where(Conversation.status == status)
    
    # Filtro por setor
    if sector:
        if sector not in VALID_SECTORS:
            raise HTTPException(status_code=400, detail=f"Setor inválido. Opções: {VALID_SECTORS}")
        query = query.where(Conversation.sector == sector)
    else:
        # Se não especificou setor, mostra conversas do setor do atendente OU sem setor definido
        from sqlalchemy import or_
        query = query.where(
            or_(
                Conversation.sector == current_agent.sector,
                Conversation.sector.is_(None)
            )
        )
    
    # Ordenação e paginação
    query = query.order_by(desc(Conversation.started_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    conversations = result.scalars().all()
    
    return {
        "conversations": [c.to_dict() for c in conversations],
        "total": len(conversations)
    }


@router.get("/debug/all")
async def list_conversations_debug(db: AsyncSession = Depends(get_db)):
    """
    DEBUG: Lista TODAS as conversas sem autenticação
    """
    result = await db.execute(select(Conversation).options(selectinload(Conversation.lead)))
    conversations = result.scalars().all()
    return [c.to_dict() for c in conversations]


@router.get("/queue")
async def get_queue(
    sector: Optional[str] = Query(None),
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista conversas na fila de espera.
    """
    redis = get_redis()
    queue_manager = QueueManager(redis)
    
    # Se não especificou setor, usa o do atendente + atendimento_humano
    # (Solicitacao do user: atendimento_humano visivel para todos)
    from sqlalchemy import or_

    conditions = [Conversation.status == "waiting_queue"]

    if sector:
        # Se front pediu setor específico, filtra só ele
        conditions.append(Conversation.sector == sector)
    else:
        # Padrão: Setor do agente + Atendimento Humano
        # Inclui também 'atendente' por compatibilidade se houver
        conditions.append(or_(
            Conversation.sector == current_agent.sector,
            Conversation.sector == 'atendimento_humano',
            Conversation.sector == 'atendente'
        ))
    
    # Busca conversas na fila
    query = select(Conversation).options(
        selectinload(Conversation.lead)
    ).where(
        *conditions
    ).order_by(Conversation.started_at)
    
    result = await db.execute(query)
    conversations = result.scalars().all()
    
    # Tamanho de todas as filas
    all_queues = await queue_manager.get_all_queues()
    
    return {
        "queue": [c.to_dict() for c in conversations],
        "queue_sizes": all_queues,
        "current_sector": sector
    }


@router.post("/{conversation_id}/accept")
async def accept_conversation(
    conversation_id: int,
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Atendente aceita/assume uma conversa.
    Funciona para conversas na fila (waiting_queue) ou com o bot (bot_handling).
    """
    result = await db.execute(
        select(Conversation)
        .options(
            selectinload(Conversation.lead),
            selectinload(Conversation.agent)
        )
        .where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    # Permite assumir conversas na fila OU com o bot
    allowed_statuses = ["waiting_queue", "bot_handling"]
    if conversation.status not in allowed_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Conversa não pode ser assumida. Status atual: {conversation.status}"
        )
    
    # Se estava na fila, remove do Redis
    if conversation.status == "waiting_queue" and conversation.sector:
        try:
            from app.database.redis_client import QueueManager
            from app.config import get_settings
            
            # Necessário inicializar QueueManager aqui pois não temos no endpoint wrapper
            # Na v2 podemos usar dependência
            import redis.asyncio as redis
            settings = get_settings()
            # Tenta pegar conexao global ou cria nova (ideal: injetar dependencia)
            from app.database.redis_client import get_redis
            r = get_redis()
            
            qm = QueueManager(r)
            await qm.remove_from_queue(conversation.sector, conversation.id)
            
            # Notifica
            from app.api.websocket import notify_queue_update
            await notify_queue_update()
            
        except Exception as e:
            print(f"Erro ao atualizar fila Redis: {e}")

    # Atribui ao atendente
    conversation.agent_id = current_agent.id
    conversation.status = "in_progress"
    
    await db.commit()
    
    return {
        "status": "accepted",
        "conversation": conversation.to_dict()
    }


@router.post("/{conversation_id}/resolve")
async def resolve_conversation(
    conversation_id: int,
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Marca conversa como resolvida.
    """
    result = await db.execute(
        select(Conversation)
        .options(
            selectinload(Conversation.lead),
            selectinload(Conversation.agent)
        )
        .where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    # Se estava na fila, remove do Redis
    if conversation.status == "waiting_queue" and conversation.sector:
        try:
            from app.database.redis_client import QueueManager, get_redis
            r = get_redis()
            qm = QueueManager(r)
            await qm.remove_from_queue(conversation.sector, conversation.id)
            
            # Notifica
            from app.api.websocket import notify_queue_update
            await notify_queue_update()
        except Exception as e:
            print(f"Erro ao atualizar fila Redis: {e}")

    conversation.status = "resolved"
    conversation.resolved_at = datetime.utcnow()
    
    await db.commit()
    
    return {
        "status": "resolved",
        "conversation": conversation.to_dict()
    }


@router.post("/{conversation_id}/close")
async def close_conversation(
    conversation_id: int,
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Fecha conversa definitivamente.
    """
    result = await db.execute(
        select(Conversation)
        .options(
            selectinload(Conversation.lead),
            selectinload(Conversation.agent)
        )
        .where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    # Se estava na fila, remove do Redis
    if conversation.status == "waiting_queue" and conversation.sector:
        try:
            from app.database.redis_client import QueueManager, get_redis
            r = get_redis()
            qm = QueueManager(r)
            await qm.remove_from_queue(conversation.sector, conversation.id)
            
            # Notifica
            from app.api.websocket import notify_queue_update
            await notify_queue_update()
        except Exception as e:
            print(f"Erro ao atualizar fila Redis: {e}")

    conversation.status = "closed"
    if not conversation.resolved_at:
        conversation.resolved_at = datetime.utcnow()
    
    await db.commit()
    
    return {
        "status": "closed",
        "conversation": conversation.to_dict()
    }


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Detalhes de uma conversa.
    """
    result = await db.execute(
        select(Conversation)
        .options(
            selectinload(Conversation.lead),
            selectinload(Conversation.agent),
            selectinload(Conversation.messages)
        )
        .where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    return conversation.to_dict(include_messages=True)


@router.get("/stats/summary")
async def get_stats(
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Estatísticas resumidas.
    """
    # Total de conversas por status
    result = await db.execute(
        select(
            Conversation.status,
            func.count(Conversation.id)
        ).group_by(Conversation.status)
    )
    status_counts = {row[0]: row[1] for row in result.all()}
    
    # Total de conversas por setor
    result = await db.execute(
        select(
            Conversation.sector,
            func.count(Conversation.id)
        ).where(Conversation.sector.isnot(None))
        .group_by(Conversation.sector)
    )
    sector_counts = {row[0] if row[0] else "outros": row[1] for row in result.all()}
    
    # Filas
    redis = get_redis()
    queue_manager = QueueManager(redis)
    queue_sizes = await queue_manager.get_all_queues()
    
    return {
        "by_status": status_counts,
        "by_sector": sector_counts,
        "queues": queue_sizes
    }
