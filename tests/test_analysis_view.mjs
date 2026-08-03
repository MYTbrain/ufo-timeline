import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const analysis = require("../webapp/static_public/analysis_view.js");

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

  scrollIntoView() {}
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
  };
  const ids = [
    "analysis-view-tablist", "view-tab-map", "view-tab-analysis", "analysis-tab-status",
    "map-explorer-panel", "analysis-panel", "analysis-baseline", "analysis-baseline-note",
    "analysis-computation-status",
    "analysis-state-region", "analysis-loading", "analysis-loading-message", "analysis-empty",
    "analysis-empty-message", "analysis-error", "analysis-error-message", "analysis-error-retry",
    "analysis-content", "analysis-preview-drawer", "analysis-preview-kind", "analysis-preview-title",
    "analysis-preview-summary", "analysis-preview-cohort", "analysis-preview-missingness",
    "analysis-preview-comparison", "analysis-preview-criteria", "analysis-preview-feedback",
    "analysis-preview-apply-filters", "analysis-preview-apply-area", "analysis-preview-cancel",
    "analysis-preview-cancel-top", "analysis-active-count", "analysis-reference-count",
    "analysis-mapped-count", "analysis-unmapped-count", "analysis-missing-count",
    "analysis-unit-label", "analysis-source-mix", "analysis-date-precision",
    "analysis-location-precision", "analysis-dataset-hash", "analysis-policy-warning",
    "analysis-coverage-chart", "analysis-comparison-chart", "analysis-time-series-chart", "analysis-decade-chart",
    "analysis-month-year-chart", "analysis-rolling-title", "analysis-rolling-chart", "analysis-bursts-chart", "analysis-craft-distribution-chart",
    "analysis-report-type-chart", "analysis-craft-confidence-chart", "analysis-craft-trends-chart", "analysis-craft-residual-chart", "analysis-geography-grid-chart",
    "analysis-geography-time-chart", "analysis-source-composition-chart",
    "analysis-source-time-chart", "analysis-quality-missingness-chart", "analysis-quality-audit-chart", "analysis-crop-context",
    "analysis-crop-context-status", "analysis-crop-time-chart", "analysis-crop-morphology-chart",
    "analysis-crop-type-chart", "analysis-crop-coordinate-chart", "analysis-crop-coverage-chart", "analysis-animal-context", "analysis-animal-context-status",
    "analysis-animal-time-chart", "analysis-animal-species-chart", "analysis-animal-status-chart",
    "analysis-animal-date-precision-chart", "analysis-animal-coverage-chart",
    "analysis-pattern-list", "analysis-pattern-count",
    "analysis-section-nav", "analysis-section-overview", "analysis-section-time", "analysis-section-craft",
    "analysis-section-geography", "analysis-section-spatial", "analysis-section-sources-quality", "analysis-section-context",
    "analysis-spatial-status", "analysis-include-crop-circles", "analysis-include-animal-reports",
    "analysis-view-crop-analysis", "analysis-view-animal-analysis", "analysis-crop-control-status", "analysis-animal-control-status",
    "analysis-export-json", "analysis-export-csv", "analysis-crop-content", "analysis-crop-excluded",
    "analysis-animal-content", "analysis-animal-excluded", "analysis-craft-era-chart", "analysis-craft-geography-chart",
    "analysis-cooccurrence-chart", "analysis-facility-context-chart", "analysis-cross-domain-readiness-chart",
    "analysis-crop-readiness-chart", "analysis-animal-readiness-chart", "analysis-relationship-readiness-chart",
  ];
  ids.forEach((id) => document.register(id, tagById[id] || "div"));
  const mapTab = document.getElementById("view-tab-map");
  mapTab.setAttribute("aria-selected", "true");
  const analysisTab = document.getElementById("view-tab-analysis");
  analysisTab.disabled = true;
  analysisTab.setAttribute("aria-disabled", "true");
  document.getElementById("analysis-baseline").value = "other_dates_balanced";
  document.getElementById("analysis-rolling-title").textContent = "Rolling observed vs. reference";
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
    const link = document.createElement("a");
    link.setAttribute("href", "#analysis-section-" + key);
    sectionNav.appendChild(link);
  });
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
assert.equal(analysis.SERIES_POINT_LIMIT, 48);
assert.equal(analysis.HEATMAP_CELL_LIMIT, 144);
assert.equal(analysis.HEATMAP_AXIS_LIMIT, 12);
const sampleInput = Array.from({ length: 100 }, (_value, index) => index);
assert.deepEqual(analysis.sampleEvenly(sampleInput, 8), [0, 14, 28, 42, 57, 71, 85, 99]);
assert.equal(analysis.sampleEvenly(sampleInput, 48).length, 48);
assert.equal(analysis.sampleEvenly(sampleInput, 48)[0], 0);
assert.equal(analysis.sampleEvenly(sampleInput, 48).at(-1), 99);
assert.deepEqual(sampleInput.slice(0, 3), [0, 1, 2], "sampling must not mutate the source array");
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
const evidenceCsv = analysis.evidencePackageToCsv(analysis.buildEvidencePackage({
  summary: { activeCount: 80, referenceCount: 240 },
  overview: { evidenceSummary: [{ label: "Disk", activeCount: 20, referenceCount: 40, adjustedDifference: 0.04, interval: [0.01, 0.07], qValue: 0.02 }] },
}, {
  baselineMode: "other_dates_balanced",
  estimatorVersion: "2.0.0",
  filterSnapshot: { generation: 17, filters: { source: "all" } },
  artifactHashes: { core: "abc123" },
}));
assert.match(evidenceCsv, /filter_snapshot,package_artifact_hashes/);
assert.match(evidenceCsv, /other_dates_balanced,2\.0\.0/);
assert.match(evidenceCsv, /overview\.evidenceSummary,Disk,reports,20,40/);
assert.match(evidenceCsv, /0\.04,0\.01,0\.07.*0\.02/);
assert.match(evidenceCsv, /abc123/);

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

const document = createShellDocument();
const viewEvents = [];
const baselineEvents = [];
const appliedFilters = [];
const appliedAreas = [];
const contextChanges = [];
const sectionActivations = [];
const spatialRequests = [];
const contextViews = [];
const evidenceExports = [];
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
  onSpatialEvidenceRequested: (event) => spatialRequests.push(event),
  onContextView: (event) => contextViews.push(event),
  onExportEvidence: (event) => evidenceExports.push(event),
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
spatialLink.emit("click");
assert.equal(controller.activeSectionId, "analysis-section-spatial");
assert.equal(sectionNav.children.filter((link) => link.getAttribute("aria-current") === "location").length, 1);
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
  },
  craft: {
    distribution: [{ label: "Disk", count: 80, patch: { craft: ["disk"] } }],
    reportTypes: [{ label: "Close encounter", count: 55, patch: { types: ["close_encounter"] } }],
    confidence: [{ label: "High", observed: 140, reference: 80 }],
    trends: [
      { row: "Disk", column: "1950s", observed: 80, reference: 40 },
      { row: "Disk", column: "1960s", observed: 65, reference: 50 },
      { row: "Triangle", column: "1950s", observed: 20, reference: 15 },
      { row: "Triangle", column: "1960s", observed: 30, reference: 18 },
    ],
    residuals: [{ row: "Disk", column: "Source A", residual: 2.1 }],
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
    byTime: [{ row: "Europe", column: "1950s", count: 70 }],
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
        ],
      }],
      sameSource: [{
        label: "25 km / ±7 days",
        status: "suppressed",
        suppressionReasons: ["Source-specific lane is descriptive"],
        cells: [{ row: "Disk", column: "Disk", observedCount: 60, expectedCount: 55, log2Enrichment: 0.12 }],
      }],
    },
    facility: {
      status: "suppressed",
      suppressionReasons: ["comparison_band_below_25"],
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

controller.setBaselineMode("other_dates_balanced", { notify: false });
controller.renderAnalysisResult(result);
assert.equal(controller.analysisState, "ready");
assert.equal(document.getElementById("analysis-content").hidden, false);
assert.equal(document.getElementById("analysis-active-count").textContent, "400");
assert.ok(document.getElementById("analysis-coverage-chart").children.length >= 2);
assert.match(
  descendants(document.getElementById("analysis-comparison-chart")).map((element) => element.textContent).join(" "),
  /-4% · 95% CI \[-6%, -2%\].*95% interval/
);
assert.ok(descendants(document.getElementById("analysis-comparison-chart")).some((element) => element.classList.contains("is-negative")));
const suppressedForestRows = descendants(document.getElementById("analysis-comparison-chart"))
  .filter((element) => element.classList.contains("is-suppressed"));
assert.equal(suppressedForestRows.length, 1);
assert.notEqual(suppressedForestRows[0].tagName, "BUTTON", "suppressed forest rows cannot open a filter preview");
assert.match(descendants(suppressedForestRows[0]).map((element) => element.textContent).join(" "), /Suppressed.*Common support below 80%/i);
assert.ok(document.getElementById("analysis-time-series-chart").children.some((child) => child.tagName === "SVG"));
assert.match(
  descendants(document.getElementById("analysis-time-series-chart")).map((element) => element.textContent).join(" "),
  /18%.*Active · source-balanced share.*Reference · source-balanced share.*Each source contributes equal total weight.*Adaptive display uses annual year bins.*Raw annual report counts.*121.*61/
);
assert.ok(document.getElementById("analysis-month-year-chart").children.length >= 2);
assert.ok(document.getElementById("analysis-decade-chart").children.length >= 2);
assert.equal(document.getElementById("analysis-rolling-title").textContent, "Rolling observed vs. reference");
assert.match(
  descendants(document.getElementById("analysis-rolling-chart")).map((element) => element.textContent).join(" "),
  /1952.*120.*60.*Descriptive rolling report counts; not a causal or incidence claim/
);
assert.equal(document.getElementById("analysis-bursts-chart").children.length, 0, "structural burst output is removed from the v2 presentation");
assert.ok(document.getElementById("analysis-craft-confidence-chart").children.length >= 2);
assert.ok(document.getElementById("analysis-report-type-chart").children.length >= 2);
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
assert.match(
  descendants(document.getElementById("analysis-cooccurrence-chart")).map((element) => element.textContent).join(" "),
  /Cross-source.*25 km.*Disk × Triangle.*Observed n=42.*Expected n=28.*Log2 observed\/expected enrichment 0.58.*q=0.02/i
);
const cooccurrenceCards = descendants(document.getElementById("analysis-cooccurrence-chart"))
  .filter((element) => element.className.includes("analysis-evidence-item"));
assert.match(descendants(cooccurrenceCards[0]).map((element) => element.textContent).join(" "), /Disk × Triangle/i, "spatial cards are ranked by qualified conservative effect within the primary lane");
const cooccurrenceViewSelect = descendants(document.getElementById("analysis-cooccurrence-chart"))
  .find((element) => element.className.includes("analysis-evidence-view-select"));
assert.ok(cooccurrenceViewSelect, "co-occurrence exposes separate lane/window views");
assert.deepEqual(cooccurrenceViewSelect.children.map((option) => option.textContent), [
  "Cross-source · 25 km / ±7 days · primary",
  "Same-source · 25 km / ±7 days · sensitivity",
]);
cooccurrenceViewSelect.value = "1";
cooccurrenceViewSelect.emit("change");
assert.match(
  descendants(document.getElementById("analysis-cooccurrence-chart")).map((element) => element.textContent).join(" "),
  /Same-source.*Disk × Disk.*Not estimable/i,
  "same-source evidence is reachable without displacing the cross-source primary lane"
);
assert.match(
  descendants(document.getElementById("analysis-facility-context-chart")).map((element) => element.textContent).join(" "),
  /comparison band below 25.*triangle.*Near band n=42.*Comparison band n=28.*CMH odds ratio 1.58.*95% CI \[1.12, 2.21\].*q=0.03.*Not estimable/i
);
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
assert.match(
  descendants(document.getElementById("analysis-cross-domain-readiness-chart")).map((element) => element.textContent).join(" "),
  /Crop circles.*Eligible 10 of 7,745.*Fewer than 25 qualifying records.*not estimable.*Animal reports.*No exact coordinates.*Relationship reconciliation.*Explicit-source.*1,250.*Computed candidate.*554.*Analyst-reviewed.*0.*Quarantined subject.*460/i
);
assert.match(
  descendants(document.getElementById("analysis-craft-trends-chart")).map((element) => element.textContent).join(" "),
  /Disk · active.*Disk · reference.*Triangle · active.*Triangle · reference/
);
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
  2,
  "active and reference are rendered as separate 100% stacked rows"
);
assert.match(
  descendants(document.getElementById("analysis-quality-audit-chart")).map((element) => element.textContent).join(" "),
  /Disk.*50.*not ground truth/
);
assert.match(
  descendants(document.getElementById("analysis-relationship-readiness-chart")).map((element) => element.textContent).join(" "),
  /Relationship reconciliation.*Eligible 0 of 1,804.*Unresolved identifiers remain quarantined.*sha256:relationships-v2.*Explicit-source.*1,250.*Computed candidate.*554.*Analyst-reviewed.*0.*Association eligible.*0/i,
  "relationship reconciliation and quarantine lanes are visible in Context"
);
assert.equal(document.getElementById("analysis-crop-context-status").textContent, "Crop-circle records: 210 active · 7,300 reference · 7,745 total projection rows.");
assert.ok(document.getElementById("analysis-crop-type-chart").children.length >= 2);
assert.match(
  descendants(document.getElementById("analysis-crop-readiness-chart")).map((element) => element.textContent).join(" "),
  /Crop circles.*Eligible 10 of 7,745.*Fewer than 25 qualifying records.*sha256:crop-v2/i,
  "crop rehabilitation readiness is mirrored in the Crop Context group"
);
assert.match(
  descendants(document.getElementById("analysis-crop-context")).map((element) => element.textContent).join(" "),
  /Membership unit: crop-circle records.*stored inclusive date intervals.*Missingness membership unit: records missing.*each record contributes at most once/i
);
assert.ok(document.getElementById("analysis-rolling-chart").children.length >= 2, "rolling comparison remains visible when bursts exist");
assert.equal(document.getElementById("analysis-bursts-chart").children.length, 0, "bursts stay out of the v2 evidence lab");
assert.ok(document.getElementById("analysis-crop-coordinate-chart").children.length >= 2);
assert.equal(document.getElementById("analysis-animal-context").hidden, false);
assert.equal(document.getElementById("analysis-animal-context-status").textContent, "Animal reports: 80 active · 1,040 reference · 1,177 total projection rows.");
assert.ok(document.getElementById("analysis-animal-status-chart").children.length >= 2);
assert.ok(document.getElementById("analysis-animal-date-precision-chart").children.length >= 2);
assert.match(
  descendants(document.getElementById("analysis-animal-readiness-chart")).map((element) => element.textContent).join(" "),
  /Animal reports.*Eligible 0 of 1,177.*No exact coordinates.*sha256:animal-v2/i,
  "animal rehabilitation readiness is mirrored in the Animal Context group"
);
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
  evidenceExports.at(-1).package.evidenceRows.some((row) => row.section.includes("geography.equalAreaMap.facets[0].cells") && row.adjusted_effect === 0.03),
  "nested equal-area cells are included in the downloadable evidence package"
);
document.getElementById("analysis-export-csv").emit("click");
assert.equal(evidenceExports.at(-1).format, "csv");
assert.match(evidenceExports.at(-1).text, /spatialEvidence\.cooccurrence\.crossSource\[0\]\.cells/);

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
const comparisonButtons = descendants(document.getElementById("analysis-comparison-chart"))
  .filter((element) => element.tagName === "BUTTON");
assert.equal(comparisonButtons.length, 1);
comparisonButtons[0].emit("click");
assert.equal(document.getElementById("analysis-preview-drawer").hidden, false);
assert.deepEqual(controller.currentPreview.patch, { craft: ["disk"] });

controller.destroy();
assert.equal(controller.listeners.length, 0);

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
assert.ok(flushedFrames > 20, "core and context charts should be split across separate frame jobs");
assert.equal(progressiveController.renderPending, false);
assert.equal(progressiveController.analysisState, "ready");
assert.equal(progressiveDocument.getElementById("analysis-content").hidden, false);
assert.equal(progressiveDocument.getElementById("analysis-active-count").textContent, "401");
assert.ok(progressiveDocument.getElementById("analysis-crop-time-chart").children.length > 0);
assert.ok(progressiveDocument.getElementById("analysis-animal-time-chart").children.length > 0);

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
  /evenly sampled to at most 48 points per series.*calculations.*unchanged.*raw annual accessible table is evenly sampled to 48 periods/i
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
