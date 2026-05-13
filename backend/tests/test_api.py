from __future__ import annotations

from datetime import datetime, timezone
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import main as main_module
from models import DocumentStatus, DocumentType
from core.security import AuthenticatedContext, get_auth_context, sync_auth_context
from routes import analysis as analysis_routes
from routes import ask as ask_routes
from routes import cases as case_routes
from routes import documents as document_routes
from services import audit_service
from services import bank_statement_pipeline as bank_statement_pipeline
from tests.sample_bank_statement_fixture import (
    load_short_history_sample_expected,
    load_short_history_sample_transactions,
)

MINIMAL_IMAGE_BYTES_BY_MIME = {
    "image/png": b"\x89PNG\r\n\x1a\nminimal-test-payload",
    "image/jpeg": b"\xff\xd8\xffminimal-test-payload",
}


def _timestamp() -> datetime:
    return datetime.now(timezone.utc)


def _make_document(**overrides):
    now = _timestamp()
    data = {
        "id": "doc_test_123",
        "filename": "stored-doc-test-123.pdf",
        "original_filename": "statement.pdf",
        "file_url": "s3://loanlens/documents/stored-doc-test-123.pdf",
        "file_type": "application/pdf",
        "document_type": DocumentType.BANK_STATEMENT,
        "status": DocumentStatus.PENDING,
        "file_size_bytes": 24,
        "created_at": now,
        "updated_at": now,
        "user_id": "user_test_123",
        "org_id": "org_test_456",
        "analyses": [],
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _make_case(**overrides):
    now = _timestamp()
    data = {
        "id": "case_test_123",
        "name": "Jane Doe",
        "status": "draft",
        "applicant_name": "Jane Doe",
        "applicant_email": "jane@example.com",
        "applicant_phone": "+1-555-0100",
        "legacy_source_document_id": None,
        "created_at": now,
        "updated_at": now,
        "user_id": "user_test_123",
        "org_id": "org_test_456",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class FakeAnalysisRecord:
    def __init__(self, **overrides):
        now = _timestamp()
        self._data = {
            "id": "analysis_123",
            "document_id": "doc_test_123",
            "risk_score": 42,
            "confidence": 0.91,
            "recommendation": "review",
            "extracted_fields": '{"score": 42}',
            "risk_alerts": '[{"severity": "medium", "message": "Review income volatility"}]',
            "summary": "Review recommended",
            "processing_time_seconds": 1.2,
            "model_used": "gemini-test",
            "raw_response": '{"decision": "review"}',
            "created_at": overrides.get("created_at", now),
        }
        self._data.update(overrides)
        self.id = self._data["id"]
        self.document_id = self._data["document_id"]
        self.created_at = self._data["created_at"]

    def model_dump(self) -> dict[str, object]:
        return dict(self._data)


def _auth_context_with_role(auth_context: AuthenticatedContext, role: str) -> AuthenticatedContext:
    return AuthenticatedContext(
        user_id=auth_context.user_id,
        org_id=auth_context.org_id,
        email=auth_context.email,
        name=auth_context.name,
        role=role,
        token_payload=auth_context.token_payload,
    )


def _override_auth_role(auth_context: AuthenticatedContext, role: str) -> None:
    async def override_get_auth_context():
        return _auth_context_with_role(auth_context, role)

    main_module.app.dependency_overrides[get_auth_context] = override_get_auth_context


def _latest_audit_data(fake_db) -> dict[str, object]:
    return fake_db.auditlog.create.await_args.kwargs["data"]


def _latest_audit_metadata(fake_db) -> dict[str, object]:
    return json.loads(str(_latest_audit_data(fake_db)["metadata_json"]))


async def test_document_upload_uses_authenticated_context(async_client, fake_db, auth_context, monkeypatch):
    created_document = _make_document()
    create_document_mock = AsyncMock(return_value=created_document)
    monkeypatch.setattr(document_routes, "create_document", create_document_mock)

    response = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("statement.pdf", b"%PDF-1.4 test payload", "application/pdf")},
        data={
            "password": "secret-pass",
            "document_type": "bank_statement",
            "applicant_name": "Jane Doe",
            "applicant_email": "jane@example.com",
            "applicant_phone": "+1-555-0100",
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == created_document.id
    assert response.json()["document_type"] == "bank_statement"
    assert response.json()["status"] == "pending"

    kwargs = create_document_mock.await_args.kwargs
    assert kwargs["original_filename"] == "statement.pdf"
    assert kwargs["file_content"] == b"%PDF-1.4 test payload"
    assert kwargs["password"] == "secret-pass"
    assert kwargs["document_type"] == "bank_statement"
    assert kwargs["applicant_name"] == "Jane Doe"
    assert kwargs["applicant_email"] == "jane@example.com"
    assert kwargs["applicant_phone"] == "+1-555-0100"
    assert kwargs["user_id"] == auth_context.user_id
    assert kwargs["org_id"] == auth_context.org_id

    audit_data = _latest_audit_data(fake_db)
    assert audit_data["action"] == audit_service.ACTION_DOCUMENT_UPLOADED
    assert audit_data["resource_type"] == "document"
    assert audit_data["resource_id"] == created_document.id
    assert audit_data["user_id"] == auth_context.user_id
    assert _latest_audit_metadata(fake_db)["org_id"] == auth_context.org_id


async def test_viewer_cannot_upload_document(async_client, fake_db, auth_context, monkeypatch):
    _override_auth_role(auth_context, "viewer")
    create_document_mock = AsyncMock()
    monkeypatch.setattr(document_routes, "create_document", create_document_mock)

    response = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("statement.pdf", b"%PDF-1.4 test payload", "application/pdf")},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "This action requires an admin or analyst role"}
    create_document_mock.assert_not_awaited()
    fake_db.auditlog.create.assert_not_awaited()


async def test_document_upload_returns_503_when_required_audit_fails(async_client, fake_db, monkeypatch):
    created_document = _make_document()
    create_document_mock = AsyncMock(return_value=created_document)
    monkeypatch.setattr(document_routes, "create_document", create_document_mock)
    fake_db.auditlog.create.side_effect = RuntimeError("audit offline")

    response = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("statement.pdf", b"%PDF-1.4 test payload", "application/pdf")},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Audit logging is temporarily unavailable. Please try again shortly."
    }
    create_document_mock.assert_awaited_once()


@pytest.mark.parametrize(
    ("filename", "mime_type"),
    [
        ("statement-scan.png", "image/png"),
        ("statement-scan.jpg", "image/jpeg"),
    ],
)
async def test_document_upload_accepts_supported_images(async_client, auth_context, monkeypatch, filename, mime_type):
    created_document = _make_document(filename=f"stored-{filename}", original_filename=filename, file_type=mime_type)
    create_document_mock = AsyncMock(return_value=created_document)
    monkeypatch.setattr(document_routes, "create_document", create_document_mock)

    response = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, MINIMAL_IMAGE_BYTES_BY_MIME[mime_type], mime_type)},
        data={"password": "ignored-for-images"},
    )

    assert response.status_code == 201
    kwargs = create_document_mock.await_args.kwargs
    assert kwargs["original_filename"] == filename
    assert kwargs["content_type"] == mime_type
    assert kwargs["password"] == "ignored-for-images"


async def test_document_upload_resolves_legacy_case_identifier_before_attach(async_client, fake_db, monkeypatch):
    created_document = _make_document(case_id="case_test_123")
    create_document_mock = AsyncMock(return_value=created_document)
    get_case_mock = AsyncMock(
        return_value=_make_case(
            id="case_test_123",
            legacy_source_document_id="legacy_doc_123",
        )
    )
    monkeypatch.setattr(document_routes, "create_document", create_document_mock)
    monkeypatch.setattr(document_routes, "get_case_by_id_for_org", get_case_mock)

    response = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("statement.pdf", b"%PDF-1.4 test payload", "application/pdf")},
        data={"case_id": "legacy_doc_123"},
    )

    assert response.status_code == 201
    get_case_mock.assert_awaited_once()
    assert create_document_mock.await_args.kwargs["case_id"] == "case_test_123"


async def test_auth_me_returns_persisted_role(async_client):
    auth_context = SimpleNamespace(
        user_id="user_admin_123",
        org_id="org_test_456",
        email="admin@example.com",
        name="Admin Analyst",
        role="admin",
    )

    async def override_sync_auth_context():
        return auth_context

    main_module.app.dependency_overrides[sync_auth_context] = override_sync_auth_context

    response = await async_client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": "user_admin_123",
        "email": "admin@example.com",
        "name": "Admin Analyst",
        "role": "admin",
        "org_id": "org_test_456",
    }


async def test_auth_signup_returns_clerk_managed_contract(async_client):
    response = await async_client.post("/api/v1/auth/signup")

    assert response.status_code == 501
    assert response.json() == {
        "status": "external_provider_required",
        "provider": "clerk",
        "action": "sign_up",
        "message": (
            "This backend does not accept direct credential submission because "
            "authentication is handled by Clerk on the frontend."
        ),
        "next_step": (
            "Create the account through the Clerk-managed frontend flow, then call "
            "/api/v1/auth/me after sign-in to sync the session."
        ),
        "session_sync_endpoint": "/api/v1/auth/me",
    }


async def test_auth_login_returns_clerk_managed_contract(async_client):
    response = await async_client.post("/api/v1/auth/login")

    assert response.status_code == 501
    assert response.json() == {
        "status": "external_provider_required",
        "provider": "clerk",
        "action": "sign_in",
        "message": (
            "This backend does not accept direct credential submission because "
            "authentication is handled by Clerk on the frontend."
        ),
        "next_step": (
            "Authenticate through the Clerk-managed frontend flow, then call "
            "/api/v1/auth/me to sync the session."
        ),
        "session_sync_endpoint": "/api/v1/auth/me",
    }


async def test_document_upload_rejects_invalid_file_type(async_client, monkeypatch):
    monkeypatch.setattr(document_routes.settings, "ALLOWED_FILE_TYPES", ["application/pdf"])

    response = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("statement.txt", b"not-a-pdf", "text/plain")},
        data={"document_type": "bank_statement"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": document_routes.UNSUPPORTED_FILE_TYPE_DETAIL}


async def test_document_upload_accepts_pdf_with_leading_bytes(async_client, monkeypatch):
    created_document = _make_document(filename="stored-statement.pdf", original_filename="statement.pdf")
    create_document_mock = AsyncMock(return_value=created_document)
    monkeypatch.setattr(document_routes, "create_document", create_document_mock)

    response = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("statement.pdf", (b"\xef\xbb\xbf\n" * 5000) + b"%PDF-1.4 test payload", "application/pdf")},
    )

    assert response.status_code == 201
    assert create_document_mock.await_args.kwargs["content_type"] == "application/pdf"


async def test_document_upload_uses_sniffed_content_type_over_client_header(async_client, auth_context, monkeypatch):
    created_document = _make_document(filename="stored-statement.pdf", original_filename="statement.pdf")
    create_document_mock = AsyncMock(return_value=created_document)
    monkeypatch.setattr(document_routes, "create_document", create_document_mock)

    response = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("statement.pdf", b"%PDF-1.4 test payload", "text/plain")},
    )

    assert response.status_code == 201
    kwargs = create_document_mock.await_args.kwargs
    assert kwargs["content_type"] == "application/pdf"
    assert kwargs["file_content"] == b"%PDF-1.4 test payload"


async def test_document_upload_rejects_spoofed_client_content_type(async_client, monkeypatch):
    monkeypatch.setattr(document_routes.settings, "APP_ENV", "production")
    create_document_mock = AsyncMock()
    monkeypatch.setattr(document_routes, "create_document", create_document_mock)

    response = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("statement.pdf", b"not-a-real-pdf", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": document_routes.UNSUPPORTED_FILE_TYPE_DETAIL}
    create_document_mock.assert_not_awaited()


async def test_document_upload_allows_declared_pdf_fallback_in_development(async_client, monkeypatch):
    monkeypatch.setattr(document_routes.settings, "APP_ENV", "development")
    created_document = _make_document(filename="stored-statement.pdf", original_filename="statement.pdf")
    create_document_mock = AsyncMock(return_value=created_document)
    monkeypatch.setattr(document_routes, "create_document", create_document_mock)

    response = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("statement.pdf", b"scanner-wrapper-without-visible-header", "application/pdf")},
    )

    assert response.status_code == 201
    assert create_document_mock.await_args.kwargs["content_type"] == "application/pdf"


async def test_document_upload_rejects_file_too_large(async_client, monkeypatch):
    monkeypatch.setattr(document_routes.settings, "MAX_FILE_SIZE_MB", 0)

    response = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("statement.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "File too large"}


async def test_read_upload_with_limit_stops_once_size_limit_is_exceeded():
    fake_file = SimpleNamespace(read=AsyncMock(side_effect=[b"ab", b"cd", b"ef", b""]))

    with pytest.raises(HTTPException) as error:
        await document_routes._read_upload_with_limit(fake_file, max_size_bytes=3)

    assert error.value.status_code == 400
    assert error.value.detail == "File too large"
    assert fake_file.read.await_count == 2


async def test_list_documents_scopes_authenticated_org(async_client, fake_db, auth_context, monkeypatch):
    documents = [
        _make_document(
            analyses=[
                SimpleNamespace(
                    id="analysis_123",
                    document_id="doc_test_123",
                    risk_score=42,
                    confidence=0.91,
                    recommendation="review",
                    extracted_fields=None,
                    processing_time_seconds=1.2,
                    created_at=_timestamp(),
                )
            ]
        )
    ]
    get_documents_mock = AsyncMock(return_value=documents)
    monkeypatch.setattr(document_routes, "get_documents", get_documents_mock)

    response = await async_client.get("/api/v1/documents?skip=5&limit=10")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "doc_test_123"
    assert response.json()[0]["analyses"][0]["id"] == "analysis_123"
    get_documents_mock.assert_awaited_once_with(
        db=fake_db,
        org_id=auth_context.org_id,
        skip=5,
        limit=10,
    )


async def test_create_case_uses_authenticated_context(async_client, fake_db, auth_context, monkeypatch):
    created_case = _make_case()
    create_case_mock = AsyncMock(return_value=created_case)
    monkeypatch.setattr(case_routes, "create_case", create_case_mock)

    response = await async_client.post(
        "/api/v1/cases",
        json={
            "name": "Jane Doe",
            "status": "draft",
            "applicant_name": "Jane Doe",
            "applicant_email": "jane@example.com",
            "applicant_phone": "+1-555-0100",
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == created_case.id
    assert response.json()["status"] == "draft"
    create_case_mock.assert_awaited_once_with(
        db=fake_db,
        user_id=auth_context.user_id,
        org_id=auth_context.org_id,
        name="Jane Doe",
        status="draft",
        applicant_name="Jane Doe",
        applicant_email="jane@example.com",
        applicant_phone="+1-555-0100",
    )
    audit_data = _latest_audit_data(fake_db)
    assert audit_data["action"] == audit_service.ACTION_CASE_CREATED
    assert audit_data["resource_type"] == "case"
    assert audit_data["resource_id"] == created_case.id


async def test_viewer_cannot_create_case(async_client, fake_db, auth_context, monkeypatch):
    _override_auth_role(auth_context, "viewer")
    create_case_mock = AsyncMock()
    monkeypatch.setattr(case_routes, "create_case", create_case_mock)

    response = await async_client.post(
        "/api/v1/cases",
        json={
            "name": "Jane Doe",
            "status": "draft",
            "applicant_name": "Jane Doe",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "This action requires an admin or analyst role"}
    create_case_mock.assert_not_awaited()
    fake_db.auditlog.create.assert_not_awaited()


async def test_list_cases_scopes_authenticated_org(async_client, fake_db, auth_context, monkeypatch):
    cases = [_make_case()]
    list_cases_mock = AsyncMock(return_value=cases)
    monkeypatch.setattr(case_routes, "list_cases", list_cases_mock)

    response = await async_client.get("/api/v1/cases?skip=2&limit=5")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "case_test_123"
    list_cases_mock.assert_awaited_once_with(
        db=fake_db,
        org_id=auth_context.org_id,
        skip=2,
        limit=5,
    )


async def test_get_case_returns_404_when_missing(async_client, fake_db, auth_context, monkeypatch):
    get_case_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(case_routes, "get_case_by_id_for_org", get_case_mock)

    response = await async_client.get("/api/v1/cases/case_missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Case not found"}
    get_case_mock.assert_awaited_once_with(
        db=fake_db,
        case_id="case_missing",
        org_id=auth_context.org_id,
    )


async def test_get_case_returns_detail_when_present(async_client, fake_db, auth_context, monkeypatch):
    case_record = _make_case(status="collecting")
    get_case_mock = AsyncMock(return_value=case_record)
    monkeypatch.setattr(case_routes, "get_case_by_id_for_org", get_case_mock)

    response = await async_client.get("/api/v1/cases/case_test_123")

    assert response.status_code == 200
    assert response.json()["id"] == "case_test_123"
    assert response.json()["status"] == "collecting"
    get_case_mock.assert_awaited_once_with(
        db=fake_db,
        case_id="case_test_123",
        org_id=auth_context.org_id,
    )
    audit_data = _latest_audit_data(fake_db)
    assert audit_data["action"] == audit_service.ACTION_CASE_VIEWED
    assert audit_data["resource_type"] == "case"
    assert audit_data["resource_id"] == "case_test_123"


async def test_case_detail_allows_best_effort_audit_failure(async_client, fake_db, monkeypatch):
    case_record = _make_case(status="collecting")
    get_case_mock = AsyncMock(return_value=case_record)
    monkeypatch.setattr(case_routes, "get_case_by_id_for_org", get_case_mock)
    fake_db.auditlog.create.side_effect = RuntimeError("audit offline")

    response = await async_client.get("/api/v1/cases/case_test_123")

    assert response.status_code == 200
    assert response.json()["id"] == "case_test_123"
    fake_db.auditlog.create.assert_awaited_once()


async def test_get_latest_case_analysis_returns_snapshot(async_client, fake_db, auth_context, monkeypatch):
    now = _timestamp().isoformat()
    latest_analysis_mock = AsyncMock(
        return_value={
            "id": "case_analysis_live_123",
            "case_id": "case_test_123",
            "case_status": "collecting",
            "is_final": False,
            "risk_score": 46,
            "confidence": 0.74,
            "recommendation": "review",
            "decision_status": "manual_review",
            "decision_recommendation": "Manual review is recommended before approval.",
            "decision_reason": "Income documents conflict with banking evidence.",
            "extraction_confidence": 0.74,
            "risk_confidence": 0.74,
            "data_completeness": 0.66,
            "required_followups_json": json.dumps(["Verify payslip income against bank credits."]),
            "analysis_limitations_json": json.dumps(["Missing supporting documents."]),
            "extracted_fields": {"snapshot_kind": "case_live_provisional"},
            "risk_alerts": [{"severity": "medium", "message": "Income mismatch needs review."}],
            "summary": "Provisional case outcome is manual review.",
            "processing_time_seconds": None,
            "model_used": "case-provisional-aggregate-v1",
            "raw_response": {"snapshot_kind": "case_live_provisional"},
            "created_at": now,
        }
    )
    monkeypatch.setattr(case_routes, "get_latest_case_analysis_for_org", latest_analysis_mock)

    response = await async_client.get("/api/v1/cases/case_test_123/analysis/latest")

    assert response.status_code == 200
    assert response.json()["case_id"] == "case_test_123"
    assert response.json()["decision_status"] == "manual_review"
    latest_analysis_mock.assert_awaited_once_with(
        db=fake_db,
        case_id="case_test_123",
        org_id=auth_context.org_id,
    )


async def test_patch_case_updates_applicant_info(async_client, fake_db, auth_context, monkeypatch):
    updated_case = _make_case(applicant_phone="+1-555-0101")
    update_case_mock = AsyncMock(return_value=updated_case)
    monkeypatch.setattr(case_routes, "update_case_applicant_info", update_case_mock)

    response = await async_client.patch(
        "/api/v1/cases/case_test_123",
        json={"applicant_phone": "+1-555-0101"},
    )

    assert response.status_code == 200
    assert response.json()["applicant_phone"] == "+1-555-0101"
    update_case_mock.assert_awaited_once_with(
        db=fake_db,
        case_id="case_test_123",
        org_id=auth_context.org_id,
        applicant_phone="+1-555-0101",
    )
    audit_data = _latest_audit_data(fake_db)
    assert audit_data["action"] == audit_service.ACTION_CASE_UPDATED
    assert audit_data["resource_type"] == "case"
    assert audit_data["resource_id"] == "case_test_123"
    assert _latest_audit_metadata(fake_db)["updated_fields"] == ["applicant_phone"]


async def test_patch_case_requires_at_least_one_applicant_field(async_client):
    response = await async_client.patch("/api/v1/cases/case_test_123", json={})

    assert response.status_code == 422


async def test_patch_case_allows_clearing_applicant_field(async_client, fake_db, auth_context, monkeypatch):
    updated_case = _make_case(applicant_phone=None)
    update_case_mock = AsyncMock(return_value=updated_case)
    monkeypatch.setattr(case_routes, "update_case_applicant_info", update_case_mock)

    response = await async_client.patch(
        "/api/v1/cases/case_test_123",
        json={"applicant_phone": None},
    )

    assert response.status_code == 200
    assert response.json()["applicant_phone"] is None
    update_case_mock.assert_awaited_once_with(
        db=fake_db,
        case_id="case_test_123",
        org_id=auth_context.org_id,
        applicant_phone=None,
    )


async def test_viewer_cannot_patch_case(async_client, fake_db, auth_context, monkeypatch):
    _override_auth_role(auth_context, "viewer")
    update_case_mock = AsyncMock()
    monkeypatch.setattr(case_routes, "update_case_applicant_info", update_case_mock)

    response = await async_client.patch(
        "/api/v1/cases/case_test_123",
        json={"applicant_phone": "+1-555-0101"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "This action requires an admin or analyst role"}
    update_case_mock.assert_not_awaited()
    fake_db.auditlog.create.assert_not_awaited()


async def test_delete_case_scopes_authenticated_org(async_client, fake_db, auth_context, monkeypatch):
    delete_case_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(case_routes, "delete_case_for_org", delete_case_mock)

    response = await async_client.delete("/api/v1/cases/case_test_123")

    assert response.status_code == 204
    assert response.content == b""
    delete_case_mock.assert_awaited_once_with(
        db=fake_db,
        case_id="case_test_123",
        org_id=auth_context.org_id,
    )
    audit_data = _latest_audit_data(fake_db)
    assert audit_data["action"] == audit_service.ACTION_CASE_DELETED
    assert audit_data["resource_type"] == "case"
    assert audit_data["resource_id"] == "case_test_123"


async def test_viewer_cannot_delete_case(async_client, fake_db, auth_context, monkeypatch):
    _override_auth_role(auth_context, "viewer")
    delete_case_mock = AsyncMock()
    monkeypatch.setattr(case_routes, "delete_case_for_org", delete_case_mock)

    response = await async_client.delete("/api/v1/cases/case_test_123")

    assert response.status_code == 403
    assert response.json() == {"detail": "This action requires an admin or analyst role"}
    delete_case_mock.assert_not_awaited()
    fake_db.auditlog.create.assert_not_awaited()


async def test_delete_case_returns_404_when_missing(async_client, monkeypatch):
    delete_case_mock = AsyncMock(return_value=False)
    monkeypatch.setattr(case_routes, "delete_case_for_org", delete_case_mock)

    response = await async_client.delete("/api/v1/cases/case_missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Case not found"}


async def test_viewer_cannot_finalize_case(async_client, fake_db, auth_context, monkeypatch):
    _override_auth_role(auth_context, "viewer")
    finalize_case_mock = AsyncMock()
    monkeypatch.setattr(case_routes, "finalize_case_and_get_read_model", finalize_case_mock)

    response = await async_client.post("/api/v1/cases/case_test_123/finalize")

    assert response.status_code == 403
    assert response.json() == {"detail": "This action requires an admin or analyst role"}
    finalize_case_mock.assert_not_awaited()
    fake_db.auditlog.create.assert_not_awaited()


async def test_finalize_case_returns_authoritative_snapshot(async_client, fake_db, auth_context, monkeypatch):
    now = _timestamp().isoformat()
    finalize_case_mock = AsyncMock(
        return_value={
            "case": {
                "id": "case_test_123",
                "name": "Jane Doe",
                "status": "finalized",
                "applicant_name": "Jane Doe",
                "applicant_email": "jane@example.com",
                "applicant_phone": "+1-555-0100",
                "legacy_source_document_id": None,
                "created_at": now,
                "updated_at": now,
                "user_id": "user_test_123",
                "org_id": "org_test_456",
            },
            "applicant_intake": {
                "applicant_name": "Jane Doe",
                "applicant_email": "jane@example.com",
                "applicant_phone": "+1-555-0100",
                "completed_fields": ["applicant_name", "applicant_email", "applicant_phone"],
                "missing_fields": [],
                "completeness": 1.0,
            },
            "documents": [],
            "supported_document_completeness": {
                "provided_score": 0.0,
                "analyzed_score": 0.0,
                "provided_requirement_count": 0,
                "analyzed_requirement_count": 0,
                "total_requirement_count": 3,
                "present_document_types": [],
                "missing_document_types": [],
                "missing_requirement_keys": ["identity", "banking", "income"],
                "pending_requirement_keys": [],
                "requirements": [],
            },
            "cross_document_comparisons": [],
            "fraud_signals": [],
            "provisional_insights": {
                "decision_status": None,
                "recommendation": None,
                "summary": "Case evidence is still being assembled.",
                "blockers": [],
                "followups": [],
                "highest_risk_score": None,
                "average_risk_score": None,
                "analyzed_document_count": 0,
                "pending_document_count": 0,
                "failed_document_count": 0,
                "conflict_fields": [],
                "fraud_signal_count": 0,
                "fraud_signal_keys": [],
                "document_decision_counts": {},
            },
            "authoritative_analysis": {
                "id": "case_analysis_final_123",
                "case_id": "case_test_123",
                "case_status": "finalized",
                "is_final": True,
                "risk_score": 42,
                "confidence": 0.88,
                "recommendation": "review",
                "decision_status": "manual_review",
                "decision_recommendation": "Manual review recommended.",
                "decision_reason": "Needs a final human decision.",
                "extraction_confidence": 0.88,
                "risk_confidence": 0.88,
                "data_completeness": 0.9,
                "required_followups_json": json.dumps(["Verify income evidence."]),
                "analysis_limitations_json": json.dumps([]),
                "extracted_fields": {"snapshot_kind": "case_finalized", "is_final": True},
                "risk_alerts": [],
                "summary": "Manual review recommended.",
                "processing_time_seconds": None,
                "model_used": "case-final-aggregate-v1",
                "raw_response": {"snapshot_kind": "case_finalized"},
                "created_at": now,
            },
        }
    )
    monkeypatch.setattr(case_routes, "finalize_case_and_get_read_model", finalize_case_mock)

    response = await async_client.post("/api/v1/cases/case_test_123/finalize")

    assert response.status_code == 200
    assert response.json()["case"]["status"] == "finalized"
    assert response.json()["authoritative_analysis"]["is_final"] is True
    finalize_case_mock.assert_awaited_once_with(
        db=fake_db,
        case_id="case_test_123",
        org_id=auth_context.org_id,
    )
    audit_data = _latest_audit_data(fake_db)
    assert audit_data["action"] == audit_service.ACTION_CASE_FINALIZED
    assert audit_data["resource_type"] == "case"
    assert audit_data["resource_id"] == "case_test_123"


async def test_case_ask_route_rejects_blank_question(async_client):
    response = await async_client.post(
        "/api/v1/cases/case_test_123/ask",
        json={"question": "   "},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Question cannot be empty"}


async def test_viewer_cannot_use_case_ask(async_client, fake_db, auth_context, monkeypatch):
    _override_auth_role(auth_context, "viewer")
    ask_about_case_mock = AsyncMock()
    monkeypatch.setattr(case_routes, "ask_about_case", ask_about_case_mock)

    response = await async_client.post(
        "/api/v1/cases/case_test_123/ask",
        json={"question": "Why is this case in manual review?"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "This action requires an admin or analyst role"}
    ask_about_case_mock.assert_not_awaited()
    fake_db.auditlog.create.assert_not_awaited()


async def test_case_ask_route_returns_answer_and_sources(async_client, fake_db, auth_context, monkeypatch):
    ask_about_case_mock = AsyncMock(
        return_value={
            "answer": "The case is currently in manual review because income evidence conflicts.",
            "sources": [{"section_title": "Decision Summary", "page_num": 0}],
        }
    )
    monkeypatch.setattr(case_routes, "ask_about_case", ask_about_case_mock)

    response = await async_client.post(
        "/api/v1/cases/case_test_123/ask",
        json={"question": "Why is this case in manual review?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "The case is currently in manual review because income evidence conflicts.",
        "sources": [{"section_title": "Decision Summary", "page_num": 0}],
    }
    ask_about_case_mock.assert_awaited_once_with(
        db=fake_db,
        case_id="case_test_123",
        org_id=auth_context.org_id,
        question="Why is this case in manual review?",
    )
    audit_data = _latest_audit_data(fake_db)
    assert audit_data["action"] == audit_service.ACTION_CASE_ASKED
    assert audit_data["resource_type"] == "case"
    assert audit_data["resource_id"] == "case_test_123"
    metadata = _latest_audit_metadata(fake_db)
    assert metadata["question_length"] == len("Why is this case in manual review?")
    assert "Why is this case in manual review?" not in str(metadata)


async def test_case_ask_route_returns_safe_answer_when_service_raises_unexpected_error(async_client, monkeypatch):
    ask_about_case_mock = AsyncMock(side_effect=RuntimeError("provider offline"))
    monkeypatch.setattr(case_routes, "ask_about_case", ask_about_case_mock)

    response = await async_client.post(
        "/api/v1/cases/case_test_123/ask",
        json={"question": "Why is this case in manual review?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": (
            "Ask AI is temporarily unavailable for this case right now. "
            "Please try again shortly or review the saved case report."
        ),
        "sources": [],
    }


async def test_get_case_report_returns_structured_payload(async_client, fake_db, auth_context, monkeypatch):
    now = _timestamp().isoformat()
    get_case_report_mock = AsyncMock(
        return_value={
            "header": {
                "report_id": "case_analysis_live_123",
                "case_id": "case_test_123",
                "title": "Jane Doe Case Report",
                "subtitle": "Provisional case assessment • Collecting workflow state",
                "report_status": "provisional",
                "is_final": False,
                "generated_at": now,
                "generated_from": "live_provisional",
                "print_filename": "loanlens-case-case_test_123-report.pdf",
            },
            "case": {
                "id": "case_test_123",
                "name": "Jane Doe",
                "status": "collecting",
                "applicant_name": "Jane Doe",
                "applicant_email": "jane@example.com",
                "applicant_phone": "+1-555-0100",
                "legacy_source_document_id": None,
                "created_at": now,
                "updated_at": now,
                "user_id": "user_test_123",
                "org_id": "org_test_456",
            },
            "applicant_intake": {
                "applicant_name": "Jane Doe",
                "applicant_email": "jane@example.com",
                "applicant_phone": "+1-555-0100",
                "completed_fields": ["applicant_name", "applicant_email", "applicant_phone"],
                "missing_fields": [],
                "completeness": 1.0,
            },
            "latest_analysis": {
                "id": "case_analysis_live_123",
                "case_id": "case_test_123",
                "case_status": "collecting",
                "is_final": False,
                "risk_score": 46,
                "confidence": 0.74,
                "recommendation": "review",
                "decision_status": "manual_review",
                "decision_recommendation": "Manual review is recommended before approval.",
                "decision_reason": "Income documents conflict with banking evidence.",
                "extraction_confidence": 0.74,
                "risk_confidence": 0.74,
                "data_completeness": 0.66,
                "required_followups_json": json.dumps(["Verify payslip income against bank credits."]),
                "analysis_limitations_json": json.dumps(["Missing supporting documents."]),
                "extracted_fields": {"snapshot_kind": "case_live_provisional"},
                "risk_alerts": [{"severity": "medium", "message": "Income mismatch needs review."}],
                "summary": "Provisional case outcome is manual review.",
                "processing_time_seconds": None,
                "model_used": "case-provisional-aggregate-v1",
                "raw_response": {"snapshot_kind": "case_live_provisional"},
                "created_at": now,
            },
            "documents": [],
            "overview": {
                "decision_status": "manual_review",
                "recommendation": "review",
                "summary": "Provisional case outcome is manual review.",
                "decision_reason": "Income documents conflict with banking evidence.",
                "risk_score": 46,
                "confidence": 0.74,
                "data_completeness": 0.66,
                "analyzed_document_count": 1,
                "pending_document_count": 0,
                "failed_document_count": 0,
                "fraud_signal_count": 1,
                "blocker_count": 1,
                "followup_count": 2,
            },
            "metrics": [
                {
                    "key": "risk_score",
                    "label": "Risk score",
                    "value": 46,
                    "display_value": "46",
                    "tone": "warning",
                    "hint": None,
                }
            ],
            "sections": [
                {
                    "key": "decision",
                    "title": "Decision Summary",
                    "summary": "Provisional case outcome is manual review.",
                    "items": [],
                }
            ],
            "print": {
                "title": "Jane Doe Case Report",
                "subtitle": "Provisional case assessment • Collecting workflow state",
                "filename": "loanlens-case-case_test_123-report.pdf",
                "generated_at": now,
                "footer_note": "AI-generated case report.",
                "sections": [
                    {
                        "key": "decision",
                        "title": "Decision Summary",
                        "paragraphs": ["Provisional case outcome is manual review."],
                        "bullets": [],
                    }
                ],
            },
        }
    )
    monkeypatch.setattr(case_routes, "get_case_report", get_case_report_mock)

    response = await async_client.get("/api/v1/cases/case_test_123/report")

    assert response.status_code == 200
    assert response.json()["header"]["case_id"] == "case_test_123"
    assert response.json()["print"]["filename"].endswith(".pdf")
    get_case_report_mock.assert_awaited_once_with(
        db=fake_db,
        case_id="case_test_123",
        org_id=auth_context.org_id,
    )
    audit_data = _latest_audit_data(fake_db)
    assert audit_data["action"] == audit_service.ACTION_CASE_REPORT_EXPORTED
    assert audit_data["resource_type"] == "case"
    assert audit_data["resource_id"] == "case_test_123"
    assert _latest_audit_metadata(fake_db)["report_status"] == "provisional"


async def test_viewer_cannot_export_case_report(async_client, fake_db, auth_context, monkeypatch):
    _override_auth_role(auth_context, "viewer")
    get_case_report_mock = AsyncMock()
    monkeypatch.setattr(case_routes, "get_case_report", get_case_report_mock)

    response = await async_client.get("/api/v1/cases/case_test_123/report")

    assert response.status_code == 403
    assert response.json() == {"detail": "This action requires an admin or analyst role"}
    get_case_report_mock.assert_not_awaited()
    fake_db.auditlog.create.assert_not_awaited()


async def test_get_document_returns_404_when_missing(async_client, fake_db, auth_context, monkeypatch):
    get_document_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(document_routes, "get_document_by_id_for_org", get_document_mock)

    response = await async_client.get("/api/v1/documents/doc_missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}
    get_document_mock.assert_awaited_once_with(
        db=fake_db,
        document_id="doc_missing",
        org_id=auth_context.org_id,
    )


async def test_delete_document_scopes_authenticated_org(async_client, fake_db, auth_context, monkeypatch):
    delete_document_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(document_routes, "delete_document_for_org", delete_document_mock)

    response = await async_client.delete("/api/v1/documents/doc_test_123")

    assert response.status_code == 204
    assert response.content == b""
    delete_document_mock.assert_awaited_once_with(
        db=fake_db,
        document_id="doc_test_123",
        org_id=auth_context.org_id,
    )
    audit_data = _latest_audit_data(fake_db)
    assert audit_data["action"] == audit_service.ACTION_DOCUMENT_DELETED
    assert audit_data["resource_type"] == "document"
    assert audit_data["resource_id"] == "doc_test_123"


async def test_viewer_cannot_delete_document(async_client, fake_db, auth_context, monkeypatch):
    _override_auth_role(auth_context, "viewer")
    delete_document_mock = AsyncMock()
    monkeypatch.setattr(document_routes, "delete_document_for_org", delete_document_mock)

    response = await async_client.delete("/api/v1/documents/doc_test_123")

    assert response.status_code == 403
    assert response.json() == {"detail": "This action requires an admin or analyst role"}
    delete_document_mock.assert_not_awaited()
    fake_db.auditlog.create.assert_not_awaited()


async def test_delete_document_returns_404_when_missing(async_client, monkeypatch):
    delete_document_mock = AsyncMock(return_value=False)
    monkeypatch.setattr(document_routes, "delete_document_for_org", delete_document_mock)

    response = await async_client.delete("/api/v1/documents/doc_missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


async def test_viewer_cannot_queue_document_analysis(async_client, fake_db, auth_context, monkeypatch):
    _override_auth_role(auth_context, "viewer")
    get_document_mock = AsyncMock()
    enqueue_mock = AsyncMock()

    monkeypatch.setattr(analysis_routes, "get_document_by_id_for_org", get_document_mock)
    monkeypatch.setattr(analysis_routes, "enqueue_analysis_job", enqueue_mock)

    response = await async_client.post("/api/v1/analysis/documents/doc_test_123/analyze")

    assert response.status_code == 403
    assert response.json() == {"detail": "This action requires an admin or analyst role"}
    get_document_mock.assert_not_awaited()
    enqueue_mock.assert_not_awaited()
    fake_db.auditlog.create.assert_not_awaited()


async def test_analysis_trigger_queues_job_for_authenticated_document(async_client, fake_db, auth_context, monkeypatch):
    document = _make_document(status=DocumentStatus.PENDING.value)
    get_document_mock = AsyncMock(return_value=document)
    enqueue_mock = AsyncMock(return_value=None)

    monkeypatch.setattr(analysis_routes, "get_document_by_id_for_org", get_document_mock)
    monkeypatch.setattr(analysis_routes, "enqueue_analysis_job", enqueue_mock)

    response = await async_client.post("/api/v1/analysis/documents/doc_test_123/analyze")

    assert response.status_code == 202
    assert response.json() == {
        "message": "Analysis queued",
        "analysis_id": None,
        "document_id": "doc_test_123",
        "status": "queued",
    }
    get_document_mock.assert_awaited_once_with(
        db=fake_db,
        document_id="doc_test_123",
        org_id=auth_context.org_id,
    )
    fake_db.document.update.assert_awaited_once_with(
        where={"id": "doc_test_123"},
        data={"status": DocumentStatus.PROCESSING.value},
    )
    enqueue_mock.assert_awaited_once_with("doc_test_123", force_reanalysis=False)
    audit_data = _latest_audit_data(fake_db)
    assert audit_data["action"] == audit_service.ACTION_DOCUMENT_ANALYSIS_QUEUED
    assert audit_data["resource_type"] == "document"
    assert audit_data["resource_id"] == "doc_test_123"
    assert _latest_audit_metadata(fake_db)["force_reanalysis"] is False


async def test_analysis_trigger_returns_existing_analysis_when_document_already_analyzed(
    async_client,
    fake_db,
    auth_context,
    monkeypatch,
):
    document = _make_document(status=DocumentStatus.ANALYZED.value)
    existing_analysis = SimpleNamespace(id="analysis_existing_123")
    get_document_mock = AsyncMock(return_value=document)
    get_analysis_mock = AsyncMock(return_value=existing_analysis)

    monkeypatch.setattr(analysis_routes, "get_document_by_id_for_org", get_document_mock)
    monkeypatch.setattr(analysis_routes, "get_analysis_by_document", get_analysis_mock)

    response = await async_client.post("/api/v1/analysis/documents/doc_test_123/analyze")

    assert response.status_code == 202
    assert response.json() == {
        "message": "Document already analyzed.",
        "analysis_id": "analysis_existing_123",
        "document_id": "doc_test_123",
        "status": "already_analyzed",
    }
    fake_db.document.update.assert_not_awaited()
    audit_data = _latest_audit_data(fake_db)
    assert audit_data["action"] == audit_service.ACTION_DOCUMENT_ANALYSIS_REUSED
    assert audit_data["resource_type"] == "analysis"
    assert audit_data["resource_id"] == "analysis_existing_123"


async def test_reanalysis_trigger_queues_for_analyzed_document(async_client, fake_db, auth_context, monkeypatch):
    document = _make_document(status=DocumentStatus.ANALYZED.value)
    get_document_mock = AsyncMock(return_value=document)
    enqueue_mock = AsyncMock(return_value=None)

    monkeypatch.setattr(analysis_routes, "get_document_by_id_for_org", get_document_mock)
    monkeypatch.setattr(analysis_routes, "enqueue_analysis_job", enqueue_mock)

    response = await async_client.post("/api/v1/analysis/documents/doc_test_123/reanalyze")

    assert response.status_code == 202
    assert response.json() == {
        "message": "Forced reanalysis queued.",
        "analysis_id": None,
        "document_id": "doc_test_123",
        "status": "queued",
    }
    fake_db.document.update.assert_awaited_once_with(
        where={"id": "doc_test_123"},
        data={"status": DocumentStatus.PROCESSING.value},
    )
    enqueue_mock.assert_awaited_once_with("doc_test_123", force_reanalysis=True)
    audit_data = _latest_audit_data(fake_db)
    assert audit_data["action"] == audit_service.ACTION_DOCUMENT_REANALYSIS_QUEUED
    assert _latest_audit_metadata(fake_db)["force_reanalysis"] is True


async def test_analysis_trigger_rolls_back_status_when_queueing_fails(async_client, fake_db, monkeypatch):
    document = _make_document(status=DocumentStatus.PENDING.value)
    get_document_mock = AsyncMock(return_value=document)
    enqueue_mock = AsyncMock(side_effect=RuntimeError("queue offline"))

    monkeypatch.setattr(analysis_routes, "get_document_by_id_for_org", get_document_mock)
    monkeypatch.setattr(analysis_routes, "enqueue_analysis_job", enqueue_mock)

    response = await async_client.post("/api/v1/analysis/documents/doc_test_123/analyze")

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to queue analysis job: queue offline"}
    assert fake_db.document.update.await_args_list[0].kwargs == {
        "where": {"id": "doc_test_123"},
        "data": {"status": DocumentStatus.PROCESSING.value},
    }
    assert fake_db.document.update.await_args_list[1].kwargs == {
        "where": {"id": "doc_test_123"},
        "data": {"status": DocumentStatus.PENDING.value},
    }


async def test_get_analysis_decodes_json_and_enforces_org_scope(async_client, fake_db, auth_context, monkeypatch):
    analysis = FakeAnalysisRecord()
    get_analysis_mock = AsyncMock(return_value=analysis)
    get_document_mock = AsyncMock(return_value=_make_document(status=DocumentStatus.ANALYZED.value))

    monkeypatch.setattr(analysis_routes, "get_analysis_by_id", get_analysis_mock)
    monkeypatch.setattr(analysis_routes, "get_document_by_id_for_org", get_document_mock)

    response = await async_client.get("/api/v1/analysis/analysis_123")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "analysis_123"
    assert payload["extracted_fields"]["score"] == 42
    assert payload["extracted_fields"]["decision"]["decision_status"] == "manual_review"
    assert payload["recommendation"] == "review"
    assert payload["risk_alerts"] == [
        {
            "severity": "medium",
            "message": "Review income volatility",
            "field": None,
            "details": None,
        }
    ]
    assert payload["document_id"] == "doc_test_123"
    get_analysis_mock.assert_awaited_once_with(db=fake_db, analysis_id="analysis_123")
    get_document_mock.assert_awaited_once_with(
        db=fake_db,
        document_id="doc_test_123",
        org_id=auth_context.org_id,
    )


async def test_get_analysis_clamps_legacy_confidence_shapes(async_client, fake_db, auth_context, monkeypatch):
    analysis = FakeAnalysisRecord(
        confidence=145,
        extracted_fields=json.dumps(
            {
                "statementMeta": {"confidence": 125},
                "incomeEngine": {"income_type": "salary", "confidence": "medium"},
                "decision": "APPROVE",
                "decisionEngine": {
                    "decision": "APPROVE",
                    "reasons": ["Stable salary and healthy balances."],
                    "confidence": "high",
                },
                "transactions": [{"confidence": "low"}],
            }
        ),
    )
    get_analysis_mock = AsyncMock(return_value=analysis)
    get_document_mock = AsyncMock(return_value=_make_document(status=DocumentStatus.ANALYZED.value))

    monkeypatch.setattr(analysis_routes, "get_analysis_by_id", get_analysis_mock)
    monkeypatch.setattr(analysis_routes, "get_document_by_id_for_org", get_document_mock)

    response = await async_client.get("/api/v1/analysis/analysis_123")

    assert response.status_code == 200
    payload = response.json()
    assert payload["confidence"] == 1.0
    assert payload["extracted_fields"]["statementMeta"]["confidence"] == 1.0
    assert payload["extracted_fields"]["incomeEngine"]["confidence"] == 0.6
    assert payload["extracted_fields"]["decision"]["risk_confidence"] == 1.0
    assert payload["extracted_fields"]["decisionEngine"]["risk_confidence"] == 1.0
    assert payload["extracted_fields"]["transactions"][0]["confidence"] == 0.3
    assert payload["extracted_fields"]["decision"]["decision_status"] == "manual_review"


async def test_get_analysis_prevents_sample_decision_contradictions(async_client, fake_db, auth_context, monkeypatch):
    expected = load_short_history_sample_expected()
    extracted_fields = bank_statement_pipeline.build_bank_statement_output(
        transactions=load_short_history_sample_transactions(),
        statement_confidence=expected["statement_confidence"],
        document_type="bank_statement",
    )
    analysis = FakeAnalysisRecord(
        confidence=145,
        recommendation="reject",
        decision_status="reject",
        decision_recommendation="Do not approve this application.",
        decision_reason="Reject due to severe risk.",
        extracted_fields=json.dumps(extracted_fields),
        raw_response=json.dumps(
            {
                "decision": "reject",
                "recommendation": "reject",
                "summary": "Reject due to severe risk.",
            }
        ),
        summary="Reject due to severe risk.",
    )
    get_analysis_mock = AsyncMock(return_value=analysis)
    get_document_mock = AsyncMock(return_value=_make_document(status=DocumentStatus.ANALYZED.value))

    monkeypatch.setattr(analysis_routes, "get_analysis_by_id", get_analysis_mock)
    monkeypatch.setattr(analysis_routes, "get_document_by_id_for_org", get_document_mock)

    response = await async_client.get("/api/v1/analysis/analysis_123")

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision_status"] == expected["decision_status"]
    assert payload["recommendation"] == expected["top_level_recommendation"]
    assert payload["decision_recommendation"] == expected["decision_recommendation"]
    assert payload["decision_reason"] == expected["decision_reason"]
    assert payload["summary"].splitlines()[0] == expected["decision_reason"]
    assert payload["extracted_fields"]["decision"]["decision_status"] == expected["decision_status"]
    assert payload["extracted_fields"]["decision"]["decision_reason"] == expected["decision_reason"]
    assert payload["decision_reason"] != "Reject due to severe risk."


async def test_list_documents_clamps_nested_analysis_confidence(async_client, fake_db, auth_context, monkeypatch):
    documents = [
        _make_document(
            analyses=[
                SimpleNamespace(
                    id="analysis_legacy_123",
                    document_id="doc_test_123",
                    risk_score=42,
                    confidence=245,
                    recommendation="review",
                    extracted_fields=None,
                    processing_time_seconds=1.2,
                    created_at=_timestamp(),
                )
            ]
        )
    ]
    get_documents_mock = AsyncMock(return_value=documents)
    monkeypatch.setattr(document_routes, "get_documents", get_documents_mock)

    response = await async_client.get("/api/v1/documents")

    assert response.status_code == 200
    assert response.json()[0]["analyses"][0]["confidence"] == 1.0


async def test_get_latest_analysis_returns_404_without_result(async_client, fake_db, auth_context, monkeypatch):
    get_document_mock = AsyncMock(return_value=_make_document(status=DocumentStatus.ANALYZED.value))
    get_analysis_mock = AsyncMock(return_value=None)

    monkeypatch.setattr(analysis_routes, "get_document_by_id_for_org", get_document_mock)
    monkeypatch.setattr(analysis_routes, "get_analysis_by_document", get_analysis_mock)

    response = await async_client.get("/api/v1/analysis/documents/doc_test_123/latest")

    assert response.status_code == 404
    assert response.json() == {"detail": "No analysis found"}
    get_analysis_mock.assert_awaited_once_with(db=fake_db, document_id="doc_test_123")


async def test_get_analysis_job_status_returns_classified_failure(async_client, fake_db, auth_context, monkeypatch):
    get_document_mock = AsyncMock(return_value=_make_document(status=DocumentStatus.FAILED.value))
    get_job_mock = AsyncMock(
        return_value={
            "job_id": "job_123",
            "document_id": "doc_test_123",
            "status": "failed",
            "attempts": 1,
            "max_attempts": 1,
            "last_error": "403 PERMISSION_DENIED. Your project has been denied access.",
            "error_code": "ai_provider_access_denied",
            "user_message": "AI analysis is blocked because the configured Gemini project was denied access. Check the Google API key/project permissions.",
        }
    )

    monkeypatch.setattr(analysis_routes, "get_document_by_id_for_org", get_document_mock)
    monkeypatch.setattr(analysis_routes, "get_analysis_job", get_job_mock)

    response = await async_client.get("/api/v1/analysis/documents/doc_test_123/job")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error_code"] == "ai_provider_access_denied"
    assert "denied access" in response.json()["user_message"]


async def test_get_analysis_job_status_returns_ocr_progress_fields(async_client, fake_db, auth_context, monkeypatch):
    get_document_mock = AsyncMock(return_value=_make_document(status=DocumentStatus.PROCESSING.value))
    get_job_mock = AsyncMock(
        return_value={
            "job_id": "job_ocr_123",
            "document_id": "doc_test_123",
            "status": "processing",
            "stage": "ocr",
            "stage_message": "Running OCR on scanned pages.",
            "ocr_provider": "mixed",
            "pages_processed": 2,
            "total_pages": 5,
            "ocr_required_pages": [3, 4, 5],
            "ocr_failed_pages": [4],
            "ocr_unreliable_pages": [5],
            "ocr_fallback_used": True,
            "ocr_quality_status": "blocked",
            "attempts": 1,
            "max_attempts": 1,
            "last_error": None,
            "error_code": None,
            "user_message": None,
        }
    )

    monkeypatch.setattr(analysis_routes, "get_document_by_id_for_org", get_document_mock)
    monkeypatch.setattr(analysis_routes, "get_analysis_job", get_job_mock)

    response = await async_client.get("/api/v1/analysis/documents/doc_test_123/job")

    assert response.status_code == 200
    assert response.json()["stage"] == "ocr"
    assert response.json()["stage_message"] == "Running OCR on scanned pages."
    assert response.json()["ocr_provider"] == "mixed"
    assert response.json()["pages_processed"] == 2
    assert response.json()["total_pages"] == 5
    assert response.json()["ocr_required_pages"] == [3, 4, 5]
    assert response.json()["ocr_failed_pages"] == [4]
    assert response.json()["ocr_unreliable_pages"] == [5]
    assert response.json()["ocr_fallback_used"] is True
    assert response.json()["ocr_quality_status"] == "blocked"


async def test_get_analysis_job_status_returns_404_without_manifest(async_client, fake_db, auth_context, monkeypatch):
    get_document_mock = AsyncMock(return_value=_make_document(status=DocumentStatus.PROCESSING.value))
    get_job_mock = AsyncMock(return_value=None)

    monkeypatch.setattr(analysis_routes, "get_document_by_id_for_org", get_document_mock)
    monkeypatch.setattr(analysis_routes, "get_analysis_job", get_job_mock)

    response = await async_client.get("/api/v1/analysis/documents/doc_test_123/job")

    assert response.status_code == 404
    assert response.json() == {"detail": "Analysis job not found"}


async def test_ask_route_requires_analyzed_document(async_client, fake_db, auth_context, monkeypatch):
    get_document_mock = AsyncMock(return_value=_make_document(status=DocumentStatus.PENDING.value))
    monkeypatch.setattr(ask_routes, "get_document_by_id_for_org", get_document_mock)

    response = await async_client.post(
        "/api/v1/ask/doc_test_123",
        json={"question": "What is the current balance?"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Document must be analyzed before you can ask questions about it."
    }
    get_document_mock.assert_awaited_once_with(
        db=fake_db,
        document_id="doc_test_123",
        org_id=auth_context.org_id,
    )


async def test_ask_route_rejects_blank_question(async_client, monkeypatch):
    get_document_mock = AsyncMock(return_value=_make_document(status=DocumentStatus.ANALYZED.value))
    monkeypatch.setattr(ask_routes, "get_document_by_id_for_org", get_document_mock)

    response = await async_client.post(
        "/api/v1/ask/doc_test_123",
        json={"question": "   "},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Question cannot be empty"}


async def test_viewer_cannot_use_document_ask(async_client, fake_db, auth_context, monkeypatch):
    _override_auth_role(auth_context, "viewer")
    get_document_mock = AsyncMock(return_value=_make_document(status=DocumentStatus.ANALYZED.value))
    ask_about_document_mock = AsyncMock()

    monkeypatch.setattr(ask_routes, "get_document_by_id_for_org", get_document_mock)
    monkeypatch.setattr(ask_routes, "ask_about_document", ask_about_document_mock)

    response = await async_client.post(
        "/api/v1/ask/doc_test_123",
        json={"question": "What was the average balance?"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "This action requires an admin or analyst role"}
    get_document_mock.assert_not_awaited()
    ask_about_document_mock.assert_not_awaited()
    fake_db.auditlog.create.assert_not_awaited()


async def test_ask_route_returns_answer_and_sources(async_client, fake_db, monkeypatch):
    get_document_mock = AsyncMock(return_value=_make_document(status=DocumentStatus.ANALYZED.value))
    ask_about_document_mock = AsyncMock(
        return_value={
            "answer": "Average balance remained above the threshold.",
            "sources": [{"section_title": "Account Summary", "page_num": 2}],
        }
    )
    monkeypatch.setattr(ask_routes, "get_document_by_id_for_org", get_document_mock)
    monkeypatch.setattr(ask_routes, "ask_about_document", ask_about_document_mock)

    response = await async_client.post(
        "/api/v1/ask/doc_test_123",
        json={"question": "What was the average balance?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Average balance remained above the threshold.",
        "sources": [{"section_title": "Account Summary", "page_num": 2}],
    }
    ask_about_document_mock.assert_awaited_once_with(
        document_id="doc_test_123",
        question="What was the average balance?",
    )
    audit_data = _latest_audit_data(fake_db)
    assert audit_data["action"] == audit_service.ACTION_DOCUMENT_ASKED
    assert audit_data["resource_type"] == "document"
    assert audit_data["resource_id"] == "doc_test_123"
    metadata = _latest_audit_metadata(fake_db)
    assert metadata["question_length"] == len("What was the average balance?")
    assert "What was the average balance?" not in str(metadata)


async def test_ask_route_returns_safe_answer_when_service_raises_unexpected_error(async_client, monkeypatch):
    get_document_mock = AsyncMock(return_value=_make_document(status=DocumentStatus.ANALYZED.value))
    ask_about_document_mock = AsyncMock(side_effect=RuntimeError("embedding provider offline"))

    monkeypatch.setattr(ask_routes, "get_document_by_id_for_org", get_document_mock)
    monkeypatch.setattr(ask_routes, "ask_about_document", ask_about_document_mock)

    response = await async_client.post(
        "/api/v1/ask/doc_test_123",
        json={"question": "What was the average balance?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": (
            "Ask AI is temporarily unavailable for this document right now. "
            "Please try again shortly or review the saved analysis summary."
        ),
        "sources": [],
    }
