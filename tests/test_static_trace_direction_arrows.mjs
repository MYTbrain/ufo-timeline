import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const directions = require("../trace_direction_summary.js");
const chronology = require("../trace_chronology.js");
const source = readFileSync(new URL("../app.js", import.meta.url), "utf8");
const first = source.indexOf("function createStaticTraceLayer(options)");
const last = source.indexOf("function clearMapDataLayers()", first);
assert.ok(first >= 0 && last > first);
const layerSource = source.slice(first, last);
const point = (x, y) => ({ x, y, subtract(other) { return point(x - other.x, y - other.y); } });
const pendingFrames = [];
let regionActive = false;
const runtime = { discardedRenderResults: 0 };
const state = { showTraceDirectionArrows: true };
const context = vm.createContext({
  L: { point, Layer: { extend(definition) { return class {
    constructor() { Object.assign(this, definition); this.initialize(); }
  }; } } },
  runtime, state, TRACE_DIRECTIONS: directions,
  TRACE_VIEWPORT_LAT_PAD: 1,
  TRACE_PROGRESSIVE_SEGMENT_THRESHOLD: 3,
  TRACE_FACILITY_POSSIBLE_TRACE_DASH_ARRAY: "3 4",
  TRACE_FACILITY_ENDPOINT_ACCENT_RATIO: 0.15,
  BROWSER_PERFORMANCE_PROFILE: { traceFrameBudgetMs: 100, traceBatchSize: 2 },
  performance: { now: () => 0 },
  window: { requestAnimationFrame: callback => { pendingFrames.push(callback); return pendingFrames.length; }, cancelAnimationFrame() {} },
  clamp: (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value)),
  hexToRgba: color => color,
  scaledTraceOpacity: opacity => opacity,
  scaledTraceStrokeWeight: weight => weight,
  scaledTraceGlowBlur: value => value,
  regionSelectionAffectsRendering: () => regionActive,
  wrappedWorldIndices: () => [0, 1],
  wrappedSegmentCopies: segment => segment.testCopies || [{ from: segment.from, to: segment.to }],
});
vm.runInContext(layerSource, context);

function canvasRecorder() {
  const ctx = { strokes: [], path: [], dash: [], saved: [], transform: { x: 0, y: 0, angle: 0 },
    globalAlpha: 1, lineWidth: 1, strokeStyle: "",
    save() { this.saved.push({ transform: { ...this.transform }, globalAlpha: this.globalAlpha,
      lineWidth: this.lineWidth, strokeStyle: this.strokeStyle, dash: [...this.dash] }); },
    restore() { Object.assign(this, this.saved.pop()); },
    beginPath() { this.path = []; },
    moveTo(x, y) { this.path.push(["M", x, y]); },
    lineTo(x, y) { this.path.push(["L", x, y]); },
    translate(x, y) { this.transform.x += x; this.transform.y += y; },
    rotate(angle) { this.transform.angle += angle; },
    setLineDash(dash) { this.dash = [...dash]; },
    clearRect() { this.strokes = []; },
    stroke() { this.strokes.push({ path: this.path.map(item => [...item]), transform: { ...this.transform },
      alpha: this.globalAlpha, width: this.lineWidth, color: this.strokeStyle }); },
  };
  return ctx;
}

function makeLayer(role = "static", projection = { offset: 50, scale: 1 }, width = 800) {
  const layer = context.createStaticTraceLayer();
  layer._ctx = canvasRecorder();
  layer._canvas = { width, height: 200 };
  layer._topLeft = point(0, 0);
  layer._map = {
    latLngToLayerPoint: pair => point(projection.offset + pair[1] * projection.scale, 100 - pair[0]),
    getBounds: () => ({ getSouth: () => -90, getNorth: () => 90 }),
  };
  if (role === "static") runtime.staticTraceLayer = layer;
  if (role === "playback") runtime.playbackTrailCanvasLayer = layer;
  return layer;
}
const bucket = { color: "#ff0000", weight: 2, opacity: 0.8 };
const link = overrides => ({ traceId: "a", from: [0, 0], to: [0, 100], gapDays: 2, bucket, ...overrides });
const glyphs = layer => layer._ctx.strokes.filter(stroke => stroke.transform.x !== 0 || stroke.transform.y !== 0);
function draw(layer, segments) {
  layer._segments = segments;
  layer._redraw();
  while (pendingFrames.length) pendingFrames.shift()();
  return glyphs(layer);
}

const staticLayer = makeLayer();
const sourceLink = link();
const before = JSON.stringify(sourceLink);
let arrows = draw(staticLayer, [sourceLink]);
assert.equal(arrows.length, 2, "known links receive one contrast outline plus one arrow stroke");
assert.equal(arrows[0].transform.angle, 0, "eastward report chronology points toward the later endpoint");
assert.ok(arrows[1].path.some(command => command[0] === "L" && command[1] > 0 && command[2] === 0));
assert.equal(arrows[1].path.filter(command => command[0] === "M").length, 2,
  "a known direction has only the forward arrowhead");
assert.notEqual(arrows[0].color, arrows[1].color, "the glyph has a contrasting halo");
assert.ok(arrows[0].width > arrows[1].width);
assert.equal(JSON.stringify(sourceLink), before, "rendering never edits chronology or source geometry");

for (const unknown of [link({ gapDays: 0 }), link({ gapDays: undefined }),
  link({ sameDayOrderKnown: false }), link({ chronology: { status: "overlapping" } })]) {
  arrows = draw(staticLayer, [unknown]);
  assert.equal(arrows.length, 2);
  assert.equal(arrows[1].color, "#969696", "unresolved ordering uses a neutral glyph");
  assert.equal(arrows[1].path.filter(command => command[0] === "M").length, 3,
    "unknown chronology is double-headed, never a chosen forward ordering");
}
assert.equal(draw(staticLayer, [link({ gapDays: 0, sameDayOrderKnown: true })])[1].path.filter(command => command[0] === "M").length, 2,
  "accepted same-day order retains a single arrowhead");

const date = Date.parse("2000-01-01T00:00:00Z");
const evidence = chronology.createEvidenceIndex({
  schemaId: chronology.SCHEMA_ID, sourceContract: chronology.SOURCE_CONTRACT, releaseId: "canvas-arrows-fixture",
  rowSchema: [...chronology.ROW_SCHEMA],
  rows: [[1, date + 12 * 3600000, date + 12 * 3600000 + 59999, 0, 0],
    [2, date + 10 * 3600000, date + 10 * 3600000 + 59999, 0, 0]],
  codes: { evidence: [{ status: "accepted", kind: "source_clock", confidence: "high", basis: "Preserved occurrence clock and historical timezone" }], zone: ["UTC"] },
});
const reversed = chronology.orientSegment(evidence, link({ fromEventId: 1, toEventId: 2, gapDays: 0 }));
assert.equal(reversed.fromEventId, 2);
assert.equal(Math.abs(draw(staticLayer, [reversed])[0].transform.angle), Math.PI,
  "source-backed reverse chronology also reverses the actual Canvas arrow");

const split = link({ fromCraftColor: "#ff0000", toCraftColor: "#0000ff" });
assert.equal(draw(staticLayer, [split]).length, 2, "split craft colors cannot bypass arrows through an early return");
assert.equal(staticLayer._ctx.strokes.filter(stroke => stroke.transform.x === 0 && stroke.transform.y === 0).length, 2);
const playbackLayer = makeLayer("playback");
assert.equal(draw(playbackLayer, [link()]).length, 2, "playback Canvas uses the same chronology-aware arrows");
const decorativeLayer = makeLayer("claimed");
assert.equal(draw(decorativeLayer, [link()]).length, 0, "claimed-base/debug canvases never acquire report chronology arrows");
for (const count of [0, 1, 200]) {
  assert.equal(draw(staticLayer, [link({ aggregateSegmentCount: count })]).length, 0,
    "aggregate representative geometry never receives an individual direction claim");
}
regionActive = true;
assert.equal(draw(staticLayer, [link()]).length, 0, "area/case interactive badges are not duplicated on the Canvas");
assert.equal(draw(playbackLayer, [link()]).length, 0);
regionActive = false;
state.showTraceDirectionArrows = false;
assert.equal(draw(staticLayer, [link()]).length, 0);
state.showTraceDirectionArrows = true;
assert.equal(draw(staticLayer, [link()]).length, 2, "reenabling redraws arrows rather than retaining occupied cells");
assert.equal(draw(staticLayer, [link({ opacity: 0 })]).length, 0, "fully faded playback lines leave no floating arrow");
assert.equal(draw(staticLayer, [link({ to: [0, 1] })]).length, 0, "unreadably short links do not become oversized glyphs");

const clippedLayer = makeLayer("static", { offset: -1100, scale: 10 }, 400);
arrows = draw(clippedLayer, [link({ to: [0, 150] })]);
assert.equal(arrows.length, 2, "a long line whose original midpoint is offscreen still shows its arrow");
assert.ok(arrows[0].transform.x >= 12 && arrows[0].transform.x <= 388);
assert.equal(arrows[0].transform.angle, 0);

const wrappedLayer = makeLayer("static");
arrows = draw(wrappedLayer, [link({ testCopies: [
  { from: [0, 0], to: [0, 100] }, { from: [0, 360], to: [0, 460] },
] })]);
assert.equal(arrows.length, 4, "each visible wrapped world copy gets the same correct arrow");
assert.equal(arrows[0].transform.angle, arrows[2].transform.angle);
assert.equal(arrows[2].transform.x - arrows[0].transform.x, 360);

arrows = draw(wrappedLayer, Array.from({ length: 40 }, (_, index) => link({ traceId: "dense-" + index })));
assert.ok(arrows.length > 0 && arrows.length <= 6,
  "progressive dense rendering bounds overlapping arrow glyphs instead of stacking every report link");
assert.equal(wrappedLayer._ctx.strokes.filter(stroke => stroke.transform.x === 0 && stroke.transform.y === 0).length, 40,
  "arrow density limits do not remove trace lines or alter population counts");
assert.equal(pendingFrames.length, 0);
console.log("Static/playback direction arrows passed: known/unknown chronology, reversal, split colors, clipping, wrapped copies, scope isolation, toggles and progressive density.");
