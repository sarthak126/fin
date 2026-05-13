from core.bank_statement_score import build_bank_statement_score_payload
from services import bank_statement_pipeline as pipeline
from services import bank_statement_pipeline_output as output_module
from services.bank_statement_engine_income import compute_income_engine
from services.bank_statement_profile import extract_bank_statement_evidence_profile
from tests.sample_bank_statement_fixture import (
    FIXTURE_DIR,
    load_short_history_sample_expected,
    load_short_history_sample_transactions,
)


def _collect_confidence_values(payload):
    values = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"confidence", "risk_confidence", "extraction_confidence", "data_completeness"}:
                values.append((key, value))
            values.extend(_collect_confidence_values(value))
    elif isinstance(payload, list):
        for item in payload:
            values.extend(_collect_confidence_values(item))
    return values


def _sum_visible_score_components(score: dict[str, int]) -> int:
    return (
        score["income_stability"]
        + score["balance_health"]
        + score["obligation_load"]
        + score["spending_discipline"]
        + score["cash_behavior"]
        + score["risk_penalty"]
    )


def test_bank_statement_score_helper_emits_the_canonical_v2_contract():
    score = build_bank_statement_score_payload(
        income_stability=11,
        balance_health=7,
        obligation_load=5,
        spending_discipline=9,
        cash_behavior=4,
        risk_penalty=3,
    )

    assert score == {
        "score_model": "bank_statement_v2",
        "income_stability": 11,
        "balance_health": 7,
        "obligation_load": 5,
        "spending_discipline": 9,
        "cash_behavior": 4,
        "risk_penalty": 3,
        "final_score": 39,
    }
    assert _sum_visible_score_components(score) == score["final_score"]


def test_bank_of_baroda_header_parser_extracts_36604_account_evidence():
    text = (FIXTURE_DIR / "bank_statement_36604_header_sample.txt").read_text(encoding="utf-8")

    profile = extract_bank_statement_evidence_profile(text)

    assert profile["account_profile"]["account_holder_name"] == "MRS. SWATI NITIN BHOKARE"
    assert profile["account_profile"]["account_number_masked"] == "****6604"
    assert profile["account_profile"]["bank_name"] == "Bank of Baroda"
    assert profile["account_profile"]["ifsc"] == "BARB0KOPERG"
    assert profile["account_profile"]["branch_phone"] == "02423-223366"
    assert profile["declared_period_start_date"] == "2024-01-22"
    assert profile["declared_period_end_date"] == "2024-01-29"
    assert profile["last_transaction_date"] == "2024-01-29"


def test_rule_engine_flags_duplicates_and_keyword_overrides():
    transactions = [
        {
            "date": "2024-01-01",
            "description": "ATM WDL Sector 18",
            "debit": "500",
            "credit": None,
            "balance": "900",
            "confidence": "high",
        },
        {
            "date": "2024-01-01",
            "description": "ATM WDL Sector 18",
            "debit": "500",
            "credit": None,
            "balance": "900",
            "confidence": "low",
        },
        {
            "date": "2024-01-02",
            "description": "Loan EMI Auto-Debit",
            "debit": "1200",
            "credit": None,
            "balance": "-50",
        },
    ]

    corrected = pipeline.apply_bank_statement_rule_engine(transactions)

    assert corrected[0]["category"] == "CASH_FLOW"
    assert corrected[1]["duplicate"] is True
    assert "Duplicate-looking transaction flagged." in corrected[1]["notes"]
    assert corrected[2]["category"] == "EMI"
    assert corrected[2]["reversal"] is False


def test_rule_engine_marks_verification_credits_and_same_day_pass_through_pairs():
    corrected = pipeline.apply_bank_statement_rule_engine(
        [
            {
                "date": "2024-01-05",
                "description": "Penny Drop Account Verification",
                "credit": "1",
                "debit": None,
                "balance": "5001",
            },
            {
                "date": "2024-01-05",
                "description": "IMPS transfer from own account",
                "credit": "10000",
                "debit": None,
                "balance": "15001",
            },
            {
                "date": "2024-01-05",
                "description": "UPI transfer to own account",
                "credit": None,
                "debit": "10000",
                "balance": "5001",
            },
        ]
    )

    assert corrected[0]["verification_credit"] is True
    assert corrected[0]["pass_through_transfer"] is False
    assert corrected[1]["pass_through_transfer"] is True
    assert corrected[2]["pass_through_transfer"] is True
    assert "Micro verification credit detected" in corrected[0]["notes"]
    assert "Same-day pass-through transfer matched within Rs25" in corrected[1]["notes"]


def test_rule_engine_relaxes_pass_through_matching_tolerance():
    corrected = pipeline.apply_bank_statement_rule_engine(
        [
            {
                "date": "2024-01-05",
                "description": "IMPS transfer from own account",
                "credit": "10000",
                "debit": None,
                "balance": "15001",
            },
            {
                "date": "2024-01-05",
                "description": "UPI transfer to own account",
                "credit": None,
                "debit": "10018",
                "balance": "4983",
            },
        ]
    )

    assert corrected[0]["pass_through_transfer"] is True
    assert corrected[1]["pass_through_transfer"] is True


def test_rule_engine_does_not_promote_loan_fees_to_emi():
    corrected = pipeline.apply_bank_statement_rule_engine(
        [
            {
                "date": "2024-01-05",
                "description": "Loan Processing Fee GST",
                "credit": None,
                "debit": "999",
                "balance": "12000",
                "category": "EXPENSE",
            },
        ]
    )

    assert corrected[0]["category"] != "EMI"
    assert corrected[0]["category"] == "EXPENSE"


def test_rule_engine_keeps_same_day_same_store_repeats_when_balance_is_missing():
    corrected = pipeline.apply_bank_statement_rule_engine(
        [
            {
                "date": "2024-01-05",
                "description": "Cafe Coffee Day",
                "credit": None,
                "debit": "250",
                "balance": None,
            },
            {
                "date": "2024-01-05",
                "description": "Cafe Coffee Day",
                "credit": None,
                "debit": "250",
                "balance": None,
            },
        ]
    )

    assert corrected[0]["duplicate"] is False
    assert corrected[1]["duplicate"] is False


def test_deterministic_aggregate_skips_duplicates_and_tracks_stress():
    corrected_transactions = [
        {
            "date": "2024-01-01",
            "description": "Salary Credit",
            "credit": 50000,
            "debit": None,
            "balance": 50000,
            "category": "VERIFIED_INCOME",
            "duplicate": False,
            "reversal": False,
        },
        {
            "date": "2024-01-02",
            "description": "Loan EMI Auto-Debit",
            "credit": None,
            "debit": 12000,
            "balance": 38000,
            "category": "EMI",
            "duplicate": False,
            "reversal": False,
        },
        {
            "date": "2024-01-03",
            "description": "ATM Withdrawal",
            "credit": None,
            "debit": 4000,
            "balance": 900,
            "category": "CASH_FLOW",
            "duplicate": False,
            "reversal": False,
        },
        {
            "date": "2024-01-03",
            "description": "ATM Withdrawal",
            "credit": None,
            "debit": 4000,
            "balance": 900,
            "category": "CASH_FLOW",
            "duplicate": True,
            "reversal": False,
        },
    ]

    aggregate = pipeline.deterministic_aggregate(corrected_transactions)
    dti = pipeline.compute_dti(aggregate["emi_total"], aggregate["verified_income"])
    cash_behavior = pipeline.analyze_cash_behavior(corrected_transactions, aggregate)

    assert aggregate["verified_income"] == 50000
    assert aggregate["emi_total"] == 12000
    assert aggregate["cash_withdrawals"] == 4000
    assert aggregate["duplicate_count"] == 1
    assert aggregate["low_balance_events"] == 1
    assert aggregate["statement_summary"]["low_balance_count"] == 1
    assert aggregate["statement_summary"]["median_balance"] == 38000.0
    assert dti == {"value": 0.24, "label": "moderate", "reliability": "verified"}
    assert cash_behavior["stressScore"] >= 8


def test_compute_dti_prefers_recurring_then_verified_then_marks_unverified_income():
    assert pipeline.compute_dti(
        12000,
        50000,
        recurring_income_estimate=40000,
        unverified_income=10000,
    ) == {"value": 0.3, "label": "moderate", "reliability": "verified"}
    assert pipeline.compute_dti(
        12000,
        50000,
        recurring_income_estimate=None,
        unverified_income=10000,
    ) == {"value": 0.24, "label": "moderate", "reliability": "verified"}
    assert pipeline.compute_dti(
        12000,
        0,
        recurring_income_estimate=None,
        unverified_income=20000,
    ) == {"value": 0.6, "label": "extreme", "reliability": "unverified"}
    assert pipeline.compute_dti(
        12000,
        0,
        recurring_income_estimate=None,
        unverified_income=0,
    ) == {"value": None, "label": "unknown", "reliability": "unavailable"}


def test_deterministic_aggregate_ignores_self_transfers_and_offsets_atm_corrections():
    corrected_transactions = [
        {
            "date": "2024-01-01",
            "description": "Salary Credit",
            "credit": 50000,
            "debit": None,
            "balance": 50000,
            "category": "VERIFIED_INCOME",
            "duplicate": False,
            "reversal": False,
        },
        {
            "date": "2024-01-02",
            "description": "SELF transfer to own account",
            "credit": None,
            "debit": 20000,
            "balance": 30000,
            "category": "CASH_FLOW",
            "duplicate": False,
            "reversal": False,
        },
        {
            "date": "2024-01-03",
            "description": "ATM Withdrawal",
            "credit": None,
            "debit": 10000,
            "balance": 20000,
            "category": "CASH_FLOW",
            "duplicate": False,
            "reversal": False,
        },
        {
            "date": "2024-01-04",
            "description": "ATM/CWRR correction",
            "credit": 4000,
            "debit": None,
            "balance": 24000,
            "category": "CASH_FLOW",
            "duplicate": False,
            "reversal": False,
        },
    ]

    aggregate = pipeline.deterministic_aggregate(corrected_transactions)
    cash_behavior = pipeline.analyze_cash_behavior(corrected_transactions, aggregate)

    assert aggregate["cash_withdrawals"] == 6000
    assert aggregate["cash_deposits"] == 0
    assert cash_behavior["flags"] == []


def test_deterministic_aggregate_applies_reversal_signs_to_cash_flow():
    corrected_transactions = [
        {
            "date": "2024-01-01",
            "description": "ATM Withdrawal",
            "credit": None,
            "debit": 10000,
            "balance": 40000,
            "category": "CASH_FLOW",
            "duplicate": False,
            "reversal": False,
        },
        {
            "date": "2024-01-02",
            "description": "ATM Withdrawal Reversal",
            "credit": 10000,
            "debit": None,
            "balance": 50000,
            "category": "CASH_FLOW",
            "duplicate": False,
            "reversal": True,
        },
        {
            "date": "2024-01-03",
            "description": "Cash Deposit Branch",
            "credit": 5000,
            "debit": None,
            "balance": 55000,
            "category": "CASH_FLOW",
            "duplicate": False,
            "reversal": False,
        },
        {
            "date": "2024-01-04",
            "description": "Cash Deposit Branch Reversal",
            "credit": None,
            "debit": 5000,
            "balance": 50000,
            "category": "CASH_FLOW",
            "duplicate": False,
            "reversal": True,
        },
    ]

    aggregate = pipeline.deterministic_aggregate(corrected_transactions)

    assert aggregate["cash_withdrawals"] == 0
    assert aggregate["cash_deposits"] == 0
    assert aggregate["reversal_count"] == 2


def test_analyze_cash_behavior_uses_transaction_dates_for_cash_cycling_detection():
    corrected_transactions = [
        {
            "date": "2024-01-10",
            "description": "Cash Deposit Branch",
            "credit": 5000,
            "debit": None,
            "balance": 25000,
            "category": "UNVERIFIED_CREDIT",
            "duplicate": False,
            "reversal": False,
        },
        {
            "date": "2024-01-01",
            "description": "Merchant Payment 1",
            "credit": None,
            "debit": 500,
            "balance": 24500,
            "category": "EXPENSE",
            "duplicate": False,
            "reversal": False,
        },
        {
            "date": "2024-01-02",
            "description": "Merchant Payment 2",
            "credit": None,
            "debit": 500,
            "balance": 24000,
            "category": "EXPENSE",
            "duplicate": False,
            "reversal": False,
        },
        {
            "date": "2024-01-03",
            "description": "Merchant Payment 3",
            "credit": None,
            "debit": 500,
            "balance": 23500,
            "category": "EXPENSE",
            "duplicate": False,
            "reversal": False,
        },
        {
            "date": "2024-01-11",
            "description": "ATM Withdrawal",
            "credit": None,
            "debit": 5000,
            "balance": 18500,
            "category": "CASH_FLOW",
            "duplicate": False,
            "reversal": False,
        },
    ]

    aggregate = pipeline.deterministic_aggregate(corrected_transactions)
    cash_behavior = pipeline.analyze_cash_behavior(corrected_transactions, aggregate)

    assert "Cash-in followed by rapid cash-out (cycling)." in cash_behavior["flags"]


def test_build_output_composes_smaller_analysis_engines(monkeypatch):
    monkeypatch.setattr(output_module, "compute_income_engine", lambda corrected: {"income_type": "Salary"})
    monkeypatch.setattr(
        output_module,
        "compute_cashflow_intelligence",
        lambda corrected, aggregate, income_engine: {"net_flow": 41000},
    )
    monkeypatch.setattr(output_module, "compute_spending_intelligence", lambda corrected: {"expense_ratio": 0.18})
    monkeypatch.setattr(
        output_module,
        "compute_behavioral_flags",
        lambda corrected, aggregate, income_engine, cashflow: {"flags": ["stable salary cadence"]},
    )
    monkeypatch.setattr(
        output_module,
        "compute_explainable_risk",
        lambda *args, **kwargs: {
            "total_risk_score": 23,
            "risk_level": "low",
            "risk_breakdown": {
                "income_stability": {"score": 5, "max": 20, "detail": "Stable salary credits."},
                "balance_health": {"score": 4, "max": 20, "detail": "Healthy balances overall."},
                "obligation_load": {"score": 4, "max": 15, "detail": "Manageable EMI burden."},
                "spending_discipline": {"score": 4, "max": 15, "detail": "Spending remains controlled."},
                "cash_behavior": {"score": 3, "max": 15, "detail": "Minor cash stress signals."},
                "risk_penalty": {"score": 3, "max": 15, "detail": "Small penalty overlay applied."},
            },
        },
    )
    monkeypatch.setattr(
        output_module,
        "compute_final_decision",
        lambda canonical_score, explainable, confidence: {
            "decision": "APPROVE",
            "reasons": ["Stable cash flow and manageable obligations."],
        },
    )

    result = pipeline.build_bank_statement_output(
        transactions=[
            {
                "date": "2024-01-01",
                "description": "Salary Credit ACME",
                "credit": 50000,
                "debit": None,
                "balance": 50000,
                "category": "VERIFIED_INCOME",
                "confidence": "high",
            },
            {
                "date": "2024-04-01",
                "description": "Loan EMI Auto-Debit",
                "credit": None,
                "debit": 12000,
                "balance": 38000,
                "category": "EMI",
                "confidence": "high",
            },
        ],
        statement_confidence=0.91,
        document_type="bank_statement",
    )

    assert set(result) == {
        "decision",
        "statement_summary",
        "transaction_insights",
        "risk_findings",
        "reasoning",
        "transactions",
    }
    assert result["decision"]["decision_status"] == "approve"
    assert result["decision"]["risk_confidence"] == 0.91
    assert isinstance(result["decision"]["analysis_limitations"], list)
    assert result["risk_findings"]["risk_score"]["score_model"] == "bank_statement_v2"
    assert result["risk_findings"]["risk_score"]["final_score"] == 23
    assert _sum_visible_score_components(result["risk_findings"]["risk_score"]) == 23
    assert result["risk_findings"]["explainable_risk"]["total_risk_score"] == 23
    assert result["transaction_insights"]["statement_quality"] == "Clean"
    assert result["transaction_insights"]["income_engine"]["income_type"] == "Salary"
    assert result["transactions"][0]["category"] == "VERIFIED_INCOME"
    assert result["transactions"][0]["confidence"] == 1.0
    assert "Final risk score: 23/100 (low)." in result["reasoning"]["narrative"][0]


def test_build_output_uses_canonical_score_for_decision_reason_and_narrative(monkeypatch):
    monkeypatch.setattr(output_module, "apply_bank_statement_rule_engine", lambda transactions: transactions)
    monkeypatch.setattr(
        output_module,
        "deterministic_aggregate",
        lambda corrected: {
            "verified_income": 50000,
            "emi_total": 12000,
            "penalties_total": 500,
            "total_expenses": 21000,
            "negative_balance_count": 0,
            "min_balance": 900,
            "low_balance_events": 2,
            "low_balance_threshold": 1000,
            "avg_balance": 4200,
            "unverified_income": 5000,
            "cash_deposits": 0,
            "cash_withdrawals": 12000,
            "suspicious_count": 1,
            "duplicate_count": 0,
            "statement_summary": {
                "statement_start_date": "2024-01-01",
                "statement_end_date": "2024-04-30",
                "coverage_days": 120,
                "opening_balance": 5000.0,
                "closing_balance": 9100.0,
                "total_credits": 55000.0,
                "total_debits": 33500.0,
                "net_flow": 21500.0,
                "min_balance": 900.0,
                "max_balance": 18200.0,
                "avg_balance": 4200.0,
                "median_balance": 4300.0,
                "transaction_count": 3,
                "credit_count": 1,
                "debit_count": 1,
                "low_balance_count": 2,
                "balance_volatility": 2200.0,
            },
        },
    )
    monkeypatch.setattr(
        output_module,
        "compute_dti",
        lambda emi_total, verified_income, **kwargs: {"value": 0.24, "label": "moderate", "reliability": "verified"},
    )
    monkeypatch.setattr(output_module, "analyze_cash_behavior", lambda corrected, aggregate: {"stressScore": 27, "flags": []})
    monkeypatch.setattr(
        output_module,
        "compute_risk_scores",
        lambda corrected, aggregate, dti, cash_behavior, overall_confidence: {
            "incomeStability": 15,
            "balanceHealth": 10,
            "obligationLoad": 7,
            "spendingDiscipline": 6,
            "cashBehavior": 4,
            "riskPenalty": 3,
            "finalScore": 45,
            "riskFlags": ["Moderate cumulative score band."],
            "overallConfidence": overall_confidence,
        },
    )
    monkeypatch.setattr(
        output_module,
        "compute_income_engine",
        lambda corrected: {
            "income_type": "salary",
            "income_regularity_score": 58,
            "recurring_income_detected": True,
            "monthly_income_estimate": "50000",
            "confidence": 0.91,
        },
    )
    monkeypatch.setattr(
        output_module,
        "compute_cashflow_intelligence",
        lambda corrected, aggregate, income_engine: {
            "monthly_burn_rate": "high",
            "savings_ratio": 0.16,
            "net_flow": aggregate["statement_summary"]["net_flow"],
        },
    )
    monkeypatch.setattr(output_module, "compute_spending_intelligence", lambda corrected: {"expense_ratio": 0.42})
    monkeypatch.setattr(
        output_module,
        "compute_behavioral_flags",
        lambda corrected, aggregate, income_engine, cashflow: {"flags": [], "flag_details": []},
    )

    result = pipeline.build_bank_statement_output(
        transactions=[
            {
                "date": "2024-01-01",
                "description": "Salary Credit ACME",
                "credit": 50000,
                "debit": None,
                "balance": 50000,
                "category": "VERIFIED_INCOME",
                "confidence": "high",
            }
        ],
        statement_confidence=0.91,
        document_type="bank_statement",
    )

    assert result["risk_findings"]["risk_score"]["final_score"] == 45
    assert result["decision"]["decision_status"] == "manual_review"
    assert result["decision"]["decision_reason"] == (
        "Manual review: uncertainty_reason=risk_score=45/100 falls in the manual review band; "
        "key_risk_signal=income stability 15/20 - Salary income is present, but cadence or amount consistency is weaker than ideal (regularity: 58/100); "
        "follow_up=Review the flagged risk factors before final approval."
    )
    assert result["reasoning"]["summary"] == result["decision"]["decision_reason"]
    assert result["reasoning"]["narrative"][0] == "Final risk score: 45/100 (medium)."
    assert "Decision: REVIEW MANUALLY" in result["reasoning"]["narrative"]
    assert any(line.endswith(result["decision"]["decision_reason"]) for line in result["reasoning"]["narrative"])


def test_build_output_enforces_short_history_gate(monkeypatch):
    result = pipeline.build_bank_statement_output(
        transactions=[
            {
                "date": "2024-01-01",
                "description": "Salary Credit ACME",
                "credit": 50000,
                "debit": None,
                "balance": 52000,
                "category": "VERIFIED_INCOME",
                "confidence": "high",
            },
            {
                "date": "2024-01-03",
                "description": "Loan EMI Auto-Debit",
                "credit": None,
                "debit": 12000,
                "balance": 40000,
                "category": "EMI",
                "confidence": "high",
            },
            {
                "date": "2024-01-07",
                "description": "UPI Grocery",
                "credit": None,
                "debit": 3000,
                "balance": 37000,
                "category": "EXPENSE",
                "confidence": "high",
            },
        ],
        statement_confidence=0.91,
        document_type="bank_statement",
    )

    assert result["statement_summary"]["coverage_days"] == 7
    assert result["decision"]["decision_status"] == "insufficient_history"
    assert result["decision"]["decision_recommendation"] == "Manual review / request 3\u20136 months statement history"
    assert result["decision"]["required_followups"] == ["Request 3\u20136 months of bank statement history"]
    assert result["decision"]["risk_confidence"] == 0.4
    assert any("only 7 day(s)" in item for item in result["decision"]["analysis_limitations"])
    assert any("long-term income stability" in item.lower() for item in result["decision"]["analysis_limitations"])
    assert any("provisional" in item.lower() for item in result["decision"]["analysis_limitations"])
    assert result["transaction_insights"]["income_engine"]["income_type"] == "salary"
    assert result["transaction_insights"]["income_engine"]["monthly_income_estimate"] == "50000"
    assert result["transaction_insights"]["income_engine"]["monthly_inflows"] == {"2024-01": 50000.0}
    assert result["transaction_insights"]["income_engine"]["provisional"] is True
    assert result["transaction_insights"]["dti"] == {"value": 0.24, "label": "moderate", "reliability": "verified"}
    assert result["transaction_insights"]["income"]["monthly_estimate"] == "50000"
    assert result["transaction_insights"]["income"]["annual_estimate"] == 600000.0
    assert result["risk_findings"]["risk_score"]["final_score"] == 23
    assert result["risk_findings"]["explainable_risk"]["total_risk_score"] == 23
    assert "monthly_income" not in result
    assert "annual_income" not in result
    assert "debt_to_income_ratio" not in result


def test_build_output_short_history_reason_is_template_driven_for_low_liquidity_sample():
    result = pipeline.build_bank_statement_output(
        transactions=[
            {
                "date": "2024-01-22",
                "description": "UPI Credit Friend",
                "credit": 4000,
                "debit": None,
                "balance": 2500,
                "category": "UNVERIFIED_CREDIT",
                "confidence": "high",
            },
            {
                "date": "2024-01-25",
                "description": "UPI Refund",
                "credit": 7381,
                "debit": None,
                "balance": 7800,
                "category": "UNVERIFIED_CREDIT",
                "confidence": "high",
            },
            {
                "date": "2024-01-29",
                "description": "UPI Transfer Out",
                "credit": None,
                "debit": 12804,
                "balance": 157.14,
                "category": "EXPENSE",
                "confidence": "high",
            },
        ],
        statement_confidence=0.9,
        document_type="bank_statement",
    )

    decision_reason = result["decision"]["decision_reason"]

    assert result["statement_summary"]["coverage_days"] == 8
    assert result["decision"]["decision_status"] == "insufficient_history"
    assert decision_reason.startswith("Insufficient history: coverage_days=8")
    assert "stable_income_status=income present but long-term stability is not fully verified" in decision_reason
    assert "liquidity_signal=low" in decision_reason
    assert "outflows=" in decision_reason and "> inflows=" in decision_reason
    assert "next_action=Request 3\u20136 months of bank statement history" in decision_reason
    assert result["reasoning"]["summary"] == decision_reason
    assert any(line.endswith("Decision: INSUFFICIENT_HISTORY") for line in result["reasoning"]["narrative"])
    assert any(decision_reason in line for line in result["reasoning"]["narrative"])


def test_build_output_exposes_first_class_statement_summary_fields(monkeypatch):
    monkeypatch.setattr(output_module, "compute_income_engine", lambda corrected: {"income_type": "salary"})
    monkeypatch.setattr(
        output_module,
        "compute_cashflow_intelligence",
        lambda corrected, aggregate, income_engine: {"net_flow": aggregate["statement_summary"]["net_flow"]},
    )
    monkeypatch.setattr(output_module, "compute_spending_intelligence", lambda corrected: {"expense_ratio": 0.42})
    monkeypatch.setattr(
        output_module,
        "compute_behavioral_flags",
        lambda corrected, aggregate, income_engine, cashflow: {"flags": [], "flag_details": []},
    )
    monkeypatch.setattr(
        output_module,
        "compute_explainable_risk",
        lambda *args, **kwargs: {
            "total_risk_score": 28,
            "risk_level": "low",
            "risk_breakdown": {},
        },
    )
    monkeypatch.setattr(
        output_module,
        "compute_final_decision",
        lambda canonical_score, explainable, confidence: {
            "decision": "APPROVE",
            "reasons": ["Healthy liquidity profile across the covered period."],
            "risk_confidence": 0.88,
        },
    )

    result = pipeline.build_bank_statement_output(
        transactions=[
            {
                "date": "2024-01-01",
                "description": "B/F",
                "credit": None,
                "debit": None,
                "balance": 5000,
                "category": "UNKNOWN",
                "confidence": "high",
            },
            {
                "date": "2024-01-03",
                "description": "Salary Credit",
                "credit": 2500,
                "debit": None,
                "balance": 7500,
                "category": "VERIFIED_INCOME",
                "confidence": "high",
            },
            {
                "date": "2024-01-05",
                "description": "ATM Withdrawal",
                "credit": None,
                "debit": 6800,
                "balance": 700,
                "category": "CASH_FLOW",
                "confidence": "high",
            },
            {
                "date": "2024-01-07",
                "description": "UPI Credit",
                "credit": 2700,
                "debit": None,
                "balance": 3400,
                "category": "UNVERIFIED_CREDIT",
                "confidence": "high",
            },
        ],
        statement_confidence=0.88,
        document_type="bank_statement",
    )

    summary = result["statement_summary"]
    score = result["risk_findings"]["risk_score"]

    assert summary == {
        "statement_start_date": "2024-01-01",
        "statement_end_date": "2024-01-07",
        "declared_period_start_date": None,
        "declared_period_end_date": None,
        "last_transaction_date": "2024-01-07",
        "coverage_days": 7,
        "opening_balance": 5000.0,
        "closing_balance": 3400.0,
        "total_credits": 5200.0,
        "total_debits": 6800.0,
        "net_flow": -1600.0,
        "min_balance": 700.0,
        "max_balance": 7500.0,
        "avg_balance": 4150.0,
        "median_balance": 4200.0,
        "transaction_count": 4,
        "credit_count": 2,
        "debit_count": 1,
        "low_balance_count": 1,
        "balance_volatility": 2470.32,
        "recurring_income_detected": False,
        "emi_pattern_detected": False,
        "pass_through_transfer_detected": False,
        "verification_credits_detected": False,
    }
    assert _sum_visible_score_components(score) == score["final_score"]


def test_build_output_keeps_boundary_balances_null_when_missing():
    result = pipeline.build_bank_statement_output(
        transactions=[
            {
                "date": "2024-01-01",
                "description": "Opening row without balance",
                "credit": 1000,
                "debit": None,
                "balance": None,
                "category": "UNVERIFIED_CREDIT",
                "confidence": "high",
            },
            {
                "date": "2024-01-02",
                "description": "Salary Credit",
                "credit": 2000,
                "debit": None,
                "balance": 3000,
                "category": "VERIFIED_INCOME",
                "confidence": "high",
            },
            {
                "date": "2024-01-03",
                "description": "Closing row without balance",
                "credit": None,
                "debit": 500,
                "balance": None,
                "category": "EXPENSE",
                "confidence": "high",
            },
        ],
        statement_confidence=0.9,
        document_type="bank_statement",
    )

    assert result["statement_summary"]["opening_balance"] is None
    assert result["statement_summary"]["closing_balance"] is None
    assert result["transaction_insights"]["balance"]["opening"] is None
    assert result["transaction_insights"]["balance"]["closing"] is None
    assert result["statement_summary"]["avg_balance"] == 3000.0


def test_build_output_flags_semantic_noise_without_treating_it_as_income():
    result = pipeline.build_bank_statement_output(
        transactions=[
            {
                "date": "2024-01-05",
                "description": "Penny Drop Account Verification",
                "credit": 1,
                "debit": None,
                "balance": 5001,
                "category": "UNVERIFIED_CREDIT",
                "confidence": "high",
            },
            {
                "date": "2024-02-05",
                "description": "Penny Drop Account Verification",
                "credit": 1,
                "debit": None,
                "balance": 5002,
                "category": "UNVERIFIED_CREDIT",
                "confidence": "high",
            },
            {
                "date": "2024-02-10",
                "description": "IMPS transfer from own account",
                "credit": 10000,
                "debit": None,
                "balance": 15002,
                "category": "UNVERIFIED_CREDIT",
                "confidence": "high",
            },
            {
                "date": "2024-02-10",
                "description": "UPI transfer to own account",
                "credit": None,
                "debit": 10000,
                "balance": 5002,
                "category": "CASH_FLOW",
                "confidence": "high",
            },
        ],
        statement_confidence=0.95,
        document_type="bank_statement",
    )

    summary = result["statement_summary"]

    assert summary["recurring_income_detected"] is False
    assert summary["emi_pattern_detected"] is False
    assert summary["pass_through_transfer_detected"] is True
    assert summary["verification_credits_detected"] is True
    assert result["transaction_insights"]["income"]["verified"] == 0
    assert result["transaction_insights"]["income"]["unverified"] == 0
    assert result["transaction_insights"]["income_engine"]["income_type"] == "unknown"
    assert result["transaction_insights"]["income_engine"]["confidence"] == 0.3
    assert result["transaction_insights"]["income_engine"]["monthly_inflows"] == {}
    assert result["transactions"][0]["verification_credit"] is True
    assert result["transactions"][2]["pass_through_transfer"] is True
    assert result["transactions"][3]["pass_through_transfer"] is True


def test_generic_transfer_credits_do_not_create_verified_income_or_reliable_dti():
    result = pipeline.build_bank_statement_output(
        transactions=[
            {
                "date": "2024-01-05",
                "description": "TRTR Credit",
                "credit": 10000,
                "debit": None,
                "balance": 15000,
                "category": "VERIFIED_INCOME",
                "confidence": "high",
            },
            {
                "date": "2024-02-05",
                "description": "DIGITB Credit",
                "credit": 12000,
                "debit": None,
                "balance": 27000,
                "category": "VERIFIED_INCOME",
                "confidence": "high",
            },
            {
                "date": "2024-02-10",
                "description": "Loan EMI Auto-Debit",
                "credit": None,
                "debit": 5000,
                "balance": 22000,
                "category": "EMI",
                "confidence": "high",
            },
        ],
        statement_confidence=0.9,
        document_type="bank_statement",
    )

    assert result["transaction_insights"]["income"]["verified"] == 0
    assert result["transaction_insights"]["income"]["verified_monthly_estimate"] is None
    assert result["transaction_insights"]["income"]["unverified_monthly_inflow_range"] == {
        "min": 10000.0,
        "max": 12000.0,
        "display": "10000-12000",
    }
    assert result["transaction_insights"]["dti"]["reliability"] == "unverified"
    assert all(transaction["category"] == "UNVERIFIED_CREDIT" for transaction in result["transactions"][:2])


def test_build_output_detects_recurring_income_and_emi_patterns():
    result = pipeline.build_bank_statement_output(
        transactions=[
            {
                "date": "2024-01-31",
                "description": "Monthly Salary ACME",
                "credit": 50000,
                "debit": None,
                "balance": 60000,
                "category": "VERIFIED_INCOME",
                "confidence": "high",
            },
            {
                "date": "2024-04-30",
                "description": "Monthly Salary ACME",
                "credit": 51000,
                "debit": None,
                "balance": 68000,
                "category": "VERIFIED_INCOME",
                "confidence": "high",
            },
            {
                "date": "2024-01-05",
                "description": "Loan EMI Auto-Debit",
                "credit": None,
                "debit": 12000,
                "balance": 10000,
                "category": "EMI",
                "confidence": "high",
            },
            {
                "date": "2024-04-05",
                "description": "Loan EMI Auto-Debit",
                "credit": None,
                "debit": 12000,
                "balance": 56000,
                "category": "EMI",
                "confidence": "high",
            },
        ],
        statement_confidence=0.96,
        document_type="bank_statement",
    )

    summary = result["statement_summary"]

    assert summary["recurring_income_detected"] is True
    assert summary["emi_pattern_detected"] is True
    assert summary["pass_through_transfer_detected"] is False
    assert summary["verification_credits_detected"] is False


def test_compute_income_engine_excludes_verification_credits_from_income_logic():
    corrected = pipeline.apply_bank_statement_rule_engine(
        [
            {
                "date": "2024-01-05",
                "description": "Penny Drop Account Verification",
                "credit": 1,
                "debit": None,
                "balance": 5001,
                "category": "UNVERIFIED_CREDIT",
                "confidence": "high",
            },
            {
                "date": "2024-01-06",
                "description": "Salary Credit ACME",
                "credit": 50000,
                "debit": None,
                "balance": 55001,
                "category": "VERIFIED_INCOME",
                "confidence": "high",
            },
            {
                "date": "2024-02-05",
                "description": "Penny Drop Account Verification",
                "credit": 1,
                "debit": None,
                "balance": 55002,
                "category": "UNVERIFIED_CREDIT",
                "confidence": "high",
            },
        ]
    )

    income_engine = compute_income_engine(corrected)

    assert corrected[0]["verification_credit"] is True
    assert corrected[2]["verification_credit"] is True
    assert income_engine["salary_credits"] == [50000.0]
    assert income_engine["upi_credits"] == []
    assert income_engine["transfer_credits"] == []
    assert income_engine["other_credits"] == []
    assert income_engine["monthly_inflows"] == {"2024-01": 50000.0}
    assert income_engine["income_sources"] == [
        {"type": "salary", "avg": 50000.0, "count": 1, "total": 50000.0}
    ]


def test_compute_income_engine_excludes_pass_through_transfers_from_stable_income_logic():
    corrected = pipeline.apply_bank_statement_rule_engine(
        [
            {
                "date": "2024-01-10",
                "description": "IMPS transfer from own account",
                "credit": 15000,
                "debit": None,
                "balance": 25000,
                "category": "UNVERIFIED_CREDIT",
                "confidence": "high",
            },
            {
                "date": "2024-01-10",
                "description": "UPI transfer to own account",
                "credit": None,
                "debit": 15000,
                "balance": 10000,
                "category": "CASH_FLOW",
                "confidence": "high",
            },
            {
                "date": "2024-02-10",
                "description": "IMPS transfer from own account",
                "credit": 15000,
                "debit": None,
                "balance": 26000,
                "category": "UNVERIFIED_CREDIT",
                "confidence": "high",
            },
            {
                "date": "2024-02-10",
                "description": "UPI transfer to own account",
                "credit": None,
                "debit": 15000,
                "balance": 11000,
                "category": "CASH_FLOW",
                "confidence": "high",
            },
        ]
    )

    income_engine = compute_income_engine(corrected)

    assert corrected[0]["pass_through_transfer"] is True
    assert corrected[1]["pass_through_transfer"] is True
    assert corrected[2]["pass_through_transfer"] is True
    assert corrected[3]["pass_through_transfer"] is True
    assert income_engine["transfer_credits"] == []
    assert income_engine["monthly_inflows"] == {}
    assert income_engine["income_sources"] == []
    assert income_engine["monthly_income_estimate"] == "0"
    assert income_engine["recurring_income_detected"] is False


def test_short_history_sample_fixture_exposes_expected_statement_facts():
    expected = load_short_history_sample_expected()

    result = pipeline.build_bank_statement_output(
        transactions=load_short_history_sample_transactions(),
        statement_confidence=expected["statement_confidence"],
        document_type="bank_statement",
    )

    assert result["decision"]["decision_status"] == expected["decision_status"]
    assert result["decision"]["decision_recommendation"] == expected["decision_recommendation"]
    assert result["decision"]["decision_reason"] == expected["decision_reason"]
    assert result["decision"]["required_followups"] == expected["required_followups"]
    assert result["decision"]["analysis_limitations"] == expected["analysis_limitations"]
    assert result["statement_summary"] == expected["statement_summary"]


def test_short_history_sample_fixture_exposes_provisional_income_and_dti_outputs():
    expected = load_short_history_sample_expected()

    result = pipeline.build_bank_statement_output(
        transactions=load_short_history_sample_transactions(),
        statement_confidence=expected["statement_confidence"],
        document_type="bank_statement",
    )

    assert result["decision"]["decision_status"] == "insufficient_history"
    assert result["transaction_insights"]["income"]["verified_monthly_estimate"] is None
    assert result["transaction_insights"]["income"]["monthly_estimate"] is None
    assert result["transaction_insights"]["income"]["annual_estimate"] is None
    assert result["transaction_insights"]["income"]["unverified_monthly_inflow_range"] == {
        "min": 11381.0,
        "max": 11381.0,
        "display": "11381",
    }
    assert result["transaction_insights"]["dti"] == {"value": 0.0, "label": "low", "reliability": "unverified"}
    assert result["transaction_insights"]["income_engine"]["income_type"] == "unstable"
    assert result["transaction_insights"]["income_engine"]["monthly_income_estimate"] == "11381"
    assert result["transaction_insights"]["income_engine"]["monthly_inflows"] == {"2024-01": 11381.0}
    assert result["transaction_insights"]["income_engine"]["provisional"] is True
    assert result["risk_findings"]["risk_score"]["final_score"] == 55
    assert result["risk_findings"]["explainable_risk"]["total_risk_score"] == 55
    assert "monthly_income" not in result
    assert "annual_income" not in result
    assert "debt_to_income_ratio" not in result


def test_bank_statement_output_clamps_all_confidence_values_to_unit_interval():
    result = pipeline.build_bank_statement_output(
        transactions=load_short_history_sample_transactions(),
        statement_confidence=91,
        document_type="bank_statement",
    )

    confidence_values = _collect_confidence_values(result)

    assert confidence_values
    for key, value in confidence_values:
        assert 0.0 <= float(value) <= 1.0, f"{key}={value} was not normalized"
    assert result["decision"]["risk_confidence"] == 0.4
    assert result["decision"]["extraction_confidence"] == 0.91


def test_build_output_preserves_income_range_display_and_emits_numeric_bounds():
    result = pipeline.build_bank_statement_output(
        transactions=[
            {
                "date": "2024-01-01",
                "description": "Salary Credit ACME",
                "credit": 45000,
                "debit": None,
                "balance": 45000,
                "category": "SALARY",
                "confidence": "high",
            },
            {
                "date": "2024-04-01",
                "description": "Salary Credit ACME",
                "credit": 67000,
                "debit": None,
                "balance": 112000,
                "category": "SALARY",
                "confidence": "high",
            },
        ],
        statement_confidence=0.93,
        document_type="bank_statement",
    )

    assert result["transaction_insights"]["income_engine"]["monthly_income_estimate"] == "45000-67000"
    assert result["transaction_insights"]["income_engine"]["monthly_income_estimate_min"] == 45000
    assert result["transaction_insights"]["income_engine"]["monthly_income_estimate_max"] == 67000
    assert result["transaction_insights"]["income_engine"]["annual_income_estimate_min"] == 540000.0
    assert result["transaction_insights"]["income_engine"]["annual_income_estimate_max"] == 804000.0
    assert result["transaction_insights"]["income"]["verified_monthly_estimate"] == 56000.0
    assert result["transaction_insights"]["income"]["monthly_estimate"] == "45000-67000"
    assert result["transaction_insights"]["income"]["monthly_estimate_min"] == 45000
    assert result["transaction_insights"]["income"]["monthly_estimate_max"] == 67000
    assert result["transaction_insights"]["income"]["annual_estimate"] == 672000.0
    assert result["transaction_insights"]["income"]["annual_estimate_min"] == 540000.0
    assert result["transaction_insights"]["income"]["annual_estimate_max"] == 804000.0
