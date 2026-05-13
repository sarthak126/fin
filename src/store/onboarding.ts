import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface OnboardingState {
  hasCompletedOnboarding: boolean;
  hasUploadedDocument: boolean;
  hasVerifiedSettings: boolean;
  tourIsActive: boolean;
  
  // Actions
  completeOnboarding: () => void;
  markDocumentUploaded: () => void;
  markSettingsVerified: () => void;
  startTour: () => void;
  stopTour: () => void;
  resetOnboarding: () => void; // for testing
}

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set) => ({
      hasCompletedOnboarding: false,
      hasUploadedDocument: false,
      hasVerifiedSettings: false,
      tourIsActive: false,

      completeOnboarding: () => set({ hasCompletedOnboarding: true }),
      markDocumentUploaded: () => set({ hasUploadedDocument: true }),
      markSettingsVerified: () => set({ hasVerifiedSettings: true }),
      startTour: () => set({ tourIsActive: true }),
      stopTour: () => set({ tourIsActive: false }),
      resetOnboarding: () => set({
        hasCompletedOnboarding: false,
        hasUploadedDocument: false,
        hasVerifiedSettings: false,
        tourIsActive: false,
      }),
    }),
    {
      name: 'argentnorth-onboarding-storage', // unique name
      partialize: (state) => ({ 
        hasCompletedOnboarding: state.hasCompletedOnboarding,
        hasUploadedDocument: state.hasUploadedDocument,
        hasVerifiedSettings: state.hasVerifiedSettings
      }),
    }
  )
);
