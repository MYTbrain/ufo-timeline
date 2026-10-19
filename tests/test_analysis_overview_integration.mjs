import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";

// Exercise the actual typed catalog, active/reference membership, lazy import,
// and calendar evidence contracts together. No corpus artifacts are required.
const require = createRequire(import.meta.url);
const day = iso => Date.parse(iso + "T00:00:00Z") / 86400000;
const statsCode = fs.readFileSync("analysis_stats.js", "utf8");
const workerCode = fs.readFileSync("catalog_filter_worker.js", "utf8");
const overviewCode = fs.readFileSync("analysis_overview_model.js", "utf8");
const jan15 = day("1994-01-15");
const base = { source: "one", type: "Triangle", craftType: "triangle", mapped: true,
  lat: 40, lon: -75, precision: "city", coordinateSource: "source_provided",
  datePrecision: "exact_day", craftConfidence: "high", sortOrdinal: jan15 };
const rows = [
  { ...base, eventId: "a" },
  { ...base, eventId: "b", type: "Disk", craftType: "disc_saucer", lat: 41, lon: -74 },
  { ...base, eventId: "month", datePrecision: "month", dateStartOrdinal: day("1994-01-01"), dateEndOrdinal: day("1994-01-31") },
  { ...base, eventId: "year", type: "Disk", craftType: "disc_saucer", datePrecision: "year",
    sortOrdinal: day("1994-07-01"), dateStartOrdinal: day("1994-01-01"), dateEndOrdinal: day("1994-12-31") },
  { ...base, eventId: "spanning-year", datePrecision: "approximate", sortOrdinal: day("1994-01-10"),
    dateStartOrdinal: day("1993-12-20"), dateEndOrdinal: day("1994-01-20") },
  { ...base, eventId: "withheld", type: "Disk", craftType: "disc_saucer", encounterOccurrenceDateExcluded: true },
  { ...base, eventId: "previous", sortOrdinal: day("1994-01-14") },
  { ...base, eventId: "later", type: "Disk", craftType: "disc_saucer", sortOrdinal: day("1994-01-16") },
  { ...base, eventId: "other-source", source: "two" },
  { ...base, eventId: "outside-area", lat: -20, lon: 130 },
  { ...base, eventId: "undated", mapped: false, lat: null, lon: null, sortOrdinal: null, datePrecision: "unknown" },
  { ...base, eventId: "other-type", type: "Cone", craftType: "cone" },
];
const allFilters = { sourceMode: "all", typeMode: "all", precisionMode: "all",
  hideLowPrecision: false, hideNonExactDates: false };
const rectangle = { type: "rectangle", bounds: { north: 42, south: 39, west: -77, east: -73 } };

function workerFixture({ preload = true } = {}) {
  const outputs = [], imports = [], fetches = [];
  const self = { postMessage: message => outputs.push(message) };
  self.self = self; // A real worker's self and globalThis share the same scope.
  if (preload) self.UfoAnalysisOverviewModel = require("../analysis_overview_model.js");
  let context;
  context = vm.createContext(Object.assign(self, { console,
    fetch: async url => { fetches.push(String(url)); throw new Error("Overview unexpectedly requested a runtime data download"); },
    importScripts: url => {
      imports.push(String(url));
      assert.match(String(url), /(?:^|\/)analysis_overview_model\.js(?:\?|$)/,
        "Overview does not import celestial, spatial, or collection engines");
      vm.runInContext(overviewCode, context, { filename: "analysis_overview_model.js" });
    },
  }));
  vm.runInContext(statsCode, context, { filename: "analysis_stats.js" });
  vm.runInContext(workerCode, context, { filename: "catalog_filter_worker.js" });
  function send(data) {
    outputs.length = 0;
    self.onmessage({ data });
    assert.equal(outputs.length, 1, "The bounded core worker replies synchronously");
    assert.notEqual(outputs[0].type, "catalogFacetWorkerError", outputs[0].error);
    return outputs[0];
  }
  send({ type: "addCatalogFacetRows", rows });
  return { send, self, imports, fetches };
}

let sequence = 0;
function request(overrides = {}) {
  return { type: "computeAnalysis", requestId: "overview-test-" + (++sequence),
    datasetHash: "bounded-overview-fixture", timeRangeMode: "window", fullTimeRange: false,
    timeRangeStartOrdinal: jan15, timeRangeEndOrdinal: jan15,
    baselineMode: "other_dates_balanced", filters: { ...allFilters },
    selectedDomains: ["overview", "time", "sources_quality"], quickMode: true, ...overrides };
}
const fixture = workerFixture();
function compute(overrides, expectedN, why) {
  const message = fixture.send(request(overrides));
  assert.equal(message.type, "analysisComputed");
  const result = message.result;
  assert.equal(result.summary.activeCount, expectedN, why);
  assert.ok(result.overviewExplorer, "Overview model travels with its actual worker result");
  assert.equal(result.overviewExplorer.status, "ready_descriptive", result.overviewExplorer.reason || why);
  assert.equal(result.overviewExplorer.totalN, expectedN, why + ": dashboard population");
  assert.equal(result.overviewExplorer.totalN, result.summary.activeCount,
    "Every Overview denominator equals the accepted active report population");
  return result;
}

const ordinary = compute({}, 9, "Window membership uses source intervals rather than stored midpoints");
assert.equal(ordinary.summary.referenceCount, 2, "Disjoint reference contains the two neighboring exact dates");
assert.equal(ordinary.overviewExplorer.coverage.knownMonthN, 6,
  "The accepted month interval is usable, while year-only, cross-month and withheld dates are not invented months");
assert.equal(ordinary.overviewExplorer.coverage.knownDecadeN, 8,
  "Cross-year intervals within one decade remain decade-compatible; withheld occurrence dates do not");
const calendarCard = ordinary.overviewExplorer.cards.find(card => card.key === "craft_month");
const calendar = calendarCard.lanes.all;
const monthTotals = calendarCard.rowDimension === "month" ? calendar.rowTotals : calendar.columnTotals;
assert.equal(monthTotals.find(row => row.key === "01").count, 6);
assert.equal(monthTotals.find(row => row.key === "__unknown__").count, 3);
assert.equal(monthTotals.some(row => row.key === "07"), false,
  "The year-only record's July storage midpoint must not appear in calendar charts");
assert.equal(calendar.cells.reduce((sum, cell) => sum + cell.count, 0), 9,
  "Calendar counts including unknowns reconcile with the true active population");
compute({ filters: { ...allFilters, sourceMode: "subset", selectedSources: ["one"] } }, 8,
  "Source selection reaches the dashboard");
compute({ filters: { ...allFilters, typeMode: "subset", selectedTypes: ["Triangle"] } }, 5,
  "Report-type selection reaches the dashboard");
compute({ keywordEventIds: ["a", "previous", "other-source"], filters: { ...allFilters, keyword: "fixture" } }, 2,
  "Keyword membership and dates both reach the dashboard");
compute({ areaFilterShapes: [rectangle] }, 8, "Geographic selection removes the distant endpoint");
const subset = { ...allFilters, sourceMode: "subset", selectedSources: ["one"], typeMode: "subset", selectedTypes: ["Triangle"] };
const fullReference = compute({ baselineMode: "full_catalog", filters: subset, areaFilterShapes: [rectangle] }, 3,
  "Full-catalog reference cannot leak nonmatching rows into the active dashboard");
assert.equal(fullReference.summary.referenceCount, rows.length,
  "The full-catalog estimator still retains its deliberately broader reference");
compute({ timeRangeMode: "full", fullTimeRange: true }, rows.length,
  "All Time includes undated reports without inventing a date");
compute({ timeRangeStartOrdinal: day("2005-06-01"), timeRangeEndOrdinal: day("2005-06-02") }, 0,
  "An empty active window remains empty despite a populated reference");
const heldFilters = { ...allFilters, sourceMode: "none", typeMode: "none", keyword: "unrelated live query",
  analysisSessionEventIds: ["b", "previous", "other-source"] };
compute({ filters: heldFilters, keywordEventIds: [], timeRangeMode: "full", fullTimeRange: true }, 3,
  "A held exact-ID population remains independent of live source/type/search edits");
compute({ filters: heldFilters, keywordEventIds: [] }, 2,
  "Held exact-ID membership retains the accepted Analysis date window");
assert.equal(fixture.fetches.length, 0, "Overview cubes require no additional runtime data fetch");

const lazy = workerFixture({ preload: false });
assert.equal(lazy.imports.length, 0, "The Overview module is absent during startup catalog ingestion");
const timeOnly = lazy.send(request({ selectedDomains: ["time", "sources_quality"] })).result;
assert.equal(timeOnly.overviewExplorer, undefined, "Non-Overview results do not carry an unused dashboard");
assert.equal(lazy.imports.length, 0, "Unrequested Overview work does not import its engine");
const firstOverview = lazy.send(request()).result;
assert.equal(firstOverview.overviewExplorer.totalN, 9);
assert.equal(lazy.imports.length, 1, "First Overview computation lazily imports the compact engine once");
lazy.send(request({ timeRangeStartOrdinal: jan15 - 1, timeRangeEndOrdinal: jan15 + 1 }));
assert.equal(lazy.imports.length, 1, "Subsequent date changes reuse the loaded engine");
assert.equal(lazy.fetches.length, 0, "No planetary, spatial, or collection data is fetched for Overview");

// Rendering/navigation contracts are supplementary: the population assertions
// above exercise actual behavior rather than merely matching implementation text.
const markup = fs.readFileSync("index.html", "utf8");
assert.ok(markup.includes('id="analysis-overview-explore"'),
  "The Overview's initial visible view has a dedicated dashboard host");
const visualScript = markup.match(/<script\s+defer\s+src="\.\/analysis_overview_visuals\.js\?[^\"]+"><\/script>/g) || [];
assert.equal(visualScript.length, 1, "The small visual math helper is included exactly once");
assert.ok(markup.indexOf(visualScript[0]) < markup.indexOf('<script defer src="./analysis_overview_view.js'),
  "Deferred dashboard scripts preserve helper-before-view execution order");
const groupsContext = vm.createContext({ window: {} });
vm.runInContext(fs.readFileSync("ui/accepted-workspace/analysis-view-groups.js", "utf8"), groupsContext);
const groups = groupsContext.window.PreviewAnalysisViewGroups.overview;
assert.equal(groups[0].key, "explore", "Exploration is the default Overview subview");
assert.ok(groups[0].anchorIds.includes("analysis-overview-explore"), "Subview ownership keeps the dashboard visible");
const renderer = fs.readFileSync("analysis_view.js", "utf8");
assert.ok(renderer.includes("_renderOverviewExplorer("), "The dashboard participates in the native Analysis renderer");
const { AnalysisViewController } = require("../analysis_view.js");
const controller = Object.create(AnalysisViewController.prototype);
const revealed = [], navigated = [], renders = [], host = {};
let overviewConfig;
Object.assign(controller, {
  document: { getElementById: id => id === "analysis-overview-explore" ? host : null },
  documentView: { UfoAnalysisOverviewView: { create(target, config) {
    assert.equal(target, host); overviewConfig = config;
    return { render(value) { renders.push(value); } };
  } } },
  _openSupportingChart: id => { revealed.push(id); return true; },
  navigateToSection: (id, options) => { navigated.push({ id, options }); return true; },
});
controller._renderOverviewExplorer({ ...ordinary, context: {
  crops: { enabled: true, status: "ready", activeCount: 27 },
  animals: { enabled: false, status: "excluded", activeCount: 0 },
} }, ordinary.summary);
assert.equal(renders[0].model.totalN, 9, "Native rendering retains the accepted active dashboard population");
assert.match(renders[0].model.contexts.find(item => item.section === "crops").detail, /27.*date window.*separate catalog/,
  "The independent crop catalog keeps its own date-window denominator");
assert.equal(renders[0].model.contexts.find(item => item.section === "animals").available, false,
  "An excluded context catalog is unavailable rather than an observed zero");
assert.equal(ordinary.overviewExplorer.contexts, undefined, "Renderer context cards do not mutate the worker model");
for (const [key, expected] of [
  ["craft_decade", "analysis-craft-era-chart"], ["craft_month", "analysis-month-year-chart"],
  ["craft_country", "analysis-geography-grid-chart"], ["being_craft", "analysis-being-craft-chart"],
  ["month_decade", "analysis-time-series-chart"], ["source_decade", "analysis-source-time-chart"],
  ["being_decade", "analysis-encounter-time-chart"], ["collections", "analysis-collections-chart"],
  ["comparisons", "analysis-comparisons-chart"], ["crops", "analysis-crop-time-chart"],
]) {
  overviewConfig.onOpenSection("encounters", { card: key });
  assert.equal(revealed.at(-1), expected, key + " reveals the requested native chart and its owning subview");
}
assert.equal(navigated.length, 0, "Known dashboard cards use native reveal, not a possibly hidden topic default");
controller._openOverviewChart("context", {});
assert.equal(navigated.at(-1).id, "analysis-section-context", "Unmapped destinations retain ordinary topic navigation");

// Run the actual app completion callback with its real state guards. Optional
// geography may enrich an already visible Overview, never delay initial Map or
// load behind fixed A/B comparisons or an unrelated Analysis section.
const appSource = fs.readFileSync("app.js", "utf8");
const completionStart = appSource.indexOf("      onRenderComplete: function () {");
const completionEnd = appSource.indexOf("\n      onComparisonSettingsChange:", completionStart);
assert.ok(completionStart >= 0 && completionEnd > completionStart, "Native Analysis completion callback is available");
const completionCode = appSource.slice(completionStart, completionEnd).trim()
  .replace(/^onRenderComplete:/, "this.complete =").replace(/,\s*$/, ";");
let geographyLoads = 0;
const completionRuntime = { analysisSessionMode: "current", analysisViewController: {
  activeSectionId: "analysis-section-overview", latestResult: ordinary,
} };
const completionState = { activeView: "map" };
const completionContext = vm.createContext({ runtime: completionRuntime, state: completionState,
  syncAnalysisComparisonWorkspace() {},
  ensureAnalysisGeographyArtifact() { geographyLoads++; return Promise.resolve(); },
  requestAnalysisTimeEvidence() { throw new Error("Overview must not load Time evidence"); },
  requestAnalysisCoordinateEvidence() { throw new Error("Overview must not load coordinate audit evidence"); },
  setAnalysisContextEvidenceSectionState() { throw new Error("Overview must not load spatial context evidence"); },
});
vm.runInContext(completionCode, completionContext);
completionContext.complete(); assert.equal(geographyLoads, 0, "Initial Map startup never requests optional Overview geography");
completionState.activeView = "analysis"; completionRuntime.analysisSessionMode = "compare";
completionContext.complete(); assert.equal(geographyLoads, 0, "Held A/B mode never loads live Overview geography");
completionRuntime.analysisSessionMode = "current"; completionRuntime.analysisViewController.activeSectionId = "analysis-section-craft";
completionContext.complete(); assert.equal(geographyLoads, 0, "Another active topic never loads Overview geography");
completionRuntime.analysisViewController.activeSectionId = "analysis-section-overview";
for (const model of [undefined, { status: "loading" }, { status: "unavailable" }]) {
  completionRuntime.analysisViewController.latestResult = { overviewExplorer: model };
  completionContext.complete();
  assert.equal(geographyLoads, 0, "Optional geography waits for a successfully rendered Overview population");
}
completionRuntime.analysisViewController.latestResult = ordinary;
completionContext.complete(); assert.equal(geographyLoads, 1, "Visible ready Overview enriches geography after its first useful render");
assert.equal(completionRuntime.analysisOverviewGeographyRequested, true);
completionContext.complete(); assert.equal(geographyLoads, 1, "Repeated renders reuse the single geography request");

console.log("Analysis Overview integration: active populations, references, exact IDs, interval dates, lazy work and navigation contracts passed.");
