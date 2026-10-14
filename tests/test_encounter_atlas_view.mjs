import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { AnalysisViewController } = require("../analysis_view.js");
class Element {
  constructor(tagName, document) {
    this.tagName = tagName; this.ownerDocument = document; this.children = []; this.attributes = new Map();
    this.events = new Map(); this.ownText = ""; this.open = false; this.value = "";
    this.style = { setProperty() {} };
    this.classList = { values: new Set(), add: (...keys) => keys.forEach((key) => this.classList.values.add(key)), contains: (key) => this.classList.values.has(key) };
  }
  appendChild(child) { this.children.push(child); child.parentNode = this; return child; }
  replaceChildren(...children) { this.children = []; this.ownText = ""; children.forEach((child) => this.appendChild(child)); }
  removeChild(child) { this.children = this.children.filter((value) => value !== child); child.parentNode = null; }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  set textContent(value) { this.ownText = String(value); this.children = []; }
  get textContent() { return this.ownText + this.children.map((child) => child.textContent).join(" "); }
  addEventListener(name, handler) { if (!this.events.has(name)) this.events.set(name, []); this.events.get(name).push(handler); }
  dispatch(name) { for (const handler of this.events.get(name) || []) handler({ target: this, preventDefault() {} }); }
}
const walk = (element) => [element, ...element.children.flatMap(walk)];
function fixture() {
  const roots = [];
  const document = {
    createElement(tagName) { return new Element(tagName, this); },
    createElementNS(_namespace, tagName) { return this.createElement(tagName); },
    getElementById(id) { return roots.flatMap(walk).find((node) => node.id === id) || null; },
  };
  const add = (id, tag = "div") => { const value = document.createElement(tag); value.id = id; roots.push(value); return value; };
  const exported = [];
  const frames = [];
  const controller = Object.create(AnalysisViewController.prototype);
  Object.assign(controller, {
    document, documentView: null, callbacks: { onExportEvidence: (value) => exported.push(value) },
    activeView: "analysis", activeSectionId: "analysis-section-encounters", resultRenderVersion: 2,
    latestResult: { summary: { activeCount: 12 }, encounters: {}, artifactHashes: { encounters: "fixturehash" } },
    latestMeta: { filterSnapshot: { filters: { encounters: { beingTypes: ["grey"] } } } },
    renderPlans: new Map(), renderedPlanVersions: new Map([["analysis-section-encounters", 2]]), deferredDisclosureJobs: new Map(),
    currentAnalysisMode: "whole_corpus_structure", requestRenderFrame: (callback) => frames.push(callback),
    _activatePreview() {}, _applyAnalysisState: (_state, message) => { throw new Error(message); },
  });
  add("analysis-encounter-atlas-chart"); add("analysis-encounter-context-chart");
  const disclosure = add("analysis-encounter-atlas-disclosure", "details");
  const contextDisclosure = add("analysis-encounter-context-disclosure", "details");
  const flush = () => { while (frames.length) frames.shift()(); };
  return { controller, document, exported, disclosure, contextDisclosure, flush, add };
}
const cell = (row, column, count) => ({ row, column, count, value: count, observedCount: count,
  share: count / 8, reportDenominator: 8, inferenceEligible: false, estimateAvailable: true, status: "descriptive_only" });
const source = { key: "source", label: "Source collection", group: "Reports", status: "ready",
  rows: [{ key: "grey", label: "Grey" }, { key: "humanoid", label: "Humanoid" }],
  columns: [{ key: "one", label: "Collection one" }, { key: "unknown", label: "Unknown collection" }],
  cells: [cell("grey", "one", 4), cell("grey", "unknown", 1), cell("humanoid", "one", 3)],
  shareLabel: "Share of eligible being reports", fieldPolicy: "Source collections can overlap; records are not unique incidents.",
  coverage: { cohortReports: 12, eligibleReports: 8, supportedReports: 7, unknownReports: 1, notLoadedReports: 0, membershipCount: 8 } };
const hour = { key: "hour", label: "Source hour", group: "Time", status: "not_loaded",
  rows: [{ key: "grey", label: "Grey" }], columns: [{ key: "not_loaded", label: "Field not loaded" }],
  cells: [cell("grey", "not_loaded", 8)],
  shareLabel: source.shareLabel, fieldPolicy: "Clock evidence must load before hours can be classified; no noon midpoint is invented.",
  coverage: { cohortReports: 12, eligibleReports: 8, supportedReports: 0, unknownReports: 0, notLoadedReports: 8, membershipCount: 8 } };
const atlas = { status: "ready", unit: "reports", policy: "Descriptions are source claims, not verified beings.", axes: [
  source, hour, { key: "lunar", label: "Moon", status: "external_comparison", cells: [] },
] };
const { controller, document, exported, disclosure, contextDisclosure, flush } = fixture();
const axisRequests = [];
controller.callbacks.onEncounterAxisRequested = (key) => { axisRequests.push(key); return Promise.resolve(true); };
controller.latestResult.encounters.comparisonAtlas = atlas;
const before = JSON.stringify(atlas);
controller._setDeferredDisclosureJobs("analysis-encounter-atlas-disclosure", [() => controller._renderEncounterAtlas(atlas, { activeCount: 12 })],
  { sectionId: "analysis-section-encounters", targets: ["analysis-encounter-atlas-chart"] });
assert.equal(controller._renderDeferredDisclosure("analysis-encounter-atlas-disclosure"), false);
assert.equal(document.getElementById("analysis-encounter-atlas-chart").children.length, 0, "Closed comparisons must not build hidden chart DOM");
disclosure.open = true;
assert.equal(controller._renderDeferredDisclosure("analysis-encounter-atlas-disclosure"), true);
flush();
const picker = document.getElementById("analysis-encounter-axis-select");
assert.equal(picker.value, "source");
assert.equal(picker.getAttribute("aria-label"), "Compare being descriptions against");
assert.deepEqual(picker.children.map((group) => group.label), ["Reports", "Time"]);
assert.equal(walk(picker).filter((element) => element.tagName === "option").length, 2, "External comparisons have their own guarded context renderer");
assert.match(document.getElementById("analysis-encounter-axis-coverage").textContent, /Eligible being reports 8/);
assert.match(document.getElementById("analysis-encounter-axis-coverage").textContent, /Unknown field 1/);
const chart = document.getElementById("analysis-encounter-axis-chart");
assert.match(chart.textContent, /Grey|Collection one/);
assert.match(chart.textContent, /Unknown collection/);
assert.match(chart.textContent, /source reports/);
assert.doesNotMatch(chart.textContent, /above expectation|p-value|No cells qualify|Effect|physical association established/);
const tableDisclosure = walk(chart).find((element) => element.tagName === "details");
assert.ok(tableDisclosure);
assert.equal(walk(tableDisclosure).filter((element) => element.tagName === "table").length, 0, "Complete exact tables also render lazily");
tableDisclosure.open = true; tableDisclosure.dispatch("toggle");
assert.equal(walk(tableDisclosure).filter((element) => element.tagName === "table").length, 1);
assert.equal(walk(tableDisclosure).filter((element) => element.tagName === "tbody")[0].children.length, 3);
assert.match(tableDisclosure.textContent, /Share of eligible being reports/);

picker.value = "hour"; picker.dispatch("change");
assert.deepEqual(axisRequests, ["hour"], "An unloaded comparison requests its projection without visiting another topic");
const loadField = walk(document.getElementById("analysis-encounter-axis-coverage")).find((node) => node.tagName === "button" && node.textContent === "Load field evidence");
assert.ok(loadField); loadField.dispatch("click");
assert.equal(loadField.disabled, true);
await Promise.resolve(); await Promise.resolve();
assert.deepEqual(axisRequests, ["hour", "hour"]);
assert.equal(loadField.disabled, false);
const appSource = fs.readFileSync("app.js", "utf8");
const routeStart = appSource.indexOf("onEncounterAxisRequested: function (axis) {");
const routeEnd = Math.min(...["\n      onEncounterReportsRequested:", "\n      onSectionActivate:"].map((marker) => appSource.indexOf(marker, routeStart)).filter((index) => index >= 0));
const routeSource = appSource.slice(routeStart + "onEncounterAxisRequested: ".length, routeEnd).trim().replace(/,$/, "");
const routeNames = ["ensureAnalysisGeographyArtifact", "ensureAnalysisDurationArtifact", "ensureAnalysisReportingDelayArtifact", "ensureAnalysisTimeOfDayArtifact", "ensureAnalysisWitnessCountArtifact", "ensureAnalysisColorArtifact", "ensureAnalysisCoordinateEvidenceArtifact"];
const route = vm.runInNewContext("(" + routeSource + ")", Object.fromEntries(routeNames.map((name) => [name, () => name])));
for (const [key, loader] of [["country", routeNames[0]], ["region", routeNames[0]], ["source_hour", routeNames[3]], ["duration", routeNames[1]], ["reporting_delay_role", routeNames[2]], ["witnesses", routeNames[4]], ["color_role", routeNames[5]], ["coordinate_quality", routeNames[6]], ["coordinate_evidence", routeNames[6]]]) assert.equal(route(key), loader);
assert.equal(route("height"), false, "Source-sidecar height is not invented from a separate projection");
assert.match(document.getElementById("analysis-encounter-axis-coverage").textContent, /Field not loaded 8/);
assert.match(document.getElementById("analysis-encounter-axis-chart").textContent, /no noon midpoint is invented|Field not loaded/);
assert.equal(controller.encounterAxisSelection, "hour");
const csv = controller._exportEncounterAxis(hour, "csv");
assert.match(csv.text, /being_key,being_label,comparison_key/);
assert.match(csv.text, /grey,Grey,not_loaded,Field not loaded,8,1,8,hour/);
assert.match(csv.text, /""notLoadedReports"":8/);
assert.deepEqual(exported[0].package.filterSnapshot, controller.latestMeta.filterSnapshot);
const json = controller._exportEncounterAxis(source, "json");
assert.equal(JSON.parse(json.text).comparison.cells.length, 3);
assert.equal(JSON.parse(json.text).unit, "reports");
assert.equal(JSON.stringify(atlas), before, "Rendering/exporting must not mutate scientific result data");

// Selection persists across a new cohort; old UI handlers cannot render stale data.
controller.resultRenderVersion += 1;
controller._renderEncounterAtlas({ ...atlas, axes: [{ ...source, cells: [cell("grey", "one", 2)] }, hour] }, { activeCount: 4 });
assert.equal(document.getElementById("analysis-encounter-axis-select").value, "hour");
const currentText = document.getElementById("analysis-encounter-axis-chart").textContent;
picker.value = "source"; picker.dispatch("change");
assert.equal(document.getElementById("analysis-encounter-axis-chart").textContent, currentText);

// A context-only update refreshes Encounters without repainting unrelated core charts.
const contexts = [];
globalThis.UfoAnalysisComparisonsView = { renderEncounterContext: (target, value, hooks) => { contexts.push({ value, hooks }); target.textContent = "Current guarded context"; } };
controller.renderedPlanVersions.set("analysis-section-encounters", controller.resultRenderVersion);
contextDisclosure.open = false;
controller.renderAnalysisComparisonEvidence({ status: "ready", encounters: { version: "first" }, encounterPlanetary: { version: "all-planets" } });
flush();
assert.equal(contexts.length, 0, "Closed context comparisons remain lazy after background computation");
contextDisclosure.open = true;
assert.equal(controller._renderDeferredDisclosure("analysis-encounter-context-disclosure"), true); flush();
assert.equal(contexts.length, 1);
assert.equal(contexts[0].value.encounterPlanetary.version, "all-planets", "Context renderer receives the complete comparison model");
controller.renderAnalysisComparisonEvidence({ status: "ready", encounters: { version: "second" } }); flush();
assert.equal(contexts.length, 2);
assert.equal(contexts[1].value.encounters.version, "second");
controller.activeSectionId = "analysis-section-overview";
controller.renderAnalysisComparisonEvidence({ status: "ready", encounters: { version: "third" } }); flush();
assert.equal(contexts.length, 2, "A hidden Encounters topic cannot repaint its context charts");
controller.activeSectionId = "analysis-section-encounters";
controller._renderDeferredDisclosure("analysis-encounter-context-disclosure"); flush();
assert.equal(contexts.length, 3);
assert.equal(contexts[2].value.encounters.version, "third");
delete globalThis.UfoAnalysisComparisonsView;

// Render the current statistics contract as well as the focused UI fixtures;
// adding an axis must not require a separate hard-coded picker/UI change.
const stats = require("../analysis_stats.js");
const actualResult = stats.computeAnalysis({ rows: [{ eventId: "fixture", source: "fixture", craftType: "triangle",
  type: "sighting", precision: "unknown", mapped: false, datePrecision: "exact_day", sortOrdinal: stats.ordinalFromCivil(2000, 5, 6),
  encounterAbductionCode: 1, encounterBeingMask: 1, encounterCraftAssociationCode: 1 }],
  fullTimeRange: true, baselineMode: "full_catalog", quickMode: true, encounterEvidenceReady: true,
  selectedDomains: ["overview", "encounters"], datasetHash: "fixture" });
const currentAtlas = actualResult.encounters.comparisonAtlas;
assert.ok(currentAtlas && currentAtlas.axes.length >= 28);
controller.latestResult = actualResult;
controller.resultRenderVersion += 1;
controller._renderEncounterAtlas(currentAtlas, actualResult.summary);
assert.equal(walk(document.getElementById("analysis-encounter-axis-select")).filter((element) => element.tagName === "option").length,
  currentAtlas.axes.filter((axis) => axis.status !== "external_comparison").length);
assert.ok(currentAtlas.axes.some((axis) => axis.key === document.getElementById("analysis-encounter-axis-select").value));

const html = fs.readFileSync("index.html", "utf8");
for (const id of ["analysis-encounter-atlas-disclosure", "analysis-encounter-atlas-chart", "analysis-encounter-context-disclosure", "analysis-encounter-context-chart"]) {
  assert.equal(html.split('id="' + id + '"').length - 1, 1);
}
assert.match(html, /id="analysis-encounter-atlas-disclosure"[^>]*>/);
assert.doesNotMatch(html, /id="analysis-encounter-(?:atlas|context)-disclosure"[^>]*\bopen\b/);
assert.ok(html.includes('encounter_analysis.css?v=2026-10-13-encounter-map-v5'));
console.log("Encounter atlas lazy navigation, coverage, exact tables/exports, stale handlers, and active-context refresh tests passed.");
