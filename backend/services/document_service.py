"""
Document service — business logic for document operations.
"""

import uuid
import os
from prisma import Prisma
from models import CaseStatus, DocumentStatus, DocumentType
from prisma.models import Document
from services.case_analysis_service import invalidate_final_case_analysis_for_case
from services.case_service import create_case
from services.storage_service import upload_file, store_password


def classify_document_type(filename: str) -> DocumentType:
    """Infer a provisional document type hint from filename text."""
    name_lower = filename.lower()
    if "bank" in name_lower or "statement" in name_lower:
        return DocumentType.BANK_STATEMENT
    elif "tax" in name_lower or "itr" in name_lower:
        return DocumentType.TAX_RETURN
    elif "salary" in name_lower or "payslip" in name_lower or "slip" in name_lower:
        return DocumentType.SALARY_SLIP
    elif "employ" in name_lower or "offer" in name_lower or "letter" in name_lower:
        return DocumentType.EMPLOYMENT_LETTER
    elif "income" in name_lower:
        return DocumentType.INCOME_PROOF
    elif "id" in name_lower or "aadhaar" in name_lower or "pan" in name_lower or "passport" in name_lower:
        return DocumentType.ID_DOCUMENT
    return DocumentType.OTHER


async def create_document(
    db: Prisma,
    original_filename: str,
    file_content: bytes,
    user_id: str,
    org_id: str,
    content_type: str = "application/pdf",
    password: str = "",
    document_type: str = "",
    case_id: str | None = None,
    applicant_name: str = "",
    applicant_email: str = "",
    applicant_phone: str = "",
) -> Document:
    """
    Save uploaded file locally (dev) and create DB record.
    In production, this uploads to S3.
    """
    extension_by_mime = {
        "application/pdf": ".pdf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
    }

    # Generate unique filename
    file_ext = os.path.splitext(original_filename)[1] or extension_by_mime.get(content_type, ".bin")
    document_id = str(uuid.uuid4())
    unique_filename = f"{document_id}{file_ext}"
    s3_key = f"documents/{unique_filename}"

    file_url = await upload_file(s3_key, file_content, content_type)

    if password and content_type == "application/pdf":
        await store_password(s3_key, password)

    # Filename inference is only a provisional hint; persist only explicit choices.
    doc_type = DocumentType.OTHER
    if document_type:
        try:
            doc_type = DocumentType(document_type)
        except Exception:
            doc_type = DocumentType.OTHER

    resolved_case_id = case_id.strip() if case_id and case_id.strip() else None
    uploaded_to_existing_case = bool(resolved_case_id)
    created_new_case = False
    if not resolved_case_id:
        draft_case = await create_case(
            db=db,
            case_id=document_id,
            user_id=user_id,
            org_id=org_id,
            name=original_filename,
            status=CaseStatus.DRAFT.value,
            applicant_name=applicant_name,
            applicant_email=applicant_email,
            applicant_phone=applicant_phone,
        )
        resolved_case_id = draft_case.id
        created_new_case = True

    # Create DB record using Prisma
    document = await db.document.create(
        data={
            "id": document_id,
            "filename": unique_filename,
            "original_filename": original_filename,
            "file_url": file_url,
            "file_type": content_type,
            "file_size_bytes": len(file_content),
            "document_type": doc_type.value,
            "status": DocumentStatus.PENDING.value,
            "case_id": resolved_case_id,
            "user_id": user_id,
            "org_id": org_id,
        }
    )
    if created_new_case:
        await db.case.update(
            where={"id": resolved_case_id},
            data={"legacy_source_document_id": document_id},
        )
    elif uploaded_to_existing_case:
        await invalidate_final_case_analysis_for_case(
            db=db,
            case_id=resolved_case_id,
            org_id=org_id,
        )

    return document


async def get_documents(db: Prisma, org_id: str, skip: int = 0, limit: int = 50) -> list[Document]:
    """Get all documents for an organization."""
    return await db.document.find_many(
        where={"org_id": org_id},
        order={"created_at": "desc"},
        skip=skip,
        take=limit,
        include={
            "analyses": {
                "take": 1,
                "order_by": {"created_at": "desc"}
            }
        }
    )


async def get_document_by_id(db: Prisma, document_id: str) -> Document | None:
    """Get a single document by ID."""
    return await db.document.find_unique(where={"id": document_id})


async def get_document_by_id_for_org(db: Prisma, document_id: str, org_id: str) -> Document | None:
    """Get a single document by ID, scoped to the caller's organization."""
    return await db.document.find_first(
        where={
            "id": document_id,
            "org_id": org_id,
        }
    )
