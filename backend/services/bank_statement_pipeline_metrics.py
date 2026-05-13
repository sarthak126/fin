"""
Deterministic aggregates and intermediate bank statement metrics.
"""

from __future__ import annotations

import statistics
from datetime import date
from typing import Any, Dict, List

from services.bank_statement_engine_common import is_excluded_from_income_analysis, parse_statement_date
from services.bank_statement_pipeline_types import (
    LOW_BALANCE_THRESHOLD,
    Transaction,
    credit_like_amount,
    debit_like_amount,
    is_cash_deposit,
    is_cash_withdrawal,
    is_self_transfer,
    norm_desc,
    safe_float,
)


CYCLING_PROXIMITY_DAYS = 3


def _round_currency(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def build_statement_summary(transactions: List[Transaction]) -> Dict[str, Any]:
    filtered_transactions = [transaction for transaction in transactions if not transaction.get("duplicate")]
    dated_transactions: list[tuple[date, int, Transaction]] = []
    balances: list[float] = []
    total_credits = 0.0
    total_debits = 0.0
    credit_count = 0
    debit_count = 0
    low_balance_count = 0

    for index, transaction in enumerate(filtered_transactions):
        parsed_date = parse_statement_date(transaction.get("date"))
        if parsed_date is not None:
            dated_transactions.append((parsed_date, index, transaction))

        reversal = bool(transaction.get("reversal"))
        debit = safe_float(transaction.get("debit")) or 0.0
        credit = safe_float(transaction.get("credit")) or 0.0
        balance = safe_float(transaction.get("balance"))

        if reversal:
            if debit > 0:
                total_credits += debit
                credit_count += 1
            if credit > 0:
                total_debits += credit
                debit_count += 1
        else:
            if credit > 0:
                total_credits += credit
                credit_count += 1
            if debit > 0:
                total_debits += debit
                debit_count += 1

        if balance is not None:
            balances.append(balance)
            if balance < LOW_BALANCE_THRESHOLD:
                low_balance_count += 1

    dated_transactions.sort(key=lambda item: (item[0], item[1]))

    opening_balance = None
    closing_balance = None
    statement_start_date = None
    statement_end_date = None
    coverage_days = 0

    if dated_transactions:
        statement_start_date = dated_transactions[0][0].isoformat()
        statement_end_date = dated_transactions[-1][0].isoformat()
        coverage_days = (dated_transactions[-1][0] - dated_transactions[0][0]).days + 1

        opening_balance = safe_float(dated_transactions[0][2].get("balance"))
        closing_balance = safe_float(dated_transactions[-1][2].get("balance"))

    avg_balance = statistics.fmean(balances) if balances else 0.0
    median_balance = statistics.median(balances) if balances else 0.0
    balance_volatility = statistics.pstdev(balances) if len(balances) > 1 else 0.0

    return {
        "statement_start_date": statement_start_date,
        "statement_end_date": statement_end_date,
        "declared_period_start_date": None,
        "declared_period_end_date": None,
        "last_transaction_date": statement_end_date,
        "coverage_days": coverage_days,
        "opening_balance": _round_currency(opening_balance),
        "closing_balance": _round_currency(closing_balance),
        "total_credits": _round_currency(total_credits),
        "total_debits": _round_currency(total_debits),
        "net_flow": _round_currency(total_credits - total_debits),
        "min_balance": _round_currency(min(balances) if balances else 0.0),
        "max_balance": _round_currency(max(balances) if balances else 0.0),
        "avg_balance": _round_currency(avg_balance),
        "median_balance": _round_currency(median_balance),
        "transaction_count": len(filtered_transactions),
        "credit_count": credit_count,
        "debit_count": debit_count,
        "low_balance_count": low_balance_count,
        "balance_volatility": _round_currency(balance_volatility),
    }


def deterministic_aggregate(transactions: List[Transaction]) -> Dict[str, Any]:
    verified_income = 0.0
    unverified_income = 0.0
    cash_withdrawals = 0.0
    cash_deposits = 0.0
    total_expenses = 0.0
    emi_total = 0.0
    penalties_total = 0.0

    balances: List[float] = []
    negative_balance_count = 0
    low_balance_events = 0
    reversal_count = 0
    duplicate_count = 0
    suspicious_count = 0

    for transaction in transactions:
        if transaction.get("duplicate"):
            duplicate_count += 1
            continue

        reversal = bool(transaction.get("reversal"))
        sign = -1.0 if reversal else 1.0
        if reversal:
            reversal_count += 1

        category = transaction.get("category") or "UNKNOWN"
        description = norm_desc(transaction.get("description"))
        debit = safe_float(transaction.get("debit")) or 0.0
        credit = safe_float(transaction.get("credit")) or 0.0
        balance = safe_float(transaction.get("balance"))
        excluded_from_income = is_excluded_from_income_analysis(transaction)

        if balance is not None:
            balances.append(balance)
            if balance < 0:
                negative_balance_count += 1
            if balance < LOW_BALANCE_THRESHOLD:
                low_balance_events += 1

        if category == "VERIFIED_INCOME":
            if not excluded_from_income:
                verified_income += sign * credit_like_amount(debit, credit)
        elif category == "UNVERIFIED_CREDIT":
            if is_cash_deposit(description):
                if not excluded_from_income:
                    cash_deposits += sign * credit_like_amount(debit, credit)
            elif not excluded_from_income:
                unverified_income += sign * credit_like_amount(debit, credit)
        elif category == "EXPENSE":
            total_expenses += sign * debit_like_amount(debit, credit)
        elif category == "EMI":
            emi_total += sign * debit_like_amount(debit, credit)
        elif category == "PENALTY":
            penalties_total += sign * debit_like_amount(debit, credit)
        elif category == "CASH_FLOW":
            if is_cash_withdrawal(description):
                cash_withdrawals += debit - credit
            elif is_cash_deposit(description):
                cash_deposits += credit - debit
            elif is_self_transfer(description):
                continue
        elif category == "SUSPICIOUS":
            suspicious_count += 1

    avg_balance = sum(balances) / len(balances) if balances else 0.0
    min_balance = min(balances) if balances else 0.0
    max_balance = max(balances) if balances else 0.0
    median_balance = statistics.median(balances) if balances else 0.0
    balance_volatility = statistics.pstdev(balances) if len(balances) > 1 else 0.0
    statement_summary = build_statement_summary(transactions)

    return {
        "verified_income": verified_income,
        "unverified_income": unverified_income,
        "total_expenses": total_expenses,
        "emi_total": emi_total,
        "penalties_total": penalties_total,
        "cash_withdrawals": cash_withdrawals,
        "cash_deposits": cash_deposits,
        "avg_balance": avg_balance,
        "median_balance": median_balance,
        "min_balance": min_balance,
        "max_balance": max_balance,
        "balance_volatility": balance_volatility,
        "negative_balance_count": negative_balance_count,
        "low_balance_events": low_balance_events,
        "reversal_count": reversal_count,
        "duplicate_count": duplicate_count,
        "suspicious_count": suspicious_count,
        "low_balance_threshold": LOW_BALANCE_THRESHOLD,
        "statement_summary": statement_summary,
    }


def _coerce_positive_income(value: Any) -> float | None:
    numeric = safe_float(value)
    if numeric is None or numeric <= 0:
        return None
    return float(numeric)


def _effective_monthly_income(
    *,
    recurring_income_estimate: Any = None,
    verified_income: Any = None,
    unverified_income: Any = None,
) -> tuple[float | None, str]:
    recurring_income = _coerce_positive_income(recurring_income_estimate)
    if recurring_income is not None:
        return recurring_income, "verified"

    verified = _coerce_positive_income(verified_income)
    if verified is not None:
        return verified, "verified"

    unverified_numeric = safe_float(unverified_income) or 0.0
    unverified = _coerce_positive_income(unverified_numeric)
    if unverified is not None:
        return unverified, "unverified"

    return None, "unavailable"


def compute_dti(
    emi_total: float,
    verified_income: float,
    *,
    recurring_income_estimate: Any = None,
    unverified_income: float = 0.0,
) -> Dict[str, Any]:
    effective_monthly_income, reliability = _effective_monthly_income(
        recurring_income_estimate=recurring_income_estimate,
        verified_income=verified_income,
        unverified_income=unverified_income,
    )
    if effective_monthly_income is None:
        return {"value": None, "label": "unknown", "reliability": reliability}

    value = emi_total / effective_monthly_income
    if value < 0.2:
        label = "low"
    elif value < 0.35:
        label = "moderate"
    elif value < 0.5:
        label = "high"
    else:
        label = "extreme"

    return {"value": round(value, 3), "label": label, "reliability": reliability}


def analyze_cash_behavior(transactions: List[Transaction], aggregate: Dict[str, Any]) -> Dict[str, Any]:
    flags: List[str] = []
    stress_points = 0

    inflow = max(
        aggregate["verified_income"] + aggregate["unverified_income"] + aggregate["cash_deposits"],
        0.0,
    )
    withdrawal_ratio = (aggregate["cash_withdrawals"] / inflow) if inflow > 0 else 0.0

    if inflow > 0 and withdrawal_ratio > 0.6:
        stress_points += 30
        flags.append("High cash withdrawal ratio (>60%).")
    elif inflow > 0 and withdrawal_ratio > 0.4:
        stress_points += 20
        flags.append("Elevated cash withdrawal ratio (>40%).")
    elif aggregate["cash_withdrawals"] > 0 and inflow == 0:
        stress_points += 20
        flags.append("Cash withdrawals without clear inflows.")

    if aggregate["negative_balance_count"] > 0:
        stress_points += 25
        flags.append(f"Negative balance events ({aggregate['negative_balance_count']}).")

    if aggregate["low_balance_events"] >= 5:
        stress_points += 25
        flags.append(f"Frequent low balance events (<{aggregate['low_balance_threshold']}).")
    elif aggregate["low_balance_events"] >= 2:
        stress_points += 15
        flags.append(f"Occasional low balance events (<{aggregate['low_balance_threshold']}).")
    elif aggregate["low_balance_events"] >= 1:
        stress_points += 8
        flags.append(f"Low balance events detected (<{aggregate['low_balance_threshold']}).")

    cash_deposit_dates = []
    cash_withdraw_dates = []
    for transaction in transactions:
        if transaction.get("duplicate") or bool(transaction.get("reversal")):
            continue

        parsed_date = parse_statement_date(transaction.get("date"))
        if parsed_date is None:
            continue

        category = transaction.get("category")
        description = norm_desc(transaction.get("description"))
        credit = safe_float(transaction.get("credit")) or 0.0
        debit = safe_float(transaction.get("debit")) or 0.0

        if category == "UNVERIFIED_CREDIT" and credit > 0 and is_cash_deposit(description):
            cash_deposit_dates.append(parsed_date)
        if category == "CASH_FLOW" and debit > 0 and is_cash_withdrawal(description):
            cash_withdraw_dates.append(parsed_date)

    cycling_detected = any(
        deposit_date <= withdraw_date and (withdraw_date - deposit_date).days <= CYCLING_PROXIMITY_DAYS
        for deposit_date in cash_deposit_dates
        for withdraw_date in cash_withdraw_dates
    )
    if cycling_detected:
        stress_points += 20
        flags.append("Cash-in followed by rapid cash-out (cycling).")

    last_balance = None
    for transaction in reversed(transactions):
        balance = safe_float(transaction.get("balance"))
        if balance is not None:
            last_balance = balance
            break

    if last_balance is not None and aggregate["avg_balance"] > 0 and last_balance < aggregate["avg_balance"] * 0.3:
        stress_points += 15
        flags.append("Weak end-of-statement balance (low retention).")
    elif last_balance is not None and last_balance < aggregate["low_balance_threshold"]:
        stress_points += 10
        flags.append("End-of-statement balance below low-balance threshold.")

    return {"stressScore": min(100, int(stress_points)), "flags": flags}
