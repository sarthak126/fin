from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.document_analysis_local_fallback import build_local_analysis_fallback
from services import gemini_service


SALARY_SLIP_TEXT = """
ACME PRIVATE LIMITED
Salary Slip - March 2026
Employer Name: ACME PRIVATE LIMITED
Employee Name: Test Analyst
Date of Joining: 01-01-2024
Gross Salary: Rs 75,000
Total Deductions: Rs 8,500
Net Pay: Rs 66,500
EMI Deduction: Rs 18,000
"""


TAX_RETURN_TEXT = """
Income Tax Return Acknowledgement
Assessment Year: 2025-26
Name: Test Trader
Profits and Gains of Business or Profession: Rs 9,60,000
Gross Total Income: Rs 12,00,000
"""


INCOME_PROOF_TEXT = """
Income Certificate
Issuer: Urban Finance Services
Average Monthly Income: Rs 42,000
Monthly installment: Rs 9,000
"""


def test_salary_slip_local_fallback_extracts_core_income_fields():
    fallback = build_local_analysis_fallback(SALARY_SLIP_TEXT, "salary_slip")

    assert fallback is not None
    assert fallback.document_type == "salary_slip"
    assert fallback.model_used == "local-fallback-salary-slip"
    assert fallback.raw_json["monthly_income"] == 66500.0
    assert fallback.raw_json["annual_income"] == 798000.0
    assert fallback.raw_json["monthly_expenses"] == 8500.0
    assert fallback.raw_json["existing_emis"] == 18000.0
    assert fallback.raw_json["applicant_name"] == "Test Analyst"
    assert fallback.raw_json["employment_type"] == "salaried"
    assert fallback.raw_json["employer_name"] == "ACME PRIVATE LIMITED"
    assert fallback.raw_json["debt_to_income_ratio"] == pytest.approx(0.271, abs=0.001)


def test_tax_return_local_fallback_extracts_declared_income():
    fallback = build_local_analysis_fallback(TAX_RETURN_TEXT, "tax_return")

    assert fallback is not None
    assert fallback.document_type == "tax_return"
    assert fallback.model_used == "local-fallback-tax-return"
    assert fallback.raw_json["applicant_name"] == "Test Trader"
    assert fallback.raw_json["annual_income"] == 1200000.0
    assert fallback.raw_json["monthly_income"] == 100000.0
    assert fallback.raw_json["employment_type"] == "business"
    assert fallback.raw_json["document_type_detected"] == "tax_return"


def test_income_proof_local_fallback_extracts_income_and_issuer():
    fallback = build_local_analysis_fallback(INCOME_PROOF_TEXT, "income_proof")

    assert fallback is not None
    assert fallback.document_type == "income_proof"
    assert fallback.model_used == "local-fallback-income-proof"
    assert fallback.raw_json["monthly_income"] == 42000.0
    assert fallback.raw_json["annual_income"] == 504000.0
    assert fallback.raw_json["employer_name"] == "Urban Finance Services"
    assert fallback.raw_json["existing_emis"] == 9000.0
    assert fallback.raw_json["debt_to_income_ratio"] == pytest.approx(0.214, abs=0.001)


@pytest.mark.asyncio
async def test_analyze_document_uses_local_fallback_when_gemini_is_unavailable(monkeypatch):
    monkeypatch.setattr(gemini_service.genai, "Client", lambda api_key: SimpleNamespace())

    async def fail_generate_content(*args, **kwargs):
        raise RuntimeError("503 UNAVAILABLE")

    monkeypatch.setattr(gemini_service, "_generate_content_with_retry", fail_generate_content)

    result = await gemini_service.analyze_document(
        document_id="doc_salary_fallback",
        full_text=SALARY_SLIP_TEXT,
        document_type="salary_slip",
        use_rag=False,
    )

    assert result.success is True
    assert result.model_used == "local-fallback-salary-slip"
    assert result.raw_json["monthly_income"] == 66500.0
