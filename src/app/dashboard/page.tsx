"use client";

import type { ElementType } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  BarChart3,
  BrainCircuit,
  Boxes,
  Command,
  DatabaseZap,
  GitBranch,
  Landmark,
  Network,
  RadioTower,
  Sparkles,
  UploadCloud,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DecisionBadge,
  HealthDot,
  InlineLinkLabel,
  PageHeader,
  ProgressBar,
  SectionHeading,
  StatusBadge,
  Surface,
  TimelineRow,
  toneClass,
} from "@/components/argentnorth/prototype-ui";
import {
  auditEvents,
  evidenceGraph,
  eventStream,
  northstarBrief,
  northstarRecommendations,
  operatingMetrics,
  policyControls,
  prototypeCases,
  type RiskTone,
} from "@/lib/argentnorth-prototype";

/* System intelligence - fleet-level view */

const decisionStages = [
  {
    label: "Ingested",
    value: 47,
    detail: "AA consent and document packets",
    progress: 100,
    tone: "neutral" as RiskTone,
  },
  {
    label: "Scored",
    value: 47,
    detail: "credit-gbm-4.8 - avg 388ms",
    progress: 100,
    tone: "neutral" as RiskTone,
  },
  {
    label: "Completed",
    value: 35,
    detail: "12 awaiting reviewer action",
    progress: 74,
    tone: "good" as RiskTone,
  },
  {
    label: "In review",
    value: 12,
    detail: "manual policy band",
    progress: 26,
    tone: "warning" as RiskTone,
  },
];

const decisionOutcomes = [
  {
    label: "Approved",
    count: 31,
    pct: 66,
    color: "bg-emerald-500",
    text: "text-emerald-600 dark:text-emerald-400",
  },
  {
    label: "In review",
    count: 12,
    pct: 26,
    color: "bg-amber-500",
    text: "text-amber-600 dark:text-amber-400",
  },
  {
    label: "Rejected",
    count: 4,
    pct: 8,
    color: "bg-red-500",
    text: "text-red-600 dark:text-red-400",
  },
];

const riskBands = [
  {
    label: "Low risk",
    pct: 62,
    count: 29,
    color: "bg-emerald-500",
    text: "text-emerald-600 dark:text-emerald-400",
  },
  {
    label: "Medium risk",
    pct: 27,
    count: 13,
    color: "bg-amber-500",
    text: "text-amber-600 dark:text-amber-400",
  },
  {
    label: "High risk",
    pct: 11,
    count: 5,
    color: "bg-red-500",
    text: "text-red-600 dark:text-red-400",
  },
];

const modelStats = [
  { label: "AUC", value: "0.84", tone: "neutral" as RiskTone },
  { label: "KS stat", value: "0.61", tone: "neutral" as RiskTone },
  { label: "Version", value: "credit-gbm-4.8", tone: "neutral" as RiskTone },
  { label: "Drift", value: "PSI 0.21", tone: "warning" as RiskTone },
];

const infraSignals = [
  { label: "AA ingestion", value: "18.4k events", status: "Healthy", tone: "good" as RiskTone },
  { label: "Core banking", value: "184ms p50", status: "Healthy", tone: "good" as RiskTone },
  { label: "Bureau gateway", value: "1.8s p95", status: "Degraded", tone: "warning" as RiskTone },
  { label: "Model inference", value: "388ms p95", status: "Healthy", tone: "good" as RiskTone },
  { label: "Drift monitor", value: "PSI 0.21", status: "Watch", tone: "warning" as RiskTone },
];

function IntelligenceHeader({
  icon: Icon,
  eyebrow,
  title,
  iconClassName,
}: {
  icon: ElementType;
  eyebrow: string;
  title: string;
  iconClassName: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${iconClassName}`}>
        <Icon className="h-[17px] w-[17px]" />
      </div>
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
          {eyebrow}
        </p>
        <h3 className="mt-0.5 truncate text-[15px] font-semibold text-[var(--text-primary)]">{title}</h3>
      </div>
    </div>
  );
}

function SystemIntelligencePanel() {
  const healthyCount = infraSignals.filter((item) => item.tone === "good").length;
  const lowRiskEnd = riskBands[0].pct * 3.6;
  const mediumRiskEnd = (riskBands[0].pct + riskBands[1].pct) * 3.6;

  return (
    <div className="grid items-start gap-4 xl:grid-cols-[1.25fr_0.86fr_1fr]">
      <Surface className="p-5 md:p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <IntelligenceHeader
            icon={Activity}
            eyebrow="Pipeline"
            title="Decision flow"
            iconClassName="border-primary/15 bg-primary/10 text-primary"
          />
          <div className="flex items-center gap-2 text-[12px] font-medium text-[var(--text-tertiary)]">
            <Zap className="h-3.5 w-3.5 text-primary" />
            <span>2m 18s avg decision</span>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-5">
          {decisionStages.map((stage) => {
            const style = toneClass(stage.tone);

            return (
              <div key={stage.label} className="min-w-0">
                <p className="font-mono text-[24px] font-semibold leading-none tracking-tight text-[var(--text-primary)] tabular-nums">
                  {stage.value}
                </p>
                <div className="mt-2 flex items-center gap-2">
                  <span className={`h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
                  <p className="text-[12px] font-semibold text-[var(--text-secondary)]">{stage.label}</p>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-5 space-y-3">
          {decisionStages.map((stage) => (
            <div key={stage.label} className="grid gap-2 sm:grid-cols-[124px_1fr] sm:items-center">
              <div className="min-w-0">
                <p className="text-[12px] font-semibold text-[var(--text-primary)]">{stage.label}</p>
                <p className="mt-0.5 truncate text-[11px] text-[var(--text-tertiary)]">{stage.detail}</p>
              </div>
              <ProgressBar value={stage.progress} tone={stage.tone} className="h-1.5" />
            </div>
          ))}
        </div>

        <div className="mt-5 border-t border-[var(--border-card)] pt-4">
          <div className="flex h-2 overflow-hidden rounded-full bg-[var(--surface-secondary)]">
            {decisionOutcomes.map((outcome) => (
              <div key={outcome.label} className={outcome.color} style={{ width: `${outcome.pct}%` }} />
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
            {decisionOutcomes.map((outcome) => (
              <div key={outcome.label} className="flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${outcome.color}`} />
                <span className="text-[12px] text-[var(--text-tertiary)]">{outcome.label}</span>
                <span className={`font-mono text-[12px] font-semibold tabular-nums ${outcome.text}`}>
                  {outcome.count}
                </span>
              </div>
            ))}
          </div>
        </div>
      </Surface>

      <Surface className="p-5 md:p-6">
        <IntelligenceHeader
          icon={BarChart3}
          eyebrow="Risk posture"
          title="Score mix"
          iconClassName="border-amber-500/20 bg-amber-500/10 text-amber-500"
        />

        <div className="mt-6 flex flex-col gap-5 sm:flex-row sm:items-center">
          <div
            className="grid h-32 w-32 shrink-0 place-items-center rounded-full"
            style={{
              background: `conic-gradient(#10b981 0deg ${lowRiskEnd}deg, #f59e0b ${lowRiskEnd}deg ${mediumRiskEnd}deg, #ef4444 ${mediumRiskEnd}deg 360deg)`,
            }}
          >
            <div className="grid h-[72%] w-[72%] place-items-center rounded-full bg-[var(--surface-raised)] text-center">
              <div>
                <p className="font-mono text-[23px] font-semibold leading-none text-[var(--text-primary)] tabular-nums">
                  47
                </p>
                <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-tertiary)]">
                  cases
                </p>
              </div>
            </div>
          </div>

          <div className="min-w-0 flex-1 space-y-3">
            {riskBands.map((band) => (
              <div key={band.label} className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${band.color}`} />
                  <span className="truncate text-[12px] font-medium text-[var(--text-secondary)]">{band.label}</span>
                </div>
                <div className="text-right">
                  <p className={`text-[14px] font-semibold leading-none tabular-nums ${band.text}`}>{band.pct}%</p>
                  <p className="mt-1 font-mono text-[11px] text-[var(--text-tertiary)]">{band.count}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 border-t border-[var(--border-card)] pt-5">
          <div className="flex items-center gap-2">
            <BrainCircuit className="h-4 w-4 text-primary" />
            <p className="text-[13px] font-semibold text-[var(--text-primary)]">Model performance</p>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
            {modelStats.map((stat) => {
              const style = toneClass(stat.tone);

              return (
                <div key={stat.label} className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-tertiary)]">
                    {stat.label}
                  </p>
                  <p
                    className={`mt-1 truncate text-[14px] font-semibold ${
                      stat.tone === "neutral" ? "text-[var(--text-primary)]" : style.text
                    }`}
                  >
                    {stat.value}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </Surface>

      <Surface className="p-5 md:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <IntelligenceHeader
            icon={RadioTower}
            eyebrow="Infrastructure"
            title="System health"
            iconClassName="border-primary/15 bg-primary/10 text-primary"
          />
          <div className="text-left sm:text-right">
            <p className="font-mono text-[21px] font-semibold leading-none text-[var(--text-primary)] tabular-nums">
              {healthyCount}/{infraSignals.length}
            </p>
            <p className="mt-1 text-[11px] font-medium text-[var(--text-tertiary)]">healthy services</p>
          </div>
        </div>

        <div className="mt-5 divide-y divide-[var(--border-subtle)]">
          {infraSignals.map((item) => {
            const style = toneClass(item.tone);

            return (
              <div key={item.label} className="flex items-center justify-between gap-3 py-3 first:pt-0">
                <div className="flex min-w-0 items-center gap-2.5">
                  <HealthDot tone={item.tone} />
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-semibold text-[var(--text-primary)]">{item.label}</p>
                    <p className={`mt-0.5 text-[12px] ${style.text}`}>{item.status}</p>
                  </div>
                </div>
                <p className="shrink-0 font-mono text-[12px] font-semibold text-[var(--text-secondary)]">{item.value}</p>
              </div>
            );
          })}
        </div>

        <div className="mt-4 border-t border-[var(--border-card)] pt-4">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-primary" />
            <p className="text-[13px] font-semibold text-[var(--text-primary)]">Recent audit events</p>
          </div>
          <div className="mt-3 space-y-3">
            {auditEvents.slice(0, 2).map((event) => {
              const style = toneClass(event.tone);

              return (
                <div key={`${event.actor}-${event.time}`} className="flex gap-2.5">
                  <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
                  <div className="min-w-0">
                    <p className="truncate text-[12px] font-semibold text-[var(--text-primary)]">{event.action}</p>
                    <p className="mt-0.5 truncate text-[12px] text-[var(--text-tertiary)]">
                      {event.actor} - {event.time}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </Surface>
    </div>
  );
}

function NorthstarBriefPanel() {
  return (
    <Surface
      className="relative overflow-hidden border-primary/20"
      style={{
        background:
          "linear-gradient(135deg, var(--surface-raised) 0%, var(--surface-raised) 58%, color-mix(in srgb, var(--primary) 14%, transparent) 100%)",
      }}
    >
      <div className="grid gap-0 xl:grid-cols-[0.92fr_1.08fr]">
        <div className="border-b border-[var(--border-card)] px-6 py-6 md:px-7 md:py-7 xl:border-b-0 xl:border-r">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-md border border-primary/20 bg-primary/10 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              {northstarBrief.status}
            </span>
            <span className="rounded-md border border-[var(--border-card)] bg-[var(--surface-secondary)]/45 px-2 py-1 font-mono text-[11px] font-semibold text-[var(--text-secondary)]">
              confidence {northstarBrief.confidence}
            </span>
          </div>

          <h2 className="mt-5 max-w-xl text-[28px] font-semibold leading-tight tracking-tight text-[var(--text-primary)] md:text-[40px]">
            {northstarBrief.headline}
          </h2>
          <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-[var(--text-secondary)]">
            {northstarBrief.summary}
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-2">
            <Button asChild className="h-9 rounded-lg bg-primary px-4 text-[13px] font-semibold text-primary-foreground">
              <Link href="/dashboard/cases">{northstarBrief.primaryAction}</Link>
            </Button>
            <Button
              asChild
              variant="outline"
              className="h-9 rounded-lg border-[var(--border-card)] bg-[var(--surface-glass)] px-4 text-[13px]"
            >
              <Link href="/dashboard/cases">{northstarBrief.secondaryAction}</Link>
            </Button>
          </div>
        </div>

        <div className="px-6 py-6 md:px-7 md:py-7">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/15 bg-primary/10">
              <Command className="h-4 w-4 text-primary" />
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
                Next Best Moves
              </p>
              <h3 className="mt-0.5 text-[15px] font-semibold text-[var(--text-primary)]">Operator brief</h3>
            </div>
          </div>

          <div className="mt-5 divide-y divide-[var(--border-subtle)]">
            {northstarRecommendations.map((item) => {
              const style = toneClass(item.tone);

              return (
                <div key={item.title} className="grid gap-4 py-4 first:pt-0 md:grid-cols-[1fr_auto] md:items-center">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
                      <p className="truncate text-[14px] font-semibold text-[var(--text-primary)]">{item.title}</p>
                    </div>
                    <p className="mt-2 max-w-xl text-[13px] leading-relaxed text-[var(--text-tertiary)]">{item.detail}</p>
                    <p className={`mt-2 text-[12px] font-semibold ${style.text}`}>{item.impact}</p>
                  </div>
                  <Button
                    asChild
                    variant="outline"
                    className="h-8 w-fit justify-self-start rounded-lg border-[var(--border-card)] bg-[var(--surface-glass)] px-3 text-[12px] md:justify-self-end"
                  >
                    <Link href="/dashboard/cases">
                      {item.action}
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </Surface>
  );
}

function OperatingMetricsStrip() {
  return (
    <Surface className="overflow-hidden">
      <div className="grid divide-y divide-[var(--border-subtle)] md:grid-cols-4 md:divide-x md:divide-y-0">
        {operatingMetrics.map((metric) => {
          const style = toneClass(metric.tone);

          return (
            <div key={metric.label} className="min-w-0 px-5 py-4">
              <div className="flex items-center justify-between gap-3">
                <p className="truncate text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
                  {metric.label}
                </p>
                <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${style.dot}`} />
              </div>
              <p className="mt-3 font-mono text-[24px] font-semibold leading-none tracking-tight text-[var(--text-primary)] tabular-nums">
                {metric.value}
              </p>
              <p className={`mt-2 truncate text-[12px] font-medium ${style.text}`}>{metric.detail}</p>
            </div>
          );
        })}
      </div>
    </Surface>
  );
}

function ControlPlanePanel() {
  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
      <Surface className="overflow-hidden">
        <div className="border-b border-[var(--border-card)] px-6 py-5">
          <SectionHeading
            icon={Boxes}
            title="Evidence Graph"
            description="Applicant, consent, bank evidence, bureau, policy, and score signals stitched into one review object."
          />
        </div>
        <div className="px-6 py-5">
          <div className="grid gap-3">
            {evidenceGraph.map((edge, index) => {
              const style = toneClass(edge.tone);

              return (
                <div
                  key={`${edge.source}-${edge.target}`}
                  className="grid gap-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-secondary)]/30 px-4 py-3 sm:grid-cols-[1fr_auto_1fr] sm:items-center"
                >
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-semibold text-[var(--text-primary)]">{edge.source}</p>
                    <p className="mt-0.5 font-mono text-[11px] text-[var(--text-muted)]">node {index + 1}</p>
                  </div>
                  <div className="hidden items-center gap-2 sm:flex">
                    <span className={`h-2 w-2 rounded-full ${style.dot}`} />
                    <div className="h-px w-12 bg-[var(--border-card)]" />
                    <ArrowRight className="h-3.5 w-3.5 text-[var(--text-muted)]" />
                  </div>
                  <div className="min-w-0 sm:text-right">
                    <p className="truncate text-[13px] font-semibold text-[var(--text-primary)]">{edge.target}</p>
                    <p className={`mt-0.5 truncate text-[12px] ${style.text}`}>{edge.detail}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </Surface>

      <Surface className="overflow-hidden">
        <div className="border-b border-[var(--border-card)] px-6 py-5">
          <SectionHeading
            icon={GitBranch}
            title="Policy Controls"
            description="Live rules, owners, and portfolio effect for credit and compliance operations."
          />
        </div>
        <div className="hidden grid-cols-[1.1fr_0.8fr_0.6fr_0.8fr] border-b border-[var(--border-card)] bg-[var(--surface-secondary)]/45 px-6 py-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)] md:grid">
          <div>Control</div>
          <div>Owner</div>
          <div>Status</div>
          <div>Effect</div>
        </div>
        <div className="divide-y divide-[var(--border-subtle)]">
          {policyControls.map((control) => (
            <div
              key={control.control}
              className="grid gap-3 px-6 py-4 md:grid-cols-[1.1fr_0.8fr_0.6fr_0.8fr] md:items-center"
            >
              <div>
                <p className="text-[13px] font-semibold text-[var(--text-primary)]">{control.control}</p>
                <p className="mt-0.5 text-[11px] text-[var(--text-muted)] md:hidden">{control.owner}</p>
              </div>
              <p className="hidden text-[12px] font-medium text-[var(--text-secondary)] md:block">{control.owner}</p>
              <div>
                <StatusBadge label={control.status} tone={control.tone} />
              </div>
              <p className="font-mono text-[12px] font-semibold text-[var(--text-secondary)]">{control.effect}</p>
            </div>
          ))}
        </div>
      </Surface>
    </div>
  );
}

/* Page */

export default function DashboardPage() {
  const approveCount = prototypeCases.filter((item) => item.decision === "approve").length;
  const reviewCount = prototypeCases.filter((item) => item.decision === "manual_review").length;
  const rejectCount = prototypeCases.filter((item) => item.decision === "reject").length;

  return (
    <div className="flex flex-col gap-8 pb-14">
      <PageHeader
        eyebrow="Command Center"
        title="Operate credit like a real-time control plane."
        description="Portfolio exposure, policy controls, evidence lineage, and reviewer queues in one dense operating surface."
      >
        <Button
          asChild
          variant="outline"
          className="h-9 rounded-lg border-[var(--border-card)] bg-[var(--surface-raised)] text-[13px]"
        >
          <Link id="analyze-doc-btn" href="/dashboard/upload">
            <UploadCloud className="h-3.5 w-3.5" />
            Start Case
          </Link>
        </Button>
        <Button asChild className="h-9 rounded-lg bg-primary px-4 text-[13px] font-semibold text-primary-foreground">
          <Link href="/dashboard/cases">Open Queue</Link>
        </Button>
      </PageHeader>

      <NorthstarBriefPanel />

      <OperatingMetricsStrip />

      <SystemIntelligencePanel />

      <ControlPlanePanel />

      <div className="grid gap-6 xl:grid-cols-[1.45fr_0.9fr]">
        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-6 py-5">
            <SectionHeading
              icon={Landmark}
              title="Decision Operations"
              description="Cases prioritized by risk score, SLA proximity, and evidence completeness."
              action={
                <Link id="view-all-cases-link" href="/dashboard/cases">
                  <InlineLinkLabel>View all</InlineLinkLabel>
                </Link>
              }
            />
          </div>

          <div className="grid grid-cols-3 border-b border-[var(--border-card)] bg-[var(--surface-secondary)]/45 px-6 py-4">
            <div>
              <p className="text-[22px] font-semibold leading-none text-emerald-500 tabular-nums">{approveCount}</p>
              <p className="mt-1.5 text-[12px] font-medium text-[var(--text-tertiary)]">approved</p>
            </div>
            <div>
              <p className="text-[22px] font-semibold leading-none text-amber-500 tabular-nums">{reviewCount}</p>
              <p className="mt-1.5 text-[12px] font-medium text-[var(--text-tertiary)]">in review</p>
            </div>
            <div>
              <p className="text-[22px] font-semibold leading-none text-red-500 tabular-nums">{rejectCount}</p>
              <p className="mt-1.5 text-[12px] font-medium text-[var(--text-tertiary)]">rejected</p>
            </div>
          </div>

          <div className="divide-y divide-[var(--border-subtle)]">
            {prototypeCases.map((item) => (
              <Link
                key={item.id}
                href="/dashboard/cases/demo"
                className="grid gap-4 px-6 py-5 transition hover:bg-[var(--surface-hover)] lg:grid-cols-[1.2fr_0.8fr_0.75fr_0.6fr_auto]"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-[14px] font-semibold text-[var(--text-primary)]">{item.applicant}</p>
                    <StatusBadge
                      label={item.priority}
                      tone={item.priority === "Critical" ? "danger" : item.priority === "Elevated" ? "warning" : "neutral"}
                    />
                  </div>
                  <p className="mt-1.5 truncate text-[13px] text-[var(--text-tertiary)]">
                    {item.product} - {item.amount} - {item.region}
                  </p>
                </div>
                <div>
                  <p className="text-[12px] font-semibold uppercase tracking-[0.12em] text-[var(--text-tertiary)]">Workflow</p>
                  <p className="mt-1.5 text-[13px] font-medium text-[var(--text-secondary)]">{item.workflow}</p>
                </div>
                <div>
                  <p className="text-[12px] font-semibold uppercase tracking-[0.12em] text-[var(--text-tertiary)]">Decision</p>
                  <div className="mt-1.5">
                    <DecisionBadge decision={item.decision} />
                  </div>
                </div>
                <div>
                  <p className="text-[12px] font-semibold uppercase tracking-[0.12em] text-[var(--text-tertiary)]">Risk</p>
                  <p className="mt-1.5 text-[14px] font-semibold text-[var(--text-primary)] tabular-nums">{item.riskScore}</p>
                </div>
                <ArrowRight className="hidden h-4 w-4 self-center text-[var(--text-faint)] lg:block" />
              </Link>
            ))}
          </div>
        </Surface>

        <div className="flex flex-col gap-6">
          <div id="activity-feed-area">
            <Surface className="p-6">
            <SectionHeading
              icon={Network}
              title="Event Stream"
              description="Live feed across AA ingestion, LOS webhooks, model inference, and policy events."
            />
            <div className="mt-5">
              {eventStream.slice(0, 4).map((event) => (
                <TimelineRow
                  key={`${event.time}-${event.label}`}
                  label={event.label}
                  detail={event.detail}
                  time={event.time}
                  tone={event.tone}
                />
              ))}
            </div>
            </Surface>
          </div>

          <Surface className="overflow-hidden">
            <div className="border-b border-[var(--border-card)] px-6 py-5">
              <SectionHeading icon={DatabaseZap} title="Platform Surface" />
            </div>
            <div className="divide-y divide-[var(--border-subtle)] px-6">
              {[
                { key: "case.create", value: "evidence packet", tone: "good" as RiskTone },
                { key: "score.explain", value: "rationale attached", tone: "good" as RiskTone },
                { key: "policy.evaluate", value: "4 controls active", tone: "warning" as RiskTone },
                { key: "audit.export", value: "SOC2-ready trail", tone: "neutral" as RiskTone },
              ].map((item) => {
                const style = toneClass(item.tone);

                return (
                  <div key={item.key} className="flex items-center justify-between gap-4 py-3">
                    <div className="min-w-0">
                      <p className="font-mono text-[12px] font-semibold text-[var(--text-primary)]">{item.key}</p>
                      <p className="mt-0.5 truncate text-[12px] text-[var(--text-muted)]">{item.value}</p>
                    </div>
                    <span className={`h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
                  </div>
                );
              })}
            </div>
          </Surface>
        </div>
      </div>
    </div>
  );
}
