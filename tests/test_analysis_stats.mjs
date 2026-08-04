import assert from "node:assert/strict";
import { createRequire } from "node:module";
import fs from "node:fs";

const require = createRequire(import.meta.url);
const stats = require("../webapp/static_public/analysis_stats.js");

assert.equal(stats.normalizeBaselineMode("other_dates_matched"), "other_dates_balanced");
assert.equal(stats.normalizeBaselineMode("other_dates_balanced"), "other_dates_balanced");

assert.equal(stats.ordinalFromCivil(1970, 1, 1), 719163);
assert.deepEqual(stats.civilFromOrdinal(719163), { year: 1970, month: 1, day: 1 });
assert.deepEqual(stats.civilFromOrdinal(stats.ordinalFromCivil(2000, 2, 29)), { year: 2000, month: 2, day: 29 });
const derivedGridFixture = stats.equalAreaGridCell(40, -100);
assert.deepEqual(
  stats.equalAreaGridCellFromIndexes(derivedGridFixture.latIndex, derivedGridFixture.lonIndex),
  derivedGridFixture,
  "worker-derived equal-area indices must reproduce the canonical grid cell exactly"
);
const lambertMapFixture = stats.equalAreaMapCell6x12(40, -100);
assert.deepEqual(
  stats.equalAreaMapCell6x12FromIndexes(lambertMapFixture.latIndex, lambertMapFixture.lonIndex),
  lambertMapFixture,
  "the 6x12 map cell must round-trip through its deterministic Lambert equal-area indices"
);

const half = stats.wilsonInterval(50, 100);
assert.ok(half.lower > 0.40 && half.lower < 0.41);
assert.ok(half.upper > 0.59 && half.upper < 0.60);
const difference = stats.newcombeDifferenceInterval(60, 100, 40, 100);
assert.ok(difference.lower > 0.05 && difference.upper < 0.34);

const qValues = stats.benjaminiHochberg([{ pValue: 0.01 }, { pValue: 0.04 }, { pValue: 0.03 }]);
assert.deepEqual(qValues.map((value) => Math.round(value * 100) / 100), [0.03, 0.04, 0.04]);

const cmh = stats.cochranMantelHaenszel([
  { key: "north", activeCount: 20, activeTotal: 40, referenceCount: 10, referenceTotal: 40 },
  { key: "south", activeCount: 20, activeTotal: 40, referenceCount: 10, referenceTotal: 40 },
]);
assert.equal(cmh.method, "cochran_mantel_haenszel");
assert.equal(cmh.oddsRatio, 3);
assert.ok(cmh.interval.lower > 1 && cmh.pValue < 0.01);

const supportStrata = [
  { key: "supported", activeCount: 48, activeTotal: 80, referenceCount: 24, referenceTotal: 80 },
  { key: "active-only", activeCount: 20, activeTotal: 20, referenceCount: 0, referenceTotal: 0 },
  { key: "reference-only", activeCount: 0, activeTotal: 0, referenceCount: 10, referenceTotal: 20 },
];
const balancedSupport = stats.balancedCommonSupportComparison(supportStrata, {
  activeN: 100,
  referenceN: 100,
  seed: "balanced-support-fixture",
  covariates: ["source", "coarse_geography"],
});
assert.equal(balancedSupport.commonSupportRate, 0.8);
assert.equal(balancedSupport.inferenceEligible, true);
assert.equal(balancedSupport.adjustedActiveShare, 0.6);
assert.equal(balancedSupport.adjustedReferenceShare, 0.3);
assert.equal(balancedSupport.adjustedDifference, 0.3);
assert.equal(balancedSupport.interval.method, "deterministic_aggregated_stratum_bootstrap");
assert.equal(balancedSupport.interval.replicates, 999);
assert.deepEqual(
  stats.balancedCommonSupportComparison(supportStrata, {
    activeN: 100,
    referenceN: 100,
    seed: "balanced-support-fixture",
    covariates: ["source", "coarse_geography"],
  }).interval,
  balancedSupport.interval,
  "aggregated-stratum bootstrap output must be deterministic for a pinned seed"
);
const heterogeneousBootstrap = stats.deterministicAggregatedStratumBootstrap([
  { key: "large-active-small-reference", activeCount: 72, activeTotal: 90, referenceCount: 2, referenceTotal: 10 },
  { key: "small-active-large-reference", activeCount: 1, activeTotal: 10, referenceCount: 63, referenceTotal: 90 },
], { seed: "heterogeneous-strata-regression", replicates: 999 });
assert.equal(heterogeneousBootstrap.estimate, 0.48);
assert.equal(heterogeneousBootstrap.strataCount, 2);
assert.deepEqual(
  { lower: heterogeneousBootstrap.lower, upper: heterogeneousBootstrap.upper },
  { lower: 0.21883333, upper: 0.69011111 },
  "bootstrap replicates must resample inside each heterogeneous support stratum and then re-standardize, not sample one pooled active/reference proportion"
);
const insufficientSupport = stats.balancedCommonSupportComparison([
  ...supportStrata,
  { key: "another-active-only", activeCount: 1, activeTotal: 1, referenceCount: 0, referenceTotal: 0 },
], { activeN: 101, referenceN: 100, seed: "insufficient-support" });
assert.ok(insufficientSupport.commonSupportRate < 0.8);
assert.equal(insufficientSupport.inferenceEligible, false);
assert.equal(insufficientSupport.pValue, null);
assert.ok(insufficientSupport.suppressionReasons.includes("common_support"));

const adjustedResidualFixture = [
  { stratum: "north", row: "disk", column: "source-a", count: 50 },
  { stratum: "north", row: "disk", column: "source-b", count: 10 },
  { stratum: "north", row: "triangle", column: "source-a", count: 10 },
  { stratum: "north", row: "triangle", column: "source-b", count: 50 },
  { stratum: "south", row: "disk", column: "source-a", count: 50 },
  { stratum: "south", row: "disk", column: "source-b", count: 10 },
  { stratum: "south", row: "triangle", column: "source-a", count: 10 },
  { stratum: "south", row: "triangle", column: "source-b", count: 50 },
];
const adjustedResiduals = stats.adjustedStandardizedResiduals(adjustedResidualFixture);
assert.equal(adjustedResiduals.metadata.eligible, true);
assert.equal(adjustedResiduals.metadata.estimatorVersion, stats.ESTIMATOR_VERSION);
assert.equal(adjustedResiduals.cells.length, 4);
assert.ok(adjustedResiduals.cells.every((cell) => cell.qValue <= 0.05 && cell.displayEligible));
assert.equal(adjustedResiduals.metadata.pValueMethod, "deterministic_stratified_permutation");
assert.equal(adjustedResiduals.metadata.permutationCount, 499);
assert.ok(adjustedResiduals.fullCells.every((cell) => (
  !cell.tested || (
    cell.pValueMethod === "deterministic_stratified_permutation" &&
    cell.permutationCount === 499 &&
    Math.abs((cell.pValue * 500) - Math.round(cell.pValue * 500)) < 1e-8
  )
)), "association p-values come from the 499-permutation empirical null, not a normal CDF");
assert.deepEqual(
  stats.adjustedStandardizedResiduals(adjustedResidualFixture.slice().reverse()),
  adjustedResiduals,
  "stratified association permutations are deterministic and invariant to aggregate input order"
);
const eligiblePermutationCells = adjustedResiduals.fullCells.filter((cell) => cell.inferenceEligible);
const expectedPermutationQ = stats.benjaminiHochberg(eligiblePermutationCells, (cell) => cell.pValue)
  .map((value) => Number(value.toFixed(12)));
assert.deepEqual(
  eligiblePermutationCells.map((cell) => cell.qValue),
  expectedPermutationQ,
  "association q-values are calculated only from eligible empirical permutation p-values"
);

const sparseHeatmap = stats.qualifySparseHeatmapCells([
  { key: "empty", row: "r1", column: "c1", observed: 0, referenceCount: 0, expected: 0, commonSupportRate: 1 },
  { key: "depletion", row: "r1", column: "c2", observed: 0, referenceCount: 25, expected: 12, commonSupportRate: 1, adjustedEffect: -0.2 },
  { key: "sparse", row: "r2", column: "c1", observed: 2, referenceCount: 3, expected: 2, commonSupportRate: 1 },
]);
assert.equal(sparseHeatmap.fullCells.find((cell) => cell.key === "empty").displayStatus, "structurally_empty");
assert.equal(sparseHeatmap.fullCells.find((cell) => cell.key === "depletion").zeroObservedQualifiedDepletion, true);
assert.equal(sparseHeatmap.fullCells.find((cell) => cell.key === "sparse").displayStatus, "low_support");
assert.equal(sparseHeatmap.fullCells.find((cell) => cell.key === "sparse").estimateAvailable, true);
assert.deepEqual(
  sparseHeatmap.visibleCells.map((cell) => cell.key).sort(),
  ["depletion", "sparse"],
  "low-support estimates remain visible instead of becoming suppression labels"
);

const mixedSupportResiduals = stats.adjustedStandardizedResiduals([
  { stratum: "all", row: "common", column: "a", count: 90 },
  { stratum: "all", row: "common", column: "b", count: 30 },
  { stratum: "all", row: "rare", column: "a", count: 1 },
  { stratum: "all", row: "rare", column: "b", count: 0 },
]);
assert.ok(mixedSupportResiduals.metadata.cramersV >= 0 && mixedSupportResiduals.metadata.cramersV <= 1);
assert.equal(mixedSupportResiduals.fullCells.length, 4, "the selected contingency table materializes observed zeroes");
assert.ok(mixedSupportResiduals.fullCells.every((cell) => cell.estimateAvailable));
const rareZeroCell = mixedSupportResiduals.fullCells.find((cell) => cell.row === "rare" && cell.column === "b");
assert.equal(rareZeroCell.observedCount, 0);
assert.ok(rareZeroCell.expectedCount > 0);
assert.equal(rareZeroCell.tested, true, "a positive-expectation zero observation receives a cell-wise permutation test");
assert.equal(rareZeroCell.pValueMethod, "deterministic_stratified_permutation");
assert.equal(rareZeroCell.permutationCount, stats.DEFAULT_ASSOCIATION_PERMUTATIONS);
assert.ok(rareZeroCell.pValue > 0 && rareZeroCell.pValue <= 1);
assert.equal(rareZeroCell.qValue, null, "low-support cells do not enter the BH family");
assert.ok(mixedSupportResiduals.fullCells.some((cell) => cell.inferenceEligible), "a rare cell cannot table-suppress supported cells");
assert.equal(
  mixedSupportResiduals.metadata.fdrFamilySize,
  mixedSupportResiduals.fullCells.filter((cell) => cell.inferenceEligible).length,
  "BH includes only individually testable, supported cells"
);

function row(overrides = {}) {
  return {
    eventId: overrides.eventId || "event",
    source: "source-a",
    type: "UFO",
    visualTypeGroup: "Structured",
    craftType: "triangle",
    shape: "Triangle",
    craftConfidence: "high",
    craftSource: "shape_normalized",
    precision: "exact_coords",
    datePrecision: "exact_day",
    coordinateSource: "raw_latlong",
    country: "United States of America",
    analysisCountry: "United States of America",
    analysisMacroregion: "Northern America",
    analysisGeographyAssignmentSource: "pinned_country_polygon",
    analysisGeographyAssignmentConfidence: "inside_polygon",
    analysisGeographyBoundaryStatus: "inside_country",
    sortOrdinal: stats.ordinalFromCivil(2000, 6, 15),
    lat: 40,
    lon: -100,
    mapped: true,
    ...overrides,
  };
}

const decadeLocalGeographyRows = [
  ...Array.from({ length: 2 }, (_value, index) => row({
    eventId: `geo-1990-us-a-${index}`,
    source: "source-a",
    sortOrdinal: stats.ordinalFromCivil(1992, 6, index + 1),
  })),
  ...Array.from({ length: 2 }, (_value, index) => row({
    eventId: `geo-1990-ca-a-${index}`,
    source: "source-a",
    country: "Canada",
    analysisCountry: "Canada",
    analysisMacroregion: "Northern America",
    sortOrdinal: stats.ordinalFromCivil(1992, 7, index + 1),
  })),
  row({ eventId: "geo-1990-us-b", source: "source-b", sortOrdinal: stats.ordinalFromCivil(1992, 8, 1) }),
  row({
    eventId: "geo-1990-ca-b",
    source: "source-b",
    country: "Canada",
    analysisCountry: "Canada",
    analysisMacroregion: "Northern America",
    sortOrdinal: stats.ordinalFromCivil(1992, 8, 2),
  }),
  ...Array.from({ length: 3 }, (_value, index) => row({
    eventId: `geo-2000-us-a-${index}`,
    source: "source-a",
    sortOrdinal: stats.ordinalFromCivil(2002, 6, index + 1),
  })),
  row({
    eventId: "geo-2000-ca-a",
    source: "source-a",
    country: "Canada",
    analysisCountry: "Canada",
    analysisMacroregion: "Northern America",
    sortOrdinal: stats.ordinalFromCivil(2002, 7, 1),
  }),
  ...Array.from({ length: 4 }, (_value, index) => row({
    eventId: `geo-2000-ca-b-${index}`,
    source: "source-b",
    country: "Canada",
    analysisCountry: "Canada",
    analysisMacroregion: "Northern America",
    sortOrdinal: stats.ordinalFromCivil(2002, 8, index + 1),
  })),
];
const decadeLocalGeography = stats.computeAnalysis({
  rows: decadeLocalGeographyRows,
  baselineMode: "other_dates_matched",
  timeRangeStartOrdinal: stats.ordinalFromCivil(1990, 1, 1),
  timeRangeEndOrdinal: stats.ordinalFromCivil(2009, 12, 31),
  datasetHash: "decade-local-geography-fixture",
  selectedDomains: ["geography"],
});
const us2000Geography = decadeLocalGeography.geography.byTime.find((cell) => (
  cell.country === "United States of America" && cell.period === "2000"
));
assert.ok(us2000Geography, "the selected-decade country evidence is materialized");
assert.deepEqual(us2000Geography.sourceMix, [
  { source: "source-a", count: 3, share: 1 },
], "decade evidence never reuses the country's whole-corpus source mix");
assert.equal(us2000Geography.geographyAssignmentProvenance.assignmentSources[0].count, 3, "assignment provenance is decade-local");
assert.equal(us2000Geography.decadeFacetActiveN, 8);
assert.equal(us2000Geography.reportShare, 0.375);
assert.equal(us2000Geography.sourceBalancedReportShare, 0.375);
assert.equal(us2000Geography.preview.cohortSize, 3, "the country drawer uses the selected country-decade N");

const allTimeDecadeGeography = stats.computeAnalysis({
  rows: decadeLocalGeographyRows,
  baselineMode: "other_dates_matched",
  fullTimeRange: true,
  datasetHash: "all-time-decade-geography-fixture",
  selectedDomains: ["geography"],
});
const allTimeUs2000Geography = allTimeDecadeGeography.geography.byTime.find((cell) => (
  cell.country === "United States of America" && cell.period === "2000"
));
assert.ok(allTimeUs2000Geography, "All-Time geography retains populated country-decade structure");
assert.equal(allTimeDecadeGeography.comparisonState, stats.COMPARISON_STATES.WHOLE_CORPUS_STRUCTURE);
assert.equal(allTimeUs2000Geography.referenceCount, null, "All-Time country-decade evidence never fabricates a zero reference cohort");
assert.equal(allTimeUs2000Geography.referenceReportShare, null);
assert.equal(allTimeUs2000Geography.referenceSourceBalancedReportShare, null);
assert.equal(allTimeUs2000Geography.adjustedDifference, null, "a descriptive source-balanced share is never relabeled as an effect");
assert.equal(allTimeUs2000Geography.log2Enrichment, null);
assert.equal(allTimeUs2000Geography.sourceBalancedReportShare, 0.375);
assert.doesNotMatch(allTimeUs2000Geography.preview.comparison, /reference|vs\./i);

const rows = [];
for (let index = 0; index < 400; index += 1) {
  rows.push(row({
    eventId: `active-${index}`,
    source: index % 2 ? "source-b" : "source-a",
    craftType: index < 200 ? "triangle" : "disk",
    shape: index < 200 ? "Triangle" : "Disk",
    sortOrdinal: stats.ordinalFromCivil(2000, (index % 12) + 1, 15),
    lat: 35 + (index % 10),
    lon: -110 + (index % 20),
  }));
}
for (let index = 0; index < 400; index += 1) {
  rows.push(row({
    eventId: `reference-${index}`,
    source: index % 2 ? "source-b" : "source-a",
    craftType: index < 50 ? "triangle" : "disk",
    shape: index < 50 ? "Triangle" : "Disk",
    sortOrdinal: stats.ordinalFromCivil(1999, (index % 12) + 1, 15),
    lat: 35 + (index % 10),
    lon: -110 + (index % 20),
  }));
}

const analysisOptions = {
  rows,
  baselineMode: "other_dates_matched",
  timeRangeStartOrdinal: stats.ordinalFromCivil(2000, 1, 1),
  timeRangeEndOrdinal: stats.ordinalFromCivil(2000, 12, 31),
  datasetHash: "fixture-catalog-sha256",
  contextLayers: { cropCirclesEnabled: false, animalMutilationsEnabled: false },
};
const analysis = stats.computeAnalysis(analysisOptions);
assert.equal(analysis.schemaVersion, 2);
assert.equal(analysis.estimatorVersion, stats.ESTIMATOR_VERSION);
assert.equal(analysis.summary.activeCount, 400);
assert.equal(analysis.summary.referenceCount, 400);
assert.equal(analysis.baseline.disjoint, true);
assert.equal(analysis.baseline.label, "Other dates, balanced");
assert.equal(analysis.summary.missingCount, 0);

const quickOptions = {
  ...analysisOptions,
  analysisPhase: "quick",
  selectedDomains: ["overview", "time", "sources_quality", "context"],
};
const quickAnalysis = stats.computeAnalysis(quickOptions);
assert.equal(quickAnalysis.analysisPhase, "quick");
assert.equal(quickAnalysis.inferenceDeferred, true);
assert.deepEqual(quickAnalysis.inference, {
  status: "deferred",
  deferred: true,
  reason: "quick_core_inference_deferred",
  estimatorVersion: stats.ESTIMATOR_VERSION,
  comparisonState: stats.COMPARISON_STATES.INFERENTIAL,
});
assert.equal(quickAnalysis.summary.activeCount, analysis.summary.activeCount);
assert.equal(quickAnalysis.summary.referenceCount, analysis.summary.referenceCount);
assert.ok(quickAnalysis.time.series.length > 0, "quick core retains a useful descriptive time series");
assert.ok(quickAnalysis.sourcesQuality.sourceComposition.length > 0, "quick core retains source and quality diagnostics");
assert.equal(quickAnalysis.craft.status, "not_requested", "unrequested craft work is not constructed during quick core");
assert.equal(quickAnalysis.geography.status, "not_requested", "unrequested geography work is not constructed during quick core");
assert.equal(quickAnalysis.time.monthByCraft.metadata.status, "deferred", "association FDR is deferred during quick core");
assert.deepEqual(quickAnalysis.patterns, []);
assert.ok(Object.values(quickAnalysis.patternFamilies).every((family) => family.length === 0));
assert.equal(quickAnalysis.overview.evidenceSummary.length, 0);
assert.ok(Object.values(quickAnalysis.comparisons).every((family) => (
  family.results.length === 0 && family.metadata.inferenceDeferred === true && family.metadata.bootstrapReplicates === 0
)), "quick core cannot run or expose CMH/bootstrap/FDR comparison output");
assert.ok(quickAnalysis.overview.comparison.every((datum) => (
  datum.interval === null && datum.pValue === null && datum.qValue === null
)), "quick coverage descriptors emit no inferential intervals, p-values, or q-values");

function assertNoNonNullInference(value, path = "quickAnalysis") {
  if (!value || typeof value !== "object") return;
  if (Array.isArray(value)) {
    value.forEach((entry, index) => assertNoNonNullInference(entry, `${path}[${index}]`));
    return;
  }
  for (const [key, entry] of Object.entries(value)) {
    if (["interval", "oddsRatioInterval", "pValue", "qValue"].includes(key)) {
      assert.equal(entry, null, `${path}.${key} must be null while inference is deferred`);
    }
    assertNoNonNullInference(entry, `${path}.${key}`);
  }
}
assertNoNonNullInference(quickAnalysis);
assert.deepEqual(stats.computeAnalysis(quickOptions), quickAnalysis, "quick-core output is deterministic");
assert.deepEqual(
  stats.computeAnalysis({ ...quickOptions, analysisPhase: undefined, quickMode: true }),
  quickAnalysis,
  "the quickMode boolean and analysisPhase interface select the same deterministic staged result"
);
const fullAfterQuick = stats.computeAnalysis(analysisOptions);
assert.deepEqual(fullAfterQuick, analysis, "a quick-core request cannot mutate or alter the exact full-mode result");
assert.equal(fullAfterQuick.comparisons.geography.metadata.bootstrapReplicates, 999);
assert.deepEqual(fullAfterQuick.inference, {
  status: "complete",
  deferred: false,
  reason: "",
  estimatorVersion: stats.ESTIMATOR_VERSION,
  comparisonState: stats.COMPARISON_STATES.INFERENTIAL,
});
assert.equal(analysis.overview.active.sourceCoordinates, 400);
assert.equal(analysis.overview.active.generalizedCoordinates, 0);
assert.ok(analysis.overview.evidenceSummary.length > 0, "Overview exposes adjusted effects rather than only raw coverage counts");
assert.ok(analysis.overview.evidenceSummary.every((item) => (
  Number.isFinite(item.adjustedEffect) && item.interval && item.estimatorVersion === stats.ESTIMATOR_VERSION
)), "each evidence-summary mark carries an adjusted effect, uncertainty, and estimator identity");
assert.ok(analysis.overview.evidenceSummary.some((item) => item.family === "craft"));
assert.equal(analysis.geography.gridDefinition.geographyKind, "country");
assert.ok(analysis.geography.cells.some((cell) => cell.country === "United States of America"));
assert.ok(analysis.geography.cells.every((cell) => !String(cell.label).includes("ea6x12:")));
const unitedStatesCountryEvidence = analysis.geography.cells.find((cell) => cell.country === "United States of America");
assert.deepEqual(unitedStatesCountryEvidence.sourceMix, [
  { source: "source-a", count: 200, share: 0.5 },
  { source: "source-b", count: 200, share: 0.5 },
]);
assert.equal(unitedStatesCountryEvidence.sourceMixLabel, "source-a 50%, source-b 50%");
assert.equal(unitedStatesCountryEvidence.geographyAssignmentSource, "pinned_country_polygon");
assert.equal(unitedStatesCountryEvidence.geographyAssignmentConfidence, "inside_polygon");
assert.equal(unitedStatesCountryEvidence.geographyBoundaryStatus, "inside_country");
assert.equal(unitedStatesCountryEvidence.geographyUnknownStatus, "assigned_country");
assert.equal(unitedStatesCountryEvidence.macroregion, "Northern America");
assert.deepEqual(unitedStatesCountryEvidence.geographyAssignmentProvenance.assignmentSources, [
  { value: "pinned_country_polygon", count: 400, share: 1 },
]);
assert.ok(analysis.geography.byTime.every((cell) => Array.isArray(cell.sourceMix) && cell.geographyAssignmentProvenance), "country decade evidence retains source mix and pinned assignment provenance");
assert.ok(analysis.geography.byTime.length > 0, "country-by-decade evidence is available to the choropleth decade selector");
assert.ok(analysis.geography.byTime.every((cell) => cell.country && /^\d+$/.test(String(cell.period))), "country decades use human country names and numeric semantic periods");
assert.ok(Array.isArray(analysis.geography.craftByCountry.fullCells));
assert.ok(analysis.geography.craftByCountry.fullCells.some((cell) => cell.country === "United States of America" && cell.craft), "selected-craft country evidence is materialized with human geography labels");
assert.ok(analysis.geography.craftByCountry.fullCells.every((cell) => !/ea6x12:/i.test(String(cell.displayColumn))), "selected-craft country evidence never exposes canonical equal-area IDs");
assert.ok(Array.isArray(analysis.geography.equalAreaSensitivity), "equal-area bins remain an advanced sensitivity lane");
assert.ok(Array.isArray(analysis.geography.byEra.fullCells));
assert.deepEqual(
  analysis.geography.byEra.metadata.adjustmentCovariates,
  ["source", "coordinate_class", "craft"]
);
assert.match(analysis.geography.byEra.metadata.policyWarning, /geography-by-era/i);
assert.equal(analysis.geography.equalAreaMap.definition.id, "lambert_cylindrical_equal_area_6_by_12_v2");
assert.equal(analysis.geography.equalAreaMap.definition.latitudeBands, 6);
assert.equal(analysis.geography.equalAreaMap.definition.longitudeBands, 12);
assert.equal(analysis.geography.equalAreaMap.cells.length, 144, "two complete 6x12 coordinate facets are emitted");
assert.deepEqual(
  analysis.geography.equalAreaMap.facets.map((facet) => facet.coordinateClass),
  ["source_coordinates", "generalized_coordinates"]
);
const sourceCoordinateFacet = analysis.geography.equalAreaMap.byCoordinateClass.sourceCoordinates;
const generalizedCoordinateFacet = analysis.geography.equalAreaMap.byCoordinateClass.generalizedCoordinates;
assert.equal(sourceCoordinateFacet.cells.length, 72);
assert.equal(generalizedCoordinateFacet.cells.length, 72);
assert.equal(sourceCoordinateFacet.cells.reduce((sum, cell) => sum + cell.observed, 0), 400);
assert.equal(sourceCoordinateFacet.cells.reduce((sum, cell) => sum + cell.referenceCount, 0), 400);
assert.equal(generalizedCoordinateFacet.structurallyEmptyCells.length, 72);
assert.ok(sourceCoordinateFacet.qualifiedCells.every((cell) => (
  cell.estimatorVersion === stats.ESTIMATOR_VERSION &&
  Number.isFinite(cell.adjustedEffect) &&
  cell.gridMetadata.definitionId === analysis.geography.equalAreaMap.definition.id
)), "map coloring consumes engine-computed adjusted effects rather than UI-aggregated raw counts");
assert.ok(sourceCoordinateFacet.structurallyEmptyCells.every((cell) => (
  cell.displayStatus === "structurally_empty" && cell.suppressionReasons.includes("both_zero")
)));
assert.equal(analysis.comparisons.geography_map_6x12.metadata.fdrFamily, "all_nonempty_6x12_cells_across_coordinate_facets");
assert.deepEqual(
  analysis.craft.reportTypes.find((datum) => datum.key === "UFO").preview,
  { kind: "filter", patch: { types: ["UFO"] } }
);
assert.ok(analysis.time.decades.some((datum) => datum.decade === 2000 && datum.observed === 400));
assert.ok(Array.isArray(analysis.time.monthByCraft.fullCells));
assert.deepEqual(
  analysis.time.monthByCraft.metadata.adjustmentCovariates,
  ["source", "coarse_geography", "coordinate_class", "era"]
);
assert.match(analysis.time.monthByCraft.metadata.policyWarning, /month-by-craft/i);
assert.ok(analysis.time.monthByCraft.fullCells.every((cell) => (
  cell.row && cell.column && Number.isFinite(cell.expected) && Array.isArray(cell.suppressionReasons)
)), "month-by-craft emits qualified or explicitly suppressed statistical cells, never blank zero proxies");
assert.ok(Array.isArray(analysis.craft.byEra.fullCells));
assert.ok(Array.isArray(analysis.craft.byGeography.fullCells));
assert.deepEqual(
  analysis.craft.byGeography.metadata.adjustmentCovariates,
  ["source", "era", "coordinate_class"]
);
assert.ok(analysis.craft.byGeography.fullCells.every((cell) => cell.preview && cell.preview.kind), "craft-geography cells retain a local preview contract");
const mappedComparison = analysis.overview.comparison.find((datum) => datum.label === "Mapped reports");
assert.equal(mappedComparison.value, mappedComparison.observedShare - mappedComparison.referenceShare);
assert.equal(mappedComparison.reference, 0);
assert.equal(mappedComparison.interval.method, "newcombe_wilson");
assert.deepEqual(
  analysis.sourcesQuality.fieldAudit.find((datum) => datum.row === "Location precision" && datum.column === "exact_coords").preview,
  { kind: "filter", patch: { precisions: ["exact_coords"] } }
);
assert.equal(
  analysis.sourcesQuality.fieldAudit.find((datum) => datum.row === "Coordinate source" && datum.column === "raw_latlong").preview,
  undefined
);
assert.ok(analysis.sourcesQuality.classifierAudit.some((datum) => datum.row === "triangle" && datum.column === "Triangle"));
assert.match(analysis.sourcesQuality.classifierAuditPolicy, /neither axis is ground truth/i);
const active2000Composition = analysis.sourcesQuality.sourceByTime.filter((datum) => datum.column === "2000");
assert.equal(Math.round(active2000Composition.reduce((sum, datum) => sum + datum.value, 0) * 1e9) / 1e9, 1);
assert.deepEqual(active2000Composition[0].preview, {
  kind: "filter",
  patch: {
    sources: [active2000Composition[0].row],
    dateRange: {
      startOrdinal: stats.ordinalFromCivil(2000, 1, 1),
      endOrdinal: stats.ordinalFromCivil(2009, 12, 31),
    },
  },
});
assert.ok(analysis.time.series.some((datum) => datum.year === 2000 && datum.observed === 400));
assert.equal(analysis.time.sourceBalanced.find((datum) => datum.year === 2000).observed, 1);
assert.match(analysis.time.sourceBalancedPolicy, /equal total weight/i);
assert.deepEqual(
  analysis.time.series.find((datum) => datum.year === 2000).preview,
  {
    kind: "filter",
    patch: {
      dateRange: {
        startOrdinal: stats.ordinalFromCivil(2000, 1, 1),
        endOrdinal: stats.ordinalFromCivil(2000, 12, 31),
      },
    },
  }
);

const trianglePattern = analysis.patterns.find((pattern) => pattern.family === "craft" && pattern.key === "triangle");
assert.ok(trianglePattern, "strong craft shift should clear the guarded Pattern Finder gates");
assert.equal(trianglePattern.estimatorVersion, stats.ESTIMATOR_VERSION);
assert.equal(trianglePattern.commonSupportRate, 1);
assert.equal(trianglePattern.supportedActiveN, 400);
assert.equal(trianglePattern.supportedReferenceN, 400);
assert.equal(trianglePattern.interval.method, "deterministic_aggregated_stratum_bootstrap");
assert.equal(trianglePattern.interval.replicates, 999);
assert.ok(trianglePattern.oddsRatio > 1);
assert.ok(trianglePattern.regionStability && Number.isInteger(trianglePattern.regionStability.regionsTested));
assert.ok(["stable_multi_source_content", "source_or_region_sensitive"].includes(trianglePattern.findingLane));
assert.equal(trianglePattern.datasetHash, "fixture-catalog-sha256");
assert.ok(trianglePattern.qValue <= 0.05);
assert.ok(trianglePattern.cramersV >= 0.10);
assert.ok(trianglePattern.relativeEnrichment > 1);
assert.equal(Object.hasOwn(trianglePattern, "relativeRisk"), false);
assert.equal(Object.hasOwn(trianglePattern, "relativeRiskUnbounded"), false);
assert.equal(trianglePattern.missingness, 0);
assert.equal(trianglePattern.sourceStability.status, "stable_multi_source");
assert.equal(trianglePattern.sourceStability.passes, 2);
assert.equal(trianglePattern.sourceStability.exclusions.length, 2);
assert.ok(trianglePattern.sourceStability.exclusions.every((exclusion) => exclusion.passes && exclusion.activeN === 200));
assert.ok(analysis.patternGroups.stableMultiSource.some((pattern) => pattern.key === "triangle"));
assert.ok(analysis.patternGroups.sourceOrRegionSensitive.some((pattern) => pattern.key === "triangle"));
assert.equal(trianglePattern.exploratory, true);
assert.match(trianglePattern.policyLabel, /not evidence of cause/i);
assert.equal(trianglePattern.chartId, "analysis-craft-distribution");
assert.deepEqual(trianglePattern.preview, { kind: "filter", patch: { craftTypes: ["triangle"] } });
assert.ok(trianglePattern.title && trianglePattern.summary && trianglePattern.effectLabel && trianglePattern.intervalLabel);
for (const sourceExclusion of trianglePattern.sourceStability.exclusions) {
  const independentlyFiltered = stats.computeAnalysis({
    ...analysisOptions,
    rows: rows.filter((candidate) => candidate.source !== sourceExclusion.source),
  });
  const independentlyBalanced = independentlyFiltered.comparisons.craft.results.find((comparison) => comparison.key === "triangle");
  assert.equal(sourceExclusion.adjustedDifference, independentlyBalanced.adjustedDifference);
  assert.equal(sourceExclusion.oddsRatio, independentlyBalanced.oddsRatio);
  assert.equal(sourceExclusion.qValue, independentlyBalanced.qValue);
  assert.deepEqual(sourceExclusion.covariates, independentlyBalanced.covariates);
}
for (const regionExclusion of trianglePattern.regionStability.exclusions) {
  const independentlyFiltered = stats.computeAnalysis({
    ...analysisOptions,
    rows: rows.filter((candidate) => {
      const cell = stats.equalAreaGridCell(candidate.lat, candidate.lon);
      const region = cell ? `ea6x12:${Math.floor(cell.latIndex / 2)}:${Math.floor(cell.lonIndex / 2)}` : "unmapped";
      return region !== regionExclusion.region;
    }),
  });
  const independentlyBalanced = independentlyFiltered.comparisons.craft.results.find((comparison) => comparison.key === "triangle");
  assert.equal(regionExclusion.adjustedDifference, independentlyBalanced.adjustedDifference);
  assert.equal(regionExclusion.oddsRatio, independentlyBalanced.oddsRatio);
  assert.equal(regionExclusion.qValue, independentlyBalanced.qValue);
}
const triangleDistribution = analysis.craft.distribution.find((datum) => datum.key === "triangle");
assert.equal(triangleDistribution.estimatorVersion, stats.ESTIMATOR_VERSION);
assert.equal(triangleDistribution.inferenceEligible, true);
assert.equal(triangleDistribution.adjustedEffect, trianglePattern.adjustedEffect);
assert.equal(analysis.comparisons.craft.metadata.minimumCommonSupport, 0.8);
assert.equal(analysis.comparisons.craft.metadata.bootstrapReplicates, 999);
assert.ok(analysis.geography.heatmap.metadata.visibleCellCount > 0);

const repeated = stats.computeAnalysis(analysisOptions);
assert.deepEqual(repeated.patterns, analysis.patterns, "pattern output and within-family ranking must be deterministic");
let analysisRowScans = 0;
const singlePassAnalysis = stats.computeAnalysis({
  ...analysisOptions,
  rows: undefined,
  forEachRow(callback) {
    analysisRowScans += 1;
    rows.forEach(callback);
  },
});
assert.equal(analysisRowScans, 1, "source sensitivity must reuse first-pass aggregates instead of rescanning the catalog");
assert.deepEqual(singlePassAnalysis.patterns, analysis.patterns, "first-pass source aggregates must preserve deterministic Pattern Finder results");

const underpoweredExclusionRows = [];
for (const source of ["source-a", "source-b"]) {
  for (let index = 0; index < 100; index += 1) {
    underpoweredExclusionRows.push(row({
      eventId: `underpowered-active-${source}-${index}`,
      source,
      craftType: index < 60 ? "triangle" : "disk",
      shape: index < 60 ? "Triangle" : "Disk",
      sortOrdinal: stats.ordinalFromCivil(2000, 6, 15),
    }));
    underpoweredExclusionRows.push(row({
      eventId: `underpowered-reference-${source}-${index}`,
      source,
      craftType: index < 20 ? "triangle" : "disk",
      shape: index < 20 ? "Triangle" : "Disk",
      sortOrdinal: stats.ordinalFromCivil(1999, 6, 15),
    }));
  }
}
const underpoweredExclusionAnalysis = stats.computeAnalysis({
  rows: underpoweredExclusionRows,
  baselineMode: "other_dates_matched",
  timeRangeStartOrdinal: stats.ordinalFromCivil(2000, 1, 1),
  timeRangeEndOrdinal: stats.ordinalFromCivil(2000, 12, 31),
});
const underpoweredTrianglePattern = underpoweredExclusionAnalysis.patterns.find(
  (pattern) => pattern.family === "craft" && pattern.key === "triangle"
);
assert.ok(underpoweredTrianglePattern, "the full 200-report active cohort should clear the Pattern Finder gates");
assert.equal(underpoweredTrianglePattern.sourceStability.status, "source_sensitive");
assert.equal(underpoweredTrianglePattern.sourceStability.stable, false);
assert.equal(underpoweredTrianglePattern.sourceStability.passes, 0);
assert.equal(underpoweredTrianglePattern.sourceStability.exclusions.length, 2);
assert.ok(underpoweredTrianglePattern.sourceStability.exclusions.every((exclusion) => (
  exclusion.activeN === 100 && !exclusion.passes && exclusion.failedGates.includes("active_n")
)), "each leave-one-source-out cohort must independently satisfy the active N gate");

const activeSubstantiveSourceRows = [];
for (let index = 0; index < 190; index += 1) {
  activeSubstantiveSourceRows.push(row({
    eventId: `substantive-a-active-${index}`,
    source: "source-a",
    craftType: index < 150 ? "triangle" : "disk",
    sortOrdinal: stats.ordinalFromCivil(2000, 6, 15),
  }));
  activeSubstantiveSourceRows.push(row({
    eventId: `substantive-a-reference-${index}`,
    source: "source-a",
    craftType: index < 50 ? "triangle" : "disk",
    sortOrdinal: stats.ordinalFromCivil(1999, 6, 15),
  }));
}
for (let index = 0; index < 100; index += 1) {
  if (index < 10) {
    activeSubstantiveSourceRows.push(row({
      eventId: `substantive-b-active-${index}`,
      source: "source-b",
      craftType: "triangle",
      sortOrdinal: stats.ordinalFromCivil(2000, 6, 15),
    }));
  }
  activeSubstantiveSourceRows.push(row({
    eventId: `substantive-b-reference-${index}`,
    source: "source-b",
    craftType: index < 20 ? "triangle" : "disk",
    sortOrdinal: stats.ordinalFromCivil(1999, 6, 15),
  }));
}
const activeSubstantiveSourceAnalysis = stats.computeAnalysis({
  rows: activeSubstantiveSourceRows,
  baselineMode: "other_dates_balanced",
  timeRangeStartOrdinal: stats.ordinalFromCivil(2000, 1, 1),
  timeRangeEndOrdinal: stats.ordinalFromCivil(2000, 12, 31),
});
const activeSubstantiveTriangle = activeSubstantiveSourceAnalysis.patterns.find(
  (pattern) => pattern.family === "craft" && pattern.key === "triangle"
);
assert.ok(activeSubstantiveTriangle);
assert.equal(activeSubstantiveTriangle.sourceStability.status, "single_source_only");
assert.equal(activeSubstantiveTriangle.sourceStability.sourcesTested, 1);
assert.equal(
  activeSubstantiveTriangle.sourceStability.dominantSource,
  "source-a",
  "multi-source status requires two sources with at least 25 active-cohort reports; reference volume cannot qualify a source"
);

const fdrRows = [];
for (let index = 0; index < 60; index += 1) {
  fdrRows.push(row({ eventId: `fdr-active-focal-${index}`, craftType: "focal", sortOrdinal: stats.ordinalFromCivil(2000, 6, 15) }));
}
for (let index = 0; index < 40; index += 1) {
  fdrRows.push(row({ eventId: `fdr-reference-focal-${index}`, craftType: "focal", sortOrdinal: stats.ordinalFromCivil(1999, 6, 15) }));
}
for (let categoryIndex = 0; categoryIndex < 10; categoryIndex += 1) {
  for (let index = 0; index < 14; index += 1) {
    fdrRows.push(row({ eventId: `fdr-active-${categoryIndex}-${index}`, craftType: `minor-${categoryIndex}`, sortOrdinal: stats.ordinalFromCivil(2000, 6, 15) }));
  }
  for (let index = 0; index < 16; index += 1) {
    fdrRows.push(row({ eventId: `fdr-reference-${categoryIndex}-${index}`, craftType: `minor-${categoryIndex}`, sortOrdinal: stats.ordinalFromCivil(1999, 6, 15) }));
  }
}
const focalComparison = stats.proportionComparison(60, 200, 40, 200);
assert.ok(focalComparison.pValue < 0.05 && focalComparison.cramersV >= 0.10, "the focal category passes its individual inferential gates");
const fullCraftFamilyQ = stats.benjaminiHochberg([
  { pValue: focalComparison.pValue },
  ...Array.from({ length: 10 }, function () {
    return { pValue: stats.proportionComparison(14, 200, 16, 200).pValue };
  }),
])[0];
assert.ok(fullCraftFamilyQ > 0.05, "the full 11-category family correction must suppress the focal category");
const fdrAnalysis = stats.computeAnalysis({
  rows: fdrRows,
  baselineMode: "other_dates_matched",
  timeRangeStartOrdinal: stats.ordinalFromCivil(2000, 1, 1),
  timeRangeEndOrdinal: stats.ordinalFromCivil(2000, 12, 31),
});
const fdrCraftComparisons = fdrAnalysis.comparisons.craft.results;
const fdrEligibleCraftComparisons = fdrCraftComparisons.filter((comparison) => (
  comparison.inferenceEligible && comparison.pValue != null
));
const independentlyCorrectedEligibleQ = stats.benjaminiHochberg(fdrEligibleCraftComparisons);
assert.deepEqual(
  fdrEligibleCraftComparisons.map((comparison) => comparison.qValue),
  independentlyCorrectedEligibleQ.map((value) => Math.round(value * 1e12) / 1e12),
  "core-family BH uses only inference-eligible, actually tested comparisons"
);
assert.ok(fdrCraftComparisons.filter((comparison) => !comparison.inferenceEligible).every((comparison) => comparison.qValue === null));
assert.equal(
  fdrAnalysis.patternFamilies.craft.some((pattern) => pattern.key === "focal"),
  false,
  "BH must include hypotheses that later fail observed/effect/expected/V display gates"
);

const previous = stats.computeAnalysis({ ...analysisOptions, baselineMode: "previous_equal_duration" });
assert.equal(previous.summary.activeCount, 400);
assert.equal(previous.summary.referenceCount, 400);
assert.equal(previous.baseline.referenceRange.end, stats.ordinalFromCivil(1999, 12, 31));

const fullCatalog = stats.computeAnalysis({
  ...analysisOptions,
  baselineMode: "full_catalog",
  matchesNonDateFilters: (candidate) => candidate.source === "source-a",
});
assert.equal(fullCatalog.summary.activeCount, 200);
assert.equal(fullCatalog.summary.referenceCount, 800, "descriptive full-catalog baseline intentionally ignores active filters");
assert.equal(fullCatalog.baseline.descriptive, true);
assert.equal(fullCatalog.patterns.length, 0, "overlapping descriptive baseline must not emit inferential patterns");
assert.ok(fullCatalog.comparisons.craft.results.every((comparison) => (
  comparison.pValue === null && comparison.qValue === null && comparison.suppressionReasons.includes("descriptive_baseline")
)), "overlapping full-catalog comparisons remain descriptive and emit no inferential significance values");

const fullCatalogSelfComparison = stats.computeAnalysis({
  rows: [
    row({ eventId: "self-comparison-a", sortOrdinal: stats.ordinalFromCivil(2000, 2, 1) }),
    row({ eventId: "self-comparison-b", sortOrdinal: stats.ordinalFromCivil(2000, 9, 1) }),
  ],
  baselineMode: "full_catalog",
  timeRangeStartOrdinal: stats.ordinalFromCivil(1999, 1, 1),
  timeRangeEndOrdinal: stats.ordinalFromCivil(2001, 12, 31),
});
assert.equal(fullCatalogSelfComparison.analysisMode, stats.ANALYSIS_MODES.COHORT_COMPARISON);
assert.equal(
  fullCatalogSelfComparison.comparisonState,
  stats.COMPARISON_STATES.UNAVAILABLE_SELF_COMPARISON,
  "a finite range that contains every matched row collapses a duplicate full-catalog self-comparison"
);
assert.equal(fullCatalogSelfComparison.summary.activeCount, fullCatalogSelfComparison.summary.referenceCount);

const noSourceSupportRows = [];
for (let index = 0; index < 200; index += 1) {
  noSourceSupportRows.push(row({
    eventId: `no-support-active-${index}`,
    source: "active-only-source",
    craftType: index < 150 ? "triangle" : "disk",
    sortOrdinal: stats.ordinalFromCivil(2000, 6, 15),
  }));
  noSourceSupportRows.push(row({
    eventId: `no-support-reference-${index}`,
    source: "reference-only-source",
    craftType: index < 50 ? "triangle" : "disk",
    sortOrdinal: stats.ordinalFromCivil(1999, 6, 15),
  }));
}
const noSourceSupport = stats.computeAnalysis({
  rows: noSourceSupportRows,
  baselineMode: "other_dates_matched",
  timeRangeStartOrdinal: stats.ordinalFromCivil(2000, 1, 1),
  timeRangeEndOrdinal: stats.ordinalFromCivil(2000, 12, 31),
});
const unsupportedTriangle = noSourceSupport.craft.distribution.find((datum) => datum.key === "triangle");
assert.equal(unsupportedTriangle.commonSupportRate, 0);
assert.equal(unsupportedTriangle.inferenceEligible, false);
assert.ok(unsupportedTriangle.suppressionReasons.includes("no_common_support"));
assert.ok(
  Object.values(noSourceSupport.comparisons).every((family) => family.results.every((comparison) => (
    comparison.inferenceEligible || comparison.qValue === null
  ))),
  "untested core and equal-area comparisons retain q=null rather than entering BH as p=1"
);
assert.equal(
  noSourceSupport.patterns.some((pattern) => pattern.family === "craft"),
  false,
  "content findings fail closed when their balancing strata have no common support"
);
assert.ok(
  noSourceSupport.patternGroups.collectionAndQuality.every((pattern) => pattern.family === "source"),
  "a source-composition shift is kept in the collection-quality lane rather than promoted as content evidence"
);

const missing = row({
  eventId: "missing",
  source: "",
  craftType: "unknown",
  craftConfidence: "none",
  shape: "",
  sortOrdinal: null,
  lat: "",
  lon: null,
  mapped: false,
  coordinateSource: "unresolved",
});
const boundedWithUndated = stats.computeAnalysis({
  rows: [row({ eventId: "active-dated" }), row({ eventId: "reference-dated", sortOrdinal: stats.ordinalFromCivil(1999, 6, 15) }), missing],
  baselineMode: "other_dates_matched",
  timeRangeStartOrdinal: stats.ordinalFromCivil(2000, 1, 1),
  timeRangeEndOrdinal: stats.ordinalFromCivil(2000, 12, 31),
});
assert.equal(boundedWithUndated.summary.activeCount, 1);
assert.equal(boundedWithUndated.summary.referenceCount, 1, "undated rows are not smuggled into an other-dates baseline");
const allTime = stats.computeAnalysis({
  rows: rows.concat([missing]),
  baselineMode: "other_dates_matched",
  timeRangeMode: "full",
  timeRangeStartOrdinal: stats.ordinalFromCivil(1999, 1, 1),
  timeRangeEndOrdinal: stats.ordinalFromCivil(2000, 12, 31),
  datasetHash: "fixture-catalog-sha256",
});
assert.equal(allTime.summary.activeCount, 801, "All Time includes filtered undated rows");
assert.equal(allTime.summary.referenceCount, 0, "Other dates is empty and disjoint when All Time is active");
assert.equal(allTime.analysisMode, stats.ANALYSIS_MODES.WHOLE_CORPUS_STRUCTURE);
assert.equal(allTime.comparisonState, stats.COMPARISON_STATES.WHOLE_CORPUS_STRUCTURE);
assert.equal(allTime.baseline.mode, stats.BASELINE_MODES.INTERNAL_STRUCTURE);
assert.equal(allTime.baseline.label, "All records — internal structure");
assert.ok(allTime.time.series.length > 0 && allTime.time.series.every((datum) => datum.referenceCount === 0));
assert.deepEqual(
  allTime.time.series.map((datum) => datum.startYear),
  allTime.time.series.map((datum) => datum.startYear).slice().sort((left, right) => left - right),
  "the single All Time activity series is chronological before any UI sampling"
);
assert.ok(allTime.time.monthByCraft.fullCells.some((cell) => cell.estimateAvailable && cell.expectedCount > 0));
assert.ok(allTime.craft.byEra.fullCells.some((cell) => cell.estimateAvailable && cell.expectedCount > 0));
assert.ok(allTime.craft.byGeography.fullCells.some((cell) => cell.estimateAvailable && cell.expectedCount > 0));
assert.ok(allTime.geography.byEra.fullCells.some((cell) => cell.estimateAvailable && cell.expectedCount > 0));
assert.ok(
  allTime.geography.equalAreaMap.cells.some((cell) => cell.observed > 0 && cell.displayStatus === "descriptive"),
  "whole-corpus geography exposes source-balanced descriptive estimates without inventing a reference"
);
const classifierObservedZero = allTime.sourcesQuality.classifierAudit.find((cell) => (
  cell.observedCount === 0 && cell.expectedCount > 0
));
assert.ok(classifierObservedZero, "the classifier audit materializes zero-observation cells with positive expectation");
assert.equal(classifierObservedZero.tested, true);
assert.equal(classifierObservedZero.pValue != null, true);
assert.ok(allTime.sourcesQuality.classifierAuditMetadata.cramersV >= 0 && allTime.sourcesQuality.classifierAuditMetadata.cramersV <= 1);
assert.equal(allTime.summary.missingCount, 1, "missingCount is a row union, not a sum that can exceed N");
assert.deepEqual(allTime.summary.missingnessPolicy.requiredFields, [
  "known date ordinal",
  "mapped point",
  "known craft classification",
  "known source",
]);
assert.equal(
  allTime.sourcesQuality.missingness.find((datum) => datum.label === "Any required analysis field").count,
  1
);
assert.equal(allTime.overview.active.unmapped, 1, "blank coordinates remain unmapped rather than becoming 0,0");

const previewMissingnessAnalysis = stats.computeAnalysis({
  rows: [
    row({ eventId: "preview-clean-1", source: "clean-source" }),
    row({ eventId: "preview-clean-2", source: "clean-source" }),
    row({ eventId: "preview-mixed-1", source: "mixed-source" }),
    row({
      eventId: "preview-mixed-2",
      source: "mixed-source",
      craftType: "unknown",
      mapped: false,
      lat: null,
      lon: null,
    }),
  ],
  baselineMode: "other_dates_matched",
  timeRangeMode: "full",
});
const cleanSourcePreview = previewMissingnessAnalysis.sourcesQuality.sourceComposition.find((datum) => datum.key === "clean-source");
const mixedSourcePreview = previewMissingnessAnalysis.sourcesQuality.sourceComposition.find((datum) => datum.key === "mixed-source");
assert.equal(cleanSourcePreview.count, 2);
assert.equal(cleanSourcePreview.missingCount, 0);
assert.equal(cleanSourcePreview.missingness, 0);
assert.equal(mixedSourcePreview.count, 2);
assert.equal(mixedSourcePreview.missingCount, 1);
assert.equal(mixedSourcePreview.missingness, 0.5, "preview missingness must use the selected cohort, not the whole active cohort");
assert.match(mixedSourcePreview.missingnessUnit, /within this preview cohort/i);

const coordinateClasses = stats.computeAnalysis({
  rows: [
    row({ eventId: "source-exact", coordinateSource: "raw_latlong", precision: "exact_coords" }),
    row({ eventId: "geocoded-exact", coordinateSource: "geocoded", precision: "exact_coords" }),
    row({ eventId: "source-city", coordinateSource: "raw_latlong", precision: "city" }),
    row({ eventId: "blank", coordinateSource: "unresolved", precision: "unknown", lat: null, lon: "", mapped: false }),
  ],
  baselineMode: "full_catalog",
  timeRangeMode: "full",
});
assert.equal(coordinateClasses.overview.active.sourceCoordinates, 1);
assert.equal(coordinateClasses.overview.active.generalizedCoordinates, 2);
assert.equal(coordinateClasses.overview.active.unmapped, 1);
assert.deepEqual(
  new Set(coordinateClasses.geography.cells.map((cell) => cell.coordinateClass)),
  new Set(["source_coordinates", "generalized_coordinates"])
);
assert.ok(coordinateClasses.geography.cells.every((cell) => !cell.key.includes("unmapped")));

const sparseMapAnalysis = stats.computeAnalysis({
  rows: [
    row({ eventId: "sparse-map-active", sortOrdinal: stats.ordinalFromCivil(2000, 6, 15), lat: 10, lon: 10 }),
    row({ eventId: "sparse-map-reference", sortOrdinal: stats.ordinalFromCivil(1999, 6, 15), lat: 10, lon: 10 }),
  ],
  baselineMode: "other_dates_matched",
  timeRangeStartOrdinal: stats.ordinalFromCivil(2000, 1, 1),
  timeRangeEndOrdinal: stats.ordinalFromCivil(2000, 12, 31),
});
const sparseMapOccupiedCell = sparseMapAnalysis.geography.equalAreaMap.byCoordinateClass.sourceCoordinates.cells.find(
  (cell) => cell.observed === 1 && cell.referenceCount === 1
);
assert.ok(sparseMapOccupiedCell);
assert.equal(sparseMapOccupiedCell.displayStatus, "low_support");
assert.equal(sparseMapOccupiedCell.estimateAvailable, true);
assert.ok(sparseMapOccupiedCell.suppressionReasons.includes("expected_cell"));
assert.equal(
  sparseMapAnalysis.geography.equalAreaMap.byCoordinateClass.sourceCoordinates.structurallyEmptyCells.length,
  71
);

const outputConformance = stats.computeAnalysis({
  rows: [
    row({
      eventId: "conformance-active-triangle",
      source: "source-a",
      craftType: "triangle",
      shape: "Triangle",
      sortOrdinal: stats.ordinalFromCivil(2000, 6, 15),
      lat: 10,
      lon: 10,
      coordinateSource: "raw_latlong",
      precision: "exact_coords",
    }),
    row({
      eventId: "conformance-active-disk",
      source: "source-a",
      craftType: "disk",
      shape: "Disk",
      sortOrdinal: stats.ordinalFromCivil(2000, 6, 15),
      lat: 10,
      lon: 10,
      coordinateSource: "raw_latlong",
      precision: "exact_coords",
    }),
    row({
      eventId: "conformance-reference-triangle",
      source: "source-b",
      craftType: "triangle",
      shape: "Triangle",
      sortOrdinal: stats.ordinalFromCivil(1990, 6, 15),
      lat: -30,
      lon: 100,
      coordinateSource: "geocoded",
      precision: "exact_coords",
    }),
    row({
      eventId: "conformance-reference-disk",
      source: "source-b",
      craftType: "disk",
      shape: "Disk",
      sortOrdinal: stats.ordinalFromCivil(1990, 6, 15),
      lat: -30,
      lon: 100,
      coordinateSource: "geocoded",
      precision: "exact_coords",
    }),
  ],
  baselineMode: "other_dates_matched",
  timeRangeStartOrdinal: stats.ordinalFromCivil(2000, 1, 1),
  timeRangeEndOrdinal: stats.ordinalFromCivil(2000, 12, 31),
  contextLayers: { cropCirclesEnabled: false, animalMutilationsEnabled: false },
});
assert.ok(outputConformance.craft.trends.every((series) => (
  Array.isArray(series.points) && series.points.every((point) => point.craft === series.craft && point.cohort === series.cohort)
)), "each trend line must contain exactly one craft and one cohort");
const activeTriangleTrend = outputConformance.craft.trends.find((series) => series.craft === "triangle" && series.cohort === "active");
const referenceTriangleTrend = outputConformance.craft.trends.find((series) => series.craft === "triangle" && series.cohort === "reference");
assert.ok(activeTriangleTrend && referenceTriangleTrend);
assert.equal(activeTriangleTrend.points.find((point) => point.column === "1990").value, 0, "reference-only craft cells remain in the active series as zeroes");
assert.equal(activeTriangleTrend.points.find((point) => point.column === "1990").referenceCount, 1);
assert.equal(referenceTriangleTrend.points.find((point) => point.column === "2000").value, 0, "active-only craft cells remain in the reference series as zeroes");
assert.equal(referenceTriangleTrend.points.find((point) => point.column === "2000").activeCount, 1);

assert.ok(outputConformance.geography.byTime.some((datum) => datum.observed === 0 && datum.referenceCount === 2), "reference-only geography-time cells must be emitted");
assert.ok(outputConformance.geography.byTime.some((datum) => datum.observed === 2 && datum.referenceCount === 0), "active-only geography-time cells must be emitted");
assert.ok(outputConformance.geography.byTime.every((datum) => (
  datum.coordinateClass &&
  datum.country &&
  datum.label.includes(datum.column) &&
  datum.preview?.kind === "area" &&
  datum.preview.area.type === "country" &&
  datum.preview.area.country === datum.country
)), "every geography-time datum must be independently interpretable and country-selectable");

assert.equal(outputConformance.sourcesQuality.sourceByTime.length, 4, "source-by-period composition exposes the complete source-period grid");
const zeroSourcePeriod = outputConformance.sourcesQuality.sourceByTime.find((datum) => datum.source === "source-b" && datum.period === "2000");
assert.ok(zeroSourcePeriod);
assert.equal(zeroSourcePeriod.activeCount, 0);
assert.equal(zeroSourcePeriod.referenceCount, 0);
assert.equal(zeroSourcePeriod.compositionBasis, "within_period_100_percent");
assert.equal(
  outputConformance.sourcesQuality.sourceByTime.filter((datum) => datum.period === "2000").reduce((sum, datum) => sum + datum.activeShare, 0),
  1
);
assert.equal(
  outputConformance.sourcesQuality.sourceByTime.filter((datum) => datum.period === "1990").reduce((sum, datum) => sum + datum.referenceShare, 0),
  1
);
const activeSourcePeriod = outputConformance.sourcesQuality.sourceByTime.find((datum) => datum.source === "source-a" && datum.period === "2000");
assert.equal(activeSourcePeriod.absoluteCount, 2);
assert.equal(activeSourcePeriod.activePeriodTotal, 2);

function craftSourceRows(counts, prefix) {
  const result = [];
  Object.entries(counts).forEach(([pair, count]) => {
    const [craftType, source] = pair.split("|");
    for (let index = 0; index < count; index += 1) {
      result.push(row({ eventId: `${prefix}-${craftType}-${source}-${index}`, craftType, source }));
    }
  });
  return result;
}

const eligibleCraftSource = stats.computeAnalysis({
  rows: craftSourceRows({ "disk|source-a": 50, "disk|source-b": 10, "triangle|source-a": 10, "triangle|source-b": 50 }, "eligible"),
  baselineMode: "full_catalog",
  timeRangeMode: "full",
});
assert.equal(eligibleCraftSource.craft.sourceAssociation.eligible, true);
assert.ok(eligibleCraftSource.craft.sourceAssociation.minimumExpectedCell >= 10);
assert.ok(eligibleCraftSource.craft.sourceAssociation.cramersV >= 0.10);
assert.match(eligibleCraftSource.craft.sourceAssociation.policyWarning, /every estimable cell is displayed/i);
assert.equal(eligibleCraftSource.craft.residuals.length, 4);
assert.ok(eligibleCraftSource.craft.residuals.every((cell) => cell.expected >= 10));

const weakCraftSource = stats.computeAnalysis({
  rows: craftSourceRows({ "disk|source-a": 30, "disk|source-b": 30, "triangle|source-a": 30, "triangle|source-b": 30 }, "weak"),
  baselineMode: "full_catalog",
  timeRangeMode: "full",
});
assert.equal(weakCraftSource.craft.sourceAssociation.eligible, true);
assert.ok(weakCraftSource.craft.sourceAssociation.minimumExpectedCell >= 10);
assert.ok(weakCraftSource.craft.sourceAssociation.cramersV < 0.10);
assert.equal(weakCraftSource.craft.sourceAssociation.associationConclusion, "no_material_association_detected");
assert.equal(weakCraftSource.craft.residuals.length, 4, "a supported negative result remains visible");

const sparseCraftSource = stats.computeAnalysis({
  rows: craftSourceRows({ "disk|source-a": 8, "disk|source-b": 2, "triangle|source-a": 2, "triangle|source-b": 8 }, "sparse"),
  baselineMode: "full_catalog",
  timeRangeMode: "full",
});
assert.equal(sparseCraftSource.craft.sourceAssociation.eligible, true);
assert.ok(sparseCraftSource.craft.sourceAssociation.minimumExpectedCell < 10);
assert.ok(sparseCraftSource.craft.sourceAssociation.cramersV >= 0.10);
assert.equal(sparseCraftSource.craft.residuals.length, 4);
assert.ok(sparseCraftSource.craft.residuals.every((cell) => cell.lowSupport && cell.qValue === null));

const burstRows = [];
for (let year = 1990; year <= 1995; year += 1) {
  for (let index = 0; index < 20; index += 1) {
    burstRows.push(row({ eventId: `steady-${year}-${index}`, sortOrdinal: stats.ordinalFromCivil(year, 6, 15) }));
  }
}
for (let index = 0; index < 100; index += 1) {
  burstRows.push(row({ eventId: `burst-1996-${index}`, sortOrdinal: stats.ordinalFromCivil(1996, 6, 15) }));
}
const burstAnalysis = stats.computeAnalysis({
  rows: burstRows,
  baselineMode: "full_catalog",
  timeRangeStartOrdinal: stats.ordinalFromCivil(1990, 1, 1),
  timeRangeEndOrdinal: stats.ordinalFromCivil(1996, 12, 31),
});
assert.equal(burstAnalysis.time.bursts.length, 1);
assert.equal(burstAnalysis.time.bursts[0].year, 1996);
assert.equal(burstAnalysis.time.bursts[0].baselineMean, 20);
assert.match(burstAnalysis.time.bursts[0].policyLabel, /not a causal or incidence claim/i);

const normalizedContext = stats.normalizeContextProjections({
  manifest: {
    artifacts: {
      cropCircles: { sha256: "manifest-crop-hash" },
      animalReports: { sha256: "manifest-animal-hash" },
    },
    codes: {
      datePrecision: ["unknown", "year"],
      coordinateClass: ["unknown", "source_coordinates"],
      morphologyFamily: ["unknown", "circular"],
      complexityTier: ["unknown", "complex"],
      speciesGroup: ["unknown", "cattle"],
      status: ["unknown", "reviewed"],
    },
    dictionaries: { country: ["unknown", "GB"], cropType: ["unknown", "wheat"] },
  },
  cropCircles: { rows: [[
    "crop", 1999, 2000, 1, 1, 1, [1], [1], 1, true, true, true,
    stats.ordinalFromCivil(1999, 1, 1), stats.ordinalFromCivil(2000, 12, 31),
  ]] },
  animalReports: { rows: [
    ["animal", 2000, 2000, 1, [1], false, 1, stats.ordinalFromCivil(2000, 1, 1), stats.ordinalFromCivil(2000, 12, 31)],
    ["animal-undated", null, null, 0, [1], false, 1, null, null],
  ] },
});
assert.equal(normalizedContext.cropCircles[0].startOrdinal, stats.ordinalFromCivil(1999, 1, 1));
assert.equal(normalizedContext.animalReports[0].endOrdinal, stats.ordinalFromCivil(2000, 12, 31));
const contextAnalysis = stats.computeAnalysis({
  ...analysisOptions,
  contextLayers: { cropCirclesEnabled: true, animalMutilationsEnabled: true },
  contextReleaseHashes: { cropCircles: "crop-release-hash", animalReports: "animal-release-hash" },
  contextProjections: normalizedContext,
});
assert.equal(contextAnalysis.context.crops.status, "ready");
assert.equal(contextAnalysis.context.crops.datasetHash, "manifest-crop-hash");
assert.equal(contextAnalysis.context.crops.activeCount, 1);
assert.equal(contextAnalysis.context.crops.referenceCount, 0);
assert.equal(contextAnalysis.context.crops.summary.unitLabel, "crop-circle records");
assert.equal(contextAnalysis.context.crops.summary.mappedCount, 1);
assert.equal(contextAnalysis.context.crops.morphology[0].label, "circular");
assert.equal(contextAnalysis.context.crops.coordinateClass[0].label, "source_coordinates");
assert.equal(contextAnalysis.context.crops.coverage.find((datum) => datum.label === "Narrative available").count, 1);
assert.equal(contextAnalysis.context.animals.species[0].label, "cattle");
assert.equal(contextAnalysis.context.animals.datasetHash, "manifest-animal-hash");
assert.equal(contextAnalysis.context.animals.summary.unitLabel, "animal reports");
assert.equal(contextAnalysis.context.animals.summary.unmappedCount, 1);
assert.equal(contextAnalysis.context.animals.datePrecision[0].label, "year");
assert.match(contextAnalysis.context.animals.policyWarning, /no cause or cross-domain association/i);

const multiLabelContext = stats.normalizeContextProjections({
  cropCircles: [
    {
      id: "multi-crop-a",
      year: 2000,
      datePrecision: "exact_day",
      morphology: ["circular", "linear", "circular"],
      crop: "wheat",
      mapped: true,
      startOrdinal: stats.ordinalFromCivil(2000, 6, 1),
      endOrdinal: stats.ordinalFromCivil(2000, 6, 1),
    },
    {
      id: "multi-crop-b",
      year: 2000,
      datePrecision: "exact_day",
      morphology: ["circular"],
      crop: "wheat",
      mapped: false,
      startOrdinal: stats.ordinalFromCivil(2000, 7, 1),
      endOrdinal: stats.ordinalFromCivil(2000, 7, 1),
    },
  ],
  animalReports: [
    {
      id: "multi-animal-a",
      year: 2000,
      datePrecision: "exact_day",
      species: ["cattle", "deer", "cattle"],
      status: "reviewed",
      mapped: true,
      startOrdinal: stats.ordinalFromCivil(2000, 6, 2),
      endOrdinal: stats.ordinalFromCivil(2000, 6, 2),
    },
    {
      id: "multi-animal-b",
      year: 2000,
      datePrecision: "exact_day",
      species: ["cattle"],
      status: "reviewed",
      mapped: false,
      startOrdinal: stats.ordinalFromCivil(2000, 7, 2),
      endOrdinal: stats.ordinalFromCivil(2000, 7, 2),
    },
  ],
});
const multiLabelAnalysis = stats.computeAnalysis({
  rows: [],
  baselineMode: "other_dates_matched",
  timeRangeMode: "full",
  contextLayers: { cropCirclesEnabled: true, animalMutilationsEnabled: true },
  contextProjections: multiLabelContext,
});
assert.equal(multiLabelAnalysis.context.crops.activeCount, 2);
assert.equal(multiLabelAnalysis.context.crops.morphologyMembership.activeMembershipCount, 3);
assert.equal(multiLabelAnalysis.context.crops.morphologyMembership.activeReportCount, 2);
assert.equal(multiLabelAnalysis.context.crops.morphologyMembership.totalsMayExceedReportN, true);
assert.match(multiLabelAnalysis.context.crops.morphologyMembershipPolicy, /may exceed crop-circle report N/i);
assert.match(multiLabelAnalysis.context.crops.policyWarning, /may exceed crop-circle report N/i);
assert.equal(multiLabelAnalysis.context.crops.morphology.reduce((sum, datum) => sum + datum.count, 0), 3);
assert.ok(multiLabelAnalysis.context.crops.morphology.every((datum) => datum.membershipUnit && datum.membershipPolicy));
assert.equal(multiLabelAnalysis.context.animals.activeCount, 2);
assert.equal(multiLabelAnalysis.context.animals.speciesMembership.activeMembershipCount, 3);
assert.equal(multiLabelAnalysis.context.animals.speciesMembership.activeReportCount, 2);
assert.equal(multiLabelAnalysis.context.animals.speciesMembership.totalsMayExceedReportN, true);
assert.match(multiLabelAnalysis.context.animals.speciesMembershipPolicy, /may exceed animal report N/i);
assert.match(multiLabelAnalysis.context.animals.policyWarning, /may exceed animal report N/i);
assert.equal(multiLabelAnalysis.context.animals.species.reduce((sum, datum) => sum + datum.count, 0), 3);
assert.ok(multiLabelAnalysis.context.animals.species.every((datum) => datum.membershipUnit && datum.membershipPolicy));

const fullTimeContext = stats.computeAnalysis({
  ...analysisOptions,
  timeRangeMode: "full",
  contextLayers: { cropCirclesEnabled: true, animalMutilationsEnabled: true },
  contextProjections: normalizedContext,
});
assert.equal(fullTimeContext.context.animals.activeCount, 2, "full-time context includes undated projection rows");
assert.equal(fullTimeContext.context.animals.referenceCount, 0);
assert.equal(fullTimeContext.context.animals.summary.missingCount, 1);

const sameYearContext = stats.normalizeContextProjections({
  manifest: {
    codes: {
      datePrecision: ["exact_day", "year"],
      coordinateClass: ["exact"],
      morphologyFamily: ["circular"],
      complexityTier: ["simple"],
      speciesGroup: ["bovine"],
      status: ["reported_unreviewed"],
    },
    dictionaries: { country: ["US"], cropType: ["wheat"] },
  },
  cropCircles: { rows: [
    ["crop-active", 2000, 2000, 0, 0, 0, [0], [0], 0, true, true, false, stats.ordinalFromCivil(2000, 8, 15), stats.ordinalFromCivil(2000, 8, 15)],
    ["crop-reference", 2000, 2000, 0, 0, 0, [0], [0], 0, true, true, false, stats.ordinalFromCivil(2000, 7, 15), stats.ordinalFromCivil(2000, 7, 15)],
    ["crop-year-uncertain", 2000, 2000, 1, 0, 0, [0], [0], 0, true, true, false, stats.ordinalFromCivil(2000, 1, 1), stats.ordinalFromCivil(2000, 12, 31)],
  ] },
  animalReports: { rows: [
    ["animal-active", 2000, 2000, 0, [0], false, 0, stats.ordinalFromCivil(2000, 8, 20), stats.ordinalFromCivil(2000, 8, 20)],
    ["animal-reference", 2000, 2000, 0, [0], false, 0, stats.ordinalFromCivil(2000, 7, 20), stats.ordinalFromCivil(2000, 7, 20)],
    ["animal-year-uncertain", 2000, 2000, 1, [0], false, 0, stats.ordinalFromCivil(2000, 1, 1), stats.ordinalFromCivil(2000, 12, 31)],
  ] },
});
const sameYearPrevious = stats.computeAnalysis({
  rows: [],
  baselineMode: "previous_equal_duration",
  timeRangeStartOrdinal: stats.ordinalFromCivil(2000, 8, 1),
  timeRangeEndOrdinal: stats.ordinalFromCivil(2000, 8, 31),
  contextLayers: { cropCirclesEnabled: true, animalMutilationsEnabled: true },
  contextProjections: sameYearContext,
});
assert.equal(sameYearPrevious.context.crops.activeCount, 2);
assert.equal(sameYearPrevious.context.crops.referenceCount, 1);
assert.ok(sameYearPrevious.context.crops.activeCount + sameYearPrevious.context.crops.referenceCount <= 3);
assert.equal(sameYearPrevious.context.animals.activeCount, 2);
assert.equal(sameYearPrevious.context.animals.referenceCount, 1);
assert.ok(sameYearPrevious.context.animals.activeCount + sameYearPrevious.context.animals.referenceCount <= 3);
assert.match(sameYearPrevious.context.crops.policyWarning, /excluded from disjoint references/i);

const funnelAnalysis = stats.computeAnalysis({
  rows: [
    row({ eventId: "funnel-undated", sortOrdinal: null, sameDayMatchStrength: "strong" }),
    row({ eventId: "funnel-unmapped", mapped: false, lat: null, lon: null, sameDayMatchStrength: "strong" }),
    row({ eventId: "funnel-generalized", coordinateSource: "geocoded", sameDayMatchStrength: "strong" }),
    row({ eventId: "funnel-weak-same-day", sameDayMatchStrength: "weak" }),
    row({ eventId: "funnel-eligible", sameDayMatchStrength: "strong", coordinatePileCount: 1 }),
  ],
  baselineMode: "full_catalog",
  timeRangeMode: "full",
});
assert.deepEqual(
  funnelAnalysis.overview.eligibilityFunnel.map((stage) => stage.count),
  [5, 4, 3, 2, 1]
);
assert.ok(funnelAnalysis.overview.eligibilityFunnel.every((stage, index, stages) => (
  stage.denominator === 5 &&
  stage.excludedCount === 5 - stage.count &&
  (index === 0 || stage.count <= stages[index - 1].count)
)), "eligibility stages are a deterministic nested attrition funnel with an explicit matched-cohort denominator");
assert.notDeepEqual(
  funnelAnalysis.overview.eligibilityFunnel.map((stage) => stage.label),
  funnelAnalysis.overview.coverage.map((stage) => stage.label),
  "the nested eligibility funnel remains distinct from complementary descriptive coverage"
);

const longSpanRows = [1801, 1850, 1955, 2020].map((year, index) => row({
  eventId: `long-span-${index}`,
  sortOrdinal: stats.ordinalFromCivil(year, 6, 15),
}));
const longSpanAnalysis = stats.computeAnalysis({
  rows: longSpanRows,
  baselineMode: "full_catalog",
  timeRangeMode: "full",
});
assert.equal(longSpanAnalysis.time.adaptiveBinning.unit, "decade");
assert.equal(longSpanAnalysis.time.adaptiveBinning.widthYears, 10);
assert.equal(
  longSpanAnalysis.time.series.reduce((sum, bin) => sum + bin.observed, 0),
  longSpanAnalysis.summary.activeCount,
  "adaptive time bins preserve every dated active report across a long sparse span"
);
assert.equal(
  longSpanAnalysis.time.series.reduce((sum, bin) => sum + bin.referenceCount, 0),
  longSpanAnalysis.summary.referenceCount,
  "adaptive time bins preserve every dated reference report across a long sparse span"
);
assert.equal(longSpanAnalysis.time.annualSeries.reduce((sum, year) => sum + year.observed, 0), 4);
assert.ok(longSpanAnalysis.time.series.length < longSpanAnalysis.time.adaptiveBinning.spanYears);

const numericAxisRows = [2020, 190, 815, 1992, 2001].flatMap((year, yearIndex) => (
  Array.from({ length: 30 }, (_, index) => row({
    eventId: `numeric-axis-${year}-${index}`,
    source: index % 2 ? "source-a" : "source-b",
    craftType: index < 15 ? "triangle" : "disk",
    shape: index < 15 ? "Triangle" : "Disk",
    sortOrdinal: stats.ordinalFromCivil(year, (index % 12) + 1, 15),
    lat: 10 + yearIndex,
    lon: -100 + yearIndex,
  }))
));
const numericAxisAnalysis = stats.computeAnalysis({
  rows: numericAxisRows,
  baselineMode: "full_catalog",
  timeRangeMode: "full",
});
assert.deepEqual(
  numericAxisAnalysis.time.annualSeries.map((datum) => datum.year),
  [190, 815, 1992, 2001, 2020],
  "three- and four-digit years are ordered numerically"
);
assert.deepEqual(
  numericAxisAnalysis.craft.byEra.metadata.columnAxis.order,
  ["190", "810", "1990", "2000", "2020"],
  "decade heatmap columns are chronological rather than lexicographic or frequency-ranked"
);
assert.deepEqual(
  numericAxisAnalysis.time.monthByCraft.metadata.columnAxis.order,
  stats.MONTH_AXIS_ORDER,
  "month heatmap columns remain January through December"
);
assert.equal(numericAxisAnalysis.summary.referenceCount, 0);
assert.ok(numericAxisAnalysis.time.series.every((datum) => datum.referenceCount === 0));

const orderedContextProjection = stats.normalizeContextProjections({
  cropCircles: [2020, 190, 815, 1992, 2001].map((year) => ({
    id: `ordered-crop-${year}`,
    year,
    startOrdinal: stats.ordinalFromCivil(year, 6, 1),
    endOrdinal: stats.ordinalFromCivil(year, 6, 1),
    datePrecision: "exact_day",
    morphology: ["unknown"],
    crop: "unknown",
    mapped: true,
  })),
  animalReports: [2025, 1950, 1969, 1975, 1984, 1991, 1996, 2012, 2014].map((year) => ({
    id: `ordered-animal-${year}`,
    year,
    startOrdinal: stats.ordinalFromCivil(year, 7, 1),
    endOrdinal: stats.ordinalFromCivil(year, 7, 1),
    datePrecision: "exact_day",
    species: ["unknown"],
    status: "unknown",
    mapped: true,
  })),
});
const orderedContextAnalysis = stats.computeAnalysis({
  rows: [],
  baselineMode: "full_catalog",
  timeRangeMode: "full",
  contextLayers: { cropCirclesEnabled: true, animalMutilationsEnabled: true },
  contextProjections: orderedContextProjection,
});
assert.deepEqual(
  orderedContextAnalysis.context.crops.time.map((datum) => Number(datum.key)),
  [190, 815, 1992, 2001, 2020],
  "crop context time is chronological"
);
assert.deepEqual(
  orderedContextAnalysis.context.animals.time.map((datum) => Number(datum.key)),
  [1950, 1969, 1975, 1984, 1991, 1996, 2012, 2014, 2025],
  "animal context time is chronological"
);
assert.equal(orderedContextAnalysis.context.crops.referenceCount, 0);
assert.equal(orderedContextAnalysis.context.animals.referenceCount, 0);
assert.ok(orderedContextAnalysis.overview.evidenceSummary.every((item) => item.patternFinderEligible === false));
assert.deepEqual(orderedContextAnalysis.patternGroups.withinCorpusAssociation, []);

const statsSource = fs.readFileSync("webapp/static_public/analysis_stats.js", "utf8");
assert.doesNotMatch(statsSource, /traceSegments|trace_segments|chronologySegments|flight path/i);

console.log("analysis statistics assertions passed");
