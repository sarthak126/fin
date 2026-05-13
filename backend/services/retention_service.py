"""
Retention and deletion helpers for sensitive case/document data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from prisma import Prisma

from core.config import Settings, get_settings
from services.job_queue_service import delete_analysis_job
from services.storage_service import (
    delete_extraction_artifact_for_file,
    delete_file,
    delete_password_for_file,
)
from services.vector_service import delete_document_vectors


@dataclass(frozen=True)
class RetentionCleanupSummary:
    case_cutoff: datetime | None
    document_cutoff: datetime | None
    audit_log_cutoff: datetime | None
    cases_deleted: int
    documents_deleted: int
    audit_logs_deleted: int

    def model_dump(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("case_cutoff", "document_cutoff", "audit_log_cutoff"):
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return data


def _field(record: Any, name: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(name, default)
    return getattr(record, name, default)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _cutoff(now: datetime, days: int) -> datetime | None:
    if days <= 0:
        return None
    return now - timedelta(days=days)


def _delete_many_count(result: Any) -> int:
    if result is None:
        return 0
    if isinstance(result, int):
        return result
    return int(getattr(result, "count", 0) or 0)


def _batch_size(settings: Settings) -> int:
    return max(1, int(settings.RETENTION_BATCH_SIZE))


async def _delete_external_document_artifacts(document: Any) -> None:
    document_id = str(_field(document, "id", ""))
    file_url = _field(document, "file_url")

    await delete_password_for_file(file_url)
    await delete_extraction_artifact_for_file(file_url)
    await delete_file(file_url)

    if document_id:
        delete_document_vectors(document_id)
        await delete_analysis_job(document_id)


async def _delete_document_record(
    db: Prisma,
    document: Any,
    *,
    clear_legacy_source: bool,
) -> None:
    document_id = str(_field(document, "id", ""))
    if not document_id:
        return

    if clear_legacy_source:
        await db.case.update_many(
            where={"legacy_source_document_id": document_id},
            data={"legacy_source_document_id": None},
        )

    await _delete_external_document_artifacts(document)
    await db.analysis.delete_many(where={"document_id": document_id})
    await db.document.delete(where={"id": document_id})


async def delete_document_for_org(db: Prisma, document_id: str, org_id: str) -> bool:
    """Delete one org-scoped document and all obvious derived artifacts."""
    document = await db.document.find_first(
        where={
            "id": document_id,
            "org_id": org_id,
        }
    )
    if not document:
        return False

    await _delete_document_record(db, document, clear_legacy_source=True)

    case_id = _field(document, "case_id")
    if case_id:
        await db.caseanalysis.delete_many(where={"case_id": case_id, "is_final": True})

    return True


async def delete_case_for_org(db: Prisma, case_id: str, org_id: str) -> bool:
    """Delete an org-scoped case, its documents, analyses, and artifacts."""
    normalized_case_id = (case_id or "").strip()
    if not normalized_case_id:
        return False

    case_record = await db.case.find_first(
        where={
            "org_id": org_id,
            "OR": [
                {"id": normalized_case_id},
                {"legacy_source_document_id": normalized_case_id},
            ],
        }
    )
    if not case_record:
        return False

    resolved_case_id = str(_field(case_record, "id"))
    legacy_document_id = _field(case_record, "legacy_source_document_id")
    document_filters: list[dict[str, str]] = [{"case_id": resolved_case_id}]
    if legacy_document_id:
        document_filters.append({"id": str(legacy_document_id)})

    documents = await db.document.find_many(
        where={
            "org_id": org_id,
            "OR": document_filters,
        }
    )

    await db.case.update(
        where={"id": resolved_case_id},
        data={"legacy_source_document_id": None},
    )
    await db.caseanalysis.delete_many(where={"case_id": resolved_case_id})

    seen_document_ids: set[str] = set()
    for document in documents:
        current_document_id = str(_field(document, "id", ""))
        if not current_document_id or current_document_id in seen_document_ids:
            continue
        seen_document_ids.add(current_document_id)
        await _delete_document_record(db, document, clear_legacy_source=False)

    await db.case.delete(where={"id": resolved_case_id})
    return True


async def delete_expired_cases(
    db: Prisma,
    *,
    cutoff: datetime,
    limit: int,
) -> int:
    """Delete the oldest cases that have exceeded the configured retention window."""
    cases = await db.case.find_many(
        where={"updated_at": {"lt": cutoff}},
        order={"updated_at": "asc"},
        take=limit,
    )

    deleted_count = 0
    for case_record in cases:
        case_id = str(_field(case_record, "id", ""))
        org_id = str(_field(case_record, "org_id", ""))
        if not case_id or not org_id:
            continue
        if await delete_case_for_org(db, case_id, org_id):
            deleted_count += 1
    return deleted_count


async def delete_expired_documents(
    db: Prisma,
    *,
    cutoff: datetime,
    limit: int,
) -> int:
    """Delete the oldest documents that have exceeded the configured retention window."""
    documents = await db.document.find_many(
        where={"created_at": {"lt": cutoff}},
        order={"created_at": "asc"},
        take=limit,
    )

    deleted_count = 0
    for document in documents:
        document_id = str(_field(document, "id", ""))
        org_id = str(_field(document, "org_id", ""))
        if not document_id or not org_id:
            continue
        if await delete_document_for_org(db, document_id, org_id):
            deleted_count += 1
    return deleted_count


async def delete_expired_audit_logs(
    db: Prisma,
    *,
    cutoff: datetime,
) -> int:
    """Delete old audit logs after their longer compliance retention window."""
    result = await db.auditlog.delete_many(where={"created_at": {"lt": cutoff}})
    return _delete_many_count(result)


async def enforce_retention_policy(
    db: Prisma,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> RetentionCleanupSummary:
    """Apply configured retention windows for cases, documents, and audit logs."""
    settings = settings or get_settings()
    now = now or _utc_now()
    limit = _batch_size(settings)

    case_cutoff = _cutoff(now, settings.RETENTION_CASE_DAYS)
    document_cutoff = _cutoff(now, settings.RETENTION_DOCUMENT_DAYS)
    audit_log_cutoff = _cutoff(now, settings.RETENTION_AUDIT_LOG_DAYS)

    cases_deleted = 0
    documents_deleted = 0
    audit_logs_deleted = 0

    if case_cutoff is not None:
        cases_deleted = await delete_expired_cases(db, cutoff=case_cutoff, limit=limit)

    if document_cutoff is not None:
        documents_deleted = await delete_expired_documents(
            db,
            cutoff=document_cutoff,
            limit=limit,
        )

    if audit_log_cutoff is not None:
        audit_logs_deleted = await delete_expired_audit_logs(db, cutoff=audit_log_cutoff)

    return RetentionCleanupSummary(
        case_cutoff=case_cutoff,
        document_cutoff=document_cutoff,
        audit_log_cutoff=audit_log_cutoff,
        cases_deleted=cases_deleted,
        documents_deleted=documents_deleted,
        audit_logs_deleted=audit_logs_deleted,
    )
