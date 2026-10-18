import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../app.js", import.meta.url), "utf8").replace(/\r\n/g, "\n");
function actualFunction(name) {
  const start = source.search(new RegExp("^  (?:async )?function " + name + "\\(", "m"));
  assert.ok(start >= 0, "Actual app function exists: " + name);
  const next = source.slice(start + 1).search(/\n  (?:async )?function \w+\(/);
  assert.ok(next >= 0);
  return source.slice(start, start + next + 1).trim();
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const flush = async () => { for (let index = 0; index < 20; index += 1) await Promise.resolve(); };
const names = ["quality", "dates", "timing", "encounters", "locations"];
function fixture() {
  const pending = Object.fromEntries(names.map(name => [name, deferred()]));
  const calls = Object.fromEntries(names.map(name => [name, 0]));
  const scoped = { scope: "initial view" }, full = { scope: "full catalog" };
  const runtime = { progressiveTiming: scoped, traceChronologyEvidence: scoped,
    traceChronologyStatus: "ready", encounterStatus: "loading", progressiveHydrating: false,
    traceChronologyEvidencePromise: pending.timing.promise, encounterEvidencePromise: pending.encounters.promise };
  const startup = { progressiveEnabled: true };
  const context = vm.createContext({ runtime, startup, Promise, Error,
    measureStartupStep: (_label, callback) => callback(),
    loadDetailQualityOverlayRuntime: () => { calls.quality += 1; return pending.quality.promise.then(value => { runtime.detailQualityOverlay = value; }); },
    loadAnalysisRepairDetailOverlayRuntime: () => { calls.dates += 1; return pending.dates.promise.then(value => { runtime.analysisRepairDetailOverlay = value; }); },
    loadTraceChronologyEvidence: () => { calls.timing += 1; return pending.timing.promise.then(value => { runtime.traceChronologyEvidence = value; return value; }); },
    loadEncounterEvidence: () => { calls.encounters += 1; return pending.encounters.promise.then(value => { runtime.encounterStatus = value ? "ready" : "unavailable"; return value; }); },
    loadLocationLabelOverlayRuntime: () => { calls.locations += 1; return pending.locations.promise; },
  });
  for (const name of ["ensureDetailQualityOverlayLoaded", "ensureAnalysisRepairDetailOverlayLoaded", "loadStartupSupportEvidence"])
    vm.runInContext(actualFunction(name), context);
  function finish(overrides = {}) {
    for (const name of names) pending[name].resolve(Object.hasOwn(overrides, name) ? overrides[name] : name === "timing" ? full : { ready: name });
  }
  return { context, runtime, startup, pending, calls, scoped, full, finish };
}

const shared = fixture();
const earlyQuality = shared.context.ensureDetailQualityOverlayLoaded();
const earlyDates = shared.context.ensureAnalysisRepairDetailOverlayLoaded();
const barrier = shared.context.loadStartupSupportEvidence();
assert.equal(shared.context.loadStartupSupportEvidence(), barrier, "Map and full-catalog preparation share the same support barrier");
await flush();
assert.deepEqual(shared.calls, { quality: 1, dates: 1, timing: 1, encounters: 1, locations: 1 },
  "All five independent loaders overlap and corrections already in flight are reused");
let complete = false; barrier.then(() => { complete = true; });
for (const name of ["quality", "dates", "encounters", "locations"]) shared.pending[name].resolve({ ready: name });
await flush();
assert.equal(complete, false, "Hydration remains behind the complete annotation barrier");
shared.pending.timing.resolve(shared.full);
const result = await barrier; await earlyQuality; await earlyDates;
assert.equal(result.traceEvidence, shared.full, "The full timing index is retained for later hydration");
assert.equal(shared.runtime.traceChronologyEvidence, shared.scoped,
  "A prefetched full timing index cannot overwrite the visible scoped map's chronology");
assert.equal(shared.runtime.traceChronologyStatus, "ready");
await shared.context.ensureDetailQualityOverlayLoaded();
await shared.context.ensureAnalysisRepairDetailOverlayLoaded();
assert.equal((await shared.context.loadStartupSupportEvidence()).traceEvidence, shared.full);
assert.deepEqual(shared.calls, { quality: 1, dates: 1, timing: 1, encounters: 1, locations: 1 },
  "Ready correction indexes and the accepted support barrier are not downloaded or processed twice");

const hydrating = fixture();
hydrating.runtime.progressiveHydrating = true;
const hydrationBarrier = hydrating.context.loadStartupSupportEvidence(); hydrating.finish(); await hydrationBarrier;
assert.equal(hydrating.runtime.traceChronologyEvidence, hydrating.full,
  "Active full-catalog hydration keeps full timing rather than restoring the small profile index");

for (const [apiName, pendingName, promiseName] of [
  ["ensureDetailQualityOverlayLoaded", "quality", "detailQualityOverlayLoadPromise"],
  ["ensureAnalysisRepairDetailOverlayLoaded", "dates", "analysisRepairDetailOverlayLoadPromise"],
]) {
  const failed = fixture(), error = new Error("Pinned correction unavailable");
  const first = failed.context[apiName](); await flush();
  failed.pending[pendingName].reject(error);
  await assert.rejects(first, value => value === error);
  assert.equal(failed.runtime[promiseName], null, "A rejected correction promise remains retryable");
  failed.pending[pendingName] = deferred();
  const second = failed.context[apiName](); await flush();
  failed.pending[pendingName].resolve({ recovered: true }); await second;
  assert.equal(failed.calls[pendingName], 2);
}

const failedSupport = fixture();
const error = new Error("Correction integrity rejected");
const rejectedBarrier = failedSupport.context.loadStartupSupportEvidence();
failedSupport.pending.quality.reject(error); failedSupport.finish();
await assert.rejects(rejectedBarrier, value => value === error);
assert.equal(failedSupport.runtime.startupSupportEvidencePromise, null);
assert.equal(failedSupport.runtime.traceChronologyEvidence, failedSupport.scoped);
failedSupport.pending.quality = deferred();
const retry = failedSupport.context.loadStartupSupportEvidence();
failedSupport.pending.quality.resolve({ recovered: true }); await retry;
assert.equal(failedSupport.calls.quality, 2, "A rejected barrier does not pin a failed correction request forever");
assert.equal(failedSupport.calls.dates, 1, "A successful date repair index is retained across a peer failure");

for (const missing of ["timing", "encounters"]) {
  const incomplete = fixture();
  const pending = incomplete.context.loadStartupSupportEvidence(); incomplete.finish({ [missing]: null });
  await assert.rejects(pending, /Report evidence did not finish loading/);
  assert.equal(incomplete.runtime.startupSupportEvidencePromise, null);
  assert.equal(incomplete.runtime[missing === "timing" ? "traceChronologyEvidencePromise" : "encounterEvidencePromise"], null,
    "Unavailable " + missing + " evidence may be retried");
  assert.equal(incomplete.runtime.traceChronologyEvidence, incomplete.scoped);
}
const prefetch = fixture();
const packed = deferred(), shardRequests = Array.from({ length: 4 }, deferred), preparationCalls = [];
prefetch.runtime.canonicalWebArtifacts = { summaryManifest: Array.from({ length: 8 }, (_, index) => ({ id: index })) };
prefetch.context.STARTUP_CATALOG_SHARD_CONCURRENCY = 4;
prefetch.context.recordStartupMilestoneIfUnset = name => { preparationCalls.push(name); };
prefetch.context.loadPackedPointsRuntime = () => { preparationCalls.push("packed"); return packed.promise; };
prefetch.context.ensureCanonicalSummaryShardLoaded = index => { preparationCalls.push(index); return shardRequests[index].promise; };
vm.runInContext(actualFunction("prepareProgressiveCatalogInputs"), prefetch.context);
const prepared = prefetch.context.prepareProgressiveCatalogInputs();
assert.equal(prefetch.context.prepareProgressiveCatalogInputs(), prepared, "Repeated initial/full callers share the same parallel preparation");
await flush();
assert.deepEqual(prefetch.calls, { quality: 1, dates: 1, timing: 1, encounters: 1, locations: 1 });
assert.deepEqual(preparationCalls, ["time to background downloads started", "packed", 0, 1, 2, 3],
  "Packed points and the bounded first four summaries start before the evidence barrier resolves");
let preparationDone = false; prepared.then(() => { preparationDone = true; });
prefetch.finish(); await flush();
assert.equal(preparationDone, false, "Evidence completion does not skip pending packed or summary inputs");
assert.equal(prefetch.runtime.traceChronologyEvidence, prefetch.scoped);
packed.resolve({ ready: true });
for (const index of [0, 2, 1]) shardRequests[index].resolve([{ index }]);
await flush();
assert.equal(preparationDone, false);
shardRequests[3].resolve([{ index: 3 }]);
assert.equal((await prepared).traceEvidence, prefetch.full, "Prepared inputs retain full timing for the explicit hydration handoff");
assert.equal(prefetch.runtime.progressiveHydrating, false, "Parallel downloading cannot turn on partial-catalog hydration");
assert.equal(prefetch.runtime.traceChronologyEvidence, prefetch.scoped, "The initial map's timing remains authoritative through all prefetch completion orders");
await prefetch.context.prepareProgressiveCatalogInputs();
assert.equal(preparationCalls.filter(value => value === "packed").length, 1, "Accepted packed/source preparation is not repeated at map promotion");

const failedPreparation = fixture();
const badPacked = deferred(), recoveredPacked = deferred();
let packedCalls = 0;
failedPreparation.runtime.canonicalWebArtifacts = { summaryManifest: [] };
failedPreparation.context.STARTUP_CATALOG_SHARD_CONCURRENCY = 4;
failedPreparation.context.recordStartupMilestoneIfUnset = () => {};
failedPreparation.context.loadPackedPointsRuntime = () => (++packedCalls === 1 ? badPacked.promise : recoveredPacked.promise);
failedPreparation.context.ensureCanonicalSummaryShardLoaded = () => assert.fail("Empty source manifest has no prefetch requests");
vm.runInContext(actualFunction("prepareProgressiveCatalogInputs"), failedPreparation.context);
const failedPreparationPromise = failedPreparation.context.prepareProgressiveCatalogInputs();
const preparationError = new Error("Packed download failed");
badPacked.reject(preparationError);
await assert.rejects(failedPreparationPromise, value => value === preparationError);
assert.equal(failedPreparation.runtime.progressiveCatalogInputsPromise, null, "Failed speculative preparation remains retryable without failing the initial map");
const recoveredPreparation = failedPreparation.context.prepareProgressiveCatalogInputs();
failedPreparation.finish(); recoveredPacked.resolve({ ready: true });
await recoveredPreparation;
assert.equal(packedCalls, 2);
assert.equal(failedPreparation.calls.quality, 1, "A retry reuses its still-running evidence barrier instead of duplicating downloads");
console.log("Actual startup support loaders share pending and accepted correction indexes, overlap all independent requests, preserve scoped timing, keep full timing for hydration, and recover failed barriers.");
