"""
Rotas de autenticação de atendentes.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
import bcrypt

from app.config import get_settings
from app.database.postgres import get_db
from app.database.redis_client import get_redis, OnlineAgentsManager
from app.models import Agent, VALID_SECTORS

router = APIRouter()
settings = get_settings()

# Configuração de segurança
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8


# Schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    agent: dict


class AgentCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    sector: str


class AgentResponse(BaseModel):
    id: int
    name: str
    email: str
    sector: str
    is_active: bool
    is_online: bool


# Funções auxiliares
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


async def get_current_agent(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Agent:
    """Dependency para obter agente autenticado"""
    # Debug
    print(f"DEBUG AUTH: Validating token {token[:10]}...")
    
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        agent_id = int(payload.get("sub"))
        print(f"DEBUG AUTH: Payload decoded. Sub: {agent_id} (Type: {type(agent_id)})")
        
        if agent_id is None:
            print("DEBUG AUTH: Agent ID is None in payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais inválidas (No ID)",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError as e:
        print(f"DEBUG AUTH: JWT Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Credenciais inválidas (JWT: {str(e)})",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    
    if agent is None:
        print("DEBUG AUTH: Agent not found in DB")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas (Agente não encontrado)",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not agent.is_active:
        print("DEBUG AUTH: Agent inactive")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas (Inativo)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return agent


# Rotas
@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    Login de atendente.
    """
    # Busca agente por email
    result = await db.execute(
        select(Agent).where(Agent.email == form_data.username)
    )
    agent = result.scalar_one_or_none()
    
    if not agent or not verify_password(form_data.password, agent.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta desativada"
        )
    
    # Marca como online
    agent.is_online = True
    redis = get_redis()
    online_manager = OnlineAgentsManager(redis)
    await online_manager.set_online(agent.id)
    
    # Cria token
    access_token = create_access_token(data={"sub": str(agent.id)})
    
    await db.commit()
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "agent": agent.to_dict()
    }


@router.post("/logout")
async def logout(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db)
):
    """
    Logout de atendente.
    """
    current_agent.is_online = False
    
    redis = get_redis()
    online_manager = OnlineAgentsManager(redis)
    await online_manager.set_offline(current_agent.id)
    
    await db.commit()
    
    return {"message": "Logout realizado com sucesso"}


@router.get("/me", response_model=AgentResponse)
async def get_me(current_agent: Agent = Depends(get_current_agent)):
    """
    Retorna dados do atendente logado.
    """
    return current_agent.to_dict()


@router.post("/register", response_model=AgentResponse)
async def register_agent(
    agent_data: AgentCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Registra novo atendente.
    TODO: Adicionar autenticação de admin.
    """
    # Verifica se email já existe
    result = await db.execute(
        select(Agent).where(Agent.email == agent_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado"
        )
    
    # Valida setor
    if agent_data.sector not in VALID_SECTORS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Setor inválido. Opções: {VALID_SECTORS}"
        )
    
    # Cria agente
    agent = Agent(
        name=agent_data.name,
        email=agent_data.email,
        password_hash=get_password_hash(agent_data.password),
        sector=agent_data.sector
    )
    
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    
    return agent.to_dict()
