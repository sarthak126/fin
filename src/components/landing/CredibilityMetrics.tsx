"use client";

import { motion } from "framer-motion";

const metrics = [
    {
        value: "88%",
        label: "Faster Underwriting",
        description: "Reduction in processing time vs. manual review",
    },
    {
        value: "3.2s",
        label: "Decision Latency",
        description: "Average end-to-end credit decision time",
    },
    {
        value: "50%",
        label: "Risk Reduction",
        description: "Decrease in default rates during pilot deployments",
    },
    {
        value: "70+",
        label: "Fairness Metrics",
        description: "Bias indicators tracked per model in production",
    },
];

const containerVariants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.08 } },
};

const itemVariants = {
    hidden: { opacity: 0, y: 16 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function CredibilityMetrics() {
    return (
        <section className="relative py-16 sm:py-20 overflow-hidden">
            <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
                <motion.div
                    variants={containerVariants}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: "-80px" }}
                    className="grid grid-cols-2 lg:grid-cols-4 border border-border rounded-lg overflow-hidden"
                >
                    {metrics.map((metric, idx) => (
                        <motion.div
                            key={metric.label}
                            variants={itemVariants}
                            className={`relative p-8 sm:p-10 text-center bg-background ${
                                idx < metrics.length - 1
                                    ? "border-r border-border"
                                    : ""
                            } ${idx < 2 ? "border-b lg:border-b-0 border-border" : ""}`}
                        >
                            <div className="text-3xl sm:text-4xl font-extrabold text-foreground tracking-tight font-mono">
                                {metric.value}
                            </div>
                            <div className="text-sm font-semibold text-foreground mt-2">
                                {metric.label}
                            </div>
                            <div className="text-xs text-muted-foreground mt-1 leading-relaxed">
                                {metric.description}
                            </div>
                        </motion.div>
                    ))}
                </motion.div>
            </div>
        </section>
    );
}
