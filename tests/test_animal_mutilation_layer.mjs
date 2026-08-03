import assert from "node:assert/strict";
import { createHash, webcrypto } from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import vm from "node:vm";
import { gunzipSync, gzipSync } from "node:zlib";


const repoRoot = path.resolve(import.meta.dirname, "..");
const staticRoot = path.join(repoRoot, "webapp", "static_public");
const animalRoot = path.join(staticRoot, "data", "animal_mutilations");
const layerSource = await fs.readFile(path.join(staticRoot, "animal_mutilation_layer.js"), "utf8");
const bootstrapSource = await fs.readFile(path.join(staticRoot, "animal_mutilation_bootstrap.js"), "utf8");
const indexSource = await fs.readFile(path.join(staticRoot, "index.html"), "utf8");
const appSource = await fs.readFile(path.join(staticRoot, "app.js"), "utf8");
const stylesheetSource = await fs.readFile(path.join(staticRoot, "styles.css"), "utf8");


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

let activeDocument = null;
class MockElement {
  constructor({ value = "", checked = false, tagName = "DIV" } = {}) {
    this.attributes = new Map();
    this.classList = new MockClassList();
    this.dataset = {};
    this.hidden = false;
    this.disabled = false;
    this.checked = checked;
    this.value = value;
    this.tagName = tagName;
    this.textContent = "";
    this.innerHTML = "";
    this.listeners = new Map();
    this.children = [];
    this.focusables = [];
    this.focusCount = 0;
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); }
  appendChild(child) { this.children.push(child); return child; }
  addEventListener(name, handler) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(handler);
  }
  async dispatch(name, event = {}) {
    event.target ||= this;
    event.preventDefault ||= function () { this.defaultPrevented = true; };
    for (const handler of this.listeners.get(name) || []) await handler(event);
    return event;
  }
  focus() {
    this.focusCount += 1;
    if (activeDocument) activeDocument.activeElement = this;
  }
  querySelectorAll() { return this.focusables.slice(); }
  closest() { return null; }
}


function createElements() {
  return new Map([
    ["#overlay-animal-mutilations", new MockElement({ tagName: "BUTTON" })],
    ["#animal-mutilation-status", new MockElement()],
    ["#animal-mutilation-browser-open", new MockElement({ tagName: "BUTTON" })],
    ["#animal-mutilation-browser", new MockElement()],
    ["#animal-mutilation-browser-close", new MockElement({ tagName: "BUTTON" })],
    ["#animal-mutilation-search", new MockElement({ tagName: "INPUT" })],
    ["#animal-mutilation-species-filter", new MockElement({ value: "all", tagName: "SELECT" })],
    ["#animal-mutilation-mapped-filter", new MockElement({ value: "all", tagName: "SELECT" })],
    ["#animal-mutilation-date-filter", new MockElement({ value: "all_time", tagName: "SELECT" })],
    ["#animal-mutilation-date-start", new MockElement({ tagName: "INPUT" })],
    ["#animal-mutilation-date-end", new MockElement({ tagName: "INPUT" })],
    ["#animal-mutilation-browser-reset", new MockElement({ tagName: "BUTTON" })],
    ["#animal-mutilation-browser-summary", new MockElement()],
    ["#animal-mutilation-browser-results", new MockElement()],
    ["#animal-mutilation-browser-more", new MockElement({ tagName: "BUTTON" })],
    ["#animal-mutilation-detail-panel", new MockElement()],
    ["#animal-mutilation-detail-body", new MockElement()],
    ["#animal-mutilation-detail-close", new MockElement({ tagName: "BUTTON" })],
  ]);
}


async function createHarness({ maliciousDetail = false } = {}) {
  const manifest = JSON.parse(await fs.readFile(path.join(animalRoot, "manifest.json"), "utf8"));
  const payloadOverrides = new Map();
  const failedPaths = new Map();
  if (maliciousDetail) {
    const declaration = manifest.details.files[0];
    const records = JSON.parse(gunzipSync(await fs.readFile(path.join(animalRoot, declaration.path))).toString("utf8"));
    const recordId = Object.keys(records)[0];
    records[recordId].title = '<img src=x onerror="alert(1)">';
    records[recordId].evidenceExcerpts = ["<script>alert(2)</script>"];
    records[recordId].sourceRefs = [
      { sourceId: "unsafe-script", sourceHash: "0".repeat(64), locator: "test", url: "javascript:alert(3)" },
      { sourceId: "unsafe-private", sourceHash: "1".repeat(64), locator: "test", url: "http://127.0.0.1/private" },
    ];
    const bytes = gzipSync(Buffer.from(JSON.stringify(records)), { level: 9, mtime: 0 });
    declaration.bytes = bytes.length;
    declaration.decodedBytes = gunzipSync(bytes).length;
    declaration.sha256 = createHash("sha256").update(bytes).digest("hex");
    payloadOverrides.set(declaration.path, bytes);
  }

  const elements = createElements();
  const requests = [];
  const requestCaches = [];
  const abortedRequests = [];
  const delayedPaths = new Set();
  const createdMarkers = [];
  const createdLayerGroups = [];
  const mapLayers = new Set();
  const panes = new Map();
  const mapContainerListeners = new Set();
  const intervals = new Map();
  let nextIntervalId = 1;
  const dispatchedEvents = [];
  const consoleErrors = [];

  const mapContainer = {
    focusCount: 0,
    focus() {
      this.focusCount += 1;
      if (activeDocument) activeDocument.activeElement = this;
    },
    addEventListener(name, handler, capture) {
      if (name === "click" && capture) mapContainerListeners.add(handler);
    },
    removeEventListener(name, handler, capture) {
      if (name === "click" && capture) mapContainerListeners.delete(handler);
    },
    dispatchClick(point) {
      const event = {
        mockPoint: point,
        defaultPrevented: false,
        immediatePropagationStopped: false,
        target: { closest() { return null; } },
        preventDefault() { this.defaultPrevented = true; },
        stopPropagation() { this.propagationStopped = true; },
        stopImmediatePropagation() { this.immediatePropagationStopped = true; },
      };
      for (const handler of mapContainerListeners) handler(event);
      return event;
    },
  };
  const map = {
    createPane(name) { panes.set(name, { style: {} }); },
    getPane(name) { return panes.get(name) || null; },
    getContainer() { return mapContainer; },
    hasLayer(layer) { return mapLayers.has(layer); },
    removeLayer(layer) { mapLayers.delete(layer); },
    latLngToContainerPoint(latlng) {
      const lat = Number(latlng.lat ?? latlng[0]);
      const lng = Number(latlng.lng ?? latlng[1]);
      return { x: lng * 3, y: lat * -3 };
    },
    mouseEventToContainerPoint(event) { return event.mockPoint; },
  };
  function layerGroup() {
    const layers = [];
    const group = {
      addLayer(layer) { layers.push(layer); return this; },
      clearLayers() { layers.length = 0; },
      getLayers() { return layers.slice(); },
      addTo(targetMap) { this._map = targetMap; mapLayers.add(this); return this; },
    };
    createdLayerGroups.push(group);
    return group;
  }
  function circleMarker(latlng, options) {
    const marker = {
      latlng,
      options: { ...options },
      getLatLng() { return { lat: Number(latlng[0]), lng: Number(latlng[1]) }; },
    };
    createdMarkers.push(marker);
    return marker;
  }

  const view = {
    map,
    timeRangeStartOrdinal: -500000,
    timeRangeEndOrdinal: 500000,
    timeRangeIsAllTime: true,
    hideLowPrecisionCoordinates: false,
    hideNonExactDates: false,
    filterGeneration: 1,
  };

  async function localFetch(input, init = {}) {
    const url = new URL(String(input));
    requests.push(url.pathname);
    requestCaches.push(init.cache || "default");
    const signal = init.signal;
    if (signal && signal.aborted) {
      abortedRequests.push(url.pathname);
      throw new DOMException("The operation was aborted.", "AbortError");
    }
    if (delayedPaths.has(url.pathname)) {
      await new Promise((resolve, reject) => {
        let settled = false;
        const onAbort = () => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          abortedRequests.push(url.pathname);
          reject(new DOMException("The operation was aborted.", "AbortError"));
        };
        const timer = setTimeout(() => {
          if (settled) return;
          settled = true;
          if (signal) signal.removeEventListener("abort", onAbort);
          resolve();
        }, 80);
        if (signal) signal.addEventListener("abort", onAbort, { once: true });
      });
    }
    if (signal && signal.aborted) {
      abortedRequests.push(url.pathname);
      throw new DOMException("The operation was aborted.", "AbortError");
    }
    if (failedPaths.has(url.pathname)) {
      return new Response("forced failure", { status: failedPaths.get(url.pathname) });
    }
    if (url.pathname === "/data/animal_mutilations/manifest.json") {
      return new Response(JSON.stringify(manifest), { status: 200 });
    }
    const relative = url.pathname.replace(/^\/releases\/[^/]+\//, "").replace(/^\/+/, "");
    try {
      const bytes = payloadOverrides.get(relative) || await fs.readFile(path.join(animalRoot, relative));
      return new Response(bytes, { status: 200 });
    } catch (error) {
      return new Response("not found", { status: 404 });
    }
  }

  const documentListeners = new Map();
  const documentObject = {
    baseURI: "https://example.test/",
    activeElement: null,
    querySelector(selector) { return elements.get(selector) || null; },
    createElement(tagName) { return new MockElement({ tagName: String(tagName).toUpperCase() }); },
    addEventListener(name, handler) {
      if (!documentListeners.has(name)) documentListeners.set(name, []);
      documentListeners.get(name).push(handler);
    },
  };
  activeDocument = documentObject;
  elements.get("#animal-mutilation-browser").hidden = true;
  elements.get("#animal-mutilation-detail-panel").hidden = true;
  elements.get("#animal-mutilation-browser").focusables = [
    elements.get("#animal-mutilation-browser-close"),
    elements.get("#animal-mutilation-search"),
    elements.get("#animal-mutilation-browser-reset"),
  ];

  class MockCustomEvent {
    constructor(type, options) { this.type = type; this.detail = options && options.detail; }
  }
  const windowObject = {
    L: {
      canvas() { return { _container: { style: {} } }; },
      layerGroup,
      circleMarker,
    },
    UfoTimelineExtensions: { getContext() { return view; } },
    CustomEvent: MockCustomEvent,
    dispatchEvent(event) { dispatchedEvents.push(event); return true; },
    crypto: webcrypto,
    setTimeout,
    clearTimeout,
    setInterval(handler) {
      const id = nextIntervalId++;
      intervals.set(id, handler);
      return id;
    },
    clearInterval(id) { intervals.delete(id); },
  };
  const context = vm.createContext({
    window: windowObject,
    document: documentObject,
    URL,
    fetch: localFetch,
    Response,
    Blob,
    DecompressionStream,
    TextDecoder,
    AbortController,
    DOMException,
    console: { error(...args) { consoleErrors.push(args); } },
    setTimeout,
    clearTimeout,
    crypto: webcrypto,
  });
  vm.runInContext(layerSource, context, { filename: "animal_mutilation_layer.js" });

  return {
    api: windowObject.UfoAnimalMutilationLayer,
    elements,
    requests,
    requestCaches,
    abortedRequests,
    delayedPaths,
    failedPaths,
    createdMarkers,
    createdLayerGroups,
    mapLayers,
    mapContainer,
    intervals,
    dispatchedEvents,
    consoleErrors,
    manifest,
    view,
    tick() { for (const handler of intervals.values()) handler(); },
  };
}


function resultTarget(recordId, chunk) {
  const button = new MockElement({ tagName: "BUTTON" });
  button.getAttribute = function (name) {
    if (name === "data-animal-record-id") return recordId;
    if (name === "data-animal-detail-chunk") return String(chunk);
    return null;
  };
  return {
    button,
    closest(selector) {
      if (!selector.includes("data-animal-record-id")) return null;
      return button;
    },
  };
}


assert.match(indexSource, /id="overlay-animal-mutilations"[\s\S]*?<span>Animal Mutilation Reports<\/span>/, "toggle uses the exact layer name");
assert.match(indexSource, /id="animal-mutilation-browser"[\s\S]*?role="dialog"[\s\S]*?aria-modal="true"/, "all-record browser is an accessible modal dialog");
assert.doesNotMatch(indexSource, /<script src="\.\/animal_mutilation_layer\.js/, "heavy animal runtime is not a startup script");
assert.match(bootstrapSource, /animal_mutilation_layer\.js/, "bootstrap lazily loads the animal runtime");
assert.match(bootstrapSource, /openBrowser\(browse\)/, "Browse action has an independent lazy entry point");
assert.match(appSource, /timeRangeIsAllTime:\s*state\.timeRangeMode === "full"/, "extension context distinguishes All Time for undated records");
assert.match(appSource, /data-map-legend-animal-mutilations/, "map legend exposes the animal context layer");
assert.doesNotMatch(layerSource, /polyline|setCropTraceFocus|traceNeighborhood/i, "animal runtime cannot construct or enter traces and relationships");
assert.match(layerSource, /Reported animal mutilation — unreviewed/, "every detail uses the fixed unreviewed label");
assert.match(layerSource, /Withheld for privacy/, "internal-only locations render explicit privacy copy");
assert.match(layerSource, /No public map point supplied/, "null public geometry is explained explicitly");
assert.match(stylesheetSource, /overlay-chip-swatch-animal-mutilations[\s\S]*?border:\s*2px dashed #9a6500/, "animal marker key is a high-contrast neutral amber, hollow, and dashed");

{
  const harness = await createHarness();
  assert.equal(harness.requests.length, 0, "loading the animal runtime makes zero data requests");
  await harness.api.openBrowser(harness.elements.get("#animal-mutilation-browser-open"));
  assert.deepEqual(harness.requests, [
    "/data/animal_mutilations/manifest.json",
    "/releases/animal-mutilations-v1-20260802/catalog.json.gz",
  ], "Browse loads only the Pages manifest and all-record R2 catalog");
  assert.deepEqual(harness.requestCaches, ["no-cache", "force-cache"]);
  assert.equal(harness.api.getStatus().catalogLoaded, true);
  assert.equal(harness.api.getStatus().loaded, false, "Browse never fetches the point index");
  assert.match(harness.elements.get("#animal-mutilation-browser-summary").textContent, /1,177 matching reports, including undated reports/);

  const mapped = harness.elements.get("#animal-mutilation-mapped-filter");
  mapped.value = "unmapped";
  await mapped.dispatch("change");
  assert.match(harness.elements.get("#animal-mutilation-browser-summary").textContent, /659 matching reports/);
  mapped.value = "all";
  const dateScope = harness.elements.get("#animal-mutilation-date-filter");
  dateScope.value = "undated";
  await dateScope.dispatch("change");
  assert.match(harness.elements.get("#animal-mutilation-browser-summary").textContent, /28 matching reports/);
  dateScope.value = "exact_day";
  await dateScope.dispatch("change");
  assert.match(harness.elements.get("#animal-mutilation-browser-summary").textContent, /921 matching reports/);

  const browser = harness.elements.get("#animal-mutilation-browser");
  const first = browser.focusables[0];
  const last = browser.focusables.at(-1);
  first.focus();
  const reverseTab = await browser.dispatch("keydown", { key: "Tab", shiftKey: true });
  assert.equal(reverseTab.defaultPrevented, true);
  assert.equal(activeDocument.activeElement, last, "Shift+Tab wraps to the last dialog control");
  last.focus();
  const forwardTab = await browser.dispatch("keydown", { key: "Tab", shiftKey: false });
  assert.equal(forwardTab.defaultPrevented, true);
  assert.equal(activeDocument.activeElement, first, "Tab wraps to the first dialog control");
  await browser.dispatch("keydown", { key: "Escape" });
  assert.equal(browser.hidden, true, "Escape closes the all-record browser");
  assert.ok(harness.elements.get("#animal-mutilation-browser-open").focusCount > 0, "dialog close restores focus");
}

{
  const harness = await createHarness();
  const catalogPath = "/releases/animal-mutilations-v1-20260802/catalog.json.gz";
  harness.delayedPaths.add(catalogPath);
  const opener = harness.elements.get("#animal-mutilation-browser-open");
  const search = harness.elements.get("#animal-mutilation-search");
  const pending = harness.api.openBrowser(opener);
  assert.equal(activeDocument.activeElement, search, "browser focus enters immediately while the catalog is loading");
  const focusCountBeforeClose = search.focusCount;
  await new Promise((resolve) => setTimeout(resolve, 10));
  harness.api.closeBrowser();
  assert.equal(harness.elements.get("#animal-mutilation-browser").hidden, true);
  assert.equal(activeDocument.activeElement, opener, "closing a loading browser restores its trigger");
  await pending;
  assert.equal(search.focusCount, focusCountBeforeClose, "a stale catalog completion cannot refocus a hidden browser");
  assert.ok(harness.abortedRequests.includes(catalogPath), "closing the browser aborts its catalog transfer");
  assert.equal(harness.api.getStatus().catalogLoaded, false, "an aborted catalog is not cached");
}

{
  const harness = await createHarness();
  await harness.api.setEnabled(true);
  assert.deepEqual(harness.requests, [
    "/data/animal_mutilations/manifest.json",
    "/releases/animal-mutilations-v1-20260802/points.json.gz",
  ], "map toggle loads points without the all-record catalog");
  assert.equal(harness.api.getStatus().catalogLoaded, false);
  assert.equal(harness.api.getStatus().visibleRecords, 518);
  assert.equal(harness.api.getStatus().visiblePositions, 400);
  assert.equal(harness.createdMarkers.length, 400, "shared generalized positions are grouped into one marker");
  assert.equal(harness.createdMarkers.reduce((sum, marker) => sum + marker.options.animalStackCount, 0), 518);
  assert.ok(harness.createdMarkers.every((marker) => marker.options.interactive === false));
  assert.ok(harness.createdMarkers.every((marker) => marker.options.fill === false && marker.options.dashArray === "4 3"));

  const groupedMarker = harness.createdMarkers.find((marker) => marker.options.animalStackCount > 1);
  const point = {
    x: groupedMarker.getLatLng().lng * 3,
    y: groupedMarker.getLatLng().lat * -3,
  };
  const click = harness.mapContainer.dispatchClick(point);
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert.equal(click.immediatePropagationStopped, true, "only an actual animal marker hit captures the map click");
  assert.match(harness.elements.get("#animal-mutilation-detail-body").innerHTML, /Reported animal mutilation — unreviewed/);
  assert.match(harness.elements.get("#animal-mutilation-detail-body").innerHTML, /reports share this generalized position/);
  assert.match(harness.elements.get("#animal-mutilation-detail-body").innerHTML, /has not been scientifically verified/);

  harness.view.hideLowPrecisionCoordinates = true;
  harness.view.filterGeneration += 1;
  harness.tick();
  assert.equal(harness.api.getStatus().visibleRecords, 0);
  assert.match(harness.elements.get("#animal-mutilation-status").textContent, /zero reviewed exact coordinates/);
  harness.view.hideLowPrecisionCoordinates = false;
  harness.view.hideNonExactDates = true;
  harness.view.filterGeneration += 1;
  harness.tick();
  assert.equal(harness.api.getStatus().visibleRecords, 339, "Exact day filter honors source precision");
  harness.view.hideNonExactDates = false;
  harness.view.timeRangeIsAllTime = false;
  harness.view.filterGeneration += 1;
  harness.tick();
  assert.equal(harness.api.getStatus().visibleRecords, 511, "seven mapped undated reports disappear outside All Time");

  await harness.api.setEnabled(false);
  assert.equal(harness.api.getStatus().enabled, false);
  assert.equal(harness.mapLayers.size, 0, "disable removes the animal layer");
  assert.equal(harness.createdLayerGroups[0].getLayers().length, 0, "disable releases all retained marker objects");
  assert.equal(harness.intervals.size, 0, "disable clears filter polling");
  assert.equal(harness.elements.get("#animal-mutilation-detail-panel").hidden, true, "disable closes detail UI");
  const requestsBeforeReenable = harness.requests.length;
  await harness.api.setEnabled(true);
  assert.equal(harness.requests.length, requestsBeforeReenable, "re-enable reuses validated point data without refetching");
  assert.equal(harness.mapLayers.size, 1, "re-enable restores the map layer");
  await harness.api.setEnabled(false);
}

{
  const harness = await createHarness();
  const pointsPath = "/releases/animal-mutilations-v1-20260802/points.json.gz";
  harness.delayedPaths.add(pointsPath);
  const pending = harness.api.setEnabled(true);
  await new Promise((resolve) => setTimeout(resolve, 10));
  await harness.api.setEnabled(false);
  assert.equal(await pending, false, "a disabled in-flight layer resolves as cancelled");
  assert.ok(harness.abortedRequests.includes(pointsPath), "disable aborts the point-index transfer");
  assert.equal(harness.api.getStatus().loaded, false, "an aborted point index is not cached");
  assert.equal(harness.mapLayers.size, 0);
  assert.doesNotMatch(harness.elements.get("#animal-mutilation-status").textContent, /failed|error/i);
}

{
  const harness = await createHarness();
  await harness.api.openBrowser(harness.elements.get("#animal-mutilation-browser-open"));
  const catalog = JSON.parse(gunzipSync(await fs.readFile(path.join(animalRoot, "catalog.json.gz"))).toString("utf8"));
  const first = catalog[0];
  const second = catalog.find((row) => row[9] !== first[9]);
  const firstPath = `/releases/animal-mutilations-v1-20260802/details/chunk_${String(first[9]).padStart(3, "0")}.json.gz`;
  harness.delayedPaths.add(firstPath);
  const results = harness.elements.get("#animal-mutilation-browser-results");
  const firstTarget = resultTarget(first[0], first[9]);
  const secondTarget = resultTarget(second[0], second[9]);
  await results.dispatch("click", { target: firstTarget });
  await results.dispatch("click", { target: secondTarget });
  await new Promise((resolve) => setTimeout(resolve, 120));
  const detailHtml = harness.elements.get("#animal-mutilation-detail-body").innerHTML;
  assert.match(detailHtml, new RegExp(second[0]), "newest detail request wins a cross-chunk race");
  assert.doesNotMatch(detailHtml, new RegExp(first[0]), "late detail response cannot replace the newest selection");
  assert.ok(harness.abortedRequests.includes(firstPath), "a newer cross-chunk selection aborts the stale detail transfer");
  const secondPath = `/releases/animal-mutilations-v1-20260802/details/chunk_${String(second[9]).padStart(3, "0")}.json.gz`;
  const before = harness.requests.filter((request) => request === secondPath).length;
  const cachedTarget = resultTarget(second[0], second[9]);
  await results.dispatch("click", { target: cachedTarget });
  await new Promise((resolve) => setTimeout(resolve, 20));
  const after = harness.requests.filter((request) => request === secondPath).length;
  assert.equal(after, before, "loaded detail chunks are cached");
  assert.ok(harness.api.getStatus().detailChunksCached <= 5, "detail cache is bounded to five chunks");
  await harness.elements.get("#animal-mutilation-detail-close").dispatch("click");
  assert.equal(harness.elements.get("#animal-mutilation-browser").hidden, false, "closing a catalog detail restores the report browser");
  assert.equal(activeDocument.activeElement, cachedTarget.button, "closing a catalog detail restores the selected report trigger");
}

{
  const harness = await createHarness();
  await harness.api.openBrowser(harness.elements.get("#animal-mutilation-browser-open"));
  const catalog = JSON.parse(gunzipSync(await fs.readFile(path.join(animalRoot, "catalog.json.gz"))).toString("utf8"));
  const first = catalog[0];
  const sameChunk = catalog.find((row) => row[0] !== first[0] && row[9] === first[9]);
  const detailPath = `/releases/animal-mutilations-v1-20260802/details/chunk_${String(first[9]).padStart(3, "0")}.json.gz`;
  harness.delayedPaths.add(detailPath);
  const results = harness.elements.get("#animal-mutilation-browser-results");
  const firstTarget = resultTarget(first[0], first[9]);
  const sameChunkTarget = resultTarget(sameChunk[0], sameChunk[9]);
  await results.dispatch("click", { target: firstTarget });
  await results.dispatch("click", { target: sameChunkTarget });
  assert.equal(harness.requests.filter((request) => request === detailPath).length, 1, "simultaneous same-chunk selections share one transfer");
  await new Promise((resolve) => setTimeout(resolve, 120));
  assert.match(harness.elements.get("#animal-mutilation-detail-body").innerHTML, new RegExp(sameChunk[0]), "the newest same-chunk selection renders");
}

{
  const harness = await createHarness();
  await harness.api.openBrowser(harness.elements.get("#animal-mutilation-browser-open"));
  const catalog = JSON.parse(gunzipSync(await fs.readFile(path.join(animalRoot, "catalog.json.gz"))).toString("utf8"));
  const first = catalog[0];
  const detailPath = `/releases/animal-mutilations-v1-20260802/details/chunk_${String(first[9]).padStart(3, "0")}.json.gz`;
  harness.delayedPaths.add(detailPath);
  const target = resultTarget(first[0], first[9]);
  await harness.elements.get("#animal-mutilation-browser-results").dispatch("click", { target });
  assert.equal(
    activeDocument.activeElement,
    harness.elements.get("#animal-mutilation-detail-close"),
    "a loading detail receives focus immediately after its browser trigger is hidden"
  );
  await new Promise((resolve) => setTimeout(resolve, 10));
  await harness.elements.get("#animal-mutilation-detail-close").dispatch("click");
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.ok(harness.abortedRequests.includes(detailPath), "closing a loading detail aborts its transfer");
  assert.equal(harness.api.getStatus().detailChunksCached, 0, "an aborted detail chunk is not cached");
  assert.equal(harness.elements.get("#animal-mutilation-browser").hidden, false);
  assert.equal(activeDocument.activeElement, target.button, "closing a loading detail restores its catalog trigger");
}

{
  const harness = await createHarness();
  await harness.api.openBrowser(harness.elements.get("#animal-mutilation-browser-open"));
  const catalog = JSON.parse(gunzipSync(await fs.readFile(path.join(animalRoot, "catalog.json.gz"))).toString("utf8"));
  const first = catalog[0];
  const detailPath = `/releases/animal-mutilations-v1-20260802/details/chunk_${String(first[9]).padStart(3, "0")}.json.gz`;
  harness.failedPaths.set(detailPath, 503);
  const target = resultTarget(first[0], first[9]);
  await harness.elements.get("#animal-mutilation-browser-results").dispatch("click", { target });
  assert.equal(activeDocument.activeElement, harness.elements.get("#animal-mutilation-detail-close"));
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(harness.elements.get("#animal-mutilation-detail-panel").hidden, true, "a failed detail request closes its loading panel");
  assert.equal(harness.elements.get("#animal-mutilation-browser").hidden, false, "a failed detail request restores the browser");
  assert.equal(activeDocument.activeElement, target.button, "a failed detail request restores its trigger");
  assert.match(harness.elements.get("#animal-mutilation-status").textContent, /request failed \(503\)/);
  assert.equal(harness.consoleErrors.length, 1, "the recovered request failure is still reported for diagnostics");
}

{
  const harness = await createHarness({ maliciousDetail: true });
  await harness.api.openBrowser(harness.elements.get("#animal-mutilation-browser-open"));
  const catalog = JSON.parse(gunzipSync(await fs.readFile(path.join(animalRoot, "catalog.json.gz"))).toString("utf8"));
  const first = catalog[0];
  await harness.elements.get("#animal-mutilation-browser-results").dispatch("click", {
    target: resultTarget(first[0], first[9]),
  });
  await new Promise((resolve) => setTimeout(resolve, 30));
  const html = harness.elements.get("#animal-mutilation-detail-body").innerHTML;
  assert.match(html, /&lt;script&gt;alert\(2\)&lt;\/script&gt;/, "untrusted detail text is HTML-escaped");
  assert.doesNotMatch(html, /<script|<img|href="javascript:|href="http:\/\/127\./i, "script markup and non-public source URLs never become active HTML");
  assert.match(html, /unsafe-script/, "unsafe URL provenance remains visible as non-link text");
  assert.match(html, /unsafe-private/, "private URL provenance remains visible as non-link text");
}

console.log("Animal Mutilation Reports runtime tests passed.");
