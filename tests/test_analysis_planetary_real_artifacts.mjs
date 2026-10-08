// Read existing shared summary shards in turn; never copy or rebuild the corpus.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import crypto from "node:crypto";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const Planetary = require("../analysis_planetary.js");
const sharedRoot = process.argv[2];
assert.ok(sharedRoot, "Supply the shared canonical workspace root.");
const catalogRoot = path.join(sharedRoot, "data/research/analysis-repairs-20261007/catalog");
const summaryPath = path.join(catalogRoot, "summary_manifest.json");
const contextPath = path.resolve("data/analysis_comparisons/context_rows.json.gz");
const read = filename => JSON.parse(filename.endsWith(".gz") ? zlib.gunzipSync(fs.readFileSync(filename)) : fs.readFileSync(filename));
const hash = filename => crypto.createHash("sha256").update(fs.readFileSync(filename)).digest("hex");
const summary = read(summaryPath);
const context = read(contextPath);
assert.equal(context.ordinalEpoch, "unix_day");
let streamedRows = 0;
Planetary.clearCaches();
const started = performance.now();
const model = Planetary.computePlanetaryContext({ ordinalEpoch: "unix_day", planet: "Venus", aspectPartner: "Mars", zodiacSystem: "sidereal", ayanamsaId: "lahiri",
  crops: context.crops, animals: context.animals,
  forEachRow(accept) {
    for (const shard of summary) {
      const rows = read(path.join(catalogRoot, "summary_shards", shard.id + ".json.gz"));
      for (const value of rows) {
        accept({ id: value.event_id, datePrecision: value.date_precision,
          sortOrdinal: value.sort_date_iso ? Math.floor(Date.parse(value.sort_date_iso) / 86400000) : null,
          craftType: value.craft_type_inferred, source: value.source, type: value.type, visualTypeGroup: value.visual_type_group });
        streamedRows += 1;
      }
    }
  },
});
const milliseconds = performance.now() - started;
assert.equal(streamedRows, 702893);
assert.equal(model.domains[0].total, streamedRows);
assert.equal(model.domains[0].nonReportContextCount, 12446);
assert.equal(model.domains[0].positionEligible, 659616);
assert.equal(model.domains[1].total, 7745);
assert.equal(model.domains[2].total, 1184);
assert.ok(milliseconds < 45000, "Cold full-catalog planetary computation exceeded the worker's45-second guard.");
for (const domain of model.domains) {
  assert.equal(domain.signBins.reduce((sum, bin) => sum + bin.count, 0), domain.positionEligible);
  assert.equal(domain.stableSignCount + domain.ambiguousSignCount, domain.positionEligible);
  assert.equal(domain.motion.bins.reduce((sum, bin) => sum + bin.count, 0), domain.positionEligible);
  assert.equal(domain.motion.stableCount + domain.motion.ambiguousCount, domain.positionEligible);
  assert.equal(domain.verifiedTimeCount, 0);
  assert.equal(domain.houses.eligible, 0);
  assert.ok(domain.positionEligible > 0);
  assert.ok(Math.abs(domain.signBins.reduce((sum, bin) => sum + bin.expectedCount, 0) - domain.positionEligible) < 0.01);
  for (const partner of domain.aspectPartners) {
    assert.equal(partner.bins.reduce((sum, bin) => sum + bin.count, 0) + partner.outsideBand.count, domain.positionEligible);
    assert.ok(Math.abs(partner.bins.reduce((sum, bin) => sum + bin.expectedCount, 0) + partner.outsideBand.expectedCount - domain.positionEligible) < 0.01);
  }
  for (const bin of [...domain.signBins, ...domain.motion.bins, ...domain.aspectPartners.flatMap(partner => partner.bins.concat([partner.outsideBand]))]) {
    assert.ok(bin.lowerCount <= bin.count && bin.count <= bin.upperCount);
    assert.ok(Number.isFinite(bin.expectedCount) && bin.expectedCount >= 0);
    assert.ok(bin.calendarAdjustedRatio == null || Number.isFinite(bin.calendarAdjustedRatio));
  }
}
const receipt = { schemaId: "ufo-planetary-context-qa-v1", status: "passed", generatedAt: new Date().toISOString(),
  runtimeMilliseconds: Math.round(milliseconds), streamedCatalogRows: streamedRows,
  settings: { planet: model.planet, aspectPartner: model.aspectPartner, zodiacSystem: model.zodiacSystem, ayanamsaId: model.ayanamsaId, aspectOrbDegrees: model.aspectOrbDegrees },
  inputs: [{ path: summaryPath, sha256: hash(summaryPath), role: "shared effective summary shard manifest" },
    { path: contextPath, sha256: hash(contextPath), role: "date-role-preserving cross-domain context" },
    { path: "analysis_planetary.js", sha256: hash("analysis_planetary.js"), role: "comparison implementation" },
    { path: "analysis_astronomy_engine.js", sha256: hash("analysis_astronomy_engine.js"), role: "pinned offline MIT ephemeris" },
    { path: "data/analysis_comparisons/planetary_reference_fixtures.json", sha256: hash("data/analysis_comparisons/planetary_reference_fixtures.json"), role: "independent primary numerical reference outputs" }],
  domains: model.domains.map(({ id, total, reportCount, nonReportContextCount, positionEligible, stableSignCount, ambiguousSignCount, distinctEligibleDates,
    excluded, dateRoles, sourceCounts, motion, aspectPartners, signBins, exposure, verifiedTimeCount, houses }) =>
    ({ id, total, reportCount, nonReportContextCount, positionEligible, stableSignCount, ambiguousSignCount, distinctEligibleDates,
      excluded, dateRoles, sourceCounts, motion, aspectPartners, signBins, exposure, verifiedTimeCount, houses })),
  checks: ["702893 shared catalog rows streamed without copies", "Explicit non-UFO context excluded", "Exact recorded dates and date roles preserved",
    "Signs, motion and major-aspect plus outside-band denominators conserved", "Actual calendar opportunity conserves expectations", "No unverified source clock promoted to UTC",
    "Sampled interval stability explicitly distinct from a formal enclosure", "Primary JPL/Swiss numerical reference fixtures passed in focused tests"],
  storage: { fullCorpusCopied: false, newFilesAbove100MiB: [], artifactRole: "Small current planetary candidate QA receipt; rebuild with this test." } };
const output = path.resolve(process.argv[3] || "data/analysis_comparisons/planetary_qa.json");
fs.writeFileSync(output, JSON.stringify(receipt, null, 2) + "\n");
console.log(JSON.stringify({ status: receipt.status, runtimeMilliseconds: receipt.runtimeMilliseconds, settings: receipt.settings,
  domains: receipt.domains.map(({ signBins, motion, aspectPartners, sourceCounts, exposure, ...domain }) => domain), receipt: output }));
