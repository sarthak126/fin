"""
Case-level Ask AI using the structured case report as context.
"""

from __future__ import annotations

import re

from google import genai
from google.genai import types
from prisma import Prisma

from core.config import get_settings
from schemas.ask import AskResponse, AskSource
from schemas.case_report import CaseReportPayload, CaseReportSection
from services.case_report_service import get_case_report
from services.gemini_service import _generate_content_with_retry

_CASE_ASK_STOPWORDS = {
    "about",
    "after",
    "and",
    "are",
    "case",
    "could",
    "does",
    "from",
    "have",
    "loan",
    "report",
    "should",
    "tell",
    "that",
    "the",
    "this",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
    "would",
}

CASE_ASK_SYSTEM_PROMPT = """You are ArgentNorth AI — an expert loan underwriting assistant.

The user is asking a question about a CASE REPORT that aggregates applicant
intake, uploaded document analyses, cross-document checks, fraud signals, and
the latest case-level decision snapshot.

RULES:
- Answer only from the provided case report context.
- If the answer is not present, say "I couldn't find that information in this case report."
- Clearly distinguish between finalized and provisional findings when relevant.
- Use concise, professional language suitable for a loan underwriter.
- Cite the most relevant report sections in your wording when possible.
"""


def _question_keywords(question: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", question.lower())
        if token not in _CASE_ASK_STOPWORDS
    }


def _section_to_text(section: CaseReportSection) -> str:
    parts: list[str] = [section.title]
    if section.summary:
        parts.append(section.summary)
    for item in section.items:
        parts.append(item.title)
        if item.summary:
            parts.append(item.summary)
        parts.extend(f"{fact.label}: {fact.display_value}" for fact in item.facts)
        parts.extend(item.bullets)
    return "\n".join(part for part in parts if part).strip()


def _score_section(question: str, section: CaseReportSection) -> int:
    lowered_question = question.lower()
    section_text = _section_to_text(section).lower()
    title_text = section.title.lower()
    score = 0

    for keyword in _question_keywords(question):
        if keyword in title_text:
            score += 4
        elif keyword in section_text:
            score += 1

    if lowered_question in section_text:
        score += 2

    return score


def _select_relevant_sections(report: CaseReportPayload, question: str, limit: int = 4) -> list[CaseReportSection]:
    scored_sections = [
        (section, _score_section(question, section))
        for section in report.sections
    ]
    scored_sections.sort(key=lambda item: item[1], reverse=True)
    selected = [section for section, score in scored_sections if score > 0][:limit]
    if selected:
        return selected
    return report.sections[:limit]


def _build_case_context(report: CaseReportPayload, sections: list[CaseReportSection]) -> str:
    header_lines = [
        f"Report title: {report.header.title}",
        f"Report status: {report.header.report_status}",
        f"Case ID: {report.case.id}",
        f"Applicant: {report.case.applicant_name or report.case.name or 'Unavailable'}",
        f"Decision status: {report.overview.decision_status or 'Unavailable'}",
        f"Recommendation: {report.overview.recommendation or 'Unavailable'}",
        f"Summary: {report.overview.summary}",
    ]
    context_parts = ["CASE REPORT OVERVIEW\n" + "\n".join(header_lines)]
    for section in sections:
        context_parts.append(f"[Section: {section.title}]\n{_section_to_text(section)}")
    return "\n\n---\n\n".join(context_parts)


async def ask_about_case(
    db: Prisma,
    *,
    case_id: str,
    org_id: str,
    question: str,
) -> AskResponse | None:
    report = await get_case_report(
        db=db,
        case_id=case_id,
        org_id=org_id,
    )
    if not report:
        return None

    selected_sections = _select_relevant_sections(report, question)
    if not selected_sections:
        return AskResponse(
            answer="I couldn't find enough information in this case report to answer your question.",
            sources=[],
        )

    prompt = f"""{CASE_ASK_SYSTEM_PROMPT}

--- CASE REPORT CONTEXT ---
{_build_case_context(report, selected_sections)}
--- END CONTEXT ---

User Question: {question}

Answer:"""
    settings = get_settings()
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    response = await _generate_content_with_retry(
        client,
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.3),
    )
    answer = response.text.strip() if response.text else "Unable to generate an answer."
    return AskResponse(
        answer=answer,
        sources=[
            AskSource(section_title=section.title, page_num=0)
            for section in selected_sections
        ],
    )


__all__ = [
    "ask_about_case",
]
