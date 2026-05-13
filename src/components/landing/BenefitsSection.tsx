"use client";

import { motion } from "framer-motion";
import { Zap, Users, Target, TrendingDown } from "lucide-react";

const benefits = [
    {
        icon: Zap,
        metric: "Triage",
        title: "Faster Document Review",
        description:
            "Extracts key fields and summarizes documents so analysts start with a prepared case, not a blank file.",
        color: "text-amber-400",
        bg: "bg-amber-500/10",
    },
    {
        icon: TrendingDown,
        metric: "Focus",
        title: "Less Manual Workload",
        description:
            "Reduces repetitive document scanning so your team can spend more time on judgment and exceptions.",
        color: "text-emerald-400",
        bg: "bg-emerald-500/10",
    },
    {
        icon: Users,
        metric: "Compare",
        title: "Cross-Document Checks",
        description:
            "Surfaces conflicts between bank statements, identity details, applicant intake, and income evidence.",
        color: "text-blue-400",
        bg: "bg-blue-500/10",
    },
    {
        icon: Target,
        metric: "Review",
        title: "Human-Owned Decisions",
        description:
            "Keeps final lending decisions with analysts while making the supporting evidence easier to inspect.",
        color: "text-purple-400",
        bg: "bg-purple-500/10",
    },
];

const containerVariants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.1 } },
};

const itemVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

export default function BenefitsSection() {
    return (
        <section id="benefits" className="relative py-24 sm:py-32 overflow-hidden">
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
                        Operational Impact
                    </span>
                    <h2 className="mt-4 text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight">
                        Built to reduce{" "}
                        <span className="text-gradient">review friction</span>
                    </h2>
                    <p className="mt-4 text-lg text-muted-foreground leading-relaxed">
                        ArgentNorth AI helps prepare the evidence analysts need, while
                        leaving credit policy, exceptions, and final approval in your
                        team&apos;s hands.
                    </p>
                </motion.div>

                {/* Benefits Grid */}
                <motion.div
                    variants={containerVariants}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: "-60px" }}
                    className="grid grid-cols-1 sm:grid-cols-2 gap-5"
                >
                    {benefits.map((benefit) => (
                        <motion.div
                            key={benefit.title}
                            variants={itemVariants}
                            className="glass-card rounded-2xl p-7 group"
                        >
                            <div className="flex items-start gap-5">
                                <div
                                    className={`w-12 h-12 rounded-xl ${benefit.bg} flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform`}
                                >
                                    <benefit.icon className={`w-6 h-6 ${benefit.color}`} />
                                </div>
                                <div>
                                    <div className={`text-3xl font-bold ${benefit.color} mb-1`}>
                                        {benefit.metric}
                                    </div>
                                    <h3 className="text-base font-semibold mb-1.5">
                                        {benefit.title}
                                    </h3>
                                    <p className="text-sm text-muted-foreground leading-relaxed">
                                        {benefit.description}
                                    </p>
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </motion.div>
            </div>
        </section>
    );
}
