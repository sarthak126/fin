"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import {
  AlertTriangle,
  ArrowUpRight,
  ClipboardList,
  FileText,
  Filter,
  Loader2,
  RefreshCw,
  Search,
  Upload,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  PageHeader,
  ProgressBar,
  SectionHeading,
  StatusBadge,
  Surface,
} from "@/components/argentnorth/prototype-ui";
import { cn } from "@/lib/utils";
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

type QueueFilter = "All" | "Review" | "Attention";

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

function getRiskBandTone(band: "Low" | "Medium" | "High"): RiskTone {
  if (band === "Low") return "good";
  if (band === "High") return "danger";
  return "warning";
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

function getLatestRiskScore(readModel: CaseReadModel | null): number | null {
  return (
    readModel?.authoritative_analysis?.risk_score ??
    readModel?.provisional_insights.highest_risk_score ??
    null
  );
}

function getRiskBand(score: number | null): "Low" | "Medium" | "High" | null {
  if (score === null || Number.isNaN(score)) return null;
  if (score < 40) return "Low";
  if (score < 70) return "Medium";
  return "High";
}

function getRiskCell(readModel: CaseReadModel | null): {
  label: string;
  tone: RiskTone;
  score: number | null;
} {
  const score = getLatestRiskScore(readModel);
  const band = getRiskBand(score);

  if (band === null || score === null) {
    return {
      label: "Pending",
      tone: "neutral",
      score: null,
    };
  }

  return {
    label: `${band} ${score.toFixed(0)}`,
    tone: getRiskBandTone(band),
    score,
  };
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

function getCompletenessPercent(readModel: CaseReadModel | null): number {
  if (!readModel) return 0;
  const completeness = readModel.supported_document_completeness;
  if (completeness.total_requirement_count === 0) return 0;
  return Math.round(
    (completeness.provided_requirement_count / completeness.total_requirement_count) * 100
  );
}

function getCompletenessDetail(readModel: CaseReadModel | null) {
  if (!readModel) return "Unavailable";
  const completeness = readModel.supported_document_completeness;
  if (completeness.total_requirement_count === 0) return "No requirements";
  if (completeness.missing_requirement_keys.length > 0) {
    return `${completeness.missing_requirement_keys.length} missing`;
  }
  if (completeness.pending_requirement_keys.length > 0) {
    return `${completeness.pending_requirement_keys.length} pending`;
  }
  return "All docs analyzed";
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

function matchesSearch(row: CaseRow, query: string) {
  if (!query) return true;
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  const applicant = getApplicantName(row.caseItem).toLowerCase();
  const name = (row.caseItem.name ?? "").toLowerCase();
  const id = row.caseItem.id.toLowerCase();
  return applicant.includes(needle) || name.includes(needle) || id.includes(needle);
}

function matchesFilter(row: CaseRow, filter: QueueFilter) {
  if (filter === "All") return true;
  const decision = getLatestDecisionStatus(row.readModel);
  if (filter === "Review") {
    return decision === "manual_review";
  }
  if (filter === "Attention") {
    return (
      decision === "reject" ||
      decision === "insufficient_history" ||
      (row.readModel?.documents.some((document) => document.status === "failed") ?? false)
    );
  }
  return true;
}

export default function CasesPage() {
  const { getToken } = useAuth();
  const [caseRows, setCaseRows] = useState<CaseRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [queueFilter, setQueueFilter] = useState<QueueFilter>("All");
  const [searchQuery, setSearchQuery] = useState("");

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

  const visibleRows = useMemo(
    () => caseRows.filter((row) => matchesFilter(row, queueFilter) && matchesSearch(row, searchQuery)),
    [caseRows, queueFilter, searchQuery]
  );

  const reviewCount = useMemo(
    () => caseRows.filter((row) => getLatestDecisionStatus(row.readModel) === "manual_review").length,
    [caseRows]
  );

  const approveCount = useMemo(
    () => caseRows.filter((row) => getLatestDecisionStatus(row.readModel) === "approve").length,
    [caseRows]
  );

  const awaitingCount = useMemo(
    () => caseRows.filter((row) => getLatestDecisionStatus(row.readModel) === null).length,
    [caseRows]
  );

  if (loading) {
    return (
      <div className="flex flex-col gap-10 pb-10">
        <PageHeader
          eyebrow="Case Queue"
          title="Decision book for active capital movement."
          description="Every row exposes evidence sufficiency, latest risk score, and decision posture across the credit queue."
        />
        <Surface className="overflow-hidden">
          <div className="flex flex-col items-center justify-center py-24">
            <Loader2 className="mb-3 h-6 w-6 animate-spin text-primary" />
            <p className="text-[13px] font-medium text-[var(--text-secondary)]">Loading case queue...</p>
          </div>
        </Surface>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col gap-10 pb-10">
        <PageHeader
          eyebrow="Case Queue"
          title="Decision book for active capital movement."
          description="Every row exposes evidence sufficiency, latest risk score, and decision posture across the credit queue."
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
      <div className="flex flex-col gap-10 pb-10">
        <PageHeader
          eyebrow="Case Queue"
          title="Decision book for active capital movement."
          description="Every row exposes evidence sufficiency, latest risk score, and decision posture across the credit queue."
        />
        <Surface className="overflow-hidden">
          <div className="flex flex-col items-center justify-center px-6 py-24">
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--surface-secondary)]">
              <FileText className="h-5 w-5 text-[var(--text-muted)]" />
            </div>
            <p className="mb-1 text-[14px] font-semibold text-[var(--text-primary)]">No cases in the queue</p>
            <p className="mb-6 max-w-[300px] text-center text-[13px] leading-relaxed text-[var(--text-tertiary)]">
              Upload documents to start a case and track applicant readiness here.
            </p>
            <Button
              asChild
              className="h-9 cursor-pointer gap-1.5 rounded-lg bg-primary px-4 text-[13px] font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Link href="/dashboard/upload">
                <Upload className="h-3.5 w-3.5" />
                Start Case
              </Link>
            </Button>
          </div>
        </Surface>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-10 pb-10">
      <PageHeader
        eyebrow="Case Queue"
        title="Decision book for active capital movement."
        description="Every row exposes evidence sufficiency, latest risk score, and decision posture across the credit queue."
      >
        <Button
          type="button"
          variant="outline"
          className="h-9 rounded-md border-[var(--border-card)] bg-[var(--surface-raised)] text-[13px]"
        >
          <Filter className="h-3.5 w-3.5" />
          Filters
        </Button>
        <Button
          asChild
          className="h-9 rounded-md bg-primary px-4 text-[13px] font-semibold text-primary-foreground"
        >
          <Link href="/dashboard/upload">
            <Upload className="h-3.5 w-3.5" />
            New case
          </Link>
        </Button>
      </PageHeader>

      <div className="grid gap-px overflow-hidden rounded-md border border-[var(--border-card)] md:grid-cols-4">
        <div className="bg-[var(--surface-raised)] p-5">
          <p className="text-[12px] text-[var(--text-muted)]">Active cases</p>
          <p className="mt-2 font-mono text-[28px] font-semibold leading-none text-[var(--text-primary)] tabular-nums">
            {caseRows.length}
          </p>
        </div>
        <div className="bg-[var(--surface-raised)] p-5">
          <p className="text-[12px] text-[var(--text-muted)]">Awaiting decision</p>
          <p className="mt-2 font-mono text-[28px] font-semibold leading-none text-[var(--text-primary)] tabular-nums">
            {awaitingCount}
          </p>
        </div>
        <div className="bg-[var(--surface-raised)] p-5">
          <p className="text-[12px] text-[var(--text-muted)]">Manual review</p>
          <p className="mt-2 font-mono text-[28px] font-semibold leading-none text-amber-600 tabular-nums dark:text-amber-400">
            {reviewCount}
          </p>
        </div>
        <div className="bg-[var(--surface-raised)] p-5">
          <p className="text-[12px] text-[var(--text-muted)]">Auto-approved</p>
          <p className="mt-2 font-mono text-[28px] font-semibold leading-none text-emerald-600 tabular-nums dark:text-emerald-400">
            {approveCount}
          </p>
        </div>
      </div>

      <Surface className="overflow-hidden" id="cases-table-area">
        <div className="flex flex-col gap-3 border-b border-[var(--border-card)] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <SectionHeading icon={ClipboardList} title="Credit Execution Book" />
          <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center">
            <label className="sr-only" htmlFor="case-queue-search">
              Search cases
            </label>
            <div className="relative min-w-0 sm:w-[320px]">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-muted)]" />
              <input
                id="case-queue-search"
                type="search"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search applicant, case, or ID"
                className="h-9 w-full rounded-lg border border-[var(--border-card)] bg-[var(--surface-secondary)]/35 pl-9 pr-3 text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] focus-visible:border-[var(--border-card-hover)]"
              />
            </div>
            <div className="inline-flex w-fit rounded-lg border border-[var(--border-card)] bg-[var(--surface-secondary)]/35 p-1">
              {(["All", "Review", "Attention"] as const).map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setQueueFilter(item)}
                  className={cn(
                    "h-7 cursor-pointer rounded-md px-3 text-[12px] font-semibold transition-colors",
                    queueFilter === item
                      ? "bg-[var(--surface-raised)] text-[var(--text-primary)] shadow-sm"
                      : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]"
                  )}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <div className="min-w-[920px]">
            <div className="grid grid-cols-[1.4fr_0.8fr_0.85fr_0.7fr_0.85fr_0.9fr] border-b border-[var(--border-card)] bg-[var(--surface-secondary)]/35 px-5 py-2.5 text-[11px] font-medium uppercase tracking-[0.06em] text-[var(--text-muted)]">
              <div>Applicant</div>
              <div>Documents</div>
              <div>Evidence</div>
              <div>Risk</div>
              <div>Decision</div>
              <div>Updated</div>
            </div>

            {visibleRows.length === 0 ? (
              <div className="flex flex-col items-center justify-center px-6 py-16">
                <p className="text-[13px] font-medium text-[var(--text-secondary)]">No cases match this filter</p>
                <p className="mt-1 text-[12px] text-[var(--text-tertiary)]">
                  Try clearing the search or selecting a different segment.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-[var(--border-subtle)]">
                {visibleRows.map(({ caseItem, readModel }) => {
                  const documentSummary = getDocumentSummary(readModel);
                  const completenessPercent = getCompletenessPercent(readModel);
                  const completenessDetail = getCompletenessDetail(readModel);
                  const decisionBadge = getDecisionBadge(readModel);
                  const riskCell = getRiskCell(readModel);
                  const lastUpdated = getLastUpdated(caseItem, readModel);
                  const detailHref = `/dashboard/cases/${caseItem.id}`;

                  return (
                    <Link
                      key={caseItem.id}
                      href={detailHref}
                      className="grid w-full grid-cols-[1.4fr_0.8fr_0.85fr_0.7fr_0.85fr_0.9fr] items-center gap-0 px-5 py-4 text-left transition-colors hover:bg-[var(--surface-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/45"
                    >
                      <div className="min-w-0 pr-4">
                        <div className="flex min-w-0 items-center gap-3">
                          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                            <FileText className="h-4 w-4 text-primary" />
                          </div>
                          <div className="min-w-0">
                            <p className="truncate text-[13px] font-semibold text-[var(--text-primary)]">
                              {getApplicantName(caseItem)}
                            </p>
                            <p className="mt-1 truncate font-mono text-[11px] text-[var(--text-muted)]">
                              {caseItem.id.slice(0, 8)} - {formatWorkflowStatus(caseItem.status)}
                            </p>
                          </div>
                        </div>
                      </div>

                      <div className="min-w-0 pr-4">
                        <p className="text-[13px] font-medium text-[var(--text-primary)] tabular-nums">
                          {documentSummary.countLabel === "--" ? "--" : `${documentSummary.countLabel} doc${documentSummary.countLabel === "1" ? "" : "s"}`}
                        </p>
                        <p className="mt-1 truncate text-[11px] text-[var(--text-muted)]">{documentSummary.detail}</p>
                      </div>

                      <div className="pr-5">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono text-[12px] font-semibold text-[var(--text-primary)] tabular-nums">
                            {completenessPercent}%
                          </span>
                        </div>
                        <ProgressBar
                          value={completenessPercent}
                          tone={completenessPercent >= 80 ? "good" : "warning"}
                          className="mt-2 h-1.5"
                        />
                        <p className="mt-1 truncate text-[11px] text-[var(--text-muted)]">{completenessDetail}</p>
                      </div>

                      <div>
                        <StatusBadge label={riskCell.label} tone={riskCell.tone} />
                      </div>

                      <div>
                        <StatusBadge label={decisionBadge.label} tone={decisionBadge.tone} />
                      </div>

                      <div className="flex items-center justify-between gap-3 pr-1">
                        <p className="text-[12px] text-[var(--text-muted)] tabular-nums">{formatDate(lastUpdated)}</p>
                        <ArrowUpRight className="h-3.5 w-3.5 text-[var(--text-faint)]" />
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </Surface>
    </div>
  );
}
