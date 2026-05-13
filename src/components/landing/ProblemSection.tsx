"use client";

import { motion } from "framer-motion";
import { Clock, AlertTriangle, TrendingUp, Users } from "lucide-react";

const painPoints = [
    {
        icon: Clock,
        title: "Hours of Manual Review",
        description:
            "Loan officers spend hours manually reviewing each application, scanning bank statements, cross-referencing income proofs, and verifying financial data.",
    },
    {
        icon: AlertTriangle,
        title: "Human Error in Verification",
        description:
            "Manual processes introduce inconsistencies, missed red flags, calculation mistakes, and overlooked discrepancies.",
    },
    {
        icon: TrendingUp,
        title: "Slow Approval Pipelines",
        description:
            "Document-heavy workflows create bottlenecks, delaying approvals and frustrating applicants while competitors move faster.",
    },
    {
        icon: Users,
        title: "Operational Bottlenecks",
        description:
            "Growing loan volumes overwhelm underwriting teams, forcing costly hiring or sacrificing review quality to meet demand.",
    },
];

const containerVariants = {
    hidden: {},
    visible: {
        transition: { staggerChildren: 0.12 },
    },
};

const itemVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

export default function ProblemSection() {
    return (
        <section className="relative py-24 sm:py-32 overflow-hidden">
            {/* Background Effect */}
            <div className="absolute inset-0 dot-pattern opacity-30" />
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
                    <span className="text-sm font-medium text-rose-400/80 tracking-wider uppercase">
                        The Problem
                    </span>
                    <h2 className="mt-4 text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight">
                        Manual loan review is{" "}
                        <span className="text-gradient-warm">broken</span>
                    </h2>
                    <p className="mt-4 text-lg text-muted-foreground leading-relaxed">
                        Traditional document analysis costs your team time and creates
                        avoidable review inconsistency across applications.
                    </p>
                </motion.div>

                {/* Pain Point Cards */}
                <motion.div
                    variants={containerVariants}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: "-80px" }}
                    className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5"
                >
                    {painPoints.map((point) => (
                        <motion.div
                            key={point.title}
                            variants={itemVariants}
                            className="glass-card rounded-2xl p-6 group"
                        >
                            <div className="w-11 h-11 rounded-xl bg-rose-500/10 flex items-center justify-center mb-5 group-hover:bg-rose-500/15 transition-colors">
                                <point.icon className="w-5 h-5 text-rose-400" />
                            </div>
                            <h3 className="text-base font-semibold mb-2">{point.title}</h3>
                            <p className="text-sm text-muted-foreground leading-relaxed">
                                {point.description}
                            </p>
                        </motion.div>
                    ))}
                </motion.div>
            </div>
        </section>
    );
}
