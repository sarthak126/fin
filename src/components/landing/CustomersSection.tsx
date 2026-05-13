"use client";

import { motion } from "framer-motion";
import {
    Building2,
    Landmark,
    Globe,
    UserCheck,
} from "lucide-react";

const customers = [
    {
        icon: Building2,
        title: "Fintech Lenders",
        description:
            "Digital-first lending companies looking to automate loan origination and scale their operations without adding headcount.",
        color: "text-indigo-400",
        bg: "bg-indigo-500/10",
    },
    {
        icon: Landmark,
        title: "NBFCs",
        description:
            "Non-banking financial companies managing high loan volumes who need faster, more reliable document processing at scale.",
        color: "text-blue-400",
        bg: "bg-blue-500/10",
    },
    {
        icon: Globe,
        title: "Digital Lending Platforms",
        description:
            "Marketplace and embedded lending platforms that need to process applications quickly while maintaining credit quality.",
        color: "text-emerald-400",
        bg: "bg-emerald-500/10",
    },
    {
        icon: UserCheck,
        title: "Underwriting Teams",
        description:
            "Credit analysts and loan officers who want AI-powered insights to augment their expertise and accelerate decision-making.",
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

export default function CustomersSection() {
    return (
        <section className="relative py-24 sm:py-32 overflow-hidden">
            <div className="absolute inset-0 dot-pattern opacity-20" />
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
                        Built For
                    </span>
                    <h2 className="mt-4 text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight">
                        Designed for{" "}
                        <span className="text-gradient">modern lenders</span>
                    </h2>
                    <p className="mt-4 text-lg text-muted-foreground leading-relaxed">
                        Whether you&apos;re a digital-first fintech or an established NBFC,
                        ArgentNorth AI adapts to your workflow and scales with your ambitions.
                    </p>
                </motion.div>

                {/* Customer Cards */}
                <motion.div
                    variants={containerVariants}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: "-60px" }}
                    className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5"
                >
                    {customers.map((customer) => (
                        <motion.div
                            key={customer.title}
                            variants={itemVariants}
                            className="glass-card rounded-2xl p-6 text-center group"
                        >
                            <div
                                className={`w-14 h-14 rounded-2xl ${customer.bg} flex items-center justify-center mx-auto mb-5 group-hover:scale-110 transition-transform`}
                            >
                                <customer.icon className={`w-7 h-7 ${customer.color}`} />
                            </div>
                            <h3 className="text-base font-semibold mb-2">{customer.title}</h3>
                            <p className="text-sm text-muted-foreground leading-relaxed">
                                {customer.description}
                            </p>
                        </motion.div>
                    ))}
                </motion.div>
            </div>
        </section>
    );
}
