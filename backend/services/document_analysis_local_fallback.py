"""
Deterministic local fallbacks for non-bank document analysis.

These heuristics intentionally favor conservative, explainable outputs over
recall. They are used when Gemini is unavailable so the underwriting flow can
still extract the most important structured fields for core document types.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Iterable

from core.config import get_settings


SUPPORTED_LOCAL_DOCUMENT_TYPES = {"salary_slip", "tax_return", "income_proof"}
ANALYSIS_LOCAL_FALLBACK_MIN_TEXT_LENGTH = get_settings().ANALYSIS_LOCAL_FALLBACK_MIN_TEXT_LENGTH


@dataclass
class LocalAnalysisFallback:
    document_type: str
    raw_json: dict
    model_used: str


def _normalize_text(text: str) -> str:
    return text.replace("\u20b9", "Rs ").replace("\xa0", " ")


def _amount_patterns(labels: Iterable[str]) -> list[re.Pattern[str]]:
    joined = "|".join(re.escape(label) for label in labels)
    return [
        re.compile(
            rf"(?im)(?:^|\b)(?:{joined})\s*(?:[:=\-]|is)?\s*(?:inr|rs\.?|rs)?\s*([0-9][0-9,]*(?:\.\d{{1,2}})?)"
        ),
        re.compile(
            rf"(?im)(?:^|\b)(?:{joined})[^\n\r]{{0,40}}?(?:inr|rs\.?|rs)?\s*([0-9][0-9,]*(?:\.\d{{1,2}})?)"
        ),
    ]


def _extract_first_amount(text: str, labels: Iterable[str]) -> float | None:
    for label in labels:
        for pattern in _amount_patterns([label]):
            match = pattern.search(text)
            if match:
                try:
                    return float(match.group(1).replace(",", ""))
                except ValueError:
                    continue
    return None


def _extract_first_text_line(text: str, labels: Iterable[str]) -> str | None:
    for label in labels:
        joined = re.escape(label)
        patterns = [
            re.compile(rf"(?im)^\s*(?:{joined})\s*[:=\-]\s*(.+?)\s*$"),
            re.compile(rf"(?im)(?:{joined})\s*[:=\-]?\s*([A-Za-z][A-Za-z0-9&.,()\/ \-]{{2,}})"),
        ]
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                value = " ".join(match.group(1).split()).strip(" -:")
                if value:
                    return value
    return None


def _extract_percentage(text: str, labels: Iterable[str]) -> float | None:
    joined = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(rf"(?im)(?:{joined})\s*(?:[:=\-]|is)?\s*([0-9]+(?:\.\d+)?)\s*%")
    match = pattern.search(text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_years_from_text(text: str) -> float | None:
    years_pattern = re.compile(
        r"(?im)(?:employment tenure|tenure|experience)\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*years?"
    )
    match = years_pattern.search(text)
    if match:
        try:
            return round(float(match.group(1)), 2)
        except ValueError:
            return None

    combined_pattern = re.compile(
        r"(?im)(?:employment tenure|tenure|experience)\s*[:=\-]?\s*([0-9]+)\s*years?\s*([0-9]+)\s*months?"
    )
    match = combined_pattern.search(text)
    if match:
        try:
            years = int(match.group(1))
            months = int(match.group(2))
            return round(years + (months / 12.0), 2)
        except ValueError:
            return None
    return None


def _try_parse_date(raw: str) -> datetime | None:
    candidates = [
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%m-%y",
        "%d/%m/%y",
        "%Y-%m-%d",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d %Y",
        "%B %d %Y",
    ]
    cleaned = raw.strip()
    for candidate in candidates:
        try:
            return datetime.strptime(cleaned, candidate)
        except ValueError:
            continue
    return None


def _extract_joining_tenure_years(text: str) -> float | None:
    join_pattern = re.compile(
        r"(?im)(?:date of joining|joining date|date joined)\s*[:=\-]?\s*([0-9A-Za-z\/\- ]{6,20})"
    )
    reference_pattern = re.compile(
        r"(?im)(?:pay period|salary month|month of salary|assessment year|financial year)\s*[:=\-]?\s*([0-9A-Za-z\/\- ]{4,25})"
    )

    join_match = join_pattern.search(text)
    if not join_match:
        return None

    join_date = _try_parse_date(join_match.group(1))
    if not join_date:
        return None

    reference_match = reference_pattern.search(text)
    reference_date = _try_parse_date(reference_match.group(1)) if reference_match else None
    end_date = reference_date or datetime.utcnow()
    if end_date <= join_date:
        return None

    delta_days = (end_date - join_date).days
    return round(delta_days / 365.25, 2)


def _extract_employment_tenure_years(text: str) -> float | None:
    explicit_years = _extract_years_from_text(text)
    if explicit_years is not None:
        return explicit_years
    return _extract_joining_tenure_years(text)


def infer_local_document_type(text: str, document_type_hint: str = "") -> str | None:
    normalized_hint = (document_type_hint or "").strip().lower()
    if normalized_hint in SUPPORTED_LOCAL_DOCUMENT_TYPES:
        return normalized_hint

    lowered = text.lower()
    salary_signals = ["salary slip", "payslip", "net pay", "gross salary", "take home"]
    tax_signals = ["income tax return", "assessment year", "gross total income", "total income", "itr"]
    income_signals = ["income proof", "income certificate", "monthly income", "average monthly income"]

    if any(signal in lowered for signal in salary_signals):
        return "salary_slip"
    if any(signal in lowered for signal in tax_signals):
        return "tax_return"
    if any(signal in lowered for signal in income_signals):
        return "income_proof"
    return None


def _base_payload(document_type: str, confidence_notes: str) -> dict:
    return {
        "applicant_name": None,
        "interest_rate": None,
        "processing_fee": None,
        "loan_amount": None,
        "tenure_months": None,
        "monthly_income": None,
        "annual_income": None,
        "monthly_expenses": None,
        "debt_to_income_ratio": None,
        "employment_type": None,
        "employment_tenure_years": None,
        "employer_name": None,
        "avg_monthly_balance": None,
        "min_balance_6m": None,
        "existing_emis": None,
        "credit_utilization_pct": None,
        "penalty_clauses": [],
        "hidden_charges": [],
        "risk_score": 50,
        "risk_reasoning": "Local fallback analysis used conservative heuristics.",
        "risk_alerts": [],
        "recommendation": "review",
        "summary": "Local fallback analysis produced a conservative underwriting summary.",
        "document_type_detected": document_type,
        "confidence_notes": confidence_notes,
    }


def _recommendation_for_risk(risk_score: float) -> str:
    if risk_score < 40:
        return "approve"
    if risk_score <= 70:
        return "review"
    return "reject"


def _finalize_payload(payload: dict, alerts: list[dict], reasoning: list[str]) -> dict:
    risk_score = max(0, min(100, round(float(payload["risk_score"]), 1)))
    payload["risk_score"] = risk_score
    payload["risk_alerts"] = alerts
    payload["recommendation"] = _recommendation_for_risk(risk_score)
    payload["risk_reasoning"] = " ".join(reasoning)
    payload["summary"] = " ".join(reasoning[:2]) if reasoning else payload["summary"]
    return payload


def _salary_slip_fallback(text: str) -> LocalAnalysisFallback:
    payload = _base_payload(
        "salary_slip",
        "Deterministic local fallback used because the AI provider was unavailable. Verify figures against the payslip.",
    )
    net_salary = _extract_first_amount(text, ["net salary", "net pay", "take home", "take-home pay", "payable salary"])
    gross_salary = _extract_first_amount(text, ["gross salary", "gross pay", "gross earnings", "total earnings"])
    deductions = _extract_first_amount(text, ["total deductions", "deductions", "employee deductions"])
    existing_emis = _extract_first_amount(text, ["emi", "loan deduction", "loan emi", "emi deduction"])
    applicant_name = _extract_first_text_line(
        text,
        ["employee name", "name of employee", "employee"],
    )
    employer_name = _extract_first_text_line(text, ["employer name", "company name", "organization", "employer"])
    tenure_years = _extract_employment_tenure_years(text)

    monthly_income = net_salary or gross_salary
    annual_income = round(monthly_income * 12, 2) if monthly_income else None
    dti = round(existing_emis / monthly_income, 3) if existing_emis and monthly_income else None

    payload.update(
        {
            "applicant_name": applicant_name,
            "monthly_income": monthly_income,
            "annual_income": annual_income,
            "monthly_expenses": deductions,
            "debt_to_income_ratio": dti,
            "employment_type": "salaried",
            "employment_tenure_years": tenure_years,
            "employer_name": employer_name,
            "existing_emis": existing_emis,
        }
    )

    risk_score = 26.0
    alerts: list[dict] = []
    reasoning = [
        "Salary-slip fallback extracted employment and payroll fields using deterministic rules.",
    ]

    if not monthly_income:
        risk_score += 25
        alerts.append(
            {
                "severity": "high",
                "message": "Monthly income could not be extracted",
                "field": "monthly_income",
                "details": "The salary slip did not expose a clear net or gross pay amount to the local parser.",
            }
        )
        reasoning.append("Income evidence is incomplete, so the result remains conservative.")
    else:
        reasoning.append(f"Estimated monthly income is Rs {monthly_income:,.0f}.")
        if monthly_income < 20000:
            risk_score += 10
            alerts.append(
                {
                    "severity": "medium",
                    "message": "Low monthly salary detected",
                    "field": "monthly_income",
                    "details": f"Estimated monthly income of Rs {monthly_income:,.0f} is on the lower side for unsecured lending.",
                }
            )

    if employer_name:
        reasoning.append(f"Employer identified as {employer_name}.")
    else:
        risk_score += 5
        alerts.append(
            {
                "severity": "low",
                "message": "Employer name was not confidently identified",
                "field": "employer_name",
                "details": "The local parser could not find a clear employer/company field in the salary slip.",
            }
        )

    if tenure_years is not None and tenure_years < 1:
        risk_score += 12
        alerts.append(
            {
                "severity": "medium",
                "message": "Short employment tenure",
                "field": "employment_tenure_years",
                "details": f"Employment tenure appears to be {tenure_years:.2f} years, which is below one year.",
            }
        )

    if dti is not None:
        if dti > 0.5:
            risk_score += 22
            alerts.append(
                {
                    "severity": "high",
                    "message": "High EMI burden against salary",
                    "field": "debt_to_income_ratio",
                    "details": f"EMI-to-income ratio is approximately {dti:.1%}, which is materially above safe underwriting levels.",
                }
            )
        elif dti > 0.35:
            risk_score += 14
            alerts.append(
                {
                    "severity": "medium",
                    "message": "EMI burden above preferred range",
                    "field": "debt_to_income_ratio",
                    "details": f"EMI-to-income ratio is approximately {dti:.1%}.",
                }
            )

    payload["risk_score"] = risk_score
    return LocalAnalysisFallback(
        document_type="salary_slip",
        raw_json=_finalize_payload(payload, alerts, reasoning),
        model_used="local-fallback-salary-slip",
    )


def _tax_return_fallback(text: str) -> LocalAnalysisFallback:
    payload = _base_payload(
        "tax_return",
        "Deterministic local fallback used because the AI provider was unavailable. Review declared income against the filing.",
    )
    annual_income = _extract_first_amount(
        text,
        [
            "gross total income",
            "total income",
            "gross income",
            "taxable income",
            "income from salary",
            "profits and gains of business or profession",
            "income from business or profession",
        ],
    )
    existing_emis = _extract_first_amount(text, ["emi", "loan repayment", "monthly installment"])
    applicant_name = _extract_first_text_line(
        text,
        ["name of assessee", "assessee name", "taxpayer name", "name"],
    )

    lowered = text.lower()
    employment_type = "business" if "business or profession" in lowered or "proprietor" in lowered else "self_employed"
    monthly_income = round(annual_income / 12.0, 2) if annual_income else None
    dti = round(existing_emis / monthly_income, 3) if existing_emis and monthly_income else None

    payload.update(
        {
            "applicant_name": applicant_name,
            "monthly_income": monthly_income,
            "annual_income": annual_income,
            "debt_to_income_ratio": dti,
            "employment_type": employment_type,
            "existing_emis": existing_emis,
        }
    )

    risk_score = 38.0
    alerts: list[dict] = []
    reasoning = [
        "Tax-return fallback extracted declared annual income from filing-style labels.",
    ]

    if not annual_income:
        risk_score += 22
        alerts.append(
            {
                "severity": "high",
                "message": "Declared annual income could not be extracted",
                "field": "annual_income",
                "details": "The local parser could not identify a reliable total-income figure in the return.",
            }
        )
        reasoning.append("Missing declared income keeps the result in manual-review territory.")
    else:
        reasoning.append(f"Estimated annual income is Rs {annual_income:,.0f}.")
        if annual_income < 300000:
            risk_score += 10
            alerts.append(
                {
                    "severity": "medium",
                    "message": "Low declared annual income",
                    "field": "annual_income",
                    "details": f"Declared income of Rs {annual_income:,.0f} may indicate limited repayment headroom.",
                }
            )

    if employment_type in {"self_employed", "business"}:
        risk_score += 5
        alerts.append(
            {
                "severity": "low",
                "message": "Income appears self-employed or business-linked",
                "field": "employment_type",
                "details": "Business/profession income can be more variable than fixed payroll income and may need extra validation.",
            }
        )

    if dti is not None and dti > 0.35:
        risk_score += 14 if dti <= 0.5 else 22
        alerts.append(
            {
                "severity": "high" if dti > 0.5 else "medium",
                "message": "Existing obligations are high relative to declared income",
                "field": "debt_to_income_ratio",
                "details": f"Estimated EMI-to-income ratio is approximately {dti:.1%}.",
            }
        )

    payload["risk_score"] = risk_score
    return LocalAnalysisFallback(
        document_type="tax_return",
        raw_json=_finalize_payload(payload, alerts, reasoning),
        model_used="local-fallback-tax-return",
    )


def _income_proof_fallback(text: str) -> LocalAnalysisFallback:
    payload = _base_payload(
        "income_proof",
        "Deterministic local fallback used because the AI provider was unavailable. Validate the issuer and recurrence of the income proof.",
    )
    monthly_income = _extract_first_amount(
        text,
        [
            "monthly income",
            "average monthly income",
            "net monthly income",
            "salary credited",
            "income credited",
            "monthly salary",
        ],
    )
    annual_income = _extract_first_amount(text, ["annual income", "yearly income", "annual salary"])
    issuer_name = _extract_first_text_line(text, ["employer", "company", "organization", "issuer", "payer"])
    existing_emis = _extract_first_amount(text, ["emi", "loan repayment", "monthly installment"])

    lowered = text.lower()
    if "salary" in lowered or "employee" in lowered:
        employment_type = "salaried"
    elif "business" in lowered or "proprietor" in lowered or "profession" in lowered:
        employment_type = "self_employed"
    else:
        employment_type = None

    if annual_income is None and monthly_income is not None:
        annual_income = round(monthly_income * 12.0, 2)
    if monthly_income is None and annual_income is not None:
        monthly_income = round(annual_income / 12.0, 2)

    dti = round(existing_emis / monthly_income, 3) if existing_emis and monthly_income else None

    payload.update(
        {
            "monthly_income": monthly_income,
            "annual_income": annual_income,
            "debt_to_income_ratio": dti,
            "employment_type": employment_type,
            "employer_name": issuer_name,
            "existing_emis": existing_emis,
        }
    )

    risk_score = 32.0
    alerts: list[dict] = []
    reasoning = [
        "Income-proof fallback extracted the clearest recurring-income fields available in the document.",
    ]

    if not monthly_income and not annual_income:
        risk_score += 24
        alerts.append(
            {
                "severity": "high",
                "message": "Income amount could not be extracted",
                "field": "monthly_income",
                "details": "The local parser could not locate a reliable monthly or annual income value.",
            }
        )
    elif monthly_income and monthly_income < 20000:
        risk_score += 10
        alerts.append(
            {
                "severity": "medium",
                "message": "Low income level detected",
                "field": "monthly_income",
                "details": f"Estimated monthly income is Rs {monthly_income:,.0f}.",
            }
        )

    if not issuer_name:
        risk_score += 8
        alerts.append(
            {
                "severity": "medium",
                "message": "Income source was not clearly identified",
                "field": "employer_name",
                "details": "The document did not expose a clear employer, issuer, or payer field to the local parser.",
            }
        )
    else:
        reasoning.append(f"Income source appears to be {issuer_name}.")

    if dti is not None and dti > 0.35:
        risk_score += 14 if dti <= 0.5 else 22
        alerts.append(
            {
                "severity": "high" if dti > 0.5 else "medium",
                "message": "Obligation load appears elevated",
                "field": "debt_to_income_ratio",
                "details": f"Estimated EMI-to-income ratio is approximately {dti:.1%}.",
            }
        )

    payload["risk_score"] = risk_score
    return LocalAnalysisFallback(
        document_type="income_proof",
        raw_json=_finalize_payload(payload, alerts, reasoning),
        model_used="local-fallback-income-proof",
    )


def build_local_analysis_fallback(full_text: str, document_type_hint: str = "") -> LocalAnalysisFallback | None:
    document_type = infer_local_document_type(_normalize_text(full_text), document_type_hint)
    if not document_type:
        return None

    normalized_text = _normalize_text(full_text)
    if document_type == "salary_slip":
        return _salary_slip_fallback(normalized_text)
    if document_type == "tax_return":
        return _tax_return_fallback(normalized_text)
    if document_type == "income_proof":
        return _income_proof_fallback(normalized_text)
    return None


__all__ = [
    "ANALYSIS_LOCAL_FALLBACK_MIN_TEXT_LENGTH",
    "LocalAnalysisFallback",
    "SUPPORTED_LOCAL_DOCUMENT_TYPES",
    "build_local_analysis_fallback",
    "infer_local_document_type",
]
