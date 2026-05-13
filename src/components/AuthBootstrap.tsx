"use client";

import { useEffect, useState } from "react";
import { Loader2, RefreshCw, ShieldAlert } from "lucide-react";
import { useAuth } from "@clerk/nextjs";
import { useHydrated } from "@/hooks/useHydrated";
import { getApiToken, isAuthEnabled } from "@/lib/auth";
import { syncCurrentUser } from "@/lib/api";
import {
  describeAuthBootstrapFailure,
  runAuthBootstrapWithRetry,
  type AuthBootstrapFailureCopy,
} from "@/lib/auth-bootstrap";

type AuthBootstrapProps = {
  children: React.ReactNode;
};

export function AuthBootstrap({ children }: AuthBootstrapProps) {
  const { getToken } = useAuth();
  const hydrated = useHydrated();
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<AuthBootstrapFailureCopy | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      if (!hydrated) {
        return;
      }

      if (!isAuthEnabled()) {
        if (!cancelled) {
          setStatus("error");
          setError(describeAuthBootstrapFailure(new Error("Authentication is not configured.")));
        }
        return;
      }

      try {
        await runAuthBootstrapWithRetry(async () => {
          const token = await getApiToken(getToken);
          await syncCurrentUser(token);
        });
        if (!cancelled) {
          setStatus("ready");
        }
      } catch (err) {
        if (!cancelled) {
          setStatus("error");
          setError(describeAuthBootstrapFailure(err));
        }
      }
    }

    bootstrap();

    return () => {
      cancelled = true;
    };
  }, [getToken, hydrated]);

  if (!hydrated) {
    return null;
  }

  if (status === "loading") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="flex items-center gap-3 rounded-xl border border-[var(--border-card)] bg-[var(--surface-secondary)] px-4 py-3 text-sm text-[var(--text-secondary)]">
          <Loader2 className="h-4 w-4 animate-spin" />
          Securing your workspace...
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="max-w-md rounded-2xl border border-red-500/20 bg-red-500/5 px-5 py-4 text-sm text-red-200">
          <div className="flex items-start gap-3">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
            <div>
              <p className="font-semibold text-red-100">Authentication setup failed</p>
              <p className="mt-1 font-medium text-red-100">{error?.title}</p>
              <p className="mt-1 text-red-200/90">{error?.message}</p>
              <button
                type="button"
                onClick={() => window.location.reload()}
                className="mt-4 inline-flex h-9 items-center gap-2 rounded-md border border-red-400/30 bg-red-400/10 px-3 text-xs font-semibold text-red-50 transition hover:bg-red-400/20"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                {error?.refreshLabel ?? "Refresh session"}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
