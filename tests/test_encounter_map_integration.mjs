// Run the actual app overlay/filter/legend lifecycle against small pinned-style
// fixtures. This is runtime integration QA, not a substitute for visual review.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const evidence = require("../encounter_evidence.js");
const encounterMap = require("../encounter_map.js");
const appCode = fs.readFileSync("app.js", "utf8");
const indexCode = fs.readFileSync("index.html", "utf8");
const plain = (value) => JSON.parse(JSON.stringify(value));
function appFunction(name) {
  const start = appCode.indexOf("  function " + name + "(");
  assert.ok(start >= 0, "Missing actual app function: " + name);
  const end = appCode.indexOf("\n  function ", start + 3);
  assert.ok(end > start, "Missing actual app function boundary: " + name);
  return appCode.slice(start, end);
}
function element(id, fields = {}) {
  const attributes = new Map(), listeners = new Map();
  let hidden = false;
  return { id, value: "", checked: false, textContent: "", children: [], ...fields,
    get hidden() { return hidden; }, set hidden(value) { hidden = Boolean(value); },
    classList: { contains: (key) => key === fields.className },
    getAttribute: (key) => attributes.get(key) || "",
    setAttribute: (key, value) => attributes.set(key, String(value)),
    hasAttribute: (key) => attributes.has(key),
    addEventListener: (key, listener) => listeners.set(key, listener),
    listeners,
  };
}
const nodes = new Map();
const node = (id, fields) => { const result = element(id, fields); nodes.set(id, result); return result; };
node("encounter-filter-target", { value: "overlay" });
node("encounter-abduction-filter", { value: "any" });
node("encounter-being-filter", { value: "any" });
node("encounter-being-search");
for (const id of ["encounter-filter-state", "encounter-filter-summary", "encounter-being-selected-count", "encounter-being-search-status", "encounter-map-layer-toggle", "encounter-filter-status"]) node(id);
const presets = ["all", "abductions", "beings", "both"].map((key) => {
  node("encounter-preset-" + key + "-count");
  const button = node("encounter-preset-" + key);
  button.setAttribute("data-encounter-preset", key);
  return button;
});
const descriptionTypes = ["grey", "nordic", "humanoid"];
const inputs = descriptionTypes.map((key) => {
  const input = element("type-" + key, { value: key });
  input.setAttribute("data-encounter-being", "");
  return input;
});
const descriptionLabels = inputs.map((input, index) => {
  const label = element("label-" + input.value);
  label.setAttribute("data-encounter-label", descriptionTypes[index]);
  label.querySelector = () => input;
  return label;
});
const groupHeading = element("being-type-group", { className: "encounter-type-group" });
groupHeading.nextElementSibling = descriptionLabels[0];
descriptionLabels.forEach((label, index) => { label.nextElementSibling = descriptionLabels[index + 1] || null; });
const typeCounts = descriptionTypes.map((key) => {
  const count = element("count-" + key);
  count.setAttribute("data-encounter-type-count", key);
  return count;
});
const document = {
  getElementById: (id) => nodes.get(id) || null,
  querySelector: () => null,
  querySelectorAll: (selector) => {
    if (selector === "[data-encounter-being]:checked") return inputs.filter((input) => input.checked);
    if (selector === "[data-encounter-being]") return inputs;
    if (selector === "[data-encounter-preset]") return presets;
    if (selector === "[data-encounter-type-count]") return typeCounts;
    if (selector === ".encounter-being-option") return descriptionLabels;
    if (selector === "#encounter-being-types .encounter-type-group") return [groupHeading];
    return [];
  },
};

const sources = { 1: "ufocat", 2: "ufocat", 3: "mufon", 4: "nuforc", 5: "mufon", 6: "ufocat", 7: "nuforc", 8: "mufon" };
const claim = (id, abductionStatus, beingTypes, craftAssociation) => ({
  eventId: String(id), source: sources[id], sourceEventId: "fixture-" + id,
  abductionStatus, beingTypes, craftAssociation,
  evidence: [{ field: "fixture_only", excerpt: "Synthetic pinned report-content classification for integration regression.", ruleId: "fixture_only" }],
  sourceRef: { chunk: "chunk_000001", detailIndex: id, chunkSha256: "a".repeat(64) },
});
const payload = { schemaId: evidence.SCHEMA_ID, releaseId: evidence.RELEASE_ID, catalogCount: evidence.CATALOG_COUNT,
  taxonomy: evidence.TAXONOMY.map(({ key, label, group }) => ({ key, label, group })), rows: [
    claim(1, "source_reported", ["grey"], "explicit"), claim(2, "", ["grey"], "none_reported"),
    claim(3, "narrative_reported", [], "not_established"), claim(4, "", ["nordic"], "co_reported"),
    claim(5, "ambiguous", [], "not_established"), claim(6, "", ["humanoid"], "not_established"),
    claim(7, "", ["grey"], "co_reported"), claim(8, "source_reported", ["grey"], "explicit"),
  ] };
const evidenceIndex = evidence.createIndex(payload);
const report = (id, changes = {}) => ({ event_id: id, source: sources[id] || "ufocat", type: "Unknown",
  craft_type_inferred: "unknown", visual_type_group: "Other / unknown", date_precision: "exact_day", sort_ordinal: 101,
  has_coordinates: true, lat: 40, lon: -75, location_precision: "city", coordinate_source: "source_provided",
  date_raw: "fixture-day", location_display: "Fixture locality", country: "USA", ...changes });
const originals = [
  report(1, { type: "Disk", craft_type_inferred: "disc_saucer", sort_ordinal: 100 }),
  report(2, { craft_type_inferred: "non_ufo_context", lat: 41, lon: -73 }),
  report(3, { type: "Triangle", craft_type_inferred: "triangle", has_coordinates: false, lat: null, lon: null, location_precision: "unknown", coordinate_source: "unresolved" }),
  report(4, { type: "Light", craft_type_inferred: "light", sort_ordinal: 104 }),
  report(5),
  report(6, { sort_ordinal: 102, has_coordinates: false, lat: null, lon: null, location_precision: "unknown", coordinate_source: "unresolved" }),
  report(7, { type: "Sphere", craft_type_inferred: "sphere_orb", lat: 48, lon: 2, location_precision: "country", country: "FRA" }),
  report(8, { type: "Triangle", craft_type_inferred: "triangle", lon: -73 }),
  report(9, { type: "Disk", craft_type_inferred: "disc_saucer" }),
];
const catalog = originals.map((value) => evidence.decorate(value, evidenceIndex));
const originalBytes = JSON.stringify(originals);
const catalogBytes = JSON.stringify(catalog);
const catalogById = new Map(catalog.map((value) => [String(value.event_id), value]));
const filterControls = {
  source: { mode: "all", selectedValues: [] }, type: { mode: "subset", selectedValues: ["Disk"] }, precision: { mode: "all", selectedValues: [] },
};
let legendSelection = { mode: "subset", colorMode: "craft_type", selectedKeys: ["disc_saucer"] };
const state = { filterGeneration: 1, filterToken: 1, timeRangeMode: "window", timeRangeStartOrdinal: 100, timeRangeEndOrdinal: 102,
  lastKeywordMatches: null, encounterAnalysisSelectionIds: null, analysisCountryAreaFilter: "",
  regionSelection: { shapes: [] }, filteredCatalog: [catalog[0], catalog[8]], filteredMappedCatalog: [catalog[0], catalog[8]],
  mapLegendEventSelection: legendSelection, colorMode: "craft_type", traceMode: "off", filteredMappedEventIdSet: new Set(["1", "9"]) };
const originalCraftCohort = state.filteredCatalog, originalMappedCraftCohort = state.filteredMappedCatalog;
let boundsValue = { north: 90, south: -90, west: -180, east: 180 };
let zoomValue = 4, refreshCalls = 0, resetPlaybackCalls = 0, legendRenderCalls = 0, markerBuilds = 0;
const createdPolylines = [];
const map = { getBounds: () => ({ getNorth: () => boundsValue.north, getSouth: () => boundsValue.south, getWest: () => boundsValue.west, getEast: () => boundsValue.east }),
  getZoom: () => zoomValue, getCenter: () => ({ lng: 0 }), hasLayer: () => true };
const layer = { members: [], clearLayers() { this.members = []; } };
const highlightLayer = { members: [], clearLayers() { this.members = []; } };
const runtime = { map, encounterStatus: "ready", encounterEvidence: evidenceIndex, encounterIndexedIds: payload.rows.map((row) => row.eventId),
  encounterLabelOrigins: null, encounterMapEnabled: true, encounterMapHiddenKinds: new Set(), encounterMapIncludeAmbiguous: false,
  encounterMapModel: null, encounterMapModelKey: "", encounterMapEvents: [], encounterMapBaseEvents: [], encounterMapLayer: layer,
  encounterTraceHighlightLayer: highlightLayer, encounterTraceHighlightEventId: null, staticTraceLayer: { _segments: [] }, playbackTrailCanvasLayer: { _segments: [] },
};
const els = { keywordInput: element("keyword"), hideLowPrecisionToggle: element("hide-low"), hideNonExactDatesToggle: element("hide-partial", { checked: true }), famousCaseSearch: element("case-search") };
let countryWorker = null;
const pendingTimers = new Map();
let nextTimerId = 0;
const staticTraceDirectionPopulations = new WeakMap();
const context = vm.createContext({
  ENCOUNTERS: evidence, ENCOUNTER_MAP: encounterMap, LOW_PRECISION_VALUES: new Set(["unknown", "country", "approximate"]),
  state, runtime, document, catalog, els, Set, Map, staticTraceDirectionPopulations,
  effectiveMultiSelectState: (key) => filterControls[key], normalizedMapLegendEventSelection: () => legendSelection,
  eventLegendKeyForMode: (event) => event.craft_type_inferred,
  resolvedCraftTypeForEvent: (event) => ({ key: event.craft_type_inferred, label: event.craft_type_inferred, color: "#38bdf8" }),
  displayLocationForEvent: (event) => event.location_display || "Location unresolved",
  getCatalogEventById: (id) => catalogById.get(String(id)) || null,
  regionSelectionAffectsRendering: () => state.regionSelection.shapes.length > 0,
  regionSelectionShapesSignature: () => JSON.stringify(state.regionSelection.shapes),
  pointInsideAnyRegionShape: (lat, lon, shapes) => shapes.some((shape) => lat >= shape.south && lat <= shape.north && lon >= shape.west && lon <= shape.east),
  isoToOrdinal: (iso) => Date.parse(iso + "T00:00:00Z") / 86400000,
  formatNumber: (value) => String(value), useMobileTapTargets: () => false,
  escapeHtml: (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]),
  scheduleRefresh: () => { refreshCalls += 1; }, resetPlayback: () => { resetPlaybackCalls += 1; }, renderMapLegend: () => { legendRenderCalls += 1; },
  clearFamousCaseCirclePulse: () => {}, renderFamousCasePicker: () => {}, renderAllMultiSelectStates: () => {},
  ensureCatalogFacetWorker: () => countryWorker,
  window: { setTimeout: (callback) => { const id = ++nextTimerId; pendingTimers.set(id, callback); return id; }, clearTimeout: (id) => pendingTimers.delete(id) },
  applyMultiSelectAction: (key, action) => { filterControls[key].mode = action === "all" ? "all" : "subset"; filterControls[key].selectedValues = action === "all" ? [] : ["Disk"]; },
  L: {
    divIcon: (options) => options,
    marker: (latLng, options) => { markerBuilds += 1; return { latLng, options, bindPopup(markup, popupOptions) { this.markup = markup; this.popupOptions = popupOptions; return this; }, addTo(target) { target.members.push(this); return this; } }; },
    polyline: (latLngs, options) => { const value = { latLngs, options, addTo(target) { target.members.push(this); return this; } }; createdPolylines.push(value); return value; },
  },
});
for (const name of ["encounterFilterSelections", "encounterOverlaySelections", "getCurrentKeyword", "currentFilterSelections", "eventMatchesMapLegendEventSelection", "eventMatchesNonDateFilters", "eventMatchesTimeRange", "encounterOverlayBaseEvents", "ensureEncounterCountryMembership", "filterEncounterDescriptionChoices", "updateEncounterControlSummary", "ensureEncounterMapModel", "normalizeTraceMode", "traceModeIncludesStatic", "traceModeIncludesPlayback", "encounterTraceScopeKey", "getEncounterMapEventById", "encounterTraceSegmentsForReport", "highlightEncounterReportTraces", "displayLocationForEvent", "encounterReportInspectionHtml", "renderEncounterMapLayer", "buildEncounterMapLegend", "applyEncounterControlsChange", "resetFilterControlsToDefaultState"]) {
  vm.runInContext(appFunction(name), context, { filename: "app.js:" + name });
}
const baseIds = () => plain(context.encounterOverlayBaseEvents().map((value) => value.event_id));
const invalidate = () => { runtime.encounterMapModelKey = ""; state.filterGeneration += 1; };
const select = (abduction = "any", being = "any", types = []) => {
  nodes.get("encounter-abduction-filter").value = abduction; nodes.get("encounter-being-filter").value = being;
  inputs.forEach((input) => { input.checked = types.includes(input.value); });
};

// Default encounter choices scope only the overlay. Normal craft/results/
// Analysis selections remain neutral until the explicit target is changed.
assert.match(indexCode, /id="encounter-filter-target"[\s\S]*?<option value="overlay" selected>/);
select("reported", "reported", ["grey"]);
assert.deepEqual(plain(context.encounterFilterSelections()), { abduction: "any", being: "any", beingTypes: [] });
assert.deepEqual(plain(context.encounterOverlaySelections()), { abduction: "reported", being: "reported", beingTypes: ["grey"] });
nodes.get("encounter-filter-target").value = "reports";
assert.deepEqual(plain(context.encounterFilterSelections()), { abduction: "reported", being: "reported", beingTypes: ["grey"] });
nodes.get("encounter-filter-target").value = "overlay";
select();

// Overlay baseline bypasses raw type and craft legend visibility, while dates,
// collection, search, precision, selected areas and explicit ID scopes survive.
assert.deepEqual(baseIds(), [1, 2, 3, 5, 6, 7, 8]);
filterControls.type.mode = "none";
legendSelection = { mode: "none", colorMode: "craft_type", selectedKeys: [] };
assert.deepEqual(baseIds(), [1, 2, 3, 5, 6, 7, 8]);
filterControls.source.mode = "subset"; filterControls.source.selectedValues = ["ufocat"];
assert.deepEqual(baseIds(), [1, 2, 6]);
filterControls.source.mode = "none";
assert.deepEqual(baseIds(), []);
filterControls.source.mode = "all"; filterControls.source.selectedValues = [];
els.keywordInput.value = "fixture"; state.lastKeywordMatches = new Set([1, 3, 8]);
assert.deepEqual(baseIds(), [1, 3, 8]);
els.keywordInput.value = ""; state.lastKeywordMatches = null;
filterControls.precision.mode = "subset"; filterControls.precision.selectedValues = ["unknown"];
assert.deepEqual(baseIds(), [3, 6]);
filterControls.precision.mode = "none";
assert.deepEqual(baseIds(), []);
filterControls.precision.mode = "all"; filterControls.precision.selectedValues = [];
els.hideLowPrecisionToggle.checked = true;
assert.deepEqual(baseIds(), [1, 2, 5, 8]);
els.hideLowPrecisionToggle.checked = false;
state.regionSelection.shapes = [{ south: 39, north: 42, west: -76, east: -72 }];
assert.deepEqual(baseIds(), [1, 2, 5, 8], "Unmapped reports remain available without an area, but cannot acquire area membership");
state.regionSelection.shapes = [];
state.encounterAnalysisSelectionIds = new Set(["2", "3", "8"]);
assert.deepEqual(baseIds(), [2, 3, 8]);
state.encounterAnalysisSelectionIds = null;
state.timeRangeStartOrdinal = 102; state.timeRangeEndOrdinal = 102;
assert.deepEqual(baseIds(), [6]);
state.timeRangeStartOrdinal = 100; state.timeRangeEndOrdinal = 102;

const model = context.ensureEncounterMapModel();
assert.equal(model.cohort.reports, 6);
assert.equal(model.cohort.mapped, 4);
assert.equal(model.cohort.unmapped, 2);
assert.deepEqual(plain(model.viewport.kinds), { abduction: 0, being: 2, both: 2, ambiguous: 0 });
assert.deepEqual(plain(model.unmappedEventIds), ["3", "6"]);
assert.equal(model.rendering.displayedReports, 4);
assert.equal(layer.members.length, model.markers.length);
assert.equal(createdPolylines.length, 0, "Mapping encounters creates no relationship edges");
assert.equal(state.filteredCatalog, originalCraftCohort);
assert.equal(state.filteredMappedCatalog, originalMappedCraftCohort);
assert.deepEqual(Array.from(state.filteredMappedEventIdSet), ["1", "9"]);
assert.equal(JSON.stringify(originals), originalBytes);
assert.equal(JSON.stringify(catalog), catalogBytes);
assert.equal(filterControls.type.mode, "none");
assert.equal(legendSelection.mode, "none");
const builds = markerBuilds;
assert.equal(context.ensureEncounterMapModel(), model, "Identical overlay scope and viewport reuse the current model");
assert.equal(markerBuilds, builds);
boundsValue = { north: 42, south: 39, west: -76, east: -74 };
const narrow = context.ensureEncounterMapModel();
assert.notEqual(narrow, model);
assert.equal(narrow.viewport.reports, 1);
assert.equal(narrow.cohort.reports, 6);
zoomValue += 1;
assert.notEqual(context.ensureEncounterMapModel(), narrow);
boundsValue = { north: 90, south: -90, west: -180, east: 180 };
invalidate();
const legend = context.buildEncounterMapLegend();
assert.match(legend, /data-encounter-legend-kind="abduction"[\s\S]*?<strong>0<\/strong>/);
assert.match(legend, /data-encounter-legend-kind="being"[\s\S]*?<strong>2<\/strong>/);
assert.match(legend, /data-encounter-legend-kind="both"[\s\S]*?<strong>2<\/strong>/);
assert.match(legend, /6 in selected encounter scope · 2 unmapped/);
assert.match(legend, /independent of craft-type visibility/);
assert.doesNotMatch(legend, /verified encounter|abduction route|same spacecraft/);
runtime.encounterMapHiddenKinds.add("being");
invalidate();
const hidden = context.ensureEncounterMapModel();
assert.equal(hidden.cohort.reports, 6, "Hiding a marker kind cannot change scope report counts or inspector membership");
assert.equal(hidden.viewport.kinds.being, 2);
assert.equal(hidden.reports.length, 6);
assert.ok(hidden.markers.flatMap((entry) => entry.records).every((entry) => entry.classification.kind !== "being"));
assert.equal(hidden.rendering.displayedReports, 2);
assert.match(context.buildEncounterMapLegend(), /data-encounter-legend-kind="being" aria-pressed="false"[\s\S]*?<strong>2<\/strong>/);
runtime.encounterMapHiddenKinds.clear();
invalidate();

// Selection changes update only the overlay in its default target. Reports and
// Analysis filtering is a separate action, not a side effect of a preset.
select("reported");
context.applyEncounterControlsChange();
assert.equal(runtime.encounterMapModel.cohort.reports, 3);
assert.equal(refreshCalls, 0);
assert.equal(resetPlaybackCalls, 0);
assert.ok(legendRenderCalls > 0);
nodes.get("encounter-filter-target").value = "reports";
context.applyEncounterControlsChange();
assert.equal(refreshCalls, 1);
assert.equal(resetPlaybackCalls, 1);
nodes.get("encounter-filter-target").value = "overlay";
select();

// Search is an option-list operation. The selected nonmatching label stays
// visible and no expensive catalog refresh/analysis/playback is scheduled.
const searchStart = appCode.indexOf('    const encounterSearch = document.getElementById("encounter-being-search");');
assert.ok(searchStart >= 0, "Actual search binding absent");
const searchEnd = appCode.indexOf('\n    document.querySelectorAll("[data-encounter-preset]")', searchStart);
assert.ok(searchEnd > searchStart);
vm.runInContext(appCode.slice(searchStart, searchEnd), context, { filename: "app.js:encounter search binding" });
const searchHandler = nodes.get("encounter-being-search").listeners.get("input");
assert.equal(typeof searchHandler, "function");
inputs[1].checked = true;
nodes.get("encounter-being-search").value = "grey";
const refreshBeforeSearch = refreshCalls;
searchHandler();
assert.equal(descriptionLabels[0].hidden, false);
assert.equal(descriptionLabels[1].hidden, false);
assert.equal(descriptionLabels[2].hidden, true);
assert.equal(groupHeading.hidden, false);
assert.match(nodes.get("encounter-being-search-status").textContent, /2 descriptions shown/);
assert.equal(refreshCalls, refreshBeforeSearch);
assert.equal(state.filteredCatalog, originalCraftCohort);

// Query the actual catalog worker's reviewed geography projection. A source
// country survives a withheld/unknown assignment, and an established projected
// country takes precedence. The app query remains neutral to craft filters.
const workerMessages = [];
const workerSelf = { postMessage: (message) => workerMessages.push(message), UFOEncounterEvidence: evidence };
const workerContext = vm.createContext({ self: workerSelf, console });
const workerCode = fs.readFileSync("catalog_filter_worker.js", "utf8");
const listenerMarker = "  self.onmessage =";
assert.ok(workerCode.includes(listenerMarker));
// Expose the actual internal projection installer for this bounded fixture;
// production source is unchanged by this VM-only test hook.
vm.runInContext(workerCode.replace(listenerMarker, "  self.__testApplyGeographyRows = applyGeographyRowsToCatalog;\n" + listenerMarker), workerContext, { filename: "catalog_filter_worker.js:geography integration" });
workerSelf.onmessage({ data: { type: "addCatalogFacetRows", rows: catalog.map((value) => ({
  eventId: value.event_id, source: value.source, type: value.type, visualTypeGroup: value.visual_type_group,
  craftType: value.craft_type_inferred, precision: value.location_precision, datePrecision: value.date_precision,
  coordinateSource: value.coordinate_source, country: value.country, lat: value.lat, lon: value.lon, mapped: value.has_coordinates,
  sortOrdinal: value.sort_ordinal, encounterEvidenceReady: value.encounterEvidenceReady, encounterAbductionCode: value.encounterAbductionCode,
  encounterBeingMask: value.encounterBeingMask, encounterCraftAssociationCode: value.encounterCraftAssociationCode,
})) } });
const projectedCountries = { 1: 1, 2: 0, 4: 2, 5: 1, 7: 2, 8: 2, 9: 1 };
workerSelf.__testApplyGeographyRows(catalog.filter((value) => value.has_coordinates).map((value, index) => [index, String(value.event_id), projectedCountries[value.event_id], 0, 0, 0, 0]),
  { codes: { ufoGeography: { country: ["unknown", "USA", "FRA"], macroregion: ["unknown"], assignmentSource: ["fixture"], assignmentConfidence: ["fixture"], boundaryStatus: ["fixture"] } } });
const countryRequests = [], countryListeners = new Set();
countryWorker = { addEventListener: (_, listener) => countryListeners.add(listener), removeEventListener: (_, listener) => countryListeners.delete(listener), postMessage: (message) => countryRequests.push(message) };
runtime.analysisGeographyWorkerReady = true; runtime.catalogFacetWorkerRowsQueued = catalog.length; runtime.catalogFacetWorkerRequestId = 0;
const completeCountry = () => {
  const request = countryRequests.at(-1);
  workerMessages.length = 0;
  workerSelf.onmessage({ data: request });
  assert.equal(workerMessages.length, 1);
  assert.equal(workerMessages[0].type, "filteredCatalogIdsComputed");
  for (const listener of Array.from(countryListeners)) listener({ data: workerMessages[0] });
  return request;
};
state.analysisCountryAreaFilter = "USA";
assert.deepEqual(baseIds(), [], "Pending country projection cannot masquerade as unrestricted geography");
assert.equal(runtime.encounterCountryStatus, "loading");
const usaRequest = completeCountry();
assert.equal(usaRequest.selectedAreaCountry, "USA");
assert.equal(usaRequest.typeMode, "all");
assert.equal(usaRequest.legendEventMode, "all");
assert.deepEqual(plain(usaRequest.encounterSelectionIds), payload.rows.map((value) => value.eventId));
assert.deepEqual(baseIds(), [1, 2, 3, 5, 6], "Unknown projection preserves report country; projected France overrides source USA");
const countryRequestCount = countryRequests.length;
assert.deepEqual(baseIds(), [1, 2, 3, 5, 6]);
assert.equal(countryRequests.length, countryRequestCount, "Completed country membership is cached for its own scope");
state.analysisCountryAreaFilter = "FRA";
assert.deepEqual(baseIds(), []);
completeCountry();
assert.deepEqual(baseIds(), [7, 8]);
state.analysisCountryAreaFilter = "CAN";
assert.deepEqual(baseIds(), []);
const staleRequest = countryRequests.at(-1);
state.analysisCountryAreaFilter = "USA";
assert.deepEqual(baseIds(), []);
for (const listener of Array.from(countryListeners)) listener({ data: { type: "filteredCatalogIdsComputed", requestId: staleRequest.requestId, result: { eventIds: [7] } } });
assert.equal(runtime.encounterCountryIds, null, "Late replies cannot install membership into another country scope");
completeCountry();
assert.deepEqual(baseIds(), [1, 2, 3, 5, 6]);
state.analysisCountryAreaFilter = "";
invalidate();

// The actual full reset removes an exact Analysis-applied ID scope, and clears
// the source-label facets rather than leaving an invisible residual selection.
state.encounterAnalysisSelectionIds = new Set(["3"]);
select("reported", "reported", ["grey", "nordic"]);
context.resetFilterControlsToDefaultState();
assert.equal(state.encounterAnalysisSelectionIds, null);
assert.deepEqual(plain(context.encounterOverlaySelections()), { abduction: "any", being: "any", beingTypes: [] });
assert.equal(els.keywordInput.value, "");
assert.equal(JSON.stringify(originals), originalBytes);
assert.equal(JSON.stringify(catalog), catalogBytes);

// Existing-link highlighting is exact endpoint membership in a current, active
// layer. No relationship edges are synthesized from coordinate/date proximity.
const traceA = { traceId: "a", fromEventId: 1, toEventId: "9", from: [40, 179], to: [41, 181], sameDayOrderKnown: false };
const traceB = { traceId: "b", fromEventId: "8", toEventId: "1", from: [39, 178], to: [40, 179], sameDayOrderKnown: true };
const nearbyUnrelated = { traceId: "unrelated", fromEventId: "90", toEventId: "91", from: [40, 179], to: [41, 181] };
const incomplete = { traceId: "invalid", fromEventId: 1, toEventId: 22, from: null, to: [40, 179] };
runtime.staticTraceLayer._segments = [traceA, plain(traceA), traceB, nearbyUnrelated, incomplete];
runtime.playbackTrailCanvasLayer._segments = [plain(traceA), traceB];
runtime.neighborhoodTraceLayer = { _segments: [plain(traceA)] };
const activeLayers = new Set([runtime.staticTraceLayer, runtime.playbackTrailCanvasLayer]);
map.hasLayer = (value) => activeLayers.has(value);
state.traceMode = "static";
runtime.staticTraceLayer._encounterScopeKey = context.encounterTraceScopeKey();
runtime.playbackTrailCanvasLayer._encounterScopeKey = context.encounterTraceScopeKey();
runtime.neighborhoodTraceLayer._encounterScopeKey = context.encounterTraceScopeKey();
staticTraceDirectionPopulations.set(runtime.staticTraceLayer._segments, { status: "loading" });
assert.equal(context.encounterTraceSegmentsForReport("1").length, 0, "Unresolved render populations cannot be highlighted as current lines");
staticTraceDirectionPopulations.set(runtime.staticTraceLayer._segments, { status: "ready" });
assert.deepEqual(plain(context.encounterTraceSegmentsForReport("1")), [traceA, traceB]);
state.traceMode = "playback";
assert.deepEqual(plain(context.encounterTraceSegmentsForReport(1)), [traceA, traceB], "Only the active playback population is used; repeated static segment IDs do not fabricate relations");
const traceBytes = JSON.stringify([runtime.staticTraceLayer._segments, runtime.playbackTrailCanvasLayer._segments, runtime.neighborhoodTraceLayer._segments]);
map.getCenter = () => ({ lng: -180 });
context.highlightEncounterReportTraces(1);
assert.equal(highlightLayer.members.length, 2);
assert.deepEqual(plain(highlightLayer.members[0].latLngs), [[40, -181], [41, -179]]);
assert.equal(highlightLayer.members[0].options.interactive, false);
assert.equal(JSON.stringify([runtime.staticTraceLayer._segments, runtime.playbackTrailCanvasLayer._segments, runtime.neighborhoodTraceLayer._segments]), traceBytes);
assert.equal(traceA.sameDayOrderKnown, false, "Highlighting does not resolve or reorder an uncertain trace");
state.filterGeneration += 1;
assert.equal(context.encounterTraceSegmentsForReport(1).length, 0, "A stale scope cannot revive historical layer segments");
context.highlightEncounterReportTraces(1);
assert.equal(highlightLayer.members.length, 0);
runtime.staticTraceLayer._encounterScopeKey = context.encounterTraceScopeKey();
runtime.playbackTrailCanvasLayer._encounterScopeKey = context.encounterTraceScopeKey();
runtime.traceFacilityWorkerPendingKey = "pending-facility-result";
state.traceMode = "static";
assert.equal(context.encounterTraceSegmentsForReport(1).length, 0);
context.highlightEncounterReportTraces(1);
assert.equal(highlightLayer.members.length, 0);
runtime.traceFacilityWorkerPendingKey = "";
activeLayers.delete(runtime.staticTraceLayer);
assert.equal(context.encounterTraceSegmentsForReport(1).length, 0, "An inactive trace layer is not a visible relationship");
activeLayers.add(runtime.staticTraceLayer);
context.highlightEncounterReportTraces(1);
assert.equal(highlightLayer.members.length, 2);
state.traceMode = "off";
context.highlightEncounterReportTraces(1);
assert.equal(highlightLayer.members.length, 0, "Turning ordinary traces off clears their existing highlights");

// A separately visible selection-neighborhood layer can be inspected even
// with ordinary traces off; membership still comes only from its exact IDs.
state.regionSelection.shapes = [{ south: 39, north: 42, west: -180, east: 180 }];
runtime.neighborhoodTraceLayer._encounterScopeKey = context.encounterTraceScopeKey();
activeLayers.add(runtime.neighborhoodTraceLayer);
assert.deepEqual(plain(context.encounterTraceSegmentsForReport(1)), [traceA]);
context.highlightEncounterReportTraces(1);
assert.equal(highlightLayer.members.length, 1);
state.regionSelection.shapes = [];
context.highlightEncounterReportTraces(1);
assert.equal(highlightLayer.members.length, 0);
context.highlightEncounterReportTraces(null);
assert.equal(runtime.encounterTraceHighlightEventId, null);

const sourceLocationOnly = { ...catalog[1], location_display: "", location_raw: "Source locality <unchanged>" };
const noCraftPopup = context.encounterReportInspectionHtml(sourceLocationOnly);
assert.match(noCraftPopup, /Source locality &lt;unchanged&gt;/);
assert.match(noCraftPopup, /No craft association reported/);
assert.doesNotMatch(noCraftPopup, /encounter-craft-sample/);
assert.doesNotMatch(noCraftPopup, /data-encounter-highlight-report/);
const explicitPopup = context.encounterReportInspectionHtml(catalog[0]);
assert.match(explicitPopup, /Explicit craft association in the same report/);
assert.match(explicitPopup, /encounter-craft-sample/);
const unmappedPopup = context.encounterReportInspectionHtml(catalog[2]);
assert.match(unmappedPopup, /Unmapped: no location invented/);
assert.doesNotMatch(unmappedPopup, /data-encounter-locate-report/);
assert.equal(JSON.stringify(originals), originalBytes);
assert.equal(JSON.stringify(catalog), catalogBytes);
console.log("Actual encounter overlay, scope/geo/legend/cache/target/search/reset, and exact existing-trace highlight lifecycle integration passed.");
