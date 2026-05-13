from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from models import CaseStatus
from services import case_analysis_service, case_report_service
from tests.test_case_analysis_service import _build_case_read_model


def test_build_case_report_payload_shapes_sections_and_print_export():
    read_model = _build_case_read_model()

    report = case_report_service.build_case_report_payload(read_model)

    assert report.header.case_id == "case_test_123"
    assert report.header.report_status == "provisional"
    assert report.latest_analysis.is_final is False
    assert report.overview.decision_status == "manual_review"
    assert any(section.key == "decision" for section in report.sections)
    assert any(section.key == "documents" for section in report.sections)
    assert report.print.filename.endswith(".pdf")
    assert report.print.sections


def test_build_case_report_payload_prefers_authoritative_snapshot():
    read_model = _build_case_read_model()
    read_model.authoritative_analysis = case_analysis_service.build_case_analysis_snapshot(
        read_model,
        is_final=True,
        snapshot_kind="case_finalized",
        case_status=CaseStatus.FINALIZED.value,
    )

    report = case_report_service.build_case_report_payload(read_model)

    assert report.header.report_status == "finalized"
    assert report.latest_analysis.is_final is True
    assert report.header.generated_from == "authoritative_analysis"


@pytest.mark.asyncio
async def test_get_case_report_returns_none_when_case_missing(monkeypatch):
    monkeypatch.setattr(
        case_report_service,
        "get_case_read_model",
        AsyncMock(return_value=None),
    )

    result = await case_report_service.get_case_report(
        db=SimpleNamespace(),
        case_id="case_missing",
        org_id="org_test_456",
    )

    assert result is None
