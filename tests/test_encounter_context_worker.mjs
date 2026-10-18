import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
import { createHash, webcrypto } from "node:crypto";
const require = createRequire(import.meta.url);
const encounter = require("../encounter_evidence.js"), contextEngine = require("../analysis_encounter_context.js");
const day = Date.parse("2000-07-01T00:00:00Z") / 86400000;
const rows = [1, 2].map((id) => ({ eventId: id, sortOrdinal: day, datePrecision: "exact_day", source: "ufocat", type: "Disk", craftType: "disc_saucer",
  mapped: true, lat: 0, lon: 0, precision: "exact_coords", coordinateSource: "source_coordinates", encounterEvidenceReady: true,
  encounterBeingMask: encounter.beingMask(["grey"]), encounterAbductionCode: 1, encounterCraftAssociationCode: 1,
  encounterHeightFeet: id === 1 ? 3.5 : 9.25, encounterUniform: id === 1 ? "silver" : null, encounterOccurrenceDateExcluded: id === 2 }));
rows.push({ ...rows[0], eventId: 3, source: "excluded-source", encounterBeingMask: encounter.beingMask(["nordic"]), encounterOccurrenceDateExcluded: null });
const crop = { id: "crop", startOrdinal: day, endOrdinal: day, datePrecision: "exact_day", dateRole: "discovery_date", lat: 0, lon: 0, sourceFamilyIds: ["independent"] };
const contextPayload = { schemaId: "ufo-analysis-comparison-context-v1", ordinalEpoch: "unix_day", crops: [crop], animals: [crop] };
const nuclearPayload = { ordinalEpoch: "unix_day", tests: [{ id: "test", ordinal: day, lat: 0, lon: 0, role: "weapons" }], nuclearFacilities: [] };
const payloads = new Map();
function artifact(name, payload) { const bytes = Buffer.from(JSON.stringify(payload)); payloads.set(name, bytes); return { file: name, bytes: bytes.length, sha256: createHash("sha256").update(bytes).digest("hex") }; }
const manifest = { releaseId: "encounter-context-fixture", artifacts: { context: artifact("context.json", contextPayload), nuclear: artifact("nuclear.json", nuclearPayload), facilities: artifact("facilities.json", []) } };
let requestN = 0; const pending = new Map();
const self = { location: { href: "https://fixture.invalid/catalog_filter_worker.js" }, crypto: webcrypto, UFOEncounterEvidence: encounter,
  UfoAnalysisEncounterContext: contextEngine, UfoAnalysisLunar: require("../analysis_lunar.js"), UfoAnalysisPlanetary: require("../analysis_planetary.js"),
  UfoAnalysisNuclear: require("../analysis_nuclear.js"), UfoAnalysisCrossContext: require("../analysis_cross_context.js"),
  postMessage(message) { const resolve = pending.get(message.requestId); assert.ok(resolve); pending.delete(message.requestId); resolve(message); } };
const sandbox = vm.createContext({ self, URL, Response, TextDecoder, Uint8Array, ArrayBuffer, console,
  fetch: async (url) => { const bytes = payloads.get(new URL(url).pathname.split("/").at(-1)); return bytes ? new Response(bytes) : new Response("missing", { status: 404 }); } });
for (const file of ["analysis_stats.js", "encounter_atlas_query.js", "catalog_filter_worker.js"]) vm.runInContext(fs.readFileSync(file, "utf8"), sandbox, { filename: file });
function send(message) { return new Promise((resolve) => { const requestId = "encounter-context-" + (++requestN); pending.set(requestId, resolve); self.onmessage({ data: { ...message, requestId } }); }); }
let response = await send({ type: "addCatalogFacetRows", rows }); assert.equal(response.type, "catalogFacetRowsAdded");
response = await send({ type: "setAnalysisComparisonArtifacts", manifest, manifestUrl: "https://fixture.invalid/manifest.json" }); assert.equal(response.type, "analysisComparisonArtifactsSet", response.error);
const query = { filters: { sourceMode: "subset", selectedSources: ["ufocat"], typeMode: "all", precisionMode: "all", hideLowPrecision: false, hideNonExactDates: false },
  fullTimeRange: true, timeRangeMode: "full", baselineMode: "full_catalog", quickMode: false, selectedDomains: ["encounters", "comparisons"], generation: 7, filterGeneration: 7,
  contextLayers: { cropCirclesEnabled: true, animalMutilationsEnabled: true } };
response = await send({ ...query, type: "computeAnalysis" }); assert.equal(response.type, "analysisComputed", response.error);
assert.equal(response.result.summary.activeCount, 2);
const atlas = response.result.encounters.comparisonAtlas.axes;
assert.equal(atlas.filter((axis) => axis.status !== "external_comparison").length, 33);
assert.ok(atlas.find((axis) => axis.key === "height").cells.some((cell) => cell.row === "grey" && cell.count > 0), "Reported heights survive app/worker typed storage");
assert.ok(atlas.find((axis) => axis.key === "uniform").cells.some((cell) => cell.row === "grey" && cell.count > 0), "Source uniform strings survive sparse storage");
assert.ok(atlas.find((axis) => axis.key === "occurrence_date_status").cells.some((cell) => cell.column === "source_date_withheld" && cell.row === "grey" && cell.count === 1));
assert.equal(response.result.comparisonEvidence.encounters.groups.find((row) => row.id === "grey").activeN, 2);
assert.equal(response.result.comparisonEvidence.encounters.lunar.matrix.rows.find((row) => row.id === "grey").eligible, 1, "Held occurrence dates stay out of astronomy contexts without losing source profile rows");
assert.equal(response.result.comparisonEvidence.encounters.crops.calendar.rows.find((row) => row.id === "grey").eligible, 1);
assert.equal(response.result.comparisonEvidence.encounters.groups.find((row) => row.id === "nordic").activeN, 0, "Encounter contexts honor source filters");
const targeted = await send({ ...query, type: "computeAnalysisComparison", component: "encounters" }); assert.equal(targeted.type, "analysisComparisonComputed", targeted.error); assert.equal(targeted.cacheHit, true);
const planetRequest = { ...query, type: "computeAnalysisComparison", component: "encounterPlanetary", comparisonOptions: { zodiacSystem: "sidereal", ayanamsaId: "lahiri", aspectOrbDegrees: 3 } };
const planets = await send(planetRequest); assert.equal(planets.type, "analysisComparisonComputed", planets.error);
assert.equal(Object.keys(planets.model.matrices.aspects).length, 36);
assert.equal(Object.values(planets.model.matrices.zodiac)[0].rows.find((row) => row.id === "grey").eligible, 1);
assert.equal((await send(planetRequest)).cacheHit, true, "Repeated atlas choices reuse the computed cohort");
const changed = await send({ ...planetRequest, comparisonOptions: { zodiacSystem: "tropical", aspectOrbDegrees: 3 } });
assert.equal(changed.cacheHit, false); assert.equal(changed.model.settings.zodiacSystem, "tropical");
const noCrops = await send({ ...query, type: "computeAnalysisComparison", component: "encounters", contextLayers: { cropCirclesEnabled: false, animalMutilationsEnabled: true } });
assert.equal(noCrops.cacheHit, false);
assert.equal(noCrops.model.crops.calendar.rows.find((row) => row.id === "grey").cells[0].count, null);
const inspection = await send({ ...query, type: "inspectEncounterReports", inspection: { domain: "core", population: "abduction", axisKey: "height", rowKey: "source_reported", bucket: "supported", offset: 0, limit: 1, requestKey: "cell", scopeKey: "scope" } });
assert.equal(inspection.type, "encounterReportsInspected", inspection.error);
assert.equal(inspection.result.total, 2); assert.equal(inspection.result.eventIds.length, 1); assert.equal(inspection.requestKey, "cell");
const lunarCell = response.result.comparisonEvidence.encounters.lunar.matrix.rows.find((row) => row.id === "grey").cells.find((cell) => cell.count);
const lunarInspection = await send({ ...query, type: "inspectEncounterReports", inspection: { domain: "context", contextTopic: "lunar", contextAxis: "phase", rowKey: "grey", columnKey: lunarCell.id, limit: 25 } });
assert.equal(lunarInspection.result.total, lunarCell.count); assert.deepEqual(lunarInspection.result.eventIds, ["1"]);
const excludedInspection = await send({ ...query, type: "inspectEncounterReports", inspection: { domain: "context", contextTopic: "lunar", contextAxis: "phase", rowKey: "grey", bucket: "excluded" } });
assert.deepEqual(excludedInspection.result.eventIds, ["2"]);
const selected = await send({ ...query, type: "computeAnalysis", filters: { ...query.filters, encounterSelectionIds: ["2"] } });
assert.equal(selected.result.summary.activeCount, 1);
await send({ type: "addCatalogFacetRows", rows: [{ ...rows[0], eventId: 4, mapped: false, lat: null, lon: null,
  encounterBeingMask: 0, encounterAbductionCode: 0, encounterCraftAssociationCode: 0 }] });
const reviewedQuery = { ...query, type: "inspectEncounterReports", reviewedContextEventIds: ["1", "3", "4"],
  inspection: { domain: "reviewed_context", reviewStatus: "all", offset: 0, limit: 1 } };
const reviewedPage = await send(reviewedQuery);
assert.equal(reviewedPage.result.total, 2, "Reviewed inventory still honors the current source filter");
assert.deepEqual(Array.from(reviewedPage.result.eventIds), ["1"]);
const reviewedNext = await send({ ...reviewedQuery, inspection: { ...reviewedQuery.inspection, offset: 1 } });
assert.deepEqual(Array.from(reviewedNext.result.eventIds), ["4"], "Nonvisual, unmapped source context is reachable without inventing a being classification");
const reviewedAll = await send({ ...reviewedQuery, inspection: { ...reviewedQuery.inspection, allIds: true } });
assert.deepEqual(Array.from(reviewedAll.result.eventIds), ["1", "4"], "Applying reviewed reports uses the exact filtered IDs, not just the visible page");
assert.equal((await send({ ...reviewedQuery, reviewedContextEventIds: [] })).result.total, 0);
const reviewOutsideWindow = await send({ ...reviewedQuery, fullTimeRange: false, timeRangeMode: "window", timeRangeStartOrdinal: day + 2, timeRangeEndOrdinal: day + 3 });
assert.equal(reviewOutsideWindow.result.total, 0);
console.log("Worker metadata, atlas, native contexts, exact cell/coverage drilldowns, bounded pages and explicit selection scopes passed.");
