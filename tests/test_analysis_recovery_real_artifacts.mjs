// Local integration test: real frozen candidate bytes through the actual worker
// SHA-256/gzip loaders. Supply the shared data root; no payloads are copied.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import zlib from "node:zlib";
import { webcrypto } from "node:crypto";

const sharedRoot = path.resolve(process.argv[2] || process.cwd());
const repairRoot = path.join(sharedRoot, "data/research/analysis-repairs-20261007");
const current = path.join(sharedRoot, "data/releases/quality-20261007");
function readJson(filename) {
  let bytes = fs.readFileSync(filename);
  if (filename.endsWith(".gz")) bytes = zlib.gunzipSync(bytes);
  return JSON.parse(bytes);
}
const pending = new Map();
const self = {
  location: { href: "https://fixture.invalid/catalog_filter_worker.js" },
  crypto: webcrypto,
  postMessage(message) {
    const resolve = pending.get(message.requestId);
    assert.ok(resolve, "unexpected worker response " + message.requestId);
    pending.delete(message.requestId);
    resolve(message);
  },
};
const requestedPayloads = [];
async function fetchArtifact(urlValue) {
  const url = new URL(String(urlValue), self.location.href);
  const name = path.basename(url.pathname);
  const layer = url.pathname.split("/").find((part) => /^analysis_(?:time_of_day|duration|witness_count)_v1$/.test(part));
  assert.ok(layer, "unexpected artifact transport URL " + url);
  const options = [
    path.join(repairRoot, "attributes", layer, name),
    path.join(current, "analysis_delta", layer, name),
    path.join(sharedRoot, "webapp/static_public/data", layer, name),
  ];
  const filename = options.find((candidate) => fs.existsSync(candidate));
  if (!filename) return new Response("missing fixture", { status: 404 });
  requestedPayloads.push({ layer, name });
  return new Response(fs.readFileSync(filename), { status: 200 });
}
const context = vm.createContext({ self, console, fetch: fetchArtifact, URL, Response, TextDecoder,
  DecompressionStream, Uint8Array, ArrayBuffer });
for (const filename of ["analysis_stats.js", "catalog_filter_worker.js"]) {
  vm.runInContext(fs.readFileSync(filename, "utf8"), context, { filename });
}
let requestNumber = 0;
function send(message) {
  return new Promise((resolve) => {
    const requestId = "real-artifacts-" + (++requestNumber);
    pending.set(requestId, resolve);
    self.onmessage({ data: { ...message, requestId } });
  });
}
function assertSuccess(message, expectedType) {
  assert.equal(message.type, expectedType, message.error || message.type);
  return message;
}

let catalogRows = 0;
const summaryIndex = readJson(path.join(repairRoot, "catalog/summary_manifest.json"));
for (const entry of summaryIndex) {
  const rows = readJson(path.join(repairRoot, "catalog/summary_shards", entry.id + ".json.gz"));
  const facets = rows.map((row) => ({
    eventId: row.event_id, source: row.source, type: row.type,
    visualTypeGroup: row.visual_type_group, craftType: row.craft_type_inferred,
    precision: row.location_precision, datePrecision: row.date_precision,
    sortOrdinal: row.sort_date_iso ? Math.floor(Date.parse(row.sort_date_iso) / 86400000) : null,
    startOrdinal: row.date_iso ? Math.floor(Date.parse(row.date_iso) / 86400000) : null,
    endOrdinal: row.end_date_iso ? Math.floor(Date.parse(row.end_date_iso) / 86400000) : null,
    mapped: Boolean(row.has_coordinates), lat: row.lat, lon: row.lon,
    craftConfidence: row.craft_type_confidence,
  }));
  assertSuccess(await send({ type: "addCatalogFacetRows", rows: facets }), "catalogFacetRowsAdded");
  catalogRows += facets.length;
}
assert.equal(catalogRows, 702893);
const witness = readJson(path.join(repairRoot, "attributes/analysis_witness_count_v1/manifest.json"));
const invalidWitness = structuredClone(witness);
delete invalidWitness.inputs.ufocatWitnessContract;
const rejected = await send({ type: "setAnalysisWitnessCountArtifact", manifest: invalidWitness,
  urls: { manifest: "https://fixture.invalid/data/analysis_witness_count_v1/manifest.json" } });
assert.equal(rejected.type, "catalogFacetWorkerError");
assert.match(rejected.error, /explicit field contract/);
const filters = { sourceMode: "all", typeMode: "all", precisionMode: "all", hideLowPrecision: false, hideNonExactDates: false };
const beforeLoad = assertSuccess(await send({ type: "computeAnalysis", fullTimeRange: true,
  timeRangeMode: "full", baselineMode: "full_catalog", datasetHash: "real-candidate-before-load",
  filters, selectedDomains: ["sources_quality"], quickMode: true }), "analysisComputed");
assert.equal(beforeLoad.result.sourcesQuality.witnessCount.status, "data_unavailable",
  "a rejected contract must leave no partially populated cells or null-manifest errors");

for (const [layer, type, expectedType, countKey] of [
  ["analysis_witness_count_v1", "setAnalysisWitnessCountArtifact", "analysisWitnessCountArtifactSet", "rawWitnessCountRows"],
  ["analysis_time_of_day_v1", "setAnalysisTimeOfDayArtifact", "analysisTimeOfDayArtifactSet", "rawTimeRows"],
  ["analysis_duration_v1", "setAnalysisDurationArtifact", "analysisDurationArtifactSet", "rawDurationRows"],
]) {
  const manifest = readJson(path.join(repairRoot, "attributes", layer, "manifest.json"));
  const response = assertSuccess(await send({ type, manifest,
    urls: { manifest: "https://fixture.invalid/data/" + layer + "/manifest.json" } }), expectedType);
  assert.equal(response.snapshot.loaded, true);
  assert.equal(response.snapshot.appliedRows, manifest.counts[countKey]);
  assert.equal(response.snapshot.typedRows ?? response.snapshot.normalizedRows,
    manifest.counts.typedRows ?? manifest.counts.normalizedRows);
}
const computed = assertSuccess(await send({ type: "computeAnalysis", fullTimeRange: true,
  timeRangeMode: "full", baselineMode: "full_catalog", datasetHash: "real-candidate-loaded",
  filters, selectedDomains: ["sources_quality", "time"], quickMode: true }), "analysisComputed");
const witnessResult = computed.result.sourcesQuality.witnessCount;
assert.equal(witnessResult.status, "ready_descriptive");
assert.equal(witnessResult.coverage.active.rawWitnessCountRows, 219882);
assert.equal(witnessResult.coverage.active.exactCountRows, 198228);
assert.equal(witnessResult.comparisonMetadata.activeReferenceInference, false);
assert.equal(witnessResult.comparisonMetadata.crossSourceComparison, false);
assert.equal(witnessResult.comparisonMetadata.status, "suppressed_source_independence");
assert.equal(witnessResult.patternFinderEligible, false);
assert.equal(computed.result.time.timeOfDay.coverage.active.descriptiveBinnedRows, 534132);
assert.equal(computed.result.time.duration.coverage.active.descriptiveBinnedRows, 243192);
assert.ok(requestedPayloads.some((item) => item.name === "witness_count_projection_v1_000.json.gz"));
assert.ok(requestedPayloads.some((item) => item.name === "time_of_day_projection_v1_003.json.gz"));
assert.ok(requestedPayloads.some((item) => item.name === "duration_projection_v1.json.gz"));
console.log(JSON.stringify({ passed: true, catalogRows, witnessRows: 219882,
  exactWitnessRows: 198228, clockDescriptiveRows: 534132, durationDescriptiveRows: 243192,
  hashedRealPayloadRequests: requestedPayloads.length, corpusCopies: 0 }));
