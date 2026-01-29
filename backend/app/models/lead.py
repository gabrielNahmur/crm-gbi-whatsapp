"""
Model Lead - Representa um cliente/contato.
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.postgres import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Lead(Base):
    """Tabela de leads (clientes)"""
    
    __tablename__ = "leads"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_contact: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_contact: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    total_conversations: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    conversations: Mapped[List["Conversation"]] = relationship("Conversation", back_populates="lead")
    
    def __repr__(self):
        return f"<Lead(id={self.id}, phone={self.phone}, name={self.name})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "phone": self.phone,
            "name": self.name,
            "email": self.email,
            "company": self.company,
            "first_contact": self.first_contact.isoformat() if self.first_contact else None,
            "last_contact": self.last_contact.isoformat() if self.last_contact else None,
            "total_conversations": self.total_conversations,
            "metadata": self.metadata_json
        }
