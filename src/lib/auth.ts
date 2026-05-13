const AUTH_FEATURE_ENABLED =
  process.env.NEXT_PUBLIC_ENABLE_AUTH?.trim().toLowerCase() !== "false";

type TokenGetter = () => Promise<string | null>;

function hasE2EAuthBypassCookie() {
  if (typeof window === "undefined") {
    return false;
  }

  const isLocalHost =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === "::1";

  return (
    isLocalHost &&
    document.cookie
      .split(";")
      .some((cookie) => cookie.trim() === "codex-e2e-auth-bypass=true")
  );
}

export function isAuthEnabled() {
  return (
    hasE2EAuthBypassCookie() ||
    (AUTH_FEATURE_ENABLED && Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY))
  );
}

export async function getApiToken(getToken: TokenGetter): Promise<string> {
  if (hasE2EAuthBypassCookie()) {
    return "codex-e2e-auth-bypass";
  }

  if (!isAuthEnabled()) {
    throw new Error("Authentication is not configured.");
  }

  const token = await getToken();
  if (!token) {
    throw new Error("Unauthorized");
  }

  return token;
}
