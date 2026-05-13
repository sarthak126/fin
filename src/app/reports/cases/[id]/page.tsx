"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  FileText,
  Loader2,
  Printer,
  ShieldAlert,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  getCaseReport,
  type CaseDocumentReadModel,
  type CaseReportMetric,
  type CaseReportPayload,
  type CaseReportPrintSection,
} from "@/lib/api";
import { getApiToken } from "@/lib/auth";
import { normalizeConfidence } from "@/lib/confidence";

type LoadState = "loading" | "ready" | "error";
type Tone = "good" | "warning" | "danger" | "neutral";

const METRIC_TONE_CLASSES: Record<Tone, string> = {
  good: "border-emerald-200 bg-emerald-50 text-emerald-950",
  warning: "border-amber-200 bg-amber-50 text-amber-950",
  danger: "border-red-200 bg-red-50 text-red-950",
  neutral: "border-slate-200 bg-slate-50 text-slate-950",
};

const BADGE_TONE_CLASSES: Record<Tone, string> = {
  good: "bg-emerald-100 text-emerald-900 border-emerald-200",
  warning: "bg-amber-100 text-amber-900 border-amber-200",
  danger: "bg-red-100 text-red-900 border-red-200",
  neutral: "bg-slate-100 text-slate-700 border-slate-200",
};

function formatLabel(value: string | null | undefined) {
  const text = String(value || "").trim();
  if (!text) return "Unavailable";

  return text
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatDateTime(value: string | Date | null | undefined) {
  if (!value) return "--";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return formatDateOnly(value);
  }

  const parsed = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(parsed.getTime())) return "--";

  return parsed.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDateOnly(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;
  const [, year, month, day] = match;
  return new Date(Number(year), Number(month) - 1, Number(day)).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatPercent(value: number | string | null | undefined) {
  const normalized = normalizeConfidence(value);
  if (normalized === null) return "--";
  return `${Math.round(normalized * 100)}%`;
}

function formatFileSize(bytes: number | null | undefined) {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return "--";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function clampRiskScore(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function getTone(value: string | null | undefined): Tone {
  if (value === "good" || value === "warning" || value === "danger" || value === "neutral") {
    return value;
  }
  return "neutral";
}

function getDocumentTone(status: string | null | undefined): Tone {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "analyzed") return "good";
  if (normalized === "failed") return "danger";
  if (normalized === "processing" || normalized === "pending") return "warning";
  return "neutral";
}

function MetricCard({ metric }: { metric: CaseReportMetric }) {
  const tone = getTone(metric.tone);

  return (
    <div className={`rounded-2xl border px-4 py-3 ${METRIC_TONE_CLASSES[tone]}`}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] opacity-70">{metric.label}</p>
      <p className="mt-2 text-[20px] font-semibold tracking-tight">{metric.display_value}</p>
      {metric.hint ? <p className="mt-2 text-[12px] leading-relaxed opacity-75">{metric.hint}</p> : null}
    </div>
  );
}

function DocumentRow({ document }: { document: CaseDocumentReadModel }) {
  const decision = document.latest_analysis?.decision_status;
  const riskScore = clampRiskScore(document.latest_analysis?.risk_score);
  const tone = getDocumentTone(document.status);

  return (
    <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 sm:grid-cols-[1.8fr_1fr_1fr_1fr] print-avoid-break">
      <div>
        <p className="text-[13px] font-semibold text-slate-950">{document.original_filename}</p>
        <p className="mt-1 text-[12px] text-slate-600">
          {formatLabel(document.document_type)} · {formatFileSize(document.file_size_bytes)}
        </p>
      </div>

      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Status</p>
        <Badge variant="secondary" className={`mt-2 border ${BADGE_TONE_CLASSES[tone]}`}>
          {formatLabel(document.status)}
        </Badge>
      </div>

      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Decision</p>
        <p className="mt-2 text-[13px] font-medium text-slate-900">{formatLabel(decision)}</p>
      </div>

      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Risk</p>
        <p className="mt-2 text-[13px] font-medium text-slate-900">{riskScore ?? "--"}</p>
        <p className="mt-1 text-[11px] text-slate-500">
          Updated {formatDateTime(document.latest_analysis?.created_at || document.updated_at)}
        </p>
      </div>
    </div>
  );
}

function PrintSectionBlock({ section }: { section: CaseReportPrintSection }) {
  return (
    <section className="print-avoid-break rounded-[28px] border border-slate-200 bg-white px-6 py-6 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-slate-950 text-white">
          <FileText className="h-4 w-4" />
        </div>
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Report Section</p>
          <h2 className="mt-1 text-[20px] font-semibold tracking-tight text-slate-950">{section.title}</h2>
        </div>
      </div>

      <div className="mt-5 space-y-4">
        {section.paragraphs.map((paragraph, index) => (
          <p key={`${section.key}-paragraph-${index}`} className="text-[13px] leading-7 text-slate-700">
            {paragraph}
          </p>
        ))}

        {section.bullets.length > 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Key points</p>
            <ul className="mt-3 space-y-2">
              {section.bullets.map((bullet, index) => (
                <li key={`${section.key}-bullet-${index}`} className="flex items-start gap-3 text-[13px] leading-6 text-slate-700">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}

export default function CaseReportPrintPage() {
  const params = useParams();
  const caseId = String(params.id);
  const { getToken } = useAuth();

  const [status, setStatus] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [report, setReport] = useState<CaseReportPayload | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadReport() {
      try {
        setStatus("loading");
        setError("");

        const token = await getApiToken(getToken);
        const nextReport = await getCaseReport(caseId, token);

        if (cancelled) return;

        setReport(nextReport);
        setStatus("ready");
      } catch (err) {
        if (cancelled) return;

        setError(err instanceof Error ? err.message : "Failed to load report.");
        setStatus("error");
      }
    }

    void loadReport();

    return () => {
      cancelled = true;
    };
  }, [caseId, getToken]);

  useEffect(() => {
    if (!report) return;

    const previousTitle = document.title;
    document.title = report.header.print_filename;

    return () => {
      document.title = previousTitle;
    };
  }, [report]);

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="print-page min-h-screen bg-[#edf1f5] text-slate-950">
      <div className="print-toolbar sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Print View</p>
            <p className="mt-1 text-[13px] text-slate-700">Optimized for browser print and Save as PDF.</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button asChild variant="outline" className="gap-2 border-slate-200 bg-white text-slate-900 hover:bg-slate-50">
              <Link href={`/dashboard/cases/${caseId}`}>
                <ArrowLeft className="h-4 w-4" />
                Back to Case
              </Link>
            </Button>
            <Button className="gap-2 bg-slate-950 text-white hover:bg-slate-800" onClick={handlePrint}>
              <Printer className="h-4 w-4" />
              Print / Save as PDF
            </Button>
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
        {status === "loading" ? (
          <div className="print-sheet flex min-h-[60vh] items-center justify-center rounded-[32px] border border-slate-200 bg-white px-6 py-10 shadow-xl">
            <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
              <Loader2 className="h-4 w-4 animate-spin" />
              Preparing the print-friendly report...
            </div>
          </div>
        ) : null}

        {status === "error" ? (
          <div className="print-sheet rounded-[32px] border border-red-200 bg-white px-6 py-10 shadow-xl">
            <div className="mx-auto max-w-xl rounded-3xl border border-red-200 bg-red-50 px-5 py-5">
              <div className="flex items-start gap-3">
                <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
                <div>
                  <p className="text-[16px] font-semibold text-red-950">Report unavailable</p>
                  <p className="mt-2 text-[13px] leading-6 text-red-900">{error || "We could not load this report."}</p>
                  <div className="mt-4">
                    <Button asChild variant="outline" className="gap-2 border-red-200 bg-white text-red-950 hover:bg-red-50">
                      <Link href={`/dashboard/cases/${caseId}`}>
                        <ArrowLeft className="h-4 w-4" />
                        Return to Case
                      </Link>
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {status === "ready" && report ? (
          <article className="print-sheet rounded-[32px] border border-slate-200 bg-white px-6 py-8 shadow-xl sm:px-10 sm:py-10">
            <header className="border-b border-slate-200 pb-8">
              <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                <div className="max-w-3xl">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                    LoanLens Final Report
                  </p>
                  <h1 className="mt-3 text-[34px] font-semibold tracking-tight text-slate-950">
                    {report.header.title}
                  </h1>
                  {report.header.subtitle ? (
                    <p className="mt-3 text-[15px] leading-7 text-slate-600">{report.header.subtitle}</p>
                  ) : null}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary" className={`border ${BADGE_TONE_CLASSES[report.header.is_final ? "good" : "warning"]}`}>
                    {formatLabel(report.header.report_status)}
                  </Badge>
                  <Badge variant="secondary" className={`border ${BADGE_TONE_CLASSES["neutral"]}`}>
                    {formatLabel(report.header.generated_from)}
                  </Badge>
                </div>
              </div>

              <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Case ID</p>
                  <p className="mt-2 text-[15px] font-medium text-slate-950">{report.case.id}</p>
                </div>
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Generated</p>
                  <p className="mt-2 text-[15px] font-medium text-slate-950">{formatDateTime(report.header.generated_at)}</p>
                </div>
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Export file</p>
                  <p className="mt-2 text-[15px] font-medium text-slate-950">{report.header.print_filename}</p>
                </div>
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Applicant</p>
                  <p className="mt-2 text-[15px] font-medium text-slate-950">
                    {report.case.applicant_name || report.case.name || `Case ${report.case.id.slice(0, 8)}`}
                  </p>
                </div>
              </div>
            </header>

            <section className="mt-8 print-avoid-break rounded-[28px] border border-slate-200 bg-slate-50 px-6 py-6">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="max-w-3xl">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Executive Summary</p>
                  <h2 className="mt-2 text-[26px] font-semibold tracking-tight text-slate-950">
                    {formatLabel(report.overview.decision_status)}
                  </h2>
                  <p className="mt-3 text-[14px] leading-7 text-slate-700">{report.overview.summary}</p>
                  {report.overview.decision_reason ? (
                    <p className="mt-3 text-[13px] leading-6 text-slate-600">{report.overview.decision_reason}</p>
                  ) : null}
                </div>

                <div className="grid gap-3 sm:grid-cols-2 lg:w-[320px]">
                  <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Risk score</p>
                    <p className="mt-2 text-[24px] font-semibold tracking-tight text-slate-950">
                      {clampRiskScore(report.overview.risk_score) ?? "--"}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Confidence</p>
                    <p className="mt-2 text-[24px] font-semibold tracking-tight text-slate-950">
                      {formatPercent(report.overview.confidence)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Completeness</p>
                    <p className="mt-2 text-[24px] font-semibold tracking-tight text-slate-950">
                      {formatPercent(report.overview.data_completeness)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Recommendation</p>
                    <p className="mt-2 text-[16px] font-semibold tracking-tight text-slate-950">
                      {formatLabel(report.overview.recommendation)}
                    </p>
                  </div>
                </div>
              </div>
            </section>

            <section className="mt-8">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {report.metrics.map((metric) => (
                  <MetricCard key={metric.key} metric={metric} />
                ))}
              </div>
            </section>

            <section className="mt-8 grid gap-5 lg:grid-cols-[1.1fr,0.9fr]">
              <div className="print-avoid-break rounded-[28px] border border-slate-200 bg-white px-6 py-6 shadow-sm">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Applicant Intake</p>
                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Applicant name</p>
                    <p className="mt-2 text-[15px] font-medium text-slate-950">{report.case.applicant_name || "--"}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Workflow status</p>
                    <p className="mt-2 text-[15px] font-medium text-slate-950">{formatLabel(report.case.status)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Email</p>
                    <p className="mt-2 text-[15px] font-medium text-slate-950">{report.case.applicant_email || "--"}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Phone</p>
                    <p className="mt-2 text-[15px] font-medium text-slate-950">{report.case.applicant_phone || "--"}</p>
                  </div>
                </div>
              </div>

              <div className="print-avoid-break rounded-[28px] border border-slate-200 bg-white px-6 py-6 shadow-sm">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Coverage Snapshot</p>
                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Analyzed documents</p>
                    <p className="mt-2 text-[24px] font-semibold tracking-tight text-slate-950">{report.overview.analyzed_document_count}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Pending documents</p>
                    <p className="mt-2 text-[24px] font-semibold tracking-tight text-slate-950">{report.overview.pending_document_count}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Fraud signals</p>
                    <p className="mt-2 text-[24px] font-semibold tracking-tight text-slate-950">{report.overview.fraud_signal_count}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Blockers</p>
                    <p className="mt-2 text-[24px] font-semibold tracking-tight text-slate-950">{report.overview.blocker_count}</p>
                  </div>
                </div>
              </div>
            </section>

            <section className="mt-8">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Documents</p>
                  <h2 className="mt-1 text-[22px] font-semibold tracking-tight text-slate-950">Evidence Included</h2>
                </div>
                <p className="text-[12px] text-slate-500">{report.documents.length} document(s)</p>
              </div>

              <div className="mt-5 space-y-3">
                {report.documents.map((document) => (
                  <DocumentRow key={document.id} document={document} />
                ))}
              </div>
            </section>

            <section className="mt-8 space-y-5">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Printable Narrative</p>
                <h2 className="mt-1 text-[22px] font-semibold tracking-tight text-slate-950">Report Sections</h2>
              </div>

              {report.print.sections.map((section) => (
                <PrintSectionBlock key={section.key} section={section} />
              ))}
            </section>

            <footer className="mt-8 rounded-[28px] border border-slate-200 bg-slate-950 px-6 py-5 text-white">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="max-w-3xl">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-300">Audit Note</p>
                  <p className="mt-2 text-[13px] leading-6 text-slate-100">{report.print.footer_note}</p>
                </div>
                <div className="grid gap-2 text-[12px] text-slate-300">
                  <span>Model {report.latest_analysis.model_used || "--"}</span>
                  <span>Generated {formatDateTime(report.print.generated_at)}</span>
                  <span>File {report.print.filename}</span>
                </div>
              </div>
            </footer>
          </article>
        ) : null}
      </main>
    </div>
  );
}
