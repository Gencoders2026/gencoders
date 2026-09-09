import uuid

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.session import Base


class SessionResult(Base):
    """
    Stores the coach agent's evaluation + a short summary of the
    conversation. The admin dashboard reads this table to show
    customer conversation history/summaries.
    """
    __tablename__ = "session_results"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(CHAR(36), ForeignKey("sessions.id"), unique=True, nullable=False)

    summary = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="result")
