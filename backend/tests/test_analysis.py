from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.bank_statement_score import build_bank_statement_score_payload
from core.confidence import build_decision_payload
from models import DocumentStatus
from services import analysis_service
from services.extraction_service import OcrQualityInsufficientError
from tests.sample_bank_statement_fixture import (
    load_short_history_sample_expected,
    load_short_history_sample_text,
)

_BANK_STATEMENT_SIGNAL_TEXT = """
STATEMENT OF ACCOUNT
Account Number: XXXXXXXX6604
Customer Name: Jane Applicant
Branch Name: Main Branch
IFSC Code: HDFC0000123
MICR Code: 400240011

DATE     PARTICULARS               WITHDRAWALS     DEPOSITS      BALANCE
01-04-26 B/F                                                     23,039.51
03-04-26 UPI/SHOP/0001               1,240.00                    21,799.51
05-04-26 Salary Credit ACME                         50,000.00    71,799.51
08-04-26 ATM WDL                       500.00                    71,299.51
"""


def _make_bank_statement_score(risk_score: int) -> dict[str, int | str]:
    remaining = max(0, int(risk_score))
    components: dict[str, int] = {}
    for key, cap in (
        ("income_stability", 20),
        ("balance_health", 20),
        ("obligation_load", 15),
        ("spending_discipline", 15),
        ("cash_behavior", 15),
        ("risk_penalty", 15),
    ):
        component = min(cap, remaining)
        components[key] = component
        remaining -= component

    if remaining > 0:
        components["risk_penalty"] += remaining

    return build_bank_statement_score_payload(**components)


def _make_extracted_doc(**overrides):
    data = {
        "file_type": "application/pdf",
        "total_text": "salary and transaction data",
        "total_pages": 3,
        "scanned_pages": 0,
        "extraction_schema_version": 2,
        "extraction_status": "complete",
        "ocr_required_pages": [],
        "ocr_provider": None,
        "ocr_failed_pages": [],
        "ocr_unreliable_pages": [],
        "ocr_fallback_used": False,
        "metadata": {},
    }
    data.update(overrides)
    payload = {
        "file_type": data["file_type"],
        "pages": [],
        "total_text": data["total_text"],
        "total_pages": data["total_pages"],
        "scanned_pages": data["scanned_pages"],
        "extraction_schema_version": data["extraction_schema_version"],
        "extraction_status": data["extraction_status"],
        "ocr_required_pages": data["ocr_required_pages"],
        "ocr_failed_pages": data["ocr_failed_pages"],
        "ocr_unreliable_pages": data["ocr_unreliable_pages"],
        "ocr_fallback_used": data["ocr_fallback_used"],
        "ocr_provider": data["ocr_provider"],
        "metadata": data["metadata"],
    }
    return SimpleNamespace(**data, to_dict=lambda: payload)


def test_canonicalize_insight_payloads_skips_recanonicalizing_canonical_payloads(monkeypatch):
    canonical_decision = build_decision_payload(
        decision_status="manual_review",
        decision_reason="Needs review.",
        extraction_confidence=0.7,
        risk_confidence=0.7,
        data_completeness=0.7,
        required_followups=["Review supporting documents."],
        analysis_limitations=[],
    )
    canonical_payload = {"decision": dict(canonical_decision)}
    insights = SimpleNamespace(
        summary="Needs review.",
        analysis_limitations=[],
        confidence=0.7,
        recommendation="review",
        extracted_fields=dict(canonical_payload),
        raw_response=dict(canonical_payload),
    )
    canonicalize_calls: list[object] = []

    def _record_call(*args, **kwargs):
        canonicalize_calls.append((args, kwargs))
        return args[0]

    monkeypatch.setattr(analysis_service, "canonicalize_analysis_payload", _record_call)

    analysis_service._canonicalize_insight_payloads(insights)

    assert canonicalize_calls == []
    assert insights.decision["decision_status"] == "manual_review"
    assert insights.extracted_fields["decision"]["decision_reason"] == "Needs review."


def _make_bank_statement_payload(
    *,
    decision_status: str,
    decision_recommendation: str,
    decision_reason: str,
    extraction_confidence: float,
    risk_confidence: float,
    risk_score: int,
    narrative: list[str],
    flags: list[str] | None = None,
):
    return {
        "decision": {
            "decision_status": decision_status,
            "decision_recommendation": decision_recommendation,
            "decision_reason": decision_reason,
            "extraction_confidence": extraction_confidence,
            "risk_confidence": risk_confidence,
            "data_completeness": extraction_confidence,
            "required_followups": [],
            "analysis_limitations": [],
        },
        "statement_summary": {},
        "transaction_insights": {
            "statement_confidence": extraction_confidence,
        },
        "risk_findings": {
            "flags": flags or [],
            "risk_score": _make_bank_statement_score(risk_score),
        },
        "reasoning": {
            "summary": decision_reason,
            "narrative": narrative,
            "required_followups": [],
            "analysis_limitations": [],
        },
        "transactions": [],
    }


@pytest.mark.asyncio
async def test_trigger_analysis_promotes_other_statement_and_routes_to_bank_pipeline(monkeypatch):
    fake_document = SimpleNamespace(
        id="doc_bank_promote_129",
        file_url="secure://doc_bank_promote_129.pdf",
        file_type="application/pdf",
        original_filename="XXXXXXXXXX6604_masked.pdf",
        document_type="other",
    )
    fake_extracted_doc = _make_extracted_doc(
        total_text=_BANK_STATEMENT_SIGNAL_TEXT,
        total_pages=2,
    )
    fake_analysis_record = SimpleNamespace(id="analysis_129")
    fake_db = SimpleNamespace(
        document=SimpleNamespace(update=AsyncMock()),
        analysis=SimpleNamespace(create=AsyncMock(return_value=fake_analysis_record)),
    )
    final_json = _make_bank_statement_payload(
        decision_status="approve",
        decision_recommendation="Proceed with approval.",
        decision_reason="Stable inflows and balances.",
        extraction_confidence=0.94,
        risk_confidence=1.0,
        risk_score=37,
        narrative=["Decision: APPROVE", "  -> Stable inflows and balances."],
    )

    monkeypatch.setattr(analysis_service, "retrieve_password_for_file", AsyncMock(return_value=""))
    monkeypatch.setattr(analysis_service, "load_extraction_artifact_for_file", AsyncMock(return_value=None))
    monkeypatch.setattr(analysis_service, "extract_document_content", AsyncMock(return_value=fake_extracted_doc))
    monkeypatch.setattr(analysis_service, "save_extraction_artifact_for_file", AsyncMock(return_value="secure://artifact"))
    chunk_document_mock = AsyncMock()
    store_document_chunks_mock = AsyncMock()
    analyze_document_mock = AsyncMock()
    monkeypatch.setattr(analysis_service, "chunk_document", chunk_document_mock)
    monkeypatch.setattr(analysis_service, "store_document_chunks", store_document_chunks_mock)
    monkeypatch.setattr(analysis_service, "analyze_document", analyze_document_mock)
    monkeypatch.setattr(
        analysis_service,
        "run_strict_bank_statement_pipeline",
        AsyncMock(return_value=final_json),
    )
    monkeypatch.setattr(analysis_service, "delete_password_for_file", AsyncMock(return_value=None))

    result = await analysis_service.trigger_analysis(db=fake_db, document=fake_document)

    assert result is fake_analysis_record
    assert fake_db.document.update.await_args_list[0].kwargs == {
        "where": {"id": "doc_bank_promote_129"},
        "data": {"status": DocumentStatus.PROCESSING.value},
    }
    assert fake_db.document.update.await_args_list[1].kwargs == {
        "where": {"id": "doc_bank_promote_129"},
        "data": {"document_type": "bank_statement"},
    }
    assert fake_db.document.update.await_args_list[2].kwargs == {
        "where": {"id": "doc_bank_promote_129"},
        "data": {"status": DocumentStatus.ANALYZED.value},
    }
    create_args = fake_db.analysis.create.await_args.kwargs["data"]
    assert create_args["confidence"] == 1.0
    assert json.loads(create_args["extracted_fields"])["decision"]["risk_confidence"] == 1.0
    analysis_service.run_strict_bank_statement_pipeline.assert_awaited_once_with(
        raw_text=_BANK_STATEMENT_SIGNAL_TEXT,
        document_type_hint="bank_statement",
    )
    chunk_document_mock.assert_not_awaited()
    store_document_chunks_mock.assert_not_awaited()
    analyze_document_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_trigger_analysis_promotes_obfuscated_sample_filename_and_routes_to_bank_pipeline(monkeypatch):
    expected = load_short_history_sample_expected()
    fake_document = SimpleNamespace(
        id="doc_bank_sample_fixture",
        file_url="secure://doc_bank_sample_fixture.pdf",
        file_type="application/pdf",
        original_filename=expected["original_filename"],
        document_type="other",
    )
    fake_extracted_doc = _make_extracted_doc(
        total_text=load_short_history_sample_text(),
        total_pages=2,
    )
    fake_analysis_record = SimpleNamespace(id="analysis_sample_fixture")
    fake_db = SimpleNamespace(
        document=SimpleNamespace(update=AsyncMock()),
        analysis=SimpleNamespace(create=AsyncMock(return_value=fake_analysis_record)),
    )
    final_json = _make_bank_statement_payload(
        decision_status=expected["decision_status"],
        decision_recommendation=expected["decision_recommendation"],
        decision_reason=expected["decision_reason"],
        extraction_confidence=expected["statement_confidence"],
        risk_confidence=0.4,
        risk_score=52,
        narrative=[
            "Decision: INSUFFICIENT_HISTORY",
            f"  -> {expected['decision_reason']}",
        ],
    )

    monkeypatch.setattr(analysis_service, "retrieve_password_for_file", AsyncMock(return_value=""))
    monkeypatch.setattr(analysis_service, "load_extraction_artifact_for_file", AsyncMock(return_value=None))
    monkeypatch.setattr(analysis_service, "extract_document_content", AsyncMock(return_value=fake_extracted_doc))
    monkeypatch.setattr(analysis_service, "save_extraction_artifact_for_file", AsyncMock(return_value="secure://artifact"))
    chunk_document_mock = AsyncMock()
    store_document_chunks_mock = AsyncMock()
    analyze_document_mock = AsyncMock()
    monkeypatch.setattr(analysis_service, "chunk_document", chunk_document_mock)
    monkeypatch.setattr(analysis_service, "store_document_chunks", store_document_chunks_mock)
    monkeypatch.setattr(analysis_service, "analyze_document", analyze_document_mock)
    monkeypatch.setattr(
        analysis_service,
        "run_strict_bank_statement_pipeline",
        AsyncMock(return_value=final_json),
    )
    monkeypatch.setattr(analysis_service, "delete_password_for_file", AsyncMock(return_value=None))

    result = await analysis_service.trigger_analysis(db=fake_db, document=fake_document)

    assert result is fake_analysis_record
    assert fake_db.document.update.await_args_list[1].kwargs == {
        "where": {"id": "doc_bank_sample_fixture"},
        "data": {"document_type": "bank_statement"},
    }
    analysis_service.run_strict_bank_statement_pipeline.assert_awaited_once_with(
        raw_text=load_short_history_sample_text(),
        document_type_hint="bank_statement",
    )
    chunk_document_mock.assert_not_awaited()
    store_document_chunks_mock.assert_not_awaited()
    analyze_document_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_trigger_analysis_persists_bank_statement_results(monkeypatch):
    fake_document = SimpleNamespace(
        id="doc_bank_123",
        file_url="secure://doc_bank_123.pdf",
        file_type="application/pdf",
        original_filename="statement.pdf",
        document_type="bank_statement",
    )
    fake_extracted_doc = _make_extracted_doc()
    fake_analysis_record = SimpleNamespace(id="analysis_123")
    fake_db = SimpleNamespace(
        document=SimpleNamespace(update=AsyncMock()),
        analysis=SimpleNamespace(create=AsyncMock(return_value=fake_analysis_record)),
    )
    final_json = _make_bank_statement_payload(
        decision_status="manual_review",
        decision_recommendation="Manual review is recommended before approval.",
        decision_reason="EMI obligations remain elevated.",
        extraction_confidence=0.91,
        risk_confidence=0.6,
        risk_score=42,
        narrative=["Decision: APPROVE WITH CAUTION", "  -> EMI obligations remain elevated."],
        flags=["High DTI.", "Duplicate-looking transactions present."],
    )
    final_json["risk_findings"]["explainable_risk"] = {
        "total_risk_score": 99,
        "risk_level": "very_high",
        "risk_breakdown": {},
        "max_possible_risk": 100,
    }

    monkeypatch.setattr(analysis_service, "retrieve_password_for_file", AsyncMock(return_value="pdf-password"))
    monkeypatch.setattr(analysis_service, "load_extraction_artifact_for_file", AsyncMock(return_value=None))
    monkeypatch.setattr(analysis_service, "extract_document_content", AsyncMock(return_value=fake_extracted_doc))
    monkeypatch.setattr(analysis_service, "save_extraction_artifact_for_file", AsyncMock(return_value="secure://artifact"))
    chunk_document_mock = AsyncMock()
    store_document_chunks_mock = AsyncMock()
    monkeypatch.setattr(analysis_service, "chunk_document", chunk_document_mock)
    monkeypatch.setattr(analysis_service, "store_document_chunks", store_document_chunks_mock)
    monkeypatch.setattr(
        analysis_service,
        "run_strict_bank_statement_pipeline",
        AsyncMock(return_value=final_json),
    )
    monkeypatch.setattr(analysis_service, "delete_password_for_file", AsyncMock(return_value=None))

    result = await analysis_service.trigger_analysis(db=fake_db, document=fake_document)

    assert result is fake_analysis_record
    assert fake_db.document.update.await_count == 2
    assert fake_db.document.update.await_args_list[0].kwargs == {
        "where": {"id": "doc_bank_123"},
        "data": {"status": DocumentStatus.PROCESSING.value},
    }
    assert fake_db.document.update.await_args_list[1].kwargs == {
        "where": {"id": "doc_bank_123"},
        "data": {"status": DocumentStatus.ANALYZED.value},
    }

    create_args = fake_db.analysis.create.await_args.kwargs["data"]
    assert create_args["document_id"] == "doc_bank_123"
    assert create_args["risk_score"] == 42
    assert create_args["confidence"] == 0.6
    assert create_args["recommendation"] == "review"
    assert create_args["decision_status"] == "manual_review"
    assert create_args["model_used"] == "bank-statement-deterministic"
    persisted_payload = json.loads(create_args["extracted_fields"])
    assert persisted_payload["decision"]["risk_confidence"] == 0.6
    assert persisted_payload["risk_findings"]["risk_score"]["score_model"] == "bank_statement_v2"
    assert json.loads(create_args["analysis_limitations_json"]) == []
    assert "Decision: APPROVE WITH CAUTION" in create_args["summary"]
    chunk_document_mock.assert_not_awaited()
    store_document_chunks_mock.assert_not_awaited()

    analysis_service.extract_document_content.assert_awaited_once_with(
        "secure://doc_bank_123.pdf",
        "application/pdf",
        password="pdf-password",
        progress_callback=None,
    )
    analysis_service.save_extraction_artifact_for_file.assert_awaited_once()
    analysis_service.run_strict_bank_statement_pipeline.assert_awaited_once_with(
        raw_text="salary and transaction data",
        document_type_hint="bank_statement",
    )
    analysis_service.delete_password_for_file.assert_awaited_once_with("secure://doc_bank_123.pdf")


@pytest.mark.asyncio
async def test_trigger_analysis_keeps_explicit_non_bank_type_authoritative(monkeypatch):
    fake_document = SimpleNamespace(
        id="doc_salary_130",
        file_url="secure://doc_salary_130.pdf",
        file_type="application/pdf",
        original_filename="salary-slip.pdf",
        document_type="salary_slip",
    )
    fake_extracted_doc = _make_extracted_doc(
        total_text=_BANK_STATEMENT_SIGNAL_TEXT,
        total_pages=2,
    )
    fake_analysis_record = SimpleNamespace(id="analysis_130")
    fake_db = SimpleNamespace(
        document=SimpleNamespace(update=AsyncMock()),
        analysis=SimpleNamespace(create=AsyncMock(return_value=fake_analysis_record)),
    )
    fake_gemini_result = SimpleNamespace(
        success=True,
        error="",
        model_used="gemini-test",
        raw_json={"summary": "structured output"},
    )
    fake_insights = SimpleNamespace(
        risk_score=26,
        confidence=0.81,
        recommendation="review",
        extracted_fields={"document_type_detected": "salary_slip"},
        raw_response={"document_type_detected": "salary_slip"},
        risk_alerts=[],
        summary="Salary slip analysis summary.",
        model_used="gemini-test",
    )

    monkeypatch.setattr(analysis_service, "retrieve_password_for_file", AsyncMock(return_value=""))
    monkeypatch.setattr(analysis_service, "load_extraction_artifact_for_file", AsyncMock(return_value=None))
    monkeypatch.setattr(analysis_service, "extract_document_content", AsyncMock(return_value=fake_extracted_doc))
    monkeypatch.setattr(analysis_service, "save_extraction_artifact_for_file", AsyncMock(return_value="secure://artifact"))
    monkeypatch.setattr(analysis_service, "chunk_document", lambda extracted_doc: ["chunk-1"])
    monkeypatch.setattr(analysis_service, "store_document_chunks", lambda document_id, chunks: len(chunks))
    monkeypatch.setattr(analysis_service, "analyze_document", AsyncMock(return_value=fake_gemini_result))
    monkeypatch.setattr(analysis_service, "process_analysis", lambda raw_gemini_output, model_used: fake_insights)
    run_bank_pipeline_mock = AsyncMock()
    monkeypatch.setattr(analysis_service, "run_strict_bank_statement_pipeline", run_bank_pipeline_mock)
    monkeypatch.setattr(analysis_service, "delete_password_for_file", AsyncMock(return_value=None))

    result = await analysis_service.trigger_analysis(db=fake_db, document=fake_document)

    assert result is fake_analysis_record
    assert fake_db.document.update.await_count == 2
    assert fake_db.document.update.await_args_list[0].kwargs == {
        "where": {"id": "doc_salary_130"},
        "data": {"status": DocumentStatus.PROCESSING.value},
    }
    assert fake_db.document.update.await_args_list[1].kwargs == {
        "where": {"id": "doc_salary_130"},
        "data": {"status": DocumentStatus.ANALYZED.value},
    }
    run_bank_pipeline_mock.assert_not_awaited()
    analysis_service.analyze_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_analysis_persists_provisional_case_analysis_for_supported_case_documents(monkeypatch):
    fake_document = SimpleNamespace(
        id="doc_salary_case_131",
        case_id="case_test_123",
        org_id="org_test_456",
        file_url="secure://doc_salary_case_131.pdf",
        file_type="application/pdf",
        original_filename="salary-slip.pdf",
        document_type="salary_slip",
    )
    fake_extracted_doc = _make_extracted_doc(total_text="salary slip text", total_pages=1)
    fake_analysis_record = SimpleNamespace(id="analysis_131")
    fake_db = SimpleNamespace(
        document=SimpleNamespace(update=AsyncMock()),
        analysis=SimpleNamespace(create=AsyncMock(return_value=fake_analysis_record)),
    )
    fake_gemini_result = SimpleNamespace(
        success=True,
        error="",
        model_used="gemini-test",
        raw_json={"summary": "structured output"},
    )
    fake_insights = SimpleNamespace(
        risk_score=21,
        confidence=0.84,
        recommendation="approve",
        extracted_fields={"monthly_income": 68000},
        raw_response={"monthly_income": 68000},
        risk_alerts=[],
        summary="Salary slip looks consistent.",
        model_used="gemini-test",
    )
    persist_case_analysis_mock = AsyncMock(return_value=None)

    monkeypatch.setattr(analysis_service, "retrieve_password_for_file", AsyncMock(return_value=""))
    monkeypatch.setattr(analysis_service, "load_extraction_artifact_for_file", AsyncMock(return_value=None))
    monkeypatch.setattr(analysis_service, "extract_document_content", AsyncMock(return_value=fake_extracted_doc))
    monkeypatch.setattr(analysis_service, "save_extraction_artifact_for_file", AsyncMock(return_value="secure://artifact"))
    monkeypatch.setattr(analysis_service, "chunk_document", lambda extracted_doc: ["chunk-1"])
    monkeypatch.setattr(analysis_service, "store_document_chunks", lambda document_id, chunks: len(chunks))
    monkeypatch.setattr(analysis_service, "analyze_document", AsyncMock(return_value=fake_gemini_result))
    monkeypatch.setattr(analysis_service, "process_analysis", lambda raw_gemini_output, model_used: fake_insights)
    monkeypatch.setattr(
        analysis_service,
        "persist_provisional_case_analysis_for_document",
        persist_case_analysis_mock,
    )
    monkeypatch.setattr(analysis_service, "delete_password_for_file", AsyncMock(return_value=None))

    result = await analysis_service.trigger_analysis(db=fake_db, document=fake_document)

    assert result is fake_analysis_record
    assert fake_db.document.update.await_args_list[1].kwargs == {
        "where": {"id": "doc_salary_case_131"},
        "data": {"status": DocumentStatus.ANALYZED.value},
    }
    persist_case_analysis_mock.assert_awaited_once_with(
        db=fake_db,
        document=fake_document,
    )


@pytest.mark.asyncio
async def test_trigger_analysis_marks_document_failed_when_no_text_is_extracted(monkeypatch):
    fake_document = SimpleNamespace(
        id="doc_bank_124",
        file_url="secure://doc_bank_124.pdf",
        file_type="application/pdf",
        original_filename="statement-empty.pdf",
        document_type="bank_statement",
    )
    fake_extracted_doc = _make_extracted_doc(total_text="   ", total_pages=1, scanned_pages=0)
    fake_db = SimpleNamespace(
        document=SimpleNamespace(update=AsyncMock()),
        analysis=SimpleNamespace(create=AsyncMock()),
    )

    monkeypatch.setattr(analysis_service, "retrieve_password_for_file", AsyncMock(return_value=""))
    monkeypatch.setattr(analysis_service, "load_extraction_artifact_for_file", AsyncMock(return_value=None))
    monkeypatch.setattr(analysis_service, "extract_document_content", AsyncMock(return_value=fake_extracted_doc))
    monkeypatch.setattr(analysis_service, "save_extraction_artifact_for_file", AsyncMock(return_value="secure://artifact"))
    monkeypatch.setattr(analysis_service, "delete_password_for_file", AsyncMock(return_value=None))

    with pytest.raises(ValueError, match="No text could be extracted"):
        await analysis_service.trigger_analysis(db=fake_db, document=fake_document)

    assert fake_db.document.update.await_args_list[0].kwargs == {
        "where": {"id": "doc_bank_124"},
        "data": {"status": DocumentStatus.PROCESSING.value},
    }
    assert fake_db.document.update.await_args_list[1].kwargs == {
        "where": {"id": "doc_bank_124"},
        "data": {"status": DocumentStatus.FAILED.value},
    }
    fake_db.analysis.create.assert_not_awaited()
    analysis_service.delete_password_for_file.assert_awaited_once_with("secure://doc_bank_124.pdf")


@pytest.mark.asyncio
async def test_trigger_analysis_marks_document_failed_when_gemini_analysis_fails(monkeypatch):
    fake_document = SimpleNamespace(
        id="doc_other_125",
        file_url="secure://doc_other_125.pdf",
        file_type="application/pdf",
        original_filename="id-proof.pdf",
        document_type="id_document",
    )
    fake_extracted_doc = _make_extracted_doc(total_text="valid extracted text", total_pages=2)
    fake_db = SimpleNamespace(
        document=SimpleNamespace(update=AsyncMock()),
        analysis=SimpleNamespace(create=AsyncMock()),
    )
    fake_gemini_result = SimpleNamespace(
        success=False,
        error="model unavailable",
        model_used="gemini-test",
        raw_json={},
    )

    monkeypatch.setattr(analysis_service, "retrieve_password_for_file", AsyncMock(return_value=""))
    monkeypatch.setattr(analysis_service, "load_extraction_artifact_for_file", AsyncMock(return_value=None))
    monkeypatch.setattr(analysis_service, "extract_document_content", AsyncMock(return_value=fake_extracted_doc))
    monkeypatch.setattr(analysis_service, "save_extraction_artifact_for_file", AsyncMock(return_value="secure://artifact"))
    monkeypatch.setattr(analysis_service, "chunk_document", lambda extracted_doc: ["chunk-1"])
    monkeypatch.setattr(analysis_service, "store_document_chunks", lambda document_id, chunks: len(chunks))
    monkeypatch.setattr(analysis_service, "analyze_document", AsyncMock(return_value=fake_gemini_result))
    monkeypatch.setattr(analysis_service, "delete_password_for_file", AsyncMock(return_value=None))

    with pytest.raises(RuntimeError, match="Gemini analysis failed: model unavailable"):
        await analysis_service.trigger_analysis(db=fake_db, document=fake_document)

    assert fake_db.document.update.await_args_list[0].kwargs == {
        "where": {"id": "doc_other_125"},
        "data": {"status": DocumentStatus.PROCESSING.value},
    }
    assert fake_db.document.update.await_args_list[1].kwargs == {
        "where": {"id": "doc_other_125"},
        "data": {"status": DocumentStatus.FAILED.value},
    }
    fake_db.analysis.create.assert_not_awaited()
    analysis_service.delete_password_for_file.assert_awaited_once_with("secure://doc_other_125.pdf")


@pytest.mark.asyncio
async def test_trigger_analysis_continues_without_rag_when_vector_storage_fails(monkeypatch):
    fake_document = SimpleNamespace(
        id="doc_other_126",
        file_url="secure://doc_other_126.pdf",
        file_type="application/pdf",
        original_filename="salary-slip.pdf",
        document_type="salary_slip",
    )
    fake_extracted_doc = _make_extracted_doc(total_text="salary slip text", total_pages=1)
    fake_analysis_record = SimpleNamespace(id="analysis_126")
    fake_db = SimpleNamespace(
        document=SimpleNamespace(update=AsyncMock()),
        analysis=SimpleNamespace(create=AsyncMock(return_value=fake_analysis_record)),
    )
    fake_gemini_result = SimpleNamespace(
        success=True,
        error="",
        model_used="gemini-test",
        raw_json={"summary": "structured output"},
    )
    fake_insights = SimpleNamespace(
        risk_score=18,
        confidence=0.92,
        recommendation="approve",
        extracted_fields={"monthly_income": 50000},
        raw_response={"monthly_income": 50000},
        risk_alerts=[],
        summary="Low risk salary profile.",
        model_used="gemini-test",
    )

    monkeypatch.setattr(analysis_service, "retrieve_password_for_file", AsyncMock(return_value=""))
    monkeypatch.setattr(analysis_service, "load_extraction_artifact_for_file", AsyncMock(return_value=None))
    monkeypatch.setattr(analysis_service, "extract_document_content", AsyncMock(return_value=fake_extracted_doc))
    monkeypatch.setattr(analysis_service, "save_extraction_artifact_for_file", AsyncMock(return_value="secure://artifact"))
    monkeypatch.setattr(analysis_service, "chunk_document", lambda extracted_doc: ["chunk-1"])
    monkeypatch.setattr(
        analysis_service,
        "store_document_chunks",
        lambda document_id, chunks: (_ for _ in ()).throw(RuntimeError("503 UNAVAILABLE")),
    )
    analyze_document_mock = AsyncMock(return_value=fake_gemini_result)
    monkeypatch.setattr(analysis_service, "analyze_document", analyze_document_mock)
    monkeypatch.setattr(analysis_service, "process_analysis", lambda raw_gemini_output, model_used: fake_insights)
    monkeypatch.setattr(analysis_service, "delete_password_for_file", AsyncMock(return_value=None))

    result = await analysis_service.trigger_analysis(db=fake_db, document=fake_document)

    assert result is fake_analysis_record
    assert analyze_document_mock.await_args.kwargs["use_rag"] is False
    assert fake_db.document.update.await_args_list[1].kwargs == {
        "where": {"id": "doc_other_126"},
        "data": {"status": DocumentStatus.ANALYZED.value},
    }


@pytest.mark.asyncio
async def test_trigger_analysis_blocks_unreliable_ocr_before_local_fallback(monkeypatch):
    fake_document = SimpleNamespace(
        id="doc_salary_sparse_127",
        file_url="secure://doc_salary_sparse_127.pdf",
        file_type="application/pdf",
        original_filename="salary-slip-scan.pdf",
        document_type="salary_slip",
    )
    fake_extracted_doc = _make_extracted_doc(
        total_text=" ",
        total_pages=1,
        scanned_pages=0,
        extraction_status="unreliable",
        ocr_required_pages=[1],
        ocr_provider=None,
        ocr_failed_pages=[],
        ocr_unreliable_pages=[1],
        ocr_fallback_used=True,
        metadata={
            "title": "",
            "author": "",
            "subject": "",
            "ocr_required_pages": [1],
            "ocr_required_page_count": 1,
            "ocr_unreliable_pages": [1],
            "ocr_unreliable_page_count": 1,
            "ocr_fallback_used": True,
            "extraction_status": "unreliable",
            "extraction_schema_version": 2,
        },
    )
    fake_db = SimpleNamespace(
        document=SimpleNamespace(update=AsyncMock()),
        analysis=SimpleNamespace(create=AsyncMock()),
    )

    monkeypatch.setattr(analysis_service, "retrieve_password_for_file", AsyncMock(return_value=""))
    monkeypatch.setattr(analysis_service, "load_extraction_artifact_for_file", AsyncMock(return_value=None))
    monkeypatch.setattr(analysis_service, "extract_document_content", AsyncMock(return_value=fake_extracted_doc))
    save_artifact_mock = AsyncMock(return_value="secure://artifact")
    monkeypatch.setattr(analysis_service, "save_extraction_artifact_for_file", save_artifact_mock)
    chunk_document_mock = AsyncMock()
    store_document_chunks_mock = AsyncMock()
    analyze_document_mock = AsyncMock()
    monkeypatch.setattr(analysis_service, "chunk_document", chunk_document_mock)
    monkeypatch.setattr(analysis_service, "store_document_chunks", store_document_chunks_mock)
    monkeypatch.setattr(analysis_service, "analyze_document", analyze_document_mock)
    monkeypatch.setattr(analysis_service, "delete_password_for_file", AsyncMock(return_value=None))

    with pytest.raises(OcrQualityInsufficientError, match="OCR quality is insufficient"):
        await analysis_service.trigger_analysis(db=fake_db, document=fake_document)

    chunk_document_mock.assert_not_awaited()
    store_document_chunks_mock.assert_not_awaited()
    analyze_document_mock.assert_not_awaited()
    assert fake_db.document.update.await_args_list[1].kwargs == {
        "where": {"id": "doc_salary_sparse_127"},
        "data": {"status": DocumentStatus.FAILED.value},
    }
    fake_db.analysis.create.assert_not_awaited()
    save_artifact_mock.assert_awaited_once()
    analysis_service.delete_password_for_file.assert_awaited_once_with("secure://doc_salary_sparse_127.pdf")


@pytest.mark.asyncio
async def test_trigger_analysis_persists_partial_artifact_when_extraction_raises_ocr_quality_error(monkeypatch):
    fake_document = SimpleNamespace(
        id="doc_salary_sparse_raised_128",
        file_url="secure://doc_salary_sparse_raised_128.pdf",
        file_type="application/pdf",
        original_filename="salary-slip-scan.pdf",
        document_type="salary_slip",
    )
    partial_extracted_doc = _make_extracted_doc(
        total_text=" ",
        total_pages=1,
        scanned_pages=0,
        extraction_status="failed",
        ocr_required_pages=[1],
        ocr_failed_pages=[1],
        ocr_unreliable_pages=[],
        ocr_fallback_used=False,
        metadata={
            "ocr_required_pages": [1],
            "ocr_required_page_count": 1,
            "ocr_failed_pages": [1],
            "ocr_failed_page_count": 1,
            "extraction_status": "failed",
            "extraction_schema_version": 2,
        },
    )
    fake_db = SimpleNamespace(
        document=SimpleNamespace(update=AsyncMock()),
        analysis=SimpleNamespace(create=AsyncMock()),
    )

    monkeypatch.setattr(analysis_service, "retrieve_password_for_file", AsyncMock(return_value=""))
    monkeypatch.setattr(analysis_service, "load_extraction_artifact_for_file", AsyncMock(return_value=None))
    monkeypatch.setattr(
        analysis_service,
        "extract_document_content",
        AsyncMock(side_effect=OcrQualityInsufficientError(partial_extracted_doc)),
    )
    save_artifact_mock = AsyncMock(return_value="secure://artifact")
    monkeypatch.setattr(analysis_service, "save_extraction_artifact_for_file", save_artifact_mock)
    monkeypatch.setattr(analysis_service, "delete_password_for_file", AsyncMock(return_value=None))

    with pytest.raises(OcrQualityInsufficientError, match="OCR quality is insufficient"):
        await analysis_service.trigger_analysis(db=fake_db, document=fake_document)

    assert fake_db.document.update.await_args_list[1].kwargs == {
        "where": {"id": "doc_salary_sparse_raised_128"},
        "data": {"status": DocumentStatus.FAILED.value},
    }
    fake_db.analysis.create.assert_not_awaited()
    save_artifact_mock.assert_awaited_once()
    analysis_service.delete_password_for_file.assert_awaited_once_with("secure://doc_salary_sparse_raised_128.pdf")


@pytest.mark.asyncio
async def test_trigger_analysis_reuses_saved_extraction_artifact(monkeypatch):
    fake_document = SimpleNamespace(
        id="doc_reuse_128",
        file_url="secure://doc_reuse_128.pdf",
        file_type="application/pdf",
        original_filename="salary-slip.pdf",
        document_type="salary_slip",
    )
    artifact = {
        "file_type": "application/pdf",
        "pages": [
            {
                "page_num": 1,
                "text": "saved extracted text",
                "source_kind": "native_text",
                "ocr_provider": None,
                "ocr_confidence": None,
            }
        ],
        "total_text": "--- Page 1 ---\nsaved extracted text",
        "total_pages": 1,
        "scanned_pages": 0,
        "extraction_schema_version": 2,
        "extraction_status": "complete",
        "ocr_required_pages": [],
        "ocr_failed_pages": [],
        "ocr_unreliable_pages": [],
        "ocr_fallback_used": False,
        "ocr_provider": None,
        "metadata": {},
    }
    fake_analysis_record = SimpleNamespace(id="analysis_128")
    fake_db = SimpleNamespace(
        document=SimpleNamespace(update=AsyncMock()),
        analysis=SimpleNamespace(create=AsyncMock(return_value=fake_analysis_record)),
    )
    fake_gemini_result = SimpleNamespace(
        success=True,
        error="",
        model_used="gemini-test",
        raw_json={"summary": "structured output"},
    )
    fake_insights = SimpleNamespace(
        risk_score=24,
        confidence=0.88,
        recommendation="approve",
        extracted_fields={"monthly_income": 72000},
        raw_response={"monthly_income": 72000},
        risk_alerts=[],
        summary="Artifact reuse summary.",
        model_used="gemini-test",
    )

    monkeypatch.setattr(analysis_service, "retrieve_password_for_file", AsyncMock(return_value=""))
    monkeypatch.setattr(analysis_service, "load_extraction_artifact_for_file", AsyncMock(return_value=artifact))
    extract_document_content_mock = AsyncMock()
    save_artifact_mock = AsyncMock()
    monkeypatch.setattr(analysis_service, "extract_document_content", extract_document_content_mock)
    monkeypatch.setattr(analysis_service, "save_extraction_artifact_for_file", save_artifact_mock)
    monkeypatch.setattr(analysis_service, "chunk_document", lambda extracted_doc: ["chunk-1"])
    monkeypatch.setattr(analysis_service, "store_document_chunks", lambda document_id, chunks: len(chunks))
    monkeypatch.setattr(analysis_service, "analyze_document", AsyncMock(return_value=fake_gemini_result))
    monkeypatch.setattr(analysis_service, "process_analysis", lambda raw_gemini_output, model_used: fake_insights)
    monkeypatch.setattr(analysis_service, "delete_password_for_file", AsyncMock(return_value=None))

    result = await analysis_service.trigger_analysis(db=fake_db, document=fake_document)

    assert result is fake_analysis_record
    extract_document_content_mock.assert_not_awaited()
    save_artifact_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_trigger_analysis_rebuilds_old_schema_saved_extraction_artifact(monkeypatch):
    fake_document = SimpleNamespace(
        id="doc_rebuild_old_schema_129",
        file_url="secure://doc_rebuild_old_schema_129.pdf",
        file_type="application/pdf",
        original_filename="salary-slip.pdf",
        document_type="salary_slip",
    )
    artifact = {
        "file_type": "application/pdf",
        "pages": [
            {
                "page_num": 1,
                "text": "legacy extracted text",
                "source_kind": "native_text",
                "ocr_provider": None,
                "ocr_confidence": None,
            }
        ],
        "total_text": "--- Page 1 ---\nlegacy extracted text",
        "total_pages": 1,
        "scanned_pages": 0,
        "ocr_required_pages": [],
        "ocr_failed_pages": [],
        "ocr_unreliable_pages": [],
        "ocr_fallback_used": False,
        "ocr_provider": None,
        "metadata": {},
    }
    rebuilt_doc = _make_extracted_doc(total_text="rebuilt extracted text", total_pages=1)
    fake_analysis_record = SimpleNamespace(id="analysis_rebuild_old_schema_129")
    fake_db = SimpleNamespace(
        document=SimpleNamespace(update=AsyncMock()),
        analysis=SimpleNamespace(create=AsyncMock(return_value=fake_analysis_record)),
    )
    fake_gemini_result = SimpleNamespace(
        success=True,
        error="",
        model_used="gemini-test",
        raw_json={"summary": "structured output"},
    )
    fake_insights = SimpleNamespace(
        risk_score=28,
        confidence=0.78,
        recommendation="review",
        extracted_fields={"monthly_income": 72000},
        raw_response={"monthly_income": 72000},
        risk_alerts=[],
        summary="Rebuilt artifact summary.",
        model_used="gemini-test",
    )

    monkeypatch.setattr(analysis_service, "retrieve_password_for_file", AsyncMock(return_value=""))
    monkeypatch.setattr(analysis_service, "load_extraction_artifact_for_file", AsyncMock(return_value=artifact))
    extract_document_content_mock = AsyncMock(return_value=rebuilt_doc)
    save_artifact_mock = AsyncMock(return_value="secure://artifact")
    monkeypatch.setattr(analysis_service, "extract_document_content", extract_document_content_mock)
    monkeypatch.setattr(analysis_service, "save_extraction_artifact_for_file", save_artifact_mock)
    monkeypatch.setattr(analysis_service, "chunk_document", lambda extracted_doc: ["chunk-1"])
    monkeypatch.setattr(analysis_service, "store_document_chunks", lambda document_id, chunks: len(chunks))
    monkeypatch.setattr(analysis_service, "analyze_document", AsyncMock(return_value=fake_gemini_result))
    monkeypatch.setattr(analysis_service, "process_analysis", lambda raw_gemini_output, model_used: fake_insights)
    monkeypatch.setattr(analysis_service, "delete_password_for_file", AsyncMock(return_value=None))

    result = await analysis_service.trigger_analysis(db=fake_db, document=fake_document)

    assert result is fake_analysis_record
    extract_document_content_mock.assert_awaited_once()
    save_artifact_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_analysis_rebuilds_unreliable_saved_extraction_artifact(monkeypatch):
    fake_document = SimpleNamespace(
        id="doc_rebuild_unreliable_130",
        file_url="secure://doc_rebuild_unreliable_130.pdf",
        file_type="application/pdf",
        original_filename="salary-slip.pdf",
        document_type="salary_slip",
    )
    artifact = {
        "file_type": "application/pdf",
        "pages": [
            {
                "page_num": 1,
                "text": "unsafe OCR text",
                "source_kind": "ocr_unreliable",
                "ocr_provider": "document_ai",
                "ocr_confidence": 0.42,
            }
        ],
        "total_text": "",
        "total_pages": 1,
        "scanned_pages": 0,
        "extraction_schema_version": 2,
        "extraction_status": "unreliable",
        "ocr_required_pages": [1],
        "ocr_failed_pages": [],
        "ocr_unreliable_pages": [1],
        "ocr_fallback_used": False,
        "ocr_provider": "document_ai",
        "metadata": {
            "extraction_status": "unreliable",
            "extraction_schema_version": 2,
        },
    }
    rebuilt_doc = _make_extracted_doc(total_text="rebuilt reliable text", total_pages=1)
    fake_analysis_record = SimpleNamespace(id="analysis_rebuild_unreliable_130")
    fake_db = SimpleNamespace(
        document=SimpleNamespace(update=AsyncMock()),
        analysis=SimpleNamespace(create=AsyncMock(return_value=fake_analysis_record)),
    )
    fake_gemini_result = SimpleNamespace(
        success=True,
        error="",
        model_used="gemini-test",
        raw_json={"summary": "structured output"},
    )
    fake_insights = SimpleNamespace(
        risk_score=22,
        confidence=0.9,
        recommendation="approve",
        extracted_fields={"monthly_income": 68000},
        raw_response={"monthly_income": 68000},
        risk_alerts=[],
        summary="Rebuilt unreliable artifact summary.",
        model_used="gemini-test",
    )

    monkeypatch.setattr(analysis_service, "retrieve_password_for_file", AsyncMock(return_value=""))
    monkeypatch.setattr(analysis_service, "load_extraction_artifact_for_file", AsyncMock(return_value=artifact))
    extract_document_content_mock = AsyncMock(return_value=rebuilt_doc)
    save_artifact_mock = AsyncMock(return_value="secure://artifact")
    monkeypatch.setattr(analysis_service, "extract_document_content", extract_document_content_mock)
    monkeypatch.setattr(analysis_service, "save_extraction_artifact_for_file", save_artifact_mock)
    monkeypatch.setattr(analysis_service, "chunk_document", lambda extracted_doc: ["chunk-1"])
    monkeypatch.setattr(analysis_service, "store_document_chunks", lambda document_id, chunks: len(chunks))
    monkeypatch.setattr(analysis_service, "analyze_document", AsyncMock(return_value=fake_gemini_result))
    monkeypatch.setattr(analysis_service, "process_analysis", lambda raw_gemini_output, model_used: fake_insights)
    monkeypatch.setattr(analysis_service, "delete_password_for_file", AsyncMock(return_value=None))

    result = await analysis_service.trigger_analysis(db=fake_db, document=fake_document)

    assert result is fake_analysis_record
    extract_document_content_mock.assert_awaited_once()
    save_artifact_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_analysis_for_document_raises_for_unknown_document(monkeypatch):
    fake_prisma_db = SimpleNamespace(
        document=SimpleNamespace(find_unique=AsyncMock(return_value=None)),
    )
    monkeypatch.setattr(analysis_service, "prisma_db", fake_prisma_db)

    with pytest.raises(ValueError, match="Document missing_doc not found"):
        await analysis_service.run_analysis_for_document("missing_doc")


@pytest.mark.asyncio
async def test_run_analysis_for_document_skips_when_analysis_already_exists(monkeypatch):
    fake_document = SimpleNamespace(
        id="doc_done_126",
        status=DocumentStatus.ANALYZED.value,
    )
    fake_prisma_db = SimpleNamespace(
        document=SimpleNamespace(find_unique=AsyncMock(return_value=fake_document)),
    )

    monkeypatch.setattr(analysis_service, "prisma_db", fake_prisma_db)
    monkeypatch.setattr(
        analysis_service,
        "get_analysis_by_document",
        AsyncMock(return_value=SimpleNamespace(id="analysis_done_126")),
    )
    trigger_analysis_mock = AsyncMock(return_value=SimpleNamespace(id="analysis_done_126"))
    monkeypatch.setattr(analysis_service, "trigger_analysis", trigger_analysis_mock)

    result = await analysis_service.run_analysis_for_document("doc_done_126")

    assert result == "already_analyzed"
    trigger_analysis_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_analysis_for_document_force_reanalysis_bypasses_skip(monkeypatch):
    fake_document = SimpleNamespace(
        id="doc_done_force_127",
        status=DocumentStatus.ANALYZED.value,
        case_id="case_test_123",
        org_id="org_test_456",
        document_type="bank_statement",
    )
    fake_prisma_db = SimpleNamespace(
        document=SimpleNamespace(find_unique=AsyncMock(return_value=fake_document)),
    )

    monkeypatch.setattr(analysis_service, "prisma_db", fake_prisma_db)
    monkeypatch.setattr(
        analysis_service,
        "get_analysis_by_document",
        AsyncMock(return_value=SimpleNamespace(id="analysis_done_force_127")),
    )
    prepare_case_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        analysis_service,
        "prepare_case_for_forced_document_reanalysis",
        prepare_case_mock,
    )
    trigger_analysis_mock = AsyncMock(return_value=SimpleNamespace(id="analysis_new_force_127"))
    monkeypatch.setattr(analysis_service, "trigger_analysis", trigger_analysis_mock)

    result = await analysis_service.run_analysis_for_document(
        "doc_done_force_127",
        force_reanalysis=True,
    )

    assert result == "completed"
    prepare_case_mock.assert_awaited_once_with(
        db=fake_prisma_db,
        document=fake_document,
    )
    trigger_analysis_mock.assert_awaited_once_with(
        db=fake_prisma_db,
        document=fake_document,
        progress_callback=None,
    )
