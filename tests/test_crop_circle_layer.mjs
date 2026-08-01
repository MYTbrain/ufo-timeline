import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import vm from "node:vm";


const repoRoot = path.resolve(import.meta.dirname, "..");
const staticRoot = path.join(repoRoot, "webapp", "static_public");
const requests = [];
const createdMarkers = [];

class MockClassList {
  toggle() {}
  add() {}
  remove() {}
}

class MockElement {
  constructor() {
    this.attributes = new Map();
    this.classList = new MockClassList();
    this.dataset = {};
    this.hidden = false;
    this.disabled = false;
    this.textContent = "";
    this.innerHTML = "";
    this.listeners = new Map();
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); }
  addEventListener(name, handler) { this.listeners.set(name, handler); }
  querySelector() { return null; }
}

const elements = new Map([
  ["#overlay-crop-circles", new MockElement()],
  ["#crop-circle-status", new MockElement()],
  ["#crop-circle-detail-panel", new MockElement()],
  ["#crop-circle-detail-body", new MockElement()],
  ["#crop-circle-detail-close", new MockElement()],
]);

const mapLayers = new Set();
const panes = new Map();
const map = {
  createPane(name) { panes.set(name, { style: {} }); },
  getPane(name) { return panes.get(name) || null; },
  hasLayer(layer) { return mapLayers.has(layer); },
  removeLayer(layer) { mapLayers.delete(layer); },
  panInside() {},
};

function layerGroup() {
  const layers = [];
  return {
    addLayer(layer) { layers.push(layer); return this; },
    clearLayers() { layers.length = 0; },
    getLayers() { return layers.slice(); },
    addTo(targetMap) { mapLayers.add(this); this._map = targetMap; return this; },
  };
}

function circleMarker(latlng, options) {
  const handlers = new Map();
  const marker = {
    latlng,
    options,
    on(name, handler) { handlers.set(name, handler); return this; },
    setStyle(style) { this.options = { ...this.options, ...style }; },
    setRadius(radius) { this.options.radius = radius; },
    getLatLng() { return { lat: latlng[0], lng: latlng[1] }; },
    fire(name) { const handler = handlers.get(name); if (handler) return handler({ originalEvent: { stopPropagation() {} } }); },
  };
  createdMarkers.push(marker);
  return marker;
}

const view = {
  map,
  timeRangeStartOrdinal: -500000,
  timeRangeEndOrdinal: 500000,
  hideLowPrecisionCoordinates: false,
  hideNonExactDates: true,
  colorMode: "craft_type",
  filterGeneration: 1,
};

async function localFetch(input) {
  const url = new URL(String(input));
  requests.push(url.pathname);
  const relative = url.pathname
    .replace(/^\/releases\/crop-circles-v155-20260731\//, "data/crop_circles/")
    .replace(/^\/+/, "");
  const filePath = path.join(staticRoot, relative);
  try {
    const bytes = await fs.readFile(filePath);
    return new Response(bytes, { status: 200 });
  } catch (error) {
    return new Response("not found", { status: 404 });
  }
}

const windowObject = {
  L: {
    canvas() { return {}; },
    layerGroup,
    circleMarker,
    DomEvent: { disableClickPropagation() {}, disableScrollPropagation() {} },
  },
  UfoTimelineExtensions: { getContext() { return view; } },
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
};

const context = vm.createContext({
  window: windowObject,
  document: {
    baseURI: "https://example.test/",
    querySelector(selector) { return elements.get(selector) || null; },
  },
  URL,
  fetch: localFetch,
  Response,
  Blob,
  DecompressionStream,
  TextDecoder,
  console,
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
});

const source = await fs.readFile(path.join(staticRoot, "crop_circle_layer.js"), "utf8");
vm.runInContext(source, context, { filename: "crop_circle_layer.js" });

assert.equal(requests.length, 0, "loading the runtime must not request crop data before enable");
assert.ok(windowObject.UfoCropCircleLayer, "runtime API is exposed");

await windowObject.UfoCropCircleLayer.setEnabled(true);
assert.deepEqual(requests.slice(0, 2), [
  "/data/crop_circles/manifest.json",
  "/releases/crop-circles-v155-20260731/points.json.gz",
]);
let status = windowObject.UfoCropCircleLayer.getStatus();
assert.equal(status.loaded, true);
assert.ok(status.renderedCount > 0 && status.renderedCount < 4305, "exact-date filter is applied");

view.hideNonExactDates = false;
await new Promise((resolve) => setTimeout(resolve, 320));
status = windowObject.UfoCropCircleLayer.getStatus();
assert.equal(status.renderedCount, 4305, "all mapped crop circles render when date precision is unrestricted");

view.hideLowPrecisionCoordinates = true;
await new Promise((resolve) => setTimeout(resolve, 320));
status = windowObject.UfoCropCircleLayer.getStatus();
assert.equal(status.renderedCount, 10, "exact-coordinate filter retains only reviewed/corroborated fields");

const visibleMarker = statefulVisibleMarker();
await visibleMarker.fire("click");
await new Promise((resolve) => setTimeout(resolve, 30));
assert.ok(requests.some((request) => /\/details\/chunk_\d{3}\.json\.gz$/.test(request)), "opening a marker loads one detail chunk");
assert.match(elements.get("#crop-circle-detail-body").innerHTML, /Measurement-informed schematic/);

await windowObject.UfoCropCircleLayer.setEnabled(false);
assert.equal(windowObject.UfoCropCircleLayer.getStatus().enabled, false);
assert.equal(mapLayers.size, 0);

console.log(JSON.stringify({ ok: true, requests: requests.length, mapped: 4305, exact: 10 }));

function statefulVisibleMarker() {
  const activeLayers = [...mapLayers];
  assert.equal(activeLayers.length, 1);
  const visibleLayers = activeLayers[0].getLayers();
  assert.equal(visibleLayers.length, 10);
  return visibleLayers[0];
}
