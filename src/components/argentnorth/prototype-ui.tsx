"use client";

import type { ComponentType, HTMLAttributes, ReactNode } from "react";
import { ArrowUpRight, CheckCircle2, Circle, Info, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { DecisionStatus, RiskTone } from "@/lib/argentnorth-prototype";
import { getToneForDecision } from "@/lib/argentnorth-prototype";
import { metricSparklines } from "@/lib/argentnorth-ui-prototype";

const toneStyles: Record<RiskTone, { text: string; bg: string; border: string; dot: string; soft: string }> = {
  good: {
    text: "text-emerald-700 dark:text-emerald-400",
    bg: "bg-emerald-500/8",
    border: "border-emerald-600/15",
    dot: "bg-emerald-600 dark:bg-emerald-500",
    soft: "from-emerald-500/10 to-transparent",
  },
  warning: {
    text: "text-amber-700 dark:text-amber-400",
    bg: "bg-amber-500/8",
    border: "border-amber-600/15",
    dot: "bg-amber-600 dark:bg-amber-500",
    soft: "from-amber-500/10 to-transparent",
  },
  danger: {
    text: "text-red-700 dark:text-red-400",
    bg: "bg-red-500/8",
    border: "border-red-600/15",
    dot: "bg-red-600 dark:bg-red-500",
    soft: "from-red-500/10 to-transparent",
  },
  neutral: {
    text: "text-blue-700 dark:text-blue-400",
    bg: "bg-blue-500/8",
    border: "border-blue-600/15",
    dot: "bg-blue-600 dark:bg-blue-500",
    soft: "from-blue-500/8 to-transparent",
  },
};

export function toneClass(tone: RiskTone) {
  return toneStyles[tone];
}

export function Surface({
  children,
  className,
  interactive = false,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
}) {
  return (
    <div
      {...props}
      className={cn(
        "rounded-md border border-[var(--border-card)] bg-[var(--surface-raised)] shadow-[var(--shadow-card)]",
        interactive && "transition-all duration-200 hover:border-[var(--border-card-hover)] hover:shadow-[var(--shadow-card-hover)]",
        className
      )}
    >
      {children}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div className="max-w-3xl">
        <p className="text-[13px] font-medium text-primary">{eyebrow}</p>
        <h1 className="mt-1 text-[24px] font-semibold tracking-[-0.02em] text-[var(--text-primary)] md:text-[30px]">
          {title}
        </h1>
        <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-[var(--text-tertiary)]">{description}</p>
      </div>
      {children ? <div className="flex flex-wrap items-center gap-2">{children}</div> : null}
    </div>
  );
}

export function SectionHeading({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">{title}</h2>
        {description ? <p className="mt-1 text-[13px] leading-relaxed text-[var(--text-tertiary)]">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function StatusBadge({ label, tone = "neutral" }: { label: string; tone?: RiskTone }) {
  const style = toneClass(tone);
  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1.5 rounded-[5px] border px-2 py-0.5 text-[11px] font-medium",
        style.bg,
        style.border,
        style.text
      )}
    >
      <span className={cn("h-1 w-1 rounded-full", style.dot)} />
      {label}
    </Badge>
  );
}

export function DecisionBadge({ decision }: { decision: DecisionStatus }) {
  const labels: Record<DecisionStatus, string> = {
    approve: "Approve",
    manual_review: "Manual Review",
    reject: "Reject",
  };

  return <StatusBadge label={labels[decision]} tone={getToneForDecision(decision)} />;
}

export function MetricCard({
  label,
  value,
  delta,
  tone = "neutral",
  icon: Icon,
  sparkData,
}: {
  label: string;
  value: string;
  delta?: string;
  tone?: RiskTone;
  icon?: ComponentType<{ className?: string }>;
  sparkData?: number[];
}) {
  const style = toneClass(tone);
  const spark = sparkData ?? metricSparklines[label];
  const sparkMax = spark?.length ? Math.max(...spark) || 1 : 1;

  return (
    <Surface className="relative overflow-hidden p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--text-muted)]">{label}</p>
          <p className="mt-2.5 text-[26px] font-semibold leading-none tracking-[-0.01em] text-[var(--text-primary)] tabular-nums">
            {value}
          </p>
        </div>
        {Icon ? (
          <div className={cn("flex h-8 w-8 items-center justify-center rounded-md", style.bg)}>
            <Icon className={cn("h-3.5 w-3.5", style.text)} />
          </div>
        ) : null}
      </div>
      {delta ? <p className={cn("mt-3 text-[12px] font-medium", style.text)}>{delta}</p> : null}
      {spark?.length ? (
        <div className="mt-3 flex h-7 items-end gap-[3px]" aria-hidden="true">
          {spark.map((point, index) => (
            <span
              key={`${label}-${index}`}
              className={cn("w-full rounded-sm", style.dot)}
              style={{ height: `${Math.max(14, (point / sparkMax) * 100)}%`, opacity: 0.12 + (index / spark.length) * 0.4 }}
            />
          ))}
        </div>
      ) : null}
    </Surface>
  );
}

export function ProgressBar({
  value,
  tone = "neutral",
  className,
}: {
  value: number;
  tone?: RiskTone;
  className?: string;
}) {
  const style = toneClass(tone);
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-[var(--surface-secondary)]", className)}>
      <div className={cn("h-full rounded-full", style.dot)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function RiskScore({ score, size = "md" }: { score: number; size?: "sm" | "md" | "lg" }) {
  const tone: RiskTone = score >= 70 ? "danger" : score >= 45 ? "warning" : "good";
  const style = toneClass(tone);
  const dimensions = size === "lg" ? "h-36 w-36" : size === "sm" ? "h-20 w-20" : "h-28 w-28";
  const text = size === "lg" ? "text-[36px]" : size === "sm" ? "text-[22px]" : "text-[30px]";

  return (
    <div
      className={cn("grid shrink-0 place-items-center rounded-full", dimensions)}
      style={{
        background: `conic-gradient(currentColor ${score * 3.6}deg, var(--surface-secondary) 0deg)`,
        color: score >= 70 ? "#ef4444" : score >= 45 ? "#f59e0b" : "#10b981",
      }}
    >
      <div className="grid h-[78%] w-[78%] place-items-center rounded-full bg-[var(--surface-raised)] text-center">
        <div>
          <p className={cn("font-semibold leading-none tracking-tight text-[var(--text-primary)] tabular-nums", text)}>
            {score}
          </p>
          <p className={cn("mt-1 text-[10px] font-semibold uppercase tracking-[0.16em]", style.text)}>risk</p>
        </div>
      </div>
    </div>
  );
}

export function DataTile({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: RiskTone;
}) {
  const style = toneClass(tone);
  return (
    <div className="rounded-md border border-[var(--border-card)] bg-[var(--surface-secondary)]/40 px-3 py-3">
      <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--text-muted)]">{label}</p>
      <p className={cn("mt-1.5 text-[14px] font-semibold text-[var(--text-primary)]", tone !== "neutral" && style.text)}>
        {value}
      </p>
    </div>
  );
}

export function DriverBar({
  label,
  value,
  direction,
}: {
  label: string;
  value: number;
  direction: "raises" | "lowers";
}) {
  const tone: RiskTone = direction === "raises" ? "danger" : "good";
  const style = toneClass(tone);
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-3">
        <span className="truncate text-[13px] font-medium text-[var(--text-secondary)]">{label}</span>
        <span className={cn("text-[12px] font-semibold tabular-nums", style.text)}>
          {direction === "raises" ? "+" : "-"}
          {value}
        </span>
      </div>
      <ProgressBar value={value * 4} tone={tone} className="h-1.5" />
    </div>
  );
}

export function TimelineRow({
  label,
  detail,
  time,
  tone = "neutral",
}: {
  label: string;
  detail: string;
  time: string;
  tone?: RiskTone;
}) {
  const style = toneClass(tone);
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <span className={cn("mt-1.5 h-2 w-2 rounded-full", style.dot)} />
        <span className="mt-1.5 h-full w-px bg-[var(--border-subtle)]" />
      </div>
      <div className="min-w-0 flex-1 pb-4">
        <div className="flex items-start justify-between gap-3">
          <p className="text-[13px] font-semibold text-[var(--text-primary)]">{label}</p>
          <span className="shrink-0 font-mono text-[11px] text-[var(--text-muted)]">{time}</span>
        </div>
        <p className="mt-1 text-[13px] leading-relaxed text-[var(--text-tertiary)]">{detail}</p>
      </div>
    </div>
  );
}

export function EmptyPrototype({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <Surface className="px-5 py-10 text-center">
      <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--surface-secondary)]">
        <Info className="h-4 w-4 text-[var(--text-muted)]" />
      </div>
      <p className="mt-3 text-[13px] font-semibold text-[var(--text-primary)]">{title}</p>
      <p className="mx-auto mt-1 max-w-sm text-[12px] leading-relaxed text-[var(--text-muted)]">{body}</p>
    </Surface>
  );
}

export function PrototypeBanner() {
  return (
    <Surface className="border-primary/10 bg-primary/[0.03] px-4 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-2.5">
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/[0.07]">
            <ShieldCheck className="h-3.5 w-3.5 text-primary" />
          </div>
          <div>
            <p className="text-[13px] font-semibold text-[var(--text-primary)]">Enterprise prototype</p>
            <p className="mt-0.5 text-[12px] text-[var(--text-muted)]">
              Static data is used to demonstrate the institutional credit-intelligence experience.
            </p>
          </div>
        </div>
        <Badge variant="outline" className="w-fit rounded-[5px] border-primary/15 bg-primary/[0.06] text-[11px] font-medium text-primary">
          Prototype
        </Badge>
      </div>
    </Surface>
  );
}

export function InlineLinkLabel({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap text-[12px] font-semibold text-primary">
      {children}
      <ArrowUpRight className="h-3 w-3" />
    </span>
  );
}

export function HealthDot({ tone = "neutral" }: { tone?: RiskTone }) {
  return (
    <span className="relative flex h-2 w-2">
      <span className={cn("relative inline-flex h-2 w-2 rounded-full", toneClass(tone).dot)} />
    </span>
  );
}

export function ComplianceStrip() {
  return (
    <div className="grid gap-3 md:grid-cols-4">
      {[
        { label: "FREE-AI", value: "Understandable by design", tone: "good" as RiskTone },
        { label: "SOC2", value: "Controls mapped", tone: "good" as RiskTone },
        { label: "BIAN", value: "Service domains aligned", tone: "neutral" as RiskTone },
        { label: "DPDP", value: "Data minimization active", tone: "good" as RiskTone },
      ].map((item) => (
        <Surface key={item.label} className="px-4 py-3">
          <div className="flex items-center gap-2">
            <span className={cn("h-1.5 w-1.5 rounded-full", toneClass(item.tone).dot)} />
            <p className="text-[12px] font-semibold text-[var(--text-primary)]">{item.label}</p>
          </div>
          <p className="mt-1.5 text-[12px] text-[var(--text-tertiary)]">{item.value}</p>
        </Surface>
      ))}
    </div>
  );
}

export function CheckItem({ children, tone = "good" }: { children: ReactNode; tone?: RiskTone }) {
  return (
    <div className="flex items-start gap-2 text-[13px] leading-relaxed text-[var(--text-secondary)]">
      {tone === "good" ? (
        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
      ) : (
        <Circle className={cn("mt-1 h-2.5 w-2.5 shrink-0 fill-current", toneClass(tone).text)} />
      )}
      <span>{children}</span>
    </div>
  );
}
