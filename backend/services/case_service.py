"""
Case service - business logic for case CRUD primitives.
"""

from __future__ import annotations

import uuid

from prisma import Prisma
from prisma.models import Case

from models import CaseStatus

_UNSET = object()


def _normalized_optional(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _default_case_name(name: str | None, applicant_name: str | None) -> str | None:
    normalized_name = _normalized_optional(name)
    if normalized_name:
        return normalized_name

    normalized_applicant_name = _normalized_optional(applicant_name)
    if normalized_applicant_name:
        return normalized_applicant_name

    return None


async def create_case(
    db: Prisma,
    user_id: str,
    org_id: str,
    *,
    case_id: str | None = None,
    name: str | None = None,
    status: str = CaseStatus.DRAFT.value,
    applicant_name: str | None = None,
    applicant_email: str | None = None,
    applicant_phone: str | None = None,
    legacy_source_document_id: str | None = None,
) -> Case:
    """Create a new org-scoped case owned by the authenticated user."""
    return await db.case.create(
        data={
            "id": case_id or str(uuid.uuid4()),
            "name": _default_case_name(name, applicant_name),
            "status": status,
            "applicant_name": _normalized_optional(applicant_name),
            "applicant_email": _normalized_optional(applicant_email),
            "applicant_phone": _normalized_optional(applicant_phone),
            "legacy_source_document_id": legacy_source_document_id,
            "user_id": user_id,
            "org_id": org_id,
        }
    )


async def list_cases(
    db: Prisma,
    org_id: str,
    *,
    skip: int = 0,
    limit: int = 50,
) -> list[Case]:
    """List cases for an organization with newest-first ordering."""
    return await db.case.find_many(
        where={"org_id": org_id},
        order={"created_at": "desc"},
        skip=skip,
        take=limit,
    )


async def get_case_summary(
    db: Prisma,
    org_id: str,
    *,
    recent_limit: int = 4,
) -> tuple[int, dict[str, int], list[Case]]:
    """Aggregate org-scoped case counts grouped by status plus the most recent cases."""
    total = await db.case.count(where={"org_id": org_id})
    by_status: dict[str, int] = {}
    for status in CaseStatus:
        by_status[status.value] = await db.case.count(
            where={"org_id": org_id, "status": status.value}
        )
    recent = await db.case.find_many(
        where={"org_id": org_id},
        order={"created_at": "desc"},
        take=recent_limit,
    )
    return total, by_status, recent


async def get_case_by_id_for_org(
    db: Prisma,
    case_id: str,
    org_id: str,
) -> Case | None:
    """Fetch a single case scoped to the caller's organization."""
    normalized_case_id = (case_id or "").strip()
    if not normalized_case_id:
        return None

    return await db.case.find_first(
        where={
            "org_id": org_id,
            "OR": [
                {"id": normalized_case_id},
                {"legacy_source_document_id": normalized_case_id},
            ],
        }
    )


async def update_case_applicant_info(
    db: Prisma,
    case_id: str,
    org_id: str,
    *,
    applicant_name: str | None | object = _UNSET,
    applicant_email: str | None | object = _UNSET,
    applicant_phone: str | None | object = _UNSET,
) -> Case | None:
    """Update applicant contact fields for an org-scoped case."""
    case_record = await get_case_by_id_for_org(db=db, case_id=case_id, org_id=org_id)
    if not case_record:
        return None

    update_data: dict[str, str | None] = {}
    normalized_name: str | None = None

    if applicant_name is not _UNSET:
        normalized_name = _normalized_optional(applicant_name)
        update_data["applicant_name"] = normalized_name

    if applicant_email is not _UNSET:
        update_data["applicant_email"] = _normalized_optional(applicant_email)

    if applicant_phone is not _UNSET:
        update_data["applicant_phone"] = _normalized_optional(applicant_phone)

    if not update_data:
        return case_record

    # If the case has no explicit display name yet, keep it aligned with the
    # applicant name so new cases remain readable in list views.
    if (
        applicant_name is not _UNSET
        and normalized_name
        and not _normalized_optional(getattr(case_record, "name", None))
    ):
        update_data["name"] = normalized_name

    return await db.case.update(
        where={"id": case_record.id},
        data=update_data,
    )
