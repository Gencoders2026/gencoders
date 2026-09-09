from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: Optional[str]
    file_size_kb: Optional[int]
    category: Optional[str]
    description: Optional[str]
    ingestion_status: str
    created_at: datetime

    class Config:
        from_attributes = True
