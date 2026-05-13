"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import type { RiskTone } from "@/lib/argentnorth-prototype";

/* ═══════════════════════════════════════
   ANIMATED NUMBER — Stripe-style counter
   ═══════════════════════════════════════ */
export function AnimatedNumber({ value, className }: { value: string; className?: string }) {
  return (
    <motion.span
      key={value}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      className={className}
    >
      {value}
    </motion.span>
  );
}

/* ═══════════════════════════════════════
   SPARKLINE — Ramp-style inline trend
   ═══════════════════════════════════════ */
export function Sparkline({
  data,
  width = 80,
  height = 28,
  tone = "neutral",
  className,
}: {
  data: number[];
  width?: number;
  height?: number;
  tone?: RiskTone;
  className?: string;
}) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pad = 2;

  const points = data
    .map((v, i) => {
      const x = pad + (i / (data.length - 1)) * (width - pad * 2);
      const y = height - pad - ((v - min) / range) * (height - pad * 2);
      return `${x},${y}`;
    })
    .join(" ");

  const colors: Record<RiskTone, string> = {
    good: "#059669",
    warning: "#D97706",
    danger: "#DC3545",
    neutral: "var(--primary)",
  };

  return (
    <svg width={width} height={height} className={cn("shrink-0", className)} viewBox={`0 0 ${width} ${height}`}>
      <polyline
        fill="none"
        stroke={colors[tone]}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
        opacity="0.85"
      />
      <circle cx={points.split(" ").pop()?.split(",")[0]} cy={points.split(" ").pop()?.split(",")[1]} r="2" fill={colors[tone]} />
    </svg>
  );
}

/* ═══════════════════════════════════════
   SVG GAUGE ARC — Animated risk score
   ═══════════════════════════════════════ */
export function GaugeArc({ score, size = 140 }: { score: number; size?: number }) {
  const r = (size - 16) / 2;
  const circumference = 2 * Math.PI * r;
  const progress = (score / 100) * circumference;
  const color = score >= 70 ? "#DC3545" : score >= 45 ? "#D97706" : "#059669";
  const trackColor = "var(--gauge-track)";

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={trackColor} strokeWidth="5" />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference - progress }}
          transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="text-[28px] font-semibold leading-none tracking-tight text-[var(--text-primary)] tabular-nums"
        >
          {score}
        </motion.span>
        <span className="mt-1 text-[10px] font-medium uppercase tracking-[0.1em]" style={{ color }}>
          risk
        </span>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════
   SHAP WATERFALL — Explainability chart
   ═══════════════════════════════════════ */
export function WaterfallChart({
  drivers,
}: {
  drivers: Array<{ label: string; value: number; direction: "raises" | "lowers" }>;
}) {
  const maxVal = Math.max(...drivers.map((d) => d.value));

  return (
    <div className="space-y-3">
      {drivers.map((driver, i) => {
        const width = (driver.value / (maxVal || 1)) * 100;
        const isRaise = driver.direction === "raises";

        return (
          <motion.div
            key={driver.label}
            initial={{ opacity: 0, x: isRaise ? 16 : -16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
            className="group"
          >
            <div className="flex items-center justify-between gap-3 mb-1.5">
              <span className="truncate text-[13px] font-medium text-[var(--text-secondary)]">{driver.label}</span>
              <span
                className={cn(
                  "text-[12px] font-semibold tabular-nums",
                  isRaise ? "text-red-500 dark:text-red-400" : "text-emerald-500 dark:text-emerald-400"
                )}
              >
                {isRaise ? "+" : "−"}{driver.value}
              </span>
            </div>
            <div className="relative h-2 w-full overflow-hidden rounded-full bg-[var(--surface-secondary)]">
              <motion.div
                className={cn("h-full rounded-full", isRaise ? "bg-red-500/80" : "bg-emerald-500/80")}
                initial={{ width: 0 }}
                animate={{ width: `${width}%` }}
                transition={{ duration: 0.6, delay: i * 0.08 + 0.1, ease: [0.16, 1, 0.3, 1] }}
                style={{ marginLeft: isRaise ? undefined : "auto", float: isRaise ? "left" : "right" }}
              />
            </div>
          </motion.div>
        );
      })}
      <div className="mt-4 flex items-center gap-4 text-[11px] text-[var(--text-muted)]">
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-red-500/80" /> Raises risk</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-emerald-500/80" /> Lowers risk</span>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════
   EVIDENCE FLOW GRAPH — Palantir lineage
   ═══════════════════════════════════════ */
const flowToneColors: Record<RiskTone, string> = {
  good: "#059669",
  warning: "#D97706",
  danger: "#DC3545",
  neutral: "var(--primary)",
};

export function EvidenceFlowGraph({
  nodes,
}: {
  nodes: Array<{ source: string; target: string; detail: string; tone: RiskTone }>;
}) {
  const uniqueLabels = Array.from(new Set(nodes.flatMap((n) => [n.source, n.target])));
  const nodeWidth = 130;
  const gapX = 48;
  const svgHeight = 80;
  const totalWidth = uniqueLabels.length * (nodeWidth + gapX) - gapX;

  const getX = (label: string) => uniqueLabels.indexOf(label) * (nodeWidth + gapX);

  return (
    <div className="overflow-x-auto">
      <div style={{ minWidth: totalWidth }} className="relative">
        {/* SVG edges */}
        <svg width={totalWidth} height={svgHeight} className="absolute top-0 left-0">
          {nodes.map((edge, i) => {
            const x1 = getX(edge.source) + nodeWidth;
            const x2 = getX(edge.target);
            const y = svgHeight / 2;
            return (
              <motion.line
                key={`${edge.source}-${edge.target}`}
                x1={x1}
                y1={y}
                x2={x2}
                y2={y}
                stroke={flowToneColors[edge.tone]}
                strokeWidth="2"
                strokeDasharray="6,4"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 0.5 }}
                transition={{ duration: 0.6, delay: i * 0.15 + 0.3 }}
              />
            );
          })}
        </svg>
        {/* Node labels */}
        <div className="relative flex" style={{ height: svgHeight }}>
          {uniqueLabels.map((label, i) => {
            const edgeForNode = nodes.find((n) => n.target === label || n.source === label);
            const tone = edgeForNode?.tone ?? "neutral";
            return (
              <motion.div
                key={label}
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.35, delay: i * 0.1 }}
                className="absolute flex items-center justify-center"
                style={{ left: getX(label), width: nodeWidth, height: svgHeight }}
              >
                <div
                  className={cn(
                    "flex h-[42px] w-full items-center justify-center rounded-lg border px-2 text-center text-[11px] font-semibold transition-shadow",
                    "bg-[var(--surface-raised)] text-[var(--text-primary)] shadow-sm hover:shadow-md"
                  )}
                  style={{ borderColor: flowToneColors[tone] + "40" }}
                >
                  <span className="h-2 w-2 shrink-0 rounded-full mr-2" style={{ backgroundColor: flowToneColors[tone] }} />
                  {label}
                </div>
              </motion.div>
            );
          })}
        </div>
        {/* Edge labels below */}
        <div className="relative flex mt-2" style={{ height: 32 }}>
          {nodes.map((edge, i) => {
            const x1 = getX(edge.source) + nodeWidth;
            const x2 = getX(edge.target);
            const midX = (x1 + x2) / 2;
            const w = x2 - x1;
            return (
              <motion.div
                key={`label-${edge.source}-${edge.target}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.15 + 0.5 }}
                className="absolute text-center text-[10px] text-[var(--text-muted)]"
                style={{ left: midX - w / 2, width: w }}
              >
                {edge.detail}
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════
   AREA CHART — Exposure trend
   ═══════════════════════════════════════ */
export function AreaChart({
  data,
  labels,
  height = 160,
  className,
}: {
  data: number[];
  labels?: string[];
  height?: number;
  className?: string;
}) {
  if (data.length < 2) return null;
  const w = 400;
  const h = height;
  const pad = { top: 8, right: 8, bottom: 24, left: 8 };
  const min = Math.min(...data) * 0.9;
  const max = Math.max(...data) * 1.05;
  const range = max - min || 1;

  const points = data.map((v, i) => ({
    x: pad.left + (i / (data.length - 1)) * (w - pad.left - pad.right),
    y: pad.top + (1 - (v - min) / range) * (h - pad.top - pad.bottom),
  }));

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
  const areaPath = `${linePath} L${points[points.length - 1].x},${h - pad.bottom} L${points[0].x},${h - pad.bottom} Z`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={cn("w-full", className)} preserveAspectRatio="none">
      <defs>
        <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.2" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <motion.path
        d={areaPath}
        fill="url(#areaFill)"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8 }}
      />
      <motion.path
        d={linePath}
        fill="none"
        stroke="var(--primary)"
        strokeWidth="2"
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
      />
      {labels &&
        labels.map((lbl, i) => {
          const x = pad.left + (i / (labels.length - 1)) * (w - pad.left - pad.right);
          return (
            <text
              key={lbl}
              x={x}
              y={h - 4}
              textAnchor="middle"
              fontSize="10"
              fill="var(--text-muted)"
              fontFamily="var(--font-mono)"
            >
              {lbl}
            </text>
          );
        })}
    </svg>
  );
}

/* ═══════════════════════════════════════
   MOTION WRAPPERS — Staggered reveals
   ═══════════════════════════════════════ */
export function StaggerContainer({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06 } } }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 12 },
        show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] } },
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ═══════════════════════════════════════
   PAGE TRANSITION — Section swap wrapper
   ═══════════════════════════════════════ */
export function PageTransition({ id, children }: { id: string; children: ReactNode }) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={id}
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

/* ═══════════════════════════════════════
   COMMAND PALETTE — Cmd+K quick nav
   ═══════════════════════════════════════ */
export function CommandPalette({
  open,
  onClose,
  onSelect,
  items,
}: {
  open: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
  items: Array<{ id: string; label: string; shortLabel: string; description: string }>;
}) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      const timer = window.setTimeout(() => {
        setQuery("");
        inputRef.current?.focus();
      }, 50);

      return () => window.clearTimeout(timer);
    }
  }, [open]);

  const filtered = items.filter(
    (it) =>
      it.label.toLowerCase().includes(query.toLowerCase()) ||
      it.description.toLowerCase().includes(query.toLowerCase())
  );

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: -8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: -8 }}
          transition={{ duration: 0.2 }}
          className="w-full max-w-lg overflow-hidden rounded-xl border border-[var(--border-card)] bg-[var(--surface-raised)] shadow-[var(--shadow-elevated)]"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center gap-3 border-b border-[var(--border-card)] px-4 py-3">
            <kbd className="rounded border border-[var(--border-card)] bg-[var(--surface-secondary)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--text-muted)]">
              ⌘K
            </kbd>
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Jump to section, case, or action..."
              className="flex-1 bg-transparent text-[14px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none"
              onKeyDown={(e) => {
                if (e.key === "Escape") onClose();
                if (e.key === "Enter" && filtered.length > 0) {
                  onSelect(filtered[0].id);
                  onClose();
                }
              }}
            />
          </div>
          <div className="max-h-[320px] overflow-y-auto p-2">
            {filtered.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => { onSelect(item.id); onClose(); }}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-[var(--surface-secondary)]"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10">
                  <span className="text-[11px] font-bold text-primary">{item.shortLabel.charAt(0)}</span>
                </div>
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-[var(--text-primary)]">{item.label}</p>
                  <p className="truncate text-[11px] text-[var(--text-muted)]">{item.description}</p>
                </div>
              </button>
            ))}
            {filtered.length === 0 && (
              <p className="py-6 text-center text-[13px] text-[var(--text-muted)]">No results found</p>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

/* ═══════════════════════════════════════
   LIVE PULSE DOT — Audit stream pulse
   ═══════════════════════════════════════ */
export function LivePulseDot({ tone = "good" }: { tone?: RiskTone }) {
  const color = flowToneColors[tone];
  return (
    <span className="relative flex h-2.5 w-2.5">
      <motion.span
        className="absolute inline-flex h-full w-full rounded-full"
        style={{ backgroundColor: color }}
        animate={{ scale: [1, 1.8, 1], opacity: [0.4, 0, 0.4] }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
      />
      <span className="relative inline-flex h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
    </span>
  );
}
