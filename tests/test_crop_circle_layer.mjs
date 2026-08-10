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
const cropTraceFocusCalls = [];
const cropTraceFocusClears = [];
let activeCropTraceFocus = null;

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
    this.open = false;
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
  ["#crop-circle-selected-summary", new MockElement()],
  ["#crop-circle-ufo-relation-disclosure", new MockElement()],
  ["#crop-circle-chronology-disclosure", new MockElement()],
  ["#crop-circle-radius-disclosure", new MockElement()],
  ["#crop-circle-ufo-relation-window", new MockElement({ value: "off" })],
  ["#crop-circle-ufo-position-quality", new MockElement({ value: "source" })],
  ["#crop-circle-ufo-crop-position-quality", new MockElement({ value: "field" })],
  ["#crop-circle-radius-km", new MockElement({ value: "25" })],
  ["#crop-circle-analyze-ufo-traces", new MockElement({ checked: false })],
  ["#crop-circle-ufo-hop-depth", new MockElement({ value: "1" })],
  ["#crop-circle-ufo-hop-direction", new MockElement({ value: "both" })],
  ["#crop-circle-show-radius", new MockElement({ checked: true })],
  ["#crop-circle-highlight-intersections", new MockElement({ checked: true })],
  ["#crop-circle-focus-mode", new MockElement({ checked: false })],
  ["#crop-circle-ufo-relation-status", new MockElement()],
  ["#crop-circle-chronology-relation", new MockElement({ value: "off" })],
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
  classList: new MockClassList(),
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
  UfoTimelineExtensions: {
    getContext() { return view; },
    async setCropTraceFocus(config) {
      const snapshot = structuredClone(config);
      cropTraceFocusCalls.push(snapshot);
      activeCropTraceFocus = snapshot;
      mapContainer.classList.toggle("crop-circle-focus-active", Boolean(snapshot.isolation));
      return {
        radiusKm: snapshot.radiusKm,
        relationEventCount: snapshot.ufoRelation.window === "off" ? 0 : 3,
        relationCapped: false,
        intersectingTraceCount: snapshot.traceAnalysisEnabled ? 2 : 0,
        reachedTraceCount: snapshot.traceAnalysisEnabled ? snapshot.hops.depth + 1 : 0,
        reachedEventCount: snapshot.traceAnalysisEnabled ? snapshot.hops.depth + 2 : 0,
        depth: snapshot.hops.depth,
        direction: snapshot.hops.direction,
        excludedUkInference: false,
        cropDateExact: Number(snapshot.crop.datePrecisionCode) === 0,
        cropPositionEligible: Number(snapshot.crop.coordinateCode) <= 1 || snapshot.ufoRelation.cropPositionQuality === "all",
        cropPositionIncludedByOverride: Number(snapshot.crop.coordinateCode) > 1 && snapshot.ufoRelation.cropPositionQuality === "all",
        traceAnalysisEnabled: snapshot.traceAnalysisEnabled,
        traceModeIndependent: true,
      };
    },
    clearCropTraceFocus(reason) {
      cropTraceFocusClears.push(String(reason || ""));
      activeCropTraceFocus = null;
      mapContainer.classList.remove("crop-circle-focus-active");
      return true;
    },
  },
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
const indexSource = await fs.readFile(path.join(staticRoot, "index.html"), "utf8");
const appSource = await fs.readFile(path.join(staticRoot, "app.js"), "utf8");
const cropArtMatch = /--crop-circle-art:\s*url\("data:image\/svg\+xml,([^"]+)"\)/.exec(stylesheetSource);
assert.ok(cropArtMatch, "the shared crop spiral is embedded as one self-contained SVG data URI");
const cropArtSvg = decodeURIComponent(cropArtMatch[1]);
assert.match(stylesheetSource, /\.overlay-chip\[data-overlay-kind="crop-circles"\]\.is-active\s*\{\s*color:\s*#344000;/, "active crop chip uses readable dark text in the light theme");
assert.match(stylesheetSource, /:root\[data-theme="dark"\] \.overlay-chip\[data-overlay-kind="crop-circles"\]\.is-active\s*\{\s*color:\s*#d8ff3e;/, "dark theme retains the acid-lime crop label");
assert.match(cropArtSvg, /viewBox='0 0 24 24'/, "shared crop art uses the Canvas marker coordinate scale");
assert.match(cropArtSvg, /#17191b/i, "shared crop art retains the Canvas charcoal outline");
assert.match(cropArtSvg, /#fff8df/i, "shared crop art retains the Canvas ivory uncertainty ring");
assert.match(cropArtSvg, /#d8ff3e/i, "shared crop art retains the Canvas acid-lime spiral");
assert.match(cropArtSvg, /<circle cx='12' cy='12' r='8\.3' stroke='#17191b' stroke-width='4\.6'\/?>/i, "shared crop art retains the Canvas singleton radius and outer outline weight");
assert.match(cropArtSvg, /<circle cx='12' cy='12' r='8\.3' stroke='#fff8df' stroke-width='2'\/?>/i, "shared crop art retains the Canvas inner ivory ring weight");
assert.match(cropArtSvg, /stroke-width='4\.2'/, "shared crop art retains the Canvas spiral outline weight");
assert.match(cropArtSvg, /stroke-width='1\.9'/, "shared crop art retains the Canvas spiral accent weight");
assert.match(cropArtSvg, /d='M 12\.00 11\.65[\s\S]*L 6\.21 14\.84'/, "shared crop art retains the Canvas singleton spiral extent");
assert.match(cropArtSvg, /<circle cx='12' cy='12' r='1\.8' fill='#d8ff3e'\/?>/i, "shared crop art retains the exact-coordinate center dot");
assert.match(source, /const radius = Math\.max\(7\.5,[\s\S]*?\|\| 8\.3\);/, "map renderer singleton radius remains the shared-art reference");
assert.match(source, /context\.lineWidth = 4\.6;[\s\S]*?context\.lineWidth = 2;/, "map renderer ring weights remain the shared-art reference");
assert.equal((cropArtSvg.match(/<path\b/g) || []).length, 2, "charcoal and lime strokes share the same spiral path");
assert.doesNotMatch(cropArtSvg, /<(?:script|image|foreignObject)\b|href=|url\(/i, "shared crop art is self-contained and inert");
assert.match(stylesheetSource, /overlay-chip \.overlay-chip-swatch-crop-circles[\s\S]*?background:\s*var\(--crop-circle-art\)/, "Overlays + View reuses the shared map spiral");
assert.match(stylesheetSource, /map-legend-marker-sample-spiral::before[\s\S]*?background:\s*var\(--crop-circle-art\)/, "the selectable legend reuses the shared map spiral");
assert.match(stylesheetSource, /map-control-context-button-crop\[aria-pressed="true"\][\s\S]*?border-color:\s*#596b00/, "the light-theme crop quick-toggle boundary remains visible");
assert.match(stylesheetSource, /:root\[data-theme="dark"\] \.map-control-context-button-crop\[aria-pressed="true"\][\s\S]*?rgba\(216, 255, 62, 0\.72\)/, "the dark-theme crop quick toggle retains its lime boundary");
assert.match(indexSource, /id="cluster-quick-crop-circles"[\s\S]*?aria-pressed="true"[\s\S]*?aria-controls="map crop-circle-status"[\s\S]*?map-legend-marker-sample-spiral/, "the quick crop toggle starts on, controls the map status, and uses the exact legend icon class");
assert.match(appSource, /clusterQuickCropCirclesButton:\s*document\.querySelector\("#cluster-quick-crop-circles"\)/, "the quick crop toggle is registered with the core UI");
assert.match(appSource, /clusterQuickCropCirclesButton\.addEventListener\("click"[\s\S]*?overlayCropCirclesToggle\.click\(\)/, "the quick crop toggle delegates to the canonical overlay control");
assert.match(appSource, /ufo:crop-circle-statechange[\s\S]*?renderMapControlQuickButtons\(\)[\s\S]*?renderMapLegend\(\)/, "crop runtime state synchronizes the quick toggle and legend");
assert.match(indexSource, /styles\.css\?v=2026-08-10-facility-symbols-v1/, "shared icon CSS uses the current cache-safe shell key");
assert.match(indexSource, /app\.js\?v=2026-08-10-facility-symbols-v1/, "the application runtime uses the current cache-safe shell key");
assert.match(stylesheetSource, /\.cc-detail-eyebrow\s*\{\s*color:\s*#596b00;/, "small crop detail eyebrow uses the higher-contrast light-theme color");
assert.match(stylesheetSource, /\.crop-circle-relation-grid\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/s, "relationship controls use a panel-width-safe one-column layout");
assert.match(indexSource, /<details id="crop-circle-ufo-relation-disclosure"[^>]*aria-disabled="true">[\s\S]*?<summary[^>]*>UFO sighting → later crop record<\/summary>/, "UFO-to-crop controls are a compact disclosure that starts unavailable without a selected crop");
assert.match(indexSource, /<details id="crop-circle-chronology-disclosure"[^>]*aria-disabled="false">[\s\S]*?<summary[^>]*>Crop record → later crop record<\/summary>/, "independent crop-to-crop controls remain available in their own compact disclosure");
assert.match(indexSource, /<details id="crop-circle-radius-disclosure"[^>]*aria-disabled="true">[\s\S]*?<summary[^>]*>Selected crop radius and UFO traces<\/summary>/, "selected-radius trace controls start closed and unavailable without a selected crop");
assert.match(stylesheetSource, /crop-circle-relation-group\[aria-disabled="true"\] summary[\s\S]*?pointer-events:\s*none/, "unavailable relationship disclosures cannot be opened by pointer interaction");
assert.match(indexSource, /id="crop-circle-ufo-crop-position-quality"/, "UFO-to-crop inference has an explicit selected-crop position-quality control");
assert.match(indexSource, /id="crop-circle-analyze-ufo-traces"/, "trace-radius analysis requires an explicit opt-in control");
assert.match(indexSource, /id="overlay-crop-circles"[^>]*data-default-enabled="true"[^>]*aria-pressed="true"/, "crop circles are enabled by default in the accessible initial state");
assert.match(indexSource, /Focus view: show only crop circles, selected relations, and this UFO trace network/, "focus copy truthfully describes the isolated crop relationship result");
assert.doesNotMatch(indexSource, /Same day \+ (?:7|30) days/i, "ambiguous cumulative date-window wording is removed");
assert.match(appSource, /data-map-legend-crop-circles/, "the selectable map legend includes Crop circles under overlays");
assert.match(appSource, /!cropCircleOverlayActive\(\)/, "legend reset treats default-on crop circles as clean and restores them when disabled");
assert.match(appSource, /UfoCropCircleLayer\.resetControls\(\)/, "legend reset preserves the default-on layer while clearing optional scientific analysis controls");
assert.match(appSource, /coordinateCode\) > 1 && relation\.cropPositionQuality !== "all"/, "locality-centroid crops are excluded from UFO-to-crop inference by default");
assert.match(appSource, /filterGeneration:\s*Number\(runtime\.activeFilterGeneration\)/, "crop focus polls the applied—not merely requested—filter generation");
assert.match(appSource, /TRACE_NEIGHBORHOOD\.clipSegmentToCircle/, "selected-radius traces use the tested exact circle clipper");
assert.match(appSource, /if \(traceAnalysisEnabled\) \{\s*const segments = buildCanonicalTraceSegments\(\)/s, "global UFO trace construction is gated behind explicit trace-analysis opt-in");
assert.match(appSource, /cropCircleEmphasisPane/, "inside-radius emphasis has its own noninteractive pane");
assert.match(appSource, /outline:\s*false/, "full selected trace baselines are not given an extra outside-radius outline");
assert.match(appSource, /runtime\.map\.on\("zoomend", runtime\.cropTraceRelationZoomHandler\)/, "UFO-to-crop arrowheads are regenerated at each zoom");
assert.match(appSource, /runtime\.map\.off\("zoomend", runtime\.cropTraceRelationZoomHandler\)/, "relation arrow zoom lifecycle is detached on clear");
const manifestFixture = JSON.parse(await fs.readFile(path.join(staticRoot, "data", "crop_circles", "manifest.json"), "utf8"));
assert.equal(manifestFixture.releaseId, "crop-circles-v156-20260731", "harness targets the immutable v156 crop release");
const expectedPointsPath = new URL(
  manifestFixture.points.path,
  manifestFixture.assetBaseUrl || "https://example.test/data/crop_circles/",
).pathname;
const pointRowsFixture = JSON.parse(gunzipSync(await fs.readFile(path.join(staticRoot, "data", "crop_circles", "points.json.gz"))).toString("utf8"));
const pointRowByIdFixture = new Map(pointRowsFixture.map((row) => [String(row[0]), row]));

const layerApi = windowObject.UfoCropCircleLayer;
assert.equal(requests.length, 0, "importing the heavy crop runtime has no fetch side effects before bootstrap activation");
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
assert.equal(status.chronology.relation, "off");
assert.equal(status.chronology.coordinateScope, "field");
assert.equal(status.chronology.maxDistanceKm, 250);
assert.equal(status.selectedRecordId, null, "enabling the layer does not silently select a crop record");
assert.equal(elements.get("#crop-circle-chronology-relation").disabled, false, "crop-to-crop relation selection does not require a selected record");
assert.equal(elements.get("#crop-circle-chronology-disclosure").getAttribute("aria-disabled"), "false", "the independent crop chronology disclosure is available when the layer is enabled");
assert.equal(elements.get("#crop-circle-ufo-relation-disclosure").getAttribute("aria-disabled"), "true", "UFO-to-crop disclosure waits for a selected crop record");
assert.equal(elements.get("#crop-circle-radius-disclosure").getAttribute("aria-disabled"), "true", "selected-radius disclosure waits for a selected crop record");
elements.get("#crop-circle-chronology-relation").setAttribute("data-analysis-unavailable", "true");
layerApi.setChronology({ relation: "off" });
assert.equal(
  elements.get("#crop-circle-chronology-relation").disabled,
  true,
  "crop-layer control sync cannot re-enable map-only controls while Analysis is active"
);
assert.equal(elements.get("#crop-circle-chronology-disclosure").getAttribute("aria-disabled"), "true", "Analysis mode closes the unavailable crop chronology disclosure");
elements.get("#crop-circle-chronology-relation").removeAttribute("data-analysis-unavailable");
layerApi.setChronology({ relation: "off" });
assert.equal(elements.get("#crop-circle-chronology-relation").disabled, false, "Map Explorer restores the available crop chronology selector");
assert.equal(elements.get("#crop-circle-chronology-disclosure").getAttribute("aria-disabled"), "false", "Map Explorer restores the crop chronology disclosure");
assert.equal(elements.get("#crop-circle-chronology-coordinate-scope").disabled, true, "crop chronology refinements remain disabled while its independent selector is off");
assert.equal(elements.get("#crop-circle-ufo-relation-window").disabled, true, "UFO-to-crop selection requires one specific crop record");
assert.equal(elements.get("#crop-circle-ufo-position-quality").disabled, true);
assert.equal(elements.get("#crop-circle-ufo-crop-position-quality").disabled, true);
for (const selector of [
  "#crop-circle-radius-km",
  "#crop-circle-analyze-ufo-traces",
  "#crop-circle-ufo-hop-depth",
  "#crop-circle-ufo-hop-direction",
  "#crop-circle-show-radius",
  "#crop-circle-highlight-intersections",
  "#crop-circle-focus-mode",
]) {
  assert.equal(elements.get(selector).disabled, true, `${selector} remains unavailable until one crop record is selected`);
}
assert.equal(cropTraceFocusCalls.length, 0, "no selected-radius bridge query runs before a record is selected");
assert.match(elements.get("#crop-circle-selected-summary").textContent, /Select one crop spiral/);
assert.match(elements.get("#crop-circle-chronology-status").textContent, /off/i);
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

const stackMarker = findPointLayer().getLayers().find((marker) =>
  marker.options.ccStackCount > 1 && marker.options.ccRecordIds.some((id) => Number(pointRowByIdFixture.get(String(id))?.[5]) === 0)
);
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
assert.equal(layerApi.getStatus().selectedRecordId, null, "a shared-position chooser is not itself treated as a selected record");
assert.equal(activeCropTraceFocus, null, "a stack chooser clears any selected-radius trace focus");
assert.equal(elements.get("#crop-circle-radius-km").disabled, true, "radius controls stay disabled until one record in the stack is chosen");
assert.match(elements.get("#crop-circle-selected-summary").textContent, /choose a specific record/i);

const chosenId = stackMarker.options.ccRecordIds.find((id) => Number(pointRowByIdFixture.get(String(id))?.[5]) === 0);
assert.ok(chosenId, "stack fixture includes an exact-day record for directed date-relation assertions");
await clickPanelTarget("[data-cc-record-id]", { ccRecordId: chosenId });
await new Promise((resolve) => setTimeout(resolve, 40));
assert.ok(requests.some((request) => /\/details\/chunk_\d{3}\.json\.gz$/.test(request)), "choosing a stacked record loads only its detail chunk");
assert.match(elements.get("#crop-circle-detail-body").innerHTML, /Measurement-informed schematic/);
assert.match(elements.get("#crop-circle-detail-body").innerHTML, /Catalog summary|Source description/);
status = layerApi.getStatus();
assert.equal(status.selectedRecordId, chosenId, "a specific stack record becomes the selected crop relation anchor");
assert.equal(elements.get("#crop-circle-ufo-relation-window").disabled, false);
assert.equal(elements.get("#crop-circle-ufo-position-quality").disabled, true, "date-relation coordinate quality remains disabled while UFO-to-crop relations are off");
assert.equal(elements.get("#crop-circle-ufo-crop-position-quality").disabled, true, "selected crop position quality remains disabled while UFO-to-crop relations are off");
for (const selector of [
  "#crop-circle-ufo-hop-depth",
  "#crop-circle-ufo-hop-direction",
  "#crop-circle-highlight-intersections",
  "#crop-circle-focus-mode",
]) {
  assert.equal(elements.get(selector).disabled, true, `${selector} waits for explicit trace analysis opt-in`);
}
assert.equal(elements.get("#crop-circle-radius-km").disabled, false, "radius display is available without building the trace network");
assert.equal(elements.get("#crop-circle-ufo-relation-disclosure").getAttribute("aria-disabled"), "false", "selecting one crop unlocks its UFO-date disclosure");
assert.equal(elements.get("#crop-circle-radius-disclosure").getAttribute("aria-disabled"), "false", "selecting one crop unlocks its radius-and-traces disclosure");
assert.equal(elements.get("#crop-circle-show-radius").disabled, false, "radius display is available without building the trace network");
assert.equal(elements.get("#crop-circle-analyze-ufo-traces").disabled, false, "specific record enables the explicit trace-analysis toggle");
assert.ok(cropTraceFocusCalls.length > 0, "selecting one record invokes the authoritative UFO trace bridge");
let focusConfig = cropTraceFocusCalls.at(-1);
assert.equal(focusConfig.crop.id, chosenId);
assert.deepEqual(focusConfig.ufoRelation, { window: "off", positionQuality: "source", cropPositionQuality: "field" });
assert.equal(focusConfig.radiusKm, 25);
assert.equal(focusConfig.traceAnalysisEnabled, false, "selecting a crop record does not automatically build the global UFO trace network");
assert.deepEqual(focusConfig.hops, { depth: 1, direction: "both" });
assert.equal(focusConfig.showRadius, true);
assert.equal(focusConfig.emphasizeIntersections, true);
assert.equal(focusConfig.isolation, false);
assert.match(elements.get("#crop-circle-selected-summary").textContent, /Selected:/);
assert.match(elements.get("#crop-circle-ufo-relation-status").textContent, /UFO-to-crop date links are off/);

elements.get("#crop-circle-ufo-relation-window").value = "after_1_7";
elements.get("#crop-circle-ufo-position-quality").value = "all";
elements.get("#crop-circle-ufo-crop-position-quality").value = "all";
elements.get("#crop-circle-radius-km").value = "100";
elements.get("#crop-circle-analyze-ufo-traces").checked = true;
elements.get("#crop-circle-ufo-hop-depth").value = "3";
elements.get("#crop-circle-ufo-hop-direction").value = "forward";
elements.get("#crop-circle-show-radius").checked = false;
elements.get("#crop-circle-highlight-intersections").checked = false;
elements.get("#crop-circle-focus-mode").checked = true;
await elements.get("#crop-circle-focus-mode").dispatch("change");
await flushAsyncWork();
status = layerApi.getStatus();
assert.equal(status.ufoFocus.relationWindow, "after_1_7");
assert.equal(status.ufoFocus.positionQuality, "all");
assert.equal(status.ufoFocus.cropPositionQuality, "all");
assert.equal(status.ufoFocus.radiusKm, 100);
assert.equal(status.ufoFocus.traceAnalysisEnabled, true);
assert.equal(status.ufoFocus.hopDepth, 3);
assert.equal(status.ufoFocus.hopDirection, "forward");
assert.equal(status.ufoFocus.showRadius, false);
assert.equal(status.ufoFocus.emphasizeIntersections, false);
assert.equal(status.ufoFocus.isolation, true);
focusConfig = cropTraceFocusCalls.at(-1);
assert.equal(focusConfig.ufoRelation.window, "after_1_7", "UFO-to-crop relation selection is passed independently to the bridge");
assert.equal(focusConfig.ufoRelation.positionQuality, "all");
assert.equal(focusConfig.ufoRelation.cropPositionQuality, "all");
assert.equal(focusConfig.radiusKm, 100);
assert.equal(focusConfig.traceAnalysisEnabled, true);
assert.deepEqual(focusConfig.hops, { depth: 3, direction: "forward" });
assert.equal(focusConfig.showRadius, false);
assert.equal(focusConfig.emphasizeIntersections, false);
assert.equal(focusConfig.isolation, true);
assert.equal(mapContainer.classList.contains("crop-circle-focus-active"), true, "focus configuration reaches the bridge isolation lifecycle");
assert.equal(status.chronology.relation, "off", "changing UFO-to-crop settings does not enable crop-to-crop progression");
assert.equal(elements.get("#crop-circle-ufo-position-quality").disabled, false, "position quality becomes available only for an active UFO-to-crop date relation");
assert.equal(elements.get("#crop-circle-ufo-crop-position-quality").disabled, false, "crop position quality becomes available only for an active UFO-to-crop date relation");
assert.equal(elements.get("#crop-circle-ufo-hop-depth").disabled, false, "hop controls enable only after explicit trace analysis opt-in");
assert.equal(elements.get("#crop-circle-focus-mode").disabled, false, "focus mode enables only after explicit trace analysis opt-in");
assert.match(elements.get("#crop-circle-ufo-relation-status").textContent, /3 UFO sightings match/);
assert.match(elements.get("#crop-circle-ufo-relation-status").textContent, /2 filtered UFO trace segments intersect/);

const focusCallsBeforeChronology = cropTraceFocusCalls.length;
elements.get("#crop-circle-ufo-relation-disclosure").open = true;
elements.get("#crop-circle-radius-disclosure").open = true;
elements.get("#crop-circle-chronology-coordinate-scope").value = "all";
elements.get("#crop-circle-chronology-max-distance").value = "1000";
elements.get("#crop-circle-chronology-relation").value = "same_day";
await elements.get("#crop-circle-chronology-relation").dispatch("change");
status = layerApi.getStatus();
assert.equal(status.chronology.enabled, true);
assert.equal(status.chronology.relation, "same_day");
assert.equal(status.chronology.coordinateScope, "all");
assert.equal(status.chronology.maxDistanceKm, 1000);
assert.equal(status.ufoFocus.relationWindow, "after_1_7", "the two relation selectors retain independent state");
assert.equal(cropTraceFocusCalls.length, focusCallsBeforeChronology, "crop-to-crop changes do not re-query the selected UFO trace bridge");
assert.equal(elements.get("#crop-circle-chronology-coordinate-scope").disabled, false);

const clearsBeforeStackReturn = cropTraceFocusClears.length;
await clickPanelTarget("[data-cc-stack-return]", {});
status = layerApi.getStatus();
assert.equal(status.selectedRecordId, null, "returning to a stacked-position chooser clears the selected relation anchor");
assert.equal(activeCropTraceFocus, null);
assert.equal(mapContainer.classList.contains("crop-circle-focus-active"), false, "stack chooser exits focus isolation through the bridge");
assert.ok(cropTraceFocusClears.length > clearsBeforeStackReturn);
assert.equal(elements.get("#crop-circle-ufo-relation-window").disabled, true);
assert.equal(elements.get("#crop-circle-radius-km").disabled, true);
assert.equal(elements.get("#crop-circle-ufo-relation-disclosure").open, false, "clearing the selected crop closes the dependent UFO-date disclosure");
assert.equal(elements.get("#crop-circle-radius-disclosure").open, false, "clearing the selected crop closes the dependent radius-and-traces disclosure");
assert.equal(elements.get("#crop-circle-ufo-relation-disclosure").getAttribute("aria-disabled"), "true");
assert.equal(elements.get("#crop-circle-radius-disclosure").getAttribute("aria-disabled"), "true");
assert.equal(status.chronology.relation, "same_day", "clearing the selected UFO focus does not disable crop-to-crop progression");

await layerApi.openRecord(chosenId);
await flushAsyncWork();
assert.equal(layerApi.getStatus().selectedRecordId, chosenId, "the chosen record can be restored after inspecting its stack");

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

elements.get("#crop-circle-chronology-relation").value = "off";
await elements.get("#crop-circle-chronology-relation").dispatch("change");
status = layerApi.getStatus();
assert.equal(status.chronology.enabled, false);
assert.equal(status.chronology.relation, "off");
assert.equal(status.chronology.renderedEdges, 0);
assert.equal(elements.get("#crop-circle-chronology-coordinate-scope").disabled, true);
assert.match(elements.get("#crop-circle-chronology-status").textContent, /off/i);
assert.equal(status.ufoFocus.relationWindow, "after_1_7", "turning crop progression off leaves UFO-to-crop settings unchanged");

mapZoom = 3;
elements.get("#crop-circle-chronology-relation").value = "7";
await elements.get("#crop-circle-chronology-relation").dispatch("change");
status = layerApi.getStatus();
assert.equal(status.chronology.enabled, true);
assert.equal(status.chronology.relation, "7");
assert.equal(status.chronology.coordinateScope, "all");
assert.equal(status.chronology.maxDistanceKm, 1000);
assert.ok(status.chronology.renderedEdges <= 120, "low-zoom viewport edge cap is enforced");
assert.equal(status.chronology.capped, status.chronology.candidateEdges > 120);
assert.ok(findChronologyLayer().getLayers().some((line) => line.options.dashArray === "8 7"), "1–7 day later crop links use a visibly different dashed acid-lime treatment");
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

assert.equal(layerApi.resetControls(), true, "legend reset can clear crop analysis without disabling the default-on markers");
status = layerApi.getStatus();
assert.equal(status.enabled, true);
assert.equal(status.selectedRecordId, null);
assert.equal(status.chronology.relation, "off");
assert.equal(status.ufoFocus.relationWindow, "off");
assert.equal(status.ufoFocus.traceAnalysisEnabled, false);
assert.equal(status.ufoFocus.radiusKm, 25);
assert.equal(status.ufoFocus.hopDepth, 1);
assert.equal(status.ufoFocus.hopDirection, "both");
assert.equal(status.ufoFocus.isolation, false);
assert.equal(elements.get("#crop-circle-detail-panel").hidden, true);
assert.equal(mapContainer.classList.contains("crop-circle-focus-active"), false);

const disableRacePath = detailPathForRow(raceRows[2]);
delayedDetailPaths.add(disableRacePath);
const pendingAtDisable = layerApi.openRecord(raceRows[2][0]);
await new Promise((resolve) => setTimeout(resolve, 5));
const focusClearsBeforeDisable = cropTraceFocusClears.length;
await layerApi.setEnabled(false);
assert.equal(await pendingAtDisable, false, "disable invalidates pending detail responses");
delayedDetailPaths.delete(disableRacePath);
status = layerApi.getStatus();
assert.equal(status.enabled, false);
assert.equal(status.selectedRecordId, null);
assert.equal(activeCropTraceFocus, null, "disable clears the authoritative selected-radius trace focus");
assert.equal(mapContainer.classList.contains("crop-circle-focus-active"), false, "disable cannot leave focus-isolation styling behind");
assert.ok(cropTraceFocusClears.length > focusClearsBeforeDisable, "disable executes the bridge cleanup lifecycle even during a detail-load race");
assert.equal(status.chronology.enabled, false);
assert.equal(status.chronology.relation, "off");
assert.equal(status.chronology.renderedEdges, 0);
assert.equal(status.chronology.eligibleNodes, 0);
assert.equal(status.chronology.candidateEdges, 0);
assert.equal(status.renderedCount, 0);
assert.equal(status.renderedPositionCount, 0);
assert.equal(mapLayers.size, 0, "disable removes both crop markers and crop chronology");
assert.equal(elements.get("#crop-circle-detail-panel").hidden, true, "stale detail response cannot reopen the panel after disable");
assert.equal(elements.get("#crop-circle-chronology-controls").hidden, true);
assert.equal(elements.get("#crop-circle-ufo-relation-window").disabled, true);
assert.equal(elements.get("#crop-circle-radius-km").disabled, true);
assert.equal(elements.get("#crop-circle-focus-mode").disabled, true);
assert.equal((mapHandlers.get("moveend") || new Set()).size, 0, "viewport listener is removed on disable");
assert.equal((mapHandlers.get("zoomend") || new Set()).size, 0, "zoom listener is removed on disable");
assert.equal(mapContainerListeners.size, 0, "bounded crop click capture listener is removed on disable");
assert.ok(requestCaches.slice(1).every((mode) => mode === "force-cache"), "all immutable point/detail payload requests remain force-cache");

await testBootstrapRetry();
await testBootstrapPreReadyOptOut();

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

function flushAsyncWork() {
  return new Promise((resolve) => setTimeout(resolve, 0));
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
  const forwardedFocusConfigs = [];
  const forwardedFocusClears = [];
  const readyHandlers = [];
  const retryWindow = {
    L: { map() { return map; } },
    setTimeout,
    clearTimeout,
    addEventListener(name, handler) {
      if (name === "ufo:timeline-ready") readyHandlers.push(handler);
    },
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
  assert.ok(retryWindow.UfoTimelineExtensions, "bootstrap exposes the narrow crop extension bridge before lazy runtime loading");
  assert.equal(retryWindow.UfoTimelineExtensions.registerCoreApi({
    getContext() { return { map }; },
    setCropTraceFocus(config) {
      forwardedFocusConfigs.push(config);
      return { radiusKm: config.radiusKm };
    },
    clearCropTraceFocus(reason) {
      forwardedFocusClears.push(reason);
      return true;
    },
  }), true);
  assert.deepEqual(
    await retryWindow.UfoTimelineExtensions.setCropTraceFocus({ radiusKm: 50, hops: { depth: 2 } }),
    { radiusKm: 50 },
    "bootstrap forwards selected-radius configuration to the registered authoritative trace runtime",
  );
  assert.equal(forwardedFocusConfigs.length, 1);
  assert.equal(retryWindow.UfoTimelineExtensions.clearCropTraceFocus("test cleanup"), true);
  assert.deepEqual(forwardedFocusClears, ["test cleanup"]);
  assert.equal(retryButton.getAttribute("aria-pressed"), "true", "bootstrap exposes the intended default-on state immediately");
  assert.equal(appendCount, 0, "bootstrap makes no crop request or runtime injection before the core Ready boundary");
  assert.equal(readyHandlers.length, 1);
  readyHandlers[0]();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(appendCount, 1, "Ready starts the first default activation attempt");
  assert.equal(retryButton.getAttribute("aria-pressed"), "false", "a failed default activation is exposed as off and retryable");
  readyHandlers[0]();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(appendCount, 1, "repeated Ready events are idempotent");
  await retryButton.dispatch("click");
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(appendCount, 2, "transient runtime load failure can be retried without reloading the app");
  assert.match(lastScriptSrc, /crop_circle_layer\.js\?v=2026-08-10-control-panel-polish-v1$/);
  assert.equal(enables, 1);
}

async function testBootstrapPreReadyOptOut() {
  const optOutButton = new MockElement();
  const readyHandlers = [];
  let appendCount = 0;
  const optOutWindow = {
    L: { map() { return map; } },
    setTimeout,
    clearTimeout,
    addEventListener(name, handler) {
      if (name === "ufo:timeline-ready") readyHandlers.push(handler);
    },
  };
  const optOutDocument = {
    querySelector(selector) { return selector === "#overlay-crop-circles" ? optOutButton : null; },
    createElement() { return {}; },
    head: { appendChild() { appendCount += 1; } },
  };
  vm.runInContext(
    await fs.readFile(path.join(staticRoot, "crop_circle_bootstrap.js"), "utf8"),
    vm.createContext({
      window: optOutWindow,
      document: optOutDocument,
      URL,
      console: { error() {} },
      setTimeout,
      clearTimeout,
    }),
    { filename: "crop_circle_bootstrap.js" },
  );
  assert.equal(optOutButton.getAttribute("aria-pressed"), "true");
  await optOutButton.dispatch("click");
  assert.equal(optOutButton.getAttribute("aria-pressed"), "false");
  readyHandlers[0]();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(appendCount, 0, "a pre-Ready user opt-out prevents default crop runtime injection");
}
