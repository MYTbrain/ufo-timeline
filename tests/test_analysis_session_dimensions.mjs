import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const Session = require("../analysis_session.js");
const Stats = require("../analysis_stats.js");
const workerSource = fs.readFileSync("catalog_filter_worker.js", "utf8");
const clone = value => JSON.parse(JSON.stringify(value));
const unixDay = (year, month, day) => Stats.ordinalFromCivil(year, month, day) - 719163;
const counts = distribution => Object.fromEntries(distribution.rows.map(row => [row.key, row.count]));
const messages = [], self = { postMessage: message => messages.push(message) };
const worker = vm.createContext({ self, console });
vm.runInContext(fs.readFileSync("analysis_stats.js", "utf8"), worker);
vm.runInContext(workerSource, worker);
function send(message) {
  messages.length = 0; self.onmessage({ data: message });
  assert.equal(messages.length, 1); assert.notEqual(messages[0].type, "catalogFacetWorkerError", messages[0].error);
  return clone(messages[0].result || messages[0]);
}
const base = { source: "fixture", type: "Disk", craftType: "disc_saucer", mapped: true, precision: "city",
  datePrecision: "exact_day", lat: 40, lon: -75, craftConfidence: "high", country: "United States", adminRegion: "Washington" };
send({ type: "addCatalogFacetRows", rows: [
  { ...base, eventId: "a", sortOrdinal: unixDay(1973, 8, 1), mapped: false },
  { ...base, eventId: "b", sortOrdinal: unixDay(1989, 11, 1), country: "Belgium", adminRegion: "Brabant", type: "Triangle", craftType: "triangle" },
  { ...base, eventId: "year", sortOrdinal: unixDay(1973, 1, 1), datePrecision: "year", dateStartOrdinal: unixDay(1973, 1, 1), dateEndOrdinal: unixDay(1973, 12, 31) },
  { ...base, eventId: "month", sortOrdinal: unixDay(1973, 9, 1), datePrecision: "month", dateStartOrdinal: unixDay(1973, 9, 1), dateEndOrdinal: unixDay(1973, 9, 30) },
  { ...base, eventId: "crossyear", sortOrdinal: unixDay(1973, 12, 31), datePrecision: "range", dateStartOrdinal: unixDay(1973, 12, 31), dateEndOrdinal: unixDay(1974, 1, 1) },
  { ...base, eventId: "withheld", sortOrdinal: unixDay(1994, 9, 16), encounterOccurrenceDateExcluded: true },
  { ...base, eventId: "undated", sortOrdinal: null, datePrecision: "unknown", mapped: false, craftConfidence: "unknown", type: "unknown", adminRegion: "unknown" },
] });
const filters = { sourceMode: "all", typeMode: "all", precisionMode: "all" };
function capture(input = {}) { return send({ type: "captureAnalysisSession", requestId: "dimensions", fullTimeRange: true, filters, ...input }); }
const first = capture({ requestedEventIds: ["a", "year", "month", "crossyear", "withheld", "undated", "a"] });
const d = first.summary.distributions;
assert.equal(first.summary.reportN, 6);
assert.deepEqual(Object.keys(d).sort(), [...Session.DOMAINS].sort(), "Worker and immutable model share all dimensions");
assert.deepEqual(counts(d.year), { "1973": 3 }, "Cross-year intervals, withheld dates and undated records cannot manufacture a year");
assert.equal(d.year.unknownN, 3);
assert.deepEqual(counts(d.calendarMonth), { "08": 1, "09": 1 }, "Year-only dates never become January");
assert.deepEqual(counts(d.weekday), { "2": 1 }, "Only exact occurrence dates support weekday; 1973-08-01 was Wednesday");
assert.equal(d.weekday.rows[0].label, "Wednesday");
assert.equal(d.country.eligibleN, 6, "Known source countries remain available for unmapped reports");
assert.equal(first.summary.unmappedN, 2);
assert.equal(d.adminRegion.unknownN, 1);
assert.equal(d.adminRegion.rows[0].key, "United States:Washington");
assert.equal(d.reportType.unknownN, 1);
assert.equal(d.craftConfidence.unknownN, 1);
assert.equal(d.datePrecision.unknownN, 1);
for (const key of ["macroregion", "timeOfDay", "duration", "witnessCount", "color", "being", "abduction"]) {
  assert.equal(d[key], null, key + " is unavailable, not a zero distribution, before its projection loads");
}
for (const distribution of Object.values(d).filter(Boolean)) {
  assert.equal(distribution.eligibleN + distribution.unknownN, 6);
  assert.equal(distribution.rows.reduce((sum, row) => sum + row.count, 0), distribution.eligibleN);
}
const a = capture({ fullTimeRange: false, timeRangeMode: "window", timeRangeStartOrdinal: unixDay(1973, 8, 1), timeRangeEndOrdinal: unixDay(1973, 8, 1) });
const b = capture({ fullTimeRange: false, timeRangeMode: "window", timeRangeStartOrdinal: unixDay(1989, 11, 1), timeRangeEndOrdinal: unixDay(1989, 11, 1) });
const store = Session.createStore();
store.setGroup("A", { ...a, label: "1973" }); store.setGroup("B", { ...b, label: "1989" });
const comparison = store.getState().comparison;
assert.equal(comparison.distributions.year.rows.find(row => row.key === "1973").bCount, 0);
assert.equal(comparison.distributions.year.rows.find(row => row.key === "1989").aCount, 0);
assert.equal(comparison.distributions.country.rows.find(row => row.key === "Belgium").aCount, 0);
assert.equal(comparison.distributions.reportType.rows.find(row => row.key === "Triangle").bCount, 1);
assert.equal(comparison.distributions.timeOfDay.available, false);
assert.equal(comparison.distributions.timeOfDay.a.unknownN, null);
assert.deepEqual(comparison.distributions.calendarMonth.rows.map(row => row.key), ["08", "11"]);
assert.ok(Object.isFrozen(store.getState().groups.A.summary.distributions.year.rows));

// Exercise the actual capture function with already validated projection-row
// fields. Projection loading/integrity is covered by the artifact suites; this
// fixture verifies the frozen-summary readiness and typed-field contracts.
const start = workerSource.indexOf("  function captureAnalysisSession(message) {");
const end = workerSource.indexOf("\n  function ", start + 1);
assert.ok(start >= 0 && end > start);
const projectionRows = [
  { eventId: "typed", source: "one", craftType: "disc_saucer", mapped: false, datePrecision: "exact_day", sortOrdinal: Stats.ordinalFromCivil(1970, 1, 1),
    analysisCountry: "United Kingdom", country: "United Kingdom", analysisMacroregion: "Europe", adminRegion: "England", type: "Disk", precision: "city", craftConfidence: "high",
    analysisTimeOfDayAvailable: true, analysisTimeOfDayDescriptiveBin: "evening_18_23",
    analysisDurationAvailable: true, analysisDurationDescriptiveBin: "1_4_minutes",
    analysisWitnessCountAvailable: true, analysisWitnessCountStatus: "exact_count", analysisWitnessCountExactCount: 2, analysisWitnessCountBin: "two",
    analysisColorAvailable: true, analysisColorStatus: "explicit_compound", analysisColorRole: "surface", analysisColorCategoryMask: 3 },
  { eventId: "unsupported", source: "two", mapped: false, datePrecision: "year", sortOrdinal: Stats.ordinalFromCivil(2000, 1, 1), country: "United States", adminRegion: "England",
    analysisTimeOfDayAvailable: true, analysisTimeOfDayDescriptiveBin: "unknown", analysisDurationAvailable: true, analysisDurationDescriptiveBin: "unknown",
    analysisWitnessCountAvailable: true, analysisWitnessCountStatus: "approximate_count", analysisWitnessCountExactCount: 20, analysisWitnessCountBin: "twenty_to_forty_nine",
    analysisColorAvailable: true, analysisColorStatus: "multicolor_unspecified", analysisColorCategoryMask: 1 },
];
const artifact = () => ({ loaded: false, manifest: null });
const projectedContext = vm.createContext({ console, encounterEvidenceReady: false, ensureAnalysisStats: () => Stats,
  analysisGeographyArtifact: artifact(), analysisTimeOfDayArtifact: artifact(), analysisDurationArtifact: artifact(),
  analysisWitnessCountArtifact: artifact(), analysisColorArtifact: artifact(), normalizedFilters: () => ({}), keywordIdSet: () => null,
  analysisActiveRange: () => null, matchedAnalysisRows: () => null, forEachAnalysisRow: callback => projectionRows.forEach(callback) });
vm.runInContext(workerSource.slice(start, end), projectedContext);
const projectedCapture = () => clone(projectedContext.captureAnalysisSession({ requestedEventIds: ["typed", "unsupported"], filters }));
assert.equal(projectedCapture().summary.distributions.color, null, "Typed-looking fields cannot override missing projection readiness");
for (const key of ["analysisGeographyArtifact", "analysisTimeOfDayArtifact", "analysisDurationArtifact", "analysisWitnessCountArtifact", "analysisColorArtifact"]) projectedContext[key].loaded = true;
projectedContext.analysisColorArtifact.manifest = { codes: { category: ["blue", "red"] } };
const projected = projectedCapture(), pd = projected.summary.distributions;
assert.deepEqual(counts(pd.macroregion), { Europe: 1 }); assert.equal(pd.macroregion.unknownN, 1);
assert.deepEqual(counts(pd.timeOfDay), { evening_18_23: 1 });
assert.deepEqual(counts(pd.duration), { "1_4_minutes": 1 });
assert.deepEqual(counts(pd.witnessCount), { two: 1 }, "Approximate witness counts do not become exact-count bins");
assert.equal(pd.witnessCount.unknownN, 1);
assert.deepEqual(counts(pd.color), { "surface:blue": 1, "surface:red": 1 }, "Color bit order follows the loaded codebook and retains reported role");
assert.equal(pd.color.eligibleN, 1); assert.equal(pd.color.unknownN, 1); assert.equal(pd.color.multiLabel, true);
projectionRows[0].analysisColorCategoryMask = 1; projectionRows[0].analysisColorStatus = "exact_single";
assert.deepEqual(counts(projectedCapture().summary.distributions.color), { "surface:blue": 1 }, "Bit zero uses the loaded blue-first codebook, not the default white-first palette");
projectionRows[0].analysisColorCategoryMask = 3; projectionRows[0].analysisColorStatus = "explicit_compound";
assert.equal(pd.adminRegion.rows.length, 2, "Identically named administrative regions in different countries are distinct");
assert.deepEqual(counts(pd.weekday), { "3": 1 }, "Unix epoch zero remains a supported Thursday");
const before = Session.compareGroups({ ...first, label: "Before projections" }, { ...projected, label: "After projections" });
assert.equal(before.distributions.color.available, false);
assert.equal(before.distributions.color.rows[0].aCount, null, "A projection unavailable at capture time cannot silently become a true zero");
assert.equal(before.distributions.color.rows[0].bCount, 1);
const overlapping = Session.compareGroups({ ...projected, eventIds: ["typed", "unsupported"] }, { ...projected, eventIds: ["typed", "unsupported"] });
assert.equal(overlapping.overlapCount, 2);
assert.equal(overlapping.distributions.color.rows[0].aCount, 1); assert.equal(overlapping.distributions.color.rows[0].bCount, 1);
assert.equal(overlapping.distributions.color.rows[0].aShare, 1);
assert.equal(overlapping.distributions.color.rows[0].aShareOfReports, 0.5);
const legacy = Session.compareGroups({ eventIds: [1], summary: { reportN: 1 } }, { eventIds: [2], summary: { reportN: 1 } });
for (const key of Session.DOMAINS) assert.equal(legacy.distributions[key].available, false, "Old capture payloads remain valid without fabricated new dimensions");
for (const [domain, keys] of [["year", ["2000", "1973"]], ["calendarMonth", ["12", "02", "01"]], ["weekday", ["6", "1", "0"]],
  ["timeOfDay", ["evening_18_23", "morning_06_11", "night_00_05"]], ["duration", ["over_5_hours", "1_4_minutes", "under_10_seconds"]],
  ["witnessCount", ["thousand_plus", "two", "one"]]]) {
  const payload = { eventIds: keys.map((_, index) => String(index)), summary: { distributions: { [domain]: {
    eligibleN: keys.length, unknownN: 0, rows: keys.map(key => ({ key, label: key, count: 1 })) } } } };
  const rows = Session.compareGroups(payload, payload).distributions[domain].rows;
  assert.deepEqual(rows.map(row => row.key), keys.slice().reverse(), "Temporal and numerical bins use logical order for " + domain);
}
console.log("Temporary comparison dimensions: exact membership, dates, geography, projection readiness, real codebooks, unknowns, overlap and immutable legacy captures passed.");
