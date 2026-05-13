"use client";

import { motion } from "framer-motion";
import {
    FileSearch,
    BarChart3,
    BadgeCheck,
    ShieldAlert,
    LayoutDashboard,
    Blocks,
} from "lucide-react";

const features = [
    {
        icon: FileSearch,
        title: "Intelligent Document Parsing",
        description:
            "OCR and document parsing pipelines extract useful fields from supported PDFs, digital files, and photographed documents.",
        color: "text-blue-400",
        bg: "bg-blue-500/10",
    },
    {
        icon: BarChart3,
        title: "Bank Statement Analysis",
        description:
            "Deep analysis of transaction histories, cash flow patterns, average monthly balances, and recurring obligations over 3–12 months.",
        color: "text-indigo-400",
        bg: "bg-indigo-500/10",
    },
    {
        icon: BadgeCheck,
        title: "Income Verification",
        description:
            "Cross-references salary slips, tax returns, and bank credits to highlight income evidence and confidence gaps.",
        color: "text-emerald-400",
        bg: "bg-emerald-500/10",
    },
    {
        icon: ShieldAlert,
        title: "Fraud Detection Signals",
        description:
            "Surfaces possible document tampering, income inflation, circular transactions, and suspicious patterns for analyst review.",
        color: "text-rose-400",
        bg: "bg-rose-500/10",
    },
    {
        icon: LayoutDashboard,
        title: "Credit Risk Dashboard",
        description:
            "Centralized dashboard showing case status, risk signals, document evidence, and review progress for your team.",
        color: "text-amber-400",
        bg: "bg-amber-500/10",
    },
    {
        icon: Blocks,
        title: "Secure API Integration",
        description:
            "API-first architecture can connect with LOS, LMS, or custom lending platforms during a planned integration.",
        color: "text-purple-400",
        bg: "bg-purple-500/10",
    },
];

const containerVariants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.08 } },
};

const itemVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

export default function FeaturesSection() {
    return (
        <section id="features" className="relative py-24 sm:py-32 overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-indigo-500/[0.015] to-transparent" />
            <div className="absolute top-0 left-0 right-0 h-px glow-line" />

            <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                {/* Section Header */}
                <motion.div
                    initial={{ opacity: 0, y: 30 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.6 }}
                    className="text-center max-w-3xl mx-auto mb-16"
                >
                    <span className="text-sm font-medium text-indigo-400 tracking-wider uppercase">
                        Key Features
                    </span>
                    <h2 className="mt-4 text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight">
                        Everything you need to{" "}
                        <span className="text-gradient">underwrite smarter</span>
                    </h2>
                    <p className="mt-4 text-lg text-muted-foreground leading-relaxed">
                        Purpose-built tools for modern lending teams. Each feature is
                        designed to reduce friction and improve review quality.
                    </p>
                </motion.div>

                {/* Feature Cards */}
                <motion.div
                    variants={containerVariants}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: "-60px" }}
                    className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"
                >
                    {features.map((feature) => (
                        <motion.div
                            key={feature.title}
                            variants={itemVariants}
                            className="glass-card rounded-2xl p-6 group"
                        >
                            <div
                                className={`w-11 h-11 rounded-xl ${feature.bg} flex items-center justify-center mb-5 group-hover:scale-110 transition-transform`}
                            >
                                <feature.icon className={`w-5 h-5 ${feature.color}`} />
                            </div>
                            <h3 className="text-base font-semibold mb-2">{feature.title}</h3>
                            <p className="text-sm text-muted-foreground leading-relaxed">
                                {feature.description}
                            </p>
                        </motion.div>
                    ))}
                </motion.div>
            </div>
        </section>
    );
}
