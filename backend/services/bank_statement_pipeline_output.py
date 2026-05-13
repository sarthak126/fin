"""
Output composition for deterministic bank statement analysis.
"""

import re
from typing import Any, Dict, List

from core.bank_statement_score import BankStatementScorePayload, canonicalize_bank_statement_score_payload
from core.confidence import (
    build_decision_payload,
    build_decision_reason_template,
    build_risk_alerts_from_flags,
    build_summary_from_decision,
    canonicalize_analysis_payload,
    normalize_confidence,
    normalize_decision_status,
)
from services.bank_statement_engine import (
    compute_behavioral_flags,
    compute_cashflow_intelligence,
    compute_explainable_risk,
    compute_final_decision,
    compute_income_engine,
    compute_spending_intelligence,
)
from services.bank_statement_engine_common import extract_month_key, is_excluded_from_income_analysis, safe_float
from services.bank_statement_pipeline_metrics import (
    analyze_cash_behavior,
    compute_dti,
    deterministic_aggregate,
)
from services.bank_statement_pipeline_rules import apply_bank_statement_rule_engine
from services.bank_statement_pipeline_scoring import compute_risk_scores
from services.bank_statement_pipeline_types import Transaction
from services.bank_statement_profile import merge_statement_evidence

MIN_HISTORY_DAYS_FOR_FULL_UNDERWRITING = 90
SHORT_HISTORY_RISK_CONFIDENCE_CAP = 0.4
SHORT_HISTORY_DECISION_RECOMMENDATION = "Manual review / request 3\u20136 months statement history"
SHORT_HISTORY_REQUIRED_FOLLOWUPS = ["Request 3\u20136 months of bank statement history"]


def _build_reasoning(
    explainable_risk: Dict[str, Any],
    decision_engine: Dict[str, Any],
    canonical_risk_score: BankStatementScorePayload,
) -> List[str]:
    decision = decision_engine["decision"]
    reasoning = [
        f"Final risk score: {canonical_risk_score['final_score']}/100 ({explainable_risk['risk_level']}).",
    ]
    for factor_key, factor in explainable_risk.get("risk_breakdown", {}).items():
        reasoning.append(f"  - {factor_key}: {factor['score']}/{factor['max']} - {factor['detail']}")
    reasoning.append(f"Decision: {decision}")
    for reason in decision_engine.get("reasons", []):
        reasoning.append(f"  -> {reason}")
    return reasoning


def _build_uncertainty_notes(corrected: List[Transaction]) -> List[str]:
    uncertainty_notes: List[str] = []
    if not corrected:
        uncertainty_notes.append("No transactions extracted.")
        return uncertainty_notes

    missing_balance = sum(1 for transaction in corrected if transaction.get("balance") is None)
    if missing_balance > max(1, len(corrected) // 3):
        uncertainty_notes.append(
            "Many transactions are missing balance values; liquidity signals may be less reliable."
        )
    return uncertainty_notes


def _is_short_history_gate_active(statement_summary: Dict[str, Any]) -> bool:
    coverage_days = int(statement_summary.get("coverage_days") or 0)
    return coverage_days < MIN_HISTORY_DAYS_FOR_FULL_UNDERWRITING


def _append_unique_strings(existing: List[str], additions: List[str]) -> List[str]:
    merged = list(existing)
    seen = set(existing)
    for item in additions:
        if not item or item in seen:
            continue
        merged.append(item)
        seen.add(item)
    return merged


def _prepend_primary_reason(primary_reason: str, additional_reasons: List[str]) -> List[str]:
    cleaned_primary = str(primary_reason or "").strip()
    merged: List[str] = [cleaned_primary] if cleaned_primary else []
    seen = {cleaned_primary.lower()} if cleaned_primary else set()

    for reason in additional_reasons:
        cleaned_reason = str(reason or "").strip()
        if not cleaned_reason:
            continue
        lowered_reason = cleaned_reason.lower()
        if lowered_reason in seen:
            continue
        merged.append(cleaned_reason)
        seen.add(lowered_reason)

    return merged


def _build_short_history_limitations(base_limitations: List[str], coverage_days: int) -> List[str]:
    return _append_unique_strings(
        list(base_limitations),
        [
            (
                f"Statement coverage is only {coverage_days} day(s), below the "
                f"{MIN_HISTORY_DAYS_FOR_FULL_UNDERWRITING}-day minimum required for full underwriting."
            ),
            "Long-term income stability, recurring obligations, and balance behavior cannot be evidenced from the available statement history.",
            "Income, DTI, and risk outputs are provisional because the available history is too short for a final underwriting decision.",
        ],
    )


def _build_decision_reason_context(
    *,
    coverage_days: int,
    statement_summary: Dict[str, Any],
    income_engine: Dict[str, Any],
    aggregate: Dict[str, Any],
    dti: Dict[str, Any],
    cashflow_intelligence: Dict[str, Any],
    explainable_risk: Dict[str, Any],
    canonical_risk_score: BankStatementScorePayload | None = None,
) -> Dict[str, Any]:
    recurring_income_detected = bool(
        income_engine.get("recurring_income_detected") or statement_summary.get("recurring_income_detected")
    )
    income_inference_skipped = bool(income_engine.get("income_inference_skipped"))
    income_type = income_engine.get("income_type")
    if not recurring_income_detected and income_type == "salary" and not income_inference_skipped:
        recurring_income_detected = True

    return {
        "coverage_days": coverage_days,
        "min_history_days": MIN_HISTORY_DAYS_FOR_FULL_UNDERWRITING,
        "stable_income_detected": recurring_income_detected,
        "income_type": income_type,
        "income_inference_skipped": income_inference_skipped,
        "monthly_income": income_engine.get("monthly_income_estimate"),
        "total_credits": statement_summary.get("total_credits"),
        "total_debits": statement_summary.get("total_debits"),
        "net_flow": statement_summary.get("net_flow"),
        "min_balance": statement_summary.get("min_balance"),
        "avg_balance": statement_summary.get("avg_balance"),
        "low_balance_count": statement_summary.get("low_balance_count"),
        "existing_emis": aggregate.get("emi_total"),
        "emi_total": aggregate.get("emi_total"),
        "dti_label": dti.get("label"),
        "dti_value": dti.get("value"),
        "burn_rate": cashflow_intelligence.get("monthly_burn_rate"),
        "risk_level": explainable_risk.get("risk_level"),
        "risk_score": (
            canonical_risk_score["final_score"]
            if canonical_risk_score is not None
            else explainable_risk.get("total_risk_score")
        ),
    }


def _mark_short_history_income_engine_provisional(
    income_engine: Dict[str, Any],
    coverage_days: int,
) -> Dict[str, Any]:
    provisional_income_engine = dict(income_engine)
    provisional_income_engine["income_inference_skipped"] = False
    provisional_income_engine["provisional"] = True
    provisional_income_engine["provisional_reason"] = (
        f"Only {coverage_days} day(s) of statement history were available; "
        f"{MIN_HISTORY_DAYS_FOR_FULL_UNDERWRITING} days are required for full underwriting."
    )
    return provisional_income_engine


def _build_short_history_decision(
    *,
    statement_confidence: float,
    coverage_days: int,
    statement_summary: Dict[str, Any],
    aggregate: Dict[str, Any],
    income_engine: Dict[str, Any],
    dti: Dict[str, Any],
    cashflow_intelligence: Dict[str, Any],
    explainable_risk: Dict[str, Any],
    canonical_risk_score: BankStatementScorePayload,
    uncertainty_notes: List[str],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    capped_confidence = min(
        normalize_confidence(statement_confidence),
        SHORT_HISTORY_RISK_CONFIDENCE_CAP,
    )
    decision_reason = (
        f"Statement coverage is only {coverage_days} day(s), which is below the "
        f"{MIN_HISTORY_DAYS_FOR_FULL_UNDERWRITING}-day minimum for full underwriting."
    )
    decision_reasons = [
        decision_reason,
        "Income, DTI, and risk outputs are provisional because the available history is too short for a reliable 3-6 month underwriting assessment.",
    ]
    analysis_limitations = _build_short_history_limitations(uncertainty_notes, coverage_days)
    reason_context = _build_decision_reason_context(
        coverage_days=coverage_days,
        statement_summary=statement_summary,
        income_engine=income_engine,
        aggregate=aggregate,
        dti=dti,
        cashflow_intelligence=cashflow_intelligence,
        explainable_risk=explainable_risk,
        canonical_risk_score=canonical_risk_score,
    )
    primary_reason = build_decision_reason_template(
        "insufficient_history",
        reason_context=reason_context,
        required_followups=SHORT_HISTORY_REQUIRED_FOLLOWUPS,
        analysis_limitations=analysis_limitations,
        fallback_reason=decision_reason,
    )
    decision_reasons = _prepend_primary_reason(primary_reason, decision_reasons)
    decision_payload = build_decision_payload(
        decision_status="insufficient_history",
        decision_recommendation=SHORT_HISTORY_DECISION_RECOMMENDATION,
        decision_reason=primary_reason,
        extraction_confidence=statement_confidence,
        risk_confidence=capped_confidence,
        data_completeness=capped_confidence,
        required_followups=SHORT_HISTORY_REQUIRED_FOLLOWUPS,
        analysis_limitations=analysis_limitations,
        reasons=decision_reasons,
        decision_candidates=["insufficient_history"],
        reason_context=reason_context,
    )
    decision_engine = {
        "decision": "INSUFFICIENT_HISTORY",
        "reasons": decision_reasons,
        "risk_confidence": capped_confidence,
    }
    return decision_payload, decision_engine


def _detect_emi_pattern(corrected: List[Transaction]) -> bool:
    emi_count = 0
    emi_months: set[str] = set()

    for transaction in corrected:
        if transaction.get("duplicate") or transaction.get("reversal") or transaction.get("category") != "EMI":
            continue

        if (safe_float(transaction.get("debit")) or 0.0) <= 0:
            continue

        emi_count += 1
        month = extract_month_key(str(transaction.get("date") or ""))
        if month:
            emi_months.add(month)

    return len(emi_months) >= 2 or emi_count >= 2


def _build_statement_semantics(
    corrected: List[Transaction],
    income_engine: Dict[str, Any],
) -> Dict[str, bool]:
    return {
        "recurring_income_detected": bool(income_engine.get("recurring_income_detected")),
        "emi_pattern_detected": _detect_emi_pattern(corrected),
        "pass_through_transfer_detected": any(
            not transaction.get("duplicate")
            and not transaction.get("reversal")
            and transaction.get("pass_through_transfer")
            for transaction in corrected
        ),
        "verification_credits_detected": any(
            not transaction.get("duplicate")
            and not transaction.get("reversal")
            and transaction.get("verification_credit")
            for transaction in corrected
        ),
    }


def _monthly_unverified_inflows(corrected: List[Transaction]) -> dict[str, float]:
    monthly: dict[str, float] = {}
    for transaction in corrected:
        if transaction.get("duplicate") or transaction.get("reversal") or is_excluded_from_income_analysis(transaction):
            continue
        if transaction.get("category") != "UNVERIFIED_CREDIT":
            continue
        credit = safe_float(transaction.get("credit")) or 0.0
        if credit <= 0:
            continue
        month = extract_month_key(str(transaction.get("date") or ""))
        if not month:
            continue
        monthly[month] = monthly.get(month, 0.0) + credit
    return {month: round(value, 2) for month, value in sorted(monthly.items())}


def _build_monthly_range(monthly_values: dict[str, float]) -> dict[str, Any] | None:
    values = sorted(value for value in monthly_values.values() if value > 0)
    if not values:
        return None
    low = round(values[0], 3)
    high = round(values[-1], 3)
    display = f"{int(low)}" if low == high else f"{int(low)}-{int(high)}"
    return {"min": low, "max": high, "display": display}


def _verified_monthly_estimate(income_engine: Dict[str, Any], aggregate: Dict[str, Any]) -> float | None:
    salary_credits = [
        safe_float(value)
        for value in income_engine.get("salary_credits") or []
    ]
    salary_credits = [value for value in salary_credits if value is not None and value > 0]
    if not salary_credits:
        verified_income = safe_float(aggregate.get("verified_income"))
        income_type = str(income_engine.get("income_type") or "").strip().lower()
        if verified_income is not None and verified_income > 0 and income_type == "salary":
            return round(verified_income, 3)
        return None

    recurring_income = safe_float(income_engine.get("recurring_income_estimate"))
    if recurring_income is not None and recurring_income > 0:
        return round(recurring_income, 3)
    return round(sum(salary_credits) / len(salary_credits), 3)


def _apply_evidence_to_statement_summary(
    statement_summary: Dict[str, Any],
    evidence_profile: Dict[str, Any] | None,
) -> Dict[str, Any]:
    evidence_profile = evidence_profile or {}
    return {
        **statement_summary,
        "declared_period_start_date": evidence_profile.get("declared_period_start_date"),
        "declared_period_end_date": evidence_profile.get("declared_period_end_date"),
        "last_transaction_date": statement_summary.get("last_transaction_date")
        or evidence_profile.get("last_transaction_date")
        or statement_summary.get("statement_end_date"),
    }


def _serialize_transactions(corrected: List[Transaction]) -> List[Dict[str, Any]]:
    return [
        {
            "date": transaction.get("date"),
            "description": transaction.get("description"),
            "debit": transaction.get("debit"),
            "credit": transaction.get("credit"),
            "balance": transaction.get("balance"),
            "category": transaction.get("category"),
            "confidence": transaction.get("confidence"),
            "duplicate": bool(transaction.get("duplicate")),
            "reversal": bool(transaction.get("reversal")),
            "verification_credit": bool(transaction.get("verification_credit")),
            "pass_through_transfer": bool(transaction.get("pass_through_transfer")),
            "notes": transaction.get("notes", ""),
        }
        for transaction in corrected
    ]


def _normalize_income_estimate_bounds(
    monthly_income_estimate: Any,
    *,
    monthly_income_estimate_min: Any = None,
    monthly_income_estimate_max: Any = None,
) -> tuple[float | None, float | None]:
    low = safe_float(monthly_income_estimate_min)
    high = safe_float(monthly_income_estimate_max)
    if low is not None or high is not None:
        if low is None:
            low = high
        if high is None:
            high = low
    elif monthly_income_estimate in (None, ""):
        return None, None
    elif isinstance(monthly_income_estimate, (int, float)):
        low = float(monthly_income_estimate)
        high = float(monthly_income_estimate)
    elif isinstance(monthly_income_estimate, str):
        cleaned = monthly_income_estimate.replace(",", "").strip()
        if not cleaned:
            return None, None
        range_match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)", cleaned)
        if range_match:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
        else:
            parsed = safe_float(cleaned)
            if parsed is None:
                return None, None
            low = float(parsed)
            high = float(parsed)
    else:
        return None, None

    assert low is not None
    assert high is not None
    return round(min(low, high), 3), round(max(low, high), 3)


def _derive_annual_estimate(
    monthly_income_estimate: Any,
    *,
    monthly_income_estimate_min: Any = None,
    monthly_income_estimate_max: Any = None,
) -> float | None:
    low, high = _normalize_income_estimate_bounds(
        monthly_income_estimate,
        monthly_income_estimate_min=monthly_income_estimate_min,
        monthly_income_estimate_max=monthly_income_estimate_max,
    )
    if low is None or high is None:
        return None
    return round(((low + high) / 2.0) * 12.0, 3)


def _derive_annual_estimate_range(
    monthly_income_estimate: Any,
    *,
    monthly_income_estimate_min: Any = None,
    monthly_income_estimate_max: Any = None,
) -> tuple[float | None, float | None]:
    low, high = _normalize_income_estimate_bounds(
        monthly_income_estimate,
        monthly_income_estimate_min=monthly_income_estimate_min,
        monthly_income_estimate_max=monthly_income_estimate_max,
    )
    if low is None or high is None:
        return None, None
    return round(low * 12.0, 3), round(high * 12.0, 3)


def build_bank_statement_output(
    transactions: List[Transaction],
    statement_confidence: float,
    document_type: str = "bank_statement",
    evidence_profile: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    corrected = apply_bank_statement_rule_engine(transactions)
    aggregate = deterministic_aggregate(corrected)
    short_history_gate_active = _is_short_history_gate_active(aggregate["statement_summary"])
    coverage_days = int(aggregate["statement_summary"].get("coverage_days") or 0)

    print("[brain] Computing Income Engine...")
    income_engine = compute_income_engine(corrected)
    if short_history_gate_active:
        income_engine = _mark_short_history_income_engine_provisional(income_engine, coverage_days)

    verified_monthly_estimate = _verified_monthly_estimate(income_engine, aggregate)
    dti = compute_dti(
        aggregate["emi_total"],
        verified_monthly_estimate or 0.0,
        recurring_income_estimate=verified_monthly_estimate,
        unverified_income=aggregate["unverified_income"],
    )
    cash_behavior = analyze_cash_behavior(corrected, aggregate)
    risk_scoring = compute_risk_scores(
        corrected,
        aggregate,
        dti,
        cash_behavior,
        overall_confidence=float(statement_confidence),
    )
    canonical_risk_score = canonicalize_bank_statement_score_payload(risk_scoring)

    statement_summary = _apply_evidence_to_statement_summary({
        **aggregate["statement_summary"],
        **_build_statement_semantics(corrected, income_engine),
    }, evidence_profile)
    uncertainty_notes = _build_uncertainty_notes(corrected)

    print("[brain] Computing Cash Flow Intelligence...")
    cashflow_intelligence = compute_cashflow_intelligence(corrected, aggregate, income_engine)

    print("[brain] Computing Spending Intelligence...")
    spending_intelligence = compute_spending_intelligence(corrected)

    print("[brain] Computing Behavioral Flags...")
    behavioral_flags = compute_behavioral_flags(corrected, aggregate, income_engine, cashflow_intelligence)

    print("[brain] Computing Explainable Risk Score...")
    explainable_risk = compute_explainable_risk(
        canonical_risk_score,
        aggregate,
        income_engine,
        cash_behavior,
        cashflow_intelligence,
        behavioral_flags,
        dti,
        float(statement_confidence),
    )

    print("[brain] Computing Final Decision...")
    if short_history_gate_active:
        decision_payload, decision_engine = _build_short_history_decision(
            statement_confidence=float(statement_confidence),
            coverage_days=coverage_days,
            statement_summary=statement_summary,
            aggregate=aggregate,
            income_engine=income_engine,
            dti=dti,
            cashflow_intelligence=cashflow_intelligence,
            explainable_risk=explainable_risk,
            canonical_risk_score=canonical_risk_score,
            uncertainty_notes=uncertainty_notes,
        )
    else:
        decision_engine = compute_final_decision(
            canonical_risk_score,
            explainable_risk,
            float(statement_confidence),
        )
        raw_decision = decision_engine.get("decision")
        normalized_decision_status = normalize_decision_status(raw_decision)
        reason_context = _build_decision_reason_context(
            coverage_days=coverage_days,
            statement_summary=statement_summary,
            income_engine=income_engine,
            aggregate=aggregate,
            dti=dti,
            cashflow_intelligence=cashflow_intelligence,
            explainable_risk=explainable_risk,
            canonical_risk_score=canonical_risk_score,
        )
        reason_context.update(
            decision_engine.get("reason_context")
            if isinstance(decision_engine.get("reason_context"), dict)
            else {}
        )
        primary_reason = build_decision_reason_template(
            normalized_decision_status,
            reason_context=reason_context,
            fallback_reason=(decision_engine.get("reasons") or [None])[0],
            analysis_limitations=uncertainty_notes,
        )
        decision_engine["reasons"] = _prepend_primary_reason(
            primary_reason,
            [str(reason) for reason in decision_engine.get("reasons") or []],
        )
        decision_payload = build_decision_payload(
            decision_status=normalized_decision_status,
            decision_reason=primary_reason,
            extraction_confidence=statement_confidence,
            risk_confidence=decision_engine.get("risk_confidence", statement_confidence),
            data_completeness=statement_confidence,
            required_followups=[],
            analysis_limitations=uncertainty_notes,
            reasons=[primary_reason],
            decision_candidates=[raw_decision],
            reason_context=reason_context,
        )

    statement_quality = "Clean" if float(statement_confidence) > 0.8 else "Noisy"
    reasoning_lines = _build_reasoning(explainable_risk, decision_engine, canonical_risk_score)
    unverified_monthly_inflows = _monthly_unverified_inflows(corrected)
    unverified_monthly_inflow_range = _build_monthly_range(unverified_monthly_inflows)
    verified_income_display = None
    verified_monthly_min = None
    verified_monthly_max = None
    if verified_monthly_estimate is not None:
        verified_income_display = income_engine.get("monthly_income_estimate") or (
            str(int(verified_monthly_estimate))
            if float(verified_monthly_estimate).is_integer()
            else str(verified_monthly_estimate)
        )
        verified_monthly_min = income_engine.get("monthly_income_estimate_min", verified_monthly_estimate)
        verified_monthly_max = income_engine.get("monthly_income_estimate_max", verified_monthly_estimate)
    annual_income_estimate = _derive_annual_estimate(
        verified_income_display,
        monthly_income_estimate_min=verified_monthly_min,
        monthly_income_estimate_max=verified_monthly_max,
    )
    annual_income_estimate_min, annual_income_estimate_max = _derive_annual_estimate_range(
        verified_income_display,
        monthly_income_estimate_min=verified_monthly_min,
        monthly_income_estimate_max=verified_monthly_max,
    )
    evidence_profile = merge_statement_evidence(evidence_profile, None)

    payload = {
            "decision": decision_payload,
            "statement_summary": statement_summary,
            "transaction_insights": {
                "document_type": document_type,
                "statement_quality": statement_quality,
                "statement_confidence": round(float(statement_confidence), 4),
                "income": {
                    "verified": round(aggregate["verified_income"], 3),
                    "unverified": round(aggregate["unverified_income"], 3),
                    "verified_monthly_estimate": verified_monthly_estimate,
                    "unverified_monthly_inflow_range": unverified_monthly_inflow_range,
                    "monthly_estimate": verified_income_display,
                    "monthly_estimate_min": verified_monthly_min,
                    "monthly_estimate_max": verified_monthly_max,
                    "annual_estimate": annual_income_estimate,
                    "annual_estimate_min": annual_income_estimate_min,
                    "annual_estimate_max": annual_income_estimate_max,
                    "income_type": income_engine.get("income_type"),
                    "confidence": income_engine.get("confidence"),
                },
                "expenses": {
                    "total": round(aggregate["total_expenses"], 3),
                    "emi": round(aggregate["emi_total"], 3),
                    "penalties": round(aggregate["penalties_total"], 3),
                },
                "cash_flow": {
                    "withdrawals": round(aggregate["cash_withdrawals"], 3),
                    "deposits": round(aggregate["cash_deposits"], 3),
                },
                "balance": {
                    "average": statement_summary["avg_balance"],
                    "median": statement_summary["median_balance"],
                    "min": statement_summary["min_balance"],
                    "max": statement_summary["max_balance"],
                    "opening": statement_summary["opening_balance"],
                    "closing": statement_summary["closing_balance"],
                    "volatility": statement_summary["balance_volatility"],
                },
                "dti": {
                    "value": dti["value"],
                    "label": dti["label"],
                    "reliability": dti.get("reliability", "verified" if dti.get("value") is not None else "unavailable"),
                },
                "cash_behavior": {
                    "stress_score": cash_behavior["stressScore"],
                    "flags": cash_behavior["flags"],
                },
                "income_engine": income_engine,
                "cash_flow_intelligence": cashflow_intelligence,
                "spending_intelligence": spending_intelligence,
            },
            "risk_findings": {
                "alerts": build_risk_alerts_from_flags(risk_scoring["riskFlags"]),
                "flags": risk_scoring["riskFlags"],
                "risk_score": canonical_risk_score,
                "behavioral_flags": behavioral_flags,
                "explainable_risk": explainable_risk,
            },
            "reasoning": {
                "summary": build_summary_from_decision(decision_payload),
                "narrative": reasoning_lines,
                "required_followups": decision_payload["required_followups"],
                "analysis_limitations": decision_payload["analysis_limitations"],
            },
            "transactions": _serialize_transactions(corrected),
        }
    if any(value not in (None, "", []) for value in (evidence_profile.get("account_profile") or {}).values()):
        payload["account_profile"] = evidence_profile.get("account_profile")

    return canonicalize_analysis_payload(
        payload,
        fallback_verdict=decision_payload.get("decision_status") or decision_engine.get("decision"),
        fallback_risk_confidence=decision_engine.get("risk_confidence", statement_confidence),
        fallback_reasons=reasoning_lines,
        fallback_extraction_confidence=statement_confidence,
        fallback_data_completeness=(
            min(normalize_confidence(statement_confidence), SHORT_HISTORY_RISK_CONFIDENCE_CAP)
            if short_history_gate_active
            else statement_confidence
        ),
        fallback_decision_reason=decision_payload.get("decision_reason"),
        fallback_required_followups=(
            SHORT_HISTORY_REQUIRED_FOLLOWUPS if short_history_gate_active else []
        ),
        fallback_analysis_limitations=(
            _build_short_history_limitations(uncertainty_notes, coverage_days)
            if short_history_gate_active
            else uncertainty_notes
        ),
    )
