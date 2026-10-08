// Bulk overview timing and exact common-grid drilldown checks on protected shared data.
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
const root = path.resolve("data/analysis_comparisons");
const manifestPath = path.join(root, "ephemeris_atlas_manifest.json");
const manifest = JSON.parse(fs.readFileSync(manifestPath));
const digest = bytes => crypto.createHash("sha256").update(bytes).digest("hex");
const compressed = fs.readFileSync(path.join(root, manifest.file));
assert.equal(digest(compressed), manifest.gzipSha256);
const binary = zlib.gunzipSync(compressed);
assert.equal(digest(binary), manifest.sha256);
Planetary.setEphemerisAtlas(Planetary.decodeEphemerisAtlas(binary, manifest));
const catalogRoot = path.join(sharedRoot, "data/research/analysis-repairs-20261007/catalog");
const summaryPath = path.join(catalogRoot, "summary_manifest.json");
const summary = JSON.parse(fs.readFileSync(summaryPath));
const contextPath = path.join(root, "context_rows.json.gz");
const context = JSON.parse(zlib.gunzipSync(fs.readFileSync(contextPath)));
let streamedRows = 0;
const preparationStarted = performance.now();
const prepared = Planetary.preparePlanetaryCohort({ crops: context.crops, animals: context.animals,
  forEachRow(accept) {
    for (const shard of summary) {
      const rows = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(catalogRoot, "summary_shards", shard.id + ".json.gz"))));
      for (const row of rows) {
        accept({ datePrecision: row.date_precision, sortOrdinal: row.sort_date_iso ? Math.floor(Date.parse(row.sort_date_iso) / 86400000) : null,
          craftType: row.craft_type_inferred, source: row.source, type: row.type, visualTypeGroup: row.visual_type_group });
        streamedRows++;
      }
    }
  },
});
const preparationMilliseconds = performance.now() - preparationStarted;
assert.equal(streamedRows, 702893);
const started = performance.now();
const model = Planetary.computePlanetaryHeatmaps({ preparedCohort: prepared });
const coldMilliseconds = performance.now() - started;
console.log(JSON.stringify({ stage: "bulk_complete", coldMilliseconds: Math.round(coldMilliseconds), precomputation: model.precomputation }));
assert.ok(coldMilliseconds < 20000, "Cold full-catalog all-body overview exceeded the bounded20-second guard.");
let checkedCells = 0;
for (const domain of model.domains) for (const [kind, rowN, colN] of [["zodiac", 9, 12], ["motion", 9, 3], ["aspects", 36, 6]]) {
  assert.equal(domain.matrices[kind].rows.length, rowN);
  for (const entry of domain.matrices[kind].rows) {
    assert.equal(entry.cells.length, colN);
    assert.equal(entry.cells.reduce((sum, cell) => sum + cell.count, 0), domain.positionEligible);
    assert.ok(Math.abs(entry.cells.reduce((sum, cell) => sum + cell.expectedCount, 0) - domain.positionEligible) < 0.002);
    for (const cell of entry.cells) {
      checkedCells++;
      assert.ok(0 <= cell.lowerCount && cell.lowerCount <= cell.count && cell.count <= cell.upperCount && cell.upperCount <= domain.positionEligible,
        domain.id + ":" + entry.label + ":" + cell.id);
      if (cell.expectedCount === 0) assert.equal(cell.calendarAdjustedRatio, null);
    }
  }
}
const fields = ["count", "lowerCount", "upperCount", "share", "expectedCount", "expectedCalendarShare", "calendarAdjustedRatio"];
const parity = [];
for (const [planet, partner] of [["Venus", "Mars"], ["Sun", "Moon"]]) {
  const singleStarted = performance.now();
  const single = Planetary.computePlanetaryContext({ preparedCohort: prepared, planet, aspectPartner: partner, samplingMode: "common_grid" });
  for (let d = 0; d < model.domains.length; d++) {
    const bulk = model.domains[d], detail = single.domains[d];
    for (const field of ["total", "reportCount", "nonReportContextCount", "positionEligible", "distinctEligibleDates", "excluded", "dateRoles", "sourceCounts", "verifiedTimeCount"]) assert.deepEqual(bulk[field], detail[field]);
    const pairs = bulk.matrices.aspects.rows.find(entry => entry.planet === planet && entry.partner === partner);
    const aspectBins = detail.aspectPartners[0].bins.concat([detail.aspectPartners[0].outsideBand]);
    for (let c = 0; c < 6; c++) for (const field of fields) assert.equal(pairs.cells[c][field], aspectBins[c][field], `${bulk.id}:${planet}:${partner}:${field}`);
    for (const [kind, bins] of [["zodiac", detail.signBins], ["motion", detail.motion.bins]]) {
      const entry = bulk.matrices[kind].rows.find(entry => entry.planet === planet);
      for (let c = 0; c < bins.length; c++) for (const field of fields) assert.equal(entry.cells[c][field], bins[c][field]);
    }
  }
  parity.push({ planet, partner, status: "exact_common_grid_parity", milliseconds: Math.round(performance.now() - singleStarted) });
}
const prior = JSON.parse(fs.readFileSync(path.join(root, "planetary_qa.json")));
const legacyNoonParity = model.domains.map(domain => {
  const previous = prior.domains.find(entry => entry.id === domain.id);
  const bulk = domain.matrices.aspects.rows.find(entry => entry.planet === "Venus" && entry.partner === "Mars");
  const previousCells = previous.aspectPartners[0].bins.concat([previous.aspectPartners[0].outsideBand]);
  const countDeltas = bulk.cells.map((cell, i) => cell.count - previousCells[i].count);
  assert.ok(countDeltas.every(delta => delta === 0), "Default noon counts changed against retained prior receipt.");
  return { id: domain.id, countDeltas, previousEstimator: "adaptive", boundsEstimator: "common_grid",
    boundDifferences: bulk.cells.map((cell, i) => ({ id: cell.id, lowerDelta: cell.lowerCount - previousCells[i].lowerCount, upperDelta: cell.upperCount - previousCells[i].upperCount })) };
});
const warmStarted = performance.now();
const warm = Planetary.computePlanetaryHeatmaps({ preparedCohort: prepared });
const warmMilliseconds = performance.now() - warmStarted;
assert.deepEqual(warm.domains, model.domains);
const receipt = { schemaId: "ufo-planetary-heatmaps-qa-v1", status: "passed", generatedAt: new Date().toISOString(),
  estimatorVersion: model.estimatorVersion, samplingMode: model.samplingMode, sharedCatalogRows: streamedRows,
  preparedCohort: { inputRows: prepared.inputRows, foldedGroupN: prepared.foldedGroupN, preparationMilliseconds: Math.round(preparationMilliseconds), rawCorpusRetained: false },
  timings: { coldFullOverviewMilliseconds: Math.round(coldMilliseconds), warmFullOverviewMilliseconds: Math.round(warmMilliseconds), scope: "All retained records; browser filtered-cohort timing is separate." },
  dimensions: { bodies: 9, unorderedPairs: 36, domains: 3, cellsPerDomain: 351, checkedCells },
  domains: model.domains.map(domain => ({ id: domain.id, positionEligible: domain.positionEligible, distinctEligibleDates: domain.distinctEligibleDates,
    verifiedTimeCount: domain.verifiedTimeCount, exclusions: domain.excluded, dateRoles: domain.dateRoles, representedMonths: domain.exposure.representedMonths })),
  fullCatalogDrilldownParity: parity, retainedDefaultNoonParity: legacyNoonParity, precomputation: model.precomputation,
  checks: ["All rows partition actual eligible cohorts and calendar expectation", "All cells contain counts within sampled stable/possible limits",
    "Two full-catalog drilldowns preserve every count, bound, ratio and source/date-role denominator", "Focused test covers all36 pair drilldowns and reverse-pair symmetry",
    "Cell-specific and row-union within-month opportunity retained", "No frozen report counts, atlas copy or corpus copy created"],
  inputs: [{ path: summaryPath, sha256: digest(fs.readFileSync(summaryPath)) }, { path: contextPath, sha256: digest(fs.readFileSync(contextPath)) },
    { path: "analysis_planetary.js", sha256: digest(fs.readFileSync("analysis_planetary.js")) }, { path: manifestPath, sha256: digest(fs.readFileSync(manifestPath)) }],
  storage: { canonicalEphemeris: manifest.file, newFilesAbove100MiB: [], growth: "Small engine, tests and receipt only", fullCorpusCopied: false, deploymentPerformed: false,
    purpose: "Current all-body heatmap QA receipt; rebuild with this test against shared protected catalog." } };
const output = path.join(root, "planetary_heatmaps_qa.json");
fs.writeFileSync(output, JSON.stringify(receipt, null, 2) + "\n");
console.log(JSON.stringify({ status: receipt.status, timings: receipt.timings, dimensions: receipt.dimensions, parity, receipt: output }));
