"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  ChevronRight,
  FileText,
  Gauge,
  Network,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import {
  DataTile,
  PageHeader,
  SectionHeading,
  StatusBadge,
  Surface,
} from "@/components/argentnorth/prototype-ui";

type EvidencePanel = {
  key: string;
  title: string;
  description: string;
  icon: LucideIcon;
  rows: { label: string; value: string }[];
};

const EVIDENCE_PANELS: EvidencePanel[] = [
  {
    key: "applicant",
    title: "Applicant Intake",
    description: "Identity, consent, and KYC posture from the borrower packet.",
    icon: FileText,
    rows: [
      { label: "Applicant", value: "—" },
      { label: "Workflow", value: "—" },
      { label: "Consent", value: "—" },
      { label: "KYC", value: "—" },
    ],
  },
  {
    key: "evidence",
    title: "Evidence Coverage",
    description: "Document completeness, OCR posture, and AA pulls.",
    icon: Network,
    rows: [
      { label: "Documents", value: "—" },
      { label: "Completeness", value: "—" },
      { label: "Pending requirements", value: "—" },
      { label: "Bureau", value: "—" },
    ],
  },
  {
    key: "risk",
    title: "Risk Posture",
    description: "Score, decision band, and policy violations.",
    icon: Gauge,
    rows: [
      { label: "Risk score", value: "—" },
      { label: "Risk band", value: "—" },
      { label: "Decision", value: "—" },
      { label: "Confidence", value: "—" },
    ],
  },
  {
    key: "compliance",
    title: "Compliance & Audit",
    description: "Policy controls, fairness checks, and event trail.",
    icon: ShieldCheck,
    rows: [
      { label: "Policy controls", value: "—" },
      { label: "Fairness", value: "—" },
      { label: "Audit events", value: "—" },
      { label: "Last action", value: "—" },
    ],
  },
];

export default function PrototypeCaseDossierPage() {
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
          href="/prototype/cases"
          className="inline-flex items-center gap-1 transition-colors hover:text-[var(--text-secondary)]"
        >
          <ArrowLeft className="h-3 w-3" strokeWidth={1.5} />
          <span>Case Queue</span>
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
        eyebrow="Case Dossier"
        title={`Case ${shortId}`}
        description="A single review object stitched from intake, evidence, scoring, policy, and audit signals. Backend hydration is pending."
      >
        <StatusBadge tone="neutral" label="Wiring in progress" />
        <Link
          href={`/prototype/reports/cases/${caseId}`}
          className="inline-flex h-9 items-center gap-1.5 rounded-md border border-[var(--border-card)] bg-[var(--surface-raised)] px-3 text-[13px] font-medium text-[var(--text-primary)] transition-colors hover:border-[var(--border-card-hover)] hover:bg-[var(--surface-hover)]"
        >
          <FileText className="h-3.5 w-3.5" strokeWidth={1.5} />
          Open Report
        </Link>
      </PageHeader>

      <Surface
        className="relative overflow-hidden p-6"
        style={{
          background:
            "radial-gradient(800px 220px at 0% 0%, color-mix(in srgb, var(--primary) 10%, transparent) 0%, transparent 60%), var(--surface-raised)",
        }}
      >
        <div className="grid gap-6 lg:grid-cols-[1fr_auto]">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-card)] bg-[var(--surface-secondary)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-secondary)]">
                <Sparkles
                  className="h-3 w-3 text-[var(--primary)]"
                  strokeWidth={1.5}
                />
                Decision summary
              </span>
              <StatusBadge tone="warning" label="Awaiting evidence" />
            </div>
            <h2 className="mt-3 max-w-2xl text-[20px] font-semibold tracking-tight text-[var(--text-primary)]">
              Decision narrative will appear here once the evidence packet is
              hydrated.
            </h2>
            <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-[var(--text-tertiary)]">
              Risk score, contributing drivers, policy violations, and reviewer
              actions will compose into a single explainable memo. This shell is
              a layout placeholder.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 lg:w-[280px]">
            <DataTile label="Risk score" value="—" />
            <DataTile label="Confidence" value="—" />
            <DataTile label="Completeness" value="—" />
            <DataTile label="Decision" value="—" />
          </div>
        </div>
      </Surface>

      <div className="grid gap-4 xl:grid-cols-2">
        {EVIDENCE_PANELS.map((panel) => {
          const Icon = panel.icon;
          return (
            <Surface key={panel.key} className="overflow-hidden">
              <div className="border-b border-[var(--border-card)] px-5 py-4">
                <SectionHeading
                  icon={Icon}
                  title={panel.title}
                  description={panel.description}
                />
              </div>
              <div className="divide-y divide-[var(--border-subtle)] px-5">
                {panel.rows.map((row) => (
                  <div
                    key={`${panel.key}-${row.label}`}
                    className="flex items-center justify-between gap-4 py-3"
                  >
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                      {row.label}
                    </p>
                    <p className="font-mono text-[13px] font-semibold text-[var(--text-secondary)] tabular-nums">
                      {row.value}
                    </p>
                  </div>
                ))}
              </div>
            </Surface>
          );
        })}
      </div>
    </div>
  );
}
