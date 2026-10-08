import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Test the current handler's routing separately from native Leaflet boundary
// mathematics, which is exercised by test_map_world_bounds.mjs.
const appSource = readFileSync(new URL("../app.js", import.meta.url), "utf8");

function extractFunctionBody(source, functionName) {
  const signatureIndex = source.indexOf(`function ${functionName}(`);
  assert.notEqual(signatureIndex, -1, `${functionName} must exist`);
  const openBrace = source.indexOf("{", signatureIndex);
  let depth = 0;
  for (let index = openBrace; index < source.length; index += 1) {
    if (source[index] === "{") depth += 1;
    if (source[index] === "}") depth -= 1;
    if (depth === 0) return source.slice(openBrace + 1, index);
  }
  throw new Error(`Could not extract ${functionName}`);
}

const handlerBody = extractFunctionBody(appSource, "handleMapMoveEnd");
assert.match(handlerBody, /refreshMapWorldConstraints\(\)/);
assert.doesNotMatch(handlerBody, /setView\(|panTo\(|normalizeLongitude\(/);

function buildHarness({ recursiveCorrection = false, wrappedRebuilt = false, recentZoom = false } = {}) {
  const counters = { maxDepth: 0, constraints: 0, wrapped: 0, events: 0, projection: 0,
    staticRefresh: 0, staticSchedule: 0, legend: 0 };
  let depth = 0;
  const runtime = { mapVerticalClampInProgress: false, map: {} };
  const handler = new Function("runtime", "refreshMapWorldConstraints", "refreshWrappedWorldRendering",
    "refreshMapEventLayerForViewportChange", "scheduleMapProjectionRefresh", "mapMoveEndFollowsRecentZoom",
    "scheduleStaticTraceViewportRefresh", "refreshStaticTraceLayerForViewportChange", "scheduleMapViewportLegendRefresh",
    `return function handleMapMoveEnd() {${handlerBody}};`)(runtime,
    () => {
      counters.constraints += 1;
      if (!recursiveCorrection) return;
      runtime.mapVerticalClampInProgress = true;
      try { invoke(); } finally { runtime.mapVerticalClampInProgress = false; }
    },
    () => { counters.wrapped += 1; return wrappedRebuilt; },
    () => { counters.events += 1; },
    () => { counters.projection += 1; },
    () => recentZoom,
    () => { counters.staticSchedule += 1; },
    () => { counters.staticRefresh += 1; },
    () => { counters.legend += 1; });
  function invoke() {
    depth += 1;
    counters.maxDepth = Math.max(counters.maxDepth, depth);
    try { handler(); } finally { depth -= 1; }
  }
  return { counters, runtime, invoke };
}

const correction = buildHarness({ recursiveCorrection: true });
correction.invoke();
assert.deepEqual(correction.counters, { maxDepth: 2, constraints: 1, wrapped: 1, events: 1,
  projection: 1, staticRefresh: 1, staticSchedule: 0, legend: 1 });
assert.equal(correction.runtime.mapVerticalClampInProgress, false);

const ordinary = buildHarness();
for (let world = 0; world < 4; world += 1) ordinary.invoke();
assert.equal(ordinary.counters.constraints, 4);
assert.equal(ordinary.counters.wrapped, 4);
assert.equal(ordinary.counters.events, 4);
assert.equal(ordinary.counters.staticRefresh, 4);

const wrapped = buildHarness({ wrappedRebuilt: true, recentZoom: true });
wrapped.invoke();
assert.equal(wrapped.counters.events, 0, "A rebuilt wrapped world already refreshed event geometry");
assert.equal(wrapped.counters.projection, 0);
assert.equal(wrapped.counters.staticSchedule, 1);
assert.equal(wrapped.counters.staticRefresh, 0);
assert.equal(wrapped.counters.legend, 1);

const hidden = buildHarness();
hidden.runtime.map = null;
hidden.invoke();
assert.equal(hidden.counters.constraints, 0, "No map means no viewport work");
assert.equal(hidden.counters.legend, 0);
hidden.runtime.map = {};
hidden.runtime.mapVerticalClampInProgress = true;
hidden.invoke();
assert.equal(hidden.counters.constraints, 0, "Correction events cannot start another correction");
assert.equal(hidden.counters.legend, 0);

console.log("Current-root map moveend constraint delegation, recursion, wrapped-world and trace routing checks passed");
