import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const messages = [];
const self = { postMessage: (message) => messages.push(message) };
const context = vm.createContext({ self, console });
for (const file of ["analysis_stats.js", "catalog_filter_worker.js"]) {
  vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
}
function send(message) {
  messages.length = 0;
  self.onmessage({ data: message });
  assert.equal(messages.length, 1);
  assert.notEqual(messages[0].type, "catalogFacetWorkerError", messages[0].error);
  return messages[0];
}
const base = { source: "fixture", type: "Triangle", craftType: "triangle", mapped: false,
  precision: "unknown", datePrecision: "unknown", craftConfidence: "high" };
send({ type: "addCatalogFacetRows", rows: [
  ...[null, undefined, "", "  ", false].map((sortOrdinal, index) => ({ ...base, eventId: "unknown-" + index, sortOrdinal })),
  { ...base, eventId: "epoch", sortOrdinal: 0, datePrecision: "exact_day" },
  { ...base, eventId: "modern", sortOrdinal: 10957, datePrecision: "exact_day" },
] });
const filters = { sourceMode: "all", typeMode: "all", precisionMode: "all", hideLowPrecision: false, hideNonExactDates: false };
const computed = send({ type: "computeAnalysis", requestId: "all", fullTimeRange: true, timeRangeMode: "full",
  baselineMode: "full_catalog", datasetHash: "fixture", filters, selectedDomains: ["overview", "time", "sources_quality"], quickMode: true });
assert.equal(computed.type, "analysisComputed");
assert.equal(computed.result.summary.activeCount, 7);
const yearRows = computed.result.time.annualSeries;
assert.ok(Array.isArray(yearRows), "year timeline should be present");
const epoch = yearRows.find((row) => Number(row.year ?? row.label) === 1970);
assert.ok(epoch, "a genuine Unix ordinal zero must remain 1970");
assert.equal(Number(epoch.count ?? epoch.value ?? epoch.activeCount), 1, "unknown values must not contribute to 1970");
const ranged = send({ type: "computeFilteredCatalogIds", requestId: "epoch-only", filters: { ...filters,
  timeRangeStartOrdinal: 0, timeRangeEndOrdinal: 0, fullTimeRange: false, timeRangeMode: "window" },
  timeRangeStartOrdinal: 0, timeRangeEndOrdinal: 0, catalogExactDayAscending: true });
assert.equal(ranged.result.legendEventCounts.triangle, 1, "date-scoped legend counts must exclude undated records");

// Exercise the actual serializer and evidence guard extracted from the app.
const app = fs.readFileSync("app.js", "utf8");
const serializer = app.slice(app.indexOf("  function nullableCatalogNumber("), app.indexOf("  const ANALYSIS_BASELINE_MODES"));
const serializerContext = vm.createContext({ eventLegendKeyForMode: () => "triangle" });
vm.runInContext(serializer + "\nthis.serialize = serializeCatalogFacetWorkerRow; this.number = nullableCatalogNumber;", serializerContext);
for (const value of [null, undefined, "", " ", false, Infinity, NaN]) {
  assert.equal(serializerContext.serialize({ event_id: 1, sort_ordinal: value, lat: value, lon: value }).sortOrdinal, null);
}
assert.equal(serializerContext.serialize({ event_id: 1, sort_ordinal: 0 }).sortOrdinal, 0);
console.log("Analysis date serialization and worker regressions passed.");
