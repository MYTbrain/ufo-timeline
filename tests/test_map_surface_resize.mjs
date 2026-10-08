// Exercise the actual resize functions. Real CSS geometry and viewport fit
// remain browser checks; this fixture models the surface's explicit height.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
const source = fs.readFileSync(new URL("../app.js", import.meta.url), "utf8");
function extract(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, name + " is present");
  const open = source.indexOf("{", start); let depth = 0;
  for (let end = open; end < source.length; end += 1) {
    if (source[end] === "{") depth += 1;
    if (source[end] === "}") depth -= 1;
    if (!depth) return source.slice(start, end + 1);
  }
  throw new Error("Unclosed resize function " + name);
}
const names = ["mapSurfaceResizeAvailable", "readMapSurfaceHeightPreference", "persistMapSurfaceHeightPreference",
  "currentMapSurfaceHeight", "mapSurfaceHeightBounds", "updateMapSurfaceResizeHandleState", "applyMapSurfaceHeight",
  "refreshMapSurfaceResizeBounds", "requestMapSurfaceHeight", "startMapSurfaceResize",
  "handleMapSurfaceResizePointerMove", "finishMapSurfaceResize", "handleMapSurfaceResizeKeydown", "resetMapSurfaceHeight"];
for (const name of names) extract(name);
const functions = source.slice(source.indexOf("function mapSurfaceResizeAvailable("), source.indexOf("function mountTimelineDock("));
const constants = Array.from(source.matchAll(/\bconst (MAP_SURFACE_[A-Z_]+|MAP_CONTROL_CLUSTER_MOBILE_BREAKPOINT)\s*=\s*([^;]+);/g))
  .map((match) => match[0]).join("\n");
const storageKey = source.match(/MAP_SURFACE_HEIGHT_STORAGE_KEY\s*=\s*"([^"]+)"/)[1];
assert.equal(storageKey, "ufoTimeline.mapSurfaceHeight.v2", "Legacy oversized height preferences do not control the new fit");
function fixture(width = 1366, naturalHeight = 360) {
  const frames = new Map(), stored = new Map(), writes = [];
  let nextFrame = 1;
  const effects = { invalidations: 0, projectionRefreshes: 0, layoutRefreshes: 0, captured: [], released: [] };
  function classes() { const values = new Set(); return { add: key => values.add(key), remove: key => values.delete(key),
    contains: key => values.has(key), toggle(key, enabled) { if (enabled) values.add(key); else values.delete(key); } }; }
  function style() { return { minHeight: "", height: "", maxHeight: "", gridTemplateRows: "",
    setProperty(key, value) { this[key] = value; }, removeProperty(key) { delete this[key]; } }; }
  const surface = { style: style(), naturalHeight, top: 120, afterMap: 240, hidden: false, getBoundingClientRect() {
    const height = this.hidden ? 0 : Number.parseFloat(this.style.height) || Math.max(this.naturalHeight, Number.parseFloat(this.style.minHeight) || 0);
    return { top: this.top, bottom: this.top + height, height, width: this.hidden ? 0 : 600, left: 0, right: 600 };
  }, getClientRects() { return this.hidden ? [] : [this.getBoundingClientRect()]; } };
  const rail = { hidden: false, attributes: new Map(), classList: classes(), style: style(),
    setAttribute(key, value) { this.attributes.set(key, value); },
    setPointerCapture(id) { effects.captured.push(id); }, releasePointerCapture(id) { effects.released.push(id); },
    focus() { context.document.activeElement = this; } };
  const context = { console, Number, Math, Set, runtime: { mapSurfaceUserHeight: null, mapSurfaceMinimumHeight: null, mapSurfaceDefaultHeight: null,
    mapSurfaceMaximumHeight: 2400, mapSurfaceResize: null, mapSurfaceResizeFrameId: null, mapSurfaceResizePendingHeight: null },
    els: { mapSurface: surface, mapHeightResizeRail: rail, mapHeightResizeLabel: { textContent: "" }, mapPanel: { style: style(), hidden: false },
      timelineCanvasWrap: { getBoundingClientRect() { return { bottom: surface.getBoundingClientRect().bottom + surface.afterMap, height: 180 }; } } },
    window: { innerWidth: width, innerHeight: width === 1280 ? 720 : 768, scrollY: 0,
      getComputedStyle: node => ({ display: node.hidden ? "none" : "grid" }),
      requestAnimationFrame(callback) { const id = nextFrame++; frames.set(id, callback); return id; },
      cancelAnimationFrame: id => frames.delete(id), setTimeout(callback) { callback(); return 1; } },
    document: { activeElement: null, documentElement: { classList: classes() } },
    clamp: (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value)),
    formatNumber: value => String(value), landscape: false,
    isMobileLandscapeLayout() { return context.landscape; },
    safeStorageGet: key => stored.get(key), safeStorageSet(key, value) { stored.set(key, value); writes.push({ key, value }); },
    applyMapControlClusterState() {}, scheduleMapInvalidate() { effects.invalidations += 1; },
    scheduleMapProjectionRefresh() { effects.projectionRefreshes += 1; }, scheduleMapDescriptionPosition() {},
    refreshMapLayoutAfterPaneChange() { effects.layoutRefreshes += 1; } };
  vm.createContext(context); vm.runInContext(constants + "\n" + functions, context);
  function flushFrames() { for (const [id, callback] of Array.from(frames)) { frames.delete(id); callback(); } }
  function event(extra = {}) { return { pointerId: 7, clientY: 500, pointerType: "mouse", button: 0,
    prevented: false, stopped: false, preventDefault() { this.prevented = true; }, stopPropagation() { this.stopped = true; }, ...extra }; }
  context.refreshMapSurfaceResizeBounds();
  return { context, surface, rail, frames, stored, writes, effects, flushFrames, event,
    height: () => context.currentMapSurfaceHeight() };
}
for (const [width, height] of [[1366, 360], [1280, 320]]) {
  const f = fixture(width, height), c = f.context;
  assert.equal(c.mapSurfaceResizeAvailable(), true);
  assert.equal(f.rail.hidden, false);
  const before = f.height();
  assert.equal(c.mapSurfaceHeightBounds().minHeight, 280, "The hard floor is independent of the fitted default");
  assert.equal(before, c.runtime.mapSurfaceDefaultHeight);
  assert.equal(f.surface.getBoundingClientRect().bottom + f.surface.afterMap + 12, c.window.innerHeight,
    "The fitted default reserves the chronology chart in the initial viewport");
  c.startMapSurfaceResize(f.event({ button: 2 })); assert.equal(c.runtime.mapSurfaceResize, null);
  const down = f.event(); c.startMapSurfaceResize(down);
  assert.equal(down.prevented, true); assert.equal(down.stopped, true);
  assert.equal(c.document.documentElement.classList.contains("is-map-height-resizing"), true);
  assert.equal(f.effects.captured.at(-1), 7);
  assert.equal(c.handleMapSurfaceResizePointerMove(f.event({ pointerId: 9, clientY: 700 })), false);
  c.handleMapSurfaceResizePointerMove(f.event({ clientY: 560 }));
  c.handleMapSurfaceResizePointerMove(f.event({ clientY: 620 }));
  assert.equal(f.frames.size, 1, "pointer moves share one animation frame");
  assert.equal(c.finishMapSurfaceResize(f.event({ pointerId: 9 })), false);
  assert.equal(c.finishMapSurfaceResize(f.event()), true);
  assert.equal(f.frames.size, 0);
  assert.equal(f.height(), before + 120, "release applies the last pending move before its frame runs");
  assert.equal(f.effects.released.at(-1), 7);
  assert.equal(c.document.documentElement.classList.contains("is-map-height-resizing"), false);
  assert.equal(c.document.activeElement, f.rail);
  assert.equal(Number(f.writes.at(-1).value), before + 120);
  assert.equal(Number(f.rail.attributes.get("aria-valuenow")), f.height());
  c.startMapSurfaceResize(f.event());
  c.handleMapSurfaceResizePointerMove(f.event({ clientY: 450 })); f.flushFrames();
  assert.equal(f.height(), before + 70, "upward drag shrinks an expanded map");
  c.finishMapSurfaceResize(f.event());
  const up = f.event({ key: "ArrowUp" }); c.handleMapSurfaceResizeKeydown(up);
  assert.equal(up.prevented, true); assert.equal(f.height(), before + 22);
  c.handleMapSurfaceResizeKeydown(f.event({ key: "End" }));
  assert.equal(f.height(), c.mapSurfaceHeightBounds().maxHeight);
  c.handleMapSurfaceResizeKeydown(f.event({ key: "Home" }));
  assert.equal(f.height(), before, "Home restores the default fitted height");
  assert.equal(f.writes.at(-1).value, "", "the default does not become a manual expansion");
  c.applyMapSurfaceHeight(before + 96, { persist: true });
  const restored = fixture(width, height);
  restored.stored.set(storageKey, f.writes.at(-1).value);
  restored.context.refreshMapSurfaceResizeBounds({ applyStored: true });
  assert.equal(restored.height(), before + 96, "explicit manual expansion survives reload");
  restored.context.resetMapSurfaceHeight(); assert.equal(restored.height(), before);
  c.applyMapSurfaceHeight(before - 48, { persist: true });
  assert.equal(f.height(), before - 48, "A user can shrink below the fitted default");
  assert.equal(c.runtime.mapSurfaceUserHeight, before - 48);
  const smaller = fixture(width, height);
  smaller.stored.set(storageKey, f.writes.at(-1).value);
  smaller.context.refreshMapSurfaceResizeBounds({ applyStored: true });
  assert.equal(smaller.height(), before - 48, "A smaller custom height survives reload");
  c.applyMapSurfaceHeight(-100, { persist: true }); assert.equal(f.height(), 280);
  c.resetMapSurfaceHeight(); assert.equal(f.height(), before, "Reset restores the default rather than the hard floor");
  const oldPreference = fixture(width, height);
  oldPreference.stored.set("ufoTimeline.mapSurfaceHeight.v1", "1400");
  oldPreference.context.refreshMapSurfaceResizeBounds({ applyStored: true });
  assert.equal(oldPreference.height(), before, "Old inflated preferences stay ignored");
  c.window.innerHeight -= 48; c.refreshMapSurfaceResizeBounds();
  assert.equal(f.height(), before - 48, "The automatic default shrinks with a smaller viewport");
  assert.equal(c.runtime.mapSurfaceMinimumHeight, 280, "Measurements cannot ratchet the hard floor upward");
  const fittedBeforeScroll = c.fittedMapSurfaceHeight();
  f.surface.top -= 80; c.window.scrollY = 80;
  assert.equal(c.fittedMapSurfaceHeight(), fittedBeforeScroll, "Page scrolling does not change the document-coordinate fit");
  const visibleDefault = c.runtime.mapSurfaceDefaultHeight;
  f.surface.hidden = true; c.window.innerHeight = 500; c.refreshMapSurfaceResizeBounds();
  assert.equal(c.runtime.mapSurfaceDefaultHeight, visibleDefault, "Hidden Analysis map geometry does not replace the visible fit");
  f.surface.hidden = false; c.refreshMapSurfaceResizeBounds();
  assert.equal(f.height(), c.runtime.mapSurfaceDefaultHeight);
  assert.ok(f.effects.invalidations > 0); assert.ok(f.effects.layoutRefreshes > 0);
}
for (const [width, landscape] of [[390, false], [844, true]]) {
  const f = fixture(); f.context.applyMapSurfaceHeight(720, { persist: true });
  f.context.window.innerWidth = width; f.context.window.innerHeight = landscape ? 390 : 844; f.context.landscape = landscape;
  f.context.refreshMapSurfaceResizeBounds();
  assert.equal(f.rail.hidden, true); assert.equal(Number.parseFloat(f.surface.style.minHeight), 0);
  assert.equal(f.height(), f.context.runtime.mapSurfaceDefaultHeight, "Compact layouts fit instead of using desktop expansion");
  assert.equal(f.context.runtime.mapSurfaceUserHeight, 720, "Compact fitting preserves the explicit desktop preference");
  f.context.startMapSurfaceResize(f.event()); assert.equal(f.context.runtime.mapSurfaceResize, null);
  f.context.window.innerWidth = 1366; f.context.window.innerHeight = 768; f.context.landscape = false;
  f.context.refreshMapSurfaceResizeBounds(); assert.equal(f.height(), 720);
}
console.log("Actual map resize pointer/frame completion, viewport/chart fit, default/floor reset, persistence, hidden-map guard, accessible values and mobile gates passed");
