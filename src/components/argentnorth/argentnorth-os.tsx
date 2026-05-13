"use client";

import { useMemo, useState, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  BrainCircuit,
  ChevronRight,
  ClipboardList,
  Command,
  DatabaseZap,
  FileText,
  Filter,
  Gauge,
  GitBranch,
  KeyRound,
  Landmark,
  LockKeyhole,
  Network,
  Route,
  Scale,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  UploadCloud,
  UsersRound,
  WalletCards,
  Zap,
} from "lucide-react";

import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DataTile,
  HealthDot,
  ProgressBar,
  StatusBadge,
  Surface,
  TimelineRow,
  toneClass,
} from "@/components/argentnorth/prototype-ui";
import {
  AreaChart,
  EvidenceFlowGraph,
  GaugeArc,
  LivePulseDot,
  PageTransition,
  Sparkline,
  WaterfallChart,
} from "@/components/argentnorth/viz-components";
import { cn } from "@/lib/utils";
import type { RiskTone } from "@/lib/argentnorth-prototype";
import {
  agenticMoves,
  apiKeyPlaceholders,
  boardMetrics,
  capitalRails,
  cohortWatchlist,
  commandEventStream,
  commandSignals,
  complianceControls,
  decisionObjects,
  dossier,
  evidenceGraphNodes,
  evidencePacket,
  exposureTrendData,
  fairnessMetrics,
  intakeFields,
  intakeSteps,
  metricSparklines,
  modelCards,
  operatingLanes,
  policyBattery,
  queueCases,
  roleAccess,
  sidebarHealthSignals,
  type PrototypeDecision,
} from "@/lib/argentnorth-ui-prototype";

type ArgentSectionId =
  | "command"
  | "execution"
  | "decision"
  | "intake"
  | "policy"
  | "risk"
  | "compliance"
  | "integrations";

const argentSections: Array<{
  id: ArgentSectionId;
  label: string;
  short: string;
  description: string;
}> = [
    {
      id: "command",
      label: "Command Center",
      short: "Command",
      description: "Portfolio exposure, live controls, and decision graph.",
    },
    {
      id: "execution",
      label: "Execution Book",
      short: "Book",
      description: "Dense underwriting queue for credit operations.",
    },
    {
      id: "decision",
      label: "Decision Object",
      short: "Object",
      description: "One case with evidence, risk, policy, and authority.",
    },
    {
      id: "intake",
      label: "Evidence Intake",
      short: "Intake",
      description: "Guided packet creation with live validation.",
    },
    {
      id: "policy",
      label: "Policy Studio",
      short: "Policy",
      description: "Rule batteries, lanes, limits, and maker-checker gates.",
    },
    {
      id: "risk",
      label: "Model Risk Ops",
      short: "Risk Ops",
      description: "Champion model, fairness, drift, and cohort watch.",
    },
    {
      id: "compliance",
      label: "Governance",
      short: "Gov",
      description: "FREE-AI, DPDP, SOC2, access, and audit controls.",
    },
    {
      id: "integrations",
      label: "Data Fabric",
      short: "Fabric",
      description: "AA, BIAN, ISO 20022, LOS, and webhook rails.",
    },
  ];

const sectionIcons: Record<ArgentSectionId, LucideIcon> = {
  command: Command,
  execution: ClipboardList,
  decision: FileText,
  intake: UploadCloud,
  policy: SlidersHorizontal,
  risk: BrainCircuit,
  compliance: ShieldCheck,
  integrations: DatabaseZap,
};

const thesis = [
  "A governed credit decision fabric for banks, NBFCs, and embedded lenders.",
  "Every approval is a typed object: data, policy, model rationale, authority, audit.",
  "Agentic systems recommend action. Humans and signed policies move capital.",
];

const architectureRails = [
  {
    label: "Data",
    detail: "AA, GST, bureau, bank statements, core ledgers",
    icon: DatabaseZap,
    tone: "good" as RiskTone,
  },
  {
    label: "Ontology",
    detail: "BIAN service domains and ISO 20022 event semantics",
    icon: GitBranch,
    tone: "neutral" as RiskTone,
  },
  {
    label: "Intelligence",
    detail: "GBM scorecards, SHAP/LIME, fraud and drift monitors",
    icon: BrainCircuit,
    tone: "warning" as RiskTone,
  },
  {
    label: "Authority",
    detail: "Maker-checker gates, policy batteries, signed actions",
    icon: ShieldCheck,
    tone: "good" as RiskTone,
  },
];

const fabricConnectors = [
  {
    name: "Account Aggregator FIU",
    source: "Finvu / OneMoney / CAMSFinServ",
    event: "Consent packet normalized",
    control: "Purpose-bound DPDP retention",
    latency: "388ms",
    tone: "good" as RiskTone,
  },
  {
    name: "Core banking adapter",
    source: "Finacle / BaNCS / custom CBS",
    event: "Balance and repayment webhooks",
    control: "Read scope, no core replacement",
    latency: "184ms",
    tone: "neutral" as RiskTone,
  },
  {
    name: "LOS writeback",
    source: "M2P / FinnOne / Newgen",
    event: "Decision and pricing packet",
    control: "Signed action with audit export",
    latency: "221ms",
    tone: "good" as RiskTone,
  },
  {
    name: "Regulatory evidence vault",
    source: "FREE-AI / SOC2 / ISO controls",
    event: "Rationale, SHAP, reviewer notes",
    control: "Immutable audit timeline",
    latency: "51ms",
    tone: "good" as RiskTone,
  },
];

function getDecisionTone(decision: PrototypeDecision): RiskTone {
  if (decision === "Approve") return "good";
  if (decision === "Reject") return "danger";
  return "warning";
}

function getRiskBandTone(riskBand: "Low" | "Medium" | "High"): RiskTone {
  if (riskBand === "Low") return "good";
  if (riskBand === "High") return "danger";
  return "warning";
}

function SectionShell({
  eyebrow,
  title,
  description,
  children,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 border-b border-[var(--border-card)] pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-4xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">{eyebrow}</p>
          <h1 className="mt-2 max-w-4xl text-2xl font-semibold leading-tight tracking-tight text-[var(--text-primary)] md:text-[34px]">
            {title}
          </h1>
          <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-[var(--text-secondary)]">{description}</p>
        </div>
        {action ? <div className="flex flex-wrap items-center gap-2">{action}</div> : null}
      </div>
      {children}
    </div>
  );
}

function PanelTitle({
  icon: Icon,
  title,
  detail,
  action,
}: {
  icon: LucideIcon;
  title: string;
  detail?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 border-b border-[var(--border-card)] px-4 py-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-primary/15 bg-primary/10">
          <Icon className="h-4 w-4 text-primary" />
        </div>
        <div className="min-w-0">
          <h2 className="text-[14px] font-semibold text-[var(--text-primary)]">{title}</h2>
          {detail ? <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-tertiary)]">{detail}</p> : null}
        </div>
      </div>
      {action}
    </div>
  );
}

function ExecutiveMetric({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: RiskTone;
}) {
  const spark = metricSparklines[label] ?? [4, 6, 5, 7, 8, 9, 10];
  return (
    <Surface className="overflow-hidden p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-tertiary)]">
            {label}
          </p>
          <p className="mt-2 text-[24px] font-semibold leading-none tracking-tight text-[var(--text-primary)] tabular-nums">
            {value}
          </p>
        </div>
        <Sparkline data={spark} tone={tone} />
      </div>
      <p className={cn("mt-3 text-[12px] font-medium", toneClass(tone).text)}>{detail}</p>
    </Surface>
  );
}

function NavRail({
  active,
  onNavigate,
  compact = false,
}: {
  active: ArgentSectionId;
  onNavigate: (section: ArgentSectionId) => void;
  compact?: boolean;
}) {
  return (
    <nav
      aria-label="ArgentNorth sections"
      className={cn(
        compact
          ? "flex gap-2 overflow-x-auto border-y border-[var(--border-card)] bg-[var(--surface-raised)] px-4 py-3 xl:hidden"
          : "flex flex-col gap-1"
      )}
    >
      {argentSections.map((item) => {
        const Icon = sectionIcons[item.id];
        const isActive = active === item.id;

        return (
          <button
            key={item.id}
            type="button"
            aria-pressed={isActive}
            onClick={() => onNavigate(item.id)}
            className={cn(
              "group inline-flex items-center gap-2.5 rounded-md border text-left text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/45",
              compact ? "h-9 shrink-0 px-3" : "min-h-11 w-full px-3 py-2.5",
              isActive
                ? "border-primary/20 bg-primary/10 text-[var(--text-primary)]"
                : "border-transparent text-[var(--text-tertiary)] hover:border-[var(--border-card)] hover:bg-[var(--surface-secondary)]/70 hover:text-[var(--text-primary)]"
            )}
          >
            <Icon className={cn("h-4 w-4 shrink-0", isActive ? "text-primary" : "text-[var(--text-muted)]")} />
            <span className="truncate">{compact ? item.short : item.label}</span>
            {!compact ? (
              <ChevronRight
                className={cn(
                  "ml-auto h-3.5 w-3.5 shrink-0 transition-opacity",
                  isActive ? "text-primary opacity-100" : "text-[var(--text-muted)] opacity-0 group-hover:opacity-100"
                )}
              />
            ) : null}
          </button>
        );
      })}
    </nav>
  );
}

function ShellSidebar({
  active,
  onNavigate,
}: {
  active: ArgentSectionId;
  onNavigate: (section: ArgentSectionId) => void;
}) {
  return (
    <aside className="hidden w-[292px] shrink-0 border-r border-[var(--border-card)] bg-[var(--surface-raised)] xl:flex xl:flex-col">
      <div className="border-b border-[var(--border-card)] px-5 py-5">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-md bg-primary text-[13px] font-semibold text-primary-foreground shadow-sm">
            AN
          </div>
          <div className="min-w-0">
            <p className="text-[14px] font-semibold text-[var(--text-primary)]">ArgentNorth</p>
            <p className="truncate text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--text-muted)]">
              Credit decision fabric
            </p>
          </div>
        </div>
        <div className="mt-4 rounded-md border border-[var(--border-card)] bg-[var(--surface-secondary)]/45 px-3 py-2.5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
            Operating doctrine
          </p>
          <p className="mt-1.5 text-[12px] leading-relaxed text-[var(--text-secondary)]">
            {"Data -> policy -> model -> authority -> audit"}, with no silent capital movement.
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-4">
        <NavRail active={active} onNavigate={onNavigate} />
      </div>

      <div className="space-y-3 border-t border-[var(--border-card)] p-4">
        {sidebarHealthSignals.map((signal) => (
          <div key={signal.label} className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-[12px] font-semibold text-[var(--text-secondary)]">{signal.label}</p>
              <p className={cn("font-mono text-[11px]", toneClass(signal.tone).text)}>{signal.value}</p>
            </div>
            <Sparkline data={signal.spark} tone={signal.tone} width={68} height={22} />
          </div>
        ))}
      </div>
    </aside>
  );
}

function TopBar({ active }: { active: ArgentSectionId }) {
  const activeSection = argentSections.find((section) => section.id === active) ?? argentSections[0];

  return (
    <header className="sticky top-0 z-30 border-b border-[var(--border-card)] bg-[var(--surface-glass)] backdrop-blur-xl">
      <div className="flex min-h-14 items-center justify-between gap-3 px-4 sm:px-6 xl:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border-card)] bg-[var(--surface-raised)] xl:hidden">
            <Command className="h-4 w-4 text-primary" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-[13px] font-semibold text-[var(--text-primary)]">{activeSection.label}</p>
            <p className="hidden truncate font-mono text-[11px] text-[var(--text-muted)] sm:block">
              /argentnorth/{activeSection.id}
            </p>
          </div>
        </div>

        <div className="flex min-w-0 items-center gap-2">
          <div className="hidden h-8 min-w-[260px] items-center gap-2 rounded-md border border-[var(--border-card)] bg-[var(--surface-raised)] px-3 text-[12px] text-[var(--text-muted)] md:flex">
            <Search className="h-3.5 w-3.5" />
            <span className="truncate">Search cases, cohorts, policy rules...</span>
            <kbd className="ml-auto rounded border border-[var(--border-card)] px-1.5 py-0.5 font-mono text-[10px]">
              Ctrl K
            </kbd>
          </div>
          <ThemeToggle />
          <Button size="sm" className="h-8 rounded-md">
            Review book
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </header>
  );
}

function CommandCenterView({ onNavigate }: { onNavigate: (section: ArgentSectionId) => void }) {
  return (
    <SectionShell
      eyebrow="ArgentNorth OS"
      title="The governed layer between financial data and capital action."
      description="A production-grade command surface for regulated lenders: every decision is traceable from Account Aggregator evidence to policy, model rationale, authority, and audit export."
      action={
        <>
          <Button variant="outline" size="sm" className="rounded-md">
            <Filter className="h-4 w-4" />
            Portfolio filters
          </Button>
          <Button size="sm" className="rounded-md" onClick={() => onNavigate("execution")}>
            Open execution book
            <ArrowRight className="h-4 w-4" />
          </Button>
        </>
      }
    >
      <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-4">
        {boardMetrics.map((metric) => (
          <ExecutiveMetric key={metric.label} {...metric} />
        ))}
      </div>

      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.5fr)_minmax(360px,0.9fr)]">
        <Surface className="overflow-hidden">
          <PanelTitle
            icon={Network}
            title="Decision fabric"
            detail="Palantir-style object graph: data, controls, and authority remain visible at every step."
            action={<StatusBadge label="Live" tone="good" />}
          />
          <div className="space-y-5 p-4">
            <div className="grid gap-3 md:grid-cols-4">
              {architectureRails.map((rail) => {
                const Icon = rail.icon;
                return (
                  <div key={rail.label} className="rounded-md border border-[var(--border-card)] bg-[var(--surface-secondary)]/35 p-3">
                    <div className="flex items-center gap-2">
                      <Icon className={cn("h-4 w-4", toneClass(rail.tone).text)} />
                      <p className="text-[12px] font-semibold text-[var(--text-primary)]">{rail.label}</p>
                    </div>
                    <p className="mt-2 text-[12px] leading-relaxed text-[var(--text-tertiary)]">{rail.detail}</p>
                  </div>
                );
              })}
            </div>

            <div className="min-h-[120px] rounded-md border border-[var(--border-card)] bg-[var(--surface-raised)] p-4">
              <EvidenceFlowGraph nodes={evidenceGraphNodes} />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left">
                <thead>
                  <tr className="border-y border-[var(--border-card)] bg-[var(--surface-secondary)]/55 text-[11px] uppercase tracking-[0.12em] text-[var(--text-tertiary)]">
                    <th className="px-3 py-2 font-semibold">Object</th>
                    <th className="px-3 py-2 font-semibold">Source</th>
                    <th className="px-3 py-2 font-semibold">Latency</th>
                    <th className="px-3 py-2 font-semibold">Control</th>
                    <th className="px-3 py-2 font-semibold">Authority</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-card)]">
                  {decisionObjects.map((object) => (
                    <tr key={object.object} className="text-[13px] text-[var(--text-secondary)]">
                      <td className="px-3 py-3 font-semibold text-[var(--text-primary)]">
                        <span className="inline-flex items-center gap-2">
                          <HealthDot tone={object.tone} />
                          {object.object}
                        </span>
                      </td>
                      <td className="px-3 py-3">{object.source}</td>
                      <td className="px-3 py-3 font-mono text-[12px]">{object.latency}</td>
                      <td className="px-3 py-3">{object.control}</td>
                      <td className="px-3 py-3">{object.authority}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Surface>

        <div className="space-y-5">
          <Surface className="overflow-hidden">
            <PanelTitle
              icon={Activity}
              title="Exposure cleared"
              detail="Same-day flow of capital through governed rails."
            />
            <div className="p-4">
              <AreaChart data={exposureTrendData.values} labels={exposureTrendData.labels} height={176} />
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {capitalRails.slice(0, 4).map((rail) => (
                  <div key={rail.label} className="space-y-2 rounded-md border border-[var(--border-card)] p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-[12px] font-semibold text-[var(--text-primary)]">{rail.label}</p>
                        <p className="mt-1 text-[11px] text-[var(--text-tertiary)]">{rail.detail}</p>
                      </div>
                      <span className="shrink-0 font-mono text-[11px] text-[var(--text-secondary)]">{rail.value}</span>
                    </div>
                    <ProgressBar value={rail.progress} tone={rail.tone} className="h-1.5" />
                  </div>
                ))}
              </div>
            </div>
          </Surface>

          <Surface className="overflow-hidden">
            <PanelTitle
              icon={Zap}
              title="Agentic control memo"
              detail="Recommendations are active, permissioned, and auditable."
            />
            <div className="divide-y divide-[var(--border-card)]">
              {agenticMoves.map((move) => (
                <div key={move.title} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[13px] font-semibold text-[var(--text-primary)]">{move.title}</p>
                      <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-tertiary)]">{move.detail}</p>
                    </div>
                    <StatusBadge label={move.impact} tone={move.tone} />
                  </div>
                  <p className="mt-2 font-mono text-[11px] text-[var(--text-muted)]">{move.authority}</p>
                </div>
              ))}
            </div>
          </Surface>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Surface className="overflow-hidden">
          <PanelTitle icon={Landmark} title="Strategic thesis" detail="Institutional posture, not consumer fintech gloss." />
          <div className="divide-y divide-[var(--border-card)]">
            {thesis.map((item, index) => (
              <div key={item} className="flex gap-3 p-4">
                <span className="font-mono text-[11px] text-primary">0{index + 1}</span>
                <p className="text-[13px] leading-relaxed text-[var(--text-secondary)]">{item}</p>
              </div>
            ))}
          </div>
        </Surface>

        <Surface className="overflow-hidden">
          <PanelTitle icon={Route} title="Live event stream" detail="Operational truth from ingestion to decision packet." />
          <div className="p-4">
            {commandEventStream.map((event) => (
              <TimelineRow key={`${event.time}-${event.label}`} {...event} />
            ))}
          </div>
        </Surface>
      </div>
    </SectionShell>
  );
}

function ExecutionBookView({ onNavigate }: { onNavigate: (section: ArgentSectionId) => void }) {
  const totals = useMemo(
    () => [
      { label: "Open cases", value: String(queueCases.length), tone: "neutral" as RiskTone },
      { label: "Auto-ready", value: "2", tone: "good" as RiskTone },
      { label: "Manual gate", value: "3", tone: "warning" as RiskTone },
      { label: "Adverse action", value: "1", tone: "danger" as RiskTone },
    ],
    []
  );

  return (
    <SectionShell
      eyebrow="Execution Book"
      title="A dense underwriting cockpit for regulated credit teams."
      description="Ramp-style operational density: every row shows risk, evidence completeness, SLA pressure, recommendation, price, and reviewer accountability."
      action={
        <>
          <Button variant="outline" size="sm" className="rounded-md">
            <Filter className="h-4 w-4" />
            Segment
          </Button>
          <Button size="sm" className="rounded-md" onClick={() => onNavigate("decision")}>
            Open AN-2057
            <ArrowRight className="h-4 w-4" />
          </Button>
        </>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {totals.map((item) => (
          <Surface key={item.label} className="px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[12px] font-semibold uppercase tracking-[0.12em] text-[var(--text-tertiary)]">
                {item.label}
              </p>
              <HealthDot tone={item.tone} />
            </div>
            <p className="mt-2 text-2xl font-semibold text-[var(--text-primary)] tabular-nums">{item.value}</p>
          </Surface>
        ))}
      </div>

      <Surface className="overflow-hidden">
        <PanelTitle
          icon={ClipboardList}
          title="Underwriting queue"
          detail="Sorted by SLA pressure, evidence gaps, and authority lane."
          action={<StatusBadge label="6 active cases" tone="warning" />}
        />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1120px] text-left">
            <thead>
              <tr className="border-b border-[var(--border-card)] bg-[var(--surface-secondary)]/55 text-[11px] uppercase tracking-[0.12em] text-[var(--text-tertiary)]">
                <th className="px-3 py-2.5 font-semibold">Case</th>
                <th className="px-3 py-2.5 font-semibold">Applicant</th>
                <th className="px-3 py-2.5 font-semibold">Product</th>
                <th className="px-3 py-2.5 font-semibold">Exposure</th>
                <th className="px-3 py-2.5 font-semibold">Risk</th>
                <th className="px-3 py-2.5 font-semibold">Evidence</th>
                <th className="px-3 py-2.5 font-semibold">SLA</th>
                <th className="px-3 py-2.5 font-semibold">Recommendation</th>
                <th className="px-3 py-2.5 font-semibold">Price</th>
                <th className="px-3 py-2.5 font-semibold">Owner</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-card)]">
              {queueCases.map((item) => (
                <tr key={item.id} className="group text-[13px] text-[var(--text-secondary)] hover:bg-[var(--surface-secondary)]/35">
                  <td className="px-3 py-3 font-mono text-[12px] font-semibold text-primary">{item.id}</td>
                  <td className="px-3 py-3">
                    <button
                      type="button"
                      onClick={() => onNavigate("decision")}
                      className="text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/45"
                    >
                      <span className="block font-semibold text-[var(--text-primary)]">{item.applicant}</span>
                      <span className="block text-[11px] text-[var(--text-muted)]">{item.entityType} / {item.region}</span>
                    </button>
                  </td>
                  <td className="px-3 py-3">{item.product}</td>
                  <td className="px-3 py-3 font-mono text-[12px] text-[var(--text-primary)]">{item.amount}</td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      <StatusBadge label={`${item.riskBand} ${item.riskScore}`} tone={getRiskBandTone(item.riskBand)} />
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex min-w-[116px] items-center gap-2">
                      <ProgressBar value={item.evidence} tone={item.evidence >= 90 ? "good" : "warning"} className="h-1.5" />
                      <span className="font-mono text-[11px]">{item.evidence}%</span>
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <span className="font-mono text-[12px] text-[var(--text-primary)]">{item.sla}</span>
                    <span className="ml-2 text-[11px] text-[var(--text-muted)]">{item.status}</span>
                  </td>
                  <td className="px-3 py-3">
                    <StatusBadge label={item.decision} tone={getDecisionTone(item.decision)} />
                  </td>
                  <td className="px-3 py-3 font-mono text-[12px]">{item.pricing}</td>
                  <td className="px-3 py-3">{item.reviewer}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Surface>

      <div className="grid gap-5 lg:grid-cols-4">
        {operatingLanes.map((lane) => (
          <Surface key={lane.lane} className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[13px] font-semibold text-[var(--text-primary)]">{lane.lane}</p>
                <p className="mt-1 font-mono text-[12px] text-[var(--text-muted)]">{lane.owner}</p>
              </div>
              <HealthDot tone={lane.tone} />
            </div>
            <div className="mt-4 grid grid-cols-3 gap-3 text-[12px]">
              <div>
                <p className="text-[var(--text-muted)]">Volume</p>
                <p className="mt-1 font-semibold text-[var(--text-primary)]">{lane.volume}</p>
              </div>
              <div>
                <p className="text-[var(--text-muted)]">Capital</p>
                <p className="mt-1 font-semibold text-[var(--text-primary)]">{lane.capital}</p>
              </div>
              <div>
                <p className="text-[var(--text-muted)]">Risk</p>
                <p className={cn("mt-1 font-semibold", toneClass(lane.tone).text)}>{lane.risk}</p>
              </div>
            </div>
          </Surface>
        ))}
      </div>
    </SectionShell>
  );
}

function DecisionObjectView() {
  return (
    <SectionShell
      eyebrow="Decision Object"
      title={`${dossier.id}: ${dossier.applicant}`}
      description={dossier.summary}
      action={
        <>
          <Button variant="outline" size="sm" className="rounded-md">
            Reject
          </Button>
          <Button variant="outline" size="sm" className="rounded-md">
            Route to CRO
          </Button>
          <Button size="sm" className="rounded-md">
            Approve with controls
          </Button>
        </>
      }
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_360px]">
        <div className="space-y-5">
          <Surface className="overflow-hidden">
            <PanelTitle
              icon={FileText}
              title="Applicant packet"
              detail="Facts, evidence, policy checks, pricing, and model rationale in one governed view."
              action={<StatusBadge label={dossier.recommendation} tone={getDecisionTone(dossier.recommendation)} />}
            />
            <div className="grid gap-4 p-4 lg:grid-cols-[160px_minmax(0,1fr)]">
              <div className="flex items-center justify-center">
                <GaugeArc score={dossier.riskScore} size={148} />
              </div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {dossier.facts.map((fact) => (
                  <DataTile key={fact.label} label={fact.label} value={fact.value} />
                ))}
              </div>
            </div>
          </Surface>

          <div className="grid gap-5 lg:grid-cols-2">
            <Surface className="overflow-hidden">
              <PanelTitle icon={Activity} title="Cash-flow intelligence" detail="AA-derived indicators normalized for underwriting." />
              <div className="grid gap-3 p-4 sm:grid-cols-2">
                {dossier.cashflow.map((item) => (
                  <DataTile key={item.label} label={item.label} value={item.value} tone={item.tone} />
                ))}
              </div>
            </Surface>

            <Surface className="overflow-hidden">
              <PanelTitle icon={AlertTriangle} title="Fraud and anomaly flags" detail="Signals that affect human confidence." />
              <div className="divide-y divide-[var(--border-card)]">
                {dossier.fraudFlags.map((flag) => (
                  <div key={flag.label} className="flex items-start gap-3 p-4">
                    <HealthDot tone={flag.tone} />
                    <div className="min-w-0">
                      <p className="text-[13px] font-semibold text-[var(--text-primary)]">{flag.label}</p>
                      <p className="mt-1 text-[12px] text-[var(--text-tertiary)]">{flag.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Surface>
          </div>

          <Surface className="overflow-hidden">
            <PanelTitle icon={BrainCircuit} title="SHAP-style reason drivers" detail="Explainability is attached to the action packet before review." />
            <div className="p-4">
              <WaterfallChart drivers={dossier.drivers} />
            </div>
          </Surface>
        </div>

        <div className="space-y-5">
          <Surface className="overflow-hidden">
            <PanelTitle icon={Scale} title="Policy checks" detail="Hard gates, exceptions, and FREE-AI rationale." />
            <div className="divide-y divide-[var(--border-card)]">
              {dossier.policyChecks.map((check) => (
                <div key={check.label} className="flex items-center justify-between gap-3 p-4">
                  <p className="text-[13px] font-medium text-[var(--text-secondary)]">{check.label}</p>
                  <StatusBadge label={check.result} tone={check.tone} />
                </div>
              ))}
            </div>
          </Surface>

          <Surface className="overflow-hidden">
            <PanelTitle icon={BadgeCheck} title="Action authority" detail="No decision can execute without a signed lane." />
            <div className="space-y-3 p-4">
              <div className="rounded-md border border-[var(--border-card)] bg-[var(--surface-secondary)]/35 p-3">
                <p className="text-[12px] font-semibold text-[var(--text-primary)]">Recommended action</p>
                <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-tertiary)]">
                  Manual approval after 12-month bank evidence exception is accepted by senior reviewer.
                </p>
              </div>
              <div className="grid gap-2">
                <Button className="justify-between rounded-md">
                  Approve with bank-history exception
                  <ArrowRight className="h-4 w-4" />
                </Button>
                <Button variant="outline" className="justify-between rounded-md">
                  Ask for more evidence
                  <ArrowRight className="h-4 w-4" />
                </Button>
                <Button variant="outline" className="justify-between rounded-md">
                  Create adverse-action packet
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </Surface>

          <Surface className="overflow-hidden">
            <PanelTitle icon={Route} title="Audit trail" detail="Immutable reviewer and system timeline." />
            <div className="p-4">
              {dossier.auditTrail.map((event) => (
                <TimelineRow key={`${event.time}-${event.label}`} {...event} />
              ))}
            </div>
          </Surface>
        </div>
      </div>
    </SectionShell>
  );
}

function EvidenceIntakeView() {
  return (
    <SectionShell
      eyebrow="Evidence Intake"
      title="Stripe-grade workflow clarity for institutional evidence creation."
      description="Guided case assembly with clear validation, input hierarchy, and a final review packet before ArgentNorth creates the decision object."
      action={
        <>
          <Button variant="outline" size="sm" className="rounded-md">
            Save draft
          </Button>
          <Button size="sm" className="rounded-md">
            Create case
          </Button>
        </>
      }
    >
      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)_340px]">
        <Surface className="overflow-hidden">
          <PanelTitle icon={UploadCloud} title="Workflow" detail="Case creation steps with live status." />
          <div className="divide-y divide-[var(--border-card)]">
            {intakeSteps.map((step, index) => (
              <div key={step.label} className="flex gap-3 p-4">
                <div className="flex flex-col items-center">
                  <span
                    className={cn(
                      "grid h-7 w-7 place-items-center rounded-md border text-[12px] font-semibold",
                      step.status === "active"
                        ? "border-primary/25 bg-primary/10 text-primary"
                        : "border-[var(--border-card)] bg-[var(--surface-secondary)] text-[var(--text-tertiary)]"
                    )}
                  >
                    {index + 1}
                  </span>
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-[13px] font-semibold text-[var(--text-primary)]">{step.label}</p>
                    <StatusBadge label={step.status} tone={step.tone} />
                  </div>
                  <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-tertiary)]">{step.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </Surface>

        <Surface className="overflow-hidden">
          <PanelTitle icon={FileText} title="Applicant evidence form" detail="Clean hierarchy, explicit labels, and visible errors." />
          <div className="grid gap-4 p-4 md:grid-cols-2">
            {intakeFields.map((field) => (
              <label key={field.id} className="space-y-2">
                <span className="text-[12px] font-semibold text-[var(--text-primary)]">{field.label}</span>
                <Input
                  readOnly
                  value={field.value}
                  aria-invalid={Boolean(field.error)}
                  className="h-10 rounded-md border-[var(--border-card)] bg-[var(--surface-secondary)]/35 font-mono text-[12px]"
                />
                <span className={cn("block text-[12px] leading-relaxed", field.error ? "text-amber-500" : "text-[var(--text-tertiary)]")}>
                  {field.error ?? field.helper}
                </span>
              </label>
            ))}
          </div>
          <div className="border-t border-[var(--border-card)] bg-amber-500/10 px-4 py-3 text-[12px] leading-relaxed text-amber-600 dark:text-amber-300">
            Bank statement coverage is below policy. Create the case only after routing the exception or adding the missing evidence.
          </div>
        </Surface>

        <Surface className="overflow-hidden">
          <PanelTitle icon={ShieldCheck} title="Evidence packet" detail="What will be sealed into the case." />
          <div className="divide-y divide-[var(--border-card)]">
            {evidencePacket.map((item) => (
              <div key={item.label} className="flex items-center justify-between gap-3 p-4">
                <p className="text-[13px] font-medium text-[var(--text-secondary)]">{item.label}</p>
                <StatusBadge label={item.value} tone={item.tone} />
              </div>
            ))}
          </div>
          <div className="border-t border-[var(--border-card)] p-4">
            <Button className="w-full justify-between rounded-md">
              Review decision object
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </Surface>
      </div>
    </SectionShell>
  );
}

function PolicyStudioView() {
  return (
    <SectionShell
      eyebrow="Policy Studio"
      title="The policy layer is the product, not an admin afterthought."
      description="Credit policy, fraud rules, human authority, and agentic recommendations are modeled as explicit controls so institutions can change safely without rewriting core systems."
      action={
        <>
          <Button variant="outline" size="sm" className="rounded-md">
            Compare versions
          </Button>
          <Button size="sm" className="rounded-md">
            Publish draft
          </Button>
        </>
      }
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_360px]">
        <Surface className="overflow-hidden">
          <PanelTitle icon={Scale} title="Rule battery" detail="Hard gates, soft gates, and exception routing." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left">
              <thead>
                <tr className="border-b border-[var(--border-card)] bg-[var(--surface-secondary)]/55 text-[11px] uppercase tracking-[0.12em] text-[var(--text-tertiary)]">
                  <th className="px-3 py-2.5 font-semibold">Rule</th>
                  <th className="px-3 py-2.5 font-semibold">Owner</th>
                  <th className="px-3 py-2.5 font-semibold">Coverage</th>
                  <th className="px-3 py-2.5 font-semibold">Effect</th>
                  <th className="px-3 py-2.5 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-card)]">
                {policyBattery.map((rule) => (
                  <tr key={rule.rule} className="text-[13px] text-[var(--text-secondary)]">
                    <td className="px-3 py-3 font-semibold text-[var(--text-primary)]">{rule.rule}</td>
                    <td className="px-3 py-3">{rule.owner}</td>
                    <td className="px-3 py-3 font-mono text-[12px]">{rule.coverage}</td>
                    <td className="px-3 py-3">{rule.effect}</td>
                    <td className="px-3 py-3"><StatusBadge label="Active" tone={rule.tone} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Surface>

        <Surface className="overflow-hidden">
          <PanelTitle icon={LockKeyhole} title="Authority model" detail="Who can change what, and when." />
          <div className="space-y-3 p-4">
            {[
              { label: "Policy draft", value: "Credit Policy owns thresholds", tone: "neutral" as RiskTone },
              { label: "Model gate", value: "Risk Ops approves score impact", tone: "warning" as RiskTone },
              { label: "Compliance sign-off", value: "FREE-AI and DPDP checks required", tone: "good" as RiskTone },
              { label: "Production action", value: "Maker-checker with audit export", tone: "good" as RiskTone },
            ].map((item) => (
              <div key={item.label} className="rounded-md border border-[var(--border-card)] p-3">
                <div className="flex items-center gap-2">
                  <HealthDot tone={item.tone} />
                  <p className="text-[12px] font-semibold text-[var(--text-primary)]">{item.label}</p>
                </div>
                <p className="mt-2 text-[12px] leading-relaxed text-[var(--text-tertiary)]">{item.value}</p>
              </div>
            ))}
          </div>
        </Surface>
      </div>

      <Surface className="overflow-hidden">
        <PanelTitle icon={Route} title="Operating lanes" detail="Policy outcome becomes queue routing and capital authority." />
        <div className="grid gap-0 divide-y divide-[var(--border-card)] lg:grid-cols-4 lg:divide-x lg:divide-y-0">
          {operatingLanes.map((lane) => (
            <div key={lane.lane} className="p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[13px] font-semibold text-[var(--text-primary)]">{lane.lane}</p>
                <HealthDot tone={lane.tone} />
              </div>
              <div className="mt-4 space-y-2 text-[12px]">
                <div className="flex justify-between gap-3">
                  <span className="text-[var(--text-muted)]">Volume</span>
                  <span className="font-mono text-[var(--text-primary)]">{lane.volume}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-[var(--text-muted)]">Capital</span>
                  <span className="font-mono text-[var(--text-primary)]">{lane.capital}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-[var(--text-muted)]">Owner</span>
                  <span className="text-[var(--text-primary)]">{lane.owner}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Surface>
    </SectionShell>
  );
}

function ModelRiskOpsView() {
  return (
    <SectionShell
      eyebrow="Model Risk Ops"
      title="The math earns trust by being observable."
      description="CreditGBM drives structured-tabular risk prediction, while explainability, fairness, drift, and policy impact are visible before the institution trusts automation."
      action={<StatusBadge label="Champion guarded" tone="warning" />}
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {modelCards.map((model) => (
          <ExecutiveMetric key={model.label} {...model} />
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Surface className="overflow-hidden">
          <PanelTitle icon={Gauge} title="Fairness monitor" detail="Institution-facing metrics for protected and operational cohorts." />
          <div className="grid gap-3 p-4 md:grid-cols-2">
            {fairnessMetrics.map((metric) => (
              <div key={metric.label} className="rounded-md border border-[var(--border-card)] p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[13px] font-semibold text-[var(--text-primary)]">{metric.label}</p>
                    <p className="mt-1 text-[11px] text-[var(--text-muted)]">Threshold {metric.threshold}</p>
                  </div>
                  <StatusBadge label={metric.value} tone={metric.tone} />
                </div>
              </div>
            ))}
          </div>
        </Surface>

        <Surface className="overflow-hidden">
          <PanelTitle icon={Activity} title="Cohort watchlist" detail="Drift and fairness controls drive action lanes." />
          <div className="divide-y divide-[var(--border-card)]">
            {cohortWatchlist.map((cohort) => (
              <div key={cohort.cohort} className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[13px] font-semibold text-[var(--text-primary)]">{cohort.cohort}</p>
                    <p className="mt-1 text-[12px] text-[var(--text-tertiary)]">{cohort.action}</p>
                  </div>
                  <StatusBadge label={cohort.drift} tone={cohort.tone} />
                </div>
                <p className="mt-2 font-mono text-[11px] text-[var(--text-muted)]">{cohort.volume}</p>
              </div>
            ))}
          </div>
        </Surface>
      </div>

      <Surface className="overflow-hidden">
        <PanelTitle icon={BrainCircuit} title="Model operating memo" detail="Where AI belongs in the institution." />
        <div className="grid gap-0 divide-y divide-[var(--border-card)] lg:grid-cols-3 lg:divide-x lg:divide-y-0">
          {[
            {
              label: "Structured credit prediction",
              value: "Gradient boosting remains the champion for tabular underwriting decisions.",
            },
            {
              label: "LLM role",
              value: "LLMs parse unstructured evidence and produce reviewer summaries, not silent approvals.",
            },
            {
              label: "Synthetic data",
              value: "Rare-event fraud and stress cohorts can be simulated without leaking PII.",
            },
          ].map((item) => (
            <div key={item.label} className="p-4">
              <p className="text-[13px] font-semibold text-[var(--text-primary)]">{item.label}</p>
              <p className="mt-2 text-[12px] leading-relaxed text-[var(--text-tertiary)]">{item.value}</p>
            </div>
          ))}
        </div>
      </Surface>
    </SectionShell>
  );
}

function GovernanceView() {
  return (
    <SectionShell
      eyebrow="Governance"
      title="Compliance is not a side panel. It is the right to sell."
      description="FREE-AI, DPDP, SOC2/ISO, role access, API scopes, retention, and credit pricing controls are presented as operational controls instead of legal footnotes."
      action={<StatusBadge label="Audit-ready" tone="good" />}
    >
      <div className="grid gap-5 lg:grid-cols-4">
        {complianceControls.map((control) => (
          <Surface key={control.label} className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[13px] font-semibold text-[var(--text-primary)]">{control.label}</p>
                <p className={cn("mt-2 text-[20px] font-semibold tracking-tight", toneClass(control.tone).text)}>
                  {control.value}
                </p>
              </div>
              <HealthDot tone={control.tone} />
            </div>
            <p className="mt-3 text-[12px] leading-relaxed text-[var(--text-tertiary)]">{control.detail}</p>
          </Surface>
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Surface className="overflow-hidden">
          <PanelTitle icon={KeyRound} title="API scopes" detail="Enterprise procurement wants explicit blast-radius control." />
          <div className="divide-y divide-[var(--border-card)]">
            {apiKeyPlaceholders.map((key) => (
              <div key={key.label} className="flex items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-[var(--text-primary)]">{key.label}</p>
                  <p className="mt-1 truncate font-mono text-[11px] text-[var(--text-muted)]">{key.value}</p>
                </div>
                <StatusBadge label={key.status} tone="neutral" />
              </div>
            ))}
          </div>
        </Surface>

        <Surface className="overflow-hidden">
          <PanelTitle icon={UsersRound} title="Role access" detail="Human and agent access are governed together." />
          <div className="divide-y divide-[var(--border-card)]">
            {roleAccess.map((role) => (
              <div key={role.role} className="p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[13px] font-semibold text-[var(--text-primary)]">{role.role}</p>
                  <span className="font-mono text-[11px] text-[var(--text-muted)]">{role.users}</span>
                </div>
                <p className="mt-1 text-[12px] text-[var(--text-tertiary)]">{role.access}</p>
              </div>
            ))}
          </div>
        </Surface>
      </div>

      <Surface className="overflow-hidden">
        <PanelTitle icon={WalletCards} title="Hybrid credit pricing preview" detail="Baseline subscription plus usage credits for compute-heavy decisions." />
        <div className="grid gap-0 divide-y divide-[var(--border-card)] lg:grid-cols-4 lg:divide-x lg:divide-y-0">
          {[
            { label: "KYC data pull", value: "1 credit", detail: "Identity and basic entity enrichment." },
            { label: "AA cash-flow analysis", value: "5 credits", detail: "Consent packet, volatility, obligations, income stability." },
            { label: "Agentic decision run", value: "20 credits", detail: "Policy battery, model score, rationale, and action memo." },
            { label: "Audit export", value: "Included", detail: "Reviewer notes, evidence hashes, SHAP, LIME, policy version." },
          ].map((item) => (
            <div key={item.label} className="p-4">
              <p className="text-[13px] font-semibold text-[var(--text-primary)]">{item.label}</p>
              <p className="mt-2 font-mono text-[15px] font-semibold text-primary">{item.value}</p>
              <p className="mt-2 text-[12px] leading-relaxed text-[var(--text-tertiary)]">{item.detail}</p>
            </div>
          ))}
        </div>
      </Surface>
    </SectionShell>
  );
}

function DataFabricView() {
  return (
    <SectionShell
      eyebrow="Data Fabric"
      title="Modernize the lending brain without replacing the bank core."
      description="ArgentNorth sits as an intelligence and orchestration layer over fragmented systems, using event-driven integrations, semantic mapping, and audited writeback."
      action={<StatusBadge label="No core replacement" tone="good" />}
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
        <Surface className="overflow-hidden">
          <PanelTitle icon={DatabaseZap} title="Connector estate" detail="Event-driven rails with explicit permissions and latency." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left">
              <thead>
                <tr className="border-b border-[var(--border-card)] bg-[var(--surface-secondary)]/55 text-[11px] uppercase tracking-[0.12em] text-[var(--text-tertiary)]">
                  <th className="px-3 py-2.5 font-semibold">Connector</th>
                  <th className="px-3 py-2.5 font-semibold">Source</th>
                  <th className="px-3 py-2.5 font-semibold">Event</th>
                  <th className="px-3 py-2.5 font-semibold">Control</th>
                  <th className="px-3 py-2.5 font-semibold">Latency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-card)]">
                {fabricConnectors.map((connector) => (
                  <tr key={connector.name} className="text-[13px] text-[var(--text-secondary)]">
                    <td className="px-3 py-3 font-semibold text-[var(--text-primary)]">
                      <span className="inline-flex items-center gap-2">
                        <LivePulseDot tone={connector.tone} />
                        {connector.name}
                      </span>
                    </td>
                    <td className="px-3 py-3">{connector.source}</td>
                    <td className="px-3 py-3">{connector.event}</td>
                    <td className="px-3 py-3">{connector.control}</td>
                    <td className="px-3 py-3 font-mono text-[12px]">{connector.latency}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Surface>

        <Surface className="overflow-hidden">
          <PanelTitle icon={GitBranch} title="Semantic layer" detail="Make data mean the same thing across the institution." />
          <div className="space-y-3 p-4">
            {commandSignals.map((signal) => (
              <div key={signal.label} className="rounded-md border border-[var(--border-card)] p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[13px] font-semibold text-[var(--text-primary)]">{signal.label}</p>
                    <p className="mt-1 font-mono text-[11px] text-[var(--text-muted)]">{signal.value}</p>
                  </div>
                  <StatusBadge label={signal.status} tone={signal.tone} />
                </div>
              </div>
            ))}
          </div>
        </Surface>
      </div>

      <Surface className="overflow-hidden">
        <PanelTitle icon={Network} title="Object lineage" detail="From applicant evidence to reviewer action." />
        <div className="p-4">
          <EvidenceFlowGraph nodes={evidenceGraphNodes} />
        </div>
      </Surface>
    </SectionShell>
  );
}

function ActiveSection({
  active,
  onNavigate,
}: {
  active: ArgentSectionId;
  onNavigate: (section: ArgentSectionId) => void;
}) {
  if (active === "execution") return <ExecutionBookView onNavigate={onNavigate} />;
  if (active === "decision") return <DecisionObjectView />;
  if (active === "intake") return <EvidenceIntakeView />;
  if (active === "policy") return <PolicyStudioView />;
  if (active === "risk") return <ModelRiskOpsView />;
  if (active === "compliance") return <GovernanceView />;
  if (active === "integrations") return <DataFabricView />;
  return <CommandCenterView onNavigate={onNavigate} />;
}

export function ArgentNorthOS() {
  const [active, setActive] = useState<ArgentSectionId>("command");

  return (
    <div className="argentnorth-os min-h-screen bg-[var(--background)] text-[var(--text-primary)]">
      <div className="flex min-h-screen">
        <ShellSidebar active={active} onNavigate={setActive} />
        <div className="min-w-0 flex-1">
          <TopBar active={active} />
          <NavRail active={active} onNavigate={setActive} compact />
          <main className="px-4 py-5 sm:px-6 lg:py-7 xl:px-8">
            <PageTransition id={active}>
              <ActiveSection active={active} onNavigate={setActive} />
            </PageTransition>
          </main>
        </div>
      </div>
    </div>
  );
}
