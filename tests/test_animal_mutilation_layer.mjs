import assert from "node:assert/strict";
import { createHash, webcrypto } from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import vm from "node:vm";
import { gunzipSync, gzipSync } from "node:zlib";


const repoRoot = path.resolve(import.meta.dirname, "..");
const staticRoot = path.join(repoRoot, "webapp", "static_public");
const animalRoot = path.join(staticRoot, "data", "animal_mutilations");
const bundledAnimalRoot = path.join(repoRoot, "static_bundle", "data", "animal_mutilations");
const layerSource = await fs.readFile(path.join(staticRoot, "animal_mutilation_layer.js"), "utf8");
const bootstrapSource = await fs.readFile(path.join(staticRoot, "animal_mutilation_bootstrap.js"), "utf8");
const indexSource = await fs.readFile(path.join(staticRoot, "index.html"), "utf8");
const appSource = await fs.readFile(path.join(staticRoot, "app.js"), "utf8");
const stylesheetSource = await fs.readFile(path.join(staticRoot, "styles.css"), "utf8");
const cowArtMatch = /--animal-cow-art:\s*url\("data:image\/svg\+xml,([^"]+)"\)/.exec(stylesheetSource);
assert.ok(cowArtMatch, "the cow is embedded as one self-contained SVG data URI");
const cowArtSvg = decodeURIComponent(cowArtMatch[1]);


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


async function createHarness({ maliciousDetail = false, contextEvidenceFixture = false } = {}) {
  const manifest = JSON.parse(await fs.readFile(path.join(animalRoot, "manifest.json"), "utf8"));
  const payloadOverrides = new Map();
  const failedPaths = new Map();
  let contextFixture = null;
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
    const decodedBytes = Buffer.from(JSON.stringify(records));
    const bytes = gzipSync(decodedBytes, { level: 9, mtime: 0 });
    declaration.bytes = bytes.length;
    declaration.decodedBytes = gunzipSync(bytes).length;
    declaration.sha256 = createHash("sha256").update(bytes).digest("hex");
    payloadOverrides.set(declaration.path, bytes);
    payloadOverrides.set(declaration.path.replace(/\.json\.gz$/i, ".json"), decodedBytes);
  }
  if (contextEvidenceFixture) {
    const pointRows = JSON.parse(gunzipSync(await fs.readFile(path.join(animalRoot, manifest.points.path))).toString("utf8"));
    pointRows.forEach(function (row) { row.push(4, null); });
    pointRows[0][8] = 0;
    pointRows[0][9] = 75;
    pointRows[1][8] = 1;
    pointRows[1][9] = 650;
    manifest.codes ||= {};
    manifest.codes.coordinateEvidenceClass = {
      source_exact: 0, source_bounded: 1, source_regional: 2,
      source_uncertainty_unknown: 3, generalized_public_marker: 4,
      locality_centroid: 5, postal_centroid: 6, approximate_map_pin: 7, unmapped: 8,
    };
    const pointDecoded = Buffer.from(JSON.stringify(pointRows));
    const pointBytes = gzipSync(pointDecoded, { level: 9, mtime: 0 });
    manifest.points.bytes = pointBytes.length;
    manifest.points.decodedBytes = pointDecoded.length;
    manifest.points.sha256 = createHash("sha256").update(pointBytes).digest("hex");
    payloadOverrides.set(manifest.points.path, pointBytes);
    payloadOverrides.set(manifest.points.path.replace(/\.json\.gz$/i, ".json"), pointDecoded);

    const recordId = String(pointRows[0][0]);
    const chunkNumber = Number(pointRows[0][7]);
    const declaration = manifest.details.files[chunkNumber];
    const records = JSON.parse(gunzipSync(await fs.readFile(path.join(animalRoot, declaration.path))).toString("utf8"));
    Object.assign(records[recordId], {
      title: "Questa calf incident",
      status: "source_reviewed",
      reviewState: "source_reviewed",
      dateRole: "occurrence_date",
      coordinateEvidenceClass: "source_exact",
      coordinateMethod: "source_reported_event_site",
      coordinateUncertaintyM: 75,
      analysisTier: "animal_strict",
      exclusionReasonCodes: [],
      dedupStatus: "stable_unique",
      independenceStatus: "qualifying_independent_source",
      sourceFamilyIds: ["sf_rommel_operation_animal_mutilation"],
    });
    const detailDecoded = Buffer.from(JSON.stringify(records));
    const detailBytes = gzipSync(detailDecoded, { level: 9, mtime: 0 });
    declaration.bytes = detailBytes.length;
    declaration.decodedBytes = detailDecoded.length;
    declaration.sha256 = createHash("sha256").update(detailBytes).digest("hex");
    payloadOverrides.set(declaration.path, detailBytes);
    payloadOverrides.set(declaration.path.replace(/\.json\.gz$/i, ".json"), detailDecoded);
    contextFixture = { recordId, chunkNumber };
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
  function divIcon(options) {
    return { options: { ...options } };
  }
  function marker(latlng, options) {
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
    const relative = url.pathname
      .replace(/^\/data\/animal_mutilations\//, "")
      .replace(/^\/releases\/[^/]+\//, "")
      .replace(/^\/+/, "");
    try {
      const payloadRoot = url.pathname.startsWith("/data/animal_mutilations/") ? bundledAnimalRoot : animalRoot;
      const bytes = payloadOverrides.get(relative) || await fs.readFile(path.join(payloadRoot, relative));
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
      layerGroup,
      divIcon,
      marker,
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
    mapContainerListeners,
    intervals,
    dispatchedEvents,
    consoleErrors,
    manifest,
    contextFixture,
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


function createAnimalBootstrapHarness() {
  const toggle = new MockElement({ tagName: "BUTTON" });
  const browse = new MockElement({ tagName: "BUTTON" });
  const status = new MockElement();
  const readyHandlers = [];
  const enableCalls = [];
  let appendCount = 0;
  const bootstrapWindow = {
    addEventListener(name, handler) {
      if (name === "ufo:timeline-ready") readyHandlers.push(handler);
    },
  };
  const bootstrapDocument = {
    baseURI: "https://example.test/",
    querySelector(selector) {
      if (selector === "#overlay-animal-mutilations") return toggle;
      if (selector === "#animal-mutilation-browser-open") return browse;
      if (selector === "#animal-mutilation-status") return status;
      return null;
    },
    createElement() { return {}; },
    head: {
      appendChild(script) {
        appendCount += 1;
        bootstrapWindow.UfoAnimalMutilationLayer = {
          setEnabled(value) {
            enableCalls.push(Boolean(value));
            return Promise.resolve(Boolean(value));
          },
          openBrowser() { return Promise.resolve(1177); },
        };
        queueMicrotask(() => script.onload());
      },
    },
  };
  vm.runInContext(bootstrapSource, vm.createContext({
    window: bootstrapWindow,
    document: bootstrapDocument,
    URL,
    console: { error() {} },
    setTimeout,
    clearTimeout,
  }), { filename: "animal_mutilation_bootstrap.js" });
  return {
    toggle,
    status,
    readyHandlers,
    enableCalls,
    get appendCount() { return appendCount; },
  };
}


assert.match(indexSource, /id="overlay-animal-mutilations"[^>]*aria-label="Animal Mutilation Reports"/, "compact toggle preserves the exact accessible layer name");
assert.match(indexSource, /id="overlay-animal-mutilations"[\s\S]*?<span class="overlay-chip-label" aria-hidden="true">Mutilations<\/span>[\s\S]*?id="overlay-animal-mutilations-count"/, "compact toggle keeps its visual label and shared visible count");
assert.match(indexSource, /id="overlay-animal-mutilations"[^>]*data-default-enabled="true"[^>]*aria-pressed="true"/, "animal reports are enabled by default in the accessible initial state");
assert.match(indexSource, /id="animal-mutilation-browser"[\s\S]*?role="dialog"[\s\S]*?aria-modal="true"/, "all-record browser is an accessible modal dialog");
assert.doesNotMatch(indexSource, /<script src="\.\/animal_mutilation_layer\.js/, "heavy animal runtime is not a startup script");
assert.match(bootstrapSource, /animal_mutilation_layer\.js/, "bootstrap lazily loads the animal runtime");
assert.match(bootstrapSource, /animal_mutilation_layer\.js\?v=2026-08-12-context-evidence-v2/, "default-on animal runtime uses a release-specific cache key");
assert.match(bootstrapSource, /addEventListener\("ufo:timeline-ready"[\s\S]*?enableDesiredLayer\(\)/, "default activation waits for the core timeline Ready event");
assert.match(bootstrapSource, /openBrowser\(browse\)/, "Browse action has an independent lazy entry point");
assert.match(appSource, /CustomEvent\("ufo:timeline-ready"/, "the core app announces the post-startup activation boundary");
assert.match(appSource, /timeRangeIsAllTime:\s*state\.timeRangeMode === "full"/, "extension context distinguishes All Time for undated records");
assert.match(appSource, /data-map-legend-animal-mutilations/, "map legend exposes the animal context layer");
assert.match(appSource, /!animalMutilationOverlayActive\(\)/, "legend reset treats the default-on animal layer as clean and restores it when disabled");
assert.doesNotMatch(layerSource, /polyline|setCropTraceFocus|traceNeighborhood/i, "animal runtime cannot construct or enter traces and relationships");
assert.match(layerSource, /Reported animal mutilation — unreviewed/, "legacy unreviewed details retain their established label");
assert.match(layerSource, /coordinateEvidenceClass:\s*8, coordinateUncertaintyM:\s*9/, "point decoder accepts appended coordinate-evidence columns");
assert.match(layerSource, /coordinateEvidenceClassForRow\(row\) !== "source_exact"/, "Exact coordinates only is evidence-driven rather than hardcoded to zero");
assert.match(layerSource, /source-bounded[\s\S]*?generalized or otherwise non-strict/, "map status distinguishes exact, bounded, and generalized coordinate evidence");
assert.match(layerSource, /Review state[\s\S]*?Date role[\s\S]*?Coordinate evidence[\s\S]*?Analysis tier[\s\S]*?Strict-lane exclusions/, "detail view exposes scientific readiness fields");
assert.match(layerSource, /Source families[\s\S]*?Independence[\s\S]*?Deduplication[\s\S]*?not_asserted/, "detail provenance remains explicit and noncausal");
assert.match(layerSource, /Withheld for privacy/, "internal-only locations render explicit privacy copy");
assert.match(layerSource, /No public map point supplied/, "null public geometry is explained explicitly");
assert.match(layerSource, /window\.L\.divIcon[\s\S]*?animal-mutilation-map-cow[\s\S]*?aria-hidden="true"/, "animal markers use a decorative cow icon");
assert.doesNotMatch(layerSource + stylesheetSource, /1F404|Emoji/, "cow rendering is deterministic and does not depend on platform emoji");
assert.doesNotMatch(stylesheetSource, /--animal-cow-mask/, "the obsolete single-color cow mask is removed");
assert.match(cowArtSvg, /viewBox='0 0 48 32'/, "the cow art has a compact map-scale view box");
assert.match(cowArtSvg, /#101417/i, "the cow art contains a warm near-black outline and patches");
assert.match(cowArtSvg, /#e9f2ff/i, "the cow art uses a cool off-white distinct from the map background");
assert.match(cowArtSvg, /stroke-width='2'/, "the cow outline remains legible at the smallest marker size");
assert.doesNotMatch(cowArtSvg, /<(?:script|image|foreignObject)\b|href=|url\(/i, "cow art is self-contained and inert");
assert.match(stylesheetSource, /overlay-chip-swatch-animal-mutilations::before[\s\S]*?background:\s*var\(--animal-cow-art\)[\s\S]*?rotate\(180deg\)/, "the layer key shows the shared black-and-off-white upside-down cow");
assert.match(stylesheetSource, /animal-mutilation-map-cow\s*\{[\s\S]*?width:\s*100%[\s\S]*?height:\s*100%[\s\S]*?background:\s*var\(--animal-cow-art\)[\s\S]*?rotate\(180deg\)/, "map cows fill their computed stack size and render upside down");
assert.match(appSource, /"Animal Mutilation Reports",\s*"#101417",\s*"cow"/, "the map legend uses the two-tone cow rather than the old amber ring");
assert.match(stylesheetSource, /map-legend-marker-sample-cow::before[\s\S]*?var\(--animal-cow-art\)[\s\S]*?rotate\(180deg\)/, "the map legend cow reuses the exact layer art");
assert.match(indexSource, /id="cluster-quick-animal-mutilations"[\s\S]*?aria-pressed="true"[\s\S]*?aria-controls="map animal-mutilation-status"[\s\S]*?map-legend-marker-sample-cow/, "the quick animal toggle starts on, controls the map status, and uses the exact legend cow class");
assert.match(stylesheetSource, /map-control-context-button-animal\[aria-pressed="true"\][\s\S]*?rgba\(233, 242, 255, 0\.2\)/, "the active quick cow has a distinct cool-white state treatment");
assert.match(stylesheetSource, /map-control-context-button-animal\[aria-pressed="true"\][\s\S]*?border-color:\s*#33404a/, "the light-theme animal quick-toggle boundary remains visible");
assert.match(stylesheetSource, /:root\[data-theme="dark"\] \.map-control-context-button-animal\[aria-pressed="true"\][\s\S]*?rgba\(233, 242, 255, 0\.76\)/, "the dark-theme animal quick toggle retains its cool-white boundary");
assert.match(appSource, /clusterQuickAnimalMutilationsButton:\s*document\.querySelector\("#cluster-quick-animal-mutilations"\)/, "the quick animal toggle is registered with the core UI");
assert.match(appSource, /clusterQuickAnimalMutilationsButton\.addEventListener\("click"[\s\S]*?overlayAnimalMutilationsToggle\.click\(\)/, "the quick animal toggle delegates to the canonical overlay control");
assert.match(appSource, /ufo:animal-mutilation-statechange[\s\S]*?renderMapControlQuickButtons\(\)[\s\S]*?renderMapLegend\(\)/, "animal runtime state synchronizes the quick toggle and legend");

{
  const defaultBootstrap = createAnimalBootstrapHarness();
  assert.equal(defaultBootstrap.toggle.getAttribute("aria-pressed"), "true");
  assert.equal(defaultBootstrap.appendCount, 0, "animal runtime injection is deferred until the core Ready boundary");
  assert.equal(defaultBootstrap.readyHandlers.length, 1);
  defaultBootstrap.readyHandlers[0]();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(defaultBootstrap.appendCount, 1);
  assert.deepEqual(defaultBootstrap.enableCalls, [true], "Ready enables the animal map exactly once");
  defaultBootstrap.readyHandlers[0]();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(defaultBootstrap.appendCount, 1, "repeated Ready events do not reinject the runtime");
  assert.deepEqual(defaultBootstrap.enableCalls, [true]);
}

{
  const optedOutBootstrap = createAnimalBootstrapHarness();
  await optedOutBootstrap.toggle.dispatch("click");
  assert.equal(optedOutBootstrap.toggle.getAttribute("aria-pressed"), "false");
  optedOutBootstrap.readyHandlers[0]();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(optedOutBootstrap.appendCount, 0, "a pre-Ready user opt-out prevents default animal activation");
  assert.deepEqual(optedOutBootstrap.enableCalls, []);
}

{
  const harness = await createHarness();
  const remoteCatalogPath = new URL(harness.manifest.catalog.path, harness.manifest.assetBaseUrl).pathname;
  harness.failedPaths.set("/data/animal_mutilations/catalog.json", 404);
  assert.equal(harness.requests.length, 0, "importing the heavy animal runtime has no fetch side effects before bootstrap activation");
  await harness.api.openBrowser(harness.elements.get("#animal-mutilation-browser-open"));
  assert.deepEqual(harness.requests, [
    "/data/animal_mutilations/manifest.json",
    "/data/animal_mutilations/catalog.json",
    remoteCatalogPath,
  ], "Browse falls back from the local catalog probe to the manifest-declared immutable R2 catalog");
  assert.deepEqual(harness.requestCaches, ["no-cache", "force-cache", "force-cache"]);
  assert.equal(harness.api.getStatus().catalogLoaded, true);
  assert.equal(harness.api.getStatus().loaded, false, "Browse never fetches the point index");
  assert.match(harness.elements.get("#animal-mutilation-browser-summary").textContent, /1,184 matching reports, including undated reports/);

  const mapped = harness.elements.get("#animal-mutilation-mapped-filter");
  mapped.value = "unmapped";
  await mapped.dispatch("change");
  assert.match(harness.elements.get("#animal-mutilation-browser-summary").textContent, /666 matching reports/);
  mapped.value = "all";
  const dateScope = harness.elements.get("#animal-mutilation-date-filter");
  dateScope.value = "undated";
  await dateScope.dispatch("change");
  assert.match(harness.elements.get("#animal-mutilation-browser-summary").textContent, /28 matching reports/);
  dateScope.value = "exact_day";
  await dateScope.dispatch("change");
  assert.match(harness.elements.get("#animal-mutilation-browser-summary").textContent, /928 matching reports/);

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
  const catalogPath = "/data/animal_mutilations/catalog.json";
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
  const remotePointsPath = new URL(harness.manifest.points.path, harness.manifest.assetBaseUrl).pathname;
  harness.failedPaths.set("/data/animal_mutilations/points.json", 404);
  await harness.api.setEnabled(true);
  assert.deepEqual(harness.requests, [
    "/data/animal_mutilations/manifest.json",
    "/data/animal_mutilations/points.json",
    remotePointsPath,
  ], "map toggle falls back from the local point-index probe to the manifest-declared immutable R2 points without loading the catalog");
  assert.equal(harness.api.getStatus().catalogLoaded, false);
  assert.equal(harness.api.getStatus().visibleRecords, 518);
  assert.equal(harness.api.getStatus().visiblePositions, 400);
  assert.equal(harness.createdMarkers.length, 400, "shared generalized positions are grouped into one marker");
  assert.equal(harness.createdMarkers.reduce((sum, marker) => sum + marker.options.animalStackCount, 0), 518);
  assert.ok(harness.createdMarkers.every((marker) => marker.options.interactive === false && marker.options.keyboard === false && marker.options.bubblingMouseEvents === false));
  assert.ok(harness.createdMarkers.every((marker) => marker.options.icon.options.className === "animal-mutilation-map-icon"));
  assert.ok(harness.createdMarkers.every((marker) => marker.options.icon.options.html.includes("animal-mutilation-map-cow")));
  assert.ok(harness.createdMarkers.every((marker) => Number(marker.options.animalHitRadius) > 0));

  const singletonMarker = harness.createdMarkers.find((marker) => marker.options.animalStackCount === 1);
  const groupedMarker = harness.createdMarkers.find((marker) => marker.options.animalStackCount > 1);
  assert.ok(groupedMarker.options.icon.options.iconSize[0] > singletonMarker.options.icon.options.iconSize[0], "shared-position cow markers remain visibly larger");
  const cowSizes = harness.createdMarkers.map((marker) => marker.options.icon.options.iconSize[0]);
  assert.equal(Math.min(...cowSizes), 21, "singleton cows retain the tested minimum size");
  assert.ok(Math.max(...cowSizes) <= 31, "the largest grouped cow remains compact");
  const outsideClick = harness.mapContainer.dispatchClick({ x: 100000, y: 100000 });
  assert.equal(outsideClick.immediatePropagationStopped, false, "clicks outside cow hit radii remain available to the map");
  const point = {
    x: groupedMarker.getLatLng().lng * 3,
    y: groupedMarker.getLatLng().lat * -3,
  };
  const click = harness.mapContainer.dispatchClick(point);
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert.equal(click.immediatePropagationStopped, true, "only an actual animal marker hit captures the map click");
  assert.match(harness.elements.get("#animal-mutilation-detail-body").innerHTML, /Reported animal mutilation — unreviewed/);
  assert.match(harness.elements.get("#animal-mutilation-detail-body").innerHTML, /reports share this mapped position/);
  assert.match(harness.elements.get("#animal-mutilation-detail-body").innerHTML, /has not been scientifically verified/);

  harness.view.hideLowPrecisionCoordinates = true;
  harness.view.filterGeneration += 1;
  harness.tick();
  assert.equal(harness.api.getStatus().visibleRecords, 0);
  assert.equal(harness.createdLayerGroups[0].getLayers().length, 0, "exact-coordinate filtering removes every cow marker layer");
  assert.match(harness.elements.get("#animal-mutilation-status").textContent, /No mapped animal reports with source-exact coordinates/);
  harness.view.hideLowPrecisionCoordinates = false;
  harness.view.hideNonExactDates = true;
  harness.view.filterGeneration += 1;
  harness.tick();
  assert.equal(harness.api.getStatus().visibleRecords, 340, "Exact day filter honors source precision");
  harness.view.hideNonExactDates = false;
  harness.view.timeRangeIsAllTime = false;
  harness.view.filterGeneration += 1;
  harness.tick();
  assert.equal(harness.api.getStatus().visibleRecords, 511, "seven mapped undated reports disappear outside All Time");

  await harness.api.setEnabled(false);
  assert.equal(harness.api.getStatus().enabled, false);
  assert.equal(harness.mapLayers.size, 0, "disable removes the animal layer");
  assert.equal(harness.createdLayerGroups[0].getLayers().length, 0, "disable releases all retained marker objects");
  assert.equal(harness.mapContainerListeners.size, 0, "disable removes the cow marker capture listener");
  assert.equal(harness.intervals.size, 0, "disable clears filter polling");
  assert.equal(harness.elements.get("#animal-mutilation-detail-panel").hidden, true, "disable closes detail UI");
  const requestsBeforeReenable = harness.requests.length;
  await harness.api.setEnabled(true);
  assert.equal(harness.requests.length, requestsBeforeReenable, "re-enable reuses validated point data without refetching");
  assert.equal(harness.mapLayers.size, 1, "re-enable restores the map layer");
  await harness.api.setEnabled(false);
}

{
  const harness = await createHarness({ contextEvidenceFixture: true });
  await harness.api.setEnabled(true);
  assert.match(harness.elements.get("#animal-mutilation-status").textContent, /1 source-exact, 1 source-bounded, 516 generalized/);
  harness.view.hideLowPrecisionCoordinates = true;
  harness.view.filterGeneration += 1;
  harness.tick();
  assert.equal(harness.api.getStatus().visibleRecords, 1, "Exact coordinates only retains a source_exact point row");
  assert.match(harness.elements.get("#animal-mutilation-status").textContent, /1 source-exact mapped report/);
  assert.ok(harness.createdMarkers.some(function (marker) {
    return marker.options.animalCoordinateEvidenceClasses.includes("source_exact") &&
      marker.options.animalCoordinateUncertaintyM === 75;
  }), "the appended uncertainty value reaches the decoded marker state");

  await harness.api.openBrowser(harness.elements.get("#animal-mutilation-browser-open"));
  await harness.elements.get("#animal-mutilation-browser-results").dispatch("click", {
    target: resultTarget(harness.contextFixture.recordId, harness.contextFixture.chunkNumber),
  });
  await new Promise((resolve) => setTimeout(resolve, 30));
  const html = harness.elements.get("#animal-mutilation-detail-body").innerHTML;
  assert.match(html, /Questa calf incident/);
  assert.match(html, /Source reviewed/);
  assert.match(html, /Occurrence Date/);
  assert.match(html, /Source-supported event site \(100 m uncertainty or less\)/);
  assert.match(html, /75 m/);
  assert.match(html, /Animal Strict/);
  assert.match(html, /sf_rommel_operation_animal_mutilation/);
  assert.match(html, /Stable Unique/);
  assert.match(html, /not_asserted/);
  assert.doesNotMatch(html, /has not been scientifically verified/);
  await harness.api.setEnabled(false);
}

{
  const harness = await createHarness();
  const pointsPath = "/data/animal_mutilations/points.json";
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
  const firstPath = `/data/animal_mutilations/details/chunk_${String(first[9]).padStart(3, "0")}.json`;
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
  const secondPath = `/data/animal_mutilations/details/chunk_${String(second[9]).padStart(3, "0")}.json`;
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
  const detailPath = `/data/animal_mutilations/details/chunk_${String(first[9]).padStart(3, "0")}.json`;
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
  const detailPath = `/data/animal_mutilations/details/chunk_${String(first[9]).padStart(3, "0")}.json`;
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
  const detailPath = `/data/animal_mutilations/details/chunk_${String(first[9]).padStart(3, "0")}.json`;
  const detailDeclaration = harness.manifest.details.files[Number(first[9])];
  const remoteDetailPath = new URL(detailDeclaration.path, harness.manifest.assetBaseUrl).pathname;
  harness.failedPaths.set(detailPath, 503);
  harness.failedPaths.set(remoteDetailPath, 503);
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
