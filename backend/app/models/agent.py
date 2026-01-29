"""
Model Agent - Representa um atendente.
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.postgres import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Agent(Base):
    """Tabela de atendentes"""
    
    __tablename__ = "agents"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str] = mapped_column(String(50), nullable=False)  # comercial, financeiro, fiscal, suporte, outros
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)  # Apenas admins podem gerenciar atendentes
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    conversations: Mapped[List["Conversation"]] = relationship("Conversation", back_populates="agent")
    
    def __repr__(self):
        return f"<Agent(id={self.id}, name={self.name}, sector={self.sector})>"
    
    def to_dict(self, include_sensitive=False):
        data = {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "sector": self.sector,
            "is_active": self.is_active,
            "is_online": self.is_online,
            "is_admin": self.is_admin,
            "avatar_url": self.avatar_url,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        if include_sensitive:
            data["password_hash"] = self.password_hash
        return data


# Setores válidos
# Setores válidos
VALID_SECTORS = [
    "comercial",
    "compras",
    "contas_pagar",
    "contas_receber",
    "rh",
    "atendimento_humano",
    "geral",
    "outros"
]
