import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
const source = readFileSync(new URL("../app.js", import.meta.url), "utf8").replace(/\r\n/g, "\n");
function actualFunction(name) {
  const start = source.search(new RegExp("^  (?:async )?function " + name + "\\(", "m"));
  assert.ok(start >= 0);
  const next = source.slice(start + 1).search(/\n  (?:async )?function \w+\(/);
  assert.ok(next >= 0); return source.slice(start, start + 1 + next);
}
const snapshot = { generation: 7, requestedGeneration: 7 }, rows = [{ event_id: 10 }, { event_id: "20" }, { event_id: 40 }];
const scripts = [], styles = [], document = {
  getElementById: id => styles.find(item => item.id === id) || null,
  createElement: tag => ({ tagName: tag, remove() { this.removed = true; } }),
  head: { appendChild(element) { (element.tagName === "script" ? scripts : styles).push(element); } },
};
const context = vm.createContext({ runtime: { catalogFacetWorkerRowsQueued: 4 }, startup: { fullCatalogReady: true }, catalog: [1, 2, 3, 4], state: { filteredCatalog: rows }, getAnalysisFilterSnapshot: () => snapshot, document, window: {}, Map, Set, Promise, Error });
vm.runInContext(actualFunction("collectionStudyContext") + actualFunction("loadCollectionStudyRuntime"), context);
assert.deepEqual([...context.collectionStudyContext({ reportIds: ["10", "20", "30"] }).allowedEventIds], ["10", "20"]);
assert.equal(context.collectionStudyContext({ allRecords: true }).allowedEventIds, null);
assert.equal(context.state.filteredCatalog, rows, "Collection comparison never replaces shared map/report data");
snapshot.requestedGeneration += 1;
assert.throws(() => context.collectionStudyContext({ reportIds: ["10"] }), /filters are still updating/, "Old cohort IDs cannot acquire newly requested dates");
snapshot.requestedGeneration = snapshot.generation;
context.startup.fullCatalogReady = false;
assert.throws(() => context.collectionStudyContext({ allRecords: true }), /complete catalog is still preparing/);
context.startup.fullCatalogReady = true;
assert.equal(scripts.length, 0, "No collection scripts are loaded during startup or scope inspection");
const first = context.loadCollectionStudyRuntime(), same = context.loadCollectionStudyRuntime();
assert.equal(first, same); assert.equal(scripts.length, 2);
scripts[0].onload(); scripts[1].onerror();
await assert.rejects(first, /component could not be downloaded/);
assert.equal(scripts[1].removed, true);
context.window.UfoAnalysisCollectionEvidence = {};
context.window.UfoAnalysisCollectionsView = {};
const retry = context.loadCollectionStudyRuntime(); assert.equal(scripts.length, 3, "A retry reuses the completed script and retries only the failed component");
scripts[2].onload(); await retry;
assert.equal(styles.length, 1); assert.match(styles[0].href, /analysis_collections\.css/);
const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
assert.doesNotMatch(html, /<script[^>]+src=["'][^"']*analysis_collection(?:s_view|_evidence)\.js/, "Study runtime remains lazy on ordinary map visits");
assert.match(html, /id="analysis-collections-card"/);
assert.match(readFileSync(new URL("../ui/accepted-workspace/analysis-view-groups.js", import.meta.url), "utf8"), /key: "collections"/);
console.log("Collection delivery: no startup fetch, shared-filter generation guard, sparse cohort intersection, single-flight and partial-failure retry passed.");
