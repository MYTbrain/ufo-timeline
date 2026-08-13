import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const appSource = readFileSync(new URL("../webapp/static_public/app.js", import.meta.url), "utf8");

function extractFunctionBody(source, functionName) {
  const signature = `function ${functionName}(`;
  const signatureIndex = source.indexOf(signature);
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

function buildHarness(initialCenter) {
  const counters = {
    maxDepth: 0,
    projectionRefreshes: 0,
    eventLayerRefreshes: 0,
    legendRefreshSchedules: 0,
    staticTraceRefreshes: 0,
    staticTraceSchedules: 0,
    viewCorrections: [],
    wrappedRefreshes: 0,
  };
  let activeDepth = 0;
  let center = { ...initialCenter };
  let handler;

  const runtime = {
    mapVerticalClampInProgress: false,
    map: {
      getCenter() {
        return { ...center };
      },
      getZoom() {
        return 1;
      },
      panTo() {
        throw new Error("handleMapMoveEnd must not use Leaflet's sub-pixel pan path");
      },
      setView(target, zoom, options) {
        counters.viewCorrections.push({ target: [...target], zoom, options: { ...options } });
        invokeHandler();
        center = { lat: target[0], lng: target[1] };
      },
    },
  };

  const createHandler = new Function(
    "runtime",
    "MAP_VERTICAL_LIMIT",
    "clamp",
    "refreshWrappedWorldRendering",
    "refreshMapEventLayerForViewportChange",
    "scheduleMapProjectionRefresh",
    "mapMoveEndFollowsRecentZoom",
    "scheduleStaticTraceViewportRefresh",
    "refreshStaticTraceLayerForViewportChange",
    "scheduleMapViewportLegendRefresh",
    `return function handleMapMoveEnd() {${handlerBody}};`
  );

  handler = createHandler(
    runtime,
    82,
    (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value)),
    () => {
      counters.wrappedRefreshes += 1;
      return false;
    },
    () => {
      counters.eventLayerRefreshes += 1;
    },
    () => {
      counters.projectionRefreshes += 1;
    },
    () => false,
    () => {
      counters.staticTraceSchedules += 1;
    },
    () => {
      counters.staticTraceRefreshes += 1;
    },
    () => {
      counters.legendRefreshSchedules += 1;
    }
  );

  function invokeHandler() {
    activeDepth += 1;
    counters.maxDepth = Math.max(counters.maxDepth, activeDepth);
    try {
      handler();
    } finally {
      activeDepth -= 1;
    }
  }

  return {
    counters,
    invokeHandler,
    runtime,
    setCenter(nextCenter) {
      center = { ...nextCenter };
    },
  };
}

const polarHarness = buildHarness({ lat: 89, lng: 540.25 });
polarHarness.invokeHandler();
assert.equal(polarHarness.counters.maxDepth, 2);
assert.deepEqual(polarHarness.counters.viewCorrections, [
  {
    target: [82, 540.25],
    zoom: 1,
    options: { animate: false, reset: true },
  },
]);
assert.equal(polarHarness.runtime.mapVerticalClampInProgress, false);
assert.equal(polarHarness.counters.wrappedRefreshes, 1);
assert.equal(polarHarness.counters.projectionRefreshes, 1);
assert.equal(polarHarness.counters.eventLayerRefreshes, 1);
assert.equal(polarHarness.counters.staticTraceRefreshes, 1);
assert.equal(polarHarness.counters.staticTraceSchedules, 0);
assert.equal(polarHarness.counters.legendRefreshSchedules, 1);

const horizontalHarness = buildHarness({ lat: 20, lng: 179.75 });
for (const lng of [179.75, 180.25, 540.25, -540.25]) {
  horizontalHarness.setCenter({ lat: 20, lng });
  horizontalHarness.invokeHandler();
}
assert.equal(horizontalHarness.counters.viewCorrections.length, 0);
assert.equal(horizontalHarness.counters.wrappedRefreshes, 4);
assert.equal(horizontalHarness.counters.projectionRefreshes, 4);
assert.equal(horizontalHarness.counters.eventLayerRefreshes, 4);
assert.equal(horizontalHarness.counters.staticTraceRefreshes, 4);
assert.equal(horizontalHarness.counters.legendRefreshSchedules, 4);

console.log("map moveend recursion and dateline continuity assertions passed");
