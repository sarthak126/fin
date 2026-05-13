"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ProcessingMode = "fast" | "accurate";

export interface ProfileSettings {
  fullName: string;
  workEmail: string;
  jobTitle: string;
  organizationName: string;
}

export interface OrganizationSettings {
  organizationName: string;
  industry: string;
  teamSize: string;
}

export interface AnalysisSettings {
  bankStatements: boolean;
  salarySlips: boolean;
  itr: boolean;
  loanAgreements: boolean;
  processingMode: ProcessingMode;
}

export interface NotificationSettings {
  analysisComplete: boolean;
  highRisk: boolean;
  weeklyReports: boolean;
  teamActivity: boolean;
}

interface SettingsState {
  profile: ProfileSettings;
  organization: OrganizationSettings;
  analysis: AnalysisSettings;
  notifications: NotificationSettings;
  saveProfile: (profile: ProfileSettings) => void;
  saveOrganization: (organization: OrganizationSettings) => void;
  saveAnalysis: (analysis: AnalysisSettings) => void;
  saveNotifications: (notifications: NotificationSettings) => void;
  resetSettings: () => void;
}

const defaultProfile: ProfileSettings = {
  fullName: "",
  workEmail: "",
  jobTitle: "",
  organizationName: "",
};

const defaultOrganization: OrganizationSettings = {
  organizationName: "",
  industry: "",
  teamSize: "",
};

const defaultAnalysis: AnalysisSettings = {
  bankStatements: true,
  salarySlips: true,
  itr: true,
  loanAgreements: false,
  processingMode: "accurate",
};

const defaultNotifications: NotificationSettings = {
  analysisComplete: true,
  highRisk: true,
  weeklyReports: false,
  teamActivity: false,
};

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      profile: defaultProfile,
      organization: defaultOrganization,
      analysis: defaultAnalysis,
      notifications: defaultNotifications,
      saveProfile: (profile) => set({ profile }),
      saveOrganization: (organization) => set({ organization }),
      saveAnalysis: (analysis) => set({ analysis }),
      saveNotifications: (notifications) => set({ notifications }),
      resetSettings: () =>
        set({
          profile: defaultProfile,
          organization: defaultOrganization,
          analysis: defaultAnalysis,
          notifications: defaultNotifications,
        }),
    }),
    {
      name: "loanlens-settings-storage",
      partialize: (state) => ({
        profile: state.profile,
        organization: state.organization,
        analysis: state.analysis,
        notifications: state.notifications,
      }),
    }
  )
);
