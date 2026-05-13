"""
Cash flow stability and burn-rate analysis for bank statements.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from services.bank_statement_engine_common import (
    extract_month_key,
    is_excluded_from_income_analysis,
    safe_float,
)


def compute_cashflow_intelligence(
    transactions: list[dict[str, Any]],
    agg: dict[str, Any],
    income_engine: dict[str, Any],
) -> dict[str, Any]:
    monthly_inflows: dict[str, float] = defaultdict(float)
    monthly_outflows: dict[str, float] = defaultdict(float)
    monthly_balances: dict[str, list[float]] = defaultdict(list)

    for transaction in transactions:
        if transaction.get("duplicate") or is_excluded_from_income_analysis(transaction):
            continue

        month = extract_month_key(str(transaction.get("date") or ""))
        if not month:
            continue

        credit = safe_float(transaction.get("credit")) or 0.0
        debit = safe_float(transaction.get("debit")) or 0.0
        balance = safe_float(transaction.get("balance"))

        monthly_inflows[month] += credit
        monthly_outflows[month] += debit
        if balance is not None:
            monthly_balances[month].append(balance)

    all_months = sorted(set(list(monthly_inflows.keys()) + list(monthly_outflows.keys())))
    monthly_net_flows = {
        month: round(monthly_inflows.get(month, 0) - monthly_outflows.get(month, 0), 2)
        for month in all_months
    }

    net_values = list(monthly_net_flows.values())
    if len(net_values) >= 2:
        mean_net = sum(net_values) / len(net_values)
        variance = sum((value - mean_net) ** 2 for value in net_values) / len(net_values)
        stdev = math.sqrt(variance)
        total_flow = sum(monthly_inflows.values()) + sum(monthly_outflows.values())
        avg_flow = total_flow / max(len(all_months), 1) / 2
        if avg_flow > 0:
            cv = stdev / avg_flow
            stability_score = max(0, min(100, int(100 * (1 - min(cv, 1.5) / 1.5))))
        else:
            stability_score = 0
    else:
        stability_score = 30

    if stability_score >= 70:
        cash_flow_stability = "high"
    elif stability_score >= 40:
        cash_flow_stability = "medium"
    else:
        cash_flow_stability = "low"

    total_inflow = sum(monthly_inflows.values())
    total_outflow = sum(monthly_outflows.values())
    if total_inflow > 0:
        burn_ratio = total_outflow / total_inflow
        if burn_ratio > 1.0:
            monthly_burn_rate = "critical"
        elif burn_ratio > 0.85:
            monthly_burn_rate = "high"
        elif burn_ratio > 0.6:
            monthly_burn_rate = "medium"
        else:
            monthly_burn_rate = "low"
        savings_ratio = max(0.0, round(1.0 - burn_ratio, 4))
    else:
        monthly_burn_rate = "critical" if total_outflow > 0 else "unknown"
        savings_ratio = 0.0

    if len(net_values) >= 4:
        midpoint = len(net_values) // 2
        first_half_avg = sum(net_values[:midpoint]) / midpoint
        second_half_avg = sum(net_values[midpoint:]) / (len(net_values) - midpoint)
        if second_half_avg > first_half_avg * 1.1:
            savings_trend = "improving"
        elif second_half_avg < first_half_avg * 0.9:
            savings_trend = "declining"
        else:
            savings_trend = "stable"
    elif len(net_values) >= 2:
        if net_values[-1] > net_values[0]:
            savings_trend = "improving"
        elif net_values[-1] < net_values[0]:
            savings_trend = "declining"
        else:
            savings_trend = "stable"
    else:
        savings_trend = "unknown"

    return {
        "cash_flow_stability": cash_flow_stability,
        "monthly_burn_rate": monthly_burn_rate,
        "savings_trend": savings_trend,
        "savings_ratio": savings_ratio,
        "monthly_net_flows": monthly_net_flows,
        "stability_score": stability_score,
    }
