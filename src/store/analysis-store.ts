import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type AnalysisStatus = 'idle' | 'uploading' | 'analyzing' | 'success' | 'error' | 'timeout';

interface AnalysisSession {
  documentId: string | null;
  fileName: string | null;
  fileSize: number | null;
  status: AnalysisStatus;
  startedAt: number | null;
  errorMsg: string | null;
}

interface AnalysisStore extends AnalysisSession {
  // Actions
  startSession: (docId: string, fileName: string, fileSize: number) => void;
  updateStatus: (status: AnalysisStatus, errorMsg?: string) => void;
  clearSession: () => void;
}

const EMPTY_SESSION: AnalysisSession = {
  documentId: null,
  fileName: null,
  fileSize: null,
  status: 'idle',
  startedAt: null,
  errorMsg: null,
};

function isResumableSession(session: AnalysisSession): boolean {
  return Boolean(session.documentId) && (session.status === 'analyzing' || session.status === 'timeout');
}

function sanitizePersistedSession(session?: Partial<AnalysisSession> | null): AnalysisSession {
  const merged: AnalysisSession = {
    ...EMPTY_SESSION,
    ...session,
  };

  if (!isResumableSession(merged)) {
    return { ...EMPTY_SESSION };
  }

  return {
    documentId: merged.documentId,
    fileName: merged.fileName,
    fileSize: merged.fileSize,
    status: merged.status,
    startedAt: merged.startedAt,
    errorMsg: null,
  };
}

export const useAnalysisStore = create<AnalysisStore>()(
  persist(
    (set) => ({
      ...EMPTY_SESSION,

      startSession: (docId, fileName, fileSize) => set({
        documentId: docId,
        fileName,
        fileSize,
        status: 'analyzing',
        startedAt: Date.now(),
        errorMsg: null,
      }),

      updateStatus: (status, errorMsg) => set({ 
        status, 
        errorMsg: errorMsg || null 
      }),

      clearSession: () => set({ ...EMPTY_SESSION }),
    }),
    {
      name: 'loanlens-analysis-storage',
      version: 2,
      partialize: (state) => sanitizePersistedSession(state),
      migrate: (persistedState) => sanitizePersistedSession(persistedState as Partial<AnalysisSession> | null),
    }
  )
);
