from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import document_service


@pytest.mark.asyncio
async def test_create_document_invalidates_final_snapshot_for_existing_case(monkeypatch):
    created_document = SimpleNamespace(id="doc_test_123", case_id="case_test_123")
    fake_db = SimpleNamespace(
        document=SimpleNamespace(create=AsyncMock(return_value=created_document)),
    )
    invalidate_mock = AsyncMock(return_value=None)

    monkeypatch.setattr(document_service, "upload_file", AsyncMock(return_value="secure://documents/doc_test_123.pdf"))
    monkeypatch.setattr(document_service, "store_password", AsyncMock(return_value=None))
    monkeypatch.setattr(
        document_service,
        "invalidate_final_case_analysis_for_case",
        invalidate_mock,
    )

    result = await document_service.create_document(
        db=fake_db,
        original_filename="statement.pdf",
        file_content=b"%PDF-1.4",
        user_id="user_test_123",
        org_id="org_test_456",
        case_id="case_test_123",
    )

    assert result is created_document
    invalidate_mock.assert_awaited_once_with(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )


@pytest.mark.asyncio
async def test_create_document_does_not_invalidate_when_creating_new_case(monkeypatch):
    created_case = SimpleNamespace(id="doc_test_123")
    created_document = SimpleNamespace(id="doc_test_123", case_id="doc_test_123")
    fake_db = SimpleNamespace(
        document=SimpleNamespace(create=AsyncMock(return_value=created_document)),
        case=SimpleNamespace(update=AsyncMock(return_value=created_case)),
    )
    invalidate_mock = AsyncMock(return_value=None)
    create_case_mock = AsyncMock(return_value=created_case)

    monkeypatch.setattr(document_service.uuid, "uuid4", lambda: "doc_test_123")
    monkeypatch.setattr(document_service, "upload_file", AsyncMock(return_value="secure://documents/doc_test_123.pdf"))
    monkeypatch.setattr(document_service, "store_password", AsyncMock(return_value=None))
    monkeypatch.setattr(document_service, "create_case", create_case_mock)
    monkeypatch.setattr(
        document_service,
        "invalidate_final_case_analysis_for_case",
        invalidate_mock,
    )

    result = await document_service.create_document(
        db=fake_db,
        original_filename="statement.pdf",
        file_content=b"%PDF-1.4",
        user_id="user_test_123",
        org_id="org_test_456",
        applicant_name="Jane Applicant",
        applicant_email="jane@example.com",
        applicant_phone="+1-555-0100",
    )

    assert result is created_document
    invalidate_mock.assert_not_awaited()

    create_case_kwargs = create_case_mock.await_args.kwargs
    assert create_case_kwargs["name"] == "statement.pdf"
    assert create_case_kwargs["applicant_name"] == "Jane Applicant"
    assert create_case_kwargs["applicant_email"] == "jane@example.com"
    assert create_case_kwargs["applicant_phone"] == "+1-555-0100"
    assert create_case_kwargs["case_id"] == created_document.id
    assert "legacy_source_document_id" not in create_case_kwargs
    fake_db.document.create.assert_awaited_once_with(
        data={
            "id": "doc_test_123",
            "filename": "doc_test_123.pdf",
            "original_filename": "statement.pdf",
            "file_url": "secure://documents/doc_test_123.pdf",
            "file_type": "application/pdf",
            "file_size_bytes": 8,
            "document_type": "other",
            "status": "pending",
            "case_id": "doc_test_123",
            "user_id": "user_test_123",
            "org_id": "org_test_456",
        }
    )
    fake_db.case.update.assert_awaited_once_with(
        where={"id": "doc_test_123"},
        data={"legacy_source_document_id": created_document.id},
    )
