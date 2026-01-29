"""
Model Message - Representa uma mensagem.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.postgres import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Message(Base):
    """Tabela de mensagens"""
    
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'customer', 'bot', 'agent'
    sender_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # phone ou agent_id
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), default="text")  # text, image, audio, document
    media_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    whatsapp_message_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    intent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sentiment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sentiment_score: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Relacionamentos
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    
    def __repr__(self):
        return f"<Message(id={self.id}, sender={self.sender_type}, content={self.content[:30]}...)>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "sender_type": self.sender_type,
            "sender_id": self.sender_id,
            "content": self.content,
            "message_type": self.message_type,
            "media_url": self.media_url,
            "whatsapp_message_id": self.whatsapp_message_id,
            "intent": self.intent,
            "sentiment": self.sentiment,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
