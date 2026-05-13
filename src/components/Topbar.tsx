"use client";

import { Plus, Search, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";

export function Topbar() {
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border-card)] bg-[var(--background)]/88 backdrop-blur-xl">
      <div className="flex h-14 items-center justify-between gap-3 px-4 md:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger className="size-8 cursor-pointer rounded-lg text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-secondary)] hover:text-[var(--text-primary)]" />

          <div className="hidden h-8 min-w-[260px] items-center gap-2 rounded-lg border border-[var(--border-card)] bg-[var(--surface-glass)] px-3 text-[12px] text-[var(--text-tertiary)] shadow-[var(--shadow-card)] md:flex">
            <Search className="h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]" />
            <span className="truncate">Ask about exposure, applicants, policy rules</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="hidden items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-1.5 text-[12px] font-semibold text-emerald-600 dark:text-emerald-300 sm:flex">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Policy live</span>
          </div>
          <Button
            asChild
            className="tour-step-quick-upload h-8 cursor-pointer gap-1.5 rounded-lg bg-primary px-3 text-[12px] font-semibold text-primary-foreground shadow-md shadow-primary/20 transition-all hover:bg-primary/90 hover:shadow-primary/30"
          >
            <Link href="/dashboard/upload">
              <Plus className="h-3.5 w-3.5" />
              New Case
            </Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
