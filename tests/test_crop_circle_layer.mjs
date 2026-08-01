import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import vm from "node:vm";
import { gunzipSync } from "node:zlib";


const repoRoot = path.resolve(import.meta.dirname, "..");
const staticRoot = path.join(repoRoot, "webapp", "static_public");
const requests = [];
const requestCaches = [];
const createdMarkers = [];
const createdPolylines = [];
const delayedDetailPaths = new Set();

class MockClassList {
  constructor() { this.names = new Set(); }
  toggle(name, enabled) {
    if (enabled === undefined) enabled = !this.names.has(name);
    if (enabled) this.names.add(name);
    else this.names.delete(name);
  }
  add(name) { this.names.add(name); }
  remove(name) { this.names.delete(name); }
  contains(name) { return this.names.has(name); }
}

class MockElement {
  constructor({ value = "", checked = false } = {}) {
    this.attributes = new Map();
    this.classList = new MockClassList();
    this.dataset = {};
    this.hidden = false;
    this.disabled = false;
    this.checked = checked;
    this.value = value;
    this.textContent = "";
    this.innerHTML = "";
    this.listeners = new Map();
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); }
  addEventListener(name, handler) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(handler);
  }
  async dispatch(name, event = {}) {
    for (const handler of this.listeners.get(name) || []) await handler(event);
  }
  querySelector() { return null; }
}

const elements = new Map([
  ["#overlay-crop-circles", new MockElement()],
  ["#crop-circle-status", new MockElement()],
  ["#crop-circle-detail-panel", new MockElement()],
  ["#crop-circle-detail-body", new MockElement()],
  ["#crop-circle-detail-close", new MockElement()],
  ["#crop-circle-chronology-controls", new MockElement()],
  ["#crop-circle-chronology-enabled", new MockElement({ checked: false })],
  ["#crop-circle-chronology-relation", new MockElement({ value: "same_day" })],
  ["#crop-circle-chronology-coordinate-scope", new MockElement({ value: "field" })],
  ["#crop-circle-chronology-max-distance", new MockElement({ value: "250" })],
  ["#crop-circle-chronology-status", new MockElement()],
]);

const mapLayers = new Set();
const panes = new Map();
const mapHandlers = new Map();
let mapZoom = 8;
let underlyingPointClicks = 0;
const mapContainerListeners = new Set();
const mapContainer = {
  addEventListener(name, handler, capture) {
    if (name === "click" && capture) mapContainerListeners.add(handler);
  },
  removeEventListener(name, handler, capture) {
    if (name === "click" && capture) mapContainerListeners.delete(handler);
  },
  dispatchClick(point, targetClosest = null) {
    const event = {
      mockPoint: point,
      defaultPrevented: false,
      immediatePropagationStopped: false,
      target: { closest(selector) { return targetClosest && selector.includes(targetClosest) ? this : null; } },
      preventDefault() { this.defaultPrevented = true; },
      stopPropagation() { this.immediatePropagationStopped = true; },
      stopImmediatePropagation() { this.immediatePropagationStopped = true; },
    };
    for (const handler of mapContainerListeners) {
      handler(event);
      if (event.immediatePropagationStopped) break;
    }
    if (!event.immediatePropagationStopped) underlyingPointClicks += 1;
    return event;
  },
};
const map = {
  createPane(name) { panes.set(name, { style: {} }); },
  getPane(name) { return panes.get(name) || null; },
  hasLayer(layer) { return mapLayers.has(layer); },
  removeLayer(layer) { mapLayers.delete(layer); },
  panInside() {},
  on(name, handler) {
    if (!mapHandlers.has(name)) mapHandlers.set(name, new Set());
    mapHandlers.get(name).add(handler);
  },
  off(name, handler) { if (mapHandlers.has(name)) mapHandlers.get(name).delete(handler); },
  getZoom() { return mapZoom; },
  getContainer() { return mapContainer; },
  mouseEventToContainerPoint(event) { return event.mockPoint; },
  getBounds() {
    return {
      pad() { return this; },
      contains() { return true; },
    };
  },
  latLngToLayerPoint(latlng) { return { x: Number(latlng[1]) * 12, y: Number(latlng[0]) * -12 }; },
  latLngToContainerPoint(latlng) { return { x: Number(latlng.lng ?? latlng[1]) * 12, y: Number(latlng.lat ?? latlng[0]) * -12 }; },
  layerPointToLatLng(point) { return { lat: Number(point.y) / -12, lng: Number(point.x) / 12 }; },
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
    fire(name) {
      const handler = handlers.get(name);
      if (handler) return handler({ originalEvent: { stopPropagation() {} } });
    },
  };
  createdMarkers.push(marker);
  return marker;
}

function polyline(latlngs, options) {
  const line = { latlngs, options };
  createdPolylines.push(line);
  return line;
}

class MockCanvas {}
MockCanvas.include = function (methods) { Object.assign(MockCanvas.prototype, methods); };

const view = {
  map,
  timeRangeStartOrdinal: -500000,
  timeRangeEndOrdinal: 500000,
  hideLowPrecisionCoordinates: false,
  hideNonExactDates: true,
  colorMode: "craft_type",
  filterGeneration: 1,
};

async function localFetch(input, init = {}) {
  const url = new URL(String(input));
  requests.push(url.pathname);
  requestCaches.push(init.cache || "default");
  if (delayedDetailPaths.has(url.pathname)) await new Promise((resolve) => setTimeout(resolve, 70));
  const relative = url.pathname
    .replace(/^\/releases\/[^/]+\//, "data/crop_circles/")
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
    Canvas: MockCanvas,
    canvas() { return Object.assign(Object.create(MockCanvas.prototype), { _container: { style: {} } }); },
    layerGroup,
    circleMarker,
    polyline,
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
const stylesheetSource = await fs.readFile(path.join(staticRoot, "styles.css"), "utf8");
assert.match(stylesheetSource, /\.overlay-chip\[data-overlay-kind="crop-circles"\]\.is-active\s*\{\s*color:\s*#344000;/, "active crop chip uses readable dark text in the light theme");
assert.match(stylesheetSource, /:root\[data-theme="dark"\] \.overlay-chip\[data-overlay-kind="crop-circles"\]\.is-active\s*\{\s*color:\s*#d8ff3e;/, "dark theme retains the acid-lime crop label");
assert.match(stylesheetSource, /\.cc-detail-eyebrow\s*\{\s*color:\s*#596b00;/, "small crop detail eyebrow uses the higher-contrast light-theme color");
const manifestFixture = JSON.parse(await fs.readFile(path.join(staticRoot, "data", "crop_circles", "manifest.json"), "utf8"));
assert.equal(manifestFixture.releaseId, "crop-circles-v156-20260731", "harness targets the immutable v156 crop release");
const expectedPointsPath = new URL(
  manifestFixture.points.path,
  manifestFixture.assetBaseUrl || "https://example.test/data/crop_circles/",
).pathname;
const pointRowsFixture = JSON.parse(gunzipSync(await fs.readFile(path.join(staticRoot, "data", "crop_circles", "points.json.gz"))).toString("utf8"));

const layerApi = windowObject.UfoCropCircleLayer;
assert.equal(requests.length, 0, "loading the runtime must not request crop data before enable");
assert.ok(layerApi, "runtime API is exposed");

await layerApi.setEnabled(true);
assert.deepEqual(requests.slice(0, 2), [
  "/data/crop_circles/manifest.json",
  expectedPointsPath,
]);
assert.deepEqual(requestCaches.slice(0, 2), ["no-cache", "force-cache"], "mutable manifest bypasses stale cache while immutable R2 payloads remain cacheable");
let status = layerApi.getStatus();
assert.equal(status.loaded, true);
assert.equal(status.traceEligible, false, "crop records never enter UFO traces or hops");
assert.ok(status.renderedCount > 0 && status.renderedCount < 4305, "exact-date filter is applied");
assert.equal(elements.get("#crop-circle-chronology-controls").hidden, false, "separate crop chronology controls appear only after enable");
assert.equal(status.chronology.enabled, false, "crop chronology is opt-in");
assert.equal(status.chronology.relation, "same_day");
assert.equal(status.chronology.coordinateScope, "field");
assert.equal(status.chronology.maxDistanceKm, 250);
assert.equal(panes.get("cropCirclePane").style.zIndex, "610", "noninteractive crop Canvas stays visible above point, trace, and marker/cluster panes");
assert.equal(panes.get("cropCirclePane").style.pointerEvents, "none", "full-map crop Canvas pane never intercepts underlying point/cluster clicks");
assert.equal(panes.get("cropCircleChronologyPane").style.zIndex, "480", "crop chronology sits above UFO trace panes but below selectable markers");

view.hideNonExactDates = false;
await waitForPoll();
status = layerApi.getStatus();
assert.equal(status.renderedCount, 4305, "all mapped crop records remain represented when date precision is unrestricted");
assert.equal(status.renderedPositionCount, 2541, "identical coordinates are grouped into one selectable marker");
assert.equal(manifestFixture.counts.recordsWithSourceDescriptions, 564);
assert.equal(manifestFixture.counts.sourceDescriptionAssertions, 566);
assert.match(elements.get("#crop-circle-status").textContent, /Source narratives captured for 564 of 7,745 records\./);
const pointLayer = findPointLayer();
assert.equal(pointLayer.getLayers().length, 2541);

const invariantMarker = pointLayer.getLayers()[0];
const invariantStyle = markerInvariant(invariantMarker);
assert.equal(invariantMarker.options.ccMarkerKind, "crop-circle-spiral");
assert.equal(invariantMarker.options.interactive, false, "Leaflet Canvas path hit handling is disabled in favor of bounded capture hit-testing");
assert.equal(invariantMarker.options.renderer._container.style.pointerEvents, "none");
assert.equal(typeof MockCanvas.prototype._updateCropCircleSpiral, "function", "shared Leaflet Canvas receives the spiral renderer");
assert.equal(typeof invariantMarker._updatePath, "function");
assert.equal(invariantMarker.options.ccAccentColor, "#d8ff3e");
assert.notEqual(invariantMarker.options.color, "#c34cff", "old UFO-conflicting purple is not used");
assert.ok(drawSpiralForTest(invariantMarker) >= 4, "spiral marker draws a charcoal/ivory ring and two-tone spiral on shared Canvas");
view.colorMode = "chronology";
view.timeRangeStartOrdinal += 1;
await waitForPoll();
assert.deepEqual(markerInvariant(findPointLayer().getLayers()[0]), invariantStyle, "crop marker appearance is invariant across UFO color modes");

const stackMarker = findPointLayer().getLayers().find((marker) => marker.options.ccStackCount > 1);
assert.ok(stackMarker, "at least one shared coordinate has a stack chooser");
const detailRequestsBeforeChooser = requests.length;
const outsideClicksBefore = underlyingPointClicks;
const outsideEvent = mapContainer.dispatchClick({ x: 999999, y: 999999 });
assert.equal(outsideEvent.immediatePropagationStopped, false, "non-crop click passes through the crop overlay");
assert.equal(underlyingPointClicks, outsideClicksBefore + 1, "underlying UFO point click handler remains reachable with crop overlay on");
const areaDrawEvent = mapContainer.dispatchClick(map.latLngToContainerPoint(stackMarker.getLatLng()), "#area-selection-draw-surface");
assert.equal(areaDrawEvent.immediatePropagationStopped, false, "active area-selection draw surface takes precedence over crop hit-testing");
const cropClicksBefore = underlyingPointClicks;
const cropHitEvent = mapContainer.dispatchClick(map.latLngToContainerPoint(stackMarker.getLatLng()), ".leaflet-marker-icon");
assert.equal(cropHitEvent.immediatePropagationStopped, true, "a visible bounded crop spiral hit wins even when a lower DOM marker overlaps it");
assert.equal(cropHitEvent.defaultPrevented, true);
assert.equal(underlyingPointClicks, cropClicksBefore, "crop hit does not also trigger an underlying UFO point");
assert.equal(requests.length, detailRequestsBeforeChooser, "opening a stack chooser does not preload detail chunks");
assert.match(elements.get("#crop-circle-detail-body").innerHTML, /crop-circle records/);
assert.match(elements.get("#crop-circle-detail-body").innerHTML, /data-cc-record-id=/);
assert.ok(isAscending(stackMarker.options.ccRecordIds.map((id) => chooserOrdinal(id))), "stack entries are ordered by catalog date");

const chosenId = stackMarker.options.ccRecordIds[0];
await clickPanelTarget("[data-cc-record-id]", { ccRecordId: chosenId });
await new Promise((resolve) => setTimeout(resolve, 40));
assert.ok(requests.some((request) => /\/details\/chunk_\d{3}\.json\.gz$/.test(request)), "choosing a stacked record loads only its detail chunk");
assert.match(elements.get("#crop-circle-detail-body").innerHTML, /Measurement-informed schematic/);
assert.match(elements.get("#crop-circle-detail-body").innerHTML, /Catalog summary|Source description/);

const enrichment = JSON.parse(await fs.readFile(path.join(repoRoot, "data", "crop_circle_description_enrichment_v1.json"), "utf8"));
const noNarrativeId = findPointLayer().getLayers()
  .flatMap((marker) => marker.options.ccRecordIds)
  .find((id) => !Object.prototype.hasOwnProperty.call(enrichment.records, id));
assert.ok(noNarrativeId, "fixture includes a record without a captured source narrative");
await layerApi.openRecord(noNarrativeId);
assert.match(
  elements.get("#crop-circle-detail-body").innerHTML,
  /No source narrative currently captured for this record\./,
  "missing descriptions are stated explicitly instead of replaced with catalog boilerplate",
);
const truncatedNarrativeId = Object.entries(enrichment.records).find(([, record]) => record.sourceExcerptTruncated)?.[0];
assert.ok(truncatedNarrativeId, "fixture includes a rights-bounded truncated source excerpt");
await layerApi.openRecord(truncatedNarrativeId);
assert.match(elements.get("#crop-circle-detail-body").innerHTML, /\[short excerpt\]/, "truncated source text is explicitly labeled as an excerpt");

await layerApi.openRecord("cc_6e836743a510");
const antonitoMarkup = elements.get("#crop-circle-detail-body").innerHTML;
assert.match(antonitoMarkup, /<h4>Source description<\/h4>/);
assert.match(antonitoMarkup, /Twelve circles in pasture grass discovered near a cattle mutilation/);
assert.match(antonitoMarkup, /Credit: Jeffrey Wilson/);
assert.match(antonitoMarkup, /<h4>Catalog summary<\/h4>/);
assert.match(antonitoMarkup, /Formation time is not established/);
assert.match(antonitoMarkup, />ICCRA — source narrative<\/a>/, "source links use a fixed source label, never raw credit text");
assert.doesNotMatch(antonitoMarkup, /class="cc-detail-description"/, "generated catalog prose is never presented as a description");

await layerApi.openRecord("cc_3e5e0b843661");
const multiDescriptionMarkup = elements.get("#crop-circle-detail-body").innerHTML;
assert.equal((multiDescriptionMarkup.match(/<article class="cc-source-description">/g) || []).length, 2, "merged formations render every source description independently");
assert.match(multiDescriptionMarkup, /Assertion iccra_2144557e42f87d0c/);
assert.match(multiDescriptionMarkup, /Assertion iccra_9dc9a6f437981f19/);

await layerApi.openRecord("cc_0123e86c92f6");
const unsafeAttributionMarkup = elements.get("#crop-circle-detail-body").innerHTML;
assert.match(unsafeAttributionMarkup, /Full attribution is available on the source page\./);
assert.doesNotMatch(unsafeAttributionMarkup, /Credit: see report\./i, "raw or non-display attribution is never rendered as credit");

mapZoom = 8;
layerApi.setChronology({ enabled: true, relation: "same_day", coordinateScope: "all", maxDistanceKm: 1000 });
status = layerApi.getStatus();
assert.equal(status.chronology.enabled, true);
assert.equal(status.chronology.role, "catalog_date_adjacency_only");
assert.equal(status.chronology.traceEligible, false);
assert.ok(status.chronology.candidateEdges > 0, "same-day crop chronology produces a deterministic forest");
const chronologyLayer = findChronologyLayer();
assert.notEqual(chronologyLayer, findPointLayer(), "crop chronology is isolated from the marker and UFO trace layers");
assert.equal(panes.get("cropCircleChronologyPane").style.pointerEvents, "none");
assert.equal(chronologyLayer.getLayers().length, status.chronology.renderedEdges * 2, "same-day links are undirected paired strokes without arrowheads");
assert.ok(chronologyLayer.getLayers().every((line) => !line.options.dashArray), "same-day links are solid and arrow-free");
assert.ok(chronologyLayer.getLayers().every(hasNonZeroSegment), "zero-length chronology strokes are excluded");
const sameDaySnapshot = JSON.stringify(chronologyLayer.getLayers().map((line) => line.latlngs));
layerApi.setChronology({ enabled: true, relation: "same_day", coordinateScope: "all", maxDistanceKm: 1000 });
assert.equal(JSON.stringify(findChronologyLayer().getLayers().map((line) => line.latlngs)), sameDaySnapshot, "same-day MST/forest output is deterministic");

mapZoom = 3;
layerApi.setChronology({ enabled: true, relation: "30", coordinateScope: "all", maxDistanceKm: 1000 });
status = layerApi.getStatus();
assert.equal(status.chronology.relation, "30");
assert.equal(status.chronology.coordinateScope, "all");
assert.equal(status.chronology.maxDistanceKm, 1000);
assert.ok(status.chronology.renderedEdges <= 120, "low-zoom viewport edge cap is enforced");
assert.equal(status.chronology.capped, status.chronology.candidateEdges > 120);
assert.ok(findChronologyLayer().getLayers().some((line) => line.options.dashArray === "8 7"), "later-date links use a visibly different dashed acid-lime treatment");
assert.match(elements.get("#crop-circle-chronology-status").textContent, /catalog-date links/);

view.hideLowPrecisionCoordinates = true;
await waitForPoll();
status = layerApi.getStatus();
assert.equal(status.renderedCount, 10, "exact-coordinate filter retains only reviewed/corroborated records");
assert.equal(status.renderedPositionCount, 10);

const raceRows = rowsFromUnusedChunks(3);
assert.equal(raceRows.length, 3, "fixture has unused detail chunks for async race checks");
const firstRacePath = detailPathForRow(raceRows[0]);
delayedDetailPaths.add(firstRacePath);
const staleOpen = layerApi.openRecord(raceRows[0][0]);
await new Promise((resolve) => setTimeout(resolve, 5));
assert.equal(await layerApi.openRecord(raceRows[1][0]), true);
assert.equal(await staleOpen, false, "a slower earlier click cannot overwrite a newer detail selection");
delayedDetailPaths.delete(firstRacePath);
const winningDetail = await localDetailForRow(raceRows[1]);
assert.ok(elements.get("#crop-circle-detail-body").innerHTML.includes(escapeFixture(winningDetail.location)), "newer detail remains visible after stale request resolves");

const disableRacePath = detailPathForRow(raceRows[2]);
delayedDetailPaths.add(disableRacePath);
const pendingAtDisable = layerApi.openRecord(raceRows[2][0]);
await new Promise((resolve) => setTimeout(resolve, 5));
await layerApi.setEnabled(false);
assert.equal(await pendingAtDisable, false, "disable invalidates pending detail responses");
delayedDetailPaths.delete(disableRacePath);
status = layerApi.getStatus();
assert.equal(status.enabled, false);
assert.equal(status.chronology.enabled, false);
assert.equal(status.chronology.renderedEdges, 0);
assert.equal(status.chronology.eligibleNodes, 0);
assert.equal(status.chronology.candidateEdges, 0);
assert.equal(status.renderedCount, 0);
assert.equal(status.renderedPositionCount, 0);
assert.equal(mapLayers.size, 0, "disable removes both crop markers and crop chronology");
assert.equal(elements.get("#crop-circle-detail-panel").hidden, true, "stale detail response cannot reopen the panel after disable");
assert.equal(elements.get("#crop-circle-chronology-controls").hidden, true);
assert.equal((mapHandlers.get("moveend") || new Set()).size, 0, "viewport listener is removed on disable");
assert.equal((mapHandlers.get("zoomend") || new Set()).size, 0, "zoom listener is removed on disable");
assert.equal(mapContainerListeners.size, 0, "bounded crop click capture listener is removed on disable");
assert.ok(requestCaches.slice(1).every((mode) => mode === "force-cache"), "all immutable point/detail payload requests remain force-cache");

await testBootstrapRetry();

console.log(JSON.stringify({
  ok: true,
  requests: requests.length,
  mappedRecords: 4305,
  mappedPositions: 2541,
  exact: 10,
}));

function waitForPoll() {
  return new Promise((resolve) => setTimeout(resolve, 320));
}

function findPointLayer() {
  const layer = [...mapLayers].find((candidate) => candidate.getLayers().some((item) => item.options?.ccMarkerKind === "crop-circle-spiral"));
  assert.ok(layer, "crop marker layer is active");
  return layer;
}

function findChronologyLayer() {
  const point = findPointLayer();
  const layer = [...mapLayers].find((candidate) => candidate !== point);
  assert.ok(layer, "separate crop chronology layer is active");
  return layer;
}

function markerInvariant(marker) {
  return {
    color: marker.options.color,
    fillColor: marker.options.fillColor,
    accent: marker.options.ccAccentColor,
    ivory: marker.options.ccIvoryColor,
    outline: marker.options.ccOutlineColor,
    kind: marker.options.ccMarkerKind,
  };
}

function chooserOrdinal(id) {
  const marker = createdMarkers.find((candidate) => candidate.options.ccRecordIds?.includes(id));
  const markup = elements.get("#crop-circle-detail-body").innerHTML;
  const index = markup.indexOf(`data-cc-record-id="${id}"`);
  assert.ok(marker && index >= 0);
  const dateMatch = markup.slice(index, index + 180).match(/<strong>(\d{4}-\d{2}-\d{2})/);
  assert.ok(dateMatch);
  return dateMatch[1];
}

function isAscending(values) {
  return values.every((value, index) => index === 0 || values[index - 1] <= value);
}

async function clickPanelTarget(selector, dataset) {
  const target = {
    dataset,
    closest(candidate) { return candidate === selector ? this : null; },
  };
  await elements.get("#crop-circle-detail-panel").dispatch("click", { target, stopPropagation() {} });
}

function hasNonZeroSegment(line) {
  if (!Array.isArray(line.latlngs) || line.latlngs.length < 2) return false;
  const first = line.latlngs[0];
  return line.latlngs.slice(1).some((point) => Number(first[0] ?? first.lat) !== Number(point[0] ?? point.lat) || Number(first[1] ?? first.lng) !== Number(point[1] ?? point.lng));
}

function drawSpiralForTest(marker) {
  let strokes = 0;
  const noop = () => {};
  const renderer = Object.create(MockCanvas.prototype);
  renderer._drawing = true;
  renderer._ctx = {
    save: noop,
    restore: noop,
    translate: noop,
    beginPath: noop,
    arc: noop,
    setLineDash: noop,
    moveTo: noop,
    lineTo: noop,
    stroke() { strokes += 1; },
    fill: noop,
  };
  renderer._updateCropCircleSpiral({
    _point: { x: 20, y: 20 },
    _radius: marker.options.radius,
    _empty() { return false; },
    options: marker.options,
  });
  return strokes;
}

function usedDetailChunks() {
  return new Set(requests.map((request) => request.match(/\/details\/chunk_(\d{3})\.json\.gz$/)?.[1]).filter(Boolean));
}

function rowsFromUnusedChunks(count) {
  const used = usedDetailChunks();
  const rows = [];
  for (const row of pointRowsFixture) {
    const chunk = String(row[8]).padStart(3, "0");
    if (used.has(chunk) || rows.some((candidate) => candidate[8] === row[8])) continue;
    rows.push(row);
    if (rows.length === count) break;
  }
  return rows;
}

function detailPathForRow(row) {
  const chunk = String(row[8]).padStart(3, "0");
  const filename = manifestFixture.details.chunkPattern
    .replace("{chunk:03d}", chunk)
    .replace("{chunk}", String(row[8]));
  const relative = String(manifestFixture.details.basePath || "") + filename;
  return new URL(relative, manifestFixture.assetBaseUrl || "https://example.test/data/crop_circles/").pathname;
}

async function localDetailForRow(row) {
  const chunk = String(row[8]).padStart(3, "0");
  const bytes = await fs.readFile(path.join(staticRoot, "data", "crop_circles", "details", `chunk_${chunk}.json.gz`));
  return JSON.parse(gunzipSync(bytes).toString("utf8"))[String(row[0])];
}

function escapeFixture(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function testBootstrapRetry() {
  const retryButton = new MockElement();
  let appendCount = 0;
  let enables = 0;
  let lastScriptSrc = "";
  const retryWindow = {
    L: { map() { return map; } },
    setTimeout,
    clearTimeout,
  };
  const retryDocument = {
    baseURI: "https://example.test/",
    querySelector(selector) { return selector === "#overlay-crop-circles" ? retryButton : null; },
    createElement() { return {}; },
    head: {
      appendChild(script) {
        appendCount += 1;
        lastScriptSrc = script.src;
        if (appendCount === 1) {
          queueMicrotask(() => script.onerror());
          return;
        }
        retryWindow.UfoCropCircleLayer = {
          setEnabled() { enables += 1; return Promise.resolve(true); },
        };
        queueMicrotask(() => script.onload());
      },
    },
  };
  const retryContext = vm.createContext({
    window: retryWindow,
    document: retryDocument,
    URL,
    console: { error() {} },
    setTimeout,
    clearTimeout,
  });
  const bootstrapSource = await fs.readFile(path.join(staticRoot, "crop_circle_bootstrap.js"), "utf8");
  vm.runInContext(bootstrapSource, retryContext, { filename: "crop_circle_bootstrap.js" });
  assert.equal(appendCount, 0, "bootstrap makes no crop request or runtime injection before user action");
  await retryButton.dispatch("click");
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(appendCount, 1);
  await retryButton.dispatch("click");
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(appendCount, 2, "transient runtime load failure can be retried without reloading the app");
  assert.match(lastScriptSrc, /crop_circle_layer\.js\?v=2026-08-01-crop-circles-v156$/);
  assert.equal(enables, 1);
}
