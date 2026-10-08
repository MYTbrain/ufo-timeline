// Actual app functions plus the vendored Leaflet projection/boundary math.
// No rendered map, network calls, copied dataset or generated bundle is needed.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
const source = fs.readFileSync(new URL("../app.js", import.meta.url), "utf8");
function extract(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, name + " exists");
  const open = source.indexOf("{", start); let depth = 0;
  for (let end = open; end < source.length; end += 1) {
    if (source[end] === "{") depth += 1;
    if (source[end] === "}") depth -= 1;
    if (!depth) return source.slice(start, end + 1);
  }
  throw new Error("Unclosed function " + name);
}
const document = { documentElement: { style: {} }, createElement() { return { style: {}, getContext() { return {}; } }; },
  createElementNS() { return { createSVGRect() { return {}; } }; }, addEventListener() {}, removeEventListener() {} };
const window = { document, navigator: { userAgent: "node", platform: "", maxTouchPoints: 0 },
  screen: { deviceXDPI: 1, logicalXDPI: 1 }, devicePixelRatio: 1, addEventListener() {}, removeEventListener() {}, setTimeout, clearTimeout };
const exports = {};
const leafletContext = { window, document, navigator: window.navigator, console, setTimeout, clearTimeout, exports,
  module: { exports }, self: window };
vm.runInNewContext(fs.readFileSync(new URL("../vendor/leaflet.js", import.meta.url), "utf8"), leafletContext);
const L = exports;
assert.equal(L.version, "1.9.4");
const constants = ["MAP_DEFAULT_MIN_ZOOM", "MAP_ZOOM_SNAP", "MAP_VERTICAL_LIMIT"].map((name) => {
  const match = source.match(new RegExp("\\bconst " + name + "\\s*=\\s*([^;]+);"));
  assert.ok(match); return match[0];
}).join("\n");
const limit = Number(source.match(/MAP_VERTICAL_LIMIT\s*=\s*([^;]+);/)[1]);
assert.ok(Math.abs(limit - L.Projection.SphericalMercator.MAX_LATITUDE) < 1e-10,
  "Vertical bounds follow the projection's real polar limit");
const initialization = extract("initializeMap");
assert.match(initialization, /worldCopyJump:\s*true/);
assert.match(initialization, /maxBounds:\s*\[\[-MAP_VERTICAL_LIMIT,\s*-Infinity\],\s*\[MAP_VERTICAL_LIMIT,\s*Infinity\]\]/);
assert.match(initialization, /maxBoundsViscosity:\s*1/);
assert.match(initialization, /bounceAtZoomLimits:\s*false/);
assert.match(initialization, /refreshMapWorldConstraints\(\)/);
assert.match(initialization, /on\("resize",\s*function\s*\(\)\s*\{\s*refreshMapWorldConstraints\(\)/);
const bounds = L.latLngBounds([[-limit, -Infinity], [limit, Infinity]]);
assert.equal(bounds.getWest(), -Infinity); assert.equal(bounds.getEast(), Infinity);

function fixture({ height = 341, width = 1366, lat = 0, lng = 0, zoom = 1 } = {}) {
  const counters = { minimumChanges: [], pans: [], maxDepth: 0, wrapped: 0, projection: 0, viewportEvents: 0,
    staticRefresh: 0, staticSchedule: 0, legend: 0 };
  let center = L.latLng(lat, lng), depth = 0;
  const map = { options: { minZoom: 1, maxZoom: 18, maxBounds: bounds }, _zoom: zoom, _loaded: Number.isFinite(zoom),
    getSize() { return L.point(width, height); }, getCenter() { return center; }, getZoom() { return this._zoom; },
    getMinZoom() { return this.options.minZoom; }, getMaxZoom() { return this.options.maxZoom; },
    getPixelWorldBounds(z) { return L.CRS.EPSG3857.getProjectedBounds(z); },
    project(value, z) { return L.CRS.EPSG3857.latLngToPoint(L.latLng(value), z); },
    unproject(value, z) { return L.CRS.EPSG3857.pointToLatLng(value, z); },
    getPixelBounds() { const point = this.project(center, this._zoom), half = this.getSize().divideBy(2);
      return L.bounds(point.subtract(half), point.add(half)); },
    fire() { return this; }, setZoom(value) { this._zoom = value; invoke(); return this; },
    setMinZoom(value) { counters.minimumChanges.push(value); return L.Map.prototype.setMinZoom.call(this, value); },
    panTo(value, options) { center = L.latLng(value); counters.pans.push({ lat: center.lat, lng: center.lng, options }); invoke(); return this; },
    panInsideBounds: L.Map.prototype.panInsideBounds, _limitCenter: L.Map.prototype._limitCenter,
    _getBoundsOffset: L.Map.prototype._getBoundsOffset, _rebound: L.Map.prototype._rebound,
    _limitOffset: L.Map.prototype._limitOffset };
  const context = { runtime: { map, mapVerticalClampInProgress: false }, Number, Math, console,
    refreshWrappedWorldRendering() { counters.wrapped += 1; return false; },
    refreshMapEventLayerForViewportChange() { counters.viewportEvents += 1; },
    scheduleMapProjectionRefresh() { counters.projection += 1; }, recentZoom: false,
    mapMoveEndFollowsRecentZoom() { return context.recentZoom; },
    scheduleStaticTraceViewportRefresh() { counters.staticSchedule += 1; },
    refreshStaticTraceLayerForViewportChange() { counters.staticRefresh += 1; },
    scheduleMapViewportLegendRefresh() { counters.legend += 1; } };
  vm.createContext(context);
  vm.runInContext(constants + "\n" + extract("refreshMapWorldConstraints") + "\n" + extract("handleMapMoveEnd"), context);
  function invoke() { depth += 1; counters.maxDepth = Math.max(depth, counters.maxDepth);
    try { context.handleMapMoveEnd(); } finally { depth -= 1; } }
  function gaps() { const view = map.getPixelBounds(), world = map.getPixelWorldBounds(map.getZoom());
    return { north: world.min.y - view.min.y, south: view.max.y - world.max.y }; }
  return { context, map, counters, invoke, gaps, setHeight(value) { height = value; },
    setCenter(latitude, longitude) { center = L.latLng(latitude, longitude); } };
}
function assertFits(f, message) {
  const gaps = f.gaps();
  assert.ok(gaps.north <= 1.01 && gaps.south <= 1.01, message + ": the whole viewport fits vertically");
  for (const value of [f.map.getCenter().lat, f.map.getCenter().lng, gaps.north, gaps.south]) assert.ok(Number.isFinite(value));
  assert.equal(f.context.runtime.mapVerticalClampInProgress, false);
}
for (const height of [280, 341, 512, 513, 724, 725, 768, 1024, 1025, 2400]) {
  const f = fixture({ height, lat: 80, lng: 540.25 }); f.invoke();
  const minimum = f.map.getMinZoom(), worldHeight = f.map.getPixelWorldBounds(minimum).getSize().y;
  assert.ok(worldHeight + 1e-6 >= height, "Minimum zoom covers height " + height);
  if (minimum > 1) assert.ok(f.map.getPixelWorldBounds(minimum - 0.25).getSize().y < height,
    "The previous zoom step cannot fit height " + height);
  assert.ok(Math.abs(f.map.getCenter().lng - 540.25) < 1e-9, "North correction preserves the unwrapped longitude");
  assertFits(f, "North constraint, height " + height);
  assert.ok(f.counters.maxDepth <= 2, "Native zoom/pan completion does not recurse indefinitely");
  assert.equal(f.counters.wrapped, 1); assert.equal(f.counters.projection, 1);
  assert.equal(f.counters.staticRefresh, 1); assert.equal(f.counters.legend, 1);
  const changes = f.counters.minimumChanges.length; f.invoke();
  assert.equal(f.counters.minimumChanges.length, changes, "An unchanged minimum does not generate zoom events");
}
for (const longitude of [179.75, 180.25, 540.25, -540.25, 10000]) {
  const f = fixture({ lat: -80, lng: longitude, height: 768 }); f.invoke();
  assertFits(f, "South constraint");
  assert.ok(Math.abs(f.map.getCenter().lng - longitude) < 1e-8, "South correction preserves wrapped-world longitude");
  const offset = f.map._limitOffset(L.point(10000, -10000), bounds);
  assert.equal(offset.x, 10000, "Leaflet leaves horizontal dragging unconstrained");
  assert.ok(Number.isFinite(offset.y), "Infinite longitude bounds produce no NaN in native offset math");
}
const resized = fixture({ height: 341, lat: 0, zoom: 1 }); resized.invoke();
resized.setHeight(1000); resized.context.refreshMapWorldConstraints();
assertFits(resized, "Expanded map"); assert.equal(resized.map.getMinZoom(), 2);
const retainedZoom = resized.map.getZoom(); resized.setHeight(280); resized.context.refreshMapWorldConstraints();
assert.equal(resized.map.getMinZoom(), 1); assert.equal(resized.map.getZoom(), retainedZoom,
  "Shrinking the map enables wider zoom without changing the user's current zoom");
const beforeHidden = resized.counters.minimumChanges.length; resized.setHeight(0);
resized.context.refreshMapWorldConstraints(); assert.equal(resized.counters.minimumChanges.length, beforeHidden);
assert.equal(resized.context.runtime.mapVerticalClampInProgress, false, "Hidden maps cannot alter world constraints");
const startup = fixture({ height: 2400 }); startup.map._zoom = undefined; startup.map._loaded = false;
startup.context.refreshMapWorldConstraints();
assert.equal(startup.map.getMinZoom(), 3.25); assert.equal(startup.counters.pans.length, 0,
  "Constraints can be installed before the initial view without panning an uninitialized map");
assert.equal(startup.map.getZoom(), undefined);
for (const [lat, lng] of [[43.77, 11.25], [47.37, -122.45], [-37.5, 149.8]]) {
  const f = fixture({ lat, lng, zoom: 5 }); f.invoke();
  assert.equal(f.counters.pans.length, 0, "Ordinary case/fitted report views retain their center");
  assert.equal(f.map.getZoom(), 5); assertFits(f, "Ordinary case view");
}
const recent = fixture({ lat: 0, zoom: 4 }); recent.context.recentZoom = true; recent.invoke();
assert.equal(recent.counters.staticSchedule, 1); assert.equal(recent.counters.staticRefresh, 0,
  "Recent-zoom trace refresh scheduling remains intact");
const failed = fixture(); failed.map.panInsideBounds = () => { throw new Error("fixture transport failure"); };
assert.throws(() => failed.context.refreshMapWorldConstraints(), /fixture transport failure/);
assert.equal(failed.context.runtime.mapVerticalClampInProgress, false, "A failed correction cannot leave future moves locked");
console.log("Actual app and Leaflet latitude-only bounds, minimum zoom, resize, dateline, startup, recursion and trace refresh checks passed");
