from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from models import CaseStatus
from services import case_service


def _timestamp() -> datetime:
    return datetime.now(timezone.utc)


def _make_case(**overrides):
    now = _timestamp()
    data = {
        "id": "case_test_123",
        "name": None,
        "status": CaseStatus.DRAFT.value,
        "applicant_name": None,
        "applicant_email": None,
        "applicant_phone": None,
        "legacy_source_document_id": None,
        "user_id": "user_test_123",
        "org_id": "org_test_456",
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.asyncio
async def test_create_case_defaults_name_from_applicant_name():
    created_case = _make_case(name="Jane Applicant", applicant_name="Jane Applicant")
    fake_db = SimpleNamespace(case=SimpleNamespace(create=AsyncMock(return_value=created_case)))

    result = await case_service.create_case(
        db=fake_db,
        user_id="user_test_123",
        org_id="org_test_456",
        applicant_name="Jane Applicant",
    )

    assert result is created_case
    create_args = fake_db.case.create.await_args.kwargs["data"]
    assert create_args["status"] == CaseStatus.DRAFT.value
    assert create_args["name"] == "Jane Applicant"
    assert create_args["applicant_name"] == "Jane Applicant"
    assert create_args["user_id"] == "user_test_123"
    assert create_args["org_id"] == "org_test_456"


@pytest.mark.asyncio
async def test_list_cases_scopes_and_orders_by_created_at():
    fake_db = SimpleNamespace(case=SimpleNamespace(find_many=AsyncMock(return_value=[])))

    await case_service.list_cases(db=fake_db, org_id="org_test_456", skip=3, limit=7)

    fake_db.case.find_many.assert_awaited_once_with(
        where={"org_id": "org_test_456"},
        order={"created_at": "desc"},
        skip=3,
        take=7,
    )


@pytest.mark.asyncio
async def test_get_case_by_id_for_org_uses_org_scope():
    case_record = _make_case()
    fake_db = SimpleNamespace(case=SimpleNamespace(find_first=AsyncMock(return_value=case_record)))

    result = await case_service.get_case_by_id_for_org(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is case_record
    fake_db.case.find_first.assert_awaited_once_with(
        where={
            "org_id": "org_test_456",
            "OR": [
                {"id": "case_test_123"},
                {"legacy_source_document_id": "case_test_123"},
            ],
        }
    )


@pytest.mark.asyncio
async def test_get_case_by_id_for_org_returns_none_for_blank_identifier():
    fake_db = SimpleNamespace(case=SimpleNamespace(find_first=AsyncMock()))

    result = await case_service.get_case_by_id_for_org(
        db=fake_db,
        case_id="   ",
        org_id="org_test_456",
    )

    assert result is None
    fake_db.case.find_first.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_case_applicant_info_sets_display_name_when_missing(monkeypatch):
    existing_case = _make_case(name=None)
    updated_case = _make_case(name="Jane Applicant", applicant_name="Jane Applicant")
    fake_db = SimpleNamespace(
        case=SimpleNamespace(update=AsyncMock(return_value=updated_case)),
    )
    monkeypatch.setattr(case_service, "get_case_by_id_for_org", AsyncMock(return_value=existing_case))

    result = await case_service.update_case_applicant_info(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
        applicant_name="Jane Applicant",
        applicant_email="jane@example.com",
        applicant_phone=None,
    )

    assert result is updated_case
    fake_db.case.update.assert_awaited_once_with(
        where={"id": "case_test_123"},
        data={
            "applicant_name": "Jane Applicant",
            "applicant_email": "jane@example.com",
            "applicant_phone": None,
            "name": "Jane Applicant",
        },
    )


@pytest.mark.asyncio
async def test_update_case_applicant_info_returns_none_when_case_missing(monkeypatch):
    fake_db = SimpleNamespace(case=SimpleNamespace(update=AsyncMock()))
    monkeypatch.setattr(case_service, "get_case_by_id_for_org", AsyncMock(return_value=None))

    result = await case_service.update_case_applicant_info(
        db=fake_db,
        case_id="case_missing",
        org_id="org_test_456",
        applicant_name="Jane Applicant",
    )

    assert result is None
    fake_db.case.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_case_applicant_info_updates_existing_case(monkeypatch):
    existing_case = _make_case(name="Manual Underwrite")
    updated_case = _make_case(
        name="Manual Underwrite",
        applicant_name="Jane Applicant",
        applicant_email="jane@example.com",
        applicant_phone="+1-555-0100",
    )
    fake_db = SimpleNamespace(case=SimpleNamespace(update=AsyncMock(return_value=updated_case)))
    monkeypatch.setattr(case_service, "get_case_by_id_for_org", AsyncMock(return_value=existing_case))

    result = await case_service.update_case_applicant_info(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
        applicant_name="Jane Applicant",
        applicant_email="jane@example.com",
        applicant_phone="+1-555-0100",
    )

    assert result is updated_case
    fake_db.case.update.assert_awaited_once_with(
        where={"id": "case_test_123"},
        data={
            "applicant_name": "Jane Applicant",
            "applicant_email": "jane@example.com",
            "applicant_phone": "+1-555-0100",
        },
    )


@pytest.mark.asyncio
async def test_update_case_applicant_info_only_updates_provided_fields(monkeypatch):
    existing_case = _make_case(
        name="Manual Underwrite",
        applicant_name="Jane Applicant",
        applicant_email="jane@example.com",
        applicant_phone="+1-555-0100",
    )
    updated_case = _make_case(
        name="Manual Underwrite",
        applicant_name="Jane Applicant",
        applicant_email="jane@example.com",
        applicant_phone="+1-555-0101",
    )
    fake_db = SimpleNamespace(case=SimpleNamespace(update=AsyncMock(return_value=updated_case)))
    monkeypatch.setattr(case_service, "get_case_by_id_for_org", AsyncMock(return_value=existing_case))

    result = await case_service.update_case_applicant_info(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
        applicant_phone="+1-555-0101",
    )

    assert result is updated_case
    fake_db.case.update.assert_awaited_once_with(
        where={"id": "case_test_123"},
        data={
            "applicant_phone": "+1-555-0101",
        },
    )
