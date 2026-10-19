import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import { webcrypto } from 'node:crypto';

const require = createRequire(import.meta.url);
const helper = require('../ufocat_references.js');
const app = readFileSync(new URL('../app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const source = app.slice(app.indexOf('  function isHttpUrl(value)'), app.indexOf('  function renderLinkList(event)'));
const context = { URL, UFOCAT_REFERENCES: helper };
runInNewContext(source, context);
const event = { source: 'ufocat', references: ['Original retained reference'], links: [],
  extra_data: { canonical: { raw_fields: { SOURCE: 'TPhillips1', PAGEVOL: '494', ISOURCE: 'TPhillips1', IPAGEVOL: '079' } } } };
const before = JSON.stringify(event);
const entries = context.detailLinkEntries(event);
assert.equal(entries.length, 1, 'direct and indirect citations link to the same book only once');
assert.equal(entries[0].url, 'https://cufos.org/PDFs/books/Physical_Traces.pdf');
assert.doesNotMatch(entries[0].url, /#page=/, 'case numbers never become fabricated book pages');
const references = helper.references(event);
assert.equal(references.length, 3);
assert.match(references[1], /case 494/);
assert.match(references[2], /page or case number unverified/);
assert.equal(references[0], 'Original retained reference');
assert.equal(JSON.stringify(event), before, 'reading source citations never rewrites dates, coordinates or source data');
assert.equal(context.detailLinkEntries({ source: 'nuforc', raw_fields: { SOURCE: 'TPhillips1' } }).length, 0);
assert.equal(context.detailLinkEntries({ source: 'ufocat', raw_fields: { AUTHOR: 'PhillipsTedR' } }).length, 0);
assert.equal(context.detailLinkEntries({ ...event, links: [entries[0].url] }).length, 1);
const fallback = { URL, UFOCAT_REFERENCES: undefined };
runInNewContext(source, fallback);
assert.equal(fallback.detailLinkEntries(event).length, 0, 'missing optional helper preserves original link behavior');
assert.match(app, /formatList\(UFOCAT_REFERENCES \? UFOCAT_REFERENCES\.references\(event\) : \(event\.references \|\| \[\]\)\)/);
assert.ok(html.indexOf('src="./ufocat_references.js?') < html.indexOf('src="./app.js?'));
assert.match(app, /const UFOCAT_REFERENCES = window\.UfoUfocatReferences;/);
const manifest = JSON.parse(readFileSync(new URL('../data/source_citations/manifest.json', import.meta.url), 'utf8'));
const compressed = readFileSync(new URL('../data/source_citations/phillips.json.gz', import.meta.url));
const loaderSource = app.slice(app.indexOf('  async function enrichEventSourceCitations(event)'), app.indexOf('  async function openFullEventView(eventId, options)'));
const member = { source_name: 'ufocat', source_file: 'ufocat2023.csv', source_native_id: '64419', source_row_number: 21,
  source_row_hash: 'c1f91dc24b122570bade1ffe31fa3cfd30ca8a22', canonical_input_id: 'cin_e0a87523012682f7306acbcd' };
const merged = { event_id: 889027367562998, canonical_event_id: 'evt_04b9763b9f6e02939a8ca22d', source: 'majestic',
  canonical_input_ids: [member.canonical_input_id], source_provenance: [member] };
function loaderFixture(bytes = compressed) {
  const calls = [], warnings = [];
  const c = { UFOCAT_REFERENCES: helper, sourceCitationIndexPromise: null, browserCanDecodeGzipJson: () => true,
    window: { crypto: webcrypto }, Response, Blob, DecompressionStream, TextDecoder, Uint8Array,
    resolveAssetPath: path => path, fetchJson: async path => { calls.push(path); return manifest; },
    fetch: async path => { calls.push(path); return new Response(bytes); }, console: { warn: (...args) => warnings.push(args) } };
  runInNewContext(loaderSource, c);
  return { c, calls, warnings };
}
const lazy = loaderFixture();
assert.equal(lazy.calls.length, 0, 'initial map/startup never requests the optional citation data');
const restored = await Promise.all([lazy.c.enrichEventSourceCitations(merged), lazy.c.enrichEventSourceCitations(merged)]);
assert.equal(lazy.calls.length, 2, 'one manifest and one payload shared across concurrent detail requests');
assert.match(helper.references(restored[0])[0], /Ted Phillips.*investigation files/);
assert.equal(helper.referenceEntries(restored[1]).filter(entry => entry.sourceCode === 'TPhillips').length, 1);
assert.deepEqual(helper.references(restored[0]), helper.references(restored[1]));
const bad = loaderFixture(Buffer.from('invalid payload'));
assert.equal(await bad.c.enrichEventSourceCitations(merged), merged, 'integrity failure preserves the original detail record');
assert.equal(await bad.c.enrichEventSourceCitations(merged), merged);
assert.equal(bad.calls.length, 2, 'a failed optional load does not trigger repeated requests');
assert.equal(bad.warnings.length, 1);
const assetSource = app.slice(app.indexOf('  function shouldVersionStaticAsset(url)'), app.indexOf('  function startupDiagnosticsRequested()'));
const assets = { URL, document: { baseURI: 'https://preview.test/' }, APP_SHELL_RELEASE_TOKEN: 'current-shell', staticAssetVersionToken: () => 'old-data' };
runInNewContext(assetSource, assets);
assert.equal(new URL(assets.resolveAssetPath('./data/source_citations/manifest.json')).searchParams.get('v'), 'current-shell');
assert.equal(new URL(assets.resolveAssetPath('./data/source_citations/phillips.json.gz')).searchParams.get('v'), 'current-shell');

const viewSource = app.slice(app.indexOf('  async function openFullEventView(eventId, options)'), app.indexOf('  async function selectEvent(eventId, options)'));
const clearSource = app.slice(app.indexOf('  function clearSelectedEventState(options)'), app.indexOf('  function syncVisibleResultCardSelection(eventId)'));
const pending = new Map(), rendered = [], busy = new Set();
const view = { state: {}, detailLoadGeneration: 0, runtime: {},
  getCatalogEventById: id => ({ event_id: id }), closeMapDescriptionPanel() {}, setPanelCollapsed() {}, setSelectedEventId() {},
  renderDetail: value => rendered.push(value), renderDetailLoading() {}, setBusyState: key => busy.add(key), clearBusyState: key => busy.delete(key),
  ensureFullEventLoaded: id => new Promise(resolve => pending.set(id, resolve)), enrichEventSourceCitations: async value => value,
  renderDetailError() { throw new Error('Unexpected detail failure'); }, renderResults() {}, renderMapSelectionOverlay() {}, console };
runInNewContext(viewSource + clearSource, view);
const first = view.openFullEventView('A'), second = view.openFullEventView('B');
pending.get('A')({ event_id: 'A' }); await first;
assert.equal(rendered.length, 0, 'late A cannot replace the selected B');
assert.ok(busy.has('detailLoad'), 'late A cannot clear the current B busy operation');
pending.get('B')({ event_id: 'B' }); await second;
assert.equal(rendered[0].event_id, 'B'); assert.equal(busy.size, 0);
const clearing = view.openFullEventView('C'); view.clearSelectedEventState();
assert.equal(busy.size, 0, 'clearing the selected detail cancels its busy state immediately');
pending.get('C')({ event_id: 'C' }); await clearing;
assert.equal(rendered.at(-1), null, 'the late cleared detail remains cleared');
console.log('UFOCAT references integration: guarded lazy loading, integrity fallback, source-owned links, cache versions, stale detail requests and selection clearing passed.');
