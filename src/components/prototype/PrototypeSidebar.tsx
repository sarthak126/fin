"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import {
  ClipboardList,
  Command,
  Hexagon,
  Settings,
  UploadCloud,
  type LucideIcon,
} from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

type NavItem = {
  title: string;
  url: string;
  icon: LucideIcon;
};

const NAV_ITEMS: NavItem[] = [
  { title: "Command Center", url: "/prototype", icon: Command },
  { title: "New Case", url: "/prototype/upload", icon: UploadCloud },
  { title: "Case Queue", url: "/prototype/cases", icon: ClipboardList },
  { title: "Settings", url: "/prototype/settings", icon: Settings },
];

function getEnvLabel(): string {
  const raw = process.env.NEXT_PUBLIC_ENV?.trim();
  if (!raw) return "LIVE";
  return raw.toUpperCase();
}

function isItemActive(pathname: string, url: string): boolean {
  if (url === "/prototype") return pathname === "/prototype";
  return pathname === url || pathname.startsWith(`${url}/`);
}

export function PrototypeSidebar() {
  const pathname = usePathname() ?? "/prototype";
  const { user, isLoaded } = useUser();
  const envLabel = getEnvLabel();

  const operatorName =
    user?.fullName?.trim() ||
    user?.primaryEmailAddress?.emailAddress ||
    user?.username ||
    "Operator";
  const operatorEmail = user?.primaryEmailAddress?.emailAddress ?? "";
  const operatorInitials = (
    user?.firstName?.[0] ||
    user?.fullName?.[0] ||
    user?.primaryEmailAddress?.emailAddress?.[0] ||
    "O"
  ).toUpperCase();
  const operatorAvatar = user?.imageUrl;

  return (
    <Sidebar
      variant="sidebar"
      className="border-r border-[var(--border-card)] bg-[var(--sidebar)] font-sans"
    >
      <SidebarHeader className="gap-0 border-b border-[var(--border-card)] px-4 py-4">
        <Link
          href="/prototype"
          className="group flex min-w-0 items-center gap-2.5 focus-visible:outline-none"
        >
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-[var(--border-card)] bg-[var(--surface-secondary)] text-[var(--text-primary)]">
            <Hexagon className="h-3.5 w-3.5" strokeWidth={1.5} />
          </div>
          <div className="min-w-0">
            <span className="block truncate font-mono text-xs font-bold uppercase tracking-[0.2em] text-[var(--text-primary)]">
              ArgentNorth
            </span>
            <span className="mt-0.5 block truncate text-[10px] font-medium uppercase tracking-[0.18em] text-[var(--text-muted)]">
              Credit Intelligence Layer
            </span>
          </div>
        </Link>
      </SidebarHeader>

      <SidebarContent className="gap-0 px-3 py-4">
        <div className="px-2 pb-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--text-muted)]">
            Operations
          </p>
        </div>

        <SidebarMenu className="gap-0.5">
          {NAV_ITEMS.map((item) => {
            const isActive = isItemActive(pathname, item.url);
            const Icon = item.icon;

            return (
              <SidebarMenuItem key={item.url}>
                <SidebarMenuButton
                  asChild
                  isActive={isActive}
                  className={cn(
                    "group relative h-9 w-full gap-2.5 rounded-md border border-transparent px-2.5 text-[13px] font-medium transition-colors duration-150 hover:bg-[var(--surface-secondary)] hover:text-[var(--text-primary)]",
                    "data-[active=true]:border-[var(--border-card)] data-[active=true]:bg-[var(--surface-secondary)] data-[active=true]:text-[var(--text-primary)]",
                    isActive
                      ? "text-[var(--text-primary)]"
                      : "text-[var(--text-tertiary)]",
                  )}
                >
                  <Link href={item.url}>
                    {isActive ? (
                      <span
                        aria-hidden="true"
                        className="absolute inset-y-1.5 left-0 w-[2px] rounded-r-sm bg-[var(--primary)]"
                      />
                    ) : null}
                    <Icon
                      className={cn(
                        "h-4 w-4 shrink-0",
                        isActive
                          ? "text-[var(--primary)]"
                          : "text-[var(--text-muted)] group-hover:text-[var(--text-secondary)]",
                      )}
                      strokeWidth={1.5}
                    />
                    <span className="truncate">{item.title}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarContent>

      <SidebarFooter className="mt-auto border-t border-[var(--border-card)] p-3">
        <div className="rounded-md border border-[var(--border-card)] bg-[var(--surface-secondary)] px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
              Operator
            </p>
            <span className="inline-flex items-center rounded-sm border border-[var(--border-card)] bg-[var(--surface-raised)] px-1.5 py-0.5 font-mono text-[9px] font-semibold tracking-[0.14em] text-[var(--text-secondary)]">
              {envLabel}
            </span>
          </div>
          <div className="mt-2 flex min-w-0 items-center gap-2.5">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full border border-[var(--border-card)] bg-[var(--surface-raised)] text-[11px] font-semibold text-[var(--text-secondary)]">
              {operatorAvatar ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={operatorAvatar}
                  alt=""
                  className="h-full w-full object-cover"
                />
              ) : (
                <span>{isLoaded ? operatorInitials : "·"}</span>
              )}
            </div>
            <div className="min-w-0">
              <p className="truncate text-[12px] font-semibold text-[var(--text-primary)]">
                {isLoaded ? operatorName : "Loading…"}
              </p>
              {operatorEmail ? (
                <p className="truncate text-[11px] text-[var(--text-muted)]">
                  {operatorEmail}
                </p>
              ) : (
                <p className="truncate text-[11px] text-[var(--text-muted)]">
                  Authenticated session
                </p>
              )}
            </div>
          </div>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
