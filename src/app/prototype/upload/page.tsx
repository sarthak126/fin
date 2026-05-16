"use client";

import {
  FileText,
  Lock,
  ScanLine,
  UploadCloud,
} from "lucide-react";

import {
  DataTile,
  PageHeader,
  SectionHeading,
  StatusBadge,
  Surface,
} from "@/components/argentnorth/prototype-ui";

const SUPPORTED_TYPES = [
  { label: "Bank statement", hint: "PDF · 6+ months" },
  { label: "ITR / Income proof", hint: "PDF · last 2 cycles" },
  { label: "ID / KYC", hint: "PDF or image" },
  { label: "AA consent", hint: "Linked via flow" },
];

export default function PrototypeNewCasePage() {
  return (
    <div className="flex flex-col gap-8 pb-14">
      <PageHeader
        eyebrow="New Case"
        title="Open a new borrower packet."
        description="Drop a document set or invoke the consent flow. Files will be ingested, OCR'd, and stitched into the decision fabric."
      >
        <StatusBadge tone="neutral" label="Wiring in progress" />
      </PageHeader>

      <Surface className="overflow-hidden">
        <div className="border-b border-[var(--border-card)] px-5 py-4">
          <SectionHeading
            icon={UploadCloud}
            title="Evidence intake"
            description="Drop bank statements, ITRs, KYC documents, or AA bundles to seed the case."
          />
        </div>

        <div className="px-5 py-6">
          <div
            aria-disabled="true"
            className="group relative flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-[var(--border-card)] bg-[var(--surface-secondary)]/35 px-6 py-14 text-center transition-colors"
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-md border border-[var(--border-card)] bg-[var(--surface-raised)] text-[var(--primary)]">
              <UploadCloud className="h-5 w-5" strokeWidth={1.5} />
            </div>
            <div className="max-w-md">
              <p className="text-[14px] font-semibold text-[var(--text-primary)]">
                Drag and drop documents here
              </p>
              <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-tertiary)]">
                Or click to browse from your device. PDF, JPEG, and PNG up to
                40 MB each. Files are encrypted at rest and never leave this
                tenant.
              </p>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-2">
              <button
                type="button"
                disabled
                className="inline-flex h-9 cursor-not-allowed items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 text-[13px] font-semibold text-[var(--primary-foreground)] opacity-90"
              >
                <UploadCloud className="h-3.5 w-3.5" strokeWidth={1.5} />
                Select files
              </button>
              <button
                type="button"
                disabled
                className="inline-flex h-9 cursor-not-allowed items-center gap-1.5 rounded-md border border-[var(--border-card)] bg-[var(--surface-raised)] px-3 text-[13px] font-medium text-[var(--text-secondary)]"
              >
                <ScanLine className="h-3.5 w-3.5" strokeWidth={1.5} />
                Start AA consent
              </button>
            </div>

            <span className="absolute right-3 top-3">
              <StatusBadge tone="neutral" label="Wiring in progress" />
            </span>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {SUPPORTED_TYPES.map((type) => (
              <DataTile key={type.label} label={type.label} value={type.hint} />
            ))}
          </div>
        </div>
      </Surface>

      <Surface className="overflow-hidden">
        <div className="border-b border-[var(--border-card)] px-5 py-4">
          <SectionHeading
            icon={FileText}
            title="Case metadata"
            description="Applicant identity, product, and policy authority are captured at intake."
          />
        </div>

        <div className="grid gap-3 px-5 py-5 sm:grid-cols-2 xl:grid-cols-3">
          <DataTile label="Applicant name" value="—" />
          <DataTile label="Applicant email" value="—" />
          <DataTile label="Product" value="—" />
          <DataTile label="Loan amount" value="—" />
          <DataTile label="Policy authority" value="—" />
          <DataTile label="Source channel" value="—" />
        </div>

        <div className="flex items-center gap-2 border-t border-[var(--border-card)] bg-[var(--surface-secondary)]/35 px-5 py-3 text-[11px] text-[var(--text-muted)]">
          <Lock className="h-3 w-3" strokeWidth={1.5} />
          <span>
            All uploads are scoped to your organization. Audit events emit on
            every file ingestion.
          </span>
        </div>
      </Surface>
    </div>
  );
}
