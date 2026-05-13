"""
Pydantic schemas for Document API requests/responses.
"""

from pydantic import BaseModel
from datetime import datetime
from models import DocumentStatus, DocumentType
from schemas.analysis import AnalysisSummary


class DocumentUploadResponse(BaseModel):
    id: str
    case_id: str | None = None
    filename: str
    original_filename: str
    document_type: DocumentType
    status: DocumentStatus
    file_size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    id: str
    case_id: str | None = None
    original_filename: str
    document_type: DocumentType
    status: DocumentStatus
    file_size_bytes: int
    created_at: datetime
    updated_at: datetime
    analyses: list[AnalysisSummary] | None = None

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentListItem):
    filename: str
    file_url: str | None = None
    file_type: str
    user_id: str
    org_id: str

    model_config = {"from_attributes": True}
