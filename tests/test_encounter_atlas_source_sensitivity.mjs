import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const stats = require("../analysis_stats.js");
const query = require("../encounter_atlas_query.js");
const day = stats.ordinalFromCivil(2000, 1, 1);
const rows = [];
function add(source, rowKey, n, triangles) {
  const mask = 1 << (rowKey === "grey" ? 0 : 6);
  for (let i = 0; i < n; i += 1) rows.push({ eventId: `${source}-${rowKey}-${i}`, source, type: "sighting",
    sortOrdinal: day, dateStartOrdinal: day, dateEndOrdinal: day, datePrecision: "exact_day", mapped: false,
    analysisCountry: "United States", analysisMacroregion: "North America", encounterOccurrenceDateExcluded: false,
    encounterBeingMask: mask, encounterAbductionCode: 1, encounterCraftAssociationCode: 1,
    craftType: i < triangles ? "triangle" : "disc_saucer" });
}
add("large", "grey", 160, 128);
add("large", "humanoid", 40, 36);
add("small", "grey", 5, 0);
add("small", "humanoid", 15, 3);
const settings = { rows, fullTimeRange: true, baselineMode: "full_catalog", quickMode: true, selectedDomains: ["encounters"],
  encounterEvidenceReady: true, geographyProjectionLoaded: true };
const atlas = stats.computeAnalysis(settings).encounters.comparisonAtlas;
const axis = atlas.axes.find((entry) => entry.key === "craft");
const cell = axis.cells.find((entry) => entry.row === "grey" && entry.column === "triangle");
assert.equal(cell.count, 128);
assert.equal(cell.rowShare, 128 / 165);
assert.equal(cell.columnShare, 128 / 167);
assert.ok(Math.abs(cell.sourceStandardizedShare - 0.32) < 1e-12);
assert.ok(Math.abs(cell.sourceStandardizedRowShare - 0.64 / 1.05) < 1e-12, "Standardization uses the same source mixture for joint and marginal report composition");
assert.ok(Math.abs(cell.sourceStandardizedColumnShare - 0.64 / (0.82 + 0.15)) < 1e-12);
assert.equal(cell.sourceCoverage.eligibleSources, 2);
assert.deepEqual(axis.sourceStandardization.weights.map((item) => [item.source, item.weight]), [["large", 0.5], ["small", 0.5]]);
assert.equal(cell.leaveOneSourceOut.find((item) => item.excludedSource === "large").rowShare, 0);
assert.equal(cell.leaveOneSourceOut.find((item) => item.excludedSource === "small").rowShare, 0.8);
assert.deepEqual(cell.sourceSensitivity.rowShare, { lower: 0, upper: 0.8, estimates: 2, kind: "leave_one_source_out_sensitivity_range", confidenceLevel: null });
assert.equal(cell.conditionalComparison.status, "ready_descriptive_conditional");
assert.equal(cell.conditionalComparison.commonSupportRate, 1);
assert.equal(cell.conditionalComparison.commonRowN, 165);
assert.equal(cell.conditionalComparison.commonOtherN, 55);
assert.equal(cell.conditionalComparison.commonStrata, 2);
const rawOtherShare = 39 / 55;
assert.ok(cell.rowShare > rawOtherShare, "Raw mixture has a positive descriptive difference");
assert.ok(Math.abs(cell.conditionalComparison.difference - (-0.1 * 200 / 220 - 0.2 * 20 / 220)) < 1e-12,
  "Common-stratum standardization detects the opposite within-source descriptive composition");
assert.equal(cell.conditionalComparison.pValue, null);
assert.equal(cell.conditionalComparison.qValue, null);
assert.equal(cell.conditionalComparison.statisticalInterval, null);
assert.equal(cell.conditionalComparison.inferenceEligible, false);
assert.equal(axis.multipleTesting.testsRun, 0);
assert.equal(axis.multipleTesting.familyId, "encounter_being_craft_conditional_v1");
assert.equal(axis.multipleTesting.declaredComparisons, 4);
assert.equal(atlas.inferentialTestsRun, 0);
assert.equal(atlas.patternFinderEligible, false);
const sourceCell = atlas.axes.find((entry) => entry.key === "source").cells[0];
assert.equal(sourceCell.conditionalComparison.status, "not_applicable_conditioned_axis");
const self = atlas.axes.find((entry) => entry.key === "co_descriptions").cells.find((entry) => entry.row === entry.column);
assert.equal(self.conditionalComparison.status, "not_applicable_row_definition");
const noGeography = stats.computeAnalysis({ ...settings, geographyProjectionLoaded: false,
  rows: rows.map((row) => ({ ...row, analysisMacroregion: undefined })) }).encounters.comparisonAtlas.axes.find((entry) => entry.key === "craft").cells[0];
assert.equal(noGeography.conditionalComparison.status, "insufficient_common_support");
assert.equal(noGeography.conditionalComparison.difference, null);
assert.equal(noGeography.conditionalComparison.conditioningUnknownReports, 220);
const rare = stats.computeAnalysis({ ...settings, rows: rows.slice(0, 2) }).encounters.comparisonAtlas.axes.find((entry) => entry.key === "craft").cells[0];
assert.equal(rare.conditionalComparison.estimateAvailable, false);
assert.equal(rare.conditionalComparison.difference, null);
const scanned = query.collectPage((visit) => rows.forEach(visit), { population: "being", axis: "craft", row: "grey", column: "triangle" },
  { offset: 100, limit: 1000 });
assert.equal(scanned.totalMatched, 128);
assert.equal(scanned.limit, 100);
assert.equal(scanned.rows.length, 28);
assert.equal(scanned.coverage.populationReports, 165);
assert.equal(scanned.coverage.supportedReports, 165);
const full = stats.computeAnalysis({ ...settings, selectedDomains: ["craft", "encounters"] }).encounters.comparisonAtlas;
assert.deepEqual(full, atlas, "Source standardization and conditional results preserve quick/full parity");
console.log("Encounter source standardization, source omission, conditional support and blocked inference checks passed.");
