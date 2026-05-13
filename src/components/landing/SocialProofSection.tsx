"use client";

import { motion } from "framer-motion";
import { Building2, Landmark, TrendingUp, Users } from "lucide-react";

const useCases = [
    {
        icon: Landmark,
        title: "Commercial Banks",
        problem: "Batch-processed credit decisions with 48-hour turnaround",
        solution: "Real-time, event-driven underwriting with full SHAP explainability for regulators",
    },
    {
        icon: Building2,
        title: "NBFCs",
        problem: "Fragmented data across Account Aggregators, bureaus, and internal systems",
        solution: "Unified data layer with AA integration and cash-flow-based underwriting models",
    },
    {
        icon: TrendingUp,
        title: "Alternative Lenders",
        problem: "Over-reliance on static bureau scores missing credit-invisible populations",
        solution: "Alternative data signals with bias-audited ML models and synthetic data augmentation",
    },
    {
        icon: Users,
        title: "Credit Unions & Co-ops",
        problem: "Limited IT resources to build modern credit decisioning infrastructure",
        solution: "Plug-and-play API integration over existing core banking — no rip-and-replace",
    },
];

const containerVariants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.1 } },
};

const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function SocialProofSection() {
    return (
        <section id="company" className="relative py-24 sm:py-32 overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-px bg-border" />

            <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.5 }}
                    className="text-center max-w-3xl mx-auto mb-16"
                >
                    <span className="text-xs font-semibold text-primary tracking-wider uppercase">
                        Built For
                    </span>
                    <h2 className="mt-3 text-3xl sm:text-4xl lg:text-[44px] font-extrabold tracking-tight text-foreground">
                        Designed for{" "}
                        <span className="text-gradient">regulated institutions</span>
                    </h2>
                    <p className="mt-4 text-lg text-muted-foreground leading-relaxed">
                        ArgentNorth serves every institution that makes lending decisions — 
                        from tier-1 commercial banks to community credit unions.
                    </p>
                </motion.div>

                <motion.div
                    variants={containerVariants}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: "-60px" }}
                    className="grid grid-cols-1 sm:grid-cols-2 gap-5"
                >
                    {useCases.map((uc) => (
                        <motion.div
                            key={uc.title}
                            variants={itemVariants}
                            className="glass-card rounded-lg p-6"
                        >
                            <div className="flex items-center gap-3 mb-4">
                                <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                                    <uc.icon className="w-4.5 h-4.5 text-primary" />
                                </div>
                                <h3 className="text-sm font-bold text-foreground">{uc.title}</h3>
                            </div>
                            <div className="space-y-2.5">
                                <div>
                                    <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Challenge</span>
                                    <p className="text-sm text-muted-foreground leading-relaxed mt-0.5">{uc.problem}</p>
                                </div>
                                <div>
                                    <span className="text-[10px] font-semibold text-primary uppercase tracking-wider">ArgentNorth Solution</span>
                                    <p className="text-sm text-foreground/80 leading-relaxed mt-0.5">{uc.solution}</p>
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </motion.div>
            </div>
        </section>
    );
}
