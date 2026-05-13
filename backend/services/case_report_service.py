"""
Case report assembly for UI rendering and print/export payloads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from prisma import Prisma

from models import DecisionStatus, DocumentStatus, Recommendation
from schemas.case_read_model import CaseAnalysisSnapshot, CaseReadModel
from schemas.case_report import (
    CaseReportHeader,
    CaseReportItem,
    CaseReportMetric,
    CaseReportOverview,
    CaseReportPayload,
    CaseReportPrintPayload,
    CaseReportPrintSection,
    CaseReportSection,
)
from services.analysis_read_service import load_string_list_json
from services.case_aggregation_service import get_case_read_model
from services.case_analysis_service import build_case_analysis_snapshot
from services.followup_utils import filter_action_followups


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _status_label(value: Any) -> str:
    text = str(_enum_value(value) or "").strip()
    if not text:
        return "Unavailable"
    return text.replace("_", " ").title()


def _confidence_percent(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    return f"{round(float(value) * 100)}%"


def _scalar_display(value: Any) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _document_status_tone(status: Any) -> str:
    normalized = str(_enum_value(status) or "").strip().lower()
    if normalized == DocumentStatus.ANALYZED.value:
        return "good"
    if normalized in {DocumentStatus.PENDING.value, DocumentStatus.PROCESSING.value}:
        return "warning"
    if normalized == DocumentStatus.FAILED.value:
        return "danger"
    return "neutral"


def _decision_tone(decision_status: Any) -> str:
    normalized = str(_enum_value(decision_status) or "").strip().lower()
    if normalized == DecisionStatus.APPROVE.value:
        return "good"
    if normalized == DecisionStatus.REJECT.value:
        return "danger"
    if normalized in {DecisionStatus.MANUAL_REVIEW.value, DecisionStatus.INSUFFICIENT_HISTORY.value}:
        return "warning"
    return "neutral"


def _risk_tone(risk_score: float | None) -> str:
    if risk_score is None:
        return "neutral"
    if risk_score >= 70:
        return "danger"
    if risk_score >= 40:
        return "warning"
    return "good"


def _latest_case_analysis(read_model: CaseReadModel) -> CaseAnalysisSnapshot:
    if read_model.authoritative_analysis is not None:
        return read_model.authoritative_analysis
    return build_case_analysis_snapshot(
        read_model,
        is_final=False,
        snapshot_kind="case_live_provisional",
        generated_from="live_provisional",
    )


def _report_generated_at(read_model: CaseReadModel, latest_analysis: CaseAnalysisSnapshot) -> datetime:
    timestamps = [
        read_model.case.created_at,
        read_model.case.updated_at,
        latest_analysis.created_at,
    ]
    for document in read_model.documents:
        timestamps.extend([document.created_at, document.updated_at])
        if document.latest_analysis is not None:
            timestamps.append(document.latest_analysis.created_at)
    return max(timestamps) if timestamps else datetime.now(timezone.utc)


def _report_title(read_model: CaseReadModel) -> str:
    applicant_name = str(read_model.case.applicant_name or "").strip()
    if applicant_name:
        return f"{applicant_name} Case Report"
    case_name = str(read_model.case.name or "").strip()
    if case_name:
        return f"{case_name} Case Report"
    return f"Case {read_model.case.id} Report"


def _report_subtitle(read_model: CaseReadModel, latest_analysis: CaseAnalysisSnapshot) -> str:
    report_state = "Finalized" if latest_analysis.is_final else "Provisional"
    case_status = _status_label(read_model.case.status)
    return f"{report_state} case assessment • {case_status} workflow state"


def _metric(key: str, label: str, value: Any, display_value: str, tone: str = "neutral", hint: str | None = None) -> CaseReportMetric:
    return CaseReportMetric(
        key=key,
        label=label,
        value=value,
        display_value=display_value,
        tone=tone,
        hint=hint,
    )


def _build_metrics(read_model: CaseReadModel, latest_analysis: CaseAnalysisSnapshot) -> list[CaseReportMetric]:
    provisional = read_model.provisional_insights
    return [
        _metric(
            key="decision_status",
            label="Decision status",
            value=_enum_value(latest_analysis.decision_status),
            display_value=_status_label(latest_analysis.decision_status),
            tone=_decision_tone(latest_analysis.decision_status),
        ),
        _metric(
            key="recommendation",
            label="Recommendation",
            value=_enum_value(latest_analysis.recommendation),
            display_value=_status_label(latest_analysis.recommendation),
            tone=_decision_tone(latest_analysis.decision_status),
        ),
        _metric(
            key="risk_score",
            label="Risk score",
            value=latest_analysis.risk_score,
            display_value=_scalar_display(latest_analysis.risk_score),
            tone=_risk_tone(latest_analysis.risk_score),
        ),
        _metric(
            key="confidence",
            label="Confidence",
            value=latest_analysis.confidence,
            display_value=_confidence_percent(latest_analysis.confidence),
            tone="neutral",
        ),
        _metric(
            key="data_completeness",
            label="Data completeness",
            value=latest_analysis.data_completeness,
            display_value=_confidence_percent(latest_analysis.data_completeness),
            tone="neutral",
        ),
        _metric(
            key="documents_analyzed",
            label="Analyzed documents",
            value=provisional.analyzed_document_count,
            display_value=str(provisional.analyzed_document_count),
            tone="neutral",
        ),
        _metric(
            key="documents_pending",
            label="Pending documents",
            value=provisional.pending_document_count,
            display_value=str(provisional.pending_document_count),
            tone="warning" if provisional.pending_document_count else "good",
        ),
        _metric(
            key="fraud_signal_count",
            label="Fraud signals",
            value=provisional.fraud_signal_count,
            display_value=str(provisional.fraud_signal_count),
            tone="danger" if provisional.fraud_signal_count else "good",
        ),
    ]


def _build_decision_section(read_model: CaseReadModel, latest_analysis: CaseAnalysisSnapshot) -> CaseReportSection:
    provisional = read_model.provisional_insights

    return CaseReportSection(
        key="decision",
        title="Decision Summary",
        summary=latest_analysis.summary or provisional.summary,
        items=[
            CaseReportItem(
                key="latest_decision",
                title="Latest case assessment",
                summary=latest_analysis.decision_reason or latest_analysis.summary,
                tone=_decision_tone(latest_analysis.decision_status),
                facts=[
                    _metric(
                        key="analysis_snapshot",
                        label="Snapshot type",
                        value="finalized" if latest_analysis.is_final else "provisional",
                        display_value="Finalized" if latest_analysis.is_final else "Provisional",
                        tone="good" if latest_analysis.is_final else "warning",
                    ),
                    _metric(
                        key="decision_status",
                        label="Decision status",
                        value=_enum_value(latest_analysis.decision_status),
                        display_value=_status_label(latest_analysis.decision_status),
                        tone=_decision_tone(latest_analysis.decision_status),
                    ),
                    _metric(
                        key="recommendation",
                        label="Recommendation",
                        value=_enum_value(latest_analysis.recommendation),
                        display_value=_status_label(latest_analysis.recommendation),
                        tone=_decision_tone(latest_analysis.decision_status),
                    ),
                    _metric(
                        key="risk_score",
                        label="Risk score",
                        value=latest_analysis.risk_score,
                        display_value=_scalar_display(latest_analysis.risk_score),
                        tone=_risk_tone(latest_analysis.risk_score),
                    ),
                    _metric(
                        key="confidence",
                        label="Confidence",
                        value=latest_analysis.confidence,
                        display_value=_confidence_percent(latest_analysis.confidence),
                    ),
                    _metric(
                        key="data_completeness",
                        label="Data completeness",
                        value=latest_analysis.data_completeness,
                        display_value=_confidence_percent(latest_analysis.data_completeness),
                    ),
                ],
                bullets=[],
            )
        ],
    )


def _build_applicant_section(read_model: CaseReadModel) -> CaseReportSection:
    intake = read_model.applicant_intake
    return CaseReportSection(
        key="applicant",
        title="Applicant Intake",
        summary="Applicant-provided intake details and completeness status.",
        items=[
            CaseReportItem(
                key="applicant_profile",
                title="Applicant profile",
                summary=read_model.case.applicant_name or read_model.case.name or "Applicant details pending.",
                facts=[
                    _metric("applicant_name", "Applicant name", read_model.case.applicant_name, _scalar_display(read_model.case.applicant_name)),
                    _metric("applicant_email", "Applicant email", read_model.case.applicant_email, _scalar_display(read_model.case.applicant_email)),
                    _metric("applicant_phone", "Applicant phone", read_model.case.applicant_phone, _scalar_display(read_model.case.applicant_phone)),
                    _metric(
                        "intake_completeness",
                        "Intake completeness",
                        intake.completeness,
                        _confidence_percent(intake.completeness),
                        tone="good" if intake.completeness >= 0.8 else "warning",
                    ),
                ],
                bullets=[
                    f"Completed fields: {', '.join(intake.completed_fields) if intake.completed_fields else 'None'}",
                    f"Missing fields: {', '.join(intake.missing_fields) if intake.missing_fields else 'None'}",
                ],
            )
        ],
    )


def _build_documents_section(read_model: CaseReadModel) -> CaseReportSection:
    items: list[CaseReportItem] = []
    for document in read_model.documents:
        latest_analysis = document.latest_analysis
        document_bullets = []
        if latest_analysis is not None:
            document_bullets.extend(alert.message for alert in (latest_analysis.risk_alerts or []))
        if not document_bullets:
            document_bullets.append(
                "No document risk findings are currently listed."
                if latest_analysis is not None
                else "No document analysis has been saved yet."
            )

        items.append(
            CaseReportItem(
                key=document.id,
                title=document.original_filename,
                summary=latest_analysis.summary if latest_analysis is not None else "No analysis summary available yet.",
                tone=_document_status_tone(document.status),
                facts=[
                    _metric("document_type", "Document type", document.document_type, _status_label(document.document_type)),
                    _metric("document_status", "Processing status", document.status, _status_label(document.status), tone=_document_status_tone(document.status)),
                    _metric("decision_status", "Decision status", getattr(latest_analysis, "decision_status", None), _status_label(getattr(latest_analysis, "decision_status", None)), tone=_decision_tone(getattr(latest_analysis, "decision_status", None))),
                    _metric("risk_score", "Risk score", getattr(latest_analysis, "risk_score", None), _scalar_display(getattr(latest_analysis, "risk_score", None)), tone=_risk_tone(getattr(latest_analysis, "risk_score", None))),
                    _metric("confidence", "Confidence", getattr(latest_analysis, "confidence", None), _confidence_percent(getattr(latest_analysis, "confidence", None))),
                ],
                bullets=document_bullets,
            )
        )

    return CaseReportSection(
        key="documents",
        title="Document Coverage",
        summary="Uploaded documents and their latest available analysis state.",
        items=items,
    )


def _build_comparisons_section(read_model: CaseReadModel) -> CaseReportSection | None:
    items: list[CaseReportItem] = []
    for comparison in read_model.cross_document_comparisons:
        bullets = [
            f"{_status_label(value.document_type)} ({value.original_filename}): {_scalar_display(value.value)}"
            for value in comparison.values
        ]
        items.append(
            CaseReportItem(
                key=comparison.field,
                title=comparison.label,
                summary=comparison.summary,
                tone="danger" if comparison.status == "mismatch" else "good" if comparison.status == "consistent" else "warning",
                bullets=bullets,
            )
        )
    if not items:
        return None

    return CaseReportSection(
        key="comparisons",
        title="Cross-document Checks",
        summary="Comparison results across analyzed evidence.",
        items=items,
    )


def _build_fraud_section(read_model: CaseReadModel) -> CaseReportSection | None:
    if not read_model.fraud_signals:
        return CaseReportSection(
            key="fraud_signals",
            title="Fraud and Mismatch Signals",
            summary="Cross-document fraud and mismatch checks from the available evidence.",
            items=[
                CaseReportItem(
                    key="fraud_empty",
                    title="No cross-document fraud or mismatch signals detected",
                    summary="Document-specific risk findings remain separate from fraud and mismatch checks.",
                    tone="good",
                    bullets=[],
                )
            ],
        )

    items = [
        CaseReportItem(
            key=signal.key,
            title=signal.label,
            summary=signal.summary,
            tone="danger" if signal.severity == "high" else "warning",
            bullets=[
                signal.recommended_action,
                *[
                    f"{evidence.source_label}: {_scalar_display(evidence.value)}"
                    for evidence in signal.evidence
                ],
            ],
        )
        for signal in read_model.fraud_signals
    ]
    return CaseReportSection(
        key="fraud_signals",
        title="Fraud and Mismatch Signals",
        summary="Signals that require verification before final underwriting.",
        items=items,
    )


def _build_followups_section(read_model: CaseReadModel, latest_analysis: CaseAnalysisSnapshot) -> CaseReportSection:
    provisional = read_model.provisional_insights
    bullets = _unique_strings(
        filter_action_followups(
            [
                *provisional.followups,
                *(load_string_list_json(latest_analysis.required_followups_json) or []),
            ]
        )
    )
    blocker_bullets = _unique_strings(
        [
            *provisional.blockers,
            *(load_string_list_json(latest_analysis.analysis_limitations_json) or []),
        ]
    )
    return CaseReportSection(
        key="followups",
        title="Actions and Blockers",
        summary="Actionable follow-ups are separated from evidence limitations and blockers.",
        items=[
            CaseReportItem(
                key="required_followups",
                title="Action follow-ups",
                summary="Actions still recommended by the current case state.",
                tone="warning" if bullets else "good",
                bullets=bullets or ["No follow-up actions are currently listed."],
            ),
            CaseReportItem(
                key="limitations",
                title="Current blockers and limitations",
                summary="Known constraints in the current evidence set.",
                tone="warning" if blocker_bullets else "good",
                bullets=blocker_bullets or ["No blocking issues are currently listed."],
            ),
        ],
    )


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(text)
    return deduped


def _build_sections(read_model: CaseReadModel, latest_analysis: CaseAnalysisSnapshot) -> list[CaseReportSection]:
    sections = [
        _build_decision_section(read_model, latest_analysis),
        _build_applicant_section(read_model),
        _build_documents_section(read_model),
        _build_comparisons_section(read_model),
        _build_fraud_section(read_model),
        _build_followups_section(read_model, latest_analysis),
    ]
    return [section for section in sections if section is not None]


def _build_print_payload(
    *,
    title: str,
    subtitle: str,
    generated_at: datetime,
    print_filename: str,
    sections: list[CaseReportSection],
) -> CaseReportPrintPayload:
    print_sections: list[CaseReportPrintSection] = []
    for section in sections:
        paragraphs: list[str] = []
        bullets: list[str] = []
        if section.summary:
            paragraphs.append(section.summary)
        for item in section.items:
            if item.summary:
                paragraphs.append(f"{item.title}: {item.summary}")
            elif item.title:
                paragraphs.append(item.title)
            for fact in item.facts:
                paragraphs.append(f"{fact.label}: {fact.display_value}")
            bullets.extend(item.bullets)

        print_sections.append(
            CaseReportPrintSection(
                key=section.key,
                title=section.title,
                paragraphs=_unique_strings(paragraphs),
                bullets=_unique_strings(bullets),
            )
        )

    return CaseReportPrintPayload(
        title=title,
        subtitle=subtitle,
        filename=print_filename,
        generated_at=generated_at,
        footer_note=(
            "AI-generated case report. Verify the summarized findings against the original "
            "documents before making a lending decision."
        ),
        sections=print_sections,
    )


def build_case_report_payload(read_model: CaseReadModel) -> CaseReportPayload:
    latest_analysis = _latest_case_analysis(read_model)
    generated_at = _report_generated_at(read_model, latest_analysis)
    title = _report_title(read_model)
    subtitle = _report_subtitle(read_model, latest_analysis)
    print_filename = f"loanlens-case-{read_model.case.id}-report.pdf"
    generated_from = "authoritative_analysis" if latest_analysis.is_final else "live_provisional"
    sections = _build_sections(read_model, latest_analysis)
    provisional = read_model.provisional_insights

    return CaseReportPayload(
        header=CaseReportHeader(
            report_id=latest_analysis.id,
            case_id=read_model.case.id,
            title=title,
            subtitle=subtitle,
            report_status="finalized" if latest_analysis.is_final else "provisional",
            is_final=latest_analysis.is_final,
            generated_at=generated_at,
            generated_from=generated_from,
            print_filename=print_filename,
        ),
        case=read_model.case,
        applicant_intake=read_model.applicant_intake,
        latest_analysis=latest_analysis,
        documents=read_model.documents,
        overview=CaseReportOverview(
            decision_status=latest_analysis.decision_status,
            recommendation=latest_analysis.recommendation,
            summary=latest_analysis.summary or provisional.summary,
            decision_reason=latest_analysis.decision_reason,
            risk_score=latest_analysis.risk_score,
            confidence=latest_analysis.confidence,
            data_completeness=latest_analysis.data_completeness,
            analyzed_document_count=provisional.analyzed_document_count,
            pending_document_count=provisional.pending_document_count,
            failed_document_count=provisional.failed_document_count,
            fraud_signal_count=provisional.fraud_signal_count,
            blocker_count=len(provisional.blockers),
            followup_count=len(provisional.followups),
        ),
        metrics=_build_metrics(read_model, latest_analysis),
        sections=sections,
        print=_build_print_payload(
            title=title,
            subtitle=subtitle,
            generated_at=generated_at,
            print_filename=print_filename,
            sections=sections,
        ),
    )


async def get_case_report(
    db: Prisma,
    *,
    case_id: str,
    org_id: str,
) -> CaseReportPayload | None:
    read_model = await get_case_read_model(
        db=db,
        case_id=case_id,
        org_id=org_id,
    )
    if not read_model:
        return None
    return build_case_report_payload(read_model)


__all__ = [
    "build_case_report_payload",
    "get_case_report",
]
