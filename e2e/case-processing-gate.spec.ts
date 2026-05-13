import { expect, test, type Page } from "@playwright/test";
import type {
  AnalysisResponse,
  CaseAnalysisSnapshot,
  CaseDetail,
  CaseDocumentOcrStatus,
  CaseDocumentReadModel,
  CaseReadModel,
  CaseReportPayload,
} from "../src/lib/api";

const CASE_ID = "case-processing-gate";
const CASE_URL = `/dashboard/cases/${CASE_ID}`;

function buildCaseDetail(overrides: Partial<CaseDetail> = {}): CaseDetail {
  return {
    applicant_email: "asha@example.com",
    applicant_name: "Asha Patel",
    applicant_phone: "+91-9876543210",
    created_at: "2026-04-21T10:00:00.000Z",
    id: CASE_ID,
    legacy_source_document_id: null,
    name: "Asha Patel Home Loan",
    org_id: "org_123",
    status: "collecting",
    updated_at: "2026-04-21T10:00:00.000Z",
    user_id: "user_123",
    ...overrides,
  };
}

function buildDocumentAnalysis(overrides: Partial<AnalysisResponse> = {}): AnalysisResponse {
  return {
    confidence: 0.86,
    created_at: "2026-04-21T10:03:00.000Z",
    data_completeness: 0.88,
    decision_reason: "Income documents are largely consistent.",
    decision_recommendation: "Proceed with manual underwriting review.",
    decision_status: "manual_review",
    document_id: "doc-analyzed",
    extracted_fields: {
      applicant: {
        employer_name: "Acme Industries",
      },
    },
    extraction_confidence: 0.84,
    id: "analysis-doc-analyzed",
    model_used: "gpt-5.4-mini",
    processing_time_seconds: 12,
    recommendation: "review",
    required_followups_json: "[]",
    risk_alerts: [
      {
        message: "Income variance detected across statements.",
        severity: "medium",
      },
    ],
    risk_confidence: 0.8,
    risk_score: 41,
    summary: "Document analysis is available.",
    analysis_limitations_json: "[]",
    ...overrides,
  };
}

function buildCaseAnalysis(overrides: Partial<CaseAnalysisSnapshot> = {}): CaseAnalysisSnapshot {
  return {
    case_id: CASE_ID,
    case_status: "collecting",
    confidence: 0.84,
    created_at: "2026-04-21T10:05:00.000Z",
    data_completeness: 0.89,
    decision_reason: "Key documents are available for review.",
    decision_recommendation: "Proceed with manual review.",
    decision_status: "manual_review",
    extraction_confidence: 0.85,
    extracted_fields: {
      applicant: {
        employer_name: "Acme Industries",
      },
    },
    id: "case-analysis-1",
    is_final: false,
    model_used: "gpt-5.4-mini",
    processing_time_seconds: 18,
    recommendation: "review",
    required_followups_json: "[]",
    risk_alerts: [
      {
        message: "Income variance detected across documents.",
        severity: "medium",
      },
    ],
    risk_confidence: 0.82,
    risk_score: 44,
    summary: "Case-level analysis is available.",
    analysis_limitations_json: "[]",
    ...overrides,
  };
}

function buildOcrStatus(overrides: Partial<CaseDocumentOcrStatus> = {}): CaseDocumentOcrStatus {
  return {
    analysis_blocked: false,
    error_code: null,
    extraction_schema_version: 1,
    extraction_status: "complete",
    ocr_failed_pages: [],
    ocr_fallback_used: false,
    ocr_provider: "vision-v1",
    ocr_quality_status: "clean",
    ocr_required_pages: [1],
    ocr_unreliable_pages: [],
    pages_processed: 2,
    stage: null,
    stage_message: null,
    total_pages: 2,
    user_message: null,
    ...overrides,
  };
}

function buildDocument(
  id: string,
  status: string,
  overrides: Partial<CaseDocumentReadModel> = {}
): CaseDocumentReadModel {
  const latestAnalysis =
    status === "analyzed"
      ? buildDocumentAnalysis({
          document_id: id,
          id: `analysis-${id}`,
        })
      : null;

  return {
    case_id: CASE_ID,
    created_at: "2026-04-21T10:00:00.000Z",
    document_type: id === "doc-analyzed" ? "bank_statement" : "salary_slip",
    file_size_bytes: 120000,
    file_type: "application/pdf",
    file_url: null,
    filename: `${id}.pdf`,
    id,
    latest_analysis: latestAnalysis,
    ocr_status: status === "analyzed" ? buildOcrStatus() : buildOcrStatus({ ocr_quality_status: "pending" }),
    org_id: "org_123",
    original_filename: `${id}.pdf`,
    status,
    updated_at: "2026-04-21T10:00:00.000Z",
    user_id: "user_123",
    ...overrides,
  };
}

function buildReadModel(documents: CaseDocumentReadModel[], overrides: Partial<CaseReadModel> = {}): CaseReadModel {
  const analyzedCount = documents.filter((document) => document.status === "analyzed").length;
  const failedCount = documents.filter(
    (document) => document.status === "failed" || document.ocr_status?.analysis_blocked
  ).length;
  const pendingCount = documents.filter(
    (document) => document.status !== "analyzed" && document.status !== "failed" && !document.ocr_status?.analysis_blocked
  ).length;

  return {
    applicant_intake: {
      applicant_email: "asha@example.com",
      applicant_name: "Asha Patel",
      applicant_phone: "+91-9876543210",
      completed_fields: ["applicant_name", "applicant_email", "applicant_phone"],
      completeness: 1,
      missing_fields: [],
    },
    authoritative_analysis: analyzedCount > 0 ? buildCaseAnalysis() : null,
    case: buildCaseDetail(),
    cross_document_comparisons: [],
    documents,
    fraud_signals: [],
    provisional_insights: {
      analyzed_document_count: analyzedCount,
      average_risk_score: analyzedCount > 0 ? 42 : null,
      blockers: failedCount > 0 ? ["One document could not be analyzed."] : [],
      conflict_fields: [],
      decision_status: analyzedCount > 0 ? "manual_review" : null,
      document_decision_counts: analyzedCount > 0 ? { manual_review: analyzedCount } : {},
      failed_document_count: failedCount,
      followups: pendingCount > 0 ? ["Waiting for the remaining documents to finish."] : [],
      fraud_signal_count: 0,
      fraud_signal_keys: [],
      highest_risk_score: analyzedCount > 0 ? 44 : null,
      pending_document_count: pendingCount,
      recommendation: analyzedCount > 0 ? "review" : null,
      summary:
        pendingCount > 0
          ? "Case is still processing."
          : failedCount > 0
            ? "Case finished with failed or blocked documents."
            : "Case is ready for review.",
    },
    supported_document_completeness: {
      analyzed_requirement_count: analyzedCount,
      analyzed_score: documents.length === 0 ? 0 : analyzedCount / documents.length,
      missing_document_types: [],
      missing_requirement_keys: [],
      pending_requirement_keys: pendingCount > 0 ? ["salary_slip"] : [],
      present_document_types: documents.map((document) => document.document_type),
      provided_requirement_count: documents.length,
      provided_score: documents.length === 0 ? 0 : 1,
      requirements: [],
      total_requirement_count: documents.length,
    },
    ...overrides,
  };
}

function buildReport(documents: CaseDocumentReadModel[], overrides: Partial<CaseReportPayload> = {}): CaseReportPayload {
  const analyzedCount = documents.filter((document) => document.status === "analyzed").length;
  const failedCount = documents.filter(
    (document) => document.status === "failed" || document.ocr_status?.analysis_blocked
  ).length;
  const pendingCount = documents.filter(
    (document) => document.status !== "analyzed" && document.status !== "failed" && !document.ocr_status?.analysis_blocked
  ).length;

  return {
    applicant_intake: buildReadModel(documents).applicant_intake,
    case: buildCaseDetail(),
    documents,
    header: {
      case_id: CASE_ID,
      generated_at: "2026-04-21T10:06:00.000Z",
      generated_from: pendingCount > 0 ? "live_provisional" : "authoritative_analysis",
      is_final: false,
      print_filename: "asha-patel-home-loan.pdf",
      report_id: "report-1",
      report_status: pendingCount > 0 ? "provisional" : "finalized",
      subtitle: "Case detail report",
      title: "Asha Patel Home Loan Review",
    },
    latest_analysis: buildCaseAnalysis(),
    metrics: [
      {
        display_value: String(analyzedCount),
        hint: null,
        key: "documents_ready",
        label: "Documents ready",
        tone: "good",
        value: analyzedCount,
      },
    ],
    overview: {
      analyzed_document_count: analyzedCount,
      blocker_count: failedCount > 0 ? 1 : 0,
      confidence: 0.84,
      data_completeness: 0.89,
      decision_reason: "Key documents are available for review.",
      decision_status: "manual_review",
      failed_document_count: failedCount,
      followup_count: pendingCount > 0 ? 1 : 0,
      fraud_signal_count: 0,
      pending_document_count: pendingCount,
      recommendation: "review",
      risk_score: 44,
      summary:
        pendingCount > 0
          ? "Some documents are still being analyzed."
          : failedCount > 0
            ? "The case includes failed or blocked documents."
            : "The case is ready for review.",
    },
    print: {
      filename: "asha-patel-home-loan.pdf",
      footer_note: "Generated for internal underwriting review.",
      generated_at: "2026-04-21T10:06:00.000Z",
      sections: [],
      subtitle: "Case detail report",
      title: "Asha Patel Home Loan Review",
    },
    sections: [],
    ...overrides,
  };
}

async function fulfillJson(route: { fulfill: (options: Record<string, unknown>) => Promise<void> }, body: unknown) {
  await route.fulfill({
    body: JSON.stringify(body),
    contentType: "application/json",
    status: 200,
  });
}

async function stubCaseApis(
  page: Page,
  {
    readModels,
    reports,
  }: {
    readModels: CaseReadModel[];
    reports: CaseReportPayload[];
  }
) {
  let readModelRequests = 0;
  let reportRequests = 0;

  await page.route("**/api/v1/auth/me", async (route) => {
    await fulfillJson(route, {
      email: "asha@example.com",
      id: "user_123",
      name: "Asha Patel",
      org_id: "org_123",
      role: "admin",
    });
  });

  await page.route(`**/api/v1/cases/${CASE_ID}/read-model`, async (route) => {
    const nextResponse = readModels[Math.min(readModelRequests, readModels.length - 1)];
    readModelRequests += 1;
    await fulfillJson(route, nextResponse);
  });

  await page.route(`**/api/v1/cases/${CASE_ID}/report`, async (route) => {
    const nextResponse = reports[Math.min(reportRequests, reports.length - 1)];
    reportRequests += 1;
    await fulfillJson(route, nextResponse);
  });

  return {
    getReadModelRequests: () => readModelRequests,
    getReportRequests: () => reportRequests,
  };
}

async function prepareCaseRoute(
  page: Page,
  {
    pollIntervalMs = 100,
    readySettleMs = 250,
    staleFingerprintMs = 10_000,
    staleTotalWaitMs = 10_000,
  }: {
    pollIntervalMs?: number;
    readySettleMs?: number;
    staleFingerprintMs?: number;
    staleTotalWaitMs?: number;
  } = {}
) {
  await page.context().addCookies([
    {
      domain: "localhost",
      name: "codex-e2e-auth-bypass",
      path: "/",
      sameSite: "Lax",
      value: "true",
    },
  ]);

  await page.addInitScript(
    ({
      nextPollIntervalMs,
      nextReadySettleMs,
      nextStaleFingerprintMs,
      nextStaleTotalWaitMs,
    }) => {
      window.localStorage.setItem("codex.caseDetail.pollIntervalMs", String(nextPollIntervalMs));
      window.localStorage.setItem("codex.caseDetail.readySettleMs", String(nextReadySettleMs));
      window.localStorage.setItem("codex.caseDetail.staleFingerprintMs", String(nextStaleFingerprintMs));
      window.localStorage.setItem("codex.caseDetail.staleTotalWaitMs", String(nextStaleTotalWaitMs));
    },
    {
      nextPollIntervalMs: pollIntervalMs,
      nextReadySettleMs: readySettleMs,
      nextStaleFingerprintMs: staleFingerprintMs,
      nextStaleTotalWaitMs: staleTotalWaitMs,
    }
  );
}

const FAST_STALE_THRESHOLDS = {
  staleFingerprintMs: 300,
  staleTotalWaitMs: 900,
} as const;

const STABLE_WAIT_THRESHOLDS = {
  staleFingerprintMs: 10_000,
  staleTotalWaitMs: 10_000,
} as const;

async function prepareStableCaseRoute(page: Page) {
  await prepareCaseRoute(page, STABLE_WAIT_THRESHOLDS);
}

test("pending and processing documents stay on the waiting screen and suppress detail actions", async ({ page }) => {
  const activeReadModel = buildReadModel([
    buildDocument("doc-analyzed", "analyzed"),
    buildDocument("doc-processing", "processing", {
      ocr_status: buildOcrStatus({
        ocr_quality_status: "pending",
        pages_processed: 1,
        stage: "extracting",
        stage_message: "Extracting salary details from page 1.",
        total_pages: 3,
      }),
      updated_at: "2026-04-21T10:00:05.000Z",
    }),
  ]);

  const api = await stubCaseApis(page, {
    readModels: [activeReadModel],
    reports: [buildReport(activeReadModel.documents)],
  });

  await prepareStableCaseRoute(page);
  await page.goto(CASE_URL);

  await expect(page.locator('[data-testid="case-processing-waiting-screen"]')).toBeVisible();
  await expect(page.locator('[data-testid="case-processing-active-document-row"]')).toHaveCount(1);
  await expect(page.getByRole("link", { name: /export pdf/i })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /finalize report/i })).toHaveCount(0);
  await expect(page.locator('[data-testid="case-detail-root"]')).toHaveCount(0);
  expect(api.getReportRequests()).toBe(0);
});

test("an active case auto-reveals the detail page once processing finishes", async ({ page }) => {
  const activeReadModel = buildReadModel([
    buildDocument("doc-analyzed", "analyzed"),
    buildDocument("doc-processing", "processing", {
      ocr_status: buildOcrStatus({
        ocr_quality_status: "pending",
        pages_processed: 1,
        stage: "ocr",
        stage_message: "Running OCR on the remaining pages.",
        total_pages: 2,
      }),
      updated_at: "2026-04-21T10:00:03.000Z",
    }),
  ]);
  const readyReadModel = buildReadModel([
    buildDocument("doc-analyzed", "analyzed"),
    buildDocument("doc-processing", "analyzed", {
      latest_analysis: buildDocumentAnalysis({
        created_at: "2026-04-21T10:00:09.000Z",
        document_id: "doc-processing",
        id: "analysis-doc-processing",
      }),
      ocr_status: buildOcrStatus({
        ocr_quality_status: "clean",
        pages_processed: 2,
        stage: null,
        stage_message: null,
        total_pages: 2,
      }),
      updated_at: "2026-04-21T10:00:09.000Z",
    }),
  ]);

  await stubCaseApis(page, {
    readModels: [activeReadModel, activeReadModel, activeReadModel, readyReadModel],
    reports: [buildReport(readyReadModel.documents)],
  });

  await prepareStableCaseRoute(page);
  await page.goto(CASE_URL);

  await expect(page.locator('[data-testid="case-processing-waiting-screen"]')).toBeVisible();
  await expect(page.locator('[data-testid="case-detail-root"]')).toBeVisible();
  await expect(page.locator('[data-testid="case-processing-waiting-screen"]')).toHaveCount(0);
  await expect(page.getByRole("link", { name: /export pdf/i })).toBeVisible();
});

test("stale processing exits waiting mode and shows the stale warning banner", async ({ page }) => {
  const stalledReadModel = buildReadModel([
    buildDocument("doc-analyzed", "analyzed"),
    buildDocument("doc-processing", "processing", {
      ocr_status: buildOcrStatus({
        ocr_quality_status: "pending",
        pages_processed: 1,
        stage: "extracting",
        stage_message: "Extracting salary details from page 1.",
        total_pages: 3,
      }),
      updated_at: "2026-04-21T10:00:02.000Z",
    }),
  ]);

  await stubCaseApis(page, {
    readModels: [stalledReadModel],
    reports: [buildReport(stalledReadModel.documents)],
  });

  await prepareCaseRoute(page, FAST_STALE_THRESHOLDS);
  await page.goto(CASE_URL);

  await expect(page.locator('[data-testid="case-processing-waiting-screen"]')).toBeVisible();
  await expect(page.locator('[data-testid="case-processing-stale-banner"]')).toBeVisible();
  await expect(page.locator('[data-testid="case-detail-root"]')).toBeVisible();
});

test("terminal failed or blocked unfinished documents skip waiting immediately", async ({ page }) => {
  const terminalReadModel = buildReadModel([
    buildDocument("doc-analyzed", "analyzed"),
    buildDocument("doc-blocked", "failed", {
      latest_analysis: null,
      ocr_status: buildOcrStatus({
        analysis_blocked: true,
        error_code: "ocr_blocked",
        ocr_quality_status: "blocked",
        pages_processed: 1,
        stage: "ocr",
        stage_message: "Required pages remained unreadable.",
        total_pages: 2,
        user_message: "The backend could not recover readable OCR from this file.",
      }),
      updated_at: "2026-04-21T10:00:08.000Z",
    }),
  ]);

  await stubCaseApis(page, {
    readModels: [terminalReadModel],
    reports: [buildReport(terminalReadModel.documents)],
  });

  await prepareStableCaseRoute(page);
  await page.goto(CASE_URL);

  await expect(page.locator('[data-testid="case-processing-waiting-screen"]')).toHaveCount(0);
  await expect(page.locator('[data-testid="case-detail-root"]')).toBeVisible();
  await expect(page.getByRole("link", { name: /export pdf/i })).toBeVisible();
});

test("completed cases open directly to the existing detail page", async ({ page }) => {
  const completedReadModel = buildReadModel([
    buildDocument("doc-analyzed", "analyzed"),
    buildDocument("doc-supporting", "analyzed", {
      latest_analysis: buildDocumentAnalysis({
        created_at: "2026-04-21T10:00:07.000Z",
        document_id: "doc-supporting",
        id: "analysis-doc-supporting",
      }),
      updated_at: "2026-04-21T10:00:07.000Z",
    }),
  ]);

  await stubCaseApis(page, {
    readModels: [completedReadModel],
    reports: [buildReport(completedReadModel.documents)],
  });

  await prepareStableCaseRoute(page);
  await page.goto(CASE_URL);

  await expect(page.locator('[data-testid="case-processing-waiting-screen"]')).toHaveCount(0);
  await expect(page.locator('[data-testid="case-detail-root"]')).toBeVisible();
  await expect(page.getByText(/final report/i)).toBeVisible();
});

test("processing -> ready -> processing again keeps the page revealed and shows the resumed banner", async ({ page }) => {
  const activeReadModel = buildReadModel([
    buildDocument("doc-analyzed", "analyzed"),
    buildDocument("doc-processing", "processing", {
      ocr_status: buildOcrStatus({
        ocr_quality_status: "pending",
        pages_processed: 1,
        stage: "queued",
        stage_message: "Queued for OCR.",
        total_pages: 2,
      }),
      updated_at: "2026-04-21T10:00:03.000Z",
    }),
  ]);
  const readyReadModel = buildReadModel([
    buildDocument("doc-analyzed", "analyzed"),
    buildDocument("doc-processing", "analyzed", {
      latest_analysis: buildDocumentAnalysis({
        created_at: "2026-04-21T10:00:08.000Z",
        document_id: "doc-processing",
        id: "analysis-doc-processing",
      }),
      updated_at: "2026-04-21T10:00:08.000Z",
    }),
  ]);
  const resumedReadModel = buildReadModel([
    buildDocument("doc-analyzed", "analyzed"),
    buildDocument("doc-processing", "processing", {
      latest_analysis: null,
      ocr_status: buildOcrStatus({
        ocr_quality_status: "pending",
        pages_processed: 1,
        stage: "extracting",
        stage_message: "A backend follow-up pass resumed on the document.",
        total_pages: 2,
      }),
      updated_at: "2026-04-21T10:00:11.000Z",
    }),
  ]);

  await stubCaseApis(page, {
    readModels: [activeReadModel, activeReadModel, readyReadModel, readyReadModel, resumedReadModel],
    reports: [buildReport(readyReadModel.documents), buildReport(resumedReadModel.documents)],
  });

  await prepareStableCaseRoute(page);
  await page.goto(CASE_URL);

  await expect(page.locator('[data-testid="case-processing-waiting-screen"]')).toBeVisible();
  await expect(page.locator('[data-testid="case-detail-root"]')).toBeVisible();
  await expect(page.locator('[data-testid="case-processing-resumed-banner"]')).toBeVisible();
  await expect(page.locator('[data-testid="case-processing-waiting-screen"]')).toHaveCount(0);
});
