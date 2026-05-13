"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { PageHeader, SectionHeading, StatusBadge, Surface } from "@/components/argentnorth/prototype-ui";
import { CheckCircle2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle,
  Bell,
  BookOpenCheck,
  Building2,
  Check,
  CreditCard,
  Download,
  Key,
  Monitor,
  Plus,
  RotateCcw,
  Shield,
  Sliders,
  Trash2,
  User,
  Users,
  Zap,
} from "lucide-react";
import { useHydrated } from "@/hooks/useHydrated";
import { useOnboardingStore } from "@/store/onboarding";
import {
  type AnalysisSettings,
  type NotificationSettings,
  type OrganizationSettings,
  type ProfileSettings,
  useSettingsStore,
} from "@/store/settings";

const tabs = [
  { id: "profile", label: "Profile", icon: User },
  { id: "organization", label: "Organization", icon: Building2 },
  { id: "security", label: "Security", icon: Shield },
  { id: "analysis", label: "Analysis", icon: Sliders },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "billing", label: "Billing", icon: CreditCard },
  { id: "danger", label: "Danger Zone", icon: AlertTriangle },
] as const;

type TabId = (typeof tabs)[number]["id"];

function profileEquals(a: ProfileSettings, b: ProfileSettings) {
  return a.fullName === b.fullName && a.workEmail === b.workEmail && a.jobTitle === b.jobTitle && a.organizationName === b.organizationName;
}

function organizationEquals(a: OrganizationSettings, b: OrganizationSettings) {
  return a.organizationName === b.organizationName && a.industry === b.industry && a.teamSize === b.teamSize;
}

function analysisEquals(a: AnalysisSettings, b: AnalysisSettings) {
  return a.bankStatements === b.bankStatements && a.salarySlips === b.salarySlips && a.itr === b.itr && a.loanAgreements === b.loanAgreements && a.processingMode === b.processingMode;
}

function notificationsEquals(a: NotificationSettings, b: NotificationSettings) {
  return a.analysisComplete === b.analysisComplete && a.highRisk === b.highRisk && a.weeklyReports === b.weeklyReports && a.teamActivity === b.teamActivity;
}

function useSaveFeedback() {
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!saved) return;
    const timeout = window.setTimeout(() => setSaved(false), 2000);
    return () => window.clearTimeout(timeout);
  }, [saved]);

  return { saved, showSaved: () => setSaved(true) };
}

function SettingsCard({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <Surface className="overflow-hidden p-0">
      <div className="border-b border-[var(--border-card)] px-6 py-4">
        <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">{title}</h3>
        {description ? <p className="mt-0.5 text-[12px] text-[var(--text-muted)]">{description}</p> : null}
      </div>
      <div className="px-6 py-5">{children}</div>
    </Surface>
  );
}

function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
      <div className="min-w-0">
        <span className="text-[13px] font-medium text-[var(--text-secondary)]">{label}</span>
        {description ? <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">{description}</p> : null}
      </div>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}

function ReadOnlyNote({ badge, children }: { badge: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-[var(--border-card)] bg-[var(--surface-secondary)] px-4 py-3">
      <Badge variant="secondary" className="mb-2 border-transparent bg-[var(--surface-hover)] text-[10px] uppercase tracking-wide text-[var(--text-secondary)]">
        {badge}
      </Badge>
      <p className="text-[12px] text-[var(--text-muted)]">{children}</p>
    </div>
  );
}

function SaveBar({ saved, dirty, onSave, label }: { saved: boolean; dirty: boolean; onSave: () => void; label: string }) {
  return (
    <div className="flex items-center justify-between">
      {saved ? (
        <div className="flex items-center gap-1.5 text-[12px] font-medium text-emerald-500">
          <Check className="h-3.5 w-3.5" />
          Saved in this browser
        </div>
      ) : (
        <div />
      )}
      <Button onClick={onSave} disabled={!dirty} className="ml-auto h-9 rounded-lg bg-primary px-5 text-[13px] font-medium text-primary-foreground shadow-md shadow-primary/20">
        {label}
      </Button>
    </div>
  );
}

function SettingsBanner() {
  return (
    <Surface className="px-4 py-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[13px] font-semibold text-[var(--text-primary)]">Workspace controls</p>
          <p className="mt-1 text-[12px] text-[var(--text-muted)]">
            Profile, organization, analysis, and notification preferences save in this browser today. Security, billing, team management, and destructive actions stay read-only until their backend flows exist.
          </p>
        </div>
        <Badge variant="secondary" className="h-fit border-transparent bg-primary/10 text-[11px] text-primary">
          Browser-saved
        </Badge>
      </div>
    </Surface>
  );
}

function ProfileTab() {
  const profile = useSettingsStore((state) => state.profile);
  const saveProfile = useSettingsStore((state) => state.saveProfile);
  const [draft, setDraft] = useState<ProfileSettings>(profile);
  const { saved, showSaved } = useSaveFeedback();

  useEffect(() => {
    setDraft(profile);
  }, [profile]);

  const dirty = !profileEquals(draft, profile);

  const save = () => {
    saveProfile(draft);
    showSaved();
  };

  return (
    <div className="space-y-5">
      <SettingsCard title="Personal Information" description="Editable profile fields until account-level sync lands.">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <Label className="mb-1.5 block text-[12px] text-[var(--text-muted)]">Full Name</Label>
            <Input value={draft.fullName} onChange={(event) => setDraft((current) => ({ ...current, fullName: event.target.value }))} placeholder="John Carter" className="h-9 border-[var(--border-card)] bg-[var(--surface-glass)] text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)]" />
          </div>
          <div>
            <Label className="mb-1.5 block text-[12px] text-[var(--text-muted)]">Work Email</Label>
            <Input value={draft.workEmail} onChange={(event) => setDraft((current) => ({ ...current, workEmail: event.target.value }))} placeholder="john@bank.com" type="email" className="h-9 border-[var(--border-card)] bg-[var(--surface-glass)] text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)]" />
          </div>
          <div>
            <Label className="mb-1.5 block text-[12px] text-[var(--text-muted)]">Role / Job Title</Label>
            <Input value={draft.jobTitle} onChange={(event) => setDraft((current) => ({ ...current, jobTitle: event.target.value }))} placeholder="Underwriter" className="h-9 border-[var(--border-card)] bg-[var(--surface-glass)] text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)]" />
          </div>
          <div>
            <Label className="mb-1.5 block text-[12px] text-[var(--text-muted)]">Organization</Label>
            <Input value={draft.organizationName} onChange={(event) => setDraft((current) => ({ ...current, organizationName: event.target.value }))} placeholder="Acme Bank" className="h-9 border-[var(--border-card)] bg-[var(--surface-glass)] text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)]" />
          </div>
        </div>
      </SettingsCard>
      <SaveBar saved={saved} dirty={dirty} onSave={save} label="Save Profile" />
    </div>
  );
}

function OrganizationTab() {
  const organization = useSettingsStore((state) => state.organization);
  const saveOrganization = useSettingsStore((state) => state.saveOrganization);
  const [draft, setDraft] = useState<OrganizationSettings>(organization);
  const { saved, showSaved } = useSaveFeedback();

  useEffect(() => {
    setDraft(organization);
  }, [organization]);

  const dirty = !organizationEquals(draft, organization);

  const save = () => {
    saveOrganization(draft);
    showSaved();
  };

  return (
    <div className="space-y-5">
      <SettingsCard title="Organization Details" description="Workspace metadata that stays available on this device.">
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label className="mb-1.5 block text-[12px] text-[var(--text-muted)]">Organization Name</Label>
              <Input value={draft.organizationName} onChange={(event) => setDraft((current) => ({ ...current, organizationName: event.target.value }))} placeholder="Acme Bank" className="h-9 border-[var(--border-card)] bg-[var(--surface-glass)] text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)]" />
            </div>
            <div>
              <Label className="mb-1.5 block text-[12px] text-[var(--text-muted)]">Industry</Label>
              <Input value={draft.industry} onChange={(event) => setDraft((current) => ({ ...current, industry: event.target.value }))} placeholder="Banking & Finance" className="h-9 border-[var(--border-card)] bg-[var(--surface-glass)] text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)]" />
            </div>
          </div>
          <div>
            <Label className="mb-1.5 block text-[12px] text-[var(--text-muted)]">Team Size</Label>
            <Input value={draft.teamSize} onChange={(event) => setDraft((current) => ({ ...current, teamSize: event.target.value }))} placeholder="10-50" className="h-9 max-w-xs border-[var(--border-card)] bg-[var(--surface-glass)] text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)]" />
          </div>
        </div>
      </SettingsCard>

      <SettingsCard title="Team Members" description="Invites and permissions will move here once org APIs are connected.">
        <div className="space-y-4">
          <ReadOnlyNote badge="Planned">Team invitations and role changes are intentionally read-only until backend membership management exists.</ReadOnlyNote>
          <div className="flex flex-col items-center justify-center py-5 text-center">
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--border-card)] bg-[var(--surface-secondary)]">
              <Users className="h-5 w-5 text-[var(--text-muted)]" />
            </div>
            <p className="mb-3 text-[13px] text-[var(--text-muted)]">Team roster tools are coming soon</p>
            <Button size="sm" disabled className="h-8 cursor-not-allowed gap-1.5 rounded-lg bg-primary text-[12px] text-primary-foreground opacity-50">
              <Plus className="h-3 w-3" />
              Invite Member
            </Button>
          </div>
        </div>
      </SettingsCard>
      <SaveBar saved={saved} dirty={dirty} onSave={save} label="Save Organization" />
    </div>
  );
}

function SecurityTab() {
  return (
    <div className="space-y-5">
      <SettingsCard title="Identity & MFA" description="Authentication is handled through Clerk-managed flows.">
        <div className="space-y-4">
          <ReadOnlyNote badge="Clerk-managed">Password entry, MFA enrollment, and recovery stay with the identity provider until account security screens are wired end to end.</ReadOnlyNote>
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-xl border border-[var(--border-card)] bg-[var(--surface-glass)] px-4 py-3">
              <div>
                <p className="text-[13px] font-medium text-[var(--text-secondary)]">Two-factor authentication</p>
                <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">Not configurable from this dashboard yet.</p>
              </div>
              <Badge variant="secondary" className="border-transparent bg-[var(--surface-hover)] text-[11px] text-[var(--text-secondary)]">Managed by Clerk</Badge>
            </div>
            <div className="flex items-center justify-between rounded-xl border border-[var(--border-card)] bg-[var(--surface-glass)] px-4 py-3">
              <div>
                <p className="text-[13px] font-medium text-[var(--text-secondary)]">Password resets</p>
                <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">Recovery still happens through the provider-managed flow.</p>
              </div>
              <Badge variant="secondary" className="border-transparent bg-[var(--surface-hover)] text-[11px] text-[var(--text-secondary)]">Frontend flow</Badge>
            </div>
          </div>
        </div>
      </SettingsCard>

      <SettingsCard title="Active Sessions" description="Session revocation from the dashboard is not wired yet.">
        <div className="space-y-4">
          <ReadOnlyNote badge="Read-only">We only expose the current device state here for now. Other-session sign-out will arrive once provider session management is connected.</ReadOnlyNote>
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10">
                <Monitor className="h-4 w-4 text-emerald-500" />
              </div>
              <div>
                <p className="text-[13px] font-medium text-[var(--text-secondary)]">Current Session</p>
                <p className="text-[11px] text-[var(--text-muted)]">This device - Active now</p>
              </div>
            </div>
            <Badge variant="secondary" className="border-transparent bg-emerald-500/10 text-[10px] text-emerald-500">Current</Badge>
          </div>
          <Button variant="outline" size="sm" disabled className="h-8 cursor-not-allowed rounded-lg border-[var(--border-card)] bg-transparent text-[12px] text-[var(--text-secondary)] opacity-50">
            Sign out of other sessions
          </Button>
        </div>
      </SettingsCard>

      <SettingsCard title="API Keys" description="Programmatic access is not available yet.">
        <div className="space-y-4">
          <ReadOnlyNote badge="Planned">API key issuance, rotation, and audit history are still backend backlog items, so key creation stays disabled for now.</ReadOnlyNote>
          <div className="flex flex-col items-center justify-center py-5 text-center">
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--border-card)] bg-[var(--surface-secondary)]">
              <Key className="h-5 w-5 text-[var(--text-muted)]" />
            </div>
            <p className="mb-1 text-[13px] text-[var(--text-muted)]">No API keys created</p>
            <p className="mb-3 max-w-xs text-[11px] text-[var(--text-muted)]">This section will become active once programmatic access ships.</p>
            <Button size="sm" disabled className="h-8 cursor-not-allowed gap-1.5 rounded-lg bg-primary text-[12px] text-primary-foreground opacity-50">
              <Plus className="h-3 w-3" />
              Create API Key
            </Button>
          </div>
        </div>
      </SettingsCard>
    </div>
  );
}

function AnalysisTab() {
  const analysis = useSettingsStore((state) => state.analysis);
  const saveAnalysis = useSettingsStore((state) => state.saveAnalysis);
  const [draft, setDraft] = useState<AnalysisSettings>(analysis);
  const { saved, showSaved } = useSaveFeedback();

  useEffect(() => {
    setDraft(analysis);
  }, [analysis]);

  const dirty = !analysisEquals(draft, analysis);

  const save = () => {
    saveAnalysis(draft);
    showSaved();
  };

  return (
    <div className="space-y-5">
      <SettingsCard title="Risk Thresholds" description="Current scoring bands are fixed while configurable policy rules are in progress.">
        <div className="space-y-3">
          {[
            { label: "Low Risk", range: "0-40", color: "bg-emerald-500" },
            { label: "Medium Risk", range: "41-70", color: "bg-amber-500" },
            { label: "High Risk", range: "71-100", color: "bg-red-500" },
          ].map((tier) => (
            <div key={tier.label} className="flex items-center justify-between py-2">
              <div className="flex items-center gap-2.5">
                <div className={`h-2 w-2 rounded-full ${tier.color}`} />
                <span className="text-[13px] font-medium text-[var(--text-secondary)]">{tier.label}</span>
              </div>
              <span className="font-mono text-[13px] text-[var(--text-muted)]">{tier.range}</span>
            </div>
          ))}
        </div>
      </SettingsCard>

      <SettingsCard title="Document Types" description="Choose which document classes this browser should queue for review.">
        <div className="divide-y divide-[var(--border-subtle)]">
          <ToggleRow label="Bank Statements" description="Monthly or quarterly bank statements" checked={draft.bankStatements} onChange={(value) => setDraft((current) => ({ ...current, bankStatements: value }))} />
          <ToggleRow label="Salary Slips" description="Employer-issued salary breakdowns" checked={draft.salarySlips} onChange={(value) => setDraft((current) => ({ ...current, salarySlips: value }))} />
          <ToggleRow label="Income Tax Returns" description="ITR forms and filings" checked={draft.itr} onChange={(value) => setDraft((current) => ({ ...current, itr: value }))} />
          <ToggleRow label="Loan Agreements" description="Existing loan documentation" checked={draft.loanAgreements} onChange={(value) => setDraft((current) => ({ ...current, loanAgreements: value }))} />
        </div>
      </SettingsCard>

      <SettingsCard title="Processing Mode" description="Balance turnaround time against review depth for this workspace.">
        <div className="grid grid-cols-2 gap-3">
          {[
            { id: "fast" as const, name: "Fast Mode", desc: "~30s per document", icon: Zap },
            { id: "accurate" as const, name: "Accurate Mode", desc: "~90s per document", icon: Shield },
          ].map((mode) => (
            <button
              key={mode.id}
              onClick={() => setDraft((current) => ({ ...current, processingMode: mode.id }))}
              className={`rounded-xl border p-4 text-left transition-all ${
                draft.processingMode === mode.id
                  ? "border-primary/30 bg-primary/5 shadow-sm"
                  : "border-[var(--border-card)] bg-[var(--surface-glass)] hover:bg-[var(--surface-hover)]"
              }`}
            >
              <mode.icon className={`mb-2 h-5 w-5 ${draft.processingMode === mode.id ? "text-primary" : "text-[var(--text-muted)]"}`} />
              <p className={`text-[13px] font-semibold ${draft.processingMode === mode.id ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)]"}`}>{mode.name}</p>
              <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">{mode.desc}</p>
            </button>
          ))}
        </div>
      </SettingsCard>
      <SaveBar saved={saved} dirty={dirty} onSave={save} label="Save Analysis" />
    </div>
  );
}

function NotificationsTab() {
  const notifications = useSettingsStore((state) => state.notifications);
  const saveNotifications = useSettingsStore((state) => state.saveNotifications);
  const [draft, setDraft] = useState<NotificationSettings>(notifications);
  const { saved, showSaved } = useSaveFeedback();

  useEffect(() => {
    setDraft(notifications);
  }, [notifications]);

  const dirty = !notificationsEquals(draft, notifications);

  const save = () => {
    saveNotifications(draft);
    showSaved();
  };

  return (
    <div className="space-y-5">
      <SettingsCard title="Email Notifications" description="Choose which alerts stay enabled on this device.">
        <div className="divide-y divide-[var(--border-subtle)]">
          <ToggleRow label="Analysis completed" description="Get notified when a document finishes processing." checked={draft.analysisComplete} onChange={(value) => setDraft((current) => ({ ...current, analysisComplete: value }))} />
          <ToggleRow label="High risk detected" description="Immediate alert when a high-risk flag is raised." checked={draft.highRisk} onChange={(value) => setDraft((current) => ({ ...current, highRisk: value }))} />
          <ToggleRow label="Weekly reports" description="Summary of analyses and risk trends." checked={draft.weeklyReports} onChange={(value) => setDraft((current) => ({ ...current, weeklyReports: value }))} />
          <ToggleRow label="Team activity" description="Notifications about team member actions." checked={draft.teamActivity} onChange={(value) => setDraft((current) => ({ ...current, teamActivity: value }))} />
        </div>
      </SettingsCard>
      <SaveBar saved={saved} dirty={dirty} onSave={save} label="Save Notifications" />
    </div>
  );
}

function BillingTab() {
  return (
    <div className="space-y-5">
      <SettingsCard title="Current Plan" description="Billing remains informational until subscriptions are wired.">
        <div className="space-y-4">
          <ReadOnlyNote badge="Read-only">Plan upgrades, payment collection, and usage enforcement are not connected to a live billing backend yet, so this section stays informational.</ReadOnlyNote>
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <div className="mb-1 flex items-center gap-2">
                <span className="text-[15px] font-bold text-[var(--text-primary)]">Free Plan</span>
                <Badge variant="secondary" className="border-transparent bg-primary/10 text-[10px] text-primary">Current</Badge>
              </div>
              <p className="text-[12px] text-[var(--text-muted)]">0 analyses this month - 10 analyses included</p>
            </div>
            <Button disabled className="h-9 cursor-not-allowed gap-1.5 rounded-lg bg-primary px-5 text-[13px] font-medium text-primary-foreground opacity-50">
              <Zap className="h-3.5 w-3.5" />
              Upgrade Plan
            </Button>
          </div>
          <div className="border-t border-[var(--border-card)] pt-4">
            <p className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Usage This Month</p>
            <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--surface-secondary)]">
              <div className="h-2 w-[0%] rounded-full bg-primary transition-all" />
            </div>
            <p className="mt-1.5 text-[11px] text-[var(--text-muted)]">0 of 10 analyses used</p>
          </div>
        </div>
      </SettingsCard>

      <SettingsCard title="Payment Method" description="Payment method management is disabled until billing integration ships.">
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--border-card)] bg-[var(--surface-secondary)]">
            <CreditCard className="h-5 w-5 text-[var(--text-muted)]" />
          </div>
          <p className="mb-3 text-[13px] text-[var(--text-muted)]">No payment method added</p>
          <Button size="sm" variant="outline" disabled className="h-8 cursor-not-allowed gap-1.5 rounded-lg border-[var(--border-card)] bg-transparent text-[12px] opacity-50">
            <Plus className="h-3 w-3" />
            Add Payment Method
          </Button>
        </div>
      </SettingsCard>

      <SettingsCard title="Invoices" description="Invoice export will arrive with live billing.">
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <p className="mb-3 text-[13px] text-[var(--text-muted)]">No invoices yet</p>
          <Button size="sm" variant="outline" disabled className="h-8 gap-1.5 rounded-lg border-[var(--border-card)] bg-transparent text-[12px] opacity-50">
            <Download className="h-3 w-3" />
            Download Invoices
          </Button>
        </div>
      </SettingsCard>
    </div>
  );
}

function DangerTab() {
  return (
    <div className="space-y-5">
      <Surface className="overflow-hidden p-0" style={{ borderColor: "rgba(239, 68, 68, 0.15)" }}>
        <div className="border-b border-red-500/10 px-6 py-4">
          <h3 className="text-[15px] font-semibold text-red-500">Danger Zone</h3>
          <p className="mt-0.5 text-[12px] text-[var(--text-muted)]">Destructive actions stay disabled until export and account lifecycle workflows are implemented safely.</p>
        </div>
        <div className="space-y-5 px-6 py-5">
          <ReadOnlyNote badge="Protected">Export, reset, and delete flows are intentionally unavailable because the product does not yet have the backend confirmation, audit, and recovery safeguards these actions need.</ReadOnlyNote>

          <div className="flex flex-col justify-between gap-3 border-b border-[var(--border-subtle)] pb-5 sm:flex-row sm:items-center">
            <div>
              <p className="text-[13px] font-medium text-[var(--text-secondary)]">Export All Data</p>
              <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">Download a full export of your analyses, cases, and account data.</p>
            </div>
            <Button variant="outline" size="sm" disabled className="h-8 shrink-0 cursor-not-allowed gap-1.5 rounded-lg border-[var(--border-card)] bg-transparent text-[12px] opacity-50">
              <Download className="h-3 w-3" />
              Export Data
            </Button>
          </div>

          <div className="flex flex-col justify-between gap-3 border-b border-[var(--border-subtle)] pb-5 sm:flex-row sm:items-center">
            <div>
              <p className="text-[13px] font-medium text-[var(--text-secondary)]">Reset Workspace</p>
              <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">Delete all analyses and reset your workspace to default settings.</p>
            </div>
            <Button variant="outline" size="sm" disabled className="h-8 shrink-0 cursor-not-allowed gap-1.5 rounded-lg border-amber-500/30 text-[12px] text-amber-500 opacity-50">
              <RotateCcw className="h-3 w-3" />
              Reset
            </Button>
          </div>

          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <div>
              <p className="text-[13px] font-medium text-red-500">Delete Account</p>
              <p className="mt-0.5 text-[11px] text-[var(--text-muted)]">Permanently delete your account and all associated data. This cannot be undone.</p>
            </div>
            <Button variant="outline" size="sm" disabled className="h-8 shrink-0 cursor-not-allowed gap-1.5 rounded-lg border-red-500/30 text-[12px] text-red-500 opacity-50">
              <Trash2 className="h-3 w-3" />
              Delete Account
            </Button>
          </div>
        </div>
      </Surface>
    </div>
  );
}

export default function SettingsPage() {
  const hydrated = useHydrated();
  const [activeTab, setActiveTab] = useState<TabId>("profile");
  const { markSettingsVerified } = useOnboardingStore();

  useEffect(() => {
    if (hydrated) markSettingsVerified();
  }, [hydrated, markSettingsVerified]);

  const renderTab = () => {
    switch (activeTab) {
      case "profile":
        return <ProfileTab />;
      case "organization":
        return <OrganizationTab />;
      case "security":
        return <SecurityTab />;
      case "analysis":
        return <AnalysisTab />;
      case "notifications":
        return <NotificationsTab />;
      case "billing":
        return <BillingTab />;
      case "danger":
        return <DangerTab />;
      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col gap-6 pb-10">
      <PageHeader
        eyebrow="Compliance & Settings"
        title="Governance controls for regulated credit operations."
        description="Workspace profile, organization, analysis, and notification preferences save in this browser. Security, billing, and destructive actions stay read-only until their backend flows ship."
      >
        <StatusBadge label="Audit-ready" tone="good" />
      </PageHeader>

      <SettingsBanner />

      {!hydrated ? (
        <Surface className="px-5 py-4 text-[13px] text-[var(--text-muted)]">Loading saved settings...</Surface>
      ) : (
        <div className="flex flex-col gap-6 lg:flex-row">
          <nav className="shrink-0 lg:w-52">
            <Surface className="p-1.5 lg:sticky lg:top-20">
              <div className="flex gap-0.5 overflow-x-auto lg:flex-col lg:overflow-visible">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`w-full cursor-pointer whitespace-nowrap rounded-lg px-3 py-2 text-left text-[13px] font-medium transition-all ${
                      activeTab === tab.id ? "bg-primary/10 text-primary" : "text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-secondary)]"
                    } ${tab.id === "danger" ? activeTab === "danger" ? "bg-red-500/10 text-red-500" : "text-red-400/70 hover:bg-red-500/5 hover:text-red-500" : ""}`}
                  >
                    <span className="flex items-center gap-2.5">
                      <tab.icon className={`h-4 w-4 shrink-0 ${tab.id === "danger" ? "" : activeTab === tab.id ? "text-primary" : "text-[var(--text-muted)]"}`} />
                      {tab.label}
                    </span>
                  </button>
                ))}
              </div>
            </Surface>
          </nav>

          <div className="min-w-0 flex-1 animate-fade-slide" key={activeTab}>
            {renderTab()}
          </div>
        </div>
      )}

      <Surface className="p-5">
        <SectionHeading
          icon={BookOpenCheck}
          title="Governance Battery"
          description="Platform-wide guardrails that apply regardless of the active tab."
        />
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {[
            "Human override required for reject decisions",
            "Agentic recommendations cannot write actions",
            "Audit export includes full reason-code chain",
            "Policy changes require dual approval before going live",
          ].map((item) => (
            <div
              key={item}
              className="flex items-start gap-2 text-[13px] leading-relaxed text-[var(--text-secondary)]"
            >
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
              <span>{item}</span>
            </div>
          ))}
        </div>
      </Surface>
    </div>
  );
}
