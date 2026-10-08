import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const Planetary = require("../analysis_planetary.js");
const day = date => Math.floor(Date.parse(date + "T00:00:00Z") / 86400000);
const row = (date, extra = {}) => ({ sortOrdinal: day(date), datePrecision: "exact_day", craftType: "disc", ...extra });
const fullMonth = (date, n, category) => Array.from({ length: n }, (_, i) => row(date, { sortOrdinal: day(date) + i, craftType: category, source: i % 2 ? "a" : "b" }));
const contexts = (date, n, category) => fullMonth(date, n, category).map(record => ({ ...record, category, dateRole: "discovery", startOrdinal: record.sortOrdinal, endOrdinal: record.sortOrdinal }));
const verified = row("2024-04-13", { utcTimestamp: "2024-04-13T12:34:00Z", utcTimestampVerified: true, timeZoneProvenance: "Independent verified fixture" });
const input = { rows: [...fullMonth("2024-04-01", 30, "disc"), ...fullMonth("2024-05-01", 31, "triangle"), verified,
  row("2024-04-03", { isContext: true }), row("2024-04-03", { datePrecision: "month" })],
  crops: contexts("2024-04-01", 30, "radial"), animals: contexts("2024-05-01", 31, "bovine") };
const prepared = Planetary.preparePlanetaryCohort(input);
const days = Array.from({ length: 63 }, (_, i) => day("2024-03-31") + i);
const atlas = Planetary.buildEphemerisAtlasBuffer(days);
Planetary.setEphemerisAtlas(Planetary.decodeEphemerisAtlas(atlas.buffer, atlas.metadata));
const model = Planetary.computePlanetaryHeatmaps({ preparedCohort: prepared, includeCategoryMatrices: true });
assert.equal(model.samplingMode, "common_grid");
assert.equal(model.pairs.length, 36);
assert.equal(new Set(model.pairs.map(pair => [pair.planet, pair.partner].sort().join("|"))).size, 36);
assert.ok(model.pairs.every(pair => pair.planet !== pair.partner));
assert.equal(model.method.sha256.length, 64);
assert.equal(model.domains[0].nonReportContextCount, 1);
assert.equal(model.domains[0].excluded.date_not_exact_day, 1);
assert.equal(model.domains[0].verifiedTimeCount, 1);
assert.equal(model.domains[1].dateRoles.discovery, 30);
const fields = ["count", "lowerCount", "upperCount", "share", "expectedCount", "expectedCalendarShare", "calendarAdjustedRatio"];
function partition(domain) {
  for (const [kind, rowN, cellN] of [["zodiac", 9, 12], ["motion", 9, 3], ["aspects", 36, 6]]) {
    assert.equal(domain.matrices[kind].rows.length, rowN);
    for (const entry of domain.matrices[kind].rows) {
      assert.equal(entry.cells.length, cellN);
      assert.equal(entry.cells.reduce((sum, cell) => sum + cell.count, 0), domain.positionEligible);
      assert.ok(Math.abs(entry.cells.reduce((sum, cell) => sum + cell.expectedCount, 0) - domain.positionEligible) < 0.001);
      for (const cell of entry.cells) {
        assert.ok(0 <= cell.lowerCount && cell.lowerCount <= cell.count && cell.count <= cell.upperCount && cell.upperCount <= domain.positionEligible,
          `${domain.id}:${entry.label}:${cell.id} bounds do not contain count`);
        if (cell.expectedCount === 0) assert.equal(cell.calendarAdjustedRatio, null);
      }
    }
  }
}
model.domains.forEach(partition);
for (const domain of model.domains) for (const category of domain.categoryMatrices) {
  partition({ ...category, id: category.category, positionEligible: category.total });
  // Each category is a complete calendar month; its expected denominator must
  // retain its own month mix rather than borrowing another category's era.
  if (category.category !== "disc") for (const matrix of Object.values(category.matrices)) for (const entry of matrix.rows) for (const cell of entry.cells) {
    if (cell.expectedCount > 0) assert.ok(Math.abs(cell.calendarAdjustedRatio - 1) < 0.0001);
  }
}

// All 36 pair drilldowns use exactly the bulk noon states and common sampled
// bounds. Verified UTC exceptions must also stay raw/raw at aspect boundaries.
for (const pair of model.pairs) {
  const individual = Planetary.computePlanetaryContext({ preparedCohort: prepared, planet: pair.planet, aspectPartner: pair.partner, samplingMode: "common_grid" });
  for (let d = 0; d < model.domains.length; d++) {
    const detail = individual.domains[d], bulk = model.domains[d];
    const aspectRow = bulk.matrices.aspects.rows.find(entry => entry.id === pair.id);
    const detailCells = detail.aspectPartners[0].bins.concat([detail.aspectPartners[0].outsideBand]);
    for (let c = 0; c < 6; c++) for (const field of fields) {
      assert.equal(aspectRow.cells[c][field], detailCells[c][field], `${bulk.id}:${pair.label}:${c}:${field}`);
    }
    for (const [kind, bins] of [["zodiac", detail.signBins], ["motion", detail.motion.bins]]) {
      const bulkRow = bulk.matrices[kind].rows.find(entry => entry.planet === pair.planet);
      for (let c = 0; c < bins.length; c++) for (const field of fields) assert.equal(bulkRow.cells[c][field], bins[c][field], `${kind}:${pair.planet}:${field}`);
    }
    assert.equal(aspectRow.variableStateReports, detail.aspectPartners[0].variableAspectReports);
    assert.equal(aspectRow.variableStateMonths, detail.aspectPartners[0].variableAspectMonths);
  }
}
const reverse = Planetary.computePlanetaryContext({ preparedCohort: prepared, planet: "Moon", aspectPartner: "Sun", samplingMode: "common_grid" });
for (let d = 0; d < model.domains.length; d++) {
  const forward = model.domains[d].matrices.aspects.rows.find(entry => entry.id === "sun__moon");
  for (let c = 0; c < 6; c++) for (const field of fields) assert.equal(forward.cells[c][field], reverse.domains[d].aspectPartners[0].bins.concat([reverse.domains[d].aspectPartners[0].outsideBand])[c][field]);
}
assert.equal(Planetary.positionForDay(day("2024-04-19"), { planet: "Venus", samplingMode: "common_grid" }).sampleCount, 11);
assert.equal(Planetary.positionForDay(day("2024-04-19"), { planet: "Venus" }).samplingMode, "adaptive");
assert.throws(() => Planetary.computePlanetaryHeatmaps({ preparedCohort: prepared, ayanamsaDegreesAtUtc: () => NaN }), /invalid offset/);
const empty = Planetary.computePlanetaryHeatmaps({ rows: [row("2024-04-03", { datePrecision: "month" })] });
for (const domain of empty.domains) for (const matrix of Object.values(domain.matrices)) for (const entry of matrix.rows) for (const cell of entry.cells) {
  assert.equal(cell.share, null); assert.equal(cell.calendarAdjustedRatio, null); assert.equal(cell.status, "unavailable_exact_dates_required");
}
const slow = model.domains[2].matrices.zodiac.rows.find(entry => entry.planet === "Saturn");
assert.equal(slow.variableStateReports, 0);
assert.ok(slow.cells.some(cell => cell.status === "no_within_month_contrast"));
assert.equal(model.inferenceEligible, false);
assert.equal(model.patternFinderEligible, false);
Planetary.clearEphemerisAtlas();
console.log("planetary heatmap partition, opportunity, common-grid and 36-pair drilldown parity passed");
