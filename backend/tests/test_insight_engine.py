from __future__ import annotations

import math

import pytest

from core.confidence import build_decision_payload
from services.insight_engine import process_analysis


def test_process_analysis_emits_normalized_decision_confidence():
    result = process_analysis(
        {
            "monthly_income": 55000,
            "annual_income": 660000,
            "existing_emis": 12000,
            "risk_score": 34,
            "risk_reasoning": "Stable income with manageable EMI burden.",
            "risk_alerts": [],
            "summary": "Generic analysis summary.",
        },
        model_used="gemini-test",
    )

    assert 0.0 <= result.confidence <= 1.0
    assert result.extracted_fields["decision"]["decision_status"] == "approve"
    assert result.recommendation == "approve"
    assert result.extracted_fields["decision"]["risk_confidence"] == pytest.approx(result.confidence, abs=1e-4)
    assert result.raw_response["decision"]["risk_confidence"] == pytest.approx(result.confidence, abs=1e-4)
    assert isinstance(result.extracted_fields["decision"]["analysis_limitations"], list)


def test_process_analysis_caps_fully_populated_confidence_at_one():
    result = process_analysis(
        {
            "interest_rate": 10.5,
            "processing_fee": 1500,
            "loan_amount": 500000,
            "tenure_months": 60,
            "monthly_income": 85000,
            "annual_income": 1020000,
            "monthly_expenses": 35000,
            "debt_to_income_ratio": 0.32,
            "employment_type": "salaried",
            "employment_tenure_years": 4,
            "applicant_name": "Jane Applicant",
            "employer_name": "ACME",
            "avg_monthly_balance": 90000,
            "min_balance_6m": 45000,
            "existing_emis": 18000,
            "credit_utilization_pct": 28,
            "penalty_clauses": [],
            "hidden_charges": [],
            "document_type_detected": "salary_slip",
            "confidence_notes": "All expected fields were present.",
            "risk_score": 18,
            "risk_alerts": [],
            "summary": "All data points extracted successfully.",
        },
        model_used="gemini-test",
    )

    assert result.confidence == 1.0
    assert result.extracted_fields["decision"]["risk_confidence"] == 1.0
    assert result.extracted_fields["decision"]["decision_status"] == "approve"


def test_build_decision_payload_enforces_canonical_priority_order():
    decision = build_decision_payload(
        decision_candidates=["approve", "manual_review", "reject"],
        decision_reason="Multiple severe risk factors were detected.",
        extraction_confidence=0.92,
        risk_confidence=0.88,
        data_completeness=0.9,
    )

    assert decision["decision_status"] == "reject"


def test_build_decision_payload_lets_insufficient_history_override_other_candidates():
    decision = build_decision_payload(
        decision_candidates=["reject", "manual_review", "insufficient_history"],
        decision_reason="There is not enough reliable history to make a final decision.",
        extraction_confidence=0.22,
        risk_confidence=0.91,
        data_completeness=0.2,
    )

    assert decision["decision_status"] == "insufficient_history"
    assert decision["analysis_limitations"] == ["Insufficient reliable history was available for a final decision."]


def test_build_decision_payload_uses_status_specific_templates_when_context_is_supplied():
    approve = build_decision_payload(
        decision_status="approve",
        extraction_confidence=0.95,
        risk_confidence=0.92,
        data_completeness=0.95,
        reason_context={
            "coverage_days": 120,
            "stable_income_detected": True,
            "min_balance": 18000,
            "total_credits": 65000,
            "total_debits": 31000,
            "dti_label": "low",
        },
    )
    manual_review = build_decision_payload(
        decision_status="manual_review",
        extraction_confidence=0.7,
        risk_confidence=0.6,
        data_completeness=0.6,
        required_followups=["Verify existing debt obligations and the borrower's DTI."],
        reason_context={
            "stable_income_detected": False,
            "existing_emis": 25000,
            "debt_to_income_ratio": 0.42,
            "dti_label": "high",
            "data_completeness": 0.6,
        },
    )
    reject = build_decision_payload(
        decision_status="reject",
        extraction_confidence=0.88,
        risk_confidence=0.84,
        data_completeness=0.88,
        reason_context={
            "primary_risk_driver": "Repayment capacity is not supported by verified stable income",
            "existing_emis": 32000,
            "dti_label": "high",
            "debt_to_income_ratio": 0.58,
        },
    )
    insufficient_history = build_decision_payload(
        decision_status="insufficient_history",
        extraction_confidence=0.4,
        risk_confidence=0.4,
        data_completeness=0.4,
        required_followups=["Request 3\u20136 months of bank statement history."],
        reason_context={
            "coverage_days": 8,
            "income_inference_skipped": True,
            "min_balance": 157.14,
            "total_credits": 11381,
            "total_debits": 12804,
        },
    )

    assert approve["decision_reason"].startswith("Approve: sufficient_history=coverage_days=120")
    assert "stability_signal=" in approve["decision_reason"]
    assert "blockers=none identified" in approve["decision_reason"]

    assert manual_review["decision_reason"].startswith("Manual review: uncertainty_reason=")
    assert "key_risk_signal=high DTI" in manual_review["decision_reason"]
    assert "follow_up=Verify existing debt obligations and the borrower's DTI" in manual_review["decision_reason"]

    assert reject["decision_reason"].startswith("Reject: primary_risk_driver=Repayment capacity is not supported by verified stable income")
    assert "supporting_signal=high DTI" in reject["decision_reason"]
    assert "next_action=Do not approve this application" in reject["decision_reason"]

    assert insufficient_history["decision_reason"].startswith("Insufficient history: coverage_days=8")
    assert "stable_income_status=no verifiable stable income detected" in insufficient_history["decision_reason"]
    assert "liquidity_signal=low" in insufficient_history["decision_reason"]
    assert "next_action=Request 3\u20136 months of bank statement history" in insufficient_history["decision_reason"]


def test_process_analysis_uses_template_reason_as_canonical_explanation():
    result = process_analysis(
        {
            "monthly_income": 60000,
            "annual_income": 720000,
            "debt_to_income_ratio": 0.42,
            "existing_emis": 25000,
            "employment_type": "salaried",
            "avg_monthly_balance": 15000,
            "risk_score": 58,
            "risk_reasoning": "Gemini free-form text should not become the canonical decision reason.",
            "risk_alerts": [{"severity": "high", "message": "High DTI", "field": "debt_to_income_ratio"}],
            "summary": "Provider summary.",
        },
        model_used="gemini-test",
    )

    decision_reason = result.extracted_fields["decision"]["decision_reason"]

    assert result.extracted_fields["decision"]["decision_status"] == "manual_review"
    assert decision_reason.startswith("Manual review: uncertainty_reason=")
    assert "key_risk_signal=high DTI" in decision_reason
    assert decision_reason != "Gemini free-form text should not become the canonical decision reason."
    assert result.summary.splitlines()[0] == decision_reason


def test_process_analysis_applies_rule_adjustments_additively():
    result = process_analysis(
        {
            "risk_score": 20,
            "interest_rate": 19,
            "hidden_charges": ["fee-1", "fee-2", "fee-3"],
            "employment_tenure_years": 0.5,
            "monthly_income": 50000,
            "avg_monthly_balance": 10000,
            "risk_alerts": [],
            "summary": "Provider baseline looked acceptable.",
        },
        model_used="gemini-test",
    )

    assert result.risk_score == 78.0
    assert result.extracted_fields["decision"]["decision_status"] == "reject"
    assert result.recommendation == "reject"
    assert any(alert["message"] == "Very high interest rate detected" for alert in result.risk_alerts)
    assert any("hidden charges" in alert["message"].lower() for alert in result.risk_alerts)


def test_process_analysis_treats_non_finite_inputs_as_missing_and_not_approve_friendly():
    result = process_analysis(
        {
            "risk_score": float("nan"),
            "monthly_income": float("nan"),
            "annual_income": float("inf"),
            "existing_emis": float("-inf"),
            "risk_alerts": [],
            "summary": "Provider returned malformed numerics.",
        },
        model_used="gemini-test",
    )

    assert math.isfinite(result.risk_score)
    assert math.isfinite(result.confidence)
    assert result.risk_score == 50.0
    assert result.extracted_fields["decision"]["decision_status"] == "manual_review"
    assert "monthly_income" not in result.extracted_fields
    assert "annual_income" not in result.extracted_fields
    assert "existing_emis" not in result.extracted_fields
