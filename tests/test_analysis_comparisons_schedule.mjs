// Exercise production comparison scheduling and response guards with small
// synchronous fixtures. No catalog copies or astronomical rebuilds are needed.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const appSource = fs.readFileSync("app.js", "utf8");
const viewSource = fs.readFileSync("analysis_view.js", "utf8");
function extract(source, name) {
  const start = source.indexOf("  function " + name + "(");
  const end = source.indexOf("\n  function ", start + 3);
  assert.ok(start >= 0 && end > start, "Missing production helper: " + name);
  return source.slice(start, end);
}
function fixture() {
  const timers = new Map(), listeners = new Set(), posted = [], rendered = [], fullComputes = [], artifactLoads = [];
  let nextTimer = 0;
  const worker = {
    addEventListener(_name, listener) { listeners.add(listener); },
    removeEventListener(_name, listener) { listeners.delete(listener); },
    postMessage(message) { posted.push(message); },
  };
  const state = { activeView: "analysis", filterGeneration: 1 };
  const core = { summary: { activeCount: 1 }, baseline: { mode: "full_catalog" }, overview: { retained: "core" },
    comparisonEvidence: { status: "ready", lunar: { retained: "lunar" }, nuclear: { retained: "nuclear" },
      planetary: { planet: "Venus", aspectPartner: "Mars" }, crossContext: { retained: "cross" }, artifactHashes: { planetaryEphemeris: "atlas-a" } } };
  const runtime = { catalogFacetWorkerRowsQueued: 1, analysisComparisonRequestId: 0, analysisCancellationGeneration: 0,
    analysisComputeScheduleGeneration: 0, discardedWorkerResults: 0, analysisCache: new Map(),
    analysisComparisonPerformanceSamples: [], analysisComparisonDirtyComponents: new Set(),
    analysisComparisonsReady: true, analysisComparisonsRequested: true,
    analysisComparisonsManifest: { releaseId: "fixture", ephemerisAtlas: { sha256: "atlas-a" } },
    analysisComparisonOptions: { planet: "Venus", aspectPartner: "Mars", aspectOrbDegrees: 3, zodiacSystem: "sidereal", windowDays: 30 },
    analysisLastResult: core,
    analysisViewController: { renderAnalysisComparisonEvidence(evidence, metadata) { rendered.push({ evidence, metadata }); } } };
  const snapshot = () => ({ generation: state.filterGeneration, baselineMode: "full_catalog",
    filters: { selectedSources: ["keep"] }, timeRange: { mode: "full", startOrdinal: null, endOrdinal: null },
    contextLayers: { crops: { enabled: true }, animals: { enabled: true } }, areaFilter: { active: false, shapes: [] } });
  const context = vm.createContext({ runtime, state, startup: { initialViewReady: true }, catalog: [{ event_id: "fixture" }],
    console, Promise, Date, Number, String, Object, Array, Boolean, Error, Map, Set,
    window: { setTimeout(callback, delay) { const id = ++nextTimer; timers.set(id, { callback, delay }); return id; },
      clearTimeout(id) { timers.delete(id); }, UfoAnalysisView: {} },
    performance: { now: () => 12 }, getAnalysisFilterSnapshot: snapshot,
    ensureCatalogFacetWorker: () => worker, analysisCatalogDatasetHash: () => "fixture-catalog",
    catalogFacetWorkerFilterPayload: () => ({ sourceMode: "subset", selectedSources: ["keep"], lowPrecisionValues: [] }),
    scheduleAnalysisCompute(reason, options) { fullComputes.push({ reason, options }); return true; },
    ensureAnalysisComparisonArtifacts() { artifactLoads.push(true); return Promise.resolve(runtime.analysisComparisonsManifest); },
    setAnalysisMapOnlyControlsAvailable() {}, restoreMapAfterAnalysis() {}, pausePlayback() {},
  });
  for (const name of ["analysisContextReleaseHashes", "analysisV2ArtifactHashes", "analysisDurationArtifactHashes",
    "analysisReportingDelayArtifactHashes", "analysisTimeOfDayArtifactHashes", "analysisWitnessCountArtifactHashes",
    "analysisColorArtifactHashes", "analysisCoordinateEvidenceArtifactHashes"]) context[name] = () => ({});
  vm.runInContext(extract(viewSource, "cleanText"), context);
  vm.runInContext(extract(viewSource, "analysisRequestEnvelopeMatches"), context);
  context.window.UfoAnalysisView.analysisRequestEnvelopeMatches = context.analysisRequestEnvelopeMatches;
  for (const name of ["analysisComputeCacheKey", "analysisResponseEnvelopeMatchesCurrentState", "trimAnalysisResultCache",
    "analysisComparisonRequestIsCurrent", "computeAnalysisComparisonViaWorker", "renderAnalysisComparisonUpdate",
    "updateAnalysisComparisonsForCurrentSelection", "scheduleAnalysisComparisonUpdate", "handleAnalysisViewChange"]) {
    vm.runInContext(extract(appSource, name), context);
  }
  vm.runInContext(extract(appSource, "requestPlanetaryHeatmaps"), context);
  const retryStart = appSource.indexOf("function () {", appSource.indexOf("onComparisonRetry:"));
  const retryEnd = appSource.indexOf("      getFilterSnapshot:", retryStart);
  assert.ok(retryStart >= 0 && retryEnd > retryStart);
  vm.runInContext("onComparisonRetry = " + appSource.slice(retryStart, retryEnd).replace(/\s*,\s*$/, ""), context);
  runtime.analysisLastCohortKey = context.analysisComputeCacheKey(snapshot(), { excludeComparisonOptions: true });
  const cacheKey = () => context.analysisComputeCacheKey(snapshot());
  const flush = async () => { for (let index = 0; index < 15; index += 1) await Promise.resolve(); };
  async function runTimers(delay = 0) {
    for (const [id, timer] of [...timers]) if (timer.delay === delay) { timers.delete(id); timer.callback(); }
    await flush();
  }
  function complete(message, extra = {}) {
    const reply = { ...message, type: "analysisComparisonComputed", component: message.component,
      filterGeneration: message.generation, model: { component: message.component, options: { ...message.comparisonOptions } },
      artifactHashes: { planetaryEphemeris: runtime.analysisComparisonsManifest.ephemerisAtlas.sha256 }, elapsedMilliseconds: 2, ...extra };
    for (const listener of [...listeners]) listener({ data: reply });
  }
  function change(component, options) {
    Object.assign(runtime.analysisComparisonOptions, options);
    return context.scheduleAnalysisComparisonUpdate(component);
  }
  return { context, runtime, state, core, timers, listeners, posted, rendered, fullComputes, artifactLoads, cacheKey, snapshot, flush, runTimers, complete, change };
}

// A settings-only update changes only its comparison evidence and caches a new
// complete page result while retaining all original core and unrelated models.
const ready = fixture();
const original = JSON.stringify(ready.core);
ready.change("planetary", { planet: "Saturn" }); await ready.runTimers();
assert.equal(ready.posted.length, 1);
assert.equal(ready.posted[0].type, "computeAnalysisComparison");
assert.equal(ready.posted[0].component, "planetary");
assert.equal(ready.posted[0].comparisonOptions.planet, "Saturn");
ready.complete(ready.posted[0]); await ready.flush();
assert.equal(ready.rendered.length, 1);
assert.equal(ready.runtime.analysisLastResult.overview, ready.core.overview);
for (const component of ["lunar", "nuclear", "crossContext"]) {
  assert.equal(ready.runtime.analysisLastResult.comparisonEvidence[component], ready.core.comparisonEvidence[component]);
}
assert.notEqual(ready.runtime.analysisLastResult, ready.core);
assert.equal(JSON.stringify(ready.core), original);
assert.equal(ready.runtime.analysisCache.get(ready.cacheKey()), ready.runtime.analysisLastResult);
assert.equal(ready.runtime.analysisComparisonDirtyComponents.size, 0);
assert.equal(ready.runtime.analysisWorkerFlight, null);
assert.equal(ready.timers.size, 0); assert.equal(ready.listeners.size, 0);
ready.change("planetary", { planet: "Saturn" }); await ready.runTimers();
assert.equal(ready.posted.length, 1, "An unchanged cached page restores only comparison evidence without a worker query");
assert.equal(ready.rendered.length, 2);
assert.equal(ready.runtime.analysisComparisonPerformanceSamples.at(-1).cacheLayer, "page");
assert.equal(ready.fullComputes.length, 0);

// Rapid changes coalesce before dispatch and wait for an old flight without
// rendering its superseded success or losing a different dirty component.
const rapid = fixture();
rapid.change("planetary", { planet: "Mercury" });
rapid.change("planetary", { planet: "Jupiter" }); await rapid.runTimers();
assert.equal(rapid.posted.length, 1); assert.equal(rapid.posted[0].comparisonOptions.planet, "Jupiter");
rapid.change("planetary", { planet: "Saturn" });
rapid.change("nuclear", { windowDays: 90 }); await rapid.runTimers();
assert.equal(rapid.posted.length, 1, "New settings must not queue obsolete work behind an active worker flight");
rapid.complete(rapid.posted[0]); await rapid.flush();
assert.equal(rapid.rendered.length, 0);
assert.equal(rapid.runtime.discardedWorkerResults, 1);
assert.equal(rapid.posted.length, 2);
assert.equal(rapid.posted[1].component, "planetary");
assert.equal(rapid.posted[1].comparisonOptions.planet, "Saturn");
rapid.complete(rapid.posted[1]); await rapid.flush();
assert.equal(rapid.rendered.length, 1);
assert.equal(rapid.runtime.analysisCache.has(rapid.cacheKey()), false, "A partially updated set of components cannot enter the complete page cache");
assert.equal(rapid.posted.length, 3); assert.equal(rapid.posted[2].component, "nuclear");
rapid.complete(rapid.posted[2]); await rapid.flush();
assert.equal(rapid.rendered.length, 2);
assert.equal(rapid.runtime.analysisLastResult.comparisonEvidence.planetary.options.planet, "Saturn");
assert.equal(rapid.runtime.analysisLastResult.comparisonEvidence.nuclear.options.windowDays, 90);
assert.equal(rapid.runtime.analysisCache.has(rapid.cacheKey()), true);
assert.equal(rapid.timers.size, 0); assert.equal(rapid.listeners.size, 0);

const staleError = fixture();
staleError.change("planetary", { planet: "Mercury" }); await staleError.runTimers();
staleError.change("planetary", { planet: "Neptune" }); await staleError.runTimers();
staleError.complete(staleError.posted[0], { type: "analysisWorkerError", error: "Superseded failure" }); await staleError.flush();
assert.equal(staleError.rendered.length, 0, "A superseded error must not replace the currently selected comparison");
assert.equal(staleError.posted.length, 2);
staleError.complete(staleError.posted[1]); await staleError.flush();
assert.equal(staleError.rendered.at(-1).evidence.planetary.options.planet, "Neptune");
assert.ok(!staleError.runtime.analysisLastError);

// The same production envelope rejects a wrong filter generation, cancellation
// generation, full settings signature, and an atlas/cohort change.
for (const [field, replacement] of [["filterGeneration", 999], ["cancellationGeneration", 999], ["analysisSignature", "wrong-settings"], ["baselineMode", "other_dates_balanced"]]) {
  const guarded = fixture(); guarded.change("planetary", { planet: "Mercury" }); await guarded.runTimers();
  guarded.complete(guarded.posted[0], { [field]: replacement }); await guarded.flush();
  assert.equal(guarded.rendered.length, 0, "Reject mismatched response field: " + field);
  assert.equal(guarded.runtime.discardedWorkerResults, 1);
}
const atlasChange = fixture(); atlasChange.change("planetary", { planet: "Mercury" }); await atlasChange.runTimers();
atlasChange.runtime.analysisComparisonsManifest.ephemerisAtlas.sha256 = "atlas-b";
atlasChange.complete(atlasChange.posted[0]); await atlasChange.flush();
assert.equal(atlasChange.rendered.length, 0, "A response from the previous atlas cannot replace a new artifact cohort");

// A real filter change uses the regular analysis path; inferred core statistics
// cannot be preserved by an update scoped to a different cohort.
const changedFilter = fixture();
changedFilter.state.filterGeneration += 1;
changedFilter.change("planetary", { planet: "Mercury" }); await changedFilter.runTimers();
assert.equal(changedFilter.posted.length, 0);
assert.equal(changedFilter.fullComputes.length, 1);
assert.equal(changedFilter.fullComputes[0].reason, "comparison cohort changed");

const currentError = fixture(); currentError.change("planetary", { planet: "Mercury" }); await currentError.runTimers();
currentError.complete(currentError.posted[0], { type: "analysisWorkerError", error: "Invalid selection" }); await currentError.flush();
assert.equal(currentError.rendered.length, 1);
assert.equal(currentError.rendered[0].evidence.status, "error");
assert.match(currentError.rendered[0].evidence.message, /Invalid selection/);
assert.equal(currentError.runtime.analysisLastResult, currentError.core);
assert.equal(currentError.runtime.analysisCache.size, 0);
currentError.context.onComparisonRetry(); await currentError.runTimers();
assert.equal(currentError.posted.length, 2, "Retry reruns the failed dirty component instead of stopping at already-loaded artifacts");
assert.equal(currentError.artifactLoads.length, 0);
currentError.complete(currentError.posted[1]); await currentError.flush();
assert.equal(currentError.rendered.at(-1).evidence.status, "ready");
assert.equal(currentError.runtime.analysisComparisonDirtyComponents.size, 0);
assert.ok(!currentError.runtime.analysisLastError);

const freshRetry = fixture(); freshRetry.context.onComparisonRetry(); await freshRetry.flush();
assert.equal(freshRetry.artifactLoads.length, 1);
assert.equal(freshRetry.fullComputes.length, 1);
assert.equal(freshRetry.fullComputes[0].reason, "comparison retry");

const timeout = fixture(); timeout.change("planetary", { planet: "Mercury" }); await timeout.runTimers();
await timeout.runTimers(30000);
assert.equal(timeout.rendered[0].evidence.status, "error");
assert.match(timeout.rendered[0].evidence.message, /timed out/);
assert.equal(timeout.listeners.size, 0); assert.equal(timeout.timers.size, 0);

const onMap = fixture(); onMap.change("planetary", { planet: "Mercury" }); await onMap.runTimers();
onMap.context.handleAnalysisViewChange("map");
assert.equal(onMap.runtime.analysisComparisonPending, null);
onMap.complete(onMap.posted[0]); await onMap.flush();
assert.equal(onMap.rendered.length, 0);
assert.equal(onMap.change("planetary", { planet: "Jupiter" }), false);
assert.equal(onMap.posted.length, 1); assert.equal(onMap.timers.size, 0);
const mapBeforeDispatch = fixture(); mapBeforeDispatch.change("planetary", { planet: "Mercury" });
mapBeforeDispatch.context.handleAnalysisViewChange("map"); await mapBeforeDispatch.runTimers();
assert.equal(mapBeforeDispatch.posted.length, 0, "Returning to the map cancels a scheduled targeted query before dispatch");
assert.equal(mapBeforeDispatch.timers.size, 0);

// A fully cached core result without an overview must still load the requested
// heatmap component. Readout/metric interactions stay renderer-local.
const heatmaps = fixture();
heatmaps.runtime.analysisCache.set(heatmaps.cacheKey(), heatmaps.core);
heatmaps.context.requestPlanetaryHeatmaps({ zodiacSystem: "sidereal", aspectOrbDegrees: 3 });
heatmaps.context.requestPlanetaryHeatmaps({ zodiacSystem: "sidereal", aspectOrbDegrees: 3 });
await heatmaps.runTimers();
assert.equal(heatmaps.posted.length, 1, "Duplicate lazy requests coalesce");
assert.equal(heatmaps.posted[0].component, "planetaryHeatmaps");
heatmaps.complete(heatmaps.posted[0], { model: { status: "ready", domains: [] } }); await heatmaps.flush();
assert.equal(heatmaps.runtime.analysisLastResult.summary, heatmaps.core.summary);
assert.equal(heatmaps.runtime.analysisLastResult.comparisonEvidence.planetary, heatmaps.core.comparisonEvidence.planetary);
assert.equal(heatmaps.core.comparisonEvidence.planetaryHeatmaps, undefined, "Earlier cache objects stay immutable");
assert.equal(heatmaps.fullComputes.length, 0);
heatmaps.context.requestPlanetaryHeatmaps({ zodiacSystem: "sidereal", aspectOrbDegrees: 3 }); await heatmaps.runTimers();
assert.equal(heatmaps.posted.length, 1, "A ready overview returns from page cache");

const changedHeatmap = fixture();
changedHeatmap.context.requestPlanetaryHeatmaps({ aspectOrbDegrees: 5 }); await changedHeatmap.runTimers();
assert.equal(changedHeatmap.posted[0].component, "planetary", "Detailed charts retain matching settings");
changedHeatmap.complete(changedHeatmap.posted[0]); await changedHeatmap.flush();
assert.equal(changedHeatmap.posted[1].component, "planetaryHeatmaps");
assert.equal(changedHeatmap.runtime.analysisCache.size, 0, "Partially refreshed combinations cannot be cached");
changedHeatmap.complete(changedHeatmap.posted[1], { model: { status: "ready", domains: [] } }); await changedHeatmap.flush();
assert.equal(changedHeatmap.runtime.analysisCache.size, 1);
assert.equal(changedHeatmap.fullComputes.length, 0);

const failedHeatmap = fixture(); failedHeatmap.context.requestPlanetaryHeatmaps(); await failedHeatmap.runTimers();
failedHeatmap.complete(failedHeatmap.posted[0], { type: "analysisWorkerError", error: "Invalid overview" }); await failedHeatmap.flush();
assert.equal(failedHeatmap.rendered[0].evidence.status, "ready", "Overview failure must not hide unrelated comparisons");
assert.equal(failedHeatmap.rendered[0].evidence.planetaryHeatmaps.status, "error");
assert.equal(failedHeatmap.rendered[0].evidence.lunar, failedHeatmap.core.comparisonEvidence.lunar);
failedHeatmap.context.requestPlanetaryHeatmaps(); await failedHeatmap.runTimers();
assert.equal(failedHeatmap.posted.length, 2);
failedHeatmap.complete(failedHeatmap.posted[1], { model: { status: "ready", domains: [] } }); await failedHeatmap.flush();
assert.equal(failedHeatmap.runtime.analysisLastResult.comparisonEvidence.planetaryHeatmaps.status, "ready");
assert.equal(failedHeatmap.runtime.analysisComparisonDirtyComponents.size, 0);

console.log("Targeted comparisons and lazy heatmaps: coalescing, immutable caches, cohort/envelope guards, stale errors, map return and retry checks passed.");
