"""
Shared helpers for bank statement engine modules.
"""

from __future__ import annotations

from datetime import date, datetime
import math
import re
from typing import Any

_TRANSFER_LIKE_KEYWORDS = [
    "upi",
    "imps",
    "neft",
    "rtgs",
    "transfer",
    "fund transfer",
    "mob transfer",
    "net banking",
    "internet banking",
    "own account",
    "self",
]

_VERIFICATION_CREDIT_KEYWORDS = [
    "account verification",
    "acct verification",
    "a/c verification",
    "ac verification",
    "verify account",
    "account verify",
    "acct verify",
    "penny drop",
    "micro settlement",
    "micro credit",
    "validation credit",
    "test credit",
    "test txn",
    "test transaction",
]
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d-%m-%y",
    "%d/%m/%y",
)


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not math.isnan(float(value)):
        return float(value)
    normalized = str(value).strip().replace(",", "")
    if normalized == "" or normalized.lower() == "null" or normalized == "-":
        return None
    try:
        return float(normalized)
    except Exception:
        return None


def normalize_description(description: Any) -> str:
    normalized = str(description or "").lower().strip()
    return " ".join(normalized.split())


def parse_statement_date(raw_value: Any) -> date | None:
    text = str(raw_value or "").strip()
    if not text:
        return None

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def extract_month_key(date_str: str) -> str | None:
    """Extract YYYY-MM from a date string."""
    text = str(date_str or "").strip()
    if not text:
        return None

    parsed_date = parse_statement_date(text)
    if parsed_date is not None:
        return parsed_date.strftime("%Y-%m")

    year_month_match = re.fullmatch(r"(\d{4})[-/](\d{1,2})", text)
    if year_month_match:
        month = int(year_month_match.group(2))
        if 1 <= month <= 12:
            return f"{year_month_match.group(1)}-{month:02d}"

    return None


def is_transfer_like_description(description: Any) -> bool:
    normalized = normalize_description(description)
    return any(keyword in normalized for keyword in _TRANSFER_LIKE_KEYWORDS)


def is_verification_credit_transaction(transaction: dict[str, Any]) -> bool:
    credit = safe_float(transaction.get("credit")) or 0.0
    if credit <= 0 or credit > 2:
        return False

    description = normalize_description(transaction.get("description"))
    if not description:
        return False

    return any(keyword in description for keyword in _VERIFICATION_CREDIT_KEYWORDS)


def is_excluded_from_income_analysis(transaction: dict[str, Any]) -> bool:
    return bool(transaction.get("verification_credit")) or bool(transaction.get("pass_through_transfer"))
