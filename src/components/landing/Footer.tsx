"use client";

const footerLinks = {
    Platform: [
        { label: "Data Unification", href: "#platform" },
        { label: "Credit Intelligence", href: "#platform" },
        { label: "AI Decisioning", href: "#platform" },
        { label: "Decision Dashboard", href: "#solutions" },
        { label: "API Documentation", href: "#" },
    ],
    Solutions: [
        { label: "Commercial Banks", href: "#company" },
        { label: "NBFCs", href: "#company" },
        { label: "Alternative Lenders", href: "#company" },
        { label: "Credit Unions", href: "#company" },
    ],
    Resources: [
        { label: "Architecture Guide", href: "#" },
        { label: "Security Whitepaper", href: "#" },
        { label: "Blog", href: "#" },
        { label: "Changelog", href: "#" },
    ],
    Company: [
        { label: "About", href: "#" },
        { label: "Careers", href: "#" },
        { label: "Contact Sales", href: "#" },
        { label: "Privacy Policy", href: "#" },
        { label: "Terms of Service", href: "#" },
    ],
};

export default function Footer() {
    return (
        <footer className="relative border-t border-border">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-8">
                    {/* Brand */}
                    <div className="col-span-2 md:col-span-1">
                        <a href="#" className="flex items-center gap-2 mb-4">
                            <span className="text-[15px] font-bold tracking-tight text-foreground">
                                Argent<span className="text-primary">North</span>
                            </span>
                        </a>
                        <p className="text-sm text-muted-foreground leading-relaxed max-w-xs">
                            AI-powered credit intelligence for banks, NBFCs,
                            and lending institutions. Faster decisions, full explainability.
                        </p>
                    </div>

                    {/* Link Columns */}
                    {Object.entries(footerLinks).map(([title, links]) => (
                        <div key={title}>
                            <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider mb-4">{title}</h4>
                            <ul className="space-y-2.5">
                                {links.map((link) => (
                                    <li key={link.label}>
                                        <a
                                            href={link.href}
                                            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                                        >
                                            {link.label}
                                        </a>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>

                {/* Bottom bar */}
                <div className="mt-12 pt-8 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-4">
                    <p className="text-xs text-muted-foreground">
                        © {new Date().getFullYear()} ArgentNorth Technologies. All rights reserved.
                    </p>
                    <div className="flex items-center gap-6">
                        {["LinkedIn", "Twitter", "GitHub"].map((social) => (
                            <a
                                key={social}
                                href="#"
                                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                            >
                                {social}
                            </a>
                        ))}
                    </div>
                </div>
            </div>
        </footer>
    );
}
