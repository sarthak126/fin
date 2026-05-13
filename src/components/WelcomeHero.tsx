"use client";

import { useUser } from "@clerk/nextjs";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useOnboardingStore } from "@/store/onboarding";
import { isAuthEnabled } from "@/lib/auth";

export function WelcomeHero() {
  const { user } = useUser();
  const { hasViewedDemo, hasUploadedDocument, hasVerifiedSettings, startTour } = useOnboardingStore();
  const firstName = isAuthEnabled() ? user?.firstName : undefined;

  const allDone = hasViewedDemo && hasUploadedDocument && hasVerifiedSettings;
  if (allDone) return null;
  const steps = [
    { label: "Review a demo case", done: hasViewedDemo, href: "/dashboard/cases/demo" },
    { label: "Start your first case", done: hasUploadedDocument, href: "/dashboard/upload" },
    { label: "Configure settings", done: hasVerifiedSettings, href: "/dashboard/settings" },
  ];
  const completed = steps.filter(s => s.done).length;

  return (
    <div className="animate-fade-in">
      <div className="flex flex-col lg:flex-row lg:items-start gap-8 lg:gap-16">
        {/* Left: Greeting */}
        <div className="flex-1 min-w-0 pt-1">
          <h1 className="text-[28px] md:text-[32px] font-semibold tracking-[-0.02em] text-[var(--text-primary)] leading-tight">
            {firstName ? `Welcome back, ${firstName}` : 'Welcome back'}
          </h1>
          <p className="text-[15px] text-[var(--text-tertiary)] mt-2 leading-relaxed max-w-lg">
            Move underwriting cases faster with AI. {completed === 0 ? 'Get started in under a minute.' : `${3 - completed} ${3 - completed === 1 ? 'step' : 'steps'} remaining.`}
          </p>
        </div>

        {/* Right: Steps */}
        <div className="shrink-0 w-full lg:w-80">
          {/* Progress */}
          <div className="flex items-center gap-3 mb-4">
            <div className="flex-1 h-[3px] bg-[var(--surface-secondary)] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-primary transition-all duration-700 ease-out"
                style={{ width: `${(completed / steps.length) * 100}%` }}
              />
            </div>
            <span className="text-[12px] font-medium text-[var(--text-tertiary)] tabular-nums">
              {completed}/{steps.length}
            </span>
          </div>

          <Button
            variant="ghost"
            size="sm"
            type="button"
            onClick={startTour}
            className="mb-3 h-8 rounded-lg px-3 text-[12px] font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-secondary)] hover:text-[var(--text-primary)]"
          >
            Take guided tour
          </Button>

          {/* Step list */}
          <div className="space-y-1">
            {steps.map((s, i) => (
              <Link key={i} href={s.href}
                className={`group flex items-center gap-3 px-3 py-2.5 -mx-3 rounded-xl text-[14px] transition-colors duration-150
                  ${s.done
                    ? 'text-[var(--text-muted)]'
                    : 'text-[var(--text-primary)] hover:bg-[var(--surface-secondary)] cursor-pointer'
                  }`}>
                {s.done ? (
                  <CheckCircle2 className="h-4 w-4 text-[#34d399] shrink-0" />
                ) : (
                  <div className="h-4 w-4 rounded-full border-[1.5px] border-[var(--text-faint)] shrink-0" />
                )}
                <span className={s.done ? 'line-through' : 'font-medium'}>{s.label}</span>
                {!s.done && <ArrowRight className="h-3.5 w-3.5 text-[var(--text-muted)] ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
