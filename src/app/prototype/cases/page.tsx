"use client";

import Link from "next/link";
import {
  ClipboardList,
  Filter,
  Search,
  Tags,
  UploadCloud,
} from "lucide-react";

import {
  DataTile,
  PageHeader,
  SectionHeading,
  StatusBadge,
  Surface,
} from "@/components/argentnorth/prototype-ui";

export default function PrototypeCaseQueuePage() {
  return (
    <div className="flex flex-col gap-8 pb-14">
      <PageHeader
        eyebrow="Case Queue"
        title="Decision book for active capital movement."
        description="Every row will expose evidence sufficiency, latest risk score, and decision posture. The queue is wiring to the live decision fabric."
      >
        <StatusBadge tone="neutral" label="Wiring in progress" />
        <Link
          href="/prototype/upload"
          className="inline-flex h-9 items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 text-[13px] font-semibold text-[var(--primary-foreground)] transition-colors hover:opacity-90"
        >
          <UploadCloud className="h-3.5 w-3.5" strokeWidth={1.5} />
          New Case
        </Link>
      </PageHeader>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <DataTile label="Active" value="—" />
        <DataTile label="Awaiting decision" value="—" />
        <DataTile label="Manual review" value="—" />
        <DataTile label="Auto-approved" value="—" />
      </div>

      <Surface className="overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-[var(--border-card)] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <SectionHeading
            icon={ClipboardList}
            title="Credit Execution Book"
            description="Cases prioritized by risk, SLA proximity, and evidence completeness."
          />

          <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center">
            <div className="relative min-w-0 sm:w-[280px]">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-muted)]"
                strokeWidth={1.5}
              />
              <input
                disabled
                type="search"
                placeholder="Search applicant, case, or ID"
                className="h-9 w-full rounded-md border border-[var(--border-card)] bg-[var(--surface-secondary)]/40 pl-9 pr-3 text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] focus-visible:border-[var(--border-card-hover)] disabled:cursor-not-allowed"
                aria-label="Search cases"
              />
            </div>
            <button
              type="button"
              disabled
              className="inline-flex h-9 cursor-not-allowed items-center gap-1.5 rounded-md border border-[var(--border-card)] bg-[var(--surface-raised)] px-3 text-[12px] font-semibold text-[var(--text-tertiary)]"
            >
              <Filter className="h-3.5 w-3.5" strokeWidth={1.5} />
              Filters
            </button>
          </div>
        </div>

        <div className="grid grid-cols-[1.4fr_0.8fr_0.85fr_0.7fr_0.85fr_0.9fr] border-b border-[var(--border-card)] bg-[var(--surface-secondary)]/40 px-5 py-2.5 text-[11px] font-medium uppercase tracking-[0.06em] text-[var(--text-muted)]">
          <div>Applicant</div>
          <div>Documents</div>
          <div>Evidence</div>
          <div>Risk</div>
          <div>Decision</div>
          <div>Updated</div>
        </div>

        <div className="flex flex-col items-center justify-center gap-4 px-6 py-20 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-md border border-[var(--border-card)] bg-[var(--surface-secondary)]">
            <Tags
              className="h-4 w-4 text-[var(--text-muted)]"
              strokeWidth={1.5}
            />
          </div>
          <div className="max-w-md">
            <p className="text-[13px] font-semibold text-[var(--text-primary)]">
              Awaiting case ingestion
            </p>
            <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-tertiary)]">
              Use New Case to ingest a borrower packet. Once evidence flows in,
              cases will line up here ranked by risk and SLA proximity.
            </p>
          </div>
          <Link
            href="/prototype/upload"
            className="inline-flex h-8 items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 text-[12px] font-semibold text-[var(--primary-foreground)] transition-colors hover:opacity-90"
          >
            <UploadCloud className="h-3.5 w-3.5" strokeWidth={1.5} />
            New Case
          </Link>
        </div>
      </Surface>
    </div>
  );
}
