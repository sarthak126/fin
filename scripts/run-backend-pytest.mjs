import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const backendRoot = path.join(repoRoot, "backend");

const candidates = [];

if (process.env.BACKEND_PYTHON) {
  candidates.push({ command: process.env.BACKEND_PYTHON, args: [] });
}

const windowsVenvPython = path.join(backendRoot, "venv", "Scripts", "python.exe");
if (existsSync(windowsVenvPython)) {
  candidates.push({ command: windowsVenvPython, args: [] });
}

const posixVenvPython = path.join(backendRoot, "venv", "bin", "python");
if (existsSync(posixVenvPython)) {
  candidates.push({ command: posixVenvPython, args: [] });
}

candidates.push({ command: "python", args: [] });

if (process.platform === "win32") {
  candidates.push({ command: "py", args: ["-3"] });
}

const pytestArgs = ["-m", "pytest", "-q", ...process.argv.slice(2)];

for (const candidate of candidates) {
  const result = spawnSync(candidate.command, [...candidate.args, ...pytestArgs], {
    cwd: backendRoot,
    stdio: "inherit",
  });

  if (result.error && result.error.code === "ENOENT") {
    continue;
  }

  process.exit(result.status ?? 1);
}

console.error(
  "Unable to find a Python interpreter for backend tests. Set BACKEND_PYTHON or create backend/venv."
);
process.exit(1);
