"use client";

import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

const trustSignals = [
    "RBI FREE-AI Aligned",
    "ISO 20022 Compatible",
    "BIAN Landscape 14.0",
    "SOC 2 Ready",
    "DPDP Act Compliant",
];

export default function HeroSection() {
    return (
        <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden pt-16">
            {/* Subtle grid background */}
            <div className="absolute inset-0 grid-pattern opacity-30" />
            <div className="absolute inset-0 bg-gradient-to-b from-background via-background/80 to-background" />

            <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
                {/* Badge */}
                <motion.div
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: 0.1 }}
                    className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full border border-border bg-secondary text-muted-foreground text-xs font-medium tracking-wide mb-8"
                >
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                    Enterprise-grade AI for credit decisioning
                </motion.div>

                {/* Headline */}
                <motion.h1
                    initial={{ opacity: 0, y: 24 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="text-4xl sm:text-5xl md:text-6xl lg:text-[64px] font-extrabold tracking-[-0.025em] leading-[1.08] max-w-4xl mx-auto text-foreground"
                >
                    The credit intelligence layer{" "}
                    <span className="text-gradient">for financial institutions</span>
                </motion.h1>

                {/* Subheadline */}
                <motion.p
                    initial={{ opacity: 0, y: 24 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.35 }}
                    className="mt-6 text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed"
                >
                    ArgentNorth helps banks and NBFCs unify fragmented data, assess
                    credit risk with explainable AI, and automate underwriting
                    decisions — without replacing core systems.
                </motion.p>

                {/* CTAs */}
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.5 }}
                    className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3"
                >
                    <Button
                        size="lg"
                        className="h-11 px-8 text-sm font-semibold bg-foreground text-background hover:bg-foreground/90 transition-colors rounded-lg group"
                    >
                        Request a Demo
                        <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />
                    </Button>
                    <Button
                        variant="outline"
                        size="lg"
                        className="h-11 px-8 text-sm font-medium border-border hover:bg-secondary text-foreground rounded-lg"
                    >
                        Read Documentation
                    </Button>
                </motion.div>

                {/* Trust Signals */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.5, delay: 0.7 }}
                    className="mt-16 flex flex-wrap items-center justify-center gap-x-2 gap-y-2"
                >
                    {trustSignals.map((signal, i) => (
                        <span key={signal} className="flex items-center">
                            <span className="text-[11px] font-mono font-medium text-muted-foreground/60 tracking-wide uppercase">
                                {signal}
                            </span>
                            {i < trustSignals.length - 1 && (
                                <span className="mx-2 text-border">·</span>
                            )}
                        </span>
                    ))}
                </motion.div>
            </div>
        </section>
    );
}
