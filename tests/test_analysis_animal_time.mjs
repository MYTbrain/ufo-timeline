import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const Stats = require("../analysis_stats.js");
const day = (year, month = 1, date = 1) => Stats.ordinalFromCivil(year, month, date);
const records = [
  { id: "multi-label", year: 1978, datePrecision: "year", species: ["bovine", "ovine", "bovine"], country: "US" },
  { id: "cross-decade", startYear: 1979, endYear: 1980, datePrecision: "range", species: ["bovine"], country: "US" },
  { id: "within-decade", startYear: 1981, endYear: 1982, datePrecision: "range", species: ["equine"], country: "CA" },
  { id: "undated", datePrecision: "unknown", species: [], country: "unknown" },
  { id: "ordinal-only", startOrdinal: day(1970, 5, 6), datePrecision: "exact_day", species: ["canid"], country: "CA" },
  { id: "interval-wins", year: 2030, startOrdinal: day(1999, 12, 20), endOrdinal: day(1999, 12, 31), datePrecision: "range", species: ["bovine"], country: "GB" },
  { id: "month", year: 1985, startOrdinal: day(1985, 5, 1), endOrdinal: day(1985, 5, 31), datePrecision: "month", species: ["caprine"] },
];
const projections = Stats.normalizeContextProjections({ animalReports: records });
const before = JSON.stringify(projections);
const compute = (options = {}, data = projections) => Stats.computeAnalysis({
  rows: [], quickMode: true, selectedDomains: ["context"], contextProjections: data, ...options,
}).context.animals;
const cell = (matrix, row, column) => {
  const found = matrix.cells.find(value => value.row === row && value.column === column);
  assert.ok(found, row + " / " + column);
  return found;
};

// All Time retains undated reports without inventing a repeated reference cohort.
let animals = compute({ fullTimeRange: true });
assert.equal(animals.activeCount, records.length);
assert.equal(animals.totalProjectionRows, records.length);
assert.equal(animals.referenceCount, 0);
const yearly = animals.temporal.species.yearly;
assert.deepEqual(yearly.columns, ["1970", "1978", "1985", "1999", "unknown"]);
assert.equal(yearly.metadata.activeReportCount, 7);
assert.equal(yearly.metadata.activeTimedReportCount, 4);
assert.equal(yearly.metadata.activeUnknownDateCount, 1);
assert.equal(yearly.metadata.activeAmbiguousPeriodCount, 2);
assert.equal(yearly.metadata.activeUnknownLabelCount, 1);
assert.equal(yearly.metadata.activeMembershipCount, 6);
assert.equal(yearly.metadata.referenceReportCount, 0);
assert.equal(cell(yearly, "bovine", "1978").observedCount, 1, "Repeated labels count once within a report");
assert.equal(cell(yearly, "ovine", "1978").observedCount, 1, "A multi-species report contributes once to each distinct species");
assert.equal(cell(yearly, "bovine", "1999").observedCount, 1, "Stored intervals override an inconsistent representative year");
assert.equal(cell(yearly, "unknown", "unknown").observedCount, 1);
assert.equal(cell(yearly, "bovine", "1970").observedCount, 0, "A represented species-period combination can legitimately contain zero reports");
assert.equal(yearly.cells.length, yearly.rows.length * yearly.columns.length, "Exact tables retain the full represented row-period matrix");
assert.ok(!yearly.columns.includes("1979") && !yearly.columns.includes("2030"), "No first-year assignment or interpolation for multi-year intervals");
assert.ok(!yearly.rows.includes("equine"), "An excluded interval does not become a zero observed annual report");

const decadal = animals.temporal.species.decadal;
assert.deepEqual(decadal.columns, ["1970", "1980", "1990", "unknown"]);
assert.equal(decadal.metadata.activeTimedReportCount, 5);
assert.equal(decadal.metadata.activeAmbiguousPeriodCount, 1);
assert.equal(decadal.metadata.activeUnknownDateCount, 1);
assert.equal(cell(decadal, "equine", "1980").observedCount, 1, "An interval wholly within one decade supports that decade");
assert.equal(cell(decadal, "bovine", "1970").observedCount, 1, "A cross-decade interval is not assigned to its first decade");
assert.equal(decadal.metadata.activeMembershipCount, 7);

const locations = animals.temporal.locations.yearly;
assert.equal(locations.metadata.multiLabel, false);
assert.equal(locations.metadata.activeMembershipCount, 5, "Country counts are reports, never number of animals or species memberships");
assert.equal(locations.metadata.activeUnknownLabelCount, 2);
assert.equal(cell(locations, "unknown", "1985").observedCount, 1, "Missing geography remains explicit");
assert.equal(cell(locations, "CA", "1970").observedCount, 1, "An explicit country is usable even without coordinates");
assert.ok(locations.metadata.membershipUnit.includes("explicit country"));

for (const dimension of Object.values(animals.temporal)) {
  for (const matrix of Object.values(dimension)) {
    assert.equal(matrix.metadata.descriptiveOnly, true);
    assert.equal(matrix.metadata.inferenceEligible, false);
    assert.equal(matrix.metadata.activeReportCount,
      matrix.metadata.activeTimedReportCount + matrix.metadata.activeUnknownDateCount + matrix.metadata.activeAmbiguousPeriodCount);
    assert.equal(matrix.cells.reduce((sum, value) => sum + value.observedCount, 0), matrix.metadata.activeMembershipCount);
    assert.ok(matrix.cells.every(value => value.inferenceEligible === false && value.patternFinderEligible === false && value.pValue === null && value.qValue === null));
  }
}

// Windowed cohorts follow existing inclusive interval membership and baseline rules.
animals = compute({ timeRangeStartOrdinal: day(1978), timeRangeEndOrdinal: day(1978, 12, 31) });
assert.equal(animals.activeCount, 1);
assert.equal(animals.referenceCount, 5, "Undated reports are excluded from finite disjoint references");
let matrix = animals.temporal.species.yearly;
assert.equal(matrix.metadata.activeReportCount, 1);
assert.equal(matrix.metadata.referenceReportCount, 5);
assert.equal(matrix.metadata.referenceAmbiguousPeriodCount, 2);
assert.equal(matrix.metadata.referenceUnknownDateCount, 0);
assert.equal(matrix.metadata.activeMembershipCount, 2);
assert.equal(matrix.metadata.referenceMembershipCount, 3);
assert.equal(cell(matrix, "canid", "1970").referenceCount, 1);
assert.equal(cell(matrix, "canid", "1970").observedCount, 0);

animals = compute({ timeRangeStartOrdinal: day(1978), timeRangeEndOrdinal: day(1978, 12, 31), baselineMode: "full_catalog" });
assert.equal(animals.referenceCount, 7, "The existing overlapping full-catalog reference semantics remain unchanged");
assert.equal(animals.temporal.species.yearly.metadata.referenceUnknownDateCount, 1);
assert.equal(cell(animals.temporal.species.yearly, "bovine", "1978").referenceCount, 1);

const intervalFixture = Stats.normalizeContextProjections({ animalReports: [
  records[0],
  { id: "previous-day", species: ["bovine"], startOrdinal: day(1978, 6, 30), datePrecision: "exact_day" },
] });
animals = compute({ timeRangeStartOrdinal: day(1978, 7, 1), timeRangeEndOrdinal: day(1978, 7, 1), baselineMode: "previous_equal_duration" }, intervalFixture);
assert.equal(animals.activeCount, 1);
assert.equal(animals.referenceCount, 1, "A year-long interval overlapping both windows belongs only to the active disjoint cohort");
assert.equal(cell(animals.temporal.species.yearly, "bovine", "1978").referenceCount, 1);
assert.equal(animals.temporal.species.yearly.metadata.referenceMembershipCount, 1);

// Optional country extension is backwards compatible with existing nine-field rows.
const packed = Stats.normalizeContextProjections({ animalReports: {
  codes: { datePrecision: ["year"], speciesGroup: ["bovine"], status: ["unreviewed"], country: ["US", "CA"] },
  rows: [
    ["old", 1978, 1978, 0, [0], false, 0, null, null],
    ["country-string", 1978, 1978, 0, [0], false, 0, null, null, "GB"],
    ["country-code", 1978, 1978, 0, [0], false, 0, null, null, 1],
  ],
} });
assert.deepEqual(packed.animalReports.map(row => row.country), ["unknown", "GB", "CA"]);
animals = compute({ fullTimeRange: true }, packed);
assert.equal(cell(animals.temporal.locations.yearly, "unknown", "1978").observedCount, 1);
assert.equal(cell(animals.temporal.locations.yearly, "GB", "1978").observedCount, 1);
assert.equal(cell(animals.temporal.locations.yearly, "CA", "1978").observedCount, 1);

animals = compute({ fullTimeRange: true, contextLayers: { animalMutilationsEnabled: false } });
assert.equal(animals.status, "disabled");
assert.equal(animals.temporal, undefined);
assert.equal(compute({ fullTimeRange: true }, Stats.normalizeContextProjections({})).status, "not_loaded");
assert.equal(JSON.stringify(projections), before, "Temporal summaries never mutate normalized source records");

console.log("Animal temporal matrices: distinct species, explicit geography, supported years/decades, unknowns, exclusions, cohort semantics, backwards-compatible country fields and descriptive-only gates passed.");
