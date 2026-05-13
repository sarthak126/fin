import { execFileSync, spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const DEFAULT_BACKEND_PORT = 8000;
export const DEFAULT_FRONTEND_PORT = 3000;

export function getRepoRoot(metaUrl = import.meta.url) {
  return path.resolve(path.dirname(fileURLToPath(metaUrl)), "..");
}

export function getBackendRoot(repoRoot = getRepoRoot()) {
  return path.join(repoRoot, "backend");
}

export function timestampForLog(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, "-");
}

export function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function pythonCandidates(repoRoot = getRepoRoot(), backendRoot = getBackendRoot(repoRoot)) {
  const candidates = [];

  if (process.env.BACKEND_PYTHON) {
    candidates.push({ command: process.env.BACKEND_PYTHON, args: [], label: "BACKEND_PYTHON" });
  }

  if (process.platform === "win32") {
    candidates.push(
      { command: path.join(backendRoot, "venv", "Scripts", "python.exe"), args: [], label: "backend venv" },
      { command: path.join(repoRoot, ".venv", "Scripts", "python.exe"), args: [], label: "repo .venv" },
      { command: path.join(backendRoot, ".venv", "Scripts", "python.exe"), args: [], label: "backend .venv" },
      { command: "python", args: [], label: "python" },
      { command: "py", args: ["-3"], label: "py -3" },
    );
  } else {
    candidates.push(
      { command: path.join(backendRoot, "venv", "bin", "python"), args: [], label: "backend venv" },
      { command: path.join(repoRoot, ".venv", "bin", "python"), args: [], label: "repo .venv" },
      { command: path.join(backendRoot, ".venv", "bin", "python"), args: [], label: "backend .venv" },
      { command: "python3", args: [], label: "python3" },
      { command: "python", args: [], label: "python" },
    );
  }

  return candidates;
}

export function selectPython(repoRoot = getRepoRoot(), backendRoot = getBackendRoot(repoRoot)) {
  for (const candidate of pythonCandidates(repoRoot, backendRoot)) {
    if (path.isAbsolute(candidate.command) && !fs.existsSync(candidate.command)) {
      continue;
    }
    return candidate;
  }

  throw new Error("Unable to find a Python interpreter. Set BACKEND_PYTHON or create .venv.");
}

export function npmCommand() {
  return process.platform === "win32" ? "npm.cmd" : "npm";
}

export function parseWindowsNetstat(output, ports) {
  const targetPorts = new Set(ports.map((port) => Number(port)));
  const owners = [];

  for (const line of output.split(/\r?\n/)) {
    const parts = line.trim().split(/\s+/);
    if (parts.length < 5 || parts[0].toUpperCase() !== "TCP") {
      continue;
    }

    const stateIndex = parts.findIndex((part) => part.toUpperCase() === "LISTENING");
    if (stateIndex === -1) {
      continue;
    }

    const portMatch = parts[1].match(/:(\d+)$/);
    const port = portMatch ? Number(portMatch[1]) : NaN;
    const pid = Number(parts[stateIndex + 1]);

    if (!targetPorts.has(port) || !Number.isInteger(pid)) {
      continue;
    }

    owners.push({ port, pid, protocol: "tcp" });
  }

  return owners;
}

function parseLsof(output, ports) {
  const targetPorts = new Set(ports.map((port) => Number(port)));
  const owners = [];

  for (const line of output.split(/\r?\n/).slice(1)) {
    const parts = line.trim().split(/\s+/);
    if (parts.length < 2) {
      continue;
    }

    const portMatch = line.match(/:(\d+)\s+\(LISTEN\)/);
    const port = portMatch ? Number(portMatch[1]) : NaN;
    const pid = Number(parts[1]);

    if (!targetPorts.has(port) || !Number.isInteger(pid)) {
      continue;
    }

    owners.push({ port, pid, name: parts[0], protocol: "tcp" });
  }

  return owners;
}

function shortenCommandLine(commandLine, repoRoot) {
  if (!commandLine) {
    return "";
  }

  return commandLine.replaceAll(repoRoot, ".").replace(/\s+/g, " ").trim().slice(0, 180);
}

function enrichWindowsOwners(owners, repoRoot) {
  if (owners.length === 0) {
    return owners;
  }

  const pids = [...new Set(owners.map((owner) => owner.pid))];
  const psScript = [
    `$ids = @(${pids.join(",")});`,
    "Get-CimInstance Win32_Process |",
      "Where-Object { $ids -contains $_.ProcessId } |",
      "Select-Object ProcessId,Name,CommandLine |",
      "ConvertTo-Json -Compress",
  ].join(" ");

  const result = spawnSync("powershell.exe", ["-NoProfile", "-Command", psScript], {
    encoding: "utf8",
    windowsHide: true,
  });

  if (result.status !== 0 || !result.stdout.trim()) {
    return owners;
  }

  try {
    const parsed = JSON.parse(result.stdout);
    const rows = Array.isArray(parsed) ? parsed : [parsed];
    const byPid = new Map(rows.map((row) => [Number(row.ProcessId), row]));
    return owners.map((owner) => {
      const row = byPid.get(owner.pid);
      return {
        ...owner,
        name: row?.Name || owner.name || "",
        command: shortenCommandLine(row?.CommandLine || "", repoRoot),
      };
    });
  } catch {
    return owners;
  }
}

function enrichPosixOwners(owners) {
  return owners.map((owner) => {
    if (owner.name) {
      return owner;
    }

    const result = spawnSync("ps", ["-p", String(owner.pid), "-o", "comm="], {
      encoding: "utf8",
    });

    return {
      ...owner,
      name: result.status === 0 ? result.stdout.trim() : "",
    };
  });
}

export function getPortOwners(ports, repoRoot = getRepoRoot()) {
  const normalizedPorts = ports.map((port) => Number(port));

  if (process.platform === "win32") {
    const output = execFileSync("netstat", ["-ano", "-p", "tcp"], {
      encoding: "utf8",
      windowsHide: true,
    });
    return enrichWindowsOwners(parseWindowsNetstat(output, normalizedPorts), repoRoot);
  }

  const owners = [];
  for (const port of normalizedPorts) {
    const result = spawnSync("lsof", ["-nP", `-iTCP:${port}`, "-sTCP:LISTEN"], {
      encoding: "utf8",
    });
    if (result.status === 0 && result.stdout.trim()) {
      owners.push(...parseLsof(result.stdout, [port]));
    }
  }

  return enrichPosixOwners(owners);
}

export function formatPortOwner(owner) {
  const name = owner.name ? ` ${owner.name}` : "";
  const command = owner.command ? ` ${owner.command}` : "";
  return `:${owner.port} pid=${owner.pid}${name}${command}`;
}

function killPidTree(pid) {
  if (pid === process.pid) {
    return { ok: false, error: "refusing to stop the current process" };
  }

  const result = process.platform === "win32"
    ? spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], { encoding: "utf8", windowsHide: true })
    : spawnSync("kill", ["-TERM", String(pid)], { encoding: "utf8" });

  return {
    ok: result.status === 0,
    error: result.status === 0 ? "" : (result.stderr || result.stdout || "unknown error").trim(),
  };
}

export function stopPortOwners(ports, repoRoot = getRepoRoot()) {
  const owners = getPortOwners(ports, repoRoot);
  const killed = [];
  const errors = [];

  for (const owner of owners) {
    if (killed.some((item) => item.pid === owner.pid)) {
      continue;
    }

    const result = killPidTree(owner.pid);
    if (result.ok) {
      killed.push(owner);
    } else {
      errors.push({ owner, error: result.error });
    }
  }

  return { owners, killed, errors };
}

export async function waitForPortsFree(ports, repoRoot = getRepoRoot(), timeoutMs = 10_000) {
  const deadline = Date.now() + timeoutMs;
  let owners = [];

  while (Date.now() < deadline) {
    owners = getPortOwners(ports, repoRoot);
    if (owners.length === 0) {
      return;
    }
    await sleep(250);
  }

  throw new Error(`Ports still have listeners: ${owners.map(formatPortOwner).join(", ")}`);
}

function prefixChunk(label, chunk) {
  const text = chunk.toString();
  return text.replace(/^/gm, `[${label}] `);
}

export function startLoggedProcess(label, command, args, options) {
  ensureDir(options.logDir);
  const outPath = path.join(options.logDir, `${label}-${options.timestamp}.out.log`);
  const errPath = path.join(options.logDir, `${label}-${options.timestamp}.err.log`);
  const stdout = fs.createWriteStream(outPath, { flags: "a" });
  const stderr = fs.createWriteStream(errPath, { flags: "a" });

  const child = spawn(command, args, {
    cwd: options.cwd,
    env: options.env,
    windowsHide: true,
  });

  child.stdout?.on("data", (chunk) => {
    stdout.write(chunk);
    process.stdout.write(prefixChunk(label, chunk));
  });
  child.stderr?.on("data", (chunk) => {
    stderr.write(chunk);
    process.stderr.write(prefixChunk(label, chunk));
  });
  child.on("close", () => {
    stdout.end();
    stderr.end();
  });

  return { child, outPath, errPath };
}

export function terminateLoggedProcess(processHandle) {
  const child = processHandle?.child;
  if (!child?.pid || child.exitCode !== null) {
    return;
  }
  killPidTree(child.pid);
}

export async function fetchJson(url, timeoutMs = 5000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, { signal: controller.signal });
    const text = await response.text();
    let body = null;
    if (text.trim()) {
      try {
        body = JSON.parse(text);
      } catch {
        body = text;
      }
    }
    return { ok: response.ok, status: response.status, body, text };
  } finally {
    clearTimeout(timeout);
  }
}

export async function waitForHttpJson(url, options = {}) {
  const timeoutMs = options.timeoutMs ?? 90_000;
  const intervalMs = options.intervalMs ?? 1_000;
  const requestTimeoutMs = options.requestTimeoutMs ?? 5_000;
  const deadline = Date.now() + timeoutMs;
  let lastResult = null;
  let lastError = null;

  while (Date.now() < deadline) {
    try {
      const result = await fetchJson(url, requestTimeoutMs);
      lastResult = result;
      if (result.ok) {
        return result;
      }
    } catch (error) {
      lastError = error;
    }
    await sleep(intervalMs);
  }

  const reason = lastResult
    ? `last status ${lastResult.status}: ${typeof lastResult.body === "string" ? lastResult.body : JSON.stringify(lastResult.body)}`
    : lastError instanceof Error
      ? lastError.message
      : "no response";
  throw new Error(`Timed out waiting for ${url} (${reason})`);
}

export function parseEnvFile(text) {
  const values = new Map();
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) {
      continue;
    }

    const separator = line.indexOf("=");
    if (separator === -1) {
      continue;
    }

    const key = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim().replace(/^["']|["']$/g, "");
    values.set(key, value);
  }
  return values;
}

export function collectEnvPresence(keys, repoRoot = getRepoRoot()) {
  const files = [
    { label: "shell", values: new Map(Object.entries(process.env)) },
    { label: ".env.local", path: path.join(repoRoot, ".env.local") },
    { label: ".env", path: path.join(repoRoot, ".env") },
    { label: "backend/.env", path: path.join(repoRoot, "backend", ".env") },
  ].map((source) => {
    if (source.values) {
      return source;
    }
    if (!fs.existsSync(source.path)) {
      return { ...source, values: new Map() };
    }
    return { ...source, values: parseEnvFile(fs.readFileSync(source.path, "utf8")) };
  });

  return keys.map((key) => {
    const sources = files
      .filter((source) => {
        const value = source.values.get(key);
        return typeof value === "string" && value.trim() !== "";
      })
      .map((source) => source.label);
    return { key, present: sources.length > 0, sources };
  });
}

export function summarizeReadyResult(result) {
  if (!result) {
    return "not reachable";
  }
  if (result.ok && result.body?.status === "ready") {
    return "ready";
  }
  if (result.status === 503 && result.body?.detail) {
    return `not ready: ${result.body.detail}`;
  }
  return `not ready: HTTP ${result.status}`;
}

export function formatBytes(bytes) {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

export function freeMemorySummary() {
  return `${formatBytes(os.freemem())} free of ${formatBytes(os.totalmem())}`;
}
