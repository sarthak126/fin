"use client";

import Link from "next/link";
import { AlertTriangle, ChevronLeft, FileText, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type { CaseDocumentReadModel } from "@/lib/api";

import { StatusPill } from "./case-detail-ui";
import {
  type CaseProcessingCounts,
  formatProcessingLabel,
  getDocumentProcessingProgress,
  getDocumentProcessingStageCopy,
  getDocumentProcessingStageLabel,
} from "./case-processing-state";

const PROCESSING_STAGE_FLOW = [
  { key: "uploaded", label: "Uploaded" },
  { key: "ocr", label: "OCR" },
  { key: "extracting", label: "Extracting" },
  { key: "scoring", label: "Scoring" },
] as const;

type ProcessingStageKey = (typeof PROCESSING_STAGE_FLOW)[number]["key"];

function SummaryRow({
  label,
  tone,
  value,
}: {
  label: string;
  tone: "good" | "warning" | "danger" | "neutral";
  value: string;
}) {
  const dotMotionClasses: Record<"good" | "warning" | "danger" | "neutral", string> = {
    danger: "",
    good: "",
    neutral: "",
    warning: "animate-ai-pulse",
  };
  const dotToneClasses: Record<"good" | "warning" | "danger" | "neutral", string> = {
    danger: "bg-red-500",
    good: "bg-emerald-500",
    neutral: "bg-blue-500",
    warning: "bg-amber-500",
  };

  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-[var(--border-card)] bg-[var(--background)]/40 px-3 py-3">
      <div className="flex items-center gap-2">
        <span
          className={`h-2.5 w-2.5 shrink-0 rounded-full ${dotToneClasses[tone]} ${dotMotionClasses[tone]}`}
          aria-hidden="true"
        />
        <p className="text-[13px] font-medium text-[var(--text-secondary)]">{label}</p>
      </div>
      <p className="text-[18px] font-semibold tabular-nums text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

function formatBackendTime(value: string | null | undefined) {
  if (!value) return null;

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return parsed.toLocaleTimeString("en-IN", {
    hour: "numeric",
    minute: "2-digit",
  });
}

function getHeadline(totalDocuments: number) {
  return totalDocuments === 1 ? "We're analyzing your document." : "We're analyzing your documents.";
}

function normalizeProcessingValue(value: string | null | undefined) {
  return String(value || "").trim().toLowerCase();
}

function getStageKey(document: CaseDocumentReadModel): ProcessingStageKey {
  const stage = normalizeProcessingValue(document.ocr_status?.stage);
  const status = normalizeProcessingValue(document.status);

  if (stage === "extracting") {
    return "extracting";
  }

  if (stage === "ocr") {
    return "ocr";
  }

  if (status === "processing") {
    return "scoring";
  }

  return "ocr";
}

function getDominantStageKey(activeDocuments: CaseDocumentReadModel[]): ProcessingStageKey {
  if (activeDocuments.length === 0) {
    return "uploaded";
  }

  return activeDocuments
    .map(getStageKey)
    .sort(
      (left, right) =>
        PROCESSING_STAGE_FLOW.findIndex((stage) => stage.key === right) -
        PROCESSING_STAGE_FLOW.findIndex((stage) => stage.key === left)
    )[0];
}

function getStageCopy(stageKey: ProcessingStageKey, activeCount: number) {
  const plurality = activeCount === 1 ? "document" : "documents";

  if (stageKey === "ocr") {
    return `OCR is reading the active ${plurality} and turning pages into structured text.`;
  }

  if (stageKey === "extracting") {
    return `We're extracting transactions, balances, and key financial fields from the active ${plurality}.`;
  }

  if (stageKey === "scoring") {
    return `We're validating patterns and scoring the extracted financial data from the active ${plurality}.`;
  }

  return `Your ${plurality} uploaded successfully and backend processing has started.`;
}

function getActivePageSnapshot(activeDocuments: CaseDocumentReadModel[]) {
  let trackedDocuments = 0;
  let processedPages = 0;
  let totalPages = 0;

  activeDocuments.forEach((document) => {
    const nextTotalPages = document.ocr_status?.total_pages;
    if (!nextTotalPages || nextTotalPages <= 0) {
      return;
    }

    trackedDocuments += 1;
    totalPages += nextTotalPages;
    processedPages += Math.min(Math.max(document.ocr_status?.pages_processed ?? 0, 0), nextTotalPages);
  });

  if (trackedDocuments === 0 || totalPages === 0) {
    return null;
  }

  return {
    percent: Math.round((processedPages / totalPages) * 100),
    processedPages,
    totalPages,
    trackedDocuments,
  };
}

function getPrimaryStatusLine({
  activeCount,
  finishedDocuments,
  totalDocuments,
}: {
  activeCount: number;
  finishedDocuments: number;
  totalDocuments: number;
}) {
  if (activeCount <= 0) {
    return `${finishedDocuments} of ${totalDocuments} finished`;
  }

  return activeCount === 1 ? "Processing 1 document" : `Processing ${activeCount} documents`;
}

function getReassuranceCopy(totalDocuments: number) {
  return totalDocuments === 1
    ? "This usually takes 10-30 seconds. We're extracting and validating financial data from your document."
    : "This usually takes 10-30 seconds. We're extracting and validating financial data from your documents.";
}

function formatProgressSummary(document: CaseDocumentReadModel) {
  const progress = getDocumentProcessingProgress(document);
  if (progress.percent !== null && progress.label) {
    return `${progress.percent}% complete - ${progress.label}`;
  }

  if (progress.percent !== null && progress.label) {
    return `${progress.percent}% complete • ${progress.label}`;
  }

  if (progress.label) {
    return progress.label;
  }

  return "Waiting for page-level progress from the backend";
}

function StageFlow({
  activeCount,
  currentStageKey,
}: {
  activeCount: number;
  currentStageKey: ProcessingStageKey;
}) {
  const currentStageIndex = PROCESSING_STAGE_FLOW.findIndex((stage) => stage.key === currentStageKey);

  return (
    <div className="mt-4">
      <div className="grid grid-cols-4 gap-2" aria-label="Processing workflow stages">
        {PROCESSING_STAGE_FLOW.map((stage, index) => {
          const isComplete = index < currentStageIndex;
          const isCurrent = index === currentStageIndex;

          return (
            <div key={stage.key} className="space-y-2">
              <div
                className={`h-1.5 rounded-full transition-colors ${
                  isCurrent
                    ? "bg-primary animate-ai-pulse"
                    : isComplete
                      ? "bg-primary/80"
                      : "bg-[var(--border-card)]"
                }`}
              />
              <p
                className={`text-[11px] font-medium ${
                  isCurrent
                    ? "text-[var(--text-primary)]"
                    : isComplete
                      ? "text-[var(--text-secondary)]"
                      : "text-[var(--text-tertiary)]"
                }`}
              >
                {stage.label}
              </p>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[12px] text-[var(--text-tertiary)]">
        {activeCount === 1
          ? `Current live step: ${PROCESSING_STAGE_FLOW[currentStageIndex]?.label || "Processing"}.`
          : `Most active work is in ${PROCESSING_STAGE_FLOW[currentStageIndex]?.label || "Processing"} right now.`}
      </p>
    </div>
  );
}

export function CaseProcessingWaitingScreen({
  activeDocuments,
  caseTitle,
  counts,
  onRefresh,
}: {
  activeDocuments: CaseDocumentReadModel[];
  caseTitle: string;
  counts: CaseProcessingCounts;
  onRefresh: () => void | Promise<void>;
}) {
  const totalDocuments = Math.max(counts.analyzedCount + counts.activeCount + counts.failedOrBlockedCount, 1);
  const finishedDocuments = counts.analyzedCount + counts.failedOrBlockedCount;
  const finishedPercent = Math.round((finishedDocuments / totalDocuments) * 100);
  const activePageSnapshot = getActivePageSnapshot(activeDocuments);
  const currentStageKey = getDominantStageKey(activeDocuments);
  const activeDocumentLabel = counts.activeCount === 1 ? "1 document still running" : `${counts.activeCount} documents still running`;
  const summaryProgressValue = activePageSnapshot?.percent ?? finishedPercent;
  const summaryProgressLabel = activePageSnapshot
    ? `${activePageSnapshot.percent}% of tracked pages processed.`
    : `${finishedDocuments} ready, ${counts.activeCount} still in progress.`;
  const primaryStatusLine = getPrimaryStatusLine({
    activeCount: counts.activeCount,
    finishedDocuments,
    totalDocuments,
  });

  return (
    <div className="flex flex-col gap-6 pb-12" data-testid="case-processing-waiting-screen">
      <div className="flex items-center gap-3">
        <Button asChild variant="ghost" size="icon" className="h-8 w-8 cursor-pointer">
          <Link aria-label="Back to cases" href="/dashboard/cases">
            <ChevronLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-tertiary)]">
            Case Analysis
          </p>
          <h1 className="text-[22px] font-semibold tracking-tight text-[var(--text-primary)]">{caseTitle}</h1>
        </div>
      </div>

      <section className="card-base overflow-hidden px-6 py-6">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-2xl">
            <div
              className="inline-flex items-center gap-2 rounded-full border border-blue-500/20 bg-blue-500/10 px-3 py-1 text-[12px] font-medium text-blue-500"
              role="status"
            >
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Backend analysis in progress
            </div>
            <h2 className="mt-4 text-[28px] font-semibold tracking-tight text-[var(--text-primary)]">
              {getHeadline(totalDocuments)}
            </h2>
            <p className="mt-3 text-[14px] leading-relaxed text-[var(--text-secondary)]">
              We poll the backend every few seconds and open the full case detail page automatically when processing
              finishes or if the backend stops moving long enough to look stalled.
            </p>
            <p className="mt-3 text-[15px] font-medium text-[var(--text-primary)]">{getReassuranceCopy(totalDocuments)}</p>
            <p className="mt-2 text-[13px] text-[var(--text-tertiary)]">
              {getStageCopy(currentStageKey, counts.activeCount)} Latest snapshot: {activeDocumentLabel}.
            </p>
          </div>

          <div
            className="relative w-full max-w-sm overflow-hidden rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] px-4 py-4"
            role="status"
            aria-live="polite"
          >
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 opacity-40 animate-shimmer"
              style={{
                backgroundImage:
                  "linear-gradient(110deg, transparent 20%, rgba(129, 140, 248, 0.14) 45%, transparent 70%)",
              }}
            />
            <div className="relative">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-tertiary)]">
                Case Status
              </p>
              <p className="mt-2 text-[20px] font-semibold text-[var(--text-primary)]">
                {primaryStatusLine}
              </p>
              <p className="mt-1 text-[13px] text-[var(--text-secondary)]">{summaryProgressLabel}</p>
              <Progress
                className="mt-4 h-2.5"
                value={summaryProgressValue}
                aria-label={
                  activePageSnapshot
                    ? `${activePageSnapshot.percent}% of tracked pages processed`
                    : `Finished backend processing for ${finishedDocuments} of ${totalDocuments} documents`
                }
              />
              <p className="mt-3 text-[12px] text-[var(--text-tertiary)]">
                {activePageSnapshot
                  ? `Live OCR page tracking: ${activePageSnapshot.processedPages}/${activePageSnapshot.totalPages} pages across ${activePageSnapshot.trackedDocuments} active ${activePageSnapshot.trackedDocuments === 1 ? "document" : "documents"}.`
                  : "Live page counters will appear here as soon as the backend sends them."}
              </p>
              <StageFlow activeCount={counts.activeCount} currentStageKey={currentStageKey} />
              <div className="mt-4 space-y-2.5">
                <SummaryRow label="Ready" tone="good" value={String(counts.analyzedCount)} />
                <SummaryRow label="In progress" tone="warning" value={String(counts.activeCount)} />
                <SummaryRow label="Needs attention" tone="danger" value={String(counts.failedOrBlockedCount)} />
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)]">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-tertiary)]">
              Active documents
            </p>
            <p className="mt-1 text-[13px] text-[var(--text-secondary)]">
              Latest backend status for the documents still in flight. This view auto-refreshes every few seconds.
            </p>
          </div>

          <div className="divide-y divide-[var(--border-card)]">
            {activeDocuments.map((document) => {
              const progress = getDocumentProcessingProgress(document);
              const backendTime = formatBackendTime(document.updated_at);
              const progressSummary = formatProgressSummary(document);

              return (
                <div
                  key={document.id}
                  className="grid gap-4 px-5 py-4 lg:grid-cols-[1.5fr_1fr]"
                  data-testid="case-processing-active-document-row"
                >
                  <div className="min-w-0">
                    <div className="flex items-start gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                        <FileText className="h-4 w-4 text-primary" />
                      </div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate text-[14px] font-medium text-[var(--text-primary)]">
                            {document.original_filename}
                          </p>
                          <StatusPill label={getDocumentProcessingStageLabel(document)} status="warning" />
                        </div>
                        <p className="mt-1 text-[12px] text-[var(--text-tertiary)]">
                          {formatProcessingLabel(document.document_type)}
                        </p>
                        <p className="mt-3 text-[13px] leading-relaxed text-[var(--text-secondary)]">
                          {getDocumentProcessingStageCopy(document)}
                        </p>
                        <StageFlow activeCount={1} currentStageKey={getStageKey(document)} />
                        <p className="mt-3 text-[12px] text-[var(--text-tertiary)]">
                          {backendTime ? `Last backend update ${backendTime}` : "Waiting for the first backend update"}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-[var(--border-card)] bg-[var(--background)]/60 px-4 py-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-tertiary)]">
                      Backend Status
                    </p>
                    <div className="mt-3">
                      {progress.percent !== null ? (
                        <Progress
                          value={progress.percent}
                          aria-label={`${progress.percent}% of tracked pages processed for ${document.original_filename}`}
                        />
                      ) : (
                        <div className="h-2 overflow-hidden rounded-full bg-primary/20" aria-hidden="true">
                          <div className="h-full w-1/3 rounded-full bg-primary/70 animate-pulse" />
                        </div>
                      )}
                    </div>
                    <p className="mt-3 text-[13px] font-medium text-[var(--text-primary)]" aria-live="polite">
                      {progressSummary}
                    </p>
                    <p className="mt-1 text-[12px] text-[var(--text-tertiary)]">
                      Backend stage: {getDocumentProcessingStageLabel(document)}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            className="cursor-pointer text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]"
            onClick={() => void onRefresh()}
          >
            Refresh Now
          </Button>
          <Button asChild variant="outline" className="cursor-pointer">
            <Link href="/dashboard/cases">Back to Cases</Link>
          </Button>
        </div>
      </section>
    </div>
  );
}

export function CaseProcessingBanner({
  body,
  title,
  variant,
}: {
  body: string;
  title: string;
  variant: "resumed" | "stale";
}) {
  const tones =
    variant === "stale"
      ? "border-amber-500/20 bg-amber-500/10 text-amber-600"
      : "border-blue-500/20 bg-blue-500/10 text-blue-500";

  const testId = variant === "stale" ? "case-processing-stale-banner" : "case-processing-resumed-banner";

  return (
    <div className={`rounded-2xl border px-4 py-3 ${tones}`} data-testid={testId}>
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="text-[13px] font-semibold text-[var(--text-primary)]">{title}</p>
          <p className="mt-1 text-[12px] text-[var(--text-secondary)]">{body}</p>
        </div>
      </div>
    </div>
  );
}
