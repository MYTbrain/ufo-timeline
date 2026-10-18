// Read the frozen current summary shards in place and exercise the actual app
// serializer, encounter helper, filter worker and Analysis statistics. No corpus
// copy, database, static build or browser automation is created by this audit.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import crypto from "node:crypto";
import zlib from "node:zlib";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const argument = (flag, fallback) => args.includes(flag) ? args[args.indexOf(flag) + 1] : fallback;
const evidenceRoot = path.resolve(argument("--evidence-root", path.join(root, "data/encounters")));
const planPath = path.resolve(argument("--delivery-plan", path.join(root, "releases/workspace-analysis-20261008/delivery_plan.json")));
const outputPath = path.resolve(argument("--output", path.join(root, "docs/qa/encounters-20261013/corpus-runtime.json")));
assert.ok(!fs.existsSync(outputPath), "Refusing to overwrite a retained runtime audit; select a new --output path");
const chronologyRoot = args.includes("--chronology-root") ? path.resolve(argument("--chronology-root", "")) : null;
const sha256 = (bytes) => crypto.createHash("sha256").update(bytes).digest("hex");
const readJson = (file) => JSON.parse(fs.readFileSync(file, "utf8"));
const filePin = (file) => { const bytes = fs.readFileSync(file); return { path: file, bytes: bytes.length, sha256: sha256(bytes) }; };
const plain = (value) => JSON.parse(JSON.stringify(value));
const started = performance.now();
const plan = readJson(planPath);
const shards = plan.uploads.filter((item) => /\/summary_shards\/summary_\d+\.json\.gz$/.test(item.key)).sort((left, right) => left.key.localeCompare(right.key));
assert.equal(shards.length, 71, "Audit requires the complete frozen effective summary inventory");
assert.equal(plan.counts.events, 702893);
const manifestPath = path.join(evidenceRoot, "manifest.json");
const evidencePath = path.join(evidenceRoot, "evidence.json.gz");
const manifest = readJson(manifestPath);
const packed = fs.readFileSync(evidencePath);
const decoded = zlib.gunzipSync(packed);
assert.equal(packed.length, manifest.artifact.gzipBytes);
assert.equal(decoded.length, manifest.artifact.decodedBytes);
assert.equal(sha256(packed), manifest.artifact.gzipSha256);
assert.equal(sha256(decoded), manifest.artifact.decodedSha256);
const payload = JSON.parse(decoded.toString("utf8"));
const api = require(path.join(root, "encounter_evidence.js"));
const index = api.createIndex(payload, manifest.attributeReviews, manifest.artifact.decodedSha256);
const originsManifest = readJson(path.join(root, "data/encounters/manifest.json")).labelOrigins;
let originsIndex = null;
if (originsManifest) {
  const bytes = fs.readFileSync(path.join(root, "data/encounters", originsManifest.file)), raw = zlib.gunzipSync(bytes);
  assert.equal(sha256(bytes), originsManifest.gzipSha256); assert.equal(sha256(raw), originsManifest.decodedSha256);
  originsIndex = api.createLabelOriginsIndex(JSON.parse(raw), index, manifest.artifact.decodedSha256);
}
assert.equal(index.catalogCount, 702893);
let chronologyIndex = null;
let chronologyPins = null;
if (chronologyRoot) {
  const chronologyManifestPath = path.join(chronologyRoot, "manifest.json");
  const chronologyManifest = readJson(chronologyManifestPath);
  const chronologyPath = path.join(chronologyRoot, chronologyManifest.file);
  const chronologyGzip = fs.readFileSync(chronologyPath), chronologyDecoded = zlib.gunzipSync(chronologyGzip);
  assert.equal(sha256(chronologyGzip), chronologyManifest.gzipSha256);
  assert.equal(sha256(chronologyDecoded), chronologyManifest.decodedSha256);
  const chronologyApi = require(path.join(root, "trace_chronology.js"));
  chronologyIndex = chronologyApi.createEvidenceIndex(JSON.parse(chronologyDecoded.toString("utf8")));
  assert.equal(chronologyIndex.snapshot().status, "ready");
  chronologyPins = { manifest: filePin(chronologyManifestPath), gzip: filePin(chronologyPath), decodedSha256: sha256(chronologyDecoded), snapshot: chronologyIndex.snapshot() };
}
const records = new Map(payload.rows.map((row) => [row.eventId, row]));
const sparseInputs = [];
const sourceCounts = Object.create(null);
const matchedSparseIds = new Set();
const joins = { eventId: 0, source: 0, chunk: 0, detailIndex: 0, mismatches: 0, missing: 0 };
let rowsRead = 0;
let dateOrdinalRows = 0;
let dateExcludedReports = 0;
let unindexedMetadataNullRows = 0;

const appCode = fs.readFileSync(path.join(root, "app.js"), "utf8");
const functionCode = (name) => {
  const begin = appCode.indexOf("  function " + name + "(");
  assert.ok(begin >= 0, "Actual app function absent: " + name);
  const end = appCode.indexOf("\n  function ", begin + 3);
  assert.ok(end > begin, "Actual app function boundary absent: " + name);
  return appCode.slice(begin, end);
};
const traceApi = require(path.join(root, "trace_neighborhood.js"));
const serializerContext = vm.createContext({ TRACE_NEIGHBORHOOD: traceApi, CRAFT_TYPE_COLORS: traceApi.CRAFT_TYPE_COLORS,
  runtime: { craftTypeResolutionByKey: new Map() }, state: { colorMode: "craft_type" }, DEFAULT_COLOR_MODE: "craft_type" });
const serializerFunctions = ["parseIsoParts", "daysFromCivil", "isoToOrdinal", "getVisualTypeGroup", "resolvedCraftTypeForEvent", "craftTypeColorKeyForEvent", "eventLegendKeyForMode", "nullableCatalogNumber", "serializeCatalogFacetWorkerRow"];
serializerFunctions.forEach((name) => vm.runInContext(functionCode(name), serializerContext, { filename: "app.js:" + name }));
assert.equal(serializerContext.isoToOrdinal("1970-01-01"), 0, "The worker receives Unix-day ordinals, never Python/Gregorian ordinals");
assert.equal(serializerContext.isoToOrdinal("2000-01-01"), 10957);

const messages = [];
const self = { postMessage: (message) => messages.push(message) };
const workerContext = vm.createContext({ self, console });
vm.runInContext(fs.readFileSync(path.join(root, "encounter_evidence.js"), "utf8"), workerContext, { filename: "encounter_evidence.js" });
self.UFOEncounterEvidence = workerContext.UFOEncounterEvidence;
for (const name of ["analysis_stats.js", "catalog_filter_worker.js"]) {
  vm.runInContext(fs.readFileSync(path.join(root, name), "utf8"), workerContext, { filename: name });
}
const send = (message) => {
  messages.length = 0;
  self.onmessage({ data: message });
  assert.equal(messages.length, 1, "One synchronous actual worker response expected for " + message.type);
  assert.notEqual(messages[0].type, "catalogFacetWorkerError", messages[0].error);
  assert.notEqual(messages[0].type, "analysisWorkerError", messages[0].error);
  return messages[0];
};
const inputPins = shards.map((shard) => ({ key: shard.key, source: shard.source, bytes: shard.bytes, sha256: shard.sha256 }));
const runtimePins = ["app.js", "encounter_evidence.js", "trace_neighborhood.js", "trace_chronology.js", "catalog_filter_worker.js", "analysis_stats.js"].map((name) => filePin(path.join(root, name)));
for (let position = 0; position < shards.length; position += 1) {
  const shard = shards[position];
  const bytes = fs.readFileSync(shard.source);
  assert.equal(bytes.length, shard.bytes, "Frozen summary size changed: " + shard.key);
  assert.equal(sha256(bytes), shard.sha256, "Frozen summary hash changed: " + shard.key);
  const summaries = JSON.parse(zlib.gunzipSync(bytes).toString("utf8"));
  assert.ok(Array.isArray(summaries));
  const serialized = summaries.map((summary) => {
    rowsRead += 1;
    sourceCounts[summary.source] = (sourceCounts[summary.source] || 0) + 1;
    const sourceRow = records.get(String(summary.event_id));
    if (sourceRow) {
      matchedSparseIds.add(String(summary.event_id));
      const checks = { eventId: sourceRow.eventId === String(summary.event_id), source: sourceRow.source === summary.source,
        chunk: sourceRow.sourceRef.chunk === summary.chunk_id, detailIndex: sourceRow.sourceRef.detailIndex === summary.detail_index };
      Object.keys(checks).forEach((field) => { if (checks[field]) joins[field] += 1; else joins.mismatches += 1; });
    }
    const event = api.decorate({ ...summary, sort_ordinal: serializerContext.isoToOrdinal(summary.sort_date_iso) }, index, originsIndex);
    event.encounterOccurrenceDateExcluded = chronologyIndex ? Boolean(chronologyIndex.exclusion(summary.event_id)) : null;
    if (event.encounterOccurrenceDateExcluded) dateExcludedReports += 1;
    assert.equal(event.encounterIdentityMismatch, false, "Encounter source identity mismatch must not enter runtime counts");
    const value = serializerContext.serializeCatalogFacetWorkerRow(event);
    assert.equal(value.encounterOccurrenceDateExcluded, event.encounterOccurrenceDateExcluded);
    assert.ok(value.encounterHeightFeet == null || typeof value.encounterHeightFeet === "number" && Number.isFinite(value.encounterHeightFeet) && value.encounterHeightFeet > 0);
    assert.ok(value.encounterUniform == null || typeof value.encounterUniform === "string");
    if (sourceRow) {
      const record = index.get(sourceRow.eventId);
      assert.equal(value.encounterHeightFeet, record.heightFeet ?? null);
      const uniform = record.uniform == null ? null : typeof record.uniform === "boolean" ? (record.uniform ? "Reported" : "Not reported in source field") : record.uniform;
      assert.equal(value.encounterUniform, uniform);
    } else {
      assert.equal(value.encounterHeightFeet, null);
      assert.equal(value.encounterUniform, null);
      unindexedMetadataNullRows += 1;
    }
    if (value.sortOrdinal != null) dateOrdinalRows += 1;
    if (sourceRow) sparseInputs.push(plain(value));
    return value;
  });
  send({ type: "addCatalogFacetRows", rows: serialized });
  if ((position + 1) % 20 === 0) console.log(`Verified and loaded ${position + 1}/71 summary shards (${rowsRead.toLocaleString()} reports).`);
}
joins.missing = payload.rows.length - matchedSparseIds.size;
assert.equal(rowsRead, 702893);
assert.equal(joins.missing, 0);
assert.equal(joins.mismatches, 0);
assert.deepEqual(plain(sourceCounts), manifest.counts.sourceCounts);

const filters = { keyword: "", sourceMode: "all", typeMode: "all", precisionMode: "all", selectedSources: [], selectedTypes: [], selectedPrecisions: [],
  hideLowPrecision: false, hideNonExactDates: false, legendEventMode: "all", selectedLegendEventKeys: [], legendColorMode: "craft_type" };
const caseSettings = [
  { key: "all", encounters: { abduction: "any", being: "any", beingTypes: [] } },
  { key: "reported_abductions", encounters: { abduction: "reported", being: "any", beingTypes: [] } },
  { key: "reported_beings", encounters: { abduction: "any", being: "reported", beingTypes: [] } },
  { key: "grey", encounters: { abduction: "any", being: "any", beingTypes: ["grey"] } },
  { key: "reported_abductions_and_grey", encounters: { abduction: "reported", being: "any", beingTypes: ["grey"] } },
];
const matrixFor = (rows) => {
  const values = new Map();
  rows.forEach((row) => {
    if (row.encounterCraftAssociationCode !== 1 && row.encounterCraftAssociationCode !== 2) return;
    api.beingTypes(row.encounterBeingMask).forEach((key) => {
      const cell = key + "\u0000" + row.craftType;
      values.set(cell, (values.get(cell) || 0) + 1);
    });
  });
  return values;
};
const receiptCases = [];
const atlasReceipts = [];
for (const setting of caseSettings) {
  const expected = setting.key === "all" ? sparseInputs : sparseInputs.filter((row) => api.matches(row, setting.encounters));
  const response = send({ type: "computeAnalysis", requestId: setting.key, fullTimeRange: true, timeRangeMode: "full", baselineMode: "full_catalog",
    datasetHash: "242ff4abc42c70c2b241a3cd16c8b9059bca137d940bd6147c5a65de63b7750b", quickMode: true, selectedDomains: ["encounters"],
    artifactHashes: { encounterEvidence: manifest.artifact.decodedSha256 }, filters: { ...filters, encounters: setting.encounters } });
  const result = response.result;
  const counts = result.encounters;
  assert.equal(result.encounterEvidenceReady, true);
  assert.equal(counts.evidenceReady, true);
  assert.equal(result.summary.activeCount, setting.key === "all" ? 702893 : expected.length);
  assert.equal(counts.catalogRows, result.summary.activeCount);
  assert.equal(counts.evidenceRows, expected.length);
  const reported = expected.filter((row) => row.encounterAbductionCode === 1 || row.encounterAbductionCode === 2).length;
  const beings = expected.filter((row) => row.encounterBeingMask !== 0).length;
  const ambiguous = expected.filter((row) => row.encounterAbductionCode === 3).length;
  assert.equal(counts.abductionRows, reported);
  assert.equal(counts.beingRows, beings);
  assert.equal(counts.ambiguousAbductionRows, ambiguous);
  const expectedMatrix = matrixFor(expected);
  const actualMatrix = new Map(counts.craftMatrix.map((cell) => [cell.row + "\u0000" + cell.column, cell.count]));
  assert.deepEqual([...actualMatrix].sort(), [...expectedMatrix].sort());
  assert.ok(counts.craftMatrix.every((cell) => cell.inferenceEligible === false));
  const atlas = counts.comparisonAtlas;
  assert.equal(atlas.status, "ready_descriptive");
  assert.equal(atlas.inferentialTestsRun, 0);
  const coreAxes = atlas.axes.filter((axis) => axis.status !== "external_comparison");
  assert.equal(coreAxes.length, 33);
  const sourceAtlas = coreAxes.find((axis) => axis.key === "source");
  const expectedSourceMatrix = new Map();
  expected.forEach((row) => api.beingTypes(row.encounterBeingMask).forEach((key) => {
    const cellKey = key + "\u0000" + row.source;
    expectedSourceMatrix.set(cellKey, (expectedSourceMatrix.get(cellKey) || 0) + 1);
  }));
  assert.deepEqual(plain(sourceAtlas.cells.map((cell) => [cell.row + "\u0000" + cell.column, cell.count]).sort()), [...expectedSourceMatrix].sort());
  coreAxes.forEach((axis) => {
    const coverage = axis.coverage;
    assert.equal(coverage.beingReports, beings);
    assert.equal(coverage.cohortReports, result.summary.activeCount);
    assert.equal(coverage.supportedReports + coverage.unknownReports + coverage.notLoadedReports, coverage.eligibleReports);
    assert.equal(coverage.eligibleReports + coverage.excludedReports, beings);
    assert.ok(axis.rows.every((row) => typeof row.key === "string" && typeof row.label === "string"));
    assert.ok(axis.columns.every((column) => typeof column.key === "string" && typeof column.label === "string"));
    assert.ok(axis.cells.every((cell) => cell.reportDenominator === coverage.eligibleReports && cell.share === cell.count / coverage.eligibleReports && cell.inferenceEligible === false));
  });
  const heightBeing = expected.filter((row) => row.encounterBeingMask && typeof row.encounterHeightFeet === "number" && row.encounterHeightFeet > 0).length;
  const uniformBeing = expected.filter((row) => row.encounterBeingMask && typeof row.encounterUniform === "string"
    && row.encounterUniform.trim() && !["unknown", "unavailable", "unresolved", "unparsed", "none", "null", "n/a", "not_provided"].includes(row.encounterUniform.trim().toLowerCase())).length;
  assert.equal(coreAxes.find((axis) => axis.key === "height").coverage.supportedReports, heightBeing);
  assert.equal(coreAxes.find((axis) => axis.key === "uniform").coverage.supportedReports, uniformBeing);
  if (chronologyIndex) {
    const holdMap = new Map();
    expected.filter((row) => row.encounterOccurrenceDateExcluded === true).forEach((row) => api.beingTypes(row.encounterBeingMask).forEach((key) => {
      holdMap.set(key, (holdMap.get(key) || 0) + 1);
    }));
    const dateAxis = coreAxes.find((axis) => axis.key === "occurrence_date_status");
    assert.deepEqual(plain(dateAxis.cells.filter((cell) => cell.column === "source_date_withheld").map((cell) => [cell.row, cell.count]).sort()), [...holdMap].sort());
    const sourceHeldBodyRows = expected.filter((row) => row.encounterBeingMask && row.encounterOccurrenceDateExcluded === true);
    for (const key of ["decade", "month", "weekday"]) {
      const axis = coreAxes.find((entry) => entry.key === key);
      assert.ok(axis.coverage.unknownReports >= sourceHeldBodyRows.length, "Source date holds must remain unknown in " + key);
    }
  }
  const beingCounts = Object.fromEntries(api.TAXONOMY.map((type) => [type.key, expected.filter((row) => Boolean(row.encounterBeingMask & (1 << type.bit))).length]));
  assert.deepEqual(Object.fromEntries(counts.beingProfile.map((item) => [item.key, item.count])), beingCounts);
  if (setting.key === "all") {
    assert.equal(reported, (manifest.counts.abductionStatusCounts.source_reported || 0) + (manifest.counts.abductionStatusCounts.narrative_reported || 0));
    assert.equal(beings, manifest.counts.beingReportCount);
    Object.entries(manifest.counts.beingTypeCounts).forEach(([key, count]) => assert.equal(beingCounts[key], count));
    assert.deepEqual(Object.fromEntries(counts.sourceCoverage.map((row) => [row.source, row.total])), manifest.counts.sourceCounts);
    assert.deepEqual(Object.fromEntries(counts.sourceCoverage.filter((row) => row.count).map((row) => [row.source, row.count])), manifest.counts.indexedSourceCounts);
  }
  receiptCases.push({ key: setting.key, selection: setting.encounters, matchedReports: result.summary.activeCount, indexedReports: counts.evidenceRows,
    reportedAbductions: reported, ambiguousAbductionMentions: ambiguous, beingReports: beings, craftAssociatedReports: counts.craftAssociatedRows,
    craftMatrixCellCount: actualMatrix.size, craftMatrixMembershipCount: [...actualMatrix.values()].reduce((sum, count) => sum + count, 0), beingTypeCounts: beingCounts });
  atlasReceipts.push({ key: setting.key, coreAxes: coreAxes.length, heightBeingReports: heightBeing, uniformBeingReports: uniformBeing,
    sourceDateHeldIndexedReports: expected.filter((row) => row.encounterOccurrenceDateExcluded === true).length,
    sourceDateHeldBeingReports: expected.filter((row) => row.encounterBeingMask && row.encounterOccurrenceDateExcluded === true).length,
    undatedAbductionReports: counts.undatedAbductionRows, undatedBeingReports: counts.undatedBeingRows,
    coveragePartitionsPassed: true,
    axes: setting.key === "all" ? coreAxes.map((axis) => ({ key: axis.key, label: axis.label, status: axis.status, rowCount: axis.rows.length, columnCount: axis.columns.length,
      cellCount: axis.cells.length, coverage: plain(axis.coverage) })) : [] });
}
const noCraftId = "3125527168511206";
const noCraft = sparseInputs.find((row) => String(row.eventId) === noCraftId);
assert.ok(noCraft, "Retained no-craft regression report must exist in the effective corpus");
assert.ok(noCraft.encounterBeingMask & api.beingMask(["grey"]));
assert.equal(noCraft.encounterCraftAssociationCode, 3);
assert.equal(matrixFor([noCraft]).size, 0, "Explicit no-craft evidence never contributes to the craft co-report matrix");
runtimePins.forEach((pin) => assert.equal(filePin(pin.path).sha256, pin.sha256, "Runtime changed during the corpus audit"));
const evidenceModes = [];
if (originsIndex) for (const mode of ["all", "source_fields", "narrative"]) {
  const response = send({ type: "computeAnalysis", requestId: "mode-" + mode, fullTimeRange: true, timeRangeMode: "full", baselineMode: "full_catalog", quickMode: true,
    selectedDomains: ["encounters"], encounterEvidenceMode: mode, filters });
  const populations = response.result.encounters.comparisonAtlas.populations;
  const expectedBeing = sparseInputs.filter(row => mode === "all" ? row.encounterBeingMask : mode === "source_fields" ? row.encounterSourceBeingMask : row.encounterNarrativeBeingMask).length;
  const expectedAbduction = sparseInputs.filter(row => mode === "all" ? [1,2].includes(row.encounterAbductionCode) : row.encounterAbductionCode === (mode === "source_fields" ? 1 : 2)).length;
  assert.equal(populations.being.reportCount, expectedBeing); assert.equal(populations.abduction.reportCount, expectedAbduction);
  assert.ok(populations.being.evidenceModes.every(value => value.available));
  evidenceModes.push({ mode, beingReports: expectedBeing, abductionReports: expectedAbduction, baseProfileAbductionReports: response.result.encounters.abductionRows });
}
const receipt = { schemaId: "ufo-encounter-corpus-runtime-audit-v1", generatedAtUtc: new Date().toISOString(), status: "passed",
  elapsedSeconds: Math.round((performance.now() - started) / 1000), method: "Each of 71 frozen gzip summary shards was verified and loaded in place through the actual app serializer and current catalog filter worker. Only sparse encounter reference rows were retained for independent exact-count and matrix comparisons.",
  ordinalPolicy: "App inputs are Unix-day ordinals (1970-01-01=0); the worker alone converts to the statistics Gregorian-day epoch.",
  catalogReports: rowsRead, summaryShards: shards.length, datedOrdinalReports: dateOrdinalRows, sourceCounts, sourceJoins: joins,
  optionalMetadata: { heightIndexedReports: sparseInputs.filter((row) => row.encounterHeightFeet != null).length,
    disputedHeightReportsWithheld: (manifest.attributeReviews && manifest.attributeReviews.rows || []).length,
    uniformIndexedReports: sparseInputs.filter((row) => row.encounterUniform != null).length, unindexedMetadataNullRows, sourceDateExcludedReports: dateExcludedReports },
  chronology: chronologyPins, comparisonAtlas: atlasReceipts, evidenceModes,
  evidence: { releaseId: manifest.releaseId, rows: index.rowCount, manifest: filePin(manifestPath), gzip: filePin(evidencePath), decodedSha256: sha256(decoded) },
  runtimePins, deliveryPlan: filePin(planPath), summaryPins: inputPins, cases: receiptCases,
  noCraftRegression: { eventId: noCraftId, source: noCraft.source, beingTypes: api.beingTypes(noCraft.encounterBeingMask), craftAssociation: "none_reported", matrixContribution: 0 },
  limitations: ["This validates counts and integration, not the truth of reported encounters or biological types.", "Source-event identity and narrative classification are pinned and reviewed by the source builder; summary joins verify event ID, collection, chunk and detail index.", "Reports remain the counting unit; source collection overlap does not establish independent incidents."],
  storage: { corpusCopiesCreated: 0, databasesCreated: 0, staticBuildsCreated: 0, artifactOver100MiBCreated: 0, receiptRetention: "Retain as the bounded current encounter runtime QA receipt; summary shards and sparse source evidence remain canonical in their original locations." } };
const bytes = Buffer.from(JSON.stringify(receipt, null, 2) + "\n");
assert.ok(bytes.length < 100 * 1024, "Receipt exceeds its bounded 100 KiB allowance");
fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, bytes);
console.log(JSON.stringify({ status: receipt.status, catalogReports: receipt.catalogReports, sourceJoins: receipt.sourceJoins, cases: receipt.cases,
  receipt: outputPath, receiptBytes: bytes.length, elapsedSeconds: receipt.elapsedSeconds }, null, 2));
