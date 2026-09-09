import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from core.config import settings
from core.deps import get_current_admin
from database.session import get_db
from models.user import User, UserRole
from models.document import Document
from models.chat_session import ChatSession
from models.session_result import SessionResult
from schemas.document import DocumentOut
from schemas.session import AdminSessionSummaryOut
from schemas.auth import UserOut

router = APIRouter(prefix="/api/admin", tags=["Admin"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


# ---------------------------------------------------------------------------
# Document upload (FAQ / policy documents)
# ---------------------------------------------------------------------------

@router.post("/documents/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    stored_name = f"{uuid.uuid4()}{ext}"
    stored_path = os.path.join(settings.UPLOAD_DIR, stored_name)

    contents = file.file.read()
    size_kb = len(contents) // 1024
    if size_kb > settings.MAX_UPLOAD_MB * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.MAX_UPLOAD_MB}MB limit")

    with open(stored_path, "wb") as f:
        f.write(contents)

    doc = Document(
        uploaded_by_id=admin.id,
        filename=file.filename,
        file_path=stored_path,
        file_type=ext.lstrip("."),
        file_size_kb=size_kb,
        category=category,
        description=description,
        ingestion_status="pending",  # Member 4's RAG pipeline picks this up
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/documents", response_model=List[DocumentOut])
def list_documents(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    return db.query(Document).order_by(Document.created_at.desc()).all()


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    db.delete(doc)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Dashboard: customer conversation history / summaries
# ---------------------------------------------------------------------------

@router.get("/dashboard/conversations", response_model=List[AdminSessionSummaryOut])
def list_conversation_summaries(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    rows = (
        db.query(ChatSession, User, SessionResult)
        .join(User, ChatSession.user_id == User.id)
        .outerjoin(SessionResult, SessionResult.session_id == ChatSession.id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )

    return [
        AdminSessionSummaryOut(
            session_id=session.id,
            user_name=user.name,
            user_email=user.email,
            product=session.product,
            scenario=session.scenario,
            status=session.status,
            created_at=session.created_at,
            summary=result.summary if result else None,
            score=result.score if result else None,
        )
        for session, user, result in rows
    ]


# ---------------------------------------------------------------------------
# User management (promote a regular user to admin, list all users)
# ---------------------------------------------------------------------------

@router.get("/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("/users/{user_id}/promote", response_model=UserOut)
def promote_to_admin(user_id: str, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = UserRole.admin
    db.commit()
    db.refresh(user)
    return user
