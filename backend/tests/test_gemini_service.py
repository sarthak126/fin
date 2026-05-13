from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import gemini_service


@pytest.mark.asyncio
async def test_generate_content_with_retry_retries_transient_provider_errors(monkeypatch):
    class FakeModels:
        def __init__(self):
            self.calls = 0

        def generate_content(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("503 UNAVAILABLE")
            return SimpleNamespace(text="OK")

    fake_models = FakeModels()
    fake_client = SimpleNamespace(models=fake_models)
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float):
        sleep_calls.append(seconds)

    monkeypatch.setattr(gemini_service.asyncio, "sleep", fake_sleep)

    response = await gemini_service._generate_content_with_retry(
        fake_client,
        model="models/gemini-2.5-flash",
        contents="hello",
        retries=2,
    )

    assert response.text == "OK"
    assert fake_models.calls == 2
    assert sleep_calls


@pytest.mark.asyncio
async def test_ask_about_document_uses_saved_analysis_when_vectors_are_missing(monkeypatch):
    saved_payload = {
        "decision": {
            "decision_status": "manual_review",
            "decision_reason": "Stable salary credits with moderate EMI load.",
        },
        "statement_summary": {},
        "transaction_insights": {
            "balance": {"average": 48000, "min": 12000},
            "expenses": {"emi": 18000},
        },
        "risk_findings": {"risk_score": {"final_score": 61}},
        "reasoning": {
            "summary": "Stable salary credits with moderate EMI load.",
            "narrative": [],
            "required_followups": [],
            "analysis_limitations": [],
        },
        "transactions": [
            {
                "date": "2024-01-05",
                "description": "SALARY CREDIT ACME LTD",
                "credit": 60000,
                "debit": None,
                "category": "VERIFIED_INCOME",
                "notes": "Recurring employer credit",
            }
        ],
    }
    fake_analysis = SimpleNamespace(
        raw_response=json.dumps(saved_payload),
        extracted_fields=None,
        summary="Stable salary credits with moderate EMI load.",
        recommendation="review",
        risk_score=61,
        model_used="bank-statement-deterministic",
    )
    fake_db = SimpleNamespace(
        analysis=SimpleNamespace(find_first=AsyncMock(return_value=fake_analysis)),
    )

    monkeypatch.setattr(gemini_service, "retrieve_relevant_chunks", lambda *args, **kwargs: [])
    monkeypatch.setattr(gemini_service, "prisma_db", fake_db)
    monkeypatch.setattr(
        gemini_service,
        "get_settings",
        lambda: SimpleNamespace(GOOGLE_API_KEY="test-key", GEMINI_MODEL="gemini-test"),
    )
    monkeypatch.setattr(gemini_service.genai, "Client", lambda api_key: SimpleNamespace())
    monkeypatch.setattr(
        gemini_service,
        "_generate_content_with_retry",
        AsyncMock(return_value=SimpleNamespace(text="Average balance is INR 48,000 and the minimum balance is INR 12,000.")),
    )

    result = await gemini_service.ask_about_document(
        document_id="doc_bank_qa_123",
        question="What is the average balance?",
    )

    assert "Average balance is INR 48,000" in result["answer"]
    assert result["sources"] == [
        {"section_title": "Executive Summary", "page_num": 0},
        {"section_title": "Structured Analysis", "page_num": 0},
        {"section_title": "Relevant Transactions", "page_num": 0},
    ]
    fake_db.analysis.find_first.assert_awaited_once_with(
        where={"document_id": "doc_bank_qa_123"},
        order={"created_at": "desc"},
    )


@pytest.mark.asyncio
async def test_ask_about_document_falls_back_to_local_saved_answer_when_provider_generation_fails(monkeypatch):
    saved_payload = {
        "decision": {
            "decision_status": "manual_review",
            "decision_reason": "Stable salary credits with moderate EMI load.",
        },
        "statement_summary": {},
        "transaction_insights": {
            "balance": {"average": 48000, "min": 12000},
        },
        "risk_findings": {"risk_score": {"final_score": 61}},
        "reasoning": {
            "summary": "Stable salary credits with moderate EMI load.",
            "narrative": [],
            "required_followups": [],
            "analysis_limitations": [],
        },
    }
    fake_analysis = SimpleNamespace(
        raw_response=json.dumps(saved_payload),
        extracted_fields=None,
        summary="Stable salary credits with moderate EMI load.",
        recommendation="review",
        risk_score=61,
        model_used="bank-statement-deterministic",
    )
    fake_db = SimpleNamespace(
        analysis=SimpleNamespace(find_first=AsyncMock(return_value=fake_analysis)),
    )

    def raise_vector_failure(*args, **kwargs):
        raise RuntimeError("embedding provider offline")

    monkeypatch.setattr(gemini_service, "retrieve_relevant_chunks", raise_vector_failure)
    monkeypatch.setattr(gemini_service, "prisma_db", fake_db)
    monkeypatch.setattr(
        gemini_service,
        "get_settings",
        lambda: SimpleNamespace(GOOGLE_API_KEY="test-key", GEMINI_MODEL="gemini-test"),
    )
    monkeypatch.setattr(gemini_service.genai, "Client", lambda api_key: SimpleNamespace())
    monkeypatch.setattr(
        gemini_service,
        "_generate_content_with_retry",
        AsyncMock(side_effect=RuntimeError("503 UNAVAILABLE")),
    )

    result = await gemini_service.ask_about_document(
        document_id="doc_bank_qa_456",
        question="What is the average balance?",
    )

    assert "average balance of INR 48,000" in result["answer"]
    assert "risk score is 61/100" in result["answer"]
