import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const app = readFileSync(new URL("../app.js", import.meta.url), "utf8").replace(/\r\n/g, "\n");
const evidence = JSON.parse(readFileSync(new URL("../docs/qa/share-view-20261031/browser.json", import.meta.url), "utf8"));
const saved = evidence.caseRoundTrip.expected;
const json = value => JSON.parse(JSON.stringify(value));
function productionFunction(name) {
  const start = app.search(new RegExp("^  (?:async )?function " + name + "\\(", "m"));
  assert.ok(start >= 0, "Missing production function " + name);
  const next = app.slice(start + 1).search(/\n  (?:async )?function \w+\(/);
  assert.ok(next >= 0);
  return app.slice(start, start + 1 + next);
}
const state = {
  ...json(saved.settings),
  regionSelection: { ...json(saved.region), shapes: [
    { id: "local-rectangle", type: "rectangle", bounds: { west: 170.123456789, east: 190.987654321, south: -10.125, north: 20.625 } },
    { id: "local-case", type: "circle", center: { lat: 55.91227293006361, lng: -3.5156250000000004 }, radiusMeters: 75000.125 },
  ] },
  analysisCountryAreaFilter: saved.region.country,
  timeRangeStartOrdinal: saved.time.start,
  timeRangeEndOrdinal: saved.time.end,
  timeRangeMode: saved.time.mode,
  visibleTimelineExtent: { minOrdinal: 19121, maxOrdinal: 19211, minIso: "2022-05-09", maxIso: "2022-08-07" },
  famousCaseId: saved.case,
  currentTileProviderId: saved.map.basemap,
  encounterAnalysisSelectionIds: new Set(["first-report", "second-report"]),
  activeView: "analysis", selectedEventId: saved.selection,
};
let sequence = 0;
const runtime = {
  map: { getCenter: () => ({ lat: -15.26869530794737, lng: -40.15014469120664 }), getZoom: () => 2.75 },
  famousCaseShapeId: "local-case",
};
const context = vm.createContext({
  state, runtime,
  els: { hideLowPrecisionToggle: { checked: true }, hideNonExactDatesToggle: { checked: false } },
  normalizedMapLegendEventSelection: () => saved.settings.mapLegendEventSelection,
  effectiveMultiSelectState: key => saved.filters.facets[key],
  getCurrentKeyword: () => "exact shared state",
  captureShareViewLayers: () => saved.layers,
  CHRONOLOGICAL_NEIGHBORHOOD_DEFAULT_DEPTH: 0,
  CHRONOLOGICAL_NEIGHBORHOOD_DEFAULT_DIRECTION: "forward",
  TRACE_NEIGHBORHOOD: { normalizeAreaDepth: value => value, normalizeDirection: value => value },
  nextRegionSelectionShapeId: () => "restored-" + ++sequence,
  syncRegionSelectionMapInteraction() {}, refreshRegionSelectionRenderState() {},
});
const constantsStart = app.indexOf("  const SHARE_SETTING_ENUMS =");
const constantsEnd = app.indexOf("  function shareBooleanMap(", constantsStart);
assert.ok(constantsStart >= 0 && constantsEnd > constantsStart);
vm.runInContext(app.slice(constantsStart, constantsEnd), context);
for (const name of ["captureShareView", "defaultRegionSelectionState", "restoreShareRegion"]) {
  vm.runInContext(productionFunction(name), context);
}

const before = JSON.stringify(state);
const snapshot = json(vm.runInContext("captureShareView()", context));
assert.equal(JSON.stringify(state), before, "capturing a link must not mutate the current view");
assert.deepEqual(snapshot.time.visible, { minOrdinal: 19121, maxOrdinal: 19211 });
assert.deepEqual(snapshot.map, { lat: -15.26869530794737, lng: -40.15014469120664, zoom: 2.75, basemap: saved.map.basemap });
assert.deepEqual(snapshot.settings, saved.settings, "all settings, including disabled controls, remain in the snapshot");
assert.deepEqual(snapshot.layers, saved.layers);
assert.equal(snapshot.filters.hideLowPrecision, true);
assert.equal(snapshot.filters.hideNonExactDates, false);
assert.deepEqual(snapshot.filters.encounterSelectionIds, ["first-report", "second-report"]);
assert.equal(snapshot.region.caseShapeIndex, 1);
assert.ok(snapshot.region.shapes.every(shape => !Object.hasOwn(shape, "id")));

context.snapshot = snapshot;
vm.runInContext("restoreShareRegion(snapshot.region)", context);
const restored = json(state.regionSelection.shapes).map(({ id, ...shape }) => shape);
assert.deepEqual(restored, snapshot.region.shapes, "rectangle and circle geometry survive restoration exactly");
assert.equal(runtime.famousCaseShapeId, state.regionSelection.shapes[1].id, "the case association follows its saved index, not a local ID");
assert.equal(runtime.famousCasePreviousSelection.regionSelection.shapes[0].id, state.regionSelection.shapes[0].id);

state.visibleTimelineExtent = null;
state.regionSelection.shapes = [];
runtime.map = null;
runtime.famousCaseShapeId = null;
const empty = json(vm.runInContext("captureShareView()", context));
assert.equal(empty.time.visible, null);
assert.equal(empty.map, null);
assert.deepEqual(empty.region.shapes, []);
assert.equal(empty.region.caseShapeIndex, -1);
console.log("Shared-view capture: derived labels and local IDs omitted; exact geometry, settings, checkboxes and case association preserved.");
