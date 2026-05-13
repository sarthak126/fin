"use client";

import { Activity, ClipboardList, LayoutDashboard, Settings, UploadCloud, Zap } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserButton } from "@clerk/nextjs";

import { HealthDot } from "@/components/argentnorth/prototype-ui";
import { ThemeToggle } from "@/components/ThemeToggle";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { isAuthEnabled } from "@/lib/auth";
import { useOnboardingStore } from "@/store/onboarding";

const items = [
  { title: "Command", url: "/dashboard", icon: LayoutDashboard },
  { title: "New Case", url: "/dashboard/upload", icon: UploadCloud },
  { title: "Case Queue", url: "/dashboard/cases", icon: ClipboardList },
  { title: "Settings", url: "/dashboard/settings", icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { markSettingsVerified } = useOnboardingStore();
  const authEnabled = isAuthEnabled();

  return (
    <Sidebar className="border-r border-[var(--border-card)] bg-sidebar font-sans" variant="sidebar">
      <SidebarContent className="gap-4">
        <div className="flex h-16 items-center px-4">
          <Link href="/dashboard" className="group flex min-w-0 items-center gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary shadow-[0_10px_22px_var(--glow-primary)]">
              <Zap className="h-4 w-4 text-primary-foreground" />
            </div>
            <div className="min-w-0">
              <span className="block truncate text-[14px] font-semibold text-[var(--text-primary)]">
                ArgentNorth
              </span>
              <span className="block truncate text-[11px] font-medium text-[var(--text-tertiary)]">
                CreditOS
              </span>
            </div>
          </Link>
        </div>

        <SidebarGroup className="px-2">
          <SidebarGroupLabel className="px-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
            Operations
          </SidebarGroupLabel>
          <SidebarGroupContent className="px-2">
            <SidebarMenu className="space-y-1">
              {items.map((item) => {
                const isActive =
                  pathname === item.url || (item.url !== "/dashboard" && pathname.startsWith(item.url));

                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      onClick={() => {
                        if (item.title === "Settings") markSettingsVerified();
                      }}
                      className={`group flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 text-[13px] transition-colors duration-150 ${isActive
                          ? "bg-primary/10 font-semibold text-[var(--text-primary)]"
                          : "text-[var(--text-tertiary)] hover:bg-[var(--surface-secondary)] hover:text-[var(--text-primary)]"
                        }`}
                    >
                      <Link href={item.url}>
                        <item.icon
                          className={`h-4 w-4 shrink-0 ${isActive ? "text-primary" : "text-[var(--text-muted)]"}`}
                          strokeWidth={isActive ? 2 : 1.5}
                        />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <div className="mx-4 rounded-lg border border-[var(--border-card)] bg-[var(--surface-glass)] p-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <HealthDot tone="good" />
              <span className="truncate text-[12px] font-semibold text-[var(--text-primary)]">
                Live decision fabric
              </span>
            </div>
            <Activity className="h-3.5 w-3.5 shrink-0 text-primary" />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <div>
              <p className="font-mono text-[15px] font-semibold leading-none text-[var(--text-primary)]">98.4%</p>
              <p className="mt-1 text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--text-muted)]">
                uptime
              </p>
            </div>
            <div>
              <p className="font-mono text-[15px] font-semibold leading-none text-[var(--text-primary)]">388ms</p>
              <p className="mt-1 text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--text-muted)]">
                p95
              </p>
            </div>
          </div>
        </div>
      </SidebarContent>

      <SidebarFooter className="mt-auto border-t border-[var(--border-card)] p-2">
        <div className="flex items-center justify-between px-1">
          <div className="flex min-w-0 items-center gap-2.5">
            {authEnabled ? (
              <>
                <UserButton appearance={{ elements: { userButtonAvatarBox: "h-7 w-7" } }} />
                <span className="truncate text-[13px] text-[var(--text-secondary)]">Account</span>
              </>
            ) : (
              <span className="truncate text-[13px] text-[var(--text-secondary)]">Local Dev Mode</span>
            )}
          </div>
          <ThemeToggle />
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
