import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { AnalysisViewController, fieldCoverageItems, eligibilityEndpointStages, readinessMatrix } = require("../analysis_view.js");

class Element {
  constructor(tagName = "div") {
    this.tagName = tagName;
    this.children = [];
    this.attributes = new Map();
    this.style = { setProperty() {} };
    this.open = false;
  }
  appendChild(element) { this.children.push(element); return element; }
  replaceChildren(...children) { this.children = children; }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  addEventListener() {}
}

function fixture() {
  const elements = new Map();
  const frames = [];
  const controller = Object.create(AnalysisViewController.prototype);
  Object.assign(controller, {
    document: {
      getElementById: (id) => elements.get(id) ?? null,
      createElement: (tagName) => new Element(tagName),
    },
    activeView: "analysis",
    activeSectionId: "analysis-section-overview",
    resultRenderVersion: 1,
    latestResult: {},
    renderPlans: new Map(),
    renderedPlanVersions: new Map(),
    deferredDisclosureJobs: new Map(),
    activeRenderPlanKeys: [],
    activeRenderTargetIds: [],
    renderPending: false,
    requestRenderFrame: (job) => { frames.push(job); return frames.length; },
    _runRenderJobs: (jobs) => { jobs.forEach((job) => job()); return true; },
    _applyAnalysisState: (state, message) => { throw new Error(`${state}: ${message}`); },
  });
  const add = (id, tagName) => { const element = new Element(tagName); elements.set(id, element); return element; };
  const flush = () => { while (frames.length) frames.shift()(); };
  return { controller, elements, frames, add, flush };
}

const coverage = fieldCoverageItems([
  { label: "Known origin", count: 0, total: 10 },
  { label: "Narrative", count: 4, total: 10 },
], { activeCount: 999 });
assert.deepEqual(coverage, [
  { label: "Known origin", present: 0, missing: 10, total: 10, share: 0 },
  { label: "Narrative", present: 4, missing: 6, total: 10, share: 0.4 },
]);
assert.deepEqual(fieldCoverageItems([{ label: "Missing date ordinal", count: 3 }], { activeCount: 10 }, { countsAreMissing: true }), [
  { label: "Known report date", present: 7, missing: 3, total: 10, share: 0.7 },
]);
assert.equal(fieldCoverageItems([{ label: "Narrative", count: 0, total: 0 }], { activeCount: 0 })[0].share, null);

const coverageFixture = fixture();
const coverageChart = coverageFixture.add("coverage");
const coverageTables = [];
coverageFixture.controller._appendDataTable = (_container, _caption, headings, rows) => coverageTables.push({ headings, rows });
coverageFixture.controller._renderFieldCoverage("coverage", [
  { label: "Known origin", count: 0, total: 10 },
  { label: "Narrative", count: 4, total: 10 },
], { activeCount: 10 });
const bars = coverageChart.children.find((node) => node.tagName === "ul");
assert.equal(bars.children.length, 2, "Zero-count coverage fields remain visible");
assert.match(bars.children[0].getAttribute("aria-label"), /0 present, 10 missing, 10 total/);
assert.equal(bars.children[0].children[1].children[0].style.width, "0.00%");
assert.deepEqual(coverageTables[0].headings, ["Field", "Present", "Missing", "Total", "Coverage"]);
assert.equal(coverageTables[0].rows.length, 2);
assert.doesNotMatch(JSON.stringify(coverageChart), /Inferentially qualified|above expectation|below expectation/);

const funnelStages = [
  { label: "All catalog reports", count: 702893, excludedN: 0 },
  { label: "Mapped reports", count: 582877, excludedN: 120016 },
  { label: "Recognized craft shapes", count: 39047, excludedN: 1349 },
  { label: "After coordinate-pile exclusions", count: 33800, excludedN: 5247 },
];
const endpoints = eligibilityEndpointStages(funnelStages);
assert.equal(endpoints[1].inputN, 702893);
assert.equal(endpoints[1].passedN, 33800);
assert.equal(endpoints[1].excludedN, 669093);
assert.equal(funnelStages[3].excludedN, 5247, "Original stage-specific evidence remains unchanged");
const funnelFixture = fixture();
const funnelChart = funnelFixture.add("funnel");
const funnelTables = [];
funnelFixture.controller._appendDataTable = (_container, caption, headings, rows) => funnelTables.push({ caption, headings, rows });
funnelFixture.controller._renderEligibilityFunnel("funnel", funnelStages, { activeCount: 100 }, {
  endpointsOnly: true,
  releaseScope: true,
  activeSupport: { activeQueryReports: 100, activeQualifiedEndpoints: 12 },
});
assert.match(funnelChart.children[0].textContent, /Release-wide/);
assert.match(funnelChart.children[1].textContent, /100 reports; 12 qualified spatial endpoints/);
assert.equal(funnelTables[0].rows[1][3], "669,093");
assert.equal(funnelTables[1].rows.length, 4, "All release funnel stages remain inspectable");
assert.equal(funnelTables[1].rows[3][3], "5,247");

const gate = (gateId, passedN = 0, status = "blocked") => ({ gateId, inputN: 25, passedN, status });
const matrix = readinessMatrix([
  { key: "crop_strict", label: "Crop circles — strict", status: "blocked", gates: [
    gate("crop_exact_site_formation_date", 1), gate("crop_strict_balanced_cohort"), gate("crop_strict_context_clusters"),
  ] },
  { key: "animal_strict", label: "Animal reports — strict", status: "blocked", gates: [
    gate("animal_exact_site_reviewed"), gate("animal_strict_balanced_cohort"), gate("animal_strict_context_clusters"),
  ] },
  { key: "cropBounded", label: "Crop circles — bounded sensitivity", status: "ready_sensitivity", gates: [gate("crop_bounded_marker_lane", 20, "ready_sensitivity")] },
]);
assert.equal(matrix.rows.length, 3);
for (const [index, prefix] of [[0, "crop"], [1, "animal"]]) {
  const sample = matrix.rows[index].cells.find((cell) => cell.key === "sample");
  assert.equal(sample.status, "blocked");
  assert.deepEqual(sample.gateIds, [`${prefix}_strict_balanced_cohort`, `${prefix}_strict_context_clusters`]);
  assert.equal(sample.representativeGateId, `${prefix}_strict_balanced_cohort`);
}
assert.equal(matrix.rows[2].cells.find((cell) => cell.key === "location").status, "ready_sensitivity");

const lifecycle = fixture();
const owner = "analysis-section-spatial";
const matrixDisclosure = lifecycle.add("matrix", "details");
const contextDisclosure = lifecycle.add("context", "details");
matrixDisclosure.open = contextDisclosure.open = true;
for (const id of ["matrix-chart", "context-chart", "category-chart"]) lifecycle.add(id);
lifecycle.controller.renderPlans.set(owner, { jobs: [], targets: ["matrix-chart", "context-chart", "category-chart"] });
let count = 0;
const chartJob = (id) => () => { lifecycle.elements.get(id).replaceChildren(new Element("svg")); count += 1; };
const register = () => {
  lifecycle.controller._setDeferredDisclosureJobs("matrix", [chartJob("matrix-chart")], { sectionId: owner, targets: ["matrix-chart"] });
  lifecycle.controller._setDeferredDisclosureJobs("context", [chartJob("context-chart"), chartJob("category-chart")], { sectionId: owner, targets: ["context-chart", "category-chart"] });
};
register();
assert.equal(lifecycle.frames.length, 0, "Registering open inactive disclosures must not queue work");
assert.equal(lifecycle.controller._renderDeferredDisclosure("matrix"), false);
lifecycle.controller.activeSectionId = owner;
lifecycle.controller._renderActiveSectionIfNeeded();
const pending = lifecycle.controller.deferredDisclosureJobs.get("context");
assert.equal(pending.pending, true);
assert.equal(pending.rendered, false, "Completion is recorded only after all jobs finish");
assert.equal(lifecycle.controller._renderDeferredDisclosure("context"), false, "Pending work is not duplicated");
lifecycle.flush();
assert.equal(count, 3);
assert.equal(pending.rendered, true);

// Reproduce the audit failure: a new result arrives while another topic is active.
lifecycle.controller.activeSectionId = "analysis-section-craft";
lifecycle.controller.resultRenderVersion = 2;
lifecycle.controller.renderedPlanVersions.clear();
register();
lifecycle.controller._enforceDeferredRenderIsolation(2);
assert.equal(lifecycle.frames.length, 0);
assert.equal(lifecycle.controller.deferredDisclosureJobs.get("context").rendered, false);
for (const id of ["matrix-chart", "context-chart", "category-chart"]) assert.equal(lifecycle.elements.get(id).children.length, 0);
lifecycle.controller.activeSectionId = owner;
lifecycle.controller._renderActiveSectionIfNeeded();
lifecycle.flush();
for (const id of ["matrix-chart", "context-chart", "category-chart"]) assert.equal(lifecycle.elements.get(id).children.length, 1);

// Clearing a completed chart invalidates its owning disclosure and restores it on activation.
lifecycle.controller._clearRenderTargets(["context-chart"]);
assert.equal(lifecycle.controller.deferredDisclosureJobs.get("context").rendered, false);
lifecycle.controller._renderActiveSectionIfNeeded();
lifecycle.frames.shift()(); // first of the two context jobs
lifecycle.controller.activeSectionId = "analysis-section-craft";
lifecycle.flush();
assert.equal(lifecycle.controller.deferredDisclosureJobs.get("context").pending, false);
assert.equal(lifecycle.controller.deferredDisclosureJobs.get("context").rendered, false);
lifecycle.controller.activeSectionId = owner;
lifecycle.controller._renderActiveSectionIfNeeded();
lifecycle.flush();
assert.equal(lifecycle.controller.deferredDisclosureJobs.get("context").rendered, true);

// Superseded queued frames may neither render stale evidence nor clear a newer busy state.
lifecycle.controller._clearRenderTargets(["context-chart"]);
lifecycle.controller._renderDeferredDisclosure("context");
lifecycle.controller.resultRenderVersion = 3;
lifecycle.controller.renderedPlanVersions.set(owner, 3);
register();
lifecycle.controller._renderDeferredDisclosure("context");
lifecycle.frames.shift()(); // stale version-2 job
assert.equal(contextDisclosure.getAttribute("aria-busy"), "true");
lifecycle.flush();
assert.equal(contextDisclosure.getAttribute("aria-busy"), "false");
assert.equal(lifecycle.controller.deferredDisclosureJobs.get("context").rendered, true);

// Use the actual constructor and renderer: a callback omitted from the
// constructor whitelist leaves this lazy overview loading indefinitely.
class ControllerElement extends Element {
  constructor(tagName, document) {
    super(tagName);
    this.ownerDocument = document;
    this.events = new Map();
    this.classList = { toggle() {} };
    this.ownText = "";
  }
  set textContent(value) { this.ownText = String(value); this.children = []; }
  get textContent() { return this.ownText + this.children.map((child) => child.textContent || "").join(""); }
  replaceChildren(...children) { this.children = children; this.ownText = ""; }
  removeAttribute(key) { this.attributes.delete(key); }
  addEventListener(name, callback) {
    if (!this.events.has(name)) this.events.set(name, []);
    this.events.get(name).push(callback);
  }
  click() { for (const callback of this.events.get("click") || []) callback({ target: this, preventDefault() {} }); }
  focus() { this.ownerDocument.activeElement = this; }
}
const requiredIds = Object.fromEntries([
  "tablist", "mapTab", "analysisTab", "tabStatus", "mapPanel", "analysisPanel",
  "baseline", "baselineNote", "stateRegion", "loading", "empty", "error", "content",
  "previewDrawer", "previewTitle", "previewCriteria", "previewApplyFilters",
  "previewApplyArea", "previewCancel", "previewCancelTop",
].map((key) => [key, "fixture-" + key]));
const controllerElements = new Map();
const walkController = (node) => [node, ...node.children.flatMap(walkController)];
const controllerDocument = {
  createElement(tagName) { return new ControllerElement(tagName, this); },
  getElementById(id) {
    return controllerElements.get(id) || Array.from(controllerElements.values()).flatMap(walkController)
      .find((node) => node.id === id) || null;
  },
};
for (const id of Object.values(requiredIds).concat("analysis-comparisons-chart")) {
  controllerElements.set(id, controllerDocument.createElement("div"));
}
const heatmapRequests = [];
const controllerBoundary = new AnalysisViewController({
  document: controllerDocument,
  ids: requiredIds,
  onPlanetaryHeatmapRequest(settings) { heatmapRequests.push(settings); },
});
const priorComparisonsView = globalThis.UfoAnalysisComparisonsView;
globalThis.UfoAnalysisComparisonsView = require("../analysis_comparisons_view.js");
try {
  controllerBoundary.setActiveView("analysis", { silent: true });
  controllerBoundary.activeSectionId = "analysis-section-comparisons";
  controllerBoundary.latestResult = {};
  const evidence = { status: "ready", planetary: require("../analysis_planetary.js").computePlanetaryContext({
    ordinalEpoch: "unix_day", rows: [], zodiacSystem: "sidereal", ayanamsaId: "lahiri", aspectOrbDegrees: 3,
  }) };
  assert.equal(controllerBoundary.renderAnalysisComparisonEvidence(evidence), true);
  assert.equal(heatmapRequests.length, 0, "The controller must preserve lazy loading until Planets is opened");
  controllerDocument.getElementById("analysis-comparison-question-planetary").click();
  assert.match(controllerElements.get("analysis-comparisons-chart").textContent, /Loading planetary heatmaps/);
  assert.deepEqual(heatmapRequests, [{ zodiacSystem: "sidereal", ayanamsaId: "lahiri", aspectOrbDegrees: 3 }],
    "The configured callback must survive the actual controller constructor and reach the lazy overview renderer");
  controllerBoundary.renderAnalysisComparisonEvidence(evidence);
  assert.equal(heatmapRequests.length, 1, "Controller rerenders must not duplicate an in-flight lazy request");
} finally {
  controllerBoundary.destroy();
  globalThis.UfoAnalysisComparisonsView = priorComparisonsView;
}

console.log("Analysis view repairs: coverage, funnel, strict gates, disclosure lifecycle and lazy heatmap callback assertions passed");
