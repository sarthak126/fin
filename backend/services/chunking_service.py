"""
Chunking Service — Semantic document chunking for loan documents.

Pipeline step: Upload → Extraction → [THIS] → Vector DB → Gemini → Insights

Strategy:
  1. Try semantic chunking by detecting section headings, clauses, and structure
  2. Within large sections, fall back to RecursiveCharacterTextSplitter
"""

import re
from dataclasses import dataclass, field
from langchain_text_splitters import RecursiveCharacterTextSplitter
from core.config import get_settings


@dataclass
class DocumentChunk:
    text: str
    chunk_index: int
    page_num: int | None = None
    section_title: str = ""
    metadata: dict = field(default_factory=dict)


# ────────────────────────────────────────
# Section heading patterns common in loan/financial documents
# ────────────────────────────────────────

SECTION_PATTERNS = [
    # "Section 1:", "Section 2.1:", "SECTION III"
    r"(?:^|\n)(?:SECTION|Section)\s+[\dIVXivx]+[\.\:]\s*.*",
    # "Clause 1:", "CLAUSE 2:"
    r"(?:^|\n)(?:CLAUSE|Clause)\s+\d+[\.\:]\s*.*",
    # "1. Introduction", "2.1 Terms", "A. Definitions"
    r"(?:^|\n)\d+(?:\.\d+)*[\.\)]\s+[A-Z][^\n]+",
    r"(?:^|\n)[A-Z][\.\)]\s+[A-Z][^\n]+",
    # "SCHEDULE I", "ANNEXURE A", "APPENDIX"
    r"(?:^|\n)(?:SCHEDULE|ANNEXURE|APPENDIX|EXHIBIT)\s+[A-Z\dIVX]+",
    # All-caps headings like "INTEREST RATE", "TERMS AND CONDITIONS"
    r"(?:^|\n)([A-Z][A-Z\s&\-]{4,})\s*(?:\n|$)",
    # Markdown-style: "# Heading", "## Heading"
    r"(?:^|\n)#{1,3}\s+.+",
    # Separator lines: "---", "===", "___"
    r"(?:^|\n)[-=_]{3,}\s*(?:\n|$)",
]

COMPILED_PATTERNS = [re.compile(p) for p in SECTION_PATTERNS]


def _detect_sections(text: str) -> list[tuple[str, str]]:
    """
    Split text into (section_title, section_body) tuples based on detected headings.
    If no headings are found, returns the entire text as one section.
    """
    # Find all heading positions
    heading_positions: list[tuple[int, str]] = []
    
    for pattern in COMPILED_PATTERNS:
        for match in pattern.finditer(text):
            heading_text = match.group().strip().strip("#").strip("-=_").strip()
            if heading_text and len(heading_text) > 2:
                heading_positions.append((match.start(), heading_text))

    if not heading_positions:
        return [("Document", text)]

    # Sort by position and deduplicate nearby headings
    heading_positions.sort(key=lambda x: x[0])
    
    # Remove duplicates within 10 chars of each other
    filtered: list[tuple[int, str]] = []
    for pos, heading in heading_positions:
        if not filtered or pos - filtered[-1][0] > 10:
            filtered.append((pos, heading))
    
    # Build sections
    sections: list[tuple[str, str]] = []
    
    # Text before first heading
    if filtered[0][0] > 50:
        sections.append(("Preamble", text[:filtered[0][0]].strip()))
    
    for i, (pos, heading) in enumerate(filtered):
        end = filtered[i + 1][0] if i + 1 < len(filtered) else len(text)
        body = text[pos:end].strip()
        # Remove the heading line from the body
        body_lines = body.split("\n", 1)
        body = body_lines[1].strip() if len(body_lines) > 1 else body
        if body:
            sections.append((heading[:80], body))  # cap heading length

    return sections


def _split_large_section(text: str, settings) -> list[str]:
    """Split a large section using RecursiveCharacterTextSplitter."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", ", ", " ", ""],
        length_function=len,
    )
    return splitter.split_text(text)


def _estimate_page_num(chunk_text: str, pages: list) -> int | None:
    """Try to find which page this chunk came from."""
    for page in pages:
        if chunk_text[:100] in page.text:
            return page.page_num
    return None


def chunk_document(extracted_doc) -> list[DocumentChunk]:
    """
    Main chunking entry point.
    
    1. Detect sections/headings in the document
    2. Keep small sections as single chunks
    3. Split large sections with RecursiveCharacterTextSplitter
    4. Attach metadata to each chunk
    """
    settings = get_settings()
    chunks: list[DocumentChunk] = []
    chunk_index = 0

    # Detect sections
    sections = _detect_sections(extracted_doc.total_text)

    for section_title, section_body in sections:
        if len(section_body) <= settings.CHUNK_SIZE:
            # Small enough to be one chunk
            chunks.append(DocumentChunk(
                text=section_body,
                chunk_index=chunk_index,
                page_num=_estimate_page_num(section_body, extracted_doc.pages),
                section_title=section_title,
                metadata={
                    "section": section_title,
                    "is_semantic_chunk": True,
                },
            ))
            chunk_index += 1
        else:
            # Too large — split further
            sub_chunks = _split_large_section(section_body, settings)
            for sub_text in sub_chunks:
                chunks.append(DocumentChunk(
                    text=sub_text,
                    chunk_index=chunk_index,
                    page_num=_estimate_page_num(sub_text, extracted_doc.pages),
                    section_title=section_title,
                    metadata={
                        "section": section_title,
                        "is_semantic_chunk": False,
                        "parent_section_size": len(section_body),
                    },
                ))
                chunk_index += 1

    # Edge case: if no chunks were created, chunk the raw text
    if not chunks and extracted_doc.total_text:
        sub_chunks = _split_large_section(extracted_doc.total_text, settings)
        for i, sub_text in enumerate(sub_chunks):
            chunks.append(DocumentChunk(
                text=sub_text,
                chunk_index=i,
                section_title="Document",
                metadata={"is_semantic_chunk": False},
            ))

    return chunks
