"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence, useInView } from "framer-motion";
import {
  Building2,
  FileText,
  ReceiptText,
  Landmark,
  CreditCard,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Zap,
  Eye,
  Scale,
  Activity,
  Clock,
} from "lucide-react";

/* ─────────────────────────────────────────────────────
 *  HeroDecisionFlow — Dashboard Screenshot
 *
 *  A single dark product-preview card styled to look
 *  like the actual ArgentNorth decision engine UI.
 *  Data populates live as a decision processes.
 *  Always dark — independent of page theme.
 * ───────────────────────────────────────────────────── */

// ── Data ──

const dataSources = [
  { id: "bureau", icon: Building2, label: "Credit Bureau", sub: "CIBIL · Experian" },
  { id: "bank", icon: Landmark, label: "Bank Statements", sub: "12 mo · 3 accounts" },
  { id: "gst", icon: ReceiptText, label: "GST Returns", sub: "GSTR-1 · GSTR-3B" },
  { id: "itr", icon: FileText, label: "ITR / Financials", sub: "AY 2024-25" },
  { id: "aa", icon: CreditCard, label: "Account Aggregator", sub: "UPI · AA flow" },
];

const shapBars = [
  { feature: "Bureau Score", value: 0.82, direction: "positive" as const },
  { feature: "Cash Flow Stability", value: 0.65, direction: "positive" as const },
  { feature: "GST Compliance", value: 0.48, direction: "positive" as const },
  { feature: "Sector Concentration", value: 0.22, direction: "negative" as const },
  { feature: "Vintage", value: 0.35, direction: "positive" as const },
];

const policyChecks = [
  { id: "kyc", label: "KYC / AML", status: "pass" as const },
  { id: "dti", label: "DTI < 50%", status: "pass" as const },
  { id: "vintage", label: "Vintage ≥ 36mo", status: "pass" as const },
  { id: "dpd", label: "No DPD 90+", status: "pass" as const },
  { id: "sector", label: "Sector limit", status: "warn" as const },
];

// ── Animation phases ──
type Phase = 0 | 1 | 2 | 3 | 4;
const PHASE_DURATIONS = [800, 2000, 2600, 2200, 3400];

// ── Animated score hook ──

function useAnimatedScore(target: number, active: boolean, duration = 1200) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!active) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setValue(0);
      return;
    }
    let raf: number;
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      setValue(Math.round((1 - Math.pow(1 - p, 3)) * target));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, target, duration]);
  return value;
}

// ── Main export ──

export function HeroDecisionFlow() {
  const containerRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(containerRef as React.RefObject<Element>, {
    once: false,
    margin: "-40px",
  });
  const [phase, setPhase] = useState<Phase>(0);
  const [sourceCount, setSourceCount] = useState(0);
  const [policyCount, setPolicyCount] = useState(0);
  const riskScore = useAnimatedScore(24, phase >= 2);

  // Phase cycling
  useEffect(() => {
    if (!isInView) return;
    let timeout: ReturnType<typeof setTimeout>;
    let current = 0;
    const advance = () => {
      current = (current + 1) % 5;
      setPhase(current as Phase);
      timeout = setTimeout(advance, PHASE_DURATIONS[current]);
    };
    timeout = setTimeout(advance, PHASE_DURATIONS[0]);
    return () => clearTimeout(timeout);
  }, [isInView]);

  // Source ingestion
  useEffect(() => {
    if (phase < 1) { setSourceCount(0); return; }
    if (phase >= 2) { setSourceCount(5); return; }
    let i = 0;
    const interval = setInterval(() => {
      i++;
      setSourceCount(i);
      if (i >= 5) clearInterval(interval);
    }, 320);
    return () => clearInterval(interval);
  }, [phase]);

  // Policy ticking
  useEffect(() => {
    if (phase < 3) { setPolicyCount(0); return; }
    let i = 0;
    const interval = setInterval(() => {
      i++;
      setPolicyCount(i);
      if (i >= 5) clearInterval(interval);
    }, 340);
    return () => clearInterval(interval);
  }, [phase]);

  const isDecisionReady = phase >= 4;

  return (
    <div ref={containerRef}>
      {/* ── Outer card — always dark, product-screenshot style ── */}
      <div
        className="overflow-hidden rounded-2xl border border-slate-800/80"
        style={{
          background: "linear-gradient(145deg, #0c1222 0%, #111827 50%, #0f172a 100%)",
          boxShadow:
            "0 0 0 1px rgba(148,163,184,0.05), 0 25px 60px -12px rgba(0,0,0,0.5), 0 12px 24px -8px rgba(0,0,0,0.25)",
        }}
      >
        {/* ── Window chrome ── */}
        <div className="flex items-center justify-between border-b border-slate-800/60 px-5 py-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div className="h-[10px] w-[10px] rounded-full bg-[#334155]" />
              <div className="h-[10px] w-[10px] rounded-full bg-[#334155]" />
              <div className="h-[10px] w-[10px] rounded-full bg-[#334155]" />
            </div>
            <div className="h-4 w-px bg-slate-800" />
            <div className="flex items-center gap-2.5">
              <div className="flex h-[18px] w-[18px] shrink-0 items-center justify-center text-white">
                <svg viewBox="0 0 100 100" className="h-full w-full" fill="currentColor">
                  <mask id="bottom-left-cut-hero">
                    <rect width="100" height="100" fill="white" />
                    <line x1="0" y1="52" x2="48" y2="100" stroke="black" strokeWidth="8" />
                  </mask>
                  <path d="M 0 0 L 46 0 L 46 12 A 34 34 0 0 1 12 46 L 0 46 Z" />
                  <path d="M 54 0 L 100 0 L 100 46 L 88 46 A 34 34 0 0 1 54 12 Z" />
                  <path d="M 88 54 L 100 54 L 100 100 L 54 100 L 54 88 A 34 34 0 0 1 88 54 Z" />
                  <path d="M 0 54 L 12 54 A 34 34 0 0 1 46 88 L 46 100 L 0 100 Z" mask="url(#bottom-left-cut-hero)" />
                </svg>
              </div>
              <span className="text-[13px] font-semibold tracking-[-0.01em] text-slate-200">
                ArgentNorth
              </span>
              <span className="ml-1 text-[11px] text-slate-600">·</span>
              <span className="ml-1 font-mono text-[11px] text-slate-500">Decision Engine v4.2</span>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-40" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            <span className="text-[10px] font-medium text-emerald-400/80">Live</span>
          </div>
        </div>

        {/* ── Case header ── */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/40 px-5 py-2.5">
          <div className="flex items-center gap-3">
            <span className="rounded bg-slate-800/80 px-2 py-0.5 font-mono text-[11px] font-medium text-slate-400">
              #CAS-2847
            </span>
            <span className="text-[12.5px] font-medium text-slate-200">
              Acme Industries Pvt Ltd
            </span>
            <span className="hidden text-[11px] text-slate-600 sm:inline">·</span>
            <span className="hidden font-mono text-[11px] text-slate-500 sm:inline">SME Working Capital</span>
          </div>
          <AnimatePresence mode="wait">
            {isDecisionReady ? (
              <motion.span
                key="done"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-400"
              >
                <CheckCircle2 className="h-3 w-3" />
                Completed
              </motion.span>
            ) : (
              <motion.span
                key="processing"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-blue-400"
              >
                <Activity className="h-3 w-3 animate-pulse" />
                Processing
              </motion.span>
            )}
          </AnimatePresence>
        </div>

        {/* ── Dashboard body ── */}
        <div className="p-4 sm:p-5">
          {/* Top: Data Sources + Risk Assessment */}
          <div className="grid gap-4 lg:grid-cols-[200px_1fr]">
            {/* Data Sources */}
            <div className="rounded-lg border border-slate-800/60 bg-[#0a1018] p-3.5">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-slate-500">
                  Data Sources
                </span>
                <span className="font-mono text-[10px] font-semibold tabular-nums text-slate-500">
                  {sourceCount}/5
                </span>
              </div>
              <div className="space-y-1">
                {dataSources.map((src, i) => {
                  const Icon = src.icon;
                  const ingested = i < sourceCount;
                  return (
                    <div
                      key={src.id}
                      className="flex items-center gap-2.5 rounded-md px-2 py-[5px] transition-all duration-300"
                      style={{
                        background: ingested ? "rgba(59,130,246,0.06)" : "transparent",
                      }}
                    >
                      <div
                        className="flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded transition-colors duration-300"
                        style={{
                          background: ingested ? "rgba(59,130,246,0.15)" : "rgba(51,65,85,0.2)",
                        }}
                      >
                        {ingested ? (
                          <CheckCircle2 className="h-2.5 w-2.5 text-blue-400" />
                        ) : (
                          <Icon className="h-2.5 w-2.5 text-slate-600" />
                        )}
                      </div>
                      <span
                        className="flex-1 text-[10.5px] font-medium transition-colors duration-300"
                        style={{ color: ingested ? "#cbd5e1" : "#475569" }}
                      >
                        {src.label}
                      </span>
                      <span
                        className="font-mono text-[9px] transition-colors duration-300"
                        style={{ color: ingested ? "#60a5fa" : "#1e293b" }}
                      >
                        {ingested ? "✓" : "—"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Risk Assessment */}
            <div className="rounded-lg border border-slate-800/60 bg-[#0a1018] p-3.5">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Eye className="h-3 w-3 text-slate-500" />
                  <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-slate-500">
                    Risk Assessment
                  </span>
                </div>
                {phase >= 2 && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[9px] font-semibold text-emerald-400"
                  >
                    <span className="h-1 w-1 rounded-full bg-emerald-500" />
                    Low Risk
                  </motion.span>
                )}
              </div>

              <div className="grid gap-4 sm:grid-cols-[110px_1fr]">
                {/* Score */}
                <div className="flex flex-col items-center justify-center rounded-lg border border-slate-800/40 bg-slate-950/60 py-3">
                  <span className="font-mono text-[34px] font-bold leading-none tracking-tighter text-slate-100">
                    {phase >= 2 ? riskScore : "—"}
                  </span>
                  <span className="mt-1 font-mono text-[10px] text-slate-500">/ 100</span>
                  <span className="mt-1.5 font-mono text-[8px] font-medium uppercase tracking-widest text-slate-600">
                    composite score
                  </span>
                </div>

                {/* SHAP bars */}
                <div>
                  <p className="mb-2 font-mono text-[8.5px] font-bold uppercase tracking-[0.08em] text-slate-600">
                    SHAP Explainability
                  </p>
                  <div className="space-y-[7px]">
                    {shapBars.map((bar, i) => (
                      <div key={bar.feature} className="flex items-center gap-2.5">
                        <span className="w-[95px] shrink-0 truncate text-[10.5px] text-slate-400">
                          {bar.feature}
                        </span>
                        <div className="relative h-[5px] flex-1 overflow-hidden rounded-full bg-slate-800/80">
                          <motion.div
                            className="absolute inset-y-0 left-0 rounded-full"
                            style={{
                              background:
                                bar.direction === "positive"
                                  ? "linear-gradient(90deg, #3b82f6, #60a5fa)"
                                  : "linear-gradient(90deg, #ef4444, #f87171)",
                            }}
                            initial={{ width: 0 }}
                            animate={{
                              width: phase >= 2 ? `${bar.value * 100}%` : "0%",
                            }}
                            transition={{ duration: 0.6, delay: 0.15 + i * 0.08 }}
                          />
                        </div>
                        <span className="w-[34px] text-right font-mono text-[9.5px] tabular-nums text-slate-500">
                          {phase >= 2
                            ? `${bar.direction === "negative" ? "-" : "+"}${bar.value.toFixed(2)}`
                            : "—"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Policy Battery */}
          <div className="mt-3.5 rounded-lg border border-slate-800/60 bg-[#0a1018] p-3.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-3 w-3 text-slate-500" />
                <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-slate-500">
                  Policy Battery
                </span>
              </div>
              {phase >= 3 && policyCount > 0 && (
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="font-mono text-[10px] font-semibold tabular-nums text-slate-400"
                >
                  {policyCount}/{policyChecks.length} evaluated
                </motion.span>
              )}
            </div>
            <div className="mt-2.5 flex flex-wrap gap-2">
              {policyChecks.map((check, i) => {
                const ticked = i < policyCount;
                const warn = check.status === "warn" && ticked;
                return (
                  <div
                    key={check.id}
                    className="flex items-center gap-1.5 rounded-md border px-2.5 py-1 transition-all duration-300"
                    style={{
                      borderColor: ticked
                        ? warn ? "rgba(217,119,6,0.3)" : "rgba(34,197,94,0.2)"
                        : "rgba(51,65,85,0.3)",
                      background: ticked
                        ? warn ? "rgba(217,119,6,0.05)" : "rgba(34,197,94,0.04)"
                        : "transparent",
                    }}
                  >
                    {ticked ? (
                      warn ? (
                        <AlertTriangle className="h-3 w-3 text-amber-500" />
                      ) : (
                        <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                      )
                    ) : (
                      <div className="h-3 w-3 rounded-full border border-slate-700" />
                    )}
                    <span
                      className="text-[10.5px] font-medium transition-colors duration-300"
                      style={{ color: ticked ? "#cbd5e1" : "#475569" }}
                    >
                      {check.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Decision Output */}
          <div
            className="mt-3.5 rounded-lg border p-3.5 transition-all duration-500"
            style={{
              borderColor: isDecisionReady ? "rgba(34,197,94,0.25)" : "rgba(51,65,85,0.3)",
              background: isDecisionReady ? "rgba(34,197,94,0.03)" : "#0a1018",
              boxShadow: isDecisionReady ? "0 0 24px rgba(34,197,94,0.05)" : "none",
            }}
          >
            <div className="flex items-center gap-2">
              <Scale className="h-3 w-3 text-slate-500" />
              <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-slate-500">
                Decision Output
              </span>
            </div>

            <AnimatePresence mode="wait">
              {isDecisionReady ? (
                <motion.div
                  key="verdict"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.35 }}
                  className="mt-3"
                >
                  <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[18px] font-bold tracking-tight text-emerald-400">
                        APPROVED
                      </span>
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    </div>
                    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px]">
                      <div>
                        <span className="text-slate-500">Credit Limit </span>
                        <span className="font-mono font-semibold text-slate-200">₹42,00,000</span>
                      </div>
                      <div>
                        <span className="text-slate-500">Risk Band </span>
                        <span className="font-mono font-semibold text-emerald-400">Low</span>
                      </div>
                      <div>
                        <span className="text-slate-500">Policies </span>
                        <span className="font-mono font-semibold text-slate-200">4/5 pass</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3 text-slate-600" />
                        <span className="font-mono font-semibold text-slate-300">340ms</span>
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-800/40 pt-2.5">
                    <span className="inline-flex items-center gap-1 rounded bg-blue-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.05em] text-blue-400">
                      <Eye className="h-2.5 w-2.5" />
                      Explainability Report
                    </span>
                    <span className="inline-flex items-center gap-1 rounded bg-slate-800/60 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.05em] text-slate-400">
                      <ShieldCheck className="h-2.5 w-2.5" />
                      Audit Trail
                    </span>
                    <span className="ml-auto hidden font-mono text-[9px] text-slate-700 sm:inline">
                      2025-05-11 · engine-v4.2.1
                    </span>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key="pending"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 0.6 }}
                  exit={{ opacity: 0 }}
                  className="mt-3 flex items-center gap-2 py-2"
                >
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-[1.5px] border-slate-700 border-t-blue-500/60" />
                  <span className="font-mono text-[11px] text-slate-600">
                    Awaiting pipeline completion…
                  </span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* ── Bottom status bar ── */}
        <div className="flex items-center justify-between border-t border-slate-800/40 px-5 py-2">
          <div className="flex items-center gap-2 sm:gap-3">
            <span className="font-mono text-[9px] text-slate-600">RBI-FREE-AI</span>
            <span className="text-slate-800">·</span>
            <span className="font-mono text-[9px] text-slate-600">ISO 27001</span>
            <span className="text-slate-800">·</span>
            <span className="font-mono text-[9px] text-slate-600">SOC 2 Type II</span>
          </div>
          <span className="font-mono text-[9px] text-slate-700">BIAN 14.0</span>
        </div>
      </div>
    </div>
  );
}
