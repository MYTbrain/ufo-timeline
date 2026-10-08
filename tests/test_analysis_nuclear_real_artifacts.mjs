// Reuses the protected shared repaired catalog. No corpus/bundle is copied.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { computeNuclearContext } = require('../analysis_nuclear.js');
const shared = path.resolve(process.argv[2] || 'C:/Users/jarod/Desktop/UFO Timeline map tool');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const readJson = file => JSON.parse(file.endsWith('.gz') ? zlib.gunzipSync(fs.readFileSync(file)) : fs.readFileSync(file, 'utf8'));
const sourceFile = path.join(root, 'data/analysis_comparisons/nuclear_context_v1.json');
const source = readJson(sourceFile);
const context = readJson(path.join(root, 'data/analysis_comparisons/context_rows.json.gz'));
const facetsRoot = path.join(shared, 'data/research/analysis-repairs-20261007/catalog');
const index = readJson(path.join(facetsRoot, 'summary_manifest.json'));
const facilities = readJson(path.join(shared, 'webapp/static_public/data/analysis_v2/facility_analysis_v1.json'));
const manifest = readJson(path.join(root, 'data/analysis_v2/manifest.json'));
let visited = 0;
const started = performance.now();
const result = computeNuclearContext({ ...source, crops: context.crops, animals: context.animals, facilities,
  facilityCodebook: manifest.codes.facilityAnalysis, windowDays: 30,
  forEachRow(callback) {
    const recyclable = {};
    for (const entry of index) {
      const rows = readJson(path.join(facetsRoot, 'summary_shards', entry.id + '.json.gz'));
      for (const row of rows) {
        Object.assign(recyclable, { eventId: row.event_id, source: row.source, type: row.type,
          craftType: row.craft_type_inferred, visualTypeGroup: row.visual_type_group, datePrecision: row.date_precision,
          ordinal: row.sort_date_iso ? Math.floor(Date.parse(row.sort_date_iso) / 86400000) : null,
          startOrdinal: row.date_iso ? Math.floor(Date.parse(row.date_iso) / 86400000) : null,
          endOrdinal: row.end_date_iso ? Math.floor(Date.parse(row.end_date_iso) / 86400000) : null,
          lat: row.lat, lon: row.lon, coordinateEvidenceClass: row.location_precision });
        callback(recyclable); visited += 1;
      }
    }
  },
});
assert.equal(visited, 702893);
assert.equal(result.coverage.catalogRows, 2051);
assert.equal(result.coverage.selectedTests, 1917);
assert.equal(result.coverage.excludedSafetyN, 133);
assert.ok(result.domains.ufo.exclusions.noncraft_or_nuclear_context_record >= 1985);
assert.ok(result.domains.ufo.linkedReportsN > 0);
assert.ok(result.domains.ufo.matchedControls.controlWindows > 0);
assert.ok(result.domains.ufo.matchedControls.controlPairCount > 0);
assert.equal(result.facilities.nuclearSitesN, 4);
assert.ok(result.facilities.broaderSitesN > 1000);
for (const domain of ['ufo', 'crops', 'animals']) {
  const d = result.domains[domain];
  assert.equal(d.phases.reduce((sum, x) => sum + x.pairCount, 0), d.distanceBands.reduce((sum, x) => sum + x.pairCount, 0));
  assert.equal(d.byDateRole.reduce((sum, x) => sum + x.eligibleN, 0), d.eligibleN);
  assert.equal(result.facilities.byDomain[domain].groups.reduce((sum, x) => sum + x.reportsN, 0), d.eligibleN);
  assert.ok(d.phases.every(x => x.uniqueReports <= d.linkedReportsN));
}
const receipt = { passed: true, elapsedSeconds: (performance.now() - started) / 1000, catalogRowsVisited: visited,
  nuclearAssetSha256: createHash('sha256').update(fs.readFileSync(sourceFile)).digest('hex'),
  coverage: result.coverage, domains: Object.fromEntries(['ufo', 'crops', 'animals'].map(name => {
    const d = result.domains[name];
    return [name, { inputN: d.inputN, eligibleN: d.eligibleN, exclusions: d.exclusions, linkedReportsN: d.linkedReportsN,
      testsWithReportsN: d.testsWithReportsN, phases: d.phases, byDateRole: d.byDateRole, matchedControls: d.matchedControls }];
  })), facilities: result.facilities,
  storage: { fullCorpusCopied: false, newFilesOver100MiB: [], canonicalArtifact: 'data/analysis_comparisons/nuclear_context_v1.json',
    rollback: 'Existing production release unchanged; protected shared source artifacts retained.' } };
fs.writeFileSync(path.join(root, 'data/analysis_comparisons/nuclear_sources/runtime_qa.json'), JSON.stringify(receipt, null, 2));
console.log(JSON.stringify({ passed: true, elapsedSeconds: receipt.elapsedSeconds, catalogRowsVisited: visited,
  nuclearSitesN: result.facilities.nuclearSitesN, broaderSitesN: result.facilities.broaderSitesN,
  domains: Object.fromEntries(['ufo', 'crops', 'animals'].map(name => [name,
    { eligibleN: result.domains[name].eligibleN, linkedReportsN: result.domains[name].linkedReportsN,
      phasePairs: result.domains[name].phases.map(x => x.pairCount),
      controls: result.domains[name].matchedControls.controlPairCount }])) }, null, 2));
