import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../app.js", import.meta.url), "utf8").replace(/\r\n/g, "\n");
function actualFunction(name) {
  const start = source.search(new RegExp("^  (?:async )?function " + name + "\\(", "m"));
  assert.ok(start >= 0, "Actual app function exists: " + name);
  const rest = source.slice(start + 1);
  const next = rest.search(/\n  (?:async )?function \w+\(/);
  assert.ok(next >= 0, "Actual function has a following boundary: " + name);
  return source.slice(start, start + 1 + next).trim();
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const flush = async () => { for (let index = 0; index < 24; index += 1) await Promise.resolve(); };
function fixture() {
  const calls = [], events = [], uiStates = [], background = deferred(), initialVisuals = deferred();
  const initial = [{ event_id: 7, sort_date_iso: "1954-09-16", has_coordinates: true }];
  const catalog = [...initial, { event_id: 8 }, { event_id: 9 }];
  const state = { timeRangeStartOrdinal: 100, timeRangeEndOrdinal: 200, timelineDataVersion: 0,
    filterToken: 3, selectedEventId: 7, filteredMappedCatalog: [], overlayVisibility: { air: true },
    playbackState: "stopped" };
  const startup = { phase: "Idle", progressiveEnabled: false, mapViewReady: false,
    initialViewReady: false, fullCatalogReady: false, backgroundError: "", errorText: "" };
  let renderFailure = null, visualCalls = 0, loadCalls = 0, analysisEnabled = false;
  const viewport = { center: [10, 20], zoom: 4 };
  const runtime = { map: { getZoom: () => viewport.zoom },
    analysisViewController: { setAnalysisEnabled(value) { analysisEnabled = value; calls.push(["analysis", value]); } },
    progressiveManifest: { counts: { defaultFilteredEvents: 1, globalCatalog: 3 } },
    canonicalWebArtifacts: { summaryManifest: [{}, {}] } };
  const payload = { events: initial, traceEventOrder: [7], traceChronology: {}, scope: "Mapped initial window",
    dateRange: { start: "1954-09-01", end: "1954-11-30" }, filterValues: {} };
  const context = vm.createContext({ startup, runtime, state, catalog, console, Promise, Map, Object, Error,
    OVERLAY_DEFINITIONS: { air: {} }, STARTUP_PROGRESS: { ready: 100 }, MAP_DEFAULT_INITIAL_ZOOM: 4,
    PACKED_TRACE_ARTIFACT_KINDS: { eventIndex: "event_index" },
    document: {}, window: { location: { search: "?progressiveStartup=1" },
      UFOStartupCatalogUI: { create() { return { update(value) { uiStates.push({ ...value }); }, dispose() {} }; } },
      UfoProgressiveCatalogRuntime: {},
      CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
      dispatchEvent(event) { events.push(event); },
    },
    URLSearchParams,
    TRACE_CHRONOLOGY: { createEvidenceIndex: () => ({ source: "initial timing" }) },
    preferredTileProviderId: () => "configured", resolveAssetPath: value => value,
    measureStartupStep: (_name, callback) => callback(),
    fetchJson: async () => ({ normalizedCount: 3 }),
    loadProgressiveStartupProfile: async () => payload,
    prepareProgressiveCatalogInputs: async () => { calls.push("prepareCatalogInputs"); return { traceEvidence: { scope: "full catalog" } }; },
    ensureCanonicalTraceArtifactLoaded: async () => { calls.push("tracePrefetch"); return { ready: true }; },
    loadCatalog: async () => { loadCalls += 1; await background.promise; },
    canonicalWebArtifactsCanServePrimaryCatalog: () => true,
    computeOrdinalExtent: rows => ({ minOrdinal: rows.length ? 1 : 0, maxOrdinal: 9 }),
    isoToOrdinal: value => value.endsWith("09-01") ? 100 : 200,
    initializeMap: () => calls.push("initializeMap"),
    initializeFilters: () => calls.push("initializeFilters"),
    setTimeRange(start, end) { calls.push("setTimeRange"); state.timeRangeStartOrdinal = start; state.timeRangeEndOrdinal = end; },
    buildFilteredCatalogState: () => ({ baseCatalog: context.progressiveInitialMapActive() ? runtime.progressiveEvents : catalog,
      keywordActive: false, preserveDateAscending: true, legendEventCounts: new Map(), legendEventColorMode: "craft" }),
    applyFilteredCatalogState(rows) { state.timelineCatalog = rows; state.filteredMappedCatalog = rows; state.timelineDataVersion += 1; calls.push(["apply", rows.length]); },
    finalizeFilteredCatalogState() { calls.push("finalizeFilters"); },
    renderFilteredState() { calls.push("render"); if (renderFailure) { const error = renderFailure; renderFailure = null; throw error; } },
    finalizeInitialStartupVisuals: async () => { visualCalls += 1; await context.applyStartupFitBeforeReady(); if (visualCalls === 1) await initialVisuals.promise; },
    runDeferredStartupRefinement: async () => { calls.push("refine"); },
    fitToResults() { calls.push("fitToResults"); viewport.center = [30, 40]; },
    waitForBrowserPaint: async () => {},
    setStartupPhase(phase) { startup.phase = phase; },
    setStartupPhaseAndPaint: async phase => { startup.phase = phase; },
    recordStartupMilestone() {}, recordStartupDecision() {},
    buildStartupTimingSummary() { calls.push("buildTimingSnapshot"); return { phase: startup.phase }; },
    writeStartupTimingExport() { calls.push("exportTimingSnapshot"); },
    finalizeStartupTimingSummary() { calls.push("finalizeTimingSession"); }, logStartupTimingSummary() {},
  });
  for (const name of ["ensureWorldReferenceData", "loadCanonicalWebArtifactsRuntime", "loadDetailQualityOverlayRuntime",
    "loadAnalysisRepairDetailOverlayRuntime", "populateBasemapOptions", "attachEventHandlers", "setBasemap",
    "syncOverlayVisibility", "ensureOverlayLayer"]) context[name] = async () => {};
  context.ensureDetailQualityOverlayLoaded = context.loadDetailQualityOverlayRuntime;
  context.ensureAnalysisRepairDetailOverlayLoaded = context.loadAnalysisRepairDetailOverlayRuntime;
  for (const name of ["progressiveStartupRequested", "progressiveInitialMapActive", "updateProgressiveCatalogUi",
    "initializeProgressiveStartup", "promoteProgressiveCatalog", "startProgressiveCatalogBackground", "applyStartupFitBeforeReady"])
    vm.runInContext(actualFunction(name), context);
  return { context, calls, events, uiStates, background, initialVisuals, startup, runtime, state, viewport,
    get loadCalls() { return loadCalls; }, get analysisEnabled() { return analysisEnabled; },
    failNextRender(error) { renderFailure = error; },
  };
}

const ready = fixture();
const initialLoad = ready.context.initializeProgressiveStartup();
await flush();
assert.equal(ready.startup.mapViewReady, false, "Initial visual gate keeps the cover closed");
assert.equal(ready.startup.fullCatalogReady, false);
assert.equal(ready.loadCalls, 0, "Heavy background catalog does not compete with initial map preparation");
assert.equal(ready.calls.includes("prepareCatalogInputs"), true, "Network preparation overlaps initial visual settling without hydrating the catalog");
ready.initialVisuals.resolve(); await initialLoad; await flush();
assert.equal(ready.startup.mapViewReady, true);
assert.equal(ready.startup.initialViewReady, true);
assert.equal(ready.startup.fullCatalogReady, false, "Usable map does not claim full-catalog readiness");
assert.equal(ready.analysisEnabled, false);
assert.equal(ready.events.filter(event => event.type === "ufo:timeline-map-ready").length, 1);
assert.equal(ready.events.some(event => event.type === "ufo:timeline-ready"), false);
assert.equal(ready.loadCalls, 1);
assert.equal(ready.calls.includes("tracePrefetch"), true, "Full trace downloading overlaps catalog preparation rather than waiting for final promotion");
assert.equal(ready.calls.includes("exportTimingSnapshot"), true, "Early map readiness exports a timing snapshot");
assert.equal(ready.calls.includes("finalizeTimingSession"), false, "Early map readiness must not freeze the full startup timing session");
const sameLoading = ready.context.startProgressiveCatalogBackground();
assert.equal(sameLoading, ready.runtime.progressiveBackgroundPromise, "Repeated retry requests share the active load");
assert.equal(ready.loadCalls, 1);
ready.viewport.center = [51, -1]; ready.viewport.zoom = 6;
ready.state.timeRangeStartOrdinal = 110; ready.state.timeRangeEndOrdinal = 190;
ready.background.resolve(); await sameLoading;
assert.equal(ready.startup.fullCatalogReady, true);
assert.equal(ready.analysisEnabled, true);
assert.deepEqual(ready.viewport, { center: [51, -1], zoom: 6 }, "Catalog promotion preserves the visitor's map view");
assert.equal(ready.state.timeRangeStartOrdinal, 110);
assert.equal(ready.state.timeRangeEndOrdinal, 190);
assert.equal(ready.calls.filter(call => call === "initializeMap").length, 1);
assert.equal(ready.calls.filter(call => call === "initializeFilters").length, 1);
assert.equal(ready.calls.filter(call => call === "setTimeRange").length, 1);
assert.equal(ready.events.filter(event => event.type === "ufo:timeline-ready").length, 1);
assert.equal(ready.calls.filter(call => call === "finalizeTimingSession").length, 1, "The timing session finishes only when the complete catalog is ready");
assert.equal(ready.state.selectedEventId, 7, "Report selection survives catalog promotion");
assert.equal(ready.runtime.progressiveBackgroundPromise, null);
await ready.context.startProgressiveCatalogBackground();
assert.equal(ready.loadCalls, 1, "Ready catalog cannot start a duplicate background build");
ready.startup.fullCatalogReady = false;
ready.state.selectedEventId = null;
ready.viewport.zoom = 4;
assert.equal(await ready.context.applyStartupFitBeforeReady(), false,
  "A panned map at its original zoom is protected even without a selected report");
assert.deepEqual(ready.viewport.center, [51, -1]);

const failed = fixture();
failed.initialVisuals.resolve(); await failed.context.initializeProgressiveStartup();
const failedJob = failed.runtime.progressiveBackgroundPromise;
failed.background.reject(new Error("Summary shard unavailable")); await failedJob;
assert.equal(failed.startup.mapViewReady, true);
assert.equal(failed.startup.initialViewReady, true);
assert.equal(failed.startup.fullCatalogReady, false);
assert.equal(failed.analysisEnabled, false);
assert.equal(failed.startup.errorText, "", "Background failures do not invoke the fatal loading cover");
assert.match(failed.startup.backgroundError, /Summary shard unavailable/);
assert.equal(failed.context.progressiveInitialMapActive(), true);
assert.equal(failed.runtime.progressiveBackgroundPromise, null);
assert.equal(failed.events.some(event => event.type === "ufo:timeline-ready"), false);
failed.context.loadCatalog = async () => {};
await failed.context.startProgressiveCatalogBackground();
assert.equal(failed.startup.fullCatalogReady, true);
assert.equal(failed.startup.backgroundError, "");
assert.equal(failed.analysisEnabled, true);

// A failure after full-population filtering must restore the verified scoped view
// and must not disable the retry by prematurely setting the final readiness flag.
const promotionFailure = fixture();
promotionFailure.initialVisuals.resolve(); await promotionFailure.context.initializeProgressiveStartup();
promotionFailure.failNextRender(new Error("Full map render failed"));
promotionFailure.background.resolve(); await promotionFailure.runtime.progressiveBackgroundPromise;
assert.equal(promotionFailure.startup.fullCatalogReady, false, "Promotion failure retains the retryable loading state");
assert.equal(promotionFailure.analysisEnabled, false);
assert.equal(promotionFailure.context.progressiveInitialMapActive(), true);
assert.equal(promotionFailure.runtime.progressivePromotion, false);
assert.equal(promotionFailure.state.filteredMappedCatalog.length, 1, "Failed promotion restores the verified initial population");
assert.match(promotionFailure.startup.backgroundError, /Full map render failed/);
assert.equal(promotionFailure.startup.errorText, "");
await promotionFailure.context.startProgressiveCatalogBackground();
assert.equal(promotionFailure.startup.fullCatalogReady, true, "Promotion failure remains recoverable by retry");

const tracePending = fixture(), traceGate = deferred();
tracePending.context.ensureCanonicalTraceArtifactLoaded = () => traceGate.promise;
tracePending.initialVisuals.resolve(); await tracePending.context.initializeProgressiveStartup();
tracePending.background.resolve(); await flush();
assert.equal(tracePending.startup.mapViewReady, true);
assert.equal(tracePending.startup.fullCatalogReady, false, "Complete catalog rows alone cannot bypass the pending full trace gate");
assert.equal(tracePending.analysisEnabled, false);
traceGate.resolve({ ready: true }); await tracePending.runtime.progressiveBackgroundPromise;
assert.equal(tracePending.startup.fullCatalogReady, true);

const optIn = fixture();
assert.equal(optIn.context.progressiveStartupRequested(), true);
for (const search of ["", "?progressiveStartup=0", "?progressiveStartup=1&autosearch=ariel", "?progressiveStartup=1&autoselect=first"]) {
  optIn.context.window.location.search = search;
  assert.equal(optIn.context.progressiveStartupRequested(), false, "Original startup remains available: " + search);
}
const realBackground = fixture();
realBackground.startup.progressiveEnabled = true;
realBackground.startup.mapViewReady = true;
realBackground.startup.previewInteractive = true;
realBackground.runtime.catalogSource = "canonical_web";
realBackground.runtime.canonicalWebArtifacts.chunkManifest = [{}];
realBackground.runtime.traceChronologyStatus = "ready";
realBackground.runtime.encounterStatus = "ready";
realBackground.state.timeRangeStartOrdinal = 115;
realBackground.state.timeRangeEndOrdinal = 185;
for (const name of ["loadTraceChronologyEvidence", "loadEncounterEvidence", "loadLocationLabelOverlayRuntime",
  "loadPackedPointsRuntime", "loadAndIngestCanonicalSummaryShards"])
  realBackground.context[name] = async () => {};
realBackground.context.canonicalWebArtifactsPrimaryCatalogRequested = () => true;
realBackground.context.validatePackedPointsCatalogParity = () => ({ ok: true });
for (const name of ["renderStartupDiagnostics", "updateCatalogLoadingMessage", "setSearchStatus"])
  realBackground.context[name] = () => {};
realBackground.context.resolveInitialTimeRangePreference = () => assert.fail("Background completion cannot restore initial dates");
vm.runInContext(actualFunction("loadCatalog"), realBackground.context);
await realBackground.context.loadCatalog();
assert.equal(realBackground.runtime.traceChronologyEvidence.scope, "full catalog",
  "Actual hydration explicitly restores the full index from cached preparation after scoped timing had ownership");
assert.equal(realBackground.runtime.progressiveHydrating, true);
assert.equal(realBackground.state.timeRangeStartOrdinal, 115);
assert.equal(realBackground.state.timeRangeEndOrdinal, 185);
assert.equal(realBackground.calls.includes("initializeMap"), false, "Actual background loader does not recreate the map");
assert.equal(realBackground.calls.includes("setTimeRange"), false, "Actual background loader does not reapply the initial date window");
assert.deepEqual(realBackground.viewport, { center: [10, 20], zoom: 4 });
// The scoped profile spans exactly the selected initial dates. It must remain a
// custom window, rather than being mistaken for the full corpus and expanding
// to all dates when applyFilteredCatalogState later reconciles the new extent.
const day = value => Math.floor(Date.parse(value + "T00:00:00Z") / 86400000);
const initialStart = day("1954-09-01"), initialEnd = day("1954-11-30");
const scopedExtent = { minOrdinal: initialStart, maxOrdinal: initialEnd };
const expandedExtent = { minOrdinal: initialStart - 700000, maxOrdinal: day("2026-04-11") };
const dateState = { timeRangeStartOrdinal: null, timeRangeEndOrdinal: null, timeRangeMode: "custom",
  filteredTimelineExtent: scopedExtent, fullCatalogExtent: scopedExtent, visibleTimelineExtent: scopedExtent };
const dateStartup = { progressiveEnabled: true, fullCatalogReady: false };
const dateRuntime = { progressivePromotion: false };
const dateContext = vm.createContext({ state: dateState, startup: dateStartup, runtime: dateRuntime,
  Math, clamp: (value, min, max) => Math.max(min, Math.min(value, max)) });
for (const name of ["ensureVisibleTimelineExtentContainsSelection", "clampVisibleTimelineExtent", "setTimeInputsFromState",
  "syncPlaybackWindowSelection", "updateTimelinePresetButtonStates", "invalidatePackedMapLayerCache",
  "refreshTemporalOverlayLayersForCurrentWindow"]) dateContext[name] = () => {};
for (const name of ["progressiveInitialMapActive", "selectionClampExtent", "setTimeRange", "reconcileTimeRangeWithExtent"])
  vm.runInContext(actualFunction(name), dateContext);
dateContext.setTimeRange(initialStart, initialEnd, { mode: "custom", autofitVisible: false, clampAnchor: "start" });
assert.equal(dateState.timeRangeMode, "custom", "Selecting the entire scoped extent must not mean All Time");
assert.equal(dateState.timeRangeStartOrdinal, initialStart);
assert.equal(dateState.timeRangeEndOrdinal, initialEnd);
dateState.fullCatalogExtent = expandedExtent;
dateState.filteredTimelineExtent = expandedExtent;
dateRuntime.progressivePromotion = true;
dateContext.reconcileTimeRangeWithExtent();
assert.equal(dateState.timeRangeMode, "custom", "Full-catalog reconciliation preserves the scoped window mode");
assert.equal(dateState.timeRangeStartOrdinal, initialStart);
assert.equal(dateState.timeRangeEndOrdinal, initialEnd, "Promotion cannot widen the initial window to all corpus dates");
dateStartup.fullCatalogReady = true;
dateRuntime.progressivePromotion = false;
dateContext.reconcileTimeRangeWithExtent();
assert.equal(dateState.timeRangeStartOrdinal, initialStart);
assert.equal(dateState.timeRangeEndOrdinal, initialEnd);
dateContext.setTimeRange(expandedExtent.minOrdinal, expandedExtent.maxOrdinal, { mode: "custom", autofitVisible: false });
assert.equal(dateState.timeRangeMode, "full", "The existing full-extent shortcut still works after the global catalog is ready");
const unsortedProfile = [
  { event_id: "late", sort_ordinal: 3, date_precision: "exact_day", has_coordinates: true },
  { event_id: "early", sort_ordinal: 1, date_precision: "exact_day", has_coordinates: true },
];
const orderRuntime = { progressivePromotion: false, progressiveEvents: unsortedProfile, catalogExactDayAscending: true };
const orderStartup = { progressiveEnabled: true, fullCatalogReady: false };
const orderState = { timelineDataVersion: 0, filterGeneration: 0, fullCatalogExtent: { minOrdinal: 1, maxOrdinal: 3 } };
const orderContext = vm.createContext({ runtime: orderRuntime, startup: orderStartup, state: orderState,
  catalog: unsortedProfile.slice().reverse(), Map,
  currentFilterSelections: () => ({ keyword: "", legendColorMode: "craft_type" }),
  filtersWithoutMapLegendEventSelection: value => value,
  eventMatchesNonDateFilters: () => true, eventMatchesTimeRange: () => true,
  eventLegendKeyForMode: () => "disc", eventComparatorAscending: (left, right) => left.sort_ordinal - right.sort_ordinal,
  sortFilteredCatalog: rows => rows.slice().sort((left, right) => left.sort_ordinal - right.sort_ordinal),
  ordinalToIso: value => String(value), reconcileTimeRangeWithExtent() {}, ensureVisibleTimelineExtentContainsSelection() {},
});
for (const name of ["progressiveInitialMapActive", "buildFilteredCatalogState", "applyFilteredCatalogState"])
  vm.runInContext(actualFunction(name), orderContext);
const scopedFilter = orderContext.buildFilteredCatalogState(null);
assert.equal(scopedFilter.preserveDateAscending, false, "Unsorted scoped rows cannot borrow the global catalog's sorted flag");
orderContext.applyFilteredCatalogState(scopedFilter.baseCatalog, scopedFilter.keywordActive,
  { preserveDateAscending: scopedFilter.preserveDateAscending });
assert.deepEqual(Array.from(orderState.timelinePlaybackEvents, row => row.event_id), ["early", "late"],
  "Actual scoped timeline construction sorts oldest first rather than trusting profile source order");
orderStartup.fullCatalogReady = true;
assert.equal(orderContext.buildFilteredCatalogState(null).preserveDateAscending, true,
  "The canonical catalog retains its existing verified ordering optimization");
const overlay = { hidden: false }, overlayStartup = { phase: "Preparing default map", progressiveEnabled: true,
  mapViewReady: false, initialViewReady: false, fullCatalogReady: false, errorText: "", backgroundError: "" };
const overlayContext = vm.createContext({ startup: overlayStartup,
  runtime: { mapStartupOverlayVisibleSince: 1000, mapStartupOverlayHideTimerId: null },
  els: { mapStartupOverlay: overlay }, MAP_STARTUP_OVERLAY_MIN_VISIBLE_MS: 900,
  performance: { now: () => 2000 }, document: { documentElement: { setAttribute() {} } },
  window: { setTimeout: () => 1, clearTimeout() {} } });
vm.runInContext(actualFunction("renderMapStartupOverlay"), overlayContext);
overlayContext.renderMapStartupOverlay(30);
assert.equal(overlay.hidden, false);
overlayStartup.initialViewReady = true;
overlayContext.renderMapStartupOverlay(100);
assert.equal(overlay.hidden, false, "A provisional visual alone cannot open the progressive map");
overlayStartup.mapViewReady = true;
overlayStartup.phase = "Map ready";
overlayContext.renderMapStartupOverlay(100);
assert.equal(overlay.hidden, true, "The complete initial map can open before the full catalog");
overlayStartup.phase = "Loading report evidence";
overlayContext.renderMapStartupOverlay(20);
assert.equal(overlay.hidden, true, "Background progress never restores the initial cover");
overlayStartup.backgroundError = "A summary shard is unavailable";
overlayStartup.phase = "Map ready";
overlayContext.renderMapStartupOverlay(100);
assert.equal(overlay.hidden, true, "Background failure leaves the verified map usable");
overlayStartup.errorText = "Initial map was not verified";
overlayContext.renderMapStartupOverlay(100);
assert.equal(overlay.hidden, false, "A true initial-view failure retains the error cover");
console.log("Actual progressive startup separates map/full readiness, waits for initial visuals, preserves map/date/filter state, and recovers background or promotion failures without replacing the loading cover.");
