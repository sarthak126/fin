from datetime import date

from core.confidence import normalize_confidence
from services.bank_statement_engine import (
    compute_behavioral_flags,
    compute_explainable_risk,
    compute_final_decision,
    compute_income_engine,
    compute_spending_intelligence,
)
from core.bank_statement_score import build_bank_statement_score_payload
from services.bank_statement_engine_common import extract_month_key, parse_statement_date
from services.bank_statement_local_parser import classify_bank_transactions_locally
from services.bank_statement_pipeline_types import is_penalty


def test_income_engine_detects_salary_pattern():
    result = compute_income_engine(
        [
            {"date": "2024-01-31", "description": "Monthly Salary ACME", "credit": 50000, "duplicate": False},
            {"date": "2024-02-29", "description": "Monthly Salary ACME", "credit": 52000, "duplicate": False},
            {"date": "2024-02-15", "description": "UPI from friend", "credit": 1500, "duplicate": False},
        ]
    )

    assert result["income_type"] == "salary"
    assert result["confidence"] == 1.0
    assert result["recurring_income_detected"] is True
    assert result["recurring_income_source"] == "ACME"
    assert result["recurring_income_estimate"] == 51000.0
    assert result["recurring_income_months"] == 2
    assert result["monthly_inflows"] == {"2024-01": 50000.0, "2024-02": 53500.0}
    assert result["income_sources"][0]["type"] == "salary"


def test_extract_month_key_supports_two_digit_statement_dates():
    assert extract_month_key("31-01-24") == "2024-01"
    assert extract_month_key("01/07/22") == "2022-07"
    assert extract_month_key("2024/07/31") == "2024-07"


def test_date_helpers_validate_months_and_reject_invalid_dates_safely():
    assert parse_statement_date("2024/07/31") == date(2024, 7, 31)
    assert parse_statement_date("31/13/2024") is None
    assert extract_month_key("2024-13") is None


def test_normalize_confidence_treats_small_numeric_values_as_percentages_not_maximum():
    assert normalize_confidence(2.0) == 0.02
    assert normalize_confidence("2%") == 0.02


def test_income_engine_preserves_other_credit_sources_and_two_digit_months():
    result = compute_income_engine(
        [
            {"date": "31-01-24", "description": "Disbursement Credit", "credit": 100000, "duplicate": False},
            {"date": "15-02-24", "description": "UPI/friend transfer", "credit": 5000, "duplicate": False},
        ]
    )

    assert result["monthly_inflows"] == {"2024-01": 100000.0, "2024-02": 5000.0}
    assert any(source["type"] == "other_credits" and source["total"] == 100000.0 for source in result["income_sources"])


def test_income_engine_excludes_semantic_noise_from_income_confidence():
    result = compute_income_engine(
        [
            {
                "date": "2024-01-05",
                "description": "Penny Drop Account Verification",
                "credit": 1,
                "duplicate": False,
                "verification_credit": True,
            },
            {
                "date": "2024-02-05",
                "description": "Penny Drop Account Verification",
                "credit": 1,
                "duplicate": False,
                "verification_credit": True,
            },
            {
                "date": "2024-02-11",
                "description": "IMPS transfer in",
                "credit": 10000,
                "duplicate": False,
                "pass_through_transfer": True,
            },
        ]
    )

    assert result["income_type"] == "unknown"
    assert result["confidence"] == 0.3
    assert result["monthly_inflows"] == {}
    assert result["recurring_income_detected"] is False


def test_penalty_detection_excludes_routine_sms_alert_fees():
    assert is_penalty("Bounce penalty charge") is True
    assert is_penalty("SMS Alert charges for Qtr Jun-21") is False

    classified = classify_bank_transactions_locally(
        [
            {
                "date": "04-06-21",
                "description": "SMS Alert charges for Qtr Jun-21",
                "debit": 17.7,
                "credit": None,
                "balance": 16977.81,
            }
        ]
    )

    assert classified[0]["category"] == "EXPENSE"


def test_spending_engine_groups_categories_and_top_merchants():
    result = compute_spending_intelligence(
        [
            {"description": "Swiggy order dinner", "debit": 900, "duplicate": False},
            {"description": "Amazon purchase", "debit": 2100, "duplicate": False},
            {"description": "Swiggy order lunch", "debit": 600, "duplicate": False},
        ]
    )

    assert result["total_spending"] == 3600.0
    assert result["category_amounts"]["shopping"] == 2100.0
    assert result["category_amounts"]["food_dining"] == 1500.0
    assert result["top_merchants"][0]["name"] in {"amazon purchase", "swiggy order dinner", "swiggy order lunch"}


def test_behavior_flags_do_not_override_score_band_decision():
    behavioral = compute_behavioral_flags(
        transactions=[
            {"date": "2024-01-01", "description": "ATM cash withdrawal", "debit": 25000, "balance": 400, "duplicate": False},
            {"date": "2024-01-02", "description": "ATM cash withdrawal", "debit": 26000, "balance": 350, "duplicate": False},
            {"date": "2024-01-03", "description": "ATM cash withdrawal", "debit": 24000, "balance": 300, "duplicate": False},
            {"date": "2024-01-04", "description": "Snack shop", "debit": 120, "balance": 280, "duplicate": False},
            {"date": "2024-01-05", "description": "Snack shop", "debit": 140, "balance": 260, "duplicate": False},
            {"date": "2024-01-06", "description": "Penalty fee", "debit": 500, "balance": 200, "duplicate": False, "category": "PENALTY"},
        ],
        agg={"avg_balance": 298, "low_balance_events": 6, "negative_balance_count": 0},
        income_engine={"income_type": "unknown", "cash_deposits": [], "monthly_inflows": {"2024-01": 10000}},
        cashflow={"savings_trend": "declining", "monthly_burn_rate": "critical"},
    )

    decision = compute_final_decision(
        canonical_risk_score=build_bank_statement_score_payload(
            income_stability=6,
            balance_health=4,
            obligation_load=3,
            spending_discipline=4,
            cash_behavior=3,
            risk_penalty=2,
        ),
        explainable_risk={
            "total_risk_score": 22,
            "risk_breakdown": {},
        },
        overall_confidence=0.4,
    )

    assert any(detail["flag"] == "irregular_income" for detail in behavioral["flag_details"])
    assert decision["decision"] == "APPROVE"
    assert decision["risk_confidence"] == 0.4


def test_explainable_risk_is_a_view_over_the_canonical_score():
    canonical_score = build_bank_statement_score_payload(
        income_stability=11,
        balance_health=7,
        obligation_load=5,
        spending_discipline=9,
        cash_behavior=4,
        risk_penalty=3,
    )

    explainable = compute_explainable_risk(
        canonical_score,
        agg={
            "avg_balance": 4200,
            "min_balance": 900,
            "low_balance_events": 2,
            "low_balance_threshold": 1000,
            "negative_balance_count": 0,
            "emi_total": 12000,
            "verified_income": 50000,
            "unverified_income": 5000,
            "cash_deposits": 0,
            "cash_withdrawals": 18000,
            "total_expenses": 21000,
            "penalties_total": 500,
            "suspicious_count": 1,
            "duplicate_count": 1,
        },
        income_engine={
            "income_type": "salary",
            "income_regularity_score": 58,
            "recurring_income_detected": True,
        },
        cash_behavior={
            "stressScore": 27,
            "flags": ["Weak end-of-statement balance trend"],
        },
        cashflow={
            "monthly_burn_rate": "high",
            "savings_ratio": 0.16,
        },
        behavioral={
            "flag_details": [
                {"flag": "low_balance_risk", "severity": "medium", "detail": "Balance dropped below Rs1,000."}
            ]
        },
        dti={"label": "moderate", "value": 0.24},
        overall_confidence=0.91,
    )

    assert explainable["total_risk_score"] == canonical_score["final_score"]
    assert explainable["risk_level"] == "medium"
    assert set(explainable["risk_breakdown"]) == {
        "income_stability",
        "balance_health",
        "obligation_load",
        "spending_discipline",
        "cash_behavior",
        "risk_penalty",
    }
    assert explainable["risk_breakdown"]["income_stability"]["score"] == canonical_score["income_stability"]
    assert explainable["risk_breakdown"]["balance_health"]["score"] == canonical_score["balance_health"]
    assert explainable["risk_breakdown"]["obligation_load"]["score"] == canonical_score["obligation_load"]
    assert explainable["risk_breakdown"]["spending_discipline"]["score"] == canonical_score["spending_discipline"]
    assert explainable["risk_breakdown"]["cash_behavior"]["score"] == canonical_score["cash_behavior"]
    assert explainable["risk_breakdown"]["risk_penalty"]["score"] == canonical_score["risk_penalty"]


def test_final_decision_uses_canonical_score_bands_only():
    approve_score = build_bank_statement_score_payload(
        income_stability=10,
        balance_health=8,
        obligation_load=4,
        spending_discipline=5,
        cash_behavior=3,
        risk_penalty=1,
    )
    approve_risk = {
        "risk_breakdown": {
            "income_stability": {"score": 10, "max": 20, "detail": "Recurring income has some variability."},
            "balance_health": {"score": 8, "max": 20, "detail": "Balances show occasional pressure."},
        },
        "total_risk_score": approve_score["final_score"],
    }
    manual_review_score = build_bank_statement_score_payload(
        income_stability=15,
        balance_health=10,
        obligation_load=7,
        spending_discipline=6,
        cash_behavior=4,
        risk_penalty=3,
    )
    manual_review_risk = {
        "risk_breakdown": {
            "income_stability": {"score": 15, "max": 20, "detail": "Recurring income is weakly evidenced."},
            "balance_health": {"score": 10, "max": 20, "detail": "Liquidity stress remains visible."},
            "obligation_load": {"score": 7, "max": 15, "detail": "EMI burden is moderate."},
        },
        "total_risk_score": manual_review_score["final_score"],
    }
    reject_score = build_bank_statement_score_payload(
        income_stability=20,
        balance_health=14,
        obligation_load=15,
        spending_discipline=11,
        cash_behavior=7,
        risk_penalty=5,
    )
    reject_risk = {
        "risk_breakdown": {
            "income_stability": {"score": 20, "max": 20, "detail": "No verified recurring income was detected."},
            "obligation_load": {"score": 15, "max": 15, "detail": "EMI burden is extreme."},
            "balance_health": {"score": 14, "max": 20, "detail": "Balance stress is persistent."},
        },
        "total_risk_score": reject_score["final_score"],
    }

    approve = compute_final_decision(
        canonical_risk_score=approve_score,
        explainable_risk=approve_risk,
        overall_confidence=0.91,
    )
    manual_review = compute_final_decision(
        canonical_risk_score=manual_review_score,
        explainable_risk=manual_review_risk,
        overall_confidence=0.91,
    )
    reject = compute_final_decision(
        canonical_risk_score=reject_score,
        explainable_risk=reject_risk,
        overall_confidence=0.91,
    )

    assert approve["decision"] == "APPROVE"
    assert approve["reasons"][0] == "Risk score 31/100 is in the approve band."
    assert approve["reason_context"]["stability_signal"].startswith("risk_score=31/100 remains in the approve band")
    assert approve["reason_context"]["blockers_signal"] == "none identified from the canonical score"

    assert manual_review["decision"] == "REVIEW MANUALLY"
    assert manual_review["reasons"][0] == "Risk score 45/100 is in the manual review band."
    assert manual_review["reason_context"]["uncertainty_reason"] == "risk_score=45/100 falls in the manual review band"
    assert "income stability 15/20" in manual_review["reason_context"]["key_risk_signal"]

    assert reject["decision"] == "REJECT"
    assert reject["reasons"][0] == "Risk score 72/100 is in the reject band."
    assert "income stability 20/20" in reject["reason_context"]["primary_risk_driver"]
    assert "obligation load 15/15" in reject["reason_context"]["obligation_signal"]
