"""
Local bank statement transaction parsing and heuristic classification.

This module keeps the bank-statement pipeline usable when Gemini extraction
or classification is unavailable. It is intentionally conservative: credits
default to unverified income unless salary-like signals are present, and
debits default to expenses unless stronger rules apply.
"""

from __future__ import annotations

import re
from typing import Any

from services.bank_statement_pipeline_types import is_emi

_DATE_RE = re.compile(r"^(?P<date>\d{2}[-/]\d{2}[-/]\d{2,4})\b")
_AMOUNT_GROUP_RE = re.compile(
    r"^(?P<prefix>.*?)(?P<amounts>(?:\s{2,}-?\d[\d,]*\.\d{2}(?:Cr|Dr)?)+)\s*$"
)
_AMOUNT_RE = re.compile(r"-?\d[\d,]*\.\d{2}(?:Cr|Dr)?")

_NOISE_SUBSTRINGS = [
    "transaction details",
    "statement of account",
    "date     particulars",
    "page total:",
    "page no:",
    "page ",
    "https://",
    "http://",
    "micr code",
    "ifsc code",
    "helpline",
    "address:",
    "account open date",
    "a/c number",
    "a/c name",
    "joint holders",
    "scheme description",
    "nomination flag",
    "nominee name",
    "unless the constituent",
    "returning on the basis opening balance in account",
    "note: cheques received in inward clearing",
]

_SALARY_KEYWORDS = [
    "salary",
    "payroll",
    "wages",
    "stipend",
    "salary credit",
    "sal credit",
    "pay credit",
]
_PENALTY_KEYWORDS = [
    "penalty",
    "bounce",
    "return charge",
    "return charges",
    "late fee",
    "late payment",
    "overdue",
    "min bal",
    "minimum balance",
    "low balance",
    "insufficient funds",
    "dishonour",
    "dishonor",
]
_CASH_WITHDRAWAL_KEYWORDS = [
    "atm",
    "cash withdrawal",
    "cash wdl",
    "withdrawal",
]
_CASH_DEPOSIT_KEYWORDS = [
    "cash deposit",
    "deposit cash",
    "branch cash deposit",
    "cash dep",
]
_SELF_TRANSFER_KEYWORDS = [
    "self",
    "own account",
    "transfer to self",
    "fund transfer to self",
]


def _parse_amount(raw_amount: str | None) -> float | None:
    if not raw_amount:
        return None

    normalized = raw_amount.replace(",", "").strip()
    sign = 1.0
    if normalized.endswith("Dr"):
        sign = -1.0
        normalized = normalized[:-2]
    elif normalized.endswith("Cr"):
        normalized = normalized[:-2]

    try:
        return round(sign * float(normalized), 2)
    except ValueError:
        return None


def _line_is_noise(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("--- Page"):
        return True
    if set(stripped) == {"-"}:
        return True

    lowered = stripped.lower()
    if lowered.startswith("bank of "):
        return True

    return any(token in lowered for token in _NOISE_SUBSTRINGS)


def _should_append_continuation(line: str) -> bool:
    stripped = line.strip()
    if _line_is_noise(line):
        return False
    if _DATE_RE.match(stripped):
        return False

    lowered = stripped.lower()
    if ":" in stripped and not any(sep in lowered for sep in ["/", "-", "@"]):
        return False
    return True


def _infer_posting_direction(
    amount: float,
    balance: float | None,
    previous_balance: float | None,
    description: str,
) -> tuple[float | None, float | None]:
    if previous_balance is not None and balance is not None:
        if abs((previous_balance - amount) - balance) <= 1.0:
            return amount, None
        if abs((previous_balance + amount) - balance) <= 1.0:
            return None, amount
        if balance > previous_balance:
            return None, amount
        if balance < previous_balance:
            return amount, None

    lowered = description.lower()
    if any(keyword in lowered for keyword in _SALARY_KEYWORDS + _CASH_DEPOSIT_KEYWORDS):
        return None, amount
    if "b/f" in lowered or "opening" in lowered:
        return None, None
    return amount, None


def _parse_transaction_record(
    line: str,
    continuation_lines: list[str],
    previous_balance: float | None,
) -> tuple[dict[str, Any] | None, float | None]:
    match = _DATE_RE.match(line.strip())
    if not match:
        return None, previous_balance

    date = match.group("date")
    remainder = line[match.end():].rstrip()
    amount_match = _AMOUNT_GROUP_RE.match(remainder)
    if not amount_match:
        return None, previous_balance

    description = amount_match.group("prefix").strip()
    if continuation_lines:
        description = " ".join([description, *continuation_lines]).strip()

    raw_amounts = _AMOUNT_RE.findall(amount_match.group("amounts"))
    amounts = [_parse_amount(raw_amount) for raw_amount in raw_amounts]
    amounts = [amount for amount in amounts if amount is not None]
    if not amounts:
        return None, previous_balance

    debit: float | None = None
    credit: float | None = None
    balance: float | None = None

    if len(amounts) >= 3:
        debit, credit, balance = amounts[-3], amounts[-2], amounts[-1]
        if debit == 0:
            debit = None
        if credit == 0:
            credit = None
    elif len(amounts) == 2:
        amount, balance = amounts
        if "b/f" in description.lower() or "opening" in description.lower():
            balance = amount
        else:
            debit, credit = _infer_posting_direction(amount, balance, previous_balance, description)
    else:
        balance = amounts[0]

    transaction = {
        "date": date,
        "description": description,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "confidence": "medium",
        "source_line": line.strip(),
    }

    if balance is not None:
        previous_balance = balance
    return transaction, previous_balance


def extract_bank_transactions_locally(text: str) -> list[dict[str, Any]]:
    """
    Parse transaction-like rows from extracted PDF text.

    Works best for digital statements where the tabular lines preserve spacing.
    """
    transactions: list[dict[str, Any]] = []
    current_line: str | None = None
    continuation_lines: list[str] = []
    previous_balance: float | None = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if _DATE_RE.match(stripped):
            if current_line:
                transaction, previous_balance = _parse_transaction_record(
                    current_line,
                    continuation_lines,
                    previous_balance,
                )
                if transaction:
                    transactions.append(transaction)
            current_line = stripped
            continuation_lines = []
            continue

        if current_line and _should_append_continuation(raw_line):
            continuation_lines.append(stripped)

    if current_line:
        transaction, _ = _parse_transaction_record(current_line, continuation_lines, previous_balance)
        if transaction:
            transactions.append(transaction)

    return transactions


def _classify_transaction(description: str, debit: float | None, credit: float | None) -> str:
    lowered = description.lower()

    if "b/f" in lowered or "c/f" in lowered or "opening balance" in lowered:
        return "UNKNOWN"
    if any(keyword in lowered for keyword in _SALARY_KEYWORDS):
        return "VERIFIED_INCOME"
    if is_emi(lowered):
        return "EMI"
    if any(keyword in lowered for keyword in _PENALTY_KEYWORDS):
        return "PENALTY"
    if debit and any(keyword in lowered for keyword in _CASH_WITHDRAWAL_KEYWORDS):
        return "CASH_FLOW"
    if credit and any(keyword in lowered for keyword in _CASH_DEPOSIT_KEYWORDS):
        return "UNVERIFIED_CREDIT"
    if any(keyword in lowered for keyword in _SELF_TRANSFER_KEYWORDS):
        return "CASH_FLOW"
    if credit and credit > 0:
        return "UNVERIFIED_CREDIT"
    if debit and debit > 0:
        return "EXPENSE"
    return "UNKNOWN"


def classify_bank_transactions_locally(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classify parsed transactions without the AI provider."""
    classified: list[dict[str, Any]] = []
    for raw_transaction in transactions:
        transaction = dict(raw_transaction)
        description = str(transaction.get("description") or "")
        debit = _parse_amount(str(transaction.get("debit"))) if isinstance(transaction.get("debit"), str) else transaction.get("debit")
        credit = _parse_amount(str(transaction.get("credit"))) if isinstance(transaction.get("credit"), str) else transaction.get("credit")

        category = _classify_transaction(description, debit, credit)
        if category == "VERIFIED_INCOME":
            notes = "Locally classified as salary-like recurring income."
        elif category == "EMI":
            notes = "Locally classified as loan or installment repayment."
        elif category == "PENALTY":
            notes = "Locally classified as fee or penalty."
        elif category == "CASH_FLOW":
            notes = "Locally classified as cash movement or self-transfer."
        elif category == "UNVERIFIED_CREDIT":
            notes = "Locally classified as unverified incoming credit."
        elif category == "EXPENSE":
            notes = "Locally classified as outgoing spending."
        else:
            notes = "Locally classified with conservative fallback rules."

        transaction["debit"] = debit
        transaction["credit"] = credit
        transaction["category"] = category
        transaction["notes"] = notes
        transaction.setdefault("confidence", "medium")
        transaction.setdefault("source_line", transaction.get("source_line"))
        classified.append(transaction)

    return classified


__all__ = [
    "classify_bank_transactions_locally",
    "extract_bank_transactions_locally",
]
