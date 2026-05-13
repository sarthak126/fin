"use client";

import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import {
    FileText,
    BarChart3,
    BanknoteIcon,
    ShieldCheck,
    ArrowRight,
} from "lucide-react";

const capabilities = [
    {
        icon: FileText,
        title: "Reads Loan Documents",
        description:
            "Parses supported PDFs, bank statements, tax returns, salary slips, and income proofs with OCR and structured extraction.",
    },
    {
        icon: BanknoteIcon,
        title: "Extracts Financial Data",
        description:
            "Pulls income figures, recurring expenses, liabilities, and transaction patterns from unstructured documents at scale.",
    },
    {
        icon: BarChart3,
        title: "Analyzes Bank Statements",
        description:
            "Deep-dives into months of transaction data to identify cash flow trends, average balances, and spending behaviors.",
    },
    {
        icon: ShieldCheck,
        title: "Generates Risk Summary",
        description:
            "Delivers a structured review report highlighting red flags, confidence scores, and follow-up questions.",
    },
];

export default function SolutionSection() {
    return (
        <section className="relative py-24 sm:py-32 overflow-hidden">
            {/* Background */}
            <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/[0.02] to-transparent" />

            <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="grid lg:grid-cols-2 gap-16 items-center">
                    {/* Left - Content */}
                    <motion.div
                        initial={{ opacity: 0, x: -40 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.6 }}
                    >
                        <span className="text-sm font-medium text-indigo-400 tracking-wider uppercase">
                            The Solution
                        </span>
                        <h2 className="mt-4 text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight leading-tight">
                            From scattered files to{" "}
                            <span className="text-gradient">structured review</span>
                        </h2>
                        <p className="mt-5 text-lg text-muted-foreground leading-relaxed">
                            LoanLens AI assists manual document review with structured
                            extraction, bank-statement analysis, and case summaries your
                            analysts can verify.
                        </p>

                        <div className="mt-8 space-y-5">
                            {capabilities.map((cap, i) => (
                                <motion.div
                                    key={cap.title}
                                    initial={{ opacity: 0, x: -20 }}
                                    whileInView={{ opacity: 1, x: 0 }}
                                    viewport={{ once: true }}
                                    transition={{ duration: 0.4, delay: i * 0.1 }}
                                    className="flex items-start gap-4 group"
                                >
                                    <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center shrink-0 group-hover:bg-indigo-500/20 transition-colors">
                                        <cap.icon className="w-5 h-5 text-indigo-400" />
                                    </div>
                                    <div>
                                        <h3 className="text-sm font-semibold mb-0.5">
                                            {cap.title}
                                        </h3>
                                        <p className="text-sm text-muted-foreground leading-relaxed">
                                            {cap.description}
                                        </p>
                                    </div>
                                </motion.div>
                            ))}
                        </div>

                        <div className="mt-10">
                            <Button
                                size="lg"
                                className="h-12 px-8 bg-indigo-500 hover:bg-indigo-600 text-white shadow-lg shadow-indigo-500/20 group"
                            >
                                See It in Action
                                <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                            </Button>
                        </div>
                    </motion.div>

                    {/* Right - Visual */}
                    <motion.div
                        initial={{ opacity: 0, x: 40 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.6, delay: 0.2 }}
                        className="relative"
                    >
                        <div className="relative rounded-2xl glass-card p-6 sm:p-8">
                            {/* Process visualization */}
                            <div className="space-y-4">
                                {/* Input */}
                                <div className="rounded-xl bg-white/[0.02] border border-white/5 p-4">
                                    <div className="text-xs text-muted-foreground mb-3 flex items-center gap-2">
                                        <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                                        Document Analysis in Progress
                                    </div>
                                    <div className="space-y-2">
                                        {[
                                            { name: "bank_statement_apr.pdf", progress: 100 },
                                            { name: "tax_return_2025.pdf", progress: 100 },
                                            { name: "salary_slip_mar.pdf", progress: 72 },
                                        ].map((file) => (
                                            <div key={file.name} className="flex items-center gap-3">
                                                <FileText className="w-4 h-4 text-indigo-400 shrink-0" />
                                                <span className="text-sm text-muted-foreground flex-1 truncate">
                                                    {file.name}
                                                </span>
                                                <div className="w-20 h-1.5 rounded-full bg-white/5 overflow-hidden">
                                                    <div
                                                        className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-1000"
                                                        style={{ width: `${file.progress}%` }}
                                                    />
                                                </div>
                                                <span
                                                    className={`text-xs ${file.progress === 100 ? "text-emerald-400" : "text-muted-foreground"}`}
                                                >
                                                    {file.progress}%
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Output */}
                                <div className="rounded-xl bg-white/[0.02] border border-white/5 p-4">
                                    <div className="text-xs text-muted-foreground mb-3">
                                        Credit Risk Summary
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="rounded-lg bg-white/[0.02] p-3">
                                            <div className="text-xs text-muted-foreground">
                                                Monthly Income
                                            </div>
                                            <div className="text-lg font-semibold text-emerald-400">
                                                ₹1,24,500
                                            </div>
                                        </div>
                                        <div className="rounded-lg bg-white/[0.02] p-3">
                                            <div className="text-xs text-muted-foreground">
                                                Debt-to-Income
                                            </div>
                                            <div className="text-lg font-semibold text-yellow-400">
                                                38.2%
                                            </div>
                                        </div>
                                        <div className="rounded-lg bg-white/[0.02] p-3">
                                            <div className="text-xs text-muted-foreground">
                                                Risk Score
                                            </div>
                                            <div className="text-lg font-semibold text-indigo-400">
                                                72/100
                                            </div>
                                        </div>
                                        <div className="rounded-lg bg-white/[0.02] p-3">
                                            <div className="text-xs text-muted-foreground">
                                                Review State
                                            </div>
                                            <div className="text-lg font-semibold text-emerald-400">
                                                Manual Review
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Decorative orb */}
                        <div className="absolute -top-10 -right-10 w-40 h-40 bg-indigo-500/10 rounded-full blur-[60px]" />
                        <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-purple-500/10 rounded-full blur-[60px]" />
                    </motion.div>
                </div>
            </div>
        </section>
    );
}
