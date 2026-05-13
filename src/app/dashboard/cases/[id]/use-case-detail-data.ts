"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  finalizeCase,
  getCaseReadModel,
  getCaseReport,
  type CaseReadModel,
  type CaseReportPayload,
} from "@/lib/api";
import { getApiToken } from "@/lib/auth";

import {
  type CaseDetailGateState,
  type CaseProcessingCounts,
  getCaseProcessingSnapshot,
} from "./case-processing-state";

type TokenGetter = () => Promise<string | null>;

type StaleReason = "fingerprint_stalled" | "total_wait_exceeded" | null;

interface CaseProcessingStaleMeta {
  fingerprintAgeMs: number;
  isStale: boolean;
  reason: StaleReason;
  totalWaitMs: number;
}

interface ProcessingTrackerState {
  cycleStartedAt: number | null;
  fingerprint: string | null;
  fingerprintStartedAt: number | null;
}

function getCaseDetailErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) {
      return "Your session expired. Refresh the page and sign in again.";
    }
    return error.message;
  }

  return error instanceof Error ? error.message : fallback;
}

function getNumericEnvValue(value: string | undefined, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function getNumericClientOverride(storageKey: string, fallback: number) {
  if (typeof window === "undefined") {
    return fallback;
  }

  try {
    const rawValue = window.localStorage.getItem(storageKey);
    const parsed = Number(rawValue);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
  } catch {
    return fallback;
  }
}

const EMPTY_COUNTS: CaseProcessingCounts = {
  activeCount: 0,
  analyzedCount: 0,
  failedOrBlockedCount: 0,
};

const EMPTY_STALE_META: CaseProcessingStaleMeta = {
  fingerprintAgeMs: 0,
  isStale: false,
  reason: null,
  totalWaitMs: 0,
};

function getStaleMeta(
  activeFingerprint: string | null,
  hasActiveDocuments: boolean,
  tracker: ProcessingTrackerState,
  now: number,
  staleFingerprintMs: number,
  staleTotalWaitMs: number
): CaseProcessingStaleMeta {
  if (!hasActiveDocuments || !activeFingerprint) {
    tracker.cycleStartedAt = null;
    tracker.fingerprint = null;
    tracker.fingerprintStartedAt = null;
    return EMPTY_STALE_META;
  }

  if (tracker.cycleStartedAt === null) {
    tracker.cycleStartedAt = now;
  }

  if (tracker.fingerprint !== activeFingerprint) {
    tracker.fingerprint = activeFingerprint;
    tracker.fingerprintStartedAt = now;
  }

  if (tracker.fingerprintStartedAt === null) {
    tracker.fingerprintStartedAt = now;
  }

  const totalWaitMs = Math.max(0, now - tracker.cycleStartedAt);
  const fingerprintAgeMs = Math.max(0, now - tracker.fingerprintStartedAt);

  let reason: StaleReason = null;
  if (totalWaitMs >= staleTotalWaitMs) {
    reason = "total_wait_exceeded";
  } else if (fingerprintAgeMs >= staleFingerprintMs) {
    reason = "fingerprint_stalled";
  }

  return {
    fingerprintAgeMs,
    isStale: reason !== null,
    reason,
    totalWaitMs,
  };
}

export function useCaseDetailData({
  caseId,
  getToken,
}: {
  caseId: string;
  getToken: TokenGetter;
}) {
  const [readModel, setReadModel] = useState<CaseReadModel | null>(null);
  const [report, setReport] = useState<CaseReportPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [finalizing, setFinalizing] = useState(false);
  const [gateState, setGateState] = useState<CaseDetailGateState>("waiting");
  const [activeDocuments, setActiveDocuments] = useState<CaseReadModel["documents"]>([]);
  const [processingCounts, setProcessingCounts] = useState<CaseProcessingCounts>(EMPTY_COUNTS);
  const [settlePollingUntil, setSettlePollingUntil] = useState<number | null>(null);
  const [staleMeta, setStaleMeta] = useState<CaseProcessingStaleMeta>(EMPTY_STALE_META);
  const [timingConfig] = useState(() => ({
    pollIntervalMs: getNumericClientOverride(
      "codex.caseDetail.pollIntervalMs",
      getNumericEnvValue(process.env.NEXT_PUBLIC_CASE_DETAIL_POLL_INTERVAL_MS, 3000)
    ),
    readySettleMs: getNumericClientOverride(
      "codex.caseDetail.readySettleMs",
      getNumericEnvValue(process.env.NEXT_PUBLIC_CASE_DETAIL_READY_SETTLE_MS, 3500)
    ),
    staleFingerprintMs: getNumericClientOverride(
      "codex.caseDetail.staleFingerprintMs",
      getNumericEnvValue(process.env.NEXT_PUBLIC_CASE_DETAIL_STALE_FINGERPRINT_MS, 30000)
    ),
    staleTotalWaitMs: getNumericClientOverride(
      "codex.caseDetail.staleTotalWaitMs",
      getNumericEnvValue(process.env.NEXT_PUBLIC_CASE_DETAIL_STALE_TOTAL_WAIT_MS, 90000)
    ),
  }));

  const reportRef = useRef<CaseReportPayload | null>(null);
  const requestIdRef = useRef(0);
  const trackerRef = useRef<ProcessingTrackerState>({
    cycleStartedAt: null,
    fingerprint: null,
    fingerprintStartedAt: null,
  });

  useEffect(() => {
    reportRef.current = report;
  }, [report]);

  useEffect(() => {
    requestIdRef.current += 1;
    trackerRef.current = {
      cycleStartedAt: null,
      fingerprint: null,
      fingerprintStartedAt: null,
    };
    reportRef.current = null;

    setActiveDocuments([]);
    setError("");
    setGateState("waiting");
    setLoading(true);
    setProcessingCounts(EMPTY_COUNTS);
    setReadModel(null);
    setReport(null);
    setSettlePollingUntil(null);
    setStaleMeta(EMPTY_STALE_META);
  }, [caseId]);

  const loadData = useCallback(
    async (silent = false) => {
      const requestId = ++requestIdRef.current;

      try {
        if (!silent) {
          setLoading(true);
        }

        const token = await getApiToken(getToken);
        if (requestId !== requestIdRef.current) {
          return;
        }

        const nextReadModel = await getCaseReadModel(caseId, token);
        if (requestId !== requestIdRef.current) {
          return;
        }

        const processingSnapshot = getCaseProcessingSnapshot(nextReadModel.documents);
        const now = Date.now();
        const nextStaleMeta = getStaleMeta(
          processingSnapshot.activeFingerprint,
          processingSnapshot.hasActiveDocuments,
          trackerRef.current,
          now,
          timingConfig.staleFingerprintMs,
          timingConfig.staleTotalWaitMs
        );
        const nextGateState: CaseDetailGateState =
          processingSnapshot.hasActiveDocuments && !nextStaleMeta.isStale ? "waiting" : nextStaleMeta.isStale ? "stale" : "ready";
        const shouldLoadReport = nextGateState !== "waiting" || reportRef.current !== null;

        if (silent && shouldLoadReport && reportRef.current === null) {
          setLoading(true);
        }

        setActiveDocuments(processingSnapshot.activeDocuments);
        setGateState(nextGateState);
        setProcessingCounts({
          activeCount: processingSnapshot.activeCount,
          analyzedCount: processingSnapshot.analyzedCount,
          failedOrBlockedCount: processingSnapshot.failedOrBlockedCount,
        });
        setReadModel(nextReadModel);
        setSettlePollingUntil((current) => {
          if (nextGateState !== "ready") {
            return null;
          }

          return current ?? now + timingConfig.readySettleMs;
        });
        setStaleMeta(nextStaleMeta);

        if (shouldLoadReport) {
          const nextReport = await getCaseReport(caseId, token);
          if (requestId !== requestIdRef.current) {
            return;
          }

          reportRef.current = nextReport;
          setReport(nextReport);
        }

        setError("");
      } catch (err) {
        if (requestId !== requestIdRef.current) {
          return;
        }

        setError(getCaseDetailErrorMessage(err, "Failed to load case data."));
      } finally {
        if (requestId === requestIdRef.current) {
          setLoading(false);
        }
      }
    },
    [caseId, getToken, timingConfig.readySettleMs, timingConfig.staleFingerprintMs, timingConfig.staleTotalWaitMs]
  );

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    const shouldKeepSettling = settlePollingUntil !== null && Date.now() < settlePollingUntil;

    if (!caseId || (!activeDocuments.length && gateState !== "stale" && !shouldKeepSettling)) {
      return;
    }

    const interval = setInterval(() => {
      void loadData(true);
    }, timingConfig.pollIntervalMs);

    return () => {
      clearInterval(interval);
    };
  }, [activeDocuments.length, caseId, gateState, loadData, settlePollingUntil, timingConfig.pollIntervalMs]);

  const finalize = useCallback(async () => {
    try {
      setFinalizing(true);
      const token = await getApiToken(getToken);
      await finalizeCase(caseId, token);
      await loadData(true);
      setError("");
    } catch (err) {
      setError(getCaseDetailErrorMessage(err, "Failed to finalize case."));
    } finally {
      setFinalizing(false);
    }
  }, [caseId, getToken, loadData]);

  const reload = useCallback(async () => {
    await loadData();
  }, [loadData]);

  return {
    activeDocuments,
    error,
    finalizing,
    finalize,
    gateState,
    loading,
    processingCounts,
    readModel,
    reload,
    report,
    staleMeta,
  };
}
