import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const appSource = fs.readFileSync("app.js", "utf8").replace(/\r\n/g, "\n");
function actualFunction(name) {
  const start = appSource.search(new RegExp("^  (?:async )?function " + name + "\\(", "m"));
  assert.ok(start >= 0, "Missing app function " + name);
  const next = appSource.slice(start + 1).search(/\n  (?:async )?function \w+\(/);
  assert.ok(next >= 0);
  return appSource.slice(start, start + 1 + next);
}
function workerFixture(withEncounters = false) {
  const messages = [], self = { postMessage: message => messages.push(message) };
  const context = vm.createContext({ self, console });
  if (withEncounters) {
    vm.runInContext(fs.readFileSync("encounter_evidence.js", "utf8"), context);
    self.UFOEncounterEvidence = context.UFOEncounterEvidence;
  }
  for (const name of ["analysis_stats.js", "catalog_filter_worker.js"]) vm.runInContext(fs.readFileSync(name, "utf8"), context);
  const send = message => { messages.length = 0; self.onmessage({ data: message }); assert.equal(messages.length, 1); return messages[0]; };
  const base = { source: "fixture", type: "Disk", craftType: "disc_saucer", mapped: true, precision: "city",
    datePrecision: "exact_day", lat: 40, lon: -75, craftConfidence: "high" };
  const rows = [
    { ...base, eventId: 0, sortOrdinal: 0 },
    { ...base, eventId: "later", sortOrdinal: 10957, source: "second", type: "Triangle", craftType: "triangle", mapped: false },
    { ...base, eventId: "undated", sortOrdinal: null, datePrecision: "unknown", craftType: "unknown", mapped: false },
  ];
  if (withEncounters) {
    rows.forEach(row => { row.encounterEvidenceReady = true; row.encounterEvidenceProvenanceReady = true; });
    rows[0].encounterBeingMask = self.UFOEncounterEvidence.beingMask(["grey", "small_humanoid"]);
    rows[0].encounterSourceBeingMask = rows[0].encounterBeingMask;
    rows[0].encounterAbductionCode = 1;
    rows[1].encounterBeingMask = self.UFOEncounterEvidence.beingMask(["nordic"]);
    rows[1].encounterNarrativeBeingMask = rows[1].encounterBeingMask;
    rows[1].encounterAbductionCode = 2;
  }
  assert.notEqual(send({ type: "addCatalogFacetRows", rows }).type, "catalogFacetWorkerError");
  return { send, rows };
}

const fixture = workerFixture();
const allFilters = { sourceMode: "all", typeMode: "all", precisionMode: "all" };
const capture = input => fixture.send({ type: "captureAnalysisSession", requestId: "fixture", generation: 1,
  fullTimeRange: true, filters: allFilters, ...input });
const live = capture({ fullTimeRange: false, timeRangeMode: "window", timeRangeStartOrdinal: 0, timeRangeEndOrdinal: 0 });
assert.deepEqual([...live.result.eventIds], ["0"], "Current capture must honor the live date window and preserve ID zero");
const explicit = capture({ requestedEventIds: ["later", "undated", "later"], filters: { sourceMode: "none", typeMode: "none" },
  fullTimeRange: false, timeRangeStartOrdinal: 0, timeRangeEndOrdinal: 0,
  areaFilterShapes: [{ type: "rectangle", bounds: { north: 1, south: 0, east: 1, west: 0 } }] });
assert.deepEqual([...explicit.result.eventIds], ["later", "undated"], "Explicit capture ignores previous date/type/area restrictions");
assert.equal(explicit.result.summary.reportN, 2);
assert.equal(explicit.result.summary.unmappedN, 2);
assert.equal(explicit.result.summary.datedN, 1);
assert.equal(explicit.result.summary.undatedN, 1);
assert.equal(explicit.result.summary.distributions.being, null, "Unavailable evidence is not a zero distribution");
assert.equal(capture({ requestedEventIds: ["later", "missing"] }).type, "catalogFacetWorkerError", "Unknown IDs reject the whole capture");

for (const [ids, year] of [[["0"], 1970], [["later"], 2000], [["0"], 1970]]) {
  const computed = fixture.send({ type: "computeAnalysis", requestId: "same-cache-envelope", generation: 1,
    fullTimeRange: true, timeRangeMode: "full", baselineMode: "whole_corpus_structure", datasetHash: "fixture", quickMode: true,
    selectedDomains: ["overview", "time"], filters: { ...allFilters, analysisSessionEventIds: ids } });
  assert.notEqual(computed.type, "catalogFacetWorkerError", computed.error);
  assert.equal(computed.result.summary.activeCount, 1);
  assert.equal(Number(computed.result.time.annualSeries[0].year), year, "Same-sized frozen populations cannot share cached results");
}
const frozenCurrent = capture({ filters: { ...allFilters, analysisSessionEventIds: ["later"] } });
assert.deepEqual([...frozenCurrent.result.eventIds], ["later"], "Pin current while a selection is active must capture that selection");
const sparse = fixture.send({ type: "inspectCollectionReportIds", requestedEventIds: ["0", "later", "undated"],
  fullTimeRange: true, filters: { ...allFilters, analysisSessionEventIds: ["later"] } });
assert.deepEqual([...sparse.result.eventIds], ["later"], "Follow-current collection context intersects the frozen population");

const encounter = workerFixture(true).send({ type: "captureAnalysisSession", fullTimeRange: true, filters: allFilters });
assert.equal(encounter.result.summary.distributions.being.eligibleN, 2);
assert.equal(encounter.result.summary.distributions.being.unknownN, 1);
assert.equal(encounter.result.summary.distributions.being.rows.reduce((sum, row) => sum + row.count, 0), 3, "Being labels may overlap within a report");
assert.equal(encounter.result.summary.distributions.abduction.unknownN, 1, "Unindexed reports are not coded as no abduction");

// Exercise the production app helpers and controller with the real RAM model.
const timers = new Map(), listeners = new Map(), posted = [], scheduled = [];
let nextTimer = 0;
const worker = { addEventListener(type, fn) { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(fn); },
  removeEventListener(type, fn) { listeners.get(type)?.delete(fn); }, postMessage(message) { posted.push(message); } };
const filters = { keyword: "stale search", sourceMode: "subset", typeMode: "subset", precisionMode: "all",
  selectedSources: new Set(["fixture"]), selectedTypes: new Set(["Disk"]), selectedPrecisions: new Set(),
  legendEventMode: "all", legendColorMode: "craft_type", selectedLegendEventKeys: new Set(), hideLowPrecision: false,
  hideNonExactDates: false, encounters: { abduction: "any", being: "any", beingTypes: [] }, encounterSelectionIds: null };
const runtime = { activeFilterGeneration: 1, catalogFacetWorkerRowsQueued: 3, catalogFacetWorkerRequestId: 0,
  analysisSessionCaptureGeneration: 0, analysisViewController: { setActiveView() {} } };
const state = { activeView: "analysis", filterGeneration: 1, analysisBaselineMode: "other_dates_balanced", timeRangeMode: "window",
  timeRangeStartOrdinal: 0, timeRangeEndOrdinal: 0, regionSelection: { pointOnly: false }, timelineCatalog: [1], filteredCatalog: [1],
  filteredMappedCatalog: [1], filteredPlaybackEventCount: 1, filteredSourceCoordinateEventIdSet: new Set(),
  filteredExactDateEventIdSet: new Set(), filteredExactDateEventCount: 1, lastKeywordMatches: new Set(["0"]) };
const hashes = () => ({});
const context = vm.createContext({ runtime, state, startup: { fullCatalogReady: true, initialViewReady: true }, catalog: fixture.rows,
  console, performance: { now: () => 0 }, document: { getElementById: () => null }, currentFilterSelections: () => filters,
  contextLayerAnalysisStatus: () => ({}), els: {}, ordinalToIso: value => String(value),
  regionSelectionHasActiveShapes: () => true, analysisRegionShapesSnapshot: () => [{ type: "circle", center: { lat: 0, lng: 0 }, radiusMeters: 1 }],
  analysisCatalogDatasetHash: () => "fixture", analysisContextReleaseHashes: hashes, analysisV2ArtifactHashes: hashes,
  analysisDurationArtifactHashes: hashes, analysisReportingDelayArtifactHashes: hashes, analysisTimeOfDayArtifactHashes: hashes,
  analysisWitnessCountArtifactHashes: hashes, analysisColorArtifactHashes: hashes, analysisCoordinateEvidenceArtifactHashes: hashes,
  LOW_PRECISION_VALUES: new Set(["country", "unknown"]), ensureCatalogFacetWorker: () => worker,
  scheduleAnalysisCompute: (...args) => scheduled.push(args),
  setTimeout(fn, delay) { assert.ok([30000, 8000, 15000, 45000].includes(delay)); const id = ++nextTimer; timers.set(id, fn); return id; },
  clearTimeout(id) { timers.delete(id); } });
context.window = context;
const projectionLoaders = ["ensureAnalysisGeographyArtifact", "ensureAnalysisDurationArtifact", "ensureAnalysisTimeOfDayArtifact", "ensureAnalysisWitnessCountArtifact", "ensureAnalysisColorArtifact"];
for (const name of projectionLoaders) context[name] = () => Promise.resolve(true);
const flushPreparation = () => new Promise(resolve => setImmediate(resolve));
function deferProjectionLoads() {
  const calls = [], pending = new Map(), originals = new Map();
  for (const name of projectionLoaders) {
    originals.set(name, context[name]);
    let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    pending.set(name, { resolve, reject }); context[name] = () => { calls.push(name); return promise; };
  }
  return { calls, pending, resolveAll() { pending.forEach(item => item.resolve(true)); }, restore() { originals.forEach((loader, name) => { context[name] = loader; }); } };
}
for (const name of ["contextLayerAnalysisStatus", "analysisContextReleaseHashes", "analysisV2ArtifactHashes", "analysisDurationArtifactHashes",
  "analysisReportingDelayArtifactHashes", "analysisTimeOfDayArtifactHashes", "analysisWitnessCountArtifactHashes", "analysisColorArtifactHashes", "analysisCoordinateEvidenceArtifactHashes"]) {
  context[name] = vm.runInContext("() => ({})", context);
}
context.analysisRegionShapesSnapshot = vm.runInContext("() => [{type:'circle',center:{lat:0,lng:0},radiusMeters:1}]", context);
filters.encounters = vm.runInContext("({abduction:'any',being:'any',beingTypes:[]})", context);
vm.runInContext(fs.readFileSync("analysis_session.js", "utf8"), context);
vm.runInContext(fs.readFileSync("analysis_view.js", "utf8"), context);
for (const name of ["getAnalysisFilterSnapshot", "analysisSessionNeutralFilters", "analysisWorkerFilterPayload",
  "catalogFacetWorkerFilterPayload", "analysisSessionCaptureSnapshot", "requireAnalysisSessionReady", "prepareAnalysisComparisonCapture", "captureAnalysisSessionPopulation",
  "initializeAnalysisSession", "setAnalysisComparisonMode", "syncAnalysisComparisonWorkspace", "analysisComputeCacheKey", "analysisResponseEnvelopeMatchesCurrentState", "computeAnalysisViaWorker"]) vm.runInContext(actualFunction(name), context);
context.initializeAnalysisSession();
const integration = context.UfoAnalysisSessionIntegration;
const cloneIntoApp = value => vm.runInContext("JSON.parse(" + JSON.stringify(JSON.stringify(value)) + ")", context);
function complete(request = posted.at(-1), transform = value => value) {
  const response = transform(fixture.send(request));
  for (const callback of [...listeners.get("message") || []]) callback({ data: cloneIntoApp(response) });
}
const initialMap = JSON.stringify(context.catalogFacetWorkerFilterPayload(state.lastKeywordMatches, 1));
const first = integration.useSelection(cloneIntoApp({ eventIds: ["later"], label: "Later report", source: "fixture" }));
complete(); await first;
const selected = context.getAnalysisFilterSnapshot();
assert.equal(selected.timeRange.mode, "full");
assert.equal(selected.filters.keyword, "");
assert.equal(selected.filters.typeMode, "all");
assert.equal(selected.areaFilter.active, false);
assert.deepEqual([...context.analysisWorkerFilterPayload(selected).analysisSessionEventIds], ["later"]);
assert.equal(JSON.stringify(context.catalogFacetWorkerFilterPayload(state.lastKeywordMatches, 1)), initialMap, "Applying an Analysis population cannot mutate the map payload");
// Use the actual request and real view envelope checker rather than a baseline-
// echoing mock. Whole-corpus structure is a result mode, not a request baseline.
runtime.analysisRequestId = 0; runtime.analysisCancellationGeneration = 0; runtime.discardedWorkerResults = 0;
for (const quickMode of [true, false]) {
  const pendingCompute = context.computeAnalysisViaWorker(selected, { quickMode });
  complete();
  const acceptedCompute = await pendingCompute;
  assert.ok(acceptedCompute, "A frozen selection's real worker envelope must be accepted");
  assert.equal(acceptedCompute.result.summary.activeCount, 1);
  assert.equal(acceptedCompute.analysisMode, "whole_corpus_structure");
  assert.equal(acceptedCompute.result.summary.unmappedCount, 1, "Unmapped selected reports retain section eligibility distinctions");
}
assert.equal(runtime.discardedWorkerResults, 0);

const selectedKey = context.analysisComputeCacheKey(selected);
const second = integration.useSelection(cloneIntoApp({ eventIds: ["0"], label: "Epoch report", source: "fixture" }));
complete(); await second;
assert.notEqual(context.analysisComputeCacheKey(context.getAnalysisFilterSnapshot()), selectedKey, "Main cache includes capture identity, not only report count");
const pin = integration.captureCurrent("A");
assert.deepEqual([...posted.at(-1).filters.analysisSessionEventIds], ["0"]);
complete(); await pin;
assert.deepEqual([...integration.getState().groups.A.eventIds], ["0"]);
// The toolbar captures the visible shared From/To controls, even after the
// user has opened a held group across Analysis. The API's captureCurrent
// above intentionally retains the frozen-selection behavior for drilldowns.
const originalSourceMode = filters.sourceMode, originalTypeMode = filters.typeMode, originalKeyword = filters.keyword;
const originalSources = filters.selectedSources, originalTypes = filters.selectedTypes;
filters.sourceMode = "all"; filters.typeMode = "all"; filters.keyword = "";
filters.selectedSources = new Set(fixture.rows.map(row => row.source));
filters.selectedTypes = new Set(fixture.rows.map(row => row.type));
state.lastKeywordMatches = null;
state.timeRangeStartOrdinal = 10957; state.timeRangeEndOrdinal = 10957;
context.regionSelectionHasActiveShapes = () => false;
const preparationStatuses = [], originalSessionView = runtime.analysisSessionView;
runtime.analysisSessionView = { setStatus(message) { preparationStatuses.push(message); } };
const originalGeographyHashes = context.analysisV2ArtifactHashes;
context.analysisV2ArtifactHashes = vm.runInContext('() => ({fixture:runtime.testArtifactHash || "before"})', context);
const deferredLoads = deferProjectionLoads(), beforePreparedCapture = posted.length;
const captureFromControls = integration.captureCurrentFilters("B");
await flushPreparation();
assert.deepEqual(deferredLoads.calls.slice().sort(), projectionLoaders.slice().sort());
assert.equal(posted.length, beforePreparedCapture, "No group snapshot is captured before optional category data settles");
assert.match(preparationStatuses.at(-1), /preparing.*category/i);
for (const name of projectionLoaders.slice(0, -1)) deferredLoads.pending.get(name).resolve(true);
await flushPreparation();
assert.equal(posted.length, beforePreparedCapture, "A slow final projection cannot leave the group with an unnecessarily incomplete snapshot");
runtime.testArtifactHash = "after";
deferredLoads.pending.get("ensureAnalysisColorArtifact").reject(new Error("Optional color projection unavailable"));
await flushPreparation();
assert.equal(posted.length, beforePreparedCapture + 1, "An optional projection failure still permits a useful group capture");
const controlsRequest = posted.at(-1);
assert.equal(controlsRequest.timeRangeStartOrdinal, 10957);
assert.equal(controlsRequest.timeRangeEndOrdinal, 10957);
assert.equal(controlsRequest.fullTimeRange, false);
assert.equal(controlsRequest.filters.analysisSessionEventIds, undefined, "Toolbar capture must not silently reuse frozen A IDs");
assert.equal(controlsRequest.filters.keywordActive, false);
complete(); await captureFromControls;
deferredLoads.restore(); context.analysisV2ArtifactHashes = originalGeographyHashes;
assert.equal(preparationStatuses.at(-1), "", "Successful preparation clears its temporary progress status");
assert.equal(integration.getState().groups.B.summary.distributions.color, null, "A failed or unloaded optional field is unavailable, not a zero distribution");
assert.deepEqual([...integration.getState().groups.B.eventIds], ["later"], "Visible dates capture distinct B while A remains held");
assert.deepEqual([...integration.getState().groups.A.eventIds], ["0"]);
assert.deepEqual([...integration.getState().selection.eventIds], ["0"], "Holding B does not replace the user's active frozen selection");
assert.equal(integration.getState().groups.B.scope.timeRange.startOrdinal, 10957);

const stalePreload = deferProjectionLoads(), beforeStalePreload = posted.length;
const controlsChangedDuringPreload = integration.captureCurrentFilters("B");
await flushPreparation(); state.timeRangeEndOrdinal = 10958;
stalePreload.resolveAll();
await assert.rejects(controlsChangedDuringPreload, /dates or filters changed|selection changed/i,
  "A live date edit while projections prepare rejects the obsolete capture before it reaches the catalog worker");
assert.equal(posted.length, beforeStalePreload); stalePreload.restore(); state.timeRangeEndOrdinal = 10957;

const cancelledPreload = deferProjectionLoads(), beforeCancelledPreload = posted.length;
const captureCancelledDuringPreload = integration.captureCurrentFilters("B");
await flushPreparation(); integration.clearGroup("A"); cancelledPreload.resolveAll();
await assert.rejects(captureCancelledDuringPreload, /dates or filters changed|selection changed/i,
  "Clearing a group while projections prepare cannot start a stale replacement capture");
assert.equal(posted.length, beforeCancelledPreload); cancelledPreload.restore();
// Restore A from its immutable earlier payload without disturbing the active
// frozen selection, whose visible shared-date behavior is tested below.
runtime.analysisSessionStore.setGroup("A", cloneIntoApp({ eventIds: ["0"], label: "Epoch report" }));

const changedControls = integration.captureCurrentFilters("B");
await flushPreparation();
state.timeRangeEndOrdinal = 10958;
complete();
await assert.rejects(changedControls, /selection changed|filters changed|source selection changed/i,
  "A live date edit during capture is rejected even while frozen A masks the ordinary active snapshot");
assert.deepEqual([...integration.getState().groups.B.eventIds], ["later"]);
state.timeRangeEndOrdinal = 10957;
const controlsChangedAfterReply = integration.captureCurrentFilters("B");
await flushPreparation();
complete(); state.timeRangeEndOrdinal = 10958;
await assert.rejects(controlsChangedAfterReply, /selection changed|filters changed|source selection changed/i,
  "A live date edit after the worker reply is rechecked before a captured group is committed");
assert.deepEqual([...integration.getState().groups.B.eventIds], ["later"]);

filters.sourceMode = originalSourceMode; filters.typeMode = originalTypeMode; filters.keyword = originalKeyword;
filters.selectedSources = originalSources; filters.selectedTypes = originalTypes;
state.lastKeywordMatches = new Set(["0"]);
state.timeRangeStartOrdinal = 0; state.timeRangeEndOrdinal = 0;
context.regionSelectionHasActiveShapes = () => true;
runtime.analysisSessionView = originalSessionView;
const cancelled = integration.captureSelection("B", cloneIntoApp({ eventIds: ["later"] }));
integration.clearAll(); complete();
await assert.rejects(cancelled, /selection changed/);
assert.equal(integration.getState().groups.B, null);
assert.equal(integration.getState().selection, null);
const commitCancelled = integration.captureSelection("A", cloneIntoApp({ eventIds: ["0"] }));
complete(); integration.clearAll();
await assert.rejects(commitCancelled, /selection changed/, "Clear after the worker reply still cancels the asynchronous slot commit");
let resolveInspection;
context.requestEncounterReports = request => { assert.equal(request.allIds, true); return new Promise(resolve => { resolveInspection = resolve; }); };
const encounterCancelled = integration.captureEncounter("B", cloneIntoApp({ inspection: { axis: "being" }, label: "Encounter subset" }));
integration.clearAll(); resolveInspection({ eventIds: ["later"] });
await assert.rejects(encounterCancelled, /cancelled or replaced/, "Clear during encounter inspection cannot start a stale later capture");
assert.equal(integration.getState().groups.A, null);
assert.equal(integration.getState().groups.B, null);
assert.equal(context.getAnalysisFilterSnapshot().timeRange.mode, "window", "Clear restores live Analysis filters");
assert.equal(JSON.stringify(context.catalogFacetWorkerFilterPayload(state.lastKeywordMatches, 1)), initialMap);
assert.equal(timers.size, 0);
assert.equal(listeners.get("message").size, 0);
assert.equal(listeners.get("error").size, 0);
assert.ok(scheduled.length >= 3);
// Verify the production toolbar uses the visible-control capture helper,
// rather than the API's intentionally frozen-population capture helper.
let sessionViewConfiguration, initialSection;
const sessionTarget = {}, comparisonTarget = {};
context.document.getElementById = id => id === "analysis-session-panel" ? sessionTarget : id === "analysis-comparison-workspace" ? comparisonTarget : null;
context.UfoAnalysisSessionView = { create(target, configuration) {
  assert.equal(target, sessionTarget); sessionViewConfiguration = configuration;
  return { setSection(section) { initialSection = section; } };
} };
runtime.analysisSessionStore = null;
runtime.analysisViewController.activeSectionId = "analysis-section-geography";
context.initializeAnalysisSession();
assert.equal(sessionViewConfiguration.onPinCurrent, context.UfoAnalysisSessionIntegration.captureCurrentFilters);
assert.notEqual(sessionViewConfiguration.onPinCurrent, context.UfoAnalysisSessionIntegration.captureCurrent);
assert.equal(sessionViewConfiguration.comparisonTarget, comparisonTarget);
assert.equal(sessionViewConfiguration.onModeChange, context.setAnalysisComparisonMode);
assert.equal(initialSection, "geography", "A restored Analysis topic initializes the comparison in that same topic");
runtime.catalogFacetWorkerRowsQueued = 1;
await assert.rejects(integration.captureCurrent("A"), /complete catalog/);
console.log("Temporary Analysis integration: exact IDs, visible-date capture, projection preparation, optional failure, stale-input cancellation, cache identities, missing evidence and map preservation passed.");
