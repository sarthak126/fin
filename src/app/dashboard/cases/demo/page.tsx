"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Download, AlertTriangle, ShieldCheck, FileText, ChevronLeft, Lightbulb, Sparkles } from "lucide-react";
import Link from "next/link";
import { useOnboardingStore } from "@/store/onboarding";


const demoAnalysis = {
  documentName: "Bank_Statement_Jane_Demo.pdf",
  applicant: "Jane Doe (Demo)",
  status: "Analyzed",
  riskScore: 12,
  riskLevel: "Low Risk",
  assessment: "Applicant demonstrates excellent financial health. Consistent monthly deposits of $8,500 average, with clear 6-month reserves. Debt-to-income ratio is well below the 35% threshold at 22%. No recent overdrafts or NSFs detected. Highly likely to meet repayment obligations.",
  detectedRisks: [
    { severity: "low", message: "Minor discrepancy: address on statement varies slightly from application." }
  ],
  extractedData: {
    "Monthly Income": "$8,540.00", "Annual Income": "$102,480.00", "Debt-to-Income": "22.4%",
    "Employment Type": "Salaried", "Tenure": "6 Years", "Employer": "Acme Corp.",
    "Avg Balance": "$42,100.00", "Min Balance (6m)": "$18,500.00", "Existing EMIs": "$1,910.00",
  }
};

function RiskGauge({ score, size = 140 }: { score: number; size?: number }) {
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (Math.min(100, Math.max(0, score)) / 100) * circumference;
  const color = score > 70 ? "#ef4444" : score > 35 ? "#f59e0b" : "#10b981";
  const glowColor = score > 70 ? "rgba(239,68,68,0.3)" : score > 35 ? "rgba(245,158,11,0.3)" : "rgba(16,185,129,0.3)";
  
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" className="transform -rotate-90" style={{ width: size, height: size }}>
        <circle cx="50" cy="50" r={radius} className="risk-gauge-track" />
        <circle cx="50" cy="50" r={radius} stroke={color} strokeWidth="8" strokeLinecap="round" fill="none"
          strokeDasharray={circumference} strokeDashoffset={strokeDashoffset}
          style={{ transition: "stroke-dashoffset 1.5s ease-out", filter: `drop-shadow(0 0 6px ${glowColor})` }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold tracking-tighter" style={{ color }}>{score}</span>
        <span className="text-[10px] font-medium text-[var(--text-muted)] mt-0.5">/ 100</span>
      </div>
    </div>
  );
}

export default function DemoAnalysisPage() {
  const { markDemoViewed } = useOnboardingStore();
  useEffect(() => { markDemoViewed(); }, [markDemoViewed]);

  const isHighRisk = demoAnalysis.riskScore > 70;
  const isMediumRisk = demoAnalysis.riskScore > 35 && demoAnalysis.riskScore <= 70;

  return (
    <div className="flex flex-col gap-6 pb-12">
      <div className="glass-panel flex items-center justify-between px-4 py-2.5 animate-fade-slide bg-primary/[0.06]">
        <div className="flex items-center gap-2 text-[13px] font-medium text-primary">
          <Sparkles className="h-3.5 w-3.5" />Sample analysis — your documents will appear exactly like this.
        </div>
        <Button size="sm" asChild className="h-7 text-[11px] bg-primary hover:bg-primary/90 rounded-md shadow-sm cursor-pointer">
          <Link href="/dashboard/upload">Try with your own PDF</Link>
        </Button>
      </div>

      <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center animate-fade-slide stagger-1">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="icon" className="h-8 w-8 text-[var(--text-muted)] hover:text-[var(--text-secondary)] cursor-pointer">
            <Link href="/dashboard"><ChevronLeft className="h-4 w-4" /></Link>
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-bold tracking-tight text-[var(--text-primary)]">{demoAnalysis.applicant}</h1>
              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 font-medium text-[11px]">{demoAnalysis.status}</Badge>
            </div>
            <p className="text-[12px] text-[var(--text-muted)] flex items-center gap-1.5 mt-0.5"><FileText className="h-3 w-3" />{demoAnalysis.documentName}</p>
          </div>
        </div>
        <Button variant="outline" size="sm" className="border-[var(--border-card)] bg-transparent hover:bg-[var(--surface-secondary)] text-[var(--text-secondary)] text-[12px] rounded-lg cursor-pointer">
          <Download className="mr-2 h-3.5 w-3.5" /> Download Report
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-5 flex flex-col gap-5">
          <div className="glass-panel flex flex-col items-center p-8 text-center animate-fade-slide stagger-2">
            <p className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.15em] mb-4">Risk Score</p>
            <RiskGauge score={demoAnalysis.riskScore} />
            <Badge variant="secondary" className={`mt-4 ${isHighRisk ? 'bg-red-500/10 text-red-500' : isMediumRisk ? 'bg-amber-500/10 text-amber-500' : 'bg-emerald-500/10 text-emerald-500'} border-transparent text-[12px] font-medium px-3 py-1`}>
              {demoAnalysis.riskLevel}
            </Badge>
          </div>

          <div className="glass-panel p-0 overflow-hidden animate-fade-slide stagger-3">
            <div className="px-5 py-3.5 border-b border-[var(--border-card)] flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-primary" />
              <h3 className="text-[13px] font-semibold text-[var(--text-secondary)]">AI Assessment</h3>
            </div>
            <div className="px-5 py-4 text-[13px] text-[var(--text-tertiary)] leading-relaxed">{demoAnalysis.assessment}</div>
          </div>

          {demoAnalysis.detectedRisks.length > 0 && (
            <div className="glass-panel p-0 overflow-hidden animate-fade-slide stagger-4">
              <div className="px-5 py-3.5 border-b border-[var(--border-card)] flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <h3 className="text-[13px] font-semibold text-amber-500">Detected Flags</h3>
              </div>
              <div className="px-5 py-4">
                <ul className="space-y-3">
                  {demoAnalysis.detectedRisks.map((risk, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-[13px]">
                      <div className={`mt-1.5 rounded-full w-2 h-2 shrink-0 ${risk.severity === 'high' ? 'bg-red-500' : 'bg-amber-500'}`} />
                      <span className="text-[var(--text-secondary)]">{risk.message}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>

        <div className="lg:col-span-7 flex flex-col gap-5">
          <div className="glass-panel p-0 overflow-hidden h-full flex flex-col animate-fade-slide stagger-3">
            <div className="px-5 py-3.5 border-b border-[var(--border-card)] flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <h3 className="text-[13px] font-semibold text-[var(--text-secondary)]">Document Insights</h3>
            </div>
            <div className="flex-1">
              <div className="grid grid-cols-1 sm:grid-cols-2">
                {Object.entries(demoAnalysis.extractedData).map(([key, value], i) => (
                  <div key={key} className={`p-4 sm:p-5 flex flex-col gap-1 transition-colors hover:bg-[var(--surface-hover)] ${i % 2 === 0 ? 'sm:border-r border-[var(--border-subtle)]' : ''} border-b border-[var(--border-subtle)]`}>
                    <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.12em]">{key}</span>
                    <span className="text-[14px] font-semibold text-[var(--text-secondary)] tracking-tight">{value}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="px-4 py-3 bg-[var(--surface-secondary)] border-t border-[var(--border-subtle)]">
              <p className="text-[10px] text-[var(--text-muted)] flex items-center gap-1.5 uppercase tracking-wider font-medium">
                <AlertTriangle className="h-3 w-3" />AI-extracted data. Verify against original document before decisions.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
