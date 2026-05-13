"""
Aggregated read model for case detail views.
"""

from __future__ import annotations

import asyncio
from collections import Counter
import re
from typing import Any

from prisma import Prisma

from core.confidence import normalize_decision_status, recommendation_from_decision_status
from models import DocumentStatus, DocumentType
from schemas.analysis import AnalysisResponse
from schemas.case import CaseDetail
from schemas.case_read_model import (
    CaseApplicantIntake,
    CaseAnalysisSnapshot,
    CaseDocumentEvidenceProfile,
    CaseDocumentReadModel,
    CaseDocumentOcrStatus,
    CaseProvisionalInsights,
    CaseReadModel,
    CrossDocumentComparison,
    CrossDocumentComparisonValue,
    FraudSignal,
    FraudSignalEvidence,
    SupportedDocumentCompleteness,
    SupportedDocumentRequirement,
)
from services.analysis_read_service import (
    format_analysis_response_payload,
    format_case_analysis_response_payload,
    load_string_list_json,
)
from services.case_service import get_case_by_id_for_org
from services.extraction_service import (
    EXTRACTION_STATUS_FAILED,
    EXTRACTION_STATUS_PARTIAL,
    EXTRACTION_STATUS_UNRELIABLE,
    OCR_QUALITY_STATUS_BLOCKED,
    resolve_ocr_quality_status,
)
from services.job_queue_service import get_analysis_job
from services.storage_service import load_extraction_artifact_for_file
from services.bank_statement_profile import (
    extract_bank_statement_evidence_profile,
    merge_statement_evidence,
)
from services.followup_utils import filter_action_followups

_INTAKE_FIELDS = (
    ("applicant_name", "Applicant name"),
    ("applicant_email", "Applicant email"),
    ("applicant_phone", "Applicant phone"),
)

_SUPPORTED_DOCUMENT_TYPES = (
    DocumentType.BANK_STATEMENT,
    DocumentType.TAX_RETURN,
    DocumentType.SALARY_SLIP,
    DocumentType.EMPLOYMENT_LETTER,
    DocumentType.INCOME_PROOF,
    DocumentType.ID_DOCUMENT,
)

_DOCUMENT_REQUIREMENTS = (
    {
        "key": "identity",
        "label": "Identity verification",
        "accepted_document_types": (DocumentType.ID_DOCUMENT,),
    },
    {
        "key": "banking",
        "label": "Bank statements",
        "accepted_document_types": (DocumentType.BANK_STATEMENT,),
    },
    {
        "key": "income",
        "label": "Income support",
        "accepted_document_types": (
            DocumentType.SALARY_SLIP,
            DocumentType.TAX_RETURN,
            DocumentType.EMPLOYMENT_LETTER,
            DocumentType.INCOME_PROOF,
        ),
    },
)

_COMPARISON_LABELS = {
    "applicant_name": "Applicant name",
    "monthly_income": "Monthly income",
    "annual_income": "Annual income",
    "employment_type": "Employment type",
    "employer_name": "Employer",
    "avg_monthly_balance": "Average monthly balance",
    "existing_emis": "Existing EMIs",
    "debt_to_income_ratio": "Debt-to-income ratio",
}
_DOCUMENT_TYPE_LABELS = {
    DocumentType.BANK_STATEMENT: "Bank statement",
    DocumentType.TAX_RETURN: "Tax return",
    DocumentType.SALARY_SLIP: "Salary slip",
    DocumentType.EMPLOYMENT_LETTER: "Employment letter",
    DocumentType.INCOME_PROOF: "Income proof",
    DocumentType.ID_DOCUMENT: "ID document",
}
_PERSON_NAME_PREFIX_TOKENS = {"mr", "mrs", "ms", "miss", "dr", "shri", "smt", "kumari"}
_COMPANY_SUFFIX_TOKENS = {"pvt", "private", "ltd", "limited", "llp", "inc", "corp", "corporation", "co", "company"}
_FRAUD_CONFLICT_LABELS = {
    "name_mismatch": "Applicant name",
    "employer_mismatch": "Employer",
    "income_discrepancy": "Monthly income",
}
_INCOME_DISCREPANCY_THRESHOLD = 0.20
_SUPPORTED_DOCUMENT_TYPE_VALUES = {document_type.value for document_type in _SUPPORTED_DOCUMENT_TYPES}
_OCR_BLOCKING_EXTRACTION_STATUSES = {
    EXTRACTION_STATUS_FAILED,
    EXTRACTION_STATUS_PARTIAL,
    EXTRACTION_STATUS_UNRELIABLE,
}
_EMAIL_LIKE_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_LIKE_RE = re.compile(r"^\+?[\d\s().-]{7,20}$")


def _strip_optional(value: Any) -> str | None:
    if value is None:
        return None
    trimmed = str(value).strip()
    return trimmed or None


def _is_valid_email(value: Any) -> bool:
    text = _strip_optional(value)
    return bool(text and _EMAIL_LIKE_RE.match(text))


def _is_valid_phone(value: Any) -> bool:
    text = _strip_optional(value)
    if not text or "@" in text:
        return False
    digits = re.sub(r"\D", "", text)
    return 7 <= len(digits) <= 15 and bool(_PHONE_LIKE_RE.match(text))


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_int_list(value: Any) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple, set)):
        value = [value]

    numbers: set[int] = set()
    for item in value:
        coerced = _coerce_int(item)
        if coerced is not None:
            numbers.add(coerced)
    return sorted(numbers)


def _round_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _strip_optional(value)
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(text)
    return deduped


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _get_nested(mapping: dict[str, Any], *path: str) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _maybe_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    cleaned = value.replace(",", "").strip()
    if not cleaned:
        return None
    range_match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)", cleaned)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        return round((low + high) / 2.0, 2)
    try:
        return float(cleaned)
    except ValueError:
        return None


def _estimate_midpoint(min_value: Any, max_value: Any, fallback: Any = None) -> float | None:
    low = _maybe_number(min_value)
    high = _maybe_number(max_value)
    if low is not None and high is not None:
        return round((low + high) / 2.0, 2)
    if low is not None:
        return low
    if high is not None:
        return high
    return _maybe_number(fallback)


def _normalized_text(value: Any) -> str | None:
    text = _strip_optional(value)
    if not text:
        return None
    return " ".join(text.lower().replace("_", " ").split())


def _tokenize_text(value: Any) -> list[str]:
    text = _strip_optional(value)
    if not text:
        return []
    return re.findall(r"[a-z0-9]+", text.lower())


def _normalized_name_tokens(value: Any) -> list[str]:
    return [token for token in _tokenize_text(value) if token not in _PERSON_NAME_PREFIX_TOKENS]


def _normalized_company_tokens(value: Any) -> list[str]:
    return [token for token in _tokenize_text(value) if token not in _COMPANY_SUFFIX_TOKENS]


def _names_match(left: Any, right: Any) -> bool:
    left_tokens = _normalized_name_tokens(left)
    right_tokens = _normalized_name_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True

    shorter, longer = sorted((left_tokens, right_tokens), key=len)
    if len(shorter) < 2:
        return False
    return set(shorter).issubset(set(longer))


def _company_names_match(left: Any, right: Any) -> bool:
    left_tokens = _normalized_company_tokens(left)
    right_tokens = _normalized_company_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True

    shorter, longer = sorted((left_tokens, right_tokens), key=len)
    return set(shorter).issubset(set(longer))


def _normalized_employment_type(value: Any) -> str | None:
    normalized = _normalized_text(value)
    if not normalized:
        return None
    if normalized in {"salary", "salaried"}:
        return "salaried"
    return normalized


def _income_relative_spread(values: list[float]) -> float:
    concrete = [abs(value) for value in values if value is not None]
    if len(concrete) < 2:
        return 0.0

    low = min(concrete)
    high = max(concrete)
    if low <= 0:
        return float("inf") if high > 0 else 0.0
    return round((high - low) / low, 4)


def _document_type_label(document_type: DocumentType) -> str:
    return _DOCUMENT_TYPE_LABELS.get(document_type, document_type.value.replace("_", " ").title())


def _is_supported_document_type(document_type: Any) -> bool:
    normalized = getattr(document_type, "value", document_type)
    return normalized in _SUPPORTED_DOCUMENT_TYPE_VALUES


def _scoreable_documents(documents: list[CaseDocumentReadModel]) -> list[CaseDocumentReadModel]:
    return [document for document in documents if _is_supported_document_type(document.document_type)]


def _comparison_tolerance(field: str, values: list[float]) -> float:
    max_value = max(abs(value) for value in values) if values else 0.0
    if field == "debt_to_income_ratio":
        return 0.05
    if field == "annual_income":
        return max(5000.0, max_value * _INCOME_DISCREPANCY_THRESHOLD)
    if field in {"monthly_income", "avg_monthly_balance"}:
        return max(500.0, max_value * 0.10)
    if field == "existing_emis":
        return max(250.0, max_value * 0.10)
    return max(1.0, max_value * 0.05)


def _evaluate_comparison_status(field: str, values: list[Any]) -> str:
    if len(values) < 2:
        return "insufficient_data"

    if field == "applicant_name":
        concrete_text = [_strip_optional(value) for value in values if _strip_optional(value)]
        if len(concrete_text) < 2:
            return "insufficient_data"
        return "consistent" if all(_names_match(concrete_text[0], value) for value in concrete_text[1:]) else "mismatch"

    if field == "employer_name":
        concrete_text = [_strip_optional(value) for value in values if _strip_optional(value)]
        if len(concrete_text) < 2:
            return "insufficient_data"
        return "consistent" if all(_company_names_match(concrete_text[0], value) for value in concrete_text[1:]) else "mismatch"

    if field == "employment_type":
        concrete_text = [_normalized_employment_type(value) for value in values if _normalized_employment_type(value)]
        if len(concrete_text) < 2:
            return "insufficient_data"
        return "consistent" if len(set(concrete_text)) == 1 else "mismatch"

    numeric_values = [_maybe_number(value) for value in values]
    if all(value is not None for value in numeric_values):
        concrete_numbers = [value for value in numeric_values if value is not None]
        if field in {"monthly_income", "annual_income"}:
            return (
                "consistent"
                if _income_relative_spread(concrete_numbers) <= _INCOME_DISCREPANCY_THRESHOLD
                else "mismatch"
            )
        tolerance = _comparison_tolerance(field, concrete_numbers)
        return "consistent" if max(concrete_numbers) - min(concrete_numbers) <= tolerance else "mismatch"

    normalized_values = [_normalized_text(value) for value in values]
    concrete_text = [value for value in normalized_values if value is not None]
    if len(concrete_text) < 2:
        return "insufficient_data"
    return "consistent" if len(set(concrete_text)) == 1 else "mismatch"


def _extract_comparison_facts(document: CaseDocumentReadModel) -> dict[str, Any]:
    latest_analysis = document.latest_analysis
    if latest_analysis is None:
        return {}

    extracted_fields = _as_dict(latest_analysis.extracted_fields)
    if not extracted_fields:
        return {}

    if {"statement_summary", "transaction_insights", "risk_findings"}.issubset(extracted_fields.keys()):
        income_engine = _get_nested(extracted_fields, "transaction_insights", "income_engine") or {}
        recurring_income_estimate = _maybe_number(
            income_engine.get("recurring_income_estimate")
        )
        verified_monthly_estimate = _maybe_number(
            _get_nested(extracted_fields, "transaction_insights", "income", "verified_monthly_estimate")
        )
        monthly_income_estimate = _estimate_midpoint(
            _get_nested(extracted_fields, "transaction_insights", "income", "monthly_estimate_min"),
            _get_nested(extracted_fields, "transaction_insights", "income", "monthly_estimate_max"),
            _get_nested(extracted_fields, "transaction_insights", "income", "monthly_estimate"),
        )
        annual_income_estimate = _estimate_midpoint(
            _get_nested(extracted_fields, "transaction_insights", "income", "annual_estimate_min"),
            _get_nested(extracted_fields, "transaction_insights", "income", "annual_estimate_max"),
            _get_nested(extracted_fields, "transaction_insights", "income", "annual_estimate"),
        )
        income_type = _get_nested(extracted_fields, "transaction_insights", "income", "income_type")
        if verified_monthly_estimate is None and str(income_type or "").strip().lower() == "salary":
            verified_monthly_estimate = monthly_income_estimate
        verified_or_recurring_income = (
            verified_monthly_estimate
            if verified_monthly_estimate is not None
            else recurring_income_estimate
        )
        return {
            "applicant_name": None,
            "monthly_income": verified_or_recurring_income
            if verified_or_recurring_income is not None
            else monthly_income_estimate,
            "annual_income": round(verified_or_recurring_income * 12.0, 2)
            if verified_or_recurring_income is not None
            else annual_income_estimate,
            "employment_type": income_type,
            "employer_name": income_engine.get("recurring_income_source"),
            "avg_monthly_balance": _get_nested(extracted_fields, "transaction_insights", "balance", "average"),
            "existing_emis": _get_nested(extracted_fields, "transaction_insights", "expenses", "emi"),
            "debt_to_income_ratio": _get_nested(extracted_fields, "transaction_insights", "dti", "value"),
            "recurring_income_source": income_engine.get("recurring_income_source"),
            "recurring_income_estimate": recurring_income_estimate,
        }

    return {
        "applicant_name": extracted_fields.get("applicant_name"),
        "monthly_income": extracted_fields.get("monthly_income"),
        "annual_income": extracted_fields.get("annual_income"),
        "employment_type": extracted_fields.get("employment_type"),
        "employer_name": extracted_fields.get("employer_name"),
        "avg_monthly_balance": extracted_fields.get("avg_monthly_balance"),
        "existing_emis": extracted_fields.get("existing_emis"),
        "debt_to_income_ratio": extracted_fields.get("debt_to_income_ratio"),
    }


def _build_applicant_form_evidence(*, field: str, value: Any) -> FraudSignalEvidence:
    return FraudSignalEvidence(
        source_type="applicant_form",
        source_label="Applicant form",
        field=field,
        value=value,
    )


def _build_document_evidence(
    document: CaseDocumentReadModel,
    *,
    field: str,
    value: Any,
    source_label: str | None = None,
) -> FraudSignalEvidence:
    return FraudSignalEvidence(
        source_type="document",
        source_label=source_label or _document_type_label(DocumentType(document.document_type)),
        field=field,
        value=value,
        document_id=document.id,
        document_type=DocumentType(document.document_type),
        original_filename=document.original_filename,
        analysis_id=document.latest_analysis.id if document.latest_analysis else None,
    )


def _format_signal_value_list(evidence: list[FraudSignalEvidence]) -> str:
    return "; ".join(f"{item.source_label}: {item.value}" for item in evidence)


def _collect_income_evidence(
    case_detail: CaseDetail,
    documents: list[CaseDocumentReadModel],
) -> list[FraudSignalEvidence]:
    evidence: list[FraudSignalEvidence] = []

    applicant_monthly_income = None
    for field_name in ("applicant_monthly_income", "declared_monthly_income", "monthly_income"):
        applicant_monthly_income = _maybe_number(getattr(case_detail, field_name, None))
        if applicant_monthly_income is not None:
            break
    if applicant_monthly_income is None:
        for field_name in ("applicant_annual_income", "declared_annual_income", "annual_income"):
            annual_income = _maybe_number(getattr(case_detail, field_name, None))
            if annual_income is not None:
                applicant_monthly_income = round(annual_income / 12.0, 2)
                break
    if applicant_monthly_income is not None:
        evidence.append(
            _build_applicant_form_evidence(field="monthly_income", value=applicant_monthly_income)
        )

    for document in documents:
        facts = _extract_comparison_facts(document)
        monthly_income = _maybe_number(facts.get("monthly_income"))
        if monthly_income is None:
            annual_income = _maybe_number(facts.get("annual_income"))
            if annual_income is not None:
                monthly_income = round(annual_income / 12.0, 2)
        if monthly_income is None:
            continue

        source_label = _document_type_label(DocumentType(document.document_type))
        if DocumentType(document.document_type) == DocumentType.BANK_STATEMENT:
            source_label = "Recurring bank income"
        evidence.append(
            _build_document_evidence(
                document,
                field="monthly_income",
                value=monthly_income,
                source_label=source_label,
            )
        )

    return evidence


def _build_name_mismatch_signal(
    case_detail: CaseDetail,
    documents: list[CaseDocumentReadModel],
) -> FraudSignal | None:
    applicant_name = _strip_optional(case_detail.applicant_name)
    if not applicant_name:
        return None

    evidence = [_build_applicant_form_evidence(field="applicant_name", value=applicant_name)]
    mismatches: list[FraudSignalEvidence] = []
    for document in documents:
        if DocumentType(document.document_type) not in {DocumentType.SALARY_SLIP, DocumentType.TAX_RETURN}:
            continue
        facts = _extract_comparison_facts(document)
        document_name = _strip_optional(facts.get("applicant_name"))
        if not document_name:
            continue

        document_evidence = _build_document_evidence(
            document,
            field="applicant_name",
            value=document_name,
        )
        evidence.append(document_evidence)
        if not _names_match(applicant_name, document_name):
            mismatches.append(document_evidence)

    if len(evidence) < 2 or not mismatches:
        return None

    mismatched_sources = ", ".join(item.source_label.lower() for item in mismatches)
    return FraudSignal(
        key="name_mismatch",
        label="Applicant name mismatch",
        severity="high",
        summary=f"Applicant name mismatch detected between the applicant form and {mismatched_sources}.",
        details="Identity values conflict across the available evidence: " + _format_signal_value_list(evidence) + ".",
        recommended_action="Verify the applicant's legal name against the applicant form, salary slip, and ITR before proceeding.",
        evidence=evidence,
    )


def _build_employer_mismatch_signal(documents: list[CaseDocumentReadModel]) -> FraudSignal | None:
    evidence: list[FraudSignalEvidence] = []
    has_bank_source = False
    has_employer_document = False

    for document in documents:
        doc_type = DocumentType(document.document_type)
        facts = _extract_comparison_facts(document)
        employer_name = _strip_optional(facts.get("employer_name"))
        if not employer_name:
            continue

        source_label = _document_type_label(doc_type)
        if doc_type == DocumentType.BANK_STATEMENT:
            source_label = "Recurring bank income"
            has_bank_source = True
        elif doc_type in {DocumentType.SALARY_SLIP, DocumentType.EMPLOYMENT_LETTER, DocumentType.INCOME_PROOF}:
            has_employer_document = True
        else:
            continue

        evidence.append(
            _build_document_evidence(
                document,
                field="employer_name",
                value=employer_name,
                source_label=source_label,
            )
        )

    if len(evidence) < 2 or not has_bank_source or not has_employer_document:
        return None
    if all(_company_names_match(evidence[0].value, item.value) for item in evidence[1:]):
        return None

    return FraudSignal(
        key="employer_mismatch",
        label="Employer mismatch",
        severity="high",
        summary="Employer name does not align with the recurring bank-income source.",
        details="Employer/source values conflict across the available evidence: " + _format_signal_value_list(evidence) + ".",
        recommended_action="Verify the employer name against the salary slip and the recurring salary credits in the bank statement.",
        evidence=evidence,
    )


def _build_income_discrepancy_signal(
    case_detail: CaseDetail,
    documents: list[CaseDocumentReadModel],
) -> FraudSignal | None:
    evidence = _collect_income_evidence(case_detail, documents)
    if len(evidence) < 2:
        return None

    income_values = [_maybe_number(item.value) for item in evidence]
    concrete_values = [value for value in income_values if value is not None]
    if len(concrete_values) < 2:
        return None

    spread = _income_relative_spread(concrete_values)
    if spread <= _INCOME_DISCREPANCY_THRESHOLD:
        return None

    return FraudSignal(
        key="income_discrepancy",
        label="Income discrepancy > 20%",
        severity="high" if spread >= 0.35 else "medium",
        summary=f"Monthly income differs by {spread * 100:.1f}% across the available evidence.",
        details="Income values used for the v1 discrepancy rule: " + _format_signal_value_list(evidence) + ".",
        recommended_action="Reconcile the applicant's declared income with the salary slip, ITR, and recurring bank income before approval.",
        evidence=evidence,
    )


def _build_fraud_signals(
    case_detail: CaseDetail,
    documents: list[CaseDocumentReadModel],
) -> list[FraudSignal]:
    documents = _scoreable_documents(documents)
    signals = [
        _build_name_mismatch_signal(case_detail, documents),
        _build_employer_mismatch_signal(documents),
        _build_income_discrepancy_signal(case_detail, documents),
    ]
    return [signal for signal in signals if signal is not None]


def _build_applicant_intake(case_detail: CaseDetail) -> CaseApplicantIntake:
    completed_fields: list[str] = []
    if _strip_optional(case_detail.applicant_name):
        completed_fields.append("applicant_name")
    if _is_valid_email(case_detail.applicant_email):
        completed_fields.append("applicant_email")
    if _is_valid_phone(case_detail.applicant_phone):
        completed_fields.append("applicant_phone")
    missing_fields = [
        field_name
        for field_name, _label in _INTAKE_FIELDS
        if field_name not in completed_fields
    ]
    return CaseApplicantIntake(
        applicant_name=case_detail.applicant_name,
        applicant_email=case_detail.applicant_email,
        applicant_phone=case_detail.applicant_phone,
        completed_fields=completed_fields,
        missing_fields=missing_fields,
        completeness=_round_ratio(len(completed_fields), len(_INTAKE_FIELDS)),
    )


def _build_supported_document_completeness(
    documents: list[CaseDocumentReadModel],
) -> SupportedDocumentCompleteness:
    present_document_types = {
        DocumentType(document.document_type)
        for document in documents
        if _is_supported_document_type(document.document_type)
    }
    requirements: list[SupportedDocumentRequirement] = []
    provided_requirement_count = 0
    analyzed_requirement_count = 0
    missing_requirement_keys: list[str] = []
    pending_requirement_keys: list[str] = []

    for requirement in _DOCUMENT_REQUIREMENTS:
        accepted = {doc_type.value for doc_type in requirement["accepted_document_types"]}
        matching_documents = [document for document in documents if document.document_type in accepted]
        analyzed_documents = [
            document for document in matching_documents if document.latest_analysis is not None
        ]

        if matching_documents:
            provided_requirement_count += 1
        else:
            missing_requirement_keys.append(requirement["key"])

        if analyzed_documents:
            analyzed_requirement_count += 1
            status = "complete"
        elif matching_documents:
            pending_requirement_keys.append(requirement["key"])
            status = "pending"
        else:
            status = "missing"

        requirements.append(
            SupportedDocumentRequirement(
                key=requirement["key"],
                label=requirement["label"],
                accepted_document_types=list(requirement["accepted_document_types"]),
                document_ids=[document.id for document in matching_documents],
                provided_count=len(matching_documents),
                analyzed_count=len(analyzed_documents),
                status=status,
            )
        )

    missing_document_types = [
        document_type for document_type in _SUPPORTED_DOCUMENT_TYPES if document_type not in present_document_types
    ]

    return SupportedDocumentCompleteness(
        provided_score=_round_ratio(provided_requirement_count, len(_DOCUMENT_REQUIREMENTS)),
        analyzed_score=_round_ratio(analyzed_requirement_count, len(_DOCUMENT_REQUIREMENTS)),
        provided_requirement_count=provided_requirement_count,
        analyzed_requirement_count=analyzed_requirement_count,
        total_requirement_count=len(_DOCUMENT_REQUIREMENTS),
        present_document_types=sorted(present_document_types, key=lambda value: value.value),
        missing_document_types=missing_document_types,
        missing_requirement_keys=missing_requirement_keys,
        pending_requirement_keys=pending_requirement_keys,
        requirements=requirements,
    )


def _build_cross_document_comparisons(
    documents: list[CaseDocumentReadModel],
) -> list[CrossDocumentComparison]:
    documents = _scoreable_documents(documents)
    comparisons: list[CrossDocumentComparison] = []

    for field, label in _COMPARISON_LABELS.items():
        comparison_values: list[CrossDocumentComparisonValue] = []
        raw_values: list[Any] = []

        for document in documents:
            facts = _extract_comparison_facts(document)
            value = facts.get(field)
            if value is None:
                continue

            raw_values.append(value)
            comparison_values.append(
                CrossDocumentComparisonValue(
                    document_id=document.id,
                    document_type=DocumentType(document.document_type),
                    original_filename=document.original_filename,
                    analysis_id=document.latest_analysis.id if document.latest_analysis else None,
                    value=value,
                )
            )

        if not comparison_values:
            continue

        status = _evaluate_comparison_status(field, raw_values)
        if status == "consistent":
            summary = f"Analyzed documents agree on {label.lower()}."
        elif status == "mismatch":
            summary = f"Analyzed documents disagree on {label.lower()}."
        else:
            summary = f"Only one analyzed document currently reports {label.lower()}."

        comparisons.append(
            CrossDocumentComparison(
                field=field,
                label=label,
                status=status,
                summary=summary,
                values=comparison_values,
            )
        )

    return comparisons


def _build_provisional_insights(
    *,
    documents: list[CaseDocumentReadModel],
    applicant_intake: CaseApplicantIntake,
    supported_document_completeness: SupportedDocumentCompleteness,
    cross_document_comparisons: list[CrossDocumentComparison],
    fraud_signals: list[FraudSignal],
) -> CaseProvisionalInsights:
    scoreable_documents = _scoreable_documents(documents)
    analyzed_documents = [document for document in scoreable_documents if document.latest_analysis is not None]
    pending_document_count = sum(
        1 for document in scoreable_documents if document.status == DocumentStatus.PENDING.value
    )
    processing_document_count = sum(
        1 for document in scoreable_documents if document.status == DocumentStatus.PROCESSING.value
    )
    failed_document_count = sum(
        1 for document in scoreable_documents if document.status == DocumentStatus.FAILED.value
    )
    decision_counter = Counter(
        normalize_decision_status(document.latest_analysis.decision_status)
        for document in analyzed_documents
        if document.latest_analysis and document.latest_analysis.decision_status
    )

    risk_scores = [
        float(document.latest_analysis.risk_score)
        for document in analyzed_documents
        if document.latest_analysis and document.latest_analysis.risk_score is not None
    ]

    blockers: list[str] = []
    followups: list[str] = []

    if applicant_intake.missing_fields:
        missing_labels = ", ".join(field.replace("_", " ") for field in applicant_intake.missing_fields)
        blockers.append(f"Applicant intake is incomplete: missing {missing_labels}.")
        followups.extend(
            f"Collect {field.replace('_', ' ')}."
            for field in applicant_intake.missing_fields
        )

    missing_requirements = [
        requirement.label
        for requirement in supported_document_completeness.requirements
        if requirement.status == "missing"
    ]
    if missing_requirements:
        blockers.append(
            "Missing supporting documents: " + ", ".join(label.lower() for label in missing_requirements) + "."
        )
        followups.extend(
            f"Request {label.lower()}."
            for label in missing_requirements
        )

    pending_requirements = [
        requirement.label
        for requirement in supported_document_completeness.requirements
        if requirement.status == "pending"
    ]
    if pending_requirements or processing_document_count:
        if pending_requirements:
            blockers.append(
                "Document review is still in progress for: "
                + ", ".join(label.lower() for label in pending_requirements)
                + "."
            )
        else:
            blockers.append("Uploaded documents are still processing.")
        followups.extend(
            f"Finish analysis for {label.lower()}."
            for label in pending_requirements
        )

    if failed_document_count:
        blockers.append("At least one uploaded document failed analysis.")
        followups.append("Retry or replace failed document uploads.")

    conflict_fields = [
        comparison.label for comparison in cross_document_comparisons if comparison.status == "mismatch"
    ]
    if fraud_signals:
        blockers.append(
            "Potential fraud signals detected: "
            + ", ".join(signal.label.lower() for signal in fraud_signals)
            + "."
        )
        followups.extend(signal.recommended_action for signal in fraud_signals)

    fraud_covered_conflicts = {
        _FRAUD_CONFLICT_LABELS.get(signal.key)
        for signal in fraud_signals
        if _FRAUD_CONFLICT_LABELS.get(signal.key)
    }
    uncovered_conflicts = [
        label for label in conflict_fields if label not in fraud_covered_conflicts
    ]
    if uncovered_conflicts:
        blockers.append(
            "Cross-document mismatches detected for " + ", ".join(label.lower() for label in uncovered_conflicts) + "."
        )
        followups.extend(
            f"Resolve the {label.lower()} discrepancy across documents."
            for label in uncovered_conflicts
        )

    for document in analyzed_documents:
        latest_analysis = document.latest_analysis
        if latest_analysis is None:
            continue
        followups.extend(filter_action_followups(load_string_list_json(latest_analysis.required_followups_json) or []))

    followups = _dedupe_strings(filter_action_followups(followups))
    blockers = _dedupe_strings(blockers)

    decision_status: str | None
    if decision_counter.get("insufficient_history"):
        decision_status = "insufficient_history"
    elif decision_counter.get("reject"):
        decision_status = "reject"
    elif blockers or decision_counter.get("manual_review"):
        decision_status = "manual_review" if analyzed_documents else None
    elif analyzed_documents:
        decision_status = "approve"
    else:
        decision_status = None

    recommendation = (
        recommendation_from_decision_status(decision_status)
        if decision_status
        else None
    )

    summary_parts: list[str] = []
    if decision_status:
        summary_parts.append(
            f"Provisional case outcome is {decision_status.replace('_', ' ')}."
        )
    else:
        summary_parts.append("Case evidence is still being assembled.")

    summary_parts.append(
        f"{len(analyzed_documents)} of {len(scoreable_documents)} scoreable document(s) currently have analysis results."
    )
    summary_parts.append(
        f"{supported_document_completeness.analyzed_requirement_count} of "
        f"{supported_document_completeness.total_requirement_count} support group(s) are fully analyzed."
    )
    if fraud_signals:
        summary_parts.append(f"{len(fraud_signals)} fraud or mismatch signal(s) need verification.")
    if blockers:
        summary_parts.append(blockers[0])

    return CaseProvisionalInsights(
        decision_status=decision_status,
        recommendation=recommendation,
        summary=" ".join(summary_parts),
        blockers=blockers,
        followups=followups,
        highest_risk_score=max(risk_scores) if risk_scores else None,
        average_risk_score=round(sum(risk_scores) / len(risk_scores), 4) if risk_scores else None,
        analyzed_document_count=len(analyzed_documents),
        pending_document_count=pending_document_count + processing_document_count,
        failed_document_count=failed_document_count,
        conflict_fields=conflict_fields,
        fraud_signal_count=len(fraud_signals),
        fraud_signal_keys=[signal.key for signal in fraud_signals],
        document_decision_counts=dict(sorted(decision_counter.items())),
    )


async def _safe_load_extraction_artifact(document: Any) -> dict[str, Any] | None:
    file_url = getattr(document, "file_url", None)
    if not file_url:
        return None

    try:
        artifact = await load_extraction_artifact_for_file(file_url)
    except Exception as exc:
        print(f"[warn] Failed to load extraction artifact for document {getattr(document, 'id', '?')}: {exc}")
        return None

    return artifact if isinstance(artifact, dict) else None


async def _safe_load_analysis_job(document: Any) -> dict[str, Any] | None:
    document_id = _strip_optional(getattr(document, "id", None))
    if not document_id:
        return None

    try:
        job = await get_analysis_job(document_id)
    except Exception as exc:
        print(f"[warn] Failed to load analysis job for document {document_id}: {exc}")
        return None

    return job if isinstance(job, dict) else None


def _build_document_ocr_status(
    document: Any,
    *,
    artifact: dict[str, Any] | None,
    job: dict[str, Any] | None,
) -> CaseDocumentOcrStatus | None:
    artifact = artifact or {}
    metadata = dict(artifact.get("metadata", {}) or {})

    def artifact_list(key: str) -> list[int]:
        return _coerce_int_list(
            artifact.get(key) if artifact.get(key) is not None else metadata.get(key)
        )

    ocr_required_pages = _coerce_int_list(
        job.get("ocr_required_pages") if job and job.get("ocr_required_pages") is not None else artifact_list("ocr_required_pages")
    )
    ocr_failed_pages = _coerce_int_list(
        job.get("ocr_failed_pages") if job and job.get("ocr_failed_pages") is not None else artifact_list("ocr_failed_pages")
    )
    ocr_unreliable_pages = _coerce_int_list(
        job.get("ocr_unreliable_pages")
        if job and job.get("ocr_unreliable_pages") is not None
        else artifact_list("ocr_unreliable_pages")
    )
    ocr_fallback_used = bool(
        job.get("ocr_fallback_used")
        if job and job.get("ocr_fallback_used") is not None
        else artifact.get("ocr_fallback_used", metadata.get("ocr_fallback_used", False))
    )
    ocr_provider = _strip_optional(
        job.get("ocr_provider")
        if job and job.get("ocr_provider") is not None
        else artifact.get("ocr_provider", metadata.get("ocr_provider"))
    )
    extraction_status = _strip_optional(artifact.get("extraction_status", metadata.get("extraction_status")))
    extraction_schema_version = _coerce_int(
        artifact.get("extraction_schema_version", metadata.get("extraction_schema_version"))
    )
    pages_processed = _coerce_int(job.get("pages_processed")) if job else None
    total_pages = (
        _coerce_int(job.get("total_pages"))
        if job and job.get("total_pages") is not None
        else _coerce_int(artifact.get("total_pages"))
    )
    error_code = _strip_optional(job.get("error_code")) if job else None
    job_status = _strip_optional(job.get("status")) if job else None
    stage = _strip_optional(job.get("stage")) if job else None
    stage_message = _strip_optional(job.get("stage_message")) if job else None
    user_message = _strip_optional(job.get("user_message")) if job else None

    if not any(
        [
            artifact,
            job,
            ocr_required_pages,
            ocr_failed_pages,
            ocr_unreliable_pages,
            ocr_fallback_used,
            ocr_provider,
            extraction_status,
        ]
    ):
        return None

    ocr_quality_status = resolve_ocr_quality_status(
        ocr_required_pages=ocr_required_pages,
        ocr_failed_pages=ocr_failed_pages,
        ocr_unreliable_pages=ocr_unreliable_pages,
        ocr_fallback_used=ocr_fallback_used,
        extraction_status=extraction_status,
        job_status=job_status,
        stage=stage,
        pages_processed=pages_processed,
        total_pages=total_pages,
        error_code=error_code,
    )
    normalized_document_status = str(getattr(document, "status", "") or "").strip().lower()
    analysis_blocked = (
        ocr_quality_status == OCR_QUALITY_STATUS_BLOCKED
        and (
            normalized_document_status == DocumentStatus.FAILED.value
            or str(job_status or "").strip().lower() == "failed"
            or str(extraction_status or "").strip().lower() in _OCR_BLOCKING_EXTRACTION_STATUSES
        )
    )

    if analysis_blocked and user_message:
        stage_message = user_message

    return CaseDocumentOcrStatus(
        ocr_quality_status=ocr_quality_status,
        ocr_required_pages=ocr_required_pages,
        ocr_failed_pages=ocr_failed_pages,
        ocr_unreliable_pages=ocr_unreliable_pages,
        ocr_fallback_used=ocr_fallback_used,
        ocr_provider=ocr_provider,
        extraction_schema_version=extraction_schema_version,
        extraction_status=extraction_status,
        stage=stage,
        stage_message=stage_message,
        pages_processed=pages_processed,
        total_pages=total_pages,
        analysis_blocked=analysis_blocked,
        error_code=error_code,
        user_message=user_message,
    )


def _artifact_total_text(artifact: dict[str, Any] | None) -> str:
    if not artifact:
        return ""
    total_text = _strip_optional(artifact.get("total_text"))
    if total_text:
        return total_text
    page_texts: list[str] = []
    for page in artifact.get("pages") or []:
        if isinstance(page, dict):
            text = _strip_optional(page.get("text"))
            if text:
                page_texts.append(text)
    return "\n".join(page_texts)


def _profile_from_analysis(latest_analysis: AnalysisResponse | None) -> dict[str, Any]:
    if latest_analysis is None:
        return {}
    extracted_fields = _as_dict(latest_analysis.extracted_fields)
    if not extracted_fields:
        return {}

    statement_summary = _as_dict(extracted_fields.get("statement_summary"))
    return {
        "account_profile": _as_dict(extracted_fields.get("account_profile")),
        "declared_period_start_date": statement_summary.get("declared_period_start_date"),
        "declared_period_end_date": statement_summary.get("declared_period_end_date"),
        "last_transaction_date": statement_summary.get("last_transaction_date")
        or statement_summary.get("statement_end_date"),
    }


def _build_document_evidence_profile(
    document: Any,
    *,
    latest_analysis: AnalysisResponse | None,
    artifact: dict[str, Any] | None,
) -> CaseDocumentEvidenceProfile | None:
    try:
        document_type = DocumentType(getattr(document, "document_type", DocumentType.OTHER.value))
    except Exception:
        document_type = DocumentType.OTHER
    if document_type != DocumentType.BANK_STATEMENT:
        return None

    analysis_profile = _profile_from_analysis(latest_analysis)
    artifact_text = _artifact_total_text(artifact)
    artifact_profile = extract_bank_statement_evidence_profile(artifact_text) if artifact_text else {}
    merged = merge_statement_evidence(analysis_profile, artifact_profile)
    account_profile = merged.get("account_profile") if isinstance(merged.get("account_profile"), dict) else {}
    if not any(
        [
            any(value not in (None, "", []) for value in account_profile.values()),
            merged.get("declared_period_start_date"),
            merged.get("declared_period_end_date"),
            merged.get("last_transaction_date"),
        ]
    ):
        return None

    return CaseDocumentEvidenceProfile.model_validate(merged)


async def _build_document_read_model(document: Any) -> CaseDocumentReadModel:
    latest_analysis = None
    raw_latest_analysis = (getattr(document, "analyses", None) or [None])[0]
    if raw_latest_analysis is not None:
        latest_analysis = AnalysisResponse.model_validate(
            format_analysis_response_payload(raw_latest_analysis)
        )
    artifact, job = await asyncio.gather(
        _safe_load_extraction_artifact(document),
        _safe_load_analysis_job(document),
    )

    return CaseDocumentReadModel(
        id=document.id,
        case_id=getattr(document, "case_id", None),
        filename=document.filename,
        original_filename=document.original_filename,
        file_url=getattr(document, "file_url", None),
        file_type=document.file_type,
        document_type=document.document_type,
        status=document.status,
        file_size_bytes=document.file_size_bytes,
        created_at=document.created_at,
        updated_at=document.updated_at,
        user_id=document.user_id,
        org_id=document.org_id,
        latest_analysis=latest_analysis,
        ocr_status=_build_document_ocr_status(
            document,
            artifact=artifact,
            job=job,
        ),
        evidence_profile=_build_document_evidence_profile(
            document,
            latest_analysis=latest_analysis,
            artifact=artifact,
        ),
    )


async def get_case_read_model(
    db: Prisma,
    case_id: str,
    org_id: str,
) -> CaseReadModel | None:
    case_record = await get_case_by_id_for_org(db=db, case_id=case_id, org_id=org_id)
    if not case_record:
        return None
    resolved_case_id = case_record.id

    raw_documents = await db.document.find_many(
        where={
            "case_id": resolved_case_id,
            "org_id": org_id,
        },
        order={"created_at": "desc"},
        include={
            "analyses": {
                "take": 1,
                "order_by": {"created_at": "desc"},
            }
        },
    )
    raw_authoritative_analysis = await db.caseanalysis.find_first(
        where={
            "case_id": resolved_case_id,
            "is_final": True,
        },
        order={"created_at": "desc"},
    )

    case_detail = CaseDetail.model_validate(case_record)
    documents = (
        await asyncio.gather(*(_build_document_read_model(document) for document in raw_documents))
        if raw_documents
        else []
    )
    authoritative_analysis = None
    if raw_authoritative_analysis is not None:
        authoritative_analysis = CaseAnalysisSnapshot.model_validate(
            format_case_analysis_response_payload(raw_authoritative_analysis)
        )
    applicant_intake = _build_applicant_intake(case_detail)
    supported_document_completeness = _build_supported_document_completeness(documents)
    cross_document_comparisons = _build_cross_document_comparisons(documents)
    fraud_signals = _build_fraud_signals(case_detail, documents)
    provisional_insights = _build_provisional_insights(
        documents=documents,
        applicant_intake=applicant_intake,
        supported_document_completeness=supported_document_completeness,
        cross_document_comparisons=cross_document_comparisons,
        fraud_signals=fraud_signals,
    )

    return CaseReadModel(
        case=case_detail,
        applicant_intake=applicant_intake,
        documents=documents,
        supported_document_completeness=supported_document_completeness,
        cross_document_comparisons=cross_document_comparisons,
        fraud_signals=fraud_signals,
        provisional_insights=provisional_insights,
        authoritative_analysis=authoritative_analysis,
    )
