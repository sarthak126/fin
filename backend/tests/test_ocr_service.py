from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from services import ocr_service
from services.ocr_service import OcrProviderUnavailableError, OcrResult, OcrToken

MINIMAL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn0XxQAAAAASUVORK5CYII="
)


def _make_settings(mode: str):
    return SimpleNamespace(
        OCR_PROVIDER_MODE=mode,
        GOOGLE_DOCUMENT_AI_PROJECT_ID="project-id",
        GOOGLE_DOCUMENT_AI_LOCATION="us",
        GOOGLE_DOCUMENT_AI_PROCESSOR_ID="processor-id",
        OCR_TESSERACT_LANGS="eng",
    )


def _make_vertex(x: float, y: float):
    return SimpleNamespace(x=x, y=y)


def _make_layout(
    *,
    start_index: int,
    end_index: int,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    confidence: float | None = None,
):
    return SimpleNamespace(
        text_anchor=SimpleNamespace(
            text_segments=[SimpleNamespace(start_index=start_index, end_index=end_index)]
        ),
        bounding_poly=SimpleNamespace(
            normalized_vertices=[
                _make_vertex(x0, y0),
                _make_vertex(x1, y0),
                _make_vertex(x1, y1),
                _make_vertex(x0, y1),
            ]
        ),
        confidence=confidence,
    )


def test_build_ocr_provider_chain_returns_only_tesseract_in_tesseract_mode(monkeypatch):
    tesseract_provider = SimpleNamespace(provider_name="tesseract")

    monkeypatch.setattr(ocr_service, "get_settings", lambda: _make_settings("tesseract"))
    monkeypatch.setattr(
        ocr_service,
        "TesseractOcrProvider",
        Mock(return_value=tesseract_provider),
    )
    monkeypatch.setattr(
        ocr_service,
        "DocumentAiOcrProvider",
        Mock(side_effect=AssertionError("Document AI should not initialize in tesseract mode")),
    )

    providers = ocr_service.build_ocr_provider_chain()

    assert providers == [tesseract_provider]


def test_build_ocr_provider_chain_raises_cleanly_in_document_ai_mode(monkeypatch):
    monkeypatch.setattr(ocr_service, "get_settings", lambda: _make_settings("document_ai"))
    monkeypatch.setattr(
        ocr_service,
        "DocumentAiOcrProvider",
        Mock(side_effect=OcrProviderUnavailableError("OCR provider unavailable: Document AI offline.")),
    )
    tesseract_constructor = Mock()
    monkeypatch.setattr(ocr_service, "TesseractOcrProvider", tesseract_constructor)

    with pytest.raises(OcrProviderUnavailableError, match="Document AI offline"):
        ocr_service.build_ocr_provider_chain()

    tesseract_constructor.assert_not_called()


def test_build_ocr_provider_chain_falls_back_to_tesseract_in_hybrid_mode(monkeypatch):
    tesseract_provider = SimpleNamespace(provider_name="tesseract")

    monkeypatch.setattr(ocr_service, "get_settings", lambda: _make_settings("hybrid"))
    monkeypatch.setattr(
        ocr_service,
        "DocumentAiOcrProvider",
        Mock(side_effect=OcrProviderUnavailableError("OCR provider unavailable: Document AI offline.")),
    )
    monkeypatch.setattr(
        ocr_service,
        "TesseractOcrProvider",
        Mock(return_value=tesseract_provider),
    )

    providers = ocr_service.build_ocr_provider_chain()

    assert providers == [tesseract_provider]


def test_reconstruct_ocr_text_builds_paragraphs_from_line_metadata():
    tokens = [
        OcrToken(text="This", left=10, top=10, width=20, height=10, page_num=1, paragraph_id="p1", line_id="l1"),
        OcrToken(text="paragraph", left=40, top=10, width=45, height=10, page_num=1, paragraph_id="p1", line_id="l1"),
        OcrToken(text="continues.", left=10, top=24, width=50, height=10, page_num=1, paragraph_id="p1", line_id="l2"),
        OcrToken(text="Next", left=15, top=52, width=20, height=10, page_num=1, paragraph_id="p2", line_id="l3"),
        OcrToken(text="paragraph.", left=40, top=52, width=50, height=10, page_num=1, paragraph_id="p2", line_id="l3"),
    ]

    text = ocr_service.reconstruct_ocr_text(tokens)

    assert text == "This paragraph continues.\n\nNext paragraph."


def test_reconstruct_ocr_text_preserves_basic_tables_as_tabs():
    tokens = [
        OcrToken(text="Date", left=10, top=10, width=20, height=10, page_num=1, line_id="l1"),
        OcrToken(text="Description", left=90, top=10, width=55, height=10, page_num=1, line_id="l1"),
        OcrToken(text="Amount", left=220, top=10, width=35, height=10, page_num=1, line_id="l1"),
        OcrToken(text="01-04-26", left=10, top=24, width=40, height=10, page_num=1, line_id="l2"),
        OcrToken(text="Salary", left=90, top=24, width=28, height=10, page_num=1, line_id="l2"),
        OcrToken(text="50000", left=220, top=24, width=28, height=10, page_num=1, line_id="l2"),
        OcrToken(text="02-04-26", left=10, top=38, width=40, height=10, page_num=1, line_id="l3"),
        OcrToken(text="Rent", left=90, top=38, width=20, height=10, page_num=1, line_id="l3"),
        OcrToken(text="12000", left=220, top=38, width=28, height=10, page_num=1, line_id="l3"),
    ]

    text = ocr_service.reconstruct_ocr_text(tokens)

    assert text == "Date\tDescription\tAmount\n01-04-26\tSalary\t50000\n02-04-26\tRent\t12000"


def test_group_tokens_into_lines_falls_back_to_y_clustering_without_line_metadata():
    tokens = [
        OcrToken(text="Alpha", left=10, top=10, width=25, height=10, page_num=1),
        OcrToken(text="beta", left=40, top=11, width=20, height=10, page_num=1),
        OcrToken(text="Gamma", left=10, top=36, width=30, height=10, page_num=1),
    ]

    lines = ocr_service._group_tokens_into_lines(tokens)

    assert len(lines) == 2
    assert lines[0].text == "Alpha beta"
    assert lines[1].text == "Gamma"


def test_extract_document_ai_tokens_assigns_provider_line_and_paragraph_metadata():
    document_text = "Opening balance Salary credit"
    page = SimpleNamespace(
        dimension=SimpleNamespace(width=1000, height=1000),
        blocks=[],
        paragraphs=[
            SimpleNamespace(layout=_make_layout(start_index=0, end_index=len(document_text), x0=0.05, y0=0.08, x1=0.9, y1=0.22))
        ],
        lines=[
            SimpleNamespace(layout=_make_layout(start_index=0, end_index=15, x0=0.05, y0=0.08, x1=0.5, y1=0.13)),
            SimpleNamespace(layout=_make_layout(start_index=16, end_index=len(document_text), x0=0.05, y0=0.16, x1=0.75, y1=0.22)),
        ],
        tokens=[
            SimpleNamespace(layout=_make_layout(start_index=0, end_index=7, x0=0.05, y0=0.08, x1=0.2, y1=0.13, confidence=0.91)),
            SimpleNamespace(layout=_make_layout(start_index=8, end_index=15, x0=0.22, y0=0.08, x1=0.5, y1=0.13, confidence=0.9)),
            SimpleNamespace(layout=_make_layout(start_index=16, end_index=22, x0=0.05, y0=0.16, x1=0.24, y1=0.22, confidence=0.93)),
            SimpleNamespace(layout=_make_layout(start_index=23, end_index=len(document_text), x0=0.28, y0=0.16, x1=0.75, y1=0.22, confidence=0.94)),
        ],
    )
    document = SimpleNamespace(text=document_text, pages=[page])

    tokens = ocr_service._extract_document_ai_tokens(document)

    assert [token.text for token in tokens] == ["Opening", "balance", "Salary", "credit"]
    assert all(token.line_id for token in tokens)
    assert all(token.paragraph_id for token in tokens)


@pytest.mark.asyncio
async def test_document_ai_provider_retries_transient_failures(monkeypatch):
    sleep_delays: list[int] = []

    class _FakeDocumentAiClient:
        def processor_path(self, project_id: str, location: str, processor_id: str) -> str:
            return f"{project_id}/{location}/{processor_id}"

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def fake_sleep(delay: int):
        sleep_delays.append(delay)

    monkeypatch.setattr(
        ocr_service,
        "documentai",
        SimpleNamespace(DocumentProcessorServiceClient=_FakeDocumentAiClient),
    )
    monkeypatch.setattr(ocr_service.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(ocr_service.asyncio, "sleep", fake_sleep)

    provider = ocr_service.DocumentAiOcrProvider(
        project_id="project-id",
        location="us",
        processor_id="processor-id",
    )
    provider._extract_text_sync = Mock(
        side_effect=[
            ConnectionError("temporary network issue"),
            ConnectionError("temporary network issue"),
            OcrResult(text="Recovered text", provider_name="document_ai", confidence=0.94),
        ]
    )

    result = await provider.extract_text(b"page-image")

    assert result.text == "Recovered text"
    assert provider._extract_text_sync.call_count == 3
    assert sleep_delays == [2, 4]


def test_tesseract_provider_uses_single_token_pass_and_reconstructed_text(monkeypatch):
    calls = {"image_to_data": 0}

    class _FakeTesseractNotFoundError(Exception):
        pass

    class _FakeImage:
        def convert(self, mode: str):
            return self

    def image_to_data(image, *, lang, output_type):
        calls["image_to_data"] += 1
        assert lang == "eng"
        assert output_type == "dict"
        return {
            "text": ["Opening", "balance", "Salary", "credit"],
            "conf": ["91", "90", "94", "95"],
            "left": [10, 60, 10, 70],
            "top": [10, 10, 28, 28],
            "width": [40, 45, 45, 42],
            "height": [10, 10, 10, 10],
            "page_num": [1, 1, 1, 1],
            "block_num": [1, 1, 1, 1],
            "par_num": [1, 1, 1, 1],
            "line_num": [1, 1, 2, 2],
        }

    fake_pytesseract = SimpleNamespace(
        Output=SimpleNamespace(DICT="dict"),
        TesseractNotFoundError=_FakeTesseractNotFoundError,
        image_to_data=image_to_data,
        image_to_string=Mock(side_effect=AssertionError("image_to_string should not be called")),
    )
    monkeypatch.setattr(ocr_service, "pytesseract", fake_pytesseract)
    monkeypatch.setattr(ocr_service, "_open_image", lambda image_bytes: _FakeImage())
    monkeypatch.setattr(ocr_service, "_preprocess_tesseract_image", lambda image: image)

    provider = ocr_service.TesseractOcrProvider(languages="eng")

    result = provider._extract_text_sync(MINIMAL_PNG, "image/png")

    assert result.text == "Opening balance Salary credit"
    assert result.confidence == 0.925
    assert calls["image_to_data"] == 1
    fake_pytesseract.image_to_string.assert_not_called()
    assert [token.text for token in result.tokens] == ["Opening", "balance", "Salary", "credit"]
