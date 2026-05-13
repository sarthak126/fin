"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import { AlertTriangle, ArrowUpRight, CheckCircle2, ClipboardList, Clock, FileText, Loader2, RefreshCw, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  PageHeader,
  ProgressBar,
  SectionHeading,
  StatusBadge,
  Surface,
} from "@/components/argentnorth/prototype-ui";
import {
  ApiError,
  getCaseReadModel,
  listCases,
  type CaseListItem,
  type CaseReadModel,
  type DecisionStatus,
} from "@/lib/api";
import { getApiToken } from "@/lib/auth";
import type { RiskTone } from "@/lib/argentnorth-prototype";

interface CaseRow {
  caseItem: CaseListItem;
  readModel: CaseReadModel | null;
}

const DECISION_BADGE_STYLES: Record<DecisionStatus, string> = {
  approve: "text-emerald-500 bg-emerald-500/10 border-transparent",
  manual_review: "text-amber-500 bg-amber-500/10 border-transparent",
  reject: "text-red-500 bg-red-500/10 border-transparent",
  insufficient_history: "text-sky-500 bg-sky-500/10 border-transparent",
};

function getDecisionTone(status: DecisionStatus | null | undefined): RiskTone {
  if (status === "approve") return "good";
  if (status === "reject") return "danger";
  if (status === "manual_review" || status === "insufficient_history") return "warning";
  return "neutral";
}

function formatDate(dateStr?: string | null) {
  if (!dateStr) return "--";

  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return "--";

  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatWorkflowStatus(status: string | null | undefined) {
  if (!status) return "Draft";

  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDecisionStatus(status: DecisionStatus | null | undefined) {
  if (!status) return "Pending";

  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function getApplicantName(caseItem: CaseListItem) {
  const applicantName = caseItem.applicant_name?.trim();
  if (applicantName) return applicantName;

  const caseName = caseItem.name?.trim();
  if (caseName) return caseName;

  return `Case ${caseItem.id.slice(0, 8)}`;
}

function getLatestTimestamp(values: Array<string | null | undefined>) {
  let latest: Date | null = null;

  for (const value of values) {
    if (!value) continue;

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) continue;

    if (!latest || parsed.getTime() > latest.getTime()) {
      latest = parsed;
    }
  }

  return latest?.toISOString() ?? null;
}

function getLatestDecisionStatus(readModel: CaseReadModel | null): DecisionStatus | null {
  return readModel?.authoritative_analysis?.decision_status ?? readModel?.provisional_insights.decision_status ?? null;
}

function getDecisionBadge(readModel: CaseReadModel | null) {
  const status = getLatestDecisionStatus(readModel);
  if (status) {
    return {
      label: formatDecisionStatus(status),
      className: DECISION_BADGE_STYLES[status],
      tone: getDecisionTone(status),
    };
  }

  if (!readModel) {
    return {
      label: "Unavailable",
      className: "text-[var(--text-muted)] bg-[var(--surface-secondary)] border-transparent",
      tone: "neutral" as RiskTone,
    };
  }

  if (readModel.documents.some((document) => document.status === "processing")) {
    return {
      label: "Processing",
      className: "text-blue-500 bg-blue-500/10 border-transparent",
      tone: "neutral" as RiskTone,
    };
  }

  if (readModel.documents.some((document) => document.status === "failed")) {
    return {
      label: "Needs Retry",
      className: "text-red-500 bg-red-500/10 border-transparent",
      tone: "danger" as RiskTone,
    };
  }

  if (readModel.documents.length === 0) {
    return {
      label: "Awaiting Docs",
      className: "text-[var(--text-muted)] bg-[var(--surface-secondary)] border-transparent",
      tone: "neutral" as RiskTone,
    };
  }

  return {
    label: "Pending Analysis",
    className: "text-amber-500 bg-amber-500/10 border-transparent",
    tone: "warning" as RiskTone,
  };
}

function getLastUpdated(caseItem: CaseListItem, readModel: CaseReadModel | null) {
  if (!readModel) {
    return caseItem.updated_at || caseItem.created_at;
  }

  return getLatestTimestamp([
    caseItem.created_at,
    caseItem.updated_at,
    readModel.case.created_at,
    readModel.case.updated_at,
    readModel.authoritative_analysis?.created_at,
    ...readModel.documents.flatMap((document) => [
      document.created_at,
      document.updated_at,
      document.latest_analysis?.created_at,
    ]),
  ]);
}

function getDocumentSummary(readModel: CaseReadModel | null) {
  if (!readModel) {
    return {
      countLabel: "--",
      detail: "Case data unavailable",
    };
  }

  const analyzedCount = readModel.documents.filter((document) => document.status === "analyzed").length;
  const processingCount = readModel.documents.filter((document) => document.status === "processing").length;
  const failedCount = readModel.documents.filter((document) => document.status === "failed").length;
  const pendingCount = readModel.documents.filter((document) => document.status === "pending").length;

  const detailParts = [
    analyzedCount > 0 ? `${analyzedCount} analyzed` : null,
    processingCount > 0 ? `${processingCount} processing` : null,
    failedCount > 0 ? `${failedCount} failed` : null,
    pendingCount > 0 ? `${pendingCount} pending` : null,
  ].filter((value): value is string => Boolean(value));

  return {
    countLabel: `${readModel.documents.length}`,
    detail: detailParts.join(" | ") || "No uploaded documents",
  };
}

function getCompletenessSummary(readModel: CaseReadModel | null) {
  if (!readModel) {
    return {
      label: "Unavailable",
      detail: "Could not load completeness",
      percent: 0,
      fillClassName: "bg-[var(--surface-secondary)]",
    };
  }

  const completeness = readModel.supported_document_completeness;
  const providedCount = completeness.provided_requirement_count;
  const analyzedCount = completeness.analyzed_requirement_count;
  const totalCount = completeness.total_requirement_count;
  const missingCount = completeness.missing_requirement_keys.length;
  const pendingCount = completeness.pending_requirement_keys.length;

  if (totalCount === 0) {
    return {
      label: "No supported docs",
      detail: "Requirements have not been configured",
      percent: 0,
      fillClassName: "bg-[var(--surface-secondary)]",
    };
  }

  if (missingCount > 0) {
    return {
      label: `${providedCount}/${totalCount} complete`,
      detail: `${missingCount} missing`,
      percent: Math.round((providedCount / totalCount) * 100),
      fillClassName: "bg-amber-500",
    };
  }

  if (pendingCount > 0 || analyzedCount < providedCount) {
    return {
      label: `${providedCount}/${totalCount} complete`,
      detail: `${Math.max(providedCount - analyzedCount, pendingCount)} pending analysis`,
      percent: Math.round((providedCount / totalCount) * 100),
      fillClassName: "bg-blue-500",
    };
  }

  return {
    label: `${providedCount}/${totalCount} complete`,
    detail: "All provided docs analyzed",
    percent: Math.round((providedCount / totalCount) * 100),
    fillClassName: "bg-emerald-500",
  };
}

function isRecoverableCaseHydrationError(error: unknown) {
  return error instanceof ApiError && [401, 403, 404].includes(error.status);
}

function getCasesLoadErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) {
      return "Your session expired while loading cases. Refresh the page and sign in again.";
    }
    return error.message;
  }

  return "Failed to load cases. Make sure the backend is running on port 8000.";
}

export default function CasesPage() {
  const { getToken } = useAuth();
  const [caseRows, setCaseRows] = useState<CaseRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadCases = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const token = await getApiToken(getToken);
      const cases = await listCases(token);

      const hydratedRows = await Promise.all(
        cases.map(async (caseItem) => {
          try {
            const readModel = await getCaseReadModel(caseItem.id, token);
            return { caseItem, readModel };
          } catch (readModelError) {
            if (!isRecoverableCaseHydrationError(readModelError)) {
              console.warn(`Failed to hydrate case ${caseItem.id}`, readModelError);
            }
            return { caseItem, readModel: null };
          }
        })
      );

      hydratedRows.sort((left, right) => {
        const leftUpdatedAt = getLastUpdated(left.caseItem, left.readModel);
        const rightUpdatedAt = getLastUpdated(right.caseItem, right.readModel);

        const leftTime = leftUpdatedAt ? new Date(leftUpdatedAt).getTime() : 0;
        const rightTime = rightUpdatedAt ? new Date(rightUpdatedAt).getTime() : 0;

        return rightTime - leftTime;
      });

      setCaseRows(hydratedRows);
    } catch (loadError) {
      if (loadError instanceof ApiError && (loadError.status === 401 || loadError.status === 403)) {
        console.warn("Cases list request lost authorization.", loadError);
      } else {
        console.error("Failed to load cases:", loadError);
      }
      setError(getCasesLoadErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    void loadCases();
  }, [loadCases]);

  if (loading) {
    return (
      <div className="flex flex-col gap-6 pb-10">
        <PageHeader
          eyebrow="Case Queue"
          title="Underwriting workbench."
          description="Live applications, evidence completeness, decisions, and aging signals across the credit queue."
        />
        <div id="cases-table-area">
          <Surface className="overflow-hidden">
            <div className="flex flex-col items-center justify-center py-24">
              <Loader2 className="mb-3 h-6 w-6 animate-spin text-primary" />
              <p className="text-[13px] font-medium text-[var(--text-secondary)]">Loading case queue...</p>
            </div>
          </Surface>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col gap-6 pb-10">
        <PageHeader
          eyebrow="Case Queue"
          title="Underwriting workbench."
          description="Live applications, evidence completeness, decisions, and aging signals across the credit queue."
        />
        <Surface className="overflow-hidden">
          <div className="flex flex-col items-center justify-center px-6 py-24">
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-red-500/10">
              <AlertTriangle className="h-5 w-5 text-red-500" />
            </div>
            <p className="mb-1 text-[14px] font-semibold text-[var(--text-primary)]">Queue connection failed</p>
            <p className="mb-4 max-w-[360px] text-center text-[13px] leading-relaxed text-[var(--text-tertiary)]">
              {error}
            </p>
            <Button
              onClick={loadCases}
              className="h-9 cursor-pointer gap-1.5 rounded-lg bg-primary px-4 text-[13px] font-semibold text-primary-foreground hover:bg-primary/90"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Retry
            </Button>
          </div>
        </Surface>
      </div>
    );
  }

  if (caseRows.length === 0) {
    return (
      <div className="flex flex-col gap-6 pb-10">
        <PageHeader
          eyebrow="Case Queue"
          title="Underwriting workbench."
          description="Live applications, evidence completeness, decisions, and aging signals across the credit queue."
        />
        <Surface className="overflow-hidden" id="cases-table-area">
          <div className="flex flex-col items-center justify-center px-6 py-24">
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--surface-secondary)]">
              <FileText className="h-5 w-5 text-[var(--text-muted)]" />
            </div>
            <p className="mb-1 text-[14px] font-semibold text-[var(--text-primary)]">No cases in the queue</p>
            <p className="mb-6 max-w-[300px] text-center text-[13px] leading-relaxed text-[var(--text-tertiary)]">
              Upload documents to start a case and track applicant readiness here.
            </p>
            <div className="flex items-center gap-2">
              <Button
                asChild
                className="h-9 cursor-pointer gap-1.5 rounded-lg bg-primary px-4 text-[13px] font-medium text-primary-foreground hover:bg-primary/90"
              >
                <Link href="/dashboard/upload">
                  <Upload className="h-3.5 w-3.5" />
                  Start Case
                </Link>
              </Button>
              <Button
                variant="ghost"
                asChild
                className="h-9 cursor-pointer rounded-lg px-4 text-[13px] text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
              >
                <Link href="/dashboard/cases/demo">View Demo</Link>
              </Button>
            </div>
          </div>
        </Surface>
      </div>
    );
  }

  const approvedCount = caseRows.filter(({ readModel }) => getLatestDecisionStatus(readModel) === "approve").length;
  const reviewCount = caseRows.filter(({ readModel }) => getLatestDecisionStatus(readModel) === "manual_review").length;
  const attentionCount = caseRows.filter(({ readModel }) => {
    const decision = getLatestDecisionStatus(readModel);
    return decision === "reject" || decision === "insufficient_history" || readModel?.documents.some((document) => document.status === "failed");
  }).length;
  const documentCount = caseRows.reduce((total, row) => total + (row.readModel?.documents.length ?? 0), 0);
  const completenessAverage = Math.round(
    caseRows.reduce((total, row) => total + getCompletenessSummary(row.readModel).percent, 0) / caseRows.length
  );

  return (
    <div className="flex flex-col gap-6 pb-10">
      <PageHeader
        eyebrow="Case Queue"
        title="Underwriting workbench."
        description="Live applications, evidence completeness, decisions, and aging signals across the credit queue."
      >
        <Button
          asChild
          className="h-9 cursor-pointer gap-1.5 rounded-lg bg-primary px-4 text-[13px] font-semibold text-primary-foreground hover:bg-primary/90"
        >
          <Link href="/dashboard/upload">
            <Upload className="h-3.5 w-3.5" />
            New Case
          </Link>
        </Button>
      </PageHeader>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Surface className="p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-tertiary)]">Active cases</p>
              <p className="mt-3 font-mono text-[30px] font-semibold leading-none text-[var(--text-primary)] tabular-nums">
                {caseRows.length}
              </p>
            </div>
            <FileText className="h-4 w-4 text-primary" />
          </div>
          <p className="mt-4 text-[12px] text-[var(--text-tertiary)]">{documentCount} documents attached</p>
        </Surface>

        <Surface className="p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-tertiary)]">Ready</p>
              <p className="mt-3 font-mono text-[30px] font-semibold leading-none text-emerald-500 tabular-nums">
                {approvedCount}
              </p>
            </div>
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          </div>
          <p className="mt-4 text-[12px] text-[var(--text-tertiary)]">{reviewCount} require reviewer action</p>
        </Surface>

        <Surface className="p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-tertiary)]">Attention</p>
              <p className="mt-3 font-mono text-[30px] font-semibold leading-none text-amber-500 tabular-nums">
                {attentionCount}
              </p>
            </div>
            <AlertTriangle className="h-4 w-4 text-amber-500" />
          </div>
          <p className="mt-4 text-[12px] text-[var(--text-tertiary)]">Rejected, failed, or insufficient history</p>
        </Surface>

        <Surface className="p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-tertiary)]">Completeness</p>
              <p className="mt-3 font-mono text-[30px] font-semibold leading-none text-[var(--text-primary)] tabular-nums">
                {completenessAverage}%
              </p>
            </div>
            <Clock className="h-4 w-4 text-primary" />
          </div>
          <ProgressBar value={completenessAverage} tone={completenessAverage >= 80 ? "good" : "warning"} className="mt-4 h-1.5" />
        </Surface>
      </div>

      <Surface className="overflow-hidden" id="cases-table-area">
        <div className="border-b border-[var(--border-card)] px-5 py-4">
          <SectionHeading
            icon={ClipboardList}
            title="Active Queue"
            description="Sorted by latest case, document, and analysis activity."
          />
        </div>

        <div className="hidden grid-cols-12 border-b border-[var(--border-card)] bg-[var(--surface-secondary)]/45 px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)] sm:grid">
          <div className="col-span-4">Applicant</div>
          <div className="col-span-2">Documents</div>
          <div className="col-span-2">Supported Docs</div>
          <div className="col-span-2">Latest Decision</div>
          <div className="col-span-2">Last Updated</div>
        </div>

        {caseRows.map(({ caseItem, readModel }) => {
          const documentSummary = getDocumentSummary(readModel);
          const completenessSummary = getCompletenessSummary(readModel);
          const decisionBadge = getDecisionBadge(readModel);
          const lastUpdated = getLastUpdated(caseItem, readModel);
          const detailHref = `/dashboard/cases/${caseItem.id}`;

          const rowContent = (
            <>
              <div className="col-span-4 min-w-0">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                    <FileText className="h-4 w-4 text-primary" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-medium text-[var(--text-primary)]">
                      {getApplicantName(caseItem)}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <p className="truncate text-[11px] text-[var(--text-muted)]">
                        {caseItem.name?.trim() || `Case ${caseItem.id.slice(0, 8)}`}
                      </p>
                      <StatusBadge label={formatWorkflowStatus(caseItem.status)} tone="neutral" />
                    </div>
                  </div>
                </div>
              </div>

              <div className="col-span-2">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] sm:hidden">
                  Documents
                </p>
                <p className="text-[13px] font-medium text-[var(--text-primary)]">
                  {documentSummary.countLabel === "--"
                    ? "Documents unavailable"
                    : `${documentSummary.countLabel} document${documentSummary.countLabel === "1" ? "" : "s"}`}
                </p>
                <p className="text-[11px] text-[var(--text-muted)]">{documentSummary.detail}</p>
              </div>

              <div className="col-span-2">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] sm:hidden">
                  Supported Docs
                </p>
                <p className="text-[13px] font-medium text-[var(--text-primary)]">{completenessSummary.label}</p>
                <ProgressBar
                  value={completenessSummary.percent}
                  tone={completenessSummary.percent >= 80 ? "good" : "warning"}
                  className="mt-2 h-1.5"
                />
                <p className="mt-1 text-[11px] text-[var(--text-muted)]">{completenessSummary.detail}</p>
              </div>

              <div className="col-span-2">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] sm:hidden">
                  Latest Decision
                </p>
                <StatusBadge label={decisionBadge.label} tone={decisionBadge.tone} />
              </div>

              <div className="col-span-2 flex items-center justify-between gap-3">
                <div>
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] sm:hidden">
                    Last Updated
                  </p>
                  <p className="text-[12px] text-[var(--text-muted)]">{formatDate(lastUpdated)}</p>
                </div>
                <ArrowUpRight className="h-3.5 w-3.5 text-[var(--text-faint)]" />
              </div>
            </>
          );

          const rowClassName = "grid grid-cols-1 items-start gap-4 border-b border-[var(--border-subtle)] px-5 py-4 transition-colors hover:bg-[var(--surface-hover)] cursor-pointer sm:grid-cols-12 sm:items-center sm:gap-0";

          return (
            <Link key={caseItem.id} href={detailHref} className={rowClassName}>
              {rowContent}
            </Link>
          );
        })}
      </Surface>
    </div>
  );
}
