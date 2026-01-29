"""
Rotas de mensagens.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database.postgres import get_db
from app.models import Message, Conversation, Lead
from app.api.routes.auth import get_current_agent
from app.services.bot_engine import BotEngine
from sqlalchemy.orm import joinedload

router = APIRouter()


class MessageSend(BaseModel):
    conversation_id: int
    content: str


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_type: str
    sender_id: Optional[str]
    content: str
    message_type: str
    created_at: str


@router.get("/conversation/{conversation_id}")
async def get_conversation_messages(
    conversation_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista mensagens de uma conversa.
    """
    # Verifica se conversa existe (com eager loading para evitar lazy load error)
    result = await db.execute(
        select(Conversation)
        .options(joinedload(Conversation.lead), joinedload(Conversation.agent))
        .where(Conversation.id == conversation_id)
    )
    conversation = result.unique().scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    # Busca mensagens
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
        .offset(offset)
    )
    messages = result.scalars().all()
    
    # Inverte para ordem cronológica
    messages = list(reversed(messages))
    
    return {
        "messages": [m.to_dict() for m in messages],
        "total": len(messages),
        "conversation": conversation.to_dict()
    }


@router.post("/send")
async def send_message(
    message_data: MessageSend,
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Envia mensagem como atendente.
    """
    bot = BotEngine(db)
    
    try:
        message = await bot.send_agent_message(
            conversation_id=message_data.conversation_id,
            agent_id=current_agent.id,
            message_text=message_data.content
        )
        
        return {
            "status": "sent",
            "message": message.to_dict()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao enviar mensagem: {str(e)}")


@router.put("/{message_id}/read")
async def mark_as_read(
    message_id: int,
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Marca mensagem como lida.
    """
    result = await db.execute(
        select(Message).where(Message.id == message_id)
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada")
    
    message.is_read = True
    await db.commit()
    
    return {"status": "ok"}
