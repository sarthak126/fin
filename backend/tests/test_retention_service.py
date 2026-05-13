from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from services import retention_service


def _document(**overrides):
    data = {
        "id": "doc_test_123",
        "file_url": "s3://loanlens-test/documents/doc_test_123.pdf",
        "case_id": "case_test_123",
        "org_id": "org_test_456",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _case(**overrides):
    data = {
        "id": "case_test_123",
        "legacy_source_document_id": "doc_test_123",
        "org_id": "org_test_456",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _fake_db(*, document=None, documents=None, case=None):
    return SimpleNamespace(
        case=SimpleNamespace(
            find_first=AsyncMock(return_value=case),
            find_many=AsyncMock(return_value=[]),
            update=AsyncMock(),
            update_many=AsyncMock(),
            delete=AsyncMock(),
        ),
        document=SimpleNamespace(
            find_first=AsyncMock(return_value=document),
            find_many=AsyncMock(return_value=documents or []),
            delete=AsyncMock(),
        ),
        analysis=SimpleNamespace(delete_many=AsyncMock()),
        caseanalysis=SimpleNamespace(delete_many=AsyncMock()),
        auditlog=SimpleNamespace(delete_many=AsyncMock(return_value=0)),
    )


def _mock_external_cleanup(monkeypatch):
    delete_password = AsyncMock()
    delete_artifact = AsyncMock()
    delete_file = AsyncMock()
    delete_vectors = Mock(return_value=True)
    delete_job = AsyncMock()

    monkeypatch.setattr(retention_service, "delete_password_for_file", delete_password)
    monkeypatch.setattr(retention_service, "delete_extraction_artifact_for_file", delete_artifact)
    monkeypatch.setattr(retention_service, "delete_file", delete_file)
    monkeypatch.setattr(retention_service, "delete_document_vectors", delete_vectors)
    monkeypatch.setattr(retention_service, "delete_analysis_job", delete_job)

    return delete_password, delete_artifact, delete_file, delete_vectors, delete_job


@pytest.mark.asyncio
async def test_delete_document_for_org_removes_storage_vectors_jobs_and_db_rows(monkeypatch):
    document = _document()
    fake_db = _fake_db(document=document)
    delete_password, delete_artifact, delete_file, delete_vectors, delete_job = _mock_external_cleanup(monkeypatch)

    deleted = await retention_service.delete_document_for_org(
        db=fake_db,
        document_id="doc_test_123",
        org_id="org_test_456",
    )

    assert deleted is True
    fake_db.document.find_first.assert_awaited_once_with(
        where={"id": "doc_test_123", "org_id": "org_test_456"}
    )
    fake_db.case.update_many.assert_awaited_once_with(
        where={"legacy_source_document_id": "doc_test_123"},
        data={"legacy_source_document_id": None},
    )
    delete_password.assert_awaited_once_with(document.file_url)
    delete_artifact.assert_awaited_once_with(document.file_url)
    delete_file.assert_awaited_once_with(document.file_url)
    delete_vectors.assert_called_once_with("doc_test_123")
    delete_job.assert_awaited_once_with("doc_test_123")
    fake_db.analysis.delete_many.assert_awaited_once_with(where={"document_id": "doc_test_123"})
    fake_db.document.delete.assert_awaited_once_with(where={"id": "doc_test_123"})
    fake_db.caseanalysis.delete_many.assert_awaited_once_with(
        where={"case_id": "case_test_123", "is_final": True}
    )


@pytest.mark.asyncio
async def test_delete_document_for_org_returns_false_when_missing(monkeypatch):
    fake_db = _fake_db(document=None)
    _mock_external_cleanup(monkeypatch)

    deleted = await retention_service.delete_document_for_org(
        db=fake_db,
        document_id="doc_missing",
        org_id="org_test_456",
    )

    assert deleted is False
    fake_db.analysis.delete_many.assert_not_awaited()
    fake_db.document.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_case_for_org_removes_case_documents_and_case_analysis(monkeypatch):
    case_record = _case()
    first_document = _document(id="doc_test_123")
    second_document = _document(id="doc_supporting_456")
    fake_db = _fake_db(
        case=case_record,
        documents=[first_document, first_document, second_document],
    )
    delete_document_record = AsyncMock()
    monkeypatch.setattr(retention_service, "_delete_document_record", delete_document_record)

    deleted = await retention_service.delete_case_for_org(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert deleted is True
    fake_db.case.find_first.assert_awaited_once_with(
        where={
            "org_id": "org_test_456",
            "OR": [
                {"id": "case_test_123"},
                {"legacy_source_document_id": "case_test_123"},
            ],
        }
    )
    fake_db.document.find_many.assert_awaited_once_with(
        where={
            "org_id": "org_test_456",
            "OR": [{"case_id": "case_test_123"}, {"id": "doc_test_123"}],
        }
    )
    fake_db.case.update.assert_awaited_once_with(
        where={"id": "case_test_123"},
        data={"legacy_source_document_id": None},
    )
    fake_db.caseanalysis.delete_many.assert_awaited_once_with(where={"case_id": "case_test_123"})
    assert delete_document_record.await_count == 2
    delete_document_record.assert_any_await(fake_db, first_document, clear_legacy_source=False)
    delete_document_record.assert_any_await(fake_db, second_document, clear_legacy_source=False)
    fake_db.case.delete.assert_awaited_once_with(where={"id": "case_test_123"})


@pytest.mark.asyncio
async def test_delete_case_for_org_returns_false_when_missing():
    fake_db = _fake_db(case=None)

    deleted = await retention_service.delete_case_for_org(
        db=fake_db,
        case_id="case_missing",
        org_id="org_test_456",
    )

    assert deleted is False
    fake_db.document.find_many.assert_not_awaited()
    fake_db.case.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_expired_cases_uses_updated_at_cutoff_and_org_scoped_delete(monkeypatch):
    cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first_case = _case(id="case_old_123", org_id="org_one")
    second_case = _case(id="case_old_456", org_id="org_two")
    fake_db = _fake_db()
    fake_db.case.find_many.return_value = [first_case, second_case]
    delete_case_mock = AsyncMock(side_effect=[True, False])
    monkeypatch.setattr(retention_service, "delete_case_for_org", delete_case_mock)

    deleted = await retention_service.delete_expired_cases(
        db=fake_db,
        cutoff=cutoff,
        limit=25,
    )

    assert deleted == 1
    fake_db.case.find_many.assert_awaited_once_with(
        where={"updated_at": {"lt": cutoff}},
        order={"updated_at": "asc"},
        take=25,
    )
    delete_case_mock.assert_any_await(fake_db, "case_old_123", "org_one")
    delete_case_mock.assert_any_await(fake_db, "case_old_456", "org_two")


@pytest.mark.asyncio
async def test_delete_expired_documents_uses_created_at_cutoff_and_org_scoped_delete(monkeypatch):
    cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first_document = _document(id="doc_old_123", org_id="org_one")
    second_document = _document(id="doc_old_456", org_id="org_two")
    fake_db = _fake_db(documents=[first_document, second_document])
    delete_document_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(retention_service, "delete_document_for_org", delete_document_mock)

    deleted = await retention_service.delete_expired_documents(
        db=fake_db,
        cutoff=cutoff,
        limit=10,
    )

    assert deleted == 2
    fake_db.document.find_many.assert_awaited_once_with(
        where={"created_at": {"lt": cutoff}},
        order={"created_at": "asc"},
        take=10,
    )
    delete_document_mock.assert_any_await(fake_db, "doc_old_123", "org_one")
    delete_document_mock.assert_any_await(fake_db, "doc_old_456", "org_two")


@pytest.mark.asyncio
async def test_delete_expired_audit_logs_returns_deleted_count():
    cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)
    fake_db = _fake_db()
    fake_db.auditlog.delete_many.return_value = SimpleNamespace(count=7)

    deleted = await retention_service.delete_expired_audit_logs(db=fake_db, cutoff=cutoff)

    assert deleted == 7
    fake_db.auditlog.delete_many.assert_awaited_once_with(where={"created_at": {"lt": cutoff}})


@pytest.mark.asyncio
async def test_enforce_retention_policy_applies_configured_windows(monkeypatch):
    now = datetime(2026, 4, 28, tzinfo=timezone.utc)
    settings = SimpleNamespace(
        RETENTION_CASE_DAYS=90,
        RETENTION_DOCUMENT_DAYS=30,
        RETENTION_AUDIT_LOG_DAYS=365,
        RETENTION_BATCH_SIZE=50,
    )
    fake_db = _fake_db()
    delete_cases_mock = AsyncMock(return_value=2)
    delete_documents_mock = AsyncMock(return_value=3)
    delete_audit_mock = AsyncMock(return_value=4)
    monkeypatch.setattr(retention_service, "delete_expired_cases", delete_cases_mock)
    monkeypatch.setattr(retention_service, "delete_expired_documents", delete_documents_mock)
    monkeypatch.setattr(retention_service, "delete_expired_audit_logs", delete_audit_mock)

    summary = await retention_service.enforce_retention_policy(
        db=fake_db,
        settings=settings,
        now=now,
    )

    assert summary.cases_deleted == 2
    assert summary.documents_deleted == 3
    assert summary.audit_logs_deleted == 4
    assert summary.case_cutoff == now - timedelta(days=90)
    assert summary.document_cutoff == now - timedelta(days=30)
    assert summary.audit_log_cutoff == now - timedelta(days=365)
    assert summary.model_dump()["case_cutoff"] == (now - timedelta(days=90)).isoformat()
    delete_cases_mock.assert_awaited_once_with(
        fake_db,
        cutoff=now - timedelta(days=90),
        limit=50,
    )
    delete_documents_mock.assert_awaited_once_with(
        fake_db,
        cutoff=now - timedelta(days=30),
        limit=50,
    )
    delete_audit_mock.assert_awaited_once_with(fake_db, cutoff=now - timedelta(days=365))


@pytest.mark.asyncio
async def test_enforce_retention_policy_skips_disabled_windows(monkeypatch):
    now = datetime(2026, 4, 28, tzinfo=timezone.utc)
    settings = SimpleNamespace(
        RETENTION_CASE_DAYS=0,
        RETENTION_DOCUMENT_DAYS=-1,
        RETENTION_AUDIT_LOG_DAYS=365,
        RETENTION_BATCH_SIZE=50,
    )
    fake_db = _fake_db()
    delete_cases_mock = AsyncMock()
    delete_documents_mock = AsyncMock()
    delete_audit_mock = AsyncMock(return_value=4)
    monkeypatch.setattr(retention_service, "delete_expired_cases", delete_cases_mock)
    monkeypatch.setattr(retention_service, "delete_expired_documents", delete_documents_mock)
    monkeypatch.setattr(retention_service, "delete_expired_audit_logs", delete_audit_mock)

    summary = await retention_service.enforce_retention_policy(
        db=fake_db,
        settings=settings,
        now=now,
    )

    assert summary.case_cutoff is None
    assert summary.document_cutoff is None
    assert summary.audit_log_cutoff == now - timedelta(days=365)
    assert summary.cases_deleted == 0
    assert summary.documents_deleted == 0
    assert summary.audit_logs_deleted == 4
    delete_cases_mock.assert_not_awaited()
    delete_documents_mock.assert_not_awaited()
    delete_audit_mock.assert_awaited_once()
