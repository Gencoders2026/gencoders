import uuid

from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.session import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(CHAR(36), ForeignKey("sessions.id"), nullable=False)

    sender = Column(String(30), nullable=False)   # customer / support / coach / system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")
