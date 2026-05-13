"""
Extraction Service - native document extraction with hybrid OCR fallback.

Pipeline step: Upload -> [THIS] -> Chunking -> Vector DB -> Gemini -> Insights
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from typing import Awaitable, Callable, Iterable

import fitz  # PyMuPDF

from core.config import get_settings
from services.ocr_service import (
    ImageDecodeError,
    OcrError,
    OcrProvider,
    OcrProviderUnavailableError,
    OcrResult,
    TesseractMissingError,
    build_ocr_provider_chain,
    normalize_image_bytes_to_png,
)
from services.storage_service import download_file

SourceKind = str
OcrProviderName = str | None
ProgressCallback = Callable[..., Awaitable[None] | None]

PAGE_SOURCE_NATIVE_TEXT = "native_text"
PAGE_SOURCE_PENDING_OCR = "pending_ocr"
PAGE_SOURCE_OCR = "ocr"
PAGE_SOURCE_OCR_FAILED = "ocr_failed"
PAGE_SOURCE_OCR_UNRELIABLE = "ocr_unreliable"

EXTRACTION_SCHEMA_VERSION = 2
EXTRACTION_STATUS_COMPLETE = "complete"
EXTRACTION_STATUS_PARTIAL = "partial"
EXTRACTION_STATUS_FAILED = "failed"
EXTRACTION_STATUS_UNRELIABLE = "unreliable"

OCR_QUALITY_STATUS_PENDING = "pending"
OCR_QUALITY_STATUS_CLEAN = "clean"
OCR_QUALITY_STATUS_DEGRADED = "degraded"
OCR_QUALITY_STATUS_BLOCKED = "blocked"

OCR_BLOCKING_ERROR_CODES = {
    "image_decode_failed",
    "ocr_no_readable_text",
    "ocr_provider_unavailable",
    "ocr_quality_blocked",
    "tesseract_missing",
}

ACCEPTED_PAGE_SOURCE_KINDS = {
    PAGE_SOURCE_NATIVE_TEXT,
    PAGE_SOURCE_OCR,
}
OCR_REQUIRED_PAGE_SOURCE_KINDS = {
    PAGE_SOURCE_PENDING_OCR,
    PAGE_SOURCE_OCR,
    PAGE_SOURCE_OCR_FAILED,
    PAGE_SOURCE_OCR_UNRELIABLE,
}


class OcrNoReadableTextError(OcrError):
    """Raised when OCR completed but no readable text was produced."""


def _aggregate_provider_names(provider_names: Iterable[str | None]) -> str | None:
    providers = {provider_name for provider_name in provider_names if provider_name}
    if not providers:
        return None
    if len(providers) == 1:
        return next(iter(providers))
    return "mixed"


def _accepted_ocr_page_numbers(pages: list["ExtractedPage"]) -> list[int]:
    return sorted({page.page_num for page in pages if page.source_kind == PAGE_SOURCE_OCR})


def _pending_ocr_page_numbers(pages: list["ExtractedPage"]) -> list[int]:
    return sorted({page.page_num for page in pages if page.source_kind == PAGE_SOURCE_PENDING_OCR})


def resolve_ocr_quality_status(
    *,
    ocr_required_pages: list[int] | None = None,
    ocr_failed_pages: list[int] | None = None,
    ocr_unreliable_pages: list[int] | None = None,
    ocr_fallback_used: bool = False,
    extraction_status: str | None = None,
    job_status: str | None = None,
    stage: str | None = None,
    pages_processed: int | None = None,
    total_pages: int | None = None,
    error_code: str | None = None,
) -> str:
    normalized_extraction_status = str(extraction_status or "").strip().lower()
    normalized_job_status = str(job_status or "").strip().lower()
    normalized_stage = str(stage or "").strip().lower()
    normalized_error_code = str(error_code or "").strip().lower()
    failed_pages = sorted({int(page_num) for page_num in (ocr_failed_pages or [])})
    unreliable_pages = sorted({int(page_num) for page_num in (ocr_unreliable_pages or [])})

    if (
        failed_pages
        or unreliable_pages
        or normalized_extraction_status in {EXTRACTION_STATUS_FAILED, EXTRACTION_STATUS_UNRELIABLE}
        or normalized_error_code in OCR_BLOCKING_ERROR_CODES
    ):
        return OCR_QUALITY_STATUS_BLOCKED

    if normalized_job_status == "queued":
        return OCR_QUALITY_STATUS_PENDING

    pages_incomplete = (
        pages_processed is not None
        and total_pages is not None
        and int(pages_processed) < int(total_pages)
    )
    if normalized_extraction_status == EXTRACTION_STATUS_PARTIAL:
        if normalized_job_status in {"queued", "processing"}:
            return OCR_QUALITY_STATUS_PENDING
        return OCR_QUALITY_STATUS_BLOCKED

    if normalized_job_status == "processing" and (
        normalized_stage in {"queued", "extracting", "ocr"} or pages_incomplete
    ):
        return OCR_QUALITY_STATUS_PENDING

    if bool(ocr_required_pages) and ocr_fallback_used:
        return OCR_QUALITY_STATUS_DEGRADED

    return OCR_QUALITY_STATUS_CLEAN


def _resolve_extraction_status(
    pages: list["ExtractedPage"],
    *,
    ocr_failed_pages: list[int],
    ocr_unreliable_pages: list[int],
) -> str:
    if _pending_ocr_page_numbers(pages):
        return EXTRACTION_STATUS_PARTIAL
    if ocr_failed_pages:
        return EXTRACTION_STATUS_FAILED
    if ocr_unreliable_pages:
        return EXTRACTION_STATUS_UNRELIABLE
    return EXTRACTION_STATUS_COMPLETE


@dataclass
class ExtractedPage:
    page_num: int
    text: str
    source_kind: SourceKind = PAGE_SOURCE_NATIVE_TEXT
    ocr_provider: OcrProviderName = None
    ocr_confidence: float | None = None

    @property
    def is_scanned(self) -> bool:
        return self.source_kind in OCR_REQUIRED_PAGE_SOURCE_KINDS

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "ExtractedPage":
        return cls(
            page_num=int(payload.get("page_num", 0)),
            text=str(payload.get("text", "")),
            source_kind=str(payload.get("source_kind", PAGE_SOURCE_NATIVE_TEXT)),
            ocr_provider=payload.get("ocr_provider"),
            ocr_confidence=payload.get("ocr_confidence"),
        )


@dataclass
class ExtractedDocument:
    file_type: str
    pages: list[ExtractedPage] = field(default_factory=list)
    total_text: str = ""
    total_pages: int = 0
    scanned_pages: int = 0
    extraction_schema_version: int = EXTRACTION_SCHEMA_VERSION
    extraction_status: str = EXTRACTION_STATUS_COMPLETE
    ocr_required_pages: list[int] = field(default_factory=list)
    ocr_failed_pages: list[int] = field(default_factory=list)
    ocr_unreliable_pages: list[int] = field(default_factory=list)
    ocr_fallback_used: bool = False
    ocr_provider: OcrProviderName = None
    metadata: dict = field(default_factory=dict)

    def rebuild(self) -> "ExtractedDocument":
        self.ocr_required_pages = sorted(
            {
                *[int(page_num) for page_num in self.ocr_required_pages],
                *[
                    page.page_num
                    for page in self.pages
                    if page.source_kind in OCR_REQUIRED_PAGE_SOURCE_KINDS
                ],
            }
        )
        self.ocr_failed_pages = sorted(
            {
                *[int(page_num) for page_num in self.ocr_failed_pages],
                *[
                    page.page_num
                    for page in self.pages
                    if page.source_kind == PAGE_SOURCE_OCR_FAILED
                ],
            }
        )
        self.ocr_unreliable_pages = sorted(
            {
                *[int(page_num) for page_num in self.ocr_unreliable_pages],
                *[
                    page.page_num
                    for page in self.pages
                    if page.source_kind == PAGE_SOURCE_OCR_UNRELIABLE
                ],
            }
        )
        self.total_pages = len(self.pages)
        accepted_ocr_pages = _accepted_ocr_page_numbers(self.pages)
        self.scanned_pages = len(accepted_ocr_pages)
        self.extraction_schema_version = EXTRACTION_SCHEMA_VERSION
        self.extraction_status = _resolve_extraction_status(
            self.pages,
            ocr_failed_pages=self.ocr_failed_pages,
            ocr_unreliable_pages=self.ocr_unreliable_pages,
        )
        self.total_text = "\n\n".join(
            f"--- Page {page.page_num} ---\n{page.text}"
            for page in self.pages
            if page.source_kind in ACCEPTED_PAGE_SOURCE_KINDS and page.text.strip()
        )

        self.ocr_provider = _aggregate_provider_names(
            page.ocr_provider
            for page in self.pages
            if page.source_kind in OCR_REQUIRED_PAGE_SOURCE_KINDS
        )

        self.metadata = {
            **(self.metadata or {}),
            "page_count": self.total_pages,
            "has_scanned_pages": self.scanned_pages > 0,
            "has_ocr_required_pages": bool(self.ocr_required_pages),
            "accepted_ocr_pages": accepted_ocr_pages,
            "accepted_ocr_page_count": len(accepted_ocr_pages),
            "ocr_required_pages": list(self.ocr_required_pages),
            "ocr_required_page_count": len(self.ocr_required_pages),
            "ocr_failed_pages": list(self.ocr_failed_pages),
            "ocr_failed_page_count": len(self.ocr_failed_pages),
            "ocr_unreliable_pages": list(self.ocr_unreliable_pages),
            "ocr_unreliable_page_count": len(self.ocr_unreliable_pages),
            "ocr_fallback_used": bool(self.ocr_fallback_used),
            "extraction_status": self.extraction_status,
            "extraction_schema_version": self.extraction_schema_version,
            "ocr_quality_status": resolve_ocr_quality_status(
                ocr_required_pages=self.ocr_required_pages,
                ocr_failed_pages=self.ocr_failed_pages,
                ocr_unreliable_pages=self.ocr_unreliable_pages,
                ocr_fallback_used=self.ocr_fallback_used,
                extraction_status=self.extraction_status,
            ),
            "ocr_provider": self.ocr_provider,
        }
        return self

    def to_dict(self) -> dict:
        self.rebuild()
        return {
            "file_type": self.file_type,
            "total_text": self.total_text,
            "total_pages": self.total_pages,
            "scanned_pages": self.scanned_pages,
            "extraction_schema_version": self.extraction_schema_version,
            "extraction_status": self.extraction_status,
            "ocr_required_pages": list(self.ocr_required_pages),
            "ocr_failed_pages": list(self.ocr_failed_pages),
            "ocr_unreliable_pages": list(self.ocr_unreliable_pages),
            "ocr_fallback_used": bool(self.ocr_fallback_used),
            "ocr_provider": self.ocr_provider,
            "metadata": dict(self.metadata or {}),
            "pages": [page.to_dict() for page in self.pages],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ExtractedDocument":
        document = cls(
            file_type=str(payload.get("file_type", "application/pdf")),
            pages=[ExtractedPage.from_dict(item) for item in payload.get("pages", [])],
            total_text=str(payload.get("total_text", "")),
            total_pages=int(payload.get("total_pages", 0)),
            scanned_pages=int(payload.get("scanned_pages", 0)),
            extraction_schema_version=int(
                payload.get("extraction_schema_version", payload.get("metadata", {}).get("extraction_schema_version", 1))
            ),
            extraction_status=str(
                payload.get("extraction_status", payload.get("metadata", {}).get("extraction_status", ""))
            ),
            ocr_required_pages=[int(page_num) for page_num in payload.get("ocr_required_pages", [])],
            ocr_failed_pages=[int(page_num) for page_num in payload.get("ocr_failed_pages", [])],
            ocr_unreliable_pages=[int(page_num) for page_num in payload.get("ocr_unreliable_pages", [])],
            ocr_fallback_used=bool(payload.get("ocr_fallback_used", False)),
            ocr_provider=payload.get("ocr_provider"),
            metadata=dict(payload.get("metadata", {}) or {}),
        )
        return document.rebuild()


@dataclass
class OcrCandidate:
    page_num: int
    image_bytes: bytes
    mime_type: str = "image/png"


@dataclass
class PreparedExtraction:
    pages: list[ExtractedPage]
    ocr_candidates: list[OcrCandidate]
    metadata: dict


@dataclass
class OcrResolution:
    accepted_result: OcrResult | None = None
    best_result: OcrResult | None = None
    fallback_used: bool = False


class OcrQualityInsufficientError(OcrError):
    """Raised when OCR-required pages remain failed, pending, or unreliable."""

    def __init__(self, extracted_document) -> None:
        self.extracted_document = extracted_document
        pending_pages = list(_pending_ocr_page_numbers(getattr(extracted_document, "pages", []) or []))
        failed_pages = list(getattr(extracted_document, "ocr_failed_pages", []) or [])
        unreliable_pages = list(getattr(extracted_document, "ocr_unreliable_pages", []) or [])

        issue_parts: list[str] = []
        if pending_pages:
            issue_parts.append(f"pending OCR pages: {', '.join(str(page_num) for page_num in pending_pages)}")
        if failed_pages:
            issue_parts.append(f"failed OCR pages: {', '.join(str(page_num) for page_num in failed_pages)}")
        if unreliable_pages:
            issue_parts.append(
                f"unreliable OCR pages: {', '.join(str(page_num) for page_num in unreliable_pages)}"
            )

        detail = "; ".join(issue_parts) if issue_parts else "unresolved OCR quality"
        super().__init__(f"OCR quality is insufficient for analysis ({detail}).")


def raise_for_unresolved_ocr_quality(extracted_document) -> None:
    pending_pages = _pending_ocr_page_numbers(getattr(extracted_document, "pages", []) or [])
    failed_pages = list(getattr(extracted_document, "ocr_failed_pages", []) or [])
    unreliable_pages = list(getattr(extracted_document, "ocr_unreliable_pages", []) or [])
    if pending_pages or failed_pages or unreliable_pages:
        raise OcrQualityInsufficientError(extracted_document)


async def _notify_progress(callback: ProgressCallback | None, **payload) -> None:
    if callback is None:
        return

    result = callback(**payload)
    if asyncio.iscoroutine(result):
        await result


def _render_page_png(page: fitz.Page, dpi: int) -> bytes:
    scale = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    return pix.tobytes("png")


def _prepare_pdf_extraction(
    file_bytes: bytes,
    password: str,
    *,
    dpi: int,
    min_text_length: int,
) -> PreparedExtraction:
    pages: list[ExtractedPage] = []
    ocr_candidates: list[OcrCandidate] = []

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        if doc.is_encrypted:
            if not password:
                raise ValueError("This PDF is password-protected. Please provide the password.")
            if not doc.authenticate(password):
                raise ValueError("Incorrect PDF password. Please check and try again.")

        metadata = doc.metadata or {}
        for page_index in range(len(doc)):
            page = doc[page_index]
            text = page.get_text("text").strip()
            page_num = page_index + 1
            requires_ocr = len(text) < min_text_length

            if requires_ocr:
                image_bytes = _render_page_png(page, dpi=dpi)
                pages.append(
                    ExtractedPage(
                        page_num=page_num,
                        text=text,
                        source_kind=PAGE_SOURCE_PENDING_OCR,
                    )
                )
                ocr_candidates.append(OcrCandidate(page_num=page_num, image_bytes=image_bytes))
            else:
                pages.append(
                    ExtractedPage(
                        page_num=page_num,
                        text=text,
                        source_kind=PAGE_SOURCE_NATIVE_TEXT,
                    )
                )
    finally:
        doc.close()

    return PreparedExtraction(
        pages=pages,
        ocr_candidates=ocr_candidates,
        metadata={
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
        },
    )


def _prepare_image_extraction(file_bytes: bytes) -> PreparedExtraction:
    image_bytes = normalize_image_bytes_to_png(file_bytes)
    return PreparedExtraction(
        pages=[
            ExtractedPage(
                page_num=1,
                text="",
                source_kind=PAGE_SOURCE_PENDING_OCR,
            )
        ],
        ocr_candidates=[OcrCandidate(page_num=1, image_bytes=image_bytes)],
        metadata={},
    )


def _ocr_result_rank(result: OcrResult | None) -> tuple[int, float, int]:
    if result is None:
        return (0, -1.0, 0)
    text = result.text.strip()
    return (
        1 if text else 0,
        -1.0 if result.confidence is None else float(result.confidence),
        len(text),
    )


def _is_acceptable_ocr_result(result: OcrResult | None, min_confidence: float) -> bool:
    return bool(
        result
        and result.text.strip()
        and result.confidence is not None
        and result.confidence >= min_confidence
    )


async def _run_ocr_with_fallback(
    providers: list[OcrProvider],
    image_bytes: bytes,
    mime_type: str,
) -> OcrResolution | None:
    settings = get_settings()
    min_confidence = settings.OCR_MIN_ACCEPTABLE_CONFIDENCE
    last_error: Exception | None = None
    best_result: OcrResult | None = None
    best_result_provider_index: int | None = None
    fallback_used = (
        (settings.OCR_PROVIDER_MODE or "").strip().lower() == "hybrid"
        and bool(providers)
        and getattr(providers[0], "provider_name", None) == "tesseract"
    )

    for index, provider in enumerate(providers):
        try:
            result = await provider.extract_text(image_bytes, mime_type=mime_type)
        except (OcrProviderUnavailableError, TesseractMissingError, ImageDecodeError, OcrError) as exc:
            last_error = exc
            continue

        if not result.text.strip():
            continue

        if _ocr_result_rank(result) > _ocr_result_rank(best_result):
            best_result = result
            best_result_provider_index = index

        if _is_acceptable_ocr_result(result, min_confidence):
            return OcrResolution(
                accepted_result=result,
                best_result=result,
                fallback_used=fallback_used or index > 0,
            )

        if index == 0 and len(providers) > 1:
            fallback_used = True

    if best_result is not None:
        return OcrResolution(
            accepted_result=None,
            best_result=best_result,
            fallback_used=fallback_used or bool((best_result_provider_index or 0) > 0),
        )
    if last_error is not None:
        raise last_error
    return None


def _aggregate_provider_chain(providers: list[OcrProvider]) -> str | None:
    return _aggregate_provider_names(provider.provider_name for provider in providers)


def _progress_ocr_provider(pages: list[ExtractedPage], providers: list[OcrProvider]) -> str | None:
    return _aggregate_provider_names(page.ocr_provider for page in pages) or _aggregate_provider_chain(providers)


async def extract_document_content(
    file_url: str,
    file_type: str,
    password: str = "",
    progress_callback: ProgressCallback | None = None,
) -> ExtractedDocument:
    """
    Extract normalized text from PDFs and images with hybrid OCR.
    """
    settings = get_settings()
    file_bytes = await download_file(file_url)
    normalized_file_type = (file_type or "").strip().lower()

    if normalized_file_type == "application/pdf":
        prepared = await asyncio.to_thread(
            _prepare_pdf_extraction,
            file_bytes,
            password,
            dpi=settings.OCR_RENDER_DPI,
            min_text_length=settings.OCR_MIN_TEXT_LENGTH,
        )
    elif normalized_file_type in {"image/png", "image/jpeg"}:
        prepared = await asyncio.to_thread(_prepare_image_extraction, file_bytes)
    else:
        raise ValueError(f"Unsupported file type for extraction: {file_type}")

    total_pages = len(prepared.pages)
    native_pages_processed = sum(1 for page in prepared.pages if page.source_kind == PAGE_SOURCE_NATIVE_TEXT)
    ocr_required_pages = sorted(candidate.page_num for candidate in prepared.ocr_candidates)

    await _notify_progress(
        progress_callback,
        stage="extracting",
        stage_message="Extracting native text and identifying OCR-needed pages.",
        pages_processed=native_pages_processed,
        total_pages=total_pages,
        ocr_provider=None,
        ocr_required_pages=ocr_required_pages,
        ocr_failed_pages=[],
        ocr_unreliable_pages=[],
        ocr_fallback_used=False,
    )

    page_lookup = {page.page_num: page for page in prepared.pages}
    ocr_failed_pages: list[int] = []
    ocr_unreliable_pages: list[int] = []
    ocr_fallback_used = False
    pages_processed = native_pages_processed
    last_ocr_error: Exception | None = None
    semaphore = asyncio.Semaphore(max(1, settings.OCR_MAX_CONCURRENCY))
    ocr_providers = build_ocr_provider_chain() if prepared.ocr_candidates else []

    async def _resolve_candidate(candidate: OcrCandidate) -> tuple[int, OcrResolution | None, Exception | None]:
        async with semaphore:
            try:
                result = await _run_ocr_with_fallback(ocr_providers, candidate.image_bytes, candidate.mime_type)
                return candidate.page_num, result, None
            except Exception as exc:  # pragma: no cover - exercised via tests with mocks
                return candidate.page_num, None, exc

    if prepared.ocr_candidates:
        await _notify_progress(
            progress_callback,
            stage="ocr",
            stage_message="Running OCR on scanned pages.",
            pages_processed=pages_processed,
            total_pages=total_pages,
            ocr_provider=_progress_ocr_provider(prepared.pages, ocr_providers),
            ocr_required_pages=ocr_required_pages,
            ocr_failed_pages=[],
            ocr_unreliable_pages=[],
            ocr_fallback_used=False,
        )

        tasks = [asyncio.create_task(_resolve_candidate(candidate)) for candidate in prepared.ocr_candidates]
        for task in asyncio.as_completed(tasks):
            page_num, ocr_resolution, error = await task
            page = page_lookup[page_num]

            if error is not None:
                last_ocr_error = error
                page.source_kind = PAGE_SOURCE_OCR_FAILED
                page.ocr_provider = None
                page.ocr_confidence = None
                ocr_failed_pages.append(page_num)
                stage_message = f"OCR failed for page {page_num} of {total_pages}."
            elif ocr_resolution and ocr_resolution.accepted_result:
                resolved_result = ocr_resolution.accepted_result
                page.text = resolved_result.text.strip()
                page.source_kind = PAGE_SOURCE_OCR
                page.ocr_provider = resolved_result.provider_name
                page.ocr_confidence = resolved_result.confidence
                ocr_fallback_used = ocr_fallback_used or ocr_resolution.fallback_used
                stage_message = f"Resolved OCR text for page {page_num} of {total_pages}."
            elif ocr_resolution and ocr_resolution.best_result and ocr_resolution.best_result.text.strip():
                resolved_result = ocr_resolution.best_result
                page.text = resolved_result.text.strip()
                page.source_kind = PAGE_SOURCE_OCR_UNRELIABLE
                page.ocr_provider = resolved_result.provider_name
                page.ocr_confidence = resolved_result.confidence
                ocr_unreliable_pages.append(page_num)
                ocr_fallback_used = ocr_fallback_used or ocr_resolution.fallback_used
                confidence_label = (
                    "unknown confidence"
                    if resolved_result.confidence is None
                    else f"{resolved_result.confidence:.2f} confidence"
                )
                stage_message = (
                    f"OCR confidence below acceptance threshold for page {page_num} of {total_pages} "
                    f"({confidence_label})."
                )
            else:
                page.source_kind = PAGE_SOURCE_OCR_FAILED
                page.ocr_provider = None
                page.ocr_confidence = None
                ocr_failed_pages.append(page_num)
                stage_message = f"OCR returned no readable text for page {page_num} of {total_pages}."

            pages_processed += 1
            await _notify_progress(
                progress_callback,
                stage="ocr",
                stage_message=stage_message,
                pages_processed=pages_processed,
                total_pages=total_pages,
                ocr_provider=_progress_ocr_provider(prepared.pages, ocr_providers),
                ocr_required_pages=ocr_required_pages,
                ocr_failed_pages=sorted(set(ocr_failed_pages)),
                ocr_unreliable_pages=sorted(set(ocr_unreliable_pages)),
                ocr_fallback_used=ocr_fallback_used,
            )

    extracted_document = ExtractedDocument(
        file_type=file_type,
        pages=prepared.pages,
        ocr_required_pages=ocr_required_pages,
        ocr_failed_pages=sorted(set(ocr_failed_pages)),
        ocr_unreliable_pages=sorted(set(ocr_unreliable_pages)),
        ocr_fallback_used=ocr_fallback_used,
        metadata=prepared.metadata,
    ).rebuild()

    raise_for_unresolved_ocr_quality(extracted_document)

    if prepared.ocr_candidates and not extracted_document.total_text.strip():
        if last_ocr_error is not None:
            raise last_ocr_error
        raise OcrNoReadableTextError("OCR completed with no readable text.")

    return extracted_document
