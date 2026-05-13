"use client";

import { motion } from "framer-motion";
import { Shield, Scale, Lock, Eye } from "lucide-react";

const complianceAreas = [
    {
        icon: Shield,
        title: "RBI FREE-AI Framework",
        description:
            "Every credit score ships with a SHAP value array and LIME interpretation. Models are explainable by design — satisfying the RBI's \"Understandable by Design\" mandate across all seven Sutras.",
        badge: "Explainability",
    },
    {
        icon: Scale,
        title: "Fairness Engineering",
        description:
            "70+ fairness metrics tracked per model including statistical parity, equal opportunity, and average odds difference. Integrated with AIF360 and Fairlearn for continuous bias monitoring.",
        badge: "Anti-Bias",
    },
    {
        icon: Lock,
        title: "Cybersecurity & Infrastructure",
        description:
            "Zero Trust architecture, end-to-end encryption, continuous VAPT. Built to ISO 27001 and SOC 2 Type II standards with adversarial attack and model poisoning incident protocols.",
        badge: "ISO 27001",
    },
    {
        icon: Eye,
        title: "Data Privacy & Governance",
        description:
            "DPDP Act 2023 compliant. Consent-based data ingestion via Account Aggregator framework. Board-level governance policies and consumer grievance redressal channels for AI-driven decisions.",
        badge: "DPDP Act",
    },
];

const certBadges = [
    "RBI FREE-AI",
    "ISO 27001",
    "SOC 2 Type II",
    "DPDP Act 2023",
    "BIAN 14.0",
    "ISO 20022",
];

const containerVariants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.08 } },
};

const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function SecuritySection() {
    return (
        <section id="security" className="relative py-24 sm:py-32 overflow-hidden">
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
                        Security & Compliance
                    </span>
                    <h2 className="mt-3 text-3xl sm:text-4xl lg:text-[44px] font-extrabold tracking-tight text-foreground">
                        Compliance is not a feature.{" "}
                        <span className="text-gradient">It&apos;s the architecture.</span>
                    </h2>
                    <p className="mt-4 text-lg text-muted-foreground leading-relaxed">
                        Selling to regulated financial institutions requires absolute transparency.
                        ArgentNorth embeds explainability, fairness, and audit controls at every layer.
                    </p>
                </motion.div>

                {/* Compliance Grid */}
                <motion.div
                    variants={containerVariants}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: "-60px" }}
                    className="grid grid-cols-1 sm:grid-cols-2 gap-5"
                >
                    {complianceAreas.map((area) => (
                        <motion.div
                            key={area.title}
                            variants={itemVariants}
                            className="glass-card rounded-lg p-6 group"
                        >
                            <div className="flex items-start gap-4">
                                <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center shrink-0">
                                    <area.icon className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                                </div>
                                <div className="flex-1">
                                    <div className="flex items-center gap-2.5 mb-2">
                                        <h3 className="text-sm font-bold text-foreground">{area.title}</h3>
                                        <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                                            {area.badge}
                                        </span>
                                    </div>
                                    <p className="text-sm text-muted-foreground leading-relaxed">
                                        {area.description}
                                    </p>
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </motion.div>

                {/* Certification Badges */}
                <motion.div
                    initial={{ opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="mt-12 flex flex-wrap justify-center gap-3"
                >
                    {certBadges.map((badge) => (
                        <div
                            key={badge}
                            className="px-3.5 py-1.5 rounded-md border border-border bg-secondary text-[11px] font-mono font-medium text-muted-foreground"
                        >
                            {badge}
                        </div>
                    ))}
                </motion.div>
            </div>
        </section>
    );
}
