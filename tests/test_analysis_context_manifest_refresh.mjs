import assert from "node:assert/strict";
import { createRequire } from "node:module";
import crypto from "node:crypto";
import fs from "node:fs";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const Stats = require("../analysis_stats.js");
const app = fs.readFileSync("app.js", "utf8");
const extract = (first, next) => {
  const start = app.indexOf("  function " + first + "(");
  const end = app.indexOf("  function " + next + "(", start + 1);
  assert.ok(start >= 0 && end > start);
  return app.slice(start, end);
};
const helpers = extract("staticAssetVersionToken", "startupDiagnosticsRequested");
const loader = extract("ensureAnalysisContextProjections", "analysisV2ArtifactHashes");
const oldRows = [["animal", 1978, 1978, 0, [0], false, 0, null, null]];
const newRows = [oldRows[0].concat("CA")];
const checksum = value => crypto.createHash("sha256").update(JSON.stringify(value)).digest("hex");
const oldManifest = { artifacts: { animalReports: { file: "old-nine-field.json", sha256: checksum(oldRows) } } };
const newManifest = { artifacts: { animalReports: { file: "animal_reports_temporal.json", sha256: checksum(newRows) } } };

function harness({ failFetchOnce = false, failWorkerOnce = false } = {}) {
  const calls = [], handoffs = [], scheduled = [], warnings = [];
  const runtime = { appConfig: { staticAssetVersion: "older-config-token" }, analysisContextWorkerReady: false,
    analysisContextPromise: null, analysisCache: new Map([["stale-analysis", "stale"]]) };
  const context = { runtime, APP_SHELL_RELEASE_TOKEN: "2026-10-20-animal-time-v2", URL,
    document: { baseURI: "https://ufo-timeline.pages.dev/" }, console: { warn: value => warnings.push(value) },
    fetch: async (url, options) => {
      calls.push({ url, options });
      if (failFetchOnce) { failFetchOnce = false; return { ok: false, status: 503 }; }
      // Model an established production origin with the prior nine-field
      // manifest still present in HTTP cache. A fresh preview lacks that state.
      const fresh = options.cache === "no-cache" && new URL(url).searchParams.get("v") === "2026-10-20-animal-time-v2";
      return { ok: true, json: async () => fresh ? newManifest : oldManifest };
    },
    setAnalysisContextProjectionsInWorker: async (manifest, manifestUrl) => {
      handoffs.push({ manifest, manifestUrl });
      if (failWorkerOnce) { failWorkerOnce = false; throw new Error("Worker setup failed"); }
      const source = manifest.artifacts.animalReports.file === "animal_reports_temporal.json" ? newRows : oldRows;
      // Actual worker normalization must receive the optional country field.
      runtime.normalized = Stats.normalizeContextProjections({ manifest, animalReports: source }).animalReports;
      runtime.analysisContextWorkerReady = true;
      return { rowCounts: { animalReports: source.length } };
    },
    scheduleAnalysisCompute: (reason, options) => scheduled.push({ reason, options }),
  };
  vm.createContext(context);
  vm.runInContext(helpers + loader, context);
  return { context, runtime, calls, handoffs, scheduled, warnings };
}

const established = harness();
const { context, runtime, calls, handoffs, scheduled } = established;
const first = context.ensureAnalysisContextProjections();
const simultaneous = context.ensureAnalysisContextProjections();
assert.equal(first, simultaneous, "Concurrent callers share one in-flight request");
assert.equal(await first, newManifest);
assert.equal(calls.length, 1);
assert.equal(calls[0].options.cache, "no-cache", "Mutable manifests are revalidated even when the browser has an older response");
assert.equal(new URL(calls[0].url).pathname, "/data/analysis_v1/manifest.json");
assert.equal(new URL(calls[0].url).searchParams.get("v"), "2026-10-20-animal-time-v2", "The current app shell wins over a stale config token");
assert.equal(handoffs[0].manifest.artifacts.animalReports.sha256, checksum(newRows));
assert.equal(handoffs[0].manifestUrl, calls[0].url);
assert.equal(runtime.normalized[0].country, "CA", "A returning production visitor sees the ten-field country extension");
assert.equal(runtime.analysisCache.size, 0);
assert.equal(scheduled.length, 1);
assert.equal(scheduled[0].reason, "context projections ready");
assert.equal(await context.ensureAnalysisContextProjections(), newManifest);
assert.equal(calls.length, 1, "A ready worker keeps the existing same-page reuse behavior");

// Existing queries, absolute URLs and unrelated domain policies remain intact.
assert.equal(new URL(context.resolveAssetPath("./data/analysis_v1/manifest.json?v=pinned")).searchParams.get("v"), "pinned");
assert.equal(context.resolveAssetPath("https://ufo-timeline.pages.dev/data/analysis_v1/manifest.json"), calls[0].url);
assert.equal(context.shouldVersionStaticAsset(new URL("https://ufo-timeline.pages.dev/data/analysis_v2/manifest.json")), true);
assert.equal(context.shouldVersionStaticAsset(new URL("https://ufo-timeline.pages.dev/data/unrelated/manifest.json")), false);

for (const failure of ["fetch", "worker"]) {
  const retry = harness({ failFetchOnce: failure === "fetch", failWorkerOnce: failure === "worker" });
  assert.equal(await retry.context.ensureAnalysisContextProjections(), null);
  assert.equal(retry.runtime.analysisContextPromise, null, "A failed setup remains retryable");
  assert.equal(retry.runtime.analysisContextWorkerReady, false);
  assert.equal(retry.runtime.analysisCache.size, 1, "Failure does not erase a prior computed result");
  assert.equal(retry.scheduled.length, 0);
  assert.equal(retry.warnings.length, 1);
  assert.match(retry.runtime.analysisLastError, failure === "fetch" ? /503/ : /Worker setup failed/);
  assert.equal(await retry.context.ensureAnalysisContextProjections(), newManifest);
  assert.equal(retry.calls.length, 2);
  assert.equal(retry.runtime.normalized[0].country, "CA");
  assert.equal(retry.scheduled.length, 1);
}

console.log("Returning-user context manifests: shell versioning, HTTP revalidation, fresh country/hash normalization, in-flight reuse, existing query preservation and retry behavior passed.");
