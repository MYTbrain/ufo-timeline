import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
import { createHash, webcrypto } from "node:crypto";

const require = createRequire(import.meta.url);
const nuclear = require("../analysis_nuclear.js");
const lunar = require("../analysis_lunar.js"), planetary = require("../analysis_planetary.js"), cross = require("../analysis_cross_context.js");
const encounter = require("../encounter_evidence.js"), encounterContext = require("../analysis_encounter_context.js");
const base = JSON.parse(fs.readFileSync("data/analysis_comparisons/nuclear_context_v1.json", "utf8"));
const extension = JSON.parse(fs.readFileSync("data/analysis_comparisons/nuclear_extension_v1.json", "utf8"));
const clone = (value) => JSON.parse(JSON.stringify(value));
const target = extension.tests.find((row) => row.date === "2013-02-12");
const fixture = { eventId: "later-report", source: "fixture", type: "sighting", craftType: "disc_saucer", mapped: true,
  precision: "exact_coords", datePrecision: "exact_day", startOrdinal: target.ordinal, endOrdinal: target.ordinal,
  sortOrdinal: target.ordinal, lat: target.lat, lon: target.lon, encounterEvidenceReady: true,
  encounterAbductionCode: 1, encounterBeingMask: 1, encounterCraftAssociationCode: 1 };
const interval = { startOrdinal: Math.min(...base.tests.map((row) => row.ordinal)), endOrdinal: Math.max(...base.tests.map((row) => row.ordinal)) };
const nativeOptions = { tests: [...base.tests, ...extension.tests], nuclearFacilities: [...base.nuclearFacilities, ...extension.nuclearFacilities],
  rows: [fixture], startOrdinal: target.ordinal, endOrdinal: target.ordinal, windowDays: 7, ordinalEpoch: "unix_day" };
const ungated = nuclear.computeNuclearContext(nativeOptions);
assert.ok(ungated.domains.ufo.matchedControls.controlWindows > 0, "The catalog span alone would wrongly supply later control dates");
const memberships = [];
const gated = nuclear.computeNuclearContext({ ...nativeOptions, controlCoverageIntervals: [interval],
  onReportMembership: (row, value) => memberships.push({ id: row.eventId, value }) });
assert.equal(gated.domains.ufo.linkedReportsN, 1, "Sparse extension events remain available as recorded-date comparisons");
assert.equal(gated.domains.ufo.matchedControls.controlWindows, 0);
assert.equal(gated.domains.ufo.matchedControls.testWindows, 0);
assert.equal(gated.domains.ufo.matchedControls.relativeReportDensity, null, "Missing continuous chronology cannot yield a density ratio");
assert.equal(gated.domains.ufo.matchedControls.status, "no_uncontaminated_calendar_controls");
assert.equal(memberships.length, 1);
assert.equal(memberships[0].id, fixture.eventId);
assert.deepEqual(memberships[0].value.phases, ["same_day"]);
assert.equal(memberships[0].value.distances.length, 1);
const multi = [];
const overlapping = nuclear.computeNuclearContext({ ...nativeOptions, tests: [target, { ...target, id: "independent-fixture-test" }],
  onReportMembership: (row, value) => multi.push({ id: row.eventId, value }) });
assert.equal(multi.length, 1);
assert.equal(overlapping.domains.ufo.phases.find((row) => row.id === "same_day").uniqueReports, 1);
assert.equal(overlapping.domains.ufo.phases.find((row) => row.id === "same_day").pairCount, 2);
assert.deepEqual([...new Set(multi[0].value.phases)], ["same_day"], "Inspector membership preserves report rather than test-pair identity");

const payloads = new Map();
function artifact(name, payload) {
  const bytes = Buffer.from(JSON.stringify(payload)); payloads.set(name, bytes);
  return { file: name, bytes: bytes.length, sha256: createHash("sha256").update(bytes).digest("hex") };
}
function manifest(value = extension) {
  const baseEntry = artifact("base.json", base), candidate = clone(value);
  candidate.baseArtifact = { sha256: baseEntry.sha256, gzipSha256: baseEntry.gzipSha256 };
  return { releaseId: "nuclear-extension-atomic-fixture", artifacts: {
    context: artifact("context.json", { schemaId: "ufo-analysis-comparison-context-v1", ordinalEpoch: "unix_day", crops: [], animals: [] }),
    nuclear: baseEntry, nuclearExtension: artifact("extension.json", candidate), facilities: artifact("facilities.json", []) } };
}
let serial = 0;
const pending = new Map();
const self = { location: { href: "https://fixture.invalid/catalog_filter_worker.js" }, crypto: webcrypto,
  UfoAnalysisNuclear: nuclear, UfoAnalysisLunar: lunar, UfoAnalysisPlanetary: planetary, UfoAnalysisCrossContext: cross,
  UFOEncounterEvidence: encounter, UfoAnalysisEncounterContext: encounterContext,
  postMessage(message) { const resolve = pending.get(message.requestId); assert.ok(resolve); pending.delete(message.requestId); resolve(message); } };
const sandbox = vm.createContext({ self, URL, Response, TextDecoder, Uint8Array, ArrayBuffer, console,
  fetch: async (url) => { const bytes = payloads.get(new URL(url).pathname.split("/").at(-1)); return bytes ? new Response(bytes) : new Response("missing", { status: 404 }); } });
for (const file of ["analysis_stats.js", "encounter_atlas_query.js", "catalog_filter_worker.js"])
  vm.runInContext(fs.readFileSync(file, "utf8"), sandbox, { filename: file });
function send(value) { return new Promise((resolve) => { const requestId = "nuclear-extension-atomic-" + (++serial);
  pending.set(requestId, resolve); self.onmessage({ data: { ...value, requestId } }); }); }
const request = { filters: { sourceMode: "all", typeMode: "all", precisionMode: "all", hideLowPrecision: false, hideNonExactDates: false },
  fullTimeRange: false, timeRangeMode: "custom", timeRangeStartOrdinal: target.ordinal, timeRangeEndOrdinal: target.ordinal,
  baselineMode: "other_dates_balanced", quickMode: false, selectedDomains: ["encounters", "comparisons"], generation: 1,
  contextLayers: { cropCirclesEnabled: false, animalMutilationsEnabled: false } };
assert.equal((await send({ type: "addCatalogFacetRows", rows: [fixture] })).type, "catalogFacetRowsAdded");
const beforeBase = JSON.stringify(base), beforeExtension = JSON.stringify(extension);
let declaration = manifest();
declaration.artifacts.nuclearExtension.sha256 = "0".repeat(64);
let response = await send({ type: "setAnalysisComparisonArtifacts", manifest: declaration, manifestUrl: "https://fixture.invalid/manifest.json" });
assert.equal(response.type, "analysisWorkerError");
assert.match(response.error, /SHA-256 mismatch/);
const unloaded = await send({ ...request, type: "computeAnalysis" });
assert.equal(unloaded.result.comparisonEvidence.status, "loading", "An initial extension failure never publishes base-only success");
declaration = manifest();
response = await send({ type: "setAnalysisComparisonArtifacts", manifest: declaration, manifestUrl: "https://fixture.invalid/manifest.json" });
assert.equal(response.type, "analysisComparisonArtifactsSet", response.error);
const accepted = await send({ ...request, type: "computeAnalysisComparison", component: "nuclear" });
assert.equal(accepted.type, "analysisComparisonComputed", accepted.error);
assert.equal(accepted.model.coverage.catalogRows, base.tests.length + 6);
assert.equal(accepted.model.facilities.nuclearSitesN, base.nuclearFacilities.length + 1);
assert.equal(accepted.model.domains.ufo.matchedControls.controlWindows, 0, "The worker transmits the base-only control-coverage interval");
const scientificModel = JSON.stringify(accepted.model);
for (const corrupt of [
  { ...clone(extension), ordinalEpoch: "unresolved_epoch" },
  { ...clone(extension), tests: [{ ...clone(extension.tests[0]), id: base.tests[0].id }] },
  { ...clone(extension), nuclearFacilities: [{ ...clone(extension.nuclearFacilities[0]), id: base.nuclearFacilities[0].id }] },
]) {
  const rejected = await send({ type: "setAnalysisComparisonArtifacts", manifest: manifest(corrupt), manifestUrl: "https://fixture.invalid/manifest.json" });
  assert.equal(rejected.type, "analysisWorkerError");
  assert.match(rejected.error, /extension (schema|test identity|institution identity) mismatch/);
  const retained = await send({ ...request, type: "computeAnalysisComparison", component: "nuclear" });
  assert.equal(retained.type, "analysisComparisonComputed", retained.error);
  assert.equal(JSON.stringify(retained.model), scientificModel, "Rejected replacements retain the complete accepted merged evidence");
}
assert.equal(JSON.stringify(base), beforeBase);
assert.equal(JSON.stringify(extension), beforeExtension);
console.log("Nuclear extension worker: atomic integrity/schema/collision failures, sparse control hold and exact native memberships passed.");
