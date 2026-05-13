"""
Audit log helpers for sensitive user actions.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import HTTPException, Request
from prisma import Prisma

from core.security import AuthenticatedContext

logger = logging.getLogger("loanlens.audit")

ACTION_CASE_ASKED = "case.asked"
ACTION_CASE_CREATED = "case.created"
ACTION_CASE_DELETED = "case.deleted"
ACTION_CASE_FINALIZED = "case.finalized"
ACTION_CASE_REPORT_EXPORTED = "case.report_exported"
ACTION_CASE_UPDATED = "case.updated"
ACTION_CASE_VIEWED = "case.viewed"
ACTION_DOCUMENT_ANALYSIS_REUSED = "document.analysis_reused"
ACTION_DOCUMENT_ANALYSIS_QUEUED = "document.analysis_queued"
ACTION_DOCUMENT_ASKED = "document.asked"
ACTION_DOCUMENT_DELETED = "document.deleted"
ACTION_DOCUMENT_REANALYSIS_QUEUED = "document.reanalysis_queued"
ACTION_DOCUMENT_UPLOADED = "document.uploaded"
ACTION_DOCUMENT_VIEWED = "document.viewed"
ACTION_ANALYSIS_VIEWED = "analysis.viewed"


class AuditLogUnavailableException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=503,
            detail="Audit logging is temporarily unavailable. Please try again shortly.",
        )


def request_ip_address(request: Request | None) -> str | None:
    if request is None:
        return None

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or None

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip() or None

    client = getattr(request, "client", None)
    return getattr(client, "host", None)


def _metadata_json(auth_context: AuthenticatedContext, metadata: dict[str, Any] | None) -> str:
    payload = {key: value for key, value in (metadata or {}).items() if value is not None}
    payload["org_id"] = auth_context.org_id
    payload["user_role"] = auth_context.role
    return json.dumps(payload, default=str, sort_keys=True)


async def record_audit_event(
    *,
    db: Prisma,
    auth_context: AuthenticatedContext,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
    required: bool = False,
) -> None:
    try:
        await db.auditlog.create(
            data={
                "user_id": auth_context.user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "metadata_json": _metadata_json(auth_context, metadata),
                "ip_address": request_ip_address(request),
            }
        )
    except Exception as exc:
        logger.exception(
            "Failed to write audit event action=%s resource_type=%s resource_id=%s",
            action,
            resource_type,
            resource_id,
        )
        if required:
            raise AuditLogUnavailableException() from exc
