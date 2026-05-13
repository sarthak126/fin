from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from models import CaseStatus
from schemas.analysis import AnalysisResponse
from schemas.case import CaseDetail
from schemas.case_read_model import (
    CaseApplicantIntake,
    CaseDocumentReadModel,
    CaseProvisionalInsights,
    CaseReadModel,
    CrossDocumentComparison,
    CrossDocumentComparisonValue,
    FraudSignal,
    FraudSignalEvidence,
    SupportedDocumentCompleteness,
    SupportedDocumentRequirement,
)
from services import case_analysis_service


def _timestamp() -> datetime:
    return datetime.now(timezone.utc)


def _build_case_read_model() -> CaseReadModel:
    now = _timestamp()
    latest_analysis = AnalysisResponse(
        id="analysis_doc_salary_123",
        document_id="doc_salary_123",
        risk_score=46,
        confidence=0.74,
        recommendation="review",
        decision_status="manual_review",
        decision_recommendation="Manual review is recommended before approval.",
        decision_reason="Income documents conflict with banking evidence.",
        extraction_confidence=0.74,
        risk_confidence=0.74,
        data_completeness=0.74,
        required_followups_json=json.dumps(["Verify payslip income against bank credits."]),
        analysis_limitations_json=json.dumps([]),
        extracted_fields={"monthly_income": 70000, "employer_name": "Acme Corp"},
        risk_alerts=[{"severity": "medium", "message": "Income mismatch needs review."}],
        summary="Income documents conflict with banking evidence.",
        processing_time_seconds=1.2,
        model_used="gemini-test",
        created_at=now,
    )
    return CaseReadModel(
        case=CaseDetail(
            id="case_test_123",
            name="Jane Applicant",
            status="collecting",
            applicant_name="Jane Applicant",
            applicant_email="jane@example.com",
            applicant_phone=None,
            legacy_source_document_id=None,
            created_at=now,
            updated_at=now,
            user_id="user_test_123",
            org_id="org_test_456",
        ),
        applicant_intake=CaseApplicantIntake(
            applicant_name="Jane Applicant",
            applicant_email="jane@example.com",
            applicant_phone=None,
            completed_fields=["applicant_name", "applicant_email"],
            missing_fields=["applicant_phone"],
            completeness=0.6667,
        ),
        documents=[
            CaseDocumentReadModel(
                id="doc_salary_123",
                case_id="case_test_123",
                filename="stored-doc-salary-123.pdf",
                original_filename="salary-slip.pdf",
                file_url="secure://documents/stored-doc-salary-123.pdf",
                file_type="application/pdf",
                document_type="salary_slip",
                status="analyzed",
                file_size_bytes=2048,
                created_at=now,
                updated_at=now,
                user_id="user_test_123",
                org_id="org_test_456",
                latest_analysis=latest_analysis,
            )
        ],
        supported_document_completeness=SupportedDocumentCompleteness(
            provided_score=0.3333,
            analyzed_score=0.3333,
            provided_requirement_count=1,
            analyzed_requirement_count=1,
            total_requirement_count=3,
            present_document_types=["salary_slip"],
            missing_document_types=["bank_statement", "id_document", "tax_return", "employment_letter", "income_proof"],
            missing_requirement_keys=["identity", "banking"],
            pending_requirement_keys=[],
            requirements=[
                SupportedDocumentRequirement(
                    key="income",
                    label="Income support",
                    accepted_document_types=["salary_slip", "tax_return", "employment_letter", "income_proof"],
                    document_ids=["doc_salary_123"],
                    provided_count=1,
                    analyzed_count=1,
                    status="complete",
                )
            ],
        ),
        cross_document_comparisons=[
            CrossDocumentComparison(
                field="monthly_income",
                label="Monthly income",
                status="insufficient_data",
                summary="Only one analyzed document currently reports monthly income.",
                values=[
                    CrossDocumentComparisonValue(
                        document_id="doc_salary_123",
                        document_type="salary_slip",
                        original_filename="salary-slip.pdf",
                        analysis_id="analysis_doc_salary_123",
                        value=70000,
                    )
                ],
            )
        ],
        fraud_signals=[
            FraudSignal(
                key="income_discrepancy",
                label="Income discrepancy > 20%",
                severity="medium",
                summary="Monthly income differs materially across the available evidence.",
                details="Income values are not aligned across the case evidence.",
                recommended_action="Verify the salary slip income against the recurring bank credits.",
                evidence=[
                    FraudSignalEvidence(
                        source_type="document",
                        source_label="Salary slip",
                        field="monthly_income",
                        value=70000,
                        document_id="doc_salary_123",
                        document_type="salary_slip",
                        original_filename="salary-slip.pdf",
                        analysis_id="analysis_doc_salary_123",
                    )
                ],
            )
        ],
        provisional_insights=CaseProvisionalInsights(
            decision_status="manual_review",
            recommendation="review",
            summary="Provisional case outcome is manual review.",
            blockers=[
                "Missing supporting documents: identity verification, bank statements.",
            ],
            followups=[
                "Request identity verification.",
                "Request bank statements.",
                "Verify payslip income against bank credits.",
            ],
            highest_risk_score=46,
            average_risk_score=46,
            analyzed_document_count=1,
            pending_document_count=0,
            failed_document_count=0,
            conflict_fields=[],
            fraud_signal_count=1,
            fraud_signal_keys=["income_discrepancy"],
            document_decision_counts={"manual_review": 1},
        ),
    )


@pytest.mark.asyncio
async def test_persist_provisional_case_analysis_creates_non_final_snapshot(monkeypatch):
    read_model = _build_case_read_model()
    fake_record = SimpleNamespace(id="case_analysis_123")
    fake_db = SimpleNamespace(
        caseanalysis=SimpleNamespace(create=AsyncMock(return_value=fake_record))
    )
    monkeypatch.setattr(
        case_analysis_service,
        "get_case_read_model",
        AsyncMock(return_value=read_model),
    )

    result = await case_analysis_service.persist_provisional_case_analysis(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is fake_record
    create_args = fake_db.caseanalysis.create.await_args.kwargs["data"]
    assert create_args["case_id"] == "case_test_123"
    assert create_args["case_status"] == "collecting"
    assert create_args["is_final"] is False
    assert create_args["risk_score"] == 46
    assert create_args["recommendation"] == "review"
    assert create_args["decision_status"] == "manual_review"
    assert json.loads(create_args["required_followups_json"]) == [
        "Request identity verification.",
        "Request bank statements.",
        "Verify payslip income against bank credits.",
    ]
    assert json.loads(create_args["analysis_limitations_json"]) == [
        "Missing supporting documents: identity verification, bank statements.",
    ]

    extracted_fields = json.loads(create_args["extracted_fields"])
    assert extracted_fields["snapshot_kind"] == "case_provisional"
    assert extracted_fields["is_final"] is False
    assert extracted_fields["provisional_insights"]["decision_status"] == "manual_review"
    assert extracted_fields["documents"][0]["analysis_id"] == "analysis_doc_salary_123"

    risk_alerts = json.loads(create_args["risk_alerts"])
    assert risk_alerts == [
        {
            "key": "income_discrepancy",
            "severity": "medium",
            "message": "Monthly income differs materially across the available evidence.",
        }
    ]


@pytest.mark.asyncio
async def test_persist_provisional_case_analysis_for_document_only_runs_for_supported_types(monkeypatch):
    fake_db = SimpleNamespace()
    persist_mock = AsyncMock(return_value="stored")
    monkeypatch.setattr(
        case_analysis_service,
        "persist_provisional_case_analysis",
        persist_mock,
    )

    supported_result = await case_analysis_service.persist_provisional_case_analysis_for_document(
        db=fake_db,
        document=SimpleNamespace(
            case_id="case_test_123",
            org_id="org_test_456",
            document_type="bank_statement",
        ),
    )
    unsupported_result = await case_analysis_service.persist_provisional_case_analysis_for_document(
        db=fake_db,
        document=SimpleNamespace(
            case_id="case_test_123",
            org_id="org_test_456",
            document_type="other",
        ),
    )

    assert supported_result == "stored"
    assert unsupported_result is None
    persist_mock.assert_awaited_once_with(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )


@pytest.mark.asyncio
async def test_prepare_case_for_forced_document_reanalysis_only_runs_for_supported_types(monkeypatch):
    fake_db = SimpleNamespace()
    invalidate_mock = AsyncMock(return_value="invalidated")
    monkeypatch.setattr(
        case_analysis_service,
        "invalidate_final_case_analysis_for_case",
        invalidate_mock,
    )

    supported_result = await case_analysis_service.prepare_case_for_forced_document_reanalysis(
        db=fake_db,
        document=SimpleNamespace(
            case_id="case_test_123",
            org_id="org_test_456",
            document_type="bank_statement",
        ),
    )
    unsupported_result = await case_analysis_service.prepare_case_for_forced_document_reanalysis(
        db=fake_db,
        document=SimpleNamespace(
            case_id="case_test_123",
            org_id="org_test_456",
            document_type="other",
        ),
    )

    assert supported_result == "invalidated"
    assert unsupported_result is None
    invalidate_mock.assert_awaited_once_with(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )


@pytest.mark.asyncio
async def test_finalize_case_and_get_read_model_creates_final_snapshot(monkeypatch):
    finalized_read_model = _build_case_read_model()
    finalized_read_model.case.status = CaseStatus.FINALIZED
    existing_case = SimpleNamespace(id="case_test_123", status=CaseStatus.COLLECTING.value)
    fake_db = SimpleNamespace(
        case=SimpleNamespace(update=AsyncMock(return_value=existing_case)),
        caseanalysis=SimpleNamespace(
            find_many=AsyncMock(return_value=[]),
            update=AsyncMock(),
            create=AsyncMock(return_value=SimpleNamespace(id="case_analysis_final_123")),
        ),
    )
    monkeypatch.setattr(
        case_analysis_service,
        "get_case_by_id_for_org",
        AsyncMock(return_value=existing_case),
    )
    monkeypatch.setattr(
        case_analysis_service,
        "get_case_read_model",
        AsyncMock(side_effect=[finalized_read_model, finalized_read_model]),
    )

    result = await case_analysis_service.finalize_case_and_get_read_model(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is finalized_read_model
    fake_db.case.update.assert_awaited_once_with(
        where={"id": "case_test_123"},
        data={"status": CaseStatus.FINALIZED.value},
    )
    create_args = fake_db.caseanalysis.create.await_args.kwargs["data"]
    assert create_args["case_id"] == "case_test_123"
    assert create_args["case_status"] == CaseStatus.FINALIZED.value
    assert create_args["is_final"] is True
    assert create_args["model_used"] == "case-final-aggregate-v1"

    extracted_fields = json.loads(create_args["extracted_fields"])
    assert extracted_fields["snapshot_kind"] == "case_finalized"
    assert extracted_fields["is_final"] is True
    assert extracted_fields["case"]["status"] == CaseStatus.FINALIZED.value


@pytest.mark.asyncio
async def test_finalize_case_and_get_read_model_uses_canonical_case_id_after_legacy_lookup(monkeypatch):
    finalized_read_model = _build_case_read_model()
    finalized_read_model.case.status = CaseStatus.FINALIZED
    existing_case = SimpleNamespace(
        id="case_test_123",
        status=CaseStatus.COLLECTING.value,
        legacy_source_document_id="legacy_doc_123",
    )
    fake_db = SimpleNamespace(
        case=SimpleNamespace(update=AsyncMock(return_value=existing_case)),
        caseanalysis=SimpleNamespace(
            find_many=AsyncMock(return_value=[]),
            update=AsyncMock(),
            create=AsyncMock(return_value=SimpleNamespace(id="case_analysis_final_legacy_123")),
        ),
    )
    monkeypatch.setattr(
        case_analysis_service,
        "get_case_by_id_for_org",
        AsyncMock(return_value=existing_case),
    )
    monkeypatch.setattr(
        case_analysis_service,
        "get_case_read_model",
        AsyncMock(side_effect=[finalized_read_model, finalized_read_model]),
    )

    result = await case_analysis_service.finalize_case_and_get_read_model(
        db=fake_db,
        case_id="legacy_doc_123",
        org_id="org_test_456",
    )

    assert result is finalized_read_model
    fake_db.case.update.assert_awaited_once_with(
        where={"id": "case_test_123"},
        data={"status": CaseStatus.FINALIZED.value},
    )
    fake_db.caseanalysis.find_many.assert_awaited_once_with(
        where={
            "case_id": "case_test_123",
            "is_final": True,
        }
    )
    get_case_read_model_mock = case_analysis_service.get_case_read_model
    assert get_case_read_model_mock.await_args_list[0].kwargs == {
        "db": fake_db,
        "case_id": "case_test_123",
        "org_id": "org_test_456",
    }
    assert get_case_read_model_mock.await_args_list[1].kwargs == {
        "db": fake_db,
        "case_id": "case_test_123",
        "org_id": "org_test_456",
    }


@pytest.mark.asyncio
async def test_invalidate_final_case_analysis_for_case_marks_snapshots_non_final(monkeypatch):
    finalized_case = SimpleNamespace(id="case_test_123", status=CaseStatus.FINALIZED.value)
    updated_case = SimpleNamespace(id="case_test_123", status=CaseStatus.COLLECTING.value)
    fake_db = SimpleNamespace(
        case=SimpleNamespace(update=AsyncMock(return_value=updated_case)),
        caseanalysis=SimpleNamespace(
            find_many=AsyncMock(
                return_value=[
                    SimpleNamespace(id="case_analysis_final_123"),
                    SimpleNamespace(id="case_analysis_final_456"),
                ]
            ),
            update=AsyncMock(),
        ),
    )
    monkeypatch.setattr(
        case_analysis_service,
        "get_case_by_id_for_org",
        AsyncMock(return_value=finalized_case),
    )

    result = await case_analysis_service.invalidate_final_case_analysis_for_case(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is updated_case
    assert fake_db.caseanalysis.update.await_count == 2
    assert fake_db.caseanalysis.update.await_args_list[0].kwargs == {
        "where": {"id": "case_analysis_final_123"},
        "data": {"is_final": False},
    }
    assert fake_db.caseanalysis.update.await_args_list[1].kwargs == {
        "where": {"id": "case_analysis_final_456"},
        "data": {"is_final": False},
    }
    fake_db.case.update.assert_awaited_once_with(
        where={"id": "case_test_123"},
        data={"status": CaseStatus.COLLECTING.value},
    )


@pytest.mark.asyncio
async def test_get_latest_case_analysis_for_org_builds_live_provisional_snapshot(monkeypatch):
    read_model = _build_case_read_model()
    monkeypatch.setattr(
        case_analysis_service,
        "get_case_read_model",
        AsyncMock(return_value=read_model),
    )

    result = await case_analysis_service.get_latest_case_analysis_for_org(
        db=SimpleNamespace(),
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is not None
    assert result.case_id == "case_test_123"
    assert result.is_final is False
    assert result.decision_status == "manual_review"
    assert result.extracted_fields["snapshot_kind"] == "case_live_provisional"


@pytest.mark.asyncio
async def test_get_latest_case_analysis_for_org_prefers_authoritative_snapshot(monkeypatch):
    read_model = _build_case_read_model()
    authoritative = case_analysis_service.build_case_analysis_snapshot(
        read_model,
        is_final=True,
        snapshot_kind="case_finalized",
        case_status=CaseStatus.FINALIZED.value,
    )
    read_model.authoritative_analysis = authoritative
    monkeypatch.setattr(
        case_analysis_service,
        "get_case_read_model",
        AsyncMock(return_value=read_model),
    )

    result = await case_analysis_service.get_latest_case_analysis_for_org(
        db=SimpleNamespace(),
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is authoritative
