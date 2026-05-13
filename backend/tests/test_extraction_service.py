from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import fitz
import pytest

from services import extraction_service
from services.extraction_service import (
    ExtractedPage,
    OcrCandidate,
    OcrQualityInsufficientError,
    OcrResolution,
    PreparedExtraction,
)
from services.ocr_service import OcrProviderUnavailableError, OcrResult

MINIMAL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn0XxQAAAAASUVORK5CYII="
)
MINIMAL_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQEBUQEBIVFRUVFRUVFRUVFRUVFRUVFRUXFhUVFRUYHSggGBolGxUVITEhJSkrLi4uFx8zODMsNygtLisBCgoKDg0OGhAQGzAmICYtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAQMBIgACEQEDEQH/xAAXAAADAQAAAAAAAAAAAAAAAAAAAQID/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEAMQAAAB6A//xAAXEAADAQAAAAAAAAAAAAAAAAAAAREC/9oACAEBAAEFAkP/xAAVEQEBAAAAAAAAAAAAAAAAAAABAP/aAAgBAwEBPwFH/8QAFBEBAAAAAAAAAAAAAAAAAAAAEP/aAAgBAgEBPwEf/8QAFBABAAAAAAAAAAAAAAAAAAAAEP/aAAgBAQAGPwJf/8QAFBABAAAAAAAAAAAAAAAAAAAAEP/aAAgBAQABPyFf/9k="
)


def _make_pdf_with_text(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_pdf_with_blank_page() -> bytes:
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_pdf_with_text_and_blank_page() -> bytes:
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text(
        (72, 72),
        "Native digital text on page one with enough characters to skip OCR completely.",
    )
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_encrypted_blank_pdf(password: str) -> bytes:
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw=password,
    )
    doc.close()
    return pdf_bytes


@pytest.mark.asyncio
async def test_extract_document_content_skips_ocr_for_digital_pdf(monkeypatch):
    monkeypatch.setattr(
        extraction_service,
        "download_file",
        AsyncMock(return_value=_make_pdf_with_text("Readable native text with enough characters to bypass OCR entirely.")),
    )
    ocr_mock = AsyncMock(side_effect=AssertionError("OCR should not run for digital PDFs"))
    monkeypatch.setattr(extraction_service, "_run_ocr_with_fallback", ocr_mock)

    extracted = await extraction_service.extract_document_content("secure://digital.pdf", "application/pdf")

    assert extracted.total_pages == 1
    assert extracted.scanned_pages == 0
    assert extracted.ocr_provider is None
    assert extracted.ocr_failed_pages == []
    assert extracted.pages[0].source_kind == "native_text"
    assert "Readable native text" in extracted.total_text
    ocr_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_document_content_ocrs_only_low_text_pages_in_scanned_pdf(monkeypatch):
    monkeypatch.setattr(
        extraction_service,
        "download_file",
        AsyncMock(return_value=_make_pdf_with_text_and_blank_page()),
    )
    monkeypatch.setattr(
        extraction_service,
        "_run_ocr_with_fallback",
        AsyncMock(
            return_value=OcrResolution(
                accepted_result=OcrResult(text="Recovered OCR text", provider_name="tesseract", confidence=0.91),
                best_result=OcrResult(text="Recovered OCR text", provider_name="tesseract", confidence=0.91),
            )
        ),
    )

    extracted = await extraction_service.extract_document_content("secure://scanned.pdf", "application/pdf")

    assert extracted.total_pages == 2
    assert extracted.scanned_pages == 1
    assert extracted.ocr_required_pages == [2]
    assert extracted.ocr_provider == "tesseract"
    assert extracted.ocr_failed_pages == []
    assert extracted.ocr_unreliable_pages == []
    assert extracted.ocr_fallback_used is False
    assert extracted.pages[0].source_kind == "native_text"
    assert extracted.pages[1].source_kind == "ocr"
    assert extracted.pages[1].ocr_provider == "tesseract"
    assert extracted.pages[1].ocr_confidence == 0.91


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mime_type", "content"),
    [
        ("image/png", MINIMAL_PNG),
        ("image/jpeg", MINIMAL_JPEG),
    ],
)
async def test_extract_document_content_supports_png_and_jpeg(monkeypatch, mime_type: str, content: bytes):
    monkeypatch.setattr(extraction_service, "download_file", AsyncMock(return_value=content))
    monkeypatch.setattr(extraction_service, "normalize_image_bytes_to_png", lambda image_bytes: MINIMAL_PNG)
    monkeypatch.setattr(
        extraction_service,
        "_run_ocr_with_fallback",
        AsyncMock(
            return_value=OcrResolution(
                accepted_result=OcrResult(text="Image OCR text", provider_name="tesseract", confidence=0.75),
                best_result=OcrResult(text="Image OCR text", provider_name="tesseract", confidence=0.75),
            )
        ),
    )

    extracted = await extraction_service.extract_document_content("secure://image", mime_type)

    assert extracted.file_type == mime_type
    assert extracted.total_pages == 1
    assert extracted.scanned_pages == 1
    assert extracted.pages[0].source_kind == "ocr"
    assert extracted.pages[0].ocr_provider == "tesseract"
    assert "Image OCR text" in extracted.total_text


class _FailingProvider:
    async def extract_text(self, image_bytes: bytes, mime_type: str = "image/png"):
        raise OcrProviderUnavailableError("OCR provider unavailable: primary OCR offline.")


class _SuccessfulProvider:
    async def extract_text(self, image_bytes: bytes, mime_type: str = "image/png"):
        return OcrResult(text="Fallback OCR text", provider_name="tesseract", confidence=0.81)


@pytest.mark.asyncio
async def test_run_ocr_with_fallback_uses_tesseract_after_document_ai_failure(monkeypatch):
    result = await extraction_service._run_ocr_with_fallback(
        [_FailingProvider(), _SuccessfulProvider()],
        MINIMAL_PNG,
        "image/png",
    )

    assert result is not None
    assert result.accepted_result is not None
    assert result.accepted_result.provider_name == "tesseract"
    assert result.accepted_result.text == "Fallback OCR text"
    assert result.fallback_used is True


class _LowConfidenceProvider:
    async def extract_text(self, image_bytes: bytes, mime_type: str = "image/png"):
        return OcrResult(text="Low confidence OCR text", provider_name="document_ai", confidence=0.42)


@pytest.mark.asyncio
async def test_run_ocr_with_fallback_uses_tesseract_after_low_confidence_document_ai_result(monkeypatch):
    result = await extraction_service._run_ocr_with_fallback(
        [_LowConfidenceProvider(), _SuccessfulProvider()],
        MINIMAL_PNG,
        "image/png",
    )

    assert result is not None
    assert result.accepted_result is not None
    assert result.accepted_result.provider_name == "tesseract"
    assert result.accepted_result.text == "Fallback OCR text"
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_extract_document_content_builds_ocr_chain_once_per_document(monkeypatch):
    prepared = PreparedExtraction(
        pages=[
            ExtractedPage(page_num=1, text="", source_kind="pending_ocr"),
            ExtractedPage(page_num=2, text="", source_kind="pending_ocr"),
        ],
        ocr_candidates=[
            OcrCandidate(page_num=1, image_bytes=b"page-1"),
            OcrCandidate(page_num=2, image_bytes=b"page-2"),
        ],
        metadata={},
    )
    provider = SimpleNamespace(
        provider_name="tesseract",
        extract_text=AsyncMock(
            side_effect=[
                OcrResult(text="Recovered page 1", provider_name="tesseract", confidence=0.91),
                OcrResult(text="Recovered page 2", provider_name="tesseract", confidence=0.92),
            ]
        ),
    )
    build_chain_mock = Mock(return_value=[provider])

    monkeypatch.setattr(extraction_service, "download_file", AsyncMock(return_value=b"%PDF"))
    monkeypatch.setattr(extraction_service, "_prepare_pdf_extraction", lambda *args, **kwargs: prepared)
    monkeypatch.setattr(extraction_service, "build_ocr_provider_chain", build_chain_mock)

    extracted = await extraction_service.extract_document_content("secure://scanned.pdf", "application/pdf")

    assert extracted.total_pages == 2
    assert extracted.ocr_failed_pages == []
    assert build_chain_mock.call_count == 1
    assert provider.extract_text.await_count == 2


@pytest.mark.asyncio
async def test_extract_document_content_reports_single_page_ocr_failure_before_raising(monkeypatch):
    prepared = PreparedExtraction(
        pages=[ExtractedPage(page_num=1, text="", source_kind="pending_ocr")],
        ocr_candidates=[OcrCandidate(page_num=1, image_bytes=b"page-1")],
        metadata={},
    )
    provider = SimpleNamespace(
        provider_name="document_ai",
        extract_text=AsyncMock(
            side_effect=OcrProviderUnavailableError("OCR provider unavailable: primary OCR offline.")
        ),
    )
    progress_events: list[dict] = []

    async def progress_callback(**payload):
        progress_events.append(payload)

    monkeypatch.setattr(extraction_service, "download_file", AsyncMock(return_value=b"%PDF"))
    monkeypatch.setattr(extraction_service, "_prepare_pdf_extraction", lambda *args, **kwargs: prepared)
    monkeypatch.setattr(extraction_service, "build_ocr_provider_chain", lambda: [provider])

    with pytest.raises(OcrQualityInsufficientError, match="OCR quality is insufficient"):
        await extraction_service.extract_document_content(
            "secure://single-page.pdf",
            "application/pdf",
            progress_callback=progress_callback,
        )

    assert progress_events[-1]["stage"] == "ocr"
    assert progress_events[-1]["pages_processed"] == 1
    assert progress_events[-1]["total_pages"] == 1
    assert progress_events[-1]["ocr_required_pages"] == [1]
    assert progress_events[-1]["ocr_failed_pages"] == [1]
    assert progress_events[-1]["ocr_unreliable_pages"] == []
    assert progress_events[-1]["ocr_fallback_used"] is False
    assert "failed" in progress_events[-1]["stage_message"].lower()


@pytest.mark.asyncio
async def test_extract_document_content_keeps_successful_sibling_ocr_results_when_one_page_fails(monkeypatch):
    prepared = PreparedExtraction(
        pages=[
            ExtractedPage(page_num=1, text="", source_kind="pending_ocr"),
            ExtractedPage(page_num=2, text="", source_kind="pending_ocr"),
        ],
        ocr_candidates=[
            OcrCandidate(page_num=1, image_bytes=b"page-1"),
            OcrCandidate(page_num=2, image_bytes=b"page-2"),
        ],
        metadata={},
    )

    async def extract_text(image_bytes: bytes, mime_type: str = "image/png"):
        if image_bytes == b"page-1":
            raise OcrProviderUnavailableError("OCR provider unavailable: page 1 failed.")
        return OcrResult(text="Recovered page 2", provider_name="tesseract", confidence=0.89)

    provider = SimpleNamespace(
        provider_name="tesseract",
        extract_text=AsyncMock(side_effect=extract_text),
    )

    monkeypatch.setattr(extraction_service, "download_file", AsyncMock(return_value=b"%PDF"))
    monkeypatch.setattr(extraction_service, "_prepare_pdf_extraction", lambda *args, **kwargs: prepared)
    monkeypatch.setattr(extraction_service, "build_ocr_provider_chain", lambda: [provider])

    with pytest.raises(OcrQualityInsufficientError, match="OCR quality is insufficient") as exc_info:
        await extraction_service.extract_document_content("secure://scanned.pdf", "application/pdf")

    extracted = exc_info.value.extracted_document
    assert extracted.total_pages == 2
    assert extracted.scanned_pages == 1
    assert extracted.ocr_required_pages == [1, 2]
    assert extracted.ocr_failed_pages == [1]
    assert extracted.pages[1].text == "Recovered page 2"
    assert extracted.pages[1].ocr_provider == "tesseract"
    assert "Recovered page 2" in extracted.total_text


@pytest.mark.asyncio
async def test_extract_document_content_uses_password_for_encrypted_pdf(monkeypatch):
    monkeypatch.setattr(
        extraction_service,
        "download_file",
        AsyncMock(return_value=_make_encrypted_blank_pdf("secret-pass")),
    )
    monkeypatch.setattr(
        extraction_service,
        "_run_ocr_with_fallback",
        AsyncMock(
            return_value=OcrResolution(
                accepted_result=OcrResult(
                    text="Recovered encrypted OCR text",
                    provider_name="tesseract",
                    confidence=0.88,
                ),
                best_result=OcrResult(
                    text="Recovered encrypted OCR text",
                    provider_name="tesseract",
                    confidence=0.88,
                ),
            )
        ),
    )

    extracted = await extraction_service.extract_document_content(
        "secure://encrypted.pdf",
        "application/pdf",
        password="secret-pass",
    )

    assert extracted.total_pages == 1
    assert extracted.scanned_pages == 1
    assert extracted.pages[0].ocr_provider == "tesseract"
    assert "Recovered encrypted OCR text" in extracted.total_text


@pytest.mark.asyncio
async def test_extract_document_content_marks_low_confidence_ocr_as_unreliable(monkeypatch):
    monkeypatch.setattr(extraction_service, "download_file", AsyncMock(return_value=_make_pdf_with_blank_page()))
    monkeypatch.setattr(
        extraction_service,
        "_run_ocr_with_fallback",
        AsyncMock(
            return_value=OcrResolution(
                accepted_result=None,
                best_result=OcrResult(
                    text="Unsafe OCR text",
                    provider_name="document_ai",
                    confidence=0.55,
                ),
                fallback_used=False,
            )
        ),
    )

    with pytest.raises(OcrQualityInsufficientError, match="OCR quality is insufficient") as exc_info:
        await extraction_service.extract_document_content("secure://unreliable.pdf", "application/pdf")

    extracted = exc_info.value.extracted_document
    assert extracted.total_pages == 1
    assert extracted.scanned_pages == 0
    assert extracted.total_text == ""
    assert extracted.ocr_required_pages == [1]
    assert extracted.ocr_failed_pages == []
    assert extracted.ocr_unreliable_pages == [1]
    assert extracted.ocr_fallback_used is False
    assert extracted.pages[0].source_kind == "ocr_unreliable"
    assert extracted.pages[0].text == "Unsafe OCR text"
    assert extracted.pages[0].ocr_provider == "document_ai"
    assert extracted.pages[0].ocr_confidence == 0.55


@pytest.mark.asyncio
async def test_extract_document_content_raises_when_ocr_produces_no_readable_text(monkeypatch):
    monkeypatch.setattr(extraction_service, "download_file", AsyncMock(return_value=_make_pdf_with_blank_page()))
    monkeypatch.setattr(
        extraction_service,
        "_run_ocr_with_fallback",
        AsyncMock(return_value=None),
    )

    with pytest.raises(OcrQualityInsufficientError, match="OCR quality is insufficient"):
        await extraction_service.extract_document_content("secure://blank.pdf", "application/pdf")
