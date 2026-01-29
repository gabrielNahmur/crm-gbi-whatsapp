"""
Model Conversation - Representa uma conversa/atendimento.
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.postgres import Base

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.agent import Agent
    from app.models.message import Message


# Status válidos
CONVERSATION_STATUS = [
    "bot_handling",
    "waiting_queue",
    "in_progress",
    "resolved",
    "closed"
]


class Conversation(Base):
    """Tabela de conversas"""
    
    __tablename__ = "conversations"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="bot_handling")
    sector: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    intent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relacionamentos
    lead: Mapped["Lead"] = relationship("Lead", back_populates="conversations")
    agent: Mapped[Optional["Agent"]] = relationship("Agent", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="conversation", order_by="Message.created_at")
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, lead_id={self.lead_id}, status={self.status})>"
    
    def to_dict(self, include_messages=False):
        data = {
            "id": self.id,
            "lead_id": self.lead_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "sector": self.sector,
            "intent": self.intent,
            "priority": self.priority,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata_json,
            "lead": self.lead.to_dict() if self.lead else None,
            "agent": self.agent.to_dict() if self.agent else None
        }
        if include_messages:
            data["messages"] = [m.to_dict() for m in self.messages]
        return data
