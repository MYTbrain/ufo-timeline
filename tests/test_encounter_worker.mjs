import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const evidence = require("../encounter_evidence.js");
const appCode = fs.readFileSync("app.js", "utf8");
function appFunction(name) {
  const start = appCode.indexOf("  function " + name + "(");
  assert.ok(start >= 0, "Missing actual app function: " + name);
  const end = appCode.indexOf("\n  function ", start + 3);
  assert.ok(end > start, "Missing app function boundary: " + name);
  return appCode.slice(start, end);
}
const appContext = vm.createContext({
  ENCOUNTERS: evidence, LOW_PRECISION_VALUES: new Set(["unknown", "country"]),
  eventLegendKeyForMode: (event, mode) => mode === "type" ? event.visual_type_group : event.craft_type_inferred,
  isoToOrdinal: (iso) => Date.parse(iso + "T00:00:00Z") / 86400000,
});
for (const name of ["nullableCatalogNumber", "serializeCatalogFacetWorkerRow", "eventMatchesMapLegendEventSelection", "eventMatchesNonDateFilters"]) {
  vm.runInContext(appFunction(name), appContext, { filename: "app.js:" + name });
}

const claim = (eventId, abductionStatus, beingTypes, craftAssociation) => ({
  eventId: String(eventId), source: ({ 1: "ufocat", 2: "majestic", 3: "mufon", 4: "nuforc", 5: "majestic", 7: "mufon", 8: "ufocat" })[eventId], sourceEventId: "fixture-" + eventId,
  abductionStatus, beingTypes, craftAssociation,
  evidence: [{ field: "fixture_claim", excerpt: "Synthetic encounter classification for runtime regression.", ruleId: "fixture_only" }],
  sourceRef: { chunk: "chunk_000001", detailIndex: eventId, chunkSha256: "a".repeat(64) },
});
const index = evidence.createIndex({ schemaId: evidence.SCHEMA_ID, releaseId: evidence.RELEASE_ID,
  catalogCount: evidence.CATALOG_COUNT,
  taxonomy: evidence.TAXONOMY.map(({ key, label, group }) => ({ key, label, group })), rows: [
    claim(1, "source_reported", ["grey", "small_humanoid"], "explicit"),
    claim(2, "narrative_reported", ["nordic"], "co_reported"),
    claim(3, "ambiguous", [], "not_established"),
    claim(4, "", ["reptilian"], "explicit"),
    claim(5, "", ["unspecified"], "not_established"),
    claim(7, "source_reported", ["human_like"], "none_reported"),
    claim(8, "narrative_reported", ["grey", "reptilian"], "co_reported"),
  ] });
const event = (event_id, source, type, craft, sort_ordinal, mapped = true, more = {}) => ({
  event_id, source, type, craft_type_inferred: craft, visual_type_group: type,
  date_precision: "exact_day", sort_ordinal, has_coordinates: mapped,
  location_precision: mapped ? "city" : "unknown", lat: mapped ? 40 : null, lon: mapped ? -75 : null,
  coordinate_source: mapped ? "source_coordinates" : "unresolved", ...more,
});
const originals = [
  event(1, "ufocat", "Disk", "disc_saucer", 100),
  event(2, "majestic", "Triangle", "triangle", 100, false),
  event(3, "mufon", "Unknown", "unknown", 104, false, { date_precision: "month",
    date_recovery_contract: "fixture_month_bounds", date_iso: "1970-04-01", end_date_iso: "1970-04-30" }),
  event(4, "nuforc", "Sphere", "sphere_orb", 101),
  event(5, "majestic", "Disk", "disc_saucer", null, false, { date_precision: "unknown" }),
  event(6, "nuforc", "Disk", "disc_saucer", 100),
  event(7, "mufon", "Other", "other", 181, true, { date_precision: "year",
    date_recovery_contract: "fixture_year_bounds", date_iso: "1970-01-01", end_date_iso: "1970-12-31" }),
  event(8, "ufocat", "Triangle", "triangle", 100),
  event(9, "majestic", "Disk", "disc_saucer", -20),
];
const events = originals.map((original) => evidence.decorate(original, index));
const rows = events.map((value) => appContext.serializeCatalogFacetWorkerRow(value));
assert.deepEqual(rows.map((row) => row.encounterAbductionCode), [1, 2, 3, 0, 0, 0, 1, 2, 0]);
assert.deepEqual(rows.map((row) => row.encounterCraftAssociationCode), [1, 2, 0, 1, 0, 0, 3, 2, 0]);
assert.ok(rows.every((row) => row.encounterEvidenceReady === true));
assert.equal(rows[0].encounterBeingMask, evidence.beingMask(["grey", "small_humanoid"]));
assert.equal(rows[2].dateStartOrdinal, 90);
assert.equal(rows[2].dateEndOrdinal, 119);
assert.equal(rows[4].sortOrdinal, null);
assert.equal(rows[1].mapped, false, "Unmapped encounter reports remain inspectable and filterable");
assert.equal(originals[0].encounterBeingMask, undefined, "The source records are never mutated");

function loadWorker(inputRows) {
  const messages = [];
  const self = { postMessage: (message) => messages.push(message) };
  const context = vm.createContext({ self, console });
  // Browser workers have globalThis === self; this VM has separate handles.
  vm.runInContext(fs.readFileSync("encounter_evidence.js", "utf8"), context, { filename: "encounter_evidence.js" });
  self.UFOEncounterEvidence = context.UFOEncounterEvidence;
  for (const file of ["analysis_stats.js", "catalog_filter_worker.js"]) {
    vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
  }
  function send(message) {
    messages.length = 0;
    self.onmessage({ data: message });
    assert.equal(messages.length, 1, "Expected one completion for " + message.type);
    assert.notEqual(messages[0].type, "catalogFacetWorkerError", messages[0].error);
    return JSON.parse(JSON.stringify(messages[0]));
  }
  send({ type: "addCatalogFacetRows", rows: inputRows });
  return { send };
}
const worker = loadWorker(rows);
const base = { keyword: "", sourceMode: "all", typeMode: "all", precisionMode: "all",
  selectedSources: [], selectedTypes: [], selectedPrecisions: [], hideLowPrecision: false, hideNonExactDates: false,
  legendEventMode: "all", selectedLegendEventKeys: [], legendColorMode: "craft_type" };
function mainFilters(filters) {
  return { ...filters, selectedSources: new Set(filters.selectedSources), selectedTypes: new Set(filters.selectedTypes),
    selectedPrecisions: new Set(filters.selectedPrecisions), selectedLegendEventKeys: new Set(filters.selectedLegendEventKeys) };
}
const selections = [
  [{}, [1, 2, 3, 4, 5, 6, 7, 8, 9]],
  [{ abduction: "reported" }, [1, 2, 7, 8]],
  [{ abduction: "source_reported" }, [1, 7]],
  [{ abduction: "ambiguous" }, [3]],
  [{ beingTypes: ["grey"] }, [1, 8]],
  [{ beingTypes: ["nordic", "grey"] }, [1, 2, 8]],
  [{ beingTypes: ["reptilian"] }, [4, 8]],
  [{ abduction: "reported", beingTypes: ["reptilian"] }, [8]],
  [{ abduction: "not_indexed", being: "reported" }, [4, 5]],
  [{ abduction: "not_indexed", being: "not_indexed" }, [6, 9]],
];
for (const [encounters, expected] of selections) {
  const filters = { ...base, encounters };
  const ids = worker.send({ type: "computeFilteredCatalogIds", filters, generation: 10 }).result.eventIds;
  const appIds = events.filter((value) => appContext.eventMatchesNonDateFilters(value, mainFilters(filters), null)).map((value) => value.event_id);
  const helperIds = events.filter((value) => evidence.matches(value, encounters)).map((value) => value.event_id);
  assert.deepEqual(ids, expected, JSON.stringify(encounters));
  assert.deepEqual(ids, appIds, "Actual main fallback and typed worker filter differently");
  assert.deepEqual(ids, helperIds, "Shared helper and typed worker disagree");
}
const sourceQuery = { ...base, encounters: { abduction: "reported" }, sourceMode: "subset", selectedSources: ["ufocat"] };
assert.deepEqual(worker.send({ type: "computeFilteredCatalogIds", filters: sourceQuery }).result.eventIds, [1, 8]);
const mappedPrecision = { ...base, encounters: { abduction: "reported" }, hideLowPrecision: true };
assert.deepEqual(worker.send({ type: "computeFilteredCatalogIds", filters: mappedPrecision, lowPrecisionValues: ["unknown"] }).result.eventIds, [1, 7, 8]);
assert.deepEqual(events.filter((value) => appContext.eventMatchesNonDateFilters(value, mainFilters(mappedPrecision), null)).map((value) => value.event_id), [1, 7, 8]);
assert.deepEqual(worker.send({ type: "computeFilteredCatalogIds", filters: { ...base, encounters: { abduction: "ambiguous" }, hideNonExactDates: true } }).result.eventIds, []);

// Dynamic facets still honor the encounter selection, including partial-date overlap.
const facets = worker.send({ type: "computeCatalogFacetCounts", filters: { ...base, encounters: { abduction: "reported" } },
  timeRangeStartOrdinal: 99, timeRangeEndOrdinal: 101 }).result;
assert.deepEqual(facets.source, { ufocat: 2, majestic: 1, mufon: 1 });
assert.deepEqual(facets.type, { Disk: 1, Triangle: 2, Other: 1 });
assert.deepEqual(facets.precision, { city: 3, unknown: 1 });
assert.deepEqual(facets.legendEventCounts, { disc_saucer: 1, triangle: 2, other: 1 });
const partialFacets = worker.send({ type: "computeCatalogFacetCounts", filters: { ...base, encounters: { abduction: "ambiguous" } },
  timeRangeStartOrdinal: 100, timeRangeEndOrdinal: 100 }).result;
assert.deepEqual(partialFacets.source, { mufon: 1 }, "A month-precision report must not disappear when its midpoint is outside the active day");

function compute(encounters, extra = {}) {
  return worker.send({ type: "computeAnalysis", requestId: "cohort", generation: 77, filterGeneration: 77,
    baselineMode: "full_catalog", fullTimeRange: true, timeRangeMode: "full", datasetHash: "fixture",
    filters: { ...base, encounters }, selectedDomains: ["overview", "encounters"], quickMode: true, ...extra });
}
function matrix(result) {
  return result.encounters.craftMatrix.map((cell) => [cell.row, cell.column, cell.count]).sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
}
const reported = compute({ abduction: "reported" });
assert.equal(reported.result.summary.activeCount, 4);
assert.equal(reported.result.encounters.abductionRows, 4);
assert.equal(reported.result.encounters.beingRows, 4);
assert.equal(reported.result.encounters.craftAssociatedRows, 3);
assert.deepEqual(matrix(reported.result), [
  ["grey", "disc_saucer", 1], ["grey", "triangle", 1], ["nordic", "triangle", 1],
  ["reptilian", "triangle", 1], ["small_humanoid", "disc_saucer", 1],
].sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))));
const reptilian = compute({ beingTypes: ["reptilian"] });
assert.equal(reptilian.result.summary.activeCount, 2);
assert.equal(reptilian.result.encounters.abductionRows, 1);
assert.equal(reptilian.result.encounters.beingRows, 2);
assert.deepEqual(matrix(reptilian.result), [
  ["grey", "triangle", 1], ["reptilian", "sphere_orb", 1], ["reptilian", "triangle", 1],
].sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))));
const ambiguous = compute({ abduction: "ambiguous" });
assert.equal(ambiguous.result.summary.activeCount, 1);
assert.equal(ambiguous.result.encounters.ambiguousAbductionRows, 1);
assert.deepEqual(matrix(ambiguous.result), []);
const restored = compute({ abduction: "reported" });
assert.equal(restored.cacheHit, true, "Restoring a previously selected cohort may reuse only its own cached result");
assert.equal(restored.result.summary.activeCount, 4);
assert.deepEqual(matrix(restored.result), matrix(reported.result));
const currentGeneration = compute({ beingTypes: ["grey"] }, { generation: 78, filterGeneration: 78 });
assert.equal(currentGeneration.generation, 78);
assert.equal(currentGeneration.result.summary.activeCount, 2);
assert.equal(currentGeneration.result.encounters.craftAssociatedRows, 2);
const full = compute({ abduction: "reported" }, { quickMode: false, analysisPhase: "full" });
assert.equal(full.result.summary.activeCount, 4);
assert.deepEqual(matrix(full.result), matrix(reported.result), "Quick and full worker computations must preserve the same encounter matrix");

// Without evidence, ordinary filtering works and active encounter facets fail closed.
const unavailableEvents = originals.map((value) => evidence.decorate(value, null));
const unavailableRows = unavailableEvents.map((value) => appContext.serializeCatalogFacetWorkerRow(value));
assert.ok(unavailableRows.every((row) => row.encounterEvidenceReady === false));
const unavailableWorker = loadWorker(unavailableRows);
assert.equal(unavailableWorker.send({ type: "computeFilteredCatalogIds", filters: base }).result.eventIds.length, 9);
for (const encounters of [{ abduction: "reported" }, { abduction: "not_indexed" }, { being: "not_indexed" }, { beingTypes: ["grey"] }]) {
  assert.deepEqual(unavailableWorker.send({ type: "computeFilteredCatalogIds", filters: { ...base, encounters } }).result.eventIds, []);
  assert.deepEqual(unavailableEvents.filter((value) => appContext.eventMatchesNonDateFilters(value, mainFilters({ ...base, encounters }), null)), []);
}
const unavailableAnalysis = unavailableWorker.send({ type: "computeAnalysis", filters: base, fullTimeRange: true,
  timeRangeMode: "full", baselineMode: "full_catalog", quickMode: true, selectedDomains: ["overview", "encounters"] }).result;
assert.equal(unavailableAnalysis.summary.activeCount, 9);
assert.equal(unavailableAnalysis.encounters.evidenceReady, false);
assert.equal(unavailableAnalysis.encounters.craftMatrix.length, 0);
console.log("Actual encounter app serializer, main fallback, root worker, dynamic facets, Analysis cohort/cache, and unavailable-evidence regressions passed.");
