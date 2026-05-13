import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import asyncio
import json
from services.analysis_service import (
    build_bank_statement_output,
    run_strict_bank_statement_pipeline,
)

messy_ocr_sample = """
HDFC BANK LTD
Acct Name: John Doe
Period: 01-Jan-2026 to 31-Jan-2026

Date       Narration                      Chq/RefNo     ValueDt    WithdrawalAmt     DepositAmt    ClosingBalance
01/01/26   BY SALARY / TECHCORP           -             01/01/26                     85000.00      85000.00
05/01/26   TO ATM WDL / LINK ROAD         -             05/01/26   10000.00                        75000.00
10/01/26   UPI/Rent/Landlord              upi123        10/01/26   20000.00                        55000.00
15/01/26   CASH DEPOSIT BRANCH 12         -             15/01/26                     5000.00       60000.00
20/01/26   LOAN EMI AUTODEBIT             emi456        20/01/26   15000.00                        45000.00
25/01/26   LATE PMT PENALTY               -             25/01/26   500.00                          44500.00
30/01/26   NEFT/UNKNOWN/FRIEND            -             30/01/26                     2000.00       46500.00
"""


def _sum_visible_score_components(score: dict) -> int:
    return (
        score["income_stability"]
        + score["balance_health"]
        + score["obligation_load"]
        + score["spending_discipline"]
        + score["cash_behavior"]
        + score["risk_penalty"]
    )

def _assert_strict_output_shape(out: dict) -> None:
    required_top = [
        "decision",
        "statement_summary",
        "transaction_insights",
        "risk_findings",
        "reasoning",
        "transactions",
    ]
    for k in required_top:
        assert k in out, f"Missing top-level key: {k}"

    assert set(out) == set(required_top), "Dedicated bank statement output must only expose the six top-level sections"
    assert isinstance(out["transactions"], list), "transactions must be a list"
    assert isinstance(out["risk_findings"]["flags"], list), "risk_findings.flags must be a list"
    assert isinstance(out["reasoning"]["narrative"], list), "reasoning.narrative must be a list"
    assert isinstance(out["reasoning"]["analysis_limitations"], list), "reasoning.analysis_limitations must be a list"

    tx_required = [
        "date",
        "description",
        "debit",
        "credit",
        "balance",
        "category",
        "confidence",
        "duplicate",
        "reversal",
        "notes",
    ]
    for t in out["transactions"]:
        for k in tx_required:
            assert k in t, f"Missing transaction key: {k}"

    # DTI block
    dti = out["transaction_insights"]["dti"]
    assert "value" in dti and "label" in dti, "dti must have value + label"

    # Risk score breakdown
    for comp in [
        "score_model",
        "income_stability",
        "balance_health",
        "obligation_load",
        "spending_discipline",
        "cash_behavior",
        "risk_penalty",
        "final_score",
    ]:
        assert comp in out["risk_findings"]["risk_score"], f"Missing risk_score component: {comp}"
    assert _sum_visible_score_components(out["risk_findings"]["risk_score"]) == out["risk_findings"]["risk_score"]["final_score"], (
        "Visible bank-statement sub-scores must add up to final_score"
    )
    explainable_risk = out["risk_findings"].get("explainable_risk") or {}
    assert explainable_risk.get("total_risk_score") == out["risk_findings"]["risk_score"]["final_score"], (
        "Explainable risk must reuse the canonical final_score"
    )


async def test_ocr_noisy_e2e():
    print("Running bank statement pipeline E2E test (messy OCR)...")
    # This E2E test calls Gemini. Skip safely when no API key is configured.
    if not os.getenv("GOOGLE_API_KEY"):
        print("Skipping noisy OCR E2E test: GOOGLE_API_KEY not set.")
        return
    out = await run_strict_bank_statement_pipeline(messy_ocr_sample, document_type_hint="bank_statement")
    _assert_strict_output_shape(out)

    # Core invariants from the sample OCR (these must be stable)
    assert out["transaction_insights"]["cash_flow"]["withdrawals"] >= 0, "withdrawals must be numeric"
    assert out["transaction_insights"]["cash_flow"]["deposits"] >= 0, "deposits must be numeric"
    assert out["transaction_insights"]["expenses"]["emi"] >= 0, "emi must be numeric"
    assert out["transaction_insights"]["expenses"]["penalties"] >= 0, "penalties must be numeric"
    assert 0 <= out["risk_findings"]["risk_score"]["final_score"] <= 100, "final_score must be 0-100"
    assert out["decision"], "decision must be non-empty"


def test_synthetic_atm_is_not_expense():
    print("Synthetic: ATM withdrawal is CASH_FLOW (not EXPENSE)")
    txns = [
        {"date": "2026-01-01", "description": "Salary CREDIT", "debit": None, "credit": 50000, "balance": 50000, "category": "VERIFIED_INCOME", "confidence": "high"},
        {"date": "2026-01-05", "description": "TO ATM WDL / LINK ROAD", "debit": 10000, "credit": None, "balance": 40000, "category": "EXPENSE", "confidence": "medium"},
        {"date": "2026-01-10", "description": "Loan EMI AUTODEBIT", "debit": 5000, "credit": None, "balance": 35000, "category": "EMI", "confidence": "high"},
    ]
    out = build_bank_statement_output(txns, statement_confidence=0.9, document_type="bank_statement")
    _assert_strict_output_shape(out)
    assert out["transaction_insights"]["cash_flow"]["withdrawals"] == 10000.0, "ATM withdrawal must be tracked as cash_flow.withdrawals"
    assert out["transaction_insights"]["expenses"]["total"] == 0.0, "ATM withdrawal must not be included in expenses.total"
    assert out["transaction_insights"]["expenses"]["emi"] == 5000.0, "EMI must aggregate correctly"
    assert out["transaction_insights"]["dti"]["label"] == "unknown", "Short statement history should suppress DTI inference"


def test_synthetic_cash_deposit_is_not_verified_income():
    print("Synthetic: cash deposit is NOT verified income")
    txns = [
        {"date": "2026-01-01", "description": "CASH DEPOSIT BRANCH 12", "debit": None, "credit": 15000, "balance": 15000, "category": "VERIFIED_INCOME", "confidence": "medium"},
        {"date": "2026-01-10", "description": "NEFT/UNKNOWN/FRIEND", "debit": None, "credit": 5000, "balance": 20000, "category": "UNVERIFIED_CREDIT", "confidence": "low"},
    ]
    out = build_bank_statement_output(txns, statement_confidence=0.7, document_type="bank_statement")
    _assert_strict_output_shape(out)
    assert out["transaction_insights"]["income"]["verified"] == 0.0, "Cash deposits must not be counted as verified income"
    assert out["transaction_insights"]["cash_flow"]["deposits"] == 15000.0, "Cash deposits must be tracked separately"


def test_synthetic_reversal_offsets_emi():
    print("Synthetic: reversal offsets EMI")
    txns = [
        {"date": "2026-01-01", "description": "LOAN EMI AUTODEBIT", "debit": 8000, "credit": None, "balance": 20000, "category": "EMI", "confidence": "high"},
        {"date": "2026-01-02", "description": "LOAN EMI AUTODEBIT REVERSAL", "debit": None, "credit": 8000, "balance": 28000, "category": "EMI", "confidence": "high"},
    ]
    out = build_bank_statement_output(txns, statement_confidence=0.9, document_type="bank_statement")
    _assert_strict_output_shape(out)
    assert out["transaction_insights"]["expenses"]["emi"] == 0.0, "Reversal should offset EMI debit"


def test_synthetic_duplicates_are_flagged_and_ignored():
    print("Synthetic: duplicates detected and not double-counted")
    txns = [
        {"date": "2026-01-03", "description": "GROCERY STORE", "debit": 2000, "credit": None, "balance": 18000, "category": "EXPENSE", "confidence": "high"},
        {"date": "2026-01-03", "description": "GROCERY STORE", "debit": 2000, "credit": None, "balance": 18000, "category": "EXPENSE", "confidence": "high"},
    ]
    out = build_bank_statement_output(txns, statement_confidence=0.9, document_type="bank_statement")
    _assert_strict_output_shape(out)
    assert out["transaction_insights"]["expenses"]["total"] == 2000.0, "Duplicate items must not be double-counted"
    dup_flags = [t.get("duplicate") for t in out["transactions"]]
    assert any(dup_flags), "At least one transaction should be marked duplicate"


def test_synthetic_negative_balance_flag():
    print("Synthetic: negative balance triggers risk flags")
    txns = [
        {"date": "2026-01-01", "description": "Salary CREDIT", "debit": None, "credit": 10000, "balance": 10000, "category": "VERIFIED_INCOME", "confidence": "high"},
        {"date": "2026-01-05", "description": "Big expense", "debit": 20000, "credit": None, "balance": -10000, "category": "EXPENSE", "confidence": "medium"},
    ]
    out = build_bank_statement_output(txns, statement_confidence=0.8, document_type="bank_statement")
    _assert_strict_output_shape(out)
    assert any("Negative balance" in f for f in out["risk_findings"]["flags"]), "Negative balance must appear in risk_findings.flags"


def test_synthetic_high_cash_withdrawal_ratio():
    print("Synthetic: high cash withdrawal ratio triggers cash stress")
    txns = [
        {"date": "2026-01-01", "description": "Salary CREDIT", "debit": None, "credit": 100000, "balance": 100000, "category": "VERIFIED_INCOME", "confidence": "high"},
        {"date": "2026-01-05", "description": "TO ATM WDL", "debit": 70000, "credit": None, "balance": 30000, "category": "CASH_FLOW", "confidence": "medium"},
    ]
    out = build_bank_statement_output(txns, statement_confidence=0.8, document_type="bank_statement")
    _assert_strict_output_shape(out)
    assert out["transaction_insights"]["cash_behavior"]["stress_score"] >= 20, "High cash withdrawal ratio should increase stressScore"
    assert any(
        "cash withdrawal ratio" in f.lower()
        for f in out["transaction_insights"]["cash_behavior"]["flags"]
    ), "Cash stress flags should mention withdrawals"


def test_synthetic_unverified_credit_heavy():
    print("Synthetic: unverified credit heavy profile should not be risk-free")
    txns = [
        {"date": "2026-01-01", "description": "NEFT/UNKNOWN/FRIEND", "debit": None, "credit": 30000, "balance": 30000, "category": "UNVERIFIED_CREDIT", "confidence": "low"},
        {"date": "2026-01-10", "description": "NEFT/UNKNOWN/FRIEND", "debit": None, "credit": 20000, "balance": 50000, "category": "UNVERIFIED_CREDIT", "confidence": "low"},
    ]
    out = build_bank_statement_output(txns, statement_confidence=0.6, document_type="bank_statement")
    _assert_strict_output_shape(out)
    assert out["transaction_insights"]["income"]["verified"] == 0.0, "Verified income should be zero"
    assert out["risk_findings"]["risk_score"]["final_score"] >= 10, "Unverified credit heavy must carry risk"


async def run_all():
    await test_ocr_noisy_e2e()
    test_synthetic_atm_is_not_expense()
    test_synthetic_cash_deposit_is_not_verified_income()
    test_synthetic_reversal_offsets_emi()
    test_synthetic_duplicates_are_flagged_and_ignored()
    test_synthetic_negative_balance_flag()
    test_synthetic_high_cash_withdrawal_ratio()
    test_synthetic_unverified_credit_heavy()

if __name__ == "__main__":
    asyncio.run(run_all())
