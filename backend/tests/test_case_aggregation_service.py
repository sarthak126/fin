from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import case_aggregation_service


def _timestamp() -> datetime:
    return datetime.now(timezone.utc)


def _make_case(**overrides):
    now = _timestamp()
    data = {
        "id": "case_test_123",
        "name": "Jane Applicant",
        "status": "draft",
        "applicant_name": "Jane Applicant",
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


def _make_document(**overrides):
    now = _timestamp()
    data = {
        "id": "doc_test_123",
        "case_id": "case_test_123",
        "filename": "stored-doc-test-123.pdf",
        "original_filename": "statement.pdf",
        "file_url": "secure://documents/stored-doc-test-123.pdf",
        "file_type": "application/pdf",
        "document_type": "bank_statement",
        "status": "analyzed",
        "file_size_bytes": 2048,
        "created_at": now,
        "updated_at": now,
        "user_id": "user_test_123",
        "org_id": "org_test_456",
        "analyses": [],
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class FakeAnalysisRecord:
    def __init__(
        self,
        *,
        analysis_id: str,
        document_id: str,
        extracted_fields: dict,
        decision_status: str,
        decision_recommendation: str,
        decision_reason: str,
        recommendation: str,
        confidence: float,
        risk_score: float,
        required_followups: list[str] | None = None,
        analysis_limitations: list[str] | None = None,
        risk_alerts: list[dict] | None = None,
    ):
        now = _timestamp()
        self._data = {
            "id": analysis_id,
            "document_id": document_id,
            "risk_score": risk_score,
            "confidence": confidence,
            "recommendation": recommendation,
            "decision_status": decision_status,
            "decision_recommendation": decision_recommendation,
            "decision_reason": decision_reason,
            "extraction_confidence": confidence,
            "risk_confidence": confidence,
            "data_completeness": confidence,
            "required_followups_json": json.dumps(required_followups or []),
            "analysis_limitations_json": json.dumps(analysis_limitations or []),
            "extracted_fields": json.dumps(extracted_fields),
            "risk_alerts": json.dumps(risk_alerts or []),
            "summary": decision_reason,
            "processing_time_seconds": 1.2,
            "model_used": "test-model",
            "raw_response": json.dumps(extracted_fields),
            "created_at": now,
        }

    def model_dump(self) -> dict:
        return dict(self._data)


@pytest.mark.asyncio
async def test_get_case_read_model_returns_none_when_case_missing():
    fake_db = SimpleNamespace(
        case=SimpleNamespace(find_first=AsyncMock(return_value=None)),
        document=SimpleNamespace(find_many=AsyncMock(return_value=[])),
        caseanalysis=SimpleNamespace(find_first=AsyncMock(return_value=None)),
    )

    result = await case_aggregation_service.get_case_read_model(
        db=fake_db,
        case_id="case_missing",
        org_id="org_test_456",
    )

    assert result is None
    fake_db.document.find_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_case_read_model_builds_completeness_comparisons_and_provisional_insights():
    case_record = _make_case()
    bank_analysis = FakeAnalysisRecord(
        analysis_id="analysis_bank_123",
        document_id="doc_bank_123",
        decision_status="approve",
        decision_recommendation="Proceed with approval.",
        decision_reason="Banking signals are stable.",
        recommendation="approve",
        confidence=0.91,
        risk_score=28,
        extracted_fields={
            "decision": {
                "decision_status": "approve",
                "decision_recommendation": "Proceed with approval.",
                "decision_reason": "Banking signals are stable.",
                "extraction_confidence": 0.91,
                "risk_confidence": 0.91,
                "data_completeness": 0.91,
                "required_followups": [],
                "analysis_limitations": [],
            },
            "statement_summary": {
                "coverage_days": 120,
            },
            "transaction_insights": {
                "income": {
                    "monthly_estimate": "50000",
                    "annual_estimate": 600000,
                    "income_type": "salary",
                },
                "balance": {
                    "average": 12000,
                },
                "expenses": {
                    "emi": 15000,
                },
                "dti": {
                    "value": 0.30,
                    "label": "moderate",
                },
            },
            "risk_findings": {},
            "reasoning": {
                "summary": "Banking signals are stable.",
                "narrative": [],
                "required_followups": [],
                "analysis_limitations": [],
            },
            "transactions": [],
        },
    )
    salary_analysis = FakeAnalysisRecord(
        analysis_id="analysis_salary_123",
        document_id="doc_salary_123",
        decision_status="manual_review",
        decision_recommendation="Manual review is recommended before approval.",
        decision_reason="Income documents conflict with banking evidence.",
        recommendation="review",
        confidence=0.74,
        risk_score=46,
        required_followups=["Verify payslip income against bank credits."],
        extracted_fields={
            "monthly_income": 70000,
            "annual_income": 840000,
            "employment_type": "salary",
            "employer_name": "Acme Corp",
            "avg_monthly_balance": 11000,
            "existing_emis": 16000,
            "debt_to_income_ratio": 0.29,
            "document_type_detected": "salary_slip",
        },
    )
    documents = [
        _make_document(
            id="doc_id_123",
            filename="stored-doc-id-123.pdf",
            original_filename="passport.pdf",
            document_type="id_document",
            status="pending",
            analyses=[],
        ),
        _make_document(
            id="doc_salary_123",
            filename="stored-doc-salary-123.pdf",
            original_filename="salary-slip.pdf",
            document_type="salary_slip",
            status="analyzed",
            analyses=[salary_analysis],
        ),
        _make_document(
            id="doc_bank_123",
            filename="stored-doc-bank-123.pdf",
            original_filename="bank-statement.pdf",
            document_type="bank_statement",
            status="analyzed",
            analyses=[bank_analysis],
        ),
    ]
    fake_db = SimpleNamespace(
        case=SimpleNamespace(find_first=AsyncMock(return_value=case_record)),
        document=SimpleNamespace(find_many=AsyncMock(return_value=documents)),
        caseanalysis=SimpleNamespace(find_first=AsyncMock(return_value=None)),
    )

    result = await case_aggregation_service.get_case_read_model(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is not None
    assert result.case.id == "case_test_123"
    assert result.applicant_intake.completed_fields == ["applicant_name"]
    assert result.applicant_intake.missing_fields == ["applicant_email", "applicant_phone"]
    assert result.supported_document_completeness.provided_score == 1.0
    assert result.supported_document_completeness.analyzed_score == pytest.approx(0.6667, rel=1e-3)
    assert result.supported_document_completeness.pending_requirement_keys == ["identity"]
    assert len(result.documents) == 3

    comparison_by_field = {comparison.field: comparison for comparison in result.cross_document_comparisons}
    assert comparison_by_field["monthly_income"].status == "mismatch"
    assert comparison_by_field["employment_type"].status == "consistent"
    assert comparison_by_field["employer_name"].status == "insufficient_data"

    assert result.provisional_insights.decision_status == "manual_review"
    assert result.provisional_insights.document_decision_counts == {
        "approve": 1,
        "manual_review": 1,
    }
    assert "Monthly income" in result.provisional_insights.conflict_fields
    assert any("applicant intake is incomplete" in blocker.lower() for blocker in result.provisional_insights.blockers)
    assert any("identity verification" in blocker.lower() for blocker in result.provisional_insights.blockers)
    assert "Collect applicant email." in result.provisional_insights.followups
    assert "Collect applicant phone." in result.provisional_insights.followups
    assert "Finish analysis for identity verification." in result.provisional_insights.followups
    assert "Verify payslip income against bank credits." in result.provisional_insights.followups


@pytest.mark.asyncio
async def test_get_case_read_model_surfaces_insufficient_history_and_missing_docs_followups():
    case_record = _make_case(
        applicant_email="jane@example.com",
        applicant_phone="+1-555-0100",
    )
    bank_analysis = FakeAnalysisRecord(
        analysis_id="analysis_bank_short_123",
        document_id="doc_bank_short_123",
        decision_status="insufficient_history",
        decision_recommendation="Collect more document history before making a final decision.",
        decision_reason="Statement history is too short for full underwriting.",
        recommendation="review",
        confidence=0.4,
        risk_score=52,
        required_followups=["Request 3-6 months of bank statement history."],
        analysis_limitations=["Statement coverage is too short."],
        extracted_fields={
            "decision": {
                "decision_status": "insufficient_history",
                "decision_recommendation": "Collect more document history before making a final decision.",
                "decision_reason": "Statement history is too short for full underwriting.",
                "extraction_confidence": 0.4,
                "risk_confidence": 0.4,
                "data_completeness": 0.4,
                "required_followups": ["Request 3-6 months of bank statement history."],
                "analysis_limitations": ["Statement coverage is too short."],
            },
            "statement_summary": {
                "coverage_days": 8,
            },
            "transaction_insights": {
                "income": {
                    "monthly_estimate": None,
                    "annual_estimate": None,
                    "income_type": "unknown",
                },
                "balance": {
                    "average": 1580,
                },
                "expenses": {
                    "emi": 0,
                },
                "dti": {
                    "value": None,
                    "label": "unknown",
                },
            },
            "risk_findings": {},
            "reasoning": {
                "summary": "Statement history is too short for full underwriting.",
                "narrative": [],
                "required_followups": ["Request 3-6 months of bank statement history."],
                "analysis_limitations": ["Statement coverage is too short."],
            },
            "transactions": [],
        },
    )
    documents = [
        _make_document(
            id="doc_bank_short_123",
            filename="stored-doc-bank-short-123.pdf",
            original_filename="bank-statement-short.pdf",
            document_type="bank_statement",
            status="analyzed",
            analyses=[bank_analysis],
        ),
    ]
    fake_db = SimpleNamespace(
        case=SimpleNamespace(find_first=AsyncMock(return_value=case_record)),
        document=SimpleNamespace(find_many=AsyncMock(return_value=documents)),
        caseanalysis=SimpleNamespace(find_first=AsyncMock(return_value=None)),
    )

    result = await case_aggregation_service.get_case_read_model(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is not None
    assert result.applicant_intake.completeness == 1.0
    assert result.supported_document_completeness.provided_score == pytest.approx(0.3333, rel=1e-3)
    assert result.supported_document_completeness.missing_requirement_keys == ["identity", "income"]
    assert result.provisional_insights.decision_status == "insufficient_history"
    assert "Request 3-6 months of bank statement history." in result.provisional_insights.followups
    assert "Request identity verification." in result.provisional_insights.followups
    assert "Request income support." in result.provisional_insights.followups
    assert result.provisional_insights.fraud_signal_count == 0


@pytest.mark.asyncio
async def test_applicant_phone_validation_rejects_email_like_phone_value():
    case_record = _make_case(
        applicant_email="jane@example.com",
        applicant_phone="sarthak14b7@gmail.com",
    )
    fake_db = SimpleNamespace(
        case=SimpleNamespace(find_first=AsyncMock(return_value=case_record)),
        document=SimpleNamespace(find_many=AsyncMock(return_value=[])),
        caseanalysis=SimpleNamespace(find_first=AsyncMock(return_value=None)),
    )

    result = await case_aggregation_service.get_case_read_model(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is not None
    assert result.applicant_intake.completed_fields == ["applicant_name", "applicant_email"]
    assert result.applicant_intake.missing_fields == ["applicant_phone"]
    assert "Collect applicant phone." in result.provisional_insights.followups


@pytest.mark.asyncio
async def test_document_followup_builder_excludes_risk_explanation_strings_from_actions():
    case_record = _make_case(
        applicant_email="jane@example.com",
        applicant_phone="+1-555-0100",
    )
    bank_analysis = FakeAnalysisRecord(
        analysis_id="analysis_bank_risk_lines_123",
        document_id="doc_bank_risk_lines_123",
        decision_status="reject",
        decision_recommendation="Do not approve this application.",
        decision_reason="Risk is high.",
        recommendation="reject",
        confidence=0.85,
        risk_score=82,
        required_followups=[
            "High DTI.",
            "No verified income detected.",
            "Request income support.",
        ],
        extracted_fields={
            "decision": {
                "decision_status": "reject",
                "decision_recommendation": "Do not approve this application.",
                "decision_reason": "Risk is high.",
                "extraction_confidence": 0.85,
                "risk_confidence": 0.85,
                "data_completeness": 0.85,
                "required_followups": [
                    "High DTI.",
                    "No verified income detected.",
                    "Request income support.",
                ],
                "analysis_limitations": [],
            },
            "statement_summary": {"coverage_days": 120},
            "transaction_insights": {
                "income": {
                    "monthly_estimate": None,
                    "verified_monthly_estimate": None,
                    "annual_estimate": None,
                    "income_type": "unstable",
                },
                "balance": {"average": 1500},
                "expenses": {"emi": 12000},
                "dti": {"value": 1.2, "label": "extreme", "reliability": "unverified"},
            },
            "risk_findings": {},
            "reasoning": {
                "summary": "Risk is high.",
                "narrative": [],
                "required_followups": [
                    "High DTI.",
                    "No verified income detected.",
                    "Request income support.",
                ],
                "analysis_limitations": [],
            },
            "transactions": [],
        },
    )
    documents = [
        _make_document(
            id="doc_bank_risk_lines_123",
            filename="stored-doc-bank-risk-lines-123.pdf",
            original_filename="bank-statement.pdf",
            document_type="bank_statement",
            status="analyzed",
            analyses=[bank_analysis],
        ),
    ]
    fake_db = SimpleNamespace(
        case=SimpleNamespace(find_first=AsyncMock(return_value=case_record)),
        document=SimpleNamespace(find_many=AsyncMock(return_value=documents)),
        caseanalysis=SimpleNamespace(find_first=AsyncMock(return_value=None)),
    )

    result = await case_aggregation_service.get_case_read_model(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is not None
    assert "Request income support." in result.provisional_insights.followups
    assert "High DTI." not in result.provisional_insights.followups
    assert "No verified income detected." not in result.provisional_insights.followups


@pytest.mark.asyncio
async def test_get_case_read_model_builds_v1_fraud_signals_for_name_employer_and_income_mismatches():
    case_record = _make_case(
        applicant_name="Jane Applicant",
        applicant_email="jane@example.com",
        applicant_phone="+1-555-0100",
    )
    bank_analysis = FakeAnalysisRecord(
        analysis_id="analysis_bank_456",
        document_id="doc_bank_456",
        decision_status="approve",
        decision_recommendation="Proceed with approval.",
        decision_reason="Recurring salary credits were detected.",
        recommendation="approve",
        confidence=0.88,
        risk_score=30,
        extracted_fields={
            "decision": {
                "decision_status": "approve",
                "decision_recommendation": "Proceed with approval.",
                "decision_reason": "Recurring salary credits were detected.",
                "extraction_confidence": 0.88,
                "risk_confidence": 0.88,
                "data_completeness": 0.88,
                "required_followups": [],
                "analysis_limitations": [],
            },
            "statement_summary": {
                "coverage_days": 120,
            },
            "transaction_insights": {
                "income": {
                    "monthly_estimate": "50500",
                    "annual_estimate": 606000,
                    "income_type": "salary",
                },
                "income_engine": {
                    "income_type": "salary",
                    "monthly_income_estimate": "50500",
                    "confidence": 0.88,
                    "salary_credits": [50000, 51000],
                    "upi_credits": [],
                    "transfer_credits": [],
                    "cash_deposits": [],
                    "other_credits": [],
                    "monthly_inflows": {"2026-01": 50000, "2026-02": 51000},
                    "income_regularity_score": 96,
                    "income_sources": [{"type": "salary", "avg": 50500, "count": 2, "total": 101000}],
                    "recurring_income_detected": True,
                    "recurring_income_source": "Acme Private Limited",
                    "recurring_income_estimate": 50500,
                    "recurring_income_months": 2,
                },
                "balance": {
                    "average": 18000,
                },
                "expenses": {
                    "emi": 12000,
                },
                "dti": {
                    "value": 0.24,
                    "label": "moderate",
                },
            },
            "risk_findings": {},
            "reasoning": {
                "summary": "Recurring salary credits were detected.",
                "narrative": [],
                "required_followups": [],
                "analysis_limitations": [],
            },
            "transactions": [],
        },
    )
    salary_analysis = FakeAnalysisRecord(
        analysis_id="analysis_salary_456",
        document_id="doc_salary_456",
        decision_status="manual_review",
        decision_recommendation="Manual review is recommended before approval.",
        decision_reason="Salary values need reconciliation.",
        recommendation="review",
        confidence=0.79,
        risk_score=48,
        extracted_fields={
            "applicant_name": "Janet Applicant",
            "monthly_income": 70000,
            "annual_income": 840000,
            "employment_type": "salary",
            "employer_name": "Bright Future Pvt Ltd",
            "document_type_detected": "salary_slip",
        },
    )
    itr_analysis = FakeAnalysisRecord(
        analysis_id="analysis_itr_456",
        document_id="doc_itr_456",
        decision_status="approve",
        decision_recommendation="Proceed with approval.",
        decision_reason="Declared income is available.",
        recommendation="approve",
        confidence=0.82,
        risk_score=34,
        extracted_fields={
            "applicant_name": "Jane Applicant",
            "monthly_income": 90000,
            "annual_income": 1080000,
            "employment_type": "self_employed",
            "document_type_detected": "tax_return",
        },
    )
    documents = [
        _make_document(
            id="doc_itr_456",
            filename="stored-doc-itr-456.pdf",
            original_filename="itr.pdf",
            document_type="tax_return",
            status="analyzed",
            analyses=[itr_analysis],
        ),
        _make_document(
            id="doc_salary_456",
            filename="stored-doc-salary-456.pdf",
            original_filename="salary-slip.pdf",
            document_type="salary_slip",
            status="analyzed",
            analyses=[salary_analysis],
        ),
        _make_document(
            id="doc_bank_456",
            filename="stored-doc-bank-456.pdf",
            original_filename="bank-statement.pdf",
            document_type="bank_statement",
            status="analyzed",
            analyses=[bank_analysis],
        ),
    ]
    fake_db = SimpleNamespace(
        case=SimpleNamespace(find_first=AsyncMock(return_value=case_record)),
        document=SimpleNamespace(find_many=AsyncMock(return_value=documents)),
        caseanalysis=SimpleNamespace(find_first=AsyncMock(return_value=None)),
    )

    result = await case_aggregation_service.get_case_read_model(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is not None
    fraud_signals = {signal.key: signal for signal in result.fraud_signals}

    assert set(fraud_signals) == {"name_mismatch", "employer_mismatch", "income_discrepancy"}
    assert "applicant form" in fraud_signals["name_mismatch"].summary.lower()
    assert "recurring bank-income source" in fraud_signals["employer_mismatch"].summary.lower()
    assert "monthly income differs" in fraud_signals["income_discrepancy"].summary.lower()

    comparison_by_field = {comparison.field: comparison for comparison in result.cross_document_comparisons}
    assert comparison_by_field["applicant_name"].status == "mismatch"
    assert comparison_by_field["employer_name"].status == "mismatch"
    assert comparison_by_field["monthly_income"].status == "mismatch"

    assert result.provisional_insights.decision_status == "manual_review"
    assert result.provisional_insights.fraud_signal_count == 3
    assert set(result.provisional_insights.fraud_signal_keys) == {"name_mismatch", "employer_mismatch", "income_discrepancy"}
    assert any("potential fraud signals detected" in blocker.lower() for blocker in result.provisional_insights.blockers)
    assert any("verify the applicant's legal name" in followup.lower() for followup in result.provisional_insights.followups)
    assert any("recurring salary credits" in followup.lower() for followup in result.provisional_insights.followups)
    assert any("reconcile the applicant's declared income" in followup.lower() for followup in result.provisional_insights.followups)


@pytest.mark.asyncio
async def test_get_case_read_model_uses_canonical_case_id_after_legacy_lookup(monkeypatch):
    case_record = _make_case(
        id="case_test_123",
        legacy_source_document_id="legacy_doc_123",
    )
    fake_db = SimpleNamespace(
        document=SimpleNamespace(find_many=AsyncMock(return_value=[])),
        caseanalysis=SimpleNamespace(find_first=AsyncMock(return_value=None)),
    )
    monkeypatch.setattr(
        case_aggregation_service,
        "get_case_by_id_for_org",
        AsyncMock(return_value=case_record),
    )

    result = await case_aggregation_service.get_case_read_model(
        db=fake_db,
        case_id="legacy_doc_123",
        org_id="org_test_456",
    )

    assert result is not None
    assert result.case.id == "case_test_123"
    fake_db.document.find_many.assert_awaited_once_with(
        where={
            "case_id": "case_test_123",
            "org_id": "org_test_456",
        },
        order={"created_at": "desc"},
        include={
            "analyses": {
                "take": 1,
                "order_by": {"created_at": "desc"},
            }
        },
    )
    fake_db.caseanalysis.find_first.assert_awaited_once_with(
        where={
            "case_id": "case_test_123",
            "is_final": True,
        },
        order={"created_at": "desc"},
    )


@pytest.mark.asyncio
async def test_get_case_read_model_keeps_unsupported_documents_but_excludes_them_from_core_scoring():
    case_record = _make_case(
        applicant_email="jane@example.com",
        applicant_phone="+1-555-0100",
    )
    bank_analysis = FakeAnalysisRecord(
        analysis_id="analysis_bank_supported_123",
        document_id="doc_bank_supported_123",
        decision_status="approve",
        decision_recommendation="Proceed with approval.",
        decision_reason="Banking signals are stable.",
        recommendation="approve",
        confidence=0.9,
        risk_score=28,
        extracted_fields={
            "decision": {
                "decision_status": "approve",
                "decision_recommendation": "Proceed with approval.",
                "decision_reason": "Banking signals are stable.",
                "extraction_confidence": 0.9,
                "risk_confidence": 0.9,
                "data_completeness": 0.9,
                "required_followups": [],
                "analysis_limitations": [],
            },
            "statement_summary": {"coverage_days": 120},
            "transaction_insights": {
                "income": {
                    "monthly_estimate": "50000",
                    "annual_estimate": 600000,
                    "income_type": "salary",
                },
                "balance": {"average": 15000},
                "expenses": {"emi": 12000},
                "dti": {"value": 0.24, "label": "moderate"},
            },
            "risk_findings": {},
            "reasoning": {
                "summary": "Banking signals are stable.",
                "narrative": [],
                "required_followups": [],
                "analysis_limitations": [],
            },
            "transactions": [],
        },
    )
    unsupported_analysis = FakeAnalysisRecord(
        analysis_id="analysis_other_123",
        document_id="doc_other_123",
        decision_status="reject",
        decision_recommendation="Reject this application.",
        decision_reason="Unsupported evidence should not influence case scoring.",
        recommendation="reject",
        confidence=0.99,
        risk_score=99,
        extracted_fields={"note": "misc attachment"},
    )
    documents = [
        _make_document(
            id="doc_other_123",
            filename="stored-doc-other-123.pdf",
            original_filename="extra-note.pdf",
            document_type="other",
            status="analyzed",
            analyses=[unsupported_analysis],
        ),
        _make_document(
            id="doc_bank_supported_123",
            filename="stored-doc-bank-supported-123.pdf",
            original_filename="bank-statement.pdf",
            document_type="bank_statement",
            status="analyzed",
            analyses=[bank_analysis],
        ),
    ]
    fake_db = SimpleNamespace(
        case=SimpleNamespace(find_first=AsyncMock(return_value=case_record)),
        document=SimpleNamespace(find_many=AsyncMock(return_value=documents)),
        caseanalysis=SimpleNamespace(find_first=AsyncMock(return_value=None)),
    )

    result = await case_aggregation_service.get_case_read_model(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is not None
    assert len(result.documents) == 2
    assert result.provisional_insights.decision_status == "manual_review"
    assert result.provisional_insights.document_decision_counts == {"approve": 1}
    assert result.provisional_insights.highest_risk_score == 28
    assert result.provisional_insights.average_risk_score == 28


@pytest.mark.asyncio
async def test_get_case_read_model_prioritizes_insufficient_history_over_other_supported_decisions():
    case_record = _make_case(
        applicant_email="jane@example.com",
        applicant_phone="+1-555-0100",
    )
    bank_analysis = FakeAnalysisRecord(
        analysis_id="analysis_bank_short_override_123",
        document_id="doc_bank_short_override_123",
        decision_status="insufficient_history",
        decision_recommendation="Collect more document history before making a final decision.",
        decision_reason="Statement history is too short for full underwriting.",
        recommendation="review",
        confidence=0.4,
        risk_score=52,
        required_followups=["Request 3-6 months of bank statement history."],
        analysis_limitations=["Statement coverage is too short."],
        extracted_fields={
            "decision": {
                "decision_status": "insufficient_history",
                "decision_recommendation": "Collect more document history before making a final decision.",
                "decision_reason": "Statement history is too short for full underwriting.",
                "extraction_confidence": 0.4,
                "risk_confidence": 0.4,
                "data_completeness": 0.4,
                "required_followups": ["Request 3-6 months of bank statement history."],
                "analysis_limitations": ["Statement coverage is too short."],
            },
            "statement_summary": {"coverage_days": 8},
            "transaction_insights": {
                "income": {
                    "monthly_estimate": None,
                    "annual_estimate": None,
                    "income_type": "unknown",
                },
                "balance": {"average": 1580},
                "expenses": {"emi": 0},
                "dti": {"value": None, "label": "unknown"},
            },
            "risk_findings": {},
            "reasoning": {
                "summary": "Statement history is too short for full underwriting.",
                "narrative": [],
                "required_followups": ["Request 3-6 months of bank statement history."],
                "analysis_limitations": ["Statement coverage is too short."],
            },
            "transactions": [],
        },
    )
    salary_analysis = FakeAnalysisRecord(
        analysis_id="analysis_salary_reject_123",
        document_id="doc_salary_reject_123",
        decision_status="reject",
        decision_recommendation="Do not approve this application.",
        decision_reason="Income evidence is not sufficient on its own.",
        recommendation="reject",
        confidence=0.83,
        risk_score=83,
        extracted_fields={
            "applicant_name": "Jane Applicant",
            "monthly_income": 30000,
            "annual_income": 360000,
            "employment_type": "salary",
            "employer_name": "Acme Corp",
        },
    )
    documents = [
        _make_document(
            id="doc_salary_reject_123",
            filename="stored-doc-salary-reject-123.pdf",
            original_filename="salary-slip.pdf",
            document_type="salary_slip",
            status="analyzed",
            analyses=[salary_analysis],
        ),
        _make_document(
            id="doc_bank_short_override_123",
            filename="stored-doc-bank-short-override-123.pdf",
            original_filename="bank-statement-short.pdf",
            document_type="bank_statement",
            status="analyzed",
            analyses=[bank_analysis],
        ),
    ]
    fake_db = SimpleNamespace(
        case=SimpleNamespace(find_first=AsyncMock(return_value=case_record)),
        document=SimpleNamespace(find_many=AsyncMock(return_value=documents)),
        caseanalysis=SimpleNamespace(find_first=AsyncMock(return_value=None)),
    )

    result = await case_aggregation_service.get_case_read_model(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is not None
    assert result.provisional_insights.decision_status == "insufficient_history"
    assert result.provisional_insights.document_decision_counts == {
        "insufficient_history": 1,
        "reject": 1,
    }
    assert "Request 3-6 months of bank statement history." in result.provisional_insights.followups


@pytest.mark.asyncio
async def test_get_case_read_model_uses_latest_analysis_row_per_document():
    case_record = _make_case(
        applicant_email="jane@example.com",
        applicant_phone="+1-555-0100",
    )
    older_analysis = FakeAnalysisRecord(
        analysis_id="analysis_bank_old_123",
        document_id="doc_bank_latest_123",
        decision_status="reject",
        decision_recommendation="Do not approve this application.",
        decision_reason="Legacy scoring was too harsh.",
        recommendation="reject",
        confidence=0.92,
        risk_score=81,
        extracted_fields={
            "decision": {
                "decision_status": "reject",
                "decision_recommendation": "Do not approve this application.",
                "decision_reason": "Legacy scoring was too harsh.",
                "extraction_confidence": 0.92,
                "risk_confidence": 0.92,
                "data_completeness": 0.92,
                "required_followups": [],
                "analysis_limitations": [],
            },
            "statement_summary": {"coverage_days": 120},
            "transaction_insights": {
                "income": {
                    "monthly_estimate": "42000",
                    "annual_estimate": 504000,
                    "income_type": "salary",
                },
                "balance": {"average": 8000},
                "expenses": {"emi": 20000},
                "dti": {"value": 0.48, "label": "high"},
            },
            "risk_findings": {},
            "reasoning": {
                "summary": "Legacy scoring was too harsh.",
                "narrative": [],
                "required_followups": [],
                "analysis_limitations": [],
            },
            "transactions": [],
        },
    )
    newer_analysis = FakeAnalysisRecord(
        analysis_id="analysis_bank_new_123",
        document_id="doc_bank_latest_123",
        decision_status="approve",
        decision_recommendation="Proceed with approval.",
        decision_reason="Corrected scoring recognizes stable salary credits.",
        recommendation="approve",
        confidence=0.95,
        risk_score=24,
        extracted_fields={
            "decision": {
                "decision_status": "approve",
                "decision_recommendation": "Proceed with approval.",
                "decision_reason": "Corrected scoring recognizes stable salary credits.",
                "extraction_confidence": 0.95,
                "risk_confidence": 0.95,
                "data_completeness": 0.95,
                "required_followups": [],
                "analysis_limitations": [],
            },
            "statement_summary": {"coverage_days": 120},
            "transaction_insights": {
                "income": {
                    "monthly_estimate": "52000",
                    "annual_estimate": 624000,
                    "income_type": "salary",
                },
                "balance": {"average": 18000},
                "expenses": {"emi": 9000},
                "dti": {"value": 0.17, "label": "low"},
            },
            "risk_findings": {},
            "reasoning": {
                "summary": "Corrected scoring recognizes stable salary credits.",
                "narrative": [],
                "required_followups": [],
                "analysis_limitations": [],
            },
            "transactions": [],
        },
    )
    documents = [
        _make_document(
            id="doc_bank_latest_123",
            filename="stored-doc-bank-latest-123.pdf",
            original_filename="bank-statement.pdf",
            document_type="bank_statement",
            status="analyzed",
            analyses=[newer_analysis, older_analysis],
        ),
    ]
    fake_db = SimpleNamespace(
        case=SimpleNamespace(find_first=AsyncMock(return_value=case_record)),
        document=SimpleNamespace(find_many=AsyncMock(return_value=documents)),
        caseanalysis=SimpleNamespace(find_first=AsyncMock(return_value=None)),
    )

    result = await case_aggregation_service.get_case_read_model(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is not None
    assert result.documents[0].latest_analysis is not None
    assert result.documents[0].latest_analysis.id == "analysis_bank_new_123"
    assert result.documents[0].latest_analysis.risk_score == 24
    assert result.provisional_insights.highest_risk_score == 24
    assert result.provisional_insights.document_decision_counts == {"approve": 1}


@pytest.mark.asyncio
async def test_get_case_read_model_surfaces_ocr_truth_from_jobs_and_artifacts(monkeypatch):
    case_record = _make_case(
        applicant_email="jane@example.com",
        applicant_phone="+1-555-0100",
    )
    documents = [
        _make_document(
            id="doc_blocked_ocr_123",
            filename="stored-doc-blocked-ocr-123.pdf",
            original_filename="blocked-scan.pdf",
            document_type="income_proof",
            status="failed",
            file_url="secure://documents/blocked-scan.pdf",
            analyses=[],
        ),
        _make_document(
            id="doc_processing_ocr_123",
            filename="stored-doc-processing-ocr-123.pdf",
            original_filename="processing-scan.pdf",
            document_type="bank_statement",
            status="processing",
            file_url="secure://documents/processing-scan.pdf",
            analyses=[],
        ),
    ]
    fake_db = SimpleNamespace(
        case=SimpleNamespace(find_first=AsyncMock(return_value=case_record)),
        document=SimpleNamespace(find_many=AsyncMock(return_value=documents)),
        caseanalysis=SimpleNamespace(find_first=AsyncMock(return_value=None)),
    )

    async def fake_load_artifact(file_url: str):
        if file_url == "secure://documents/blocked-scan.pdf":
            return {
                "file_type": "application/pdf",
                "total_pages": 2,
                "scanned_pages": 0,
                "extraction_schema_version": 2,
                "extraction_status": "unreliable",
                "ocr_required_pages": [2],
                "ocr_failed_pages": [],
                "ocr_unreliable_pages": [2],
                "ocr_fallback_used": False,
                "ocr_provider": "document_ai",
                "metadata": {},
                "pages": [],
            }
        return None

    async def fake_get_analysis_job(document_id: str):
        if document_id == "doc_blocked_ocr_123":
            return {
                "job_id": "job_blocked_ocr_123",
                "document_id": document_id,
                "status": "failed",
                "stage": "failed",
                "stage_message": "Analysis failed.",
                "ocr_provider": "document_ai",
                "pages_processed": 2,
                "total_pages": 2,
                "ocr_required_pages": [2],
                "ocr_failed_pages": [],
                "ocr_unreliable_pages": [2],
                "ocr_fallback_used": False,
                "ocr_quality_status": "blocked",
                "attempts": 1,
                "max_attempts": 1,
                "last_error": "OCR quality is insufficient for analysis (unreliable OCR pages: 2).",
                "error_code": "ocr_quality_blocked",
                "user_message": "Analysis is blocked because OCR did not recover reliable text for every required page.",
            }
        if document_id == "doc_processing_ocr_123":
            return {
                "job_id": "job_processing_ocr_123",
                "document_id": document_id,
                "status": "processing",
                "stage": "ocr",
                "stage_message": "Running OCR on scanned pages.",
                "ocr_provider": "mixed",
                "pages_processed": 1,
                "total_pages": 2,
                "ocr_required_pages": [1, 2],
                "ocr_failed_pages": [],
                "ocr_unreliable_pages": [],
                "ocr_fallback_used": True,
                "ocr_quality_status": "pending",
                "attempts": 1,
                "max_attempts": 1,
                "last_error": None,
                "error_code": None,
                "user_message": None,
            }
        return None

    monkeypatch.setattr(case_aggregation_service, "load_extraction_artifact_for_file", fake_load_artifact)
    monkeypatch.setattr(case_aggregation_service, "get_analysis_job", fake_get_analysis_job)

    result = await case_aggregation_service.get_case_read_model(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is not None

    blocked_doc = next(document for document in result.documents if document.id == "doc_blocked_ocr_123")
    assert blocked_doc.ocr_status is not None
    assert blocked_doc.ocr_status.ocr_quality_status == "blocked"
    assert blocked_doc.ocr_status.analysis_blocked is True
    assert blocked_doc.ocr_status.ocr_unreliable_pages == [2]
    assert blocked_doc.ocr_status.user_message is not None
    assert "blocked because OCR" in blocked_doc.ocr_status.user_message

    processing_doc = next(document for document in result.documents if document.id == "doc_processing_ocr_123")
    assert processing_doc.ocr_status is not None
    assert processing_doc.ocr_status.ocr_quality_status == "pending"
    assert processing_doc.ocr_status.ocr_required_pages == [1, 2]
    assert processing_doc.ocr_status.ocr_fallback_used is True
    assert processing_doc.ocr_status.stage_message == "Running OCR on scanned pages."


@pytest.mark.asyncio
async def test_existing_analysis_without_account_profile_returns_evidence_profile_from_artifact(monkeypatch):
    case_record = _make_case(
        applicant_email="jane@example.com",
        applicant_phone="+1-555-0100",
    )
    bank_analysis = FakeAnalysisRecord(
        analysis_id="analysis_bank_legacy_36604",
        document_id="doc_bank_legacy_36604",
        decision_status="reject",
        decision_recommendation="Do not approve this application.",
        decision_reason="Legacy bank statement analysis.",
        recommendation="reject",
        confidence=0.84,
        risk_score=78,
        extracted_fields={
            "decision": {
                "decision_status": "reject",
                "decision_recommendation": "Do not approve this application.",
                "decision_reason": "Legacy bank statement analysis.",
                "extraction_confidence": 0.84,
                "risk_confidence": 0.84,
                "data_completeness": 0.84,
                "required_followups": [],
                "analysis_limitations": [],
            },
            "statement_summary": {"coverage_days": 8, "statement_end_date": "2024-01-29"},
            "transaction_insights": {
                "income": {"monthly_estimate": None, "income_type": "unstable"},
                "balance": {"average": 1580},
                "expenses": {"emi": 0},
                "dti": {"value": None, "label": "unknown"},
            },
            "risk_findings": {},
            "reasoning": {
                "summary": "Legacy bank statement analysis.",
                "narrative": [],
                "required_followups": [],
                "analysis_limitations": [],
            },
            "transactions": [],
        },
    )
    documents = [
        _make_document(
            id="doc_bank_legacy_36604",
            filename="stored-doc-bank-legacy-36604.pdf",
            original_filename="36604.pdf",
            document_type="bank_statement",
            status="analyzed",
            file_url="secure://documents/36604.pdf",
            analyses=[bank_analysis],
        ),
    ]
    fake_db = SimpleNamespace(
        case=SimpleNamespace(find_first=AsyncMock(return_value=case_record)),
        document=SimpleNamespace(find_many=AsyncMock(return_value=documents)),
        caseanalysis=SimpleNamespace(find_first=AsyncMock(return_value=None)),
    )
    artifact_text = (
        "Bank of Baroda\n"
        "Account Name : MRS. SWATI NITIN BHOKARE\n"
        "A/C Number : 04740100006604\n"
        "Branch Name : KOPARGAON\n"
        "IFSC Code : BARB0KOPERG\n"
        "Statement Period : 22-01-2024 to 29-01-2024\n"
        "29-01-2024 UPI Transfer Out 12,804.00 0.00 157.14\n"
    )

    async def fake_load_artifact(file_url: str):
        assert file_url == "secure://documents/36604.pdf"
        return {
            "file_type": "application/pdf",
            "total_text": artifact_text,
            "total_pages": 1,
            "scanned_pages": 0,
            "extraction_schema_version": 2,
            "extraction_status": "complete",
            "metadata": {},
            "pages": [],
        }

    monkeypatch.setattr(case_aggregation_service, "load_extraction_artifact_for_file", fake_load_artifact)
    monkeypatch.setattr(case_aggregation_service, "get_analysis_job", AsyncMock(return_value=None))

    result = await case_aggregation_service.get_case_read_model(
        db=fake_db,
        case_id="case_test_123",
        org_id="org_test_456",
    )

    assert result is not None
    document = result.documents[0]
    assert document.evidence_profile is not None
    assert document.evidence_profile.account_profile is not None
    assert document.evidence_profile.account_profile.account_holder_name == "MRS. SWATI NITIN BHOKARE"
    assert document.evidence_profile.account_profile.account_number_masked == "****6604"
    assert document.evidence_profile.declared_period_start_date == "2024-01-22"
    assert document.evidence_profile.declared_period_end_date == "2024-01-29"


def test_extract_comparison_facts_uses_numeric_income_bounds_for_ranges():
    document = SimpleNamespace(
        latest_analysis=SimpleNamespace(
            extracted_fields={
                "statement_summary": {"coverage_days": 120},
                "transaction_insights": {
                    "income": {
                        "monthly_estimate": "45000-67000",
                        "monthly_estimate_min": 45000,
                        "monthly_estimate_max": 67000,
                        "annual_estimate": 672000,
                        "annual_estimate_min": 540000,
                        "annual_estimate_max": 804000,
                        "income_type": "salary",
                    },
                    "income_engine": {
                        "recurring_income_estimate": None,
                        "recurring_income_source": "ACME Payroll",
                    },
                    "balance": {"average": 25000},
                    "expenses": {"emi": 12000},
                    "dti": {"value": 0.214, "label": "moderate"},
                },
                "risk_findings": {},
            }
        )
    )

    facts = case_aggregation_service._extract_comparison_facts(document)

    assert facts["monthly_income"] == 56000.0
    assert facts["annual_income"] == 672000.0
    assert facts["employment_type"] == "salary"
    assert facts["employer_name"] == "ACME Payroll"
