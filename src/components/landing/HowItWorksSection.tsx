"use client";

import { motion } from "framer-motion";
import { Database, Brain, Workflow } from "lucide-react";

const pillars = [
    {
        step: "01",
        icon: Database,
        title: "Data Unification",
        description:
            "Connect CRMs, core banking ledgers, Account Aggregator feeds, and payment gateways via event-driven APIs. Real-time sync without replacing legacy systems.",
        details: ["BIAN 14.0 aligned", "ISO 20022 messaging", "Webhook-driven EDA"],
    },
    {
        step: "02",
        icon: Brain,
        title: "Credit & Risk Intelligence",
        description:
            "XGBoost and LightGBM models analyze structured financial data. Detect fraud patterns, predict defaults, and generate synthetic training data for edge cases.",
        details: ["Gradient-boosted ensembles", "SHAP explainability", "Synthetic data augmentation"],
    },
    {
        step: "03",
        icon: Workflow,
        title: "AI Decisioning & Automation",
        description:
            "Agentic workflows auto-approve, reject, or route to manual review. Full audit trail with compliance checks, fairness metrics, and human-in-the-loop controls.",
        details: ["Agentic credit engine", "70+ fairness metrics", "Rule + Model battery"],
    },
];

const containerVariants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.12 } },
};

const itemVariants = {
    hidden: { opacity: 0, y: 24 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function HowItWorksSection() {
    return (
        <section id="platform" className="relative py-24 sm:py-32 overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-px bg-border" />

            <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                {/* Section Header */}
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.5 }}
                    className="text-center max-w-3xl mx-auto mb-16"
                >
                    <span className="text-xs font-semibold text-primary tracking-wider uppercase">
                        The Platform
                    </span>
                    <h2 className="mt-3 text-3xl sm:text-4xl lg:text-[44px] font-extrabold tracking-tight text-foreground">
                        Three layers of{" "}
                        <span className="text-gradient">financial intelligence</span>
                    </h2>
                    <p className="mt-4 text-lg text-muted-foreground leading-relaxed">
                        ArgentNorth sits between raw financial data and institutional
                        decision-making — unifying, analyzing, and acting.
                    </p>
                </motion.div>

                {/* Pillar Cards */}
                <motion.div
                    variants={containerVariants}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: "-80px" }}
                    className="grid grid-cols-1 md:grid-cols-3 gap-6"
                >
                    {pillars.map((pillar, idx) => (
                        <motion.div
                            key={pillar.step}
                            variants={itemVariants}
                            className="relative"
                        >
                            {/* Connector */}
                            {idx < pillars.length - 1 && (
                                <div className="hidden md:block absolute top-10 left-full w-6 h-px bg-border z-10" />
                            )}

                            <div className="glass-card rounded-lg p-6 h-full group">
                                <div className="flex items-center justify-between mb-5">
                                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                                        <pillar.icon className="w-5 h-5 text-primary" />
                                    </div>
                                    <span className="text-xs font-mono text-muted-foreground/40">
                                        {pillar.step}
                                    </span>
                                </div>

                                <h3 className="text-base font-bold text-foreground mb-2">
                                    {pillar.title}
                                </h3>
                                <p className="text-sm text-muted-foreground leading-relaxed mb-5">
                                    {pillar.description}
                                </p>

                                <div className="flex flex-wrap gap-1.5">
                                    {pillar.details.map((d) => (
                                        <span
                                            key={d}
                                            className="text-[10px] font-mono font-medium px-2 py-0.5 rounded bg-secondary text-muted-foreground border border-border"
                                        >
                                            {d}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </motion.div>
            </div>
        </section>
    );
}
