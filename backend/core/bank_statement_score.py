"""
Canonical bank statement score payload helpers.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, TypedDict

BANK_STATEMENT_SCORE_MODEL = "bank_statement_v2"
_CANONICAL_COMPONENT_FIELDS = (
    ("income_stability", "incomeStability"),
    ("balance_health", "balanceHealth"),
    ("obligation_load", "obligationLoad"),
    ("spending_discipline", "spendingDiscipline"),
    ("cash_behavior", "cashBehavior"),
    ("risk_penalty", "riskPenalty"),
)


class BankStatementScorePayload(TypedDict):
    score_model: Literal["bank_statement_v2"]
    income_stability: int
    balance_health: int
    obligation_load: int
    spending_discipline: int
    cash_behavior: int
    risk_penalty: int
    final_score: int


def _coerce_score_int(value: Any) -> int:
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, numeric)


def _derive_final_score_from_components(components: Mapping[str, int]) -> int:
    return min(
        100,
        sum(
            int(components[field])
            for field, _legacy_field in _CANONICAL_COMPONENT_FIELDS
        ),
    )


def build_bank_statement_score_payload(
    *,
    income_stability: Any,
    balance_health: Any,
    obligation_load: Any,
    spending_discipline: Any,
    cash_behavior: Any,
    risk_penalty: Any,
    final_score: Any | None = None,
) -> BankStatementScorePayload:
    components = {
        "income_stability": _coerce_score_int(income_stability),
        "balance_health": _coerce_score_int(balance_health),
        "obligation_load": _coerce_score_int(obligation_load),
        "spending_discipline": _coerce_score_int(spending_discipline),
        "cash_behavior": _coerce_score_int(cash_behavior),
        "risk_penalty": _coerce_score_int(risk_penalty),
    }
    return {
        "score_model": BANK_STATEMENT_SCORE_MODEL,
        **components,
        "final_score": (
            _derive_final_score_from_components(components)
            if final_score is None
            else _coerce_score_int(final_score)
        ),
    }


def canonicalize_bank_statement_score_payload(
    payload: Mapping[str, Any] | None,
    *,
    final_score: Any | None = None,
) -> BankStatementScorePayload:
    normalized = dict(payload or {})
    has_component_keys = any(
        canonical_field in normalized or legacy_field in normalized
        for canonical_field, legacy_field in _CANONICAL_COMPONENT_FIELDS
    )
    explicit_final_score = (
        final_score
        if final_score is not None
        else normalized.get("final_score", normalized.get("finalScore"))
    )
    return build_bank_statement_score_payload(
        income_stability=normalized.get("income_stability", normalized.get("incomeStability")),
        balance_health=normalized.get("balance_health", normalized.get("balanceHealth")),
        obligation_load=normalized.get("obligation_load", normalized.get("obligationLoad")),
        spending_discipline=normalized.get("spending_discipline", normalized.get("spendingDiscipline")),
        cash_behavior=normalized.get("cash_behavior", normalized.get("cashBehavior")),
        risk_penalty=normalized.get("risk_penalty", normalized.get("riskPenalty")),
        final_score=None if has_component_keys else explicit_final_score,
    )
