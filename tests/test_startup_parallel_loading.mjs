import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const app = fs.readFileSync("app.js", "utf8");
function source(name, next) {
  const start = app.indexOf("  async function " + name + "(");
  const end = app.indexOf("  " + next, start);
  assert.ok(start >= 0 && end > start, "Expected actual application function: " + name);
  return app.slice(start, end);
}
const catalogSource = source("loadCatalog", "function prepareFileProtocolMode(");
const initializeSource = source("initialize", "window.__UFO_TIMELINE_DEBUG__ =");
const terminalStart = app.lastIndexOf("  initialize().catch(");
const terminalSource = app.slice(terminalStart, app.lastIndexOf("})();"));
assert.ok(terminalStart > 0 && terminalSource.includes("setStartupFailure(error)"));
const supportNames = ["loadDetailQualityOverlayRuntime", "loadAnalysisRepairDetailOverlayRuntime", "loadTraceChronologyEvidence",
  "loadEncounterEvidence", "loadLocationLabelOverlayRuntime"];
const flush = async () => { for (let n = 0; n < 12; n += 1) await Promise.resolve(); };
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function fixture() {
  const calls = [], support = supportNames.map(deferred), boundary = new Error("Readiness boundary reached");
  const startup = { phase: "Loading", initialViewReady: false }, runtime = {}, state = {};
  const context = vm.createContext({ console: { error() {} }, Promise, Date, Object, WeakMap, Error,
    startup, runtime, state, STARTUP_PROGRESS: { config: 2, preparingMap: 8 },
    fetchJson: async () => ({ encounterEvidence: { enabled: true } }),
    preferredTileProviderId: () => "default", renderStartupDiagnostics() {}, progressiveStartupRequested: () => false,
    measureStartupStep: (_name, fn) => fn(),
    setStartupPhaseAndPaint: async phase => { startup.phase = phase; calls.push(phase); if (phase === "Preparing map") throw boundary; },
    setStartupFailure: error => { startup.phase = "Failed"; calls.push({ failure: error.message }); },
    document: { documentElement: { classList: { remove() {} } } },
    window: { location: { protocol: "https:" }, dispatchEvent: event => calls.push({ event: event.type }) },
  });
  supportNames.forEach((name, position) => {
    context[name] = () => { calls.push(name); return support[position].promise; };
  });
  for (const name of ["resetStartupTimingSession", "applyBrowserPerformanceProfile", "initializeAppearanceState",
    "applyFilterSectionCollapseState", "initializeGuideChips", "mountHeroGuide", "mountMapControlCluster",
    "syncResponsivePrimaryFiltersPlacement", "mountTimelineDock", "applyMapControlClusterState",
    "applyMobileLandscapeResultsColumnWidth", "bindMapControlClusterResizing", "initializeMapSurfaceHeightResize",
    "initializeAnalysisView", "initializeAnalysisDateRangeControls", "ensureCatalogFacetWorker"]) context[name] = () => {};
  // These functions cannot run while any required support loader is pending.
  for (const name of ["initializeMap", "loadStartupProfileRuntime", "ingestCatalogShard", "loadAndIngestCanonicalSummaryShards",
    "initializeFilters", "renderFilteredState", "finalizeInitialStartupVisuals"]) context[name] = () => { calls.push(name); throw new Error("Premature catalog use: " + name); };
  vm.runInContext(catalogSource + initializeSource, context);
  return { context, calls, support, boundary, startup };
}

const success = fixture();
const loading = success.context.loadCatalog();
const checked = loading.catch(error => error);
await flush();
assert.deepEqual(success.calls.filter(value => supportNames.includes(value)), supportNames,
  "All five independent loaders start before any of them resolves");
for (const position of [4, 2, 0, 3]) { success.support[position].resolve(); await flush(); }
assert.equal(success.calls.includes("Preparing map"), false, "One unresolved loader keeps map/profile/catalog hydration behind the barrier");
assert.equal(success.startup.initialViewReady, false);
success.support[1].resolve();
assert.equal(await checked, success.boundary, "Map preparation resumes only after every support loader settles successfully");
assert.equal(success.calls.at(-1), "Preparing map");

// Exercise the real initialize().catch handler, rather than hiding a required
// loader failure behind an early Ready state. Pending peers cannot revive it.
for (let failurePosition = 0; failurePosition < supportNames.length; failurePosition += 1) {
  const failed = fixture();
  const initialized = vm.runInContext(terminalSource, failed.context);
  await flush();
  assert.equal(failed.calls.filter(value => supportNames.includes(value)).length, 5);
  failed.support[failurePosition].reject(new Error("Pinned support payload rejected"));
  await initialized;
  assert.equal(failed.startup.phase, "Failed");
  assert.equal(failed.startup.initialViewReady, false, "Failure leaves the loading/error screen's readiness gate closed");
  assert.equal(failed.calls.includes("Preparing map"), false);
  assert.deepEqual(failed.calls.filter(value => value && value.failure), [{ failure: "Pinned support payload rejected" }]);
  assert.equal(failed.calls.some(value => value && value.event === "ufo:timeline-ready"), false);
  failed.support.forEach((item, position) => { if (position !== failurePosition) item.resolve(); });
  await flush();
  assert.equal(failed.startup.phase, "Failed");
  assert.equal(failed.calls.includes("Preparing map"), false, "Late successful peers do not resume a failed startup");
}
console.log("Startup support loads overlap while all five readiness barriers, profile/catalog safety, and every required-failure path remain intact.");
