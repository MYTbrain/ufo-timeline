import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
const require = createRequire(import.meta.url), Encounters = require("../encounter_evidence.js");
const responses = [], self = { postMessage(message) { responses.push(message); }, UFOEncounterEvidence: Encounters };
const context = vm.createContext({ self, console });
for (const file of ["analysis_stats.js", "catalog_filter_worker.js"]) vm.runInContext(readFileSync(new URL("../" + file, import.meta.url), "utf8"), context, { filename: file });
const row = (eventId, more = {}) => ({ eventId: String(eventId), source: "ufocat", type: "Disk", visualTypeGroup: "Disc / saucer", craftType: "disc_saucer",
  datePrecision: "exact_day", sortOrdinal: 100, mapped: true, lat: 0, lon: 0, precision: "city", country: "France", ...more });
const rows = [row(10), row(20, { mapped: false, lat: null, lon: null, precision: "unknown", encounterEvidenceReady: true,
  encounterBeingMask: Encounters.beingMask(["grey"]), encounterAbductionCode: 1 }),
  row(30, { source: "nuforc", country: "United States", lat: 40, lon: -75 }),
  row(40, { type: "Triangle", visualTypeGroup: "Triangle", craftType: "triangle", country: "Japan", sortOrdinal: 105, lat: 35, lon: 139 }),
  row(50, { mapped: false, lat: null, lon: null, precision: "unknown", datePrecision: "month", sortOrdinal: 110, dateStartOrdinal: 90, dateEndOrdinal: 119 }),
  row(60, { mapped: false, lat: null, lon: null, precision: "unknown", datePrecision: "unknown", sortOrdinal: null }),
  row(70, { mapped: false, lat: null, lon: null, precision: "country" }), row(80, { country: "Germany", lat: 50, lon: 10 }), row(90, { sortOrdinal: 0 })];
function send(message) { responses.length = 0; self.onmessage({ data: message }); assert.equal(responses.length, 1, message.type); return JSON.parse(JSON.stringify(responses[0])); }
assert.equal(send({ type: "addCatalogFacetRows", rows }).type, "catalogFacetRowsAdded");
const filters = { sourceMode: "all", typeMode: "all", precisionMode: "all", selectedSources: [], selectedTypes: [], selectedPrecisions: [],
  keyword: "", hideLowPrecision: false, hideNonExactDates: false, legendEventMode: "all", selectedLegendEventKeys: [], legendColorMode: "craft_type" };
const allIds = rows.map(value => value.eventId), base = { type: "inspectCollectionReportIds", requestId: "sparse", generation: 7, analysisSignature: "fixture-signature",
  requestedEventIds: allIds, filters, lowPrecisionValues: ["country", "unknown"], timeRangeMode: "custom", timeRangeStartOrdinal: 100, timeRangeEndOrdinal: 100 };
const inspect = (extra = {}) => { const response = send({ ...base, ...extra }); assert.equal(response.type, "collectionReportIdsInspected", response.error);
  assert.equal(response.generation, 7); assert.equal(response.analysisSignature, "fixture-signature"); return response.result; };
const ids = extra => inspect(extra).eventIds;
assert.deepEqual(ids(), ["10", "20", "30", "50", "70", "80"], "Analysis includes mapped and unmapped reports and overlapping date intervals");
assert.equal(inspect().totalMatchedAnalysisReports, null, "Sparse uncached lookup does not materialize a full cohort for metadata");
assert.deepEqual(ids({ requestedEventIds: ["20", "missing", "10", "20"] }), ["10", "20"], "Only requested report IDs return, without duplicates");
assert.deepEqual(ids({ requestedEventIds: [] }), []);
assert.deepEqual(ids({ timeRangeStartOrdinal: 0, timeRangeEndOrdinal: 0 }), ["90"], "Unix day zero is a valid date rather than an absent boundary");
assert.deepEqual(ids({ timeRangeStartOrdinal: 101, timeRangeEndOrdinal: 99 }), ["10", "20", "30", "50", "70", "80"], "Reversed date boundaries normalize");
assert.deepEqual(ids({ fullTimeRange: true, timeRangeMode: "full" }), allIds, "Undated reports remain in the full Analysis cohort");
assert.deepEqual(ids({ filters: { ...filters, sourceMode: "subset", selectedSources: ["nuforc"] } }), ["30"]);
assert.deepEqual(ids({ filters: { ...filters, sourceMode: "none" } }), []);
assert.deepEqual(ids({ fullTimeRange: true, filters: { ...filters, typeMode: "subset", selectedTypes: ["Triangle"] } }), ["40"]);
assert.deepEqual(ids({ filters: { ...filters, precisionMode: "subset", selectedPrecisions: ["unknown"] } }), ["20", "50"]);
assert.deepEqual(ids({ filters: { ...filters, hideLowPrecision: true } }), ["10", "30", "80"]);
assert.deepEqual(ids({ filters: { ...filters, hideNonExactDates: true } }), ["10", "20", "30", "70", "80"]);
assert.deepEqual(ids({ filters: { ...filters, keyword: "soil" }, keywordEventIds: ["20"] }), ["20"], "Keyword membership preserves a matching unmapped report");
assert.deepEqual(ids({ filters: { ...filters, keyword: "soil" }, keywordEventIds: [] }), [], "Empty keyword match set fails closed");
assert.deepEqual(ids({ filters: { ...filters, legendEventMode: "none" } }), []);
assert.deepEqual(ids({ fullTimeRange: true, filters: { ...filters, legendEventMode: "subset", selectedLegendEventKeys: ["triangle"] } }), ["40"]);
assert.deepEqual(ids({ filters: { ...filters, encounters: { beingTypes: ["grey"] } } }), ["20"], "Shared encounter classifications apply to sparse collection membership");
assert.deepEqual(ids({ filters: { ...filters, encounterSelectionIds: ["20", "30"] } }), ["20", "30"]);
assert.deepEqual(ids({ areaFilterShapes: [{ type: "rectangle", bounds: { north: 1, south: -1, east: 1, west: -1 } }] }), ["10"], "Point areas require a supported coordinate");
assert.deepEqual(ids({ areaFilterShapes: [{ type: "country", country: "France" }] }), ["10", "20", "50", "70"], "Country filters retain text-assigned unmapped reports");
assert.deepEqual(ids({ areaFilterEventIds: ["20", "50"] }), ["20", "50"]);
const analysis = send({ ...base, type: "computeAnalysis", selectedDomains: ["overview"], quickMode: true, baselineMode: "other_dates_balanced", datasetHash: "fixture" });
assert.equal(analysis.type, "analysisComputed", analysis.error);
assert.equal(analysis.result.summary.activeCount, 6);
const cached = inspect({ requestedEventIds: ["10", "20"] });
assert.deepEqual(cached.eventIds, ["10", "20"]);
assert.equal(cached.totalMatchedAnalysisReports, 6, "Existing Analysis match cache exposes the same full cohort count while returning only requested IDs");
const invalid = send({ ...base, requestedEventIds: Array(10001).fill("10") });
assert.equal(invalid.type, "catalogFacetWorkerError"); assert.match(invalid.error, /inventory is invalid/);
console.log("Collection worker cohort: unmapped reports, sparse intersection, date intervals/zero, shared filters, spatial/country selection and Analysis cache parity passed.");
