"""
Income detection and stability scoring for bank statements.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any

from core.confidence import normalize_confidence
from services.bank_statement_engine_common import (
    extract_month_key,
    is_excluded_from_income_analysis,
    normalize_description,
    safe_float,
)

SALARY_KEYWORDS = [
    "salary",
    "payroll",
    "sal cr",
    "sal/",
    "neft salary",
    "monthly salary",
    "stipend",
    "wages",
    "compensation",
    "pay credit",
]

UPI_KEYWORDS = ["upi", "upi/", "upi-", "phonepe", "gpay", "google pay", "paytm"]

TRANSFER_KEYWORDS = [
    "neft",
    "rtgs",
    "imps",
    "trtr",
    "digitb",
    "transfer",
    "fund transfer",
    "mob transfer",
    "net banking",
    "internet banking",
]
GENERIC_UNVERIFIED_SOURCE_KEYWORDS = [
    "upi",
    "trtr",
    "digitb",
    "transfer",
    "fund transfer",
    "cash",
    "unknown",
]

_MONTH_TOKEN_PATTERN = re.compile(
    r"\b(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\b"
)
_INCOME_SOURCE_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z&.]*")
_INCOME_SOURCE_STOPWORDS = {
    "salary",
    "monthly",
    "payroll",
    "sal",
    "cr",
    "credit",
    "credited",
    "pay",
    "payment",
    "compensation",
    "stipend",
    "wages",
    "income",
    "bonus",
    "by",
    "from",
    "via",
    "to",
    "for",
    "ref",
    "txn",
    "transaction",
    "id",
    "neft",
    "rtgs",
    "imps",
    "transfer",
    "fund",
    "banking",
    "net",
    "internet",
    "mob",
    "bank",
}
_COMPANY_SUFFIXES = {"pvt", "private", "ltd", "limited", "llp", "inc", "corp", "corporation", "co", "company"}


def _is_salary_like(description: str) -> bool:
    return any(keyword in description for keyword in SALARY_KEYWORDS)


def _is_upi_credit(description: str) -> bool:
    return any(keyword in description for keyword in UPI_KEYWORDS)


def _is_transfer_credit(description: str) -> bool:
    return any(keyword in description for keyword in TRANSFER_KEYWORDS)


def _is_generic_unverified_source(description: str) -> bool:
    return any(keyword in description for keyword in GENERIC_UNVERIFIED_SOURCE_KEYWORDS)


def _recurring_credit_signature(description: str) -> str | None:
    if not description or _is_upi_credit(description) or _is_transfer_credit(description):
        return None

    signature = _MONTH_TOKEN_PATTERN.sub(" ", description)
    signature = re.sub(r"\d+", " ", signature)
    signature = " ".join(signature.split())
    if _is_generic_unverified_source(signature):
        return None
    return signature or None


def _format_source_label(value: str | None) -> str | None:
    if not value:
        return None

    parts = []
    for token in value.split():
        if token.isupper() or len(token) <= 4:
            parts.append(token.upper())
        else:
            parts.append(token.title())
    return " ".join(parts) or None


def _extract_income_source_name(raw_description: Any) -> str | None:
    text = str(raw_description or "").strip()
    if not text:
        return None

    cleaned = _MONTH_TOKEN_PATTERN.sub(" ", text)
    cleaned = re.sub(r"\d+", " ", cleaned)
    tokens = [
        token.strip(".").lower()
        for token in _INCOME_SOURCE_TOKEN_PATTERN.findall(cleaned.replace("/", " ").replace("-", " "))
    ]
    meaningful_tokens = [token for token in tokens if token and token not in _INCOME_SOURCE_STOPWORDS]
    if not meaningful_tokens:
        return None

    if len(meaningful_tokens) > 1:
        while meaningful_tokens and meaningful_tokens[-1] in _COMPANY_SUFFIXES:
            meaningful_tokens.pop()
        if not meaningful_tokens:
            return None

    return _format_source_label(" ".join(meaningful_tokens[:4]))


def compute_income_engine(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    monthly_inflows: dict[str, float] = defaultdict(float)
    salary_credits: list[float] = []
    upi_credits: list[float] = []
    transfer_credits: list[float] = []
    cash_deposits: list[float] = []
    other_credits: list[float] = []
    salary_months: set[str] = set()
    recurring_credit_months: dict[str, set[str]] = defaultdict(set)
    salary_source_months: dict[str, set[str]] = defaultdict(set)
    salary_source_totals: dict[str, float] = defaultdict(float)
    salary_source_counts: dict[str, int] = defaultdict(int)
    recurring_signature_totals: dict[str, float] = defaultdict(float)
    recurring_signature_counts: dict[str, int] = defaultdict(int)

    for transaction in transactions:
        if transaction.get("duplicate") or is_excluded_from_income_analysis(transaction):
            continue

        credit = safe_float(transaction.get("credit")) or 0.0
        if credit <= 0:
            continue

        raw_description = transaction.get("description")
        description = normalize_description(raw_description)
        month = extract_month_key(str(transaction.get("date") or ""))

        if month:
            monthly_inflows[month] += credit

        if _is_salary_like(description):
            salary_credits.append(credit)
            if month:
                salary_months.add(month)
            salary_source = _extract_income_source_name(raw_description)
            if salary_source:
                salary_source_totals[salary_source] += credit
                salary_source_counts[salary_source] += 1
                if month:
                    salary_source_months[salary_source].add(month)
        elif _is_upi_credit(description):
            upi_credits.append(credit)
        elif _is_transfer_credit(description):
            transfer_credits.append(credit)
        elif "cash deposit" in description or "deposit cash" in description or "branch cash" in description:
            cash_deposits.append(credit)
        else:
            other_credits.append(credit)

        signature = _recurring_credit_signature(description)
        if month and signature:
            recurring_credit_months[signature].add(month)
            recurring_signature_totals[signature] += credit
            recurring_signature_counts[signature] += 1

    recurring_income_detected = len(salary_months) >= 2

    recurring_income_source = None
    recurring_income_estimate = None
    recurring_income_months = None
    if salary_source_months:
        source_name, months = max(
            salary_source_months.items(),
            key=lambda item: (len(item[1]), salary_source_counts[item[0]], salary_source_totals[item[0]], item[0]),
        )
        if months:
            recurring_income_source = source_name
            recurring_income_estimate = round(salary_source_totals[source_name] / salary_source_counts[source_name], 2)
            recurring_income_months = len(months)

    total_salary = sum(salary_credits)
    total_upi = sum(upi_credits)
    total_transfer = sum(transfer_credits)
    total_cash = sum(cash_deposits)
    total_other = sum(other_credits)
    total_all = total_salary + total_upi + total_transfer + total_cash + total_other

    if total_all == 0:
        return {
            "income_type": "unknown",
            "monthly_income_estimate": "0",
            "monthly_income_estimate_min": 0,
            "monthly_income_estimate_max": 0,
            "annual_income_estimate_min": 0.0,
            "annual_income_estimate_max": 0.0,
            "confidence": normalize_confidence("low"),
            "salary_credits": [],
            "upi_credits": [],
            "transfer_credits": [],
            "cash_deposits": [],
            "other_credits": [],
            "monthly_inflows": dict(monthly_inflows),
            "income_regularity_score": 0,
            "income_sources": [],
            "recurring_income_detected": False,
            "recurring_income_source": None,
            "recurring_income_estimate": None,
            "recurring_income_months": None,
        }

    salary_share = total_salary / total_all if total_all > 0 else 0
    if salary_share > 0.6:
        income_type = "salary"
        confidence = normalize_confidence("high" if recurring_income_detected else "medium")
    elif salary_share > 0.3:
        income_type = "mixed"
        confidence = normalize_confidence("medium" if recurring_income_detected else "low")
    elif total_upi + total_transfer + total_cash > 0:
        income_type = "unstable"
        confidence = normalize_confidence("low")
    else:
        income_type = "unknown"
        confidence = normalize_confidence("low")

    monthly_values = sorted(monthly_inflows.values()) if monthly_inflows else [0]
    if len(monthly_values) >= 2:
        p25_idx = max(0, len(monthly_values) // 4)
        p75_idx = min(len(monthly_values) - 1, 3 * len(monthly_values) // 4)
        monthly_income_estimate_min = int(monthly_values[p25_idx])
        monthly_income_estimate_max = int(monthly_values[p75_idx])
        monthly_income_estimate = (
            str(monthly_income_estimate_min)
            if monthly_income_estimate_min == monthly_income_estimate_max
            else f"{monthly_income_estimate_min}-{monthly_income_estimate_max}"
        )
    elif monthly_values:
        monthly_income_estimate_min = int(monthly_values[0])
        monthly_income_estimate_max = monthly_income_estimate_min
        monthly_income_estimate = str(monthly_income_estimate_min)
    else:
        monthly_income_estimate_min = 0
        monthly_income_estimate_max = 0
        monthly_income_estimate = "0"
    annual_income_estimate_min = round(monthly_income_estimate_min * 12.0, 3)
    annual_income_estimate_max = round(monthly_income_estimate_max * 12.0, 3)

    if len(monthly_values) >= 2:
        mean = sum(monthly_values) / len(monthly_values)
        if mean > 0:
            variance = sum((value - mean) ** 2 for value in monthly_values) / len(monthly_values)
            regularity = max(0, min(100, int(100 * (1 - (math.sqrt(variance) / mean)))))
        else:
            regularity = 0
    else:
        regularity = 20

    income_sources = []
    if salary_credits:
        income_sources.append(
            {
                "type": "salary",
                "avg": round(sum(salary_credits) / len(salary_credits), 2),
                "count": len(salary_credits),
                "total": round(total_salary, 2),
            }
        )
    if upi_credits:
        income_sources.append(
            {
                "type": "upi_transfers",
                "avg": round(sum(upi_credits) / len(upi_credits), 2),
                "count": len(upi_credits),
                "total": round(total_upi, 2),
            }
        )
    if transfer_credits:
        income_sources.append(
            {
                "type": "bank_transfers",
                "avg": round(sum(transfer_credits) / len(transfer_credits), 2),
                "count": len(transfer_credits),
                "total": round(total_transfer, 2),
            }
        )
    if cash_deposits:
        income_sources.append(
            {
                "type": "cash_deposits",
                "avg": round(sum(cash_deposits) / len(cash_deposits), 2),
                "count": len(cash_deposits),
                "total": round(total_cash, 2),
            }
        )
    if other_credits:
        income_sources.append(
            {
                "type": "other_credits",
                "avg": round(sum(other_credits) / len(other_credits), 2),
                "count": len(other_credits),
                "total": round(total_other, 2),
            }
        )

    return {
        "income_type": income_type,
        "monthly_income_estimate": monthly_income_estimate,
        "monthly_income_estimate_min": monthly_income_estimate_min,
        "monthly_income_estimate_max": monthly_income_estimate_max,
        "annual_income_estimate_min": annual_income_estimate_min,
        "annual_income_estimate_max": annual_income_estimate_max,
        "confidence": confidence,
        "salary_credits": [round(value, 2) for value in salary_credits],
        "upi_credits": [round(value, 2) for value in upi_credits],
        "transfer_credits": [round(value, 2) for value in transfer_credits],
        "cash_deposits": [round(value, 2) for value in cash_deposits],
        "other_credits": [round(value, 2) for value in other_credits],
        "monthly_inflows": {month: round(value, 2) for month, value in sorted(monthly_inflows.items())},
        "income_regularity_score": regularity,
        "income_sources": income_sources,
        "recurring_income_detected": recurring_income_detected,
        "recurring_income_source": recurring_income_source,
        "recurring_income_estimate": recurring_income_estimate,
        "recurring_income_months": recurring_income_months,
    }
