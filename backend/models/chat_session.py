import uuid

from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.session import Base


class ChatSession(Base):
    """
    Represents one simulated support conversation created by a user.
    Product / Scenario / Mode / Difficulty come from Member 3's session
    configuration screen and are stored here as plain strings so this
    table stays decoupled from whichever config options the frontend adds.
    """
    __tablename__ = "sessions"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(CHAR(36), ForeignKey("users.id"), nullable=False)

    mode = Column(String(50), nullable=False, default="simulator")       # simulator / manual / replay
    product = Column(String(150), nullable=True)
    scenario = Column(String(255), nullable=True)
    customer_mood = Column(String(50), nullable=True)
    difficulty = Column(String(50), nullable=True)

    status = Column(String(30), nullable=False, default="active")        # active / completed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    result = relationship("SessionResult", back_populates="session", uselist=False, cascade="all, delete-orphan")
