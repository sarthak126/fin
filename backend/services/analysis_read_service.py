"""
Read-model helpers for normalized analysis payloads.
"""

from __future__ import annotations

import json
from typing import Any

from core.confidence import (
    build_summary_from_decision,
    canonicalize_analysis_payload,
    extract_canonical_decision,
    extract_decision_risk_confidence,
    normalize_confidence,
    recommendation_from_decision_status,
)


def load_string_list_json(raw_value: Any) -> list[str] | None:
    if not raw_value:
        return None
    if isinstance(raw_value, list):
        return raw_value
    try:
        parsed = json.loads(raw_value)
    except Exception:
        return None
    return parsed if isinstance(parsed, list) else None


def _format_record_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize persisted analysis-like records for read-model consumers."""
    data["confidence"] = normalize_confidence(data.get("confidence"))

    if data.get("extracted_fields") and isinstance(data["extracted_fields"], str):
        data["extracted_fields"] = json.loads(data["extracted_fields"])
    if isinstance(data.get("extracted_fields"), dict):
        data["extracted_fields"] = canonicalize_analysis_payload(
            data["extracted_fields"],
            fallback_verdict=data.get("decision_status") or data.get("recommendation"),
            fallback_risk_confidence=data.get("risk_confidence")
            if data.get("risk_confidence") is not None
            else data.get("confidence"),
            fallback_extraction_confidence=data.get("extraction_confidence")
            if data.get("extraction_confidence") is not None
            else data.get("confidence"),
            fallback_data_completeness=data.get("data_completeness")
            if data.get("data_completeness") is not None
            else data.get("extraction_confidence") or data.get("confidence"),
            fallback_decision_recommendation=data.get("decision_recommendation"),
            fallback_decision_reason=data.get("decision_reason") or data.get("summary"),
            fallback_required_followups=load_string_list_json(data.get("required_followups_json")),
            fallback_analysis_limitations=load_string_list_json(data.get("analysis_limitations_json")),
        )
    if data.get("risk_alerts") and isinstance(data["risk_alerts"], str):
        data["risk_alerts"] = json.loads(data["risk_alerts"])
    if data.get("raw_response") and isinstance(data["raw_response"], str):
        data["raw_response"] = json.loads(data["raw_response"])
    if isinstance(data.get("raw_response"), dict):
        data["raw_response"] = canonicalize_analysis_payload(
            data["raw_response"],
            fallback_verdict=data.get("decision_status") or data.get("recommendation"),
            fallback_risk_confidence=data.get("risk_confidence")
            if data.get("risk_confidence") is not None
            else data.get("confidence"),
            fallback_extraction_confidence=data.get("extraction_confidence")
            if data.get("extraction_confidence") is not None
            else data.get("confidence"),
            fallback_data_completeness=data.get("data_completeness")
            if data.get("data_completeness") is not None
            else data.get("extraction_confidence") or data.get("confidence"),
            fallback_decision_recommendation=data.get("decision_recommendation"),
            fallback_decision_reason=data.get("decision_reason") or data.get("summary"),
            fallback_required_followups=load_string_list_json(data.get("required_followups_json")),
            fallback_analysis_limitations=load_string_list_json(data.get("analysis_limitations_json")),
        )

    decision_source = data.get("extracted_fields") if isinstance(data.get("extracted_fields"), dict) else {}
    if not decision_source and isinstance(data.get("raw_response"), dict):
        decision_source = data["raw_response"]

    decision = extract_canonical_decision(
        decision_source,
        fallback_status=data.get("decision_status") or data.get("recommendation"),
        fallback_recommendation=data.get("decision_recommendation"),
        fallback_reason=data.get("decision_reason") or data.get("summary"),
        fallback_extraction_confidence=data.get("extraction_confidence")
        if data.get("extraction_confidence") is not None
        else data.get("confidence"),
        fallback_risk_confidence=data.get("risk_confidence")
        if data.get("risk_confidence") is not None
        else data.get("confidence"),
        fallback_data_completeness=data.get("data_completeness")
        if data.get("data_completeness") is not None
        else data.get("extraction_confidence") or data.get("confidence"),
        fallback_required_followups=load_string_list_json(data.get("required_followups_json")),
        fallback_analysis_limitations=load_string_list_json(data.get("analysis_limitations_json")),
    )

    if isinstance(data.get("extracted_fields"), dict):
        data["extracted_fields"]["decision"] = dict(decision)
        data["confidence"] = extract_decision_risk_confidence(
            data["extracted_fields"],
            fallback=decision["risk_confidence"],
        )
    if isinstance(data.get("raw_response"), dict):
        data["raw_response"]["decision"] = dict(decision)

    data["decision_status"] = decision["decision_status"]
    data["decision_recommendation"] = decision["decision_recommendation"]
    data["decision_reason"] = decision["decision_reason"]
    data["extraction_confidence"] = decision["extraction_confidence"]
    data["risk_confidence"] = decision["risk_confidence"]
    data["data_completeness"] = decision["data_completeness"]
    data["required_followups_json"] = json.dumps(decision["required_followups"])
    data["analysis_limitations_json"] = json.dumps(decision["analysis_limitations"])
    data["recommendation"] = recommendation_from_decision_status(decision["decision_status"])
    data["confidence"] = decision["risk_confidence"]
    data["summary"] = build_summary_from_decision(decision, data.get("summary"))
    return data


def format_analysis_response_payload(analysis: Any) -> dict[str, Any]:
    """
    Decode persisted JSON fields and normalize decision/confidence payloads for
    read-model consumers.
    """

    return _format_record_payload(analysis.model_dump())


def format_case_analysis_response_payload(case_analysis: Any) -> dict[str, Any]:
    """Normalize a persisted case-analysis snapshot for read-model consumers."""

    return _format_record_payload(case_analysis.model_dump())
