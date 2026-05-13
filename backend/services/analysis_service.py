"""
Analysis service.

This module orchestrates document extraction, chunking, vector storage, AI
analysis, and persistence. Deterministic bank-statement scoring lives in
`bank_statement_pipeline.py` so this file stays focused on workflow control.
"""

import asyncio
import json
import re
import time
import uuid
from types import SimpleNamespace
from typing import Awaitable, Callable, Dict, List

from prisma import Prisma
from prisma.models import Analysis, Document

from core.confidence import (
    build_risk_alerts_from_flags,
    build_summary_from_decision,
    canonicalize_analysis_payload,
    extract_canonical_decision,
    extract_decision_risk_confidence,
    normalize_confidence,
    normalize_decision_status,
    recommendation_from_decision_status,
)
from core.config import get_settings
from core.database import db as prisma_db
from models import DocumentStatus, DocumentType
from services.bank_statement_local_parser import extract_bank_transactions_locally
from services.bank_statement_pipeline import (
    build_bank_statement_output,
    run_strict_bank_statement_pipeline,
)
from services.case_analysis_service import (
    persist_provisional_case_analysis_for_document,
    prepare_case_for_forced_document_reanalysis,
)
from services.chunking_service import chunk_document
from services.document_analysis_local_fallback import (
    SUPPORTED_LOCAL_DOCUMENT_TYPES,
    build_local_analysis_fallback,
)
from services.extraction_service import (
    EXTRACTION_SCHEMA_VERSION,
    EXTRACTION_STATUS_COMPLETE,
    ExtractedDocument,
    OcrQualityInsufficientError,
    extract_document_content,
    raise_for_unresolved_ocr_quality,
)
from services.gemini_service import analyze_document
from services.insight_engine import process_analysis
from services.storage_service import (
    delete_password_for_file,
    load_extraction_artifact_for_file,
    retrieve_password_for_file,
    save_extraction_artifact_for_file,
)
from services.vector_service import store_document_chunks

JobProgressCallback = Callable[..., Awaitable[None] | None]

_STATEMENT_HEADER_PATTERNS = (
    r"\bstatement of account\b",
    r"\baccount statement\b",
    r"\bbank statement\b",
    r"\bstatement period\b",
    r"\bstatement summary\b",
)
_ACCOUNT_DETAIL_PATTERNS = (
    r"\baccount number\b",
    r"\baccount no\b",
    r"\ba/c number\b",
    r"\ba/c no\b",
    r"\baccount name\b",
    r"\bcustomer id\b",
    r"\bcustomer name\b",
    r"\bbranch name\b",
    r"\bbranch address\b",
)
_TRANSACTION_COLUMN_PATTERNS = (
    r"\bdate\b.*\b(?:particulars|narration|description|transaction details?)\b.*\b(?:withdrawals?|debit)\b.*\b(?:deposits?|credit)\b.*\bbalance\b",
    r"\bdate\b.*\b(?:particulars|narration|description|transaction details?)\b.*\bamount\b.*\bbalance\b",
)


def _map_recommendation(decision) -> str:
    if isinstance(decision, dict):
        decision = (
            decision.get("decision_status")
            or decision.get("verdict")
            or decision.get("decision")
            or decision.get("recommendation")
        )
    return recommendation_from_decision_status(normalize_decision_status(decision))


def _build_risk_alerts(flags: List[str]) -> List[Dict[str, str]]:
    return build_risk_alerts_from_flags(flags)


def _build_sparse_extraction_context(document: Document, extracted_doc) -> str:
    parts: list[str] = []

    if extracted_doc.total_text.strip():
        parts.append(extracted_doc.total_text.strip())

    metadata = getattr(extracted_doc, "metadata", {}) or {}
    title = metadata.get("title")
    subject = metadata.get("subject")
    author = metadata.get("author")
    if title:
        parts.append(f"Document title: {title}")
    if subject:
        parts.append(f"Document subject: {subject}")
    if author:
        parts.append(f"Document author: {author}")

    if getattr(document, "original_filename", None):
        parts.append(f"Filename: {document.original_filename}")
    if getattr(document, "document_type", None):
        parts.append(f"Document type hint: {document.document_type}")

    scanned_pages = getattr(extracted_doc, "scanned_pages", 0) or 0
    if scanned_pages:
        parts.append(f"Scanned pages detected: {scanned_pages}")

    unreliable_pages = list(getattr(extracted_doc, "ocr_unreliable_pages", []) or [])
    if unreliable_pages:
        parts.append(
            "Unreliable OCR pages: "
            + ", ".join(str(page_num) for page_num in unreliable_pages)
        )

    if getattr(extracted_doc, "ocr_fallback_used", False):
        parts.append("OCR fallback provider was used during extraction.")

    return "\n".join(part for part in parts if part).strip()


def _detect_bank_statement_signals(text: str) -> dict[str, object]:
    normalized_text = (text or "").strip()
    if not normalized_text:
        return {
            "should_promote": False,
            "score": 0,
            "reasons": [],
            "transaction_count": 0,
        }

    collapsed_text = re.sub(r"\s+", " ", normalized_text.lower())
    reasons: list[str] = []
    score = 0

    statement_header = any(re.search(pattern, collapsed_text) for pattern in _STATEMENT_HEADER_PATTERNS)
    if statement_header:
        reasons.append("statement header")
        score += 3

    account_detail_hits = sum(1 for pattern in _ACCOUNT_DETAIL_PATTERNS if re.search(pattern, collapsed_text))
    account_details = account_detail_hits >= 2
    if account_details:
        reasons.append("account details")
        score += 2

    bank_codes = any(code in collapsed_text for code in ("ifsc", "micr"))
    if bank_codes:
        reasons.append("IFSC/MICR")
        score += 2

    balance_columns = any(re.search(pattern, collapsed_text) for pattern in _TRANSACTION_COLUMN_PATTERNS)
    if balance_columns:
        reasons.append("debit/credit/balance columns")
        score += 2

    transaction_count = len(extract_bank_transactions_locally(normalized_text))
    transaction_table = transaction_count >= 3
    if transaction_table:
        reasons.append(f"transaction table ({transaction_count} rows)")
        score += 3
    elif transaction_count >= 2:
        reasons.append(f"transaction-like rows ({transaction_count})")
        score += 2

    should_promote = score >= 5 and len(reasons) >= 2 and (
        statement_header or balance_columns or transaction_table
    )
    return {
        "should_promote": should_promote,
        "score": score,
        "reasons": reasons,
        "transaction_count": transaction_count,
    }


async def _maybe_promote_bank_statement_document_type(
    *,
    db: Prisma,
    document: Document,
    extracted_doc: ExtractedDocument,
) -> str:
    current_type = ((document.document_type or "").strip().lower() or DocumentType.OTHER.value)
    if current_type != DocumentType.OTHER.value:
        return current_type

    detection = _detect_bank_statement_signals(getattr(extracted_doc, "total_text", "") or "")
    if not detection["should_promote"]:
        return current_type

    promoted_type = DocumentType.BANK_STATEMENT.value
    signal_summary = ", ".join(detection["reasons"])
    print(
        "      Promoting document type from other to bank_statement "
        f"based on extracted statement signals: {signal_summary}"
    )
    await db.document.update(
        where={"id": document.id},
        data={"document_type": promoted_type},
    )
    try:
        document.document_type = promoted_type
    except Exception:
        pass
    return promoted_type


def _canonicalize_insight_payloads(insights) -> None:
    fallback_lines = [
        line.strip()
        for line in str(getattr(insights, "summary", "") or "").splitlines()
        if line.strip()
    ][:6]
    fallback_reason = fallback_lines[0] if fallback_lines else str(getattr(insights, "summary", "") or "")
    fallback_followups = fallback_lines[1:]
    fallback_limitations = list(getattr(insights, "analysis_limitations", []) or [])
    fallback_confidence = normalize_confidence(getattr(insights, "confidence", 0.0))

    extracted_fields = getattr(insights, "extracted_fields", {}) or {}
    raw_response = getattr(insights, "raw_response", {}) or {}

    def _has_canonical_decision(payload) -> bool:
        decision = payload.get("decision") if isinstance(payload, dict) else None
        return isinstance(decision, dict) and all(
            key in decision
            for key in (
                "decision_status",
                "decision_recommendation",
                "decision_reason",
                "extraction_confidence",
                "risk_confidence",
                "data_completeness",
                "required_followups",
                "analysis_limitations",
            )
        )

    if not _has_canonical_decision(extracted_fields):
        extracted_fields = canonicalize_analysis_payload(
            extracted_fields,
            fallback_verdict=getattr(insights, "recommendation", None),
            fallback_risk_confidence=fallback_confidence,
            fallback_reasons=fallback_lines,
            fallback_extraction_confidence=fallback_confidence,
            fallback_data_completeness=fallback_confidence,
            fallback_decision_reason=fallback_reason,
            fallback_required_followups=fallback_followups,
            fallback_analysis_limitations=fallback_limitations,
        )
    if not _has_canonical_decision(raw_response):
        raw_response = canonicalize_analysis_payload(
            raw_response,
            fallback_verdict=getattr(insights, "recommendation", None),
            fallback_risk_confidence=fallback_confidence,
            fallback_reasons=fallback_lines,
            fallback_extraction_confidence=fallback_confidence,
            fallback_data_completeness=fallback_confidence,
            fallback_decision_reason=fallback_reason,
            fallback_required_followups=fallback_followups,
            fallback_analysis_limitations=fallback_limitations,
        )
    decision = extract_canonical_decision(
        extracted_fields,
        fallback_status=getattr(insights, "recommendation", None),
        fallback_reason=fallback_reason,
        fallback_extraction_confidence=fallback_confidence,
        fallback_risk_confidence=fallback_confidence,
        fallback_data_completeness=fallback_confidence,
        fallback_required_followups=fallback_followups,
        fallback_analysis_limitations=fallback_limitations,
        fallback_reasons=fallback_lines,
    )

    extracted_fields["decision"] = dict(decision)
    raw_response["decision"] = dict(decision)
    insights.extracted_fields = extracted_fields
    insights.raw_response = raw_response
    insights.decision = decision
    insights.analysis_limitations = decision["analysis_limitations"]
    insights.recommendation = recommendation_from_decision_status(decision["decision_status"])
    insights.confidence = extract_decision_risk_confidence(extracted_fields, fallback=fallback_confidence)
    insights.summary = build_summary_from_decision(decision, getattr(insights, "summary", ""))


def _should_force_local_fallback(document_type: str, extracted_doc) -> bool:
    settings = get_settings()
    normalized_type = (document_type or "").strip().lower()
    if normalized_type not in SUPPORTED_LOCAL_DOCUMENT_TYPES:
        return False

    scanned_pages = getattr(extracted_doc, "scanned_pages", 0) or 0
    if scanned_pages <= 0:
        return False

    extracted_text = getattr(extracted_doc, "total_text", "") or ""
    return len(extracted_text.strip()) < settings.ANALYSIS_LOCAL_FALLBACK_MIN_TEXT_LENGTH


def _build_forced_local_fallback(document: Document, extracted_doc):
    fallback_seed_text = _build_sparse_extraction_context(document, extracted_doc)
    fallback = build_local_analysis_fallback(
        fallback_seed_text,
        (document.document_type or "").lower(),
    )
    if not fallback:
        return None

    print(
        "      [warn] Extraction was too sparse for scanned document OCR recovery; "
        f"using deterministic local fallback ({fallback.model_used})"
    )
    return SimpleNamespace(
        success=True,
        error="",
        model_used=fallback.model_used,
        raw_json=fallback.raw_json,
    )


async def _report_progress(callback: JobProgressCallback | None, **payload) -> None:
    if callback is None:
        return

    result = callback(**payload)
    if asyncio.iscoroutine(result):
        await result


def _ocr_progress_fields(extracted_doc: ExtractedDocument) -> dict[str, object]:
    return {
        "ocr_provider": extracted_doc.ocr_provider,
        "pages_processed": extracted_doc.total_pages,
        "total_pages": extracted_doc.total_pages,
        "ocr_required_pages": list(getattr(extracted_doc, "ocr_required_pages", []) or []),
        "ocr_failed_pages": list(getattr(extracted_doc, "ocr_failed_pages", []) or []),
        "ocr_unreliable_pages": list(getattr(extracted_doc, "ocr_unreliable_pages", []) or []),
        "ocr_fallback_used": bool(getattr(extracted_doc, "ocr_fallback_used", False)),
    }


def _artifact_schema_version(artifact: dict) -> int:
    try:
        return int(
            artifact.get(
                "extraction_schema_version",
                (artifact.get("metadata", {}) or {}).get("extraction_schema_version", 0),
            )
            or 0
        )
    except (TypeError, ValueError):
        return 0


def _artifact_extraction_status(artifact: dict, extracted_doc: ExtractedDocument) -> str:
    raw_status = str(
        artifact.get(
            "extraction_status",
            (artifact.get("metadata", {}) or {}).get("extraction_status", ""),
        )
        or ""
    ).strip().lower()
    if raw_status:
        return raw_status
    return str(getattr(extracted_doc, "extraction_status", "") or "").strip().lower()


def _extraction_artifact_rebuild_reason(artifact: dict) -> tuple[ExtractedDocument | None, str | None]:
    try:
        extracted_doc = ExtractedDocument.from_dict(artifact)
    except Exception:
        return None, "invalid artifact payload"

    schema_version = _artifact_schema_version(artifact)
    if schema_version != EXTRACTION_SCHEMA_VERSION:
        missing_or_old = "missing schema version" if schema_version <= 0 else f"schema v{schema_version}"
        return extracted_doc, f"{missing_or_old} requires rebuild"

    extraction_status = _artifact_extraction_status(artifact, extracted_doc)
    if extraction_status and extraction_status != EXTRACTION_STATUS_COMPLETE:
        return extracted_doc, f"{extraction_status} extraction artifact cannot be reused"

    if str(getattr(extracted_doc, "extraction_status", "") or "").strip().lower() != EXTRACTION_STATUS_COMPLETE:
        return extracted_doc, "artifact OCR state is not reusable"

    return extracted_doc, None


async def _load_or_create_extraction(
    *,
    document: Document,
    password: str,
    progress_callback: JobProgressCallback | None,
) -> ExtractedDocument:
    artifact = await load_extraction_artifact_for_file(document.file_url)
    if artifact:
        extracted_doc, rebuild_reason = _extraction_artifact_rebuild_reason(artifact)
        if rebuild_reason is None and extracted_doc is not None:
            await _report_progress(
                progress_callback,
                stage="extracting",
                stage_message="Loaded saved extraction artifact.",
                **_ocr_progress_fields(extracted_doc),
            )
            return extracted_doc

        await _report_progress(
            progress_callback,
            stage="extracting",
            stage_message=f"Saved extraction artifact found but will be rebuilt ({rebuild_reason}).",
            **_ocr_progress_fields(extracted_doc or ExtractedDocument(file_type=document.file_type)),
        )

    try:
        extracted_doc = await extract_document_content(
            document.file_url,
            document.file_type,
            password=password,
            progress_callback=progress_callback,
        )
    except OcrQualityInsufficientError as error:
        artifact_document = getattr(error, "extracted_document", None)
        if artifact_document is not None and hasattr(artifact_document, "to_dict"):
            await save_extraction_artifact_for_file(document.file_url, artifact_document.to_dict())
        raise

    await save_extraction_artifact_for_file(document.file_url, extracted_doc.to_dict())
    return extracted_doc


async def trigger_analysis(
    db: Prisma,
    document: Document,
    progress_callback: JobProgressCallback | None = None,
) -> Analysis:
    """
    Full AI analysis pipeline:

    1. Extract text from PDF
    2. Chunk the document semantically
    3. Store chunks as vectors
    4. Run the appropriate analysis pipeline
    5. Persist the result and update status
    """
    start_time = time.time()

    await db.document.update(
        where={"id": document.id},
        data={"status": DocumentStatus.PROCESSING.value},
    )

    is_pdf_document = (document.file_type or "").lower() == "application/pdf"

    try:
        pdf_password = ""
        if is_pdf_document:
            pdf_password = await retrieve_password_for_file(document.file_url)
        document_type = (document.document_type or "").lower()

        print(f"[1/5] Extracting text from {document.original_filename}...")
        extracted_doc = await _load_or_create_extraction(
            document=document,
            password=pdf_password,
            progress_callback=progress_callback,
        )
        raise_for_unresolved_ocr_quality(extracted_doc)

        document_type = await _maybe_promote_bank_statement_document_type(
            db=db,
            document=document,
            extracted_doc=extracted_doc,
        )

        forced_local_fallback = None
        if _should_force_local_fallback(document_type, extracted_doc):
            forced_local_fallback = _build_forced_local_fallback(document, extracted_doc)

        if not extracted_doc.total_text.strip() and forced_local_fallback is None:
            raise ValueError("No text could be extracted from the document.")

        print(
            f"      Extracted {len(extracted_doc.total_text)} chars from {extracted_doc.total_pages} pages "
            f"({extracted_doc.scanned_pages} accepted OCR pages, "
            f"{len(getattr(extracted_doc, 'ocr_required_pages', []) or [])} OCR-required, "
            f"{len(getattr(extracted_doc, 'ocr_failed_pages', []) or [])} failed, "
            f"{len(getattr(extracted_doc, 'ocr_unreliable_pages', []) or [])} unreliable)"
        )

        if document_type == "bank_statement":
            print("[2/5] Skipping chunk embeddings for deterministic bank statement analysis...")
            print("[3/5] Running local-first bank statement pipeline...")
            print(
                "      Routing to strict bank statement pipeline "
                "(local extraction/classification fallback + deterministic scoring)..."
            )
            await _report_progress(
                progress_callback,
                stage="analyzing",
                stage_message="Running deterministic bank statement analysis.",
                **_ocr_progress_fields(extracted_doc),
            )
            final_json = await run_strict_bank_statement_pipeline(
                raw_text=extracted_doc.total_text,
                document_type_hint=document_type,
            )
            raw_decision = final_json.get("decision")
            decision_verdict = raw_decision.get("decision_status") if isinstance(raw_decision, dict) else raw_decision
            insights = SimpleNamespace()
            insights.risk_score = ((final_json.get("risk_findings") or {}).get("risk_score") or {}).get(
                "final_score"
            ) or 0
            insights.confidence = extract_decision_risk_confidence(
                final_json,
                fallback=((final_json.get("transaction_insights") or {}).get("statement_confidence")),
            )
            insights.recommendation = _map_recommendation(final_json.get("decision") or decision_verdict)
            insights.extracted_fields = final_json
            insights.raw_response = final_json
            insights.risk_alerts = (
                ((final_json.get("risk_findings") or {}).get("alerts"))
                or _build_risk_alerts(((final_json.get("risk_findings") or {}).get("flags")) or [])
            )

            reasoning = final_json.get("reasoning") or {}
            narrative = reasoning.get("narrative") if isinstance(reasoning, dict) else []
            if isinstance(narrative, list) and narrative:
                insights.summary = "\n".join(narrative)
            else:
                insights.summary = str(
                    reasoning.get("summary")
                    if isinstance(reasoning, dict)
                    else ""
                )
            insights.model_used = "bank-statement-deterministic"
        else:
            if forced_local_fallback is not None:
                print("[2/5] Skipping chunking because scanned extraction was too sparse...")
                print("[3/5] Skipping vector storage for sparse local fallback analysis...")
                print("[4/5] Using deterministic local document analysis fallback...")
                await _report_progress(
                    progress_callback,
                    stage="analyzing",
                    stage_message="Running deterministic fallback for sparse OCR output.",
                    **_ocr_progress_fields(extracted_doc),
                )
                gemini_result = forced_local_fallback
            else:
                print("[2/5] Chunking document semantically...")
                await _report_progress(
                    progress_callback,
                    stage="chunking",
                    stage_message="Chunking normalized document text.",
                    **_ocr_progress_fields(extracted_doc),
                )
                chunks = await asyncio.to_thread(chunk_document, extracted_doc)
                print(f"      Created {len(chunks)} chunks")

                print("[3/5] Storing chunks in vector database...")
                await _report_progress(
                    progress_callback,
                    stage="vectorizing",
                    stage_message="Storing chunk embeddings for retrieval.",
                    **_ocr_progress_fields(extracted_doc),
                )
                use_rag = True
                try:
                    stored_count = await asyncio.to_thread(store_document_chunks, document.id, chunks)
                    print(f"      Stored {stored_count} chunks with embeddings")
                except Exception as vector_error:
                    use_rag = False
                    print(
                        "      [warn] Vector embedding storage failed; continuing without RAG "
                        f"for this analysis: {vector_error}"
                    )

                print("[4/5] Running analysis pipeline...")
                await _report_progress(
                    progress_callback,
                    stage="analyzing",
                    stage_message="Running Gemini semantic analysis on normalized text.",
                    **_ocr_progress_fields(extracted_doc),
                )
                gemini_result = await analyze_document(
                    document_id=document.id,
                    full_text=extracted_doc.total_text,
                    document_type=document_type,
                    use_rag=use_rag,
                )
            if not gemini_result.success:
                raise RuntimeError(f"Gemini analysis failed: {gemini_result.error}")

            print(f"      Gemini analysis complete (model: {gemini_result.model_used})")
            print("[5/5] Processing insights...")
            await _report_progress(
                progress_callback,
                stage="finalizing",
                stage_message="Finalizing insights and persisting analysis.",
                **_ocr_progress_fields(extracted_doc),
            )
            insights = await asyncio.to_thread(
                process_analysis,
                raw_gemini_output=gemini_result.raw_json,
                model_used=gemini_result.model_used,
            )

        _canonicalize_insight_payloads(insights)
        insights.confidence = normalize_confidence(insights.confidence)

        processing_time = time.time() - start_time
        print(
            f"      Risk Score: {insights.risk_score}/100 | "
            f"Recommendation: {insights.recommendation} | "
            f"Alerts: {len(insights.risk_alerts)} | "
            f"Time: {processing_time:.1f}s"
        )
        await _report_progress(
            progress_callback,
            stage="finalizing",
            stage_message="Persisting analysis results.",
            **_ocr_progress_fields(extracted_doc),
        )

        analysis = await db.analysis.create(
            data={
                "id": str(uuid.uuid4()),
                "document_id": document.id,
                "risk_score": insights.risk_score,
                "confidence": insights.confidence,
                "recommendation": insights.recommendation,
                "decision_status": insights.decision["decision_status"],
                "decision_recommendation": insights.decision["decision_recommendation"],
                "decision_reason": insights.decision["decision_reason"],
                "extraction_confidence": insights.decision["extraction_confidence"],
                "risk_confidence": insights.decision["risk_confidence"],
                "data_completeness": insights.decision["data_completeness"],
                "required_followups_json": json.dumps(insights.decision["required_followups"]),
                "analysis_limitations_json": json.dumps(insights.decision["analysis_limitations"]),
                "extracted_fields": json.dumps(insights.extracted_fields),
                "risk_alerts": json.dumps(insights.risk_alerts),
                "summary": insights.summary,
                "processing_time_seconds": round(processing_time, 2),
                "model_used": insights.model_used,
                "raw_response": json.dumps(insights.raw_response),
            }
        )

        await db.document.update(
            where={"id": document.id},
            data={"status": DocumentStatus.ANALYZED.value},
        )
        try:
            await persist_provisional_case_analysis_for_document(
                db=db,
                document=document,
            )
        except Exception as provisional_error:
            print(
                "[warn] Failed to persist provisional case analysis snapshot "
                f"for document {document.id}: {provisional_error}"
            )

        print(f"[ok] Analysis complete: {analysis.id}")
        return analysis

    except Exception as error:
        print(f"[error] Analysis failed: {error}")
        await db.document.update(
            where={"id": document.id},
            data={"status": DocumentStatus.FAILED.value},
        )
        raise error
    finally:
        if is_pdf_document:
            try:
                await delete_password_for_file(document.file_url)
            except Exception as cleanup_error:
                print(f"[warn] Failed to delete stored PDF password for {document.id}: {cleanup_error}")


async def get_analysis_by_id(db: Prisma, analysis_id: str) -> Analysis | None:
    return await db.analysis.find_unique(where={"id": analysis_id})


async def get_analysis_by_document(db: Prisma, document_id: str) -> Analysis | None:
    return await db.analysis.find_first(
        where={"document_id": document_id},
        order={"created_at": "desc"},
    )


async def run_analysis_for_stored_document(
    *,
    db: Prisma,
    document_id: str,
    progress_callback: JobProgressCallback | None = None,
    force_reanalysis: bool = False,
) -> str:
    """
    Execute analysis for a persisted document record.

    When `force_reanalysis` is enabled, the latest document analysis is rerun
    even if the document already has an analyzed result. Supported case
    snapshots are downgraded from final to provisional first so case-level
    read models stop preferring stale finalized snapshots.
    """
    document = await db.document.find_unique(where={"id": document_id})
    if not document:
        raise ValueError(f"Document {document_id} not found")

    existing = await get_analysis_by_document(db=db, document_id=document_id)
    if document.status == DocumentStatus.ANALYZED.value and existing and not force_reanalysis:
        print(f"[queue] Skipping {document_id}; analysis already exists")
        return "already_analyzed"

    if force_reanalysis:
        await prepare_case_for_forced_document_reanalysis(
            db=db,
            document=document,
        )

    await trigger_analysis(
        db=db,
        document=document,
        progress_callback=progress_callback,
    )
    return "completed"


async def run_analysis_for_document(
    document_id: str,
    progress_callback: JobProgressCallback | None = None,
    force_reanalysis: bool = False,
) -> str:
    """
    Background task entry point.

    Uses the shared Prisma client so analysis can continue after the request
    returns and the frontend can poll on document status.
    """
    return await run_analysis_for_stored_document(
        db=prisma_db,
        document_id=document_id,
        progress_callback=progress_callback,
        force_reanalysis=force_reanalysis,
    )


__all__ = [
    "build_bank_statement_output",
    "get_analysis_by_document",
    "get_analysis_by_id",
    "run_analysis_for_document",
    "run_analysis_for_stored_document",
    "run_strict_bank_statement_pipeline",
    "trigger_analysis",
]
