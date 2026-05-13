"""
Schemas for case report rendering and print export payloads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from models import DecisionStatus, Recommendation
from schemas.case import CaseDetail
from schemas.case_read_model import (
    CaseAnalysisSnapshot,
    CaseApplicantIntake,
    CaseDocumentReadModel,
)


class CaseReportMetric(BaseModel):
    key: str
    label: str
    value: Any = None
    display_value: str
    tone: str = "neutral"
    hint: str | None = None


class CaseReportItem(BaseModel):
    key: str
    title: str
    summary: str | None = None
    tone: str = "neutral"
    facts: list[CaseReportMetric] = []
    bullets: list[str] = []


class CaseReportSection(BaseModel):
    key: str
    title: str
    summary: str | None = None
    items: list[CaseReportItem] = []


class CaseReportPrintSection(BaseModel):
    key: str
    title: str
    paragraphs: list[str] = []
    bullets: list[str] = []


class CaseReportPrintPayload(BaseModel):
    title: str
    subtitle: str | None = None
    filename: str
    generated_at: datetime
    footer_note: str
    sections: list[CaseReportPrintSection] = []


class CaseReportHeader(BaseModel):
    report_id: str
    case_id: str
    title: str
    subtitle: str | None = None
    report_status: str
    is_final: bool = False
    generated_at: datetime
    generated_from: str
    print_filename: str


class CaseReportOverview(BaseModel):
    decision_status: DecisionStatus | None = None
    recommendation: Recommendation | None = None
    summary: str
    decision_reason: str | None = None
    risk_score: float | None = None
    confidence: float | None = None
    data_completeness: float | None = None
    analyzed_document_count: int
    pending_document_count: int
    failed_document_count: int
    fraud_signal_count: int
    blocker_count: int
    followup_count: int


class CaseReportPayload(BaseModel):
    header: CaseReportHeader
    case: CaseDetail
    applicant_intake: CaseApplicantIntake
    latest_analysis: CaseAnalysisSnapshot
    documents: list[CaseDocumentReadModel]
    overview: CaseReportOverview
    metrics: list[CaseReportMetric]
    sections: list[CaseReportSection]
    print: CaseReportPrintPayload
