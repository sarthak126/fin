import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import { ThemeProvider } from "@/components/ThemeProvider";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "ArgentNorth — AI-Powered Credit Intelligence for Financial Institutions",
  description:
    "ArgentNorth is an AI-driven financial intelligence platform that helps banks and NBFCs unify data, assess credit risk, automate underwriting, and make faster, explainable lending decisions.",
  keywords: [
    "credit intelligence platform",
    "AI underwriting",
    "credit risk assessment",
    "fintech infrastructure",
    "NBFC lending technology",
    "explainable AI finance",
    "RBI FREE-AI compliance",
    "account aggregator lending",
    "agentic credit decisioning",
  ],
  openGraph: {
    title: "ArgentNorth — AI-Powered Credit Intelligence",
    description:
      "The intelligent decision layer for lending. Unify data, assess risk, and automate credit decisions with full explainability.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${jetbrainsMono.variable} antialiased font-sans flex flex-col min-h-screen`}>
        <ClerkProvider>
          <ThemeProvider>
            {children}
          </ThemeProvider>
        </ClerkProvider>
      </body>
    </html>
  );
}
