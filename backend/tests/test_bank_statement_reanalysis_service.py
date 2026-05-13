from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import bank_statement_reanalysis_service


@pytest.mark.asyncio
async def test_select_bank_statement_documents_resolves_legacy_case_ids_and_skips_processing():
    fake_db = SimpleNamespace(
        case=SimpleNamespace(
            find_many=AsyncMock(
                return_value=[SimpleNamespace(id="case_test_123")]
            )
        ),
        document=SimpleNamespace(
            find_many=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        id="doc_processing_123",
                        case_id="case_test_123",
                        org_id="org_test_456",
                        status="processing",
                        original_filename="processing-bank-statement.pdf",
                    ),
                    SimpleNamespace(
                        id="doc_ready_123",
                        case_id="case_test_123",
                        org_id="org_test_456",
                        status="analyzed",
                        original_filename="ready-bank-statement.pdf",
                    ),
                ]
            )
        ),
    )

    result = await bank_statement_reanalysis_service.select_bank_statement_documents(
        db=fake_db,
        case_ids=["legacy_doc_123"],
        org_ids=["org_test_456"],
    )

    assert [document.id for document in result] == ["doc_ready_123"]
    fake_db.case.find_many.assert_awaited_once()
    fake_db.document.find_many.assert_awaited_once_with(
        where={
            "document_type": "bank_statement",
            "org_id": {"in": ["org_test_456"]},
            "case_id": {"in": ["case_test_123"]},
        },
        order={"created_at": "asc"},
    )


@pytest.mark.asyncio
async def test_rerun_bank_statement_documents_reports_new_document_and_case_scores(monkeypatch):
    fake_db = SimpleNamespace()
    document = SimpleNamespace(
        id="doc_bank_123",
        case_id="case_test_123",
        org_id="org_test_456",
    )
    old_analysis = SimpleNamespace(id="analysis_old_123", risk_score=81)
    new_analysis = SimpleNamespace(id="analysis_new_123", risk_score=24)
    case_snapshot = SimpleNamespace(
        id="case_live_123",
        risk_score=24,
        is_final=False,
    )

    get_analysis_mock = AsyncMock(side_effect=[old_analysis, new_analysis])
    monkeypatch.setattr(
        bank_statement_reanalysis_service,
        "get_analysis_by_document",
        get_analysis_mock,
    )
    rerun_mock = AsyncMock(return_value="completed")
    monkeypatch.setattr(
        bank_statement_reanalysis_service,
        "run_analysis_for_stored_document",
        rerun_mock,
    )
    case_latest_mock = AsyncMock(return_value=case_snapshot)
    monkeypatch.setattr(
        bank_statement_reanalysis_service,
        "get_latest_case_analysis_for_org",
        case_latest_mock,
    )

    results = await bank_statement_reanalysis_service.rerun_bank_statement_documents(
        db=fake_db,
        documents=[document],
    )

    assert len(results) == 1
    assert results[0].document_id == "doc_bank_123"
    assert results[0].previous_analysis_id == "analysis_old_123"
    assert results[0].previous_risk_score == 81
    assert results[0].new_analysis_id == "analysis_new_123"
    assert results[0].new_risk_score == 24
    assert results[0].case_latest_analysis_id == "case_live_123"
    assert results[0].case_latest_risk_score == 24
    assert results[0].case_latest_is_final is False
    rerun_mock.assert_awaited_once_with(
        db=fake_db,
        document_id="doc_bank_123",
        force_reanalysis=True,
    )
