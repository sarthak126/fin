"use client";

import { useEffect, useState } from "react";
import type { ElementType } from "react";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Brain,
  Building2,
  CheckCircle2,
  ChevronLeft,
  Clock,
  Download,
  FileText,
  Info,
  Loader2,
  ScanText,
  Shield,
  ShieldAlert,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { normalizeConfidence } from "@/lib/confidence";
import {
  type CaseDocumentReadModel,
  type CaseDocumentOcrStatus,
  type CaseReadModel,
  type CaseReportItem,
  type CaseReportMetric,
  type CaseReportSection,
  type CrossDocumentComparison,
  type DecisionStatus,
  type FraudSignal,
  isBankStatementAnalysisPayload,
} from "@/lib/api";

import { RiskGauge, StatusPill } from "./case-detail-ui";
import { CaseProcessingBanner, CaseProcessingWaitingScreen } from "./case-processing-ui";
import { useCaseDetailData } from "./use-case-detail-data";

type Tone = "good" | "warning" | "danger" | "neutral";

interface ExtractedFact {
  label: string;
  value: string;
}

const TONE_CARD_CLASSES: Record<Tone, string> = {
  good: "border-emerald-500/20 bg-emerald-500/5",
  warning: "border-amber-500/20 bg-amber-500/5",
  danger: "border-red-500/20 bg-red-500/5",
  neutral: "border-[var(--border-card)] bg-[var(--surface-glass)]",
};

const EXTRACTED_FACT_SKIP_KEYS = new Set([
  "transactions",
  "reasoning",
  "risk_findings",
  "decision",
  "account_profile",
  "raw_response",
  "risk_alerts",
  "cross_document_comparisons",
  "fraud_signals",
  "documents",
  "supported_document_completeness",
  "provisional_insights",
  "applicant_intake",
  "case",
  "flag_details",
  "risk_breakdown",
  "top_merchants",
  "monthly_inflows",
  "monthly_net_flows",
  "category_amounts",
  "spending_categories",
]);

function formatLabel(value: string | null | undefined) {
  const text = String(value || "").trim();
  if (!text) return "Unavailable";

  return text
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "--";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return formatDateOnly(value);
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "--";

  return parsed.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDateOnly(value: string | null | undefined) {
  if (!value) return "--";
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (match) {
    const [, year, month, day] = match;
    return new Date(Number(year), Number(month) - 1, Number(day)).toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "--";
  return parsed.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatDurationSeconds(milliseconds: number) {
  const seconds = Math.max(1, Math.round(milliseconds / 1000));
  return `${seconds}s`;
}

function formatFileSize(bytes: number | null | undefined) {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return "--";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function formatCurrency(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return `Rs ${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatScalarValue(value: unknown) {
  if (value === null || value === undefined) return "--";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return value.toLocaleString("en-IN");
  if (typeof value === "string") return value || "--";
  return JSON.stringify(value);
}

function formatOptionalCurrency(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "Unavailable";
  return formatCurrency(value);
}

function formatUnverifiedInflowRange(
  range: { min: number; max: number; display: string } | null | undefined
) {
  if (!range) return "Unavailable";
  if (range.min === range.max) return formatCurrency(range.min);
  return `${formatCurrency(range.min)} - ${formatCurrency(range.max)}`;
}

function formatDtiDisplay(dti: { value: number | null; label: string; reliability?: string } | null | undefined) {
  if (!dti || dti.reliability === "unavailable") return "Unavailable";
  if (dti.reliability === "unverified") return "Not reliable without verified income";
  if (dti.value === null || dti.value === undefined) return "Unavailable";
  return `${Math.round(dti.value * 100)}% (${formatLabel(dti.label)})`;
}

function formatPercent(value: number | string | null | undefined) {
  const normalized = normalizeConfidence(value);
  if (normalized === null) return "--";
  return `${Math.round(normalized * 100)}%`;
}

function looksLikeDate(value: string) {
  if (!/\d{4}-\d{2}-\d{2}/.test(value)) return false;
  return !Number.isNaN(new Date(value).getTime());
}

function clampRiskScore(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function getDecisionTone(status: DecisionStatus | null | undefined): Tone {
  if (status === "approve") return "good";
  if (status === "reject") return "danger";
  if (status === "manual_review" || status === "insufficient_history") return "warning";
  return "neutral";
}

function getDocumentTone(status: string | null | undefined): Tone {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "analyzed") return "good";
  if (normalized === "failed") return "danger";
  if (normalized === "processing" || normalized === "pending") return "warning";
  return "neutral";
}

function getRequirementTone(status: string | null | undefined): Tone {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "complete") return "good";
  if (normalized === "missing") return "danger";
  if (normalized === "pending") return "warning";
  return "neutral";
}

function getComparisonTone(status: string | null | undefined): Tone {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "consistent") return "good";
  if (normalized === "mismatch") return "danger";
  if (normalized === "insufficient_data") return "warning";
  return "neutral";
}

function getFraudTone(severity: string | null | undefined): Tone {
  const normalized = String(severity || "").trim().toLowerCase();
  if (normalized === "high") return "danger";
  if (normalized === "medium") return "warning";
  if (normalized === "low") return "neutral";
  return "neutral";
}

function getMetricTone(tone: string | null | undefined): Tone {
  if (tone === "good" || tone === "warning" || tone === "danger" || tone === "neutral") {
    return tone;
  }
  return "neutral";
}

function formatStatusPillLabel(value: string | null | undefined) {
  if (!value) return "Pending";
  return formatLabel(value);
}

function formatPageList(pages: number[] | null | undefined) {
  if (!pages || pages.length === 0) return "None";
  return pages.join(", ");
}

function getOcrQualityTone(status: string | null | undefined): Tone {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "clean") return "good";
  if (normalized === "blocked") return "danger";
  if (normalized === "degraded" || normalized === "pending") return "warning";
  return "neutral";
}

function formatOcrQualityLabel(status: string | null | undefined) {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "clean") return "Clean OCR";
  if (normalized === "degraded") return "Degraded OCR";
  if (normalized === "blocked") return "Blocked OCR";
  if (normalized === "pending") return "OCR Running";
  return "OCR Unknown";
}

function getDocumentOcrInlineSummary(document: CaseDocumentReadModel) {
  const ocrStatus = document.ocr_status;
  if (!ocrStatus) {
    if (document.status === "processing") {
      return "Waiting for backend OCR status.";
    }
    if (document.status === "pending") {
      return "Analysis has not started yet.";
    }
    return null;
  }

  if (ocrStatus.analysis_blocked) {
    return ocrStatus.user_message || "OCR blocked analysis for this document.";
  }

  if (ocrStatus.stage_message) {
    return ocrStatus.stage_message;
  }

  if (ocrStatus.ocr_quality_status === "degraded") {
    return ocrStatus.ocr_fallback_used
      ? "OCR fallback was used, so this document should be reviewed more carefully."
      : "OCR completed with degraded quality signals.";
  }

  if (ocrStatus.ocr_quality_status === "clean") {
    return ocrStatus.ocr_required_pages.length > 0
      ? "OCR completed cleanly on the required pages."
      : "This document had enough native text and did not need OCR.";
  }

  if (ocrStatus.ocr_quality_status === "blocked") {
    return "OCR left required pages unreadable, so analysis could not continue.";
  }

  return null;
}

function getDocumentOcrHeadline(document: CaseDocumentReadModel) {
  const ocrStatus = document.ocr_status;
  if (!ocrStatus) {
    if (document.status === "pending") {
      return "Analysis has not started for this document yet.";
    }
    if (document.status === "processing") {
      return "Backend analysis is active and waiting to publish OCR details.";
    }
    return "No OCR details were saved for this document.";
  }

  if (ocrStatus.analysis_blocked) {
    return ocrStatus.user_message || "Analysis stopped because OCR was not reliable enough.";
  }

  if (ocrStatus.ocr_quality_status === "pending") {
    return ocrStatus.stage_message || "OCR is still running on backend-required pages.";
  }

  if (ocrStatus.ocr_quality_status === "blocked") {
    return "Required OCR pages remained unreadable or unreliable, so analysis could not continue.";
  }

  if (ocrStatus.ocr_quality_status === "degraded") {
    return ocrStatus.ocr_fallback_used
      ? "Fallback OCR recovered the required pages, but the document should still be reviewed closely."
      : "OCR completed, but the quality signal is degraded.";
  }

  if (ocrStatus.ocr_required_pages.length > 0) {
    return "OCR completed cleanly on the required pages and did not block analysis.";
  }

  return "This document had enough native text, so OCR was not required.";
}

function getOcrStageDetail(ocrStatus: CaseDocumentOcrStatus | null) {
  if (!ocrStatus) {
    return "--";
  }

  if (ocrStatus.stage_message) {
    return ocrStatus.stage_message;
  }

  if (ocrStatus.stage) {
    return formatLabel(ocrStatus.stage);
  }

  return "--";
}

function getCaseTitle(readModel: CaseReadModel) {
  return (
    readModel.case.applicant_name?.trim() ||
    readModel.case.name?.trim() ||
    `Case ${readModel.case.id.slice(0, 8)}`
  );
}

export default function CaseDetailPage() {
  const params = useParams();
  const caseId = String(params.id);

  return <CaseDetailPageContent key={caseId} caseId={caseId} />;
}

function getLatestTimestamp(readModel: CaseReadModel, generatedAt?: string | null) {
  const timestamps = [
    readModel.case.created_at,
    readModel.case.updated_at,
    generatedAt,
    ...readModel.documents.flatMap((document) => [
      document.created_at,
      document.updated_at,
      document.latest_analysis?.created_at,
    ]),
  ];

  let latest: Date | null = null;
  for (const timestamp of timestamps) {
    if (!timestamp) continue;

    const parsed = new Date(timestamp);
    if (Number.isNaN(parsed.getTime())) continue;

    if (!latest || parsed.getTime() > latest.getTime()) {
      latest = parsed;
    }
  }

  return latest?.toISOString() ?? null;
}

function parseStringList(value: string | null | undefined) {
  if (!value) return [];

  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed)) return [];

    return parsed.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
  } catch {
    return [];
  }
}

function isCurrencyLike(pathText: string) {
  return [
    "income",
    "balance",
    "credit",
    "debit",
    "salary",
    "amount",
    "deposit",
    "withdraw",
    "emi",
    "expense",
    "spending",
    "rent",
    "medical",
    "education",
    "shopping",
    "savings",
    "merchant",
    "cash_flow",
    "net_flow",
    "penalt",
  ].some((token) => pathText.includes(token));
}

function formatFactValue(path: string[], value: string | number | boolean) {
  const pathText = path.join("_").toLowerCase();

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (typeof value === "number") {
    if (pathText.includes("confidence") || pathText.includes("completeness")) {
      return formatPercent(value);
    }

    if (pathText.includes("ratio")) {
      const percentage = value <= 1 ? value * 100 : value;
      return `${Math.round(percentage)}%`;
    }

    if (isCurrencyLike(pathText)) {
      return formatCurrency(value);
    }

    return value.toLocaleString("en-IN");
  }

  if (looksLikeDate(value)) {
    return formatDateOnly(value);
  }

  if (value.includes("_")) {
    return formatLabel(value);
  }

  return value;
}

function formatFactLabel(path: string[]) {
  const relevantPath = path.length > 2 ? path.slice(-2) : path;
  return relevantPath.map((segment) => formatLabel(segment)).join(" / ") || "Value";
}

function collectExtractedFacts(
  value: unknown,
  path: string[] = [],
  facts: ExtractedFact[] = [],
  depth = 0
): ExtractedFact[] {
  if (facts.length >= 12 || value === null || value === undefined || depth > 4) {
    return facts;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return facts;

    if (value.every((item) => ["string", "number", "boolean"].includes(typeof item))) {
      facts.push({
        label: formatFactLabel(path),
        value: value.slice(0, 4).map((item) => formatFactValue(path, item as string | number | boolean)).join(", "),
      });
    }

    return facts;
  }

  if (typeof value === "object") {
    for (const [key, nestedValue] of Object.entries(value as Record<string, unknown>)) {
      if (EXTRACTED_FACT_SKIP_KEYS.has(key)) continue;
      collectExtractedFacts(nestedValue, [...path, key], facts, depth + 1);
      if (facts.length >= 12) break;
    }

    return facts;
  }

  facts.push({
    label: formatFactLabel(path),
    value: formatFactValue(path, value as string | number | boolean),
  });
  return facts;
}

function getBankEvidenceProfile(document: CaseDocumentReadModel) {
  const profile = document.evidence_profile;
  if (profile) return profile;

  const payload = document.latest_analysis?.extracted_fields;
  if (!isBankStatementAnalysisPayload(payload)) return null;
  return {
    account_profile: payload.account_profile ?? null,
    declared_period_start_date: payload.statement_summary.declared_period_start_date ?? null,
    declared_period_end_date: payload.statement_summary.declared_period_end_date ?? null,
    last_transaction_date: payload.statement_summary.last_transaction_date ?? payload.statement_summary.statement_end_date ?? null,
  };
}

function hasBankEvidenceProfile(document: CaseDocumentReadModel) {
  const profile = getBankEvidenceProfile(document);
  const account = profile?.account_profile;
  return Boolean(
    account?.account_holder_name ||
      account?.account_number_masked ||
      account?.bank_name ||
      account?.branch_name ||
      account?.ifsc ||
      profile?.declared_period_start_date ||
      profile?.declared_period_end_date ||
      profile?.last_transaction_date
  );
}

function renderBankEvidenceCard(document: CaseDocumentReadModel) {
  const profile = getBankEvidenceProfile(document);
  if (!profile) return null;
  const account = profile.account_profile;

  return (
    <div key={`${document.id}-account-evidence`} className="rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">{document.original_filename}</h3>
        <StatusPill label="Document Evidence" status="neutral" />
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <DetailTile label="Statement owner" value={account?.account_holder_name || "--"} />
        <DetailTile label="Account" value={account?.account_number_masked || "--"} />
        <DetailTile label="Bank" value={account?.bank_name || "--"} />
        <DetailTile label="Branch" value={account?.branch_name || "--"} />
        <DetailTile label="IFSC" value={account?.ifsc || "--"} />
        <DetailTile label="Declared period" value={`${formatDateOnly(profile.declared_period_start_date)} - ${formatDateOnly(profile.declared_period_end_date)}`} />
        <DetailTile label="Last transaction" value={formatDateOnly(profile.last_transaction_date)} />
        <DetailTile label="Branch phone" value={account?.branch_phone || "--"} />
        <DetailTile label="MICR" value={account?.micr || "--"} />
      </div>
    </div>
  );
}

function renderBankFinancialEvidence(document: CaseDocumentReadModel) {
  const payload = document.latest_analysis?.extracted_fields;
  if (!isBankStatementAnalysisPayload(payload)) return null;

  const income = payload.transaction_insights.income;
  const dti = payload.transaction_insights.dti;

  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      <MetricTile
        label="Verified monthly income"
        value={formatOptionalCurrency(income.verified_monthly_estimate ?? null)}
        tone={income.verified_monthly_estimate ? "good" : "warning"}
      />
      <MetricTile
        label="Unverified inflow range"
        value={formatUnverifiedInflowRange(income.unverified_monthly_inflow_range)}
        tone={income.unverified_monthly_inflow_range ? "neutral" : "good"}
      />
      <MetricTile
        label="DTI"
        value={formatDtiDisplay(dti)}
        tone={dti.reliability === "verified" ? "neutral" : "warning"}
      />
      <MetricTile
        label="Last transaction"
        value={formatDateOnly(payload.statement_summary.last_transaction_date ?? payload.statement_summary.statement_end_date)}
      />
    </div>
  );
}

function SectionHeader({
  icon: Icon,
  title,
  summary,
}: {
  icon: ElementType;
  title: string;
  summary: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <div>
        <h2 className="text-[16px] font-semibold text-[var(--text-primary)]">{title}</h2>
        <p className="mt-1 text-[13px] leading-relaxed text-[var(--text-muted)]">{summary}</p>
      </div>
    </div>
  );
}

function MetricTile({
  label,
  value,
  tone = "neutral",
  hint,
}: {
  label: string;
  value: string;
  tone?: Tone;
  hint?: string | null;
}) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${TONE_CARD_CLASSES[tone]}`}>
      <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">{label}</p>
      <p className="mt-1 text-[18px] font-semibold text-[var(--text-primary)]">{value}</p>
      {hint ? <p className="mt-1 text-[12px] text-[var(--text-muted)]">{hint}</p> : null}
    </div>
  );
}

function DetailTile({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: Tone;
}) {
  return (
    <div className={`rounded-xl border px-3 py-3 ${TONE_CARD_CLASSES[tone]}`}>
      <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">{label}</p>
      <p className="mt-1 text-[13px] font-medium leading-relaxed text-[var(--text-primary)] break-words">{value}</p>
    </div>
  );
}

function EmptySection({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--border-card)] bg-[var(--surface-glass)] px-5 py-8 text-center">
      <p className="text-[14px] font-medium text-[var(--text-primary)]">{title}</p>
      <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-muted)]">{body}</p>
    </div>
  );
}

function ReportItemBlock({ item }: { item: CaseReportItem }) {
  return (
    <div className="rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-[14px] font-semibold text-[var(--text-primary)]">{item.title}</h4>
        <StatusPill label={formatLabel(item.tone)} status={getMetricTone(item.tone)} />
      </div>
      {item.summary ? (
        <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-secondary)]">{item.summary}</p>
      ) : null}

      {item.facts.length > 0 ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {item.facts.map((fact) => (
            <MetricTile
              key={`${item.key}-${fact.key}`}
              label={fact.label}
              value={fact.display_value}
              tone={getMetricTone(fact.tone)}
              hint={fact.hint}
            />
          ))}
        </div>
      ) : null}

      {item.bullets.length > 0 ? (
        <div className="mt-4 space-y-2">
          {item.bullets.map((bullet, index) => (
            <div key={`${item.key}-bullet-${index}`} className="flex items-start gap-2 text-[13px] text-[var(--text-secondary)]">
              <span className="mt-0.5 text-[var(--text-muted)]">-</span>
              <span>{bullet}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function renderDocumentSummary(document: CaseDocumentReadModel) {
  const latestAnalysis = document.latest_analysis;
  const ocrSummary = getDocumentOcrInlineSummary(document);

  return (
    <div key={document.id} className="grid grid-cols-1 gap-4 border-b border-[var(--border-subtle)] px-5 py-4 last:border-b-0 lg:grid-cols-[1.6fr_1fr_1fr_1fr_1fr] lg:items-center lg:gap-3">
      <div className="min-w-0">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
            <FileText className="h-4 w-4 text-primary" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-[13px] font-medium text-[var(--text-primary)]">{document.original_filename}</p>
            <p className="mt-1 text-[11px] text-[var(--text-muted)]">
              {formatLabel(document.document_type)} | {formatFileSize(document.file_size_bytes)}
            </p>
            {ocrSummary ? (
              <p className="mt-2 text-[11px] leading-relaxed text-[var(--text-muted)]">{ocrSummary}</p>
            ) : null}
          </div>
        </div>
      </div>

      <div>
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] lg:hidden">
          Status
        </p>
        <StatusPill label={formatStatusPillLabel(document.status)} status={getDocumentTone(document.status)} />
      </div>

      <div>
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] lg:hidden">
          Decision
        </p>
        <StatusPill
          label={formatStatusPillLabel(latestAnalysis?.decision_status)}
          status={getDecisionTone(latestAnalysis?.decision_status)}
        />
      </div>

      <div>
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] lg:hidden">
          Risk
        </p>
        <p className="text-[13px] font-medium text-[var(--text-primary)]">
          {latestAnalysis?.risk_score !== null && latestAnalysis?.risk_score !== undefined
            ? clampRiskScore(latestAnalysis.risk_score).toString()
            : "--"}
        </p>
      </div>

      <div>
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] lg:hidden">
          Updated
        </p>
        <p className="text-[12px] text-[var(--text-muted)]">
          {formatDateTime(latestAnalysis?.created_at || document.updated_at)}
        </p>
      </div>
    </div>
  );
}

function renderDocumentOcrCard(document: CaseDocumentReadModel) {
  const ocrStatus = document.ocr_status;
  const qualityTone = getOcrQualityTone(ocrStatus?.ocr_quality_status);
  const blockedTone = ocrStatus?.analysis_blocked ? "danger" : "good";

  return (
    <div key={`${document.id}-ocr`} className="rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">{document.original_filename}</h3>
        <StatusPill
          label={formatOcrQualityLabel(ocrStatus?.ocr_quality_status)}
          status={qualityTone}
        />
        {ocrStatus?.ocr_fallback_used ? (
          <Badge variant="secondary" className="border-transparent bg-amber-500/10 text-amber-500">
            Fallback used
          </Badge>
        ) : null}
      </div>

      <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-secondary)]">
        {getDocumentOcrHeadline(document)}
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <DetailTile label="Current stage" value={getOcrStageDetail(ocrStatus)} tone={qualityTone} />
        <DetailTile
          label="Analysis blocked"
          value={ocrStatus?.analysis_blocked ? "Yes" : "No"}
          tone={blockedTone}
        />
        <DetailTile
          label="Required pages"
          value={formatPageList(ocrStatus?.ocr_required_pages)}
          tone={ocrStatus?.ocr_required_pages.length ? "neutral" : "good"}
        />
        <DetailTile
          label="Unreliable pages"
          value={formatPageList(ocrStatus?.ocr_unreliable_pages)}
          tone={ocrStatus?.ocr_unreliable_pages.length ? "warning" : "good"}
        />
        <DetailTile
          label="Failed pages"
          value={formatPageList(ocrStatus?.ocr_failed_pages)}
          tone={ocrStatus?.ocr_failed_pages.length ? "danger" : "good"}
        />
        <DetailTile
          label="OCR provider"
          value={ocrStatus?.ocr_provider ? formatLabel(ocrStatus.ocr_provider) : "--"}
        />
      </div>

      {ocrStatus?.total_pages ? (
        <p className="mt-4 text-[12px] text-[var(--text-muted)]">
          OCR progress:{" "}
          {ocrStatus.pages_processed !== null && ocrStatus.pages_processed !== undefined
            ? `${ocrStatus.pages_processed}/${ocrStatus.total_pages} pages processed`
            : `${ocrStatus.total_pages} total pages`}
        </p>
      ) : null}
    </div>
  );
}

function renderComparison(comparison: CrossDocumentComparison) {
  return (
    <div key={comparison.field} className="rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">{comparison.label}</h3>
        <StatusPill label={formatStatusPillLabel(comparison.status)} status={getComparisonTone(comparison.status)} />
      </div>
      <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-secondary)]">{comparison.summary}</p>

      {comparison.values.length > 0 ? (
        <div className="mt-4 space-y-2">
          {comparison.values.map((value) => (
            <div
              key={`${comparison.field}-${value.document_id}-${String(value.value)}`}
              className="rounded-xl border border-[var(--border-card)] bg-[var(--surface-secondary)] px-4 py-3"
            >
              <p className="text-[12px] font-medium text-[var(--text-primary)]">
                {formatLabel(value.document_type)} | {value.original_filename}
              </p>
              <p className="mt-1 text-[12px] text-[var(--text-muted)]">{formatScalarValue(value.value)}</p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function renderFraudSignal(signal: FraudSignal) {
  return (
    <div key={signal.key} className={`rounded-2xl border p-5 ${TONE_CARD_CLASSES[getFraudTone(signal.severity)]}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">{signal.label}</h3>
        <StatusPill label={formatStatusPillLabel(signal.severity)} status={getFraudTone(signal.severity)} />
      </div>
      <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-secondary)]">{signal.summary}</p>
      <p className="mt-3 text-[13px] text-[var(--text-secondary)]">{signal.details}</p>

      <div className="mt-4 rounded-xl border border-[var(--border-card)] bg-[var(--surface-glass)] px-4 py-3">
        <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">Recommended action</p>
        <p className="mt-1 text-[13px] font-medium text-[var(--text-primary)]">{signal.recommended_action}</p>
      </div>

      {signal.evidence.length > 0 ? (
        <div className="mt-4 space-y-2">
          {signal.evidence.map((evidence, index) => (
            <div
              key={`${signal.key}-evidence-${index}`}
              className="rounded-xl border border-[var(--border-card)] bg-[var(--surface-glass)] px-4 py-3"
            >
              <p className="text-[12px] font-medium text-[var(--text-primary)]">
                {evidence.source_label}
                {evidence.original_filename ? ` | ${evidence.original_filename}` : ""}
              </p>
              <p className="mt-1 text-[12px] text-[var(--text-muted)]">
                {formatLabel(evidence.field)}: {formatScalarValue(evidence.value)}
              </p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function renderReportMetric(metric: CaseReportMetric) {
  return (
    <MetricTile
      key={metric.key}
      label={metric.label}
      value={metric.display_value}
      tone={getMetricTone(metric.tone)}
      hint={metric.hint}
    />
  );
}

function CaseDetailPageContent({ caseId }: { caseId: string }) {
  const router = useRouter();
  const { getToken } = useAuth();
  const [hasRevealedDetail, setHasRevealedDetail] = useState(false);

  const {
    activeDocuments,
    error,
    finalizing,
    finalize,
    gateState,
    loading,
    processingCounts,
    readModel,
    reload,
    report,
    staleMeta,
  } = useCaseDetailData({
    caseId,
    getToken,
  });
  const resolvedCaseId = readModel?.case.id ?? caseId;

  useEffect(() => {
    if (readModel?.case.id && readModel.case.id !== caseId) {
      router.replace(`/dashboard/cases/${readModel.case.id}`);
    }
  }, [caseId, readModel?.case.id, router]);

  useEffect(() => {
    if (hasRevealedDetail || !readModel || !report || gateState === "waiting") {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setHasRevealedDetail(true);
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [gateState, hasRevealedDetail, readModel, report]);

  if (loading) {
    return (
      <div className="flex flex-col gap-6 pb-12 animate-pulse">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-[var(--surface-secondary)]" />
          <div className="flex-1">
            <div className="mb-2 h-6 w-56 rounded-md bg-[var(--surface-secondary)]" />
            <div className="h-3 w-40 rounded-md bg-[var(--surface-secondary)]" />
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[320px,1fr]">
          <div className="card-base h-72 animate-skeleton" />
          <div className="card-base h-72 animate-skeleton" />
        </div>
        <div className="card-base h-56 animate-skeleton" />
        <div className="card-base h-64 animate-skeleton" />
      </div>
    );
  }

  if (!readModel) {
    return (
      <div className="flex flex-col gap-6 pb-12">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="icon" className="h-8 w-8 cursor-pointer">
            <Link href="/dashboard/cases">
              <ChevronLeft className="h-4 w-4" />
            </Link>
          </Button>
          <h1 className="text-lg font-bold text-[var(--text-primary)]">Case Detail</h1>
        </div>
        <div className="card-base flex flex-col items-center py-20">
          <XCircle className="mb-3 h-8 w-8 text-red-500" />
          <p className="text-[14px] font-medium text-[var(--text-primary)]">{error || "Case not found"}</p>
          <Button asChild className="mt-4 cursor-pointer">
            <Link href="/dashboard/cases">Back to Cases</Link>
          </Button>
        </div>
      </div>
    );
  }

  const caseTitle = getCaseTitle(readModel);
  const showProcessingGate = gateState === "waiting" && !hasRevealedDetail;

  if (showProcessingGate) {
    return (
      <CaseProcessingWaitingScreen
        activeDocuments={activeDocuments}
        caseTitle={caseTitle}
        counts={processingCounts}
        onRefresh={reload}
      />
    );
  }

  if (!report) {
    return (
      <div className="flex flex-col gap-6 pb-12">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="icon" className="h-8 w-8 cursor-pointer">
            <Link href="/dashboard/cases">
              <ChevronLeft className="h-4 w-4" />
            </Link>
          </Button>
          <h1 className="text-lg font-bold text-[var(--text-primary)]">Case Detail</h1>
        </div>
        <div className="card-base flex flex-col items-center py-20">
          <XCircle className="mb-3 h-8 w-8 text-red-500" />
          <p className="text-[14px] font-medium text-[var(--text-primary)]">
            {error || "Case detail is still loading."}
          </p>
          <Button asChild className="mt-4 cursor-pointer">
            <Link href="/dashboard/cases">Back to Cases</Link>
          </Button>
        </div>
      </div>
    );
  }

  const latestAnalysis = report.latest_analysis;
  const caseLastUpdated = getLatestTimestamp(readModel, report.header.generated_at);
  const riskScore = clampRiskScore(
    report.overview.risk_score ??
      readModel.provisional_insights.highest_risk_score ??
      readModel.provisional_insights.average_risk_score
  );
  const applicantProgress = Math.round(readModel.applicant_intake.completeness * 100);
  const supportedProgress = Math.round(readModel.supported_document_completeness.analyzed_score * 100);
  const analyzedDocuments = readModel.documents.filter((document) => document.status === "analyzed");
  const extractedDocuments = analyzedDocuments.filter((document) => document.latest_analysis);
  const bankEvidenceDocuments = readModel.documents.filter(hasBankEvidenceProfile);
  const latestFollowups = parseStringList(latestAnalysis.required_followups_json);
  const latestLimitations = parseStringList(latestAnalysis.analysis_limitations_json);
  const liveOcrUpdates = activeDocuments.length > 0;
  const cleanOcrCount = readModel.documents.filter((document) => document.ocr_status?.ocr_quality_status === "clean").length;
  const degradedOcrCount = readModel.documents.filter((document) => document.ocr_status?.ocr_quality_status === "degraded").length;
  const blockedOcrCount = readModel.documents.filter((document) => document.ocr_status?.analysis_blocked).length;
  const fallbackOcrCount = readModel.documents.filter((document) => document.ocr_status?.ocr_fallback_used).length;
  const showStaleBanner = gateState === "stale";
  const showResumedBanner = hasRevealedDetail && gateState === "waiting";

  return (
    <div className="flex flex-col gap-6 pb-12" data-testid="case-detail-root">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-3">
          <Button asChild variant="ghost" size="icon" className="mt-0.5 h-8 w-8 cursor-pointer">
            <Link href="/dashboard/cases">
              <ChevronLeft className="h-4 w-4" />
            </Link>
          </Button>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-[24px] font-bold tracking-tight text-[var(--text-primary)]">{caseTitle}</h1>
              <StatusPill
                label={formatStatusPillLabel(report.overview.decision_status)}
                status={getDecisionTone(report.overview.decision_status)}
              />
              <Badge variant="secondary" className="border-transparent bg-[var(--surface-secondary)] text-[11px] text-[var(--text-muted)]">
                {formatLabel(report.header.report_status)}
              </Badge>
              <Badge variant="secondary" className="border-transparent bg-[var(--surface-secondary)] text-[11px] text-[var(--text-muted)]">
                {formatLabel(readModel.case.status)}
              </Badge>
            </div>

            <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-muted)]">
              {report.overview.summary}
            </p>

            <div className="mt-3 flex flex-wrap items-center gap-3 text-[12px] text-[var(--text-muted)]">
              <span>Case ID {readModel.case.id.slice(0, 8)}</span>
              <span>Updated {formatDateTime(caseLastUpdated)}</span>
              <span>Generated {formatDateTime(report.header.generated_at)}</span>
              <span>Source {formatLabel(report.header.generated_from)}</span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" className="cursor-pointer" onClick={() => void reload()}>
            Refresh
          </Button>
          <Button asChild variant="outline" className="cursor-pointer gap-2">
            <Link href={`/reports/cases/${resolvedCaseId}`} target="_blank" rel="noopener noreferrer">
              <Download className="h-4 w-4" />
              Export PDF
            </Link>
          </Button>
          {!report.header.is_final ? (
            <Button className="cursor-pointer gap-2" onClick={() => void finalize()} disabled={finalizing}>
              {finalizing ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
              {finalizing ? "Finalizing..." : "Finalize Report"}
            </Button>
          ) : null}
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/5 px-4 py-3">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 text-red-500" />
            <div>
              <p className="text-[13px] font-medium text-[var(--text-primary)]">Case data warning</p>
              <p className="mt-1 text-[12px] text-[var(--text-muted)]">{error}</p>
            </div>
          </div>
        </div>
      ) : null}

      {showStaleBanner ? (
        <CaseProcessingBanner
          body={
            staleMeta.reason === "total_wait_exceeded"
              ? `We opened the case detail page after ${formatDurationSeconds(
                  staleMeta.totalWaitMs
                )} because backend progress still has active documents and has taken longer than expected.`
              : `We opened the case detail page because the active document fingerprint has not changed for ${formatDurationSeconds(
                  staleMeta.fingerprintAgeMs
                )}.`
          }
          title="Analysis appears stalled on the backend"
          variant="stale"
        />
      ) : null}

      {showResumedBanner ? (
        <CaseProcessingBanner
          body="The case detail page will stay visible while we keep polling for fresh OCR and analysis updates in the background."
          title="Analysis resumed in the background"
          variant="resumed"
        />
      ) : null}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[320px,1fr]">
        <div className="card-base flex flex-col items-center justify-center px-6 py-6 text-center">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">Risk Score</p>
          <div className="mt-4">
            <RiskGauge score={riskScore} label="case risk" />
          </div>
          <p className="mt-4 text-[13px] text-[var(--text-secondary)]">
            {latestAnalysis.decision_reason || report.overview.summary}
          </p>
        </div>

        <div className="card-base px-6 py-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
                Case Overview
              </p>
              <h2 className="mt-2 text-[22px] font-semibold tracking-tight text-[var(--text-primary)]">
                {formatStatusPillLabel(report.overview.decision_status)}
              </h2>
              <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-[var(--text-secondary)]">
                {latestAnalysis.decision_recommendation || latestAnalysis.summary || report.overview.summary}
              </p>
            </div>
            {liveOcrUpdates ? (
              <Badge variant="secondary" className="border-transparent bg-blue-500/10 text-blue-500">
                Live updates active
              </Badge>
            ) : null}
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile
              label="Analyzed docs"
              value={String(report.overview.analyzed_document_count)}
              tone="good"
            />
            <MetricTile
              label="Pending docs"
              value={String(report.overview.pending_document_count)}
              tone={report.overview.pending_document_count > 0 ? "warning" : "good"}
            />
            <MetricTile
              label="Fraud signals"
              value={String(report.overview.fraud_signal_count)}
              tone={report.overview.fraud_signal_count > 0 ? "danger" : "good"}
            />
            <MetricTile
              label="Blockers"
              value={String(report.overview.blocker_count)}
              tone={report.overview.blocker_count > 0 ? "warning" : "good"}
            />
          </div>
        </div>
      </div>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr,0.8fr]">
        <div className="card-base px-6 py-6">
          <SectionHeader
            icon={Building2}
            title="Applicant Info"
            summary="Borrower intake details and readiness indicators derived from the case-level model."
          />

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <MetricTile label="Applicant name" value={readModel.case.applicant_name || "--"} />
            <MetricTile label="Applicant email" value={readModel.case.applicant_email || "--"} />
            <MetricTile label="Applicant phone" value={readModel.case.applicant_phone || "--"} />
            <MetricTile label="Workflow status" value={formatLabel(readModel.case.status)} />
          </div>
        </div>

        <div className="card-base px-6 py-6">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
            Intake Completeness
          </p>
          <p className="mt-2 text-[28px] font-semibold tracking-tight text-[var(--text-primary)]">
            {applicantProgress}%
          </p>
          <Progress className="mt-4" value={applicantProgress} />

          <div className="mt-5">
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">Completed fields</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {readModel.applicant_intake.completed_fields.length > 0 ? (
                readModel.applicant_intake.completed_fields.map((field) => (
                  <Badge key={field} variant="secondary" className="border-transparent bg-emerald-500/10 text-emerald-500">
                    {formatLabel(field)}
                  </Badge>
                ))
              ) : (
                <Badge variant="secondary" className="border-transparent bg-[var(--surface-secondary)] text-[var(--text-muted)]">
                  None
                </Badge>
              )}
            </div>
          </div>

          <div className="mt-5">
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">Missing fields</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {readModel.applicant_intake.missing_fields.length > 0 ? (
                readModel.applicant_intake.missing_fields.map((field) => (
                  <Badge key={field} variant="secondary" className="border-transparent bg-amber-500/10 text-amber-500">
                    {formatLabel(field)}
                  </Badge>
                ))
              ) : (
                <Badge variant="secondary" className="border-transparent bg-emerald-500/10 text-emerald-500">
                  Nothing missing
                </Badge>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="card-base overflow-hidden p-0">
        <div className="px-6 py-6">
          <SectionHeader
            icon={FileText}
            title="Documents"
            summary="Uploaded evidence, supported-document completeness, and the latest per-document analysis state."
          />

          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile label="Documents" value={String(readModel.documents.length)} />
            <MetricTile
              label="Supported coverage"
              value={`${supportedProgress}%`}
              tone={supportedProgress >= 80 ? "good" : supportedProgress >= 50 ? "warning" : "danger"}
            />
            <MetricTile
              label="Requirements met"
              value={`${readModel.supported_document_completeness.analyzed_requirement_count}/${readModel.supported_document_completeness.total_requirement_count}`}
            />
            <MetricTile
              label="Missing requirements"
              value={String(readModel.supported_document_completeness.missing_requirement_keys.length)}
              tone={
                readModel.supported_document_completeness.missing_requirement_keys.length > 0 ? "warning" : "good"
              }
            />
          </div>

          <div className="mt-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
              Supported document requirements
            </p>
            <div className="mt-3 grid gap-3 lg:grid-cols-3">
              {readModel.supported_document_completeness.requirements.map((requirement) => (
                <div key={requirement.key} className="rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-[13px] font-semibold text-[var(--text-primary)]">{requirement.label}</h3>
                    <StatusPill
                      label={formatStatusPillLabel(requirement.status)}
                      status={getRequirementTone(requirement.status)}
                    />
                  </div>
                  <p className="mt-2 text-[12px] text-[var(--text-muted)]">
                    {requirement.analyzed_count}/{requirement.provided_count} analyzed | accepted:{" "}
                    {requirement.accepted_document_types.map((documentType) => formatLabel(documentType)).join(", ")}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-6">
            <SectionHeader
              icon={ScanText}
              title="OCR Status"
              summary="Real backend OCR truth for each document, including fallback use, unreliable pages, failed pages, and whether OCR blocked analysis."
            />

            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricTile label="Clean OCR" value={String(cleanOcrCount)} tone={cleanOcrCount > 0 ? "good" : "neutral"} />
              <MetricTile
                label="Degraded OCR"
                value={String(degradedOcrCount)}
                tone={degradedOcrCount > 0 ? "warning" : "good"}
              />
              <MetricTile
                label="Blocked Analysis"
                value={String(blockedOcrCount)}
                tone={blockedOcrCount > 0 ? "danger" : "good"}
              />
              <MetricTile
                label="Fallback Used"
                value={String(fallbackOcrCount)}
                tone={fallbackOcrCount > 0 ? "warning" : "good"}
              />
            </div>

            <div className="mt-5 grid gap-4 xl:grid-cols-2">
              {readModel.documents.map(renderDocumentOcrCard)}
            </div>
          </div>
        </div>

        <div className="border-t border-[var(--border-card)]">
          <div className="hidden grid-cols-[1.6fr_1fr_1fr_1fr_1fr] border-b border-[var(--border-card)] px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] lg:grid">
            <div>Document</div>
            <div>Status</div>
            <div>Decision</div>
            <div>Risk</div>
            <div>Updated</div>
          </div>
          {readModel.documents.map(renderDocumentSummary)}
        </div>
      </section>

      {bankEvidenceDocuments.length > 0 ? (
        <section className="card-base px-6 py-6">
          <SectionHeader
            icon={Building2}
            title="Statement Owner / Account Evidence"
            summary="Bank-statement account details extracted as source evidence for underwriting review."
          />

          <div className="mt-5 grid gap-4 xl:grid-cols-2">
            {bankEvidenceDocuments.map(renderBankEvidenceCard)}
          </div>
        </section>
      ) : null}

      <section className="card-base px-6 py-6">
        <SectionHeader
          icon={Brain}
          title="Extracted Data"
          summary="Normalized fields surfaced from analyzed documents and grouped at the case level."
        />

        {extractedDocuments.length === 0 ? (
          <div className="mt-5">
            <EmptySection
              title="No extracted data yet"
              body="Once one or more documents have been analyzed, the case page will surface the key extracted fields here."
            />
          </div>
        ) : (
          <div className="mt-5 grid gap-4 xl:grid-cols-2">
            {extractedDocuments.map((document) => {
              const facts = collectExtractedFacts(document.latest_analysis?.extracted_fields);

              return (
                <div key={document.id} className="rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] p-5">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">{document.original_filename}</h3>
                    <StatusPill
                      label={formatStatusPillLabel(document.latest_analysis?.decision_status)}
                      status={getDecisionTone(document.latest_analysis?.decision_status)}
                    />
                  </div>

                  <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-secondary)]">
                    {document.latest_analysis?.summary || "Latest extracted data from this document is shown below."}
                  </p>

                  {renderBankFinancialEvidence(document)}

                  {facts.length > 0 ? (
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      {facts.map((fact) => (
                        <MetricTile
                          key={`${document.id}-${fact.label}`}
                          label={fact.label}
                          value={fact.value}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="mt-4">
                      <EmptySection
                        title="No scalar fields available"
                        body="This document has analysis output, but there are no compact extracted fields ready for inline display."
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="space-y-4">
        <div className="card-base px-6 py-6">
          <SectionHeader
            icon={Activity}
            title="Cross-Doc Insights"
            summary="Cross-document comparisons, blockers, and follow-ups derived from the aggregated case evidence."
          />

          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile
              label="Conflicts"
              value={String(readModel.provisional_insights.conflict_fields.length)}
              tone={readModel.provisional_insights.conflict_fields.length > 0 ? "danger" : "good"}
            />
            <MetricTile
              label="Follow-ups"
              value={String(readModel.provisional_insights.followups.length)}
              tone={readModel.provisional_insights.followups.length > 0 ? "warning" : "good"}
            />
            <MetricTile
              label="Document decisions"
              value={String(Object.keys(readModel.provisional_insights.document_decision_counts).length)}
            />
            <MetricTile
              label="Failed docs"
              value={String(readModel.provisional_insights.failed_document_count)}
              tone={readModel.provisional_insights.failed_document_count > 0 ? "danger" : "good"}
            />
          </div>

          <div className="mt-5 grid gap-4 xl:grid-cols-2">
            <div className="rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
                Blockers
              </p>
              <div className="mt-3 space-y-2">
                {readModel.provisional_insights.blockers.length > 0 ? (
                  readModel.provisional_insights.blockers.map((blocker, index) => (
                    <div key={`blocker-${index}`} className="flex items-start gap-2 text-[13px] text-[var(--text-secondary)]">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                      <span>{blocker}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-[13px] text-[var(--text-muted)]">No blockers are currently listed.</p>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
                Follow-ups
              </p>
              <div className="mt-3 space-y-2">
                {readModel.provisional_insights.followups.length > 0 ? (
                  readModel.provisional_insights.followups.map((followup, index) => (
                    <div key={`followup-${index}`} className="flex items-start gap-2 text-[13px] text-[var(--text-secondary)]">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                      <span>{followup}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-[13px] text-[var(--text-muted)]">No follow-up actions are currently listed.</p>
                )}
              </div>
            </div>
          </div>
        </div>

        {readModel.cross_document_comparisons.length > 0 ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {readModel.cross_document_comparisons.map(renderComparison)}
          </div>
        ) : (
          <EmptySection
            title="No cross-document comparisons yet"
            body="Cross-document checks appear here when at least two relevant analyzed documents expose comparable fields."
          />
        )}
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[320px,1fr]">
        <div className="card-base px-6 py-6">
          <SectionHeader
            icon={Shield}
            title="Risk Score"
            summary="Case-level decision, confidence, completeness, and alert posture."
          />

          <div className="mt-5 flex flex-col items-center text-center">
            <RiskGauge score={riskScore} label="risk" />
            <div className="mt-4">
              <StatusPill
                label={formatStatusPillLabel(latestAnalysis.decision_status)}
                status={getDecisionTone(latestAnalysis.decision_status)}
              />
            </div>
          </div>
        </div>

        <div className="card-base px-6 py-6">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <MetricTile
              label="Confidence"
              value={formatPercent(latestAnalysis.confidence)}
              tone={getMetricTone(
                latestAnalysis.confidence === null
                  ? "neutral"
                  : normalizeConfidence(latestAnalysis.confidence) !== null &&
                      normalizeConfidence(latestAnalysis.confidence)! >= 0.8
                    ? "good"
                    : normalizeConfidence(latestAnalysis.confidence) !== null &&
                        normalizeConfidence(latestAnalysis.confidence)! >= 0.5
                      ? "warning"
                      : "danger"
              )}
            />
            <MetricTile
              label="Data completeness"
              value={formatPercent(latestAnalysis.data_completeness)}
              tone={getMetricTone(
                latestAnalysis.data_completeness === null
                  ? "neutral"
                  : normalizeConfidence(latestAnalysis.data_completeness) !== null &&
                      normalizeConfidence(latestAnalysis.data_completeness)! >= 0.8
                    ? "good"
                    : normalizeConfidence(latestAnalysis.data_completeness) !== null &&
                        normalizeConfidence(latestAnalysis.data_completeness)! >= 0.5
                      ? "warning"
                      : "danger"
              )}
            />
            <MetricTile
              label="Highest document risk"
              value={
                readModel.provisional_insights.highest_risk_score !== null
                  ? String(clampRiskScore(readModel.provisional_insights.highest_risk_score))
                  : "--"
              }
            />
            <MetricTile
              label="Average document risk"
              value={
                readModel.provisional_insights.average_risk_score !== null
                  ? String(clampRiskScore(readModel.provisional_insights.average_risk_score))
                  : "--"
              }
            />
            <MetricTile
              label="Risk alerts"
              value={String(latestAnalysis.risk_alerts?.length || 0)}
              tone={(latestAnalysis.risk_alerts?.length || 0) > 0 ? "warning" : "good"}
            />
            <MetricTile
              label="Model"
              value={latestAnalysis.model_used || "--"}
            />
          </div>

          <div className="mt-5 grid gap-4 xl:grid-cols-2">
            <div className="rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
                Alerts
              </p>
              <div className="mt-3 space-y-2">
                {latestAnalysis.risk_alerts && latestAnalysis.risk_alerts.length > 0 ? (
                  latestAnalysis.risk_alerts.map((alert, index) => (
                    <div key={`alert-${index}`} className="flex items-start gap-2 text-[13px] text-[var(--text-secondary)]">
                      <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                      <span>{alert.message}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-[13px] text-[var(--text-muted)]">No case-level risk alerts were emitted.</p>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
                Limitations and follow-ups
              </p>
              <div className="mt-3 space-y-2">
                {[...latestLimitations, ...latestFollowups].length > 0 ? (
                  [...latestLimitations, ...latestFollowups].map((item, index) => (
                    <div key={`risk-note-${index}`} className="flex items-start gap-2 text-[13px] text-[var(--text-secondary)]">
                      <Clock className="mt-0.5 h-4 w-4 shrink-0 text-[var(--text-muted)]" />
                      <span>{item}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-[13px] text-[var(--text-muted)]">No additional limitations are currently listed.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <div className="card-base px-6 py-6">
          <SectionHeader
            icon={ShieldAlert}
            title="Fraud Signals"
            summary="Signals that need verification before final underwriting or approval decisions."
          />
        </div>

        {readModel.fraud_signals.length > 0 ? (
          <div className="grid gap-4 xl:grid-cols-2">{readModel.fraud_signals.map(renderFraudSignal)}</div>
        ) : (
          <EmptySection
            title="No cross-document fraud or mismatch signals detected"
            body="Document risk alerts remain visible separately in the risk section."
          />
        )}
      </section>

      <section className="space-y-4">
        <div className="card-base px-6 py-6">
          <SectionHeader
            icon={Info}
            title="Final Report"
            summary="Structured report output generated from the latest case-level snapshot."
          />

          <div className="mt-5 rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] p-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h3 className="text-[18px] font-semibold text-[var(--text-primary)]">{report.header.title}</h3>
                {report.header.subtitle ? (
                  <p className="mt-1 text-[13px] text-[var(--text-muted)]">{report.header.subtitle}</p>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary" className="border-transparent bg-[var(--surface-secondary)] text-[var(--text-muted)]">
                  {formatLabel(report.header.report_status)}
                </Badge>
                <Badge variant="secondary" className="border-transparent bg-[var(--surface-secondary)] text-[var(--text-muted)]">
                  {formatLabel(report.header.generated_from)}
                </Badge>
              </div>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {report.metrics.map(renderReportMetric)}
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-3 text-[12px] text-[var(--text-muted)]">
              <span>Generated {formatDateTime(report.header.generated_at)}</span>
              <span>Print file {report.header.print_filename}</span>
            </div>
          </div>
        </div>

        {report.sections.length > 0 ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {report.sections.map((section: CaseReportSection) => (
              <div key={section.key} className="card-base px-6 py-6">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                    <BarChart3 className="h-4 w-4 text-primary" />
                  </div>
                  <div>
                    <h3 className="text-[16px] font-semibold text-[var(--text-primary)]">{section.title}</h3>
                    {section.summary ? (
                      <p className="mt-1 text-[13px] leading-relaxed text-[var(--text-muted)]">{section.summary}</p>
                    ) : null}
                  </div>
                </div>

                <div className="mt-5 space-y-4">
                  {section.items.map((item) => (
                    <ReportItemBlock key={`${section.key}-${item.key}`} item={item} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptySection
            title="No report sections yet"
            body="The case report payload is available, but it did not include any structured sections to display."
          />
        )}

        <div className="rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] px-5 py-4">
          <p className="text-[12px] text-[var(--text-muted)]">{report.print.footer_note}</p>
        </div>
      </section>
    </div>
  );
}
