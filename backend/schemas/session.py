from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class SessionCreate(BaseModel):
    mode: str = "simulator"
    product: Optional[str] = None
    scenario: Optional[str] = None
    customer_mood: Optional[str] = None
    difficulty: Optional[str] = None


class MessageCreate(BaseModel):
    sender: str
    content: str


class MessageOut(BaseModel):
    id: str
    sender: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class SessionResultOut(BaseModel):
    summary: Optional[str]
    score: Optional[float]
    feedback: Optional[str]

    class Config:
        from_attributes = True


class SessionOut(BaseModel):
    id: str
    mode: str
    product: Optional[str]
    scenario: Optional[str]
    customer_mood: Optional[str]
    difficulty: Optional[str]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class SessionDetailOut(SessionOut):
    messages: List[MessageOut] = []
    result: Optional[SessionResultOut] = None


class AdminSessionSummaryOut(BaseModel):
    """Row shown on the admin dashboard: one conversation + its user + summary."""
    session_id: str
    user_name: str
    user_email: str
    product: Optional[str]
    scenario: Optional[str]
    status: str
    created_at: datetime
    summary: Optional[str] = None
    score: Optional[float] = None
