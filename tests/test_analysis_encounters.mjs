import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const stats = require("../analysis_stats.js");
const { AnalysisViewController, buildEvidencePackage } = require("../analysis_view.js");
const day = (year, month = 1, date = 1) => stats.ordinalFromCivil(year, month, date);
const base = { type: "sighting", precision: "unknown", mapped: false, craftConfidence: "unknown", datePrecision: "exact_day" };
const row = (id, year, source, craftType, encounterAbductionCode, encounterBeingMask, encounterCraftAssociationCode, extra = {}) => ({
  ...base, eventId: id, sortOrdinal: year == null ? null : day(year), source, craftType,
  encounterAbductionCode, encounterBeingMask, encounterCraftAssociationCode, ...extra,
});
const rows = [
  row("a", 2000, "one", "triangle", 1, (1 << 0) | (1 << 6), 1),
  row("b", 2000, "one", "disc", 2, 1 << 0, 2),
  row("c", 2001, "two", "unknown", 0, 1 << 18, 1),
  row("d", 2001, "two", "triangle", 3, 1 << 12, 0),
  row("e", 2002, "two", "unknown", 0, 0, 0),
  row("f", null, "one", "disc", 1, 1 << 8, 2, { datePrecision: "unknown" }),
  row("g", 2000, "one", "disc", 2, 1 << 5, 2, { datePrecision: "year", dateStartOrdinal: day(2000), dateEndOrdinal: day(2001, 12, 31) }),
  row("h", 1999, "one", "disc", 0, 1 << 7, 3),
];
const settings = { rows, fullTimeRange: true, baselineMode: "full_catalog", quickMode: true,
  selectedDomains: ["overview", "encounters"], encounterEvidenceReady: true, datasetHash: "fixture" };
const result = stats.computeAnalysis(settings);
const data = result.encounters;
assert.equal(result.encounterEvidenceReady, true);
assert.equal(result.encounterTaxonomy.length, 19);
assert.equal(data.catalogRows, 8);
assert.equal(data.abductionRows, 4);
assert.equal(data.ambiguousAbductionRows, 1);
assert.equal(data.beingRows, 7);
assert.equal(data.craftAssociatedRows, 5);
assert.equal(data.explicitCraftRows, 2);
assert.equal(data.coReportedCraftRows, 3);
assert.deepEqual(data.abductionProfile.map((item) => item.count), [3, 2, 2, 1]);
assert.equal(data.beingProfile.find((item) => item.key === "grey").count, 2);
assert.equal(data.beingProfile.find((item) => item.key === "unspecified").count, 1);
assert.equal(data.craftMatrix.reduce((count, item) => count + item.count, 0), 6, "multi-label descriptions count once per cell, not once per label match");
assert.equal(data.craftMatrix.find((item) => item.row === "unspecified" && item.column === "unknown").count, 1);
assert.ok(!data.craftMatrix.some((item) => item.row === "luminous" || item.row === "small_humanoid"), "unestablished and no-craft relations do not enter the matrix");
assert.ok(data.craftMatrix.every((item) => item.inferenceEligible === false));
assert.equal(data.undatedAbductionRows, 2, "an interval spanning years must not enter an invented year");
assert.equal(data.undatedBeingRows, 2);
assert.deepEqual(data.annualActivity[0].points.map((point) => [point.label, point.count]), [["1999", 0], ["2000", 2], ["2001", 0]]);
assert.equal(data.sourceCoverage.find((item) => item.source === "two").total, 3);
assert.equal(data.sourceCoverage.find((item) => item.source === "two").count, 2);

const filtered = stats.computeAnalysis({ ...settings, matchesNonDateFilters: (item) => item.source === "two" });
assert.equal(filtered.encounters.catalogRows, 3);
assert.equal(filtered.encounters.beingRows, 2);
assert.equal(filtered.encounters.abductionRows, 0);
const ranged = stats.computeAnalysis({ ...settings, fullTimeRange: false, timeRangeStartOrdinal: day(2000), timeRangeEndOrdinal: day(2000, 12, 31), baselineMode: "other_dates_balanced" });
assert.equal(ranged.encounters.catalogRows, 3, "partial dates retain the same overlap membership as the main cohort");
assert.equal(ranged.encounters.abductionRows, 3);
const fullPath = stats.computeAnalysis({ ...settings, selectedDomains: ["craft", "encounters"] });
assert.deepEqual(fullPath.encounters, data, "quick-core and full-row accumulation must agree");
const unavailable = stats.computeAnalysis({ ...settings, encounterEvidenceReady: false });
assert.equal(unavailable.encounters.status, "loading");
assert.deepEqual(unavailable.encounters.abductionProfile, [], "loading evidence never appears as zero classified reports");
const exported = buildEvidencePackage(result, {}).evidenceRows.filter((item) => item.section.startsWith("encounters."));
assert.ok(exported.some((item) => item.section === "encounters.craftMatrix" && item.active_n === 1));
assert.ok(exported.every((item) => item.adjusted_effect === "" && item.low_support === false), "descriptive report counts are not exported as adjusted effects or failed inference");

class Element {
  constructor(tagName = "div") {
    this.tagName = tagName; this.children = []; this.attributes = new Map(); this.textContent = "";
    this.style = { values: new Map(), setProperty: (key, value) => this.style.values.set(key, value) };
    this.classList = { values: new Set(), add: (...names) => names.forEach((name) => this.classList.values.add(name)), contains: (name) => this.classList.values.has(name) };
  }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.children = children; }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  addEventListener() {}
}
const elements = new Map([["matrix", new Element()]]);
const controller = Object.create(AnalysisViewController.prototype);
const tables = [];
Object.assign(controller, {
  document: { getElementById: (id) => elements.get(id) ?? null, createElement: (tag) => new Element(tag), createElementNS: (_ns, tag) => new Element(tag) },
  currentAnalysisMode: "whole_corpus_structure", _appendLazyDataTable: (_container, caption, headings, tableRows) => tables.push({ caption, headings, rows: tableRows }),
  _appendChartPolicy() {},
  _appendDataTable() {}, _activatePreview() {}, latestResult: result,
});
const createElement = (tag) => { const element = new Element(tag); element.ownerDocument = controller.document; return element; };
controller.document.createElement = createElement;
controller.document.createElementNS = (_ns, tag) => createElement(tag);
elements.get("matrix").ownerDocument = controller.document;
controller._renderHeatmap("matrix", data.craftMatrix, { activeCount: 8 }, { descriptiveCounts: true, inspectable: false,
  rowHeading: "Being", columnHeading: "Craft", valueKeys: ["count", "value"] });
assert.deepEqual(tables[0].headings, ["Being", "Craft", "Reports", "Share of eligible co-reports"]);
const text = (element) => [element.textContent, ...element.children.map(text)].join(" ");
const matrixText = text(elements.get("matrix"));
assert.doesNotMatch(matrixText, /above expectation|below expectation|p-value|q-value|No cells qualify|Effect/);
assert.match(matrixText, /source reports/);
const nodes = (element) => [element, ...element.children.flatMap(nodes)];
assert.ok(!nodes(elements.get("matrix")).some((element) => element.classList.contains("is-low-support")), "descriptive count cells have no inferential support hatching");
assert.ok(nodes(elements.get("matrix")).some((element) => /zero indexed co-reporting records/.test(element.getAttribute("aria-label") ?? "")), "absent combinations are explicit zero counts");
for (const id of ["analysis-encounter-status", "analysis-abduction-profile-chart", "analysis-being-profile-chart", "analysis-being-craft-chart", "analysis-abduction-craft-chart", "analysis-encounter-time-chart", "analysis-encounter-source-chart", "analysis-encounter-coverage-chart"]) {
  elements.set(id, createElement("div"));
}
controller._renderEncounterEvidence(data, { activeCount: 8 });
const activityNodes = nodes(elements.get("analysis-encounter-time-chart"));
assert.equal(activityNodes.filter((element) => element.getAttribute("class") === "analysis-series-line").length, 2,
  "whole-corpus mode preserves both distinct encounter metrics");
assert.equal(elements.get("analysis-encounter-status").getAttribute("data-analysis-state"), "ready");
controller._renderEncounterEvidence(unavailable.encounters, { activeCount: 8 });
assert.equal(elements.get("analysis-encounter-status").getAttribute("data-analysis-state"), "loading");
assert.match(text(elements.get("analysis-being-craft-chart")), /remain unknown/);
console.log("Encounter cohort summaries and native count heatmap checks passed.");
