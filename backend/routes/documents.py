"""
Document API routes — upload, list, and retrieve loan documents.
"""
import fitz
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, Request, Response
from core.database import get_db
from core.config import get_settings
from core.security import AuthenticatedContext, get_auth_context, require_mutation_role
from schemas.document import DocumentUploadResponse, DocumentListItem, DocumentDetail
from services.audit_service import (
    ACTION_DOCUMENT_DELETED,
    ACTION_DOCUMENT_UPLOADED,
    ACTION_DOCUMENT_VIEWED,
    record_audit_event,
)
from services.case_service import get_case_by_id_for_org
from services.document_service import create_document, get_documents, get_document_by_id_for_org
from services.retention_service import delete_document_for_org
from prisma import Prisma

router = APIRouter(prefix="/documents", tags=["Documents"])
settings = get_settings()
UPLOAD_READ_CHUNK_SIZE = 1024 * 1024
UNSUPPORTED_FILE_TYPE_DETAIL = "Unsupported file content. Upload a valid PDF, PNG, or JPEG file."


def _default_filename_for_content_type(content_type: str | None) -> str:
    return {
        "application/pdf": "unnamed.pdf",
        "image/png": "unnamed.png",
        "image/jpeg": "unnamed.jpg",
    }.get(content_type or "", "unnamed.bin")


def _sniff_content_type(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if _is_valid_pdf_content(content):
        return "application/pdf"
    return None


def _is_declared_pdf(file: UploadFile) -> bool:
    filename = (file.filename or "").strip().lower()
    content_type = (file.content_type or "").strip().lower()
    return filename.endswith(".pdf") or content_type == "application/pdf"


def _is_valid_pdf_content(content: bytes) -> bool:
    if b"%PDF-" in content:
        return True

    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception:
        return False

    try:
        return document.page_count >= 0
    finally:
        document.close()


async def _read_upload_with_limit(file: UploadFile, *, max_size_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total_size = 0

    while True:
        chunk = await file.read(UPLOAD_READ_CHUNK_SIZE)
        if not chunk:
            break

        total_size += len(chunk)
        if total_size > max_size_bytes:
            raise HTTPException(status_code=400, detail="File too large")

        chunks.append(chunk)

    return b"".join(chunks)


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    password: str = Form(""),
    document_type: str = Form(""),
    case_id: str = Form(""),
    applicant_name: str = Form(""),
    applicant_email: str = Form(""),
    applicant_phone: str = Form(""),
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    require_mutation_role(auth_context)
    content = await _read_upload_with_limit(
        file,
        max_size_bytes=settings.MAX_FILE_SIZE_MB * 1024 * 1024,
    )
    detected_content_type = _sniff_content_type(content)
    if not detected_content_type and settings.APP_ENV == "development" and _is_declared_pdf(file):
        detected_content_type = "application/pdf"
    if detected_content_type not in settings.ALLOWED_FILE_TYPES:
        raise HTTPException(status_code=400, detail=UNSUPPORTED_FILE_TYPE_DETAIL)

    normalized_case_id = case_id.strip()
    if normalized_case_id:
        case_record = await get_case_by_id_for_org(
            db=db,
            case_id=normalized_case_id,
            org_id=auth_context.org_id,
        )
        if not case_record:
            raise HTTPException(status_code=404, detail="Case not found")
        normalized_case_id = case_record.id

    document = await create_document(
        db=db,
        original_filename=file.filename or _default_filename_for_content_type(detected_content_type),
        file_content=content,
        user_id=auth_context.user_id,
        org_id=auth_context.org_id,
        content_type=detected_content_type or "application/pdf",
        password=password,
        document_type=document_type,
        case_id=normalized_case_id or None,
        applicant_name=applicant_name,
        applicant_email=applicant_email,
        applicant_phone=applicant_phone,
    )
    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_DOCUMENT_UPLOADED,
        resource_type="document",
        resource_id=document.id,
        metadata={
            "case_id": normalized_case_id or None,
            "document_type": document_type or None,
            "file_size_bytes": len(content),
            "file_type": detected_content_type,
        },
        request=request,
        required=True,
    )
    return document


@router.get("", response_model=list[DocumentListItem])
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    return await get_documents(db=db, org_id=auth_context.org_id, skip=skip, limit=limit)


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: str,
    request: Request,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    document = await get_document_by_id_for_org(
        db=db,
        document_id=document_id,
        org_id=auth_context.org_id,
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_DOCUMENT_VIEWED,
        resource_type="document",
        resource_id=document_id,
        metadata={"document_status": getattr(document, "status", None)},
        request=request,
    )
    return document


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    request: Request,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    require_mutation_role(auth_context)
    deleted = await delete_document_for_org(
        db=db,
        document_id=document_id,
        org_id=auth_context.org_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_DOCUMENT_DELETED,
        resource_type="document",
        resource_id=document_id,
        request=request,
        required=True,
    )
    return Response(status_code=204)
