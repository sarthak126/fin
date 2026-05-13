#!/usr/bin/env node
import path from "node:path";
import {
  DEFAULT_BACKEND_PORT,
  DEFAULT_FRONTEND_PORT,
  formatPortOwner,
  getBackendRoot,
  getRepoRoot,
  selectPython,
  startLoggedProcess,
  stopPortOwners,
  terminateLoggedProcess,
  timestampForLog,
  waitForPortsFree,
  waitForHttpJson,
} from "./dev-stack-utils.mjs";

const repoRoot = getRepoRoot(import.meta.url);
const backendRoot = getBackendRoot(repoRoot);
const backendPort = Number(process.env.BACKEND_PORT || DEFAULT_BACKEND_PORT);
const frontendPort = Number(process.env.PORT || DEFAULT_FRONTEND_PORT);
const backendHost = process.env.BACKEND_HOST || "127.0.0.1";
const logDir = path.join(repoRoot, "run-logs");
const timestamp = timestampForLog();
const python = selectPython(repoRoot, backendRoot);
const frontendCommand = process.platform === "win32" ? (process.env.ComSpec || "cmd.exe") : "npm";
const frontendArgs = process.platform === "win32"
  ? ["/d", "/s", "/c", `npm run dev -- --port ${frontendPort}`]
  : ["run", "dev", "--", "--port", String(frontendPort)];
let shuttingDown = false;
const handles = [];

function shutdown(exitCode = 0) {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;
  for (const handle of handles) {
    terminateLoggedProcess(handle);
  }
  process.exitCode = exitCode;
}

function watchExit(label, handle) {
  handle.child.on("exit", (code, signal) => {
    if (shuttingDown) {
      return;
    }
    console.error(`${label} exited before the dev stack was stopped (${signal || code}).`);
    shutdown(code ?? 1);
  });
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));
process.on("exit", () => shutdown(process.exitCode ?? 0));

console.log("Starting ArgentNorth local dev stack");
console.log(`- Backend Python: ${python.command} ${python.args.join(" ")}`.trim());
console.log(`- Stopping existing listeners on :${frontendPort} and :${backendPort}`);
const stopped = stopPortOwners([frontendPort, backendPort], repoRoot);
if (stopped.owners.length === 0) {
  console.log("- No existing listeners found");
}
for (const owner of stopped.killed) {
  console.log(`- Stopped ${formatPortOwner(owner)}`);
}
for (const failure of stopped.errors) {
  console.warn(`- Could not stop ${formatPortOwner(failure.owner)}: ${failure.error}`);
}
try {
  await waitForPortsFree([frontendPort, backendPort], repoRoot);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}

const backend = startLoggedProcess(
  "backend",
  python.command,
  [...python.args, "dev_server.py"],
  {
    cwd: backendRoot,
    env: {
      ...process.env,
      APP_ENV: process.env.APP_ENV || "development",
      BACKEND_HOST: backendHost,
      BACKEND_PORT: String(backendPort),
      BACKEND_RELOAD: "false",
      PYTHONUNBUFFERED: "1",
    },
    logDir,
    timestamp,
  },
);
handles.push(backend);
watchExit("Backend", backend);

const frontend = startLoggedProcess(
  "frontend",
  frontendCommand,
  frontendArgs,
  {
    cwd: repoRoot,
    env: {
      ...process.env,
      PORT: String(frontendPort),
      NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || `http://${backendHost}:${backendPort}/api/v1`,
    },
    logDir,
    timestamp,
  },
);
handles.push(frontend);
watchExit("Frontend", frontend);

console.log(`- Backend logs: ${backend.outPath} / ${backend.errPath}`);
console.log(`- Frontend logs: ${frontend.outPath} / ${frontend.errPath}`);
console.log("- Waiting for backend DB readiness at /health/ready");

try {
  const ready = await waitForHttpJson(`http://${backendHost}:${backendPort}/health/ready`, {
    timeoutMs: 120_000,
    intervalMs: 1_000,
    requestTimeoutMs: 5_000,
  });
  console.log(`- Backend ready: ${JSON.stringify(ready.body)}`);

  await waitForHttpJson(`http://127.0.0.1:${frontendPort}`, {
    timeoutMs: 120_000,
    intervalMs: 1_000,
    requestTimeoutMs: 5_000,
  });

  console.log("");
  console.log("ArgentNorth dev stack is ready");
  console.log(`- Frontend: http://localhost:${frontendPort}`);
  console.log(`- Backend: http://${backendHost}:${backendPort}`);
  console.log(`- Backend readiness: http://${backendHost}:${backendPort}/health/ready`);
  await new Promise(() => {});
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  console.error("Dev stack did not become ready. Check the timestamped logs above.");
  shutdown(1);
}
