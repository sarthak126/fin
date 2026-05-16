"use client";

import { ChevronRight } from "lucide-react";
import { usePathname } from "next/navigation";
import { UserButton } from "@clerk/nextjs";

import { ThemeToggle } from "@/components/ThemeToggle";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

type Crumb = {
  label: string;
  /** Display crumb as eyebrow / muted if not final */
  isFinal: boolean;
};

function truncateId(value: string, length = 8): string {
  if (value.length <= length) return value;
  return value.slice(0, length);
}

function buildCrumbs(pathname: string): Crumb[] {
  const segments = pathname.split("/").filter(Boolean);

  // Always anchor with Command Center for the prototype root.
  if (segments[0] !== "prototype") {
    return [{ label: "Command Center", isFinal: true }];
  }

  // /prototype
  if (segments.length === 1) {
    return [{ label: "Command Center", isFinal: true }];
  }

  // /prototype/upload
  if (segments[1] === "upload") {
    return [{ label: "New Case", isFinal: true }];
  }

  // /prototype/settings
  if (segments[1] === "settings") {
    return [{ label: "Settings", isFinal: true }];
  }

  // /prototype/cases (and /prototype/cases/[id])
  if (segments[1] === "cases") {
    if (segments.length === 2) {
      return [{ label: "Case Queue", isFinal: true }];
    }
    return [
      { label: "Case Queue", isFinal: false },
      { label: truncateId(segments[2]), isFinal: true },
    ];
  }

  // /prototype/reports/cases/[id]
  if (segments[1] === "reports") {
    if (segments[2] === "cases" && segments[3]) {
      return [
        { label: "Case Reports", isFinal: false },
        { label: truncateId(segments[3]), isFinal: true },
      ];
    }
    return [{ label: "Reports", isFinal: true }];
  }

  // Fallback — derive a single readable crumb.
  return [
    {
      label: segments
        .slice(1)
        .join(" / ")
        .replace(/\b\w/g, (char) => char.toUpperCase()),
      isFinal: true,
    },
  ];
}

function Breadcrumb({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <nav
      aria-label="Breadcrumb"
      className="flex min-w-0 items-center gap-1.5 text-[12px]"
    >
      {crumbs.map((crumb, index) => (
        <div key={`${crumb.label}-${index}`} className="flex min-w-0 items-center gap-1.5">
          {index > 0 ? (
            <ChevronRight
              className="h-3 w-3 shrink-0 text-[var(--text-faint)]"
              strokeWidth={1.5}
              aria-hidden="true"
            />
          ) : null}
          <span
            className={cn(
              "truncate",
              crumb.isFinal
                ? "text-[13px] font-semibold text-[var(--text-primary)]"
                : "font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]",
            )}
          >
            {crumb.label}
          </span>
        </div>
      ))}
    </nav>
  );
}

export function PrototypeTopbar() {
  const pathname = usePathname() ?? "/prototype";
  const crumbs = buildCrumbs(pathname);

  return (
    <header className="sticky top-0 z-30 border-b border-[var(--border-card)] bg-[var(--background)]/85 backdrop-blur-md">
      <div className="flex h-14 items-center gap-3 px-5 md:px-10 lg:px-14">
        <SidebarTrigger className="size-7 shrink-0 rounded-md text-[var(--text-muted)] hover:bg-[var(--surface-secondary)] hover:text-[var(--text-primary)]" />

        <div className="h-4 w-px bg-[var(--border-card)]" aria-hidden="true" />

        <Breadcrumb crumbs={crumbs} />

        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            aria-label="Open command palette"
            disabled
            className="hidden h-7 items-center gap-2 rounded-md border border-[var(--border-card)] bg-[var(--surface-secondary)]/60 px-2.5 text-[11px] font-medium text-[var(--text-tertiary)] transition-colors hover:border-[var(--border-card-hover)] hover:text-[var(--text-secondary)] disabled:opacity-90 sm:inline-flex"
          >
            <span className="font-mono uppercase tracking-[0.14em]">Search</span>
            <kbd className="rounded-sm border border-[var(--border-card)] bg-[var(--surface-raised)] px-1 py-px font-mono text-[10px] text-[var(--text-muted)]">
              ⌘K
            </kbd>
          </button>

          <ThemeToggle />

          <UserButton
            appearance={{ elements: { avatarBox: "h-7 w-7" } }}
          />
        </div>
      </div>
    </header>
  );
}
