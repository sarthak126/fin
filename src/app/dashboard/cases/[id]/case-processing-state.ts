"use client";

import type { CaseDocumentReadModel } from "@/lib/api";

export type CaseDetailGateState = "waiting" | "stale" | "ready";

export interface CaseProcessingCounts {
  analyzedCount: number;
  activeCount: number;
  failedOrBlockedCount: number;
}

export interface CaseProcessingSnapshot extends CaseProcessingCounts {
  activeDocuments: CaseDocumentReadModel[];
  activeFingerprint: string | null;
  allRemainingDocumentsTerminal: boolean;
  hasActiveDocuments: boolean;
}

const ACTIVE_OCR_STAGES = new Set(["queued", "extracting", "ocr"]);

function normalizeStatus(value: string | null | undefined) {
  return String(value || "").trim().toLowerCase();
}

export function formatProcessingLabel(value: string | null | undefined) {
  const text = String(value || "").trim();
  if (!text) return "Pending";

  return text
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function isDocumentTerminal(document: CaseDocumentReadModel) {
  return normalizeStatus(document.status) === "failed" || document.ocr_status?.analysis_blocked === true;
}

export function isDocumentAnalyzed(document: CaseDocumentReadModel) {
  return normalizeStatus(document.status) === "analyzed";
}

export function isDocumentActivelyProcessing(document: CaseDocumentReadModel) {
  if (isDocumentTerminal(document)) {
    return false;
  }

  const status = normalizeStatus(document.status);
  if (status === "pending" || status === "processing") {
    return true;
  }

  const ocrStatus = document.ocr_status;
  if (!ocrStatus) {
    return false;
  }

  if (normalizeStatus(ocrStatus.ocr_quality_status) === "pending") {
    return true;
  }

  return ACTIVE_OCR_STAGES.has(normalizeStatus(ocrStatus.stage));
}

export function getActiveProcessingFingerprint(activeDocuments: CaseDocumentReadModel[]) {
  if (activeDocuments.length === 0) {
    return null;
  }

  return activeDocuments
    .map((document) => {
      const ocrStatus = document.ocr_status;

      return [
        document.id,
        document.status || "",
        ocrStatus?.stage || "",
        ocrStatus?.pages_processed ?? "",
        ocrStatus?.total_pages ?? "",
        document.updated_at || "",
      ].join("::");
    })
    .sort()
    .join("|");
}

export function getCaseProcessingSnapshot(documents: CaseDocumentReadModel[]): CaseProcessingSnapshot {
  const activeDocuments = documents.filter(isDocumentActivelyProcessing);
  const remainingDocuments = documents.filter((document) => !isDocumentAnalyzed(document));

  return {
    activeDocuments,
    activeCount: activeDocuments.length,
    activeFingerprint: getActiveProcessingFingerprint(activeDocuments),
    allRemainingDocumentsTerminal:
      remainingDocuments.length === 0 || remainingDocuments.every(isDocumentTerminal),
    analyzedCount: documents.filter(isDocumentAnalyzed).length,
    failedOrBlockedCount: documents.filter(isDocumentTerminal).length,
    hasActiveDocuments: activeDocuments.length > 0,
  };
}

export function getDocumentProcessingStageLabel(document: CaseDocumentReadModel) {
  const stage = normalizeStatus(document.ocr_status?.stage);
  if (stage) {
    return formatProcessingLabel(stage);
  }

  const status = normalizeStatus(document.status);
  if (status) {
    return formatProcessingLabel(status);
  }

  return "Pending";
}

export function getDocumentProcessingStageCopy(document: CaseDocumentReadModel) {
  const ocrStatus = document.ocr_status;
  const documentType = normalizeStatus(document.document_type);
  if (ocrStatus?.analysis_blocked) {
    return ocrStatus.user_message || "Analysis could not continue for this document.";
  }

  if (ocrStatus?.stage_message) {
    return ocrStatus.stage_message;
  }

  if (ocrStatus?.stage) {
    return `Current stage: ${formatProcessingLabel(ocrStatus.stage)}.`;
  }

  const status = normalizeStatus(document.status);
  if (status === "pending") {
    return "Queued for analysis.";
  }

  if (status === "processing") {
    if (documentType.includes("bank")) {
      return "Extracting transactions and validating financial patterns.";
    }

    if (documentType.includes("salary")) {
      return "Reading salary figures and validating employer and income fields.";
    }

    return "Extracting text and validating financial fields for this document.";
  }

  if (status === "failed") {
    return "Analysis failed for this document.";
  }

  return "Waiting for the next backend update.";
}

export function getDocumentProcessingProgress(document: CaseDocumentReadModel) {
  const pagesProcessed = document.ocr_status?.pages_processed ?? null;
  const totalPages = document.ocr_status?.total_pages ?? null;

  if (pagesProcessed === null && totalPages === null) {
    return { label: null, percent: null };
  }

  if (pagesProcessed !== null && totalPages !== null && totalPages > 0) {
    const percent = Math.max(8, Math.min(100, Math.round((pagesProcessed / totalPages) * 100)));

    return {
      label: `${pagesProcessed}/${totalPages} pages processed`,
      percent,
    };
  }

  if (pagesProcessed !== null) {
    return {
      label: `${pagesProcessed} pages processed`,
      percent: null,
    };
  }

  if (totalPages !== null && totalPages > 0) {
    return {
      label: `${totalPages} total pages`,
      percent: null,
    };
  }

  return { label: null, percent: null };
}
