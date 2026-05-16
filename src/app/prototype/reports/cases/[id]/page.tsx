"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  ChevronRight,
  FileText,
  Printer,
} from "lucide-react";

import {
  DataTile,
  PageHeader,
  SectionHeading,
  StatusBadge,
  Surface,
} from "@/components/argentnorth/prototype-ui";

const REPORT_SECTIONS = [
  {
    key: "executive",
    title: "Executive summary",
    paragraphs: [
      "A narrative summary of the decision, supported by score, evidence completeness, and policy posture, will render here once the case is hydrated.",
      "Limitations and follow-up items will be enumerated alongside the recommendation.",
    ],
  },
  {
    key: "evidence",
    title: "Evidence ledger",
    paragraphs: [
      "Documents, AA pulls, and bureau records are listed with provenance, OCR posture, and analyst notes.",
      "Hashes and ingest timestamps anchor the audit trail for SOC2 and FREE-AI reviews.",
    ],
  },
  {
    key: "risk",
    title: "Risk decomposition",
    paragraphs: [
      "Top drivers, contributing factors, and counter-signals are broken out in a waterfall to make the score legible.",
      "Comparable cohorts and historical priors will be referenced for context.",
    ],
  },
  {
    key: "compliance",
    title: "Compliance footnotes",
    paragraphs: [
      "Policy controls evaluated, fairness checks, and reviewer attestation will be footnoted for export.",
    ],
  },
];

export default function PrototypeCaseReportPage() {
  const params = useParams<{ id: string }>();
  const caseId = String(params?.id ?? "");
  const shortId = caseId ? caseId.slice(0, 8) : "—";

  return (
    <div className="flex flex-col gap-8 pb-14">
      <nav
        aria-label="Breadcrumb"
        className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]"
      >
        <Link
          href={`/prototype/cases/${caseId}`}
          className="inline-flex items-center gap-1 transition-colors hover:text-[var(--text-secondary)]"
        >
          <ArrowLeft className="h-3 w-3" strokeWidth={1.5} />
          <span>Case Dossier</span>
        </Link>
        <ChevronRight
          className="h-3 w-3 text-[var(--text-faint)]"
          strokeWidth={1.5}
        />
        <span className="font-mono text-[10px] tracking-[0.14em] text-[var(--text-secondary)]">
          {shortId}
        </span>
      </nav>

      <PageHeader
        eyebrow="Case Report"
        title={`Final report · ${shortId}`}
        description="Print-style memo composed from the latest case-level snapshot. Backend hydration is pending."
      >
        <StatusBadge tone="neutral" label="Wiring in progress" />
        <button
          type="button"
          disabled
          className="inline-flex h-9 cursor-not-allowed items-center gap-1.5 rounded-md border border-[var(--border-card)] bg-[var(--surface-raised)] px-3 text-[13px] font-medium text-[var(--text-tertiary)]"
        >
          <Printer className="h-3.5 w-3.5" strokeWidth={1.5} />
          Print / Save as PDF
        </button>
      </PageHeader>

      <Surface className="overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-[var(--border-card)] bg-[var(--surface-secondary)]/40 px-6 py-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--text-muted)]">
              ArgentNorth Final Report
            </p>
            <h2 className="mt-2 text-[22px] font-semibold tracking-tight text-[var(--text-primary)]">
              Case {shortId}
            </h2>
            <p className="mt-1 text-[12px] text-[var(--text-tertiary)]">
              Generated · — · file CASE-{shortId}.pdf
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone="neutral" label="Draft" />
            <StatusBadge tone="warning" label="Awaiting hydration" />
          </div>
        </div>

        <div className="grid gap-3 border-b border-[var(--border-card)] px-6 py-5 sm:grid-cols-2 xl:grid-cols-4">
          <DataTile label="Risk score" value="—" />
          <DataTile label="Confidence" value="—" />
          <DataTile label="Completeness" value="—" />
          <DataTile label="Recommendation" value="—" />
        </div>

        <div className="space-y-6 px-6 py-6">
          {REPORT_SECTIONS.map((section) => (
            <section key={section.key} className="space-y-3">
              <SectionHeading
                icon={FileText}
                title={section.title}
              />
              <div className="space-y-3 rounded-md border border-[var(--border-card)] bg-[var(--surface-secondary)]/30 px-5 py-4">
                {section.paragraphs.map((paragraph, index) => (
                  <p
                    key={`${section.key}-${index}`}
                    className="text-[13px] leading-relaxed text-[var(--text-tertiary)]"
                  >
                    {paragraph}
                  </p>
                ))}
              </div>
            </section>
          ))}
        </div>

        <div className="flex flex-col gap-2 border-t border-[var(--border-card)] bg-[var(--surface-secondary)]/40 px-6 py-4 text-[11px] text-[var(--text-muted)] sm:flex-row sm:items-center sm:justify-between">
          <span>
            Print sheet placeholder · audit footer renders once decisioning is
            complete.
          </span>
          <span className="font-mono uppercase tracking-[0.14em]">
            CASE-{shortId} · DRAFT
          </span>
        </div>
      </Surface>
    </div>
  );
}
