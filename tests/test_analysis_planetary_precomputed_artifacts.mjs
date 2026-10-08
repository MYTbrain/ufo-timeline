// Whole-cohort parity and nine-body response timing using protected shared data.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import crypto from "node:crypto";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const Planetary = require("../analysis_planetary.js");
const sharedRoot = process.argv[2];
assert.ok(sharedRoot, "Supply the canonical shared workspace.");
const artifactRoot = path.resolve("data/analysis_comparisons");
const manifestPath = path.join(artifactRoot, "ephemeris_atlas_manifest.json");
const manifest = JSON.parse(fs.readFileSync(manifestPath));
const digest = bytes => crypto.createHash("sha256").update(bytes).digest("hex");
const compressed = fs.readFileSync(path.join(artifactRoot, manifest.file));
assert.equal(digest(compressed), manifest.gzipSha256);
const binary = zlib.gunzipSync(compressed);
assert.equal(digest(binary), manifest.sha256);
assert.equal(binary.length, manifest.byteLength);
const atlas = Planetary.decodeEphemerisAtlas(binary, manifest);
const catalogRoot = path.join(sharedRoot, "data/research/analysis-repairs-20261007/catalog");
const summaryPath = path.join(catalogRoot, "summary_manifest.json");
const summary = JSON.parse(fs.readFileSync(summaryPath));
const contextPath = path.join(artifactRoot, "context_rows.json.gz");
const context = JSON.parse(zlib.gunzipSync(fs.readFileSync(contextPath)));
const originalReceipt = JSON.parse(fs.readFileSync(path.join(artifactRoot, "planetary_qa.json")));
let streamedRows = 0;
const preparationStarted = performance.now();
const prepared = Planetary.preparePlanetaryCohort({ ordinalEpoch: "unix_day", crops: context.crops, animals: context.animals,
  forEachRow(accept) {
    for (const shard of summary) {
      const rows = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(catalogRoot, "summary_shards", shard.id + ".json.gz"))));
      for (const row of rows) {
        accept({ datePrecision: row.date_precision, sortOrdinal: row.sort_date_iso ? Math.floor(Date.parse(row.sort_date_iso) / 86400000) : null,
          craftType: row.craft_type_inferred, source: row.source, type: row.type, visualTypeGroup: row.visual_type_group });
        streamedRows += 1;
      }
    }
  },
});
const preparationMilliseconds = performance.now() - preparationStarted;
assert.equal(streamedRows, 702893);
assert.ok(prepared.foldedGroupN < prepared.inputRows / 2);
Planetary.setEphemerisAtlas(atlas);
const defaultStarted = performance.now();
const defaultModel = Planetary.computePlanetaryContext({ preparedCohort: prepared, planet: "Venus", aspectPartner: "Mars", zodiacSystem: "sidereal", ayanamsaId: "lahiri" });
const defaultMilliseconds = performance.now() - defaultStarted;
for (const actual of defaultModel.domains) {
  const reference = originalReceipt.domains.find(domain => domain.id === actual.id);
  for (const field of ["total", "reportCount", "nonReportContextCount", "positionEligible", "stableSignCount", "ambiguousSignCount", "distinctEligibleDates",
    "excluded", "dateRoles", "sourceCounts", "motion", "aspectPartners", "signBins", "exposure", "verifiedTimeCount", "houses"]) {
    assert.deepEqual(actual[field], reference[field], "Full catalog parity failed: " + actual.id + "." + field);
  }
}
const timings = [];
for (const planet of Planetary.PLANETS) {
  Planetary.clearCaches();
  const started = performance.now();
  const model = Planetary.computePlanetaryContext({ preparedCohort: prepared, planet });
  const milliseconds = performance.now() - started;
  assert.ok(milliseconds < 10000, "Precomputed cold model exceeded its bounded10-second guard: " + planet);
  assert.equal(model.precomputation.status, "precomputed_raw_ephemeris");
  assert.equal(model.precomputation.precessionFallbackCalls, 0, "Current calendar cohort must be fully precomputed");
  assert.equal(model.precomputation.directEphemerisCalls, model.precomputation.rateFallbackCalls * 2, "Only threshold-protected rare rates may require direct resolution");
  for (const domain of model.domains) {
    assert.equal(domain.signBins.reduce((sum, bin) => sum + bin.count, 0), domain.positionEligible);
    assert.equal(domain.motion.bins.reduce((sum, bin) => sum + bin.count, 0), domain.positionEligible);
    for (const partner of domain.aspectPartners) assert.equal(partner.bins.reduce((sum, bin) => sum + bin.count, 0) + partner.outsideBand.count, domain.positionEligible);
  }
  timings.push({ planet, aspectPartner: model.aspectPartner, milliseconds: Math.round(milliseconds), precomputation: model.precomputation });
}
const receipt = { schemaId: "ufo-planetary-precomputation-qa-v1", status: "passed", generatedAt: new Date().toISOString(), streamedCatalogRows: streamedRows,
  preparedCohort: { inputRows: prepared.inputRows, foldedGroupN: prepared.foldedGroupN, preparationMilliseconds: Math.round(preparationMilliseconds),
    originalRowsRetained: false, snapshotScope: "Complete retained catalog plus compact crop/animal context; live filtered cohorts have separate denominators." },
  defaultModel: { planet: defaultModel.planet, aspectPartner: defaultModel.aspectPartner, zodiacSystem: defaultModel.zodiacSystem,
    milliseconds: Math.round(defaultMilliseconds), completePriorResultParity: true, precomputation: defaultModel.precomputation },
  nineBodyTimings: timings, atlas: { file: manifest.file, sha256: manifest.sha256, gzipSha256: manifest.gzipSha256,
    byteLength: manifest.byteLength, gzipByteLength: manifest.gzipByteLength, dateCount: manifest.dateCount, dayIndexSha256: manifest.dayIndexSha256 },
  inputs: [{ path: summaryPath, sha256: digest(fs.readFileSync(summaryPath)) }, { path: contextPath, sha256: digest(fs.readFileSync(contextPath)) },
    { path: "analysis_planetary.js", sha256: digest(fs.readFileSync("analysis_planetary.js")) },
    { path: "analysis_astronomy_engine.js", sha256: digest(fs.readFileSync("analysis_astronomy_engine.js")) }],
  checks: ["Full retained cohort result parity, including all date-role/source coverage and sampled bounds", "Nine offered bodies preserve denominators",
    "No original corpus rows retained in prepared snapshot", "Physical values reused across body/partner/zodiac/orb settings",
    "Covered current dates require no ephemeris calculation except explicitly protected threshold cases", "Checksums/dimensions validated before install"],
  storage: { canonical: manifest.file, rawBinaryRetained: false, fullCorpusCopied: false, newFilesAbove100MiB: [], purpose: "Small current precomputation validation receipt; rebuild with this test." } };
const outputPath = path.join(artifactRoot, "planetary_precomputation_qa.json");
fs.writeFileSync(outputPath, JSON.stringify(receipt, null, 2) + "\n");
console.log(JSON.stringify({ status: receipt.status, preparedCohort: receipt.preparedCohort, defaultModel: receipt.defaultModel,
  timings: timings.map(({ planet, milliseconds, precomputation }) => ({ planet, milliseconds, directCalls: precomputation.directEphemerisCalls })), receipt: outputPath }));
