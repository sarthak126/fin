export const AUTH_BOOTSTRAP_RETRY_DELAYS_MS = [250, 600] as const;

export type AuthBootstrapErrorKind =
  | "expired_session"
  | "clock_skew"
  | "db_unavailable"
  | "auth_config"
  | "unknown";

export type AuthBootstrapFailureCopy = {
  kind: AuthBootstrapErrorKind;
  title: string;
  message: string;
  refreshLabel: string;
};

type RetryOptions = {
  retryDelaysMs?: readonly number[];
  sleep?: (delayMs: number) => Promise<void>;
};

type ErrorWithStatus = {
  status?: number;
  message?: string;
};

function defaultSleep(delayMs: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, delayMs));
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  if (error && typeof error === "object" && "message" in error) {
    return String((error as ErrorWithStatus).message || "");
  }
  return "";
}

function errorStatus(error: unknown): number | undefined {
  if (error && typeof error === "object" && "status" in error) {
    const status = Number((error as ErrorWithStatus).status);
    return Number.isFinite(status) ? status : undefined;
  }
  return undefined;
}

export async function runAuthBootstrapWithRetry<T>(
  operation: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const retryDelaysMs = options.retryDelaysMs ?? AUTH_BOOTSTRAP_RETRY_DELAYS_MS;
  const sleep = options.sleep ?? defaultSleep;

  for (let attempt = 0; attempt <= retryDelaysMs.length; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      if (attempt >= retryDelaysMs.length) {
        throw error;
      }
      await sleep(retryDelaysMs[attempt]);
    }
  }

  throw new Error("Authentication bootstrap failed");
}

export function getAuthBootstrapErrorKind(error: unknown): AuthBootstrapErrorKind {
  const status = errorStatus(error);
  const message = errorMessage(error).toLowerCase();

  if (
    message.includes("token expired") ||
    message.includes("expired session") ||
    message.includes("session expired")
  ) {
    return "expired_session";
  }

  if (
    message.includes("clock") ||
    message.includes("not yet valid") ||
    message.includes("immature") ||
    message.includes("nbf") ||
    message.includes("iat")
  ) {
    return "clock_skew";
  }

  if (
    message.includes("database") ||
    message.includes("query engine") ||
    message.includes("connection is unavailable") ||
    message.includes("database not connected")
  ) {
    return "db_unavailable";
  }

  if (
    message.includes("authentication is not configured") ||
    message.includes("clerk_secret_key") ||
    message.includes("jwks") ||
    message.includes("signing key") ||
    message.includes("auth config")
  ) {
    return "auth_config";
  }

  if (status === 401) {
    return "expired_session";
  }

  if (status === 503) {
    return "auth_config";
  }

  return "unknown";
}

export function describeAuthBootstrapFailure(error: unknown): AuthBootstrapFailureCopy {
  const kind = getAuthBootstrapErrorKind(error);

  if (kind === "expired_session") {
    return {
      kind,
      title: "Session needs refresh",
      message: "Your Clerk session may have expired. Refresh the session, then sign in again if Clerk asks.",
      refreshLabel: "Refresh session",
    };
  }

  if (kind === "clock_skew") {
    return {
      kind,
      title: "Session time check failed",
      message: "The session timestamp is outside the backend clock tolerance. Check your system clock, then refresh the session.",
      refreshLabel: "Refresh session",
    };
  }

  if (kind === "db_unavailable") {
    return {
      kind,
      title: "Backend database is not ready",
      message: "The backend is running but cannot reach the database yet. Wait for /health/ready to report ready, then refresh the session.",
      refreshLabel: "Refresh session",
    };
  }

  if (kind === "auth_config") {
    return {
      kind,
      title: "Authentication is not configured",
      message: "Clerk keys or JWKS access are missing or unavailable. Check local env, restart the backend and Next, then refresh the session.",
      refreshLabel: "Refresh session",
    };
  }

  return {
    kind,
    title: "Authentication setup failed",
    message: "The app could not initialize your session. Refresh the session; if it repeats, run npm run dev:doctor.",
    refreshLabel: "Refresh session",
  };
}
