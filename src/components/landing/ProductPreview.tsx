"use client";

import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";

const applicants = [
    { name: "Rajesh Kapoor", entity: "Kapoor Textiles Pvt Ltd", risk: "Low", score: 82, status: "Approved" },
    { name: "Priya Sharma", entity: "Sharma AgriTech", risk: "Medium", score: 64, status: "In Review" },
    { name: "Vikram Malhotra", entity: "VM Steel Exports", risk: "High", score: 38, status: "Flagged" },
    { name: "Anita Desai", entity: "Desai Pharma Corp", risk: "Low", score: 91, status: "Approved" },
];

const shapFeatures = [
    { feature: "Credit Utilization Ratio", value: +0.18, color: "bg-blue-500" },
    { feature: "Cash-Flow Volatility", value: -0.12, color: "bg-red-400" },
    { feature: "Account Age (months)", value: +0.09, color: "bg-blue-500" },
    { feature: "Recent Inquiry Count", value: -0.07, color: "bg-red-400" },
    { feature: "Avg Monthly Balance", value: +0.06, color: "bg-blue-500" },
];

const riskColor = (risk: string) => {
    if (risk === "Low") return "text-emerald-400 bg-emerald-400/10";
    if (risk === "Medium") return "text-amber-400 bg-amber-400/10";
    return "text-red-400 bg-red-400/10";
};

export default function ProductPreview() {
    return (
        <section id="solutions" className="relative py-20 sm:py-28 overflow-hidden">
            <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                {/* Section Header */}
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.5 }}
                    className="text-center max-w-3xl mx-auto mb-14"
                >
                    <span className="text-xs font-semibold text-primary tracking-wider uppercase">
                        Decision Dashboard
                    </span>
                    <h2 className="mt-3 text-3xl sm:text-4xl lg:text-[44px] font-extrabold tracking-tight text-foreground">
                        Institutional-grade{" "}
                        <span className="text-gradient">credit decisioning</span>
                    </h2>
                    <p className="mt-4 text-lg text-muted-foreground leading-relaxed">
                        From application intake to AI recommendation with full SHAP
                        explainability — a single pane of glass for your credit operations.
                    </p>
                </motion.div>

                {/* Dashboard Mock — always dark shell for contrast */}
                <motion.div
                    initial={{ opacity: 0, y: 40 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-80px" }}
                    transition={{ duration: 0.6 }}
                    className="relative mx-auto max-w-6xl product-shell overflow-hidden"
                >
                    {/* Title bar */}
                    <div className="flex items-center gap-2 px-5 py-3 border-b border-white/[0.06]">
                        <div className="flex gap-1.5">
                            <div className="w-2.5 h-2.5 rounded-full bg-white/10" />
                            <div className="w-2.5 h-2.5 rounded-full bg-white/10" />
                            <div className="w-2.5 h-2.5 rounded-full bg-white/10" />
                        </div>
                        <div className="flex-1 text-center text-[11px] text-slate-500 font-mono">
                            argentnorth.io/decisions — Credit Decision Engine
                        </div>
                    </div>

                    {/* Dashboard Content */}
                    <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[460px]">
                        {/* Left Panel — Application Queue */}
                        <div className="lg:col-span-4 border-r border-white/[0.06] p-4">
                            <div className="text-[10px] font-semibold text-slate-500 mb-3 uppercase tracking-[0.1em]">
                                Application Queue
                            </div>
                            <div className="space-y-1.5">
                                {applicants.map((app, idx) => (
                                    <div
                                        key={app.name}
                                        className={`flex items-center gap-3 px-3 py-2.5 rounded-md cursor-pointer transition-colors group ${idx === 1 ? "bg-white/[0.06] border border-blue-500/20" : "hover:bg-white/[0.03]"}`}
                                    >
                                        <div className="w-7 h-7 rounded-md bg-slate-700/50 flex items-center justify-center text-[10px] font-bold text-slate-400 shrink-0">
                                            {app.name.split(" ").map(n => n[0]).join("")}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="text-[13px] text-slate-200 font-medium truncate">
                                                {app.name}
                                            </div>
                                            <div className="text-[10px] text-slate-500 truncate">
                                                {app.entity}
                                            </div>
                                        </div>
                                        <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${riskColor(app.risk)}`}>
                                            {app.risk}
                                        </span>
                                        <ChevronRight className="w-3 h-3 text-slate-600 group-hover:text-slate-400 transition-colors" />
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Right Panel — Decision Detail */}
                        <div className="lg:col-span-8 p-5">
                            {/* Top: Score + Recommendation */}
                            <div className="flex flex-col sm:flex-row gap-4 mb-5">
                                {/* Risk Score */}
                                <div className="flex-1 rounded-md bg-white/[0.03] border border-white/[0.06] p-4">
                                    <div className="text-[10px] text-slate-500 uppercase tracking-[0.1em] mb-2">Risk Score</div>
                                    <div className="flex items-end gap-2">
                                        <span className="text-3xl font-extrabold font-mono text-amber-400">64</span>
                                        <span className="text-sm text-slate-500 mb-1">/100</span>
                                    </div>
                                    <div className="mt-2 w-full h-1.5 rounded-full bg-slate-700/50 overflow-hidden">
                                        <div className="h-full rounded-full bg-gradient-to-r from-emerald-500 via-amber-400 to-red-500" style={{ width: "64%" }} />
                                    </div>
                                    <div className="text-[10px] text-slate-500 mt-1.5">Medium Risk · Confidence 94.2%</div>
                                </div>

                                {/* AI Recommendation */}
                                <div className="flex-1 rounded-md bg-white/[0.03] border border-white/[0.06] p-4">
                                    <div className="text-[10px] text-slate-500 uppercase tracking-[0.1em] mb-2">AI Recommendation</div>
                                    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded bg-amber-400/10 border border-amber-400/20">
                                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                                        <span className="text-sm font-bold text-amber-400 uppercase tracking-wide">Manual Review</span>
                                    </div>
                                    <div className="text-[10px] text-slate-500 mt-2.5">
                                        Agentic workflow flagged 2 risk indicators requiring human oversight
                                    </div>
                                </div>
                            </div>

                            {/* SHAP Explainability */}
                            <div className="rounded-md bg-white/[0.03] border border-white/[0.06] p-4 mb-4">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="text-[10px] text-slate-500 uppercase tracking-[0.1em] font-semibold">
                                        SHAP Feature Attribution
                                    </div>
                                    <span className="text-[9px] font-mono text-slate-600">
                                        Model v3.2 · XGBoost
                                    </span>
                                </div>
                                <div className="space-y-2">
                                    {shapFeatures.map((f) => (
                                        <div key={f.feature} className="flex items-center gap-3">
                                            <span className="text-[11px] text-slate-400 w-40 shrink-0 truncate">{f.feature}</span>
                                            <div className="flex-1 flex items-center gap-2">
                                                <div className="flex-1 h-4 relative flex items-center">
                                                    <div className="absolute left-1/2 h-full w-px bg-slate-700/50" />
                                                    {f.value > 0 ? (
                                                        <div
                                                            className={`absolute left-1/2 h-3 rounded-r ${f.color}`}
                                                            style={{ width: `${Math.abs(f.value) * 250}%` }}
                                                        />
                                                    ) : (
                                                        <div
                                                            className={`absolute h-3 rounded-l ${f.color}`}
                                                            style={{
                                                                width: `${Math.abs(f.value) * 250}%`,
                                                                right: "50%",
                                                            }}
                                                        />
                                                    )}
                                                </div>
                                                <span className={`text-[11px] font-mono w-10 text-right ${f.value > 0 ? "text-blue-400" : "text-red-400"}`}>
                                                    {f.value > 0 ? "+" : ""}{f.value.toFixed(2)}
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Key Metrics */}
                            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
                                {[
                                    { label: "Monthly Income", value: "₹1,24,500" },
                                    { label: "Debt-to-Income", value: "38.2%" },
                                    { label: "Employment", value: "Salaried · 4yr" },
                                    { label: "Avg Balance", value: "₹3,42,000" },
                                    { label: "Loan Amount", value: "₹15,00,000" },
                                    { label: "EMI Capacity", value: "₹28,400" },
                                ].map((item) => (
                                    <div key={item.label} className="rounded-md bg-white/[0.02] border border-white/[0.05] px-3 py-2.5">
                                        <div className="text-[10px] text-slate-500">{item.label}</div>
                                        <div className="text-[13px] font-semibold text-slate-200 mt-0.5 font-mono">{item.value}</div>
                                    </div>
                                ))}
                            </div>

                            {/* Compliance Footer */}
                            <div className="flex items-center justify-between pt-3 border-t border-white/[0.05]">
                                <div className="flex items-center gap-3">
                                    <span className="text-[9px] font-mono text-slate-600 px-2 py-0.5 rounded bg-white/[0.03] border border-white/[0.06]">
                                        FREE-AI Compliant
                                    </span>
                                    <span className="text-[9px] font-mono text-slate-600 px-2 py-0.5 rounded bg-white/[0.03] border border-white/[0.06]">
                                        Bias Audit: Pass
                                    </span>
                                </div>
                                <span className="text-[9px] font-mono text-slate-600">
                                    Audit ID: AN-2026-04892
                                </span>
                            </div>
                        </div>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}
