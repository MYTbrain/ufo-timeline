import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url), Query = require("../search_query.js"), CatalogSearch = require("../search_catalog.js");
const source = fs.readFileSync("app.js", "utf8").replace(/\r\n/g, "\n");
function actualFunction(name) {
  const start = source.search(new RegExp("^  (?:async )?function " + name + "\\(", "m"));
  assert.ok(start >= 0, "Missing production function " + name);
  const next = source.slice(start + 1).search(/\n  (?:async )?function \w+\(/);
  assert.ok(next >= 0, "Missing function boundary after " + name);
  return source.slice(start, start + 1 + next);
}
const clone = value => JSON.parse(JSON.stringify(value));
const complete = ids => ({ complete: true, ids, coverage: { rawPreservedText: true, metadataOverlay: true, checkedRecords: 3 } });
function fixture() {
  const catalog = [
    { event_id: 0, description: "An object nearby", location_display: "Harare", has_coordinates: false },
    { event_id: 21, description: "A humanoid carried a soil sample", location_display: "Lyon", has_coordinates: true },
    { event_id: 22, description: "A plant collection account", location_display: "Paris", has_coordinates: false },
  ];
  const viewStates = [], calls = [], created = [], destroyed = [], applied = [], captures = [], scheduled = [];
  let viewConfig, responder = async () => complete(["0", "21"]);
  const view = { state: {}, setState(patch) { this.state = { ...this.state, ...patch }; viewStates.push(clone(this.state)); } };
  const context = vm.createContext({ console, URL, AbortController, setTimeout, clearTimeout,
    performance: { now: () => 0 }, document: { baseURI: "https://example.org/tool/", getElementById: () => ({}) },
    catalog, els: { keywordInput: { value: "" } }, searchCache: new Map(), searchRuntime: null, searchRuntimeKey: "", searchView: null,
    searchAbortController: null, searchExcerptController: null, searchResult: null, searchResultRenderGeneration: 0,
    startup: { progressiveEnabled: false, fullCatalogReady: true, initialViewReady: true },
    runtime: { appConfig: { searchIndex: { manifestUrl: "./data/search/manifest.json", manifestSha256: "manifest-A" } },
      activeFilterGeneration: 1, catalogFacetWorkerRowsQueued: 3, discardedFilterGenerations: 0, renderedResultCardsByEventId: new Map() },
    state: { filterToken: 1, filterGeneration: 1, lastKeyword: "", lastKeywordMatches: null,
      filteredCatalog: [catalog[0]], filteredMappedCatalog: [], timeRangeMode: "window", timeRangeStartOrdinal: 0, timeRangeEndOrdinal: 10 },
    datasetHash: "catalog-A", analysisCatalogDatasetHash: () => context.datasetHash,
    getCatalogEventById: id => catalog.find(event => String(event.event_id) === String(id)) || null,
    setSearchStatus: () => {}, scheduleRefresh: options => scheduled.push(options),
    buildFilteredCatalogStateViaWorker: async matches => ({ matches }),
    applyFilterState(matches, options) {
      applied.push({ matches, options }); context.runtime.activeFilterGeneration = options.generation;
      context.state.filteredCatalog = matches == null ? catalog.slice() : catalog.filter(event => matches.has(event.event_id));
      context.state.filteredMappedCatalog = context.state.filteredCatalog.filter(event => event.has_coordinates); return true;
    },
    UfoSearchQuery: Query, UfoSearchCatalog: CatalogSearch,
    UfoSearchView: { create(target, config) { viewConfig = config; return view; } },
    UfoSearchRuntime: { create(config) {
      created.push(config); return { async search(plan, options) { calls.push({ plan, options }); return responder(plan, options); }, destroy() { destroyed.push(config); } };
    } },
    UfoAnalysisSessionIntegration: {
      async useSelection(payload) { captures.push({ kind: "use", payload }); return payload; },
      async captureSelection(slot, payload) { captures.push({ kind: "hold", slot, payload }); return payload; },
    },
  });
  context.window = context;
  for (const name of ["getCurrentKeyword", "serializeSearchableEvent", "searchDatasetKey", "cancelKeywordSearch", "initializeSearchTools",
    "captureSearchSelection", "publishSearchResult", "searchAcrossFullCorpus", "refreshFilters"]) vm.runInContext(actualFunction(name), context);
  function query(value, token = true) { context.els.keywordInput.value = value; if (token) context.state.filterToken += 1; }
  async function search(value) { query(value); return context.searchAcrossFullCorpus(context.getCurrentKeyword(), context.state.filterToken); }
  return { context, catalog, view, viewStates, calls, created, destroyed, applied, captures, scheduled, query, search,
    respond(callback) { responder = callback; }, get viewConfig() { return viewConfig; } };
}
async function until(predicate) {
  for (let index = 0; index < 20 && !predicate(); index += 1) await Promise.resolve();
  assert.ok(predicate(), "Expected asynchronous production search to reach the runtime");
}

const basic = fixture();
basic.respond(async (plan, options) => {
  assert.equal(plan.mode, "expression", "typed uppercase AND survives the real keyword getter");
  assert.deepEqual(plan.terms, ["humanoid", "harare"]);
  assert.deepEqual(options.supplementalMatches.harare, ["0"], "current corrected metadata is passed independently per leaf");
  assert.deepEqual(options.supplementalMatches.humanoid, ["21"]);
  assert.equal(options.metadataComplete, true); assert.equal(options.expectedRecordCount, 3);
  return complete(["0"]); // The raw text supplies humanoid; metadata supplies Harare.
});
basic.query("humanoid AND Harare"); await basic.context.refreshFilters();
assert.deepEqual([...basic.context.state.lastKeywordMatches], [0], "index strings resolve back to the numeric canonical catalog ID");
assert.equal(basic.applied.length, 1); assert.equal(basic.context.searchResult.complete, true);
assert.equal(basic.view.state.status, "complete"); assert.equal(basic.context.searchCache.size, 1);
assert.deepEqual([...basic.context.state.filteredCatalog].map(event => event.event_id), [0], "unmapped matches remain in filter results");

const fallback = fixture(); let attempts = 0;
fallback.respond(async () => { attempts += 1; if (attempts === 1) throw new Error("Fixture fragment unavailable"); return complete(["0", "21"]); });
fallback.query("soil"); await fallback.context.refreshFilters();
assert.deepEqual([...fallback.context.state.lastKeywordMatches], [21]);
assert.equal(fallback.context.searchCache.size, 0, "summary fallback never poisons the verified complete cache");
assert.equal(fallback.view.state.complete, false); assert.equal(fallback.view.state.summaryOnly, true);
assert.equal(fallback.view.state.canUseSelection, false);
await assert.rejects(fallback.context.captureSearchSelection({ query: "soil", scope: "all" }), /complete search/);
fallback.viewConfig.onRetry();
assert.equal(fallback.scheduled.length, 1); assert.equal(fallback.scheduled[0].immediate, true);
await fallback.context.refreshFilters();
assert.equal(attempts, 2, "same-query retry calls the runtime instead of using partial summary matches");
assert.equal(fallback.context.searchCache.size, 1); assert.equal(fallback.context.searchResult.complete, true);
assert.deepEqual([...fallback.context.state.lastKeywordMatches], [0, 21]);
const beforeCalls = fallback.calls.length; await fallback.context.refreshFilters();
assert.equal(fallback.calls.length, beforeCalls, "verified complete results are cached");

const syntax = fixture();
syntax.query("soil"); await syntax.context.refreshFilters();
const previous = syntax.context.state.lastKeywordMatches, appliedBefore = syntax.applied.length;
syntax.query("soil AND"); await syntax.context.refreshFilters();
assert.equal(syntax.applied.length, appliedBefore, "syntax error must not apply an empty or unfiltered population");
assert.equal(syntax.context.state.lastKeywordMatches, previous);
assert.equal(syntax.context.state.lastKeyword, "soil");
assert.equal(syntax.view.state.status, "error"); assert.match(syntax.view.state.message, /Previous results remain displayed/);

const cancelled = fixture(); let resolveOld;
cancelled.respond((plan, options) => plan.query === "old" ? new Promise(resolve => { resolveOld = resolve; }) : complete(["21"]));
const old = cancelled.search("old"); await until(() => Boolean(resolveOld));
cancelled.query("new"); cancelled.context.cancelKeywordSearch();
const newer = cancelled.context.searchAcrossFullCorpus("new", cancelled.context.state.filterToken); await newer;
resolveOld(complete(["0"])); assert.equal(await old, null);
assert.equal(cancelled.context.searchResult.query, "new"); assert.equal(cancelled.view.state.query, "new");
assert.equal(cancelled.context.searchCache.size, 1, "cancelled old requests cannot publish or cache after the new result");
cancelled.query("different"); cancelled.context.cancelKeywordSearch();
const stateBeforeStaleHit = cancelled.viewStates.length;
assert.equal(await cancelled.context.searchAcrossFullCorpus("new", cancelled.context.state.filterToken - 1), null,
  "a stale cached query cannot publish over the current input");
assert.equal(cancelled.viewStates.length, stateBeforeStaleHit);

const drift = fixture(); let resolveDrift;
drift.respond(() => new Promise(resolve => { resolveDrift = resolve; }));
const drifting = drift.search("soil"); await until(() => Boolean(resolveDrift));
drift.context.datasetHash = "catalog-replaced";
resolveDrift(complete(["0"])); assert.equal(await drifting, null);
assert.equal(drift.context.searchResult, null); assert.equal(drift.context.searchCache.size, 0,
  "dataset changes during an in-flight request cannot publish or cache obsolete coverage");

const identity = fixture(); await identity.search("soil");
const identities = [identity.context.searchDatasetKey()];
for (const mutate of [
  () => { identity.context.datasetHash = "catalog-B"; },
  () => { identity.context.runtime.appConfig.searchIndex.manifestSha256 = "manifest-B"; },
  () => { identity.context.runtime.appConfig.searchIndex.manifestUrl = "./data/search/next-manifest.json"; },
  () => { identity.context.runtime.appConfig.locationLabelOverlay = { sha256: "locations-B" }; },
  () => { identity.context.runtime.appConfig.detailQualityOverlay = { sha256: "quality-B" }; },
  () => { identity.context.runtime.appConfig.analysisRepairDetailOverlay = { sha256: "repair-B" }; },
]) {
  const callsBefore = identity.calls.length; mutate(); const nextKey = identity.context.searchDatasetKey();
  assert.ok(!identities.includes(nextKey), "dataset and overlay identity changes invalidate the complete-result cache"); identities.push(nextKey);
  await identity.search("soil"); assert.equal(identity.calls.length, callsBefore + 1);
}
assert.equal(identity.context.searchCache.size, 6, "verified report ID cache is bounded");
assert.equal(identity.created.length, 7, "dataset/config changes recreate the index runtime rather than querying its old manifest");
assert.equal(identity.destroyed.length, 6);

const capture = fixture(); capture.query("soil"); await capture.context.refreshFilters();
capture.context.state.filteredCatalog = [capture.catalog[0]];
await capture.context.captureSearchSelection({ query: "soil", scope: "current" });
assert.deepEqual([...capture.captures.at(-1).payload.eventIds], ["0"], "filtered capture includes unmapped reports");
assert.equal(capture.captures.at(-1).payload.provenance.selectionScope, "current_shared_filters");
await capture.context.captureSearchSelection({ query: "soil", scope: "all", slot: "B" });
assert.deepEqual([...capture.captures.at(-1).payload.eventIds], ["0", "21"]);
assert.equal(capture.captures.at(-1).slot, "B");
assert.equal(capture.captures.at(-1).payload.scope.timeRange.mode, "full");
await assert.rejects(capture.context.captureSearchSelection({ query: "obsolete query", scope: "all" }), /changed|current|complete search|stale/i,
  "stale action payloads must not capture a different query's reports");
capture.context.runtime.activeFilterGeneration -= 1;
await assert.rejects(capture.context.captureSearchSelection({ query: "soil", scope: "all" }), /current filters/);
capture.context.runtime.activeFilterGeneration = capture.context.state.filterGeneration;
capture.context.searchResult.datasetKey = "obsolete dataset";
await assert.rejects(capture.context.captureSearchSelection({ query: "soil", scope: "all" }), /complete search/);
capture.context.searchResult.datasetKey = capture.context.searchDatasetKey();
capture.query("new query");
await assert.rejects(capture.context.captureSearchSelection({ query: "soil", scope: "all" }), /complete search/);

console.log("Search app integration: parser input, exact metadata leaves, canonical IDs, partial retry, cancellation, cache identities, syntax preservation, and scoped complete-only Analysis captures passed.");
