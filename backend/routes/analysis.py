"""
Analysis API routes — trigger AI analysis and retrieve results.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from prisma import Prisma

from core.database import get_db
from core.security import AuthenticatedContext, get_auth_context, require_mutation_role
from models import DocumentStatus
from schemas.analysis import AnalysisJobStatusResponse, AnalysisResponse, AnalysisTriggerResponse
from services.audit_service import (
    ACTION_ANALYSIS_VIEWED,
    ACTION_DOCUMENT_ANALYSIS_QUEUED,
    ACTION_DOCUMENT_ANALYSIS_REUSED,
    ACTION_DOCUMENT_REANALYSIS_QUEUED,
    record_audit_event,
)
from services.analysis_read_service import format_analysis_response_payload
from services.analysis_service import get_analysis_by_document, get_analysis_by_id
from services.document_service import get_document_by_id_for_org
from services.job_queue_service import enqueue_analysis_job, get_analysis_job

router = APIRouter(prefix="/analysis", tags=["Analysis"])


async def _queue_document_analysis(
    document_id: str,
    *,
    force_reanalysis: bool,
    request: Request | None = None,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    require_mutation_role(auth_context)
    document = await get_document_by_id_for_org(
        db=db,
        document_id=document_id,
        org_id=auth_context.org_id,
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status == DocumentStatus.PROCESSING.value:
        raise HTTPException(status_code=409, detail="Document is already being processed")

    if document.status == DocumentStatus.ANALYZED.value and not force_reanalysis:
        existing = await get_analysis_by_document(db=db, document_id=document_id)
        if existing:
            await record_audit_event(
                db=db,
                auth_context=auth_context,
                action=ACTION_DOCUMENT_ANALYSIS_REUSED,
                resource_type="analysis",
                resource_id=existing.id,
                metadata={"document_id": document_id, "force_reanalysis": False},
                request=request,
                required=True,
            )
            return AnalysisTriggerResponse(
                message="Document already analyzed.",
                analysis_id=existing.id,
                document_id=document_id,
                status="already_analyzed",
            )

    await db.document.update(
        where={"id": document_id},
        data={"status": DocumentStatus.PROCESSING.value}
    )
    try:
        await enqueue_analysis_job(
            document_id,
            force_reanalysis=force_reanalysis,
        )
    except Exception as exc:
        await db.document.update(
            where={"id": document_id},
            data={"status": document.status}
        )
        raise HTTPException(status_code=500, detail=f"Failed to queue analysis job: {exc}")

    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_DOCUMENT_REANALYSIS_QUEUED if force_reanalysis else ACTION_DOCUMENT_ANALYSIS_QUEUED,
        resource_type="document",
        resource_id=document_id,
        metadata={
            "force_reanalysis": force_reanalysis,
            "previous_status": document.status,
        },
        request=request,
        required=True,
    )

    return AnalysisTriggerResponse(
        message="Forced reanalysis queued." if force_reanalysis else "Analysis queued",
        analysis_id=None,
        document_id=document_id,
        status="queued",
    )


@router.post("/documents/{document_id}/analyze", response_model=AnalysisTriggerResponse, status_code=202)
async def analyze_document(
    document_id: str,
    request: Request,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    return await _queue_document_analysis(
        document_id=document_id,
        force_reanalysis=False,
        request=request,
        db=db,
        auth_context=auth_context,
    )


@router.post("/documents/{document_id}/reanalyze", response_model=AnalysisTriggerResponse, status_code=202)
async def reanalyze_document(
    document_id: str,
    request: Request,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    return await _queue_document_analysis(
        document_id=document_id,
        force_reanalysis=True,
        request=request,
        db=db,
        auth_context=auth_context,
    )


@router.get("/documents/{document_id}/job", response_model=AnalysisJobStatusResponse)
async def get_analysis_job_status(
    document_id: str,
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

    job = await get_analysis_job(document_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return job


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: str,
    request: Request,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    analysis = await get_analysis_by_id(db=db, analysis_id=analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    document = await get_document_by_id_for_org(
        db=db,
        document_id=analysis.document_id,
        org_id=auth_context.org_id,
    )
    if not document:
        raise HTTPException(status_code=404, detail="Analysis not found")

    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_ANALYSIS_VIEWED,
        resource_type="analysis",
        resource_id=analysis_id,
        metadata={"document_id": analysis.document_id},
        request=request,
    )
    return format_analysis_response_payload(analysis)


@router.get("/documents/{document_id}/latest", response_model=AnalysisResponse)
async def get_latest_analysis_for_document(
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

    analysis = await get_analysis_by_document(db=db, document_id=document_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found")
    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_ANALYSIS_VIEWED,
        resource_type="analysis",
        resource_id=analysis.id,
        metadata={"document_id": document_id, "view": "latest_for_document"},
        request=request,
    )
    return format_analysis_response_payload(analysis)
