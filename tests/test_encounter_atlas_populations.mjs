import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const stats = require("../analysis_stats.js");
const query = require("../encounter_atlas_query.js");
const day = stats.ordinalFromCivil(2000, 1, 1);
const base = { source: "one", type: "sighting", datePrecision: "exact_day", sortOrdinal: day,
  dateStartOrdinal: day, dateEndOrdinal: day, precision: "city", mapped: false, analysisCountry: "United States",
  analysisMacroregion: "North America", craftType: "triangle", encounterCraftAssociationCode: 1,
  encounterBeingMask: 0, encounterAbductionCode: 0, encounterOccurrenceDateExcluded: false,
  encounterEvidenceProvenanceReady: true, encounterSourceBeingMask: 0, encounterNarrativeBeingMask: 0 };
const rows = [
  { ...base, eventId: "source-with-beings", encounterAbductionCode: 1, encounterBeingMask: (1 << 0) | (1 << 6),
    encounterSourceBeingMask: 1 << 0, encounterNarrativeBeingMask: 1 << 6, analysisTimeOfDayAvailable: true,
    analysisTimeOfDayStatus: "exact_clock", analysisTimeOfDayLowerMinute: 1290, analysisTimeOfDayUpperMinute: 1290,
    analysisTimeOfDayDescriptiveBin: "evening_18_23", analysisColorAvailable: true, analysisColorStatus: "explicit_compound",
    analysisColorCategoryMask: (1 << 0) | (1 << 8), analysisColorRole: "object_surface" },
  { ...base, eventId: "source-no-being", source: "two", encounterAbductionCode: 1, craftType: "unknown",
    encounterCraftAssociationCode: 0 },
  { ...base, eventId: "narrative-no-being", source: "two", encounterAbductionCode: 2, craftType: "disc_saucer",
    encounterCraftAssociationCode: 0, analysisTimeOfDayAvailable: true, analysisTimeOfDayStatus: "clock_range",
    analysisTimeOfDayLowerMinute: 475, analysisTimeOfDayUpperMinute: 485 },
  { ...base, eventId: "being-only", source: "two", encounterBeingMask: 1 << 6, encounterSourceBeingMask: 1 << 6,
    encounterCraftAssociationCode: 3 },
  { ...base, eventId: "ambiguous", source: "three", encounterAbductionCode: 3, encounterBeingMask: 1 << 11,
    encounterNarrativeBeingMask: 1 << 11 },
  { ...base, eventId: "uncoded", source: "three" },
];
const settings = { rows, fullTimeRange: true, baselineMode: "full_catalog", quickMode: true, selectedDomains: ["encounters"],
  encounterEvidenceReady: true, geographyProjectionLoaded: true, timeOfDayProjectionLoaded: true,
  durationProjectionLoaded: true, witnessCountProjectionLoaded: true, colorProjectionLoaded: true,
  reportingDelayProjectionLoaded: true, coordinateEvidenceProjectionLoaded: true };
const result = stats.computeAnalysis(settings).encounters;
const population = (key) => result.comparisonAtlas.populations[key];
const axis = (pop, key) => population(pop).axes.find((item) => item.key === key);
const cell = (pop, key, row, column) => axis(pop, key).cells.find((item) => item.row === row && item.column === column);
assert.equal(result.abductionRows, 3);
assert.equal(result.abductionWithoutBeingRows, 2);
assert.equal(population("being").reportCount, 3);
assert.equal(population("abduction").reportCount, 3);
assert.equal(population("abduction").axes.filter((item) => item.group !== "External context").length, 33);
assert.deepEqual(result.comparisonAtlas.axes, population("being").axes, "Existing being atlas contract remains available");
assert.deepEqual(axis("abduction", "source").rows.map((item) => [item.key, item.reports]), [["source_reported", 2], ["narrative_reported", 1]]);
assert.equal(cell("abduction", "craft", "narrative_reported", "disc_saucer").count, 1, "No being description is required for abduction/craft co-reporting");
assert.equal(axis("abduction", "craft").coverage.excludedReports, 0);
assert.equal(cell("abduction", "craft", "source_reported", "unknown").count, 1);
assert.equal(cell("abduction", "co_descriptions", "source_reported", "unknown").count, 1, "Unindexed beings remain unknown, never physically absent");
assert.equal(cell("abduction", "co_descriptions", "narrative_reported", "unknown").count, 1);
assert.equal(cell("abduction", "source_hour", "narrative_reported", "unknown").count, 1);
const compound = cell("being", "co_descriptions", "grey", "humanoid");
assert.equal(compound.rowReportDenominator, 1);
assert.equal(compound.columnReportDenominator, 2, "Column denominator is original reports, not label-membership sum");
assert.equal(compound.rowShare, 1);
assert.equal(compound.columnShare, 0.5);
const hour = cell("abduction", "source_hour", "source_reported", "21");
assert.equal(hour.rowShare, 0.5);
assert.equal(hour.supportedRowShare, 1);
assert.equal(hour.rowReportDenominator, 2);
assert.equal(hour.supportedRowReportDenominator, 1);
assert.deepEqual(hour.missingFieldBounds, { lower: 0.5, upper: 1, kind: "worst_case_missing_field_completion", confidenceLevel: null });
assert.equal(hour.conditionalComparison.estimateAvailable, false);
assert.equal(hour.conditionalComparison.difference, null);
for (const pop of ["being", "abduction"]) {
  for (const entry of population(pop).axes.filter((item) => item.group !== "External context")) {
    assert.equal(entry.coverage.supportedReports + entry.coverage.unknownReports + entry.coverage.notLoadedReports, entry.coverage.eligibleReports);
    assert.equal(entry.coverage.eligibleReports + entry.coverage.excludedReports, population(pop).reportCount);
    assert.equal(entry.multipleTesting.testsRun, 0);
    for (const value of entry.cells) {
      assert.equal(value.rowShare, value.count / value.rowReportDenominator);
      assert.equal(value.columnShare, value.count / value.columnReportDenominator);
      assert.equal(value.inferenceEligible, false);
      assert.equal(value.conditionalComparison.pValue, null);
      assert.equal(value.conditionalComparison.qValue, null);
      assert.equal(value.conditionalComparison.statisticalInterval, null);
      const n = rows.filter((row) => query.matches(row, { population: pop, axis: entry.key, row: value.row, column: value.column },
        { projectionReadiness: { geography: true, timeOfDay: true, duration: true, witnessCount: true, color: true, reportingDelay: true, coordinateEvidence: true } })).length;
      assert.equal(n, value.count, `Shared drilldown membership matches ${pop}/${entry.key}/${value.row}/${value.column}`);
    }
  }
}
const sourceOnly = stats.computeAnalysis({ ...settings, encounterEvidenceMode: "source_fields" }).encounters;
assert.deepEqual(sourceOnly.abductionProfile, result.abductionProfile, "Atlas-only evidence modes preserve original profiles");
assert.equal(sourceOnly.comparisonAtlas.populations.abduction.reportCount, 2);
assert.equal(sourceOnly.comparisonAtlas.populations.being.reportCount, 2);
assert.ok(!sourceOnly.comparisonAtlas.populations.being.axes.find((item) => item.key === "source").rows.some((item) => item.key === "robotic"));
const narrative = stats.computeAnalysis({ ...settings, encounterEvidenceMode: "narrative" }).encounters.comparisonAtlas.populations;
assert.equal(narrative.abduction.reportCount, 1);
assert.equal(narrative.being.reportCount, 2);
assert.ok(narrative.being.axes.find((item) => item.key === "source").rows.some((item) => item.key === "humanoid"));
const missingProvenanceRows = rows.map((row) => ({ ...row, encounterEvidenceProvenanceReady: undefined,
  encounterSourceBeingMask: undefined, encounterNarrativeBeingMask: undefined }));
const unavailable = stats.computeAnalysis({ ...settings, rows: missingProvenanceRows, encounterEvidenceMode: "source_fields" }).encounters.comparisonAtlas.populations;
assert.equal(unavailable.being.status, "evidence_provenance_unavailable");
assert.ok(unavailable.being.axes.every((item) => item.cells.length === 0));
assert.equal(unavailable.abduction.reportCount, 2, "Source abduction classifications do not require being-label provenance");
assert.equal(unavailable.abduction.axes.find((item) => item.key === "co_descriptions").coverage.notLoadedReports, 1);
assert.equal(unavailable.abduction.axes.find((item) => item.key === "co_descriptions").coverage.unknownReports, 1);
assert.equal(unavailable.being.evidenceModes.find((item) => item.key === "source_fields").available, false);
assert.equal(query.membership(missingProvenanceRows[1], { population: "abduction", evidenceMode: "source_fields" }).eligible, true);
assert.equal(query.membership(missingProvenanceRows[0], { population: "being", evidenceMode: "source_fields" }).status, "evidence_provenance_unavailable");
assert.equal(query.membership(rows[5], { population: "being", evidenceMode: "source_fields" }).eligible, false);
const corrupt = { ...rows[0], encounterNarrativeBeingMask: 0 };
assert.equal(query.membership(corrupt, { population: "being", evidenceMode: "source_fields" }).status, "evidence_provenance_unavailable", "Incomplete per-label provenance cannot silently lose a label");
const unix = { ...rows[0], sortOrdinal: 10957, dateStartOrdinal: 10957, dateEndOrdinal: 10957 };
assert.equal(query.matches(unix, { population: "abduction", axis: "weekday", row: "source_reported", column: "5" }, { ordinalEpoch: "unix_day" }), true);
assert.equal(query.canonicalRow({ sortOrdinal: 0 }, "unix_day").sortOrdinal, stats.ordinalFromCivil(1970, 1, 1));
assert.throws(() => query.canonicalRow(unix, "guess_epoch"), /explicit supported ordinal epoch/);
const page = query.collectPage((visit) => rows.forEach(visit), { population: "abduction", axis: "craft" }, { offset: 1, limit: 1 });
assert.equal(page.totalMatched, 3);
assert.equal(page.rows.length, 1);
assert.equal(page.rows[0].eventId, "source-no-being");
assert.equal(page.coverage.unknownReports, 1);
const excluded = query.collectPage((visit) => rows.forEach(visit), { population: "being", axis: "craft", fieldState: "excluded" }, {});
assert.equal(excluded.totalMatched, 1);
assert.equal(excluded.rows[0].eventId, "being-only");
assert.equal(excluded.rows[0].field.exclusionReason, "no_craft_reported_in_source");
assert.equal(query.matches(rows[3], { population: "being", axis: "craft", fieldState: "excluded" }), true);
const loading = stats.computeAnalysis({ ...settings, encounterEvidenceReady: false }).encounters.comparisonAtlas.populations;
assert.ok(Object.values(loading).every((entry) => entry.status === "loading" && entry.axes.every((item) => !item.cells.length)));
console.log("Encounter populations, distinct-report percentages, provenance modes and exact bounded drilldown checks passed.");
