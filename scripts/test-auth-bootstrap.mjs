import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import ts from "typescript";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const sourcePath = path.join(repoRoot, "src", "lib", "auth-bootstrap.ts");
const source = fs.readFileSync(sourcePath, "utf8");
const transpiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  },
});

const compiledModule = { exports: {} };
vm.runInNewContext(transpiled.outputText, {
  module: compiledModule,
  exports: compiledModule.exports,
  setTimeout,
  clearTimeout,
});

const {
  describeAuthBootstrapFailure,
  getAuthBootstrapErrorKind,
  runAuthBootstrapWithRetry,
} = compiledModule.exports;

{
  let attempts = 0;
  const delays = [];
  const result = await runAuthBootstrapWithRetry(
    async () => {
      attempts += 1;
      if (attempts < 3) {
        throw new Error("temporary backend failure");
      }
      return "ready";
    },
    {
      retryDelaysMs: [1, 2],
      sleep: async (delayMs) => {
        delays.push(delayMs);
      },
    },
  );

  assert.equal(result, "ready");
  assert.equal(attempts, 3);
  assert.deepEqual(delays, [1, 2]);
}

{
  let attempts = 0;
  await assert.rejects(
    () => runAuthBootstrapWithRetry(
      async () => {
        attempts += 1;
        throw Object.assign(new Error("database connection is unavailable"), { status: 503 });
      },
      {
        retryDelaysMs: [1, 2],
        sleep: async () => {},
      },
    ),
    /database connection is unavailable/,
  );
  assert.equal(attempts, 3);
}

assert.equal(
  getAuthBootstrapErrorKind(Object.assign(new Error("Token expired"), { status: 401 })),
  "expired_session",
);
assert.equal(getAuthBootstrapErrorKind(new Error("JWT is not yet valid")), "clock_skew");
assert.equal(getAuthBootstrapErrorKind(new Error("Database not connected")), "db_unavailable");
assert.equal(getAuthBootstrapErrorKind(new Error("Unable to fetch Clerk JWKS")), "auth_config");

assert.match(describeAuthBootstrapFailure(new Error("Database not connected")).message, /health\/ready/);
assert.match(describeAuthBootstrapFailure(new Error("Token expired")).message, /Refresh the session/);

console.log("AuthBootstrap retry and error-copy tests passed");
