from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from core.deps import get_current_user
from database.session import get_db
from models.user import User
from models.chat_session import ChatSession
from models.message import Message
from models.session_result import SessionResult
from schemas.session import (
    SessionCreate,
    SessionOut,
    SessionDetailOut,
    MessageCreate,
    MessageOut,
    SessionResultOut,
)

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Any logged-in user can start a new conversation."""
    session = ChatSession(
        user_id=current_user.id,
        mode=payload.mode,
        product=payload.product,
        scenario=payload.scenario,
        customer_mood=payload.customer_mood,
        difficulty=payload.difficulty,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("", response_model=List[SessionOut])
def list_my_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """A user only ever sees their own conversations."""
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )


@router.get("/{session_id}", response_model=SessionDetailOut)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(ChatSession)
        .options(joinedload(ChatSession.messages), joinedload(ChatSession.result))
        .filter(ChatSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not your session")
    return session


@router.post("/{session_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def add_message(
    session_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Appends a message to a conversation. Called by the frontend for the
    user's own reply, and by Member 2's orchestrator (server-side) to
    store customer/support/coach agent turns.
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not your session")

    message = Message(session_id=session_id, sender=payload.sender, content=payload.content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.post("/{session_id}/complete", response_model=SessionOut)
def complete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy.sql import func

    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not your session")

    session.status = "completed"
    session.completed_at = func.now()
    db.commit()
    db.refresh(session)
    return session


@router.post("/{session_id}/result", response_model=SessionResultOut, status_code=status.HTTP_201_CREATED)
def save_session_result(
    session_id: str,
    payload: SessionResultOut,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stores the coach agent's summary/score/feedback for a session.
    Called by Member 2's orchestrator once the coach agent finishes
    evaluating the conversation. Powers the admin dashboard summaries.
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not your session")

    result = db.query(SessionResult).filter(SessionResult.session_id == session_id).first()
    if result:
        result.summary = payload.summary
        result.score = payload.score
        result.feedback = payload.feedback
    else:
        result = SessionResult(
            session_id=session_id,
            summary=payload.summary,
            score=payload.score,
            feedback=payload.feedback,
        )
        db.add(result)

    db.commit()
    db.refresh(result)
    return result
