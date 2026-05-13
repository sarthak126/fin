"""
Explainable risk scoring and final decisioning for bank statements.
"""

from __future__ import annotations

from typing import Any

from core.bank_statement_score import BankStatementScorePayload
from core.confidence import normalize_confidence

_CANONICAL_COMPONENT_MAX = {
    "income_stability": 20,
    "balance_health": 20,
    "obligation_load": 15,
    "spending_discipline": 15,
    "cash_behavior": 15,
    "risk_penalty": 15,
}
_MANUAL_REVIEW_MIN_SCORE = 35
_REJECT_MIN_SCORE = 70


def _safe_score(value: Any) -> int:
    try:
        return max(0, int(round(float(value))))
    except (TypeError, ValueError):
        return 0


def _safe_ratio(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _derive_risk_level(total_risk: int) -> str:
    if total_risk >= 70:
        return "very_high"
    if total_risk >= 55:
        return "high"
    if total_risk >= 35:
        return "medium"
    if total_risk >= 15:
        return "low"
    return "very_low"


def _humanize_component_key(component_key: str) -> str:
    return component_key.replace("_", " ")


def _iter_ranked_risk_components(explainable_risk: dict[str, Any]) -> list[tuple[str, int, int, str]]:
    ranked_components: list[tuple[str, int, int, str]] = []
    for key, factor in (explainable_risk.get("risk_breakdown") or {}).items():
        if not isinstance(factor, dict):
            continue
        score = _safe_score(factor.get("score"))
        if score <= 0:
            continue
        max_score = max(1, _safe_score(factor.get("max")))
        detail = str(factor.get("detail") or "").strip()
        ranked_components.append((key, score, max_score, detail))
    ranked_components.sort(key=lambda item: (item[1], item[2], item[0]), reverse=True)
    return ranked_components


def _format_component_signal(component_key: str, score: int, max_score: int, detail: str) -> str:
    component_label = _humanize_component_key(component_key)
    cleaned_detail = detail.rstrip(".")
    if cleaned_detail:
        return f"{component_label} {score}/{max_score} - {cleaned_detail}"
    return f"{component_label} contributes {score}/{max_score} risk points"


def _score_band_status(total_risk: int) -> tuple[str, str]:
    if total_risk >= _REJECT_MIN_SCORE:
        return "REJECT", "reject"
    if total_risk >= _MANUAL_REVIEW_MIN_SCORE:
        return "REVIEW MANUALLY", "manual_review"
    return "APPROVE", "approve"


def _base_risk_confidence(total_risk: int, normalized_status: str) -> float:
    if normalized_status == "reject":
        return normalize_confidence("high" if total_risk >= 85 else "medium")
    if normalized_status == "manual_review":
        return normalize_confidence("medium")
    return normalize_confidence("high" if total_risk < 20 else "medium")


def _build_score_band_reason(total_risk: int, normalized_status: str) -> str:
    if normalized_status == "reject":
        return f"Risk score {total_risk}/100 is in the reject band."
    if normalized_status == "manual_review":
        return f"Risk score {total_risk}/100 is in the manual review band."
    return f"Risk score {total_risk}/100 is in the approve band."


def _build_score_reason_context(
    *,
    total_risk: int,
    normalized_status: str,
    ranked_components: list[tuple[str, int, int, str]],
) -> dict[str, str]:
    primary_signal = (
        _format_component_signal(*ranked_components[0])
        if ranked_components
        else f"risk_score={total_risk}/100"
    )
    secondary_signal = (
        _format_component_signal(*ranked_components[1])
        if len(ranked_components) > 1
        else f"risk_score={total_risk}/100"
    )

    if normalized_status == "reject":
        return {
            "primary_risk_driver": primary_signal,
            "obligation_signal": secondary_signal,
        }

    if normalized_status == "manual_review":
        return {
            "uncertainty_reason": f"risk_score={total_risk}/100 falls in the manual review band",
            "key_risk_signal": primary_signal,
        }

    top_components = [
        f"{_humanize_component_key(component_key)} {score}/{max_score}"
        for component_key, score, max_score, _detail in ranked_components[:2]
    ]
    if top_components:
        stability_signal = (
            f"risk_score={total_risk}/100 remains in the approve band with "
            f"{' and '.join(top_components)} as the largest contributors"
        )
    else:
        stability_signal = f"risk_score={total_risk}/100 remains in the approve band across all six components"

    return {
        "stability_signal": stability_signal,
        "blockers_signal": "none identified from the canonical score",
    }


def _build_income_stability_detail(score: int, income_engine: dict[str, Any]) -> str:
    income_type = str(income_engine.get("income_type") or "unknown").lower()
    regularity = _safe_score(income_engine.get("income_regularity_score"))
    recurring_income_detected = bool(income_engine.get("recurring_income_detected"))

    if score <= 0:
        if recurring_income_detected and income_type == "salary":
            return f"Recurring salary credits detected with strong cadence (regularity: {regularity}/100)."
        return "Income stability risk is currently minimal."
    if income_type == "unknown":
        return "No verified recurring income was detected, so income stability risk stays elevated."
    if income_type == "unstable":
        return f"Income inflows appear unstable or irregular (regularity: {regularity}/100)."
    if income_type == "mixed":
        return f"Income comes from mixed sources, which weakens stability confidence (regularity: {regularity}/100)."
    if income_type == "salary":
        return f"Salary income is present, but cadence or amount consistency is weaker than ideal (regularity: {regularity}/100)."
    return f"Income pattern contributes {score}/{_CANONICAL_COMPONENT_MAX['income_stability']} risk points."


def _build_balance_health_detail(score: int, agg: dict[str, Any]) -> str:
    negative_count = _safe_score(agg.get("negative_balance_count"))
    low_events = _safe_score(agg.get("low_balance_events"))
    min_balance = _safe_ratio(agg.get("min_balance")) or 0.0
    avg_balance = _safe_ratio(agg.get("avg_balance")) or 0.0
    low_balance_threshold = _safe_ratio(agg.get("low_balance_threshold")) or 1000.0

    if score <= 0:
        return f"Balance health is strong, with average balance around Rs{avg_balance:,.0f}."
    if negative_count > 0:
        return f"{negative_count} negative balance event(s) were observed; minimum balance fell to Rs{min_balance:,.0f}."
    if low_events >= 3:
        return (
            f"{low_events} low balance event(s) fell below the Rs{low_balance_threshold:,.0f} threshold, "
            f"signaling recurring liquidity pressure."
        )
    if low_events >= 1 or min_balance < low_balance_threshold:
        return (
            f"Balance dipped below the Rs{low_balance_threshold:,.0f} threshold {max(low_events, 1)} time(s); "
            f"minimum balance was Rs{min_balance:,.0f}."
        )
    return f"Average balance is thin at roughly Rs{avg_balance:,.0f}, which weakens liquidity resilience."


def _build_obligation_load_detail(score: int, agg: dict[str, Any], dti: dict[str, Any]) -> str:
    emi_total = _safe_ratio(agg.get("emi_total")) or 0.0
    dti_label = str(dti.get("label") or "unknown").lower()
    dti_value = _safe_ratio(dti.get("value"))
    dti_reliability = str(dti.get("reliability") or "verified").lower()

    if score <= 0 and emi_total <= 0:
        return "No EMI obligations were detected."
    if dti_reliability == "unavailable":
        return f"EMI obligations of Rs{emi_total:,.0f} are present, but DTI is unavailable without verified income."
    if dti_reliability == "unverified":
        if dti_value is None:
            return f"EMI obligations of Rs{emi_total:,.0f} are present, but DTI is not reliable without verified income."
        return (
            f"EMI load is {dti_label} at {dti_value:.1%} using unverified inflows "
            f"(Rs{emi_total:,.0f}); not reliable without verified income."
        )
    if dti_label == "unknown":
        return f"EMI obligations of Rs{emi_total:,.0f} are present, but DTI could not be verified from stable income."
    if dti_value is None:
        return f"Obligation load contributes {score}/{_CANONICAL_COMPONENT_MAX['obligation_load']} risk points."
    if dti_label == "low":
        return f"EMI load is low at {dti_value:.1%} of verified income (Rs{emi_total:,.0f})."
    if dti_label == "moderate":
        return f"EMI load is moderate at {dti_value:.1%} of verified income (Rs{emi_total:,.0f})."
    if dti_label == "high":
        return f"EMI load is high at {dti_value:.1%} of verified income (Rs{emi_total:,.0f})."
    return f"EMI load is extreme at {dti_value:.1%} of verified income (Rs{emi_total:,.0f})."


def _build_spending_discipline_detail(
    score: int,
    agg: dict[str, Any],
    cashflow: dict[str, Any],
) -> str:
    verified_income = _safe_ratio(agg.get("verified_income")) or 0.0
    emi_total = _safe_ratio(agg.get("emi_total")) or 0.0
    penalties = _safe_ratio(agg.get("penalties_total")) or 0.0
    total_expenses = _safe_ratio(agg.get("total_expenses")) or 0.0
    total_commitments = total_expenses + emi_total + penalties
    burn_rate = str(cashflow.get("monthly_burn_rate") or "unknown").lower()
    savings_ratio = _safe_ratio(cashflow.get("savings_ratio"))
    burn_ratio = (total_commitments / verified_income) if verified_income > 0 else None

    if verified_income <= 0:
        return (
            "Spending and obligations are present without verified income, so discipline is scored conservatively."
            if score > 0
            else "No verified income or outflow pressure was detected."
        )
    if score <= 1:
        return (
            f"Spending discipline is healthy: total outflows are about {burn_ratio:.0%} of verified income"
            f" with a savings ratio near {(savings_ratio or 0.0):.0%}."
        )
    if burn_rate == "critical":
        return f"Expenses and obligations consume about {burn_ratio:.0%} of verified income, which is unsustainable."
    if burn_rate == "high":
        return f"Expenses and obligations consume about {burn_ratio:.0%} of verified income, leaving limited savings."
    if burn_rate == "medium":
        return f"Expenses and obligations consume about {burn_ratio:.0%} of verified income, indicating moderate pressure."
    return f"Spending discipline contributes {score}/{_CANONICAL_COMPONENT_MAX['spending_discipline']} risk points."


def _build_cash_behavior_detail(
    score: int,
    cash_behavior: dict[str, Any],
    behavioral: dict[str, Any],
) -> str:
    stress_score = _safe_score(cash_behavior.get("stressScore"))
    cash_flags = [str(flag).strip() for flag in cash_behavior.get("flags") or [] if str(flag).strip()]
    high_flags = sum(1 for detail in behavioral.get("flag_details", []) if detail.get("severity") == "high")
    medium_flags = sum(1 for detail in behavioral.get("flag_details", []) if detail.get("severity") == "medium")

    if score <= 0 and not cash_flags and high_flags == 0 and medium_flags == 0:
        return "No cash-behavior stress signals were detected."
    if cash_flags:
        return (
            f"Cash behavior stress is {stress_score}/100 with {len(cash_flags)} liquidity warning(s); "
            f"top signal: {cash_flags[0]}"
        )
    if high_flags or medium_flags:
        return (
            f"Behavioral review found {high_flags} high-severity and {medium_flags} medium-severity liquidity flag(s); "
            f"cash stress score is {stress_score}/100."
        )
    return f"Cash behavior contributes {score}/{_CANONICAL_COMPONENT_MAX['cash_behavior']} risk points."


def _build_risk_penalty_detail(
    score: int,
    agg: dict[str, Any],
    cash_behavior: dict[str, Any],
    dti: dict[str, Any],
) -> str:
    if score <= 0:
        return "No additional penalty multipliers were applied."

    penalty_reasons: list[str] = []
    negative_count = _safe_score(agg.get("negative_balance_count"))
    low_events = _safe_score(agg.get("low_balance_events"))
    dti_label = str(dti.get("label") or "").lower()
    verified_income = _safe_ratio(agg.get("verified_income")) or 0.0
    unverified_income = _safe_ratio(agg.get("unverified_income")) or 0.0
    cash_deposits = _safe_ratio(agg.get("cash_deposits")) or 0.0
    inflow = max(verified_income + unverified_income + cash_deposits, 0.0)
    cash_withdrawals = _safe_ratio(agg.get("cash_withdrawals")) or 0.0
    withdrawal_ratio = (cash_withdrawals / inflow) if inflow > 0 else 0.0
    unverified_share = (unverified_income / inflow) if inflow > 0 else 0.0
    suspicious_count = _safe_score(agg.get("suspicious_count"))
    duplicate_count = _safe_score(agg.get("duplicate_count"))
    cash_flags = [str(flag) for flag in cash_behavior.get("flags") or []]

    if negative_count > 0:
        penalty_reasons.append("negative balances")
    if low_events >= 3:
        penalty_reasons.append("repeated low balances")
    if dti_label in {"high", "extreme"}:
        penalty_reasons.append(f"{dti_label} DTI")
    if inflow > 0 and withdrawal_ratio > 0.4:
        penalty_reasons.append("high cash withdrawal ratio")
    if inflow > 0 and unverified_income > 0 and unverified_share > 0.5:
        penalty_reasons.append("heavy unverified credit share")
    if suspicious_count > 0:
        penalty_reasons.append("suspicious transfer patterns")
    if any("Weak end-of-statement" in flag for flag in cash_flags):
        penalty_reasons.append("weak end-of-month balance")
    if duplicate_count > 0:
        penalty_reasons.append("duplicate-looking transactions")

    if not penalty_reasons:
        return f"Additional penalty adjustments contribute {score}/{_CANONICAL_COMPONENT_MAX['risk_penalty']} risk points."
    return (
        f"Additional penalty points were applied for {', '.join(penalty_reasons)}."
    )


def compute_explainable_risk(
    canonical_risk_score: BankStatementScorePayload,
    agg: dict[str, Any],
    income_engine: dict[str, Any],
    cash_behavior: dict[str, Any],
    cashflow: dict[str, Any],
    behavioral: dict[str, Any],
    dti: dict[str, Any],
    overall_confidence: float,
) -> dict[str, Any]:
    _ = overall_confidence
    breakdown = {
        "income_stability": {
            "score": canonical_risk_score["income_stability"],
            "max": _CANONICAL_COMPONENT_MAX["income_stability"],
            "detail": _build_income_stability_detail(canonical_risk_score["income_stability"], income_engine),
        },
        "balance_health": {
            "score": canonical_risk_score["balance_health"],
            "max": _CANONICAL_COMPONENT_MAX["balance_health"],
            "detail": _build_balance_health_detail(canonical_risk_score["balance_health"], agg),
        },
        "obligation_load": {
            "score": canonical_risk_score["obligation_load"],
            "max": _CANONICAL_COMPONENT_MAX["obligation_load"],
            "detail": _build_obligation_load_detail(canonical_risk_score["obligation_load"], agg, dti),
        },
        "spending_discipline": {
            "score": canonical_risk_score["spending_discipline"],
            "max": _CANONICAL_COMPONENT_MAX["spending_discipline"],
            "detail": _build_spending_discipline_detail(
                canonical_risk_score["spending_discipline"],
                agg,
                cashflow,
            ),
        },
        "cash_behavior": {
            "score": canonical_risk_score["cash_behavior"],
            "max": _CANONICAL_COMPONENT_MAX["cash_behavior"],
            "detail": _build_cash_behavior_detail(canonical_risk_score["cash_behavior"], cash_behavior, behavioral),
        },
        "risk_penalty": {
            "score": canonical_risk_score["risk_penalty"],
            "max": _CANONICAL_COMPONENT_MAX["risk_penalty"],
            "detail": _build_risk_penalty_detail(canonical_risk_score["risk_penalty"], agg, cash_behavior, dti),
        },
    }
    total_risk = canonical_risk_score["final_score"]

    return {
        "risk_breakdown": breakdown,
        "total_risk_score": total_risk,
        "max_possible_risk": sum(_CANONICAL_COMPONENT_MAX.values()),
        "risk_level": _derive_risk_level(total_risk),
    }


def compute_final_decision(
    canonical_risk_score: BankStatementScorePayload,
    explainable_risk: dict[str, Any],
    overall_confidence: float,
) -> dict[str, Any]:
    total_risk = canonical_risk_score["final_score"]
    decision, normalized_status = _score_band_status(total_risk)
    ranked_components = _iter_ranked_risk_components(explainable_risk)
    reasons = [_build_score_band_reason(total_risk, normalized_status)]

    for component_key, score, max_score, detail in ranked_components[:3]:
        reasons.append(_format_component_signal(component_key, score, max_score, detail))

    return {
        "decision": decision,
        "reasons": reasons[:8],
        "risk_confidence": min(
            _base_risk_confidence(total_risk, normalized_status),
            normalize_confidence(overall_confidence),
        ),
        "reason_context": _build_score_reason_context(
            total_risk=total_risk,
            normalized_status=normalized_status,
            ranked_components=ranked_components,
        ),
    }
