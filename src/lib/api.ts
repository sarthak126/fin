/**
 * ArgentNorth AI — API client for communicating with the FastAPI backend.
 */
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readErrorDetail(res: Response, fallback: string): Promise<string> {
  const contentType = res.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    const err = await res
      .json()
      .catch(() => null) as { detail?: unknown; message?: unknown } | null;
    if (typeof err?.detail === "string" && err.detail.trim()) {
      return err.detail;
    }
    if (typeof err?.message === "string" && err.message.trim()) {
      return err.message;
    }
  } else {
    const text = await res.text().catch(() => "");
    if (text.trim()) {
      return text.trim();
    }
  }

  const statusText = res.statusText.trim();
  return statusText ? `${fallback} (${res.status} ${statusText})` : `${fallback} (${res.status})`;
}

async function throwApiError(res: Response, fallback: string): Promise<never> {
  throw new ApiError(res.status, await readErrorDetail(res, fallback));
}
/**
 * Upload a supported document to the backend.
 * Returns the created document record.
 */
export interface UploadDocumentRequest {
  file: File;
  token: string;
  password?: string;
  documentType?: string;
  caseId?: string;
  applicantName?: string;
  applicantEmail?: string;
  applicantPhone?: string;
}

export async function uploadDocument({
  file,
  token,
  password,
  documentType,
  caseId,
  applicantName,
  applicantEmail,
  applicantPhone,
}: UploadDocumentRequest): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (password) {
    formData.append("password", password);
  }
  if (documentType) {
    formData.append("document_type", documentType);
  }
  if (caseId) {
    formData.append("case_id", caseId);
  }
  if (applicantName) {
    formData.append("applicant_name", applicantName);
  }
  if (applicantEmail) {
    formData.append("applicant_email", applicantEmail);
  }
  if (applicantPhone) {
    formData.append("applicant_phone", applicantPhone);
  }

  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  if (!res.ok) {
    await throwApiError(res, "Upload failed");
  }

  return res.json();
}

/**
 * Trigger AI analysis on an uploaded document.
 */
export async function triggerAnalysis(documentId: string, token: string): Promise<AnalysisTriggerResponse> {
  const res = await fetch(`${API_BASE}/analysis/documents/${documentId}/analyze`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    await throwApiError(res, "Analysis failed");
  }

  return res.json();
}

/**
 * List all documents for the org.
 */
export async function listDocuments(token: string): Promise<DocumentListItem[]> {
  const res = await fetch(`${API_BASE}/documents`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) {
    await throwApiError(res, "Failed to fetch documents");
  }
  return res.json();
}

/**
 * Get a single document by ID.
 */
export async function getDocument(id: string, token: string): Promise<DocumentDetail> {
  const res = await fetch(`${API_BASE}/documents/${id}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) await throwApiError(res, "Failed to load document");
  return res.json();
}

/**
 * Get the latest analysis for a document.
 */
export async function getAnalysis(documentId: string, token: string): Promise<AnalysisResponse> {
  const res = await fetch(`${API_BASE}/analysis/documents/${documentId}/latest`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) await throwApiError(res, "Failed to load analysis");
  return res.json();
}

/**
 * List all cases for the org.
 */
export async function listCases(token: string): Promise<CaseListItem[]> {
  const res = await fetch(`${API_BASE}/cases`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    await throwApiError(res, "Failed to fetch cases");
  }

  return res.json();
}

/**
 * Aggregated case counts and N most-recent cases for the Command Center.
 */
export async function getCaseSummary(
  token: string,
  options: { recentLimit?: number } = {},
): Promise<CaseSummaryResponse> {
  const params = new URLSearchParams();
  if (options.recentLimit !== undefined) {
    params.set("recent_limit", String(options.recentLimit));
  }
  const query = params.toString();
  const url = `${API_BASE}/cases/summary${query ? `?${query}` : ""}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    await throwApiError(res, "Failed to load case summary");
  }

  return res.json();
}

/**
 * Get a single case by ID.
 */
export async function getCase(id: string, token: string): Promise<CaseDetail> {
  const res = await fetch(`${API_BASE}/cases/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) await throwApiError(res, "Failed to load case");
  return res.json();
}

/**
 * Get the latest case-level analysis snapshot.
 */
export async function getCaseLatestAnalysis(id: string, token: string): Promise<CaseAnalysisSnapshot> {
  const res = await fetch(`${API_BASE}/cases/${id}/analysis/latest`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) await throwApiError(res, "Failed to load case analysis");
  return res.json();
}

/**
 * Get the aggregated case read model with documents, latest analyses, and
 * provisional cross-document insights.
 */
export async function getCaseReadModel(id: string, token: string): Promise<CaseReadModel> {
  const res = await fetch(`${API_BASE}/cases/${id}/read-model`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) await throwApiError(res, "Failed to load case data");
  return res.json();
}

/**
 * Ask AI a question about a case-level report.
 */
export async function askAboutCase(caseId: string, question: string, token: string): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/cases/${caseId}/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({ question }),
  });

  if (!res.ok) {
    await throwApiError(res, "Ask failed");
  }

  return res.json();
}

/**
 * Finalize a case and create the authoritative case snapshot.
 */
export async function finalizeCase(id: string, token: string): Promise<CaseReadModel> {
  const res = await fetch(`${API_BASE}/cases/${id}/finalize`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) await throwApiError(res, "Failed to finalize case");
  return res.json();
}

/**
 * Get a structured case report for UI rendering and print export.
 */
export async function getCaseReport(id: string, token: string): Promise<CaseReportPayload> {
  const res = await fetch(`${API_BASE}/cases/${id}/report`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) await throwApiError(res, "Failed to load case report");
  return res.json();
}

/**
 * Create a new case.
 */
export async function createCase(payload: CreateCaseRequest, token: string): Promise<CaseDetail> {
  const res = await fetch(`${API_BASE}/cases`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    await throwApiError(res, "Case creation failed");
  }

  return res.json();
}

/**
 * Update applicant information on an existing case.
 */
export async function updateCaseApplicantInfo(
  caseId: string,
  payload: UpdateCaseApplicantInfoRequest,
  token: string
): Promise<CaseDetail> {
  const res = await fetch(`${API_BASE}/cases/${caseId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    await throwApiError(res, "Case update failed");
  }

  return res.json();
}

/**
 * Fetch the background analysis job status for a document.
 */
export async function getAnalysisJobStatus(
  documentId: string,
  token: string
): Promise<AnalysisJobStatusResponse> {
  const res = await fetch(`${API_BASE}/analysis/documents/${documentId}/job`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    await throwApiError(res, "Failed to load analysis job");
  }

  return res.json();
}

/**
 * Ask AI a question about an analyzed document.
 */
export async function askAboutDocument(documentId: string, question: string, token: string): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/ask/${documentId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({ question }),
  });

  if (!res.ok) {
    await throwApiError(res, "Ask failed");
  }

  return res.json();
}

/**
 * Sync the authenticated Clerk session with the backend user/org mapping.
 */
export async function syncCurrentUser(token: string): Promise<CurrentUserResponse> {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    await throwApiError(res, "Authentication sync failed");
  }

  return res.json();
}

// ── Types ──

export interface DocumentUploadResponse {
  id: string;
  case_id: string | null;
  filename: string;
  original_filename: string;
  document_type: string;
  status: string;
  file_size_bytes: number;
  created_at: string;
}

export interface AnalysisTriggerResponse {
  message: string;
  analysis_id: string | null;
  document_id: string;
  status: string;
}

export interface DocumentListItem {
  id: string;
  case_id: string | null;
  original_filename: string;
  document_type: string;
  status: string;
  file_size_bytes: number;
  created_at: string;
  updated_at: string;
  analyses?: AnalysisSummary[];
}

export type CaseStatus = "draft" | "collecting" | "finalized";

export interface CaseListItem {
  id: string;
  name: string | null;
  status: CaseStatus;
  applicant_name: string | null;
  applicant_email: string | null;
  applicant_phone: string | null;
  legacy_source_document_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CaseDetail extends CaseListItem {
  user_id: string;
  org_id: string;
}

export interface CaseStatusCount {
  status: CaseStatus;
  count: number;
}

export interface CaseSummaryResponse {
  total_count: number;
  by_status: CaseStatusCount[];
  recent_cases: CaseListItem[];
}

export interface CreateCaseRequest {
  name?: string | null;
  status?: CaseStatus;
  applicant_name?: string | null;
  applicant_email?: string | null;
  applicant_phone?: string | null;
}

export interface UpdateCaseApplicantInfoRequest {
  applicant_name?: string | null;
  applicant_email?: string | null;
  applicant_phone?: string | null;
}

export interface CaseApplicantIntake {
  applicant_name: string | null;
  applicant_email: string | null;
  applicant_phone: string | null;
  completed_fields: string[];
  missing_fields: string[];
  completeness: number;
}

export interface CaseDocumentOcrStatus {
  ocr_quality_status: "pending" | "clean" | "degraded" | "blocked" | null;
  ocr_required_pages: number[];
  ocr_failed_pages: number[];
  ocr_unreliable_pages: number[];
  ocr_fallback_used: boolean;
  ocr_provider: string | null;
  extraction_schema_version: number | null;
  extraction_status: string | null;
  stage: string | null;
  stage_message: string | null;
  pages_processed: number | null;
  total_pages: number | null;
  analysis_blocked: boolean;
  error_code: string | null;
  user_message: string | null;
}

export interface BankStatementAccountProfile {
  bank_name?: string | null;
  branch_name?: string | null;
  branch_phone?: string | null;
  ifsc?: string | null;
  micr?: string | null;
  account_holder_name?: string | null;
  account_number_masked?: string | null;
  address_lines?: string[];
}

export interface CaseDocumentEvidenceProfile {
  account_profile: BankStatementAccountProfile | null;
  declared_period_start_date: string | null;
  declared_period_end_date: string | null;
  last_transaction_date: string | null;
}

export interface CaseDocumentReadModel {
  id: string;
  case_id: string | null;
  filename: string;
  original_filename: string;
  file_url: string | null;
  file_type: string;
  document_type: string;
  status: string;
  file_size_bytes: number;
  created_at: string;
  updated_at: string;
  user_id: string;
  org_id: string;
  latest_analysis: AnalysisResponse | null;
  ocr_status: CaseDocumentOcrStatus | null;
  evidence_profile?: CaseDocumentEvidenceProfile | null;
}

export type SupportedDocumentRequirementStatus = "complete" | "pending" | "missing";

export interface SupportedDocumentRequirement {
  key: string;
  label: string;
  accepted_document_types: string[];
  document_ids: string[];
  provided_count: number;
  analyzed_count: number;
  status: SupportedDocumentRequirementStatus;
}

export interface SupportedDocumentCompleteness {
  provided_score: number;
  analyzed_score: number;
  provided_requirement_count: number;
  analyzed_requirement_count: number;
  total_requirement_count: number;
  present_document_types: string[];
  missing_document_types: string[];
  missing_requirement_keys: string[];
  pending_requirement_keys: string[];
  requirements: SupportedDocumentRequirement[];
}

export interface CrossDocumentComparisonValue {
  document_id: string;
  document_type: string;
  original_filename: string;
  analysis_id: string | null;
  value: unknown;
}

export type CrossDocumentComparisonStatus = "consistent" | "mismatch" | "insufficient_data";

export interface CrossDocumentComparison {
  field: string;
  label: string;
  status: CrossDocumentComparisonStatus;
  summary: string;
  values: CrossDocumentComparisonValue[];
}

export interface FraudSignalEvidence {
  source_type: string;
  source_label: string;
  field: string;
  value: unknown;
  document_id: string | null;
  document_type: string | null;
  original_filename: string | null;
  analysis_id: string | null;
}

export interface FraudSignal {
  key: string;
  label: string;
  severity: "high" | "medium" | "low";
  summary: string;
  details: string;
  recommended_action: string;
  evidence: FraudSignalEvidence[];
}

export interface CaseProvisionalInsights {
  decision_status: DecisionStatus | null;
  recommendation: "approve" | "review" | "reject" | null;
  summary: string;
  blockers: string[];
  followups: string[];
  highest_risk_score: number | null;
  average_risk_score: number | null;
  analyzed_document_count: number;
  pending_document_count: number;
  failed_document_count: number;
  conflict_fields: string[];
  fraud_signal_count: number;
  fraud_signal_keys: string[];
  document_decision_counts: Record<string, number>;
}

export interface CaseAnalysisSnapshot {
  id: string;
  case_id: string;
  case_status: CaseStatus;
  is_final: boolean;
  risk_score: number | null;
  confidence: number | null;
  recommendation: "approve" | "review" | "reject" | null;
  decision_status: DecisionStatus | null;
  decision_recommendation: string | null;
  decision_reason: string | null;
  extraction_confidence: number | null;
  risk_confidence: number | null;
  data_completeness: number | null;
  required_followups_json: string | null;
  analysis_limitations_json: string | null;
  extracted_fields: Record<string, unknown> | null;
  risk_alerts: RiskAlert[] | null;
  summary: string | null;
  processing_time_seconds: number | null;
  model_used: string | null;
  raw_response: Record<string, unknown> | null;
  created_at: string;
}

export interface CaseReportMetric {
  key: string;
  label: string;
  value: unknown;
  display_value: string;
  tone: "good" | "warning" | "danger" | "neutral" | string;
  hint: string | null;
}

export interface CaseReportItem {
  key: string;
  title: string;
  summary: string | null;
  tone: "good" | "warning" | "danger" | "neutral" | string;
  facts: CaseReportMetric[];
  bullets: string[];
}

export interface CaseReportSection {
  key: string;
  title: string;
  summary: string | null;
  items: CaseReportItem[];
}

export interface CaseReportPrintSection {
  key: string;
  title: string;
  paragraphs: string[];
  bullets: string[];
}

export interface CaseReportPrintPayload {
  title: string;
  subtitle: string | null;
  filename: string;
  generated_at: string;
  footer_note: string;
  sections: CaseReportPrintSection[];
}

export interface CaseReportHeader {
  report_id: string;
  case_id: string;
  title: string;
  subtitle: string | null;
  report_status: "finalized" | "provisional" | string;
  is_final: boolean;
  generated_at: string;
  generated_from: "authoritative_analysis" | "live_provisional" | string;
  print_filename: string;
}

export interface CaseReportOverview {
  decision_status: DecisionStatus | null;
  recommendation: "approve" | "review" | "reject" | null;
  summary: string;
  decision_reason: string | null;
  risk_score: number | null;
  confidence: number | null;
  data_completeness: number | null;
  analyzed_document_count: number;
  pending_document_count: number;
  failed_document_count: number;
  fraud_signal_count: number;
  blocker_count: number;
  followup_count: number;
}

export interface CaseReportPayload {
  header: CaseReportHeader;
  case: CaseDetail;
  applicant_intake: CaseApplicantIntake;
  latest_analysis: CaseAnalysisSnapshot;
  documents: CaseDocumentReadModel[];
  overview: CaseReportOverview;
  metrics: CaseReportMetric[];
  sections: CaseReportSection[];
  print: CaseReportPrintPayload;
}

export interface CaseReadModel {
  case: CaseDetail;
  applicant_intake: CaseApplicantIntake;
  documents: CaseDocumentReadModel[];
  supported_document_completeness: SupportedDocumentCompleteness;
  cross_document_comparisons: CrossDocumentComparison[];
  fraud_signals: FraudSignal[];
  provisional_insights: CaseProvisionalInsights;
  authoritative_analysis: CaseAnalysisSnapshot | null;
}

export type DecisionStatus = "approve" | "manual_review" | "reject" | "insufficient_history";

export interface AnalysisDecision {
  decision_status: DecisionStatus;
  decision_recommendation: string;
  decision_reason: string;
  extraction_confidence: number;
  risk_confidence: number;
  data_completeness: number;
  required_followups: string[];
  analysis_limitations: string[];
}

export interface BankStatementCashBehavior {
  stress_score: number;
  flags: string[];
}

export interface BankStatementRiskScore {
  score_model: "bank_statement_v2";
  income_stability: number;
  balance_health: number;
  obligation_load: number;
  spending_discipline: number;
  cash_behavior: number;
  risk_penalty: number;
  final_score: number;
}

export interface BankStatementTransaction {
  date: string;
  description: string;
  debit: number | null;
  credit: number | null;
  balance: number | null;
  category: string;
  confidence: number;
  duplicate: boolean;
  reversal: boolean;
  verification_credit: boolean;
  pass_through_transfer: boolean;
  notes: string;
}

export interface BankStatementSummary {
  statement_start_date: string | null;
  statement_end_date: string | null;
  declared_period_start_date?: string | null;
  declared_period_end_date?: string | null;
  last_transaction_date?: string | null;
  coverage_days: number;
  opening_balance: number;
  closing_balance: number;
  total_credits: number;
  total_debits: number;
  net_flow: number;
  min_balance: number;
  max_balance: number;
  avg_balance: number;
  median_balance: number;
  transaction_count: number;
  credit_count: number;
  debit_count: number;
  low_balance_count: number;
  balance_volatility: number;
  recurring_income_detected: boolean;
  emi_pattern_detected: boolean;
  pass_through_transfer_detected: boolean;
  verification_credits_detected: boolean;
}

export interface BankStatementIncomeSource {
  type: string;
  avg: number;
  count: number;
  total: number;
}

export interface BankStatementIncomeEngine {
  income_type: string;
  monthly_income_estimate: string | null;
  monthly_income_estimate_min?: number | null;
  monthly_income_estimate_max?: number | null;
  annual_income_estimate_min?: number | null;
  annual_income_estimate_max?: number | null;
  confidence: number;
  salary_credits: number[];
  upi_credits: number[];
  transfer_credits: number[];
  cash_deposits: number[];
  other_credits?: number[];
  monthly_inflows: Record<string, number>;
  income_regularity_score: number;
  income_sources: BankStatementIncomeSource[];
  recurring_income_detected?: boolean;
  recurring_income_source?: string | null;
  recurring_income_estimate?: number | null;
  recurring_income_months?: number | null;
  income_inference_skipped?: boolean;
  skip_reason?: string;
}

export interface BankStatementCashFlowIntelligence {
  cash_flow_stability: string;
  monthly_burn_rate: string;
  savings_trend: string;
  savings_ratio: number;
  monthly_net_flows: Record<string, number>;
  stability_score: number;
}

export interface BankStatementSpendingIntelligence {
  spending_categories: Record<string, number>;
  category_amounts: Record<string, number>;
  top_merchants: { name: string; total: number; count: number }[];
  total_spending: number;
}

export interface BankStatementBehavioralFlags {
  flags: string[];
  flag_details: { flag: string; severity: string; detail: string }[];
}

export interface BankStatementExplainableRisk {
  risk_breakdown: Record<string, { score: number; max: number; detail: string }>;
  total_risk_score: number;
  max_possible_risk: number;
  risk_level: string;
}

export interface BankStatementIncomeSummary {
  verified: number;
  unverified: number;
  verified_monthly_estimate?: number | null;
  unverified_monthly_inflow_range?: { min: number; max: number; display: string } | null;
  monthly_estimate: string | null;
  monthly_estimate_min?: number | null;
  monthly_estimate_max?: number | null;
  annual_estimate: number | null;
  annual_estimate_min?: number | null;
  annual_estimate_max?: number | null;
  income_type: string | null;
  confidence: number | null;
}

export interface BankStatementExpenseSummary {
  total: number;
  emi: number;
  penalties: number;
}

export interface BankStatementCashFlowSummary {
  withdrawals: number;
  deposits: number;
}

export interface BankStatementBalanceSummary {
  average: number;
  median: number;
  min: number;
  max: number;
  opening: number;
  closing: number;
  volatility: number;
}

export interface BankStatementDTI {
  value: number | null;
  label: string;
  reliability?: "verified" | "unverified" | "unavailable";
}

export interface BankStatementTransactionInsights {
  document_type: string;
  statement_quality: string;
  statement_confidence: number;
  income: BankStatementIncomeSummary;
  expenses: BankStatementExpenseSummary;
  cash_flow: BankStatementCashFlowSummary;
  balance: BankStatementBalanceSummary;
  dti: BankStatementDTI;
  cash_behavior: BankStatementCashBehavior;
  income_engine: BankStatementIncomeEngine | null;
  cash_flow_intelligence: BankStatementCashFlowIntelligence | null;
  spending_intelligence: BankStatementSpendingIntelligence | null;
}

export interface BankStatementRiskFindings {
  alerts: RiskAlert[];
  flags: string[];
  risk_score: BankStatementRiskScore;
  behavioral_flags: BankStatementBehavioralFlags | null;
  explainable_risk: BankStatementExplainableRisk | null;
}

export interface BankStatementReasoning {
  summary: string | null;
  narrative: string[];
  required_followups: string[];
  analysis_limitations: string[];
}

export interface BankStatementAnalysisPayload {
  decision: AnalysisDecision;
  account_profile?: BankStatementAccountProfile | null;
  statement_summary: BankStatementSummary;
  transaction_insights: BankStatementTransactionInsights;
  risk_findings: BankStatementRiskFindings;
  reasoning: BankStatementReasoning;
  transactions: BankStatementTransaction[];
}

export type AnalysisExtractedFields = BankStatementAnalysisPayload | Record<string, unknown>;

export function isBankStatementAnalysisPayload(
  value: AnalysisExtractedFields | null | undefined
): value is BankStatementAnalysisPayload {
  return Boolean(
    value &&
      typeof value === "object" &&
      "decision" in value &&
      "statement_summary" in value &&
      "transaction_insights" in value &&
      "risk_findings" in value &&
      "reasoning" in value &&
      "transactions" in value
  );
}

export interface AnalysisSummary {
  id: string;
  document_id: string;
  risk_score: number | null;
  confidence: number | null;
  recommendation: "approve" | "review" | "reject" | null;
  decision_status: DecisionStatus | null;
  decision_recommendation: string | null;
  decision_reason: string | null;
  extraction_confidence: number | null;
  risk_confidence: number | null;
  data_completeness: number | null;
  required_followups_json: string | null;
  analysis_limitations_json: string | null;
  extracted_fields: string | null;
  processing_time_seconds: number | null;
  created_at: string;
}

export interface DocumentDetail extends DocumentListItem {
  filename: string;
  file_url: string | null;
  file_type: string;
  user_id: string;
  org_id: string;
}

export interface RiskAlert {
  severity: "high" | "medium" | "low";
  message: string;
  field?: string | null;
  details?: string | null;
}

export interface AnalysisResponse {
  id: string;
  document_id: string;
  risk_score: number | null;
  confidence: number | null;
  recommendation: "approve" | "review" | "reject" | null;
  decision_status: DecisionStatus | null;
  decision_recommendation: string | null;
  decision_reason: string | null;
  extraction_confidence: number | null;
  risk_confidence: number | null;
  data_completeness: number | null;
  required_followups_json: string | null;
  analysis_limitations_json: string | null;
  extracted_fields: AnalysisExtractedFields | null;
  risk_alerts: RiskAlert[] | null;
  summary: string | null;
  processing_time_seconds: number | null;
  model_used: string | null;
  created_at: string;
}

export interface AskResponse {
  answer: string;
  sources: { section_title: string; page_num: number }[];
}

export interface CurrentUserResponse {
  id: string;
  email: string;
  name: string;
  role: string;
  org_id: string;
}

export interface AnalysisJobStatusResponse {
  job_id: string;
  document_id: string;
  status: string;
  stage?: string | null;
  stage_message?: string | null;
  ocr_provider?: string | null;
  pages_processed?: number | null;
  total_pages?: number | null;
  ocr_required_pages?: number[] | null;
  ocr_failed_pages?: number[] | null;
  ocr_unreliable_pages?: number[] | null;
  ocr_fallback_used?: boolean | null;
  ocr_quality_status?: "pending" | "clean" | "degraded" | "blocked" | null;
  attempts: number;
  max_attempts: number;
  last_error: string | null;
  error_code: string | null;
  user_message: string | null;
}
