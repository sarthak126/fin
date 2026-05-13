"use client";

export type {
  AnalysisDecision,
  BankStatementBehavioralFlags as BehavioralFlags,
  BankStatementCashFlowIntelligence as CashFlowIntelligence,
  BankStatementExplainableRisk as ExplainableRisk,
  BankStatementIncomeEngine as IncomeEngine,
  BankStatementSpendingIntelligence as SpendingIntelligence,
} from "@/lib/api";

type StatusTone = "good" | "warning" | "danger" | "neutral";

export function RiskGauge({ score, label }: { score: number; label?: string }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;
  const color = score < 30 ? "#10b981" : score < 55 ? "#f59e0b" : score < 70 ? "#f97316" : "#ef4444";

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="140" height="140" viewBox="0 0 140 140" className="-rotate-90">
        <circle cx="70" cy="70" r={radius} fill="none" stroke="var(--border-card)" strokeWidth="8" opacity="0.3" />
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          strokeLinecap="round"
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-[28px] font-bold text-[var(--text-primary)] tabular-nums">{score}</span>
        <span className="text-[10px] text-[var(--text-muted)] font-medium uppercase tracking-wider">{label || "risk"}</span>
      </div>
    </div>
  );
}

export function StatusPill({ label, status }: { label: string; status: StatusTone }) {
  const colors = {
    good: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
    warning: "bg-amber-500/10 text-amber-500 border-amber-500/20",
    danger: "bg-red-500/10 text-red-500 border-red-500/20",
    neutral: "bg-blue-500/10 text-blue-500 border-blue-500/20",
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${colors[status]} uppercase tracking-wider`}>
      {label}
    </span>
  );
}

export const CATEGORY_COLORS: Record<string, string> = {
  p2p_transfers: "#8b5cf6",
  utilities: "#3b82f6",
  groceries: "#10b981",
  food_dining: "#f59e0b",
  transport: "#f97316",
  shopping: "#ec4899",
  rent: "#ef4444",
  insurance: "#06b6d4",
  medical: "#14b8a6",
  education: "#6366f1",
  entertainment: "#a855f7",
  cash_withdrawal: "#64748b",
  emi_loan: "#dc2626",
  other: "#94a3b8",
};

export const CATEGORY_LABELS: Record<string, string> = {
  p2p_transfers: "P2P Transfers",
  utilities: "Utilities",
  groceries: "Groceries",
  food_dining: "Food & Dining",
  transport: "Transport",
  shopping: "Shopping",
  rent: "Rent",
  insurance: "Insurance",
  medical: "Medical",
  education: "Education",
  entertainment: "Entertainment",
  cash_withdrawal: "Cash Withdrawal",
  emi_loan: "EMI / Loan",
  other: "Other",
};

export function HorizontalBar({ value, max, color, height = 6 }: { value: number; max: number; color: string; height?: number }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="w-full rounded-full overflow-hidden" style={{ height, background: "var(--border-card)" }}>
      <div className="h-full rounded-full transition-all duration-700 ease-out" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

export function formatINR(val: number | null | undefined): string {
  if (val === null || val === undefined) return "-";
  return `Rs.${val.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}
