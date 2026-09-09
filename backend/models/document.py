import uuid

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.session import Base


class Document(Base):
    """
    Metadata row for FAQ / policy documents uploaded by admins.
    The physical file is saved to disk (UPLOAD_DIR); Member 4's RAG
    pipeline can read from this table to know which files to ingest,
    chunk and embed.
    """
    __tablename__ = "documents"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    uploaded_by_id = Column(CHAR(36), ForeignKey("users.id"), nullable=False)

    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=True)
    file_size_kb = Column(Integer, nullable=True)
    category = Column(String(100), nullable=True)   # e.g. "refund_policy", "faq"
    description = Column(Text, nullable=True)

    # RAG ingestion status, updated by Member 4's pipeline later
    ingestion_status = Column(String(30), nullable=False, default="pending")  # pending / processed / failed

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    uploaded_by = relationship("User", back_populates="documents")
