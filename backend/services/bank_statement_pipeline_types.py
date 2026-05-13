"""
Shared types and helpers for the deterministic bank statement pipeline.
"""

import math
import re
from typing import Any, Dict, List, Optional

from core.confidence import normalize_confidence

ALLOWED_TX_CATEGORIES = {
    "VERIFIED_INCOME",
    "UNVERIFIED_CREDIT",
    "EXPENSE",
    "EMI",
    "CASH_FLOW",
    "PENALTY",
    "SUSPICIOUS",
    "UNKNOWN",
}

CONFIDENCE_MAP = {"high": 1.0, "medium": 0.6, "low": 0.3}
LOW_BALANCE_THRESHOLD = 1000.0
_SELF_TRANSFER_KEYWORDS = [
    "self",
    "own account",
    "transfer to self",
    "fund transfer to self",
]
_PENALTY_KEYWORDS = [
    "penalty",
    "bounce",
    "late fee",
    "late payment",
    "overdue",
    "return charge",
    "return charges",
    "min bal",
    "minimum balance",
    "low balance",
    "insufficient funds",
    "dishonour",
    "dishonor",
]
_BENIGN_BANK_FEE_KEYWORDS = [
    "sms alert",
    "sms charge",
    "sms charges",
    "annual maintenance",
    "maintenance charge",
    "maintenance charges",
    "debit card annual",
    "statement charge",
    "statement charges",
    "gst",
]
_EMI_PATTERNS = (
    re.compile(r"\bemi\b"),
    re.compile(r"\bloan emi\b"),
    re.compile(r"\bloan recovery\b"),
    re.compile(r"\bautodebit\b"),
    re.compile(r"\bauto[- ]debit\b"),
    re.compile(r"\bnach\b"),
    re.compile(r"\becs\b"),
    re.compile(r"\bstanding instruction\b"),
    re.compile(r"\bsi loan\b"),
    re.compile(r"\bmonthly installment\b"),
    re.compile(r"\bmonthly instalment\b"),
)

Transaction = Dict[str, Any]


def safe_float(value: Any) -> Optional[float]:
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


def norm_desc(description: Any) -> str:
    normalized = str(description or "").lower().strip()
    return " ".join(normalized.split())


def parse_tx_confidence(confidence: Any) -> float:
    return normalize_confidence(confidence, default=CONFIDENCE_MAP["medium"])


def statement_confidence_from_txns(transactions: List[Transaction]) -> float:
    if not transactions:
        return 0.0

    total = 0.0
    for transaction in transactions:
        total += parse_tx_confidence(transaction.get("confidence"))
    return total / max(len(transactions), 1)


def is_cash_withdrawal(description: str) -> bool:
    lowered = description.lower()
    return any(keyword in lowered for keyword in ["atm", "cash withdrawal", "cash wdl", "wdl", "withdrawal"])


def is_cash_deposit(description: str) -> bool:
    lowered = description.lower()
    return any(
        keyword in lowered
        for keyword in ["cash deposit", "deposit cash", "branch cash deposit", "cash deposit branch"]
    )


def is_emi(description: str) -> bool:
    lowered = description.lower()
    return any(pattern.search(lowered) for pattern in _EMI_PATTERNS)


def is_penalty(description: str) -> bool:
    lowered = description.lower()
    if any(keyword in lowered for keyword in _BENIGN_BANK_FEE_KEYWORDS):
        return False
    return any(keyword in lowered for keyword in _PENALTY_KEYWORDS)


def is_self_transfer(description: str) -> bool:
    lowered = description.lower()
    return any(keyword in lowered for keyword in _SELF_TRANSFER_KEYWORDS)


def is_reversal(description: str) -> bool:
    lowered = description.lower()
    return any(keyword in lowered for keyword in ["reversal", "refund", "chargeback", "reverse"])


def is_suspicious(description: str) -> bool:
    lowered = description.lower()
    return any(
        keyword in lowered
        for keyword in ["unknown", "friend", "upi/unknown", "neft/unknown", "cash transfer", "suspicious", "circular"]
    )


def append_note(transaction: Transaction, note: str) -> None:
    existing = str(transaction.get("notes") or "").strip()
    transaction["notes"] = f"{existing} | {note}".strip(" |")


def normalize_category(category: Any) -> str:
    normalized = str(category or "UNKNOWN").strip().upper()
    if normalized in ALLOWED_TX_CATEGORIES:
        return normalized
    return "UNKNOWN"


def credit_like_amount(debit: float, credit: float) -> float:
    return credit if credit > 0 else (debit if debit > 0 else 0.0)


def debit_like_amount(debit: float, credit: float) -> float:
    return debit if debit > 0 else (credit if credit > 0 else 0.0)
