#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import {
  DEFAULT_BACKEND_PORT,
  DEFAULT_FRONTEND_PORT,
  collectEnvPresence,
  fetchJson,
  formatPortOwner,
  freeMemorySummary,
  getBackendRoot,
  getPortOwners,
  getRepoRoot,
  summarizeReadyResult,
} from "./dev-stack-utils.mjs";

const repoRoot = getRepoRoot(import.meta.url);
const backendRoot = getBackendRoot(repoRoot);
const backendPort = Number(process.env.BACKEND_PORT || DEFAULT_BACKEND_PORT);
const frontendPort = Number(process.env.PORT || DEFAULT_FRONTEND_PORT);
const backendBase = `http://127.0.0.1:${backendPort}`;

function section(title) {
  console.log("");
  console.log(title);
}

async function safeFetch(url, timeoutMs = 10_000) {
  try {
    return await fetchJson(url, timeoutMs);
  } catch (error) {
    return {
      ok: false,
      status: 0,
      body: error instanceof Error ? error.message : String(error),
      text: "",
    };
  }
}

function collectLogFiles() {
  const dirs = [
    repoRoot,
    backendRoot,
    path.join(repoRoot, "run-logs"),
  ];
  const files = [];

  for (const dir of dirs) {
    if (!fs.existsSync(dir)) {
      continue;
    }
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (!entry.isFile() || !entry.name.endsWith(".log")) {
        continue;
      }
      const filePath = path.join(dir, entry.name);
      const stat = fs.statSync(filePath);
      files.push({ filePath, mtimeMs: stat.mtimeMs, size: stat.size });
    }
  }

  return files.sort((a, b) => b.mtimeMs - a.mtimeMs);
}

function readTail(filePath, size) {
  const bytes = Math.min(size, 80 * 1024);
  const buffer = Buffer.alloc(bytes);
  const fd = fs.openSync(filePath, "r");
  try {
    fs.readSync(fd, buffer, 0, bytes, Math.max(0, size - bytes));
  } finally {
    fs.closeSync(fd);
  }
  return buffer.toString("utf8");
}

function newestLogErrors() {
  const errorPattern = /(\bERROR\b|Traceback|Exception|\bfailed\b|EADDRINUSE|database connection failed|invalid token|unable to fetch clerk)/i;
  const results = [];

  for (const log of collectLogFiles().slice(0, 10)) {
    const text = readTail(log.filePath, log.size);
    const lines = text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => errorPattern.test(line))
      .slice(-4);

    if (lines.length > 0) {
      results.push({
        filePath: log.filePath,
        lines,
      });
    }

    if (results.length >= 4) {
      break;
    }
  }

  return results;
}

console.log("ArgentNorth dev doctor");

section("Port Owners");
const owners = getPortOwners([frontendPort, backendPort], repoRoot);
if (owners.length === 0) {
  console.log(`No listeners found on :${frontendPort} or :${backendPort}`);
} else {
  for (const owner of owners) {
    console.log(formatPortOwner(owner));
  }
}

section("Backend Health");
const health = await safeFetch(`${backendBase}/health`);
if (health.status === 0) {
  console.log(`health: unreachable (${health.body})`);
} else {
  console.log(`health: HTTP ${health.status} ${JSON.stringify(health.body)}`);
}

const ready = await safeFetch(`${backendBase}/health/ready`);
console.log(`readiness: ${summarizeReadyResult(ready)}`);

section("Clerk Env");
for (const item of collectEnvPresence(
  ["NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "CLERK_SECRET_KEY", "CODEX_E2E_AUTH_BYPASS"],
  repoRoot,
)) {
  const suffix = item.sources.length > 0 ? ` (${item.sources.join(", ")})` : "";
  console.log(`${item.key}: ${item.present ? "present" : "missing"}${suffix}`);
}

section("Memory");
console.log(freeMemorySummary());

section("Newest Log Errors");
const errors = newestLogErrors();
if (errors.length === 0) {
  console.log("No recent error lines found in top-level or run-logs/*.log files.");
} else {
  for (const entry of errors) {
    console.log(path.relative(repoRoot, entry.filePath));
    for (const line of entry.lines) {
      console.log(`  ${line}`);
    }
  }
}
