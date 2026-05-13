"""
OCR provider abstractions for LoanLens document extraction.
"""

from __future__ import annotations

import asyncio
import io
import re
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from core.config import get_settings

try:
    from PIL import Image, ImageOps, ImageStat, UnidentifiedImageError
except Exception:  # pragma: no cover - dependency is optional in some test envs
    Image = None
    ImageOps = None
    ImageStat = None

    class UnidentifiedImageError(Exception):
        pass

try:
    import pytesseract
except Exception:  # pragma: no cover - dependency is optional in some test envs
    pytesseract = None

try:
    from google.cloud import documentai
except Exception:  # pragma: no cover - dependency is optional in some test envs
    documentai = None

try:
    from google.api_core import exceptions as google_api_exceptions
except Exception:  # pragma: no cover - dependency is optional in some test envs
    google_api_exceptions = None


DOCUMENT_AI_RETRY_BACKOFF_SECONDS = (2, 4)


class OcrError(RuntimeError):
    """Base OCR error."""


class OcrProviderUnavailableError(OcrError):
    """Document AI or OCR provider is not configured/available."""


class TesseractMissingError(OcrError):
    """Raised when local Tesseract is unavailable."""


class ImageDecodeError(OcrError):
    """Raised when image bytes cannot be decoded."""


@dataclass
class OcrToken:
    text: str
    left: float
    top: float
    width: float
    height: float
    confidence: float | None = None
    page_num: int = 1
    block_id: str | None = None
    paragraph_id: str | None = None
    line_id: str | None = None

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def center_y(self) -> float:
        return self.top + (self.height / 2.0)


@dataclass
class OcrResult:
    text: str
    provider_name: str
    confidence: float | None = None
    tokens: list[OcrToken] = field(default_factory=list)


class OcrProvider(ABC):
    provider_name: str

    @abstractmethod
    async def extract_text(self, image_bytes: bytes, mime_type: str = "image/png") -> OcrResult:
        """Extract text from image bytes."""


def _open_image(image_bytes: bytes):
    if Image is None:
        raise ImageDecodeError("Image decode failure: Pillow is not installed.")

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except UnidentifiedImageError as exc:
        raise ImageDecodeError("Image decode failure: Uploaded image could not be decoded.") from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise ImageDecodeError(f"Image decode failure: {exc}") from exc
    return image


def normalize_image_bytes_to_png(image_bytes: bytes) -> bytes:
    """Normalize arbitrary image bytes into RGB PNG bytes."""
    image = _open_image(image_bytes).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _average_normalized_confidence(values: Iterable[float]) -> float | None:
    cleaned = [float(value) for value in values if value is not None]
    if not cleaned:
        return None
    return round(max(0.0, min(sum(cleaned) / len(cleaned), 1.0)), 4)


@dataclass
class _OcrCell:
    text: str
    left: float
    right: float


@dataclass
class _OcrLine:
    page_num: int
    tokens: list[OcrToken]
    text: str
    left: float
    top: float
    right: float
    bottom: float
    avg_height: float
    paragraph_id: str | None
    line_id: str | None
    cells: list[_OcrCell]


@dataclass
class _LayoutRegion:
    region_id: str
    left: float
    top: float
    right: float
    bottom: float

    @property
    def center_y(self) -> float:
        return self.top + ((self.bottom - self.top) / 2.0)


def _clean_ocr_fragment(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_document_ai_confidence_value(value: Any) -> float | None:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if confidence < 0:
        return None
    return round(max(0.0, min(confidence, 1.0)), 4)


def _normalize_tesseract_confidence_value(value: Any) -> float | None:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if confidence < 0:
        return None
    return round(max(0.0, min(confidence, 100.0)) / 100.0, 4)


def _average_provider_confidence(
    values: Iterable[Any],
    *,
    normalizer,
) -> float | None:
    cleaned = [normalizer(value) for value in values]
    return _average_normalized_confidence(value for value in cleaned if value is not None)


def _median(values: Sequence[float], default: float) -> float:
    cleaned = [float(value) for value in values if value is not None]
    if not cleaned:
        return default
    return float(statistics.median(cleaned))


def _most_common_string(values: Iterable[str | None]) -> str | None:
    cleaned = [value for value in values if value]
    if not cleaned:
        return None
    counts: dict[str, int] = {}
    for value in cleaned:
        counts[value] = counts.get(value, 0) + 1
    return max(counts.items(), key=lambda item: item[1])[0]


def _join_paragraph_text(existing: str, line_text: str) -> str:
    if not existing:
        return line_text
    if existing.endswith("-"):
        return f"{existing[:-1]}{line_text.lstrip()}".strip()
    return f"{existing.rstrip()} {line_text.lstrip()}".strip()


def _token_sort_key(token: OcrToken) -> tuple[int, float, float, float]:
    return (token.page_num, round(token.top, 4), round(token.left, 4), round(token.right, 4))


def _cluster_tokens_by_y(tokens: Sequence[OcrToken]) -> list[list[OcrToken]]:
    if not tokens:
        return []

    clusters: list[list[OcrToken]] = []
    for token in sorted(tokens, key=_token_sort_key):
        if not clusters:
            clusters.append([token])
            continue

        current_cluster = clusters[-1]
        current_center = _median([item.center_y for item in current_cluster], default=token.center_y)
        current_height = _median([item.height for item in current_cluster], default=token.height or 1.0)
        tolerance = max(current_height * 0.65, (token.height or 1.0) * 0.65, 8.0)
        if abs(token.center_y - current_center) <= tolerance:
            current_cluster.append(token)
        else:
            clusters.append([token])
    return clusters


def _split_line_into_cells(tokens: Sequence[OcrToken], avg_height: float) -> list[_OcrCell]:
    sorted_tokens = sorted(tokens, key=lambda token: (token.left, token.top))
    if not sorted_tokens:
        return []

    char_widths = [
        token.width / max(len(token.text), 1)
        for token in sorted_tokens
        if token.width > 0 and token.text
    ]
    gap_threshold = max(avg_height * 0.85, _median(char_widths, default=max(avg_height / 2.0, 3.0)) * 3.5, 12.0)

    cells: list[_OcrCell] = []
    current_tokens: list[OcrToken] = []
    for token in sorted_tokens:
        if current_tokens:
            gap = token.left - current_tokens[-1].right
            if gap > gap_threshold:
                cells.append(
                    _OcrCell(
                        text=" ".join(item.text for item in current_tokens).strip(),
                        left=current_tokens[0].left,
                        right=current_tokens[-1].right,
                    )
                )
                current_tokens = []
        current_tokens.append(token)

    if current_tokens:
        cells.append(
            _OcrCell(
                text=" ".join(item.text for item in current_tokens).strip(),
                left=current_tokens[0].left,
                right=current_tokens[-1].right,
            )
        )
    return [cell for cell in cells if cell.text]


def _build_ocr_line(tokens: Sequence[OcrToken]) -> _OcrLine:
    sorted_tokens = sorted(tokens, key=lambda token: (token.left, token.top))
    heights = [token.height for token in sorted_tokens if token.height > 0]
    avg_height = _median(heights, default=12.0)
    line_text = " ".join(token.text for token in sorted_tokens if token.text).strip()
    return _OcrLine(
        page_num=sorted_tokens[0].page_num if sorted_tokens else 1,
        tokens=list(sorted_tokens),
        text=line_text,
        left=min((token.left for token in sorted_tokens), default=0.0),
        top=min((token.top for token in sorted_tokens), default=0.0),
        right=max((token.right for token in sorted_tokens), default=0.0),
        bottom=max((token.bottom for token in sorted_tokens), default=0.0),
        avg_height=avg_height,
        paragraph_id=_most_common_string(token.paragraph_id for token in sorted_tokens),
        line_id=_most_common_string(token.line_id for token in sorted_tokens),
        cells=_split_line_into_cells(sorted_tokens, avg_height),
    )


def _attach_tokens_to_metadata_lines(
    tokens_with_metadata: list[list[OcrToken]],
    tokens_without_metadata: Sequence[OcrToken],
) -> tuple[list[list[OcrToken]], list[OcrToken]]:
    if not tokens_with_metadata:
        return list(tokens_with_metadata), list(tokens_without_metadata)

    grouped_tokens = [list(group) for group in tokens_with_metadata]
    unresolved: list[OcrToken] = []
    for token in tokens_without_metadata:
        best_group_index: int | None = None
        best_distance: float | None = None
        for index, group in enumerate(grouped_tokens):
            center = _median([item.center_y for item in group], default=token.center_y)
            avg_height = _median([item.height for item in group if item.height > 0], default=token.height or 1.0)
            distance = abs(token.center_y - center)
            tolerance = max(avg_height * 0.75, (token.height or 1.0) * 0.75, 8.0)
            if distance <= tolerance and (best_distance is None or distance < best_distance):
                best_distance = distance
                best_group_index = index
        if best_group_index is None:
            unresolved.append(token)
        else:
            grouped_tokens[best_group_index].append(token)
    return grouped_tokens, unresolved


def _group_tokens_into_lines(tokens: Sequence[OcrToken]) -> list[_OcrLine]:
    if not tokens:
        return []

    page_numbers = sorted({token.page_num for token in tokens})
    lines: list[_OcrLine] = []
    for page_num in page_numbers:
        page_tokens = sorted((token for token in tokens if token.page_num == page_num), key=_token_sort_key)
        metadata_groups: dict[str, list[OcrToken]] = {}
        no_metadata_tokens: list[OcrToken] = []
        for token in page_tokens:
            if token.line_id:
                metadata_groups.setdefault(token.line_id, []).append(token)
            else:
                no_metadata_tokens.append(token)

        if metadata_groups:
            grouped_tokens, unresolved = _attach_tokens_to_metadata_lines(list(metadata_groups.values()), no_metadata_tokens)
            grouped_tokens.extend(_cluster_tokens_by_y(unresolved))
        else:
            grouped_tokens = _cluster_tokens_by_y(page_tokens)

        lines.extend(_build_ocr_line(group) for group in grouped_tokens if group)

    return sorted(lines, key=lambda line: (line.page_num, round(line.top, 4), round(line.left, 4)))


def _aligned_column_count(first: _OcrLine, second: _OcrLine) -> int:
    if len(first.cells) < 2 or len(second.cells) < 2:
        return 0

    tolerance = max(min(first.avg_height, second.avg_height) * 1.5, 12.0)
    aligned = 0
    for first_cell, second_cell in zip(first.cells, second.cells):
        if abs(first_cell.left - second_cell.left) <= tolerance:
            aligned += 1
    return aligned


def _detect_table_lines(lines: Sequence[_OcrLine]) -> list[bool]:
    flags = [False] * len(lines)
    for index in range(len(lines) - 1):
        current = lines[index]
        following = lines[index + 1]
        if current.page_num != following.page_num:
            continue
        if abs(len(current.cells) - len(following.cells)) > 1:
            continue
        if _aligned_column_count(current, following) >= 2:
            flags[index] = True
            flags[index + 1] = True
    return flags


def _starts_new_paragraph(previous: _OcrLine | None, current: _OcrLine) -> bool:
    if previous is None:
        return True
    if previous.page_num != current.page_num:
        return True
    if previous.paragraph_id and current.paragraph_id and previous.paragraph_id != current.paragraph_id:
        return True

    gap = current.top - previous.bottom
    avg_height = max(previous.avg_height, current.avg_height, 1.0)
    if gap > max(avg_height * 0.9, 12.0):
        return True

    indent_shift = current.left - previous.left
    if indent_shift > max(avg_height * 1.2, 18.0):
        return True

    return False


def reconstruct_ocr_text(tokens: Sequence[OcrToken], *, fallback_text: str = "") -> str:
    lines = _group_tokens_into_lines(tokens)
    if not lines:
        return fallback_text.strip()

    table_flags = _detect_table_lines(lines)
    blocks: list[str] = []
    current_paragraph = ""
    current_table_rows: list[str] = []
    previous_paragraph_line: _OcrLine | None = None

    for line, is_table in zip(lines, table_flags):
        if is_table:
            if current_paragraph:
                blocks.append(current_paragraph.strip())
                current_paragraph = ""
            row = "\t".join(cell.text for cell in line.cells if cell.text).strip()
            if row:
                current_table_rows.append(row)
            previous_paragraph_line = None
            continue

        if current_table_rows:
            blocks.append("\n".join(current_table_rows).strip())
            current_table_rows = []

        if not line.text:
            continue

        if _starts_new_paragraph(previous_paragraph_line, line):
            if current_paragraph:
                blocks.append(current_paragraph.strip())
            current_paragraph = line.text
        else:
            current_paragraph = _join_paragraph_text(current_paragraph, line.text)
        previous_paragraph_line = line

    if current_paragraph:
        blocks.append(current_paragraph.strip())
    if current_table_rows:
        blocks.append("\n".join(current_table_rows).strip())

    reconstructed = "\n\n".join(block for block in blocks if block.strip()).strip()
    return reconstructed or fallback_text.strip()


def _document_ai_text_from_anchor(document_text: str, text_anchor: Any) -> str:
    if text_anchor is None:
        return ""
    segments = getattr(text_anchor, "text_segments", None) or []
    parts: list[str] = []
    for segment in segments:
        start_index = int(getattr(segment, "start_index", 0) or 0)
        end_index = int(getattr(segment, "end_index", 0) or 0)
        if end_index > start_index:
            parts.append(document_text[start_index:end_index])
    return _clean_ocr_fragment("".join(parts))


def _layout_bounding_box(layout: Any, page_width: float, page_height: float) -> tuple[float, float, float, float]:
    bounding_poly = getattr(layout, "bounding_poly", None)
    if bounding_poly is None:
        return 0.0, 0.0, 0.0, 0.0

    normalized_vertices = getattr(bounding_poly, "normalized_vertices", None) or []
    if normalized_vertices:
        points = [
            (_coerce_float(getattr(vertex, "x", 0.0)) * page_width, _coerce_float(getattr(vertex, "y", 0.0)) * page_height)
            for vertex in normalized_vertices
        ]
    else:
        vertices = getattr(bounding_poly, "vertices", None) or []
        points = [
            (_coerce_float(getattr(vertex, "x", 0.0)), _coerce_float(getattr(vertex, "y", 0.0)))
            for vertex in vertices
        ]

    if not points:
        return 0.0, 0.0, 0.0, 0.0

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    left = min(xs)
    top = min(ys)
    return left, top, max(xs) - left, max(ys) - top


def _build_layout_regions(items: Sequence[Any], *, prefix: str, page_width: float, page_height: float) -> list[_LayoutRegion]:
    regions: list[_LayoutRegion] = []
    for index, item in enumerate(items, start=1):
        layout = getattr(item, "layout", None)
        left, top, width, height = _layout_bounding_box(layout, page_width, page_height)
        if width <= 0 or height <= 0:
            continue
        regions.append(
            _LayoutRegion(
                region_id=f"{prefix}-{index}",
                left=left,
                top=top,
                right=left + width,
                bottom=top + height,
            )
        )
    return regions


def _match_layout_region(token: OcrToken, regions: Sequence[_LayoutRegion]) -> str | None:
    if not regions:
        return None

    best_region_id: str | None = None
    best_score = -1.0
    for region in regions:
        vertical_overlap = max(0.0, min(token.bottom, region.bottom) - max(token.top, region.top))
        horizontal_overlap = max(0.0, min(token.right, region.right) - max(token.left, region.left))
        contains_center = region.top <= token.center_y <= region.bottom
        if vertical_overlap <= 0 and not contains_center:
            continue
        score = (vertical_overlap * 2.0) + horizontal_overlap
        if contains_center:
            score += 5.0
        if score > best_score:
            best_score = score
            best_region_id = region.region_id
    return best_region_id


def _extract_document_ai_tokens(document: Any) -> list[OcrToken]:
    document_text = getattr(document, "text", "") or ""
    pages = getattr(document, "pages", None) or []
    tokens: list[OcrToken] = []
    for page_index, page in enumerate(pages, start=1):
        dimension = getattr(page, "dimension", None)
        page_width = _coerce_float(getattr(dimension, "width", 1.0), default=1.0) or 1.0
        page_height = _coerce_float(getattr(dimension, "height", 1.0), default=1.0) or 1.0
        block_regions = _build_layout_regions(
            getattr(page, "blocks", None) or [],
            prefix=f"page-{page_index}-block",
            page_width=page_width,
            page_height=page_height,
        )
        paragraph_regions = _build_layout_regions(
            getattr(page, "paragraphs", None) or [],
            prefix=f"page-{page_index}-paragraph",
            page_width=page_width,
            page_height=page_height,
        )
        line_regions = _build_layout_regions(
            getattr(page, "lines", None) or [],
            prefix=f"page-{page_index}-line",
            page_width=page_width,
            page_height=page_height,
        )

        for token in getattr(page, "tokens", None) or []:
            layout = getattr(token, "layout", None)
            token_text = _document_ai_text_from_anchor(document_text, getattr(layout, "text_anchor", None))
            if not token_text:
                continue
            left, top, width, height = _layout_bounding_box(layout, page_width, page_height)
            normalized_token = OcrToken(
                text=token_text,
                left=left,
                top=top,
                width=width,
                height=height,
                confidence=_normalize_document_ai_confidence_value(getattr(layout, "confidence", None)),
                page_num=page_index,
            )
            normalized_token.block_id = _match_layout_region(normalized_token, block_regions)
            normalized_token.paragraph_id = _match_layout_region(normalized_token, paragraph_regions)
            normalized_token.line_id = _match_layout_region(normalized_token, line_regions)
            tokens.append(normalized_token)
    return tokens


def _preprocess_tesseract_image(image):
    if ImageOps is None or ImageStat is None:
        return image.convert("RGB")

    oriented = ImageOps.exif_transpose(image)
    grayscale = ImageOps.grayscale(oriented.convert("RGB"))
    contrasted = ImageOps.autocontrast(grayscale)
    stats = ImageStat.Stat(contrasted)
    mean_value = stats.mean[0] if stats.mean else 160.0
    threshold = max(96, min(208, int(mean_value * 0.95)))
    return contrasted.point(lambda value: 255 if value >= threshold else 0, mode="L")


def _tesseract_tokens_from_data(data: Any) -> list[OcrToken]:
    if not isinstance(data, dict):
        return []

    raw_texts = data.get("text", []) or []
    if not hasattr(raw_texts, "__len__"):
        return []

    tokens: list[OcrToken] = []
    for index in range(len(raw_texts)):
        token_text = _clean_ocr_fragment(raw_texts[index])
        if not token_text:
            continue

        page_num = int(_coerce_float((data.get("page_num", []) or [1])[index] if index < len(data.get("page_num", []) or []) else 1, 1.0))
        block_num = int(_coerce_float((data.get("block_num", []) or [0])[index] if index < len(data.get("block_num", []) or []) else 0, 0.0))
        paragraph_num = int(_coerce_float((data.get("par_num", []) or [0])[index] if index < len(data.get("par_num", []) or []) else 0, 0.0))
        line_num = int(_coerce_float((data.get("line_num", []) or [0])[index] if index < len(data.get("line_num", []) or []) else 0, 0.0))

        block_id = f"page-{page_num}-block-{block_num}" if block_num else None
        paragraph_id = f"{block_id}-paragraph-{paragraph_num}" if block_id and paragraph_num else None
        line_id = f"{paragraph_id}-line-{line_num}" if paragraph_id and line_num else None
        if line_id is None and line_num:
            line_id = f"page-{page_num}-line-{line_num}"

        tokens.append(
            OcrToken(
                text=token_text,
                left=_coerce_float((data.get("left", []) or [0])[index] if index < len(data.get("left", []) or []) else 0, 0.0),
                top=_coerce_float((data.get("top", []) or [0])[index] if index < len(data.get("top", []) or []) else 0, 0.0),
                width=_coerce_float((data.get("width", []) or [0])[index] if index < len(data.get("width", []) or []) else 0, 0.0),
                height=_coerce_float((data.get("height", []) or [0])[index] if index < len(data.get("height", []) or []) else 0, 0.0),
                confidence=_normalize_tesseract_confidence_value(
                    (data.get("conf", []) or [None])[index] if index < len(data.get("conf", []) or []) else None
                ),
                page_num=max(page_num, 1),
                block_id=block_id,
                paragraph_id=paragraph_id,
                line_id=line_id,
            )
        )
    return tokens


class DocumentAiOcrProvider(OcrProvider):
    provider_name = "document_ai"

    def __init__(
        self,
        *,
        project_id: str,
        location: str,
        processor_id: str,
    ) -> None:
        if documentai is None:
            raise OcrProviderUnavailableError(
                "OCR provider unavailable: google-cloud-documentai is not installed."
            )
        if not project_id or not location or not processor_id:
            raise OcrProviderUnavailableError(
                "OCR provider unavailable: Google Document AI OCR processor is not configured."
            )

        self._project_id = project_id
        self._location = location
        self._processor_id = processor_id
        try:
            self._client = documentai.DocumentProcessorServiceClient()
        except Exception as exc:
            raise OcrProviderUnavailableError(
                f"OCR provider unavailable: Google Document AI client failed to initialize ({exc})."
            ) from exc
        self._processor_name = self._client.processor_path(
            self._project_id,
            self._location,
            self._processor_id,
        )

    async def extract_text(self, image_bytes: bytes, mime_type: str = "image/png") -> OcrResult:
        for attempt in range(len(DOCUMENT_AI_RETRY_BACKOFF_SECONDS) + 1):
            try:
                return await asyncio.to_thread(self._extract_text_sync, image_bytes, mime_type)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not _is_transient_document_ai_error(exc) or attempt >= len(DOCUMENT_AI_RETRY_BACKOFF_SECONDS):
                    raise OcrError(f"Document AI OCR failed: {exc}") from exc
                await asyncio.sleep(DOCUMENT_AI_RETRY_BACKOFF_SECONDS[attempt])

    def _extract_text_sync(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        request = documentai.ProcessRequest(
            name=self._processor_name,
            raw_document=documentai.RawDocument(
                content=image_bytes,
                mime_type=mime_type,
            ),
        )
        result = self._client.process_document(request=request)
        document = result.document
        tokens = _extract_document_ai_tokens(document)
        text = reconstruct_ocr_text(tokens, fallback_text=(getattr(document, "text", "") or ""))

        confidence_sources: list[float] = []
        for page in getattr(document, "pages", []) or []:
            layout_confidence = getattr(getattr(page, "layout", None), "confidence", None)
            if layout_confidence is not None:
                confidence_sources.append(layout_confidence)
            for token in getattr(page, "tokens", []) or []:
                token_confidence = getattr(getattr(token, "layout", None), "confidence", None)
                if token_confidence is not None:
                    confidence_sources.append(token_confidence)

        return OcrResult(
            text=text,
            provider_name=self.provider_name,
            confidence=_average_provider_confidence(
                confidence_sources,
                normalizer=_normalize_document_ai_confidence_value,
            ),
            tokens=tokens,
        )


class TesseractOcrProvider(OcrProvider):
    provider_name = "tesseract"

    def __init__(self, *, languages: str) -> None:
        self._languages = languages or "eng"

    async def extract_text(self, image_bytes: bytes, mime_type: str = "image/png") -> OcrResult:
        return await asyncio.to_thread(self._extract_text_sync, image_bytes, mime_type)

    def _extract_text_sync(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        if pytesseract is None:
            raise TesseractMissingError("Tesseract missing: pytesseract is not installed.")

        image = _preprocess_tesseract_image(_open_image(image_bytes))
        try:
            data = pytesseract.image_to_data(
                image,
                lang=self._languages,
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractNotFoundError as exc:
            raise TesseractMissingError(
                "Tesseract missing: Tesseract OCR executable is not installed or not available."
            ) from exc
        except RuntimeError as exc:
            raise OcrError(f"Tesseract OCR failed: {exc}") from exc

        tokens = _tesseract_tokens_from_data(data)
        confidence_values = [token.confidence for token in tokens if token.confidence is not None]
        text = reconstruct_ocr_text(tokens)

        return OcrResult(
            text=text,
            provider_name=self.provider_name,
            confidence=_average_normalized_confidence(confidence_values),
            tokens=tokens,
        )


def _is_transient_document_ai_error(error: Exception) -> bool:
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True

    if google_api_exceptions is None:
        return False

    retryable_google_errors = tuple(
        error_type
        for error_type in (
            getattr(google_api_exceptions, "DeadlineExceeded", None),
            getattr(google_api_exceptions, "InternalServerError", None),
            getattr(google_api_exceptions, "RetryError", None),
            getattr(google_api_exceptions, "ServiceUnavailable", None),
            getattr(google_api_exceptions, "TooManyRequests", None),
        )
        if error_type is not None
    )
    return isinstance(error, retryable_google_errors)


def build_primary_ocr_provider(*, settings=None) -> OcrProvider:
    settings = settings or get_settings()
    return DocumentAiOcrProvider(
        project_id=settings.GOOGLE_DOCUMENT_AI_PROJECT_ID,
        location=settings.GOOGLE_DOCUMENT_AI_LOCATION,
        processor_id=settings.GOOGLE_DOCUMENT_AI_PROCESSOR_ID,
    )


def build_fallback_ocr_provider(*, settings=None) -> OcrProvider:
    settings = settings or get_settings()
    return TesseractOcrProvider(languages=settings.OCR_TESSERACT_LANGS)


def build_ocr_provider_chain() -> list[OcrProvider]:
    settings = get_settings()
    mode = (settings.OCR_PROVIDER_MODE or "hybrid").strip().lower()

    if mode == "document_ai":
        return [build_primary_ocr_provider(settings=settings)]
    if mode == "tesseract":
        return [build_fallback_ocr_provider(settings=settings)]
    if mode == "hybrid":
        providers: list[OcrProvider] = []
        try:
            providers.append(build_primary_ocr_provider(settings=settings))
        except OcrProviderUnavailableError:
            pass
        providers.append(build_fallback_ocr_provider(settings=settings))
        return providers

    raise OcrProviderUnavailableError(
        f"OCR provider unavailable: Unsupported OCR provider mode '{settings.OCR_PROVIDER_MODE}'."
    )
