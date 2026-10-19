import assert from "node:assert/strict";
import { createRequire } from "node:module";
import fs from "node:fs";
import vm from "node:vm";
const require = createRequire(import.meta.url);
const Model = require("../analysis_overview_model.js"), Stats = require("../analysis_stats.js"), Encounter = require("../encounter_evidence.js");
const day = (year, month = 1, date = 1) => Stats.ordinalFromCivil(year, month, date);
const mask = keys => Encounter.beingMask(keys);
const row = (id, year, month, extra = {}) => ({ eventId: String(id), source: "ufocat", craftType: "Disc / saucer", country: "USA",
  sortOrdinal: day(year, month), dateStartOrdinal: day(year, month), dateEndOrdinal: day(year, month), datePrecision: "exact_day",
  encounterEvidenceReady: true, encounterBeingMask: 0, encounterAbductionCode: 0, mapped: true, ...extra });
const reports = [
  row(1, 1952, 7, { encounterBeingMask: mask(["grey", "humanoid"]), encounterSourceBeingMask: mask(["grey"]), encounterNarrativeBeingMask: mask(["humanoid"]), encounterEvidenceProvenanceReady: true, encounterAbductionCode: 1 }),
  row(2, 1952, 8, { craftType: "Triangle", encounterBeingMask: mask(["grey"]), encounterSourceBeingMask: 0, encounterNarrativeBeingMask: mask(["grey"]), encounterEvidenceProvenanceReady: true, encounterAbductionCode: 2 }),
  row(3, 1952, 1, { datePrecision: "year", dateEndOrdinal: day(1952, 12, 31), country: "United Kingdom", encounterAbductionCode: 3, mapped: false }),
  row(4, 1979, 12, { datePrecision: "range", dateEndOrdinal: day(1980, 1), country: "France", craftType: "Light", encounterBeingMask: mask(["grey"]) }),
  row(5, 1989, 9, { country: "unknown", analysisCountry: "United Kingdom", craftType: "unknown", encounterBeingMask: mask(["human_like"]), encounterAbductionCode: 1 }),
  row(6, 1989, 9, { country: "unknown", analysisCountry: "unavailable", sourceCountry: "USA", craftType: "Triangle", encounterEvidenceReady: false, encounterBeingMask: mask(["grey"]), encounterAbductionCode: 1, mapped: false }),
  row(7, 1994, 9, { country: "Zimbabwe", encounterOccurrenceDateExcluded: true, encounterBeingMask: mask(["grey"]), mapped: false }),
  row(8, 2000, 1, { source: "unknown", country: "unknown", craftType: "unknown", datePrecision: "unknown", encounterEvidenceReady: false, mapped: false }),
];
const options = { rows: reports, encounterApi: Encounter, geographyProjectionLoaded: true };
const model = Model.compute(options);
const card = (value, key, lane = "all") => value.cards.find(item => item.key === key).lanes[lane];
const cell = (value, key, r, c, lane = "all") => card(value, key, lane).cells.find(item => item.rowKey === r && item.columnKey === c)?.count || 0;
assert.equal(model.schemaId, "ufo-analysis-overview-v1");
assert.equal(model.status, "ready_descriptive");
assert.equal(model.totalN, 8);
assert.equal(model.unit, "report representations");
assert.equal(model.inferentialTestsRun, 0);
assert.deepEqual(model.lanes.map(item => [item.key, item.totalN]), [["all", 8], ["beings", 5], ["abduction", 3]]);
assert.equal(model.coverage.ambiguousAbductionN, 1);
assert.equal(model.coverage.encounterUnavailableN, 2);
assert.equal(model.coverage.beingNotIndexedN, 1);
assert.equal(model.coverage.abductionNotIndexedN, 2, "Unindexed abduction evidence is distinct from unavailable data and ambiguous mentions");
assert.equal(model.coverage.mappedN, 4, "Unmapped report representations remain in comparisons");
assert.equal(model.coverage.knownCountryN, 7, "Reviewed country overrides known source; unknown reviewed country falls back to the source");
assert.equal(model.coverage.knownDecadeN, 5);
assert.equal(model.coverage.knownMonthN, 4);
assert.equal(cell(model, "craft_decade", "1950", "Disc / saucer"), 2);
assert.equal(cell(model, "craft_decade", "__unknown__", "Disc / saucer"), 1, "Withheld occurrence dates are not assigned to an era");
assert.equal(cell(model, "craft_decade", "__unknown__", "Light"), 1, "Spanning decade intervals do not become their first decade");
assert.equal(cell(model, "craft_month", "__unknown__", "Disc / saucer"), 2, "Year-only dates do not become January; withheld dates do not become September");
assert.equal(cell(model, "craft_country", "United Kingdom", "unknown"), 0);
assert.equal(cell(model, "craft_country", "United Kingdom", "__unknown__"), 1);
assert.equal(cell(model, "craft_country", "USA", "Triangle"), 2, "Country fallback includes unmapped reports");
assert.equal(cell(model, "being_craft", "grey", "Disc / saucer"), 2);
assert.equal(cell(model, "being_craft", "humanoid", "Disc / saucer"), 1);
assert.equal(card(model, "being_craft", "beings").columnTotals.find(item => item.key === "Disc / saucer").count, 2,
  "Column denominators count distinct reports, rather than overlapping being memberships");
assert.equal(card(model, "being_craft", "beings").rowTotals.reduce((n, item) => n + item.count, 0), 6);
assert.equal(card(model, "being_craft", "beings").totalN, 5);
assert.equal(cell(model, "being_craft", "__not_indexed__", "Disc / saucer"), 1);
assert.equal(cell(model, "being_craft", "__unavailable__", "Triangle"), 1);
assert.equal(card(model, "being_craft").eligibleN, 4);
assert.equal(card(model, "being_craft").unknownN, 4);
assert.match(model.notes.join(" "), /not independent events/);
assert.match(model.notes.join(" "), /Unmapped reports remain included/);
assert.match(model.cards.find(item => item.key === "being_craft").notes.join(" "), /physical craft association is not established/);

// Every single-label cross-tab reconciles to its lane; each label cell uses distinct report counts.
for (const entry of model.cards) for (const lane of Object.values(entry.lanes)) {
  assert.equal(lane.totalN, lane.eligibleN + lane.unknownN);
  for (const value of lane.cells) {
    assert.ok(value.count <= lane.rowTotals.find(item => item.key === value.rowKey).count);
    assert.ok(value.count <= lane.columnTotals.find(item => item.key === value.columnKey).count);
  }
  if (!entry.multiLabel) assert.equal(lane.cells.reduce((n, item) => n + item.count, 0), lane.totalN);
  lane.rows.forEach(item => item.counts.forEach((n, index) => assert.equal(n, lane.cells.find(value => value.rowKey === item.key && value.columnKey === lane.columns[index].key)?.count || 0)));
}

const sourceOnly = Model.compute({ ...options, encounterEvidenceMode: "source_fields" });
assert.deepEqual(sourceOnly.lanes.map(item => item.totalN), [8, 1, 2]);
assert.equal(cell(sourceOnly, "being_craft", "grey", "Disc / saucer"), 1);
assert.equal(cell(sourceOnly, "being_craft", "humanoid", "Disc / saucer"), 0);
assert.equal(cell(sourceOnly, "being_craft", "__unavailable__", "Light"), 1, "Missing origin provenance does not become no indexed description");
assert.equal(cell(sourceOnly, "being_craft", "__not_indexed__", "Triangle"), 1, "Known source-origin zero is not a source-reported being");
assert.equal(sourceOnly.coverage.ambiguousAbductionN, 0, "Ambiguous origin is not attributed to source/narrative evidence modes");
assert.equal(sourceOnly.coverage.abductionOtherEvidenceModeN, 1, "A narrative-reported abduction is outside source-field mode, not a negative abduction report");
const narrativeOnly = Model.compute({ ...options, encounterEvidenceMode: "narrative" });
assert.deepEqual(narrativeOnly.lanes.map(item => item.totalN), [8, 2, 1]);
assert.equal(cell(narrativeOnly, "being_craft", "humanoid", "Disc / saucer"), 1);

// The worker reuses a mutable row object. The overview must aggregate immediately, without retaining it or report IDs.
const reused = {};
const visitor = Model.compute({ encounterApi: Encounter, geographyProjectionLoaded: true, forEachRow(consume) {
  for (const value of reports) { Object.keys(reused).forEach(key => delete reused[key]); Object.assign(reused, value); consume(reused); }
} });
assert.deepEqual(visitor, model);
assert.ok(!JSON.stringify(model).includes('"eventId"'));
assert.deepEqual(Model.compute({ ...options, rows: reports.slice().reverse() }), model, "Result ordering does not depend on catalog chunk order");

const spans = Model.compute({ encounterApi: Encounter, rows: [
  row(10, 1981, 1, { datePrecision: "range", dateEndOrdinal: day(1989, 12, 31) }),
  row(11, 1990, 1, { datePrecision: "decade", dateEndOrdinal: day(1999, 12, 31) }),
  row(12, 1900, 1, { datePrecision: "century", dateEndOrdinal: day(1999, 12, 31) }),
  row(13, 1950, 1, { datePrecision: "range", dateEndOrdinal: day(1949, 12, 31) }),
  row(14, 1, 1, { datePrecision: "year_only" }),
] });
assert.equal(cell(spans, "craft_decade", "1980", "Disc / saucer"), 1, "A multi-year interval within one decade has known decade, not known month");
assert.equal(cell(spans, "craft_decade", "1990", "Disc / saucer"), 1);
assert.equal(cell(spans, "craft_decade", "__unknown__", "Disc / saucer"), 2, "Century precision and invalid intervals stay unknown");
assert.equal(card(spans, "craft_decade").rowTotals.find(item => item.key === "0").label, "1–9", "There is no invented year zero");
assert.equal(spans.coverage.knownMonthN, 0);
assert.deepEqual(model.cards.filter(item => ["craft_decade", "month_decade", "source_decade", "being_decade"].includes(item.key)).map(item => item.rowDimension),
  ["decade", "decade", "decade", "decade"], "Within-row shares answer composition within a decade");
const badOrigins = Model.compute({ encounterApi: Encounter, encounterEvidenceMode: "source_fields", rows: [row(15, 2000, 1, {
  encounterBeingMask: mask(["grey", "humanoid"]), encounterSourceBeingMask: mask(["grey"]), encounterNarrativeBeingMask: 0, encounterEvidenceProvenanceReady: true,
})] });
assert.equal(badOrigins.coverage.beingN, 0);
assert.equal(badOrigins.coverage.beingEvidenceUnavailableN, 1, "Incomplete source/narrative mask partitions remain unavailable despite a readiness flag");
assert.deepEqual(Model.civilFromOrdinal(1), { year: 1, month: 1, day: 1 });
assert.deepEqual(Model.civilFromOrdinal(day(2000, 2, 29)), { year: 2000, month: 2, day: 29 });
assert.equal(Model.civilFromOrdinal(0), null);

const unavailable = Model.compute({ rows: reports });
assert.equal(unavailable.lanes.find(item => item.key === "beings").available, false);
assert.equal(unavailable.lanes.find(item => item.key === "beings").totalN, 0);
assert.equal(unavailable.coverage.beingEvidenceUnavailableN, 8);
assert.match(unavailable.notes.join(" "), /optional reviewed geography projection has not loaded/);
assert.equal(Model.compute({ rows: [], encounterApi: Encounter }).totalN, 0);
assert.throws(() => Model.compute({}), /Overview requires rows/);
assert.throws(() => Model.compute({ rows: [null] }), /report objects/);

const scope = {};
vm.runInNewContext(fs.readFileSync(new URL("../analysis_overview_model.js", import.meta.url), "utf8"), scope);
assert.equal(typeof scope.UfoAnalysisOverviewModel.compute, "function", "Worker/browser UMD export is available without Node imports");
console.log("Analysis overview model checks passed.");
