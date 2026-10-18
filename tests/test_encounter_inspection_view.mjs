import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { AnalysisViewController } = require('../analysis_view.js');
const stats = require('../analysis_stats.js');
const context = require('../analysis_encounter_context.js');
const { renderEncounterContext } = require('../analysis_comparisons_view.js');

const walk = (node) => [node, ...node.children.flatMap(walk)];
class Element {
  constructor(tagName, document) {
    this.tagName = tagName; this.ownerDocument = document; this.children = []; this.attributes = new Map(); this.events = new Map();
    this.ownText = ''; this.value = ''; this.hidden = false; this.style = { setProperty() {} };
    this.classList = { values: new Set(), add: (...keys) => keys.forEach((key) => this.classList.values.add(key)), contains: (key) => this.classList.values.has(key) };
  }
  appendChild(child) { this.children.push(child); child.parentNode = this; return child; }
  removeChild(child) { this.children = this.children.filter((item) => item !== child); }
  replaceChildren(...children) { this.children = []; this.ownText = ''; children.forEach((child) => this.appendChild(child)); }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  set textContent(value) { this.ownText = String(value); this.children = []; }
  get textContent() { return this.ownText + this.children.map((child) => child.textContent).join(' '); }
  addEventListener(name, fn) { if (!this.events.has(name)) this.events.set(name, []); this.events.get(name).push(fn); }
  dispatch(name, extra = {}) { for (const fn of this.events.get(name) || []) fn({ target: this, preventDefault() {}, ...extra }); }
  click() { this.dispatch('click'); }
  focus() { this.ownerDocument.activeElement = this; this.dispatch('focus'); }
}
function fixture() {
  const roots = [];
  const document = { createElement(tag) { return new Element(tag, this); },
    getElementById(id) { return roots.flatMap(walk).find((node) => node.id === id) || null; } };
  const add = (id) => { const node = document.createElement('div'); node.id = id; roots.push(node); return node; };
  const controller = Object.create(AnalysisViewController.prototype);
  const calls = [], opens = [], applies = [], settings = [], exports = [];
  Object.assign(controller, { document, documentView: null, resultRenderVersion: 1, latestResult: null,
    latestMeta: { filterSnapshot: { start: '2000-01-01', end: '2000-12-31', source: ['A', 'B'] } }, callbacks: {
      onEncounterReportsRequested(query, options) { return new Promise((resolve, reject) => calls.push({ query, options, resolve, reject })); },
      onEncounterReportOpen: (value) => opens.push(value), onEncounterSelectionApply: (value) => applies.push(value),
      onEncounterSettingsChange: (value) => settings.push(value), onExportEvidence: (value) => exports.push(value),
    }, currentAnalysisMode: 'whole_corpus_structure', _activatePreview() { throw new Error('Inspection must not activate a map/filter preview'); } });
  add('analysis-encounter-atlas-chart'); add('analysis-encounter-context-chart'); add('analysis-encounter-report-inspector').hidden = true;
  return { controller, document, calls, opens, applies, settings, exports, add };
}
const picker = (node, label) => walk(node).find((item) => item.tagName === 'select' && item.getAttribute('aria-label') === label);
const button = (node, text) => walk(node).find((item) => item.tagName === 'button' && item.textContent === text);
const tick = async () => { for (let i = 0; i < 4; i++) await Promise.resolve(); };
const change = (node, label, value) => { const select = picker(node, label); assert.ok(select, label); select.value = value; select.dispatch('change'); };
const base = { type: 'sighting', datePrecision: 'exact_day', precision: 'unknown', mapped: false, craftType: 'triangle',
  sortOrdinal: stats.ordinalFromCivil(2000, 5, 6), encounterCraftAssociationCode: 1, encounterEvidenceReady: true };
const result = stats.computeAnalysis({ rows: [
  { ...base, eventId: 'a', source: 'A', encounterBeingMask: 3, encounterAbductionCode: 1 },
  { ...base, eventId: 'b', source: 'A', encounterBeingMask: 1, encounterAbductionCode: 2 },
  { ...base, eventId: 'c', source: 'B', encounterBeingMask: 1, encounterAbductionCode: 0 },
  { ...base, eventId: 'd', source: 'B', encounterBeingMask: 2, encounterAbductionCode: 0 },
  { ...base, eventId: 'e', source: 'B', encounterBeingMask: 0, encounterAbductionCode: 2 },
], fullTimeRange: true, baselineMode: 'full_catalog', quickMode: true, encounterEvidenceReady: true,
  selectedDomains: ['overview', 'encounters'], datasetHash: 'fixture' });
const f = fixture(), { controller, document, calls, opens, applies, settings } = f;
controller.latestResult = result; controller.encounterAxisSelection = 'source';
controller._renderEncounterAtlas(result.encounters.comparisonAtlas, result.summary);
const atlasTarget = document.getElementById('analysis-encounter-atlas-chart');
assert.equal(picker(atlasTarget, 'Encounter population').value, 'being');
assert.ok(picker(atlasTarget, 'Encounter evidence').children.find((item) => item.value === 'source_fields').disabled,
  'Collection identity cannot proxy unavailable being-label provenance');
change(atlasTarget, 'Heatmap value', 'rowShare');
const sourceAxis = result.encounters.comparisonAtlas.populations.being.axes.find((axis) => axis.key === 'source');
const selectedCell = sourceAxis.cells.find((cell) => cell.row === 'grey' && cell.column === 'A');
assert.equal(selectedCell.count, 2); assert.equal(selectedCell.rowReportDenominator, 3); assert.equal(selectedCell.columnReportDenominator, 2);
const chart = document.getElementById('analysis-encounter-axis-chart');
assert.match(chart.textContent, /66\.7%/); assert.match(chart.textContent, /2 reports/);
const clicked = walk(chart).find((item) => item.tagName === 'button' && item.getAttribute('aria-label')?.startsWith('Grey, A:'));
assert.ok(clicked);
document.getElementById('analysis-encounter-axis-chart-cell-0-0').focus();
document.getElementById('analysis-encounter-axis-chart-cell-0-0').dispatch('keydown', { key: 'ArrowRight' });
assert.equal(document.activeElement.id, 'analysis-encounter-axis-chart-cell-0-1');
assert.equal(walk(chart).filter((node) => node.tagName === 'button' && node.tabIndex === 0).length, 1, 'The core grid has one roving tab stop');
clicked.click(); await tick();
assert.equal(calls.length, 1, 'A cell click sends exactly one original-report query');
assert.equal(calls[0].query.bucket, 'cell'); assert.equal(calls[0].query.domain, 'core'); assert.equal(calls[0].query.axisKey, 'source');
assert.equal(calls[0].query.rowKey, 'grey'); assert.equal(calls[0].query.columnKey, 'A'); assert.equal(calls[0].query.limit, 25);
assert.equal(opens.length, 0); assert.equal(applies.length, 0);
const inspector = document.getElementById('analysis-encounter-report-inspector');
assert.equal(inspector.hidden, false); assert.match(inspector.textContent, /66\.7%.*3 eligible.*100%.*2 eligible/);
assert.match(inspector.textContent, /confidence intervals|not confidence intervals/);
const original = (id, mapped) => ({ eventId: String(id), date_raw: '5/6/2000', location_display: '<img onerror=bad> source place', source: 'A', mapped,
  encounterRecord: { source: 'A', sourceEventId: 'original-' + id, sourceRef: { chunk: 'details/source-a.json.gz', detailIndex: id, chunkSha256: 'a'.repeat(64) },
    evidence: [{ field: 'description', ruleId: 'reported-being', excerpt: '<script>alert(1)</script> retained original text' }] } });
const resolve = (call, total, reports) => call.resolve({ status: 'ready', requestKey: call.query.requestKey, scopeKey: call.query.scopeKey,
  offset: call.query.offset, limit: call.query.limit, total, reports });
resolve(calls[0], 26, Array.from({ length: 25 }, (_, i) => original(i, i % 2 === 0))); await tick();
assert.match(inspector.textContent, /Showing 1–25 of 26 source reports/);
assert.match(inspector.textContent, /unmapped/); assert.match(inspector.textContent, /SHA-256 a{64}/);
assert.ok(inspector.textContent.includes('<script>alert(1)</script> retained original text'));
assert.equal(walk(inspector).filter((item) => ['script', 'img'].includes(item.tagName)).length, 0, 'Source strings are text nodes, never executable markup');
assert.equal(walk(inspector).filter((item) => item.tagName === 'article').length, 25);
const enrichmentTarget = document.createElement('div');
controller._appendEncounterEnrichment(enrichmentTarget, { links: [{ acceptedForRuntime: false, status: 'contradicted_hold', case: { title: '<img> Case' },
  episodes: [{ scope: 'later_recall', recallMethod: 'hypnosis', date: { raw: '1975', precision: 'year', status: 'disputed', conflicts: ['retrospective date conflict'] }, time: { raw: null, status: 'unknown', utcVerified: false } }],
  entityObservations: [{ label: 'Reported humanoid', count: null, attributes: [{ field: 'height', value: null, attribution: 'not_established' }] }],
  sourceEntries: [{ title: 'Unsafe source URL', shortExcerpt: '<script> retained quote', source: { url: 'javascript:alert(1)' } },
    { title: 'Reviewed source', locator: 'page 2', source: { url: 'https://example.org/source' } }],
  qualityReviews: [{ disposition: 'conflicting_version', rationale: 'Preserve both clocks.', findings: [{ field: 'time', text: '00:15 conflicts with 02:00 <img>.', sourceEntryId: 'new' }],
    sourceEntries: [{ entryId: 'new', locator: 'original page 15', source: { url: 'https://example.org/original' } }] }] }] });
assert.match(enrichmentTarget.textContent, /0 accepted links.*1 candidate or held/);
assert.match(enrichmentTarget.textContent, /not used as an accepted case link|contradicted/);
assert.match(enrichmentTarget.textContent, /UTC not verified|reported count —/);
assert.match(enrichmentTarget.textContent, /Additional source review/);
assert.match(enrichmentTarget.textContent, /00:15 conflicts with 02:00 <img>/);
assert.equal(walk(enrichmentTarget).filter((node) => node.tagName === 'a').length, 2);
assert.equal(walk(enrichmentTarget).find((node) => node.tagName === 'a').href, 'https://example.org/source');
assert.equal(walk(enrichmentTarget).filter((node) => ['script', 'img'].includes(node.tagName)).length, 0);
button(inspector, 'Open original report').click(); await tick(); assert.deepEqual(opens[0], { eventId: '0', mode: 'details' });
button(inspector, 'Locate on map').click(); await tick(); assert.deepEqual(opens[1], { eventId: '0', mode: 'map' });
button(inspector, 'Use these reports as filters').click(); await tick(); assert.equal(applies[0].bucket, 'cell'); assert.equal(applies[0].total, 26);
assert.equal(applies[0].offset, 0, 'Applying a drilldown scopes all matching reports, not only the current page');
button(inspector, 'Next reports').click(); await tick(); assert.equal(calls[1].query.offset, 25);
assert.equal(calls[0].options.signal.aborted, true);
resolve(calls[1], 26, [original(25, false)]); await tick();
assert.match(inspector.textContent, /Showing 26–26 of 26/); assert.equal(button(inspector, 'Next reports').disabled, true);
assert.equal(button(inspector, 'Locate on map'), undefined, 'Unmapped reports remain inspectable without a fake location action');
const openCallback = controller.callbacks.onEncounterReportOpen;
controller.callbacks.onEncounterReportOpen = () => Promise.reject(new Error('Original source detail is temporarily unavailable.'));
button(inspector, 'Open original report').click(); await tick(); await tick();
assert.match(inspector.textContent, /Original source detail is temporarily unavailable/);
assert.equal(button(inspector, 'Open original report').disabled, false, 'A failed explicit action can be retried');
controller.callbacks.onEncounterReportOpen = openCallback;
button(inspector, 'Previous reports').click(); await tick();
controller._openEncounterReports({ domain: 'core', axisKey: 'source', population: 'being', bucket: 'unknown' }, { title: 'New bucket' }); await tick();
assert.equal(calls[2].options.signal.aborted, true);
resolve(calls[2], 1, [original(999, true)]); await tick(); assert.doesNotMatch(inspector.textContent, /original-999/);
resolve(calls[3], 0, []); await tick(); assert.match(inspector.textContent, /No source reports match/); assert.equal(button(inspector, 'Use these reports as filters').disabled, true);

// Invalid response scope does not expose stale records or an enabled Apply action.
controller._openEncounterReports({ domain: 'core', axisKey: 'source', population: 'being', bucket: 'excluded' }, { title: 'Excluded records' }); await tick();
calls[4].resolve({ status: 'ready', requestKey: calls[4].query.requestKey, scopeKey: 'wrong-cohort', offset: 0, total: 1, reports: [original(999, true)] }); await tick();
assert.match(inspector.textContent, /no longer matches/); assert.doesNotMatch(inspector.textContent, /original-999/); assert.ok(button(inspector, 'Retry reports'));
button(inspector, 'Retry reports').click(); await tick(); controller.resultRenderVersion += 1;
resolve(calls[5], 1, [original(1000, true)]); await tick(); assert.doesNotMatch(inspector.textContent, /original-1000/);
controller._closeEncounterReports(); assert.equal(inspector.hidden, true);

// Source vs narrative controls are computed and available for the abduction population.
controller._renderEncounterAtlas(result.encounters.comparisonAtlas, result.summary);
change(atlasTarget, 'Encounter population', 'abduction');
assert.equal(picker(atlasTarget, 'Encounter evidence').children.find((item) => item.value === 'source_fields').disabled, false);
change(atlasTarget, 'Encounter evidence', 'source_fields'); assert.deepEqual(settings.at(-1), { population: 'abduction', evidenceMode: 'source_fields' });
assert.equal(picker(atlasTarget, 'Encounter evidence').value, 'all', 'The visible computed cohort label stays accurate while a different evidence mode is requested');
const requestedFields = [];
controller.callbacks.onEncounterAxisRequested = (key) => { requestedFields.push(key); return true; };
change(atlasTarget, 'Heatmap value', 'sourceStandardizedRowShare');
assert.equal(requestedFields.at(-1), 'country', 'Source/conditional comparisons request geography support without visiting another topic');
change(atlasTarget, 'Heatmap value', 'conditionalDifference');
assert.equal(requestedFields.at(-1), 'country');
assert.match(document.getElementById('analysis-encounter-axis-chart').textContent, /No cell has sufficient shared/);
assert.doesNotMatch(document.getElementById('analysis-encounter-axis-chart').textContent, /0 pp/);
assert.ok(walk(document.getElementById('analysis-encounter-axis-chart')).some((node) => node.tagName === 'button'), 'An unsupported adjusted view retains original report inspection');
const exported = controller._exportEncounterAxis(sourceAxis, 'csv');
assert.match(exported.text, /row_share,row_report_denominator,column_share,column_report_denominator/);
assert.match(exported.text, /source_sensitivity,conditional_comparison,missing_field_bounds/);
const negativeCell = { ...selectedCell, conditionalComparison: { difference: -0.15, commonSupportRate: 0.9, commonStrata: 3, estimateAvailable: true } };
controller.encounterPopulationSelection = 'being';
controller._renderEncounterAtlas({ ...result.encounters.comparisonAtlas, populations: { being: { ...result.encounters.comparisonAtlas.populations.being, axes: [{ ...sourceAxis, cells: [negativeCell] }] } } }, result.summary);
const negativeChart = document.getElementById('analysis-encounter-axis-chart');
assert.match(negativeChart.textContent, /-15 pp/);
assert.ok(walk(negativeChart).some((node) => node.classList.contains('is-negative')), 'Signed conditional differences preserve an amber negative lane');
assert.doesNotMatch(negativeChart.textContent, /0 pp/);

// Actual context engines route all five topics through the same inspector without altering map/filter state.
const unixDay = Date.parse('2000-05-06T00:00:00Z') / 86400000;
const contextRows = [{ ...base, id: 'context-a', eventId: 'context-a', startOrdinal: unixDay, endOrdinal: unixDay, lat: 0, lon: 0, source: 'A', encounterBeingMask: 1, encounterAbductionCode: 1 }];
const marker = { id: 'context-independent', startOrdinal: unixDay, endOrdinal: unixDay, datePrecision: 'exact_day', dateRole: 'report_date', lat: 0, lon: 0, sourceFamilyIds: ['independent'] };
const options = { rows: contextRows, range: { start: unixDay - 30, end: unixDay + 30 }, ordinalEpoch: 'unix_day', encounterEvidenceReady: true,
  crops: [marker], animals: [marker], nuclear: { tests: [{ id: 'test', ordinal: unixDay, lat: 0, lon: 0, role: 'weapons' }], nuclearFacilities: [] } };
const model = context.computeEncounterContext(options), planetary = context.computeEncounterPlanetary(options);
const queries = [], resets = [];
const target = document.getElementById('analysis-encounter-context-chart');
renderEncounterContext(target, { status: 'ready', encounters: model, encounterPlanetary: planetary }, {
  onInspectReports: (query, detail) => queries.push({ query, detail }), onInspectReset: () => resets.push(true),
});
for (const topic of ['lunar', 'nuclear', 'crops', 'animals', 'planetary']) {
  change(target, 'Encounter context comparison', topic);
  document.getElementById('encounter-context-cell-0-0').click();
  assert.equal(queries.at(-1).query.contextTopic, topic); assert.equal(queries.at(-1).query.domain, 'context'); assert.equal(queries.at(-1).query.rowKey, 'grey');
  assert.equal(queries.at(-1).query.bucket, 'cell'); assert.ok(queries.at(-1).detail.cell.rowReportDenominator >= 0);
  const missing = walk(target).find((item) => item.tagName === 'button' && item.textContent.startsWith('Inspect missing or ineligible evidence'));
  assert.ok(missing); missing.click(); assert.equal(queries.at(-1).query.bucket, 'unknown');
}
assert.ok(resets.length >= 5);
change(target, 'Encounter context comparison', 'nuclear');
assert.ok(walk(target).some((item) => item.tagName === 'caption' && item.textContent === 'Matched nuclear controls & common support'));
change(target, 'Encounter heatmap value', 'columnShare');
const first = document.getElementById('encounter-context-cell-0-0');
assert.ok(first.textContent === '—' || /%/.test(first.textContent), 'Unavailable normalized context values are never displayed as count-zero');
assert.match(target.textContent, /Missing denominators remain unavailable/);
const html = fs.readFileSync('index.html', 'utf8');
assert.equal(html.split('id="analysis-encounter-report-inspector"').length - 1, 1);
assert.match(html, /id="analysis-encounter-report-inspector"[^>]*hidden/);
const mismatched = fixture(); mismatched.controller.latestResult = result;
mismatched.controller._openEncounterReports({ domain: 'core', axisKey: 'source', population: 'being', bucket: 'cell' }); await tick();
const wrongSource = original(7, false); wrongSource.encounterRecord.source = 'Other collection';
resolve(mismatched.calls[0], 1, [wrongSource]); await tick();
assert.match(mismatched.document.getElementById('analysis-encounter-report-inspector').textContent, /source identity does not match/);
assert.doesNotMatch(mismatched.document.getElementById('analysis-encounter-report-inspector').textContent, /retained original text/);
console.log('Encounter populations, exact metric denominators, source-mode guards, original report pagination/provenance/actions, stale responses and all context drilldowns passed. Browser visual/accessibility verification remains pending.');
