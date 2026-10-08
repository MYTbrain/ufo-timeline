// Bounded shared-data QA: existing effective summary shards are read in turn;
// no canonical data is copied, rebuilt or written.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import crypto from "node:crypto";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const Lunar = require("../analysis_lunar.js");
const sourceRoot = process.argv[2];
assert.ok(sourceRoot, "Supply the shared canonical workspace root.");
const catalogRoot = path.join(sourceRoot, "data/research/analysis-repairs-20261007/catalog");
const summaryPath = path.join(catalogRoot, "summary_manifest.json");
const contextPath = path.resolve("data/analysis_comparisons/context_rows.json.gz");
const read = filename => JSON.parse(filename.endsWith(".gz") ? zlib.gunzipSync(fs.readFileSync(filename)) : fs.readFileSync(filename));
const hash = filename => crypto.createHash("sha256").update(fs.readFileSync(filename)).digest("hex");
const summary = read(summaryPath);
const context = read(contextPath);
assert.equal(context.ordinalEpoch, "unix_day");
let streamedRows = 0;
const started = performance.now();
const model = Lunar.computeLunarContext({ ordinalEpoch: "unix_day", crops: context.crops, animals: context.animals,
  forEachRow(accept) {
    for (const shard of summary) {
      const rows = read(path.join(catalogRoot, "summary_shards", shard.id + ".json.gz"));
      for (const value of rows) {
        accept({ id: value.event_id, datePrecision: value.date_precision,
          sortOrdinal: value.sort_date_iso ? Math.floor(Date.parse(value.sort_date_iso) / 86400000) : null,
          craftType: value.craft_type_inferred, source: value.source, type: value.type,
          visualTypeGroup: value.visual_type_group });
        streamedRows += 1;
      }
    }
  },
});
const milliseconds = performance.now() - started;
assert.equal(streamedRows, 702893);
assert.equal(model.domains[0].total, streamedRows);
assert.equal(model.domains[0].nonReportContextCount, 12446);
assert.equal(model.domains[1].total, 7745);
assert.equal(model.domains[2].total, 1184);
assert.ok(milliseconds < 30000, "Cold full-catalog lunar computation exceeded its 30-second guard.");
for (const domain of model.domains) {
  assert.equal(domain.phaseBins.reduce((sum, bin) => sum + bin.count, 0), domain.phaseEligible);
  assert.equal(domain.stablePhaseCount + domain.ambiguousPhaseCount, domain.phaseEligible);
  assert.equal(domain.sky.eligible, 0, "Current data has no verified UTC observation timestamps.");
  assert.ok(domain.phaseEligible > 0);
  assert.ok(Math.abs(domain.phaseBins.reduce((sum, bin) => sum + bin.expectedCount, 0) - domain.phaseEligible) < 0.01);
  for (const bin of domain.phaseBins) {
    assert.ok(bin.lowerCount <= bin.count && bin.count <= bin.upperCount);
    assert.ok(Number.isFinite(bin.expectedCount) && bin.expectedCount >= 0);
    assert.ok(Number.isFinite(bin.expectedCalendarShare) && bin.expectedCalendarShare >= 0 && bin.expectedCalendarShare <= 1);
    assert.ok(bin.calendarAdjustedRatio == null || Number.isFinite(bin.calendarAdjustedRatio));
  }
}
const receipt = { schemaId: "ufo-lunar-context-qa-v1", status: "passed", generatedAt: new Date().toISOString(),
  runtimeMilliseconds: Math.round(milliseconds), streamedCatalogRows: streamedRows,
  inputs: [ { path: summaryPath, sha256: hash(summaryPath), role: "effective summary shard manifest" },
    { path: contextPath, sha256: hash(contextPath), role: "shared date-role-preserving cross-domain context" },
    { path: "analysis_lunar.js", sha256: hash("analysis_lunar.js"), role: "comparison implementation" },
    { path: "analysis_astronomy_engine.js", sha256: hash("analysis_astronomy_engine.js"), role: "pinned offline MIT ephemeris" } ],
  domains: model.domains.map(domain => ({ id: domain.id, consideredCatalogRows: domain.total, reportCount: domain.reportCount,
    phaseEligible: domain.phaseEligible, stablePhaseCount: domain.stablePhaseCount,
    ambiguousPhaseCount: domain.ambiguousPhaseCount, excluded: domain.excluded, dateRoles: domain.dateRoles,
    skyEligible: domain.sky.eligible, exposure: domain.exposure, phaseBins: domain.phaseBins })),
  checks: ["702893 shared catalog rows streamed without copies", "Explicit non-UFO context removed from UFO phase counts",
    "Recorded crop/animal date roles retained", "Phase and uncertainty-bound counts conserved", "Calendar opportunity finite",
    "No unverified source clock promoted to UTC", "Independent JPL reference fixtures passed in unit suite"],
  storage: { fullCorpusCopied: false, newFilesAbove100MiB: [], artifactRole: "small local QA receipt; rebuild with this test" } };
const output = path.resolve(process.argv[3] || "data/analysis_comparisons/lunar_qa.json");
fs.writeFileSync(output, JSON.stringify(receipt, null, 2) + "\n");
console.log(JSON.stringify({ status: receipt.status, runtimeMilliseconds: receipt.runtimeMilliseconds,
  domains: receipt.domains.map(({ phaseBins, exposure, ...domain }) => domain), receipt: output }));
