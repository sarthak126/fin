"""
Shared helpers for canonical normalized confidence values and decision payloads.
"""

from __future__ import annotations

import math
import re
from typing import Any

from core.bank_statement_score import canonicalize_bank_statement_score_payload

CONFIDENCE_LABEL_MAP: dict[str, float] = {
    "high": 1.0,
    "medium": 0.6,
    "low": 0.3,
}

BANK_STATEMENT_REQUIRED_SECTIONS = {
    "decision",
    "statement_summary",
    "transaction_insights",
    "risk_findings",
    "reasoning",
    "transactions",
}

DECISION_STATUS_VALUES = {
    "approve",
    "manual_review",
    "reject",
    "insufficient_history",
}

DECISION_STATUS_PRIORITY = {
    "approve": 0,
    "manual_review": 1,
    "reject": 2,
    "insufficient_history": 3,
}

_DEFAULT_DECISION_RECOMMENDATIONS = {
    "approve": "Proceed with approval.",
    "manual_review": "Manual review is recommended before approval.",
    "reject": "Do not approve this application.",
    "insufficient_history": "Collect more document history before making a final decision.",
}

_DEFAULT_DECISION_REASONS = {
    "approve": "The available signals support approval.",
    "manual_review": "The application needs manual review before a final decision.",
    "reject": "The available signals do not support approval.",
    "insufficient_history": "There is not enough reliable history to make a final decision.",
}

_DEFAULT_REQUIRED_FOLLOWUPS = {
    "approve": [],
    "manual_review": ["Review the flagged risk factors before final approval."],
    "reject": [],
    "insufficient_history": ["Collect additional document history or supporting evidence."],
}

_DEFAULT_ANALYSIS_LIMITATIONS = {
    "approve": [],
    "manual_review": [],
    "reject": [],
    "insufficient_history": ["Insufficient reliable history was available for a final decision."],
}

_INSUFFICIENT_HISTORY_PATTERNS = (
    "insufficient history",
    "not enough history",
    "insufficient data",
    "not enough data",
    "more history",
    "additional history",
    "missing history",
    "limited history",
)

_REASON_TEMPLATE_MIN_HISTORY_DAYS = 90
_REASON_TEMPLATE_LOW_BALANCE_THRESHOLD = 1000.0
_REASON_TEMPLATE_HEALTHY_BALANCE_THRESHOLD = 5000.0


def _clamp_unit_interval(value: float) -> float:
    return max(0.0, min(1.0, value))


def normalize_confidence(value: Any, default: float = 0.0) -> float:
    """
    Coerce legacy percentage-style, label-style, or out-of-range confidence
    values onto the canonical 0.0-1.0 scale.
    """

    fallback = _clamp_unit_interval(float(default)) if isinstance(default, (int, float)) else 0.0

    if value is None:
        return fallback

    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized:
            return fallback
        if normalized in CONFIDENCE_LABEL_MAP:
            return CONFIDENCE_LABEL_MAP[normalized]
        is_percent = normalized.endswith("%")
        if is_percent:
            normalized = normalized[:-1].strip()
        try:
            value = float(normalized)
        except ValueError:
            return fallback
        if is_percent:
            return _clamp_unit_interval(value / 100.0)

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback

    if math.isnan(numeric) or math.isinf(numeric):
        return fallback
    if numeric < 0:
        return 0.0
    if numeric <= 1.0:
        return _clamp_unit_interval(numeric)
    if numeric <= 100.0:
        return _clamp_unit_interval(numeric / 100.0)
    return 1.0


def build_risk_alerts_from_flags(flags: Any) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    for flag in _normalize_string_list(flags):
        lowered = flag.lower()
        if any(
            keyword in lowered
            for keyword in [
                "negative",
                "extreme",
                "high cash",
                "high dti",
                "extreme dti",
                "weak end-of-statement",
                "weak end-of-month",
                "repeated",
            ]
        ):
            severity = "high"
        elif any(
            keyword in lowered
            for keyword in ["moderate", "low balance", "irregular", "suspicious", "duplicate"]
        ):
            severity = "medium"
        else:
            severity = "low"
        alerts.append({"message": flag, "severity": severity})
    return alerts


def normalize_confidence_payload(payload: Any) -> Any:
    """
    Recursively clamp all confidence-shaped fields in dict/list payloads.
    """

    if isinstance(payload, dict):
        normalized: dict[str, Any] = {}
        for key, value in payload.items():
            if key in {"confidence", "risk_confidence", "extraction_confidence", "data_completeness"}:
                normalized[key] = normalize_confidence(value)
            else:
                normalized[key] = normalize_confidence_payload(value)
        return normalized

    if isinstance(payload, list):
        return [normalize_confidence_payload(item) for item in payload]

    return payload


def _collapse_whitespace(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _sentence_from_text(value: Any) -> str:
    text = _collapse_whitespace(value)
    if not text:
        return ""

    text = re.sub(r"^(decision|reason|summary)\s*:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^[>\-\u2022]+\s*", "", text)
    text = re.sub(r"^->\s*", "", text)

    sentences = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
    text = sentences[0].strip()
    if text and text[-1] not in ".!?":
        text += "."
    return text


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []

    raw_items = value if isinstance(value, list) else [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = _collapse_whitespace(item)
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _humanize_label(value: Any) -> str:
    text = _collapse_whitespace(value).replace("_", " ")
    if not text:
        return ""
    return " ".join(part.capitalize() for part in text.split())


def normalize_decision_status(value: Any, fallback: str = "manual_review") -> str:
    fallback_status = str(fallback or "manual_review").strip().lower().replace("-", "_")
    if fallback_status not in DECISION_STATUS_VALUES:
        fallback_status = "manual_review"

    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return fallback_status
    if normalized in DECISION_STATUS_VALUES:
        return normalized
    if "insufficient" in normalized or ("history" in normalized and "approve" not in normalized):
        return "insufficient_history"
    if "reject" in normalized or "declin" in normalized:
        return "reject"
    if normalized == "review" or "manual" in normalized or "caution" in normalized:
        return "manual_review"
    if "approve" in normalized:
        return "approve"
    return fallback_status


def select_decision_status(candidates: list[Any] | tuple[Any, ...], fallback: str = "manual_review") -> str:
    normalized_candidates = [
        normalize_decision_status(candidate, fallback)
        for candidate in candidates
        if _collapse_whitespace(candidate)
    ]
    if not normalized_candidates:
        return normalize_decision_status(fallback, "manual_review")
    return max(
        normalized_candidates,
        key=lambda status: DECISION_STATUS_PRIORITY[status],
    )


def recommendation_from_decision_status(status: Any) -> str:
    normalized = normalize_decision_status(status)
    if normalized in {"manual_review", "insufficient_history"}:
        return "review"
    return normalized


def _default_decision_recommendation(status: str) -> str:
    return _DEFAULT_DECISION_RECOMMENDATIONS[status]


def _default_decision_reason(status: str) -> str:
    return _DEFAULT_DECISION_REASONS[status]


def _default_required_followups(status: str) -> list[str]:
    return list(_DEFAULT_REQUIRED_FOLLOWUPS[status])


def _default_analysis_limitations(status: str) -> list[str]:
    return list(_DEFAULT_ANALYSIS_LIMITATIONS[status])


def _context_lookup(context: dict[str, Any] | None, *path_options: Any) -> Any:
    if not isinstance(context, dict):
        return None

    for option in path_options:
        path = option if isinstance(option, tuple) else (option,)
        current: Any = context
        found = True
        for key in path:
            if not isinstance(current, dict) or key not in current:
                found = False
                break
            current = current.get(key)
        if not found:
            continue
        if current in (None, "", [], {}):
            continue
        return current

    return None


def _safe_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if not cleaned:
            return None
        if "-" in cleaned:
            return None
        value = cleaned
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _format_currency(value: Any) -> str:
    numeric = _safe_float_or_none(value)
    if numeric is None:
        return "unknown"
    if math.isclose(numeric, round(numeric), abs_tol=0.01):
        return f"Rs{numeric:,.0f}"
    return f"Rs{numeric:,.2f}"


def _format_followup_action(value: Any) -> str:
    text = _sentence_from_text(value).rstrip(".")
    return text or "Review the available evidence"


def _describe_history_signal(status: str, reason_context: dict[str, Any] | None) -> str:
    coverage_days = _safe_float_or_none(
        _context_lookup(reason_context, "coverage_days", ("statement_summary", "coverage_days"))
    )
    min_history_days = int(
        _safe_float_or_none(_context_lookup(reason_context, "min_history_days")) or _REASON_TEMPLATE_MIN_HISTORY_DAYS
    )

    if coverage_days is None or coverage_days <= 0:
        return "coverage_days=unknown"

    coverage_value = int(round(coverage_days))
    comparator = ">=" if coverage_value >= min_history_days else "<"
    if status == "approve":
        comparator = ">="
    return f"coverage_days={coverage_value} ({comparator} {min_history_days} required)"


def _describe_stable_income_signal(reason_context: dict[str, Any] | None) -> str:
    explicit_signal = _context_lookup(reason_context, "stable_income_status")
    if explicit_signal:
        return _sentence_from_text(explicit_signal).rstrip(".")

    stable_income_detected = _context_lookup(
        reason_context,
        "stable_income_detected",
        "recurring_income_detected",
        ("income_engine", "recurring_income_detected"),
    )
    income_inference_skipped = bool(
        _context_lookup(
            reason_context,
            "income_inference_skipped",
            ("income_engine", "income_inference_skipped"),
        )
    )
    income_type = str(
        _context_lookup(reason_context, "income_type", ("income_engine", "income_type")) or ""
    ).strip().lower()
    monthly_income = _context_lookup(
        reason_context,
        "monthly_income",
        ("income", "monthly_estimate"),
        ("income_engine", "monthly_income_estimate"),
    )
    annual_income = _context_lookup(reason_context, "annual_income", ("income", "annual_estimate"))
    employment_type = str(_context_lookup(reason_context, "employment_type") or "").strip().lower()

    if stable_income_detected is True or income_type == "salary":
        return "stable income detected"
    if income_inference_skipped:
        return "no verifiable stable income detected"
    if employment_type in {"salaried", "salary"} and monthly_income not in (None, ""):
        return "stable income detected"
    if income_type == "mixed" or monthly_income not in (None, "") or annual_income not in (None, ""):
        return "income present but long-term stability is not fully verified"
    if income_type in {"unknown", "unstable"}:
        return "no verifiable stable income detected"
    return "stable income status is unclear"


def _describe_liquidity_signal(reason_context: dict[str, Any] | None) -> str:
    explicit_signal = _context_lookup(reason_context, "liquidity_signal")
    if explicit_signal:
        return _sentence_from_text(explicit_signal).rstrip(".")

    min_balance = _safe_float_or_none(
        _context_lookup(
            reason_context,
            "min_balance",
            "min_balance_6m",
            ("statement_summary", "min_balance"),
            ("balance", "min"),
        )
    )
    avg_balance = _safe_float_or_none(
        _context_lookup(
            reason_context,
            "avg_balance",
            "avg_monthly_balance",
            ("statement_summary", "avg_balance"),
            ("balance", "average"),
        )
    )
    low_balance_count = _safe_float_or_none(
        _context_lookup(
            reason_context,
            "low_balance_count",
            "low_balance_events",
            ("statement_summary", "low_balance_count"),
        )
    )
    total_credits = _safe_float_or_none(
        _context_lookup(reason_context, "total_credits", ("statement_summary", "total_credits"))
    )
    total_debits = _safe_float_or_none(
        _context_lookup(reason_context, "total_debits", ("statement_summary", "total_debits"))
    )
    net_flow = _safe_float_or_none(_context_lookup(reason_context, "net_flow", ("statement_summary", "net_flow")))

    details: list[str] = []
    label = "unknown"

    if min_balance is not None and min_balance < _REASON_TEMPLATE_LOW_BALANCE_THRESHOLD:
        label = "low"
        details.append(f"min_balance={_format_currency(min_balance)}")
    elif (low_balance_count or 0) > 0:
        label = "low"
        details.append(f"low_balance_events={int(low_balance_count or 0)}")
    elif avg_balance is not None and avg_balance < _REASON_TEMPLATE_HEALTHY_BALANCE_THRESHOLD:
        label = "pressured"
        details.append(f"avg_balance={_format_currency(avg_balance)}")
    elif min_balance is not None or avg_balance is not None:
        label = "healthy"
        if min_balance is not None:
            details.append(f"min_balance={_format_currency(min_balance)}")
        elif avg_balance is not None:
            details.append(f"avg_balance={_format_currency(avg_balance)}")

    if total_debits is not None and total_credits is not None:
        if total_debits > total_credits:
            if label in {"healthy", "unknown"}:
                label = "pressured" if label == "healthy" else "low"
            details.append(f"outflows={_format_currency(total_debits)} > inflows={_format_currency(total_credits)}")
        elif total_credits > 0:
            details.append("inflows cover outflows")
    elif net_flow is not None:
        if net_flow < 0:
            if label in {"healthy", "unknown"}:
                label = "pressured" if label == "healthy" else "low"
            details.append(f"net_flow={_format_currency(net_flow)}")
        elif net_flow > 0:
            details.append(f"net_flow={_format_currency(net_flow)}")

    if not details:
        return "unknown (limited liquidity data)"

    unique_details = list(dict.fromkeys(details))
    return f"{label} ({'; '.join(unique_details[:2])})"


def _describe_obligation_signal(reason_context: dict[str, Any] | None) -> str:
    explicit_signal = _context_lookup(reason_context, "obligation_signal")
    if explicit_signal:
        return _sentence_from_text(explicit_signal).rstrip(".")

    dti_label = str(_context_lookup(reason_context, "dti_label", ("dti", "label")) or "").strip().lower()
    dti_value = _safe_float_or_none(
        _context_lookup(reason_context, "dti_value", "debt_to_income_ratio", ("dti", "value"))
    )
    existing_emis = _safe_float_or_none(
        _context_lookup(reason_context, "existing_emis", "emi_total", ("expenses", "emi"))
    )
    burn_rate = str(
        _context_lookup(reason_context, "burn_rate", ("cash_flow_intelligence", "monthly_burn_rate")) or ""
    ).strip().lower()

    if dti_label in {"high", "extreme"} and dti_value is not None:
        return f"{dti_label} DTI ({dti_value:.1%})"
    if existing_emis is not None and existing_emis > 0:
        return f"existing EMI {_format_currency(existing_emis)}"
    if burn_rate == "critical":
        return "spending exceeds inflows"
    return _describe_liquidity_signal(reason_context)


def _describe_primary_risk_driver(reason_context: dict[str, Any] | None, fallback_reason: str | None) -> str:
    explicit_signal = _context_lookup(reason_context, "primary_risk_driver")
    if explicit_signal:
        return _sentence_from_text(explicit_signal).rstrip(".")

    coverage_days = _safe_float_or_none(
        _context_lookup(reason_context, "coverage_days", ("statement_summary", "coverage_days"))
    )
    min_history_days = int(
        _safe_float_or_none(_context_lookup(reason_context, "min_history_days")) or _REASON_TEMPLATE_MIN_HISTORY_DAYS
    )
    stable_income_signal = _describe_stable_income_signal(reason_context).lower()
    obligation_signal = _describe_obligation_signal(reason_context).lower()
    liquidity_signal = _describe_liquidity_signal(reason_context).lower()
    risk_level = str(_context_lookup(reason_context, "risk_level", ("explainable_risk", "risk_level")) or "").lower()

    if coverage_days is not None and coverage_days < min_history_days:
        return "history is too short for a supportable underwriting decision"
    if "no verifiable stable income" in stable_income_signal and (
        "dti" in obligation_signal or "emi" in obligation_signal
    ):
        return "repayment capacity is not supported by verified stable income"
    if "no verifiable stable income" in stable_income_signal:
        return "stable income is not verifiable"
    if "low (" in liquidity_signal or liquidity_signal.startswith("low "):
        return "liquidity stress"
    if liquidity_signal.startswith("pressured "):
        return "cash flow is under pressure"
    if risk_level in {"high", "very_high"}:
        return f"overall risk remains {risk_level}"

    fallback_text = _sentence_from_text(fallback_reason).rstrip(".")
    if fallback_text:
        return fallback_text
    return "material risk signals outweigh approval support"


def _describe_uncertainty_reason(
    reason_context: dict[str, Any] | None,
    analysis_limitations: list[str],
    fallback_reason: str | None,
) -> str:
    explicit_signal = _context_lookup(reason_context, "uncertainty_reason")
    if explicit_signal:
        return _sentence_from_text(explicit_signal).rstrip(".")

    coverage_days = _safe_float_or_none(
        _context_lookup(reason_context, "coverage_days", ("statement_summary", "coverage_days"))
    )
    min_history_days = int(
        _safe_float_or_none(_context_lookup(reason_context, "min_history_days")) or _REASON_TEMPLATE_MIN_HISTORY_DAYS
    )
    stable_income_signal = _describe_stable_income_signal(reason_context).lower()
    data_completeness = _safe_float_or_none(_context_lookup(reason_context, "data_completeness"))

    if coverage_days is not None and coverage_days < min_history_days:
        return "history coverage is below the minimum required for full underwriting"
    if "no verifiable stable income" in stable_income_signal:
        return "stable income could not be verified from the available evidence"
    if data_completeness is not None and data_completeness < 0.35:
        return "document evidence is incomplete"
    if analysis_limitations:
        limitation_text = _sentence_from_text(analysis_limitations[0]).rstrip(".")
        if limitation_text:
            return limitation_text

    fallback_text = _sentence_from_text(fallback_reason).rstrip(".")
    if fallback_text:
        return fallback_text
    return "additional verification is required"


def _describe_key_risk_signal(reason_context: dict[str, Any] | None) -> str:
    explicit_signal = _context_lookup(reason_context, "key_risk_signal")
    if explicit_signal:
        return _sentence_from_text(explicit_signal).rstrip(".")

    obligation_signal = _describe_obligation_signal(reason_context)
    stable_income_signal = _describe_stable_income_signal(reason_context).lower()
    liquidity_signal = _describe_liquidity_signal(reason_context)
    risk_score = _safe_float_or_none(_context_lookup(reason_context, "risk_score"))

    if "dti" in obligation_signal.lower() or "emi" in obligation_signal.lower():
        if "no verifiable stable income" in stable_income_signal:
            return f"{obligation_signal} without verified stable income"
        return obligation_signal
    if liquidity_signal != "unknown (limited liquidity data)":
        return liquidity_signal
    if risk_score is not None:
        return f"risk_score={int(round(risk_score))}/100"
    return "unresolved risk indicators remain"


def _describe_stability_signal(reason_context: dict[str, Any] | None) -> str:
    explicit_signal = _context_lookup(reason_context, "stability_signal")
    if explicit_signal:
        return _sentence_from_text(explicit_signal).rstrip(".")

    stable_income_signal = _describe_stable_income_signal(reason_context).lower()
    liquidity_signal = _describe_liquidity_signal(reason_context)
    dti_label = str(_context_lookup(reason_context, "dti_label", ("dti", "label")) or "").strip().lower()
    parts: list[str] = []

    if "stable income detected" in stable_income_signal:
        parts.append("stable income detected")
    elif "income present" in stable_income_signal:
        parts.append("income is present and partially verified")

    if liquidity_signal.startswith("healthy"):
        parts.append("liquidity is healthy")
    elif liquidity_signal.startswith("pressured"):
        parts.append(f"liquidity is acceptable but {liquidity_signal}")

    if dti_label in {"low", "moderate"}:
        parts.append(f"{dti_label} obligation load")

    if parts:
        return " and ".join(parts[:3])
    return "the available financial signals remain stable"


def _describe_blockers_signal(reason_context: dict[str, Any] | None) -> str:
    explicit_signal = _context_lookup(reason_context, "blockers_signal")
    if explicit_signal:
        return _sentence_from_text(explicit_signal).rstrip(".")

    blockers: list[str] = []
    stable_income_signal = _describe_stable_income_signal(reason_context).lower()
    liquidity_signal = _describe_liquidity_signal(reason_context).lower()
    obligation_signal = _describe_obligation_signal(reason_context).lower()
    coverage_days = _safe_float_or_none(
        _context_lookup(reason_context, "coverage_days", ("statement_summary", "coverage_days"))
    )
    min_history_days = int(
        _safe_float_or_none(_context_lookup(reason_context, "min_history_days")) or _REASON_TEMPLATE_MIN_HISTORY_DAYS
    )

    if coverage_days is not None and coverage_days < min_history_days:
        blockers.append("history gap remains")
    if "no verifiable stable income" in stable_income_signal:
        blockers.append("stable income is not verified")
    if liquidity_signal.startswith("low") or liquidity_signal.startswith("pressured"):
        blockers.append("liquidity pressure remains")
    if "high dti" in obligation_signal or "extreme dti" in obligation_signal:
        blockers.append("obligation burden is elevated")

    if blockers:
        return "; ".join(blockers[:3])
    return "none identified"


def build_decision_reason_template(
    status: str,
    *,
    reason_context: dict[str, Any] | None = None,
    required_followups: list[str] | None = None,
    analysis_limitations: list[str] | None = None,
    fallback_reason: str | None = None,
) -> str:
    if not isinstance(reason_context, dict):
        return ""

    followups = _normalize_string_list(required_followups)
    limitations = _normalize_string_list(analysis_limitations)
    next_action = _format_followup_action(
        followups[0] if followups else (_default_required_followups(status) or [_default_decision_recommendation(status)])[0]
    )

    if status == "insufficient_history":
        return (
            f"Insufficient history: {_describe_history_signal(status, reason_context)}; "
            f"stable_income_status={_describe_stable_income_signal(reason_context)}; "
            f"liquidity_signal={_describe_liquidity_signal(reason_context)}; "
            f"next_action={next_action}."
        )

    if status == "reject":
        return (
            f"Reject: primary_risk_driver={_describe_primary_risk_driver(reason_context, fallback_reason)}; "
            f"supporting_signal={_describe_obligation_signal(reason_context)}; "
            f"next_action={next_action}."
        )

    if status == "manual_review":
        return (
            f"Manual review: uncertainty_reason={_describe_uncertainty_reason(reason_context, limitations, fallback_reason)}; "
            f"key_risk_signal={_describe_key_risk_signal(reason_context)}; "
            f"follow_up={next_action}."
        )

    if status == "approve":
        return (
            f"Approve: sufficient_history={_describe_history_signal(status, reason_context)}; "
            f"stability_signal={_describe_stability_signal(reason_context)}; "
            f"blockers={_describe_blockers_signal(reason_context)}."
        )

    return ""


def _has_insufficient_history_signal(values: list[str]) -> bool:
    lowered_values = [value.lower() for value in values]
    return any(pattern in value for value in lowered_values for pattern in _INSUFFICIENT_HISTORY_PATTERNS)


def build_decision_payload(
    *,
    verdict: str | None = None,
    decision_status: str | None = None,
    decision_recommendation: str | None = None,
    decision_reason: str | None = None,
    extraction_confidence: Any = 0.0,
    risk_confidence: Any = 0.0,
    data_completeness: Any | None = None,
    required_followups: list[str] | None = None,
    analysis_limitations: list[str] | None = None,
    reasons: list[str] | None = None,
    decision_candidates: list[Any] | tuple[Any, ...] | None = None,
    reason_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_status = decision_status or verdict
    normalized_reasons = _normalize_string_list(reasons)

    normalized_extraction_confidence = normalize_confidence(
        extraction_confidence,
        data_completeness if data_completeness is not None else risk_confidence,
    )
    normalized_risk_confidence = normalize_confidence(risk_confidence, normalized_extraction_confidence)
    normalized_data_completeness = normalize_confidence(
        data_completeness if data_completeness is not None else normalized_extraction_confidence,
        normalized_extraction_confidence,
    )

    followups = _normalize_string_list(required_followups)
    limitations = _normalize_string_list(analysis_limitations)

    status_candidates: list[Any] = []
    if decision_candidates:
        status_candidates.extend(decision_candidates)
    if raw_status:
        status_candidates.append(raw_status)

    insufficient_history_signal = _has_insufficient_history_signal(
        [
            _collapse_whitespace(decision_reason),
            *normalized_reasons,
            *followups,
            *limitations,
        ]
    )
    if insufficient_history_signal:
        status_candidates.append("insufficient_history")
    elif (
        _context_lookup(reason_context, "coverage_days", ("statement_summary", "coverage_days")) is not None
        and reason_context is not None
        and
        min(normalized_extraction_confidence, normalized_data_completeness) < 0.35
        and select_decision_status(status_candidates or ["manual_review"], fallback="manual_review")
        in {"approve", "manual_review"}
    ):
        status_candidates.append("insufficient_history")

    status = select_decision_status(status_candidates or [raw_status or "manual_review"], fallback="manual_review")

    recommendation_text = _collapse_whitespace(decision_recommendation)
    if not recommendation_text and raw_status:
        raw_text = _collapse_whitespace(raw_status)
        raw_token = raw_text.lower().replace("-", "_").replace(" ", "_")
        if raw_token not in DECISION_STATUS_VALUES | {"review"}:
            recommendation_text = _humanize_label(raw_text)
    if not recommendation_text:
        recommendation_text = _default_decision_recommendation(status)

    if not followups:
        followups = _normalize_string_list(normalized_reasons[1:])
    if not followups:
        followups = _default_required_followups(status)

    if not limitations:
        limitations = _default_analysis_limitations(status)

    reason_text = build_decision_reason_template(
        status,
        reason_context=reason_context,
        required_followups=followups,
        analysis_limitations=limitations,
        fallback_reason=decision_reason or (normalized_reasons[0] if normalized_reasons else None),
    )
    if not reason_text:
        reason_text = _sentence_from_text(decision_reason)
    if not reason_text and normalized_reasons:
        reason_text = _sentence_from_text(normalized_reasons[0])
    if not reason_text:
        reason_text = _default_decision_reason(status)

    return {
        "decision_status": status,
        "decision_recommendation": recommendation_text,
        "decision_reason": reason_text,
        "extraction_confidence": normalized_extraction_confidence,
        "risk_confidence": normalized_risk_confidence,
        "data_completeness": normalized_data_completeness,
        "required_followups": followups,
        "analysis_limitations": limitations,
    }


def extract_decision_risk_confidence(payload: Any, fallback: Any = 0.0) -> float:
    if isinstance(payload, dict):
        decision = payload.get("decision")
        if isinstance(decision, dict):
            return normalize_confidence(decision.get("risk_confidence"), fallback)

        decision_engine = payload.get("decisionEngine")
        if isinstance(decision_engine, dict):
            if "risk_confidence" in decision_engine:
                return normalize_confidence(decision_engine.get("risk_confidence"), fallback)
            if "confidence" in decision_engine:
                return normalize_confidence(decision_engine.get("confidence"), fallback)

        statement_meta = payload.get("statementMeta")
        if isinstance(statement_meta, dict) and "confidence" in statement_meta:
            return normalize_confidence(statement_meta.get("confidence"), fallback)

        if "risk_confidence" in payload:
            return normalize_confidence(payload.get("risk_confidence"), fallback)
        if "confidence" in payload:
            return normalize_confidence(payload.get("confidence"), fallback)

    return normalize_confidence(fallback)


def build_summary_from_decision(decision: dict[str, Any], existing_summary: Any = None) -> str:
    lead = _sentence_from_text(decision.get("decision_reason"))
    summary = str(existing_summary or "").strip()
    if not lead:
        return summary
    if not summary:
        return lead

    lines = [line.strip() for line in str(summary).splitlines() if line.strip()]
    if not lines:
        return lead
    if _sentence_from_text(lines[0]).lower() == lead.lower():
        return "\n".join(lines)
    return "\n".join([lead, *lines])


def _is_dedicated_bank_statement_payload(payload: Any) -> bool:
    return isinstance(payload, dict) and BANK_STATEMENT_REQUIRED_SECTIONS.issubset(payload.keys())


def _canonicalize_dedicated_bank_statement_payload(
    normalized: dict[str, Any],
    *,
    fallback_verdict: str | None,
    fallback_risk_confidence: Any,
    fallback_reasons: list[str] | None,
    fallback_extraction_confidence: Any | None,
    fallback_data_completeness: Any | None,
    fallback_decision_recommendation: str | None,
    fallback_decision_reason: str | None,
    fallback_required_followups: list[str] | None,
    fallback_analysis_limitations: list[str] | None,
) -> dict[str, Any]:
    transaction_insights = dict(normalized.get("transaction_insights") or {})
    risk_findings = dict(normalized.get("risk_findings") or {})
    reasoning_payload = dict(normalized.get("reasoning") or {})
    raw_decision = normalized.get("decision")

    status_candidates: list[Any] = [fallback_verdict]
    raw_recommendation = fallback_decision_recommendation
    raw_reason = reasoning_payload.get("summary") or fallback_decision_reason
    risk_confidence = None
    extraction_confidence = None
    data_completeness = None
    required_followups = reasoning_payload.get("required_followups", fallback_required_followups)
    analysis_limitations = reasoning_payload.get("analysis_limitations", fallback_analysis_limitations)
    reason_candidates = _normalize_string_list(reasoning_payload.get("narrative")) or _normalize_string_list(
        fallback_reasons
    )

    if isinstance(raw_decision, dict):
        status_candidates.extend(
            [
                raw_decision.get("decision_status"),
                raw_decision.get("verdict"),
                raw_decision.get("decision"),
            ]
        )
        raw_recommendation = raw_decision.get("decision_recommendation") or raw_recommendation
        raw_reason = raw_decision.get("decision_reason") or raw_reason
        risk_confidence = raw_decision.get("risk_confidence")
        extraction_confidence = raw_decision.get("extraction_confidence")
        data_completeness = raw_decision.get("data_completeness")
        required_followups = raw_decision.get("required_followups", required_followups)
        analysis_limitations = raw_decision.get("analysis_limitations", analysis_limitations)
    elif raw_decision is not None:
        status_candidates.append(raw_decision)

    statement_confidence = transaction_insights.get("statement_confidence")
    if risk_confidence is None:
        risk_confidence = statement_confidence if statement_confidence is not None else fallback_risk_confidence
    if extraction_confidence is None:
        extraction_confidence = (
            statement_confidence if statement_confidence is not None else fallback_extraction_confidence
        )

    if data_completeness is None and isinstance(transaction_insights.get("income_engine"), dict):
        data_completeness = transaction_insights["income_engine"].get("confidence")
    if data_completeness is None:
        data_completeness = (
            statement_confidence if statement_confidence is not None else fallback_data_completeness
        )

    if not raw_reason and reason_candidates:
        raw_reason = reason_candidates[0]

    decision = build_decision_payload(
        verdict=str(fallback_verdict or "").strip() or None,
        decision_recommendation=raw_recommendation,
        decision_reason=raw_reason,
        extraction_confidence=extraction_confidence,
        risk_confidence=risk_confidence,
        data_completeness=data_completeness,
        required_followups=required_followups,
        analysis_limitations=analysis_limitations,
        reasons=reason_candidates,
        decision_candidates=status_candidates,
    )

    transaction_insights["statement_confidence"] = normalize_confidence(
        transaction_insights.get("statement_confidence"),
        extraction_confidence if extraction_confidence is not None else risk_confidence,
    )
    if isinstance(transaction_insights.get("income"), dict):
        income_summary = dict(transaction_insights["income"])
        if income_summary.get("confidence") is not None:
            income_summary["confidence"] = normalize_confidence(
                income_summary.get("confidence"),
                data_completeness if data_completeness is not None else risk_confidence,
            )
        transaction_insights["income"] = income_summary
    if isinstance(transaction_insights.get("dti"), dict):
        dti_summary = dict(transaction_insights["dti"])
        if not dti_summary.get("reliability"):
            dti_summary["reliability"] = (
                "unavailable"
                if dti_summary.get("value") is None
                else "verified"
            )
        transaction_insights["dti"] = dti_summary

    risk_findings["flags"] = _normalize_string_list(risk_findings.get("flags"))
    alerts = risk_findings.get("alerts")
    if not isinstance(alerts, list) or not alerts:
        alerts = build_risk_alerts_from_flags(risk_findings.get("flags"))
    risk_findings["alerts"] = alerts
    risk_findings["risk_score"] = canonicalize_bank_statement_score_payload(
        risk_findings.get("risk_score") if isinstance(risk_findings.get("risk_score"), dict) else None
    )

    reasoning_payload["summary"] = build_summary_from_decision(
        decision,
        reasoning_payload.get("summary") or raw_reason,
    )
    reasoning_payload["narrative"] = _normalize_string_list(reasoning_payload.get("narrative")) or reason_candidates
    reasoning_payload["required_followups"] = decision["required_followups"]
    reasoning_payload["analysis_limitations"] = decision["analysis_limitations"]

    result = {
        "decision": decision,
        "statement_summary": normalized.get("statement_summary"),
        "transaction_insights": transaction_insights,
        "risk_findings": risk_findings,
        "reasoning": reasoning_payload,
        "transactions": normalized.get("transactions") if isinstance(normalized.get("transactions"), list) else [],
    }
    if isinstance(normalized.get("account_profile"), dict):
        result["account_profile"] = normalized["account_profile"]
    return result


def canonicalize_analysis_payload(
    payload: Any,
    *,
    fallback_verdict: str | None = None,
    fallback_risk_confidence: Any = 0.0,
    fallback_reasons: list[str] | None = None,
    fallback_extraction_confidence: Any | None = None,
    fallback_data_completeness: Any | None = None,
    fallback_decision_recommendation: str | None = None,
    fallback_decision_reason: str | None = None,
    fallback_required_followups: list[str] | None = None,
    fallback_analysis_limitations: list[str] | None = None,
) -> Any:
    """
    Apply canonical confidence normalization and ensure the exact shared
    `decision` object exists for persisted analysis payloads.
    """

    normalized = normalize_confidence_payload(payload)
    if not isinstance(normalized, dict):
        return normalized

    if _is_dedicated_bank_statement_payload(normalized):
        return _canonicalize_dedicated_bank_statement_payload(
            normalized,
            fallback_verdict=fallback_verdict,
            fallback_risk_confidence=fallback_risk_confidence,
            fallback_reasons=fallback_reasons,
            fallback_extraction_confidence=fallback_extraction_confidence,
            fallback_data_completeness=fallback_data_completeness,
            fallback_decision_recommendation=fallback_decision_recommendation,
            fallback_decision_reason=fallback_decision_reason,
            fallback_required_followups=fallback_required_followups,
            fallback_analysis_limitations=fallback_analysis_limitations,
        )

    decision_engine = normalized.get("decisionEngine")
    if isinstance(decision_engine, dict):
        engine = dict(decision_engine)
        if "confidence" in engine:
            engine["risk_confidence"] = normalize_confidence(
                engine.pop("confidence"),
                fallback_risk_confidence,
            )
        elif "risk_confidence" in engine:
            engine["risk_confidence"] = normalize_confidence(
                engine["risk_confidence"],
                fallback_risk_confidence,
            )
        else:
            engine["risk_confidence"] = normalize_confidence(fallback_risk_confidence)
        normalized["decisionEngine"] = engine

    if isinstance(normalized.get("statementMeta"), dict):
        statement_meta = dict(normalized["statementMeta"])
        statement_meta["confidence"] = normalize_confidence(
            statement_meta.get("confidence"),
            fallback_extraction_confidence if fallback_extraction_confidence is not None else fallback_risk_confidence,
        )
        normalized["statementMeta"] = statement_meta

    if isinstance(normalized.get("incomeEngine"), dict) and "confidence" in normalized["incomeEngine"]:
        income_engine = dict(normalized["incomeEngine"])
        income_engine["confidence"] = normalize_confidence(
            income_engine.get("confidence"),
            fallback_data_completeness if fallback_data_completeness is not None else fallback_risk_confidence,
        )
        normalized["incomeEngine"] = income_engine

    raw_decision = normalized.get("decision")
    status_candidates: list[Any] = []
    fallback_status_candidates: list[Any] = [
        normalized.get("decision_label"),
        normalized.get("recommendation"),
        fallback_verdict,
    ]
    raw_recommendation = fallback_decision_recommendation
    raw_reason = fallback_decision_reason
    risk_confidence = None
    extraction_confidence = None
    data_completeness = None
    required_followups = fallback_required_followups
    analysis_limitations = fallback_analysis_limitations
    reason_candidates = _normalize_string_list(fallback_reasons)

    if isinstance(raw_decision, dict):
        status_candidates.extend(
            [
                raw_decision.get("decision_status"),
                raw_decision.get("verdict"),
                raw_decision.get("decision"),
            ]
        )
        raw_recommendation = raw_decision.get("decision_recommendation") or raw_recommendation
        raw_reason = raw_decision.get("decision_reason") or raw_reason
        risk_confidence = raw_decision.get("risk_confidence", raw_decision.get("confidence"))
        extraction_confidence = raw_decision.get("extraction_confidence")
        data_completeness = raw_decision.get("data_completeness")
        required_followups = raw_decision.get("required_followups", required_followups)
        analysis_limitations = raw_decision.get("analysis_limitations", analysis_limitations)
        reason_candidates = _normalize_string_list(raw_decision.get("reasons")) or reason_candidates
    else:
        status_candidates.append(raw_decision)

    if isinstance(normalized.get("decisionEngine"), dict):
        engine = normalized["decisionEngine"]
        status_candidates.append(engine.get("decision"))
        if not raw_reason:
            engine_reasons = _normalize_string_list(engine.get("reasons"))
            if engine_reasons:
                raw_reason = engine_reasons[0]
                reason_candidates = engine_reasons
        if risk_confidence is None:
            risk_confidence = engine.get("risk_confidence")

    reasoning = normalized.get("reasoning")
    if isinstance(reasoning, list):
        cleaned_reasoning = [
            _collapse_whitespace(item).removeprefix("Decision: ").strip()
            for item in reasoning
            if _collapse_whitespace(item)
        ]
        if not raw_reason:
            for item in cleaned_reasoning:
                if item.startswith("->"):
                    raw_reason = item.removeprefix("->").strip()
                    break
            if not raw_reason and cleaned_reasoning:
                raw_reason = cleaned_reasoning[0]
        if not required_followups:
            required_followups = [item.removeprefix("->").strip() for item in cleaned_reasoning[1:] if item]

    if not raw_reason:
        raw_reason = normalized.get("risk_reasoning") or normalized.get("summary")

    if not required_followups:
        required_followups = normalized.get("required_followups") or normalized.get("riskFlags")

    if not analysis_limitations:
        analysis_limitations = (
            normalized.get("analysis_limitations")
            or normalized.get("uncertaintyNotes")
        )

    if risk_confidence is None:
        risk_confidence = extract_decision_risk_confidence(normalized, fallback_risk_confidence)

    statement_meta = normalized.get("statementMeta")
    if extraction_confidence is None and isinstance(statement_meta, dict):
        extraction_confidence = statement_meta.get("confidence")
    if extraction_confidence is None:
        extraction_confidence = normalized.get("extraction_confidence")
    if extraction_confidence is None and fallback_extraction_confidence is not None:
        extraction_confidence = fallback_extraction_confidence
    if extraction_confidence is None:
        extraction_confidence = risk_confidence

    if data_completeness is None:
        data_completeness = normalized.get("data_completeness")
    if data_completeness is None and fallback_data_completeness is not None:
        data_completeness = fallback_data_completeness
    if data_completeness is None and isinstance(normalized.get("incomeEngine"), dict):
        data_completeness = normalized["incomeEngine"].get("confidence")
    if data_completeness is None:
        data_completeness = extraction_confidence

    if not any(_collapse_whitespace(candidate) for candidate in status_candidates):
        status_candidates.extend(fallback_status_candidates)

    decision = build_decision_payload(
        verdict=str(fallback_verdict or "").strip() or None,
        decision_recommendation=raw_recommendation,
        decision_reason=raw_reason,
        extraction_confidence=extraction_confidence,
        risk_confidence=risk_confidence,
        data_completeness=data_completeness,
        required_followups=required_followups,
        analysis_limitations=analysis_limitations,
        reasons=reason_candidates,
        decision_candidates=status_candidates,
    )

    normalized["decision"] = decision
    normalized["decision_label"] = decision["decision_status"]
    return normalized


def extract_canonical_decision(
    payload: Any,
    *,
    fallback_status: str | None = None,
    fallback_recommendation: str | None = None,
    fallback_reason: str | None = None,
    fallback_extraction_confidence: Any = 0.0,
    fallback_risk_confidence: Any = 0.0,
    fallback_data_completeness: Any | None = None,
    fallback_required_followups: list[str] | None = None,
    fallback_analysis_limitations: list[str] | None = None,
    fallback_reasons: list[str] | None = None,
) -> dict[str, Any]:
    normalized = canonicalize_analysis_payload(
        dict(payload) if isinstance(payload, dict) else payload,
        fallback_verdict=fallback_status,
        fallback_risk_confidence=fallback_risk_confidence,
        fallback_reasons=fallback_reasons,
        fallback_extraction_confidence=fallback_extraction_confidence,
        fallback_data_completeness=fallback_data_completeness,
        fallback_decision_recommendation=fallback_recommendation,
        fallback_decision_reason=fallback_reason,
        fallback_required_followups=fallback_required_followups,
        fallback_analysis_limitations=fallback_analysis_limitations,
    )
    if isinstance(normalized, dict) and isinstance(normalized.get("decision"), dict):
        return dict(normalized["decision"])
    return build_decision_payload(
        decision_status=fallback_status,
        decision_recommendation=fallback_recommendation,
        decision_reason=fallback_reason,
        extraction_confidence=fallback_extraction_confidence,
        risk_confidence=fallback_risk_confidence,
        data_completeness=fallback_data_completeness,
        required_followups=fallback_required_followups,
        analysis_limitations=fallback_analysis_limitations,
        reasons=fallback_reasons,
        decision_candidates=[fallback_status],
    )
