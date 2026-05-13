import assert from "node:assert/strict";
import test from "node:test";
import {
  parseEnvFile,
  parseWindowsNetstat,
  pythonCandidates,
  summarizeReadyResult,
} from "./dev-stack-utils.mjs";

test("parseWindowsNetstat returns listening owners for requested ports", () => {
  const output = `
  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:3000           0.0.0.0:0              LISTENING       111
  TCP    [::]:8000              [::]:0                 LISTENING       222
  TCP    127.0.0.1:9000         0.0.0.0:0              LISTENING       333
  `;

  assert.deepEqual(parseWindowsNetstat(output, [3000, 8000]), [
    { port: 3000, pid: 111, protocol: "tcp" },
    { port: 8000, pid: 222, protocol: "tcp" },
  ]);
});

test("summarizeReadyResult makes DB readiness clear", () => {
  assert.equal(summarizeReadyResult({ ok: true, status: 200, body: { status: "ready" } }), "ready");
  assert.equal(
    summarizeReadyResult({ ok: false, status: 503, body: { detail: "Database not connected" } }),
    "not ready: Database not connected",
  );
});

test("parseEnvFile reports only populated keys", () => {
  const parsed = parseEnvFile(`
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_123
    CLERK_SECRET_KEY=""
    # COMMENTED=value
  `);

  assert.equal(parsed.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"), "pk_test_123");
  assert.equal(parsed.get("CLERK_SECRET_KEY"), "");
  assert.equal(parsed.has("COMMENTED"), false);
});

test("pythonCandidates prefers the backend virtualenv for backend startup", () => {
  const labels = pythonCandidates("C:\\repo", "C:\\repo\\backend").map((candidate) => candidate.label);

  assert.ok(labels.indexOf("backend venv") < labels.indexOf("repo .venv"));
});
