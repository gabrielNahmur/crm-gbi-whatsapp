"""
Rotas de gerenciamento de atendentes.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.postgres import get_db
from app.database.redis_client import get_redis, OnlineAgentsManager
from app.models import Agent, VALID_SECTORS
from app.api.routes.auth import get_current_agent, get_password_hash

router = APIRouter()


class AgentCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    sector: str


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    sector: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("")
async def create_agent(
    agent_data: AgentCreate,
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Cria um novo atendente. Apenas admins podem usar.
    """
    # Verificar permissão de admin
    if not current_agent.is_admin:
        raise HTTPException(status_code=403, detail="Apenas administradores podem criar atendentes")
    
    # Validar setor
    if agent_data.sector not in VALID_SECTORS:
        raise HTTPException(status_code=400, detail=f"Setor inválido. Opções: {VALID_SECTORS}")
    
    # Verificar se email já existe
    result = await db.execute(
        select(Agent).where(Agent.email == agent_data.email)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    
    # Criar agente
    new_agent = Agent(
        name=agent_data.name,
        email=agent_data.email,
        password_hash=get_password_hash(agent_data.password),
        sector=agent_data.sector,
        is_active=True,
        is_online=False
    )
    
    db.add(new_agent)
    await db.commit()
    await db.refresh(new_agent)
    
    return new_agent.to_dict()


@router.get("")
async def list_agents(
    sector: Optional[str] = None,
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista todos os atendentes.
    """
    query = select(Agent).where(Agent.is_active == True)
    
    if sector:
        if sector not in VALID_SECTORS:
            raise HTTPException(status_code=400, detail=f"Setor inválido. Opções: {VALID_SECTORS}")
        query = query.where(Agent.sector == sector)
    
    result = await db.execute(query)
    agents = result.scalars().all()
    
    return {
        "agents": [a.to_dict() for a in agents]
    }


@router.get("/online")
async def list_online_agents(
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista atendentes online.
    """
    redis = get_redis()
    online_manager = OnlineAgentsManager(redis)
    
    online_ids = await online_manager.get_online_agents()
    
    if not online_ids:
        return {"agents": []}
    
    result = await db.execute(
        select(Agent).where(Agent.id.in_(online_ids))
    )
    agents = result.scalars().all()
    
    return {
        "agents": [a.to_dict() for a in agents]
    }


@router.get("/{agent_id}")
async def get_agent(
    agent_id: int,
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Detalhes de um atendente.
    """
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Atendente não encontrado")
    
    return agent.to_dict()


@router.put("/{agent_id}")
async def update_agent(
    agent_id: int,
    agent_data: AgentUpdate,
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Atualiza dados de um atendente.
    TODO: Adicionar verificação de permissão (apenas admin ou próprio agente).
    """
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Atendente não encontrado")
    
    if agent_data.name is not None:
        agent.name = agent_data.name
    
    if agent_data.sector is not None:
        if agent_data.sector not in VALID_SECTORS:
            raise HTTPException(status_code=400, detail=f"Setor inválido. Opções: {VALID_SECTORS}")
        agent.sector = agent_data.sector
    
    if agent_data.is_active is not None:
        agent.is_active = agent_data.is_active
    
    await db.commit()
    
    return agent.to_dict()


@router.put("/{agent_id}/admin")
async def toggle_admin(
    agent_id: int,
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Promove ou remove permissão de admin de um atendente.
    Apenas admins podem usar. Não pode remover a própria permissão.
    """
    # Verificar permissão de admin
    if not current_agent.is_admin:
        raise HTTPException(status_code=403, detail="Apenas administradores podem alterar permissões")
    
    # Não pode alterar a própria permissão
    if current_agent.id == agent_id:
        raise HTTPException(status_code=400, detail="Você não pode alterar sua própria permissão de admin")
    
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Atendente não encontrado")
    
    # Toggle is_admin
    agent.is_admin = not agent.is_admin
    await db.commit()
    
    action = "promovido a" if agent.is_admin else "removido de"
    return {
        "status": "success",
        "message": f"Atendente {action} administrador",
        "is_admin": agent.is_admin,
        "agent": agent.to_dict()
    }

@router.delete("/{agent_id}")
async def deactivate_agent(
    agent_id: int,
    current_agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Desativa um atendente (soft delete). Apenas admins podem usar.
    """
    # Verificar permissão de admin
    if not current_agent.is_admin:
        raise HTTPException(status_code=403, detail="Apenas administradores podem desativar atendentes")
    
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Atendente não encontrado")
    
    agent.is_active = False
    agent.is_online = False
    
    # Remove do Redis
    redis = get_redis()
    online_manager = OnlineAgentsManager(redis)
    await online_manager.set_offline(agent_id)
    
    await db.commit()
    
    return {"status": "deactivated"}
