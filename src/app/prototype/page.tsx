"use client";

import Link from "next/link";
import {
  Activity,
  ClipboardList,
  Clock,
  ShieldAlert,
  UploadCloud,
} from "lucide-react";

import {
  MetricCard,
  PageHeader,
  SectionHeading,
  StatusBadge,
  Surface,
} from "@/components/argentnorth/prototype-ui";

const PLACEHOLDER_METRICS = [
  { label: "Cases active", icon: ClipboardList },
  { label: "Awaiting decision", icon: Clock },
  { label: "Avg cycle", icon: Activity },
  { label: "Risk flagged", icon: ShieldAlert },
] as const;

export default function PrototypeCommandCenterPage() {
  return (
    <div className="flex flex-col gap-8 pb-14">
      <PageHeader
        eyebrow="Command Center"
        title="Operate the credit decision plane."
        description="A live, governed surface for pipeline, exposure, and reviewer queues. Backend signals are wiring in — interface scaffold is online."
      >
        <StatusBadge tone="neutral" label="Wiring in progress" />
        <Link
          href="/prototype/upload"
          className="inline-flex h-9 items-center gap-1.5 rounded-md border border-[var(--border-card)] bg-[var(--surface-raised)] px-3 text-[13px] font-medium text-[var(--text-primary)] transition-colors hover:border-[var(--border-card-hover)] hover:bg-[var(--surface-hover)]"
        >
          <UploadCloud className="h-3.5 w-3.5" strokeWidth={1.5} />
          New Case
        </Link>
      </PageHeader>

      <section
        aria-label="Pipeline metrics"
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        {PLACEHOLDER_METRICS.map((metric) => (
          <MetricCard
            key={metric.label}
            label={metric.label}
            value="—"
            icon={metric.icon}
            sparkData={[]}
          />
        ))}
      </section>

      <Surface className="overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-[var(--border-card)] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <SectionHeading
            icon={ClipboardList}
            title="Recent cases"
            description="The last decisions, evidence packets, and reviewer transitions across the organization."
          />
          <StatusBadge tone="neutral" label="Wiring in progress" />
        </div>

        <div className="grid grid-cols-[1.4fr_0.8fr_0.8fr_0.7fr_0.8fr] border-b border-[var(--border-card)] bg-[var(--surface-secondary)]/40 px-5 py-2.5 text-[11px] font-medium uppercase tracking-[0.06em] text-[var(--text-muted)]">
          <div>Applicant</div>
          <div>Evidence</div>
          <div>Risk</div>
          <div>Decision</div>
          <div>Updated</div>
        </div>

        <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-md border border-[var(--border-card)] bg-[var(--surface-secondary)]">
            <ClipboardList
              className="h-4 w-4 text-[var(--text-muted)]"
              strokeWidth={1.5}
            />
          </div>
          <div className="max-w-md">
            <p className="text-[13px] font-semibold text-[var(--text-primary)]">
              No recent cases yet
            </p>
            <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-tertiary)]">
              Once decisions and evidence packets flow into this organization,
              they will surface here in reverse chronological order.
            </p>
          </div>
          <Link
            href="/prototype/upload"
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[var(--border-card)] bg-[var(--surface-raised)] px-3 text-[12px] font-semibold text-[var(--text-primary)] transition-colors hover:border-[var(--border-card-hover)] hover:bg-[var(--surface-hover)]"
          >
            <UploadCloud className="h-3.5 w-3.5" strokeWidth={1.5} />
            Start the first case
          </Link>
        </div>
      </Surface>
    </div>
  );
}
