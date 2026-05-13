"use client";

import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

export default function CTASection() {
    return (
        <section className="relative py-24 sm:py-32 overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-px bg-border" />

            <div className="relative max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.5 }}
                >
                    <h2 className="text-3xl sm:text-4xl lg:text-[44px] font-extrabold tracking-tight leading-tight text-foreground">
                        Ready to modernize your{" "}
                        <span className="text-gradient">credit decisioning?</span>
                    </h2>

                    <p className="mt-5 text-lg text-muted-foreground leading-relaxed max-w-2xl mx-auto">
                        Start with a structured 90-day pilot. Test ArgentNorth against
                        your historical data, validate the Gini lift, and measure
                        operational velocity — before committing to production rollout.
                    </p>

                    <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
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
                            Talk to Sales
                        </Button>
                    </div>

                    <div className="mt-8 flex flex-wrap items-center justify-center gap-x-2 text-xs text-muted-foreground">
                        <span>Structured pilot programs</span>
                        <span className="text-border">·</span>
                        <span>90-day POC</span>
                        <span className="text-border">·</span>
                        <span>White-glove onboarding</span>
                        <span className="text-border">·</span>
                        <span>Regulatory sandbox support</span>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}
