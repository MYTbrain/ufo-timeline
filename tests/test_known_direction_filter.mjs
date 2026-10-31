import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const directions = require("../trace_direction_summary.js");
const neighborhood = require("../trace_neighborhood.js");
const chronology = require("../trace_chronology.js");
const source = readFileSync(new URL("../app.js", import.meta.url), "utf8");

function extractFunction(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, name);
  const end = source.indexOf("\n  function ", start + 1);
  return source.slice(start, end);
}

const ordered = { traceId: "A->B", fromEventId: "A", toEventId: "B", from: [0, 0], to: [1, 1], gapDays: 1 };
const unordered = { traceId: "B->C", fromEventId: "B", toEventId: "C", from: [1, 1], to: [2, 2], gapDays: 0 };
assert.equal(directions.segmentHasKnownDirection(ordered), true);
assert.equal(directions.segmentHasKnownDirection(unordered), false);
assert.equal(directions.segmentHasKnownDirection({ ...unordered, sameDayOrderKnown: true }), true);
assert.equal(directions.segmentHasKnownDirection({ ...ordered, sameDayOrderKnown: false }), false);
assert.equal(directions.segmentHasKnownDirection({ ...ordered, chronology: { status: "unknown" }, sameDayOrderKnown: true }), false, "authoritative uncertainty wins over legacy flags and positive day gaps");
assert.equal(directions.segmentHasKnownDirection({ ...unordered, chronology: { status: "ordered" } }), true, "accepted same-day chronology is retained");
assert.equal(directions.segmentHasKnownDirection({ ...ordered, neighborhood: { direction: "both" } }), true, "both traversal directions do not mean unknown chronology");
for (const gapDays of [undefined, null, "", false, -1, Infinity, "unknown"]) {
  assert.equal(directions.segmentHasKnownDirection({ ...ordered, gapDays }), false, `missing or invalid ordering evidence: ${gapDays}`);
}
for (const invalid of [{ from: [null, 0] }, { to: [0, 0] }, { from: [86, 0], to: [87, 0] }]) {
  assert.equal(directions.segmentHasKnownDirection({ ...ordered, ...invalid }), false);
}

// Exercise the current source-backed timing contract, not only hand-set flags.
const day = Date.parse("1986-01-29T00:00:00Z");
const hour = 3600000;
const evidence = chronology.createEvidenceIndex({
  schemaId: chronology.SCHEMA_ID, sourceContract: chronology.SOURCE_CONTRACT,
  releaseId: "known-direction-test", rowSchema: [...chronology.ROW_SCHEMA],
  rows: [[1, day + hour, day + hour + 59999, 0, 0], [2, day + 2 * hour, day + 2 * hour + 59999, 0, 0]],
  codes: { evidence: [{ status: "accepted", kind: "source_clock", confidence: "high", basis: "Preserved source clock and timezone" }], zone: ["UTC"] },
});
const reports = [1, 2, 3].map(id => ({ event_id: id, lat: id, lon: id, has_coordinates: true,
  sort_date_iso: "1986-01-29", sort_ordinal: day / 86400000, date_precision: "exact_day", craft_type_inferred: "sphere_orb" }));
const caseSegments = neighborhood.buildSameDayCraftTraceSegments(reports, { chronology: evidence, timingSupport: chronology });
assert.equal(caseSegments.length, 2);
assert.deepEqual(caseSegments.filter(directions.segmentHasKnownDirection).map(segment => segment.traceId), ["1->2"], "accepted clock link survives while missing timing is filtered");

const state = { traceMode: "static", regionSelection: { knownDirectionOnly: false }, filterGeneration: 1, showTraceDirectionArrows: true };
let caseActive = false;
const rawSegments = [ordered, unordered];
const calls = { invalidate: 0, close: 0, refresh: 0, playback: 0, legend: 0, header: 0, message: "" };
const runtime = { largeWindowTraceBuildToken: 1, largeWindowTraceBuildKey: "old", traceFacilityWorkerRenderToken: 1, traceFacilityWorkerPendingKey: "old" };
const context = vm.createContext({ state, runtime, TRACE_DIRECTIONS: directions,
  TRACE_NEIGHBORHOOD: neighborhood, CHRONOLOGICAL_NEIGHBORHOOD_DEFAULT_DEPTH: 0,
  CHRONOLOGICAL_NEIGHBORHOOD_DEFAULT_DIRECTION: "forward",
  famousCaseTraceSelectionActive: () => caseActive,
  buildCanonicalTraceSegments: () => rawSegments, buildFamousCaseTraceSegments: () => caseSegments,
  normalizeTraceMode: value => value,
  activeTraceBuckets: () => [{ key: "gap_le_1" }], traceFacilityFilterSignature: () => "off",
  closeChronologicalNeighborhoodInspector: () => calls.close++,
  invalidateTraceSequenceCache: () => calls.invalidate++,
  syncPlaybackTrailVisibility: () => calls.playback++,
  refreshRegionSelectionRenderState: () => calls.refresh++,
  renderLegendTraceDirectionPanel: () => calls.legend++, renderMapLegendHeaderControls: () => calls.header++,
  announceMapLegendStatus: message => calls.message = message,
});
vm.runInContext(["currentSelectableTraceSegments", "currentRegionSelectionTraceKey", "defaultRegionSelectionState", "setKnownTraceDirectionOnly"].map(extractFunction).join("\n"), context);
assert.equal(context.defaultRegionSelectionState().knownDirectionOnly, true, "fresh views and resets show only known-direction connections");
assert.equal(context.currentSelectableTraceSegments(), rawSegments, "disabled filter preserves the existing cached sequence");
const allKey = context.currentRegionSelectionTraceKey();
context.setKnownTraceDirectionOnly(true);
assert.equal(state.showTraceDirectionArrows, true, "the filter does not reset existing arrow preferences");
assert.deepEqual(calls, { invalidate: 1, close: 1, refresh: 1, playback: 1, legend: 1, header: 1, message: "Only traces with known report order are shown." });
assert.equal(runtime.largeWindowTraceBuildToken, 2, "in-flight global renders cannot put unfiltered traces back");
assert.equal(runtime.traceFacilityWorkerRenderToken, 2, "in-flight facility renders cannot put unfiltered traces back");
assert.notEqual(context.currentRegionSelectionTraceKey(), allKey, "switching invalidates neighborhood and result caches");
const filtered = context.currentSelectableTraceSegments();
assert.deepEqual(filtered, [ordered]);
assert.deepEqual(rawSegments, [ordered, unordered]);
const events = ["A", "B", "C"].map((event_id, index) => ({ event_id, lat: index, lon: index }));
function reached(segments) {
  const index = neighborhood.buildNeighborhoodIndex(segments, events, 1);
  return neighborhood.traverseNeighborhood({ index, depth: 4, direction: "both",
    eventSeeds: [{ eventId: "A", regionIds: ["test-area"] }], traceSeeds: [] });
}
assert.ok(reached(rawSegments).eventIds.has("C"));
assert.equal(reached(filtered).eventIds.has("C"), false, "hidden links cannot bridge to remote related sightings");
caseActive = true;
assert.deepEqual(context.currentSelectableTraceSegments().map(segment => segment.traceId), ["1->2"]);
context.setKnownTraceDirectionOnly(false);
assert.equal(context.currentSelectableTraceSegments(), caseSegments, "unchecking restores all case connections");
state.traceMode = "off";
assert.equal(context.currentSelectableTraceSegments().length, 0);
const markup = extractFunction("renderMapLegend");
assert.ok(markup.indexOf('id="legend-known-direction-only"') > markup.indexOf('id="legend-trace-arrows"'));
assert.match(markup, /aria-describedby="legend-known-direction-help"/);
assert.match(extractFunction("resetMapLegendControls"), /state\.regionSelection\.knownDirectionOnly = defaultKnownDirectionOnly/);
assert.match(extractFunction("resetViewState"), /state\.regionSelection = Object\.assign\(\{\}, defaults\.regionSelection/);
assert.match(extractFunction("createDefaultResetViewState"), /showTraceDirectionArrows: false/);
assert.match(extractFunction("resetViewState"), /state\.showTraceDirectionArrows = defaults\.showTraceDirectionArrows/);
// The ordinary map needs the same controls as a selected area or case.
let selectedArea = false;
let pointOnly = false;
const arrowToggle = {};
const knownToggle = {};
const holder = { firstChild: {}, querySelector: () => null };
const arrowCalls = { static: 0, playback: 0, neighborhood: 0 };
const arrowContext = vm.createContext({
  state, runtime: { legendTraceDirectionMarkup: "summary",
    staticTraceLayer: { _redraw: () => arrowCalls.static++ },
    playbackTrailCanvasLayer: { _redraw: () => arrowCalls.playback++ } },
  els: {}, document: { getElementById: id => ({
    "legend-trace-direction-summary": holder,
    "legend-trace-arrows": arrowToggle,
    "legend-known-direction-only": knownToggle,
  })[id] },
  TRACE_DIRECTIONS: { legendSummaryMarkup: () => "summary" },
  TRACE_DIRECTION_ARROWS_STORAGE_KEY: "arrows", safeStorageSet: () => {},
  legendTraceDirectionView: () => ({ summary: {} }),
  regionSelectionAffectsRendering: () => selectedArea,
  currentRegionSelectionResult: () => ({ pointOnly }),
  renderChronologicalNeighborhoodOverlay: () => arrowCalls.neighborhood++,
  renderMapLegendHeaderControls: () => {}, announceMapLegendStatus: () => {},
});
vm.runInContext(["renderLegendTraceDirectionPanel", "setTraceDirectionArrowsVisible"].map(extractFunction).join("\n"), arrowContext);
state.traceMode = "static";
arrowContext.renderLegendTraceDirectionPanel();
assert.equal(arrowToggle.disabled, false, "global static traces do not require selecting an area");
state.traceMode = "playback";
arrowContext.renderLegendTraceDirectionPanel();
assert.equal(arrowToggle.disabled, false, "global playback arrows remain available");
arrowContext.setTraceDirectionArrowsVisible(false);
assert.deepEqual(arrowCalls, { static: 1, playback: 1, neighborhood: 1 }, "arrow toggle redraws every supported presentation");
assert.equal(state.regionSelection.knownDirectionOnly, false, "arrow visibility never changes the direction filter");
selectedArea = true; pointOnly = true;
arrowContext.renderLegendTraceDirectionPanel();
assert.equal(arrowToggle.disabled, true, "a points-only selection has no arrow layer");
pointOnly = false; state.traceMode = "off";
arrowContext.renderLegendTraceDirectionPanel();
assert.equal(arrowToggle.disabled, false, "case/area connections retain arrows when ordinary traces are off");
selectedArea = false; state.traceMode = "off";
arrowContext.renderLegendTraceDirectionPanel();
assert.equal(arrowToggle.disabled, true, "arrows are disabled only when trace lines are unavailable");
console.log("Known-direction filter passed: accepted same-day clocks, authoritative uncertainty, traversal, cache invalidation, legend controls and reset.");
