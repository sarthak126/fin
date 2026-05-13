"""
Insight Engine — Post-processes Gemini output into validated, normalized analysis results.

Pipeline step: Upload → Extraction → Chunking → Vectors → Gemini → [THIS] → DB

This is the "product layer" — rule-based risk scoring, validation, and normalization.
"""

from dataclasses import dataclass
import math

from core.confidence import (
    build_decision_payload,
    build_decision_reason_template,
    build_summary_from_decision,
    canonicalize_analysis_payload,
    extract_canonical_decision,
    extract_decision_risk_confidence,
    normalize_confidence,
    recommendation_from_decision_status,
)


@dataclass
class RiskAlert:
    severity: str  # "high", "medium", "low"
    message: str
    field: str
    details: str


@dataclass
class InsightResult:
    risk_score: float
    confidence: float
    recommendation: str  # "approve", "review", "reject"
    extracted_fields: dict
    risk_alerts: list[dict]
    summary: str
    model_used: str
    raw_response: dict
    analysis_limitations: list[str] | None = None


# ────────────────────────────────────────
# Rule-Based Risk Scoring
# ────────────────────────────────────────

def _calculate_rule_based_risk(fields: dict) -> tuple[float, list[RiskAlert]]:
    """
    Apply domain-specific rules on top of the Gemini-generated risk score.
    Returns (risk_score_adjustment, additional_alerts).
    """
    risk_adjustment = 0.0
    alerts: list[RiskAlert] = []

    # Rule 1: Interest rate > 12%
    interest_rate = fields.get("interest_rate")
    if interest_rate and isinstance(interest_rate, (int, float)):
        if interest_rate > 18:
            risk_adjustment += 25
            alerts.append(RiskAlert(
                severity="high",
                message="Very high interest rate detected",
                field="interest_rate",
                details=f"Interest rate of {interest_rate}% significantly exceeds standard market rates (8-12%). This may indicate a predatory lending product.",
            ))
        elif interest_rate > 12:
            risk_adjustment += 15
            alerts.append(RiskAlert(
                severity="medium",
                message="Above-average interest rate",
                field="interest_rate",
                details=f"Interest rate of {interest_rate}% is above the typical range of 8-12%.",
            ))

    # Rule 2: DTI ratio > 35%
    dti = fields.get("debt_to_income_ratio")
    if dti and isinstance(dti, (int, float)):
        if dti > 50:
            risk_adjustment += 20
            alerts.append(RiskAlert(
                severity="high",
                message="Dangerously high debt-to-income ratio",
                field="debt_to_income_ratio",
                details=f"DTI ratio of {dti}% is critically above the safe threshold of 35%. Borrower may struggle with repayments.",
            ))
        elif dti > 35:
            risk_adjustment += 12
            alerts.append(RiskAlert(
                severity="medium",
                message="Debt-to-income ratio above threshold",
                field="debt_to_income_ratio",
                details=f"DTI ratio of {dti}% exceeds the recommended maximum of 35%.",
            ))

    # Rule 3: Penalty clauses
    penalties = fields.get("penalty_clauses", [])
    if isinstance(penalties, list):
        for penalty in penalties:
            if isinstance(penalty, dict):
                amount = penalty.get("amount")
                if amount and isinstance(amount, (int, float)) and amount > 500:
                    risk_adjustment += 10
                    alerts.append(RiskAlert(
                        severity="medium",
                        message=f"High penalty: {penalty.get('type', 'Unknown')}",
                        field="penalty_clauses",
                        details=penalty.get("description", f"Penalty of ₹{amount} detected."),
                    ))

    # Rule 4: Prepayment penalty exists
    prepayment_penalties = [
        p for p in (penalties if isinstance(penalties, list) else [])
        if isinstance(p, dict) and "prepay" in str(p.get("type", "")).lower()
    ]
    if prepayment_penalties:
        risk_adjustment += 8
        alerts.append(RiskAlert(
            severity="medium",
            message="Prepayment penalty detected",
            field="penalty_clauses",
            details="The loan includes a prepayment penalty, limiting the borrower's ability to close the loan early.",
        ))

    # Rule 5: Hidden charges
    hidden_charges = fields.get("hidden_charges", [])
    if isinstance(hidden_charges, list) and len(hidden_charges) >= 3:
        risk_adjustment += 15
        alerts.append(RiskAlert(
            severity="high",
            message=f"{len(hidden_charges)} hidden charges identified",
            field="hidden_charges",
            details="Multiple hidden charges detected. This may indicate unfavorable loan terms.",
        ))
    elif isinstance(hidden_charges, list) and len(hidden_charges) >= 1:
        risk_adjustment += 5
        alerts.append(RiskAlert(
            severity="low",
            message=f"{len(hidden_charges)} additional charge(s) found",
            field="hidden_charges",
            details="Additional charges found in the document. Review for transparency.",
        ))

    # Rule 6: Short employment tenure
    tenure = fields.get("employment_tenure_years")
    if tenure and isinstance(tenure, (int, float)) and tenure < 1:
        risk_adjustment += 10
        alerts.append(RiskAlert(
            severity="medium",
            message="Short employment tenure",
            field="employment_tenure_years",
            details=f"Employment tenure of {tenure} year(s) is below the recommended minimum of 1 year for stable loan assessment.",
        ))

    # Rule 7: Low monthly balance vs income
    avg_balance = fields.get("avg_monthly_balance")
    monthly_income = fields.get("monthly_income")
    if (avg_balance and monthly_income 
        and isinstance(avg_balance, (int, float)) 
        and isinstance(monthly_income, (int, float))
        and monthly_income > 0):
        balance_ratio = avg_balance / monthly_income
        if balance_ratio < 0.5:
            risk_adjustment += 8
            alerts.append(RiskAlert(
                severity="medium",
                message="Low savings relative to income",
                field="avg_monthly_balance",
                details=f"Average balance (₹{avg_balance:,.0f}) is less than 50% of monthly income (₹{monthly_income:,.0f}), suggesting thin financial cushion.",
            ))

    return risk_adjustment, alerts


# ────────────────────────────────────────
# Main Processing
# ────────────────────────────────────────

def _clamp(value: float, min_v: float, max_v: float) -> float:
    return max(min_v, min(max_v, value))


def _safe_float(value, default: float = 0.0) -> float:
    numeric = _maybe_float(value)
    return default if numeric is None else numeric


def _maybe_float(value) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _sanitize_payload_value(value):
    if isinstance(value, dict):
        return {key: _sanitize_payload_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_payload_value(item) for item in value]
    if isinstance(value, (int, float)) and not math.isfinite(float(value)):
        return None
    return value


def _dti_label(value) -> str | None:
    numeric = _maybe_float(value)
    if numeric is None or numeric <= 0:
        return None
    if numeric < 0.2:
        return "low"
    if numeric < 0.35:
        return "moderate"
    if numeric < 0.5:
        return "high"
    return "extreme"


def _top_alert_message(alerts: list[dict]) -> str | None:
    if not alerts:
        return None
    first_alert = alerts[0]
    if not isinstance(first_alert, dict):
        return None
    message = str(first_alert.get("message") or "").strip()
    return message or None


def _build_reason_context(fields: dict, alerts: list[dict], final_risk: float, data_completeness: float) -> dict:
    employment_type = str(fields.get("employment_type") or "").strip().lower()
    return {
        "coverage_days": fields.get("coverage_days"),
        "monthly_income": fields.get("monthly_income"),
        "annual_income": fields.get("annual_income"),
        "employment_type": fields.get("employment_type"),
        "stable_income_detected": bool(
            fields.get("monthly_income") is not None and employment_type in {"salaried", "salary"}
        ),
        "avg_monthly_balance": fields.get("avg_monthly_balance"),
        "min_balance_6m": fields.get("min_balance_6m"),
        "existing_emis": fields.get("existing_emis"),
        "debt_to_income_ratio": fields.get("debt_to_income_ratio"),
        "dti_value": fields.get("debt_to_income_ratio"),
        "dti_label": _dti_label(fields.get("debt_to_income_ratio")),
        "risk_score": final_risk,
        "risk_level": (
            "very_high"
            if final_risk >= 70
            else "high"
            if final_risk >= 55
            else "medium"
            if final_risk >= 35
            else "low"
        ),
        "data_completeness": data_completeness,
        "document_type_detected": fields.get("document_type_detected"),
        "primary_risk_driver": _top_alert_message(alerts),
    }


def _build_generic_followups(fields: dict, recommendation: str) -> list[str]:
    followups: list[str] = []
    if fields.get("monthly_income") is None and fields.get("annual_income") is None:
        followups.append("Provide verified income proof before final approval.")
    if fields.get("existing_emis") is None and fields.get("debt_to_income_ratio") is None:
        followups.append("Verify existing debt obligations and the borrower's DTI.")
    if fields.get("avg_monthly_balance") is None and fields.get("min_balance_6m") is None:
        followups.append("Review recent bank balances to confirm liquidity stability.")
    if fields.get("employment_type") is None or fields.get("employment_tenure_years") is None:
        followups.append("Confirm employment type and tenure with supporting documents.")
    if recommendation == "reject":
        return []
    return followups[:4]


def _build_generic_limitations(fields: dict, data_completeness: float) -> list[str]:
    limitations: list[str] = []
    if data_completeness < 0.35:
        limitations.append("Limited reliable history was extracted from the document.")
    if fields.get("monthly_income") is None and fields.get("annual_income") is None:
        limitations.append("Income data could not be fully verified from the extracted fields.")
    if fields.get("existing_emis") is None and fields.get("debt_to_income_ratio") is None:
        limitations.append("Debt obligation coverage is incomplete in the extracted data.")
    return limitations[:4]


def process_analysis(raw_gemini_output: dict, model_used: str = "") -> InsightResult:
    """
    Main insight engine entry point.
    
    1. Validate and normalize Gemini's raw JSON output
    2. Apply rule-based risk scoring adjustments
    3. Merge Gemini alerts with rule-based alerts
    4. Determine final recommendation
    5. Return a clean InsightResult
    """

    # ── Extract key fields ──
    sanitized_raw_output = _sanitize_payload_value(dict(raw_gemini_output or {}))
    gemini_risk = _safe_float(sanitized_raw_output.get("risk_score"), 50.0)
    gemini_alerts = sanitized_raw_output.get("risk_alerts", [])
    if not isinstance(gemini_alerts, list):
        gemini_alerts = []

    # Normalize extracted fields (the financial data)
    extracted_fields = {}
    field_keys = [
        "applicant_name",
        "interest_rate", "processing_fee", "loan_amount", "tenure_months",
        "monthly_income", "annual_income", "monthly_expenses",
        "debt_to_income_ratio", "employment_type", "employment_tenure_years",
        "employer_name", "avg_monthly_balance", "min_balance_6m",
        "existing_emis", "credit_utilization_pct",
        "penalty_clauses", "hidden_charges",
        "document_type_detected", "confidence_notes",
    ]
    for key in field_keys:
        val = sanitized_raw_output.get(key)
        if val is not None:
            extracted_fields[key] = val
    if sanitized_raw_output.get("coverage_days") is not None:
        extracted_fields["coverage_days"] = sanitized_raw_output.get("coverage_days")

    # ── Apply rule-based adjustments ──
    risk_adjustment, rule_alerts = _calculate_rule_based_risk(extracted_fields)

    # Add deterministic rule adjustments on top of the provider baseline.
    final_risk = gemini_risk + risk_adjustment
    final_risk = _clamp(final_risk, 0, 100)

    # ── Merge alerts ──
    all_alerts = []

    # Gemini alerts first
    for alert in gemini_alerts:
        if isinstance(alert, dict):
            all_alerts.append({
                "severity": alert.get("severity", "medium"),
                "message": alert.get("message", "Alert detected"),
                "field": alert.get("field", "general"),
                "details": alert.get("details", ""),
            })

    # Rule-based alerts
    for alert in rule_alerts:
        # Check for duplicate messages
        existing_messages = {a["message"].lower() for a in all_alerts}
        if alert.message.lower() not in existing_messages:
            all_alerts.append({
                "severity": alert.severity,
                "message": alert.message,
                "field": alert.field,
                "details": alert.details,
            })

    # Sort by severity: high > medium > low
    severity_order = {"high": 0, "medium": 1, "low": 2}
    all_alerts.sort(key=lambda a: severity_order.get(a.get("severity", "low"), 3))

    # ── Determine recommendation ──
    if final_risk < 40:
        recommendation = "approve"
    elif final_risk <= 70:
        recommendation = "manual_review"
    else:
        recommendation = "reject"

    # ── Confidence score ──
    # Based on how many fields were actually extracted
    total_possible = len(field_keys)
    extracted_count = sum(1 for k in field_keys if extracted_fields.get(k) is not None)
    data_completeness = _clamp(extracted_count / total_possible if total_possible else 0.0, 0.0, 1.0)
    extraction_confidence = data_completeness
    risk_confidence = normalize_confidence(data_completeness)

    # ── Summary ──
    summary = sanitized_raw_output.get("summary", "")
    if not summary:
        summary = f"Document analyzed with risk score {final_risk:.0f}/100. Recommendation: {recommendation}."

    decision_reasons: list[str] = []
    risk_reasoning = sanitized_raw_output.get("risk_reasoning")
    if isinstance(risk_reasoning, str) and risk_reasoning.strip():
        decision_reasons.append(risk_reasoning.strip())
    required_followups = _build_generic_followups(extracted_fields, recommendation)
    analysis_limitations = _build_generic_limitations(extracted_fields, data_completeness)
    reason_context = _build_reason_context(extracted_fields, all_alerts, final_risk, data_completeness)
    canonical_decision_reason = build_decision_reason_template(
        recommendation,
        reason_context=reason_context,
        required_followups=required_followups,
        analysis_limitations=analysis_limitations,
        fallback_reason=decision_reasons[0] if decision_reasons else summary,
    )

    extracted_fields["decision"] = build_decision_payload(
        decision_status=recommendation,
        decision_reason=canonical_decision_reason,
        extraction_confidence=extraction_confidence,
        risk_confidence=risk_confidence,
        data_completeness=data_completeness,
        required_followups=required_followups,
        analysis_limitations=analysis_limitations,
        reasons=decision_reasons,
        reason_context=reason_context,
    )
    extracted_fields = canonicalize_analysis_payload(
        extracted_fields,
        fallback_verdict=recommendation,
        fallback_risk_confidence=risk_confidence,
        fallback_reasons=decision_reasons,
        fallback_extraction_confidence=extraction_confidence,
        fallback_data_completeness=data_completeness,
        fallback_required_followups=required_followups,
        fallback_analysis_limitations=analysis_limitations,
    )
    raw_response = canonicalize_analysis_payload(
        sanitized_raw_output,
        fallback_verdict=recommendation,
        fallback_risk_confidence=risk_confidence,
        fallback_reasons=decision_reasons,
        fallback_extraction_confidence=extraction_confidence,
        fallback_data_completeness=data_completeness,
        fallback_decision_reason=canonical_decision_reason,
        fallback_required_followups=required_followups,
        fallback_analysis_limitations=analysis_limitations,
    )
    decision = extract_canonical_decision(
        extracted_fields,
        fallback_status=recommendation,
        fallback_reason=canonical_decision_reason,
        fallback_extraction_confidence=extraction_confidence,
        fallback_risk_confidence=risk_confidence,
        fallback_data_completeness=data_completeness,
        fallback_required_followups=required_followups,
        fallback_analysis_limitations=analysis_limitations,
        fallback_reasons=decision_reasons,
    )
    extracted_fields["decision"] = dict(decision)
    raw_response["decision"] = dict(decision)
    summary = build_summary_from_decision(decision, summary)
    confidence = extract_decision_risk_confidence(extracted_fields, fallback=risk_confidence)
    recommendation = recommendation_from_decision_status(decision["decision_status"])

    return InsightResult(
        risk_score=round(final_risk, 1),
        confidence=round(confidence, 4),
        recommendation=recommendation,
        extracted_fields=extracted_fields,
        risk_alerts=all_alerts,
        summary=summary,
        model_used=model_used,
        raw_response=raw_response,
        analysis_limitations=decision["analysis_limitations"],
    )
