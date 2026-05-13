"""
Ask AI route — Conversational Q&A about analyzed documents.

POST /api/v1/ask/{document_id}
Body: { "question": "Explain clause 7" }
Response: { "answer": "...", "sources": [...] }
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from prisma import Prisma
from core.database import get_db
from core.security import AuthenticatedContext, get_auth_context, require_mutation_role
from services.audit_service import ACTION_DOCUMENT_ASKED, record_audit_event
from services.gemini_service import ask_about_document
from services.document_service import get_document_by_id_for_org
from models import DocumentStatus
from schemas.ask import AskRequest, AskResponse, AskSource

router = APIRouter(prefix="/ask", tags=["Ask AI"])
logger = logging.getLogger("loanlens.ask")


@router.post("/{document_id}", response_model=AskResponse)
async def ask_about_loan(
    document_id: str,
    request: AskRequest,
    http_request: Request,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    """Ask a question about an analyzed loan document."""
    require_mutation_role(auth_context)

    # Verify document exists and is analyzed
    document = await get_document_by_id_for_org(
        db=db,
        document_id=document_id,
        org_id=auth_context.org_id,
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status != DocumentStatus.ANALYZED.value:
        raise HTTPException(
            status_code=400,
            detail="Document must be analyzed before you can ask questions about it.",
        )

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Use Gemini RAG to answer the question
    try:
        result = await ask_about_document(
            document_id=document_id,
            question=request.question.strip(),
        )
    except Exception:
        logger.exception("Ask AI failed unexpectedly for document_id=%s", document_id)
        return AskResponse(
            answer=(
                "Ask AI is temporarily unavailable for this document right now. "
                "Please try again shortly or review the saved analysis summary."
            ),
            sources=[],
        )

    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_DOCUMENT_ASKED,
        resource_type="document",
        resource_id=document_id,
        metadata={"question_length": len(request.question.strip())},
        request=http_request,
        required=True,
    )
    return AskResponse(
        answer=result["answer"],
        sources=[AskSource(**s) for s in result.get("sources", [])],
    )
