import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const View = require("../analysis_collections_view.js");
const Engine = require("../analysis_collection_evidence.js");

const walk = element => [element, ...element.children.flatMap(walk)];
class Element {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName; this.ownerDocument = ownerDocument; this.children = []; this.attributes = new Map();
    this.events = new Map(); this.ownText = ""; this.value = "";
    this.style = { setProperty(key, value) { this[key] = String(value); } };
  }
  appendChild(element) { this.children.push(element); element.parentNode = this; return element; }
  append(...elements) { elements.forEach(element => this.appendChild(element)); }
  replaceChildren(...elements) { this.children = []; this.ownText = ""; this.append(...elements); }
  set textContent(value) { this.ownText = String(value); this.children = []; }
  get textContent() { return this.ownText + this.children.map(child => child.textContent).join(" "); }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  addEventListener(name, callback) { if (!this.events.has(name)) this.events.set(name, []); this.events.get(name).push(callback); }
  dispatch(name, extra = {}) { return Promise.all((this.events.get(name) || []).map(callback => callback({ target: this, currentTarget: this, preventDefault() {}, ...extra }))); }
  click() { if (this.tagName === "a") this.ownerDocument.lastDownload = this; return this.dispatch("click"); }
  focus() { this.ownerDocument.activeElement = this; }
  scrollIntoView() {}
}
function fixture() {
  const document = {
    targets: [], createElement(tag) { return new Element(tag, this); },
    getElementById(id) { return this.targets.flatMap(walk).find(element => element.id === id); },
    defaultView: { Blob, URL: {
      createObjectURL(blob) { document.exportedBlob = blob; return "blob:collection-test"; },
      revokeObjectURL(url) { document.revokedUrl = url; },
    }, setTimeout(callback) { callback(); } },
  };
  const target = document.createElement("div"); document.targets.push(target); return { document, target };
}
const all = (target, tag) => walk(target).filter(element => element.tagName === tag);
const byText = (target, tag, text) => all(target, tag).find(element => element.textContent === text);
const byClass = (target, className) => walk(target).find(element => (element.className || "").split(" ").includes(className));
const change = async (target, key, value) => { const element = walk(target).find(element => element.id === "collection-study-" + key); assert.ok(element, key); element.value = value; await element.dispatch("change"); await Promise.resolve(); };
const row = (eventId, extra = {}) => ({ eventId: String(eventId), title: "Report " + eventId, source: "ufocat", sourceId: String(eventId),
  canonicalJoinStatus: "validated_id_source_chunk_index", disposition: "direct_report", scope: "occupant_soil_plant", materials: ["soil"],
  actions: ["taking"], beingTypes: ["grey"], country: "France", location: "France", startOrdinal: 0, endOrdinal: 0, dateIso: "1970-01-01",
  datePrecision: "exact_day", craftType: "disc", craftLabel: "Disc", ...extra });
const evidence = { schemaId: Engine.SCHEMA_ID, schemaVersion: 1,
  taxonomy: { materials: [{ key: "soil", label: "Soil" }, { key: "flowers", label: "Flowers" }, { key: "minerals", label: "Minerals" }],
    actions: [{ key: "taking", label: "Taking" }, { key: "examining", label: "Examining" }] },
  reports: [row(11), row(12, { materials: ["soil", "flowers"], actions: ["taking", "examining"], beingTypes: ["grey", "humanoid"],
    dateLabel: "January 1970 (reported approximately)", sourceDatePrecision: "approximate_day", sourceDateNote: "Original source marks the nominal day approximate.",
    sourceUrls: ["https://example.org/report", "javascript:alert(1)", "file:///C:/private.txt"] }),
    row(13, { materials: ["flowers"], country: "United States", location: "Ohio", beingTypes: [], source: "nuforc" }),
    row(14, { disposition: "ambiguous" }), row(15, { scope: "minerals_only", materials: ["minerals"], country: "Japan", location: "Tokyo" }),
    row(16, { disposition: "adjacent", scope: "traces_only", materials: ["flowers"] })],
  cases: [{ caseId: "no-join", title: "Unmatched source dossier", observedBehavior: "An unjoined account", indexedReportIds: [], sources: [{ url: "https://example.org/dossier", title: "Original source" }] }],
  policy: { coding: "Fixture classification only" }, coverage: {}, provenance: {
    artifact: { gzipSha256: "a".repeat(64), decodedSha256: "b".repeat(64) },
    inputPins: [{ file: "reviewed_report_rows.json", sha256: "c".repeat(64) }],
    canonicalChunkPins: [{ chunkId: "chunk_000001", gzipSha256: "d".repeat(64) }],
  } };
const before = JSON.stringify(evidence), { target, document } = fixture();
let loads = 0, contextCalls = 0, allowed = new Set(["11", "12", "13"]);
const api = { ...Engine, load: async () => { loads++; return evidence; } };
const study = View.create(target, { evidenceApi: api, getContext: () => { contextCalls++; return { allowedEventIds: allowed,
  snapshot: { generation: contextCalls, requestedGeneration: contextCalls, timeRange: { mode: "full" } } }; } });
await Promise.all([study.load(), study.load()]);
assert.equal(loads, 1, "view load is single-flight");
assert.deepEqual(study.getModel().reports.map(report => report.eventId), ["11", "12", "13"]);
assert.match(target.textContent, /Following shared filters/);
await change(target, "metric", "share");
const flowersGrey = all(target, "button").find(element => element.title === "Flowers × Grey: 1 reports / 2 material reports");
// Labels come from the authoritative being taxonomy, so match the key count and row via title if capitalization changes.
const flowersCell = flowersGrey || all(target, "button").find(element => element.title?.startsWith("Flowers × ") && element.title.includes(": 1 reports / 2 material reports") && element.textContent === "50.0%");
assert.ok(flowersCell, "populated share uses unique material-report denominator");
await flowersCell.click();
assert.match(byClass(target, "collection-list-status").textContent, /^1 matching report representations/);
await byText(target, "button", "Export matched reports CSV").click();
assert.match(await document.exportedBlob.text(), /"12"/);
assert.doesNotMatch(await document.exportedBlob.text(), /"11"|"13"/);
const qualifiedCsv = await document.exportedBlob.text();
assert.ok(qualifiedCsv.split("\r\n")[0].includes("dateLabel,dateIso,datePrecision,sourceDatePrecision,sourceDateNote"), "CSV names canonical and source-qualified date columns separately");
assert.match(qualifiedCsv, /"exact_day","approximate_day","Original source marks the nominal day approximate\."/, "CSV preserves canonical precision and source qualification together");
assert.equal(all(target, "a").filter(link => link.href?.startsWith("https://example.org/report")).length, 1);
assert.equal(all(target, "a").filter(link => /^(javascript|file):/.test(link.href || "")).length, 0, "unsafe links omitted");
const search = document.getElementById("collection-study-search");
search.value = "Report 13"; await search.dispatch("input");
assert.match(byClass(target, "collection-list-status").textContent, /^0 matching report representations/, "search intersects the selected cell");
await byText(target, "button", "Export matched reports CSV").click();
assert.equal((await document.exportedBlob.text()).split("\r\n").length, 1, "CSV with no displayed matches contains only headers");
await byText(target, "button", "Clear cell selection").click();
assert.match(byClass(target, "collection-list-status").textContent, /^1 matching report representations/, "clearing a cell retains the list search");
await byText(target, "button", "Export matched reports CSV").click();
assert.match(await document.exportedBlob.text(), /"13"/);
assert.doesNotMatch(await document.exportedBlob.text(), /"11"|"12"/, "CSV export follows the same search as displayed reports");
await byText(target, "button", "Export comparison JSON").click();
const searchedComparison = JSON.parse(await document.exportedBlob.text());
assert.equal(searchedComparison.listFiltersDoNotChangeMatrices, true);
assert.equal(searchedComparison.filters.query, "report 13");
assert.deepEqual(searchedComparison.reportIds, ["11", "12", "13"], "comparison export retains the full statistical cohort while declaring the separate list search");
search.value = ""; await search.dispatch("input");
for (const axis of ["action", "decade", "country", "source", "craft", "abduction"]) {
  await change(target, "axis", axis);
  const populated = all(target, "button").find(element => element.className === "collection-heatmap-cell" && !element.disabled);
  assert.ok(populated, axis + " populated cell");
  const count = Number(populated.title.match(/: ([\d,]+) reports/)[1].replaceAll(",", ""));
  await populated.click();
  assert.ok(byClass(target, "collection-list-status").textContent.startsWith(count.toLocaleString() + " matching report representations"), axis + " drill-down matches cell count");
  await byText(target, "button", "Clear cell selection").click();
}
await byText(target, "button", "Source dossiers & controls").click();
assert.match(byClass(target, "collection-list-status").textContent, /1 source dossiers.*full inventory/);
assert.match(target.textContent, /No accepted catalog association/);
await byText(target, "button", "Matched reports").click();
await byText(target, "button", "Export comparison JSON").click();
const exported = JSON.parse(await document.exportedBlob.text());
assert.equal(exported.countUnit, "catalog report representations");
assert.deepEqual(exported.reportIds, ["11", "12", "13"]);
assert.ok(exported.matrices.being);
assert.deepEqual(exported.provenance, evidence.provenance, "export retains exact artifact identity, input pins and canonical chunk pins");
assert.equal(exported.listFiltersDoNotChangeMatrices, true);
assert.equal(document.revokedUrl, "blob:collection-test");
await change(target, "cohort", "all");
assert.equal(study.getModel().reports.length, 3, "all scope still uses soil/plant and direct disposition");
await change(target, "scope", "allmaterials");
assert.equal(study.getModel().reports.length, 4);
await change(target, "disposition", "allcontexts");
assert.equal(study.getModel().reports.length, 6);
await change(target, "cohort", "shared");
allowed = new Set(); await study.refresh();
assert.equal(study.getModel().reports.length, 0, "empty shared cohort must not become the full study");
assert.equal(byClass(target, "collection-empty").hidden, false);
assert.equal(JSON.stringify(evidence), before, "view never mutates source evidence");

const failureFixture = fixture(); let fail = true, attempts = 0;
const retryStudy = View.create(failureFixture.target, { evidenceApi: { ...Engine, load: async () => { attempts++; if (fail) throw new Error("network fixture"); return evidence; } } });
await assert.rejects(retryStudy.load(), /network fixture/); fail = false; await retryStudy.load();
assert.equal(attempts, 2, "failed artifact load can be retried");
assert.ok(retryStudy.getModel());

const contextFixture = fixture(); let contextFails = true;
const contextStudy = View.create(contextFixture.target, { evidenceApi: api, getContext: () => {
  if (contextFails) throw new Error("shared filters are still updating");
  return { allowedEventIds: new Set(["11"]), snapshot: { timeRange: { mode: "full" } } };
} });
await assert.rejects(contextStudy.load(), /shared filters are still updating/, "initial context failure reaches the outer load/retry handler");
assert.equal(contextStudy.getModel(), null);
contextFails = false; await contextStudy.load(); assert.equal(contextStudy.getModel().reports.length, 1);
contextFails = true; await contextStudy.refresh();
assert.equal(contextStudy.getModel(), null, "a failed refresh must not leave an actionable stale cohort");
assert.equal(byClass(contextFixture.target, "collection-matrix-container").hidden, true);
assert.equal(byClass(contextFixture.target, "collection-exports").hidden, true);
const refreshControl = byText(contextFixture.target, "button", "Refresh collection view");
assert.equal(refreshControl.hidden, false);
contextFails = false; await refreshControl.click();
assert.equal(contextStudy.getModel().reports.length, 1);
assert.equal(byClass(contextFixture.target, "collection-exports").hidden, false);
assert.equal(refreshControl.hidden, true);

const asyncFixture = fixture(); let resolver;
const asyncStudy = View.create(asyncFixture.target, { evidenceApi: api, getContext: () => resolver ? { allowedEventIds: new Set(["13"]) }
  : new Promise(resolve => { resolver = resolve; }) });
const olderLoad = asyncStudy.load(); await Promise.resolve(); await Promise.resolve();
await asyncStudy.refresh();
assert.deepEqual(asyncStudy.getModel().reports.map(report => report.eventId), ["13"]);
resolver({ allowedEventIds: new Set(["11"]) }); await olderLoad;
assert.deepEqual(asyncStudy.getModel().reports.map(report => report.eventId), ["13"], "late context completion cannot replace a newer filter cohort");

assert.equal(View.safeUrl("javascript:alert(1)"), null);
assert.equal(View.safeUrl("file:///C:/private.txt"), null);
assert.equal(View.csvValue("=SUM(1,2)"), '"\'=SUM(1,2)"');
console.log("Collection view: material denominators, seven-axis drill-downs, filter generations, stale async/error recovery, dossier separation, searched/qualified/pinned exports and safe links passed.");
