import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const app = fs.readFileSync(new URL('../app.js', import.meta.url), 'utf8');
const start = app.indexOf('  function staticAssetVersionToken()');
const end = app.indexOf('  function startupDiagnosticsRequested()', start);
assert.ok(start > 0 && end > start);
const context = {URL, document: {baseURI: 'https://example.test/index.html'},
  runtime: {appConfig: {staticAssetVersion: 'mapping-recovery-20261103'}},
  APP_SHELL_RELEASE_TOKEN: '2026-11-03-mapping-recovery-v1'};
vm.createContext(context);
vm.runInContext(app.slice(start, end), context);
for (const lane of ['analysis_v1', 'analysis_v2', 'analysis_duration_v1', 'analysis_reporting_delay_v1',
  'analysis_time_of_day_v1', 'analysis_witness_count_v1', 'analysis_color_v1', 'analysis_coordinate_evidence_v1']) {
  const url = new URL(context.resolveAssetPath('./data/' + lane + '/manifest.json'));
  assert.match(url.searchParams.get('v'), /mapping-recovery/, lane + ' must invalidate a returning visitor cache');
}
const frozen = 'https://r2.example.test/releases/old/analysis_color_v1/color_projection_v1.json.gz';
assert.equal(context.resolveAssetPath(frozen), frozen, 'immutable payload URLs stay unchanged');
console.log('Mapping release manifest cache checks passed');
