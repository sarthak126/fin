from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.security import AuthenticatedContext
from services import audit_service


def _auth_context(role: str = "analyst") -> AuthenticatedContext:
    return AuthenticatedContext(
        user_id="user_test_123",
        org_id="org_test_456",
        email="analyst@example.com",
        name="Test Analyst",
        role=role,
        token_payload={"sub": "user_test_123", "org_id": "org_test_456"},
    )


@pytest.mark.asyncio
async def test_record_audit_event_persists_user_action_metadata_and_forwarded_ip():
    fake_db = SimpleNamespace(auditlog=SimpleNamespace(create=AsyncMock()))
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.10, 198.51.100.5"},
        client=SimpleNamespace(host="127.0.0.1"),
    )

    await audit_service.record_audit_event(
        db=fake_db,
        auth_context=_auth_context(),
        action=audit_service.ACTION_DOCUMENT_UPLOADED,
        resource_type="document",
        resource_id="doc_test_123",
        metadata={"file_type": "application/pdf", "password": None},
        request=request,
    )

    fake_db.auditlog.create.assert_awaited_once()
    data = fake_db.auditlog.create.await_args.kwargs["data"]
    assert data["user_id"] == "user_test_123"
    assert data["action"] == audit_service.ACTION_DOCUMENT_UPLOADED
    assert data["resource_type"] == "document"
    assert data["resource_id"] == "doc_test_123"
    assert data["ip_address"] == "203.0.113.10"

    metadata = json.loads(data["metadata_json"])
    assert metadata == {
        "file_type": "application/pdf",
        "org_id": "org_test_456",
        "user_role": "analyst",
    }


@pytest.mark.asyncio
async def test_record_audit_event_does_not_block_when_audit_write_fails():
    fake_db = SimpleNamespace(
        auditlog=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("audit offline")))
    )

    await audit_service.record_audit_event(
        db=fake_db,
        auth_context=_auth_context(),
        action=audit_service.ACTION_CASE_DELETED,
        resource_type="case",
        resource_id="case_test_123",
    )

    fake_db.auditlog.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_required_audit_event_raises_when_audit_write_fails():
    fake_db = SimpleNamespace(
        auditlog=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("audit offline")))
    )

    with pytest.raises(audit_service.AuditLogUnavailableException) as error:
        await audit_service.record_audit_event(
            db=fake_db,
            auth_context=_auth_context(),
            action=audit_service.ACTION_DOCUMENT_DELETED,
            resource_type="document",
            resource_id="doc_test_123",
            required=True,
        )

    assert error.value.status_code == 503
    assert error.value.detail == "Audit logging is temporarily unavailable. Please try again shortly."
