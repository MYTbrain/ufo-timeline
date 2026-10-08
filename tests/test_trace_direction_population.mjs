import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const directions = require("../trace_direction_summary.js");
const chronology = require("../trace_chronology.js");
const source = readFileSync(new URL("../app.js", import.meta.url), "utf8");

function between(start, end) {
  const first = source.indexOf(start);
  const last = source.indexOf(end, first);
  assert.ok(first >= 0 && last > first, "The actual app function must exist");
  return source.slice(first, last);
}

const populationHelpers = between(
  "const staticTraceDirectionPopulations = new WeakMap();",
  "function createStaticTraceLayer(options)"
);
const packedBuilder = between(
  "function buildCanonicalPackedTraceRenderSegments(",
  "function buildPackedTraceFacilityWorkerCandidateSegments("
);
const orientSource = between("function applyTraceChronology(", "function canonicalTraceSegmentsCacheKey(");
const date = Date.parse("2000-01-01T00:00:00Z");
const hour = 3600000;
const events = [
  { event_id: 1, lat: 0, lon: 0 },
  { event_id: 2, lat: 0, lon: 10 },
  { event_id: 3, lat: 10, lon: 10 },
  { event_id: 4, lat: 10, lon: 20 },
].map(event => ({ ...event, date_precision: "exact_day", sort_ordinal: date / 86400000 }));
const originalEvents = JSON.stringify(events);
const evidence = chronology.createEvidenceIndex({
  schemaId: chronology.SCHEMA_ID,
  sourceContract: chronology.SOURCE_CONTRACT,
  releaseId: "direction-population-fixture",
  rowSchema: [...chronology.ROW_SCHEMA],
  rows: [2, 3, 4].map((id, index) => [id, date + (10 + index) * hour, date + (10 + index) * hour + 59999, 0, 0]),
  codes: {
    evidence: [{ status: "accepted", kind: "source_clock", confidence: "high", basis: "Preserved occurrence clock and historical timezone" }],
    zone: ["UTC"],
  },
});
const publications = [];
const bucket = { key: "gap_le_1" };
let staticMode = true;
const context = vm.createContext({
  TRACE_DIRECTIONS: directions,
  TRACE_CHRONOLOGY: chronology,
  runtime: { traceChronologyEvidence: evidence, packedTraceRenderCacheKey: "", packedTraceRenderCacheValue: null },
  state: { timelineDataVersion: 1, filterGeneration: 1, colorMode: "craft_type", filteredMappedCatalog: events },
  TRACE_RENDER_MODE_INDIVIDUAL: "individual",
  TRACE_RENDER_MODE_AGGREGATE: "aggregate",
  TRACE_RENDER_MODE_SUMMARY: "summary",
  getCatalogEventById: id => events.find(event => String(event.event_id) === String(id)),
  activeTraceBuckets: () => [bucket],
  filteredMappedEventIdSet: () => new Set(events.map(event => String(event.event_id))),
  traceFacilityFilterEnabled: () => false,
  traceViewportBoundsKey: bounds => bounds ? "viewport:current" : "viewport=none",
  canonicalTraceSegmentsPackedCacheKey: () => "fixture",
  catalogEventIdIdentityKey: () => "1234",
  traceAggregateZoomBucket: () => ({ label: "fixture" }),
  canonicalFilteredTraceAggregationRequested: () => true,
  traceFacilityFilterSignature: () => "",
  packedTraceRenderResultIsUsable: () => true,
  traceFacilityFilterStatsSnapshot: () => ({}),
  packedTraceOrdinalScanRange: () => ({ startRow: 0, endRow: 4, bounded: true }),
  decodePackedTraceEventIndexRowForRender: (_, index) => events[index],
  playbackTrailBucketForGapDays: () => bucket,
  shortestWrappedSegment: (from, to) => ({ from: [from.lat, from.lon], to: [to.lat, to.lon] }),
  canonicalTraceId: (from, to) => from + "->" + to,
  applyTraceFacilityFilterToSegment: segment => segment,
  traceSegmentMayIntersectBounds: (segment, bounds) => !bounds.onlyNorth || segment.fromEventId === 2,
  resolveTraceRenderMode: count => count >= 2 ? "aggregate" : "individual",
  filteredTraceAggregateCellSizeForMode: () => 1,
  addTraceSegmentToAggregateMap: (map, segment) => map.set(segment.traceId, segment),
  traceRenderSampleLimitForMode: () => 1,
  // A deliberately north-pointing representative catches accidental counts
  // from simplified geometry instead of the original report links.
  finalizeTraceAggregateSegments: () => [{ traceId: "aggregate:representative", from: [0, 0], to: [1, 0], aggregateSegmentCount: 3 }],
  styleRawTraceSegmentsForDensity: segments => segments,
  traceModeIncludesStatic: () => staticMode,
  setLegendTraceDirectionPopulation: (summary, options) => publications.push({ summary, options }),
});
vm.runInContext(populationHelpers + "\n" + orientSource + "\n" + packedBuilder, context);

const artifact = { rowCount: events.length };
const all = context.buildCanonicalPackedTraceRenderSegments(artifact, { bounds: {} });
assert.equal(all.segments.length, 1, "The displayed LOD contains one representative line");
assert.equal(all.directionSummary.uniqueSegments, 3, "Statistics count the three original links before LOD");
assert.equal(all.directionSummary.unorderedSegments, 1, "A missing accepted clock remains unresolved");
assert.equal(all.directionSummary.denominator, 2, "Unresolved links never enter directional percentages");
assert.equal(all.directionSummary.sectors.find(sector => sector.key === "N").count, 1);
assert.equal(all.directionSummary.sectors.find(sector => sector.key === "E").count, 1);
assert.equal(all.directionSummary.sectors.find(sector => sector.key === "E").percentage, 50,
  "The synthetic north-only aggregate must not erase original eastward links");
assert.equal(all.directionViewportScoped, true, "Actual bounds are tracked independently of LOD mode changes");

context.publishStaticTraceDirectionPopulation(all.segments);
assert.equal(publications.at(-1).summary, all.directionSummary, "Layer activation publishes the exact source summary");
assert.equal(publications.at(-1).options.viewportScoped, true);
const cached = context.buildCanonicalPackedTraceRenderSegments(artifact, { bounds: {} });
assert.equal(cached, all, "Cache restoration preserves source-population metadata");
context.publishStaticTraceDirectionPopulation(cached.segments);
assert.equal(publications.at(-1).summary.denominator, 2, "Cached activation never recalculates representative bearings");

context.state.filterGeneration += 1;
context.resolveTraceRenderMode = () => "individual";
const north = context.buildCanonicalPackedTraceRenderSegments(artifact, { bounds: { onlyNorth: true } });
assert.equal(north.directionSummary.uniqueSegments, 1, "Viewport intersection applies before counting");
assert.equal(north.directionSummary.denominator, 1);
assert.equal(north.directionSummary.sectors.find(sector => sector.key === "N").percentage, 100);
assert.equal(north.renderMode, "individual");
assert.equal(north.aggregationStatus.viewportWindowed, false,
  "The existing aggregation flag can be false although the population was filtered by bounds");
assert.equal(north.directionViewportScoped, true, "A narrow packed viewport still requires viewport refresh");
assert.equal(all.directionSummary.denominator, 2, "Subsequent windows leave prior cached summaries immutable");

context.state.filterGeneration += 1;
context.resolveTraceRenderMode = count => count >= 2 ? "aggregate" : "individual";
const fallback = context.buildCanonicalPackedTraceRenderSegments(artifact, {
  bounds: null,
  viewportBoundsKey: "viewport=fallback-all",
});
assert.match(fallback.directionScopeLabel, /outside map view included/, "Fallback scope cannot imply that all counted traces are on screen");
assert.equal(fallback.directionSummary.uniqueSegments, 3);
assert.equal(fallback.directionViewportScoped, false, "Fallback-all counts do not depend on map bounds");

context.publishStaticTraceDirectionPopulation(context.pendingStaticTraceDirectionSegments());
assert.equal(publications.at(-1).options.status, "loading");
assert.equal(publications.at(-1).summary, null, "Pending work cannot present stale counts as current");
context.publishStaticTraceDirectionPopulation([]);
assert.equal(publications.at(-1).summary.denominator, 0, "A completed empty layer has a truthful zero population");
staticMode = false;
context.publishStaticTraceDirectionPopulation(all.segments);
assert.equal(publications.at(-1).options.status, "off");
assert.equal(publications.at(-1).summary, null, "Hidden static layers never retain active statistics");
assert.equal(JSON.stringify(events), originalEvents, "Statistics leave source reports untouched");

const viewportModeSource = between("function traceRenderModeUsesViewportWindow(", "function traceViewportBoundsKey(");
const refreshPredicateSource = between("function staticTraceViewportRefreshNeeded(", "function refreshStaticTraceLayerForViewportChange(");
context.TRACE_RENDER_MODE_BUDGETED = "budgeted";
vm.runInContext(viewportModeSource + "\n" + refreshPredicateSource, context);
staticMode = true;
context.runtime.map = { hasLayer: () => true };
context.runtime.staticTraceLayer = { _segments: north.segments };
context.runtime.staticTraceRenderMode = "individual";
context.runtime.staticTraceAggregationStatus = { viewportWindowed: false };
assert.equal(context.staticTraceViewportRefreshNeeded(), true,
  "The actual refresh predicate includes a viewport-scoped population even at individual LOD");

const allFilteredNarrowSegments = [north.segments[0]];
context.registerStaticTraceDirectionPopulation(allFilteredNarrowSegments, north.directionSummary, {
  scopeLabel: "Filtered traces · current time window",
  viewportScoped: false,
});
context.runtime.staticTraceLayer._segments = allFilteredNarrowSegments;
assert.equal(context.staticTraceViewportRefreshNeeded(), false,
  "A raw all-filtered narrow population needs no source rescan when the viewport changes");
context.runtime.staticTraceLayer._segments = fallback.segments;
assert.equal(context.staticTraceViewportRefreshNeeded(), false,
  "Fallback-all population metadata does not introduce needless narrow-window refreshes");
context.runtime.staticTraceRenderMode = "budgeted";
assert.equal(context.staticTraceViewportRefreshNeeded(), true, "Existing dense-window refresh behavior remains active");
context.runtime.staticTraceLayer._segments = north.segments;
staticMode = false;
assert.equal(context.staticTraceViewportRefreshNeeded(), false, "Inactive static layers never schedule viewport scans");
staticMode = true;
context.runtime.map.hasLayer = () => false;
assert.equal(context.staticTraceViewportRefreshNeeded(), false, "A detached line layer never schedules viewport scans");

const legendViewSource = between("function legendTraceDirectionView(", "function renderLegendTraceDirectionPanel(");
const areaSummarySource = between("function currentAreaDirectionSummary(", "function renderAreaDirectionSummary(");
const rawLinks = events.slice(1).map((event, index) => {
  const earlier = events[index];
  return context.applyTraceChronology({
    traceId: earlier.event_id + "->" + event.event_id,
    fromEventId: earlier.event_id,
    toEventId: event.event_id,
    from: [earlier.lat, earlier.lon],
    to: [event.lat, event.lon],
    gapDays: 0,
  }, earlier, event);
});
let areaActive = true;
let isCase = true;
let areaResult = { pointOnly: false, visibleTraceSegments: rawLinks };
const legendRuntime = {
  map: {},
  playbackTrailCanvasLayer: { _segments: rawLinks },
};
const legendState = { traceMode: "off", regionSelection: { direction: "forward" } };
const viewContext = vm.createContext({
  TRACE_DIRECTIONS: directions,
  runtime: legendRuntime,
  state: legendState,
  regionSelectionAffectsRendering: () => areaActive,
  currentRegionSelectionResult: () => areaResult,
  famousCaseTraceSelectionActive: () => isCase,
  traceModeIncludesPlayback: () => legendState.traceMode === "playback",
  currentMapViewportBoundsSnapshot: () => ({ visibleLinks: new Set(["1->2", "2->3"]) }),
  traceSegmentMayIntersectBounds: (segment, bounds) => bounds.visibleLinks.has(segment.traceId),
});
vm.runInContext(areaSummarySource + "\n" + legendViewSource, viewContext);

let view = viewContext.legendTraceDirectionView();
assert.equal(view.status, "ready", "Selected case links remain usable while global static traces are off");
assert.equal(view.scopeLabel, "Case connections · current time window");
assert.equal(view.summary.denominator, 2, "The case selection takes precedence over the global off state");
assert.equal(view.summary.unorderedSegments, 1, "Case statistics preserve missing-clock exclusions");
isCase = false;
view = viewContext.legendTraceDirectionView();
assert.equal(view.scopeLabel, "Selected traces · current time window", "Drawn-area links use their own population");
assert.equal(view.summary.denominator, 2);

areaResult = { pointOnly: true, visibleTraceSegments: rawLinks };
view = viewContext.legendTraceDirectionView();
assert.equal(view.summary, null, "A point-only selection cannot show direction counts from hidden lines");
assert.match(view.emptyMessage, /Show traces from this selection/);
areaActive = false;
view = viewContext.legendTraceDirectionView();
assert.equal(view.status, "off", "Global off applies when no independent selection is active");
assert.equal(view.summary, undefined);

legendState.traceMode = "playback";
view = viewContext.legendTraceDirectionView();
assert.equal(view.status, "ready");
assert.equal(view.scopeLabel, "Visible playback trail", "Trail scope describes both Hold and Fade modes");
assert.equal(view.summary.uniqueSegments, 2, "Playback statistics use only the current visible trail subset");
assert.equal(view.summary.unorderedSegments, 1);
assert.equal(view.summary.denominator, 1);
assert.equal(view.summary.sectors.find(sector => sector.key === "N").percentage, 100);
legendRuntime.map = null;
assert.equal(viewContext.legendTraceDirectionView().summary.denominator, 2,
  "A missing viewport conservatively uses the existing trail, without inventing whole-window statistics");

legendState.traceMode = "static";
view = viewContext.legendTraceDirectionView();
assert.equal(view.status, "loading", "An absent static population must wait for actual trace counts");
assert.equal(view.summary, undefined);
legendRuntime.legendTraceDirectionPopulation = {
  summary: all.directionSummary,
  status: "preview",
  scopeLabel: "Startup preview · waiting for full traces",
};
view = viewContext.legendTraceDirectionView();
assert.equal(view.status, "loading", "Startup preview counts must not appear complete");
assert.equal(view.summary, all.directionSummary);
assert.equal(legendRuntime.legendTraceDirectionPopulation.status, "preview", "Rendering never mutates stored population status");

console.log("Trace direction population passed: exact pre-LOD counts, accepted-clock exclusions, viewport scope, narrow-window refresh, immutable cache metadata, fallback disclosure, loading/off states, selected-case precedence, point-only exclusions and visible playback scope.");
