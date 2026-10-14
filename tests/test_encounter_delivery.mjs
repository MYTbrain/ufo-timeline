import assert from "node:assert/strict";
import fs from "node:fs/promises";
import http from "node:http";
import { createHash, webcrypto } from "node:crypto";
import { gunzipSync } from "node:zlib";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const evidence = require("../encounter_evidence.js");
if (!globalThis.crypto) globalThis.crypto = webcrypto;
const BASE_URL = "http://127.0.0.1:8168/";
const VERSION = "2026-10-13-encounter-atlas-v2";
const MAX_RESPONSE_BYTES = 24 * 1024 * 1024;
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
const statuses = [];
function getLocal(path) {
  const url = new URL(path, BASE_URL);
  assert.equal(url.origin, new URL(BASE_URL).origin, "This check may fetch only the existing local preview server");
  return new Promise((resolve, reject) => {
    const request = http.get(url, { headers: { "Accept-Encoding": "identity" } }, (response) => {
      const chunks = [];
      let length = 0;
      response.on("data", (chunk) => {
        length += chunk.length;
        if (length > MAX_RESPONSE_BYTES) { request.destroy(new Error("Local verification response exceeds the bounded artifact budget")); return; }
        chunks.push(chunk);
      });
      response.on("error", reject);
      response.on("end", () => {
        const bytes = Buffer.concat(chunks);
        const result = { url: url.toString(), status: response.statusCode, headers: response.headers, bytes };
        statuses.push({ path: url.pathname + url.search, status: response.statusCode, bytes: bytes.length,
          sha256: hash(bytes), contentType: response.headers["content-type"] || "",
          contentEncoding: response.headers["content-encoding"] || "" });
        if (response.statusCode !== 200) { reject(new Error("Local resource unavailable (" + response.statusCode + "): " + url.pathname)); return; }
        resolve(result);
      });
    });
    request.on("error", reject);
    request.setTimeout(15000, () => request.destroy(new Error("Local preview request timed out: " + url.pathname)));
  });
}
function jsonOf(response) {
  const bytes = response.bytes[0] === 0x1f && response.bytes[1] === 0x8b ? gunzipSync(response.bytes) : response.bytes;
  return JSON.parse(bytes.toString("utf8"));
}
function idsInHtml(html, ids) {
  for (const id of ids) {
    const count = html.split('id="' + id + '"').length - 1;
    assert.equal(count, 1, "Expected one served control/chart target: " + id);
  }
}

const [configResponse, htmlResponse] = await Promise.all([
  getLocal("data/app_config.json"), getLocal("whole-site.html"),
]);
const config = jsonOf(configResponse);
assert.equal(config.encounterEvidence?.enabled, true, "Final encounter delivery must be enabled explicitly");
assert.equal(config.encounterEvidence.manifestUrl, "./data/encounters/manifest.json");
const manifestUrl = new URL(config.encounterEvidence.manifestUrl, BASE_URL);
const manifestResponse = await getLocal(manifestUrl);
const manifest = jsonOf(manifestResponse);
const artifact = manifest.artifact || manifest;
assert.equal(manifest.schemaId, evidence.SCHEMA_ID);
assert.equal(manifest.releaseId, evidence.RELEASE_ID);
assert.equal(manifest.catalogCount, evidence.CATALOG_COUNT);
assert.ok(Number.isSafeInteger(manifest.rowCount) && manifest.rowCount > 0);
assert.equal(artifact.rowCount, manifest.rowCount);
assert.ok(/^[a-f0-9]{64}$/i.test(artifact.gzipSha256));
assert.ok(/^[a-f0-9]{64}$/i.test(artifact.sha256 || artifact.decodedSha256));
const payloadResponse = await getLocal(new URL(artifact.file || "evidence.json.gz", manifestUrl));
const isGzip = payloadResponse.bytes[0] === 0x1f && payloadResponse.bytes[1] === 0x8b;
const decodedBytes = isGzip ? gunzipSync(payloadResponse.bytes) : payloadResponse.bytes;
if (isGzip) {
  assert.equal(hash(payloadResponse.bytes), artifact.gzipSha256);
  assert.equal(payloadResponse.bytes.length, artifact.gzipBytes);
}
assert.equal(hash(decodedBytes), artifact.sha256 || artifact.decodedSha256);
assert.equal(decodedBytes.length, artifact.decodedBytes ?? artifact.bytes);
// Exercise exactly the shared runtime decoder against the bytes obtained over
// HTTP. No canonical dataset, source archive, or browser state is accessed.
const payload = await evidence.decodeEvidenceResponse(new Response(payloadResponse.bytes), artifact);
const index = evidence.createIndex(payload);
assert.equal(index.rowCount, manifest.rowCount);
assert.equal(index.catalogCount, 702893);
assert.equal(index.taxonomy.length, 19);
assert.deepEqual(index.taxonomy.map((entry) => entry.key), manifest.taxonomy.map((entry) => entry.key));
const snapshot = index.snapshot();
assert.equal(snapshot.beingReportCount, manifest.counts.beingReportCount);
for (const [status, code] of [["source_reported", 1], ["narrative_reported", 2], ["ambiguous", 3]]) {
  assert.equal(payload.rows.filter((row) => row.abductionStatus === status).length, manifest.counts.abductionStatusCounts[status] || 0);
  assert.equal(index.get(payload.rows.find((row) => row.abductionStatus === status)?.eventId)?.encounterAbductionCode, code);
}
assert.deepEqual(snapshot.beingTypeCounts, Object.fromEntries(evidence.TAXONOMY.map((entry) => [entry.key, manifest.counts.beingTypeCounts[entry.key] || 0])));
const noCraft = payload.rows.filter((row) => row.source === "ufocat" && row.beingTypes.length && row.evidence.some((entry) =>
  entry.field.toUpperCase() === "TYPE" && /^0H/.test(entry.excerpt) ||
  entry.field.toUpperCase() === "VALLEE" && entry.excerpt === "AN3" ||
  entry.field.toUpperCase() === "OBJS" && /^0(?:\.0+)?$/.test(entry.excerpt)));
assert.ok(noCraft.length > 0, "Source-coded no-craft encounter reports must remain represented");
for (const row of noCraft) assert.equal(row.craftAssociation, "none_reported", "A source no-craft report must not become a craft co-report: " + row.eventId);
assert.equal(index.get(noCraft[0].eventId).encounterCraftAssociationCode, 3);
assert.ok(evidence.renderEvidence(noCraft[0].eventId, index).includes("No craft association reported"));

const html = htmlResponse.bytes.toString("utf8");
const controlIds = ["encounter-filter-panel", "encounter-abduction-filter", "encounter-being-filter", "encounter-being-types",
  "clear-encounter-filters", "encounter-include-all-types", "encounter-filter-status", "analysis-section-tab-encounters",
  "analysis-section-encounters", "analysis-abduction-profile-chart", "analysis-being-profile-chart", "analysis-being-craft-chart",
  "analysis-abduction-craft-chart", "analysis-encounter-time-chart", "analysis-encounter-coverage-chart", "analysis-encounter-source-chart"];
idsInHtml(html, controlIds);
idsInHtml(html, ["map-legend-panel", "map-control-cluster", "map-control-section-sightings", "map-control-section-traces"]);
const changedHtmlAssets = ["app.js", "analysis_view.js", "analysis_comparisons_view.js", "encounter_evidence.js", "encounter_analysis.css"];
for (const path of changedHtmlAssets) assert.ok(html.includes(path + "?v=" + VERSION), "Changed runtime has a stale served cache token: " + path);
assert.ok(html.indexOf("encounter_evidence.js?") < html.indexOf("app.js?"), "Encounter module must load before the app");
const resourcePaths = [...changedHtmlAssets, "catalog_filter_worker.js", "analysis_stats.js", "analysis_encounter_context.js", "trace_neighborhood.js", "styles.css",
  "ui/accepted-workspace/analysis-navigation.js", "ui/accepted-workspace/analysis-view-groups.js"];
const resources = await Promise.all(resourcePaths.map((path) => getLocal(path + "?v=" + VERSION)));
const workerText = resources[resourcePaths.indexOf("catalog_filter_worker.js")].bytes.toString("utf8");
assert.ok(workerText.includes('ANALYSIS_RUNTIME_CACHE_KEY = "' + VERSION + '"'), "Worker import cache token must match this encounter release");
const appText = resources[resourcePaths.indexOf("app.js")].bytes.toString("utf8");
assert.ok(appText.includes("loadEncounterEvidence") && appText.includes("encounterEvidenceReady"));
const traceText = resources[resourcePaths.indexOf("trace_neighborhood.js")].bytes.toString("utf8");
assert.ok(traceText.includes('"Disc / saucer"') && appText.includes("CRAFT_TYPE_LABELS = TRACE_NEIGHBORHOOD.CRAFT_TYPE_LABELS") &&
  appText.includes('"Close encounter / occupant / abduction"'), "Native craft and encounter legend definitions must be preserved");
const receipt = {
  schemaId: "ufo-encounter-local-delivery-check-v1", checkedAtUtc: new Date().toISOString(),
  previewUrl: BASE_URL + "whole-site.html", releaseId: manifest.releaseId, catalogCount: manifest.catalogCount,
  rowCount: index.rowCount, manifestHttpSha256: hash(manifestResponse.bytes),
  gzipSha256: artifact.gzipSha256, observedGzipSha256: isGzip ? hash(payloadResponse.bytes) : null,
  decodedSha256: hash(decodedBytes), gzipBytes: artifact.gzipBytes, decodedBytes: decodedBytes.length,
  artifactHashPinsValidated: true, runtimeDecoderValidated: true, fullSparseIndexValidated: true,
  knownNoCraftRowsChecked: noCraft.length, knownNoCraftSampleEventId: noCraft[0].eventId,
  beingReportCount: snapshot.beingReportCount, abductionReportedCount: snapshot.abductionReportedCount,
  ambiguousAbductionCount: snapshot.ambiguousAbductionCount, taxonomyKeys: index.taxonomy.map((entry) => entry.key),
  staticChecks: { uniqueControlAndChartIds: controlIds, preservedNativeLegend: true, preservedMapControls: true,
    changedRuntimeCacheTokens: VERSION, moduleBeforeApp: true },
  resources: statuses,
  browserValidation: "not_performed_by_this_check", visualValidation: "pending_browser_review",
  limitation: "HTTP delivery and source-contract checks do not confirm interactive browser behavior or visual layout.",
  newFilesOver100MiB: [], canonicalCorpusCopied: false,
};
const output = new URL("../docs/qa/encounter-atlas-20261013/delivery.json", import.meta.url);
await fs.mkdir(new URL(".", output), { recursive: true });
await fs.writeFile(output, JSON.stringify(receipt, null, 2) + "\n", "utf8");
console.log(JSON.stringify({ status: "passed", rowCount: index.rowCount, catalogCount: index.catalogCount,
  knownNoCraftRowsChecked: noCraft.length, resourcesChecked: statuses.length, receipt: output.pathname,
  browserValidation: receipt.browserValidation }));
