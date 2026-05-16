"use client";

import {
  Building2,
  ShieldCheck,
  UserCog,
  type LucideIcon,
} from "lucide-react";

import {
  DataTile,
  PageHeader,
  SectionHeading,
  StatusBadge,
  Surface,
} from "@/components/argentnorth/prototype-ui";

type SettingsSection = {
  eyebrow: string;
  title: string;
  description: string;
  icon: LucideIcon;
  rows: { label: string; value: string }[];
};

const SECTIONS: SettingsSection[] = [
  {
    eyebrow: "Profile",
    title: "Operator identity",
    description:
      "Authentication, contact, and notification preferences for the active operator.",
    icon: UserCog,
    rows: [
      { label: "Display name", value: "—" },
      { label: "Email", value: "—" },
      { label: "Role", value: "—" },
      { label: "MFA", value: "—" },
    ],
  },
  {
    eyebrow: "Organization",
    title: "Tenant configuration",
    description:
      "Organization metadata, capital rails, and policy authority defaults.",
    icon: Building2,
    rows: [
      { label: "Organization", value: "—" },
      { label: "Tenant ID", value: "—" },
      { label: "Capital rails", value: "—" },
      { label: "Default authority", value: "—" },
    ],
  },
  {
    eyebrow: "Compliance",
    title: "Controls & audit",
    description:
      "Policy controls, fairness checks, retention windows, and audit export posture.",
    icon: ShieldCheck,
    rows: [
      { label: "FREE-AI posture", value: "—" },
      { label: "Retention", value: "—" },
      { label: "Audit export", value: "—" },
      { label: "Fairness band", value: "—" },
    ],
  },
];

export default function PrototypeSettingsPage() {
  return (
    <div className="flex flex-col gap-8 pb-14">
      <PageHeader
        eyebrow="Settings"
        title="Operator, organization, and compliance controls."
        description="The settings surface composes three governed sections: profile, organization, and compliance. Live wiring is pending."
      >
        <StatusBadge tone="neutral" label="Wiring in progress" />
      </PageHeader>

      <div className="grid gap-4">
        {SECTIONS.map((section) => {
          const Icon = section.icon;

          return (
            <Surface key={section.eyebrow} className="overflow-hidden">
              <div className="flex flex-col gap-3 border-b border-[var(--border-card)] px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--text-muted)]">
                    {section.eyebrow}
                  </p>
                  <div className="mt-2">
                    <SectionHeading
                      icon={Icon}
                      title={section.title}
                      description={section.description}
                    />
                  </div>
                </div>
                <StatusBadge tone="neutral" label="Wiring in progress" />
              </div>

              <div className="grid gap-3 px-5 py-5 sm:grid-cols-2 xl:grid-cols-4">
                {section.rows.map((row) => (
                  <DataTile
                    key={`${section.eyebrow}-${row.label}`}
                    label={row.label}
                    value={row.value}
                  />
                ))}
              </div>
            </Surface>
          );
        })}
      </div>
    </div>
  );
}
