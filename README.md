ArgentNorth local development is designed to run one Next.js listener on `3000`
and one FastAPI listener on `8000`.

## Local Development

Start the full stack with deterministic port cleanup, timestamped logs, and a
DB-backed readiness check:

```bash
npm run dev:full
```

Useful commands:

```bash
npm run dev:backend          # stable backend, reload disabled
npm run dev:backend:reload   # backend reload only when intentionally needed
npm run dev:doctor           # ports, health, DB readiness, Clerk env, memory, logs
npm run dev                  # Next.js only
```

`dev:full` stops existing listeners on `3000` and `8000`, starts the backend
through the backend virtualenv Python, starts Next on `3000`, writes logs under
`run-logs/`, and waits for `http://127.0.0.1:8000/health/ready` before it
declares the stack ready.

## Auth In Development

Real Clerk auth is the default. For local tests or troubleshooting only, the
existing bypass path can be enabled by setting `CODEX_E2E_AUTH_BYPASS=true` for
both frontend and backend processes, then setting this localhost cookie:

```js
document.cookie = "codex-e2e-auth-bypass=true; path=/; SameSite=Lax"
```

The bypass is rejected outside `APP_ENV=development` and should not be used for
production auth or database behavior.

## Verification

```bash
npm run test:backend -- tests/test_health.py tests/test_security.py tests/test_main_lifecycle.py
npx tsc --noEmit
npm run lint
npm run build
```

Run `npm run dev:doctor` when the browser looks stale or auth bootstrap fails.
