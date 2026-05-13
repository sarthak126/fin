"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  Cpu,
  Database,
  File,
  Info,
  ScanText,
  Shield,
  type LucideIcon,
} from "lucide-react";

import { getAnalysisJobStatus, getDocument } from "@/lib/api";
import { getApiToken } from "@/lib/auth";
import type { AnalysisStatus } from "@/store/analysis-store";

type TokenGetter = () => Promise<string | null>;

export interface UploadStage {
  id: string;
  label: string;
  icon: LucideIcon;
  substeps: string[];
}

export interface DocumentTypeOption {
  value: string;
  label: string;
  hint: string;
}

export const STAGES: UploadStage[] = [
  { id: "queued", label: "Upload complete", icon: CheckCircle2, substeps: [] },
  {
    id: "extracting",
    label: "Extracting native text",
    icon: File,
    substeps: ["Opening document structure", "Reading embedded text", "Checking which pages need OCR"],
  },
  {
    id: "ocr",
    label: "Running OCR",
    icon: ScanText,
    substeps: ["Sending scanned pages to OCR", "Falling back to local OCR if needed", "Normalizing recovered text"],
  },
  {
    id: "chunking",
    label: "Chunking document",
    icon: Shield,
    substeps: ["Segmenting the document", "Grouping related sections", "Preparing retrieval chunks"],
  },
  {
    id: "vectorizing",
    label: "Building retrieval index",
    icon: Database,
    substeps: ["Generating embeddings", "Persisting chunk vectors", "Linking the document index"],
  },
  {
    id: "analyzing",
    label: "Analyzing semantics",
    icon: Cpu,
    substeps: ["Understanding financial signals", "Evaluating risk indicators", "Comparing extracted patterns"],
  },
  {
    id: "finalizing",
    label: "Finalizing insights",
    icon: Info,
    substeps: ["Formatting summary output", "Saving analysis results", "Preparing the case detail view"],
  },
];

export const DOCUMENT_TYPE_OPTIONS: DocumentTypeOption[] = [
  { value: "auto", label: "Auto-detect (recommended)", hint: "Let ArgentNorth infer type from content + filename" },
  { value: "bank_statement", label: "Bank statement", hint: "Balances, salary credits, NACH/EMIs, cash deposits" },
  { value: "salary_slip", label: "Salary slip / payslip", hint: "Net pay, deductions, employer, pay period" },
  { value: "tax_return", label: "ITR / tax return", hint: "Declared income, stability, self-employed signals" },
  { value: "employment_letter", label: "Employment letter / offer letter", hint: "Tenure, compensation, contract terms" },
  { value: "income_proof", label: "Income proof (other)", hint: "Recurring income evidence and consistency" },
  { value: "id_document", label: "ID document (PAN/Aadhaar/etc.)", hint: "Identity-only; financial fields usually null" },
  { value: "other", label: "Other", hint: "Best-effort extraction with stronger confidence notes" },
];

const JOB_STAGE_TO_INDEX: Record<string, number> = {
  queued: 0,
  extracting: 1,
  ocr: 2,
  chunking: 3,
  vectorizing: 4,
  analyzing: 5,
  finalizing: 6,
  completed: 6,
  failed: 6,
};

function mapStageToIndex(stage: string | null | undefined): number | null {
  if (!stage) {
    return null;
  }
  return JOB_STAGE_TO_INDEX[stage] ?? null;
}

export function useUploadAnalysisProgress({
  documentId,
  getToken,
  markDocumentUploaded,
  onCompleted,
  startedAt,
  status,
  updateStatus,
}: {
  documentId: string | null;
  getToken: TokenGetter;
  markDocumentUploaded: () => void;
  onCompleted: (documentId: string) => void;
  startedAt: number | null;
  status: AnalysisStatus;
  updateStatus: (status: AnalysisStatus, errorMsg?: string) => void;
}) {
  const [currentStage, setCurrentStage] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [substepIdx, setSubstepIdx] = useState(0);
  const [stageMessage, setStageMessage] = useState<string | null>(null);
  const [pagesProcessed, setPagesProcessed] = useState<number | null>(null);
  const [totalPages, setTotalPages] = useState<number | null>(null);
  const [ocrProvider, setOcrProvider] = useState<string | null>(null);
  const [usingLiveStatus, setUsingLiveStatus] = useState(false);

  const resetProgress = useCallback(() => {
    setCurrentStage(0);
    setElapsed(0);
    setSubstepIdx(0);
    setStageMessage(null);
    setPagesProcessed(null);
    setTotalPages(null);
    setOcrProvider(null);
    setUsingLiveStatus(false);
  }, []);

  useEffect(() => {
    if (status !== "analyzing" && status !== "timeout") {
      return;
    }

    const interval = setInterval(() => {
      const seconds = Math.floor((Date.now() - (startedAt || Date.now())) / 1000);
      setElapsed(seconds);
    }, 1000);

    return () => clearInterval(interval);
  }, [startedAt, status]);

  useEffect(() => {
    if (!documentId || (status !== "analyzing" && status !== "timeout")) {
      return;
    }

    let cancelled = false;
    const pollDocumentStatus = async () => {
      try {
        const token = await getApiToken(getToken);

        let latestJobError: string | null = null;
        try {
          const job = await getAnalysisJobStatus(documentId, token);
          if (cancelled) {
            return;
          }

          const liveStageIndex = mapStageToIndex(job.stage);
          if (liveStageIndex !== null) {
            if (liveStageIndex !== currentStage) {
              setSubstepIdx(0);
            }
            setCurrentStage(liveStageIndex);
          }
          setUsingLiveStatus(true);

          setStageMessage(job.stage_message ?? null);
          setPagesProcessed(job.pages_processed ?? null);
          setTotalPages(job.total_pages ?? null);
          setOcrProvider(job.ocr_provider ?? null);

          if (job.status === "failed") {
            latestJobError = job.user_message || job.last_error || "Analysis failed. Please retry.";
          }
        } catch {
          if (!cancelled) {
            setUsingLiveStatus(false);
            setStageMessage(null);
            setPagesProcessed(null);
            setTotalPages(null);
            setOcrProvider(null);
          }
        }

        const document = await getDocument(documentId, token);

        if (cancelled) {
          return;
        }

        if (document.status === "analyzed") {
          updateStatus("success");
          markDocumentUploaded();
          onCompleted(documentId);
          return;
        }

        if (document.status === "failed") {
          updateStatus("error", latestJobError || "Analysis failed. Please retry.");
        }
      } catch (error) {
        if (!cancelled) {
          updateStatus(
            "error",
            error instanceof Error ? error.message : "Unable to refresh analysis status."
          );
        }
      }
    };

    void pollDocumentStatus();
    const interval = setInterval(() => {
      void pollDocumentStatus();
    }, 3000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [currentStage, documentId, getToken, markDocumentUploaded, onCompleted, status, updateStatus]);

  return {
    currentStage,
    elapsed,
    ocrProvider,
    pagesProcessed,
    resetProgress,
    stageMessage,
    substepIdx,
    totalPages,
    usingLiveStatus,
  };
}
