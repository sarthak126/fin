"use client";

import { useState, useEffect, useRef } from "react";
import { motion, useInView } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Banknote,
  BookOpenCheck,
  BrainCircuit,
  Building2,
  CheckCircle2,
  ClipboardCheck,
  ClipboardList,
  Command,
  DatabaseZap,
  Eye,
  FileCheck2,
  FileText,
  Filter,
  Gauge,
  GitBranch,
  KeyRound,
  Landmark,
  LockKeyhole,
  Network,
  Radio,
  ReceiptText,
  Scale,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TrendingUp,
  UploadCloud,
  UsersRound,
  WalletCards,
  Zap,
} from "lucide-react";

import { ThemeToggle } from "@/components/ThemeToggle";
import {
  DataTile,
  MetricCard,
  PageHeader,
  ProgressBar,
  SectionHeading,
  StatusBadge,
  Surface,
  TimelineRow,
  toneClass,
} from "@/components/argentnorth/prototype-ui";
import {
  AnimatedNumber,
  AreaChart,
  CommandPalette,
  EvidenceFlowGraph,
  GaugeArc,
  PageTransition,
  Sparkline,
  WaterfallChart,
} from "@/components/argentnorth/viz-components";
import { Button } from "@/components/ui/button";
import { HeroDecisionFlow } from "@/components/ui/hero-decision-flow";
import { cn } from "@/lib/utils";
import type { RiskTone } from "@/lib/argentnorth-prototype";
import {
  apiKeyPlaceholders,
  agenticMoves,
  boardMetrics,
  capitalRails,
  cohortWatchlist,
  commandEventStream,
  commandSignals,
  complianceControls,
  dossier,
  decisionObjects,
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
  prototypeSections,
  queueCases,
  roleAccess,
  type PrototypeDecision,
  type PrototypeSectionId,
} from "@/lib/argentnorth-ui-prototype";

const sectionIcons: Record<PrototypeSectionId, LucideIcon> = {
  overview: Sparkles,
  command: Command,
  queue: ClipboardList,
  intake: UploadCloud,
  dossier: FileText,
  modelOps: BrainCircuit,
  compliance: ShieldCheck,
};

const sectionEyebrows: Record<PrototypeSectionId, string> = {
  overview: "Prototype Surface",
  command: "Command Center",
  queue: "Case Queue",
  intake: "Evidence Intake",
  dossier: "Case Dossier",
  modelOps: "Model/Risk Ops",
  compliance: "Compliance/Settings",
};

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

function ShellNav({
  active,
  onNavigate,
  compact = false,
}: {
  active: PrototypeSectionId;
  onNavigate: (section: PrototypeSectionId) => void;
  compact?: boolean;
}) {
  return (
    <nav
      aria-label="Prototype sections"
      className={cn(
        compact
          ? "flex gap-1 overflow-x-auto border-y border-[var(--border-card)] bg-[var(--surface-raised)] px-4 py-2 xl:hidden"
          : "flex flex-col gap-px"
      )}
    >
      {prototypeSections.map((item) => {
        const Icon = sectionIcons[item.id];
        const isActive = active === item.id;

        return (
          <button
            key={item.id}
            type="button"
            aria-pressed={isActive}
            onClick={() => onNavigate(item.id)}
            className={cn(
              "group inline-flex items-center gap-2.5 rounded-md text-left text-[13px] transition-all duration-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
              compact
                ? "h-8 shrink-0 px-3"
                : "h-9 w-full px-3",
              isActive
                ? "bg-[var(--surface-secondary)]/80 font-medium text-[var(--text-primary)]"
                : "font-normal text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
            )}
          >
            <Icon className={cn("h-4 w-4 shrink-0", isActive ? "text-[var(--text-primary)]" : "text-[var(--text-muted)] group-hover:text-[var(--text-tertiary)]")} />
            <span className="truncate">{compact ? item.shortLabel : item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

function PrototypeShellFrame({
  active,
  children,
  onNavigate,
}: {
  active: PrototypeSectionId;
  children: React.ReactNode;
  onNavigate: (section: PrototypeSectionId) => void;
}) {
  const activeSection = prototypeSections.find((section) => section.id === active) ?? prototypeSections[0];
  const ActiveIcon = sectionIcons[active];

  return (
    <div className="min-h-screen bg-background text-foreground">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[240px] border-r border-[var(--border-card)] bg-[var(--surface-raised)] xl:flex xl:flex-col">
        <div className="flex h-[52px] items-center px-5">
          <button
            type="button"
            onClick={() => onNavigate("overview")}
            className="group flex min-w-0 items-center gap-2.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          >
            <img src="/ag.svg" alt="ArgentNorth" className="h-8 w-auto shrink-0 dark:invert" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 pt-2 pb-4">
          <ShellNav active={active} onNavigate={onNavigate} />
        </div>

        <div className="border-t border-[var(--border-card)] px-5 py-3">
          <ThemeToggle />
        </div>
      </aside>

      <div className="xl:pl-[240px]">
        <header className="sticky top-0 z-20 border-b border-[var(--border-card)] bg-[var(--surface-glass)] backdrop-blur-xl">
          <div className="flex h-[52px] items-center justify-between gap-4 px-5 md:px-8 lg:px-10">
            <div className="flex min-w-0 items-center gap-3 xl:hidden">
              <ActiveIcon className="h-4 w-4 text-[var(--text-muted)]" />
              <h1 className="truncate text-[14px] font-medium text-[var(--text-primary)]">{activeSection.label}</h1>
            </div>
            <div className="hidden xl:block" />
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => {
                  const evt = new KeyboardEvent('keydown', { key: 'k', metaKey: true, ctrlKey: true });
                  window.dispatchEvent(evt);
                }}
                className="hidden items-center gap-2 rounded-md border border-[var(--border-card)] px-3 py-1.5 text-[13px] text-[var(--text-muted)] transition-colors hover:border-[var(--border-card-hover)] hover:text-[var(--text-secondary)] sm:inline-flex"
              >
                <Search className="h-3.5 w-3.5" />
                <span>Search</span>
                <kbd className="ml-2 rounded border border-[var(--border-card)] bg-[var(--surface-secondary)]/60 px-1.5 py-0.5 font-mono text-[10px] text-[var(--text-muted)]">⌘K</kbd>
              </button>
            </div>
          </div>
          <ShellNav active={active} onNavigate={onNavigate} compact />
        </header>

        <main className="mx-auto flex max-w-[1320px] flex-col gap-10 px-5 py-10 md:px-8 lg:px-10 lg:py-12">
          {children}
        </main>
      </div>
    </div>
  );
}

function BoardMetricStrip({ compact = false }: { compact?: boolean }) {
  return (
    <div className={cn("grid overflow-hidden rounded-md border border-[var(--border-card)]", compact ? "grid-cols-2" : "md:grid-cols-4")}>
      {boardMetrics.map((metric) => {
        const style = toneClass(metric.tone);
        const spark = metricSparklines[metric.label];

        return (
          <div
            key={metric.label}
            className="min-w-0 border-b border-[var(--border-subtle)] bg-[var(--surface-raised)] px-5 py-4 last:border-b-0 md:border-b-0 md:border-r md:last:border-r-0"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="truncate text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--text-muted)]">
                {metric.label}
              </p>
              {spark ? <Sparkline data={spark} width={52} height={18} tone={metric.tone} /> : null}
            </div>
            <p className="mt-2.5 truncate font-mono text-[20px] font-semibold leading-none tracking-[-0.01em] text-[var(--text-primary)] tabular-nums">
              <AnimatedNumber value={metric.value} />
            </p>
            <p className={cn("mt-2 truncate text-[12px] font-medium", style.text)}>{metric.detail}</p>
          </div>
        );
      })}
    </div>
  );
}

function CapitalRailsPanel() {
  return (
    <Surface className="overflow-hidden">
      <div className="border-b border-[var(--border-card)] px-5 py-4">
        <SectionHeading
          icon={Banknote}
          title="Capital Rails"
          description="Credit demand, risk appetite, and policy authority by product rail."
        />
      </div>
      <div className="divide-y divide-[var(--border-subtle)] px-5">
        {capitalRails.map((rail) => {
          const style = toneClass(rail.tone);

          return (
            <div key={rail.label} className="grid gap-3 py-3.5 md:grid-cols-[0.85fr_0.55fr_1fr] md:items-center">
              <div className="min-w-0">
                <p className="truncate text-[13px] font-medium text-[var(--text-primary)]">{rail.label}</p>
                <p className="mt-0.5 truncate text-[12px] text-[var(--text-muted)]">{rail.detail}</p>
              </div>
              <p className="font-mono text-[14px] font-semibold text-[var(--text-primary)] tabular-nums">{rail.value}</p>
              <ProgressBar value={rail.progress} tone={rail.tone} className="h-1.5" />
            </div>
          );
        })}
      </div>
    </Surface>
  );
}

function DecisionObjectTable({ compact = false }: { compact?: boolean }) {
  return (
    <Surface className="overflow-hidden">
      <div className="border-b border-[var(--border-card)] px-5 py-4">
        <SectionHeading
          icon={Network}
          title="Decision Fabric Objects"
          description="Every decision is composed of governed objects, controls, and action authority."
        />
      </div>
      <div className="overflow-x-auto">
        <div className={cn("min-w-[860px]", compact && "min-w-[760px]")}>
          <div className="grid grid-cols-[0.9fr_1fr_0.45fr_0.85fr_0.7fr] border-b border-[var(--border-card)] bg-[var(--surface-secondary)]/35 px-5 py-2.5 text-[11px] font-medium uppercase tracking-[0.06em] text-[var(--text-muted)]">
            <div>Object</div>
            <div>Source</div>
            <div>Latency</div>
            <div>Control</div>
            <div>Authority</div>
          </div>
          {decisionObjects.map((object) => {
            const style = toneClass(object.tone);

            return (
              <div
                key={object.object}
                className="grid grid-cols-[0.9fr_1fr_0.45fr_0.85fr_0.7fr] border-b border-[var(--border-subtle)] px-5 py-3 last:border-b-0"
              >
                <div className="flex min-w-0 items-center gap-2">
                  <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", style.dot)} />
                  <span className="truncate text-[13px] font-medium text-[var(--text-primary)]">{object.object}</span>
                </div>
                <p className="truncate text-[13px] text-[var(--text-secondary)]">{object.source}</p>
                <p className="font-mono text-[12px] font-medium text-[var(--text-primary)]">{object.latency}</p>
                <p className={cn("truncate text-[12px] font-medium", style.text)}>{object.control}</p>
                <p className="truncate text-[12px] text-[var(--text-tertiary)]">{object.authority}</p>
              </div>
            );
          })}
        </div>
      </div>
    </Surface>
  );
}

function AgenticMovesPanel() {
  return (
    <Surface className="overflow-hidden">
      <div className="border-b border-[var(--border-card)] px-5 py-4">
        <SectionHeading
          icon={Sparkles}
          title="Agentic Control Memo"
          description="Recommendations are explicit, scoped, and gated by authority."
        />
      </div>
      <div className="divide-y divide-[var(--border-subtle)] px-5">
        {agenticMoves.map((move) => {
          const style = toneClass(move.tone);

          return (
            <div key={move.title} className="py-3.5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[13px] font-medium text-[var(--text-primary)]">{move.title}</p>
                  <p className="mt-1.5 text-[12px] leading-relaxed text-[var(--text-tertiary)]">{move.detail}</p>
                </div>
                <StatusBadge label={move.authority} tone={move.tone} />
              </div>
              <p className={cn("mt-1.5 text-[12px] font-medium", style.text)}>{move.impact}</p>
            </div>
          );
        })}
      </div>
    </Surface>
  );
}

/* ═══════════════════════════════════════════════════════════════
   LANDING PAGE — Full-width, no sidebar, inspired by
   Stripe (gradient text, big numbers), Mercury (whitespace, serif feel),
   Ramp (bold product cards), Palantir (enterprise authority)
   ═══════════════════════════════════════════════════════════════ */

const pipelineStages = [
  { id: "ingest", label: "Evidence Ingestion", sub: "AA · Bureau · GST · Bank" },
  { id: "score", label: "Risk Scoring", sub: "XGBoost · SHAP drivers" },
  { id: "policy", label: "Policy Engine", sub: "Rule battery · Fairness" },
  { id: "decide", label: "Decision", sub: "Approve · Review · Reject" },
  { id: "audit", label: "Audit Seal", sub: "Immutable · Full lineage" },
];

const trustArchitecture = [
  { title: "End-to-end encryption", detail: "All data encrypted at rest and in transit. Zero plaintext persistence for sensitive borrower evidence." },
  { title: "Immutable audit trail", detail: "Every decision, override, and policy change captured with full lineage. Tamper-proof. Export-ready." },
  { title: "SHAP explainability", detail: "Every credit decision ships with machine-readable reason codes. Adverse action letters auto-generated." },
  { title: "Consent-first data", detail: "Account Aggregator flows are consent-gated. Purpose-limited. Retention-scoped. Borrower-revocable." },
  { title: "Role-based access control", detail: "Operator, reviewer, and admin roles with scoped authority. Capital actions require human sign-off." },
  { title: "Governed automation", detail: "Agentic recommendations are read-only. No autonomous writes. Policy changes require dual approval." },
  { title: "Drift detection", detail: "PSI monitoring across all scoring cohorts. Automated alerts before portfolio impact materializes." },
  { title: "Fairness monitoring", detail: "Continuous bias checks across protected dimensions. Disparate impact ratios tracked per model version." },
];

function useCountUp(target: number, duration = 2000, startOnView = true) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref as React.RefObject<Element>, { once: true });
  useEffect(() => {
    if (!startOnView || !inView) return;
    let start = 0;
    const step = target / (duration / 16);
    const timer = setInterval(() => {
      start += step;
      if (start >= target) { setCount(target); clearInterval(timer); }
      else setCount(Math.floor(start));
    }, 16);
    return () => clearInterval(timer);
  }, [inView, target, duration, startOnView]);
  return { count, ref };
}

const heroEase = [0.16, 1, 0.3, 1] as [number, number, number, number];

const heroCardVariants = {
  hidden: { opacity: 0, y: 22, scale: 0.96, filter: "blur(5px)" },
  visible: (i: number) => ({
    opacity: 1, y: 0, scale: 1, filter: "blur(0px)",
    transition: { delay: 0.35 + i * 0.16, duration: 0.9, ease: heroEase },
  }),
};

const heroLineEase = [0.25, 0.1, 0.25, 1] as [number, number, number, number];

const dataSources = [
  { icon: Radio, label: "AA Consent", sub: "Account Aggregator", state: "Verified", priority: "core" },
  { icon: Building2, label: "Bureau Data", sub: "Credit Bureau", state: "Matched", priority: "support" },
  { icon: Landmark, label: "Bank Statement", sub: "Cash Flow", state: "Primary", priority: "core" },
  { icon: ReceiptText, label: "GST Data", sub: "Tax Signals", state: "Stable", priority: "core" },
  { icon: ShieldCheck, label: "KYC / AML", sub: "Identity Check", state: "Cleared", priority: "support" },
  { icon: Scale, label: "Policy Rules", sub: "Risk Policies", state: "Gated", priority: "core" },
];

const primaryFlowSourceIndexes = [0, 2, 3, 5];

const leftFlowPaths = [
  { source: 0, d: "M 238 104 C 315 104 348 238 434 304", delay: 0.45 },
  { source: 2, d: "M 238 260 C 318 260 352 288 434 308", delay: 0.65 },
  { source: 3, d: "M 238 338 C 315 338 352 328 434 314", delay: 0.85 },
  { source: 5, d: "M 238 496 C 318 496 350 388 434 318", delay: 1.05 },
];

const rightFlowPaths = [
  { key: "risk", d: "M 466 310 C 548 310 570 126 646 126", delay: 1.1, tone: "blue" },
  { key: "decision", d: "M 466 310 C 560 310 572 498 646 498", delay: 1.35, tone: "green" },
];

const heroCardShadow = "0 14px 34px rgba(15, 23, 42, 0.08), 0 1px 0 rgba(255, 255, 255, 0.9) inset";
const heroSoftCardShadow = "0 10px 26px rgba(15, 23, 42, 0.06), 0 1px 0 rgba(255, 255, 255, 0.88) inset";
const approvalCardShadow = "0 20px 48px rgba(5, 150, 105, 0.18), 0 1px 0 rgba(255, 255, 255, 0.95) inset";

function HeroVisual() {
  const containerRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(containerRef as React.RefObject<Element>, { once: true, margin: "-80px" });
  const { count: riskScoreCount, ref: riskScoreRef } = useCountUp(24, 1800);
  const [hoveredSource, setHoveredSource] = useState<number | null>(null);
  const [signalIndex, setSignalIndex] = useState(0);
  const [pulsing, setPulsing] = useState(false);
  const activeSource = hoveredSource ?? primaryFlowSourceIndexes[signalIndex];

  useEffect(() => {
    if (!isInView) return;
    const interval = setInterval(() => {
      setPulsing(true);
      setSignalIndex((current) => (current + 1) % primaryFlowSourceIndexes.length);
      setTimeout(() => setPulsing(false), 1500);
    }, 5200);
    return () => clearInterval(interval);
  }, [isInView]);

  return (
    <div
      ref={containerRef}
      className="relative w-full overflow-hidden rounded-xl border border-slate-950/10 p-4 shadow-[0_24px_70px_rgba(15,23,42,0.12)]"
      style={{
        background:
          "linear-gradient(135deg, rgba(248,250,252,0.98) 0%, rgba(239,246,255,0.92) 46%, rgba(236,253,245,0.78) 100%)",
      }}
      aria-label="ArgentNorth decision pipeline visualization"
    >
      <motion.div
        className="pointer-events-none absolute inset-0"
        initial={{ opacity: 0 }}
        animate={isInView ? { opacity: 1 } : {}}
        transition={{ duration: 1.6, ease: heroEase }}
      >
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(circle at 51% 50%, rgba(26,86,219,0.13), rgba(26,86,219,0.045) 31%, transparent 58%), linear-gradient(180deg, rgba(255,255,255,0.56), rgba(255,255,255,0.18))",
          }}
        />
        <div
          className="absolute inset-x-6 top-6 h-px"
          style={{ background: "linear-gradient(90deg, transparent, rgba(26,86,219,0.26), transparent)" }}
        />
      </motion.div>

      <div className="relative grid min-h-[610px] grid-cols-[minmax(190px,0.9fr)_minmax(220px,0.95fr)_minmax(240px,1fr)] items-center gap-5">
        {/* SVG Connection Lines — Full grid overlay with proper viewBox */}
        <svg
          className="absolute inset-0 h-full w-full pointer-events-none z-0"
          viewBox="0 0 900 620"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="argent-flow-blue" x1="0%" x2="100%" y1="0%" y2="0%">
              <stop offset="0%" stopColor="rgba(30, 64, 175, 0.08)" />
              <stop offset="50%" stopColor="rgba(37, 99, 235, 0.72)" />
              <stop offset="100%" stopColor="rgba(14, 165, 233, 0.22)" />
            </linearGradient>
            <linearGradient id="argent-flow-green" x1="0%" x2="100%" y1="0%" y2="0%">
              <stop offset="0%" stopColor="rgba(37, 99, 235, 0.1)" />
              <stop offset="58%" stopColor="rgba(5, 150, 105, 0.78)" />
              <stop offset="100%" stopColor="rgba(16, 185, 129, 0.4)" />
            </linearGradient>
            <filter id="argent-flow-shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="8" stdDeviation="8" floodColor="rgba(37,99,235,0.18)" />
            </filter>
          </defs>

          {leftFlowPaths.map((path) => {
            const isActive = activeSource === path.source;
            return (
              <g key={path.source}>
                <motion.path
                  d={path.d}
                  fill="none"
                  stroke="rgba(30, 64, 175, 0.2)"
                  strokeWidth="2"
                  vectorEffect="non-scaling-stroke"
                  strokeLinecap="round"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={isInView ? { pathLength: 1, opacity: isActive ? 0.52 : 0.18 } : {}}
                  transition={{ delay: path.delay, duration: 1.4, ease: heroLineEase }}
                />
                <motion.path
                  d={path.d}
                  fill="none"
                  stroke="url(#argent-flow-blue)"
                  strokeWidth={isActive ? "3" : "2.25"}
                  vectorEffect="non-scaling-stroke"
                  strokeLinecap="round"
                  strokeDasharray="12 28"
                  filter={isActive ? "url(#argent-flow-shadow)" : undefined}
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={isInView ? {
                    pathLength: 1,
                    opacity: isActive ? [0.35, 0.86, 0.35] : 0.14,
                    strokeDashoffset: [40, 0],
                  } : {}}
                  transition={{
                    pathLength: { delay: path.delay + 0.1, duration: 1.5, ease: heroLineEase },
                    opacity: { duration: 4.8, repeat: Infinity, ease: "easeInOut" },
                    strokeDashoffset: { duration: 5.6, repeat: Infinity, ease: "linear" },
                  }}
                />
              </g>
            );
          })}

          {rightFlowPaths.map((path) => (
            <g key={path.key}>
              <motion.path
                d={path.d}
                fill="none"
                stroke={path.tone === "green" ? "rgba(5, 150, 105, 0.2)" : "rgba(30, 64, 175, 0.2)"}
                strokeWidth="2"
                vectorEffect="non-scaling-stroke"
                strokeLinecap="round"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={isInView ? { pathLength: 1, opacity: path.key === "decision" ? 0.42 : 0.24 } : {}}
                transition={{ delay: path.delay, duration: 1.6, ease: heroLineEase }}
              />
              <motion.path
                d={path.d}
                fill="none"
                stroke={path.tone === "green" ? "url(#argent-flow-green)" : "url(#argent-flow-blue)"}
                strokeWidth={path.key === "decision" ? "3.25" : "2.5"}
                vectorEffect="non-scaling-stroke"
                strokeLinecap="round"
                strokeDasharray="14 30"
                filter={path.key === "decision" ? "url(#argent-flow-shadow)" : undefined}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={isInView ? { pathLength: 1, opacity: path.key === "decision" ? [0.46, 0.9, 0.46] : 0.42, strokeDashoffset: [44, 0] } : {}}
                transition={{
                  pathLength: { delay: path.delay + 0.1, duration: 1.7, ease: heroLineEase },
                  opacity: { duration: 5.2, repeat: Infinity, ease: "easeInOut" },
                  strokeDashoffset: { duration: 6.4, repeat: Infinity, ease: "linear" },
                }}
              />
            </g>
          ))}
        </svg>

        {/* LEFT — Data Source Cards */}
        <div className="relative z-[1] flex flex-col gap-3">
          {dataSources.map((source, i) => {
            const Icon = source.icon;
            const isActive = activeSource === i;
            const isCore = source.priority === "core";
            return (
              <motion.div
                key={source.label}
                custom={i}
                variants={heroCardVariants}
                initial="hidden"
                animate={isInView ? "visible" : "hidden"}
                onHoverStart={() => setHoveredSource(i)}
                onHoverEnd={() => setHoveredSource(null)}
                className={cn(
                  "group relative flex items-center gap-3 rounded-lg border bg-white/90 px-3.5 py-3 backdrop-blur-sm transition-all duration-300",
                  isActive
                    ? "border-blue-600/35"
                    : isCore
                      ? "border-slate-950/10"
                      : "border-slate-950/[0.07] opacity-[0.82]"
                )}
                style={{ boxShadow: isActive ? heroCardShadow : heroSoftCardShadow }}
              >
                <div className={cn(
                  "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg transition-colors duration-300",
                  isActive ? "bg-blue-700 text-white" : isCore ? "bg-blue-50 text-blue-700" : "bg-slate-100 text-slate-500"
                )}>
                  <Icon className="h-[18px] w-[18px]" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[13.5px] font-semibold leading-tight text-slate-950">{source.label}</p>
                  <div className="mt-1 flex items-center gap-1.5">
                    <span className={cn("h-1.5 w-1.5 rounded-full", isActive ? "bg-blue-700" : isCore ? "bg-blue-300" : "bg-slate-300")} />
                    <p className="text-[12px] leading-snug text-slate-600">{source.sub}</p>
                  </div>
                </div>
                <motion.div
                  className={cn(
                    "absolute -right-[7px] top-1/2 h-[12px] w-[12px] -translate-y-1/2 rounded-full border-2 bg-white",
                    isActive ? "border-blue-700" : "border-slate-300"
                  )}
                  animate={isActive || pulsing ? { scale: [1, 1.3, 1] } : { scale: 1 }}
                  transition={{ duration: 1.1, ease: "easeInOut" }}
                />
              </motion.div>
            );
          })}
        </div>

        {/* CENTER — Hub */}
        <div className="relative z-[1] flex min-h-[520px] flex-col items-center justify-center">
          <motion.div
            className="relative z-10 flex h-[230px] w-[230px] items-center justify-center rounded-full border border-blue-700/15 bg-white/45 shadow-[0_22px_70px_rgba(30,64,175,0.12)] backdrop-blur-sm"
            initial={{ opacity: 0, scale: 0.5 }}
            animate={isInView ? { opacity: 1, scale: 1 } : {}}
            transition={{ delay: 0.25, duration: 1, ease: heroEase }}
          >
            {/* Outer pulse rings — rounded-square */}
            <motion.div
              className="absolute inset-[-22px] rounded-full border border-blue-700/10"
              animate={pulsing ? { scale: [1, 1.08, 1], opacity: [0.5, 0.12, 0.5] } : { opacity: 0.36 }}
              transition={{ duration: 2, ease: "easeInOut" }}
            />
            <motion.div
              className="absolute inset-[18px] rounded-full border border-blue-700/20"
              animate={{ rotate: 360 }}
              transition={{ duration: 28, repeat: Infinity, ease: "linear" }}
              style={{
                background:
                  "conic-gradient(from 180deg, rgba(37,99,235,0), rgba(37,99,235,0.18), rgba(5,150,105,0.16), rgba(37,99,235,0))",
              }}
            />
            <motion.div
              className="relative flex h-[158px] w-[158px] flex-col items-center justify-center rounded-full border border-blue-700/25 bg-white text-center"
              animate={{ boxShadow: ["0 16px 42px rgba(26,86,219,0.14)", "0 20px 58px rgba(26,86,219,0.22)", "0 16px 42px rgba(26,86,219,0.14)"] }}
              transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            >
              <img src="/ag.svg" alt="ArgentNorth" className="h-12 w-auto" />
            </motion.div>
          </motion.div>

          {/* Label below hub */}
          <motion.div
            className="mt-5 flex items-center gap-2 rounded-full border border-blue-700/15 bg-white/80 px-3 py-1.5 shadow-[0_8px_20px_rgba(15,23,42,0.06)]"
            initial={{ opacity: 0, y: 8 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ delay: 0.95, duration: 0.7, ease: heroEase }}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-600" />
            <p className="text-[12px] font-semibold text-slate-700">Governed intelligence layer</p>
          </motion.div>
        </div>

        {/* RIGHT — Output Cards */}
        <div className="relative z-[1] flex flex-col gap-3">
          {/* Risk Score Card */}
          <motion.div
            custom={1}
            variants={heroCardVariants}
            initial="hidden"
            animate={isInView ? "visible" : "hidden"}
            className="relative rounded-lg border border-slate-950/10 bg-white/[0.92] p-4 backdrop-blur-sm"
            style={{ boxShadow: heroCardShadow }}
          >
            <motion.div className="absolute -left-[7px] top-1/2 h-[12px] w-[12px] -translate-y-1/2 rounded-full border-2 border-blue-700/50 bg-white" />
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-[13px] font-semibold text-slate-700">Risk score</p>
                <p className="mt-2 text-[38px] font-bold leading-none tracking-[-0.04em] text-slate-950">
                  <span ref={riskScoreRef}>{riskScoreCount}</span>
                </p>
                <motion.div
                  className="mt-2 flex items-center gap-1.5"
                  initial={{ opacity: 0 }}
                  animate={isInView ? { opacity: 1 } : {}}
                  transition={{ delay: 2 }}
                >
                  <span className="h-2 w-2 rounded-full bg-emerald-600" />
                  <span className="text-[12px] font-semibold text-emerald-700">Low risk</span>
                </motion.div>
              </div>
              <GaugeArc score={24} size={78} />
            </div>
          </motion.div>

          {/* SHAP Drivers Card */}
          <motion.div
            custom={2}
            variants={heroCardVariants}
            initial="hidden"
            animate={isInView ? "visible" : "hidden"}
            className="relative rounded-lg border border-slate-950/[0.08] bg-white/[0.86] p-4 backdrop-blur-sm"
            style={{ boxShadow: heroSoftCardShadow }}
          >
            <motion.div className="absolute -left-[7px] top-1/2 h-[12px] w-[12px] -translate-y-1/2 rounded-full border-2 border-slate-300 bg-white" />
            <div className="flex items-center justify-between gap-3">
              <p className="text-[13px] font-semibold text-slate-700">SHAP drivers</p>
              <span className="text-[11px] font-semibold text-slate-500">3 factors</span>
            </div>
            <div className="mt-3 space-y-2.5">
              {[
                { label: "GST stable", value: "+0.38", width: 76, color: "bg-emerald-600" },
                { label: "Low bounce", value: "+0.21", width: 56, color: "bg-emerald-500" },
                { label: "High DTI", value: "-0.16", width: 38, color: "bg-amber-500" },
              ].map((bar, idx) => (
                <div key={bar.label} className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 flex-1">
                    <span className="w-[74px] text-[12px] font-medium text-slate-600">{bar.label}</span>
                    <div className="h-[7px] flex-1 overflow-hidden rounded-full bg-slate-200/80">
                      <motion.div
                        className={cn("h-full rounded-full", bar.color)}
                        initial={{ width: 0 }}
                        animate={isInView ? { width: `${bar.width}%` } : {}}
                        transition={{ delay: 1.6 + idx * 0.16, duration: 1, ease: heroEase }}
                      />
                    </div>
                  </div>
                  <span className="w-[42px] text-right font-mono text-[11.5px] font-semibold text-slate-700">{bar.value}</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Policy Decision Card */}
          <motion.div
            custom={3}
            variants={heroCardVariants}
            initial="hidden"
            animate={isInView ? "visible" : "hidden"}
            className="relative rounded-lg border border-slate-950/[0.08] bg-white/[0.88] p-4 backdrop-blur-sm"
            style={{ boxShadow: heroSoftCardShadow }}
          >
            <motion.div className="absolute -left-[7px] top-1/2 h-[12px] w-[12px] -translate-y-1/2 rounded-full border-2 border-slate-300 bg-white" />
            <p className="text-[13px] font-semibold text-slate-700">Policy decision</p>
            <p className="mt-1.5 text-[17px] font-bold text-slate-950">Policy pass</p>
            <motion.div
              className="mt-2 flex items-center gap-1.5"
              initial={{ opacity: 0 }}
              animate={isInView ? { opacity: 1 } : {}}
              transition={{ delay: 2.2 }}
            >
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <span className="text-[12px] font-semibold text-emerald-700">All checks passed</span>
            </motion.div>
          </motion.div>

          {/* Final Decision Card */}
          <motion.div
            custom={4}
            variants={heroCardVariants}
            initial="hidden"
            animate={isInView ? "visible" : "hidden"}
            className="relative overflow-hidden rounded-lg border border-emerald-600/35 bg-white p-5"
            style={{
              boxShadow: approvalCardShadow,
              background: "linear-gradient(135deg, rgba(255,255,255,0.98), rgba(236,253,245,0.94))",
            }}
          >
            <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-emerald-600 via-emerald-500 to-blue-600" />
            <motion.div className="absolute -left-[7px] top-1/2 h-[14px] w-[14px] -translate-y-1/2 rounded-full border-2 border-emerald-600 bg-white shadow-[0_0_0_5px_rgba(16,185,129,0.12)]" />
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[13px] font-semibold text-slate-700">Decision</p>
                <motion.p
                  className="mt-1.5 text-[30px] font-extrabold leading-none tracking-[-0.04em] text-emerald-700"
                  initial={{ opacity: 0 }}
                  animate={isInView ? { opacity: 1 } : {}}
                  transition={{ delay: 2.4, duration: 0.5 }}
                >
                  APPROVED
                </motion.p>
                <p className="mt-2 text-[12px] font-medium text-slate-600"><span className="font-bold text-slate-950">INR 42L</span> credit limit</p>
              </div>
              <motion.div
                initial={{ scale: 0 }}
                animate={isInView ? { scale: 1 } : {}}
                transition={{ delay: 2.6, duration: 0.4, ease: heroEase }}
              >
                <CheckCircle2 className="h-10 w-10 text-emerald-600" />
              </motion.div>
            </div>
            <motion.div
              className="mt-4 grid grid-cols-2 gap-2"
              initial={{ opacity: 0, y: 4 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ delay: 2.8, duration: 0.4 }}
            >
              <span className="flex items-center justify-center gap-1.5 rounded-[6px] bg-blue-700 px-2 py-1.5 text-[11.5px] font-semibold text-white">
                <LockKeyhole className="h-3 w-3" /> SHAP attached
              </span>
              <span className="flex items-center justify-center gap-1.5 rounded-[6px] bg-blue-50 px-2 py-1.5 text-[11.5px] font-semibold text-blue-800 ring-1 ring-blue-700/10">
                <LockKeyhole className="h-3 w-3" /> Audit sealed
              </span>
            </motion.div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}

const architectureBadges = [
  "End-to-end encryption",
  "Immutable audit trail",
  "SHAP explainability",
  "Consent-first data",
  "Governed automation",
];

function MobileHeroVisual() {
  return (
    <div className="lg:hidden">
      <div
        className="overflow-hidden rounded-xl border border-slate-950/10 p-5 shadow-[0_18px_48px_rgba(15,23,42,0.1)]"
        style={{
          background:
            "linear-gradient(135deg, rgba(248,250,252,0.98) 0%, rgba(239,246,255,0.94) 50%, rgba(236,253,245,0.82) 100%)",
        }}
      >
        {/* Data source pills */}
        <div className="flex flex-wrap gap-2">
          {dataSources.map((source) => {
            const Icon = source.icon;
            return (
              <div key={source.label} className="flex items-center gap-2 rounded-lg border border-slate-950/10 bg-white/[0.82] px-3 py-1.5 shadow-[0_6px_16px_rgba(15,23,42,0.05)]">
                <Icon className="h-3.5 w-3.5 text-blue-700" />
                <span className="text-[12px] font-semibold text-slate-700">{source.label}</span>
              </div>
            );
          })}
        </div>
        {/* Center logo */}
        <div className="my-6 flex justify-center">
          <div className="flex h-28 w-28 flex-col items-center justify-center rounded-full border border-blue-700/25 bg-white shadow-[0_18px_42px_rgba(26,86,219,0.16)]">
            <img src="/ag.svg" alt="ArgentNorth" className="h-10 w-auto" />
          </div>
        </div>
        <p className="mb-4 text-center text-[12px] font-semibold text-slate-700">Governed intelligence layer</p>
        {/* Key metrics */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg border border-slate-950/10 bg-white/90 p-3 shadow-[0_10px_24px_rgba(15,23,42,0.06)]">
            <p className="text-[12px] font-semibold text-slate-700">Risk score</p>
            <p className="mt-1 text-[28px] font-bold leading-none text-slate-950">24</p>
            <div className="mt-1 flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-600" />
              <span className="text-[11px] font-semibold text-emerald-700">Low risk</span>
            </div>
          </div>
          <div className="rounded-lg border border-emerald-600/35 bg-white p-3 shadow-[0_14px_30px_rgba(5,150,105,0.14)]">
            <p className="text-[12px] font-semibold text-slate-700">Decision</p>
            <p className="mt-1 text-[22px] font-extrabold leading-none text-emerald-700">APPROVED</p>
            <p className="mt-1 text-[11px] font-medium text-slate-600">INR 42L credit limit</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function LandingPage({ onNavigate }: { onNavigate: (section: PrototypeSectionId) => void }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* ── Top Navigation — Premium Enterprise ── */}
      <nav className="fixed inset-x-0 top-0 z-50 border-b border-[var(--border-card)] bg-[var(--surface-glass)] backdrop-blur-xl">
        <div className="mx-auto flex h-[60px] max-w-[1280px] items-center justify-between px-6 lg:px-10">
          <div className="flex items-center gap-10">
            <button
              type="button"
              onClick={() => onNavigate("overview")}
              className="flex items-center gap-2.5 focus-visible:outline-none"
            >
              <img src="/ag.svg" alt="ArgentNorth" className="h-8 w-auto shrink-0 dark:invert" />
            </button>
            <div className="hidden items-center gap-7 lg:flex">
              <button type="button" onClick={() => onNavigate("command")} className="text-[13.5px] font-medium text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]">Platform</button>
              <button type="button" onClick={() => onNavigate("queue")} className="text-[13.5px] font-medium text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]">Solutions</button>
              <button type="button" onClick={() => onNavigate("modelOps")} className="text-[13.5px] font-medium text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]">Risk Ops</button>
              <button type="button" onClick={() => onNavigate("compliance")} className="text-[13.5px] font-medium text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]">Governance</button>
              <button type="button" onClick={() => onNavigate("dossier")} className="text-[13.5px] font-medium text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]">Documentation</button>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button type="button" onClick={() => onNavigate("command")} className="hidden text-[13.5px] font-medium text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)] md:block">
              Sign in
            </button>
            <Button
              type="button"
              onClick={() => onNavigate("command")}
              className="h-[36px] rounded-lg bg-gradient-to-b from-primary to-blue-700 px-5 text-[13px] font-semibold text-white shadow-[0_1px_2px_rgba(0,0,0,0.1),inset_0_1px_0_rgba(255,255,255,0.1)] transition-all hover:shadow-[0_2px_8px_rgba(26,86,219,0.3)]"
            >
              Request a demo
            </Button>
          </div>
        </div>
      </nav>

      {/* ── Hero Section — Split layout: LEFT text + RIGHT decision flow ── */}
      <section className="pt-[120px] pb-0 lg:pt-[140px]">
        <div className="mx-auto max-w-[1280px] px-6 lg:px-10">
          <div className="grid items-center gap-10 lg:grid-cols-[0.85fr_1.15fr] lg:gap-14">
            {/* LEFT — Copy */}
            <div className="hero-fade-in max-w-[560px] py-8 lg:py-16">
              <h1 className="hero-fade-in-d1 text-[36px] font-bold leading-[1.06] tracking-[-0.04em] text-[var(--text-primary)] sm:text-[44px] md:text-[52px] lg:text-[56px]">
                The intelligence layer{" "}
                <span className="bg-gradient-to-r from-primary via-blue-600 to-cyan-600 bg-clip-text text-transparent">
                  for credit decisions.
                </span>
              </h1>
              <p className="hero-fade-in-d2 mt-6 max-w-[460px] text-[16px] leading-[1.75] text-[var(--text-tertiary)] md:text-[17px]">
                The intelligent middleware layer where banks and NBFCs unify data,
                assess risk, and execute explainable lending decisions — governed at every step.
              </p>
              <div className="hero-fade-in-d3 mt-10 flex flex-wrap items-center gap-4">
                <Button
                  type="button"
                  onClick={() => onNavigate("command")}
                  className="h-[46px] rounded-lg bg-gradient-to-b from-primary to-blue-700 px-7 text-[14px] font-semibold text-white shadow-[0_1px_3px_rgba(0,0,0,0.12),inset_0_1px_0_rgba(255,255,255,0.1)] transition-all hover:shadow-[0_4px_16px_rgba(26,86,219,0.35)]"
                >
                  Request a demo
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
                <button
                  type="button"
                  onClick={() => onNavigate("dossier")}
                  className="flex items-center gap-1.5 text-[14px] font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
                >
                  Explore platform
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            {/* RIGHT — Animated Decision Flow schematic */}
            <div className="hero-fade-in-d2">
              <HeroDecisionFlow />
            </div>
          </div>
        </div>
      </section>

      {/* ── Architecture Authority Bar ── */}
      <section className="border-y border-[var(--border-card)]">
        <div className="mx-auto max-w-[1280px] px-6 lg:px-10">
          <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2 py-5 md:gap-x-6">
            {architectureBadges.map((badge, i) => (
              <span key={badge} className="flex items-center gap-3">
                {i > 0 && <span className="hidden text-[var(--text-faint)] select-none md:inline">·</span>}
                <span className="font-mono text-[10.5px] font-medium tracking-[0.04em] text-[var(--text-muted)] md:text-[11px]">
                  {badge}
                </span>
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── Narrative A — Unified Evidence Layer ── */}
      <section className="py-28 lg:py-36">
        <div className="mx-auto max-w-[1280px] px-6 lg:px-10">
          <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
            <div className="max-w-[520px]">
              <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-primary">
                Data Infrastructure
              </p>
              <h2 className="mt-5 text-[28px] font-bold leading-[1.08] tracking-[-0.035em] text-[var(--text-primary)] md:text-[40px]">
                Every signal.{" "}
                <span className="text-[var(--text-muted)]">One evidence graph.</span>
              </h2>
              <p className="mt-6 text-[15px] leading-[1.8] text-[var(--text-tertiary)]">
                Account Aggregator consent flows, credit bureau pulls, GST returns,
                bank statements, and KYC checks — normalized into a single
                decision-ready evidence packet. No data silos. No brittle integrations.
              </p>
              <p className="mt-4 text-[15px] leading-[1.8] text-[var(--text-tertiary)]">
                Every data source is ingested, validated, and mapped into a
                structured evidence graph before it touches the scoring engine.
              </p>
            </div>
            <div
              className="overflow-hidden rounded-xl border border-slate-800/80"
              style={{
                background: "linear-gradient(145deg, #0c1222 0%, #111827 50%, #0f172a 100%)",
                boxShadow: "0 0 0 1px rgba(148,163,184,0.05), 0 25px 60px -12px rgba(0,0,0,0.5)",
              }}
            >
              <div className="flex items-center gap-2 border-b border-slate-800/60 px-5 py-3">
                <DatabaseZap className="h-3 w-3 text-slate-500" />
                <span className="font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-slate-500">
                  Evidence Ingestion Pipeline
                </span>
                <span className="ml-auto flex items-center gap-1.5">
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-40" />
                    <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  </span>
                  <span className="text-[9px] font-medium text-emerald-400/70">Active</span>
                </span>
              </div>
              <div className="p-5">
                <div className="space-y-2">
                  {[
                    { label: "Account Aggregator", sub: "Consent flow · UPI · AA", status: "Verified" },
                    { label: "Credit Bureau", sub: "CIBIL · Experian · CRIF", status: "Matched" },
                    { label: "GST Returns", sub: "GSTR-1 · GSTR-3B · 24 mo", status: "Ingested" },
                    { label: "Bank Statements", sub: "3 accounts · 12 months", status: "Primary" },
                    { label: "KYC / AML", sub: "PAN · Aadhaar · Identity", status: "Cleared" },
                  ].map((source, i) => (
                    <motion.div
                      key={source.label}
                      className="flex items-center justify-between rounded-lg border border-slate-800/50 bg-[#0a1018] px-4 py-3"
                      initial={{ opacity: 0, x: -12 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.1 + i * 0.08, duration: 0.5 }}
                      viewport={{ once: true }}
                    >
                      <div className="min-w-0">
                        <p className="text-[12px] font-semibold text-slate-200">{source.label}</p>
                        <p className="mt-0.5 text-[10px] text-slate-500">{source.sub}</p>
                      </div>
                      <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[9px] font-semibold text-emerald-400">
                        <CheckCircle2 className="h-2.5 w-2.5" />
                        {source.status}
                      </span>
                    </motion.div>
                  ))}
                </div>
                <div className="mt-4 flex items-center justify-between border-t border-slate-800/40 pt-3">
                  <span className="font-mono text-[10px] text-slate-600">5/5 sources verified</span>
                  <span className="font-mono text-[10px] text-slate-600">evidence-graph-v3.1</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Narrative B — Explainable Risk Engine ── */}
      <section className="border-y border-[var(--border-card)] bg-[var(--surface-secondary)]/20 py-28 lg:py-36">
        <div className="mx-auto max-w-[1280px] px-6 lg:px-10">
          <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
            <div
              className="order-2 overflow-hidden rounded-xl border border-slate-800/80 lg:order-1"
              style={{
                background: "linear-gradient(145deg, #0c1222 0%, #111827 50%, #0f172a 100%)",
                boxShadow: "0 0 0 1px rgba(148,163,184,0.05), 0 25px 60px -12px rgba(0,0,0,0.5)",
              }}
            >
              <div className="flex items-center gap-2 border-b border-slate-800/60 px-5 py-3">
                <BrainCircuit className="h-3 w-3 text-slate-500" />
                <span className="font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-slate-500">
                  Risk Scoring Engine
                </span>
                <span className="ml-auto font-mono text-[9px] text-slate-600">credit-gbm-4.8</span>
              </div>
              <div className="p-5">
                <div className="grid gap-4 sm:grid-cols-[100px_1fr]">
                  <div className="flex flex-col items-center justify-center rounded-lg border border-slate-800/40 bg-slate-950/60 py-4">
                    <motion.span
                      className="font-mono text-[36px] font-bold leading-none tracking-tighter text-slate-100"
                      initial={{ opacity: 0 }}
                      whileInView={{ opacity: 1 }}
                      transition={{ duration: 0.8 }}
                      viewport={{ once: true }}
                    >
                      24
                    </motion.span>
                    <span className="mt-1 font-mono text-[9px] text-slate-500">/ 100</span>
                    <span className="mt-1.5 font-mono text-[8px] font-medium uppercase tracking-widest text-emerald-400/60">
                      low risk
                    </span>
                  </div>
                  <div>
                    <p className="mb-2.5 font-mono text-[8.5px] font-bold uppercase tracking-[0.08em] text-slate-600">
                      SHAP Explainability
                    </p>
                    <div className="space-y-[8px]">
                      {[
                        { feature: "Bureau Score", value: 0.82, positive: true },
                        { feature: "Cash Flow", value: 0.65, positive: true },
                        { feature: "GST Compliance", value: 0.48, positive: true },
                        { feature: "Sector Risk", value: 0.22, positive: false },
                        { feature: "Vintage", value: 0.35, positive: true },
                      ].map((bar, i) => (
                        <div key={bar.feature} className="flex items-center gap-2.5">
                          <span className="w-[85px] shrink-0 truncate text-[10px] text-slate-400">{bar.feature}</span>
                          <div className="relative h-[5px] flex-1 overflow-hidden rounded-full bg-slate-800/80">
                            <motion.div
                              className="absolute inset-y-0 left-0 rounded-full"
                              style={{
                                background: bar.positive
                                  ? "linear-gradient(90deg, #3b82f6, #60a5fa)"
                                  : "linear-gradient(90deg, #ef4444, #f87171)",
                              }}
                              initial={{ width: 0 }}
                              whileInView={{ width: `${bar.value * 100}%` }}
                              transition={{ duration: 0.6, delay: 0.2 + i * 0.08 }}
                              viewport={{ once: true }}
                            />
                          </div>
                          <span className="w-[34px] text-right font-mono text-[9px] tabular-nums text-slate-500">
                            {bar.positive ? "+" : "-"}{bar.value.toFixed(2)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="mt-4 flex items-center gap-3 border-t border-slate-800/40 pt-3">
                  <span className="inline-flex items-center gap-1 rounded bg-blue-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.05em] text-blue-400">
                    <Eye className="h-2.5 w-2.5" />
                    Explainability attached
                  </span>
                  <span className="font-mono text-[9px] text-slate-600">SHAP v2.1 · 5 drivers</span>
                </div>
              </div>
            </div>
            <div className="order-1 max-w-[520px] lg:order-2">
              <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-primary">
                Decision Intelligence
              </p>
              <h2 className="mt-5 text-[28px] font-bold leading-[1.08] tracking-[-0.035em] text-[var(--text-primary)] md:text-[40px]">
                Score. Explain.{" "}
                <span className="text-[var(--text-muted)]">Defend.</span>
              </h2>
              <p className="mt-6 text-[15px] leading-[1.8] text-[var(--text-tertiary)]">
                XGBoost ensemble scoring with SHAP reason codes attached to every
                decision. Not a black box — every score comes with machine-readable
                explanations that satisfy both regulators and borrowers.
              </p>
              <p className="mt-4 text-[15px] leading-[1.8] text-[var(--text-tertiary)]">
                Fairness monitors run continuously across protected dimensions.
                PSI drift detection triggers governance alerts before portfolio
                impact materializes.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Narrative C — Governed Execution Layer ── */}
      <section className="py-28 lg:py-36">
        <div className="mx-auto max-w-[1280px] px-6 lg:px-10">
          <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
            <div className="max-w-[520px]">
              <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-primary">
                Governance Layer
              </p>
              <h2 className="mt-5 text-[28px] font-bold leading-[1.08] tracking-[-0.035em] text-[var(--text-primary)] md:text-[40px]">
                Every action.{" "}
                <span className="text-[var(--text-muted)]">Sealed in audit.</span>
              </h2>
              <p className="mt-6 text-[15px] leading-[1.8] text-[var(--text-tertiary)]">
                Agentic recommendations are scoped and gated by authority. Capital
                actions require human approval. Policy changes need dual sign-off.
                Every override, every decision, every exception — captured in an
                immutable compliance trail with full lineage.
              </p>
              <p className="mt-4 text-[15px] leading-[1.8] text-[var(--text-tertiary)]">
                The system cannot act alone. Humans govern. The audit trail proves it.
              </p>
            </div>
            <div
              className="overflow-hidden rounded-xl border border-slate-800/80"
              style={{
                background: "linear-gradient(145deg, #0c1222 0%, #111827 50%, #0f172a 100%)",
                boxShadow: "0 0 0 1px rgba(148,163,184,0.05), 0 25px 60px -12px rgba(0,0,0,0.5)",
              }}
            >
              <div className="flex items-center gap-2 border-b border-slate-800/60 px-5 py-3">
                <ShieldCheck className="h-3 w-3 text-slate-500" />
                <span className="font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-slate-500">
                  Governance & Audit
                </span>
                <span className="ml-auto font-mono text-[9px] text-slate-600">immutable ledger</span>
              </div>
              <div className="p-5">
                <div className="space-y-1.5">
                  {[
                    { label: "KYC / AML clearance", status: "pass" },
                    { label: "DTI ratio < 50%", status: "pass" },
                    { label: "Vintage ≥ 36 months", status: "pass" },
                    { label: "No DPD 90+ in 12 mo", status: "pass" },
                    { label: "Sector concentration", status: "warn" },
                  ].map((check, i) => (
                    <motion.div
                      key={check.label}
                      className="flex items-center justify-between rounded-md border px-3 py-2"
                      style={{
                        borderColor: check.status === "warn" ? "rgba(217,119,6,0.25)" : "rgba(34,197,94,0.15)",
                        background: check.status === "warn" ? "rgba(217,119,6,0.04)" : "rgba(34,197,94,0.03)",
                      }}
                      initial={{ opacity: 0, x: -8 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.1 + i * 0.06, duration: 0.4 }}
                      viewport={{ once: true }}
                    >
                      <span className="text-[11px] font-medium text-slate-300">{check.label}</span>
                      {check.status === "warn" ? (
                        <AlertTriangle className="h-3 w-3 text-amber-500" />
                      ) : (
                        <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                      )}
                    </motion.div>
                  ))}
                </div>
                <div className="mt-4 border-t border-slate-800/40 pt-3">
                  <p className="mb-2 font-mono text-[8.5px] font-bold uppercase tracking-[0.08em] text-slate-600">
                    Audit Trail
                  </p>
                  <div className="space-y-2">
                    {[
                      { time: "14:32:01", event: "Evidence packet sealed", actor: "system" },
                      { time: "14:32:04", event: "Risk score computed — 24/100", actor: "engine-v4.2" },
                      { time: "14:32:06", event: "Policy battery evaluated — 4/5 pass", actor: "policy-svc" },
                      { time: "14:32:09", event: "Decision: APPROVED — human sign-off", actor: "reviewer.01" },
                    ].map((entry) => (
                      <div key={entry.time} className="flex items-start gap-3">
                        <span className="mt-0.5 font-mono text-[9px] tabular-nums text-slate-600">{entry.time}</span>
                        <div className="min-w-0 flex-1">
                          <p className="text-[10.5px] text-slate-300">{entry.event}</p>
                          <p className="mt-0.5 font-mono text-[9px] text-slate-600">{entry.actor}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Decision Pipeline — Animated system architecture ── */}
      <section className="border-y border-[var(--border-card)] bg-[var(--surface-secondary)]/20 py-28 lg:py-36">
        <div className="mx-auto max-w-[1280px] px-6 lg:px-10">
          <div className="mx-auto max-w-2xl text-center">
            <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-primary">
              System Architecture
            </p>
            <h2 className="mt-5 text-[28px] font-bold leading-[1.08] tracking-[-0.035em] text-[var(--text-primary)] md:text-[40px]">
              From raw evidence to sealed decision.
            </h2>
            <p className="mt-4 text-[15px] leading-[1.8] text-[var(--text-tertiary)]">
              A governed sequence. Every stage observable. Every transition auditable.
            </p>
          </div>
          <div className="mt-16">
            <div className="relative flex flex-col items-stretch gap-4 md:flex-row md:items-center md:gap-0">
              {pipelineStages.map((stage, i) => (
                <div key={stage.id} className="flex flex-1 items-center">
                  <motion.div
                    className="relative flex w-full flex-col items-center rounded-xl border border-[var(--border-card)] bg-[var(--surface-raised)] px-4 py-6 text-center transition-all duration-300 hover:border-primary/25 hover:shadow-[0_8px_32px_rgba(26,86,219,0.06)]"
                    initial={{ opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.1, duration: 0.5 }}
                    viewport={{ once: true }}
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/[0.06]">
                      <span className="font-mono text-[13px] font-bold text-primary">{String(i + 1).padStart(2, "0")}</span>
                    </div>
                    <h3 className="mt-4 text-[14px] font-bold tracking-[-0.01em] text-[var(--text-primary)]">{stage.label}</h3>
                    <p className="mt-1.5 font-mono text-[10.5px] text-[var(--text-muted)]">{stage.sub}</p>
                  </motion.div>
                  {i < pipelineStages.length - 1 && (
                    <div className="hidden h-px w-8 shrink-0 md:block" style={{ background: "linear-gradient(90deg, var(--border-card), var(--border-card-hover), var(--border-card))" }} />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Enterprise Trust Architecture ── */}
      <section className="py-28 lg:py-36">
        <div className="mx-auto max-w-[1280px] px-6 lg:px-10">
          <div className="max-w-2xl">
            <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-primary">
              Trust Architecture
            </p>
            <h2 className="mt-5 text-[28px] font-bold leading-[1.08] tracking-[-0.035em] text-[var(--text-primary)] md:text-[40px]">
              Security is architecture,{" "}
              <span className="text-[var(--text-muted)]">not a feature.</span>
            </h2>
            <p className="mt-4 text-[15px] leading-[1.8] text-[var(--text-tertiary)]">
              Every layer of the stack is built for institutional-grade governance,
              from data ingestion to decision output.
            </p>
          </div>
          <div className="mt-14 grid gap-px overflow-hidden rounded-xl border border-[var(--border-card)] bg-[var(--border-card)] sm:grid-cols-2 lg:grid-cols-4">
            {trustArchitecture.map((item) => (
              <div
                key={item.title}
                className="bg-[var(--surface-raised)] p-6 transition-colors duration-200 hover:bg-[var(--surface-hover)]"
              >
                <h3 className="text-[13px] font-bold tracking-[-0.01em] text-[var(--text-primary)]">{item.title}</h3>
                <p className="mt-3 text-[13px] leading-[1.7] text-[var(--text-tertiary)]">{item.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Bottom CTA — Restrained enterprise authority ── */}
      <section className="border-t border-[var(--border-card)]">
        <div className="mx-auto max-w-[1280px] px-6 py-28 lg:px-10 lg:py-40">
          <div className="mx-auto max-w-[680px] text-center">
            <h2 className="text-[28px] font-bold leading-[1.08] tracking-[-0.035em] text-[var(--text-primary)] md:text-[44px]">
              Built for institutions that move capital under governance.
            </h2>
            <p className="mt-6 text-[16px] leading-[1.75] text-[var(--text-tertiary)]">
              If your lending infrastructure requires explainability, auditability,
              and human-in-the-loop decisioning — we should talk.
            </p>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
              <Button
                type="button"
                onClick={() => onNavigate("command")}
                className="h-[46px] rounded-lg bg-gradient-to-b from-primary to-blue-700 px-8 text-[14px] font-semibold text-white shadow-[0_1px_3px_rgba(0,0,0,0.12),inset_0_1px_0_rgba(255,255,255,0.1)] transition-all hover:shadow-[0_4px_16px_rgba(26,86,219,0.35)]"
              >
                Request a demo
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
              <button
                type="button"
                onClick={() => onNavigate("command")}
                className="flex items-center gap-1.5 text-[14px] font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
              >
                Explore the platform
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-[var(--border-card)]">
        <div className="mx-auto max-w-[1280px] px-6 lg:px-10">
          <div className="flex flex-col gap-8 py-12 md:flex-row md:items-start md:justify-between md:py-16">
            <div className="max-w-[280px]">
              <div className="flex items-center gap-2.5">
                <img src="/ag.svg" alt="ArgentNorth" className="h-7 w-auto shrink-0 dark:invert" />
              </div>
              <p className="mt-3 text-[13px] leading-[1.7] text-[var(--text-muted)]">
                Autonomous credit decisioning infrastructure for banks and NBFCs.
              </p>
            </div>
            <div className="flex flex-wrap gap-12 md:gap-16">
              <div>
                <p className="font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-muted)]">Platform</p>
                <div className="mt-3 flex flex-col gap-2">
                  <button type="button" onClick={() => onNavigate("command")} className="text-left text-[13px] text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]">Command Center</button>
                  <button type="button" onClick={() => onNavigate("queue")} className="text-left text-[13px] text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]">Decision Queue</button>
                  <button type="button" onClick={() => onNavigate("modelOps")} className="text-left text-[13px] text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]">Risk Ops</button>
                </div>
              </div>
              <div>
                <p className="font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-muted)]">Governance</p>
                <div className="mt-3 flex flex-col gap-2">
                  <button type="button" onClick={() => onNavigate("compliance")} className="text-left text-[13px] text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]">Compliance</button>
                  <button type="button" onClick={() => onNavigate("dossier")} className="text-left text-[13px] text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]">Documentation</button>
                </div>
              </div>
              <div>
                <p className="font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--text-muted)]">Company</p>
                <div className="mt-3 flex flex-col gap-2">
                  <span className="text-[13px] text-[var(--text-tertiary)]">About</span>
                  <span className="text-[13px] text-[var(--text-tertiary)]">Security</span>
                  <span className="text-[13px] text-[var(--text-tertiary)]">Contact</span>
                </div>
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between border-t border-[var(--border-card)] py-6">
            <p className="text-[12px] text-[var(--text-muted)]">&copy; {new Date().getFullYear()} ArgentNorth Technologies.</p>
            <ThemeToggle />
          </div>
        </div>
      </footer>
    </div>
  );
}

function CommandCenterView() {
  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        eyebrow="Command Center"
        title="Control plane for capital, policy, model risk, and authority."
        description="Exposure, consent, semantic mapping, risk drift, policy execution, agent recommendations, and audit lineage."
      >
        <StatusBadge label="Authority gated" tone="good" />
        <StatusBadge label="Drift watch" tone="warning" />
      </PageHeader>

      <BoardMetricStrip />

      <div className="grid gap-6 xl:grid-cols-[1fr_0.78fr]">
        <DecisionObjectTable />
        <AgenticMovesPanel />
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <SectionHeading
              icon={Gauge}
              title="Operating Lanes"
              description="How today's cases are routed through capital, risk, and compliance lanes."
            />
          </div>
          <div className="divide-y divide-[var(--border-subtle)] px-5">
            {operatingLanes.map((lane) => {
              const style = toneClass(lane.tone);

              return (
                <div key={lane.lane} className="grid gap-3 py-3.5 md:grid-cols-[0.85fr_0.55fr_0.65fr_0.55fr_0.7fr] md:items-center">
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-medium text-[var(--text-primary)]">{lane.lane}</p>
                  </div>
                  <p className="font-mono text-[12px] text-[var(--text-secondary)]">{lane.volume}</p>
                  <p className="font-mono text-[12px] font-medium text-[var(--text-primary)]">{lane.capital}</p>
                  <p className={cn("text-[12px] font-medium", style.text)}>{lane.risk}</p>
                  <p className="truncate text-[12px] text-[var(--text-tertiary)]">{lane.owner}</p>
                </div>
              );
            })}
          </div>
        </Surface>

        <CapitalRailsPanel />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_0.8fr]">
        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <SectionHeading
              icon={TrendingUp}
              title="Exposure Trend"
              description="Rolling 12-month capital cleared through the decision fabric."
            />
          </div>
          <div className="p-5">
            <AreaChart data={exposureTrendData.values} labels={exposureTrendData.labels} height={180} />
          </div>
        </Surface>

        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <SectionHeading
              icon={Network}
              title="Evidence Flow Graph"
              description="Data lineage from applicant to capital action."
            />
          </div>
          <div className="p-5">
            <EvidenceFlowGraph nodes={evidenceGraphNodes} />
          </div>
        </Surface>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_0.8fr]">
        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <SectionHeading
              icon={Activity}
              title="Live Audit Stream"
              description="AA, BIAN, model, policy, governance, and action events for operators."
            />
          </div>
          <div className="p-5">
            {commandEventStream.map((event) => (
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

        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <SectionHeading
              icon={DatabaseZap}
              title="Infrastructure Health"
              description="Ingestion, semantic mapping, policy controls, and fairness monitors."
            />
          </div>
          <div className="divide-y divide-[var(--border-subtle)] px-5">
            {commandSignals.map((signal) => {
              const style = toneClass(signal.tone);

              return (
                <div key={signal.label} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-semibold text-[var(--text-primary)]">{signal.label}</p>
                    <p className={cn("mt-1 text-[12px] font-medium", style.text)}>{signal.status}</p>
                  </div>
                  <p className="font-mono text-[12px] font-semibold text-[var(--text-primary)]">{signal.value}</p>
                </div>
              );
            })}
          </div>
        </Surface>
      </div>
    </div>
  );
}

function QueueDecisionBadge({ decision }: { decision: PrototypeDecision }) {
  return <StatusBadge label={decision} tone={getDecisionTone(decision)} />;
}

function CaseQueueView() {
  const [queueFilter, setQueueFilter] = useState<"All" | "SLA" | "Review">("All");

  const filteredCases = queueCases.filter((item) => {
    if (queueFilter === "SLA") return item.status.toLowerCase().includes("sla") || item.sla.length <= 3;
    if (queueFilter === "Review") return item.decision === "Manual Review";
    return true;
  });

  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        eyebrow="Case Queue"
        title="Decision book for active capital movement."
        description="Every row exposes capital at stake, evidence sufficiency, risk authority, and next action."
      >
        <Button type="button" variant="outline" className="h-9 rounded-md border-[var(--border-card)] bg-[var(--surface-raised)] text-[13px]">
          <Filter className="h-3.5 w-3.5" />
          Filters
        </Button>
        <Button type="button" className="h-9 rounded-md bg-primary px-4 text-[13px] font-semibold text-primary-foreground">
          Execute batch
        </Button>
      </PageHeader>

      <div className="grid gap-px overflow-hidden rounded-md border border-[var(--border-card)] md:grid-cols-4">
        <div className="bg-[var(--surface-raised)] p-5">
          <p className="text-[12px] text-[var(--text-muted)]">Active cases</p>
          <p className="mt-2 font-mono text-[28px] font-semibold leading-none text-[var(--text-primary)]">{queueCases.length}</p>
        </div>
        <div className="bg-[var(--surface-raised)] p-5">
          <p className="text-[12px] text-[var(--text-muted)]">Capital in queue</p>
          <p className="mt-2 font-mono text-[28px] font-semibold leading-none text-[var(--text-primary)]">₹1.85Cr</p>
        </div>
        <div className="bg-[var(--surface-raised)] p-5">
          <p className="text-[12px] text-[var(--text-muted)]">Manual review</p>
          <p className="mt-2 font-mono text-[28px] font-semibold leading-none text-amber-600 dark:text-amber-400">
            {queueCases.filter((item) => item.decision === "Manual Review").length}
          </p>
        </div>
        <div className="bg-[var(--surface-raised)] p-5">
          <p className="text-[12px] text-[var(--text-muted)]">Auto-sanctionable</p>
          <p className="mt-2 font-mono text-[28px] font-semibold leading-none text-emerald-600 dark:text-emerald-400">
            {queueCases.filter((item) => item.decision === "Approve").length}
          </p>
        </div>
      </div>

      <Surface className="overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-[var(--border-card)] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <SectionHeading icon={ClipboardList} title="Credit Execution Book" />
          <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center">
            <label className="sr-only" htmlFor="prototype-case-search">
              Search cases
            </label>
            <div className="relative min-w-0 sm:w-[320px]">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-muted)]" />
              <input
                id="prototype-case-search"
                readOnly
                value="Risk, region, applicant, authority"
                className="h-9 w-full rounded-lg border border-[var(--border-card)] bg-[var(--surface-secondary)]/35 pl-9 pr-3 text-[13px] text-[var(--text-tertiary)] outline-none"
              />
            </div>
            <div className="inline-flex w-fit rounded-lg border border-[var(--border-card)] bg-[var(--surface-secondary)]/35 p-1">
              {(["All", "SLA", "Review"] as const).map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setQueueFilter(item)}
                  className={cn(
                    "h-7 rounded-md px-3 text-[12px] font-semibold transition-colors",
                    queueFilter === item ? "bg-[var(--surface-raised)] text-[var(--text-primary)] shadow-sm" : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]"
                  )}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <div className="min-w-[1280px]">
            <div className="grid grid-cols-[1.15fr_0.72fr_0.7fr_0.52fr_0.62fr_0.58fr_0.72fr_0.76fr_0.7fr] border-b border-[var(--border-card)] bg-[var(--surface-secondary)]/35 px-5 py-2.5 text-[11px] font-medium uppercase tracking-[0.06em] text-[var(--text-muted)]">
              <div>Applicant</div>
              <div>Product</div>
              <div>Region</div>
              <div>Risk</div>
              <div>Evidence</div>
              <div>SLA</div>
              <div>Recommendation</div>
              <div>Authority</div>
              <div>Reviewer</div>
            </div>

            <div className="divide-y divide-[var(--border-subtle)]">
              {filteredCases.map((item) => {
                const style = toneClass(item.tone);

                return (
                  <button
                    key={item.id}
                    type="button"
                    className="grid w-full grid-cols-[1.15fr_0.72fr_0.7fr_0.52fr_0.62fr_0.58fr_0.72fr_0.76fr_0.7fr] items-center gap-0 px-5 py-4 text-left transition-colors hover:bg-[var(--surface-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/45"
                  >
                    <div className="min-w-0 pr-4">
                      <div className="flex min-w-0 items-center gap-2">
                        <span className={cn("h-2 w-2 shrink-0 rounded-full", style.dot)} />
                        <p className="truncate text-[13px] font-semibold text-[var(--text-primary)]">{item.applicant}</p>
                      </div>
                      <p className="mt-1 truncate font-mono text-[11px] text-[var(--text-muted)]">
                        {item.id} - {item.entityType}
                      </p>
                    </div>
                    <div className="min-w-0 pr-4">
                      <p className="truncate text-[13px] font-semibold text-[var(--text-primary)]">{item.product}</p>
                      <p className="mt-1 truncate text-[11px] text-[var(--text-muted)]">{item.amount}</p>
                    </div>
                    <p className="truncate pr-4 text-[13px] font-medium text-[var(--text-secondary)]">{item.region}</p>
                    <div>
                      <StatusBadge label={`${item.riskBand} ${item.riskScore}`} tone={getRiskBandTone(item.riskBand)} />
                    </div>
                    <div className="pr-5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-[12px] font-semibold text-[var(--text-primary)]">{item.evidence}%</span>
                      </div>
                      <ProgressBar value={item.evidence} tone={item.evidence >= 90 ? "good" : "warning"} className="mt-2 h-1.5" />
                    </div>
                    <p className={cn("font-mono text-[12px] font-semibold", item.sla.includes("m") && item.sla.length <= 3 ? "text-red-500" : "text-[var(--text-secondary)]")}>
                      {item.sla}
                    </p>
                    <div>
                      <QueueDecisionBadge decision={item.decision} />
                      <p className="mt-1 truncate text-[11px] text-[var(--text-muted)]">{item.pricing}</p>
                    </div>
                    <div className="min-w-0 pr-4">
                      <p className="truncate text-[12px] font-semibold text-[var(--text-primary)]">
                        {item.decision === "Approve" ? "Signed policy" : item.decision === "Reject" ? "Compliance signoff" : "Human signoff"}
                      </p>
                      <p className="mt-1 truncate text-[11px] text-[var(--text-muted)]">
                        {item.decision === "Approve" ? "auto permitted" : "action locked"}
                      </p>
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-[13px] font-semibold text-[var(--text-primary)]">{item.reviewer}</p>
                      <p className={cn("mt-1 truncate text-[11px]", style.text)}>{item.status}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </Surface>
    </div>
  );
}

function EvidenceIntakeView() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Evidence Intake"
        title="Guided case creation with live validation."
        description="Stripe Checkout-inspired workflow clarity: clean form hierarchy, clear completion states, visible validation, evidence packet summary, and final review before case creation."
      >
        <StatusBadge label="Step 2 of 4" tone="warning" />
      </PageHeader>

      <div className="grid items-start gap-6 xl:grid-cols-[280px_1fr_360px]">
        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <SectionHeading icon={ClipboardCheck} title="Workflow" />
          </div>
          <div className="divide-y divide-[var(--border-subtle)]">
            {intakeSteps.map((step, index) => {
              const style = toneClass(step.tone);

              return (
                <button
                  key={step.label}
                  type="button"
                  className={cn(
                    "flex w-full gap-3 px-5 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/45",
                    step.status === "active" ? "bg-primary/[0.06]" : "hover:bg-[var(--surface-hover)]"
                  )}
                >
                  <span className={cn("mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border font-mono text-[11px] font-semibold", style.bg, style.border, style.text)}>
                    {index + 1}
                  </span>
                  <span className="min-w-0">
                    <span className="flex items-center gap-2">
                      <span className="text-[13px] font-semibold text-[var(--text-primary)]">{step.label}</span>
                      <span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} />
                    </span>
                    <span className="mt-1 block text-[12px] leading-relaxed text-[var(--text-tertiary)]">{step.detail}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </Surface>

        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <SectionHeading
              icon={UploadCloud}
              title="Applicant and Evidence Details"
              description="Static fields show how validation and helper copy should behave before API wiring."
            />
          </div>
          <div className="grid gap-4 p-5 md:grid-cols-2">
            {intakeFields.map((field) => {
              const errorId = `${field.id}-error`;

              return (
                <div key={field.id} className={cn(field.id === "bankWindow" ? "md:col-span-2" : "")}>
                  <label htmlFor={field.id} className="text-[12px] font-semibold text-[var(--text-primary)]">
                    {field.label}
                  </label>
                  <input
                    id={field.id}
                    readOnly
                    value={field.value}
                    aria-invalid={Boolean(field.error)}
                    aria-describedby={field.error ? errorId : undefined}
                    className={cn(
                      "mt-2 h-10 w-full rounded-lg border bg-[var(--surface-secondary)]/35 px-3 text-[13px] font-medium text-[var(--text-primary)] outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
                      field.error ? "border-amber-500/45" : "border-[var(--border-card)]"
                    )}
                  />
                  <p className="mt-1.5 text-[12px] leading-relaxed text-[var(--text-tertiary)]">{field.helper}</p>
                  {field.error ? (
                    <p id={errorId} className="mt-1.5 flex items-start gap-2 text-[12px] leading-relaxed text-amber-600 dark:text-amber-400">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      <span>{field.error}</span>
                    </p>
                  ) : null}
                </div>
              );
            })}
          </div>
        </Surface>

        <div className="flex flex-col gap-6">
          <Surface className="overflow-hidden">
            <div className="border-b border-[var(--border-card)] px-5 py-4">
              <SectionHeading icon={FileCheck2} title="Evidence Packet" />
            </div>
            <div className="divide-y divide-[var(--border-subtle)] px-5">
              {evidencePacket.map((item) => {
                const style = toneClass(item.tone);

                return (
                  <div key={item.label} className="flex items-start justify-between gap-4 py-3">
                    <div className="min-w-0">
                      <p className="text-[13px] font-semibold text-[var(--text-primary)]">{item.label}</p>
                      <p className={cn("mt-1 text-[12px] leading-relaxed", style.text)}>{item.value}</p>
                    </div>
                    <span className={cn("mt-1 h-2 w-2 shrink-0 rounded-full", style.dot)} />
                  </div>
                );
              })}
            </div>
          </Surface>

          <Surface className="p-5">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-amber-500/20 bg-amber-500/10">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
              </div>
              <div className="min-w-0">
                <h3 className="text-[14px] font-semibold text-[var(--text-primary)]">Final review blocked</h3>
                <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-tertiary)]">
                  One evidence rule needs attention before Create Case becomes available.
                </p>
              </div>
            </div>
            <Button
              type="button"
              disabled
              className="mt-5 h-10 w-full rounded-lg bg-primary px-4 text-[13px] font-semibold text-primary-foreground"
            >
              Create Case
            </Button>
          </Surface>
        </div>
      </div>
    </div>
  );
}

function CaseDossierView() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Case Dossier"
        title={`${dossier.id}: ${dossier.applicant}`}
        description={dossier.summary}
      >
        <QueueDecisionBadge decision={dossier.recommendation} />
        <Button type="button" className="h-9 rounded-lg bg-primary px-4 text-[13px] font-semibold text-primary-foreground">
          Approve with conditions
        </Button>
      </PageHeader>

      <div className="grid items-start gap-6 xl:grid-cols-[0.82fr_1.18fr]">
        <Surface className="p-5">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
            <GaugeArc score={dossier.riskScore} size={140} />
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-tertiary)]">Risk recommendation</p>
              <h2 className="mt-2 text-[24px] font-semibold text-[var(--text-primary)]">Manual Review</h2>
              <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-tertiary)]">
                SHAP-style drivers show elevated DTI and short history, offset by strong GST stability and low bounce rate.
              </p>
              <div className="mt-4 grid gap-2 sm:grid-cols-3">
                <Button type="button" className="h-9 rounded-lg bg-emerald-600 px-3 text-[13px] text-white hover:bg-emerald-600/90">
                  Approve
                </Button>
                <Button type="button" variant="outline" className="h-9 rounded-lg border-[var(--border-card)] bg-[var(--surface-raised)] px-3 text-[13px]">
                  Review
                </Button>
                <Button type="button" variant="outline" className="h-9 rounded-lg border-red-500/25 bg-red-500/10 px-3 text-[13px] text-red-500">
                  Reject
                </Button>
              </div>
            </div>
          </div>
        </Surface>

        <div className="grid gap-3 md:grid-cols-3">
          {dossier.facts.map((fact) => (
            <DataTile key={fact.label} label={fact.label} value={fact.value} />
          ))}
        </div>
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-[0.9fr_1.1fr_0.9fr]">
        <Surface className="p-5">
          <SectionHeading icon={Banknote} title="Cash-flow Intelligence" />
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            {dossier.cashflow.map((item) => (
              <DataTile key={item.label} label={item.label} value={item.value} tone={item.tone} />
            ))}
          </div>
        </Surface>

        <Surface className="p-5">
          <SectionHeading
            icon={BrainCircuit}
            title="Explainability Drivers"
            description="SHAP/LIME-ready reason codes for human review and adverse action."
          />
          <div className="mt-5">
            <WaterfallChart drivers={dossier.drivers} />
          </div>
        </Surface>

        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <SectionHeading icon={ShieldCheck} title="Policy Checks" />
          </div>
          <div className="divide-y divide-[var(--border-subtle)] px-5">
            {dossier.policyChecks.map((check) => (
              <div key={check.label} className="flex items-center justify-between gap-3 py-3">
                <p className="text-[13px] font-semibold text-[var(--text-primary)]">{check.label}</p>
                <StatusBadge label={check.result} tone={check.tone} />
              </div>
            ))}
          </div>
        </Surface>
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-[0.82fr_1.18fr]">
        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <SectionHeading icon={AlertTriangle} title="Fraud and Integrity Flags" />
          </div>
          <div className="divide-y divide-[var(--border-subtle)] px-5">
            {dossier.fraudFlags.map((flag) => {
              const style = toneClass(flag.tone);

              return (
                <div key={flag.label} className="flex items-start gap-3 py-3">
                  <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", style.dot)} />
                  <div className="min-w-0">
                    <p className="text-[13px] font-semibold text-[var(--text-primary)]">{flag.label}</p>
                    <p className={cn("mt-1 text-[12px] leading-relaxed", style.text)}>{flag.detail}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </Surface>

        <Surface className="p-5">
          <SectionHeading icon={GitBranch} title="Audit Trail" />
          <div className="mt-5">
            {dossier.auditTrail.map((event) => (
              <TimelineRow key={`${event.time}-${event.label}`} label={event.label} detail={event.detail} time={event.time} tone={event.tone} />
            ))}
          </div>
        </Surface>
      </div>
    </div>
  );
}

function ModelRiskOpsView() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Model/Risk Ops"
        title="Audit-ready model, drift, fairness, and policy monitoring."
        description="Model version, AUC, KS, PSI drift, fairness metrics, cohort watchlists, policy rule battery, and governance controls."
      >
        <StatusBadge label="credit-gbm-4.8" tone="good" />
        <StatusBadge label="Retail cohort watch" tone="warning" />
      </PageHeader>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {modelCards.map((card) => (
          <MetricCard key={card.label} label={card.label} value={card.value} delta={card.detail} tone={card.tone} icon={BrainCircuit} />
        ))}
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-[0.82fr_1.18fr]">
        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <SectionHeading icon={Scale} title="Fairness and Drift Metrics" />
          </div>
          <div className="grid gap-3 p-5 sm:grid-cols-2">
            {fairnessMetrics.map((metric) => {
              const style = toneClass(metric.tone);

              return (
                <div key={metric.label} className="rounded-lg border border-[var(--border-card)] bg-[var(--surface-secondary)]/30 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-[12px] font-semibold text-[var(--text-primary)]">{metric.label}</p>
                    <span className={cn("h-2 w-2 rounded-full", style.dot)} />
                  </div>
                  <p className="mt-3 font-mono text-[26px] font-semibold leading-none text-[var(--text-primary)]">{metric.value}</p>
                  <p className={cn("mt-2 text-[12px] font-medium", style.text)}>Threshold {metric.threshold}</p>
                </div>
              );
            })}
          </div>
        </Surface>

        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <SectionHeading
              icon={UsersRound}
              title="Cohort Watchlist"
              description="Cohorts with drift, fairness, or policy sensitivity requiring operator action."
            />
          </div>
          <div className="divide-y divide-[var(--border-subtle)]">
            {cohortWatchlist.map((cohort) => {
              const style = toneClass(cohort.tone);

              return (
                <div key={cohort.cohort} className="grid gap-3 px-5 py-4 md:grid-cols-[1fr_0.42fr_0.42fr_0.85fr] md:items-center">
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-semibold text-[var(--text-primary)]">{cohort.cohort}</p>
                    <p className="mt-1 text-[12px] text-[var(--text-muted)]">{cohort.volume}</p>
                  </div>
                  <p className={cn("font-mono text-[12px] font-semibold", style.text)}>{cohort.drift}</p>
                  <StatusBadge label={cohort.tone === "warning" ? "Watch" : "Stable"} tone={cohort.tone} />
                  <p className="text-[12px] leading-relaxed text-[var(--text-tertiary)]">{cohort.action}</p>
                </div>
              );
            })}
          </div>
        </Surface>
      </div>

      <Surface className="overflow-hidden">
        <div className="border-b border-[var(--border-card)] px-5 py-4">
          <SectionHeading
            icon={SlidersHorizontal}
            title="Policy Rule Battery"
            description="Rule coverage, owners, and live portfolio impact for risk operations."
          />
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[760px]">
            <div className="grid grid-cols-[1fr_0.7fr_0.45fr_0.8fr] border-b border-[var(--border-card)] bg-[var(--surface-secondary)]/45 px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
              <div>Rule</div>
              <div>Owner</div>
              <div>Coverage</div>
              <div>Effect</div>
            </div>
            {policyBattery.map((rule) => {
              const style = toneClass(rule.tone);

              return (
                <div key={rule.rule} className="grid grid-cols-[1fr_0.7fr_0.45fr_0.8fr] border-b border-[var(--border-subtle)] px-5 py-4">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className={cn("h-2 w-2 rounded-full", style.dot)} />
                    <span className="truncate text-[13px] font-semibold text-[var(--text-primary)]">{rule.rule}</span>
                  </div>
                  <p className="truncate text-[13px] text-[var(--text-secondary)]">{rule.owner}</p>
                  <p className="font-mono text-[12px] font-semibold text-[var(--text-primary)]">{rule.coverage}</p>
                  <p className={cn("truncate text-[12px] font-semibold", style.text)}>{rule.effect}</p>
                </div>
              );
            })}
          </div>
        </div>
      </Surface>
    </div>
  );
}

function ComplianceSettingsView() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Compliance/Settings"
        title="Governance controls for regulated credit operations."
        description="FREE-AI, DPDP, SOC2/ISO controls, API keys placeholder, role access, retention settings, and pricing credits preview."
      >
        <StatusBadge label="Audit-ready" tone="good" />
      </PageHeader>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {complianceControls.map((control) => (
          <Surface key={control.label} className="p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[12px] font-semibold text-[var(--text-primary)]">{control.label}</p>
              <span className={cn("h-2 w-2 rounded-full", toneClass(control.tone).dot)} />
            </div>
            <p className="mt-3 text-[20px] font-semibold text-[var(--text-primary)]">{control.value}</p>
            <p className="mt-2 text-[12px] leading-relaxed text-[var(--text-tertiary)]">{control.detail}</p>
          </Surface>
        ))}
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <SectionHeading icon={KeyRound} title="API Keys Placeholder" />
          </div>
          <div className="divide-y divide-[var(--border-subtle)] px-5">
            {apiKeyPlaceholders.map((key) => (
              <div key={key.label} className="grid gap-2 py-4 sm:grid-cols-[0.8fr_1fr_auto] sm:items-center">
                <p className="text-[13px] font-semibold text-[var(--text-primary)]">{key.label}</p>
                <code className="min-w-0 rounded-md border border-[var(--border-card)] bg-[var(--surface-secondary)]/40 px-2 py-1.5 font-mono text-[12px] text-[var(--text-secondary)]">
                  {key.value}
                </code>
                <StatusBadge label={key.status} tone="neutral" />
              </div>
            ))}
          </div>
        </Surface>

        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <SectionHeading icon={UsersRound} title="Role Access" />
          </div>
          <div className="divide-y divide-[var(--border-subtle)]">
            {roleAccess.map((role) => (
              <div key={role.role} className="grid gap-3 px-5 py-4 md:grid-cols-[0.8fr_0.35fr_1fr] md:items-center">
                <p className="text-[13px] font-semibold text-[var(--text-primary)]">{role.role}</p>
                <p className="font-mono text-[12px] font-semibold text-[var(--text-secondary)]">{role.users}</p>
                <p className="text-[12px] leading-relaxed text-[var(--text-tertiary)]">{role.access}</p>
              </div>
            ))}
          </div>
        </Surface>
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-3">
        <Surface className="p-5">
          <SectionHeading icon={LockKeyhole} title="Retention" />
          <div className="mt-5 space-y-4">
            <DataTile label="AA evidence" value="180 days" tone="good" />
            <DataTile label="Audit logs" value="7 years" tone="neutral" />
            <DataTile label="Raw documents" value="Policy scoped" tone="warning" />
          </div>
        </Surface>

        <Surface className="p-5">
          <SectionHeading icon={WalletCards} title="Pricing Credits Preview" />
          <div className="mt-5 space-y-4">
            <DataTile label="Decision credits" value="42,000 / month" tone="neutral" />
            <DataTile label="AA enrichment" value="INR 2.80 / pull" tone="good" />
            <DataTile label="Model explainability" value="Included" tone="good" />
          </div>
        </Surface>

        <Surface className="p-5">
          <SectionHeading icon={BookOpenCheck} title="Governance Battery" />
          <div className="mt-5 space-y-3">
            {["Human override required for reject", "Agentic recommendations cannot write actions", "Audit export includes reason code chain", "Policy changes require dual approval"].map((item) => (
              <div key={item} className="flex items-start gap-2 text-[13px] leading-relaxed text-[var(--text-secondary)]">
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                <span>{item}</span>
              </div>
            ))}
          </div>
        </Surface>
      </div>
    </div>
  );
}

function ActiveSection({
  active,
  onNavigate,
}: {
  active: PrototypeSectionId;
  onNavigate: (section: PrototypeSectionId) => void;
}) {
  switch (active) {
    case "overview":
      return <CommandCenterView />;
    case "command":
      return <CommandCenterView />;
    case "queue":
      return <CaseQueueView />;
    case "intake":
      return <EvidenceIntakeView />;
    case "dossier":
      return <CaseDossierView />;
    case "modelOps":
      return <ModelRiskOpsView />;
    case "compliance":
      return <ComplianceSettingsView />;
    default:
      return <CommandCenterView />;
  }
}

export function ArgentNorthPrototypeShell() {
  const [active, setActive] = useState<PrototypeSectionId>("overview");
  const [cmdkOpen, setCmdkOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdkOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <>
      {active === "overview" ? (
        <LandingPage onNavigate={setActive} />
      ) : (
        <PrototypeShellFrame active={active} onNavigate={setActive}>
          <PageTransition id={active}>
            <ActiveSection active={active} onNavigate={setActive} />
          </PageTransition>
        </PrototypeShellFrame>
      )}
      <CommandPalette
        open={cmdkOpen}
        onClose={() => setCmdkOpen(false)}
        onSelect={(id) => setActive(id as PrototypeSectionId)}
        items={prototypeSections}
      />
    </>
  );
}
