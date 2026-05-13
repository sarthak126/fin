"use client";

import { AlertTriangle, Clock, FileText, Info, Shield } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { demoBankStatementCase } from "@/lib/demo-bank-statement-case";
import { formatConfidencePercent, normalizeConfidence } from "@/lib/confidence";

function getDecisionAppearance(status: string) {
  if (status === "insufficient_history") {
    return {
      badgeClass: "border-sky-500/30 bg-sky-500/15 text-sky-500",
      cardClass: "border-sky-500/20",
      iconClass: "bg-sky-500/12 text-sky-500",
      icon: Clock,
    };
  }

  return {
    badgeClass: "border-amber-500/30 bg-amber-500/15 text-amber-500",
    cardClass: "border-amber-500/20",
    iconClass: "bg-amber-500/12 text-amber-500",
    icon: AlertTriangle,
  };
}

function formatDecisionTitle(status: string) {
  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatDecisionBadge(status: string) {
  return status.replace(/_/g, " ").toUpperCase();
}

export default function DemoBankStatementDetailPage() {
  const decisionAppearance = getDecisionAppearance(demoBankStatementCase.decision.decision_status);
  const DecisionIcon = decisionAppearance.icon;
  const confidenceValues = [
    {
      label: "Extraction confidence",
      rawValue: demoBankStatementCase.decision.extraction_confidence,
    },
    {
      label: "Risk confidence",
      rawValue: demoBankStatementCase.decision.risk_confidence,
    },
    {
      label: "Data completeness",
      rawValue: demoBankStatementCase.decision.data_completeness,
    },
  ];

  return (
    <main className="min-h-screen bg-[var(--background)] px-6 py-10 text-[var(--text-primary)]">
      <div className="mx-auto flex max-w-[1100px] flex-col gap-6">
        <div className="rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] px-5 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
            Regression Demo
          </p>
          <h1 className="mt-1 text-[24px] font-bold tracking-tight">
            Bank Statement Detail Regression Fixture
          </h1>
          <p className="mt-2 text-[14px] text-[var(--text-secondary)]">
            This public demo route mirrors the short-history sample used in regression tests.
          </p>
        </div>

        <section
          data-testid="final-decision-block"
          data-decision-status={demoBankStatementCase.decision.decision_status}
          className={`overflow-hidden rounded-2xl border px-6 py-6 ${decisionAppearance.cardClass} bg-[var(--surface-glass)]`}
        >
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex-1 space-y-4">
              <div className="flex items-start gap-4">
                <div className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl ${decisionAppearance.iconClass}`}>
                  <DecisionIcon className="h-7 w-7" />
                </div>
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
                    Final decision
                  </p>
                  <h2 className="mt-1 text-[28px] font-bold tracking-tight">
                    {formatDecisionTitle(demoBankStatementCase.decision.decision_status)}
                  </h2>
                  <Badge
                    data-testid="decision-badge"
                    className={`mt-3 border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${decisionAppearance.badgeClass}`}
                  >
                    {formatDecisionBadge(demoBankStatementCase.decision.decision_status)}
                  </Badge>
                </div>
              </div>

              <p data-testid="primary-reasoning" className="max-w-3xl text-[14px] leading-relaxed text-[var(--text-secondary)]">
                {demoBankStatementCase.decision.decision_reason}
              </p>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                {[
                  { label: "Statement type", value: demoBankStatementCase.documentType.replace(/_/g, " ") },
                  { label: "Statement quality", value: demoBankStatementCase.statementQuality },
                  { label: "Coverage", value: `${demoBankStatementCase.coverageDays} days` },
                ].map((item) => (
                  <div key={item.label} className="rounded-xl border border-[var(--border-card)] bg-[var(--surface-glass)] px-4 py-3">
                    <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">{item.label}</p>
                    <p className="mt-1 text-[14px] font-semibold">{item.value}</p>
                  </div>
                ))}
              </div>

              <div
                data-testid="recommendation-copy"
                className="rounded-xl border border-[var(--border-card)] bg-[var(--surface-glass)] px-4 py-4"
              >
                <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                  Recommendation
                </p>
                <p className="mt-1 text-[14px] font-medium">
                  {demoBankStatementCase.decision.decision_recommendation}
                </p>
              </div>

              <div className="rounded-xl border border-[var(--border-card)] bg-[var(--surface-glass)] px-4 py-4">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                  Required follow-ups
                </p>
                <div className="mt-2 space-y-2">
                  {demoBankStatementCase.decision.required_followups.map((followup) => (
                    <div key={followup} className="flex items-start gap-2 text-[13px] text-[var(--text-secondary)]">
                      <span className="mt-0.5 text-[var(--text-muted)]">-</span>
                      <span>{followup}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div
              data-testid="confidence-layer"
              className="w-full max-w-xl shrink-0 rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] p-5"
            >
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-[var(--text-muted)]" />
                <h3 className="text-[12px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
                  Data confidence layer
                </h3>
              </div>

              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                {confidenceValues.map((item) => (
                  <div key={item.label} className="rounded-xl bg-[var(--surface-secondary)] px-4 py-3">
                    <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">{item.label}</p>
                    <p data-testid="confidence-value" className="mt-1 text-[18px] font-bold">
                      {formatConfidencePercent(item.rawValue)}
                    </p>
                  </div>
                ))}
              </div>

              <div className="mt-4 rounded-xl border border-[var(--border-card)] bg-[var(--surface-secondary)] px-4 py-3">
                <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                  Explanation
                </p>
                <p className="mt-1 text-[13px] text-[var(--text-secondary)]">
                  {normalizeConfidence(demoBankStatementCase.decision.risk_confidence)! < 0.5
                    ? "Low confidence due to short history."
                    : "Confidence is supported by the extracted statement signals."}
                </p>
              </div>
            </div>
          </div>
        </section>

        <section
          data-testid="analysis-limitations"
          className="rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] px-5 py-4"
        >
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-[var(--text-muted)]" />
            <h3 className="text-[12px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
              Analysis limitations
            </h3>
          </div>

          <div className="mt-3 space-y-2">
            {demoBankStatementCase.decision.analysis_limitations.map((limitation) => (
              <div key={limitation} className="flex items-start gap-2 text-[13px] text-[var(--text-secondary)]">
                <span className="mt-0.5 text-[var(--text-muted)]">-</span>
                <span>{limitation}</span>
              </div>
            ))}
          </div>
        </section>

        <section
          data-testid="statement-summary"
          className="rounded-2xl border border-[var(--border-card)] bg-[var(--surface-glass)] px-5 py-5"
        >
          <div className="flex items-center gap-2 mb-4">
            <FileText className="h-4 w-4 text-[var(--text-muted)]" />
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
              Statement summary
            </h3>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {demoBankStatementCase.statementSummary.map((item) => (
              <div key={item.label} className="rounded-xl border border-[var(--border-card)] bg-[var(--surface-glass)] px-4 py-3">
                <p className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">{item.label}</p>
                <p className="mt-1 text-[15px] font-semibold">{item.value}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
