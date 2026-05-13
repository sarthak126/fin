"""
Pydantic schemas for Analysis API responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from core.confidence import normalize_confidence, normalize_decision_status
from models import DecisionStatus, Recommendation


class RiskAlert(BaseModel):
    severity: str
    message: str
    field: str | None = None
    details: str | None = None


class AnalysisResponse(BaseModel):
    id: str
    document_id: str
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
    extracted_fields: BankStatementAnalysisOutput | dict[str, Any] | None = None
    risk_alerts: list[RiskAlert] | None = None
    summary: str | None = None
    processing_time_seconds: float | None = None
    model_used: str | None = None
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


class AnalysisSummary(BaseModel):
    """Lightweight summary for list views."""
    id: str
    document_id: str
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
    extracted_fields: str | None = None
    processing_time_seconds: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

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


class AnalysisTriggerResponse(BaseModel):
    message: str
    analysis_id: str | None = None
    document_id: str
    status: str


class AnalysisJobStatusResponse(BaseModel):
    job_id: str
    document_id: str
    status: str
    stage: str | None = None
    stage_message: str | None = None
    ocr_provider: str | None = None
    pages_processed: int | None = None
    total_pages: int | None = None
    ocr_required_pages: list[int] | None = None
    ocr_failed_pages: list[int] | None = None
    ocr_unreliable_pages: list[int] | None = None
    ocr_fallback_used: bool | None = None
    ocr_quality_status: str | None = None
    attempts: int
    max_attempts: int
    last_error: str | None = None
    error_code: str | None = None
    user_message: str | None = None


# ─────────────────────────────────────────────
# Optional: Bank statement strict output schema
# (used for validation/typing of extracted_fields/raw_response)
# ─────────────────────────────────────────────

class BankStatementDTI(BaseModel):
    value: float | int | None
    label: str
    reliability: Literal["verified", "unverified", "unavailable"] = "verified"


class BankStatementAccountProfile(BaseModel):
    bank_name: str | None = None
    branch_name: str | None = None
    branch_phone: str | None = None
    ifsc: str | None = None
    micr: str | None = None
    account_holder_name: str | None = None
    account_number_masked: str | None = None
    address_lines: List[str] = Field(default_factory=list)


class BankStatementInflowRange(BaseModel):
    min: float
    max: float
    display: str


class BankStatementCashBehavior(BaseModel):
    stress_score: int
    flags: List[str]


class BankStatementRiskScore(BaseModel):
    score_model: Literal["bank_statement_v2"] = "bank_statement_v2"
    income_stability: int
    balance_health: int
    obligation_load: int
    spending_discipline: int
    cash_behavior: int
    risk_penalty: int
    final_score: int


class StatementSummaryOutput(BaseModel):
    statement_start_date: str | None
    statement_end_date: str | None
    declared_period_start_date: str | None = None
    declared_period_end_date: str | None = None
    last_transaction_date: str | None = None
    coverage_days: int
    opening_balance: float | None
    closing_balance: float | None
    total_credits: float
    total_debits: float
    net_flow: float
    min_balance: float
    max_balance: float
    avg_balance: float
    median_balance: float
    transaction_count: int
    credit_count: int
    debit_count: int
    low_balance_count: int
    balance_volatility: float
    recurring_income_detected: bool = False
    emi_pattern_detected: bool = False
    pass_through_transfer_detected: bool = False
    verification_credits_detected: bool = False


class BankStatementTransaction(BaseModel):
    date: str
    description: str
    debit: float | None
    credit: float | None
    balance: float | None
    category: str
    confidence: float
    duplicate: bool
    reversal: bool
    verification_credit: bool = False
    pass_through_transfer: bool = False
    notes: str


class IncomeSourceDetail(BaseModel):
    type: str
    avg: float
    count: int
    total: float


class IncomeEngineOutput(BaseModel):
    income_type: str  # salary | unstable | mixed | unknown
    monthly_income_estimate: str | None  # "15000-35000", "25000", or null when gated
    confidence: float
    salary_credits: List[float]
    upi_credits: List[float]
    transfer_credits: List[float]
    cash_deposits: List[float]
    monthly_inflows: Dict[str, float]
    income_regularity_score: int
    income_sources: List[IncomeSourceDetail]
    recurring_income_detected: bool = False
    recurring_income_source: str | None = None
    recurring_income_estimate: float | None = None
    recurring_income_months: int | None = None


class CashFlowIntelligenceOutput(BaseModel):
    cash_flow_stability: str  # low | medium | high
    monthly_burn_rate: str  # low | medium | high | critical
    savings_trend: str  # improving | stable | declining | unknown
    savings_ratio: float
    monthly_net_flows: Dict[str, float]
    stability_score: int


class SpendingIntelligenceOutput(BaseModel):
    spending_categories: Dict[str, float]  # category -> % share
    category_amounts: Dict[str, float]  # category -> total amount
    top_merchants: List[Dict[str, Any]]
    total_spending: float


class BehavioralFlagDetail(BaseModel):
    flag: str
    severity: str  # high | medium | low
    detail: str


class BehavioralFlagsOutput(BaseModel):
    flags: List[str]
    flag_details: List[BehavioralFlagDetail]


class RiskBreakdownFactor(BaseModel):
    score: int
    max: int
    detail: str


class ExplainableRiskOutput(BaseModel):
    risk_breakdown: Dict[str, RiskBreakdownFactor]
    total_risk_score: int
    max_possible_risk: int
    risk_level: str  # very_low | low | medium | high | very_high


class DecisionEngineOutput(BaseModel):
    decision: str  # APPROVE | REJECT | APPROVE WITH CAUTION | REVIEW MANUALLY
    reasons: List[str]
    risk_confidence: float


class DecisionOutput(BaseModel):
    decision_status: DecisionStatus
    decision_recommendation: str
    decision_reason: str
    extraction_confidence: float
    risk_confidence: float
    data_completeness: float
    required_followups: List[str]
    analysis_limitations: List[str]

    @field_validator("decision_status", mode="before")
    @classmethod
    def _normalize_decision_status_field(cls, value):
        return normalize_decision_status(value)


class BankStatementIncomeSummary(BaseModel):
    verified: float
    unverified: float
    verified_monthly_estimate: float | None = None
    unverified_monthly_inflow_range: BankStatementInflowRange | None = None
    monthly_estimate: str | None = None
    monthly_estimate_min: float | None = None
    monthly_estimate_max: float | None = None
    annual_estimate: float | None = None
    annual_estimate_min: float | None = None
    annual_estimate_max: float | None = None
    income_type: str | None = None
    confidence: float | None = None


class BankStatementExpenseSummary(BaseModel):
    total: float
    emi: float
    penalties: float


class BankStatementCashFlowSummary(BaseModel):
    withdrawals: float
    deposits: float


class BankStatementBalanceSummary(BaseModel):
    average: float
    median: float
    min: float
    max: float
    opening: float | None
    closing: float | None
    volatility: float


class TransactionInsightsOutput(BaseModel):
    document_type: str
    statement_quality: str
    statement_confidence: float
    income: BankStatementIncomeSummary
    expenses: BankStatementExpenseSummary
    cash_flow: BankStatementCashFlowSummary
    balance: BankStatementBalanceSummary
    dti: BankStatementDTI
    cash_behavior: BankStatementCashBehavior
    income_engine: Optional[IncomeEngineOutput] = None
    cash_flow_intelligence: Optional[CashFlowIntelligenceOutput] = None
    spending_intelligence: Optional[SpendingIntelligenceOutput] = None


class RiskFindingsOutput(BaseModel):
    alerts: List[RiskAlert]
    flags: List[str]
    risk_score: BankStatementRiskScore
    behavioral_flags: Optional[BehavioralFlagsOutput] = None
    explainable_risk: Optional[ExplainableRiskOutput] = None


class ReasoningOutput(BaseModel):
    summary: str | None = None
    narrative: List[str]
    required_followups: List[str]
    analysis_limitations: List[str]


class BankStatementAnalysisOutput(BaseModel):
    decision: DecisionOutput
    account_profile: BankStatementAccountProfile | None = None
    statement_summary: StatementSummaryOutput
    transaction_insights: TransactionInsightsOutput
    risk_findings: RiskFindingsOutput
    reasoning: ReasoningOutput
    transactions: List[BankStatementTransaction]

    model_config = {"extra": "forbid"}
