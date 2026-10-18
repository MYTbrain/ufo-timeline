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
const snapshot = { generation: 7, requestedGeneration: 7, timeRange: { mode: "custom", startOrdinal: 100, endOrdinal: 101 },
  areaFilter: { active: false, shapes: [] } }, rows = [{ event_id: 10 }, { event_id: "20" }, { event_id: 40 }];
const scripts = [], styles = [], timers = new Map(), workerRequests = [], listeners = new Map();
let timerId = 0;
const worker = {
  addEventListener(type, callback) { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(callback); },
  removeEventListener(type, callback) { listeners.get(type)?.delete(callback); },
  postMessage(message) { workerRequests.push(message); },
  emit(type, data) { [...listeners.get(type) || []].forEach(callback => callback(type === "message" ? { data } : {})); },
};
const document = {
  getElementById: id => styles.find(item => item.id === id) || null,
  createElement: tag => ({ tagName: tag, remove() { this.removed = true; } }),
  head: { appendChild(element) { (element.tagName === "script" ? scripts : styles).push(element); } },
};
const context = vm.createContext({ runtime: { catalogFacetWorkerRowsQueued: 4, catalogFacetWorkerRequestId: 0 },
  startup: { fullCatalogReady: true }, catalog: [1, 2, 3, 4], state: { filteredCatalog: rows, lastKeywordMatches: null },
  getAnalysisFilterSnapshot: () => snapshot, ensureCatalogFacetWorker: () => worker,
  catalogFacetWorkerFilterPayload: () => ({ keywordEventIds: null, lowPrecisionValues: ["country", "unknown"], sourceMode: "all" }),
  analysisComputeCacheKey: value => JSON.stringify(value), document, window: {
    setTimeout(callback, milliseconds) { assert.equal(milliseconds, 30000); const id = ++timerId; timers.set(id, callback); return id; },
    clearTimeout(id) { timers.delete(id); },
  }, Map, Set, Promise, Error });
vm.runInContext(actualFunction("analysisSessionNeutralFilters") + actualFunction("analysisWorkerFilterPayload") +
  actualFunction("collectionStudyContext") + actualFunction("loadCollectionStudyRuntime"), context);
const reply = (request, eventIds, extra = {}) => worker.emit("message", { type: "collectionReportIdsInspected", requestId: request.requestId,
  generation: request.generation, analysisSignature: request.analysisSignature, result: { eventIds, totalMatchedAnalysisReports: 821 }, ...extra });
const clean = () => { assert.equal(timers.size, 0); assert.equal(listeners.get("message")?.size || 0, 0); assert.equal(listeners.get("error")?.size || 0, 0); };
const sparse = context.collectionStudyContext({ reportIds: ["10", "20", "30"] });
assert.equal(workerRequests.length, 1);
const request = workerRequests.at(-1); assert.equal(request.type, "inspectCollectionReportIds");
assert.deepEqual([...request.requestedEventIds], ["10", "20", "30"]);
assert.equal(request.timeRangeStartOrdinal, 100); assert.equal(request.timeRangeEndOrdinal, 101);
reply(request, ["10", "30"]);
const sparseContext = await sparse;
assert.deepEqual([...sparseContext.allowedEventIds], ["10", "30"], "qualifying unmapped Analysis report remains eligible even when absent from map Results");
assert.equal(sparseContext.totalMatchedAnalysisReports, 821); clean();
assert.equal((await context.collectionStudyContext({ allRecords: true })).allowedEventIds, null);
assert.equal((await context.collectionStudyContext({ reportIds: [] })).allowedEventIds.size, 0);
assert.equal(workerRequests.length, 1, "all-record and empty scopes avoid a worker request");
assert.equal(context.state.filteredCatalog, rows, "Collection comparison never replaces shared map/report data");
snapshot.requestedGeneration += 1;
await assert.rejects(context.collectionStudyContext({ reportIds: ["10"] }), /filters are still updating/);
snapshot.requestedGeneration = snapshot.generation;
const stale = context.collectionStudyContext({ reportIds: ["10"] });
const staleRequest = workerRequests.at(-1); snapshot.requestedGeneration += 1; reply(staleRequest, ["10"]);
await assert.rejects(stale, /Shared filters changed/); clean(); snapshot.requestedGeneration = snapshot.generation;
const changed = context.collectionStudyContext({ reportIds: ["10"] });
const changedRequest = workerRequests.at(-1); snapshot.timeRange.endOrdinal += 1; reply(changedRequest, ["10"]);
await assert.rejects(changed, /Shared filters changed/); clean();
const invalid = context.collectionStudyContext({ reportIds: ["10"] }); reply(workerRequests.at(-1), ["outside-inventory"]);
await assert.rejects(invalid, /invalid report inventory/); clean();
const failed = context.collectionStudyContext({ reportIds: ["10"] });
worker.emit("message", { type: "catalogFacetWorkerError", requestId: workerRequests.at(-1).requestId, error: "fixture worker failure" });
await assert.rejects(failed, /fixture worker failure/); clean();
const timeout = context.collectionStudyContext({ reportIds: ["10"] }); [...timers.values()][0]();
await assert.rejects(timeout, /timed out/); clean();
const workerError = context.collectionStudyContext({ reportIds: ["10"] }); worker.emit("error");
await assert.rejects(workerError, /inspection failed/); clean();
await assert.rejects(context.collectionStudyContext({ reportIds: Array(10001).fill("10") }), /inventory is invalid/);
context.startup.fullCatalogReady = false;
await assert.rejects(context.collectionStudyContext({ allRecords: true }), /complete catalog is still preparing/);
context.startup.fullCatalogReady = true;
assert.equal(scripts.length, 0, "No collection scripts are loaded during startup or scope inspection");
const first = context.loadCollectionStudyRuntime(), same = context.loadCollectionStudyRuntime();
assert.equal(first, same); assert.equal(scripts.length, 2);
scripts[0].onload(); scripts[1].onerror();
await assert.rejects(first, /component could not be downloaded/);
assert.equal(scripts[1].removed, true);
context.window.UfoAnalysisCollectionEvidence = {};
context.window.UfoAnalysisCollectionsView = {};
const retry = context.loadCollectionStudyRuntime(); assert.equal(scripts.length, 3, "Retry reuses completed scripts");
scripts[2].onload(); await retry;
assert.equal(styles.length, 1); assert.match(styles[0].href, /analysis_collections\.css/);
const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
assert.doesNotMatch(html, /<script[^>]+src=["'][^"']*analysis_collection(?:s_view|_evidence)\.js/, "Study runtime remains lazy on ordinary map visits");
assert.match(html, /id="analysis-collections-card"/);
assert.match(readFileSync(new URL("../ui/accepted-workspace/analysis-view-groups.js", import.meta.url), "utf8"), /key: "collections"/);
console.log("Collection delivery: lazy startup, sparse Analysis cohort including unmapped reports, stale/error/timeout cleanup and script retry passed.");
