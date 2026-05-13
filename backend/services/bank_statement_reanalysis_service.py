"""
Operational recovery helpers for bank-statement reanalysis backfills.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from prisma import Prisma

from models import DocumentStatus, DocumentType
from services.analysis_service import get_analysis_by_document, run_analysis_for_stored_document
from services.case_analysis_service import get_latest_case_analysis_for_org


def _normalized_unique(values: Sequence[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


async def _resolve_case_ids(
    db: Prisma,
    *,
    case_ids: Sequence[str] | None,
    org_ids: Sequence[str] | None,
) -> list[str] | None:
    normalized_case_ids = _normalized_unique(case_ids)
    if not normalized_case_ids:
        return None

    where: dict[str, Any] = {
        "OR": [
            {"id": {"in": normalized_case_ids}},
            {"legacy_source_document_id": {"in": normalized_case_ids}},
        ]
    }
    normalized_org_ids = _normalized_unique(org_ids)
    if normalized_org_ids:
        where["org_id"] = {"in": normalized_org_ids}

    cases = await db.case.find_many(where=where)
    resolved_case_ids: list[str] = []
    seen: set[str] = set()
    for case_record in cases:
        case_id = str(getattr(case_record, "id", "") or "").strip()
        if not case_id or case_id in seen:
            continue
        seen.add(case_id)
        resolved_case_ids.append(case_id)
    return resolved_case_ids


async def select_bank_statement_documents(
    db: Prisma,
    *,
    document_ids: Sequence[str] | None = None,
    case_ids: Sequence[str] | None = None,
    org_ids: Sequence[str] | None = None,
    limit: int | None = None,
    include_processing: bool = False,
) -> list[Any]:
    normalized_document_ids = _normalized_unique(document_ids)
    normalized_org_ids = _normalized_unique(org_ids)
    resolved_case_ids = await _resolve_case_ids(
        db=db,
        case_ids=case_ids,
        org_ids=normalized_org_ids,
    )
    if case_ids and resolved_case_ids == []:
        return []

    where: dict[str, Any] = {"document_type": DocumentType.BANK_STATEMENT.value}
    if normalized_document_ids:
        where["id"] = {"in": normalized_document_ids}
    if normalized_org_ids:
        where["org_id"] = {"in": normalized_org_ids}
    if resolved_case_ids is not None:
        where["case_id"] = {"in": resolved_case_ids}

    documents = await db.document.find_many(
        where=where,
        order={"created_at": "asc"},
    )
    filtered_documents = [
        document
        for document in documents
        if include_processing or getattr(document, "status", None) != DocumentStatus.PROCESSING.value
    ]
    if limit is not None and limit > 0:
        return filtered_documents[:limit]
    return filtered_documents


@dataclass(slots=True)
class BankStatementReanalysisResult:
    document_id: str
    case_id: str | None
    org_id: str | None
    previous_analysis_id: str | None
    previous_risk_score: float | None
    new_analysis_id: str | None
    new_risk_score: float | None
    case_latest_analysis_id: str | None
    case_latest_risk_score: float | None
    case_latest_is_final: bool | None
    worker_result: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


async def rerun_bank_statement_documents(
    db: Prisma,
    *,
    documents: Sequence[Any],
) -> list[BankStatementReanalysisResult]:
    results: list[BankStatementReanalysisResult] = []

    for document in documents:
        document_id = str(getattr(document, "id", "") or "").strip()
        if not document_id:
            continue

        previous_analysis = await get_analysis_by_document(db=db, document_id=document_id)
        worker_result = await run_analysis_for_stored_document(
            db=db,
            document_id=document_id,
            force_reanalysis=True,
        )
        latest_analysis = await get_analysis_by_document(db=db, document_id=document_id)
        if latest_analysis is None:
            raise RuntimeError(f"Reanalysis completed without a persisted analysis row for document {document_id}.")
        if previous_analysis is not None and latest_analysis.id == previous_analysis.id:
            raise RuntimeError(f"Forced reanalysis did not create a fresh analysis row for document {document_id}.")

        case_id = str(getattr(document, "case_id", "") or "").strip() or None
        org_id = str(getattr(document, "org_id", "") or "").strip() or None
        case_latest_analysis = None
        if case_id and org_id:
            case_latest_analysis = await get_latest_case_analysis_for_org(
                db=db,
                case_id=case_id,
                org_id=org_id,
            )

        results.append(
            BankStatementReanalysisResult(
                document_id=document_id,
                case_id=case_id,
                org_id=org_id,
                previous_analysis_id=getattr(previous_analysis, "id", None),
                previous_risk_score=getattr(previous_analysis, "risk_score", None),
                new_analysis_id=getattr(latest_analysis, "id", None),
                new_risk_score=getattr(latest_analysis, "risk_score", None),
                case_latest_analysis_id=getattr(case_latest_analysis, "id", None),
                case_latest_risk_score=getattr(case_latest_analysis, "risk_score", None),
                case_latest_is_final=getattr(case_latest_analysis, "is_final", None),
                worker_result=worker_result,
            )
        )

    return results


__all__ = [
    "BankStatementReanalysisResult",
    "rerun_bank_statement_documents",
    "select_bank_statement_documents",
]
