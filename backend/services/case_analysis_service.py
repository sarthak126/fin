"""
Persistence helpers for derived case-analysis snapshots.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid
from typing import Any

from prisma import Prisma

from core.confidence import build_summary_from_decision, extract_canonical_decision
from models import CaseStatus, DocumentType
from schemas.case_read_model import CaseAnalysisSnapshot, CaseDocumentReadModel, CaseReadModel
from services.case_service import get_case_by_id_for_org

_SUPPORTED_DOCUMENT_TYPES = {
    DocumentType.BANK_STATEMENT,
    DocumentType.TAX_RETURN,
    DocumentType.SALARY_SLIP,
    DocumentType.EMPLOYMENT_LETTER,
    DocumentType.INCOME_PROOF,
    DocumentType.ID_DOCUMENT,
}


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


async def get_case_read_model(
    db: Prisma,
    *,
    case_id: str,
    org_id: str,
) -> CaseReadModel | None:
    from services.case_aggregation_service import get_case_read_model as load_case_read_model

    return await load_case_read_model(
        db=db,
        case_id=case_id,
        org_id=org_id,
    )


def is_supported_case_analysis_document_type(document_type: Any) -> bool:
    normalized = _enum_value(document_type)
    try:
        return DocumentType(normalized) in _SUPPORTED_DOCUMENT_TYPES
    except Exception:
        return False


def _build_document_snapshot(document: CaseDocumentReadModel) -> dict[str, Any]:
    latest_analysis = document.latest_analysis
    return {
        "id": document.id,
        "case_id": document.case_id,
        "document_type": _enum_value(document.document_type),
        "status": _enum_value(document.status),
        "original_filename": document.original_filename,
        "analysis_id": latest_analysis.id if latest_analysis else None,
        "decision_status": _enum_value(latest_analysis.decision_status) if latest_analysis else None,
        "recommendation": _enum_value(latest_analysis.recommendation) if latest_analysis else None,
        "risk_score": latest_analysis.risk_score if latest_analysis else None,
        "confidence": latest_analysis.confidence if latest_analysis else None,
    }


def _snapshot_created_at(read_model: CaseReadModel) -> datetime:
    timestamps: list[datetime] = [
        read_model.case.created_at,
        read_model.case.updated_at,
    ]
    for document in read_model.documents:
        timestamps.extend([document.created_at, document.updated_at])
        if document.latest_analysis is not None:
            timestamps.append(document.latest_analysis.created_at)
    return max(timestamps) if timestamps else datetime.now(timezone.utc)


def _build_case_snapshot_payload(
    read_model: CaseReadModel,
    *,
    is_final: bool,
    snapshot_kind: str,
    case_status: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    provisional = read_model.provisional_insights
    resolved_case_status = case_status or _enum_value(read_model.case.status)
    data_completeness = round(
        (
            float(read_model.applicant_intake.completeness)
            + float(read_model.supported_document_completeness.analyzed_score)
        )
        / 2.0,
        4,
    )
    risk_score = provisional.highest_risk_score
    if risk_score is None:
        risk_score = provisional.average_risk_score

    decision = extract_canonical_decision(
        {},
        fallback_status=_enum_value(provisional.decision_status),
        fallback_reason=provisional.summary,
        fallback_extraction_confidence=data_completeness,
        fallback_risk_confidence=data_completeness,
        fallback_data_completeness=data_completeness,
        fallback_required_followups=provisional.followups,
        fallback_analysis_limitations=provisional.blockers,
    )
    case_payload = read_model.case.model_dump(mode="json")
    case_payload["status"] = resolved_case_status

    aggregate_payload = {
        "snapshot_kind": snapshot_kind,
        "is_final": is_final,
        "case": case_payload,
        "documents": [_build_document_snapshot(document) for document in read_model.documents],
        "applicant_intake": read_model.applicant_intake.model_dump(mode="json"),
        "supported_document_completeness": read_model.supported_document_completeness.model_dump(mode="json"),
        "cross_document_comparisons": [
            comparison.model_dump(mode="json") for comparison in read_model.cross_document_comparisons
        ],
        "fraud_signals": [signal.model_dump(mode="json") for signal in read_model.fraud_signals],
        "provisional_insights": provisional.model_dump(mode="json"),
        "decision": decision,
    }
    record_payload = {
        "id": str(uuid.uuid4()),
        "case_id": read_model.case.id,
        "case_status": resolved_case_status,
        "is_final": is_final,
        "risk_score": risk_score,
        "confidence": decision["risk_confidence"],
        "recommendation": _enum_value(provisional.recommendation),
        "decision_status": decision["decision_status"],
        "decision_recommendation": decision["decision_recommendation"],
        "decision_reason": decision["decision_reason"],
        "extraction_confidence": decision["extraction_confidence"],
        "risk_confidence": decision["risk_confidence"],
        "data_completeness": decision["data_completeness"],
        "required_followups_json": json.dumps(decision["required_followups"]),
        "analysis_limitations_json": json.dumps(decision["analysis_limitations"]),
        "extracted_fields": json.dumps(aggregate_payload),
        "risk_alerts": json.dumps(
            [
                {
                    "key": signal.key,
                    "severity": signal.severity,
                    "message": signal.summary,
                }
                for signal in read_model.fraud_signals
            ]
        ),
        "summary": build_summary_from_decision(decision, provisional.summary),
        "model_used": "case-final-aggregate-v1" if is_final else "case-provisional-aggregate-v1",
        "raw_response": json.dumps(
            {
                "snapshot_kind": snapshot_kind,
                "decision": decision,
                "aggregate": aggregate_payload,
            }
        ),
    }
    return record_payload, aggregate_payload


def build_case_analysis_snapshot(
    read_model: CaseReadModel,
    *,
    is_final: bool,
    snapshot_kind: str,
    case_status: str | None = None,
    generated_from: str | None = None,
) -> CaseAnalysisSnapshot:
    record_payload, aggregate_payload = _build_case_snapshot_payload(
        read_model,
        is_final=is_final,
        snapshot_kind=snapshot_kind,
        case_status=case_status,
    )
    snapshot_payload = {
        **record_payload,
        "extracted_fields": aggregate_payload,
        "risk_alerts": json.loads(record_payload["risk_alerts"]),
        "raw_response": json.loads(record_payload["raw_response"]),
        "created_at": _snapshot_created_at(read_model),
    }
    if generated_from:
        snapshot_payload["raw_response"]["generated_from"] = generated_from
    return CaseAnalysisSnapshot.model_validate(snapshot_payload)


async def persist_provisional_case_analysis(
    db: Prisma,
    *,
    case_id: str,
    org_id: str,
):
    read_model = await get_case_read_model(
        db=db,
        case_id=case_id,
        org_id=org_id,
    )
    if not read_model:
        return None

    record_payload, _ = _build_case_snapshot_payload(
        read_model,
        is_final=False,
        snapshot_kind="case_provisional",
    )
    return await db.caseanalysis.create(data=record_payload)


async def persist_provisional_case_analysis_for_document(
    db: Prisma,
    *,
    document: Any,
):
    case_id = str(getattr(document, "case_id", "") or "").strip()
    org_id = str(getattr(document, "org_id", "") or "").strip()
    if not case_id or not org_id:
        return None
    if not is_supported_case_analysis_document_type(getattr(document, "document_type", None)):
        return None

    return await persist_provisional_case_analysis(
        db=db,
        case_id=case_id,
        org_id=org_id,
    )


async def prepare_case_for_forced_document_reanalysis(
    db: Prisma,
    *,
    document: Any,
):
    case_id = str(getattr(document, "case_id", "") or "").strip()
    org_id = str(getattr(document, "org_id", "") or "").strip()
    if not case_id or not org_id:
        return None
    if not is_supported_case_analysis_document_type(getattr(document, "document_type", None)):
        return None

    return await invalidate_final_case_analysis_for_case(
        db=db,
        case_id=case_id,
        org_id=org_id,
    )


async def _clear_final_case_snapshots(
    db: Prisma,
    *,
    case_id: str,
) -> int:
    final_snapshots = await db.caseanalysis.find_many(
        where={
            "case_id": case_id,
            "is_final": True,
        }
    )
    for snapshot in final_snapshots:
        await db.caseanalysis.update(
            where={"id": snapshot.id},
            data={"is_final": False},
        )
    return len(final_snapshots)


async def finalize_case_and_get_read_model(
    db: Prisma,
    *,
    case_id: str,
    org_id: str,
) -> CaseReadModel | None:
    case_record = await get_case_by_id_for_org(
        db=db,
        case_id=case_id,
        org_id=org_id,
    )
    if not case_record:
        return None
    resolved_case_id = case_record.id

    previous_status = _enum_value(getattr(case_record, "status", None)) or CaseStatus.DRAFT.value
    if previous_status != CaseStatus.FINALIZED.value:
        await db.case.update(
            where={"id": resolved_case_id},
            data={"status": CaseStatus.FINALIZED.value},
        )

    try:
        await _clear_final_case_snapshots(db=db, case_id=resolved_case_id)
        read_model = await get_case_read_model(
            db=db,
            case_id=resolved_case_id,
            org_id=org_id,
        )
        if not read_model:
            return None

        record_payload, _ = _build_case_snapshot_payload(
            read_model,
            is_final=True,
            snapshot_kind="case_finalized",
            case_status=CaseStatus.FINALIZED.value,
        )
        await db.caseanalysis.create(data=record_payload)
    except Exception:
        if previous_status != CaseStatus.FINALIZED.value:
            await db.case.update(
                where={"id": resolved_case_id},
                data={"status": previous_status},
            )
        raise

    return await get_case_read_model(
        db=db,
        case_id=resolved_case_id,
        org_id=org_id,
    )


async def get_latest_case_analysis_for_org(
    db: Prisma,
    *,
    case_id: str,
    org_id: str,
) -> CaseAnalysisSnapshot | None:
    read_model = await get_case_read_model(
        db=db,
        case_id=case_id,
        org_id=org_id,
    )
    if not read_model:
        return None
    if read_model.authoritative_analysis is not None:
        return read_model.authoritative_analysis

    return build_case_analysis_snapshot(
        read_model,
        is_final=False,
        snapshot_kind="case_live_provisional",
        generated_from="live_provisional",
    )


async def invalidate_final_case_analysis_for_case(
    db: Prisma,
    *,
    case_id: str,
    org_id: str,
):
    case_record = await get_case_by_id_for_org(
        db=db,
        case_id=case_id,
        org_id=org_id,
    )
    if not case_record:
        return None
    resolved_case_id = case_record.id

    cleared_count = await _clear_final_case_snapshots(
        db=db,
        case_id=resolved_case_id,
    )
    if _enum_value(getattr(case_record, "status", None)) == CaseStatus.FINALIZED.value:
        return await db.case.update(
            where={"id": resolved_case_id},
            data={"status": CaseStatus.COLLECTING.value},
        )
    if cleared_count:
        return case_record
    return case_record


__all__ = [
    "build_case_analysis_snapshot",
    "finalize_case_and_get_read_model",
    "get_latest_case_analysis_for_org",
    "invalidate_final_case_analysis_for_case",
    "is_supported_case_analysis_document_type",
    "prepare_case_for_forced_document_reanalysis",
    "persist_provisional_case_analysis",
    "persist_provisional_case_analysis_for_document",
]
