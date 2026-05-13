import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const isWindows = process.platform === "win32";

function runScript(scriptName) {
  const command = isWindows ? "cmd.exe" : "npm";
  const args = isWindows
    ? ["/d", "/s", "/c", `npm run ${scriptName}`]
    : ["run", scriptName];

  const result = spawnSync(command, args, { cwd: repoRoot, stdio: "inherit" });

  if (result.error) {
    console.error(`Failed to execute npm run ${scriptName}: ${result.error.message}`);
    process.exit(1);
  }

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

runScript("test:backend");
runScript("test:devtools");
runScript("test:auth-bootstrap");
runScript("test:frontend");
