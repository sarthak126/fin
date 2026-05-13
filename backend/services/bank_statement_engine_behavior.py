"""
Behavioral risk flag detection for bank statements.
"""

from __future__ import annotations

from typing import Any

from services.bank_statement_engine_common import extract_month_key, normalize_description, safe_float


def compute_behavioral_flags(
    transactions: list[dict[str, Any]],
    agg: dict[str, Any],
    income_engine: dict[str, Any],
    cashflow: dict[str, Any],
) -> dict[str, Any]:
    flags: list[str] = []
    flag_details: list[dict[str, str]] = []

    def add_flag(flag: str, severity: str, detail: str) -> None:
        flags.append(flag)
        flag_details.append({"flag": flag, "severity": severity, "detail": detail})

    valid_transactions = [transaction for transaction in transactions if not transaction.get("duplicate")]
    total_count = len(valid_transactions)

    months_with_transactions = {
        month
        for transaction in valid_transactions
        if (month := extract_month_key(str(transaction.get("date") or "")))
    }
    num_months = max(len(months_with_transactions), 1)
    avg_txns_per_month = total_count / num_months

    if avg_txns_per_month > 60:
        add_flag(
            "high_transaction_frequency",
            "medium",
            f"Average {avg_txns_per_month:.0f} transactions/month suggests impulsive spending behavior",
        )
    elif avg_txns_per_month > 40:
        add_flag(
            "moderate_transaction_frequency",
            "low",
            f"Average {avg_txns_per_month:.0f} transactions/month - above typical patterns",
        )

    small_transactions = [
        transaction
        for transaction in valid_transactions
        if 0 < (safe_float(transaction.get("debit")) or 0) < 200
    ]
    if len(small_transactions) > total_count * 0.4 and len(small_transactions) > 10:
        add_flag(
            "impulse_spending_pattern",
            "medium",
            f"{len(small_transactions)} transactions under Rs200 ({len(small_transactions) * 100 // max(total_count, 1)}% of all) - suggests impulsive spending",
        )

    balances = [
        safe_float(transaction.get("balance"))
        for transaction in valid_transactions
        if safe_float(transaction.get("balance")) is not None
    ]
    if balances:
        low_balance_count = sum(1 for balance in balances if balance < 1000)
        if low_balance_count > len(balances) * 0.3:
            add_flag(
                "low_balance_risk",
                "high",
                f"Balance dropped below Rs1,000 in {low_balance_count} of {len(balances)} entries - severe liquidity risk",
            )
        elif low_balance_count > len(balances) * 0.1:
            add_flag(
                "occasional_low_balance",
                "medium",
                f"Balance dropped below Rs1,000 in {low_balance_count} entries - liquidity concern",
            )

        critical_low = sum(1 for balance in balances if balance < 500)
        if critical_low > 3:
            add_flag(
                "critical_balance_drops",
                "high",
                f"Balance dropped below Rs500 on {critical_low} occasions - high financial stress",
            )

    if income_engine.get("income_type") in ("unstable", "unknown"):
        add_flag(
            "irregular_income",
            "high",
            "No stable salary detected. Income is through UPI/transfers/cash - high uncertainty for repayment",
        )
    elif income_engine.get("income_type") == "mixed":
        add_flag(
            "mixed_income_sources",
            "medium",
            "Income comes from mix of salary and informal sources - partial stability",
        )

    cash_dep_total = sum(income_engine.get("cash_deposits", []))
    total_inflow = sum(value for value in income_engine.get("monthly_inflows", {}).values())
    if total_inflow > 0 and cash_dep_total / total_inflow > 0.3:
        add_flag(
            "cash_dependency",
            "high",
            f"Cash deposits are {cash_dep_total * 100 / total_inflow:.0f}% of total inflows - untraceable income source",
        )

    large_withdrawals = [
        transaction
        for transaction in valid_transactions
        if (safe_float(transaction.get("debit")) or 0) > 20000
        and "atm" in normalize_description(transaction.get("description"))
    ]
    if len(large_withdrawals) >= 3:
        add_flag(
            "large_cash_withdrawals",
            "high",
            f"{len(large_withdrawals)} large ATM withdrawals (>Rs20K) - possible financial stress or cash economy",
        )
    elif large_withdrawals:
        add_flag(
            "occasional_large_withdrawal",
            "medium",
            f"{len(large_withdrawals)} large ATM withdrawal(s) (>Rs20K) detected",
        )

    if cashflow.get("savings_trend") == "declining":
        add_flag(
            "declining_savings",
            "high",
            "Savings trend is declining over the statement period - worsening financial health",
        )

    if cashflow.get("monthly_burn_rate") in ("critical", "high"):
        add_flag(
            "high_burn_rate",
            "high",
            f"Monthly burn rate is {cashflow['monthly_burn_rate']} - expenses consuming most/all income",
        )

    if balances and len(balances) >= 5:
        last_balance = balances[-1]
        avg_balance = sum(balances) / len(balances)
        if avg_balance > 0 and last_balance < avg_balance * 0.3:
            add_flag(
                "end_period_balance_drop",
                "medium",
                f"End balance (Rs{last_balance:,.0f}) is much lower than average (Rs{avg_balance:,.0f}) - weak retention",
            )

    penalty_transactions = [
        transaction for transaction in valid_transactions if transaction.get("category") == "PENALTY"
    ]
    if len(penalty_transactions) >= 3:
        add_flag(
            "frequent_penalties",
            "high",
            f"{len(penalty_transactions)} penalty/bounce charges - indicates poor financial discipline",
        )
    elif penalty_transactions:
        add_flag(
            "penalty_charges_present",
            "medium",
            f"{len(penalty_transactions)} penalty/bounce charge(s) found in statement",
        )

    return {"flags": flags, "flag_details": flag_details}
