import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
import { isoToOrdinal, ordinalToIso } from "../webapp/static/app-utils.mjs";

const require = createRequire(import.meta.url);
const directions = require("../trace_direction_summary.js");
const cases = require("../famous_case_presets.js");
const neighborhood = require("../trace_neighborhood.js");
const legend = require("../legend_controls.js");
const playbackPerformance = require("../playback_performance.js");
const source = readFileSync(new URL("../app.js", import.meta.url), "utf8");
const index = readFileSync(new URL("../index.html", import.meta.url), "utf8");

function extractFunction(name) {
  let start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `missing integration function ${name}`);
  if (source.slice(start - 6, start) === "async ") start -= 6;
  const brace = source.indexOf("{", start);
  let depth = 0;
  for (let position = brace; position < source.length; position += 1) {
    if (source[position] === "{") depth += 1;
    if (source[position] === "}") depth -= 1;
    if (!depth) return source.slice(start, position + 1);
  }
  assert.fail(`unterminated function ${name}`);
}

function extractControlBlock(signature, occurrence = "first") {
  const start = occurrence === "last" ? source.lastIndexOf(signature) : source.indexOf(signature);
  assert.notEqual(start, -1, `missing control block ${signature}`);
  const brace = source.indexOf("{", start);
  let depth = 0;
  for (let position = brace; position < source.length; position += 1) {
    if (source[position] === "{") depth += 1;
    if (source[position] === "}") depth -= 1;
    if (!depth) return source.slice(start, position + 1);
  }
  assert.fail(`unterminated control block ${signature}`);
}

function loadFunctions(names, overrides) {
  const context = vm.createContext({ Array, Boolean, JSON, Map, Math, Number, Object, Set, String, ...overrides });
  vm.runInContext(names.map(extractFunction).join("\n"), context);
  return context;
}

const clone = value => JSON.parse(JSON.stringify(value));
const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
const noOp = () => {};

function casePanelElement() {
  let markup = "";
  return {
    hidden: true, writes: 0, handlers: {}, details: null,
    get innerHTML() { return markup; },
    set innerHTML(value) {
      markup = value;
      this.writes += 1;
      this.details = value.includes("data-case-results-details") ? {
        open: /<details\b[^>]*\bopen(?:\s|>)/.test(value),
        matches: selector => selector === "[data-case-results-details]",
        hasAttribute: attribute => attribute === "data-case-results-details",
      } : null;
    },
    querySelector(selector) { return selector === "[data-case-results-details]" ? this.details : null; },
    addEventListener(name, handler, capture) { this.handlers[name] = { handler, capture }; },
  };
}

function caseHarness() {
  let mapZoom = 5.25;
  const originalRegion = { shapes: [{ id: "user-area", type: "circle", center: { lat: 42, lng: -70 }, radiusMeters: 40000 }], drawingActive: true, modeActive: true, depth: 3, direction: "both", pointOnly: false };
  const state = { famousCaseId: "", famousCaseOrder: "alphabetical", regionSelection: originalRegion, analysisCountryAreaFilter: "Canada", timeRangeStartOrdinal: isoToOrdinal("2000-01-01"), timeRangeEndOrdinal: isoToOrdinal("2010-12-31"), timeRangeMode: "custom", traceMode: "off", traceBucketVisibility: { gap_le_1: false, gap_le_2: true, gap_le_7: false }, timelineDataVersion: 0, filterGeneration: 0, lastKeyword: "", lastKeywordMatches: null };
  const runtime = { map: {
    getZoom() { return mapZoom; },
    setView(center, zoom) { mapZoom = zoom; calls.views.push({ center: [...center], zoom }); },
    panTo(center, options) { calls.pans.push({ center: [...center], options: clone(options) }); },
  }, traceIntersectionController: { notifyTraceModeChanged(mode) { calls.modeNotifications.push(mode); }, notifyTimelineRangeChanged: noOp } };
  const orderButtons = ["alphabetical", "chronological"].map(order => ({ dataset: { famousCaseOrder: order }, attributes: {}, setAttribute(name, value) { this.attributes[name] = value; } }));
  const els = { keywordInput: { value: "existing research query" }, famousCaseSearch: { value: "" }, famousCaseOrderButtons: orderButtons, famousCaseSearchStatus: { textContent: "" }, filterFamousCases: { innerHTML: "", value: "" }, famousCaseDetails: casePanelElement(), resultsFamousCaseSummary: casePanelElement() };
  const calls = { refreshes: 0, views: [], pans: [], pulses: [], pulseClears: 0, areaRefreshes: 0, shapeIds: 0, drawingStops: 0, modeNotifications: [], playbackClears: 0, traceFits: 0, coveragePointChecks: 0 };
  const control = { extent: { minOrdinal: isoToOrdinal("1500-01-01"), maxOrdinal: isoToOrdinal("2030-12-31") }, result: { selectedEventCount: 2, visibleTraceCount: 1 }, facilityEnabled: false, catalog: [],
    startup: { phase: "Ready", totalCatalogShards: 1, ingestedCatalogShards: 1 },
    filters: { keyword: "", sourceMode: "all", typeMode: "all", precisionMode: "all", selectedSources: new Set(), selectedTypes: new Set(), selectedPrecisions: new Set(), hideLowPrecision: false, hideNonExactDates: false } };
  const context = loadFunctions([
    "timelinePresetMatchesCurrentRange", "updateTimelinePresetButtonStates", "setTimeRange",
    "renderFamousCasePicker", "renderFamousCaseResultsSummary", "famousCaseCatalogEntries", "renderFamousCaseCatalogEntries", "bindFamousCaseActions", "clearFamousCasePreset", "applyFamousCasePreset", "applyAnalysisAreaFilter", "applyTimelinePreset", "applyFullTimeRange",
    "famousCaseTraceSelectionActive", "famousCaseTraceStatusText", "currentFamousCaseVicinityCoverage", "famousCaseVicinityCoverageText", "normalizeTraceMode", "traceBucketActive", "setTraceMode",
    "eventMatchesTimeRange", "eventMatchesNonDateFilters", "worldIndicesNearReferenceLongitude", "wrappedLongitudesNearReference", "localProjectedMeters", "pointInsideCircleShape", "pointInsideRegionShape", "regionSelectionShapeBounds", "pointMayIntersectRegionShapeBounds",
  ], {
    state, runtime, els, FAMOUS_CASES: cases, isoToOrdinal, ordinalToIso, escapeHtml, clamp,
    formatNumber: String,
    catalog: control.catalog, startup: control.startup,
    getCatalogEventById: () => null,
    currentFilterSelections: () => control.filters,
    eventMatchesMapLegendEventSelection: () => true,
    LOW_PRECISION_VALUES: new Set(["country", "state_province", "approximate", "unknown"]),
    REGION_SELECTION_EARTH_RADIUS_METERS: 6371008.8,
    normalizeLongitude: value => ((((Number(value) + 180) % 360) + 360) % 360) - 180,
    selectionClampExtent() { return control.extent; },
    setRegionSelectionDrawingActive(active) { state.regionSelection.drawingActive = active; state.regionSelection.modeActive = active; calls.drawingStops += 1; },
    refreshRegionSelectionRenderState() { calls.areaRefreshes += 1; },
    nextRegionSelectionShapeId() { return "case-area-" + (++calls.shapeIds); },
    scheduleRefresh() { calls.refreshes += 1; },
    scheduleCurrentTimeRangeState() { calls.refreshes += 1; },
    setTimeInputsFromState: noOp, syncPlaybackWindowSelection: noOp,
    ensureVisibleTimelineExtentContainsSelection: noOp, clampVisibleTimelineExtent: noOp,
    invalidatePackedMapLayerCache: noOp, refreshTemporalOverlayLayersForCurrentWindow: noOp,
    clearPendingDateInputEdits: noOp, setDateRangeFeedback: noOp, resetPlayback: noOp,
    clearCraftLegendSoloState: noOp, invalidatePlaybackForTimeChange: noOp,
    invalidateRegionSelectionResult: noOp, renderRegionSelectionShapes: noOp, renderRegionSelectionUi: noOp,
    currentRegionSelectionResult: () => control.result,
    traceFacilityFilterEnabled: () => control.facilityEnabled,
    invalidateTraceSequenceCache() { runtime.traceSequenceCacheKey = ""; runtime.traceSequenceCacheValue = null; },
    clearPlaybackTrailHistory() { calls.playbackClears += 1; },
    pulseFamousCaseCircle() { calls.pulses.push(runtime.famousCaseShapeId); },
    clearFamousCaseCirclePulse() { calls.pulseClears += 1; },
    fitFamousCaseTraces() { calls.traceFits += 1; },
    renderTraceControls: noOp, traceLinkedOrRegionVisibilityAffectsRendering: () => false,
    renderTraceLinkedVisibilityUi: noOp, renderStaticTraceLayer: noOp, renderPlaybackStatus: noOp,
    renderPrimaryFiltersFlapStatus: noOp,
    TIMELINE_WINDOW_PRESET_BUTTONS: [], TIMELINE_FLAP_PRESET_BUTTONS: [],
    TIMELINE_PRESET_BY_ID: new Map([
      ["test-flap", { kind: "fixed", startIso: "1954-09-01", endIso: "1954-11-30" }],
      ["test-rolling", { kind: "rolling", days: 7 }],
    ]),
  });
  const pointInside = context.pointInsideRegionShape;
  context.pointInsideRegionShape = function (...arguments_) { calls.coveragePointChecks += 1; return pointInside(...arguments_); };
  return { context, state, runtime, els, calls, control, originalRegion };
}

const kecksberg = cases.filterCases("Kecksberg")[0];
const ariel = cases.filterCases("Ariel School")[0];
assert.ok(kecksberg && ariel, "requested case examples are available");

const harness = caseHarness();
const originalDates = [harness.state.timeRangeStartOrdinal, harness.state.timeRangeEndOrdinal];
const originalZoom = harness.runtime.map.getZoom();
const sourceCaseSnapshot = JSON.stringify(kecksberg);
harness.context.applyFamousCasePreset(kecksberg.id);
assert.equal(harness.state.famousCaseId, kecksberg.id);
assert.equal(harness.state.timeRangeStartOrdinal, isoToOrdinal(kecksberg.startIso) - 1, "case navigation includes the preceding calendar day");
assert.equal(harness.state.timeRangeEndOrdinal, isoToOrdinal(kecksberg.endIso) + 1, "case navigation includes the following calendar day");
assert.equal(JSON.stringify(kecksberg), sourceCaseSnapshot, "context padding never changes the sourced case dates");
assert.equal(harness.runtime.map.getZoom(), originalZoom, "case navigation preserves the user's current zoom");
assert.deepEqual(harness.calls.views, [], "case selection does not call a zoom-changing map view method");
assert.deepEqual(harness.calls.pans, [{ center: [...kecksberg.center], options: { animate: false } }], "case selection centers the map at its current scale");
assert.deepEqual(harness.calls.pulses, [harness.runtime.famousCaseShapeId], "the brief circle highlight follows the case-owned vicinity");
assert.equal(harness.state.regionSelection.pointOnly, false, "case reports can anchor same-day, same-type connections");
assert.equal(harness.state.regionSelection.selectTraces, false);
assert.equal(harness.state.regionSelection.selectEvents, true, "case vicinity seeds reports, not crossing lines");
assert.equal(harness.state.regionSelection.showSelectedEvents, true);
assert.equal(harness.state.regionSelection.showTracesAssociatedWithSelectedEvents, true);
assert.equal(harness.state.regionSelection.showEventsAssociatedWithSelectedTraces, false);
assert.equal(harness.state.regionSelection.depth, 0, "case links stay incident to local reports without an extra neighborhood walk");
assert.equal(harness.state.traceMode, "static");
assert.equal(harness.state.traceBucketVisibility.gap_le_1, true);
assert.equal(harness.context.famousCaseTraceSelectionActive(), true);
assert.equal(harness.state.regionSelection.drawingActive, false, "case selection exits area drawing");
assert.equal(harness.state.regionSelection.shapes[0].type, "circle");
assert.equal(harness.state.regionSelection.shapes[0].radiusMeters, kecksberg.radiusKm * 1000);
assert.equal(harness.runtime.famousCaseShapeId, harness.state.regionSelection.shapes[0].id);
assert.equal(harness.els.keywordInput.value, "existing research query", "case navigation does not trigger a full-corpus keyword search");
harness.context.renderFamousCaseResultsSummary();
assert.ok(harness.els.famousCaseDetails.innerHTML.includes(escapeHtml(kecksberg.name)), "the compact left control retains the selected case name");
assert.match(harness.els.famousCaseDetails.innerHTML, /data-clear-famous-case/);
assert.ok(!harness.els.famousCaseDetails.innerHTML.includes(escapeHtml(kecksberg.description)), "case background appears in Results without duplicating it in the left controls");
assert.ok(!/famous-case-(?:location|dates|scope|trace-status|sources)|data-fit-famous-case-traces/.test(harness.els.famousCaseDetails.innerHTML), "the left case control stays compact");
assert.match(harness.els.resultsFamousCaseSummary.innerHTML, /Candidate reports, not verified case matches/);
assert.match(harness.els.resultsFamousCaseSummary.innerHTML, /1 same-day connection/);
assert.match(harness.els.resultsFamousCaseSummary.innerHTML, /data-fit-famous-case-traces/);
assert.ok(harness.els.resultsFamousCaseSummary.innerHTML.includes(escapeHtml(kecksberg.description)));
assert.ok(harness.els.resultsFamousCaseSummary.innerHTML.includes(escapeHtml(kecksberg.location)));
assert.ok(kecksberg.sources.every(item => harness.els.resultsFamousCaseSummary.innerHTML.includes(escapeHtml(item.url))), "Results retains the case sources");
assert.equal(harness.els.resultsFamousCaseSummary.details.open, false, "longer case context starts collapsed");
const previousSnapshot = harness.runtime.famousCasePreviousSelection;
harness.context.applyFamousCasePreset(ariel.id);
assert.equal(harness.runtime.famousCasePreviousSelection, previousSnapshot, "switching cases preserves the user's original selection");
assert.equal(harness.state.famousCaseId, ariel.id, "switching does not let the previous case clear the new area");
assert.equal(harness.state.regionSelection.shapes[0].radiusMeters, ariel.radiusKm * 1000);
assert.equal(harness.runtime.map.getZoom(), originalZoom, "switching cases also preserves zoom");
assert.equal(harness.calls.pulses.at(-1), harness.runtime.famousCaseShapeId, "switching cases highlights the new vicinity");
harness.context.clearFamousCasePreset();
assert.equal(harness.state.famousCaseId, "");
assert.deepEqual([harness.state.timeRangeStartOrdinal, harness.state.timeRangeEndOrdinal], originalDates);
assert.equal(harness.state.regionSelection.shapes[0].id, "user-area");
assert.equal(harness.state.regionSelection.depth, 3);
assert.equal(harness.state.regionSelection.direction, "both");
assert.equal(harness.state.regionSelection.drawingActive, false, "clear restores the prior filter without resuming pointer drawing");
assert.equal(harness.state.analysisCountryAreaFilter, "Canada");
assert.equal(harness.runtime.famousCasePreviousSelection, null);
assert.equal(harness.els.famousCaseDetails.hidden, true);
harness.context.renderFamousCaseResultsSummary();
assert.equal(harness.els.resultsFamousCaseSummary.hidden, true);
assert.equal(harness.els.resultsFamousCaseSummary.innerHTML, "", "explicit Clear removes the case context from Results");
assert.equal(harness.state.traceMode, "off", "Clear restores the pre-case trace mode");
assert.equal(harness.state.traceBucketVisibility.gap_le_1, false, "Clear restores the pre-case same-day bucket");
assert.equal(harness.state.traceBucketVisibility.gap_le_2, true, "other gap buckets remain independent");
assert.ok(harness.calls.pulseClears > 0, "explicit Clear cancels any pending vicinity highlight");
assert.deepEqual(harness.calls.modeNotifications, ["static", "static", "off"], "mode changes also reach the convergence-layer controller");

const caseSummary = caseHarness();
const summaryOriginalDates = [caseSummary.state.timeRangeStartOrdinal, caseSummary.state.timeRangeEndOrdinal];
caseSummary.context.bindFamousCaseActions(caseSummary.els.famousCaseDetails);
caseSummary.context.bindFamousCaseActions(caseSummary.els.resultsFamousCaseSummary);
caseSummary.context.applyFamousCasePreset(kecksberg.id);
caseSummary.context.renderFamousCaseResultsSummary();
const summaryPanel = caseSummary.els.resultsFamousCaseSummary;
assert.equal(summaryPanel.hidden, false);
assert.equal(summaryPanel.handlers.toggle.capture, true, "the Results disclosure uses the actual non-bubbling toggle event in capture mode");
const firstDetails = summaryPanel.details;
firstDetails.open = true;
summaryPanel.handlers.toggle.handler({ target: firstDetails });
assert.equal(caseSummary.runtime.famousCaseResultsDetailsOpen, true);
const initialSummaryWrites = summaryPanel.writes;
caseSummary.els.famousCaseSearch.value = "Zimbabwe";
caseSummary.context.renderFamousCasePicker();
caseSummary.context.renderFamousCaseResultsSummary();
assert.equal(summaryPanel.writes, initialSummaryWrites, "catalog search and unchanged refreshes preserve the native Results disclosure node");
assert.equal(summaryPanel.details, firstDetails);
assert.equal(summaryPanel.details.open, true);
const summaryCaseArea = clone(caseSummary.state.regionSelection);
caseSummary.context.setTimeRange(isoToOrdinal("1989-11-01"), isoToOrdinal("1990-04-30"), { mode: "custom" });
caseSummary.control.result = { selectedEventCount: 4, visibleTraceCount: 2 };
caseSummary.context.renderFamousCaseResultsSummary();
assert.equal(caseSummary.state.famousCaseId, kecksberg.id);
assert.deepEqual(clone(caseSummary.state.regionSelection), summaryCaseArea, "Results date refresh preserves the case's area and trace settings");
assert.equal(caseSummary.state.traceMode, "static");
assert.equal(caseSummary.state.traceBucketVisibility.gap_le_1, true);
assert.match(summaryPanel.innerHTML, /Viewing 1989-11-01 to 1990-04-30/);
assert.ok(summaryPanel.innerHTML.includes("Reported " + escapeHtml(cases.formatCaseDate(kecksberg))), "the historical case date remains separate from the active viewing range");
assert.match(summaryPanel.innerHTML, /2 same-day connections/);
assert.equal(summaryPanel.details.open, true, "a changed date or count retains the user's open case context");
summaryPanel.handlers.click.handler({ target: { closest: selector => selector === "[data-fit-famous-case-traces]" ? {} : null } });
assert.equal(caseSummary.calls.traceFits, 1, "the Fit control in Results invokes the actual delegated action");
assert.equal(caseSummary.state.famousCaseId, kecksberg.id);
caseSummary.control.result = { selectedEventCount: 1, visibleTraceCount: 0 };
caseSummary.context.renderFamousCaseResultsSummary();
assert.match(summaryPanel.innerHTML, /no same-day, same-type connections are available/);
assert.match(summaryPanel.innerHTML, /data-fit-famous-case-traces disabled/, "Results disables Fit when current filters leave no connections");
assert.equal(summaryPanel.details.open, true);
caseSummary.context.applyFamousCasePreset(ariel.id);
caseSummary.context.renderFamousCaseResultsSummary();
assert.ok(summaryPanel.innerHTML.includes(escapeHtml(ariel.name)));
assert.ok(summaryPanel.innerHTML.includes(escapeHtml(ariel.description)));
assert.ok(!summaryPanel.innerHTML.includes(escapeHtml(kecksberg.description)), "switching cases replaces Results context rather than accumulating old prose");
assert.equal(summaryPanel.details.open, false, "a newly selected case starts with its longer context collapsed");
assert.equal(caseSummary.runtime.famousCaseResultsDetailsOpen, false);
caseSummary.els.famousCaseDetails.handlers.click.handler({ target: { closest: selector => selector === "[data-clear-famous-case]" ? {} : null } });
caseSummary.context.renderFamousCaseResultsSummary();
assert.equal(caseSummary.state.famousCaseId, "", "Clear remains available in the compact left controls");
assert.deepEqual([caseSummary.state.timeRangeStartOrdinal, caseSummary.state.timeRangeEndOrdinal], summaryOriginalDates);
assert.equal(caseSummary.state.regionSelection.shapes[0].id, "user-area");
assert.equal(caseSummary.state.traceMode, "off");
assert.equal(caseSummary.state.traceBucketVisibility.gap_le_1, false);
assert.equal(caseSummary.els.famousCaseDetails.hidden, true);
assert.equal(summaryPanel.hidden, true);
assert.equal(summaryPanel.innerHTML, "");
assert.equal(caseSummary.runtime.famousCaseResultsDetailsOpen, false);
assert.equal(caseSummary.runtime.famousCaseResultsContextId, "");

const editedArea = caseHarness();
editedArea.context.applyFamousCasePreset(kecksberg.id);
editedArea.state.regionSelection.shapes = [{ id: "new-user-area", type: "rectangle" }];
editedArea.context.clearFamousCasePreset();
assert.equal(editedArea.state.regionSelection.shapes[0].id, "new-user-area", "clearing a case cannot overwrite a subsequently edited area");

const changedTraceMode = caseHarness();
changedTraceMode.context.applyFamousCasePreset(kecksberg.id);
changedTraceMode.context.setTraceMode("playback");
assert.equal(changedTraceMode.runtime.famousCaseTraceModeOwned, false, "a user trace-mode change releases case ownership");
changedTraceMode.context.clearFamousCasePreset();
assert.equal(changedTraceMode.state.traceMode, "playback", "Clear preserves the user's later trace mode");
assert.equal(changedTraceMode.state.traceBucketVisibility.gap_le_1, false, "unchanged case-owned controls still restore independently");

const changedBucket = caseHarness();
changedBucket.context.applyFamousCasePreset(kecksberg.id);
const bucketButtons = ["gap_le_1", "gap_le_2"].map(key => ({ key, handlers: {}, getAttribute() { return key; }, addEventListener(name, handler) { this.handlers[name] = handler; } }));
changedBucket.els.traceBucketButtons = bucketButtons;
changedBucket.context.traceBucketForKey = key => ({ key });
vm.runInContext(extractControlBlock("if (els.traceBucketButtons && els.traceBucketButtons.length) {", "last"), changedBucket.context);
bucketButtons[0].handlers.click();
assert.equal(changedBucket.runtime.famousCaseGapBucketOwned, false, "the real same-day bucket handler releases case ownership");
assert.match(changedBucket.context.famousCaseTraceStatusText(changedBucket.control.result, true), /Same-day traces are disabled/);
bucketButtons[0].handlers.click();
bucketButtons[1].handlers.click();
changedBucket.context.clearFamousCasePreset();
assert.equal(changedBucket.state.traceBucketVisibility.gap_le_1, true, "Clear preserves the user's explicitly re-enabled same-day bucket");
assert.equal(changedBucket.state.traceBucketVisibility.gap_le_2, false, "unrelated later bucket changes survive Clear");
assert.equal(changedBucket.state.traceMode, "off", "unchanged case-owned trace mode restores independently");

const traceStatus = caseHarness();
traceStatus.context.applyFamousCasePreset(kecksberg.id);
assert.match(traceStatus.context.famousCaseTraceStatusText({ selectedEventCount: 1, visibleTraceCount: 0 }, true), /1 report.*no same-day, same-type connections/);
traceStatus.control.facilityEnabled = true;
assert.match(traceStatus.context.famousCaseTraceStatusText({ selectedEventCount: 1, visibleTraceCount: 0 }, true), /Facility proximity also filters connections/);
assert.match(traceStatus.context.famousCaseTraceStatusText({ selectedEventCount: 0, visibleTraceCount: 0 }, true), /No mapped reports in this vicinity/);
traceStatus.context.setTraceMode("off");
assert.match(traceStatus.context.famousCaseTraceStatusText(traceStatus.control.result, true), /Case traces are off/);
assert.match(traceStatus.context.famousCaseTraceStatusText(traceStatus.control.result, false), /vicinity cleared or edited/);

const coverage = caseHarness();
coverage.context.applyFamousCasePreset(kecksberg.id);
const coverageShape = coverage.state.regionSelection.shapes[0];
const coverageDate = isoToOrdinal(kecksberg.startIso);
const coverageReport = (id, extra = {}) => ({ event_id: id, has_coordinates: true,
  lat: coverageShape.center.lat, lon: coverageShape.center.lng, sort_ordinal: coverageDate,
  source: "ufocat", type: "Diamond", location_precision: "city", date_precision: "exact_day", ...extra });
coverage.control.catalog.push(
  coverageReport("inside-one"),
  coverageReport("inside-two", { lat: coverageShape.center.lat + 0.1, type: "Unknown", date_precision: "month", location_precision: "country" }),
  coverageReport("elsewhere", { lat: coverageShape.center.lat + 2 }),
  coverageReport("different-date", { sort_ordinal: coverageDate + 30 }),
  coverageReport("unmapped", { has_coordinates: false, lat: null, lon: null }),
  coverageReport("invalid-coordinate", { lat: null }),
);
coverage.control.filters.selectedTypes = new Set(["Triangle"]);
let coverageResult = coverage.context.currentFamousCaseVicinityCoverage();
assert.equal(coverageResult.status, "ready");
assert.equal(coverageResult.mappedCount, 2, "coverage ignores current report filters but requires valid mapped points in the current date window and circle");
assert.equal(coverageResult.includedCount, 0);
assert.equal(coverageResult.excludedCount, 2);
const cachedCoverageEvents = coverage.runtime.famousCaseVicinityCoverageCacheValue;
const initialCoveragePointChecks = coverage.calls.coveragePointChecks;
coverage.context.currentFamousCaseVicinityCoverage();
assert.equal(coverage.runtime.famousCaseVicinityCoverageCacheValue, cachedCoverageEvents);
assert.equal(coverage.calls.coveragePointChecks, initialCoveragePointChecks, "unchanged coverage reuses its date/geometry scan");
coverage.context.setTraceMode("off");
assert.match(coverage.context.famousCaseTraceStatusText({ selectedEventCount: 0, visibleTraceCount: 0 }, true), /2 mapped vicinity reports hidden by current filters/);
assert.ok(!coverage.context.famousCaseTraceStatusText({ selectedEventCount: 0, visibleTraceCount: 0 }, true).includes("Case traces are off"), "zero-record coverage explains missing results before trace visibility hints");
coverage.control.filters.selectedTypes = new Set();
coverageResult = coverage.context.currentFamousCaseVicinityCoverage();
assert.equal(coverageResult.includedCount, 2, "filter changes reevaluate the cached vicinity cohort with the actual UI predicate");
assert.equal(coverageResult.excludedCount, 0);
assert.equal(coverage.calls.coveragePointChecks, initialCoveragePointChecks, "filter changes do not rescan the unfiltered catalog");
coverage.control.filters.hideNonExactDates = true;
assert.equal(coverage.context.currentFamousCaseVicinityCoverage().excludedCount, 1, "non-exact date filtering is included in the diagnostic");
coverage.control.filters.hideNonExactDates = false;
coverage.control.filters.keyword = "specific";
coverage.state.lastKeyword = "specific";
coverage.state.lastKeywordMatches = new Set(["inside-one"]);
assert.equal(coverage.context.currentFamousCaseVicinityCoverage().includedCount, 1, "coverage uses full-text keyword membership rather than guessing from summary text");
coverage.state.lastKeyword = "old search";
assert.match(coverage.context.famousCaseVicinityCoverageText(coverage.context.currentFamousCaseVicinityCoverage()), /Updating filters/, "pending keyword matches do not become a definitive hidden-report count");
coverage.control.filters.keyword = "";
coverage.state.lastKeyword = "";
coverage.state.lastKeywordMatches = null;
coverageShape.radiusMeters = 1;
coverageResult = coverage.context.currentFamousCaseVicinityCoverage();
assert.equal(coverageResult.mappedCount, 1, "changing the circle radius invalidates unfiltered coverage");
assert.notEqual(coverage.runtime.famousCaseVicinityCoverageCacheValue, cachedCoverageEvents);
const radiusCache = coverage.runtime.famousCaseVicinityCoverageCacheValue;
coverageShape.center.lng += 10;
coverageResult = coverage.context.currentFamousCaseVicinityCoverage();
assert.equal(coverageResult.mappedCount, 0, "changing the circle center invalidates coverage");
assert.notEqual(coverage.runtime.famousCaseVicinityCoverageCacheValue, radiusCache);
const emptyCoverageText = coverage.context.famousCaseTraceStatusText({ selectedEventCount: 0, visibleTraceCount: 0 }, true);
assert.match(emptyCoverageText, /before filters/);
assert.ok(!/case is absent|case is missing|not in the database/.test(emptyCoverageText), "vicinity coverage does not infer historical case identity or database absence");
assert.ok(!emptyCoverageText.includes("Case traces are off"));
const beforeDateCache = coverage.runtime.famousCaseVicinityCoverageCacheValue;
coverage.context.setTimeRange(coverageDate + 10, coverageDate + 11, { mode: "custom" });
coverage.context.currentFamousCaseVicinityCoverage();
assert.notEqual(coverage.runtime.famousCaseVicinityCoverageCacheValue, beforeDateCache, "date changes invalidate coverage even when both windows have zero points");
coverage.control.catalog.push(coverageReport("newly-loaded", { lon: coverageShape.center.lng, sort_ordinal: coverageDate + 10 }));
assert.equal(coverage.context.currentFamousCaseVicinityCoverage().mappedCount, 1, "newly ingested catalog rows invalidate cached coverage");
const loadedCoverageCache = coverage.runtime.famousCaseVicinityCoverageCacheValue;
coverage.state.timelineDataVersion += 1;
coverage.context.currentFamousCaseVicinityCoverage();
assert.notEqual(coverage.runtime.famousCaseVicinityCoverageCacheValue, loadedCoverageCache, "a catalog data-version change invalidates coverage");
coverage.control.startup.ingestedCatalogShards = 0;
assert.match(coverage.context.famousCaseVicinityCoverageText(coverage.context.currentFamousCaseVicinityCoverage()), /catalog loads/, "partial catalog coverage cannot imply absence");
coverage.control.startup.phase = "Failed";
assert.match(coverage.context.famousCaseVicinityCoverageText(coverage.context.currentFamousCaseVicinityCoverage()), /unavailable/);
coverage.state.regionSelection.shapes = [];
assert.equal(coverage.context.currentFamousCaseVicinityCoverage(), null, "edited or cleared case areas have no owned vicinity diagnostic");

const manualDate = caseHarness();
const preCaseManualDates = [manualDate.state.timeRangeStartOrdinal, manualDate.state.timeRangeEndOrdinal];
manualDate.context.applyFamousCasePreset(kecksberg.id);
const manualDateCaseArea = clone(manualDate.state.regionSelection);
const nextStart = isoToOrdinal("1989-11-01");
const nextEnd = isoToOrdinal("1990-04-30");
manualDate.context.setTimeRange(nextStart, nextEnd, { mode: "custom" });
assert.equal(manualDate.state.famousCaseId, kecksberg.id, "manual dates retain the selected case");
assert.deepEqual([manualDate.state.timeRangeStartOrdinal, manualDate.state.timeRangeEndOrdinal], [nextStart, nextEnd]);
assert.deepEqual(clone(manualDate.state.regionSelection), manualDateCaseArea, "manual dates retain the case area and report-link controls");
assert.equal(manualDate.state.traceMode, "static");
assert.equal(manualDate.state.traceBucketVisibility.gap_le_1, true);
assert.equal(manualDate.runtime.famousCaseTraceModeOwned, true);
assert.equal(manualDate.runtime.famousCaseGapBucketOwned, true);
manualDate.context.clearFamousCasePreset();
assert.equal(manualDate.state.famousCaseId, "", "the case remains active until explicit Clear");
assert.equal(manualDate.state.regionSelection.shapes[0].id, "user-area");
assert.deepEqual([manualDate.state.timeRangeStartOrdinal, manualDate.state.timeRangeEndOrdinal], preCaseManualDates, "explicit Clear restores the original pre-case dates");
assert.equal(manualDate.state.traceMode, "off");
assert.equal(manualDate.state.traceBucketVisibility.gap_le_1, false);

const flap = caseHarness();
flap.context.applyFamousCasePreset(kecksberg.id);
const flapCaseArea = clone(flap.state.regionSelection);
flap.context.applyTimelinePreset("test-flap");
assert.equal(flap.state.famousCaseId, kecksberg.id, "famous flap dates retain the chosen case vicinity");
assert.equal(flap.state.timeRangeStartOrdinal, isoToOrdinal("1954-09-01"));
assert.deepEqual(clone(flap.state.regionSelection), flapCaseArea);
assert.equal(flap.state.traceMode, "static");
flap.context.applyTimelinePreset("test-rolling");
assert.equal(flap.state.famousCaseId, kecksberg.id, "rolling timeline presets also retain the case");
assert.deepEqual(clone(flap.state.regionSelection), flapCaseArea);
assert.equal(flap.state.timeRangeEndOrdinal - flap.state.timeRangeStartOrdinal, 6);
flap.context.applyFullTimeRange();
assert.equal(flap.state.famousCaseId, kecksberg.id, "All Time retains the case until it is cleared");
assert.deepEqual(clone(flap.state.regionSelection), flapCaseArea);
assert.equal(flap.state.timeRangeMode, "full");
assert.equal(flap.state.timeRangeStartOrdinal, flap.control.extent.minOrdinal);
assert.equal(flap.state.timeRangeEndOrdinal, flap.control.extent.maxOrdinal);
assert.equal(flap.state.traceMode, "static");
assert.equal(flap.state.traceBucketVisibility.gap_le_1, true);
flap.context.clearFamousCasePreset();
assert.equal(flap.state.famousCaseId, "");
assert.equal(flap.state.regionSelection.shapes[0].id, "user-area");
assert.equal(flap.state.traceMode, "off");

const boundary = caseHarness();
boundary.control.extent = { minOrdinal: isoToOrdinal(kecksberg.startIso), maxOrdinal: isoToOrdinal(kecksberg.endIso) };
boundary.context.applyFamousCasePreset(kecksberg.id);
assert.equal(boundary.state.famousCaseId, kecksberg.id, "a sourced case date at the catalog boundary remains available");
assert.equal(boundary.state.timeRangeStartOrdinal, boundary.control.extent.minOrdinal, "only padding outside the catalog is clamped");
assert.equal(boundary.state.timeRangeEndOrdinal, boundary.control.extent.maxOrdinal);
assert.equal(JSON.stringify(kecksberg), sourceCaseSnapshot);

const startupFitCalls = { fits: [], zoomReads: 0, paints: 0 };
const startupFitState = { famousCaseId: kecksberg.id, filteredMappedCatalog: [{ event_id: "mapped-report" }], selectedEventId: null, playbackState: "paused" };
const startupFit = loadFunctions(["applyStartupFitBeforeReady"], {
  state: startupFitState,
  runtime: { map: { getZoom() { startupFitCalls.zoomReads += 1; return 2.5; } } },
  MAP_DEFAULT_INITIAL_ZOOM: 2.5,
  fitToResults(options) { startupFitCalls.fits.push(clone(options)); },
  async waitForBrowserPaint() { startupFitCalls.paints += 1; },
});
assert.equal(await startupFit.applyStartupFitBeforeReady(), false, "late startup fitting cannot override a selected case even at the default zoom");
assert.deepEqual(startupFitCalls, { fits: [], zoomReads: 0, paints: 0 }, "a selected case short-circuits before map fitting");
startupFitState.famousCaseId = "";
assert.equal(await startupFit.applyStartupFitBeforeReady(), true, "startup still fits ordinary unselected results at the default zoom");
assert.deepEqual(startupFitCalls, { fits: [{ animate: false }], zoomReads: 1, paints: 1 });

const unavailable = caseHarness();
const untouched = clone(unavailable.state);
unavailable.control.extent = null;
unavailable.context.applyFamousCasePreset(kecksberg.id);
assert.deepEqual(clone(unavailable.state), untouched, "catalog loading preserves date and area state");
assert.match(unavailable.els.famousCaseSearchStatus.textContent, /catalog is loading/i);
unavailable.control.extent = { minOrdinal: isoToOrdinal("2000-01-01"), maxOrdinal: isoToOrdinal("2030-12-31") };
unavailable.context.applyFamousCasePreset(kecksberg.id);
assert.deepEqual(clone(unavailable.state), untouched, "unsupported case dates cannot clamp into an unrelated time period");
assert.match(unavailable.els.famousCaseSearchStatus.textContent, /outside the available catalog/);
assert.equal(unavailable.calls.refreshes, 0);

function circlePulseHarness(reducedMotion = false) {
  const shape = { id: "case-circle", type: "circle", center: { lat: 40, lng: -79 }, radiusMeters: 75000 };
  const state = { regionSelection: { shapes: [shape] } };
  const timers = new Map();
  const layers = [];
  let nextTimerId = 0;
  const runtime = { famousCaseShapeId: shape.id, regionSelectionLayer: {
    clearLayers() { layers.length = 0; }, addLayer(layer) { layers.push(layer); },
  } };
  const L = {
    circle(center, options) { return { kind: "circle", center, options }; },
    rectangle(bounds, options) { return { kind: "rectangle", bounds, options }; },
  };
  const context = loadFunctions([
    "createRegionSelectionLayer", "renderRegionSelectionShapes", "clearFamousCaseCirclePulse", "pulseFamousCaseCircle",
  ], {
    state, runtime, L,
    window: { L, matchMedia: () => ({ matches: reducedMotion }),
      setTimeout(callback, delay) { const id = ++nextTimerId; timers.set(id, { callback, delay }); return id; },
      clearTimeout(id) { timers.delete(id); } },
    REGION_SELECTION_SHAPE_STROKE: "#39bfd0", REGION_SELECTION_SHAPE_FILL: "#39bfd0",
    REGION_SELECTION_SHAPE_STROKE_WEIGHT: 2, REGION_SELECTION_SHAPE_STROKE_OPACITY: 0.6,
    REGION_SELECTION_SHAPE_FILL_OPACITY: 0.08,
    regionSelectionHasActiveShapes: () => state.regionSelection.shapes.length > 0,
    clearRegionSelectionPreview: noOp,
  });
  function advance() {
    assert.equal(timers.size, 1, "only the current vicinity pulse owns a timer");
    const [id, timer] = [...timers][0];
    timers.delete(id);
    timer.callback();
  }
  return { context, state, runtime, shape, timers, layers, advance };
}

const circlePulse = circlePulseHarness();
circlePulse.context.pulseFamousCaseCircle();
assert.equal(circlePulse.runtime.famousCaseCirclePulse.shapeId, circlePulse.shape.id);
assert.equal(circlePulse.layers[0].options.weight, 4, "the case vicinity briefly thickens its existing outline");
assert.equal(circlePulse.layers[0].options.opacity, 1);
assert.ok(circlePulse.layers[0].options.fillOpacity >= 0.3);
assert.equal(circlePulse.layers[0].options.color, "#39bfd0", "pulsing retains the existing area-selection color");
assert.equal(circlePulse.context.createRegionSelectionLayer({ ...circlePulse.shape, id: "other-circle" }, false).options.weight, 2, "the highlight does not affect other areas");
assert.equal(circlePulse.context.createRegionSelectionLayer(circlePulse.shape, true).options.weight, 2.5, "the highlight does not affect drawing previews");
assert.equal(circlePulse.context.createRegionSelectionLayer({ id: circlePulse.shape.id, type: "rectangle", bounds: { south: 0, north: 1, west: 0, east: 1 } }, false).options.weight, 2, "the highlight is limited to circles");
assert.equal([...circlePulse.timers.values()][0].delay, 450);
circlePulse.advance();
assert.equal(circlePulse.layers[0].options.weight, 2);
assert.equal(circlePulse.layers[0].options.opacity, 0.25, "the brief dim phase makes the circle's pulse legible");
assert.equal(circlePulse.layers[0].options.fillOpacity, 0.02);
circlePulse.advance();
assert.equal(circlePulse.layers[0].options.weight, 4);
circlePulse.advance();
assert.equal(circlePulse.layers[0].options.weight, 2);
circlePulse.advance();
assert.equal(circlePulse.runtime.famousCaseCirclePulse, null, "two brief flashes automatically finish");
assert.equal(circlePulse.timers.size, 0);
assert.equal(circlePulse.layers[0].options.fillOpacity, 0.08);

const reducedPulse = circlePulseHarness(true);
reducedPulse.context.pulseFamousCaseCircle();
assert.equal([...reducedPulse.timers.values()][0].delay, 900, "reduced motion uses a single static highlight");
reducedPulse.advance();
assert.equal(reducedPulse.runtime.famousCaseCirclePulse, null);
assert.equal(reducedPulse.layers[0].options.weight, 2);

const replacedPulse = circlePulseHarness();
replacedPulse.context.pulseFamousCaseCircle();
const previousTimer = [...replacedPulse.timers.values()][0];
replacedPulse.state.regionSelection.shapes = [{ ...replacedPulse.shape, id: "replacement-case-circle" }];
replacedPulse.runtime.famousCaseShapeId = "replacement-case-circle";
replacedPulse.context.pulseFamousCaseCircle();
assert.equal(replacedPulse.timers.size, 1, "switching cases cancels the previous timer");
previousTimer.callback();
assert.equal(replacedPulse.runtime.famousCaseCirclePulse.shapeId, "replacement-case-circle", "a stale timer cannot change the new case's highlight");
replacedPulse.context.clearFamousCaseCirclePulse();
assert.equal(replacedPulse.timers.size, 0, "explicit Clear cancels the timer immediately");
assert.equal(replacedPulse.layers[0].options.weight, 2);

const picker = caseHarness();
picker.context.applyFamousCasePreset(kecksberg.id);
picker.els.famousCaseSearch.value = "Zimbabwe";
picker.context.renderFamousCasePicker();
assert.ok(picker.els.filterFamousCases.innerHTML.includes(ariel.id));
assert.ok(picker.els.filterFamousCases.innerHTML.includes(kecksberg.id), "an active case remains selectable when catalog search changes");
assert.equal(picker.els.keywordInput.value, "existing research query");
const selectedDates = [picker.state.timeRangeStartOrdinal, picker.state.timeRangeEndOrdinal];
const selectedArea = clone(picker.state.regionSelection);
picker.els.famousCaseSearch.value = "1952";
picker.state.famousCaseOrder = "chronological";
picker.context.renderFamousCasePicker();
const chronologicalChoices = Array.from(picker.els.filterFamousCases.innerHTML.matchAll(/<option value="([^"]+)"/g))
  .map(match => cases.getCase(match[1])).filter(Boolean);
assert.deepEqual(chronologicalChoices.map(item => item.id), cases.sortCases(chronologicalChoices, "chronological").map(item => item.id));
const chronologicalLabels = [...picker.els.filterFamousCases.innerHTML.matchAll(/<option value="(case_[^"]+)"[^>]*>([^<]+)<\/option>/g)];
for (const option of chronologicalLabels) {
  const suffix = cases.getCase(option[1]).catalogReview?.status === "no_confirmed_match" ? " · no confirmed record" : "";
  assert.equal(option[2], escapeHtml(cases.formatCaseLabel(option[1], "chronological")) + suffix, "the picker keeps the year first and identifies unmatched presets");
  assert.match(option[2], /^\d{4}(?:–\d{4})? · /);
}
assert.equal(picker.els.famousCaseOrderButtons[1].attributes["aria-pressed"], "true");
assert.equal(picker.els.famousCaseOrderButtons[0].attributes["aria-pressed"], "false");
picker.state.famousCaseOrder = "alphabetical";
picker.context.renderFamousCasePicker();
const alphabeticalLabels = [...picker.els.filterFamousCases.innerHTML.matchAll(/<option value="(case_[^"]+)"[^>]*>([^<]+)<\/option>/g)];
for (const option of alphabeticalLabels) {
  const suffix = cases.getCase(option[1]).catalogReview?.status === "no_confirmed_match" ? " · no confirmed record" : "";
  assert.equal(option[2], escapeHtml(cases.formatCaseLabel(option[1], "alphabetical")) + suffix);
}
assert.equal(picker.els.famousCaseOrderButtons[0].attributes["aria-pressed"], "true");
assert.equal(picker.els.filterFamousCases.value, kecksberg.id, "changing case order preserves the selected case");
assert.equal(picker.els.famousCaseSearch.value, "1952", "changing case order preserves search text");
assert.deepEqual([picker.state.timeRangeStartOrdinal, picker.state.timeRangeEndOrdinal], selectedDates);
assert.deepEqual(clone(picker.state.regionSelection), selectedArea);
assert.ok(index.indexOf('id="filter-famous-cases"') > index.indexOf('id="filter-flap-presets"'));

// A case's local reports anchor connections from the global filtered pool.
// Interleaved craft groups and crossing-only lines must not change membership.
function caseConnectionsHarness() {
  const day = "1965-12-09";
  const ordinal = isoToOrdinal(day);
  const report = (id, craft, lon, order, extra = {}) => ({
    event_id: id, craft_type_inferred: craft, sort_date_iso: day, sort_ordinal: ordinal,
    date_precision: "exact_day", lat: 0, lon, has_coordinates: true, playback_sort_key: [order], ...extra,
  });
  const events = [
    report("triangle-before", "triangle", -2, 0), report("triangle-local", "triangle", 0, 2),
    report("disc-local", "disc_saucer", 0.1, 1), report("triangle-after", "triangle", 2, 4),
    report("triangle-remote", "triangle", 4, 6), report("disc-remote", "disc_saucer", 5, 3),
    report("light-before", "light", -3, 0), report("light-after", "light", 3, 7),
    report("orb-singleton", "sphere_orb", 0.2, 5), report("unknown-local", "unknown", 0.3, 8),
    report("month-local", "triangle", 0.4, 3, { date_precision: "month" }),
  ];
  const localIds = events.filter(event => Math.abs(event.lon) < 0.5).map(event => event.event_id);
  const state = {
    famousCaseId: kecksberg.id, traceMode: "static", traceBucketVisibility: { gap_le_1: true },
    timeRangeStartOrdinal: ordinal, timeRangeEndOrdinal: ordinal, filterGeneration: 1, timelineDataVersion: 1,
    filteredCatalog: events, filteredMappedCatalog: events,
    regionSelection: { shapes: [{ id: "case-vicinity", type: "circle", center: { lat: 0, lng: 0 }, radiusMeters: 75000 }], pointOnly: false,
      selectEvents: true, selectTraces: false, showSelectedEvents: true, showSelectedTraces: false,
      showEventsAssociatedWithSelectedTraces: false, showTracesAssociatedWithSelectedEvents: true,
      depth: 0, direction: "forward" },
  };
  const runtime = { famousCaseShapeId: "case-vicinity", activeFilterGeneration: 1, neighborhoodPerformanceSamples: [] };
  const control = { facilityRejects: false };
  const context = loadFunctions([
    "famousCaseTraceSelectionActive", "normalizeTraceMode", "traceBucketActive", "traceBucketForKey",
    "eventMatchesTimeRange", "shortestLongitudeDelta", "shortestWrappedSegment",
    "worldIndicesNearReferenceLongitude", "wrappedLongitudesNearReference", "pointInsideRectangleShape",
    "localProjectedMeters", "pointInsideCircleShape", "pointInsideRegionShape", "pointInsideAnyRegionShape",
    "buildFamousCaseTraceSegments", "currentSelectableTraceSegments", "currentChronologicalNeighborhoodIndex",
    "computeRegionSelectionResult", "traceLinkedVisibilityAffectsRendering",
  ], {
    state, runtime, TRACE_NEIGHBORHOOD: neighborhood, performance,
    PLAYBACK_TRAIL_BUCKET_BY_KEY: new Map([["gap_le_1", { key: "gap_le_1", maxDays: 1 }]]),
    CHRONOLOGICAL_NEIGHBORHOOD_SPATIAL_CELL_DEGREES: 5,
    REGION_SELECTION_EARTH_RADIUS_METERS: 6371008.8,
    normalizeLongitude: value => ((((Number(value) + 180) % 360) + 360) % 360) - 180,
    canonicalTraceSegmentsCacheKey: () => state.traceMode + "|" + state.traceBucketVisibility.gap_le_1 + "|" + control.facilityRejects,
    currentRegionSelectionTraceKey: () => state.traceMode + "|" + state.traceBucketVisibility.gap_le_1 + "|" + control.facilityRejects,
    catalogEventIdIdentityKey: events => events.map(event => event.event_id).join(","),
    createTraceFacilityClassificationContext: () => ({}),
    applyTraceFacilityFilterToSegmentWithContext: segment => control.facilityRejects ? null : segment,
    buildCanonicalTraceSegments() { assert.fail("a case-owned vicinity must use its grouped report connections"); },
    regionSelectionHasActiveShapes: () => true,
    regionSelectionShapeBounds: () => ({ north: 0.5, south: -0.5, east: 0.5, west: -0.5 }),
    currentChronologicalNeighborhoodSeeds(index) {
      return { eventSeeds: localIds.map(eventId => ({ eventId, regionIds: ["case-vicinity"] })),
        // This line crosses the vicinity with neither report inside it.
        traceSeeds: [{ traceId: "light-before->light-after", regionIds: ["case-vicinity"] }],
        candidateEventCount: localIds.length, candidateTraceCount: index.segments.length };
    },
    updateRegionSelectionMetrics(metrics) { runtime.regionSelectionMetrics = metrics; },
  });
  return { context, state, runtime, control, events, localIds };
}

const connections = caseConnectionsHarness();
const poolSnapshot = JSON.stringify(connections.events);
const caseSegments = connections.context.currentSelectableTraceSegments();
assert.equal(caseSegments.length, 5, "each craft group connects neighboring reports in the global filtered pool");
assert.ok(caseSegments.every(segment => segment.gapDays === 0 && segment.sameDayOrderKnown === false));
assert.ok(caseSegments.every(segment => segment.bucket.key === "gap_le_1"));
assert.ok(caseSegments.every(segment => segment.craftType === connections.events.find(event => event.event_id === segment.toEventId).craft_type_inferred));
assert.equal(connections.context.currentSelectableTraceSegments(), caseSegments, "the case-specific sequence is cached");
const caseResult = connections.context.computeRegionSelectionResult();
assert.deepEqual([...caseResult.visibleTraceIds].sort(), ["disc-local->disc-remote", "triangle-before->triangle-local", "triangle-local->triangle-after"]);
assert.equal(caseResult.selectedTraceCount, 0, "crossing lines never become case seeds");
assert.ok(!caseResult.visibleTraceIds.has("light-before->light-after"), "crossing-only links do not belong to the case vicinity");
assert.ok(!caseResult.visibleTraceIds.has("triangle-after->triangle-remote"), "zero hops avoids a further walk from the remote endpoint");
assert.deepEqual([...caseResult.visibleMappedCatalog].map(event => event.event_id).sort(), connections.localIds.slice().sort(), "singletons, unknown craft and imprecise-date reports remain visible as local reports");
assert.equal(connections.state.filteredMappedCatalog.length, 11, "selection leaves remote reports available in the global pool");
assert.equal(JSON.stringify(connections.events), poolSnapshot, "grouping and selection preserve source report records");
assert.equal(connections.context.traceLinkedVisibilityAffectsRendering(), false, "unmatched local reports are not hidden by link visibility");
connections.state.traceMode = "off";
assert.equal(connections.context.computeRegionSelectionResult().visibleTraceCount, 0);
assert.equal(connections.context.computeRegionSelectionResult().visibleEventCount, connections.localIds.length, "turning traces off retains the case's reports");
connections.state.traceMode = "static";
connections.state.traceBucketVisibility.gap_le_1 = false;
assert.equal(connections.context.computeRegionSelectionResult().visibleTraceCount, 0, "the same-day bucket still controls case links");
connections.state.traceBucketVisibility.gap_le_1 = true;
connections.control.facilityRejects = true;
const proximityResult = connections.context.computeRegionSelectionResult();
assert.equal(proximityResult.visibleTraceCount, 0, "facility filtering can remove case connections");
assert.equal(proximityResult.visibleEventCount, connections.localIds.length, "facility filtering retains unmatched local reports");
assert.equal(proximityResult.caseResultsCatalog.length, connections.localIds.length, "outside endpoint rows disappear when their connections are filtered out");
assert.equal(proximityResult.caseResultLinkedEventIds.size, 0);

const resultsConnections = caseConnectionsHarness();
const resultsContext = resultsConnections.context;
const resultsControl = { displayCatalogCalls: 0, summary: "" };
const resultsEls = {
  resultsCaseContext: { hidden: true, textContent: "" },
  resultList: { innerHTML: "", scrollTop: 0, classList: { remove: noOp }, removeAttribute: noOp, setAttribute: noOp },
};
Object.assign(resultsContext, {
  els: resultsEls, PLAYBACK_PERFORMANCE: playbackPerformance, RESULTS_RENDER_BATCH: 60, escapeHtml, formatNumber: String,
  currentRegionSelectionResult: () => resultsContext.computeRegionSelectionResult(),
  regionSelectionAffectsRendering: () => true,
  currentVisibleDisplayCatalog(events) { resultsControl.displayCatalogCalls += 1; return events; },
  startupProfilePreviewResultsCatalog: () => null,
  traceLinkedVisibilityAffectsRendering: () => false,
  sortResultsForDisplay: events => events,
  currentPlaybackEvent: () => null,
  setResultSummaryValue(value) { resultsControl.summary = value; },
  displayLocationForEvent: event => event.event_id,
  locationPrecisionDisplayLabel: String,
  rebuildRenderedResultCardIndex: noOp,
  clearFamousCaseCirclePulse: noOp, renderTraceControls: noOp, renderFamousCasePicker: noOp, renderFamousCaseResultsSummary: noOp, scheduleRefresh: noOp,
});
vm.runInContext([
  "currentVisibleResultsCatalog", "currentResultsPaneCatalog", "currentVisibleMappedCatalog", "visibleResultsEventIdSet",
  "famousCaseResultMembership", "renderResultsCaseContext", "eventVisibleInCurrentResults", "renderResults",
  "resultsRenderContextKey", "renderExpandedResultDescription", "resultWindowNavigationMarkup", "clearFamousCasePreset",
].map(extractFunction).join("\n"), resultsContext);
const resultsSelection = resultsContext.computeRegionSelectionResult();
const outsideIds = ["disc-remote", "triangle-after", "triangle-before"];
assert.equal(resultsSelection.caseResultsCatalog.length, 8, "Results includes the five local reports and three endpoints of visible connections");
assert.equal(new Set(resultsSelection.caseResultsCatalog.map(event => String(event.event_id))).size, 8, "shared and already-local endpoints appear only once");
assert.deepEqual([...resultsSelection.caseResultAreaEventIds].sort(), resultsConnections.localIds.slice().sort(), "membership uses the actual circle geometry");
assert.deepEqual([...resultsSelection.caseResultLinkedEventIds].sort(), outsideIds);
assert.ok(!resultsSelection.caseResultLinkedEventIds.has("triangle-remote"), "a further remote chain report is not a visible connection endpoint");
assert.ok(!resultsSelection.caseResultLinkedEventIds.has("light-before"), "crossing-only trace endpoints stay excluded");
const paneRows = resultsContext.currentResultsPaneCatalog();
assert.equal(paneRows.length, 8);
assert.equal(resultsControl.displayCatalogCalls, 0, "case endpoint IDs bypass content-level display suppression in the pane");
assert.equal(resultsContext.currentVisibleResultsCatalog().length, 5, "the core results cohort remains limited to local reports");
assert.equal(resultsContext.currentVisibleMappedCatalog().length, 5, "outside pane rows do not expand map points");
assert.deepEqual([...resultsContext.visibleResultsEventIdSet()].sort(), resultsConnections.localIds.slice().sort(), "playback retains the local cohort ID set");
assert.equal(resultsContext.famousCaseResultMembership("triangle-local", resultsSelection), "area");
assert.equal(resultsContext.famousCaseResultMembership("triangle-before", resultsSelection), "connected");
assert.equal(resultsContext.famousCaseResultMembership("triangle-remote", resultsSelection), "");
assert.equal(resultsContext.eventVisibleInCurrentResults("disc-remote"), true, "outside endpoint rows remain selectable in the pane");
assert.equal(resultsContext.eventVisibleInCurrentResults("light-before"), false);
resultsContext.renderResults();
assert.equal(resultsControl.summary, "8");
assert.equal(resultsEls.resultsCaseContext.hidden, false);
assert.equal(resultsEls.resultsCaseContext.textContent, "5 in selected area · 3 connected outside area");
const resultCards = [...resultsEls.resultList.innerHTML.matchAll(/<article class="([^"]+)" data-result-card-event-id="([^"]+)">([\s\S]*?)<\/article>/g)];
assert.equal(resultCards.length, 8);
for (const [, classes, eventId, contents] of resultCards) {
  assert.ok(classes.includes(outsideIds.includes(eventId) ? "is-case-connected" : "is-case-area"));
  assert.ok(contents.includes(outsideIds.includes(eventId) ? "Connected outside area" : "In selected area"));
  assert.ok(contents.includes('data-result-details="' + eventId + '"'), "both membership categories retain full report details");
}
const initialResultsCatalog = resultsConnections.state.filteredCatalog;
resultsConnections.state.filteredCatalog = initialResultsCatalog.concat({ ...initialResultsCatalog.find(event => event.event_id === "disc-remote") });
assert.equal(resultsContext.currentResultsPaneCatalog().length, 8, "duplicate copies of one endpoint ID do not add a pane row");
resultsConnections.state.filteredCatalog = initialResultsCatalog.filter(event => event.event_id !== "disc-remote");
assert.ok(!resultsContext.currentResultsPaneCatalog().some(event => event.event_id === "disc-remote"), "an endpoint missing from the current filtered catalog cannot be resurrected by a stale visible trace");
resultsConnections.state.filteredCatalog = initialResultsCatalog;
resultsConnections.state.traceMode = "off";
assert.equal(resultsContext.currentResultsPaneCatalog().length, 5, "turning traces off removes their outside endpoint rows");
resultsConnections.state.traceMode = "static";
resultsConnections.state.traceBucketVisibility.gap_le_1 = false;
assert.equal(resultsContext.currentResultsPaneCatalog().length, 5, "the trace bucket controls both visible connections and related outside rows");
resultsConnections.state.traceBucketVisibility.gap_le_1 = true;
resultsContext.buildCanonicalTraceSegments = () => [];
resultsContext.clearFamousCasePreset();
resultsContext.renderResults();
assert.equal(resultsConnections.state.famousCaseId, "");
assert.equal(resultsContext.currentResultsPaneCatalog().length, 5, "explicit Clear restores the normal local-area pane cohort");
assert.equal(resultsEls.resultsCaseContext.hidden, true);
assert.equal(resultsEls.resultsCaseContext.textContent, "");
assert.ok(!/is-case-area|is-case-connected|result-case-membership/.test(resultsEls.resultList.innerHTML), "case-specific labels and emphasis disappear after Clear");
assert.equal(resultsContext.eventVisibleInCurrentResults("disc-remote"), false, "related outside selections are no longer pane-visible after Clear");

function directionHarness(inputSegments, projectionScale = 1) {
  const segment = (id, from, to, direction) => ({ traceId: id, fromEventId: id + "-a", toEventId: id + "-b", from, to, neighborhood: { direction, hop: 0 }, color: "#ff8000" });
  const segments = inputSegments || [segment("direct-east", [0, 0], [0, 10], "direct"), segment("back-west", [0, 1], [0, 11], "backward"), segment("both-ns", [0, 2], [10, 2], "both"), segment("coincident", [1, 3], [1, 3], "forward")];
  const result = { visibleTraceSegments: segments, neighborhoodSegments: segments, selectedTraceIds: new Set(segments.map(row => row.traceId)), pointOnly: false };
  const layers = [];
  const runtime = { neighborhoodTraceLayer: { clearLayers() { layers.length = 0; } }, map: {
    getZoom() { return 6.5 + Math.log2(projectionScale); },
    project(value, zoom) { assert.equal(zoom, this.getZoom()); return this.latLngToLayerPoint(value); },
    latLngToLayerPoint(value) {
      const lat = Array.isArray(value) ? value[0] : value.lat;
      const lng = Array.isArray(value) ? value[1] : value.lng;
      return { x: lng * 10 * projectionScale, y: -Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)) * 1800 * projectionScale / Math.PI };
    },
    layerPointToLatLng(point) { return { lat: (2 * Math.atan(Math.exp(-point.y * Math.PI / (1800 * projectionScale))) - Math.PI / 2) * 180 / Math.PI, lng: point.x / (10 * projectionScale) }; },
    latLngToContainerPoint(value) { return this.latLngToLayerPoint(value); },
  } };
  const state = { regionSelection: { direction: "forward" }, resolvedTheme: "dark" };
  const els = { areaDirectionSummary: { hidden: true }, areaDirectionSummaryBody: { innerHTML: "" }, chronologicalNeighborhoodInspector: { hidden: true }, chronologicalNeighborhoodInspectorBody: { innerHTML: "", handlers: {}, addEventListener(name, handler) { this.handlers[name] = handler; } } };
  const controls = { active: true, paneInteractive: false };
  function layer(kind, geometry, options) { return { kind, geometry, options, handlers: {}, on(name, handler) { this.handlers[name] = handler; return this; }, addTo() { layers.push(this); return this; } }; }
  const L = { point: (x, y) => ({ x, y }), polyline: (points, options) => layer("line", points, options), marker: (point, options) => layer("badge", point, options), divIcon: options => options };
  const context = loadFunctions([
    "currentAreaDirectionSummary", "renderAreaDirectionSummary", "neighborhoodArrowAngle", "neighborhoodPointAlongCopy", "neighborhoodBadgePosition", "renderChronologicalNeighborhoodBadge", "renderChronologicalNeighborhoodOverlay",
    "closeChronologicalNeighborhoodInspector", "currentUnorderedConnectionGroups", "renderChronologicalNeighborhoodInspector", "selectNeighborhoodReportLink", "chronologicalNeighborhoodEndpointLabel", "chronologicalNeighborhoodDateLabel",
  ], {
    runtime, state, els, L, TRACE_DIRECTIONS: directions, TRACE_NEIGHBORHOOD: neighborhood,
    CRAFT_TYPE_COLORS: {}, CHRONOLOGICAL_NEIGHBORHOOD_OUTLINE_COLOR: "#111", CHRONOLOGICAL_NEIGHBORHOOD_LIGHT_OUTLINE_COLOR: "#eee", clamp, escapeHtml, formatNumber: String,
    currentRegionSelectionResult: () => result, regionSelectionAffectsRendering: () => controls.active,
    setChronologicalNeighborhoodPaneInteractive(active) { controls.paneInteractive = active; },
    normalTraceDensityProfile: () => ({}), styleTraceSegmentForDensity: row => row,
    scaledTraceOpacity: value => value, scaledTraceStrokeWeight: value => value,
    craftTraceColoringActive: () => false,
    wrappedSegmentCopies(row) { return [{ from: row.from, to: row.to }, { from: [row.from[0], row.from[1] + 360], to: [row.to[0], row.to[1] + 360] }]; },
    renderedPointMarkerHitAtLatLng: () => null, activateMapPointEvent: () => false,
    getCatalogEventById(id) { return { event_id: id, location: "Report " + id, date_raw: "1965-12-09" }; },
  });
  return { context, runtime, state, els, result, controls, layers };
}

const arrows = directionHarness();
arrows.context.renderChronologicalNeighborhoodOverlay();
const summary = arrows.context.currentAreaDirectionSummary(arrows.result);
assert.equal(summary.denominator, 4, "one direct, one backward and one both-direction link supply four directions");
assert.equal(summary.validSegments, 3);
assert.equal(summary.excludedCounts.zeroDistance, 1);
assert.equal(summary.sectors.find(row => row.key === "W").percentage, 25);
const badges = arrows.layers.filter(row => row.kind === "badge");
assert.equal(badges.length, 8, "world copies render badges without multiplying the statistics");
for (const badge of badges) {
  assert.equal(badge.options.interactive, true);
  assert.equal(badge.options.keyboard, true);
  assert.match(badge.options.title, /25% of ordered connections/);
  assert.equal(badge.options.icon.html.replace(/<[^>]*>/g, ""), "➜", "only the arrow is visible on each map badge");
}
assert.match(arrows.els.areaDirectionSummaryBody.innerHTML, /4 (?:ordered )?directions across 3 (?:ordered )?report links/);
assert.match(arrows.els.areaDirectionSummaryBody.innerHTML, /Radial scale: 0–25%/);
const eastBadge = badges.find(row => row.options.title.startsWith("East "));
eastBadge.handlers.click();
assert.equal(arrows.runtime.neighborhoodInspectorTraceId, "direct-east");
assert.equal(arrows.els.chronologicalNeighborhoodInspector.hidden, false);
assert.match(arrows.els.chronologicalNeighborhoodInspectorBody.innerHTML, /East \(E\), 90° · 1 \/ 4 directions \(25%\)/);
assert.match(arrows.els.chronologicalNeighborhoodInspectorBody.innerHTML, /is-selected-direction/);
const westBadge = badges.find(row => row.options.title.startsWith("West "));
westBadge.handlers.click();
assert.equal(arrows.runtime.neighborhoodInspectorTraceId, "back-west");
assert.match(arrows.els.chronologicalNeighborhoodInspectorBody.innerHTML, /West \(W\), 270°/);
assert.equal(arrows.context.currentAreaDirectionSummary(arrows.result), summary, "the same selection reuses its full statistical summary");
assert.equal(arrows.context.chronologicalNeighborhoodEndpointLabel({ location_raw: "Source-reported place" }), "Source-reported place", "compact runtime report locations remain readable in the connection inspector");
arrows.result.pointOnly = true;
arrows.context.renderAreaDirectionSummary(arrows.result, true);
arrows.context.renderChronologicalNeighborhoodOverlay();
assert.equal(arrows.layers.length, 0, "point-only area filtering does not retain connection badges");
assert.equal(arrows.els.areaDirectionSummary.hidden, true);
assert.equal(arrows.els.chronologicalNeighborhoodInspector.hidden, true);
assert.equal(arrows.controls.paneInteractive, false);

const reportLink = (id, from, to, extra = {}) => ({
  traceId: id, fromEventId: id + "-a", toEventId: id + "-b", from, to,
  neighborhood: { direction: "direct", hop: 0 }, color: "#ff8000", gapDays: 1, ...extra,
});
const mixedDirections = directionHarness([
  reportLink("known-east", [0, 0], [0, 10], { sameDayOrderKnown: true }),
  reportLink("known-west", [0, 10], [0, 0], { gapDays: 2 }),
  reportLink("unordered-case", [1, 0], [1, 10], { gapDays: 0, sameDayOrderKnown: false, neighborhood: { direction: "backward", hop: 0 } }),
  reportLink("unordered-canonical", [0, 1], [10, 1], { gapDays: 0 }),
]);
mixedDirections.context.renderChronologicalNeighborhoodOverlay();
const mixedSummary = mixedDirections.context.currentAreaDirectionSummary(mixedDirections.result);
assert.equal(mixedSummary.denominator, 2, "uncertain same-day links never contribute arbitrarily ordered directions");
assert.equal(mixedSummary.orderedSegments, 2);
assert.equal(mixedSummary.unorderedSegments, 2);
assert.equal(mixedSummary.validSegments, 4, "uncertain links remain available as valid report connections");
assert.equal(mixedSummary.sectors.find(row => row.key === "E").percentage, 50);
assert.equal(mixedSummary.sectors.find(row => row.key === "W").percentage, 50);
const mixedBadges = mixedDirections.layers.filter(row => row.kind === "badge");
assert.equal(mixedBadges.length, 8, "each uncertain link has one neutral badge per rendered world copy");
const uncertainBadges = mixedBadges.filter(row => row.options.icon.html.includes("is-order-uncertain"));
assert.equal(uncertainBadges.length, 4);
for (const badge of uncertainBadges) {
  assert.equal(badge.options.icon.html.replace(/<[^>]*>/g, ""), "↔");
  assert.match(badge.options.icon.html, /sector-unordered/);
  assert.match(badge.options.icon.html, /--direction-tone:#969696/);
  assert.match(badge.options.icon.html, /border-style:dashed/, "the neutral badge border marks its uncertain ordering");
  assert.match(badge.options.icon.html, /aria-label="[^"]*order (?:uncertain|unknown)/i);
  assert.match(badge.options.title, /order (?:uncertain|unknown)/i);
  assert.match(badge.options.alt, /order (?:uncertain|unknown)/i);
  assert.ok(!badge.options.title.includes("%"), "neutral badges never claim a directional share");
  assert.equal(badge.options.interactive, true);
  assert.equal(badge.options.keyboard, true);
}
const knownEast = mixedBadges.find(row => row.options.title.startsWith("East "));
const knownWest = mixedBadges.find(row => row.options.title.startsWith("West "));
assert.ok(knownEast && knownWest, "ordered links retain their compass labels");
assert.match(knownEast.options.icon.html, /--direction-tone:#c7c7c7/);
assert.match(knownWest.options.icon.html, /--direction-tone:#606060/);
assert.equal(knownEast.options.icon.html.replace(/<[^>]*>/g, ""), "➜", "ordered links retain their ordinary arrow");
assert.match(knownEast.options.title, /50% of ordered connections/);
uncertainBadges.find(badge => badge.options.title.includes("East–West")).handlers.click();
const mixedInspector = mixedDirections.els.chronologicalNeighborhoodInspectorBody.innerHTML;
const mixedDetails = mixedInspector.match(/<dl[\s\S]*?<\/dl>/)[0];
assert.match(mixedDetails, /Endpoint A/);
assert.match(mixedDetails, /Endpoint B/);
assert.match(mixedDetails, /Map connection axis/);
assert.match(mixedDetails, /East–West/);
assert.match(mixedDetails, /Unordered/);
assert.ok(!mixedDetails.includes("%"), "uncertain connection details have no ordered-direction share");
assert.ok(!mixedDetails.includes("Map direction ("));
assert.ok(!mixedInspector.includes("is-selected-direction"), "an uncertain connection highlights no polar direction in the ordered summary");

// Use actual zero-hop case connections to cover the all-uncertain UI.
const caseDirections = directionHarness(caseResult.visibleTraceSegments);
caseDirections.context.renderChronologicalNeighborhoodOverlay();
const caseDirectionSummary = caseDirections.context.currentAreaDirectionSummary(caseDirections.result);
assert.equal(caseDirectionSummary.denominator, 0);
assert.equal(caseDirectionSummary.unorderedSegments, 3);
assert.equal(caseDirectionSummary.orderedSegments, 0);
const caseDirectionMarkup = caseDirections.els.areaDirectionSummaryBody.innerHTML;
assert.ok(!caseDirectionMarkup.includes("trace-direction-table"), "all-uncertain selections omit the ordered-direction table");
assert.ok(!caseDirectionMarkup.includes("trace-direction-chart"), "all-uncertain selections omit the ordered-direction radar");
assert.ok(!/\d%/.test(caseDirectionMarkup), "no percentage distribution is invented from uncertain links");
const caseBadges = caseDirections.layers.filter(row => row.kind === "badge");
assert.equal(caseBadges.length, caseDirections.context.currentUnorderedConnectionGroups(caseResult.visibleTraceSegments).length * 2, "case badges follow displayed overlap groups without changing the underlying links");
caseBadges[0].handlers.click();
assert.ok(caseResult.visibleTraceSegments.some(segment => segment.traceId === caseDirections.runtime.neighborhoodInspectorTraceId), "a neutral badge opens one of its retained report links");
assert.equal(caseDirections.els.chronologicalNeighborhoodInspector.hidden, false);
const caseInspector = caseDirections.els.chronologicalNeighborhoodInspectorBody.innerHTML;
assert.match(caseInspector, /Endpoint A/);
assert.match(caseInspector, /Endpoint B/);
assert.match(caseInspector, /elapsed hours and order uncertain/);
assert.match(caseInspector, /travel direction and origin are unestablished/);
assert.ok(!caseInspector.includes("Earlier endpoint"));
assert.ok(!/East \(E\)|West \(W\)|\d%|Map direction \(/.test(caseInspector), "uncertain case inspectors show orientation without polar travel claims or artificial shares");

const reciprocalLinks = [
  reportLink("reciprocal-a", [10, 20], [10, 30], { gapDays: 0, sameDayOrderKnown: false }),
  reportLink("reciprocal-b", [10, 30], [10, 20], { gapDays: 0, sameDayOrderKnown: false }),
];
const reciprocalDirections = directionHarness(reciprocalLinks);
reciprocalDirections.context.renderChronologicalNeighborhoodOverlay();
const reciprocalSummary = reciprocalDirections.context.currentAreaDirectionSummary(reciprocalDirections.result);
assert.equal(reciprocalSummary.validSegments, 2, "badge grouping retains both source report links");
assert.equal(reciprocalSummary.unorderedSegments, 2);
assert.equal(reciprocalSummary.denominator, 0, "grouping never manufactures an ordered direction");
assert.equal(reciprocalDirections.result.visibleTraceSegments.length, 2);
assert.equal(reciprocalDirections.layers.filter(row => row.kind === "line").length, 8, "both raw links and their outline/world copies remain rendered");
const reciprocalBadges = reciprocalDirections.layers.filter(row => row.kind === "badge");
assert.equal(reciprocalBadges.length, 2, "reciprocal unknown geometry renders one neutral badge per world copy");
assert.ok(reciprocalBadges.every(row => row.options.icon.html.includes("is-order-uncertain")));
reciprocalBadges[0].handlers.click();
const reciprocalInspector = reciprocalDirections.els.chronologicalNeighborhoodInspectorBody.innerHTML;
assert.match(reciprocalInspector, /data-neighborhood-trace-id="reciprocal-a"/, "the grouped badge offers the first report link");
assert.match(reciprocalInspector, /data-neighborhood-trace-id="reciprocal-b"/, "the grouped badge offers its reciprocal report link");
assert.match(reciprocalInspector, /2 report links share this map line/);
vm.runInContext(extractControlBlock("if (els.chronologicalNeighborhoodInspectorBody) {", "last"), reciprocalDirections.context);
const reciprocalBody = reciprocalDirections.els.chronologicalNeighborhoodInspectorBody;
for (const traceId of ["reciprocal-b", "reciprocal-a"]) {
  reciprocalBody.handlers.click({ target: { closest(selector) {
    assert.equal(selector, "[data-neighborhood-trace-id]");
    return { getAttribute(name) { assert.equal(name, "data-neighborhood-trace-id"); return traceId; } };
  } } });
  assert.equal(reciprocalDirections.runtime.neighborhoodInspectorTraceId, traceId, "each retained report link is reachable through the grouped inspector");
  assert.ok(reciprocalBody.innerHTML.includes(traceId + "-a"), "the chosen link displays its own endpoint records");
  assert.ok(reciprocalBody.innerHTML.includes('data-neighborhood-trace-id="' + traceId + '" aria-pressed="true"'), "the current group member is announced as selected");
}
reciprocalDirections.context.selectNeighborhoodReportLink("unavailable-report-link");
assert.equal(reciprocalDirections.runtime.neighborhoodInspectorTraceId, "reciprocal-a", "an invalid group member does not replace the inspector");

const separatedDirections = directionHarness([
  ...reciprocalLinks,
  reportLink("separate-unknown-path", [10.2, 20], [10.2, 30], { gapDays: 0 }),
  reportLink("ordered-same-path", [10, 20], [10, 30]),
]);
separatedDirections.context.renderChronologicalNeighborhoodOverlay();
const separatedSummary = separatedDirections.context.currentAreaDirectionSummary(separatedDirections.result);
assert.equal(separatedSummary.validSegments, 4);
assert.equal(separatedSummary.unorderedSegments, 3);
assert.equal(separatedSummary.orderedSegments, 1);
assert.equal(separatedSummary.denominator, 1, "an ordered arrow on matching geometry remains independent of the unordered group");
assert.equal(separatedSummary.sectors.find(row => row.key === "E").percentage, 100);
assert.equal(separatedDirections.layers.filter(row => row.kind === "line").length, 16);
const separatedBadges = separatedDirections.layers.filter(row => row.kind === "badge");
assert.equal(separatedBadges.filter(row => row.options.icon.html.includes("is-order-uncertain")).length, 4, "spatially separate uncertain paths retain separate badge groups");
assert.equal(separatedBadges.filter(row => !row.options.icon.html.includes("is-order-uncertain")).length, 2, "ordered arrows sharing the geometry are not folded into the neutral group");

const nearReciprocalLinks = [
  reportLink("near-path-a", [10, 20], [10, 30], { gapDays: 0 }),
  reportLink("near-path-b", [10.04, 30.02], [10.04, 20.02], { gapDays: 0 }),
];
const nearSourceSnapshot = JSON.stringify(nearReciprocalLinks);
const overviewDirections = directionHarness(nearReciprocalLinks);
overviewDirections.context.renderChronologicalNeighborhoodOverlay();
assert.equal(overviewDirections.context.currentUnorderedConnectionGroups(nearReciprocalLinks).length, 1, "subpixel reciprocal endpoint differences group at the current map scale");
assert.equal(overviewDirections.layers.filter(row => row.kind === "badge").length, 2, "near-coincident paths show one badge per world copy at overview scale");
assert.equal(overviewDirections.layers.filter(row => row.kind === "line").length, 8, "display grouping preserves both slightly different path geometries");
const overviewSummary = overviewDirections.context.currentAreaDirectionSummary(overviewDirections.result);
assert.equal(overviewSummary.unorderedSegments, 2);
assert.equal(overviewSummary.denominator, 0);
overviewDirections.layers.find(row => row.kind === "badge").handlers.click();
assert.match(overviewDirections.els.chronologicalNeighborhoodInspectorBody.innerHTML, /data-neighborhood-trace-id="near-path-a"/);
assert.match(overviewDirections.els.chronologicalNeighborhoodInspectorBody.innerHTML, /data-neighborhood-trace-id="near-path-b"/, "the inspector uses the same current display grouping as the map");
const detailedDirections = directionHarness(nearReciprocalLinks, 100);
detailedDirections.context.renderChronologicalNeighborhoodOverlay();
assert.equal(detailedDirections.context.currentUnorderedConnectionGroups(nearReciprocalLinks).length, 2, "zooming in separates paths whose endpoint differences become visible");
assert.equal(detailedDirections.layers.filter(row => row.kind === "badge").length, 4);
assert.equal(detailedDirections.layers.filter(row => row.kind === "line").length, 8);
assert.equal(detailedDirections.context.currentAreaDirectionSummary(detailedDirections.result).unorderedSegments, 2, "zoom changes display grouping without changing report-link counts");
assert.equal(JSON.stringify(nearReciprocalLinks), nearSourceSnapshot, "display grouping never alters endpoint coordinates or source report links");

// Translate the live Mariana projected coordinates into this harness's
// invertible map projection; translations preserve pixel overlap distances.
const reportCoordinateForPixel = ([x, y]) => {
  const projectedX = x - 3000;
  const projectedY = y - 8000;
  return [(2 * Math.atan(Math.exp(-projectedY * Math.PI / 1800)) - Math.PI / 2) * 180 / Math.PI, projectedX / 10];
};
const salemPoint = reportCoordinateForPixel([3666.399421, 8340.194759]);
const greatFallsPoint = reportCoordinateForPixel([4421.646847, 8102.231373]);
const hermistonPoint = reportCoordinateForPixel([3912.126170, 8263.474880]);
const overlappingLinks = [
  reportLink("mariana-short-reverse", greatFallsPoint, hermistonPoint, { gapDays: 0 }),
  reportLink("mariana-long", salemPoint, greatFallsPoint, { gapDays: 0 }),
];
const overlapSourceSnapshot = JSON.stringify(overlappingLinks);
const overlapDirections = directionHarness(overlappingLinks);
overlapDirections.context.renderChronologicalNeighborhoodOverlay();
const overlapGroups = overlapDirections.context.currentUnorderedConnectionGroups(overlappingLinks);
assert.equal(overlapGroups.length, 1, "a shared endpoint and subpixel collinear overlap share one neutral badge group");
assert.equal(overlapGroups[0].representative.traceId, "mariana-long", "the longest raw path represents the visible overlap even when encountered second");
assert.equal(overlapDirections.layers.filter(row => row.kind === "line").length, 8);
const overlapBadges = overlapDirections.layers.filter(row => row.kind === "badge");
assert.equal(overlapBadges.length, 2, "the live Mariana-style overlap renders one badge per world copy");
assert.equal(overlapDirections.context.currentAreaDirectionSummary(overlapDirections.result).unorderedSegments, 2);
overlapBadges[0].handlers.click();
assert.equal(overlapDirections.runtime.neighborhoodInspectorTraceId, "mariana-long");
const overlapInspector = overlapDirections.els.chronologicalNeighborhoodInspectorBody.innerHTML;
assert.match(overlapInspector, /data-neighborhood-trace-id="mariana-short-reverse"/);
assert.match(overlapInspector, /data-neighborhood-trace-id="mariana-long"/);
assert.match(overlapInspector, /One arrow marks this overlap/);
const detailedOverlapDirections = directionHarness(overlappingLinks, 10);
detailedOverlapDirections.context.renderChronologicalNeighborhoodOverlay();
assert.equal(detailedOverlapDirections.context.currentUnorderedConnectionGroups(overlappingLinks).length, 2, "zooming in reveals and separates the noncoincident Mariana paths");
assert.equal(detailedOverlapDirections.layers.filter(row => row.kind === "badge").length, 4);
assert.equal(detailedOverlapDirections.layers.filter(row => row.kind === "line").length, 8);
assert.equal(detailedOverlapDirections.context.currentAreaDirectionSummary(detailedOverlapDirections.result).unorderedSegments, 2);
assert.equal(JSON.stringify(overlappingLinks), overlapSourceSnapshot, "collinear display grouping retains every source endpoint and report link");

const legendState = { soloKey: "", craftTypeColorOverrides: { disc_saucer: "#112233" } };
const legendContext = loadFunctions(["buildCraftLegendRow"], {
  LEGEND_CONTROLS: legend, state: legendState, escapeHtml, formatNumber: String,
  craftLegendSoloKey: () => legendState.soloKey,
});
const legendEntry = { key: "disc_saucer", label: "Disc / saucer", active: true, count: 23, color: "#112233" };
const expectedSymbol = legend.craftSymbolMarkup(legendEntry.key);
assert.ok(expectedSymbol, "the craft legend has a silhouette for the disc/saucer category");
for (const surface of ["map", "panel"]) {
  const row = legendContext.buildCraftLegendRow(legendEntry, surface);
  const soloButton = row.match(/<button class="craft-legend-label-button"[^>]*>([\s\S]*?)<\/button>/)[1];
  assert.ok(soloButton.includes(expectedSymbol), "the silhouette belongs to the existing label/solo button");
  assert.ok(soloButton.indexOf(expectedSymbol) < soloButton.indexOf('class="craft-legend-label-text"'), "the silhouette appears before its readable craft label");
  assert.ok(row.indexOf('class="legend-swatch"') < row.indexOf(expectedSymbol), "the color dot retains its position before the silhouette");
  assert.ok(row.includes(surface === "map" ? 'data-map-legend-event-key="disc_saucer"' : 'data-craft-legend-toggle-key="disc_saucer"'));
  assert.ok(row.includes('data-craft-legend-solo-key="disc_saucer"'), "the silhouette preserves the label's solo interaction");
  assert.ok(row.includes('aria-label="23 events visible on the current map"'));
  assert.ok(row.includes('type="color" data-craft-color-key="disc_saucer" value="#112233"'), "craft recoloring remains a separate control");
  assert.ok(!expectedSymbol.includes(legendEntry.color), "the silhouette uses a neutral tone independently of the craft swatch color");
}
legendState.soloKey = legendEntry.key;
const soloRow = legendContext.buildCraftLegendRow(legendEntry, "map");
assert.match(soloRow, /data-craft-legend-solo-key="disc_saucer" aria-pressed="true"/);
assert.match(soloRow, /Restore the previous craft selection/);

console.log("Direction, famous-case and craft-legend integration passed: case persistence across date controls, padded dates and preserved zoom, accessible vicinity pulses, grouped report connections, control restoration, arrow statistics and neutral legend silhouettes.");
