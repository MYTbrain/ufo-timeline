import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const stats = require("../analysis_stats.js");
const day = (year, month = 1, date = 1) => stats.ordinalFromCivil(year, month, date);
const base = { source: "fixture", type: "sighting", precision: "city", datePrecision: "exact_day", mapped: false,
  craftType: "disc_saucer", craftConfidence: "medium", encounterAbductionCode: 0, encounterCraftAssociationCode: 1 };
const rows = [
  { ...base, eventId: "a", source: "one", sortOrdinal: day(2000), encounterBeingMask: (1 << 0) | (1 << 6), encounterAbductionCode: 1,
    craftType: "triangle", shape: "Triangle", analysisCountry: "United States", analysisMacroregion: "North America", adminRegion: "California",
    analysisTimeOfDayAvailable: true, analysisTimeOfDayStatus: "exact_clock", analysisTimeOfDayLowerMinute: 1290, analysisTimeOfDayUpperMinute: 1290,
    analysisTimeOfDayDescriptiveBin: "evening_18_23", analysisDurationAvailable: true, analysisDurationStatus: "exact_seconds", analysisDurationDescriptiveBin: "under_10_seconds",
    analysisWitnessCountAvailable: true, analysisWitnessCountStatus: "exact_count", analysisWitnessCountExactCount: 2, analysisWitnessCountBin: "two",
    analysisColorAvailable: true, analysisColorStatus: "explicit_compound", analysisColorCategoryMask: (1 << 0) | (1 << 8), analysisColorRole: "object_surface",
    encounterHeightFeet: 6, encounterUniform: "Reported", coordinateSource: "source_coordinates",
    analysisReportingDelayAvailable: true, analysisReportingDelayStatus: "reported_valid", analysisReportingDelayBin: "same_day", analysisReportingDelaySelectedRole: "reported",
    analysisCoordinateEvidenceAvailable: true, analysisCoordinateQualityBin: "country_consistent" },
  { ...base, eventId: "b", source: "two", sortOrdinal: day(2000, 3, 1), encounterBeingMask: 1 << 7, encounterCraftAssociationCode: 3,
    analysisCountry: "Egypt", analysisMacroregion: "Africa", mapped: true,
    analysisTimeOfDayAvailable: true, analysisTimeOfDayStatus: "clock_range", analysisTimeOfDayLowerMinute: 475, analysisTimeOfDayUpperMinute: 485,
    analysisTimeOfDayDescriptiveBin: "morning_06_11", analysisDurationAvailable: true, analysisDurationStatus: "approximate_seconds", analysisDurationDescriptiveBin: "1_4_minutes",
    analysisWitnessCountAvailable: true, analysisWitnessCountStatus: "lower_bound", analysisWitnessCountExactCount: null, analysisWitnessCountBin: "two",
    analysisColorAvailable: true, analysisColorStatus: "exact_single", analysisColorCategoryMask: 1 << 2, analysisColorRole: "role_unspecified",
    encounterHeightFeet: 3, encounterUniform: null },
  { ...base, eventId: "c", source: "one", sortOrdinal: day(2000, 7, 1), datePrecision: "year", dateStartOrdinal: day(2000), dateEndOrdinal: day(2000, 12, 31),
    encounterBeingMask: 1 << 12, encounterAbductionCode: 2,
    analysisTimeOfDayAvailable: true, analysisTimeOfDayStatus: "midnight_noon_sentinel", analysisTimeOfDayLowerMinute: 720, analysisTimeOfDayUpperMinute: 720,
    analysisTimeOfDayDescriptiveBin: "unknown", analysisColorAvailable: true, analysisColorStatus: "changing_unspecified", analysisColorCategoryMask: 0 },
  { ...base, eventId: "d", source: "two", sortOrdinal: day(1999, 12, 31), datePrecision: "month", dateStartOrdinal: day(1999, 12, 1), dateEndOrdinal: day(2000, 1, 31),
    encounterBeingMask: 1 << 17, encounterAbductionCode: 3, encounterCraftAssociationCode: 0, encounterHeightFeet: -1, duplicateLineage: "reviewed-lineage" },
  { ...base, eventId: "e", source: "two", sortOrdinal: null, datePrecision: "unknown", craftType: "unknown", craftConfidence: "none",
    encounterBeingMask: 1 << 11, encounterHeightFeet: true, encounterUniform: "Not reported in source field", encounterCraftAssociationCode: 2 },
  { ...base, eventId: "f", source: "one", sortOrdinal: day(2001), encounterBeingMask: 0, encounterAbductionCode: 1 },
];
const options = { rows, fullTimeRange: true, baselineMode: "full_catalog", quickMode: true, selectedDomains: ["encounters"],
  encounterEvidenceReady: true, geographyProjectionLoaded: true, timeOfDayProjectionLoaded: true, durationProjectionLoaded: true,
  witnessCountProjectionLoaded: true, colorProjectionLoaded: true, reportingDelayProjectionLoaded: true, coordinateEvidenceProjectionLoaded: true };
const result = stats.computeAnalysis(options);
const atlas = result.encounters.comparisonAtlas;
const axis = (key) => atlas.axes.find((item) => item.key === key);
const cell = (key, row, column) => axis(key).cells.find((item) => item.row === row && item.column === column);
assert.equal(atlas.status, "ready_descriptive");
assert.equal(atlas.inferentialTestsRun, 0);
assert.equal(atlas.patternFinderEligible, false);
assert.equal(result.encounters.beingRows, 5);
assert.equal(axis("source").coverage.cohortReports, 6);
assert.equal(axis("source").coverage.eligibleReports, 5);
assert.equal(cell("source", "grey", "one").count, 1);
assert.equal(cell("source", "humanoid", "one").count, 1);
assert.equal(cell("co_descriptions", "grey", "humanoid").count, 1);
assert.equal(cell("co_descriptions", "humanoid", "grey").count, 1);
assert.equal(cell("co_descriptions", "grey", "grey").count, 1);
assert.equal(axis("abduction").coverage.supportedReports, 3);
assert.equal(axis("abduction").coverage.unknownReports, 2);
assert.equal(cell("abduction", "robotic", "not_indexed").count, 1);
assert.equal(axis("craft").coverage.eligibleReports, 3);
assert.equal(axis("craft").coverage.excludedReports, 2);
assert.equal(axis("craft").coverage.supportedReports, 2);
assert.equal(axis("craft").coverage.unknownReports, 1);
assert.equal(cell("craft", "robotic", "unknown").count, 1);
assert.ok(!axis("craft").cells.some((item) => item.row === "small_humanoid" || item.row === "other_described"), "No-craft and unestablished reports do not enter craft combinations");
assert.equal(cell("country", "grey", "United States").count, 1, "An explicit country remains usable for an unmapped report");
assert.equal(cell("admin_region", "grey", "United States:California").count, 1);
assert.equal(cell("decade", "luminous", "2000").count, 1, "A year-only report supports its decade");
assert.equal(cell("decade", "other_described", "unknown").count, 1, "A date interval crossing decades must not enter an invented decade");
assert.equal(cell("month", "luminous", "unknown").count, 1);
assert.equal(cell("month", "other_described", "unknown").count, 1);
assert.equal(cell("month", "grey", "01").count, 1);
assert.equal(axis("month").columns.find((item) => item.key === "01").label, "January");
assert.equal(cell("weekday", "grey", "5").count, 1, "2000-01-01 is Saturday in the source calendar");
assert.equal(cell("weekday", "small_humanoid", "2").count, 1, "2000-03-01 is Wednesday");
assert.equal(cell("weekday", "luminous", "unknown").count, 1);
assert.equal(axis("source_hour").coverage.supportedReports, 1);
assert.equal(cell("source_hour", "grey", "21").count, 1);
assert.equal(cell("source_hour", "small_humanoid", "unknown").count, 1, "A range spanning hours cannot pick one endpoint hour");
assert.equal(cell("source_hour", "luminous", "unknown").count, 1, "Noon/midnight sentinels cannot become exact clock hours");
assert.equal(cell("time_status", "luminous", "midnight_noon_sentinel").count, 1);
assert.equal(cell("duration", "small_humanoid", "1_4_minutes").count, 1, "Existing descriptive approximate duration bins stay descriptive");
assert.equal(cell("witnesses", "small_humanoid", "unknown").count, 1, "A lower-bound witness count is not an exact-count bin");
assert.equal(cell("witness_status", "small_humanoid", "lower_bound").count, 1);
assert.equal(cell("color", "grey", "object_surface:white").count, 1);
assert.equal(cell("color", "grey", "object_surface:blue").count, 1);
assert.equal(cell("color", "humanoid", "object_surface:white").count, 1);
assert.equal(cell("color", "small_humanoid", "role_unspecified:gray").count, 1, "An unknown color role never becomes object surface");
assert.equal(axis("color").coverage.supportedReports, 2);
assert.ok(axis("color").coverage.membershipCount > axis("color").coverage.eligibleReports);
assert.equal(cell("height", "grey", "5_to_under_7_ft").count, 1);
assert.equal(cell("height", "small_humanoid", "3_to_under_5_ft").count, 1);
assert.equal(cell("height", "robotic", "unknown").count, 1, "A boolean must not become numeric source height");
assert.equal(cell("uniform", "robotic", "Not reported in source field").count, 1);
assert.equal(cell("mapped", "grey", "unmapped").count, 1);
assert.equal(cell("mapped", "small_humanoid", "mapped").count, 1);
assert.equal(cell("duplicate_lineage", "other_described", "lineage_flag_present").count, 1);
assert.equal(cell("reporting_delay", "grey", "same_day").count, 1);
assert.equal(cell("reporting_delay_role", "grey", "reported").count, 1);
for (const entry of atlas.axes.filter((item) => item.group !== "External context")) {
  assert.equal(entry.coverage.supportedReports + entry.coverage.unknownReports + entry.coverage.notLoadedReports, entry.coverage.eligibleReports);
  assert.equal(entry.coverage.eligibleReports + entry.coverage.excludedReports, 5);
  assert.ok(entry.cells.every((item) => item.reportDenominator === entry.coverage.eligibleReports && item.share === item.count / entry.coverage.eligibleReports));
  assert.ok(entry.cells.every((item) => item.inferenceEligible === false && !Object.hasOwn(item, "pValue") && !Object.hasOwn(item, "qValue")));
}
for (const key of ["lunar", "planetary", "nuclear", "facilities", "crops", "animals"]) {
  assert.equal(axis(key).status, "external_comparison");
  assert.deepEqual(axis(key).cells, []);
}
const unloaded = stats.computeAnalysis({ ...options, rows: [{ ...base, eventId: "missing", sortOrdinal: day(2000), encounterBeingMask: 1 }],
  timeOfDayProjectionLoaded: false, durationProjectionLoaded: false, witnessCountProjectionLoaded: false, colorProjectionLoaded: false });
const unloadedHour = unloaded.encounters.comparisonAtlas.axes.find((item) => item.key === "source_hour");
assert.equal(unloadedHour.status, "data_unavailable");
assert.equal(unloadedHour.coverage.notLoadedReports, 1);
assert.equal(unloadedHour.cells[0].column, "not_loaded");
const missingClock = stats.computeAnalysis({ ...options, rows: [{ ...base, eventId: "missing", sortOrdinal: day(2000), encounterBeingMask: 1 }] });
assert.equal(missingClock.encounters.comparisonAtlas.axes.find((item) => item.key === "source_hour").coverage.unknownReports, 1,
  "After the clock projection loads, absent source clocks are unknown rather than not loaded");
const notReady = stats.computeAnalysis({ ...options, encounterEvidenceReady: false }).encounters.comparisonAtlas;
assert.equal(notReady.status, "loading");
assert.ok(notReady.axes.every((item) => item.cells.length === 0 && item.coverage.supportedReports === 0));
const excludedDate = stats.computeAnalysis({ ...options, rows: [{ ...rows[0], encounterOccurrenceDateExcluded: true }] }).encounters.comparisonAtlas;
for (const key of ["decade", "month", "weekday"]) assert.equal(excludedDate.axes.find((item) => item.key === key).coverage.supportedReports, 0,
  "A source-excluded occurrence date must not populate a new temporal combination");
assert.equal(excludedDate.axes.find((item) => item.key === "occurrence_date_status").cells[0].column, "source_date_withheld");
const filtered = stats.computeAnalysis({ ...options, matchesNonDateFilters: (item) => item.source === "one" });
assert.equal(filtered.encounters.comparisonAtlas.axes.find((item) => item.key === "source").coverage.cohortReports, 3);
assert.equal(filtered.encounters.comparisonAtlas.axes.find((item) => item.key === "source").coverage.beingReports, 2);
assert.deepEqual(stats.computeAnalysis({ ...options, selectedDomains: ["craft", "encounters"] }).encounters.comparisonAtlas, atlas,
  "Quick and full row accumulation preserve the same comparison atlas");
console.log("Encounter comparison atlas: supported fields, unknowns, source roles, calendar gates, multi-label counts and coverage checks passed.");
