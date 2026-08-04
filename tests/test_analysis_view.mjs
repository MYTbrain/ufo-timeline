import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const analysis = require("../webapp/static_public/analysis_view.js");

assert.deepEqual(
  analysis.collapseDuplicateReferenceSeries([
    { label: "Active", points: [{ label: "190", value: 2 }, { label: "2020", value: 30 }] },
    { label: "Reference", reference: true, points: [{ label: "190", value: 2 }, { label: "2020", value: 30 }] },
  ]).map((series) => series.label),
  ["Active"],
  "identical full-catalog reference series collapse instead of drawing a fabricated comparison"
);

class FakeClassList {
  constructor() {
    this.values = new Set();
  }

  add(...tokens) {
    tokens.forEach((token) => this.values.add(token));
  }

  remove(...tokens) {
    tokens.forEach((token) => this.values.delete(token));
  }

  toggle(token, force) {
    const shouldAdd = force === undefined ? !this.values.has(token) : Boolean(force);
    if (shouldAdd) this.values.add(token);
    else this.values.delete(token);
    return shouldAdd;
  }

  contains(token) {
    return this.values.has(token);
  }
}

class FakeStyle {
  constructor() {
    this.values = new Map();
  }

  setProperty(name, value) {
    this.values.set(name, String(value));
  }
}

class FakeElement {
  constructor(tagName, ownerDocument) {
    this.tagName = String(tagName || "div").toUpperCase();
    this.ownerDocument = ownerDocument;
    this.attributes = new Map();
    this.children = [];
    this.listeners = new Map();
    this.classList = new FakeClassList();
    this.style = new FakeStyle();
    this.hidden = false;
    this.inert = false;
    this.disabled = false;
    this.value = "";
    this.textContent = "";
    this.className = "";
    this.parentNode = null;
    this.scrollLeft = 0;
    this.scrollCalls = [];
    this.scrollIntoViewCalls = [];
    this.rect = { top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0 };
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }

  replaceChildren(...children) {
    this.children = [];
    children.forEach((child) => this.appendChild(child));
  }

  removeChild(child) {
    this.children = this.children.filter((candidate) => candidate !== child);
    child.parentNode = null;
    return child;
  }

  get firstChild() {
    return this.children.length ? this.children[0] : null;
  }

  addEventListener(name, handler) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(handler);
  }

  removeEventListener(name, handler) {
    const handlers = this.listeners.get(name) || [];
    this.listeners.set(name, handlers.filter((candidate) => candidate !== handler));
  }

  emit(name, event = {}) {
    const payload = Object.assign({
      target: this,
      key: "",
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
    }, event);
    (this.listeners.get(name) || []).forEach((handler) => handler(payload));
    return payload;
  }

  focus() {
    this.ownerDocument.activeElement = this;
  }

  getBoundingClientRect() {
    return this.rect;
  }

  scrollTo(options = {}) {
    this.scrollLeft = Number(options.left || 0);
    this.scrollCalls.push(Object.assign({}, options));
  }

  scrollIntoView(options = {}) {
    this.scrollIntoViewCalls.push(Object.assign({}, options));
  }
}

class FakeDocument {
  constructor() {
    this.elements = new Map();
    this.documentElement = new FakeElement("html", this);
    this.activeElement = null;
  }

  register(id, tagName = "div") {
    const element = new FakeElement(tagName, this);
    element.setAttribute("id", id);
    this.elements.set(id, element);
    return element;
  }

  getElementById(id) {
    return this.elements.get(id) || null;
  }

  createElement(tagName) {
    return new FakeElement(tagName, this);
  }

  createElementNS(_namespace, tagName) {
    return new FakeElement(tagName, this);
  }
}

function createShellDocument() {
  const document = new FakeDocument();
  const tagById = {
    "analysis-view-tablist": "div",
    "view-tab-map": "button",
    "view-tab-analysis": "button",
    "analysis-baseline": "select",
    "analysis-error-retry": "button",
    "analysis-preview-apply-filters": "button",
    "analysis-preview-apply-area": "button",
    "analysis-preview-cancel": "button",
    "analysis-preview-cancel-top": "button",
    "analysis-include-crop-circles": "button",
    "analysis-include-animal-reports": "button",
    "analysis-view-crop-analysis": "a",
    "analysis-view-animal-analysis": "a",
    "analysis-export-json": "button",
    "analysis-export-csv": "button",
    "analysis-preview-criteria": "ul",
    "analysis-pattern-list": "ol",
    "analysis-section-nav": "nav",
    "analysis-context-subview-tabs": "div",
    "analysis-context-tab-crops": "button",
    "analysis-context-tab-animals": "button",
    "analysis-context-tab-relationships": "button",
    "analysis-baseline-label": "span",
    "analysis-mode-label": "span",
    "analysis-date-range-chip-mode": "span",
  };
  const ids = [
    "analysis-view-tablist", "view-tab-map", "view-tab-analysis", "analysis-tab-status", "analysis-mode-label", "analysis-date-range-chip-mode",
    "map-explorer-panel", "analysis-panel", "analysis-baseline", "analysis-baseline-note",
    "analysis-computation-status",
    "analysis-state-region", "analysis-loading", "analysis-loading-message", "analysis-empty",
    "analysis-empty-message", "analysis-error", "analysis-error-message", "analysis-error-retry",
    "analysis-content", "analysis-preview-drawer", "analysis-preview-kind", "analysis-preview-title",
    "analysis-preview-summary", "analysis-preview-cohort", "analysis-preview-missingness",
    "analysis-preview-comparison", "analysis-preview-criteria", "analysis-preview-feedback",
    "analysis-preview-apply-filters", "analysis-preview-apply-area", "analysis-preview-cancel",
    "analysis-preview-cancel-top", "analysis-active-count-card", "analysis-active-count-label", "analysis-active-count", "analysis-reference-count-card", "analysis-reference-count",
    "analysis-mapped-count", "analysis-unmapped-count", "analysis-missing-count",
    "analysis-unit-label", "analysis-source-mix", "analysis-date-precision",
    "analysis-location-precision", "analysis-dataset-hash", "analysis-policy-warning",
    "analysis-coverage-chart", "analysis-comparison-chart", "analysis-time-series-chart",
    "analysis-duration-status", "analysis-duration-chart", "analysis-duration-comparison-chart",
    "analysis-month-year-chart", "analysis-time-series-title", "analysis-time-series-question", "analysis-craft-distribution-chart",
    "analysis-report-type-chart", "analysis-craft-confidence-chart", "analysis-craft-residual-chart", "analysis-geography-grid-chart", "analysis-geography-sensitivity-chart",
    "analysis-geography-time-chart", "analysis-source-composition-chart",
    "analysis-source-time-chart", "analysis-quality-missingness-chart", "analysis-quality-audit-chart", "analysis-crop-context",
    "analysis-crop-context-status", "analysis-crop-time-chart", "analysis-crop-morphology-chart",
    "analysis-crop-type-chart", "analysis-crop-coordinate-chart", "analysis-crop-coverage-chart", "analysis-crop-spatial-chart", "analysis-animal-context", "analysis-animal-context-status",
    "analysis-animal-time-chart", "analysis-animal-species-chart", "analysis-animal-status-chart",
    "analysis-animal-date-precision-chart", "analysis-animal-coverage-chart", "analysis-animal-spatial-chart",
    "analysis-pattern-list", "analysis-pattern-count",
    "analysis-section-nav", "analysis-section-overview", "analysis-section-time", "analysis-section-craft",
    "analysis-section-geography", "analysis-section-spatial", "analysis-section-sources-quality", "analysis-section-context",
    "analysis-spatial-status", "analysis-context-status", "analysis-include-crop-circles", "analysis-include-animal-reports",
    "analysis-view-crop-analysis", "analysis-view-animal-analysis", "analysis-crop-control-status", "analysis-animal-control-status",
    "analysis-export-json", "analysis-export-csv", "analysis-crop-content", "analysis-crop-excluded",
    "analysis-animal-content", "analysis-animal-excluded", "analysis-craft-era-chart",
    "analysis-cooccurrence-chart", "analysis-spatial-eligibility-chart", "analysis-context-neighborhood-chart", "analysis-context-category-card", "analysis-context-category-chart", "analysis-facility-context-chart", "analysis-cross-domain-readiness-chart",
    "analysis-crop-readiness-chart", "analysis-animal-readiness-chart", "analysis-relationship-readiness-chart",
    "analysis-context-subview-tabs", "analysis-context-tab-crops", "analysis-context-tab-animals", "analysis-context-tab-relationships", "analysis-relationship-context",
  ];
  ids.forEach((id) => document.register(id, tagById[id] || "div"));
  const mapTab = document.getElementById("view-tab-map");
  mapTab.setAttribute("aria-selected", "true");
  const analysisTab = document.getElementById("view-tab-analysis");
  analysisTab.disabled = true;
  analysisTab.setAttribute("aria-disabled", "true");
  document.getElementById("analysis-baseline").value = "other_dates_balanced";
  document.getElementById("analysis-panel").hidden = true;
  document.getElementById("analysis-preview-drawer").hidden = true;
  document.getElementById("analysis-crop-excluded").hidden = true;
  document.getElementById("analysis-animal-excluded").hidden = true;
  document.getElementById("analysis-export-json").disabled = true;
  document.getElementById("analysis-export-csv").disabled = true;
  document.getElementById("analysis-include-crop-circles").setAttribute("aria-checked", "true");
  document.getElementById("analysis-include-animal-reports").setAttribute("aria-checked", "true");
  const sectionNav = document.getElementById("analysis-section-nav");
  ["overview", "time", "craft", "geography", "spatial", "sources-quality", "context"].forEach((key) => {
    const link = document.createElement("button");
    link.setAttribute("role", "tab");
    link.setAttribute("aria-controls", "analysis-section-" + key);
    link.textContent = key;
    sectionNav.appendChild(link);
  });
  const contextSubviewTablist = document.getElementById("analysis-context-subview-tabs");
  const contextSubviews = [
    ["analysis-context-tab-crops", "analysis-crop-context", true],
    ["analysis-context-tab-animals", "analysis-animal-context", false],
    ["analysis-context-tab-relationships", "analysis-relationship-context", false],
  ];
  contextSubviews.forEach(([tabId, panelId, selected]) => {
    const tab = document.getElementById(tabId);
    const panel = document.getElementById(panelId);
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-controls", panelId);
    tab.setAttribute("aria-selected", selected ? "true" : "false");
    tab.setAttribute("tabindex", selected ? "0" : "-1");
    contextSubviewTablist.appendChild(tab);
    panel.classList.add("analysis-context-subview");
    panel.setAttribute("role", "tabpanel");
    panel.hidden = !selected;
    panel.setAttribute("aria-hidden", selected ? "false" : "true");
    panel.inert = !selected;
  });
  contextSubviewTablist.querySelectorAll = function () {
    return this.children.filter((child) => child.getAttribute("role") === "tab" && child.getAttribute("aria-controls"));
  };
  return document;
}

function descendants(element) {
  return element.children.flatMap((child) => [child, ...descendants(child)]);
}

function createFrameHarness() {
  let nextId = 1;
  const callbacks = new Map();
  return {
    requestAnimationFrame(callback) {
      const id = nextId;
      nextId += 1;
      callbacks.set(id, callback);
      return id;
    },
    cancelAnimationFrame(id) {
      callbacks.delete(id);
    },
    pendingCount() {
      return callbacks.size;
    },
    peekCallback() {
      const first = callbacks.entries().next();
      return first.done ? null : first.value[1];
    },
    flushOne() {
      const first = callbacks.entries().next();
      if (first.done) return false;
      callbacks.delete(first.value[0]);
      first.value[1](16);
      return true;
    },
    flushAll(limit = 200) {
      let count = 0;
      while (callbacks.size && count < limit) {
        this.flushOne();
        count += 1;
      }
      if (callbacks.size) throw new Error("Frame harness exceeded its flush limit.");
      return count;
    },
  };
}

assert.deepEqual(analysis.ACTIVE_VIEWS, ["map", "analysis"]);
assert.equal(analysis.normalizeView("ANALYSIS"), "analysis");
assert.throws(() => analysis.normalizeView("table"), /Unknown analysis view/);
assert.equal(analysis.normalizeBaselineMode("previous_equal_duration"), "previous_equal_duration");
assert.equal(analysis.normalizeBaselineMode("unknown"), "other_dates_balanced");
assert.equal(analysis.normalizeBaselineMode("other_dates_matched"), "other_dates_balanced", "v1 baseline remains an input alias");
const requestEnvelope = {
  requestId: "analysis-7",
  generation: 12,
  baselineMode: "other_dates_balanced",
  signature: "filters:A|area:none|context:crop",
};
assert.equal(analysis.analysisRequestEnvelopeMatches(requestEnvelope, {
  requestId: "analysis-7",
  filterGeneration: 12,
  baselineMode: "other_dates_balanced",
  analysisSignature: requestEnvelope.signature,
}, requestEnvelope.signature), true);
assert.equal(analysis.analysisRequestEnvelopeMatches(requestEnvelope, {
  requestId: "analysis-7",
  filterGeneration: 12,
  baselineMode: "other_dates_balanced",
  analysisSignature: requestEnvelope.signature,
}, "filters:B|area:none|context:crop"), false, "a result from a previous filter signature must be stale");
assert.equal(analysis.analysisRequestEnvelopeMatches(requestEnvelope, {
  requestId: "analysis-7",
  filterGeneration: 12,
  baselineMode: "other_dates_balanced",
  analysisSignature: "filters:A|area:new|context:crop",
}, requestEnvelope.signature), false, "area and context signature mismatches must be stale");
assert.equal(analysis.positiveSeriesMaximum([0.08, 0.24, 0.12]), 0.24);
assert.equal(analysis.positiveSeriesMaximum([]), Number.EPSILON);
const countInterval = analysis.poissonCountInterval(100);
assert.ok(countInterval.lower < 100 && countInterval.upper > 100, "report-volume uncertainty brackets the observed count");
const treemap = analysis.proportionalTreemap([{ label: "A", weight: 60 }, { label: "B", weight: 30 }, { label: "C", weight: 10 }]);
assert.equal(treemap.length, 3);
assert.ok(Math.abs(treemap.reduce((sum, rectangle) => sum + rectangle.areaShare, 0) - 1) < 1e-10, "mosaic rectangles cover the full plotting area");
assert.ok(Math.abs(treemap[0].areaShare - 0.6) < 1e-10 && Math.abs(treemap[2].areaShare - 0.1) < 1e-10, "mosaic tile area is exactly proportional to report weight");
assert.equal(analysis.SERIES_POINT_LIMIT, 48);
assert.equal(analysis.HEATMAP_CELL_LIMIT, 144);
assert.equal(analysis.HEATMAP_AXIS_LIMIT, 12);
const sampleInput = Array.from({ length: 100 }, (_value, index) => index);
assert.deepEqual(analysis.sampleEvenly(sampleInput, 8), [0, 14, 28, 42, 57, 71, 85, 99]);
assert.equal(analysis.sampleEvenly(sampleInput, 48).length, 48);
assert.equal(analysis.sampleEvenly(sampleInput, 48)[0], 0);
assert.equal(analysis.sampleEvenly(sampleInput, 48).at(-1), 99);
assert.deepEqual(sampleInput.slice(0, 3), [0, 1, 2], "sampling must not mutate the source array");
assert.deepEqual(
  analysis.sortSemanticAxis(["2020", "190", "1960", "815", "1954"], "year"),
  ["190", "815", "1954", "1960", "2020"],
  "three- and four-digit years sort numerically before rendering"
);
assert.deepEqual(
  analysis.sortSemanticAxis(["10", "07", "06", "11", "04", "01", "12", "03", "02", "05", "08", "09"], "month"),
  ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"],
  "months retain calendar order"
);
assert.equal(analysis.monthDisplayLabel("January"), "01/JAN");
assert.equal(analysis.monthDisplayLabel("12"), "12/DEC");
assert.equal(analysis.craftDisplayLabel("dumbbell_barbell"), "Dumbbell Barbell", "dumbbell/barbell is never aliased to Formation");
assert.notEqual(analysis.craftDisplayLabel("dumbbell_barbell"), analysis.craftDisplayLabel("formation"));
assert.match(analysis.humanGeographyLabel("ea6x12:2:4"), /^Latitude .*\/ longitude /);
assert.doesNotMatch(analysis.humanGeographyLabel("ea6x12:2:4"), /ea6x12/i, "grid identifiers never leak into presentation labels");
const orderedSharedAxis = analysis.orderedSeriesDisplay([
  { label: "Active", points: [{ label: "2020", value: 3 }, { label: "190", value: 1 }, { label: "1960", value: 2 }] },
  { label: "Reference", reference: true, points: [{ label: "1960", value: 4 }, { label: "2020", value: 5 }, { label: "190", value: 2 }] },
], 3, { axisKind: "year" });
assert.deepEqual(orderedSharedAxis.labels, ["190", "1960", "2020"]);
assert.deepEqual(orderedSharedAxis.series[0].points.map((point) => point.label), orderedSharedAxis.labels, "all series share the same ordered x-domain");
const heatmapYears = Array.from({ length: 697 }, (_value, index) => String(1300 + index));
const heatmapMonths = Array.from({ length: 12 }, (_value, index) => String(index + 1).padStart(2, "0"));
const sampledHeatmap = analysis.sampledHeatmapAxes(heatmapYears, heatmapMonths, analysis.HEATMAP_CELL_LIMIT);
assert.equal(sampledHeatmap.rows.length, 12);
assert.deepEqual(sampledHeatmap.columns, heatmapMonths, "the short month axis should remain complete");
assert.equal(sampledHeatmap.rows[0], heatmapYears[0]);
assert.equal(sampledHeatmap.rows.at(-1), heatmapYears.at(-1));
assert.ok(sampledHeatmap.rows.length * sampledHeatmap.columns.length <= analysis.HEATMAP_CELL_LIMIT);
assert.equal(sampledHeatmap.sampled, true);
assert.equal(analysis.formatSignedPercent(0.04), "+4%");
assert.equal(analysis.formatSignedPercent(-0.04), "-4%");
assert.equal(analysis.formatPercentInterval({ lower: -0.06, upper: -0.02 }), "[-6%, -2%]");
assert.equal(analysis.nextEnabledTabIndex(0, "End", [1], 2), 0);
assert.equal(analysis.nextEnabledTabIndex(0, "ArrowRight", [], 2), 1);
assert.equal(analysis.nextEnabledTabIndex(1, "ArrowRight", [], 2), 0);
assert.equal(analysis.formatInterval({ lower: 0.12, upper: 0.35 }), "[0.12, 0.35]");
assert.match(
  analysis.formatSourceStability({ status: "stable", sourcesTested: 4, dominantSource: "A" }),
  /stable.*4 sources tested.*dominant: A/
);
assert.equal(
  analysis.resolvedPatternChartId("analysis-geography-grid"),
  "analysis-geography-grid-chart"
);
assert.equal(
  analysis.resolvedPatternChartId("analysis-time-decades"),
  "analysis-time-series-chart",
  "legacy evidence links resolve to the consolidated adaptive timeline"
);
assert.deepEqual(
  analysis.normalizeGeographyCells([{ key: "ea12x24:7:3", latIndex: 7, lonIndex: 3, latMinimum: 9.6, latMaximum: 19.5, lonMinimum: -135, lonMaximum: -120 }])
    .map((item) => [item.row, item.column]),
  [["Unspecified coordinate class · 9.6° to 19.5°", "-135° to -120°"]]
);

assert.deepEqual(
  analysis.geographyMapCells({
    facets: [
      { coordinateClass: "source_coordinates", cells: [{ latIndex: 0, lonIndex: 0, activeCount: 3 }] },
      { coordinateClass: "generalized_coordinates", cells: [{ latIndex: 1, lonIndex: 2, activeCount: 4 }] },
    ],
  }).map((item) => item.coordinateClass),
  ["generalized_coordinates", "source_coordinates"]
);

const normalizedSummary = analysis.normalizeSummary({
  active_count: 250,
  reference_count: 750,
  dataset_hash: { core: "abc", crop: "def" },
  warnings: ["Exploratory only."],
});
assert.equal(normalizedSummary.activeCount, 250);
assert.equal(normalizedSummary.datasetHash, "core: abc · crop: def");
assert.equal(normalizedSummary.policyWarning, "Exploratory only.");
const unixOrdinalPreview = analysis.previewForDatum(
  { count: 12, patch: { dateRange: { startOrdinal: 10957, endOrdinal: 11322 } } },
  "Year 2000",
  normalizedSummary,
  "filter"
);
assert.equal(unixOrdinalPreview.missingness, "Not computed for this preview");
assert.deepEqual(unixOrdinalPreview.criteria, [
  { label: "Date range", value: "2000-01-01 to 2000-12-31" },
]);

assert.deepEqual(
  analysis.matrixItems({
    columns: ["Jan", "Feb"],
    rows: [{ label: "1952", values: [2, { value: 3, patch: { month: 2 } }] }],
  }).map((item) => [item.row, item.column, item.value]),
  [["1952", "Jan", 2], ["1952", "Feb", 3]]
);
assert.deepEqual(
  analysis.matrixItems({
    cells: [{ key: "visible-only" }],
    fullCells: [{ key: "qualified" }, { key: "suppressed", displayStatus: "suppressed" }],
  }).map((item) => item.key),
  ["qualified", "suppressed"],
  "accessible heatmaps retain the complete qualified and suppressed evidence table"
);

const sparseHeatmap = analysis.heatmapDisplayItems([
  { row: "Disk", column: "1950s", activeCount: 0, referenceCount: 0, value: 0 },
  { row: "Disk", column: "1960s", activeCount: 0, referenceCount: 40, difference: -0.03 },
  { row: "Triangle", column: "1970s", activeCount: 8, referenceCount: 6, suppressed: true, suppressionReason: "Expected cell below 10" },
]);
assert.equal(sparseHeatmap.data.length, 2, "both-zero heatmap cells are not rendered");
assert.equal(sparseHeatmap.data[0].column, "1960s", "qualified effects determine information ordering");
const gatedHeatmap = analysis.heatmapDisplayItems({ fullCells: [
  { row: "Disk", column: "empty", activeCount: 0, referenceCount: 0, displayStatus: "structurally_empty", displayEligible: false, suppressionReasons: ["both_zero"] },
  { row: "Disk", column: "sparse", activeCount: 4, referenceCount: 6, value: 0.2, displayStatus: "suppressed", displayEligible: false, suppressionReasons: ["expected_cell"] },
] });
assert.equal(gatedHeatmap.data.length, 1, "structural empties are omitted while suppressed tested cells remain visible");
assert.equal(gatedHeatmap.data[0].column, "sparse");
const typedReadiness = analysis.readinessMatrix({ readiness: [{
  key: "ufoCraftPoints",
  label: "UFO craft points",
  status: "ready_descriptive",
  inputN: 580783,
  passedN: 33801,
  eligibleN: 33801,
  totalN: 580783,
  policyId: "ufo-spatial-v2",
  evidenceHash: "sha256:points",
  gates: [{
    gateId: "source_coordinates",
    label: "Source coordinates",
    status: "ready_inferential",
    inputN: 580783,
    passedN: 33801,
    failedN: 546982,
    unknownN: 0,
    denominatorLabel: "Mapped report points",
    reasonCodes: ["source_marker_required"],
  }],
}, {
  key: "cropLocality",
  label: "Crop locality",
  status: "not_evaluated",
  inputN: 3249,
  passedN: 3249,
  gates: [],
}, {
  key: "opaqueDomain",
  label: "Opaque domain",
  status: "not_evaluated",
  inputN: 50,
  passedN: 25,
  gates: [{
    gateId: "opaque_gate",
    label: "Source coordinates, exact dates, provenance, lineage, review, and sample",
    status: "ready_inferential",
    inputN: 50,
    passedN: 25,
    failedN: 20,
    unknownN: 5,
  }],
}, {
  key: "notApplicableDomain",
  label: "Not-applicable domain",
  status: "ready_descriptive",
  gates: [{
    gateId: "exact_day",
    label: "Exact-day dates",
    applicability: "not_applicable",
    status: "ready_descriptive",
  }],
}] });
assert.equal(typedReadiness.typed, true);
assert.deepEqual(typedReadiness.columns.map((column) => column.key), ["location", "date", "provenance", "lineage", "review", "sample", "overall"]);
assert.equal(typedReadiness.rows[0].cells[0].value, "33,801 / 580,783");
assert.equal(typedReadiness.rows[0].cells[0].status, "ready_inferential");
assert.deepEqual(typedReadiness.rows[0].cells[0].counts, { input: 580783, passed: 33801, failed: 546982, unknown: 0 });
assert.match(typedReadiness.rows[0].cells[0].reason, /failed 546,982; unknown 0/i);
assert.equal(typedReadiness.rows[1].cells[0].status, "not_evaluated", "an absent typed dimension is reported honestly as not evaluated");
assert.ok(typedReadiness.rows[2].cells.slice(0, 6).every((cell) => cell.status === "not_evaluated"), "gate labels and prose never classify a gate into a common column");
assert.deepEqual(typedReadiness.rows[2].detailedGates.map((gate) => gate.key), ["opaque_gate"], "unmapped typed gates remain in the complete gate ledger");
assert.equal(typedReadiness.rows[3].cells[1].status, "not_applicable");
assert.equal(typedReadiness.rows[3].cells[1].value, "N/A", "typed non-applicability is distinct from a gate that was not evaluated");
const supportedReadinessStatuses = new Set(["ready_inferential", "ready_sensitivity", "ready_descriptive", "limited", "blocked", "not_applicable", "not_evaluated", "data_unavailable"]);
assert.ok(typedReadiness.rows.flatMap((row) => row.cells).every((cell) => supportedReadinessStatuses.has(cell.status)), "compact matrix cells use only the supported typed readiness states");
assert.doesNotMatch(JSON.stringify(typedReadiness), /Not reported|mentioned/i);
const evidencePackage = analysis.buildEvidencePackage({
  analysisMode: "whole_corpus_structure",
  comparisonState: "whole_corpus_structure",
  summary: { activeCount: 80, referenceCount: 240 },
  overview: { evidenceSummary: [{ label: "Disk", activeCount: 20, expectedCount: 40, adjustedDifference: 0.04, interval: [0.01, 0.07], qValue: 0.02, estimateAvailable: true, inferenceEligible: true, permutationCount: 999 }] },
  geography: { cells: [{
    key: "source_coordinates|country:France",
    country: "France",
    displayLabel: "France",
    macroregion: "Western Europe",
    geographyAssignmentSource: "pinned_country_polygon",
    geographyAssignmentConfidence: "inside_polygon",
    geographyBoundaryStatus: "inside_country",
    geographyUnknownStatus: "assigned_country",
    sourceMix: [{ source: "source-a", count: 18, share: 0.75 }, { source: "source-b", count: 6, share: 0.25 }],
    geographyAssignmentProvenance: { assignmentSources: [{ value: "pinned_country_polygon", count: 24, share: 1 }] },
    activeCount: 24,
  }] },
  spatialEvidence: {
    cooccurrence: { configuration: { crossSource: [{
      sourceLane: "cross",
      cells: [{ row: "formation", column: "disc_saucer", observedCount: 12, expectedCount: 8, log2Enrichment: 0.58 }],
    }] } },
    readiness: [{
      key: "cropBounded",
      label: "Bounded crop markers",
      policyId: "crop-bounded-v1",
      evidenceHash: "sha256:crop-bounded",
      gates: [{
        gateId: "date_role",
        label: "Catalog date role",
        status: "ready_descriptive",
        applicability: "applicable",
        inputN: 406,
        passedN: 406,
        failedN: 0,
        unknownN: 0,
        reasonCodes: ["catalog_date_not_formation_date"],
      }],
    }],
  },
}, {
  baselineMode: "other_dates_balanced",
  estimatorVersion: "2.0.0",
  filterSnapshot: { generation: 17, filters: { source: "all" } },
  artifactHashes: { core: "abc123" },
});
const evidenceCsv = analysis.evidencePackageToCsv(evidencePackage);
assert.equal(evidencePackage.analysisMode, "whole_corpus_structure");
assert.equal(evidencePackage.comparisonState, "whole_corpus_structure");
assert.match(evidenceCsv, /analysis_mode,comparison_state,baseline_mode/);
assert.match(evidenceCsv, /reference_n,expected_count/);
assert.match(evidenceCsv, /estimate_available,inference_eligible,low_support/);
assert.match(evidenceCsv, /permutation_count,bootstrap_count/);
assert.match(evidenceCsv, /other_dates_balanced,2\.0\.0/);
assert.match(evidenceCsv, /overview\.evidenceSummary,Disk,Disk,Disk.*reports,20,,40/);
assert.match(evidenceCsv, /0\.04,0\.01,0\.07.*0\.02/);
assert.match(evidenceCsv, /abc123/);
const exactCountryExport = evidencePackage.evidenceRows.find((row) => row.section === "geography.cells" && row.geography_country === "France");
assert.deepEqual({
  raw_label: exactCountryExport.raw_label,
  display_label: exactCountryExport.display_label,
  lane: exactCountryExport.lane,
  geography_country: exactCountryExport.geography_country,
  geography_macroregion: exactCountryExport.geography_macroregion,
  geography_assignment_source: exactCountryExport.geography_assignment_source,
  geography_assignment_confidence: exactCountryExport.geography_assignment_confidence,
  geography_boundary_status: exactCountryExport.geography_boundary_status,
  geography_unknown_status: exactCountryExport.geography_unknown_status,
  geography_source_mix: exactCountryExport.geography_source_mix,
}, {
  raw_label: "source_coordinates|country:France",
  display_label: "France",
  lane: "",
  geography_country: "France",
  geography_macroregion: "Western Europe",
  geography_assignment_source: "pinned_country_polygon",
  geography_assignment_confidence: "inside_polygon",
  geography_boundary_status: "inside_country",
  geography_unknown_status: "assigned_country",
  geography_source_mix: [{ source: "source-a", count: 18, share: 0.75 }, { source: "source-b", count: 6, share: 0.25 }],
});
const exactFormationExport = evidencePackage.evidenceRows.find((row) => row.section.includes("spatialEvidence.cooccurrence.configuration.crossSource[0].cells"));
assert.deepEqual({
  raw_label: exactFormationExport.raw_label,
  display_label: exactFormationExport.display_label,
  raw_row_label: exactFormationExport.raw_row_label,
  display_row_label: exactFormationExport.display_row_label,
  raw_column_label: exactFormationExport.raw_column_label,
  display_column_label: exactFormationExport.display_column_label,
  lane: exactFormationExport.lane,
}, {
  raw_label: "formation / disc_saucer",
  display_label: "Formation / Disc Saucer",
  raw_row_label: "formation",
  display_row_label: "Formation",
  raw_column_label: "disc_saucer",
  display_column_label: "Disc Saucer",
  lane: "formation_configuration",
});
const exactGateExport = evidencePackage.evidenceRows.find((row) => row.gate_id === "date_role");
assert.deepEqual({
  gate_id: exactGateExport.gate_id,
  gate_label: exactGateExport.gate_label,
  readiness_status: exactGateExport.readiness_status,
  applicability: exactGateExport.applicability,
  input_n: exactGateExport.input_n,
  passed_n: exactGateExport.passed_n,
  failed_n: exactGateExport.failed_n,
  unknown_n: exactGateExport.unknown_n,
  reason_codes: exactGateExport.reason_codes,
  policy_id: exactGateExport.policy_id,
  evidence_hash: exactGateExport.evidence_hash,
}, {
  gate_id: "date_role",
  gate_label: "Catalog date role",
  readiness_status: "ready_descriptive",
  applicability: "applicable",
  input_n: 406,
  passed_n: 406,
  failed_n: 0,
  unknown_n: 0,
  reason_codes: ["catalog_date_not_formation_date"],
  policy_id: "crop-bounded-v1",
  evidence_hash: "sha256:crop-bounded",
});
assert.deepEqual(
  evidenceCsv.split("\r\n", 1)[0].split(",").filter((column) => [
    "raw_label", "display_label", "raw_row_label", "display_row_label", "raw_column_label", "display_column_label", "lane",
    "gate_id", "gate_label", "readiness_status", "applicability", "input_n", "passed_n", "failed_n", "unknown_n", "policy_id", "evidence_hash", "reason_codes",
    "geography_country", "geography_macroregion", "geography_assignment_source", "geography_assignment_confidence", "geography_boundary_status", "geography_unknown_status", "geography_source_mix", "geography_assignment_provenance",
  ].includes(column)),
  [
    "raw_label", "display_label", "raw_row_label", "display_row_label", "raw_column_label", "display_column_label", "lane",
    "gate_id", "gate_label", "readiness_status", "applicability", "input_n", "passed_n", "failed_n", "unknown_n", "policy_id", "evidence_hash", "reason_codes",
    "geography_country", "geography_macroregion", "geography_assignment_source", "geography_assignment_confidence", "geography_boundary_status", "geography_unknown_status", "geography_source_mix", "geography_assignment_provenance",
  ],
  "CSV export keeps the audited v2.2 raw/display, lane, typed-gate, and geography-provenance contract"
);
const typedGatePackage = analysis.buildEvidencePackage({ spatialEvidence: { readiness: [{
  key: "cropBounded",
  label: "Bounded crop markers",
  gates: [{
    gateId: "crop_bounded_marker_lane",
    label: "Exact-day bounded crop markers",
    applicability: "applicable",
    status: "ready_sensitivity",
    inputN: 7745,
    passedN: 406,
    failedN: 7339,
    unknownN: 0,
    policyId: "crop-marker-v1",
    evidenceHash: "sha256:crop-gate",
    reasonCodes: ["catalog_date_not_formation_date"],
  }],
}] } }, {});
const typedGateExportRow = typedGatePackage.evidenceRows.find((row) => row.gate_id === "crop_bounded_marker_lane");
assert.deepEqual({
  status: typedGateExportRow.readiness_status,
  input: typedGateExportRow.input_n,
  passed: typedGateExportRow.passed_n,
  failed: typedGateExportRow.failed_n,
  unknown: typedGateExportRow.unknown_n,
  policy: typedGateExportRow.policy_id,
  hash: typedGateExportRow.evidence_hash,
}, {
  status: "ready_sensitivity",
  input: 7745,
  passed: 406,
  failed: 7339,
  unknown: 0,
  policy: "crop-marker-v1",
  hash: "sha256:crop-gate",
}, "CSV evidence rows retain the complete typed gate counts and provenance");
assert.equal(typedGatePackage.result.spatialEvidence.readiness[0].gates[0].gateId, "crop_bounded_marker_lane", "the JSON evidence package preserves the original gate object");
assert.match(analysis.evidencePackageToCsv(typedGatePackage), /crop_bounded_marker_lane,Exact-day bounded crop markers,ready_sensitivity,applicable,7745,406,7339,0,crop-marker-v1,sha256:crop-gate/);

const inferredPreview = analysis.previewForDatum(
  { label: "Disk", count: 80, referenceCount: 40, patch: { craft: ["disk"] } },
  "Disk",
  normalizedSummary,
  "filter"
);
assert.equal(inferredPreview.kind, "filter");
assert.deepEqual(inferredPreview.patch, { craft: ["disk"] });
assert.deepEqual(inferredPreview.criteria, [{ label: "Craft type", value: "disk" }]);
assert.match(inferredPreview.comparison, /80 active vs\. 40 reference/);

const balancedPreview = analysis.sourceBalancedDisplay(
  [{ label: "1952", observed: 0.18, reference: 0.09 }],
  [{ label: "1952", count: 120, referenceCount: 60, patch: { dateRange: { startIso: "1952-01-01", endIso: "1952-12-31" } } }]
)[0].points[0].preview;
assert.equal(balancedPreview.cohortSize, 120);
assert.equal(balancedPreview.comparison, "18% source-balanced active vs. 9% reference");

const craftTrendDisplay = analysis.craftTrendSeries([
  { row: "Triangle", column: "1960s", observed: 18, reference: 9 },
  { row: "Disk", column: "1950s", observed: 80, reference: 40 },
  { row: "Triangle", column: "1950s", observed: 12, reference: 8 },
  { row: "Disk", column: "1960s", observed: 65, reference: 50 },
]);
assert.deepEqual(
  craftTrendDisplay.map((series) => series.label),
  ["Triangle · active", "Triangle · reference", "Disk · active", "Disk · reference"],
  "craft trends must remain separate per craft and cohort"
);
assert.deepEqual(craftTrendDisplay[0].points.map((point) => point.value), [18, 12]);
assert.equal(craftTrendDisplay[0].colorIndex, craftTrendDisplay[1].colorIndex, "active/reference pairs share a craft color");
assert.equal(craftTrendDisplay[1].reference, true);

const sourceCompositionDisplay = analysis.sourceCompositionDisplay([
  { row: "Source A", column: "1950s", value: 0.6, reference: 0.4, count: 60, referenceCount: 40 },
  { row: "Source B", column: "1950s", value: 0.4, reference: 0.6, count: 40, referenceCount: 60 },
]);
assert.deepEqual(sourceCompositionDisplay.sources, ["Source A", "Source B"]);
assert.equal(sourceCompositionDisplay.rows.reduce((sum, row) => sum + row.activeShare, 0), 1);
assert.equal(sourceCompositionDisplay.rows.reduce((sum, row) => sum + row.referenceShare, 0), 1);

const groupedPatterns = analysis.patternGroupsForDisplay(
  [
    { family: "craft", key: "disk", label: "Craft first", findingLane: "stable_multi_source_content", sourceStability: { status: "stable_multi_source" } },
    { family: "time_month", key: "7", label: "Time second", findingLane: "source_or_region_sensitive", sourceStability: { status: "source_sensitive" } },
    { family: "source", key: "A", label: "Source third", findingLane: "collection_and_quality", sourceStability: { status: "source_specific_dimension" } },
  ],
  {
    stableMultiSourceContent: [
      { family: "time_month", key: "8", label: "Later family", findingLane: "stable_multi_source_content", sourceStability: { status: "stable_multi_source" } },
      { family: "craft", key: "disk", label: "Craft first", findingLane: "stable_multi_source_content", sourceStability: { status: "stable_multi_source" } },
    ],
    sourceOrRegionSensitive: [{ family: "time_month", key: "7", label: "Time second", findingLane: "source_or_region_sensitive", sourceStability: { status: "source_sensitive" } }],
    collectionAndQuality: [{ family: "source", key: "A", label: "Source third", findingLane: "collection_and_quality", sourceStability: { status: "source_specific_dimension" } }],
  }
);
assert.deepEqual(groupedPatterns.map((lane) => lane.label), ["Stable multi-source content shifts", "Source- or region-sensitive findings", "Collection and data-quality shifts"]);
assert.deepEqual(groupedPatterns[0].patterns.map((pattern) => pattern.label), ["Craft first", "Later family"], "family order is preserved within every lane");

assert.match(
  analysis.contextMembershipDisclosure({}, {
    unitLabel: "crop-circle records",
    policyWarning: "Stored inclusive date intervals define cohort membership.",
    missingnessPolicy: {
      unit: "records missing any required descriptive field",
      aggregation: "set union; each record contributes at most once",
      requiredFields: ["known date interval", "mapped state"],
    },
  }, "Crop-circle records"),
  /Membership unit: crop-circle records.*inclusive date intervals.*Missingness membership unit: records missing.*set union.*known date interval, mapped state/
);
assert.equal(
  analysis.contextEnabledForRender(
    { enabled: false },
    { contextLayers: { crops: { enabled: true } } },
    "crops"
  ),
  true,
  "the current shared filter snapshot overrides a stale excluded crop result"
);
assert.equal(
  analysis.contextEnabledForRender(
    { enabled: true },
    { contextLayers: { animals: { enabled: false } } },
    "animals"
  ),
  false,
  "the current shared filter snapshot overrides a stale included animal result"
);
assert.equal(
  analysis.contextEnabledForRender({ enabled: false }, {}, "crops"),
  false,
  "standalone evidence renders retain the result-owned context state when no shared snapshot is supplied"
);

const document = createShellDocument();
const viewEvents = [];
const baselineEvents = [];
const appliedFilters = [];
const appliedAreas = [];
const contextChanges = [];
const sectionActivations = [];
const geographyRequests = [];
const spatialRequests = [];
const contextViews = [];
const evidenceExports = [];
const renderCompletions = [];
const controller = new analysis.AnalysisViewController({
  document,
  onViewChange: (event) => viewEvents.push(event),
  onBaselineChange: (event) => baselineEvents.push(event),
  onApplyFilterPreview: (preview) => appliedFilters.push(preview),
  onApplyAreaPreview: (preview) => appliedAreas.push(preview),
  onContextLayerChange: (change) => {
    contextChanges.push(change);
    return { enabled: change.enabled, status: "ready", message: change.enabled ? "Included from shared state" : "Excluded from shared state" };
  },
  onSectionActivate: (event) => sectionActivations.push(event),
  onGeographyRequested: (event) => geographyRequests.push(event),
  onSpatialEvidenceRequested: (event) => spatialRequests.push(event),
  onContextView: (event) => contextViews.push(event),
  onExportEvidence: (event) => evidenceExports.push(event),
  onRenderComplete: (event) => renderCompletions.push(event),
  getFilterSnapshot: () => ({ generation: 12, dateRange: { start: "1954-09-01", end: "1954-11-30" } }),
});

assert.equal(controller.getActiveView(), "map");
assert.equal(document.getElementById("map-explorer-panel").hidden, false);
assert.equal(document.getElementById("analysis-panel").hidden, true);
assert.equal(controller.setActiveView("analysis"), false);

controller.setAnalysisEnabled(true);
assert.equal(document.getElementById("view-tab-analysis").disabled, false);
const keyEvent = document.getElementById("analysis-view-tablist").emit("keydown", {
  key: "End",
  target: document.getElementById("view-tab-map"),
});
assert.equal(keyEvent.defaultPrevented, true);
assert.equal(controller.getActiveView(), "analysis");
assert.equal(document.getElementById("map-explorer-panel").hidden, true);
assert.equal(document.getElementById("map-explorer-panel").inert, true);
assert.equal(document.getElementById("analysis-panel").hidden, false);
assert.equal(viewEvents.at(-1).firstAnalysisActivation, true);
assert.equal(controller.setComputationPhase("inference", "Computing adjusted intervals."), "inference");
assert.equal(document.getElementById("analysis-computation-status").hidden, false);
assert.equal(document.getElementById("analysis-computation-status").textContent, "Computing adjusted intervals.");
assert.equal(document.getElementById("analysis-content").getAttribute("aria-busy"), "true");
assert.equal(controller.setComputationPhase("ready", "Complete."), "ready");
assert.equal(document.getElementById("analysis-computation-status").hidden, true);
assert.equal(document.getElementById("analysis-content").getAttribute("aria-busy"), "false");

controller.setActiveView("map");
controller.setActiveView("analysis");
assert.equal(viewEvents.at(-1).firstAnalysisActivation, false);

// Sticky section navigation owns exactly one active location, supports keyboard
// movement, and advertises Spatial Evidence activation for lazy app loading.
const sectionNav = document.getElementById("analysis-section-nav");
const spatialLink = sectionNav.children[4];
const geographyLink = sectionNav.children[3];
assert.equal(sectionNav.getAttribute("role"), "tablist");
assert.equal(sectionNav.children.filter((link) => link.getAttribute("aria-selected") === "true").length, 1);
assert.equal(sectionNav.children[0].getAttribute("aria-selected"), "true");
assert.equal(document.getElementById("analysis-section-overview").hidden, false);
assert.equal(document.getElementById("analysis-section-time").hidden, true);
assert.equal(document.getElementById("analysis-section-time").inert, true);
assert.equal(document.getElementById("analysis-section-time").getAttribute("aria-hidden"), "true");
geographyLink.emit("click");
assert.deepEqual(geographyRequests, [{ origin: "section-visible", requestedDomains: ["geography"] }]);
assert.equal(controller.geographyRequested, true);
assert.equal(document.getElementById("analysis-section-geography").getAttribute("aria-busy"), "true");
assert.match(controller.els.geographyStatus.textContent, /Loading country-level geography evidence/i);
geographyLink.emit("click");
assert.equal(geographyRequests.length, 1, "geography artifacts are requested only once while loading or ready");
controller.setSectionState("geography", "error", "Geography hash mismatch.");
assert.equal(controller.geographyRequested, false);
geographyLink.emit("click");
assert.equal(geographyRequests.length, 2, "a failed geography load can be retried from its dashboard tab");
controller.setSectionState("geography", "ready", "Country data ready.");
assert.equal(document.getElementById("analysis-section-geography").getAttribute("aria-busy"), "false");
spatialLink.emit("click");
assert.equal(controller.activeSectionId, "analysis-section-spatial");
assert.equal(sectionNav.children.filter((link) => link.getAttribute("aria-current") === "location").length, 1);
assert.equal(sectionNav.children.filter((link) => link.getAttribute("aria-selected") === "true").length, 1);
assert.equal(document.getElementById("analysis-section-spatial").hidden, false);
assert.equal(document.getElementById("analysis-section-overview").hidden, true);
assert.equal(document.getElementById("analysis-section-overview").inert, true);
assert.equal(document.getElementById("analysis-section-spatial").getAttribute("aria-hidden"), "false");
assert.equal(document.getElementById("analysis-section-spatial").scrollIntoViewCalls.length, 0, "top-level section tabs never trigger document scrolling");
assert.deepEqual(sectionActivations.at(-1), {
  sectionId: "analysis-section-spatial",
  sectionKey: "spatial",
  source: "section-link",
});
assert.equal(spatialRequests.length, 1);
controller.setSectionState("spatial", "error", "Artifact hash did not match.");
assert.equal(controller.spatialRequested, false);
assert.equal(document.getElementById("analysis-spatial-status").getAttribute("data-analysis-state"), "error");
spatialLink.emit("click");
assert.equal(spatialRequests.length, 2, "the active Spatial Evidence link retries after a transient load failure");
assert.equal(document.getElementById("analysis-spatial-status").getAttribute("data-analysis-state"), "loading");
const sectionKeyEvent = sectionNav.emit("keydown", { key: "End", target: spatialLink });
assert.equal(sectionKeyEvent.defaultPrevented, true);
assert.equal(controller.activeSectionId, "analysis-section-context");
assert.equal(document.activeElement, sectionNav.children[6], "keyboard activation retains focus on the selected tab");
controller.setSectionState("context", "loading", "Loading context neighbors.");
assert.equal(document.getElementById("analysis-section-context").getAttribute("aria-busy"), "true");
assert.equal(document.getElementById("analysis-context-status").getAttribute("data-analysis-state"), "loading");
controller.setSectionState("context", "ready", "Context neighbors ready.");
assert.equal(document.getElementById("analysis-section-context").getAttribute("aria-busy"), "false");
assert.equal(document.getElementById("analysis-context-status").textContent, "Context neighbors ready.");
assert.equal(controller.setActiveSection("analysis-section-time", { source: "api" }), true);
assert.equal(controller.activeSectionId, "analysis-section-time");
assert.equal(document.getElementById("analysis-section-time").hidden, false);
controller.setActiveSection("analysis-section-context", { source: "test" });

// Context is a nested selected dashboard with one perceivable panel, roving
// keyboard focus, and stable public activation semantics.
const contextSubviewTablist = document.getElementById("analysis-context-subview-tabs");
const cropSubviewTab = document.getElementById("analysis-context-tab-crops");
const animalSubviewTab = document.getElementById("analysis-context-tab-animals");
const relationshipSubviewTab = document.getElementById("analysis-context-tab-relationships");
assert.equal(contextSubviewTablist.children.filter((tab) => tab.getAttribute("aria-selected") === "true").length, 1);
assert.equal(cropSubviewTab.getAttribute("aria-selected"), "true");
assert.equal(document.getElementById("analysis-crop-context").hidden, false);
assert.equal(document.getElementById("analysis-animal-context").hidden, true);
animalSubviewTab.emit("click");
assert.equal(controller.activeContextSubviewId, "analysis-animal-context");
assert.equal(document.activeElement, animalSubviewTab);
assert.equal(document.getElementById("analysis-crop-context").hidden, true);
assert.equal(document.getElementById("analysis-crop-context").inert, true);
assert.equal(document.getElementById("analysis-animal-context").hidden, false);
assert.equal(document.getElementById("analysis-animal-context").getAttribute("aria-hidden"), "false");
const contextEndEvent = contextSubviewTablist.emit("keydown", { key: "End", target: animalSubviewTab });
assert.equal(contextEndEvent.defaultPrevented, true);
assert.equal(controller.activeContextSubviewId, "analysis-relationship-context");
assert.equal(document.activeElement, relationshipSubviewTab);
contextSubviewTablist.emit("keydown", { key: "Home", target: relationshipSubviewTab });
assert.equal(controller.activeContextSubviewId, "analysis-crop-context");
assert.equal(document.activeElement, cropSubviewTab);
assert.equal(controller.setActiveContextSubview("missing-context-panel"), false);

// Context inclusion is a controller callback contract, independent of the
// hidden and inert Map Explorer controls.
document.getElementById("analysis-include-crop-circles").emit("click");
await Promise.resolve();
await Promise.resolve();
assert.deepEqual(contextChanges.at(-1), { domain: "crops", enabled: false, origin: "analysis" });
assert.equal(document.getElementById("analysis-include-crop-circles").getAttribute("aria-checked"), "false");
assert.equal(document.getElementById("analysis-crop-content").hidden, true);
assert.equal(document.getElementById("analysis-crop-excluded").hidden, false);
document.getElementById("analysis-view-crop-analysis").emit("click");
assert.equal(contextViews.at(-1).domain, "crops");
assert.equal(document.getElementById("analysis-crop-context").scrollIntoViewCalls.length, 1, "nested context actions visibly reveal the requested group");

const baseline = document.getElementById("analysis-baseline");
baseline.value = "previous_equal_duration";
baseline.emit("change");
assert.deepEqual(baselineEvents.at(-1), {
  baselineMode: "previous_equal_duration",
  previousMode: "other_dates_balanced",
});
// Programmatic changes report the true previous value.
controller.setBaselineMode("other_dates_balanced", { notify: false });
controller.setBaselineMode("full_catalog");
assert.deepEqual(baselineEvents.at(-1), {
  baselineMode: "full_catalog",
  previousMode: "other_dates_balanced",
});

controller.setAnalysisState("error", "Worker stopped safely.");
assert.equal(document.getElementById("analysis-error").hidden, false);
assert.equal(document.getElementById("analysis-error-message").textContent, "Worker stopped safely.");
assert.equal(document.getElementById("analysis-content").hidden, true);

controller.showPreview({
  kind: "filter",
  title: "Disk reports",
  cohortSize: 80,
  missingness: 0.05,
  comparison: "2.0× reference",
  criteria: [{ label: "Craft", value: "Disk" }],
  patch: { craft: ["disk"] },
});
assert.equal(document.getElementById("analysis-preview-drawer").hidden, false);
assert.equal(document.getElementById("analysis-preview-apply-filters").hidden, false);
document.getElementById("analysis-preview-apply-filters").emit("click");
assert.equal(appliedFilters.length, 1);
assert.equal(document.getElementById("analysis-preview-drawer").hidden, true);

controller.showPreview({ kind: "area", title: "Grid cell", area: { west: 0, east: 10 } });
assert.equal(document.getElementById("analysis-preview-apply-area").hidden, false);
document.getElementById("analysis-preview-apply-area").emit("click");
assert.equal(appliedAreas.length, 1);

const stablePattern = {
  family: "craft",
  key: "disk",
  label: "Disk share shift",
  policyLabel: "Passed the craft-family display gates.",
  observedCount: 80,
  referenceCount: 40,
  difference: 0.04,
  relativeEnrichment: 1.5,
  interval: { lower: 0.02, upper: 0.06 },
  qValue: 0.01,
  findingLane: "stable_multi_source_content",
  missingness: 0.03,
  sourceStability: { status: "stable_multi_source", stable: true, sourcesTested: 3, dominantSource: "A" },
  datasetHash: "sha256:abc",
  chartId: "analysis-craft-distribution-chart",
};
const sensitivePattern = {
  family: "time_month",
  key: "7",
  label: "July share shift",
  observedCount: 65,
  referenceCount: 41,
  difference: 0.025,
  interval: { lower: 0.01, upper: 0.04 },
  qValue: 0.02,
  findingLane: "source_or_region_sensitive",
  sourceStability: { status: "source_sensitive", sourcesTested: 2 },
  datasetHash: "sha256:abc",
  chartId: "analysis-month-year-chart",
};
const sourceSpecificPattern = {
  family: "source",
  key: "Source A",
  label: "Source A composition shift",
  observedCount: 240,
  referenceCount: 180,
  difference: 0.03,
  interval: { lower: 0.01, upper: 0.05 },
  qValue: 0.03,
  findingLane: "collection_and_quality",
  sourceStability: { status: "source_specific_dimension", sourcesTested: 1 },
  datasetHash: "sha256:abc",
  chartId: "analysis-source-time-chart",
};

const result = {
  summary: {
    activeCount: 400,
    referenceCount: 900,
    mappedCount: 350,
    unmappedCount: 50,
    missingCount: 20,
    unitLabel: "Reports",
    sourceMixLabel: "Three sources",
    datePrecisionLabel: "82% exact",
    locationPrecisionLabel: "70% source-coordinate",
    policyWarnings: ["Exploratory only."],
    datasetHash: "sha256:abc",
  },
  overview: {
    eligibilityFunnel: [
      { label: "Mapped report points", inputN: 580783, passedN: 580783, failedN: 0, criteria: "Mapped UFO report markers" },
      { label: "Qualified craft point evidence", inputN: 580783, passedN: 33801, failedN: 546982, criteria: "Exact-day, source-coordinate, recognized craft, confidence, pile, and lineage gates" },
    ],
    coverage: [{ label: "Mapped", count: 350 }],
    comparison: [
      { label: "Disk", value: -0.04, reference: 0, interval: { lower: -0.06, upper: -0.02 }, patch: { craft: ["disk"] } },
      { label: "Unsupported", value: 0.08, interval: { lower: 0.01, upper: 0.14 }, status: "suppressed", suppressionReasons: ["Common support below 80%"], patch: { craft: ["unsupported"] } },
    ],
  },
  time: {
    series: [{ label: "1952", count: 120, patch: { startDate: "1952-01-01", endDate: "1952-12-31" } }],
    annualSeries: [{ label: "1952", count: 121, reference: 61 }],
    adaptiveBinning: { unit: "year", widthYears: 1, possibleBinCount: 1, occupiedBinCount: 1 },
    decades: [{ label: "1950s", observed: 320, reference: 240 }],
    sourceBalanced: [{ label: "1952", observed: 0.18, reference: 0.09 }],
    sourceBalancedPolicy: "Each source contributes equal total weight.",
    monthYear: [{ row: "1952", column: "July", count: 30 }],
    rolling: [{ label: "1952", observed: 120, reference: 60 }],
    bursts: [{ label: "1952", observed: 120, baselineMean: 40, standardizedExcess: 12.6, preview: { kind: "filter", patch: { dateRange: { year: 1952 } } } }],
    burstPolicy: "Exploratory burst gate passed; not a causal or incidence claim.",
    duration: {
      releaseId: "analysis-duration-v1-fixture",
      assessmentLane: "descriptive_with_runtime_gated_comparisons",
      status: "ready_descriptive",
      readinessStatus: "ready_descriptive",
      coverage: {
        active: {
          catalogRows: 400,
          normalizedRows: 160,
          descriptiveBinnedRows: 155,
          inferentialBinnedRows: 80,
          normalizedSources: [{ source: "nuforc", rows: 85 }, { source: "ufocat", rows: 75 }],
        },
        reference: { catalogRows: 300, normalizedRows: 120, descriptiveBinnedRows: 118, inferentialBinnedRows: 60 },
      },
      distribution: [
        { key: "1_4_minutes", label: "1–4 minutes", activeCount: 80, referenceCount: 55, activeShare: 80 / 155, referenceShare: 55 / 118, measurementClass: "descriptive_includes_source_declared_approximate_values" },
        { key: "5_14_minutes", label: "5–14 minutes", activeCount: 75, referenceCount: 63, activeShare: 75 / 155, referenceShare: 63 / 118, measurementClass: "descriptive_includes_source_declared_approximate_values" },
      ],
      comparisons: [
        { key: "1_4_minutes", label: "1–4 minutes", observedCount: 45, referenceCount: 32, adjustedDifference: 0.04, interval: { lower: 0.01, upper: 0.07 }, qValue: 0.04, inferenceEligible: true, measurementClass: "exact_or_closed_range_same_bin_only" },
        { key: "5_14_minutes", label: "5–14 minutes", observedCount: 35, referenceCount: 28, adjustedDifference: -0.04, oddsRatioInterval: { lower: 0.7, upper: 1.4 }, suppressionReasons: ["minimum_independent_sources"], inferenceEligible: false, measurementClass: "exact_or_closed_range_same_bin_only" },
      ],
      comparisonMetadata: { fdrFamily: "duration_bins_v1" },
      patternFinderEligible: false,
    },
  },
  craft: {
    distribution: [
      { label: "Disk", count: 80, adjustedDifference: 0.04, patch: { craft: ["disk"] } },
      { label: "Triangle", count: 40, adjustedDifference: -0.02, patch: { craft: ["triangle"] } },
      { label: "Light", count: 20, adjustedDifference: 0.01, patch: { craft: ["light"] } },
    ],
    reportTypes: [{ label: "Close encounter", count: 55, patch: { types: ["close_encounter"] } }],
    confidence: [{ label: "High", observed: 140, reference: 80 }],
    trends: [
      { row: "Disk", column: "1950s", observed: 80, reference: 40 },
      { row: "Disk", column: "1960s", observed: 65, reference: 50 },
      { row: "Triangle", column: "1950s", observed: 20, reference: 15 },
      { row: "Triangle", column: "1960s", observed: 30, reference: 18 },
    ],
    residuals: [{ row: "Disk", column: "Source A", residual: 2.1 }],
    byGeography: [
      { row: "Disk", column: "ea6x12:2:4", observedCount: 44, expectedCount: 30, adjustedResidual: 2.4, inferenceEligible: true },
      { row: "dumbbell_barbell", column: "ea6x12:3:5", observedCount: 16, expectedCount: 14, adjustedResidual: 0.5, inferenceEligible: false },
    ],
    sourceAssociation: {
      eligible: true,
      cramersV: 0.2,
      minimumExpectedCell: 12,
      policyWarning: "Every expected cell is at least 10 and table-level Cramer's V is at least 0.10; descriptive only.",
    },
  },
  geography: {
    equalAreaMap: {
      facets: [
        { coordinateClass: "source_coordinates", cells: [
          { latIndex: 2, lonIndex: 4, activeCount: 22, referenceCount: 15, adjustedActiveShare: 0.08, adjustedReferenceShare: 0.05, adjustedDifference: 0.03, differenceInterval: [0.01, 0.05], qValue: 0.04, commonSupportRate: 0.91, log2Enrichment: 0.55, preview: { kind: "area", area: { bounds: { west: -60, east: -30, south: -30, north: 0 } } } },
          { latIndex: 0, lonIndex: 0, activeCount: 0, referenceCount: 0, displayStatus: "structurally_empty", displayEligible: false, suppressionReasons: ["Both cohorts are empty"] },
        ] },
        { coordinateClass: "generalized_coordinates", cells: [{ latIndex: 3, lonIndex: 4, activeCount: 8, referenceCount: 12, adjustedDifference: -0.02, log2Enrichment: -0.4 }] },
      ],
    },
    cells: [{ row: "30–45°N", column: "0–15°E", count: 22, area: { west: 0, east: 15, south: 30, north: 45 } }],
    byTime: {
      fullCells: [{ row: "Europe", column: "1950s", count: 70, expectedCount: 55, standardizedResidual: 2.02 }],
    },
  },
  spatialEvidence: {
    status: "ready",
    cooccurrence: {
      crossSource: [{
        window: { label: "25 km / ±7 days", primary: true },
        status: "ready",
        cells: [
          { row: "Orb", column: "Disk", observedCount: 29, expectedCount: 24, log2Enrichment: 0.2, effectInterval: [0.02, 0.35], qValue: 0.04 },
          { row: "Disk", column: "Triangle", observedCount: 42, expectedCount: 28, log2Enrichment: 0.58, effectInterval: [0.2, 0.9], qValue: 0.02 },
          { row: "Triangle", column: "Disk", observedCount: 18, expectedCount: 24, log2Enrichment: -0.42, effectInterval: [-0.7, -0.1], qValue: 0.03 },
          { row: "dumbbell_barbell", column: "Orb", observedCount: 12, expectedCount: 8, log2Enrichment: 0.58, effectInterval: [0.1, 0.9], qValue: 0.04 },
        ],
      }],
      sameSource: [{
        label: "25 km / ±7 days",
        status: "suppressed",
        suppressionReasons: ["Source-specific lane is descriptive"],
        cells: [{ row: "Disk", column: "Disk", observedCount: 60, expectedCount: 55, log2Enrichment: 0.12 }],
      }],
      configuration: {
        status: "available",
        policyWarnings: ["Formation is a multi-object configuration lane and is never relabeled from dumbbell/barbell craft shape."],
        crossSource: [{
          window: { label: "25 km / ±7 days", primary: true },
          status: "ready",
          cells: [
            { row: "formation", column: "Disk", observedCount: 24, expectedCount: 12, log2Enrichment: 1, effectInterval: [0.5, 1.4], qValue: 0.01 },
            { row: "Disk", column: "formation", observedCount: 14, expectedCount: 12, log2Enrichment: 0.22, effectInterval: [-0.1, 0.5], qValue: 0.2 },
          ],
        }],
        sameSource: [],
      },
    },
    facility: {
      status: "suppressed",
      suppressionReasons: ["comparison_band_below_25"],
      inferentialFacilityN: 70,
      claimedFacilityN: 11,
      catalogSummary: {
        totalN: 1800,
        inferentialEligibleN: 70,
        descriptiveOnlyN: 1730,
        coverageLimitations: ["research_test_supplements_concentrated_in_northern_europe_and_new_zealand"],
      },
      policyWarnings: [
        "Research/test-site coverage is strongly limited to the Northern Europe and New Zealand supplements.",
      ],
      cells: [{
        label: "triangle",
        nearCount: 42,
        nearTotal: 150,
        comparisonCount: 28,
        comparisonTotal: 200,
        commonOddsRatio: 1.58,
        oddsRatioInterval: [1.12, 2.21],
        qValue: 0.03,
        status: "eligible",
      }],
      inactiveNegativeControl: {
        status: "exploratory",
        cells: [{ label: "triangle", nearCount: 18, comparisonCount: 24, commonOddsRatio: 0.95, oddsRatioInterval: [0.7, 1.2], qValue: 0.8, status: "eligible" }],
      },
      sensitivity: [{
        status: "sensitivity",
        nearRadiusKm: 10,
        cells: [{ label: "triangle", nearCount: 14, comparisonCount: 28, commonOddsRatio: 1.4, oddsRatioInterval: [0.9, 2.1], status: "sensitivity" }],
      }],
    },
    readiness: [
      { key: "cropCircles", label: "Crop circles", eligibleN: 10, totalN: 7745, status: "not_estimable", reason: "Fewer than 25 qualifying records", releaseHash: "sha256:crop-v2" },
      { key: "animalReports", label: "Animal reports", eligibleN: 0, totalN: 1177, status: "not_estimable", reason: "No exact coordinates", releaseHash: "sha256:animal-v2" },
      { key: "relationshipReconciliation", label: "Relationship reconciliation", eligibleN: 0, totalN: 1804, status: "not_estimable", reasons: ["Unresolved identifiers remain quarantined", "No analyst-reviewed association lane is eligible"], releaseHash: "sha256:relationships-v2", laneCounts: { explicitSource: 1250, computedCandidate: 554, analystReviewed: 0, reconciledCurrent: 1069, reconciledUnmapped: 251, quarantinedSubject: 460, quarantinedObject: 24, associationEligible: 0 } },
    ],
  },
  sourcesQuality: {
    sourceComposition: [{ label: "Source A", count: 240, patch: { sources: ["A"] } }],
    sourceByTime: [
      {
        row: "Source A",
        column: "1950s",
        value: 0.6,
        reference: 0.4,
        count: 240,
        referenceCount: 180,
        preview: {
          kind: "filter",
          patch: { sources: ["Source A"], dateRange: { startIso: "1950-01-01", endIso: "1959-12-31" } },
          cohortSize: 240,
          missingness: 0.125,
        },
      },
      { row: "Source B", column: "1950s", value: 0.4, reference: 0.6, count: 160, referenceCount: 270 },
      { row: "Source A", column: "1960s", value: 0.35, reference: 0.45, count: 140, referenceCount: 190 },
      { row: "Source B", column: "1960s", value: 0.65, reference: 0.55, count: 260, referenceCount: 230 },
    ],
    missingness: [{ row: "Craft", column: "Missing", rate: 0.2 }],
    audit: [{ row: "Fallback", column: "Fallback", count: 1 }],
    classifierAudit: [{ row: "Disk", column: "Disk", count: 50 }],
    classifierAuditPolicy: "Agreement audit only; classifier output is not ground truth.",
  },
  context: {
    crops: {
      enabled: true,
      status: "ready",
      activeCount: 210,
      referenceCount: 7300,
      totalProjectionRows: 7745,
      datasetHash: "sha256:crop",
      policyWarning: "Descriptive crop-circle records only. Date-window cohorts use stored inclusive date intervals.",
      summary: {
        unitLabel: "crop-circle records",
        missingnessPolicy: {
          unit: "records missing any required descriptive field",
          aggregation: "set union; each record contributes at most once",
          requiredFields: ["known date interval", "mapped state", "known morphology"],
        },
      },
      time: [{ label: "1990", count: 110 }],
      morphology: [{ label: "Circular", count: 200 }],
      crop: [{ label: "Wheat", count: 120 }],
      coordinateClass: [{ label: "Source coordinates", count: 160 }],
      coverage: [{ row: "Narrative", column: "Present", rate: 0.8 }],
    },
    animals: {
      enabled: true,
      status: "ready",
      activeCount: 80,
      referenceCount: 1040,
      totalProjectionRows: 1177,
      datasetHash: "sha256:animals",
      policyWarning: "Descriptive animal-report records only. Date-window cohorts use stored inclusive date intervals.",
      summary: {
        unitLabel: "animal reports",
        missingnessPolicy: {
          unit: "records missing any required descriptive field",
          aggregation: "set union; each record contributes at most once",
          requiredFields: ["known date interval", "mapped state", "known species group"],
        },
      },
      time: [{ label: "1990", count: 80 }],
      species: [{ label: "Cattle", count: 60 }],
      statusBreakdown: [{ label: "Reported · unreviewed", count: 75 }],
      datePrecision: [{ label: "Exact day", count: 32 }],
      coverage: [{ row: "Mapped", column: "Present", rate: 0.5 }],
    },
  },
  patterns: [stablePattern, sensitivePattern, sourceSpecificPattern],
  patternGroups: {
    stableMultiSourceContent: [stablePattern],
    sourceOrRegionSensitive: [sensitivePattern],
    collectionAndQuality: [sourceSpecificPattern],
  },
};

const durationEvidencePackage = analysis.buildEvidencePackage(result, { estimatorVersion: "duration-export-fixture" });
const durationDistributionRow = durationEvidencePackage.evidenceRows.find((row) => row.section === "time.duration.distribution" && row.duration_bin === "1_4_minutes");
assert.equal(durationDistributionRow.duration_release_id, "analysis-duration-v1-fixture");
assert.equal(durationDistributionRow.duration_assessment_lane, "descriptive_with_runtime_gated_comparisons");
assert.equal(durationDistributionRow.duration_measurement_class, "descriptive_includes_source_declared_approximate_values");
assert.equal(durationDistributionRow.active_share, 80 / 155);
const durationEvidenceCsv = analysis.evidencePackageToCsv(durationEvidencePackage);
assert.match(durationEvidenceCsv, /duration_bin,duration_measurement_class,duration_release_id,duration_assessment_lane/);
assert.match(durationEvidenceCsv, /1_4_minutes,descriptive_includes_source_declared_approximate_values,analysis-duration-v1-fixture,descriptive_with_runtime_gated_comparisons/);

controller.setBaselineMode("other_dates_balanced", { notify: false });
controller.setActiveSection("analysis-section-overview", { source: "test" });
controller.renderAnalysisResult(result);
assert.equal(controller.analysisState, "ready");
assert.equal(renderCompletions.at(-1).state, "ready", "render completion is observable only after the final chart job");
assert.equal(document.getElementById("analysis-content").hidden, false);
assert.equal(document.getElementById("analysis-mode-label").textContent, "Balanced comparison");
assert.equal(document.getElementById("analysis-date-range-chip-mode").getAttribute("data-comparison-state"), "inferential");
assert.equal(document.getElementById("analysis-active-count").textContent, "400");
assert.equal(document.getElementById("analysis-time-series-chart").children.length, 0, "hidden Time does not build chart DOM before activation");
assert.equal(document.getElementById("analysis-craft-distribution-chart").children.length, 0, "hidden Craft does not build chart DOM before activation");
assert.equal(document.getElementById("analysis-geography-grid-chart").children.length, 0, "hidden Geography does not build chart DOM before activation");
assert.equal(document.getElementById("analysis-cooccurrence-chart").children.length, 0, "hidden Spatial Evidence does not build chart DOM before activation");
assert.equal(document.getElementById("analysis-crop-time-chart").children.length, 0, "hidden Context does not build selected-subview chart DOM before activation");
assert.equal(document.getElementById("analysis-source-time-chart").children.length, 0, "hidden Sources & Quality does not build chart DOM before activation");
assert.ok(document.getElementById("analysis-coverage-chart").children.length >= 2);
const eligibilityText = descendants(document.getElementById("analysis-coverage-chart")).map((element) => element.textContent).join(" ");
assert.match(eligibilityText, /Mapped report points.*580,783.*Qualified craft point evidence.*33,801/i, "the spatial-point eligibility funnel exposes the qualified 33,801-report stage");
assert.match(descendants(document.getElementById("analysis-coverage-chart")).map((element) => element.getAttribute("aria-label") || "").join(" "), /33,801 eligible from 580,783.*546,982 excluded/i);
assert.equal(descendants(document.getElementById("analysis-comparison-chart")).filter((element) => element.className.includes("analysis-signal-spectrum-row")).length, 2);
assert.match(
  descendants(document.getElementById("analysis-comparison-chart")).map((element) => element.textContent).join(" "),
  /-4% · \[-6%, -2%\].*95% interval/
);
const compactSignalRows = descendants(document.getElementById("analysis-comparison-chart"))
  .filter((element) => element.className.includes("analysis-signal-spectrum-row"));
assert.match(compactSignalRows[0].getAttribute("aria-label"), /95% CI/i, "compact signal faces retain the full interval in their accessible label");
assert.match(compactSignalRows[0].getAttribute("title"), /95% CI/i, "compact signal faces expose the complete evidence on hover");
assert.ok(descendants(document.getElementById("analysis-comparison-chart")).some((element) => element.classList.contains("is-negative")));
const lowSupportForestRows = descendants(document.getElementById("analysis-comparison-chart"))
  .filter((element) => element.classList.contains("is-low-support"));
assert.equal(lowSupportForestRows.length, 1);
assert.equal(lowSupportForestRows[0].tagName, "BUTTON", "descriptive estimates retain local preview access");
assert.match(descendants(lowSupportForestRows[0]).map((element) => element.textContent).join(" "), /Descriptive estimate.*Common support below 80%/i);
controller.setActiveSection("analysis-section-time", { source: "test" });
assert.ok(document.getElementById("analysis-time-series-chart").children.some((child) => child.tagName === "SVG"));
assert.match(
  descendants(document.getElementById("analysis-time-series-chart")).map((element) => element.textContent).join(" "),
  /18%.*Active · source-balanced share.*Reference · source-balanced share.*Each source contributes equal total weight.*Adaptive display uses annual year bins.*Raw annual report counts.*121.*61/
);
const timelineViewButtons = descendants(document.getElementById("analysis-time-series-chart"))
  .filter((element) => element.className.includes("analysis-timeline-view-button"));
assert.deepEqual(timelineViewButtons.map((button) => button.textContent), ["Report volume", "Source-balanced activity", "Collection change"]);
timelineViewButtons[0].emit("click");
assert.ok(descendants(document.getElementById("analysis-time-series-chart")).some((element) => (element.getAttribute("class") || "").includes("analysis-series-uncertainty")), "report-volume mode overlays descriptive count uncertainty in the same adaptive timeline");
assert.match(descendants(document.getElementById("analysis-time-series-chart")).map((element) => element.textContent).join(" "), /approximate descriptive 95% Poisson interval/i);
const refreshedTimelineButtons = descendants(document.getElementById("analysis-time-series-chart"))
  .filter((element) => element.className.includes("analysis-timeline-view-button"));
refreshedTimelineButtons[2].emit("click");
assert.match(descendants(document.getElementById("analysis-time-series-chart")).map((element) => element.textContent).join(" "), /Source A.*Source B.*Largest displayed source-composition shift/i, "collection-change diagnostics reuse the existing source-composition evidence in the same card");
assert.ok(document.getElementById("analysis-month-year-chart").children.length >= 2);
assert.match(document.getElementById("analysis-duration-status").textContent, /160 normalized duration records across 2 sources.*40% of matched reports/i);
assert.match(descendants(document.getElementById("analysis-duration-chart")).map((element) => element.textContent).join(" "), /1–4 minutes.*51\.6%.*5–14 minutes.*48\.4%/i);
assert.match(descendants(document.getElementById("analysis-duration-chart")).map((element) => element.textContent).join(" "), /1–4 minutes.*46\.6%.*5–14 minutes.*53\.4%/i, "duration reference bars use reference shares, not reference counts formatted as percentages");
assert.match(descendants(document.getElementById("analysis-duration-comparison-chart")).map((element) => element.textContent).join(" "), /1–4 minutes.*\+4%.*95%/i);
assert.match(descendants(document.getElementById("analysis-duration-comparison-chart")).map((element) => element.textContent).join(" "), /minimum independent sources/i);
assert.match(descendants(document.getElementById("analysis-duration-comparison-chart")).map((element) => element.textContent).join(" "), /5–14 minutes.*-4%.*95% CI unavailable/i, "suppressed share differences do not relabel an odds-ratio interval as a percent interval");
assert.match(descendants(document.getElementById("analysis-month-year-chart")).map((element) => element.textContent).join(" "), /07\/JUL/, "month heatmaps use unambiguous chronological number/name labels");
const monthHeatmapHeaders = descendants(document.getElementById("analysis-month-year-chart"))
  .filter((element) => element.tagName === "TH" && /^\d{2}\/[A-Z]{3}$/.test(element.textContent))
  .map((element) => element.textContent);
assert.deepEqual(monthHeatmapHeaders, ["01/JAN", "02/FEB", "03/MAR", "04/APR", "05/MAY", "06/JUN", "07/JUL", "08/AUG", "09/SEP", "10/OCT", "11/NOV", "12/DEC"], "month-by-craft always shows the complete chronological calendar axis");
assert.equal(document.getElementById("analysis-decade-chart"), null, "the redundant decade panel is absent from the dashboard shell");
assert.equal(document.getElementById("analysis-rolling-chart"), null, "the redundant rolling comparison is absent from the dashboard shell");
assert.equal(document.getElementById("analysis-bursts-chart"), null, "the legacy burst panel is absent from the dashboard shell");
controller.setActiveSection("analysis-section-craft", { source: "test" });
assert.ok(document.getElementById("analysis-craft-confidence-chart").children.length >= 2);
assert.ok(descendants(document.getElementById("analysis-craft-distribution-chart")).some((element) => element.className.includes("analysis-craft-mosaic")), "craft distribution is a compact mosaic");
const mosaicTiles = descendants(document.getElementById("analysis-craft-distribution-chart"))
  .filter((element) => element.className.includes("analysis-craft-mosaic-tile"));
assert.equal(mosaicTiles.length, 3);
assert.equal(mosaicTiles[0].style.values.get("--analysis-mosaic-area-share"), (80 / 140).toFixed(8));
assert.equal(mosaicTiles[1].style.values.get("--analysis-mosaic-area-share"), (40 / 140).toFixed(8));
assert.match(mosaicTiles[0].style.values.get("--analysis-mosaic-fill"), /var\(--accent\)/, "positive adjusted effects use the teal diverging hue");
assert.match(mosaicTiles[1].style.values.get("--analysis-mosaic-fill"), /var\(--warn-text\)/, "negative adjusted effects use the amber diverging hue");
assert.ok(mosaicTiles.every((tile) => /%$/.test(tile.style.width) && /%$/.test(tile.style.height)), "mosaic tiles receive proportional two-dimensional rectangles");
assert.match(descendants(document.getElementById("analysis-craft-distribution-chart")).map((element) => element.textContent).join(" "), /Area = report share.*Teal = above.*amber = below/i);
assert.equal(document.getElementById("analysis-craft-geography-chart"), null, "craft-by-geography is consolidated into the Geography dashboard rather than rendered twice");
assert.equal(document.getElementById("analysis-report-type-chart").children.length, 0, "Sources & Quality remains deferred while Craft is active");
controller.setActiveSection("analysis-section-geography", { source: "test" });
assert.equal(
  descendants(document.getElementById("analysis-geography-grid-chart")).filter((element) => element.tagName === "SVG").length,
  2,
  "the geography renderer provides separate equal-area facets by coordinate class"
);
assert.equal(
  descendants(document.getElementById("analysis-geography-grid-chart")).filter((element) => element.tagName === "BUTTON" && element.className.includes("analysis-map-mode-button")).length,
  3,
  "adjusted difference, log2 enrichment, and count modes remain available"
);
assert.equal(
  descendants(document.getElementById("analysis-geography-grid-chart")).filter((element) => element.tagName === "RECT").length,
  2,
  "structurally empty geography cells are omitted instead of rendered as zero or suppressed"
);
assert.ok(
  descendants(document.getElementById("analysis-geography-time-chart")).some((element) => /Europe, 1950s/.test(element.getAttribute("aria-label") || "")),
  "geography-by-era association objects render their fullCells instead of collapsing to an empty panel"
);
const selectableMapCells = descendants(document.getElementById("analysis-geography-grid-chart"))
  .filter((element) => element.tagName === "RECT" && element.getAttribute("role") === "button");
assert.equal(selectableMapCells.length, 1);
selectableMapCells[0].emit("click");
assert.deepEqual(controller.currentPreview.area, { bounds: { west: -60, east: -30, south: -30, north: 0 } });
assert.deepEqual(
  controller.currentPreview.criteria.filter((criterion) => ["Coordinate class", "Adjusted active share", "Adjusted reference share", "Adjusted difference", "95% interval", "q-value", "Common support"].includes(criterion.label)),
  [
    { label: "Coordinate class", value: "source coordinates" },
    { label: "Adjusted active share", value: "8%" },
    { label: "Adjusted reference share", value: "5%" },
    { label: "Adjusted difference", value: "+3%" },
    { label: "95% interval", value: "[+1%, +5%]" },
    { label: "q-value", value: "0.04" },
    { label: "Common support", value: "91%" },
  ],
  "Area Filter previews disclose adjusted effects, uncertainty, support, and coordinate class before apply"
);
controller.hidePreview({ restoreFocus: false });
controller.setActiveSection("analysis-section-spatial", { source: "test" });
const cooccurrenceHeatmap = descendants(document.getElementById("analysis-cooccurrence-chart"))
  .find((element) => element.className.includes("analysis-heatmap-table"));
assert.ok(cooccurrenceHeatmap, "co-occurrence is a directed heatmap rather than a card wall");
assert.equal(descendants(document.getElementById("analysis-cooccurrence-chart")).filter((element) => element.tagName === "TD").length, 9, "co-occurrence uses one fixed square axis for focal and neighbor craft");
assert.equal(descendants(document.getElementById("analysis-cooccurrence-chart")).filter((element) => element.tagName === "TD" && element.classList.contains("is-diagonal")).length, 3, "every same-craft diagonal is explicit");
const cooccurrencePresentation = descendants(cooccurrenceHeatmap).map((element) => (element.textContent || "") + " " + (element.getAttribute("aria-label") || "")).join(" ");
assert.doesNotMatch(cooccurrencePresentation, /Formation/i, "Formation appears only in its separately selected configuration lane");
assert.doesNotMatch(cooccurrencePresentation, /dumbbell_barbell/i);
const cooccurrenceCompleteDetails = descendants(document.getElementById("analysis-cooccurrence-chart"))
  .find((element) => element.className.includes("analysis-data-details-lazy"));
cooccurrenceCompleteDetails.open = true;
cooccurrenceCompleteDetails.emit("toggle");
assert.match(descendants(cooccurrenceCompleteDetails).map((element) => element.textContent).join(" "), /dumbbell_barbell/, "the raw craft label remains in the expanded evidence table");
const cooccurrenceCell = descendants(document.getElementById("analysis-cooccurrence-chart"))
  .find((element) => /Disk, Triangle/.test(element.getAttribute("aria-label") || ""));
assert.match(cooccurrenceCell.getAttribute("aria-label"), /0.58.*O 42.*E 28.*95% CI.*q 0.02.*inferentially qualified/i);
const reverseCooccurrenceCell = descendants(document.getElementById("analysis-cooccurrence-chart"))
  .find((element) => /Triangle, Disk/.test(element.getAttribute("aria-label") || ""));
assert.match(reverseCooccurrenceCell.getAttribute("aria-label"), /-0.42.*O 18.*E 24/i, "directed asymmetry remains visible in the reverse cell");
assert.equal(descendants(cooccurrenceCell).filter((element) => element.classList.contains("analysis-heat-cell-counts")).length, 0, "compact heatmap faces show only the effect");
cooccurrenceCell.emit("click");
assert.equal(document.getElementById("analysis-preview-kind").textContent, "Evidence details");
assert.match(document.getElementById("analysis-preview-comparison").textContent, /Observed n=42.*conditional expected n=28/i);
assert.equal(document.getElementById("analysis-preview-apply-filters").hidden, true, "read-only cell inspection never offers a fabricated filter patch");
controller.hidePreview({ restoreFocus: false });
assert.equal(descendants(document.getElementById("analysis-cooccurrence-chart")).filter((element) => element.className.includes("analysis-evidence-item")).length, 0);
const cooccurrenceViewSelect = descendants(document.getElementById("analysis-cooccurrence-chart"))
  .find((element) => element.className.includes("analysis-evidence-view-select"));
assert.ok(cooccurrenceViewSelect, "co-occurrence exposes separate lane/window views");
assert.deepEqual(cooccurrenceViewSelect.children.map((option) => option.textContent), [
  "Cross-source · 25 km / ±7 days · primary",
  "Same-source · 25 km / ±7 days · sensitivity",
  "Formation configurations · Cross-source · 25 km / ±7 days · primary",
]);
cooccurrenceViewSelect.value = "2";
cooccurrenceViewSelect.emit("change");
const formationLaneText = descendants(document.getElementById("analysis-cooccurrence-chart")).map((element) => (element.textContent || "") + " " + (element.getAttribute("aria-label") || "")).join(" ");
assert.match(formationLaneText, /Formation configurations.*Formation.*Disk.*1.*O 24.*E 12/i);
assert.match(formationLaneText, /never relabeled from dumbbell\/barbell craft shape/i);
assert.equal(document.getElementById("analysis-cooccurrence-chart").classList.contains("shows-formation-configuration"), true);
const sameSourceSelect = descendants(document.getElementById("analysis-cooccurrence-chart"))
  .find((element) => element.className.includes("analysis-evidence-view-select"));
sameSourceSelect.value = "1";
sameSourceSelect.emit("change");
const sameSourceText = descendants(document.getElementById("analysis-cooccurrence-chart")).map((element) => element.textContent).join(" ");
assert.match(sameSourceText, /Same-source.*descriptive estimate remains visible/i);
const sameSourceCell = descendants(document.getElementById("analysis-cooccurrence-chart"))
  .find((element) => /Disk, Disk/.test(element.getAttribute("aria-label") || ""));
assert.match(sameSourceCell.getAttribute("aria-label"), /0.12.*O 60.*E 55/i, "effect-only faces retain observed and expected evidence in their accessible details");
assert.match(
  descendants(document.getElementById("analysis-facility-context-chart")).map((element) => element.textContent).join(" "),
  /triangle.*CMH odds ratio 1.58.*95% CI \[1.12, 2.21\].*q=0.03.*Near band n=42.*Comparison band n=28.*Descriptive estimate.*comparison band below 25/i
);
const facilityScopeText = descendants(document.getElementById("analysis-facility-context-chart"))
  .map((element) => element.textContent)
  .join(" ");
assert.match(facilityScopeText, /Qualified for inference.*70/i);
assert.match(facilityScopeText, /Full catalog shown descriptively.*1,800/i);
assert.match(facilityScopeText, /Descriptive-only markers.*1,730/i);
assert.match(facilityScopeText, /Claimed UFO sites.*descriptive only.*11/i);
assert.match(facilityScopeText, /Northern Europe and New Zealand/i);
assert.doesNotMatch(facilityScopeText, /[ÃâÂ�]/, "facility evidence labels contain no mojibake");
let facilityViewSelect = descendants(document.getElementById("analysis-facility-context-chart"))
  .find((element) => element.className.includes("analysis-evidence-view-select"));
assert.ok(facilityViewSelect, "facility evidence exposes primary, negative-control, and sensitivity views");
assert.deepEqual(facilityViewSelect.children.map((option) => option.textContent), [
  "Temporally active · 25 km vs 100–250 km · primary",
  "Inactive at event · negative control",
  "10 km active-facility radius · sensitivity",
]);
facilityViewSelect.value = "1";
facilityViewSelect.emit("change");
assert.match(descendants(document.getElementById("analysis-facility-context-chart")).map((element) => element.textContent).join(" "), /Inactive at event.*negative control.*CMH odds ratio 0.95/i);
facilityViewSelect = descendants(document.getElementById("analysis-facility-context-chart"))
  .find((element) => element.className.includes("analysis-evidence-view-select"));
facilityViewSelect.value = "2";
facilityViewSelect.emit("change");
assert.match(descendants(document.getElementById("analysis-facility-context-chart")).map((element) => element.textContent).join(" "), /10 km active-facility radius.*sensitivity.*CMH odds ratio 1.4/i);
controller.setActiveSection("analysis-section-context", { source: "test" });
controller.setActiveContextSubview("analysis-crop-context", { source: "test" });
const readinessText = descendants(document.getElementById("analysis-cross-domain-readiness-chart")).map((element) => element.textContent).join(" ");
assert.ok(descendants(document.getElementById("analysis-cross-domain-readiness-chart")).some((element) => element.className.includes("analysis-readiness-matrix")), "readiness is a domain-by-gate matrix");
assert.match(readinessText, /Crop circles.*10 \/ 7,745.*Blocked.*Animal reports.*0 \/ 1,177.*Blocked.*Relationship reconciliation.*0 \/ 1,804.*Blocked/i);
assert.match(readinessText, /Fewer than 25 qualifying records.*No exact coordinates.*Unresolved identifiers remain quarantined/i);
controller.setActiveSection("analysis-section-sources-quality", { source: "test" });
assert.ok(document.getElementById("analysis-report-type-chart").children.length >= 2);
assert.equal(document.getElementById("analysis-craft-trends-chart"), null, "the standalone craft trend duplicate is not rendered after classifier consistency");
assert.match(
  descendants(document.getElementById("analysis-craft-residual-chart")).map((element) => element.textContent).join(" "),
  /expected cell is at least 10.*Cramer's V is at least 0.10.*descriptive only/i
);
const sourceTimeText = descendants(document.getElementById("analysis-source-time-chart")).map((element) => element.textContent).join(" ");
assert.match(sourceTimeText, /1950s.*Active.*Reference.*100% stacked source composition/i);
assert.match(sourceTimeText, /Source A: 60%.*Source A: 40%/);
assert.match(sourceTimeText, /Source B: 40%.*Source B: 60%/);
assert.equal(
  descendants(document.getElementById("analysis-source-time-chart")).filter((element) => element.className === "analysis-composition-track").length,
  4,
  "active and reference are rendered as separate 100% stacked rows for both periods"
);
assert.match(
  descendants(document.getElementById("analysis-quality-audit-chart")).map((element) => element.textContent).join(" "),
  /Disk.*50.*not ground truth/
);
controller.setActiveSection("analysis-section-context", { source: "test" });
controller.setActiveContextSubview("analysis-relationship-context", { source: "test" });
const relationshipText = descendants(document.getElementById("analysis-relationship-readiness-chart")).map((element) => element.textContent).join(" ");
assert.match(relationshipText, /Relationship lane.*Explicit-source.*Computed candidate.*Analyst-reviewed.*Association eligible/i);
assert.match(relationshipText, /1,250.*554.*0.*Reconciliation.*1,069.*251.*Quarantine.*460.*24.*Output.*0/i, "relationship reconciliation and quarantine lanes are visible in Context");
controller.setActiveContextSubview("analysis-crop-context", { source: "test" });
assert.equal(document.getElementById("analysis-crop-context-status").textContent, "Crop-circle records: 210 active · 7,300 reference · 7,745 total projection rows.");
assert.ok(document.getElementById("analysis-crop-type-chart").children.length >= 2);
assert.match(
  descendants(document.getElementById("analysis-crop-readiness-chart")).map((element) => element.textContent).join(" "),
  /Crop circles.*10 \/ 7,745.*Blocked.*Fewer than 25 qualifying records.*sha256:crop-v2/i,
  "crop rehabilitation readiness is mirrored in the Crop Context group"
);
assert.match(
  descendants(document.getElementById("analysis-crop-context")).map((element) => element.textContent).join(" "),
  /Membership unit: crop-circle records.*stored inclusive date intervals.*Missingness membership unit: records missing.*each record contributes at most once/i
);
assert.ok(document.getElementById("analysis-crop-coordinate-chart").children.length >= 2);
const staleContextMembershipResult = structuredClone(result);
staleContextMembershipResult.context.crops.enabled = false;
staleContextMembershipResult.context.animals.enabled = false;
controller.renderAnalysisResult(staleContextMembershipResult, {
  filterSnapshot: {
    contextLayers: {
      crops: { enabled: true },
      animals: { enabled: true },
    },
  },
});
assert.equal(document.getElementById("analysis-include-crop-circles").getAttribute("aria-checked"), "true");
assert.equal(document.getElementById("analysis-crop-control-status").textContent, "Included");
assert.equal(document.getElementById("analysis-crop-content").hidden, false);
assert.equal(document.getElementById("analysis-crop-excluded").hidden, true, "the selected shared filter snapshot cannot render a stale excluded crop panel");
assert.equal(document.getElementById("analysis-include-animal-reports").getAttribute("aria-checked"), "true");
assert.equal(document.getElementById("analysis-animal-control-status").textContent, "Included");
assert.equal(document.getElementById("analysis-animal-content").hidden, false);
assert.equal(document.getElementById("analysis-animal-excluded").hidden, true, "the selected shared filter snapshot cannot render a stale excluded animal panel");
controller.renderAnalysisResult(result);
assert.equal(document.getElementById("analysis-animal-context").hidden, true, "rendering hidden context data does not expose a second tabpanel");
document.getElementById("analysis-context-tab-animals").emit("click");
assert.equal(document.getElementById("analysis-animal-context").hidden, false);
assert.equal(document.getElementById("analysis-crop-context").hidden, true);
assert.equal(document.getElementById("analysis-animal-context-status").textContent, "Animal reports: 80 active · 1,040 reference · 1,177 total projection rows.");
assert.ok(document.getElementById("analysis-animal-status-chart").children.length >= 2);
assert.ok(document.getElementById("analysis-animal-date-precision-chart").children.length >= 2);
assert.match(
  descendants(document.getElementById("analysis-animal-readiness-chart")).map((element) => element.textContent).join(" "),
  /Animal reports.*0 \/ 1,177.*Blocked.*No exact coordinates.*sha256:animal-v2/i,
  "animal rehabilitation readiness is mirrored in the Animal Context group"
);
controller.setActiveSection("analysis-section-overview", { source: "test" });
assert.equal(document.getElementById("analysis-pattern-count").textContent, "3");
assert.match(
  descendants(document.getElementById("analysis-pattern-list")).map((element) => element.textContent).join(" "),
  /Stable multi-source content shifts.*Disk share shift.*Relative enrichment 1.5x.*Source stability.*stable_multi_source.*3 sources tested.*Source- or region-sensitive findings.*July share shift.*Collection and data-quality shifts.*Source A composition shift/
);
assert.equal(document.getElementById("analysis-export-json").disabled, false);
document.getElementById("analysis-export-json").emit("click");
assert.equal(evidenceExports.at(-1).format, "json");
assert.equal(evidenceExports.at(-1).result, result);
assert.equal(evidenceExports.at(-1).package.filterSnapshot.generation, 12);
assert.match(evidenceExports.at(-1).text, /ufo-timeline-analysis-evidence-v2/);
assert.ok(
  evidenceExports.at(-1).package.evidenceRows.some((row) => row.section.includes("spatialEvidence.cooccurrence.crossSource[0].cells") && row.adjusted_effect === 0.58),
  "nested point-neighborhood cells are included in the downloadable evidence package"
);
assert.ok(
  evidenceExports.at(-1).package.evidenceRows.some((row) => row.section.includes("spatialEvidence.cooccurrence.crossSource[0].cells") && row.row_label === "dumbbell_barbell"),
  "the raw dumbbell/barbell craft category remains available in the evidence package even though it is omitted from the default visible matrix"
);
assert.ok(
  evidenceExports.at(-1).package.evidenceRows.some((row) => row.section.includes("geography.equalAreaMap.facets[0].cells") && row.adjusted_effect === 0.03),
  "nested equal-area cells are included in the downloadable evidence package"
);
document.getElementById("analysis-export-csv").emit("click");
assert.equal(evidenceExports.at(-1).format, "csv");
assert.match(evidenceExports.at(-1).text, /spatialEvidence\.cooccurrence\.crossSource\[0\]\.cells/);
assert.match(evidenceExports.at(-1).text, /dumbbell_barbell/);

controller.setActiveSection("analysis-section-sources-quality", { source: "test" });
const sourceCompositionButtons = descendants(document.getElementById("analysis-source-time-chart"))
  .filter((element) => element.tagName === "BUTTON" && element.className === "analysis-composition-segment");
assert.equal(sourceCompositionButtons.length, 1);
sourceCompositionButtons[0].emit("click");
assert.deepEqual(controller.currentPreview.patch, {
  sources: ["Source A"],
  dateRange: { startIso: "1950-01-01", endIso: "1959-12-31" },
});
assert.equal(document.getElementById("analysis-preview-missingness").textContent, "12.5%", "worker-provided numeric preview missingness is retained");
controller.hidePreview({ restoreFocus: false });

// Selectable chart marks stay local and open the preview drawer.
controller.setActiveSection("analysis-section-overview", { source: "test" });
const comparisonButtons = descendants(document.getElementById("analysis-comparison-chart"))
  .filter((element) => element.tagName === "BUTTON");
assert.equal(comparisonButtons.length, 2, "qualified and descriptive estimates can both open a non-mutating local preview");
comparisonButtons[0].emit("click");
assert.equal(document.getElementById("analysis-preview-drawer").hidden, false);
assert.deepEqual(controller.currentPreview.patch, { craft: ["disk"] });
controller.hidePreview({ restoreFocus: false });

// Spatial context evidence stays compact: a lane-controlled 4x4 heatmap and a
// separate provenance-lane relationship heatmap replace long card walls.
const contextEvidenceResult = structuredClone(result);
contextEvidenceResult.spatialEvidence.contextAssociations = {
  lanes: [{
    lane: "crop_bounded",
    contextClusterN: 406,
    policyWarnings: ["Catalog dates are not established formation times."],
    cells: [
      { row: "100_250_km", column: "8_30_days", observedClusterCount: 30, expectedClusterCount: 20, log2Enrichment: 0.585, effectInterval: [0.2, 0.8], qValue: 0.03, estimateAvailable: true, inferenceEligible: true },
      { row: "0_25_km", column: "same_day", observedClusterCount: 2, expectedClusterCount: 4, log2Enrichment: -1, supportReasons: ["observed_clusters_below_25"], estimateAvailable: true, inferenceEligible: false },
    ],
    featureAssociation: {
      cells: [{ row: "Disk", column: "Circular", observedCount: 28, expectedCount: 20, log2Enrichment: 0.485, estimateAvailable: true, inferenceEligible: true }],
      poolingThreshold: 25,
      completeAccessibleTable: { fullCells: [{ row: "Disk", column: "Circular", observedCount: 28, expectedCount: 20, log2Enrichment: 0.485 }] },
    },
  }, {
    lane: "crop_locality",
    contextClusterN: 3249,
    observedPairN: 68,
    excludedObservedPairN: 3,
    uncertaintyCounts: { ambiguous: 38, far: 30 },
    policyWarnings: ["Locality markers do not locate a formation site."],
    cells: [{ row: "100_250_km", column: "8_30_days", observedClusterCount: 38, expectedClusterCount: 31, log2Enrichment: 0.294, estimateAvailable: true, inferenceEligible: false }],
  }, {
    lane: "animal_public_marker",
    contextClusterN: 339,
    observedPairN: 41,
    excludedObservedPairN: 12,
    uncertaintyCounts: { ambiguous: 41 },
    policyWarnings: ["Public markers do not establish exact-site proximity."],
    cells: [{ row: "0_25_km", column: "same_day", observedClusterCount: 4, expectedClusterCount: 3, log2Enrichment: 0.32, estimateAvailable: true, inferenceEligible: false }],
    featureAssociation: {
      cells: [{ row: "Triangle", column: "Cattle", observedCount: 26, expectedCount: 20, log2Enrichment: 0.38, estimateAvailable: true, inferenceEligible: false }],
    },
  }],
};
contextEvidenceResult.spatialEvidence.relationshipSummary = {
  cells: [
    { lane: "explicit_source", relationshipType: "reported_nearby", reconciliation: "reconciled_current", count: 67 },
    { lane: "deterministic_match", relationshipType: "regional_context", reconciliation: "quarantined_object", count: 1737 },
  ],
};
controller.renderAnalysisResult(contextEvidenceResult);
controller.setActiveSection("analysis-section-spatial", { source: "test" });
const contextNeighborhoodText = descendants(document.getElementById("analysis-context-neighborhood-chart")).map((element) => element.textContent).join(" ");
assert.match(contextNeighborhoodText, /Bounded crop markers.*Same day.*8–30 days.*0–25 km.*-1.*100–250 km.*0.59/i);
const neighborhoodLabels = descendants(document.getElementById("analysis-context-neighborhood-chart")).map((element) => element.getAttribute("aria-label") || "").join(" ");
assert.match(neighborhoodLabels, /0–25 km.*Same day.*-1.*O 2.*E 4.*100–250 km.*8–30 days.*0.59.*O 30.*E 20/i);
assert.equal(document.getElementById("analysis-context-category-card").hidden, false);
assert.match(descendants(document.getElementById("analysis-context-category-chart")).map((element) => element.textContent).join(" "), /Circular.*Disk.*0.49/i);
assert.match(descendants(document.getElementById("analysis-context-category-chart")).map((element) => element.getAttribute("aria-label") || "").join(" "), /Circular.*Disk.*0.49.*O 28.*E 20/i);
assert.equal(descendants(document.getElementById("analysis-context-category-chart")).filter((element) => element.tagName === "OPTION").length, 2, "each context lane with feature evidence remains selectable while lanes without a feature table stay out of the selector");
assert.match(descendants(document.getElementById("analysis-context-category-chart")).map((element) => element.textContent).join(" "), /complete unpooled table remains available/i);
controller.setActiveSection("analysis-section-context", { source: "test" });
controller.setActiveContextSubview("analysis-crop-context", { source: "test" });
const cropSpatialText = descendants(document.getElementById("analysis-crop-spatial-chart")).map((element) => element.textContent).join(" ");
assert.match(cropSpatialText, /Bounded crop markers.*field candidates.*Crop locality markers/i, "the Crop subview exposes bounded-field and locality-marker point lanes without another readiness card");
const cropSpatialSelect = descendants(document.getElementById("analysis-crop-spatial-chart")).find((element) => element.tagName === "SELECT");
cropSpatialSelect.value = "1";
cropSpatialSelect.emit("change");
assert.match(descendants(document.getElementById("analysis-crop-spatial-chart")).map((element) => element.textContent).join(" "), /3,249 unique location-date clusters.*Locality markers do not locate a formation site/i);
controller.setActiveContextSubview("analysis-animal-context", { source: "test" });
const animalSpatialText = descendants(document.getElementById("analysis-animal-spatial-chart")).map((element) => element.textContent).join(" ");
assert.match(animalSpatialText, /Animal public markers.*uncertainty lane.*Contamination exclusions 12.*ambiguous 41.*Contamination audit: 12/i, "the Animal subview quantifies marker uncertainty and origin/publisher contamination exclusions");
controller.setActiveContextSubview("analysis-relationship-context", { source: "test" });
const relationshipCells = descendants(document.getElementById("analysis-relationship-readiness-chart")).filter((element) => element.className.includes("analysis-heat-cell"));
assert.match(relationshipCells.find((element) => /explicit source.*reconciled current/.test(element.getAttribute("aria-label") || "")).getAttribute("aria-label"), /reported nearby.*reconciled current.*67/i);
assert.match(relationshipCells.find((element) => /deterministic match.*quarantined object/.test(element.getAttribute("aria-label") || "")).getAttribute("aria-label"), /regional context.*quarantined object.*1,737/i);
controller._renderContextAssociations("analysis-animal-spatial-chart", {
  lanes: [{
    lane: "animal_public_marker",
    contextClusterN: 300,
    observedPairN: 0,
    cells: [{
      row: "0_25_km",
      column: "same_day",
      observedClusterCount: 0,
      expectedClusterCount: 0,
      displayStatus: "structurally_empty",
      estimateAvailable: false,
    }],
  }],
}, { activeCount: 1177 }, {
  allowedLanes: ["animal_public_marker"],
  emptyMessage: "Animal public-marker neighborhood evidence has not loaded.",
});
const loadedContextNoMatchText = descendants(document.getElementById("analysis-animal-spatial-chart")).map((element) => element.textContent).join(" ");
assert.match(loadedContextNoMatchText, /Evidence artifact loaded.*No eligible report-point neighborhoods match the active date window and filters/i);
assert.doesNotMatch(loadedContextNoMatchText, /has not loaded/i, "a loaded context artifact with no matching neighborhoods must not be reported as unloaded");

// An unavailable comparator falls back to populated descriptive geography,
// rather than hatching every occupied cell or leaving an empty map.
const geographyFallbackResult = structuredClone(result);
geographyFallbackResult.comparisonState = "unavailable_no_reference";
geographyFallbackResult.geography.equalAreaMap.facets[0].cells = [{
  latIndex: 2, lonIndex: 4, activeCount: 22, referenceCount: 0,
  displayStatus: "suppressed", suppressionReasons: ["No disjoint reference"],
}];
controller.renderAnalysisResult(geographyFallbackResult);
controller.setActiveSection("analysis-section-geography", { source: "test" });
assert.equal(document.getElementById("analysis-mode-label").textContent, "No valid reference");
const geographyModeButtons = descendants(document.getElementById("analysis-geography-grid-chart"))
  .filter((element) => element.className.includes("analysis-map-mode-button"));
assert.equal(geographyModeButtons.find((button) => /Active counts/.test(button.textContent)).getAttribute("aria-pressed"), "true");
const fallbackMapCell = descendants(document.getElementById("analysis-geography-grid-chart")).find((element) => element.tagName === "RECT");
assert.match(fallbackMapCell.getAttribute("aria-label"), /22 reports/i);
assert.doesNotMatch(fallbackMapCell.getAttribute("fill") || "", /hatch/);

// All Time is a true one-corpus presentation: the baseline is replaced,
// duplicate references disappear, and internal-structure findings remain.
const wholeCorpusResult = structuredClone(result);
wholeCorpusResult.analysisMode = "whole_corpus_structure";
wholeCorpusResult.comparisonState = "whole_corpus_structure";
wholeCorpusResult.summary.referenceCount = 0;
wholeCorpusResult.time.series = [
  { label: "2020", count: 30 },
  { label: "190", count: 2 },
  { label: "1960", count: 20 },
];
controller.renderAnalysisResult(wholeCorpusResult);
assert.equal(document.getElementById("analysis-mode-label").textContent, "Internal structure");
assert.equal(document.getElementById("analysis-date-range-chip-mode").textContent, "Internal structure");
assert.equal(document.getElementById("analysis-baseline").disabled, true);
assert.equal(document.getElementById("analysis-baseline").value, "whole_corpus_structure");
assert.match(document.getElementById("analysis-baseline-note").textContent, /All records.*internal structure.*no duplicate or fabricated reference/i);
assert.equal(document.getElementById("analysis-reference-count-card").hidden, true);
controller.setActiveSection("analysis-section-time", { source: "test" });
const wholeSeriesText = descendants(document.getElementById("analysis-time-series-chart")).map((element) => element.textContent).join(" ");
assert.match(wholeSeriesText, /All records.*190.*1960.*2020/i);
assert.doesNotMatch(wholeSeriesText, /Reference/);
assert.equal(descendants(document.getElementById("analysis-time-series-chart")).find((element) => element.tagName === "SVG").getAttribute("aria-label"), "Trend chart for all matched records");
controller.setActiveSection("analysis-section-craft", { source: "test" });
const wholeMosaicTiles = descendants(document.getElementById("analysis-craft-distribution-chart"))
  .filter((element) => element.className.includes("analysis-craft-mosaic-tile"));
assert.ok(wholeMosaicTiles.every((tile) => /var\(--accent\)/.test(tile.style.values.get("--analysis-mosaic-fill") || "")), "All Time mosaic hue encodes whole-corpus share intensity rather than a fabricated comparison");
assert.equal(descendants(document.getElementById("analysis-craft-distribution-chart")).filter((element) => element.className.includes("analysis-craft-mosaic-effect")).length, 0, "All Time mosaic omits adjusted-difference face labels");
controller.setActiveSection("analysis-section-sources-quality", { source: "test" });
assert.equal(descendants(document.getElementById("analysis-source-time-chart")).filter((element) => element.className === "analysis-composition-track").length, 2, "All Time draws one real composition row for each period and no duplicate reference row");
controller.setActiveSection("analysis-section-overview", { source: "test" });
assert.equal(document.getElementById("analysis-pattern-count").textContent, "3", "within-corpus findings remain eligible for display");
controller.setActiveSection("analysis-section-geography", { source: "test" });
const wholeCorpusMapCell = descendants(document.getElementById("analysis-geography-grid-chart")).find((element) => element.tagName === "RECT" && element.getAttribute("role") === "button");
assert.match(wholeCorpusMapCell.getAttribute("aria-label"), /report n=.*internal structure has no reference cohort/i);
assert.doesNotMatch(wholeCorpusMapCell.getAttribute("aria-label"), /reference n=/i);
wholeCorpusMapCell.emit("click");
assert.match(document.getElementById("analysis-preview-comparison").textContent, /reports in this grid cell.*no reference cohort/i);
assert.doesNotMatch(document.getElementById("analysis-preview-comparison").textContent, /active vs.*reference/i);
controller.hidePreview({ restoreFocus: false });

controller.destroy();
assert.equal(controller.listeners.length, 0);

// The controller consumes already-cached world geometry for a country
// choropleth. No network function is supplied or invoked, and repeated renders
// reuse the projected path cache while recoloring current evidence.
const choroplethDocument = createShellDocument();
const worldGeometry = {
  type: "FeatureCollection",
  features: [{
    type: "Feature",
    properties: { name: "France" },
    geometry: { type: "Polygon", coordinates: [[[-5, 42], [8, 42], [8, 51], [-5, 51], [-5, 42]]] },
  }, {
    type: "Feature",
    properties: { name: "Germany" },
    geometry: { type: "Polygon", coordinates: [[[5, 47], [15, 47], [15, 55], [5, 55], [5, 47]]] },
  }],
};
let worldGeometryReads = 0;
const choroplethController = new analysis.AnalysisViewController({
  document: choroplethDocument,
  getWorldReferenceData: () => {
    worldGeometryReads += 1;
    return worldGeometry;
  },
});
choroplethController.setAnalysisEnabled(true);
const choroplethResult = structuredClone(result);
choroplethResult.overview.comparison = Array.from({ length: 12 }, (_value, index) => ({
  label: "Signal " + String(index + 1).padStart(2, "0"),
  adjustedDifference: (index + 1) / 100,
  interval: [(index + 0.5) / 100, (index + 1.5) / 100],
  estimateAvailable: true,
  inferenceEligible: true,
}));
choroplethResult.geography.countryChoropleth = { cells: [{
  countryName: "France",
  coordinateClass: "source_coordinates",
  observedCount: 120,
  expectedCount: 80,
  adjustedDifference: 0.04,
  log2Enrichment: 0.585,
  estimateAvailable: true,
  inferenceEligible: true,
  preview: { kind: "area", area: { type: "country", country: "France" } },
  sourceMix: [{ source: "source-a", count: 90, share: 0.75 }, { source: "source-b", count: 30, share: 0.25 }],
  geographyAssignmentSource: "pinned_country_polygon",
  geographyAssignmentConfidence: "inside_polygon",
  geographyBoundaryStatus: "inside_country",
  geographyUnknownStatus: "assigned_country",
  macroregion: "Western Europe",
  geographyAssignmentProvenance: {
    assignmentSources: [{ value: "pinned_country_polygon", count: 120, share: 1 }],
    assignmentConfidences: [{ value: "inside_polygon", count: 120, share: 1 }],
    boundaryStatuses: [{ value: "inside_country", count: 120, share: 1 }],
    unknownStatuses: [{ value: "assigned_country", count: 120, share: 1 }],
    macroregions: [{ value: "Western Europe", count: 120, share: 1 }],
  },
}, {
  countryName: "France",
  coordinateClass: "generalized_coordinates",
  observedCount: 12,
  expectedCount: 20,
  adjustedDifference: -0.05,
  log2Enrichment: -0.737,
  estimateAvailable: true,
  inferenceEligible: false,
}], byDecade: [{
  countryName: "France",
  coordinateClass: "source_coordinates",
  period: "1950",
  observedCount: 30,
  referenceCount: 10,
  reportShare: 0.75,
  referenceReportShare: 0.25,
  sourceBalancedReportShare: 0.65,
  sourceBalancedShare: 0.65,
  referenceSourceBalancedReportShare: 0.2,
  sourceBalancedSourceN: 2,
  referenceSourceBalancedSourceN: 2,
  decadeFacetActiveN: 40,
  decadeFacetReferenceN: 40,
  adjustedDifference: 0.45,
  sourceMix: [{ source: "decade-source", count: 30, share: 1 }],
  geographyAssignmentSource: "decade_polygon",
  geographyAssignmentConfidence: "inside_polygon",
  geographyBoundaryStatus: "inside_country",
  geographyUnknownStatus: "assigned_country",
  macroregion: "Decade-local Western Europe",
  geographyAssignmentProvenance: {
    assignmentSources: [{ value: "decade_polygon", count: 30, share: 1 }],
    assignmentConfidences: [{ value: "inside_polygon", count: 30, share: 1 }],
    boundaryStatuses: [{ value: "inside_country", count: 30, share: 1 }],
    unknownStatuses: [{ value: "assigned_country", count: 30, share: 1 }],
    macroregions: [{ value: "Decade-local Western Europe", count: 30, share: 1 }],
  },
  preview: { kind: "area", area: { type: "country", country: "France" } },
}, {
  countryName: "Germany",
  coordinateClass: "source_coordinates",
  period: "1950",
  observedCount: 10,
  referenceCount: 30,
}], craftAssociations: { fullCells: [{
  countryName: "France",
  coordinateClass: "source_coordinates",
  craft: "triangle",
  row: "triangle",
  standardizedResidual: 2.4,
  observedCount: 24,
  expectedCount: 12,
  estimateAvailable: true,
}, {
  countryName: "Germany",
  coordinateClass: "source_coordinates",
  craft: "triangle",
  row: "triangle",
  standardizedResidual: -1.8,
  observedCount: 8,
  expectedCount: 16,
  estimateAvailable: true,
}] } };
choroplethResult.spatialEvidence.readiness = [{
  key: "cropBounded",
  label: "Bounded crop markers",
  status: "ready_sensitivity",
  inputN: 406,
  passedN: 406,
  totalN: 406,
  eligibleN: 406,
  policyId: "crop-bounded-v1",
  evidenceHash: "sha256:crop-bounded",
  gates: [{ gateId: "date_role", label: "Catalog date role", status: "ready_descriptive", inputN: 406, passedN: 406, reasonCodes: ["catalog_date_not_formation_date"] }],
}];
choroplethController.renderAnalysisResult(choroplethResult);
assert.equal(worldGeometryReads, 0, "cached world geometry is not requested while Geography remains hidden");
assert.equal(choroplethDocument.getElementById("analysis-geography-grid-chart").children.length, 0);
choroplethController.setActiveSection("analysis-section-geography", { source: "test" });
assert.equal(worldGeometryReads, 1);
assert.equal(choroplethController.worldPathCache.get(worldGeometry).size, 2);
const sensitivityPresentation = descendants(choroplethDocument.getElementById("analysis-geography-sensitivity-chart"));
assert.ok(choroplethController.worldEqualAreaPathCache.get(worldGeometry), "the advanced sensitivity view consumes the cached world-reference object");
assert.equal(choroplethController.worldEqualAreaPathCache.get(worldGeometry).length, 2, "the advanced sensitivity overlay caches Lambert equal-area land paths");
assert.ok(sensitivityPresentation.some((element) => element.tagName === "SVG" && element.getAttribute("viewBox") === "-42 -20 684 375"), "the labeled axes remain inside the equal-area SVG viewport");
assert.ok(sensitivityPresentation.some((element) => element.tagName === "PATH" && element.getAttribute("class") === "analysis-equal-area-land"), "advanced equal-area sensitivity overlays the cached land silhouette");
assert.ok(sensitivityPresentation.some((element) => element.tagName === "TEXT" && element.textContent === "Longitude"));
assert.ok(sensitivityPresentation.some((element) => element.tagName === "TEXT" && element.textContent === "Equal-area latitude"));
assert.ok(sensitivityPresentation.some((element) => element.tagName === "TEXT" && /180°W/.test(element.textContent)), "longitude context is labeled on the scientific sensitivity grid without mojibake");
const countryPaths = descendants(choroplethDocument.getElementById("analysis-geography-grid-chart")).filter((element) => element.tagName === "PATH");
assert.equal(countryPaths.length, 2);
const franceCountryPath = countryPaths.find((path) => /France/.test(path.getAttribute("aria-label") || ""));
assert.match(franceCountryPath.getAttribute("aria-label"), /\+4%.*observed n=120.*conditional expected n=80/i);
franceCountryPath.emit("click");
const countryEvidenceDrawerText = descendants(choroplethDocument.getElementById("analysis-preview-criteria")).map((element) => element.textContent).join(" ");
assert.match(countryEvidenceDrawerText, /Source mix: source-a 75% \(n=90\), source-b 25% \(n=30\)/i);
assert.match(countryEvidenceDrawerText, /Assignment source: pinned country polygon 100% \(n=120\).*Assignment confidence: inside polygon 100% \(n=120\).*Boundary status: inside country 100% \(n=120\).*Unknown status: assigned country 100% \(n=120\).*Macroregion: Western Europe 100% \(n=120\)/i);
choroplethController.hidePreview({ restoreFocus: false });
assert.equal(countryPaths.find((path) => path.getAttribute("data-country-key") === "germany").getAttribute("aria-hidden"), "true");
const countryCoordinateSelect = descendants(choroplethDocument.getElementById("analysis-geography-grid-chart")).find((element) => element.className === "analysis-country-coordinate-select");
assert.ok(countryCoordinateSelect, "country coordinate classes are separate selectable facets rather than silently overwriting each other");
countryCoordinateSelect.value = "generalized_coordinates";
countryCoordinateSelect.emit("change");
const generalizedCountryPaths = descendants(choroplethDocument.getElementById("analysis-geography-grid-chart")).filter((element) => element.tagName === "PATH");
assert.match(generalizedCountryPaths.find((path) => /France/.test(path.getAttribute("aria-label") || "")).getAttribute("aria-label"), /-5%.*observed n=12.*conditional expected n=20/i);
countryCoordinateSelect.value = "source_coordinates";
countryCoordinateSelect.emit("change");
const countryDecadeSelect = descendants(choroplethDocument.getElementById("analysis-geography-grid-chart")).find((element) => element.className === "analysis-country-decade-select");
assert.ok(countryDecadeSelect, "the country choropleth exposes a chronologically ordered decade selector");
assert.deepEqual(countryDecadeSelect.children.map((option) => option.textContent), ["All decades", "1950s"]);
countryDecadeSelect.value = "1950";
countryDecadeSelect.emit("change");
const decadeCountryPaths = descendants(choroplethDocument.getElementById("analysis-geography-grid-chart")).filter((element) => element.tagName === "PATH");
const decadeFrancePath = decadeCountryPaths.find((path) => /France/.test(path.getAttribute("aria-label") || ""));
assert.match(decadeFrancePath.getAttribute("aria-label"), /\+45%.*observed n=30.*reference n=10/i, "selected-decade color and label preserve the adjusted comparison metric with decade-local Ns");
const decadeShareButton = descendants(choroplethDocument.getElementById("analysis-geography-grid-chart")).find((element) => element.tagName === "BUTTON" && /Adjusted difference/.test(element.textContent));
assert.equal(decadeShareButton.getAttribute("aria-pressed"), "true");
const decadeLegend = descendants(choroplethDocument.getElementById("analysis-geography-grid-chart")).find((element) => element.className === "analysis-map-legend");
assert.match(decadeLegend.textContent, /1950s adjusted within-decade share difference.*counts are decade-local/i);
decadeFrancePath.emit("click");
const decadeDrawerText = descendants(choroplethDocument.getElementById("analysis-preview-criteria")).map((element) => element.textContent).join(" ");
assert.match(decadeDrawerText, /Source-balanced within-decade share: 65%.*Reference reports in decade: 10.*Adjusted within-decade share difference: \+45%.*Selected-decade coordinate-facet reports: 40/i);
assert.match(decadeDrawerText, /Source mix: decade-source 100% \(n=30\).*Assignment source: decade polygon 100% \(n=30\).*Macroregion: Decade-local Western Europe 100% \(n=30\)/i, "drawer retains decade-local source mix and geography provenance");
assert.doesNotMatch(decadeDrawerText, /source-a|pinned country polygon/i, "whole-country source and provenance never leak into selected-decade evidence");
assert.match(choroplethDocument.getElementById("analysis-preview-comparison").textContent, /Selected-decade active n=30.*reference n=10/i);
choroplethController.hidePreview({ restoreFocus: false });
const selectedCraftButton = descendants(choroplethDocument.getElementById("analysis-geography-grid-chart")).find((element) => element.tagName === "BUTTON" && /Selected craft/.test(element.textContent));
assert.ok(selectedCraftButton, "the country choropleth exposes a selected-craft association mode");
selectedCraftButton.emit("click");
const countryCraftSelect = descendants(choroplethDocument.getElementById("analysis-geography-grid-chart")).find((element) => element.className === "analysis-country-craft-select");
assert.equal(countryCraftSelect.value, "triangle");
const craftCountryPaths = descendants(choroplethDocument.getElementById("analysis-geography-grid-chart")).filter((element) => element.tagName === "PATH");
assert.match(craftCountryPaths.find((path) => /France/.test(path.getAttribute("aria-label") || "")).getAttribute("aria-label"), /2\.4 adjusted residual.*observed n=24.*conditional expected n=12/i);
choroplethController.setActiveSection("analysis-section-overview", { source: "test" });
assert.equal(descendants(choroplethDocument.getElementById("analysis-comparison-chart")).filter((element) => element.className.includes("analysis-signal-spectrum-row")).length, 6, "the Overview face presents the six strongest effects within the approved maximum of eight");
choroplethController.setActiveSection("analysis-section-context", { source: "test" });
const typedReadinessText = descendants(choroplethDocument.getElementById("analysis-cross-domain-readiness-chart")).map((element) => element.textContent).join(" ");
assert.match(typedReadinessText, /Location.*Date.*Provenance.*Lineage.*Review.*Sample.*Output/i, "the readiness matrix exposes the fixed compact domain columns");
assert.match(typedReadinessText, /Catalog date role.*Gate date_role.*passed\/input 406 \/ 406/i, "the expandable ledger retains every original typed gate and its counts");
const wholeCorpusChoroplethResult = structuredClone(choroplethResult);
wholeCorpusChoroplethResult.analysisMode = "whole_corpus_structure";
wholeCorpusChoroplethResult.comparisonState = "whole_corpus_structure";
wholeCorpusChoroplethResult.summary.referenceCount = 0;
choroplethController.renderAnalysisResult(wholeCorpusChoroplethResult);
choroplethController.setActiveSection("analysis-section-geography", { source: "test" });
const wholeCountryModeLabels = descendants(choroplethDocument.getElementById("analysis-geography-grid-chart"))
  .filter((element) => element.className.includes("analysis-map-mode-button"))
  .map((element) => element.textContent);
const wholeSensitivityModeLabels = descendants(choroplethDocument.getElementById("analysis-geography-sensitivity-chart"))
  .filter((element) => element.className.includes("analysis-map-mode-button"))
  .map((element) => element.textContent);
assert.deepEqual(wholeCountryModeLabels, ["Source-balanced share", "Selected craft", "Report count"], "whole-corpus country geography hides reference-dependent enrichment mode");
assert.deepEqual(wholeSensitivityModeLabels, ["Report share", "Report counts"], "whole-corpus equal-area sensitivity hides reference-dependent enrichment mode");
assert.ok(wholeCountryModeLabels.concat(wholeSensitivityModeLabels).every((label) => !/Log/i.test(label)));
const wholeCorpusDecadeSelect = descendants(choroplethDocument.getElementById("analysis-geography-grid-chart")).find((element) => element.className === "analysis-country-decade-select");
wholeCorpusDecadeSelect.value = "1950";
wholeCorpusDecadeSelect.emit("change");
const wholeCorpusDecadePaths = descendants(choroplethDocument.getElementById("analysis-geography-grid-chart")).filter((element) => element.tagName === "PATH");
const wholeCorpusFranceDecadePath = wholeCorpusDecadePaths.find((path) => /France/.test(path.getAttribute("aria-label") || ""));
assert.match(wholeCorpusFranceDecadePath.getAttribute("aria-label"), /65%.*observed n=30/i, "All-Time decade geography keeps the source-balanced corpus metric");
assert.doesNotMatch(wholeCorpusFranceDecadePath.getAttribute("aria-label"), /reference|expected/i, "All-Time decade geography never exposes a fabricated reference");
wholeCorpusFranceDecadePath.emit("click");
assert.match(choroplethDocument.getElementById("analysis-preview-comparison").textContent, /Selected-decade reports n=30.*No reference cohort/i);
assert.doesNotMatch(descendants(choroplethDocument.getElementById("analysis-preview-criteria")).map((element) => element.textContent).join(" "), /Reference reports in decade/i);
choroplethController.hidePreview({ restoreFocus: false });
choroplethController.renderAnalysisResult(choroplethResult);
assert.equal(worldGeometryReads, 1, "rerendering reuses the cached in-memory world geometry without refetching or rereading it");
choroplethController.setActiveSection("analysis-section-geography", { source: "test" });
assert.equal(choroplethController.worldPathCache.get(worldGeometry).size, 2, "projected geometry remains cached across recolors");
assert.equal(choroplethController.worldEqualAreaPathCache.get(worldGeometry).length, 2, "equal-area land geometry remains cached across result invalidation");
choroplethController.destroy();

// Direct hashes activate the corresponding selected dashboard. Nested context
// hashes activate Context without making multiple panels perceivable.
const hashDocument = createShellDocument();
const hashListeners = new Map();
const hashView = {
  location: { hash: "#analysis-section-craft" },
  history: { replaceState(_state, _title, hash) { hashView.location.hash = hash; } },
  matchMedia() { return { matches: true }; },
  addEventListener(name, handler) {
    if (!hashListeners.has(name)) hashListeners.set(name, []);
    hashListeners.get(name).push(handler);
  },
  removeEventListener(name, handler) {
    hashListeners.set(name, (hashListeners.get(name) || []).filter((candidate) => candidate !== handler));
  },
  emit(name) { (hashListeners.get(name) || []).forEach((handler) => handler({ type: name })); },
};
hashDocument.defaultView = hashView;
const hashController = new analysis.AnalysisViewController({ document: hashDocument });
hashController.setAnalysisEnabled(true);
hashController.setActiveView("analysis");
assert.equal(hashController.activeSectionId, "analysis-section-craft");
assert.equal(hashDocument.getElementById("analysis-section-craft").hidden, false);
hashView.location.hash = "#analysis-animal-context";
hashView.emit("hashchange");
assert.equal(hashController.activeSectionId, "analysis-section-context");
assert.equal(hashDocument.getElementById("analysis-section-context").hidden, false);
assert.equal(hashDocument.getElementById("analysis-section-craft").hidden, true);
assert.equal(hashDocument.getElementById("analysis-section-context").scrollIntoViewCalls.length, 0, "direct hashes switch panels without document-flow scrolling");
assert.equal(hashDocument.getElementById("analysis-animal-context").scrollIntoViewCalls.length, 1, "nested direct hashes reveal the requested context group");
assert.equal(hashDocument.getElementById("analysis-animal-context").scrollIntoViewCalls[0].behavior, "auto", "nested hash navigation honors reduced motion");
assert.equal(hashDocument.getElementById("analysis-context-tab-animals").getAttribute("aria-selected"), "true");
assert.equal(hashDocument.getElementById("analysis-animal-context").hidden, false);
assert.equal(hashDocument.getElementById("analysis-crop-context").hidden, true);
assert.equal(hashDocument.getElementById("analysis-crop-context").inert, true);
hashDocument.getElementById("analysis-context-tab-relationships").emit("click");
assert.equal(hashView.location.hash, "#analysis-relationship-context", "subview clicks preserve a direct-linkable nested hash");
assert.equal(hashDocument.getElementById("analysis-relationship-context").hidden, false);
assert.equal(hashDocument.activeElement, hashDocument.getElementById("analysis-context-tab-relationships"));
hashDocument.getElementById("analysis-context-subview-tabs").emit("keydown", {
  key: "Home",
  target: hashDocument.getElementById("analysis-context-tab-relationships"),
});
assert.equal(hashView.location.hash, "#analysis-crop-context", "keyboard subview activation updates the nested hash");
assert.equal(hashDocument.getElementById("analysis-crop-context").hidden, false);
assert.equal(hashDocument.getElementById("analysis-animal-context").getAttribute("aria-hidden"), "true");
hashController.destroy();

// When Context is the visible dashboard, its selected subview renders before
// offscreen core charts so a ready artifact cannot leave the visible panel
// looking unloaded while background frame work drains.
const contextPriorityFrames = createFrameHarness();
const contextPriorityDocument = createShellDocument();
const contextPriorityController = new analysis.AnalysisViewController({
  document: contextPriorityDocument,
  requestAnimationFrame: contextPriorityFrames.requestAnimationFrame,
  cancelAnimationFrame: contextPriorityFrames.cancelAnimationFrame,
});
contextPriorityController.setAnalysisEnabled(true);
contextPriorityController.setActiveView("analysis");
contextPriorityController.setActiveSection("analysis-section-context", { source: "test" });
contextPriorityController.setActiveContextSubview("analysis-animal-context", { source: "test" });
contextPriorityController.renderAnalysisResult(result);
assert.equal(contextPriorityDocument.getElementById("analysis-animal-readiness-chart").children.length, 0);
assert.equal(contextPriorityDocument.getElementById("analysis-coverage-chart").children.length, 0);
contextPriorityFrames.flushOne();
assert.ok(contextPriorityDocument.getElementById("analysis-animal-readiness-chart").children.length > 0, "the selected Animal Context evidence is the first progressive render job");
assert.equal(contextPriorityDocument.getElementById("analysis-coverage-chart").children.length, 0, "offscreen Overview work waits until selected Context evidence is visible");
contextPriorityController.destroy();

// Real-browser rendering yields one chart job per frame, rejects stale frame
// callbacks by generation, and does not expose Ready until the final job.
const frameHarness = createFrameHarness();
const progressiveDocument = createShellDocument();
const progressiveController = new analysis.AnalysisViewController({
  document: progressiveDocument,
  requestAnimationFrame: frameHarness.requestAnimationFrame,
  cancelAnimationFrame: frameHarness.cancelAnimationFrame,
});
const staticProgressiveListenerCount = progressiveController.listeners.length;
progressiveController.setAnalysisEnabled(true);
progressiveController.setActiveView("analysis");
progressiveController.renderAnalysisResult(result);
assert.equal(progressiveController.renderPending, true);
assert.equal(progressiveController.analysisState, "loading");
assert.equal(frameHarness.pendingCount(), 1, "only one chart job should be scheduled per frame");
assert.equal(progressiveDocument.getElementById("analysis-coverage-chart").children.length, 0);
assert.equal(progressiveDocument.getElementById("analysis-crop-time-chart").children.length, 0);

frameHarness.flushOne();
assert.ok(progressiveDocument.getElementById("analysis-coverage-chart").children.length > 0);
assert.equal(progressiveDocument.getElementById("analysis-comparison-chart").children.length, 0);
assert.equal(progressiveDocument.getElementById("analysis-crop-time-chart").children.length, 0);
const staleGeneration = progressiveController.renderGeneration;
const staleFrameCallback = frameHarness.peekCallback();

const largeYears = Array.from({ length: 120 }, (_value, index) => ({
  label: String(1900 + index),
  count: 100 + index,
  referenceCount: 80 + index,
  patch: { dateRange: { startIso: String(1900 + index) + "-01-01", endIso: String(1900 + index) + "-12-31" } },
}));
const largeMonthYear = heatmapYears.flatMap((year, yearIndex) => heatmapMonths.map((month, monthIndex) => ({
  row: year,
  column: month,
  count: yearIndex + monthIndex + 1,
  patch: { dateRange: { startIso: year + "-" + month + "-01", endIso: year + "-" + month + "-28" } },
})));
const progressiveResult = Object.assign({}, result, {
  summary: Object.assign({}, result.summary, { activeCount: 401 }),
  time: Object.assign({}, result.time, {
    series: largeYears,
    annualSeries: largeYears,
    sourceBalanced: largeYears.map(function (item, index) {
      return {
        label: item.label,
        observed: (index + 1) / 200,
        reference: (index + 1) / 250,
      };
    }),
    rolling: largeYears,
    monthYear: largeMonthYear,
    bursts: [],
  }),
});
progressiveController.renderAnalysisResult(progressiveResult);
assert.ok(progressiveController.renderGeneration > staleGeneration);
assert.equal(frameHarness.pendingCount(), 1, "a newer result must cancel the prior scheduled frame");
staleFrameCallback(16);
assert.equal(frameHarness.pendingCount(), 1, "a stale callback must not consume the current generation's frame");
progressiveController.setAnalysisState("ready");
assert.equal(progressiveController.analysisState, "loading", "Ready is deferred until all current render jobs finish");

const flushedFrames = frameHarness.flushAll();
assert.ok(flushedFrames >= 4 && flushedFrames <= 6, "only the active Overview dashboard should render in its bounded frame batch; observed " + flushedFrames + "; state " + progressiveController.analysisState + "; error " + progressiveDocument.getElementById("analysis-error-message").textContent);
assert.equal(progressiveController.renderPending, false);
assert.equal(progressiveController.analysisState, "ready");
assert.equal(progressiveDocument.getElementById("analysis-content").hidden, false);
assert.equal(progressiveDocument.getElementById("analysis-active-count").textContent, "401");
assert.equal(progressiveDocument.getElementById("analysis-time-series-chart").children.length, 0, "the hidden Time dashboard remains unmaterialized after Overview finishes");
assert.equal(progressiveDocument.getElementById("analysis-crop-time-chart").children.length, 0, "the hidden Crop subview remains unmaterialized after Overview finishes");
assert.equal(progressiveDocument.getElementById("analysis-animal-time-chart").children.length, 0, "the hidden Animal subview remains unmaterialized after Overview finishes");

progressiveController.setActiveSection("analysis-section-time", { source: "test" });
assert.equal(frameHarness.pendingCount(), 1, "activating Time schedules its first deferred chart job");
const timeFrames = frameHarness.flushAll();
assert.ok(timeFrames >= 4 && timeFrames <= 6, "Time renders its timeline, duration readiness, and month-by-craft charts plus completion and alignment work");
assert.match(progressiveDocument.getElementById("analysis-duration-status").textContent, /160 normalized duration records across 2 sources/i);
assert.ok(progressiveDocument.getElementById("analysis-duration-chart").children.length > 0, "duration materializes with the rest of the requested Time dashboard");

const progressiveTimeChart = progressiveDocument.getElementById("analysis-time-series-chart");
const plottedPoints = descendants(progressiveTimeChart).filter((element) => element.tagName === "CIRCLE");
assert.equal(plottedPoints.length, analysis.SERIES_POINT_LIMIT * 2);
assert.equal(plottedPoints.filter((element) => element.classList.contains("is-selectable")).length, analysis.SERIES_POINT_LIMIT);
const timeDataDetails = progressiveTimeChart.children.filter((element) => element.tagName === "DETAILS");
assert.equal(timeDataDetails.length, 2, "sampled plot values and raw annual counts retain accessible tables");
assert.equal(
  descendants(timeDataDetails.at(-1)).filter((element) => element.tagName === "TR").length,
  analysis.SERIES_POINT_LIMIT + 1,
  "raw annual accessible rows must use the same deterministic cap plus one header row"
);
assert.match(
  [progressiveTimeChart, ...descendants(progressiveTimeChart)].map((element) => element.textContent).join(" "),
  /shared chronological axis is ordered before it is evenly sampled to at most 48 periods.*complete accessible table retains every period.*raw annual accessible table is evenly sampled to 48 periods/i
);

const progressiveMonthYearChart = progressiveDocument.getElementById("analysis-month-year-chart");
assert.equal(
  descendants(progressiveMonthYearChart).filter((element) => element.tagName === "TD").length,
  analysis.HEATMAP_CELL_LIMIT,
  "the largest live heatmap must stay within the per-frame DOM cell budget"
);
assert.match(
  [progressiveMonthYearChart, ...descendants(progressiveMonthYearChart)].map((element) => element.textContent).join(" "),
  /12 of 697 highest-information rows and 12 of 12 highest-information columns.*at most 144 cells.*calculations.*every cell/i
);

// Reproduce the live navigation sequence that exposed the v2.2 regression:
// Overview -> Time -> Craft. Completed dashboards stay warm, while every
// never-opened dashboard remains empty. The injected Geography child models a
// late/stale callback and must be swept because no Geography plan owns it.
const progressiveOverviewFirstChild = progressiveDocument.getElementById("analysis-coverage-chart").children[0];
const progressiveTimeFirstChild = progressiveTimeChart.children[0];
const strayGeographyChild = progressiveDocument.createElement("div");
progressiveDocument.getElementById("analysis-geography-grid-chart").appendChild(strayGeographyChild);
assert.equal(progressiveDocument.getElementById("analysis-geography-grid-chart").children.length, 1);

progressiveController.setActiveSection("analysis-section-craft", { source: "test" });
assert.equal(frameHarness.pendingCount(), 1, "activating Craft schedules only its deferred plan");
frameHarness.flushAll();
assert.ok(progressiveDocument.getElementById("analysis-craft-distribution-chart").children.length > 0);
assert.equal(
  progressiveDocument.getElementById("analysis-coverage-chart").children[0],
  progressiveOverviewFirstChild,
  "completed Overview DOM remains warm after visiting Time and Craft"
);
assert.equal(
  progressiveTimeChart.children[0],
  progressiveTimeFirstChild,
  "completed Time DOM remains warm after visiting Craft"
);
[
  "analysis-geography-grid-chart",
  "analysis-geography-sensitivity-chart",
  "analysis-geography-time-chart",
  "analysis-cooccurrence-chart",
  "analysis-spatial-eligibility-chart",
  "analysis-context-neighborhood-chart",
  "analysis-context-category-chart",
  "analysis-facility-context-chart",
  "analysis-cross-domain-readiness-chart",
  "analysis-crop-time-chart",
  "analysis-animal-time-chart",
  "analysis-relationship-readiness-chart",
  "analysis-report-type-chart",
  "analysis-craft-residual-chart",
  "analysis-source-composition-chart",
  "analysis-source-time-chart",
  "analysis-quality-missingness-chart",
  "analysis-quality-audit-chart",
].forEach((targetId) => {
  assert.equal(
    progressiveDocument.getElementById(targetId).children.length,
    0,
    targetId + " must remain unmaterialized until its dashboard or Context subview is opened"
  );
});

progressiveController.setActiveSection("analysis-section-overview", { source: "test" });
assert.equal(frameHarness.pendingCount(), 0, "returning to a warm dashboard schedules no chart work");
assert.equal(progressiveDocument.getElementById("analysis-coverage-chart").children[0], progressiveOverviewFirstChild);

progressiveController.setActiveSection("analysis-section-context", { source: "test" });
progressiveController.setActiveContextSubview("analysis-crop-context", { source: "test" });
frameHarness.flushAll();
assert.ok(progressiveDocument.getElementById("analysis-crop-time-chart").children.length > 0, "the selected Crop subview materializes on demand");
assert.equal(progressiveDocument.getElementById("analysis-animal-time-chart").children.length, 0, "the unselected Animal subview remains unmaterialized");
progressiveController.setActiveContextSubview("analysis-animal-context", { source: "test" });
frameHarness.flushAll();
assert.ok(progressiveDocument.getElementById("analysis-animal-time-chart").children.length > 0, "the Animal subview materializes only after selection");
assert.equal(
  progressiveController.listeners.length,
  staticProgressiveListenerCount,
  "rerendered chart nodes must not accumulate in the controller listener registry"
);

progressiveController.destroy();
assert.equal(frameHarness.pendingCount(), 0);
assert.equal(progressiveController.renderPending, false);

// A viewport resize must reveal the current link even when native
// IntersectionObserver owns vertical scrollspy updates. This covers mobile
// rotation and responsive-pane width changes without requiring another
// section intersection.
const resizeDocument = createShellDocument();
const resizeFrames = createFrameHarness();
const resizeListeners = new Map();
const resizeView = {
  location: { hash: "" },
  history: {
    replaceState(_state, _title, hash) {
      resizeView.location.hash = hash;
    },
  },
  matchMedia() {
    return { matches: true };
  },
  addEventListener(name, handler) {
    if (!resizeListeners.has(name)) resizeListeners.set(name, []);
    resizeListeners.get(name).push(handler);
  },
  removeEventListener(name, handler) {
    resizeListeners.set(name, (resizeListeners.get(name) || []).filter((candidate) => candidate !== handler));
  },
  emit(name) {
    (resizeListeners.get(name) || []).forEach((handler) => handler({ type: name }));
  },
};
resizeDocument.defaultView = resizeView;
class ResizeIntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
const resizeController = new analysis.AnalysisViewController({
  document: resizeDocument,
  IntersectionObserver: ResizeIntersectionObserver,
  requestAnimationFrame: resizeFrames.requestAnimationFrame.bind(resizeFrames),
  cancelAnimationFrame: resizeFrames.cancelAnimationFrame.bind(resizeFrames),
});
resizeController.setAnalysisEnabled(true);
resizeController.setActiveView("analysis");
const resizeNav = resizeDocument.getElementById("analysis-section-nav");
resizeNav.rect = { top: 8, left: 0, right: 710, bottom: 68, width: 710, height: 60 };
const resizeSpatialLink = resizeNav.children[4];
resizeSpatialLink.rect = { top: 16, left: 400, right: 500, bottom: 52, width: 100, height: 36 };
resizeController.navigateToSection("analysis-section-spatial", { focus: false });
resizeNav.scrollCalls = [];
resizeNav.scrollLeft = 0;
resizeNav.rect = { top: 8, left: 0, right: 320, bottom: 68, width: 320, height: 60 };
[
  [-1000, "analysis-section-overview"],
  [-800, "analysis-section-time"],
  [-600, "analysis-section-craft"],
  [-400, "analysis-section-geography"],
  [84, "analysis-section-spatial"],
  [900, "analysis-section-sources-quality"],
  [1500, "analysis-section-context"],
].forEach(([top, id]) => {
  resizeDocument.getElementById(id).rect = { top, left: 0, right: 320, bottom: top + 300, width: 320, height: 300 };
});
resizeView.emit("resize");
resizeFrames.flushAll();
assert.equal(resizeController.activeSectionId, "analysis-section-spatial");
assert.equal(resizeNav.scrollCalls.length, 1);
assert.equal(resizeNav.scrollLeft, 188, "the active mobile link is moved inside the narrowed rail");
resizeController.destroy();

console.log("analysis view assertions passed");
