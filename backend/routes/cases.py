"""
Case API routes - create, list, retrieve, and update applicant info.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from core.database import get_db
from core.security import AuthenticatedContext, get_auth_context, require_mutation_role
from models import CaseStatus
from prisma import Prisma
from schemas.ask import AskRequest, AskResponse
from schemas.case import (
    CaseApplicantInfoUpdateRequest,
    CaseCreateRequest,
    CaseDetail,
    CaseListItem,
    CaseStatusCount,
    CaseSummaryResponse,
)
from schemas.case_read_model import CaseAnalysisSnapshot, CaseReadModel
from schemas.case_report import CaseReportPayload
from services.audit_service import (
    ACTION_CASE_ASKED,
    ACTION_CASE_CREATED,
    ACTION_CASE_DELETED,
    ACTION_CASE_FINALIZED,
    ACTION_CASE_REPORT_EXPORTED,
    ACTION_CASE_UPDATED,
    ACTION_CASE_VIEWED,
    ACTION_ANALYSIS_VIEWED,
    record_audit_event,
)
from services.case_aggregation_service import get_case_read_model
from services.case_analysis_service import (
    finalize_case_and_get_read_model,
    get_latest_case_analysis_for_org,
)
from services.case_ask_service import ask_about_case
from services.case_report_service import get_case_report
from services.case_service import (
    create_case,
    get_case_by_id_for_org,
    get_case_summary,
    list_cases,
    update_case_applicant_info,
)
from services.retention_service import delete_case_for_org

router = APIRouter(prefix="/cases", tags=["Cases"])
logger = logging.getLogger("loanlens.case_routes")


@router.post("", response_model=CaseDetail, status_code=201)
async def create_case_route(
    payload: CaseCreateRequest,
    request: Request,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    require_mutation_role(auth_context)
    case_record = await create_case(
        db=db,
        user_id=auth_context.user_id,
        org_id=auth_context.org_id,
        name=payload.name,
        status=payload.status.value,
        applicant_name=payload.applicant_name,
        applicant_email=payload.applicant_email,
        applicant_phone=payload.applicant_phone,
    )
    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_CASE_CREATED,
        resource_type="case",
        resource_id=case_record.id,
        metadata={"case_status": case_record.status},
        request=request,
        required=True,
    )
    return case_record


@router.get("", response_model=list[CaseListItem])
async def list_cases_route(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    return await list_cases(
        db=db,
        org_id=auth_context.org_id,
        skip=skip,
        limit=limit,
    )


@router.get("/summary", response_model=CaseSummaryResponse)
async def get_case_summary_route(
    recent_limit: int = Query(4, ge=1, le=20),
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    """Aggregated case counts and recent cases for the Command Center."""
    total, by_status_map, recent = await get_case_summary(
        db=db,
        org_id=auth_context.org_id,
        recent_limit=recent_limit,
    )
    return CaseSummaryResponse(
        total_count=total,
        by_status=[
            CaseStatusCount(status=CaseStatus(status_value), count=count)
            for status_value, count in by_status_map.items()
        ],
        recent_cases=recent,
    )


@router.get("/{case_id}/read-model", response_model=CaseReadModel)
async def get_case_read_model_route(
    case_id: str,
    request: Request,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    read_model = await get_case_read_model(
        db=db,
        case_id=case_id,
        org_id=auth_context.org_id,
    )
    if not read_model:
        raise HTTPException(status_code=404, detail="Case not found")

    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_CASE_VIEWED,
        resource_type="case",
        resource_id=case_id,
        metadata={"view": "read_model"},
        request=request,
    )
    return read_model


@router.get("/{case_id}/analysis/latest", response_model=CaseAnalysisSnapshot)
async def get_latest_case_analysis_route(
    case_id: str,
    request: Request,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    analysis = await get_latest_case_analysis_for_org(
        db=db,
        case_id=case_id,
        org_id=auth_context.org_id,
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Case not found")

    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_ANALYSIS_VIEWED,
        resource_type="case_analysis",
        resource_id=analysis.get("id") if isinstance(analysis, dict) else getattr(analysis, "id", None),
        metadata={"case_id": case_id, "view": "latest_for_case"},
        request=request,
    )
    return analysis


@router.post("/{case_id}/ask", response_model=AskResponse)
async def ask_about_case_route(
    case_id: str,
    payload: AskRequest,
    request: Request,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    require_mutation_role(auth_context)
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = await ask_about_case(
            db=db,
            case_id=case_id,
            org_id=auth_context.org_id,
            question=payload.question.strip(),
        )
    except Exception:
        logger.exception("Case Ask AI failed unexpectedly for case_id=%s", case_id)
        return AskResponse(
            answer=(
                "Ask AI is temporarily unavailable for this case right now. "
                "Please try again shortly or review the saved case report."
            ),
            sources=[],
        )

    if not result:
        raise HTTPException(status_code=404, detail="Case not found")
    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_CASE_ASKED,
        resource_type="case",
        resource_id=case_id,
        metadata={"question_length": len(payload.question.strip())},
        request=request,
        required=True,
    )
    return result


@router.get("/{case_id}/report", response_model=CaseReportPayload)
async def get_case_report_route(
    case_id: str,
    request: Request,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    require_mutation_role(auth_context)
    report = await get_case_report(
        db=db,
        case_id=case_id,
        org_id=auth_context.org_id,
    )
    if not report:
        raise HTTPException(status_code=404, detail="Case not found")

    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_CASE_REPORT_EXPORTED,
        resource_type="case",
        resource_id=case_id,
        metadata={
            "report_status": report.get("header", {}).get("report_status")
            if isinstance(report, dict)
            else None
        },
        request=request,
        required=True,
    )
    return report


@router.get("/{case_id}", response_model=CaseDetail)
async def get_case_route(
    case_id: str,
    request: Request,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    case_record = await get_case_by_id_for_org(
        db=db,
        case_id=case_id,
        org_id=auth_context.org_id,
    )
    if not case_record:
        raise HTTPException(status_code=404, detail="Case not found")

    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_CASE_VIEWED,
        resource_type="case",
        resource_id=case_record.id,
        metadata={"case_status": case_record.status},
        request=request,
    )
    return case_record


@router.post("/{case_id}/finalize", response_model=CaseReadModel)
async def finalize_case_route(
    case_id: str,
    request: Request,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    require_mutation_role(auth_context)
    read_model = await finalize_case_and_get_read_model(
        db=db,
        case_id=case_id,
        org_id=auth_context.org_id,
    )
    if not read_model:
        raise HTTPException(status_code=404, detail="Case not found")

    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_CASE_FINALIZED,
        resource_type="case",
        resource_id=case_id,
        metadata={"case_status": "finalized"},
        request=request,
        required=True,
    )
    return read_model


@router.patch("/{case_id}", response_model=CaseDetail)
async def update_case_applicant_info_route(
    case_id: str,
    request: Request,
    payload: CaseApplicantInfoUpdateRequest,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    require_mutation_role(auth_context)
    raw_payload = await request.json()
    update_payload = {
        field_name: getattr(payload, field_name)
        for field_name in ("applicant_name", "applicant_email", "applicant_phone")
        if field_name in raw_payload
    }
    case_record = await update_case_applicant_info(
        db=db,
        case_id=case_id,
        org_id=auth_context.org_id,
        **update_payload,
    )
    if not case_record:
        raise HTTPException(status_code=404, detail="Case not found")

    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_CASE_UPDATED,
        resource_type="case",
        resource_id=case_record.id,
        metadata={"updated_fields": sorted(update_payload.keys())},
        request=request,
        required=True,
    )
    return case_record


@router.delete("/{case_id}", status_code=204)
async def delete_case_route(
    case_id: str,
    request: Request,
    db: Prisma = Depends(get_db),
    auth_context: AuthenticatedContext = Depends(get_auth_context),
):
    require_mutation_role(auth_context)
    deleted = await delete_case_for_org(
        db=db,
        case_id=case_id,
        org_id=auth_context.org_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Case not found")
    await record_audit_event(
        db=db,
        auth_context=auth_context,
        action=ACTION_CASE_DELETED,
        resource_type="case",
        resource_id=case_id,
        request=request,
        required=True,
    )
    return None
