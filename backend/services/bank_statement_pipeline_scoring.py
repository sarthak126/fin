"""
Risk component scoring for bank statement analysis.
"""

import math
from typing import Any, Dict, List

from services.bank_statement_engine_common import is_excluded_from_income_analysis
from services.bank_statement_pipeline_types import Transaction, safe_float


def compute_risk_scores(
    transactions: List[Transaction],
    aggregate: Dict[str, Any],
    dti: Dict[str, Any],
    cash_behavior: Dict[str, Any],
    overall_confidence: float,
) -> Dict[str, Any]:
    verified_income = aggregate["verified_income"]
    emi_total = aggregate["emi_total"]
    penalties = aggregate["penalties_total"]
    total_expenses = aggregate["total_expenses"]

    verified_transactions = [
        transaction
        for transaction in transactions
        if not transaction.get("duplicate")
        and not transaction.get("reversal")
        and not is_excluded_from_income_analysis(transaction)
        and transaction.get("category") == "VERIFIED_INCOME"
        and (safe_float(transaction.get("credit")) or 0.0) > 0
    ]
    income_amounts = [safe_float(transaction.get("credit")) for transaction in verified_transactions]
    income_amounts = [amount for amount in income_amounts if amount is not None]

    risk_flags: List[str] = []

    if verified_income <= 0 or not income_amounts:
        income_stability = 20
        risk_flags.append("No verified income detected.")
    else:
        if len(income_amounts) <= 1:
            income_stability = 15
            risk_flags.append("Irregular income: too few verified income events.")
        elif len(income_amounts) <= 3:
            income_stability = 10
        else:
            income_stability = 6

        mean_income = sum(income_amounts) / len(income_amounts)
        if mean_income > 0:
            variance = sum((amount - mean_income) ** 2 for amount in income_amounts) / max(len(income_amounts), 1)
            stdev = math.sqrt(variance)
            if stdev / mean_income > 0.5:
                income_stability = min(20, income_stability + 6)
                risk_flags.append("Irregular income amounts (high variability).")

    negative_count = aggregate["negative_balance_count"]
    min_balance = aggregate["min_balance"]
    low_events = aggregate["low_balance_events"]
    if negative_count > 0:
        balance_health = 20
        risk_flags.append("Negative balance events.")
    elif min_balance < aggregate["low_balance_threshold"]:
        balance_health = 12
        risk_flags.append("Weak balance health (min balance below threshold).")
    elif low_events >= 3:
        balance_health = 10
        risk_flags.append("Repeated low balance events.")
    elif low_events >= 1:
        balance_health = 6
        risk_flags.append("Low balance events detected.")
    else:
        balance_health = 0

    dti_label = dti.get("label")
    if dti_label == "unknown":
        obligation_load = 15 if emi_total > 0 else 0
        if emi_total > 0:
            risk_flags.append("EMI obligations present without verified income (DTI unknown).")
    elif dti_label == "low":
        obligation_load = 3
    elif dti_label == "moderate":
        obligation_load = 7
    elif dti_label == "high":
        obligation_load = 11
        risk_flags.append("High DTI.")
    else:
        obligation_load = 15
        risk_flags.append("Extreme DTI.")

    if verified_income > 0:
        burn_rate = (total_expenses + emi_total + penalties) / verified_income
        if burn_rate > 1.0:
            spending_discipline = 15
            risk_flags.append("Expenses + obligations exceed verified income.")
        elif burn_rate > 0.8:
            spending_discipline = 11
        elif burn_rate > 0.6:
            spending_discipline = 7
        elif burn_rate > 0.4:
            spending_discipline = 4
        else:
            spending_discipline = 1
    else:
        spending_discipline = 10 if (total_expenses + emi_total + penalties) > 0 else 0
        if spending_discipline > 0:
            risk_flags.append("Spending/obligations present without verified income.")

    cash_component = min(15, int(round(cash_behavior.get("stressScore", 0) / 100 * 15)))
    if cash_behavior.get("flags"):
        risk_flags.append("Poor liquidity management (cash stress flags present).")

    risk_penalty = 0
    if negative_count > 0:
        risk_penalty += 5
    if low_events >= 3:
        risk_penalty += 4
        risk_flags.append("Repeated low balance penalties.")
    if dti_label in {"high", "extreme"}:
        risk_penalty += 5

    inflow = max(aggregate["verified_income"] + aggregate["unverified_income"] + aggregate["cash_deposits"], 0.0)
    withdrawal_ratio = (aggregate["cash_withdrawals"] / inflow) if inflow > 0 else 0.0
    if inflow > 0 and withdrawal_ratio > 0.4:
        risk_penalty += 5
        risk_flags.append("High cash withdrawal ratio.")

    total_inflow = max(inflow, 1e-9)
    unverified_share = aggregate["unverified_income"] / total_inflow if total_inflow > 0 else 0.0
    if unverified_share > 0.5 and aggregate["unverified_income"] > 0:
        risk_penalty += 4
        risk_flags.append("Heavy unverified credit share.")
    if aggregate["suspicious_count"] > 0:
        risk_penalty += 3
        risk_flags.append("Suspicious transfer patterns.")
    if any("Weak end-of-statement" in flag for flag in cash_behavior.get("flags", [])):
        risk_penalty += 3
        risk_flags.append("Weak end-of-month balance.")
    if aggregate["duplicate_count"] > 0:
        risk_penalty += 2
        risk_flags.append("Duplicate-looking transactions present.")

    risk_penalty = min(15, risk_penalty)
    final_score = min(
        100,
        income_stability
        + balance_health
        + obligation_load
        + spending_discipline
        + cash_component
        + risk_penalty,
    )

    return {
        "incomeStability": income_stability,
        "balanceHealth": balance_health,
        "obligationLoad": obligation_load,
        "spendingDiscipline": spending_discipline,
        "cashBehavior": cash_component,
        "riskPenalty": risk_penalty,
        "finalScore": int(final_score),
        "riskFlags": sorted(set(risk_flags)),
        "overallConfidence": overall_confidence,
    }
