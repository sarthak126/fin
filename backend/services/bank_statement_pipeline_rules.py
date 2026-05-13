"""
Transaction normalization and deterministic category overrides.
"""

from collections import defaultdict
from typing import Any, List, Tuple

from services.bank_statement_engine_common import (
    is_transfer_like_description,
    is_verification_credit_transaction,
    parse_statement_date,
)
from services.bank_statement_pipeline_types import (
    Transaction,
    append_note,
    is_cash_deposit,
    is_cash_withdrawal,
    is_emi,
    is_penalty,
    is_reversal,
    is_suspicious,
    norm_desc,
    normalize_category,
    parse_tx_confidence,
    safe_float,
)

PASS_THROUGH_MATCH_TOLERANCE = 25.0
_GENERIC_CREDIT_KEYWORDS = ("upi", "trtr", "digitb")
_VERIFIED_INCOME_KEYWORDS = ("salary", "payroll", "sal cr", "sal/", "stipend", "wages", "compensation")


def _is_generic_non_salary_credit(description: str) -> bool:
    if any(keyword in description for keyword in _VERIFIED_INCOME_KEYWORDS):
        return False
    return any(keyword in description for keyword in _GENERIC_CREDIT_KEYWORDS)


def _override_category(transaction: Transaction, description: str) -> None:
    credit = safe_float(transaction.get("credit")) or 0.0
    if credit > 0 and normalize_category(transaction.get("category")) == "VERIFIED_INCOME" and _is_generic_non_salary_credit(description):
        transaction["category"] = "UNVERIFIED_CREDIT"
        append_note(transaction, "Overridden: generic transfer/UPI credit is not verified income.")
    elif is_cash_withdrawal(description):
        transaction["category"] = "CASH_FLOW"
        append_note(transaction, "Overridden: ATM/cash withdrawal -> CASH_FLOW.")
    elif is_cash_deposit(description):
        transaction["category"] = "UNVERIFIED_CREDIT"
        append_note(transaction, "Overridden: cash deposit -> UNVERIFIED_CREDIT (not verified income).")
    elif is_emi(description):
        transaction["category"] = "EMI"
        append_note(transaction, "Overridden: EMI/installment repayment signals -> EMI.")
    elif is_penalty(description):
        transaction["category"] = "PENALTY"
        append_note(transaction, "Overridden: penalty/fee keywords -> PENALTY.")
    elif is_suspicious(description):
        transaction["category"] = "SUSPICIOUS"
        append_note(transaction, "Overridden: suspicious/unknown credit pattern -> SUSPICIOUS.")


def _mark_pass_through_transfers(transactions: List[Transaction]) -> None:
    credits_by_day: dict[object, list[tuple[int, float]]] = defaultdict(list)
    debits_by_day: dict[object, list[tuple[int, float]]] = defaultdict(list)

    for index, transaction in enumerate(transactions):
        if transaction.get("duplicate") or transaction.get("reversal") or transaction.get("verification_credit"):
            continue

        statement_date = parse_statement_date(transaction.get("date"))
        if statement_date is None:
            continue

        description = norm_desc(transaction.get("description"))
        credit = safe_float(transaction.get("credit")) or 0.0
        debit = safe_float(transaction.get("debit")) or 0.0

        if is_transfer_like_description(description):
            if credit > 0:
                credits_by_day[statement_date].append((index, credit))
            if debit > 0:
                debits_by_day[statement_date].append((index, debit))

    for statement_date, credits in credits_by_day.items():
        debits = debits_by_day.get(statement_date, [])
        used_debits: set[int] = set()

        for credit_index, credit_amount in sorted(credits, key=lambda item: item[1], reverse=True):
            best_match: tuple[int, float] | None = None
            best_diff: float | None = None

            for debit_index, debit_amount in debits:
                if debit_index == credit_index or debit_index in used_debits:
                    continue

                diff = abs(credit_amount - debit_amount)
                if diff > PASS_THROUGH_MATCH_TOLERANCE:
                    continue

                if best_diff is None or diff < best_diff:
                    best_match = (debit_index, debit_amount)
                    best_diff = diff

            if best_match is None:
                continue

            debit_index, debit_amount = best_match
            used_debits.add(debit_index)
            transactions[credit_index]["pass_through_transfer"] = True
            transactions[debit_index]["pass_through_transfer"] = True
            append_note(
                transactions[credit_index],
                (
                    f"Same-day pass-through transfer matched within Rs{PASS_THROUGH_MATCH_TOLERANCE:,.0f} "
                    f"(paired debit Rs{debit_amount:,.2f}); excluded from stable-income analysis."
                ),
            )
            append_note(
                transactions[debit_index],
                (
                    f"Same-day pass-through transfer matched within Rs{PASS_THROUGH_MATCH_TOLERANCE:,.0f} "
                    f"(paired credit Rs{credit_amount:,.2f}); excluded from stable-income analysis."
                ),
            )


def apply_bank_statement_rule_engine(transactions: List[Transaction]) -> List[Transaction]:
    """
    Apply deterministic corrections to extracted transactions.

    Gemini helps with extraction and soft categorization, but the backend
    remains the source of truth for category normalization and math inputs.
    """
    seen: set[Tuple[Any, ...]] = set()
    corrected: List[Transaction] = []

    for raw_transaction in transactions:
        transaction = dict(raw_transaction)
        transaction.setdefault("notes", "")
        transaction.setdefault("duplicate", False)
        transaction.setdefault("reversal", False)
        transaction.setdefault("category", "UNKNOWN")
        transaction.setdefault("verification_credit", False)
        transaction.setdefault("pass_through_transfer", False)

        description = norm_desc(transaction.get("description"))
        debit = safe_float(transaction.get("debit"))
        credit = safe_float(transaction.get("credit"))
        balance = safe_float(transaction.get("balance"))
        date = str(transaction.get("date") or "").strip()
        source_line = norm_desc(transaction.get("source_line"))

        dedupe_key: Tuple[Any, ...] | None = None
        if source_line:
            dedupe_key = ("source_line", source_line)
        elif balance is not None:
            dedupe_key = (
                "dated_amount_balance",
                date,
                round(float(debit or 0.0), 2),
                round(float(credit or 0.0), 2),
                round(float(balance), 2),
                description,
            )

        if dedupe_key is not None:
            if dedupe_key in seen:
                transaction["duplicate"] = True
                append_note(transaction, "Duplicate-looking transaction flagged.")
            else:
                seen.add(dedupe_key)

        if is_reversal(description):
            transaction["reversal"] = True
            append_note(transaction, "Reversal/refund/chargeback detected.")

        _override_category(transaction, description)

        if is_verification_credit_transaction(transaction):
            transaction["verification_credit"] = True
            append_note(
                transaction,
                "Micro verification credit detected; excluded from stable-income analysis.",
            )

        transaction["category"] = normalize_category(transaction.get("category"))
        transaction["debit"] = debit if debit is not None else None
        transaction["credit"] = credit if credit is not None else None
        transaction["balance"] = balance if balance is not None else None
        transaction["date"] = date or transaction.get("date")
        transaction["confidence"] = parse_tx_confidence(transaction.get("confidence"))
        transaction.setdefault("source_line", transaction.get("source_line") or None)

        corrected.append(transaction)

    _mark_pass_through_transfers(corrected)

    return corrected
