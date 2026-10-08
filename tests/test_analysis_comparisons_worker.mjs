// New comparison integration only: small retained fixtures, no corpus copies.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
import { createHash, webcrypto } from "node:crypto";

const require = createRequire(import.meta.url);
const cross = require("../analysis_cross_context.js");
const nuclearEngine = require("../analysis_nuclear.js");
const planetaryEngine = require("../analysis_planetary.js");
const day = (iso) => Date.parse(iso + "T00:00:00Z") / 86400000;
const record = (id, iso, extra = {}) => ({ id, startOrdinal: day(iso), endOrdinal: day(iso),
  datePrecision: "exact_day", dateRole: "catalog_unspecified", lat: 0, lon: 0,
  coordinateEvidenceClass: "locality_centroid", uncertaintyKm: null,
  sourceFamilyIds: [id + "_source"], ...extra });
const crop = record("crop", "2000-07-01");
const animals = [1998, 1999, 2000, 2001, 2002].map((year) => record("animal" + year, year + "-07-01"));
animals.push(record("early", "1997-01-01", { lon: 100 }), record("late", "2003-12-31", { lon: 100 }));
const payload = { schemaId: "ufo-analysis-comparison-context-v1", ordinalEpoch: "unix_day", crops: [crop], animals };
const nuclear = { ordinalEpoch: "unix_day", tests: [{ id: "test", ordinal: day("2000-07-01"), lat: 0, lon: 0, role: "weapons" }],
  nuclearFacilities: [{ id: "nuclear_site", lat: 0, lon: 0, nuclearRoleSourceVerified: true, activeIntervals: [[1900, 2100]] }] };
const broaderFacilities = [{ id: "broader_site", lat: 0, lon: 0.01, facilityClass: "research_test", activeIntervals: [[1900, 2100]] }];
const encode = (value) => Buffer.from(JSON.stringify(value));
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
const payloads = new Map();
const pending = new Map();
const calls = { lunar: [], nuclear: [], planetary: [], heatmaps: [], crossContext: [], preparePlanetary: [], base: 0 };
const self = {
  location: { href: "https://fixture.invalid/catalog_filter_worker.js" }, crypto: webcrypto,
  UfoAnalysisCrossContext: { ...cross, computeCrossContext(options) { calls.crossContext.push(options); return cross.computeCrossContext(options); } },
  UfoAnalysisPlanetary: { ...planetaryEngine, preparePlanetaryCohort(options) {
    calls.preparePlanetary.push(options); return planetaryEngine.preparePlanetaryCohort(options);
  }, computePlanetaryContext(options) {
    const all = []; options.forEachRow((row) => all.push({ ...row }));
    calls.planetary.push({ options, rows: all });
    return planetaryEngine.computePlanetaryContext({ ...options, forEachRow: undefined, rows: all });
  }, computePlanetaryHeatmaps(options) {
    calls.heatmaps.push(options); return planetaryEngine.computePlanetaryHeatmaps(options);
  } },
  UfoAnalysisLunar: { computeLunarContext(options) {
    const all = []; options.forEachRow((row) => all.push({ ...row }));
    calls.lunar.push({ options, rows: all });
    return { ordinalEpoch: "unix_day", domains: [{ id: "ufo", total: all.filter((row) => !options.range || row.startOrdinal >= options.range.start && row.startOrdinal <= options.range.end).length }] };
  } },
  UfoAnalysisNuclear: { computeNuclearContext(options) {
    const all = []; options.forEachRow((row) => all.push({ ...row }));
    calls.nuclear.push({ options, rows: all });
    const result = nuclearEngine.computeNuclearContext({ ...options, forEachRow: undefined, rows: all });
    return { ...result, ordinalEpoch: "unix_day", inputRowCount: all.length,
      nuclearFacilityN: result.facilities.nuclearSitesN, broaderFacilityN: result.facilities.broaderSitesN };
  } },
  postMessage(message) {
    const resolve = pending.get(message.requestId);
    assert.ok(resolve, "unexpected worker response: " + message.requestId);
    pending.delete(message.requestId); resolve(message);
  },
};
const context = vm.createContext({ self, console, URL, Response, TextDecoder, Uint8Array, ArrayBuffer,
  fetch: async (urlValue) => {
    const filename = new URL(String(urlValue)).pathname.split("/").at(-1);
    const bytes = payloads.get(filename);
    return bytes ? new Response(bytes) : new Response("missing fixture", { status: 404 });
  },
});
for (const filename of ["analysis_stats.js", "catalog_filter_worker.js"]) {
  vm.runInContext(fs.readFileSync(filename, "utf8"), context, { filename });
  if (filename === "analysis_stats.js") {
    const baseCompute = self.UfoAnalysisStats.computeAnalysis;
    self.UfoAnalysisStats = { ...self.UfoAnalysisStats,
      computeAnalysis(...args) { calls.base += 1; return baseCompute.apply(this, args); } };
  }
}
let request = 0;
function send(message) {
  return new Promise((resolve) => {
    const requestId = "comparison-test-" + (++request);
    pending.set(requestId, resolve);
    self.onmessage({ data: { ...message, requestId } });
  });
}
function manifest(contextValue = payload, nuclearValue = nuclear, atlas = null) {
  const contextBytes = encode(contextValue), nuclearBytes = encode(nuclearValue), facilityBytes = encode(broaderFacilities);
  payloads.set("context_rows.json", contextBytes); payloads.set("nuclear_context_v1.json", nuclearBytes);
  payloads.set("facility_analysis_v1.json", facilityBytes);
  const result = { releaseId: "fixture", artifacts: {
    context: { file: "context_rows.json", sha256: hash(contextBytes), bytes: contextBytes.length },
    nuclear: { file: "nuclear_context_v1.json", sha256: hash(nuclearBytes), bytes: nuclearBytes.length },
    facilities: { file: "facility_analysis_v1.json", sha256: hash(facilityBytes), bytes: facilityBytes.length },
  } };
  if (atlas) {
    const bytes = Buffer.from(atlas.buffer);
    payloads.set("planetary_fixture.bin", bytes);
    result.ephemerisAtlas = { ...atlas.metadata, file: "planetary_fixture.bin", sha256: hash(bytes), bytes: bytes.length };
  }
  return result;
}
const baseFilters = { sourceMode: "subset", selectedSources: ["keep"], typeMode: "all", precisionMode: "all", hideLowPrecision: false, hideNonExactDates: false };
const compute = (extra = {}) => send({ type: "computeAnalysis", baselineMode: "other_dates_balanced",
  datasetHash: "fixture", filters: baseFilters, selectedDomains: ["comparisons"], quickMode: false,
  fullTimeRange: false, timeRangeMode: "window", timeRangeStartOrdinal: day("2000-06-01"), timeRangeEndOrdinal: day("2000-08-01"),
  contextLayers: { cropCirclesEnabled: true, animalMutilationsEnabled: true }, ...extra });
const comparison = (component, extra = {}) => compute({ type: "computeAnalysisComparison", component, ...extra });
const scienceModel = (value) => {
  const model = JSON.parse(JSON.stringify(value));
  // Performance counters depend on warm caches; preserve scientific quantities.
  delete model.precomputation;
  return model;
};
const facets = animals.map((row, index) => ({ ...row, eventId: "ufo" + index, sortOrdinal: row.startOrdinal,
  source: "keep", type: "Triangle", craftType: "triangle", visualTypeGroup: "Craft", mapped: true, precision: "source_coordinates" }));
facets.push({ ...facets[2], eventId: "source_filtered", source: "omit" });
assert.equal((await send({ type: "addCatalogFacetRows", rows: facets })).type, "catalogFacetRowsAdded");
let response = await compute();
assert.equal(response.type, "analysisComputed", response.error);
assert.equal(response.result.comparisonEvidence.status, "loading");

// A first-load integrity failure must not publish a partial artifact state.
let declared = manifest();
declared.artifacts.nuclear.sha256 = "0".repeat(64);
response = await send({ type: "setAnalysisComparisonArtifacts", manifest: declared,
  manifestUrl: "https://fixture.invalid/data/analysis_comparisons/manifest.json" });
assert.equal(response.type, "analysisWorkerError");
assert.match(response.error, /SHA-256 mismatch/);
assert.equal((await compute()).result.comparisonEvidence.status, "loading");

declared = manifest();
response = await send({ type: "setAnalysisComparisonArtifacts", manifest: declared,
  manifestUrl: "https://fixture.invalid/data/analysis_comparisons/manifest.json" });
assert.equal(response.type, "analysisComparisonArtifactsSet", response.error);
assert.equal(response.snapshot.crops, 1);
assert.equal(response.snapshot.animals, 7);
const savedHashes = JSON.stringify(response.snapshot.artifactHashes);
const beforeInput = JSON.stringify(payload);
response = await compute();
assert.equal(response.type, "analysisComputed", response.error);
const evidence = response.result.comparisonEvidence;
assert.equal(evidence.status, "ready");
assert.equal(evidence.ordinalEpoch, "unix_day");
assert.equal(evidence.planetary.ordinalEpoch, "unix_day");
assert.equal(evidence.planetary.planet, "Venus");
assert.equal(evidence.planetary.aspectPartner, "Mars");
assert.equal(evidence.planetary.zodiacSystem, "sidereal");
assert.equal(evidence.planetary.ayanamsaId, "lahiri");
assert.equal(evidence.planetary.aspectOrbDegrees, 3);
assert.equal(evidence.planetary.domains[0].positionEligible, 1, "Planetary estimates scope the active window internally");
assert.equal(evidence.planetary.domains[0].outsideRange, 6, "Calendar opportunity rows outside the window remain available to the engine");
assert.equal(evidence.planetary.houses.eligible, 0);
assert.equal(evidence.planetary.houses.calculated, false);
assert.equal(evidence.planetary.inferenceEligible, false);
assert.deepEqual(scienceModel(evidence.planetary), scienceModel(planetaryEngine.computePlanetaryContext({
  ...calls.planetary.at(-1).options, forEachRow: undefined, rows: calls.planetary.at(-1).rows,
})), "The worker must retain the actual planetary model without a second ordinal conversion");
assert.equal(evidence.lunar.domains[0].total, 1, "Engine scopes active dates internally");
assert.equal(evidence.nuclear.inputRowCount, 7, "Control opportunities outside active dates must reach the engines");
assert.equal(evidence.nuclear.nuclearFacilityN, 1, "nuclearFacilities must be wired from the actual artifact contract");
assert.equal(evidence.nuclear.broaderFacilityN, 1, "Broader facility inputs must remain separate from the reviewed nuclear inventory");
assert.equal(evidence.nuclear.facilities.byDomain.ufo.groups.find((group) => group.id === "both").reportsN, 1);
assert.equal(calls.nuclear.at(-1).rows[2].startOrdinal, day("2000-07-01"), "No accidental second Python-ordinal conversion");
assert.ok(calls.nuclear.at(-1).rows.every((row) => row.source === "keep"), "Non-date report source filters remain active");
assert.equal(calls.planetary.at(-1).rows[2].startOrdinal, day("2000-07-01"));
assert.ok(calls.planetary.at(-1).rows.every((row) => row.source === "keep"));
const publicRow = evidence.crossContext.lanes.find((lane) => lane.id === "public_marker").rows[0];
assert.equal(publicRow.observedPairN, 1);
assert.equal(publicRow.controlPairN, 4, "Context controls beyond the selected dates remain available");
assert.equal(publicRow.expectedMatchedPairN, 1);
assert.equal(publicRow.descriptiveObservedControlRatio, 1);
assert.equal(JSON.stringify(payload), beforeInput, "Comparison engines must not mutate source contexts");
assert.equal(JSON.stringify(evidence.artifactHashes), savedHashes);

// Readiness/hash changes must invalidate loading-result caches; settings changes
// invalidate computed comparison models and inclusion switches honor the scope.
const beforeCalls = calls.nuclear.length;
const beforePlanetaryCalls = calls.planetary.length;
await compute();
assert.equal(calls.nuclear.length, beforeCalls, "Identical full result should be reused");
assert.equal(calls.planetary.length, beforePlanetaryCalls, "Identical planetary settings should reuse the full result");
await compute({ comparisonOptions: { windowDays: 7 } });
assert.equal(calls.nuclear.length, beforeCalls + 1);
assert.equal(calls.nuclear.at(-1).options.windowDays, 7);
const planetSettings = { planet: "Mars", aspectPartner: "Sun", zodiacSystem: "tropical", aspectOrbDegrees: 1 };
let planetaryCalls = calls.planetary.length;
response = await compute({ comparisonOptions: planetSettings });
assert.equal(calls.planetary.length, planetaryCalls + 1, "Planetary settings must invalidate the comparison cache");
assert.equal(response.result.comparisonEvidence.planetary.planet, "Mars");
assert.equal(response.result.comparisonEvidence.planetary.aspectPartner, "Sun");
assert.equal(response.result.comparisonEvidence.planetary.zodiacSystem, "tropical");
assert.equal(response.result.comparisonEvidence.planetary.ayanamsaId, null);
assert.equal(response.result.comparisonEvidence.planetary.aspectOrbDegrees, 1);
planetaryCalls = calls.planetary.length;
await compute({ comparisonOptions: { ...planetSettings } });
assert.equal(calls.planetary.length, planetaryCalls, "Equivalent settings must reuse the result");
for (const settings of [
  { ...planetSettings, planet: "Jupiter" },
  { ...planetSettings, aspectPartner: "Moon" },
  { ...planetSettings, zodiacSystem: "sidereal" },
  { ...planetSettings, aspectOrbDegrees: 5 },
]) {
  const previous = calls.planetary.length;
  response = await compute({ comparisonOptions: settings });
  assert.equal(response.type, "analysisComputed", response.error);
  assert.equal(calls.planetary.length, previous + 1, "Every planetary comparison setting belongs to cache identity");
  for (const key of ["planet", "aspectPartner", "zodiacSystem", "aspectOrbDegrees"]) {
    assert.equal(response.result.comparisonEvidence.planetary[key], settings[key]);
  }
}
response = await compute({ contextLayers: { cropCirclesEnabled: true, animalMutilationsEnabled: false } });
assert.equal(response.result.comparisonEvidence.crossContext.coverage.animals.totalN, 0);
assert.equal(response.result.comparisonEvidence.planetary.domains.find((domain) => domain.id === "animals").total, 0);

// Explicit non-report context and non-exact dates must not enter astronomical
// denominators. Craft appearance remains a report even if it resembles a fireball.
const gateFacets = [
  { ...facets[2], eventId: "planetary_report", source: "gates", craftType: "fireball", type: "Fireball / meteor-like", visualTypeGroup: "Craft" },
  { ...facets[2], eventId: "planetary_context", source: "gates", craftType: "non_ufo_context", type: "Nuclear / atomic event", visualTypeGroup: "Nuclear / atomic / weapons test" },
  { ...facets[2], eventId: "planetary_month", source: "gates", endOrdinal: day("2000-07-31"), datePrecision: "month" },
];
assert.equal((await send({ type: "addCatalogFacetRows", rows: gateFacets })).type, "catalogFacetRowsAdded");
response = await compute({ filters: { ...baseFilters, selectedSources: ["gates"] } });
const gatedPlanetary = response.result.comparisonEvidence.planetary.domains[0];
assert.equal(gatedPlanetary.total, 3);
assert.equal(gatedPlanetary.reportCount, 2);
assert.equal(gatedPlanetary.positionEligible, 1);
assert.equal(gatedPlanetary.excluded.non_ufo_context, 1);
assert.equal(gatedPlanetary.excluded.date_not_exact_day, 1);
assert.ok(calls.planetary.at(-1).rows.every((row) => row.source === "gates"));

// Rejection of a later corrupted artifact leaves the earlier validated candidate
// intact, and explicitly mismatched epoch contracts are rejected.
declared = manifest({ ...payload, ordinalEpoch: "python_day" });
response = await send({ type: "setAnalysisComparisonArtifacts", manifest: declared,
  manifestUrl: "https://fixture.invalid/data/analysis_comparisons/manifest.json" });
assert.equal(response.type, "analysisWorkerError", "Mismatched context epoch must fail before committing");
response = await compute();
assert.equal(JSON.stringify(response.result.comparisonEvidence.artifactHashes), savedHashes);
assert.equal(response.result.comparisonEvidence.crossContext.lanes[0].rows[0].controlPairN, 4);

// Unmapped rows must not become the point (0,0) through numeric coercion, and
// country scopes use source country metadata rather than guessing animal sites.
const geographyPayload = { ...payload, crops: [{ ...crop, country: "France" },
  { ...crop, id: "unmapped_crop", lat: null, lon: null, country: "France" }] };
response = await send({ type: "setAnalysisComparisonArtifacts", manifest: manifest(geographyPayload),
  manifestUrl: "https://fixture.invalid/data/analysis_comparisons/manifest.json" });
assert.equal(response.type, "analysisComparisonArtifactsSet", response.error);
response = await compute({ areaFilterShapes: [{ type: "circle", center: { lat: 0, lng: 0 }, radiusMeters: 1000 }] });
assert.equal(response.result.comparisonEvidence.crossContext.coverage.crops.totalN, 1);
response = await compute({ areaFilterShapes: [{ type: "country", country: "France" }] });
assert.equal(response.result.comparisonEvidence.crossContext.coverage.crops.totalN, 2);
assert.equal(response.result.comparisonEvidence.crossContext.coverage.animals.totalN, 0);

// A tiny precomputed atlas exercises the real binary hash/decoder path. Only
// ephemeris values are precomputed; filtered statistics must remain current.
const atlasDays = [];
for (let ordinal = day("2000-05-31"); ordinal <= day("2000-08-02"); ordinal += 1) atlasDays.push(ordinal);
const tinyAtlas = planetaryEngine.buildEphemerisAtlasBuffer(atlasDays);
const atlasManifest = manifest(payload, nuclear, tinyAtlas);
response = await send({ type: "setAnalysisComparisonArtifacts", manifest: atlasManifest,
  manifestUrl: "https://fixture.invalid/data/analysis_comparisons/manifest.json" });
assert.equal(response.type, "analysisComparisonArtifactsSet", response.error);
assert.equal(response.snapshot.artifactHashes.planetaryEphemeris, atlasManifest.ephemerisAtlas.sha256);
response = await compute();
assert.equal(response.type, "analysisComputed", response.error);
const precomputedEvidence = response.result.comparisonEvidence;
const precomputedBefore = JSON.stringify(precomputedEvidence);
assert.equal(precomputedEvidence.planetary.precomputation.status, "precomputed_raw_ephemeris");
assert.equal(precomputedEvidence.planetary.precomputation.artifactSha256, atlasManifest.ephemerisAtlas.sha256);
assert.equal(precomputedEvidence.planetary.precomputation.directEphemerisCalls, 0, "Covered date-only comparisons must read precomputed positions");
assert.equal(precomputedEvidence.planetary.cohort.prepared, true);

const unaffectedBefore = { base: calls.base, lunar: calls.lunar.length, nuclear: calls.nuclear.length, crossContext: calls.crossContext.length };
const preparedBefore = calls.preparePlanetary.length;
response = await comparison("planetary", { comparisonOptions: { planet: "Saturn", aspectPartner: "Mars", aspectOrbDegrees: 5 },
  generation: 27, filterGeneration: 27, cancellationGeneration: 16, analysisSignature: "current-filter-and-settings" });
assert.equal(response.type, "analysisComparisonComputed", response.error);
assert.equal(response.component, "planetary");
assert.equal(response.model.planet, "Saturn");
assert.equal(response.model.aspectPartner, "Mars");
assert.equal(response.model.aspectOrbDegrees, 5);
assert.equal(response.filterGeneration, 27);
assert.equal(response.cancellationGeneration, 16);
assert.equal(response.analysisSignature, "current-filter-and-settings");
assert.equal(response.cacheHit, false);
assert.equal(response.artifactHashes.planetaryEphemeris, atlasManifest.ephemerisAtlas.sha256);
assert.equal(response.model.domains[0].positionEligible, 1);
assert.equal(response.model.precomputation.directEphemerisCalls, 0);
assert.equal(calls.preparePlanetary.length, preparedBefore, "Settings reuse the immutable folded cohort");
assert.deepEqual({ base: calls.base, lunar: calls.lunar.length, nuclear: calls.nuclear.length, crossContext: calls.crossContext.length },
  unaffectedBefore, "Planetary-only updates must skip the base estimator and all unrelated comparison engines");
assert.equal(JSON.stringify(precomputedEvidence), precomputedBefore, "Targeted updates must not mutate an earlier whole-result cache");
const initialCohortKey = response.comparisonCohortKey;
const targetedModel = response.model;
let targetedCalls = calls.planetary.length;
response = await comparison("planetary", { comparisonOptions: { planet: "Saturn", aspectPartner: "Mars", aspectOrbDegrees: 5 } });
assert.equal(response.cacheHit, true);
assert.equal(calls.planetary.length, targetedCalls);
assert.deepEqual(scienceModel(response.model), scienceModel(targetedModel));
assert.equal(response.comparisonCohortKey, initialCohortKey, "Request generations do not change an identical scientific cohort");

// Cohort identity includes actual keyword IDs, active dates, source filters and
// context inclusions. Equal keyword-list lengths cannot alias different reports.
response = await comparison("planetary", { comparisonOptions: { planet: "Saturn", aspectPartner: "Mars", aspectOrbDegrees: 5 }, keywordEventIds: ["ufo2"] });
assert.equal(response.model.domains[0].positionEligible, 1);
const keywordCohort = response.comparisonCohortKey;
response = await comparison("planetary", { comparisonOptions: { planet: "Saturn", aspectPartner: "Mars", aspectOrbDegrees: 5 }, keywordEventIds: ["ufo0"] });
assert.notEqual(response.comparisonCohortKey, keywordCohort);
assert.equal(response.model.domains[0].positionEligible, 0);
response = await comparison("planetary", { filters: { ...baseFilters, selectedSources: ["gates"] } });
assert.equal(response.model.domains[0].positionEligible, 1);
assert.equal(response.model.domains[0].excluded.non_ufo_context, 1);
assert.equal(response.model.domains[0].excluded.date_not_exact_day, 1);
response = await comparison("planetary", { timeRangeStartOrdinal: day("2000-06-01"), timeRangeEndOrdinal: day("2000-06-30") });
assert.equal(response.model.domains[0].positionEligible, 0);
response = await comparison("planetary", { contextLayers: { cropCirclesEnabled: false, animalMutilationsEnabled: false } });
assert.equal(response.model.domains[1].total, 0);
assert.equal(response.model.domains[2].total, 0);

const nonNuclearBefore = { base: calls.base, lunar: calls.lunar.length, planetary: calls.planetary.length, crossContext: calls.crossContext.length };
response = await comparison("nuclear", { comparisonOptions: { windowDays: 90, testRoles: ["weapons"], distanceBandsKm: [25] } });
assert.equal(response.type, "analysisComparisonComputed", response.error);
assert.equal(response.component, "nuclear");
assert.equal(response.model.settings.windowDays, 90);
assert.deepEqual({ base: calls.base, lunar: calls.lunar.length, planetary: calls.planetary.length, crossContext: calls.crossContext.length }, nonNuclearBefore,
  "Nuclear-only settings must not recompute planetary, lunar or cross-context data");

const nonHeatmapBefore = { base: calls.base, lunar: calls.lunar.length, planetary: calls.planetary.length,
  nuclear: calls.nuclear.length, crossContext: calls.crossContext.length };
response = await comparison("planetaryHeatmaps", { comparisonOptions: { zodiacSystem: "sidereal", aspectOrbDegrees: 3 } });
assert.equal(response.type, "analysisComparisonComputed", response.error);
assert.equal(response.component, "planetaryHeatmaps");
assert.equal(response.model.status, "ready");
assert.equal(response.model.domains[0].matrices.zodiac.rows.length, 9);
assert.equal(response.model.domains[0].matrices.aspects.rows.length, 36);
assert.equal(response.model.domains[0].matrices.motion.rows.length, 9);
assert.deepEqual({ base: calls.base, lunar: calls.lunar.length, planetary: calls.planetary.length,
  nuclear: calls.nuclear.length, crossContext: calls.crossContext.length }, nonHeatmapBefore,
  "Lazy heatmaps must not restart any detailed/core comparison");
const overview = response.model, heatmapCohort = response.comparisonCohortKey;
const overviewCalls = calls.heatmaps.length, overviewPrepCalls = calls.preparePlanetary.length;
response = await comparison("planetaryHeatmaps", { comparisonOptions: { planet: "Saturn", aspectPartner: "Moon",
  zodiacSystem: "sidereal", aspectOrbDegrees: 3, samplingMode: "common_grid" } });
assert.equal(response.cacheHit, true, "Bodies and detailed sampling do not change an all-body overview");
assert.equal(calls.heatmaps.length, overviewCalls);
assert.equal(calls.preparePlanetary.length, overviewPrepCalls);
assert.equal(response.comparisonCohortKey, heatmapCohort);
assert.deepEqual(scienceModel(response.model), scienceModel(overview));
response = await compute();
assert.deepEqual(scienceModel(response.result.comparisonEvidence.planetaryHeatmaps), scienceModel(overview),
  "A whole-result refresh can retain a previously validated matching overview");
assert.equal(calls.heatmaps.length, overviewCalls);
response = await comparison("planetaryHeatmaps", { keywordEventIds: ["ufo0"] });
assert.equal(response.model.domains[0].positionEligible, 0);
assert.equal(response.model.domains[0].matrices.zodiac.rows[0].cells[0].share, null);
assert.notEqual(response.comparisonCohortKey, heatmapCohort);
response = await comparison("planetaryHeatmaps", { contextLayers: { cropCirclesEnabled: false, animalMutilationsEnabled: false } });
assert.equal(response.model.domains[1].positionEligible, 0);
assert.equal(response.model.domains[2].positionEligible, 0);

response = await comparison("unknown", { generation: 27, cancellationGeneration: 16, analysisSignature: "invalid-target-current-signature" });
assert.equal(response.type, "analysisWorkerError");
assert.match(response.error, /Unsupported comparison update/);
assert.equal(response.filterGeneration, 27);
assert.equal(response.cancellationGeneration, 16);
assert.equal(response.analysisSignature, "invalid-target-current-signature");
assert.equal(response.baselineMode, "other_dates_balanced");

// Hash and shape failures cannot replace the already validated atlas, context
// or component cache; successful replacement invalidates derived models.
let corruptedAtlasManifest = manifest(payload, nuclear, tinyAtlas);
corruptedAtlasManifest.ephemerisAtlas.sha256 = "0".repeat(64);
response = await send({ type: "setAnalysisComparisonArtifacts", manifest: corruptedAtlasManifest,
  manifestUrl: "https://fixture.invalid/data/analysis_comparisons/manifest.json" });
assert.equal(response.type, "analysisWorkerError");
assert.match(response.error, /SHA-256 mismatch/);
corruptedAtlasManifest = manifest({ ...payload, crops: [] }, nuclear, tinyAtlas);
corruptedAtlasManifest.ephemerisAtlas.dateCount += 1;
response = await send({ type: "setAnalysisComparisonArtifacts", manifest: corruptedAtlasManifest,
  manifestUrl: "https://fixture.invalid/data/analysis_comparisons/manifest.json" });
assert.equal(response.type, "analysisWorkerError");
assert.match(response.error, /dimensions\/offsets mismatch/);
corruptedAtlasManifest = manifest({ ...payload, crops: [] }, nuclear, tinyAtlas);
corruptedAtlasManifest.ephemerisAtlas.longitudeFormat = "float32";
response = await send({ type: "setAnalysisComparisonArtifacts", manifest: corruptedAtlasManifest,
  manifestUrl: "https://fixture.invalid/data/analysis_comparisons/manifest.json" });
assert.equal(response.type, "analysisWorkerError");
assert.match(response.error, /numeric format\/ephemeris identity mismatch/);
response = await comparison("planetary", { comparisonOptions: { planet: "Saturn", aspectPartner: "Mars", aspectOrbDegrees: 5 } });
assert.equal(response.cacheHit, true, "Rejected atlas candidates must retain the previously validated component cache");
assert.equal(response.model.domains[1].total, 1, "Rejected metadata must not commit accompanying context changes");
assert.equal(response.model.precomputation.artifactSha256, atlasManifest.ephemerisAtlas.sha256);
assert.deepEqual(scienceModel(response.model), scienceModel(targetedModel));
const replacementAtlas = planetaryEngine.buildEphemerisAtlasBuffer(atlasDays.concat([day("2000-08-03")]));
const replacementManifest = manifest(payload, nuclear, replacementAtlas);
response = await send({ type: "setAnalysisComparisonArtifacts", manifest: replacementManifest,
  manifestUrl: "https://fixture.invalid/data/analysis_comparisons/manifest.json" });
assert.equal(response.type, "analysisComparisonArtifactsSet", response.error);
response = await comparison("planetary", { comparisonOptions: { planet: "Saturn", aspectPartner: "Mars", aspectOrbDegrees: 5 } });
assert.equal(response.cacheHit, false);
assert.notEqual(response.comparisonCohortKey, initialCohortKey);
assert.equal(response.model.precomputation.artifactSha256, replacementManifest.ephemerisAtlas.sha256);
assert.deepEqual(scienceModel(response.model), scienceModel(targetedModel));

// Exercise retained real compact assets through the actual SHA loaders and
// result serializer. This compares the entire unmutated direct context model.
if (fs.existsSync("data/analysis_comparisons/context_rows.json") && fs.existsSync("data/analysis_comparisons/nuclear_context_v1.json")) {
  const realContext = JSON.parse(fs.readFileSync("data/analysis_comparisons/context_rows.json", "utf8"));
  const realNuclear = JSON.parse(fs.readFileSync("data/analysis_comparisons/nuclear_context_v1.json", "utf8"));
  response = await send({ type: "setAnalysisComparisonArtifacts", manifest: manifest(realContext, realNuclear),
    manifestUrl: "https://fixture.invalid/data/analysis_comparisons/manifest.json" });
  assert.equal(response.type, "analysisComparisonArtifactsSet", response.error);
  assert.equal(response.snapshot.crops, 7745);
  assert.equal(response.snapshot.animals, 1184);
  response = await compute({ fullTimeRange: true, timeRangeMode: "full" });
  assert.equal(response.type, "analysisComputed", response.error);
  assert.equal(response.result.comparisonEvidence.nuclear.nuclearFacilityN, realNuclear.nuclearFacilities.length);
  assert.equal(JSON.stringify(response.result.comparisonEvidence.crossContext), JSON.stringify(cross.computeCrossContext(realContext)));
}
console.log("Comparison worker integrity, atomicity, scopes, epochs, controls, cache identity and input-preservation checks passed.");
