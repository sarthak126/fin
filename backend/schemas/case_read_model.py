"""
Schemas for the aggregated case read model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from core.confidence import normalize_confidence, normalize_decision_status
from models import CaseStatus, DecisionStatus, DocumentStatus, DocumentType, Recommendation
from schemas.analysis import AnalysisResponse, BankStatementAccountProfile, RiskAlert
from schemas.case import CaseDetail


class CaseApplicantIntake(BaseModel):
    applicant_name: str | None = None
    applicant_email: str | None = None
    applicant_phone: str | None = None
    completed_fields: list[str]
    missing_fields: list[str]
    completeness: float


class CaseDocumentOcrStatus(BaseModel):
    ocr_quality_status: str | None = None
    ocr_required_pages: list[int] = Field(default_factory=list)
    ocr_failed_pages: list[int] = Field(default_factory=list)
    ocr_unreliable_pages: list[int] = Field(default_factory=list)
    ocr_fallback_used: bool = False
    ocr_provider: str | None = None
    extraction_schema_version: int | None = None
    extraction_status: str | None = None
    stage: str | None = None
    stage_message: str | None = None
    pages_processed: int | None = None
    total_pages: int | None = None
    analysis_blocked: bool = False
    error_code: str | None = None
    user_message: str | None = None


class CaseDocumentEvidenceProfile(BaseModel):
    account_profile: BankStatementAccountProfile | None = None
    declared_period_start_date: str | None = None
    declared_period_end_date: str | None = None
    last_transaction_date: str | None = None


class CaseDocumentReadModel(BaseModel):
    id: str
    case_id: str | None = None
    filename: str
    original_filename: str
    file_url: str | None = None
    file_type: str
    document_type: DocumentType
    status: DocumentStatus
    file_size_bytes: int
    created_at: datetime
    updated_at: datetime
    user_id: str
    org_id: str
    latest_analysis: AnalysisResponse | None = None
    ocr_status: CaseDocumentOcrStatus | None = None
    evidence_profile: CaseDocumentEvidenceProfile | None = None


class SupportedDocumentRequirement(BaseModel):
    key: str
    label: str
    accepted_document_types: list[DocumentType]
    document_ids: list[str]
    provided_count: int
    analyzed_count: int
    status: str


class SupportedDocumentCompleteness(BaseModel):
    provided_score: float
    analyzed_score: float
    provided_requirement_count: int
    analyzed_requirement_count: int
    total_requirement_count: int
    present_document_types: list[DocumentType]
    missing_document_types: list[DocumentType]
    missing_requirement_keys: list[str]
    pending_requirement_keys: list[str]
    requirements: list[SupportedDocumentRequirement]


class CrossDocumentComparisonValue(BaseModel):
    document_id: str
    document_type: DocumentType
    original_filename: str
    analysis_id: str | None = None
    value: Any


class CrossDocumentComparison(BaseModel):
    field: str
    label: str
    status: str
    summary: str
    values: list[CrossDocumentComparisonValue]


class FraudSignalEvidence(BaseModel):
    source_type: str
    source_label: str
    field: str
    value: Any
    document_id: str | None = None
    document_type: DocumentType | None = None
    original_filename: str | None = None
    analysis_id: str | None = None


class FraudSignal(BaseModel):
    key: str
    label: str
    severity: str
    summary: str
    details: str
    recommended_action: str
    evidence: list[FraudSignalEvidence]


class CaseProvisionalInsights(BaseModel):
    decision_status: DecisionStatus | None = None
    recommendation: Recommendation | None = None
    summary: str
    blockers: list[str]
    followups: list[str]
    highest_risk_score: float | None = None
    average_risk_score: float | None = None
    analyzed_document_count: int
    pending_document_count: int
    failed_document_count: int
    conflict_fields: list[str]
    fraud_signal_count: int
    fraud_signal_keys: list[str]
    document_decision_counts: dict[str, int]


class CaseAnalysisSnapshot(BaseModel):
    id: str
    case_id: str
    case_status: CaseStatus
    is_final: bool = False
    risk_score: float | None = None
    confidence: float | None = None
    recommendation: Recommendation | None = None
    decision_status: DecisionStatus | None = None
    decision_recommendation: str | None = None
    decision_reason: str | None = None
    extraction_confidence: float | None = None
    risk_confidence: float | None = None
    data_completeness: float | None = None
    required_followups_json: str | None = None
    analysis_limitations_json: str | None = None
    extracted_fields: dict[str, Any] | None = None
    risk_alerts: list[RiskAlert] | None = None
    summary: str | None = None
    processing_time_seconds: float | None = None
    model_used: str | None = None
    raw_response: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True, "protected_namespaces": ()}

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, value):
        if value is None:
            return None
        return normalize_confidence(value)

    @field_validator("extraction_confidence", "risk_confidence", "data_completeness", mode="before")
    @classmethod
    def _normalize_decision_confidence_fields(cls, value):
        if value is None:
            return None
        return normalize_confidence(value)

    @field_validator("decision_status", mode="before")
    @classmethod
    def _normalize_decision_status_field(cls, value):
        if value is None:
            return None
        return normalize_decision_status(value)


class CaseReadModel(BaseModel):
    case: CaseDetail
    applicant_intake: CaseApplicantIntake
    documents: list[CaseDocumentReadModel]
    supported_document_completeness: SupportedDocumentCompleteness
    cross_document_comparisons: list[CrossDocumentComparison]
    fraud_signals: list[FraudSignal]
    provisional_insights: CaseProvisionalInsights
    authoritative_analysis: CaseAnalysisSnapshot | None = None
