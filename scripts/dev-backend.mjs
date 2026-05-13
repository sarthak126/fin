#!/usr/bin/env node
import path from "node:path";
import {
  DEFAULT_BACKEND_PORT,
  formatPortOwner,
  getBackendRoot,
  getRepoRoot,
  selectPython,
  startLoggedProcess,
  stopPortOwners,
  terminateLoggedProcess,
  timestampForLog,
  waitForPortsFree,
} from "./dev-stack-utils.mjs";

const repoRoot = getRepoRoot(import.meta.url);
const backendRoot = getBackendRoot(repoRoot);
const reload = process.argv.includes("--reload");
const port = Number(process.env.BACKEND_PORT || DEFAULT_BACKEND_PORT);
const host = process.env.BACKEND_HOST || "127.0.0.1";
const logDir = path.join(repoRoot, "run-logs");
const timestamp = timestampForLog();
const python = selectPython(repoRoot, backendRoot);

console.log(`LoanLens backend dev server`);
console.log(`- Python: ${python.command} ${python.args.join(" ")}`.trim());
console.log(`- URL: http://${host}:${port}`);
console.log(`- Reload: ${reload ? "enabled" : "disabled"}`);

if (process.env.LOANLENS_SKIP_PORT_CLEANUP !== "true") {
  const result = stopPortOwners([port], repoRoot);
  for (const owner of result.killed) {
    console.log(`- Stopped existing listener ${formatPortOwner(owner)}`);
  }
  for (const failure of result.errors) {
    console.warn(`- Could not stop ${formatPortOwner(failure.owner)}: ${failure.error}`);
  }
  try {
    await waitForPortsFree([port], repoRoot);
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
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
      BACKEND_HOST: host,
      BACKEND_PORT: String(port),
      BACKEND_RELOAD: reload ? "true" : "false",
      PYTHONUNBUFFERED: "1",
    },
    logDir,
    timestamp,
  },
);

console.log(`- Logs: ${backend.outPath} / ${backend.errPath}`);

let shuttingDown = false;
function shutdown() {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;
  terminateLoggedProcess(backend);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
process.on("exit", shutdown);

backend.child.on("exit", (code, signal) => {
  if (!shuttingDown) {
    console.log(`Backend exited with ${signal || code}`);
    process.exit(code ?? 1);
  }
});
