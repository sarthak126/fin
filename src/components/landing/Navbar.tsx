"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Menu, X } from "lucide-react";
import { Show, UserButton, SignInButton } from "@clerk/nextjs";
import Link from "next/link";
import { isAuthEnabled } from "@/lib/auth";

const navLinks = [
    { label: "Platform", href: "#platform" },
    { label: "Solutions", href: "#solutions" },
    { label: "Security & Compliance", href: "#security" },
    { label: "Company", href: "#company" },
];

export default function Navbar() {
    const [scrolled, setScrolled] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);
    const authEnabled = isAuthEnabled();

    useEffect(() => {
        const handleScroll = () => setScrolled(window.scrollY > 20);
        window.addEventListener("scroll", handleScroll);
        return () => window.removeEventListener("scroll", handleScroll);
    }, []);

    return (
        <motion.nav
            initial={{ y: -100 }}
            animate={{ y: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${scrolled
                ? "bg-background/95 backdrop-blur-sm border-b border-border shadow-sm"
                : "bg-transparent"
                }`}
        >
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between h-16">
                    {/* Logo */}
                    <a href="#" className="flex items-center gap-2 group">
                        <span className="text-[17px] font-bold tracking-tight text-foreground">
                            Argent<span className="text-primary">North</span>
                        </span>
                    </a>

                    {/* Desktop Links */}
                    <div className="hidden md:flex items-center gap-1">
                        {navLinks.map((link) => (
                            <a
                                key={link.label}
                                href={link.href}
                                className="px-3 py-2 text-[13px] font-medium text-muted-foreground hover:text-foreground transition-colors rounded-md"
                            >
                                {link.label}
                            </a>
                        ))}
                    </div>

                    {/* Desktop CTA */}
                    <div className="hidden md:flex items-center gap-3">
                        {authEnabled ? (
                            <>
                                <Show when="signed-out">
                                    <SignInButton mode="modal">
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="text-[13px] text-muted-foreground hover:text-foreground cursor-pointer"
                                        >
                                            Sign In
                                        </Button>
                                    </SignInButton>
                                </Show>
                                <Show when="signed-in">
                                    <div className="flex items-center gap-3">
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="text-[13px] text-muted-foreground hover:text-foreground cursor-pointer"
                                            onClick={() => window.location.href = "/dashboard"}
                                        >
                                            Dashboard
                                        </Button>
                                        <UserButton />
                                    </div>
                                </Show>
                            </>
                        ) : (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="text-[13px] text-muted-foreground hover:text-foreground"
                                asChild
                            >
                                <Link href="/dashboard">Dashboard</Link>
                            </Button>
                        )}

                        <Button
                            size="sm"
                            className="h-8 px-4 text-[13px] font-medium bg-foreground text-background hover:bg-foreground/90 transition-colors rounded-md"
                        >
                            Request Demo
                        </Button>
                    </div>

                    {/* Mobile Toggle */}
                    <button
                        className="md:hidden p-2 text-muted-foreground"
                        onClick={() => setMobileOpen(!mobileOpen)}
                    >
                        {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                    </button>
                </div>
            </div>

            {/* Mobile Menu */}
            <AnimatePresence>
                {mobileOpen && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="md:hidden bg-background border-t border-border"
                    >
                        <div className="px-4 py-4 space-y-1">
                            {navLinks.map((link) => (
                                <a
                                    key={link.label}
                                    href={link.href}
                                    onClick={() => setMobileOpen(false)}
                                    className="block px-3 py-2.5 text-sm text-muted-foreground hover:text-foreground rounded-md transition"
                                >
                                    {link.label}
                                </a>
                            ))}
                            <div className="pt-3 flex flex-col gap-2">
                                {authEnabled ? (
                                    <>
                                        <Show when="signed-out">
                                            <SignInButton mode="modal">
                                                <Button variant="ghost" size="sm" className="w-full justify-start cursor-pointer">
                                                    Sign In
                                                </Button>
                                            </SignInButton>
                                        </Show>
                                        <Show when="signed-in">
                                            <div className="flex items-center justify-between px-3 py-2.5">
                                                <span className="text-sm font-medium">Account</span>
                                                <UserButton />
                                            </div>
                                            <Button variant="ghost" size="sm" className="w-full justify-start cursor-pointer" onClick={() => window.location.href = "/dashboard"}>
                                                Dashboard
                                            </Button>
                                        </Show>
                                    </>
                                ) : (
                                    <Button variant="ghost" size="sm" className="w-full justify-start" asChild>
                                        <Link href="/dashboard">Dashboard</Link>
                                    </Button>
                                )}
                                <Button
                                    size="sm"
                                    className="w-full bg-foreground text-background hover:bg-foreground/90 font-medium rounded-md"
                                >
                                    Request Demo
                                </Button>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.nav>
    );
}
