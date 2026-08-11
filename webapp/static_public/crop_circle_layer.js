(function () {
  "use strict";

  const MANIFEST_URL = "./data/crop_circles/manifest.json";
  const POLL_INTERVAL_MS = 250;
  const MAX_DETAIL_CHUNKS = 5;
  const CROP_CHARCOAL = "#17191b";
  const CROP_IVORY = "#fff8df";
  const CROP_LIME = "#d8ff3e";
  const MIN_EDGE_KM = 0.001;
  const ROW = Object.freeze({
    id: 0,
    lat: 1,
    lon: 2,
    start: 3,
    end: 4,
    datePrecision: 5,
    coordinate: 6,
    morphology: 7,
    chunk: 8,
  });

  const state = {
    enabled: false,
    loading: false,
    enableGeneration: 0,
    manifest: null,
    points: null,
    map: null,
    renderer: null,
    layer: null,
    markerByPosition: new Map(),
    markerById: new Map(),
    rowById: new Map(),
    rowsByPosition: new Map(),
    detailChunkCache: new Map(),
    visibleRecords: null,
    visiblePositions: null,
    activeDetail: null,
    activeRow: null,
    activePositionRows: null,
    detailRequestGeneration: 0,
    activeDiagramIndex: 0,
    lastViewKey: "",
    lastFilterGeneration: null,
    lastTraceContextKey: "",
    pollTimer: null,
    mapHandlersInstalled: false,
    markerHitContainer: null,
    markerHitHandler: null,
    chronology: {
      enabled: false,
      relation: "off",
      coordinateScope: "field",
      maxDistanceKm: 250,
      renderer: null,
      layer: null,
      graphKey: "",
      graphEdges: [],
      renderedEdges: 0,
      eligibleNodes: 0,
      candidateEdges: 0,
      capped: false,
    },
    ufoFocus: {
      relationWindow: "off",
      positionQuality: "source",
      cropPositionQuality: "field",
      radiusKm: 25,
      traceAnalysisEnabled: false,
      hopDepth: 1,
      hopDirection: "both",
      showRadius: true,
      emphasizeIntersections: true,
      isolation: false,
      requestGeneration: 0,
      lastResult: null,
    },
  };

  const button = document.querySelector("#overlay-crop-circles");
  const status = document.querySelector("#crop-circle-status");
  const panel = document.querySelector("#crop-circle-detail-panel");
  const panelBody = document.querySelector("#crop-circle-detail-body");
  const panelClose = document.querySelector("#crop-circle-detail-close");
  const chronologyPanel = document.querySelector("#crop-circle-chronology-controls");
  const chronologyRelation = document.querySelector("#crop-circle-chronology-relation");
  const chronologyScope = document.querySelector("#crop-circle-chronology-coordinate-scope");
  const chronologyDistance = document.querySelector("#crop-circle-chronology-max-distance");
  const chronologyStatus = document.querySelector("#crop-circle-chronology-status");
  const selectedSummary = document.querySelector("#crop-circle-selected-summary");
  const ufoRelationDisclosure = document.querySelector("#crop-circle-ufo-relation-disclosure");
  const chronologyDisclosure = document.querySelector("#crop-circle-chronology-disclosure");
  const radiusDisclosure = document.querySelector("#crop-circle-radius-disclosure");
  const ufoRelationWindow = document.querySelector("#crop-circle-ufo-relation-window");
  const ufoPositionQuality = document.querySelector("#crop-circle-ufo-position-quality");
  const ufoCropPositionQuality = document.querySelector("#crop-circle-ufo-crop-position-quality");
  const radiusSelect = document.querySelector("#crop-circle-radius-km");
  const traceAnalysisToggle = document.querySelector("#crop-circle-analyze-ufo-traces");
  const hopDepthSelect = document.querySelector("#crop-circle-ufo-hop-depth");
  const hopDirectionSelect = document.querySelector("#crop-circle-ufo-hop-direction");
  const showRadiusToggle = document.querySelector("#crop-circle-show-radius");
  const emphasizeIntersectionsToggle = document.querySelector("#crop-circle-highlight-intersections");
  const focusModeToggle = document.querySelector("#crop-circle-focus-mode");
  const ufoRelationStatus = document.querySelector("#crop-circle-ufo-relation-status");

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function safeHttpUrl(value) {
    try {
      const raw = String(value || "").trim();
      if (!raw) return "";
      const url = new URL(raw, document.baseURI);
      return url.protocol === "https:" || url.protocol === "http:" ? url.href : "";
    } catch (error) {
      return "";
    }
  }

  function setStatus(message, isError) {
    if (!status) return;
    status.textContent = message || "";
    status.classList.toggle("is-error", Boolean(isError));
  }

  function setButtonState(enabled, busy) {
    if (!button) return;
    button.setAttribute("aria-pressed", enabled ? "true" : "false");
    button.classList.toggle("is-active", enabled);
    button.disabled = Boolean(busy);
    if (busy) button.setAttribute("aria-busy", "true");
    else button.removeAttribute("aria-busy");
    dispatchLayerState({ enabled: Boolean(enabled), busy: Boolean(busy) });
  }

  function dispatchLayerState(detail) {
    if (!window || typeof window.dispatchEvent !== "function" || typeof window.CustomEvent !== "function") return;
    window.dispatchEvent(new window.CustomEvent("ufo:crop-circle-statechange", {
      detail: Object.assign({
        enabled: state.enabled,
        visibleRecords: state.visibleRecords,
        visiblePositions: state.visiblePositions,
        totalRecords: state.manifest && state.manifest.counts ? Number(state.manifest.counts.events) : null,
      }, detail || {}),
    }));
  }

  async function readJson(url, compressed, cacheMode) {
    const response = await fetch(url, { cache: cacheMode || "force-cache" });
    if (!response.ok) {
      throw new Error("Crop-circle data request failed (" + response.status + ").");
    }
    if (!compressed) return response.json();
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes.length > 1 && bytes[0] === 0x1f && bytes[1] === 0x8b) {
      if (typeof DecompressionStream !== "function") {
        throw new Error("This browser cannot decode the compact crop-circle data.");
      }
      const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
      return new Response(stream).json();
    }
    return JSON.parse(new TextDecoder("utf-8").decode(bytes));
  }

  function assetBaseUrl() {
    if (state.manifest && state.manifest.assetBaseUrl) {
      return new URL(state.manifest.assetBaseUrl, document.baseURI);
    }
    return new URL("./data/crop_circles/", document.baseURI);
  }

  function localAssetBaseUrl() {
    return new URL("./data/crop_circles/", document.baseURI);
  }

  function assetCandidates(pathValue) {
    const path = String(pathValue || "");
    const localPath = path.replace(/\.json\.gz$/i, ".json");
    const candidates = [new URL(localPath, localAssetBaseUrl())];
    const remote = new URL(path, assetBaseUrl());
    if (remote.toString() !== candidates[0].toString()) candidates.push(remote);
    return candidates;
  }

  async function readAssetJson(pathValue) {
    let lastError = null;
    for (const url of assetCandidates(pathValue)) {
      try {
        return await readJson(url, /\.gz(?:\?|$)/i.test(url.toString()));
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError || new Error("Crop-circle data is unavailable.");
  }

  async function ensureData() {
    if (state.manifest && state.points) return;
    const manifest = await readJson(new URL(MANIFEST_URL, document.baseURI), false, "no-cache");
    if (!manifest || manifest.schemaVersion !== 1 || !manifest.points) {
      throw new Error("Crop-circle manifest is incompatible with this app release.");
    }
    state.manifest = manifest;
    const points = await readAssetJson(manifest.points.path);
    if (!Array.isArray(points) || points.length !== Number(manifest.counts.mapped)) {
      throw new Error("Crop-circle point index failed its record-count check.");
    }
    state.points = points;
    state.rowById.clear();
    state.rowsByPosition.clear();
    for (const row of points) {
      state.rowById.set(String(row[ROW.id]), row);
      const key = positionKey(row);
      if (!state.rowsByPosition.has(key)) state.rowsByPosition.set(key, []);
      state.rowsByPosition.get(key).push(row);
    }
    for (const rows of state.rowsByPosition.values()) rows.sort(compareRowsByDate);
  }

  function extensionContext() {
    const bridge = window.UfoTimelineExtensions;
    return bridge && typeof bridge.getContext === "function" ? bridge.getContext() : null;
  }

  function waitForMap() {
    return new Promise(function (resolve, reject) {
      const started = Date.now();
      function poll() {
        const context = extensionContext();
        if (context && context.map) {
          resolve(context);
          return;
        }
        if (Date.now() - started > 15000) {
          reject(new Error("The map was not ready for the crop-circle layer."));
          return;
        }
        window.setTimeout(poll, 60);
      }
      poll();
    });
  }

  function ensureMapLayer(context) {
    if (state.map === context.map && state.layer) return;
    state.map = context.map;
    if (!state.map.getPane("cropCirclePane")) {
      state.map.createPane("cropCirclePane");
      const pane = state.map.getPane("cropCirclePane");
      pane.style.zIndex = "610";
      pane.style.pointerEvents = "none";
    }
    installSpiralRenderer();
    state.renderer = window.L.canvas({ pane: "cropCirclePane", padding: 0.25, tolerance: 8 });
    state.layer = window.L.layerGroup();
    if (!state.map.getPane("cropCircleChronologyPane")) {
      state.map.createPane("cropCircleChronologyPane");
      const pane = state.map.getPane("cropCircleChronologyPane");
      pane.style.zIndex = "480";
      pane.style.pointerEvents = "none";
    }
    state.chronology.renderer = window.L.canvas({ pane: "cropCircleChronologyPane", padding: 0.5, tolerance: 0 });
    state.chronology.layer = window.L.layerGroup();
  }

  function viewKey(context) {
    return [
      context.timeRangeStartOrdinal,
      context.timeRangeEndOrdinal,
      context.hideLowPrecisionCoordinates ? 1 : 0,
      context.hideNonExactDates ? 1 : 0,
    ].join("|");
  }

  function pointMatches(row, context) {
    if (context.hideNonExactDates && row[ROW.datePrecision] !== 0) return false;
    if (context.hideLowPrecisionCoordinates && row[ROW.coordinate] !== 0) return false;
    const start = Number(row[ROW.start]);
    const end = Number(row[ROW.end]);
    if (Number.isFinite(context.timeRangeStartOrdinal) && end < context.timeRangeStartOrdinal) return false;
    if (Number.isFinite(context.timeRangeEndOrdinal) && start > context.timeRangeEndOrdinal) return false;
    return true;
  }

  function positionKey(row) {
    return String(row[ROW.lat]) + "|" + String(row[ROW.lon]);
  }

  function compareRowsByDate(left, right) {
    return Number(left[ROW.start]) - Number(right[ROW.start]) ||
      Number(left[ROW.end]) - Number(right[ROW.end]) ||
      String(left[ROW.id]).localeCompare(String(right[ROW.id]));
  }

  function markerStyle(rows) {
    const coordinate = rows.reduce(function (leastPrecise, row) {
      return Math.max(leastPrecise, Number(row[ROW.coordinate]) || 0);
    }, 0);
    return {
      color: CROP_CHARCOAL,
      fillColor: CROP_IVORY,
      fillOpacity: 0,
      weight: 2.2,
      radius: rows.length > 1 ? 9.4 : 8.3,
      dashArray: coordinate === 1 ? "3 2" : coordinate === 2 ? "1 3" : null,
      ccAccentColor: CROP_LIME,
      ccOutlineColor: CROP_CHARCOAL,
      ccIvoryColor: CROP_IVORY,
      ccCoordinateCode: coordinate,
      ccStackCount: rows.length,
      ccMarkerKind: "crop-circle-spiral",
    };
  }

  function installSpiralRenderer() {
    if (!window.L || !window.L.Canvas || typeof window.L.Canvas.include !== "function" || window.L.Canvas.prototype._cropCircleSpiralInstalled) return;
    window.L.Canvas.include({
      _cropCircleSpiralInstalled: true,
      _updateCropCircleSpiral: function (layer) {
        if (!this._drawing || (typeof layer._empty === "function" && layer._empty())) return;
        const point = layer._point;
        const radius = Math.max(7.5, Number(layer._radius) || Number(layer.options.radius) || 8.3);
        const options = layer.options;
        const context = this._ctx;
        const coordinate = Number(options.ccCoordinateCode) || 0;
        context.save();
        context.globalAlpha = 1;
        context.translate(point.x, point.y);
        context.lineCap = "round";
        context.lineJoin = "round";

        context.beginPath();
        context.arc(0, 0, radius, 0, Math.PI * 2);
        context.setLineDash(coordinate === 1 ? [3, 2] : coordinate === 2 ? [1, 3] : []);
        context.strokeStyle = options.ccOutlineColor || CROP_CHARCOAL;
        context.lineWidth = 4.6;
        context.stroke();
        context.strokeStyle = options.ccIvoryColor || CROP_IVORY;
        context.lineWidth = 2;
        context.stroke();
        context.setLineDash([]);

        function spiral(strokeStyle, lineWidth) {
          context.beginPath();
          for (let step = 0; step <= 34; step += 1) {
            const angle = -Math.PI / 2 + step * 0.31;
            const spiralRadius = 0.35 + (radius - 2.2) * (step / 34);
            const x = Math.cos(angle) * spiralRadius;
            const y = Math.sin(angle) * spiralRadius;
            if (step === 0) context.moveTo(x, y);
            else context.lineTo(x, y);
          }
          context.strokeStyle = strokeStyle;
          context.lineWidth = lineWidth;
          context.stroke();
        }
        spiral(options.ccOutlineColor || CROP_CHARCOAL, 4.2);
        spiral(options.ccAccentColor || CROP_LIME, 1.9);

        if (coordinate === 0) {
          context.beginPath();
          context.arc(0, 0, 1.8, 0, Math.PI * 2);
          context.fillStyle = options.ccAccentColor || CROP_LIME;
          context.fill();
        }
        const tickCount = Math.min(6, Math.max(0, Number(options.ccStackCount) - 1));
        for (let index = 0; index < tickCount; index += 1) {
          const angle = -Math.PI / 2 + (Math.PI * 2 * index) / Math.max(1, tickCount);
          const x = Math.cos(angle) * (radius + 2.2);
          const y = Math.sin(angle) * (radius + 2.2);
          context.beginPath();
          context.arc(x, y, 1.25, 0, Math.PI * 2);
          context.fillStyle = options.ccOutlineColor || CROP_CHARCOAL;
          context.fill();
          context.beginPath();
          context.arc(x, y, 0.65, 0, Math.PI * 2);
          context.fillStyle = options.ccAccentColor || CROP_LIME;
          context.fill();
        }
        context.restore();
      },
    });
  }

  function markerForPosition(key, rows) {
    let marker = state.markerByPosition.get(key);
    const style = markerStyle(rows);
    if (!marker) {
      const representative = rows[0];
      marker = window.L.circleMarker([representative[ROW.lat], representative[ROW.lon]], Object.assign({
        pane: "cropCirclePane",
        renderer: state.renderer,
        interactive: false,
        bubblingMouseEvents: false,
        keyboard: false,
      }, style));
      const originalUpdatePath = marker._updatePath;
      marker._updatePath = function () {
        if (this._renderer && typeof this._renderer._updateCropCircleSpiral === "function") {
          this._renderer._updateCropCircleSpiral(this);
        } else if (typeof originalUpdatePath === "function") {
          originalUpdatePath.call(this);
        }
      };
      state.markerByPosition.set(key, marker);
    } else {
      marker.setStyle(style);
      marker.setRadius(style.radius);
    }
    marker._cropCircleRows = rows.slice().sort(compareRowsByDate);
    marker.options.ccRecordIds = marker._cropCircleRows.map(function (row) { return String(row[ROW.id]); });
    for (const row of rows) state.markerById.set(String(row[ROW.id]), marker);
    return marker;
  }

  function renderPoints(force) {
    if (!state.enabled || !state.points || !state.layer || !state.map) return;
    const context = extensionContext();
    if (!context || context.map !== state.map) return;
    const key = viewKey(context);
    if (!force && key === state.lastViewKey) return;
    state.lastViewKey = key;
    state.layer.clearLayers();
    let visibleRecords = 0;
    const positions = new Map();
    for (const row of state.points) {
      if (!pointMatches(row, context)) continue;
      const position = positionKey(row);
      if (!positions.has(position)) positions.set(position, []);
      positions.get(position).push(row);
      visibleRecords += 1;
    }
    if (state.activeRow && !pointMatches(state.activeRow, context)) {
      closePanel();
    }
    state.markerById.clear();
    for (const [key, rows] of positions) state.layer.addLayer(markerForPosition(key, rows));
    if (!state.map.hasLayer(state.layer)) state.layer.addTo(state.map);
    disableCropCanvasPointerEvents();
    const exactNote = context.hideLowPrecisionCoordinates
      ? " Exact-coordinate filtering is active."
      : " Solid center = exact field; dashed ring = candidate field; dotted ring = locality centroid.";
    const sourceDescriptionCount = Number(state.manifest.counts.recordsWithSourceDescriptions);
    state.visibleRecords = visibleRecords;
    state.visiblePositions = positions.size;
    const descriptionNote = Number.isFinite(sourceDescriptionCount)
      ? " Source narratives captured for " + sourceDescriptionCount.toLocaleString() + " of " + state.manifest.counts.events.toLocaleString() + " records."
      : "";
    setStatus(
      visibleRecords.toLocaleString() + " records at " + positions.size.toLocaleString() + " mapped positions visible (" +
      state.manifest.counts.events.toLocaleString() + " records total)." + exactNote + descriptionNote
    );
    dispatchLayerState({
      enabled: true,
      visibleRecords: visibleRecords,
      visiblePositions: positions.size,
    });
    renderChronology(false);
  }

  function setChronologyStatus(message, isError) {
    if (!chronologyStatus) return;
    chronologyStatus.textContent = message || "";
    chronologyStatus.classList.toggle("is-error", Boolean(isError));
  }

  function setRelationDisclosureAvailability(disclosure, available) {
    if (!disclosure) return;
    const enabled = Boolean(available);
    disclosure.setAttribute("aria-disabled", enabled ? "false" : "true");
    disclosure.classList.toggle("is-unavailable", !enabled);
    if (!enabled) disclosure.open = false;
    const summary = typeof disclosure.querySelector === "function"
      ? disclosure.querySelector("summary")
      : null;
    if (!summary) return;
    if (enabled) summary.removeAttribute("tabindex");
    else summary.setAttribute("tabindex", "-1");
  }

  function syncChronologyControlState() {
    if (chronologyPanel) chronologyPanel.hidden = !state.enabled;
    const on = state.enabled && state.chronology.enabled;
    if (chronologyRelation) {
      chronologyRelation.disabled = !state.enabled
        || chronologyRelation.getAttribute("data-analysis-unavailable") === "true";
    }
    for (const input of [chronologyScope, chronologyDistance]) if (input) input.disabled = !on;
    setRelationDisclosureAvailability(
      chronologyDisclosure,
      Boolean(chronologyRelation && !chronologyRelation.disabled)
    );
    if (chronologyRelation) chronologyRelation.value = state.chronology.relation;
    if (chronologyScope) chronologyScope.value = state.chronology.coordinateScope;
    if (chronologyDistance) chronologyDistance.value = String(state.chronology.maxDistanceKm);
    syncUfoFocusControlState();
  }

  function readChronologyControls() {
    const relation = chronologyRelation ? chronologyRelation.value : state.chronology.relation;
    state.chronology.relation = ["off", "same_day", "7", "30"].includes(relation) ? relation : "off";
    state.chronology.enabled = Boolean(state.enabled && state.chronology.relation !== "off");
    state.chronology.coordinateScope = chronologyScope && chronologyScope.value === "all" ? "all" : "field";
    const distance = Number(chronologyDistance && chronologyDistance.value);
    state.chronology.maxDistanceKm = [100, 250, 500, 1000].includes(distance) ? distance : 250;
    syncChronologyControlState();
  }

  function setUfoRelationStatus(message, isError) {
    if (!ufoRelationStatus) return;
    ufoRelationStatus.textContent = message || "";
    ufoRelationStatus.classList.toggle("is-error", Boolean(isError));
  }

  function selectedCropLabel() {
    if (!state.activeRow) return "";
    const detail = state.activeDetail || {};
    return String(detail.location || "Crop record " + String(state.activeRow[ROW.id])) + " · " + ordinalLabel(state.activeRow);
  }

  function syncUfoFocusControlState() {
    const selected = Boolean(state.enabled && state.activeRow);
    setRelationDisclosureAvailability(ufoRelationDisclosure, selected);
    setRelationDisclosureAvailability(radiusDisclosure, selected);
    if (selectedSummary) {
      selectedSummary.textContent = selected
        ? "Selected: " + selectedCropLabel()
        : "Select one crop spiral, then choose a specific record if that position contains a stack.";
    }
    if (ufoRelationWindow) {
      ufoRelationWindow.disabled = !selected;
      ufoRelationWindow.value = state.ufoFocus.relationWindow;
    }
    if (ufoPositionQuality) {
      ufoPositionQuality.disabled = !selected || state.ufoFocus.relationWindow === "off";
      ufoPositionQuality.value = state.ufoFocus.positionQuality;
    }
    if (ufoCropPositionQuality) {
      ufoCropPositionQuality.disabled = !selected || state.ufoFocus.relationWindow === "off";
      ufoCropPositionQuality.value = state.ufoFocus.cropPositionQuality;
    }
    if (radiusSelect) radiusSelect.value = String(state.ufoFocus.radiusKm);
    if (traceAnalysisToggle) {
      traceAnalysisToggle.checked = state.ufoFocus.traceAnalysisEnabled;
      traceAnalysisToggle.disabled = !selected;
    }
    if (hopDepthSelect) hopDepthSelect.value = String(state.ufoFocus.hopDepth);
    if (hopDirectionSelect) hopDirectionSelect.value = state.ufoFocus.hopDirection;
    if (showRadiusToggle) showRadiusToggle.checked = state.ufoFocus.showRadius;
    if (emphasizeIntersectionsToggle) emphasizeIntersectionsToggle.checked = state.ufoFocus.emphasizeIntersections;
    if (focusModeToggle) focusModeToggle.checked = state.ufoFocus.isolation;
    for (const input of [radiusSelect, showRadiusToggle]) {
      if (input) input.disabled = !selected;
    }
    for (const input of [hopDepthSelect, hopDirectionSelect, emphasizeIntersectionsToggle, focusModeToggle]) {
      if (input) input.disabled = !selected || !state.ufoFocus.traceAnalysisEnabled;
    }
  }

  function readUfoFocusControls() {
    const relation = ufoRelationWindow ? ufoRelationWindow.value : state.ufoFocus.relationWindow;
    state.ufoFocus.relationWindow = ["off", "same_day", "after_1_7", "after_1_30"].includes(relation) ? relation : "off";
    state.ufoFocus.positionQuality = ufoPositionQuality && ufoPositionQuality.value === "all" ? "all" : "source";
    state.ufoFocus.cropPositionQuality = ufoCropPositionQuality && ufoCropPositionQuality.value === "all" ? "all" : "field";
    const radius = Number(radiusSelect && radiusSelect.value);
    state.ufoFocus.radiusKm = [5, 10, 25, 50, 100, 250, 500].includes(radius) ? radius : 25;
    state.ufoFocus.traceAnalysisEnabled = Boolean(traceAnalysisToggle && traceAnalysisToggle.checked);
    const depth = Number(hopDepthSelect && hopDepthSelect.value);
    state.ufoFocus.hopDepth = [1, 2, 3, 4].includes(depth) ? depth : 1;
    const direction = hopDirectionSelect ? hopDirectionSelect.value : state.ufoFocus.hopDirection;
    state.ufoFocus.hopDirection = ["forward", "backward", "both"].includes(direction) ? direction : "both";
    state.ufoFocus.showRadius = Boolean(showRadiusToggle && showRadiusToggle.checked);
    state.ufoFocus.emphasizeIntersections = Boolean(emphasizeIntersectionsToggle && emphasizeIntersectionsToggle.checked);
    state.ufoFocus.isolation = Boolean(state.ufoFocus.traceAnalysisEnabled && focusModeToggle && focusModeToggle.checked);
    syncUfoFocusControlState();
  }

  function cropFocusConfig() {
    if (!state.activeRow) return null;
    const row = state.activeRow;
    const detail = state.activeDetail || {};
    return {
      crop: {
        id: String(row[ROW.id]),
        lat: Number(row[ROW.lat]),
        lon: Number(row[ROW.lon]),
        startOrdinal: Number(row[ROW.start]),
        endOrdinal: Number(row[ROW.end]),
        datePrecisionCode: Number(row[ROW.datePrecision]),
        coordinateCode: Number(row[ROW.coordinate]),
        country: detail.country || "",
        countryCode: detail.countryCode || detail.country_code || "",
        dateRole: detail.dateRole || detail.date_role || "catalog_unspecified",
        coordinateUncertaintyKm: detail.coordinateUncertaintyKm,
      },
      ufoRelation: {
        window: state.ufoFocus.relationWindow,
        positionQuality: state.ufoFocus.positionQuality,
        cropPositionQuality: state.ufoFocus.cropPositionQuality,
      },
      radiusKm: state.ufoFocus.radiusKm,
      traceAnalysisEnabled: state.ufoFocus.traceAnalysisEnabled,
      showRadius: state.ufoFocus.showRadius,
      emphasizeIntersections: state.ufoFocus.emphasizeIntersections,
      isolation: state.ufoFocus.isolation,
      hops: {
        depth: state.ufoFocus.hopDepth,
        direction: state.ufoFocus.hopDirection,
      },
    };
  }

  function clearUfoFocus(reason) {
    state.ufoFocus.requestGeneration += 1;
    state.ufoFocus.lastResult = null;
    const bridge = window.UfoTimelineExtensions;
    if (bridge && typeof bridge.clearCropTraceFocus === "function") bridge.clearCropTraceFocus(reason || "selection cleared");
  }

  async function refreshUfoFocus(reason) {
    const config = cropFocusConfig();
    if (!state.enabled || !config) {
      clearUfoFocus(reason || "no selected crop record");
      setUfoRelationStatus("Select a crop record to inspect nearby UFO relations and trace intersections.");
      return null;
    }
    const bridge = window.UfoTimelineExtensions;
    if (!bridge || typeof bridge.setCropTraceFocus !== "function") {
      setUfoRelationStatus("The UFO trace runtime is not ready yet.", true);
      return null;
    }
    const generation = ++state.ufoFocus.requestGeneration;
    setUfoRelationStatus("Calculating selected-radius UFO relations and filtered trace intersections…");
    try {
      const result = (await bridge.setCropTraceFocus(config)) || {};
      if (generation !== state.ufoFocus.requestGeneration || !state.activeRow) return null;
      state.ufoFocus.lastResult = result || {};
      const relationText = state.ufoFocus.relationWindow === "off"
        ? "UFO-to-crop date links are off."
        : !result.cropDateExact
          ? "This crop record has no exact catalog day, so no date links are inferred."
          : Number(result.relationEventCount || 0).toLocaleString() + " UFO sighting" + (Number(result.relationEventCount) === 1 ? "" : "s") + " match the selected date window and radius.";
      const ukText = result.excludedUkInference ? " UK crop records are excluded from relationship inference." : "";
      const capText = result.relationCapped ? " Relation display capped at 300; reduce the radius." : "";
      const uncertaintyText = result.radiusBelowCoordinateUncertainty
        ? " Warning: the selected radius is smaller than this record’s estimated " + Number(result.coordinateUncertaintyKm).toLocaleString() + " km coordinate uncertainty."
        : "";
      const cropPositionText = state.ufoFocus.relationWindow === "off"
        ? ""
        : result.cropPositionEligible
          ? (result.cropPositionIncludedByOverride ? " Locality-centroid crop position included by explicit selection." : "")
          : " UFO-to-crop date links require an exact or candidate field position unless locality centroids are explicitly included.";
      const traceText = result.traceAnalysisEnabled
        ? Number(result.intersectingTraceCount || 0).toLocaleString() +
          " filtered UFO trace segment" + (Number(result.intersectingTraceCount) === 1 ? " intersects" : "s intersect") +
          " the " + Number(result.radiusKm || state.ufoFocus.radiusKm).toLocaleString() + " km radius; " +
          Number(result.reachedTraceCount || 0).toLocaleString() + " trace segment" + (Number(result.reachedTraceCount) === 1 ? " is" : "s are") +
          " shown through hop " + Number(result.depth || state.ufoFocus.hopDepth) + "."
        : "UFO trace-radius analysis is off.";
      setUfoRelationStatus(
        relationText + " " + traceText + ukText + cropPositionText + capText + uncertaintyText
      );
      return result;
    } catch (error) {
      if (generation !== state.ufoFocus.requestGeneration) return null;
      setUfoRelationStatus(error && error.message ? error.message : String(error), true);
      return null;
    }
  }

  function clearChronologyLayer() {
    if (state.chronology.layer) state.chronology.layer.clearLayers();
    if (state.map && state.chronology.layer && state.map.hasLayer(state.chronology.layer)) {
      state.map.removeLayer(state.chronology.layer);
    }
    state.chronology.renderedEdges = 0;
    state.chronology.capped = false;
  }

  function installChronologyControls() {
    if (!chronologyPanel || chronologyPanel.dataset.cropCircleReady === "1") return;
    chronologyPanel.dataset.cropCircleReady = "1";
    function chronologyChange() {
      readChronologyControls();
      state.chronology.graphKey = "";
      if (!state.chronology.enabled) {
        clearChronologyLayer();
        setChronologyStatus("Crop-to-crop progression is off.");
        return;
      }
      renderChronology(true);
    }
    function ufoChange() {
      readUfoFocusControls();
      refreshUfoFocus("controls changed");
    }
    for (const input of [chronologyRelation, chronologyScope, chronologyDistance]) {
      if (input) input.addEventListener("change", chronologyChange);
    }
    for (const input of [ufoRelationWindow, ufoPositionQuality, ufoCropPositionQuality, radiusSelect, traceAnalysisToggle, hopDepthSelect, hopDirectionSelect, showRadiusToggle, emphasizeIntersectionsToggle, focusModeToggle]) {
      if (input) input.addEventListener("change", ufoChange);
    }
    for (const disclosure of [ufoRelationDisclosure, chronologyDisclosure, radiusDisclosure]) {
      if (!disclosure) continue;
      disclosure.addEventListener("toggle", function () {
        if (disclosure.getAttribute("aria-disabled") === "true" && disclosure.open) {
          disclosure.open = false;
        }
      });
    }
    syncChronologyControlState();
  }

  function installMapHandlers() {
    if (!state.map || state.mapHandlersInstalled || typeof state.map.on !== "function") return;
    state.map.on("moveend", renderChronologyViewport);
    state.map.on("zoomend", renderChronologyViewport);
    state.mapHandlersInstalled = true;
  }

  function disableCropCanvasPointerEvents() {
    const pane = state.map && state.map.getPane("cropCirclePane");
    if (pane && pane.style) pane.style.pointerEvents = "none";
    const container = state.renderer && state.renderer._container;
    if (container && container.style) container.style.pointerEvents = "none";
  }

  function markerAtContainerPoint(point) {
    if (!point || !state.layer || typeof state.layer.getLayers !== "function" || !state.map || typeof state.map.latLngToContainerPoint !== "function") return null;
    let best = null;
    let bestDistanceSquared = Infinity;
    for (const marker of state.layer.getLayers()) {
      const markerPoint = state.map.latLngToContainerPoint(marker.getLatLng());
      const deltaX = Number(markerPoint.x) - Number(point.x);
      const deltaY = Number(markerPoint.y) - Number(point.y);
      const distanceSquared = deltaX * deltaX + deltaY * deltaY;
      const hitRadius = Number(marker.options.radius || 8.3) + 6;
      if (distanceSquared > hitRadius * hitRadius || distanceSquared >= bestDistanceSquared) continue;
      best = marker;
      bestDistanceSquared = distanceSquared;
    }
    return best;
  }

  function installMarkerHitHandler() {
    removeMarkerHitHandler();
    if (!state.map || typeof state.map.getContainer !== "function" || typeof state.map.mouseEventToContainerPoint !== "function") return;
    const container = state.map.getContainer();
    if (!container || typeof container.addEventListener !== "function") return;
    state.markerHitContainer = container;
    state.markerHitHandler = function (event) {
      if (!state.enabled || !state.layer || !state.map.hasLayer(state.layer)) return;
      const target = event.target;
      if (target && typeof target.closest === "function" && target.closest("#area-selection-draw-surface, .leaflet-control, .crop-circle-detail-panel, button, input, select, a")) return;
      const marker = markerAtContainerPoint(state.map.mouseEventToContainerPoint(event));
      if (!marker) return;
      if (typeof event.preventDefault === "function") event.preventDefault();
      if (typeof event.stopImmediatePropagation === "function") event.stopImmediatePropagation();
      else if (typeof event.stopPropagation === "function") event.stopPropagation();
      openPosition(marker._cropCircleRows || []).catch(function (error) {
        showPanelError(error);
        console.error(error);
      });
    };
    container.addEventListener("click", state.markerHitHandler, true);
  }

  function removeMarkerHitHandler() {
    if (state.markerHitContainer && state.markerHitHandler && typeof state.markerHitContainer.removeEventListener === "function") {
      state.markerHitContainer.removeEventListener("click", state.markerHitHandler, true);
    }
    state.markerHitContainer = null;
    state.markerHitHandler = null;
  }

  function removeMapHandlers() {
    if (!state.map || !state.mapHandlersInstalled || typeof state.map.off !== "function") return;
    state.map.off("moveend", renderChronologyViewport);
    state.map.off("zoomend", renderChronologyViewport);
    state.mapHandlersInstalled = false;
  }

  function haversineKm(left, right) {
    const radians = Math.PI / 180;
    const lat1 = Number(left.lat) * radians;
    const lat2 = Number(right.lat) * radians;
    const dLat = (Number(right.lat) - Number(left.lat)) * radians;
    const dLon = (Number(right.lng) - Number(left.lng)) * radians;
    const sinLat = Math.sin(dLat / 2);
    const sinLon = Math.sin(dLon / 2);
    const a = sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLon * sinLon;
    return 6371.0088 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
  }

  function chronologyNodes(context) {
    const nodes = new Map();
    for (const row of state.points || []) {
      if (!pointMatches(row, context) || Number(row[ROW.datePrecision]) !== 0) continue;
      if (state.chronology.coordinateScope === "field" && Number(row[ROW.coordinate]) > 1) continue;
      const day = Number(row[ROW.start]);
      if (!Number.isFinite(day)) continue;
      const position = positionKey(row);
      const key = String(day) + "|" + position;
      const candidate = {
        key,
        id: String(row[ROW.id]),
        day,
        position,
        lat: Number(row[ROW.lat]),
        lng: Number(row[ROW.lon]),
      };
      const existing = nodes.get(key);
      if (!existing || candidate.id < existing.id) nodes.set(key, candidate);
    }
    return Array.from(nodes.values()).sort(function (left, right) {
      return left.day - right.day || left.id.localeCompare(right.id) || left.position.localeCompare(right.position);
    });
  }

  function edgeKey(left, right, kind, dayGap) {
    if (kind === "same-day" && left.key > right.key) return edgeKey(right, left, kind, dayGap);
    return kind + "|" + left.key + "|" + right.key + "|" + String(dayGap || 0);
  }

  function sameDayForest(nodes, maxDistanceKm) {
    const byDay = new Map();
    for (const node of nodes) {
      if (!byDay.has(node.day)) byDay.set(node.day, []);
      byDay.get(node.day).push(node);
    }
    const result = [];
    for (const dayNodes of byDay.values()) {
      if (dayNodes.length < 2) continue;
      const candidates = [];
      for (let leftIndex = 0; leftIndex < dayNodes.length; leftIndex += 1) {
        for (let rightIndex = leftIndex + 1; rightIndex < dayNodes.length; rightIndex += 1) {
          const left = dayNodes[leftIndex];
          const right = dayNodes[rightIndex];
          const distanceKm = haversineKm(left, right);
          if (distanceKm <= MIN_EDGE_KM || distanceKm > maxDistanceKm) continue;
          candidates.push({ left, right, distanceKm, dayGap: 0, kind: "same-day" });
        }
      }
      candidates.sort(function (left, right) {
        return left.distanceKm - right.distanceKm || left.left.id.localeCompare(right.left.id) || left.right.id.localeCompare(right.right.id);
      });
      const parent = new Map(dayNodes.map(function (node) { return [node.key, node.key]; }));
      function root(key) {
        let value = key;
        while (parent.get(value) !== value) value = parent.get(value);
        let current = key;
        while (parent.get(current) !== current) {
          const next = parent.get(current);
          parent.set(current, value);
          current = next;
        }
        return value;
      }
      for (const edge of candidates) {
        const leftRoot = root(edge.left.key);
        const rightRoot = root(edge.right.key);
        if (leftRoot === rightRoot) continue;
        parent.set(rightRoot, leftRoot);
        result.push(edge);
      }
    }
    return result;
  }

  function laterDateEdges(nodes, dayWindow, maxDistanceKm) {
    if (!dayWindow) return [];
    const byDay = new Map();
    for (const node of nodes) {
      if (!byDay.has(node.day)) byDay.set(node.day, []);
      byDay.get(node.day).push(node);
    }
    const days = Array.from(byDay.keys()).sort(function (left, right) { return left - right; });
    const result = [];
    const seen = new Set();
    for (let dayIndex = 0; dayIndex < days.length; dayIndex += 1) {
      const sourceDay = days[dayIndex];
      for (const source of byDay.get(sourceDay)) {
        let selected = null;
        for (let laterIndex = dayIndex + 1; laterIndex < days.length; laterIndex += 1) {
          const targetDay = days[laterIndex];
          const dayGap = targetDay - sourceDay;
          if (dayGap > dayWindow) break;
          let nearest = null;
          for (const target of byDay.get(targetDay)) {
            const distanceKm = haversineKm(source, target);
            if (distanceKm <= MIN_EDGE_KM || distanceKm > maxDistanceKm) continue;
            if (!nearest || distanceKm < nearest.distanceKm || (distanceKm === nearest.distanceKm && target.id < nearest.right.id)) {
              nearest = { left: source, right: target, distanceKm, dayGap, kind: "later" };
            }
          }
          if (nearest) {
            selected = nearest;
            break;
          }
        }
        if (!selected) continue;
        const key = edgeKey(selected.left, selected.right, selected.kind, selected.dayGap);
        if (!seen.has(key)) {
          seen.add(key);
          result.push(selected);
        }
      }
    }
    return result;
  }

  function buildChronologyGraph(context) {
    const nodes = chronologyNodes(context);
    const maxDistanceKm = state.chronology.maxDistanceKm;
    const windowDays = state.chronology.relation === "7" ? 7 : state.chronology.relation === "30" ? 30 : 0;
    const edges = state.chronology.relation === "same_day"
      ? sameDayForest(nodes, maxDistanceKm)
      : laterDateEdges(nodes, windowDays, maxDistanceKm);
    edges.sort(function (left, right) {
      return (left.kind === right.kind ? 0 : left.kind === "same-day" ? -1 : 1) ||
        left.left.day - right.left.day || left.dayGap - right.dayGap ||
        left.distanceKm - right.distanceKm || edgeKey(left.left, left.right, left.kind, left.dayGap).localeCompare(edgeKey(right.left, right.right, right.kind, right.dayGap));
    });
    state.chronology.eligibleNodes = nodes.length;
    state.chronology.candidateEdges = edges.length;
    state.chronology.graphEdges = edges;
  }

  function edgeInViewport(edge) {
    if (!state.map || typeof state.map.getBounds !== "function") return true;
    let bounds = state.map.getBounds();
    if (bounds && typeof bounds.pad === "function") bounds = bounds.pad(0.12);
    if (!bounds || typeof bounds.contains !== "function") return true;
    return bounds.contains([edge.left.lat, edge.left.lng]) || bounds.contains([edge.right.lat, edge.right.lng]);
  }

  function chronologyEdgeCap() {
    const zoom = state.map && typeof state.map.getZoom === "function" ? Number(state.map.getZoom()) : 8;
    if (zoom < 4) return 120;
    if (zoom < 7) return 260;
    if (zoom < 10) return 480;
    return 800;
  }

  function addChronologyStroke(latlngs, options) {
    if (!window.L || typeof window.L.polyline !== "function") return;
    state.chronology.layer.addLayer(window.L.polyline(latlngs, Object.assign({
      pane: "cropCircleChronologyPane",
      renderer: state.chronology.renderer,
      interactive: false,
      bubblingMouseEvents: false,
      smoothFactor: 1,
    }, options)));
  }

  function laterArrowLatLngs(edge) {
    if (!state.map || typeof state.map.latLngToLayerPoint !== "function" || typeof state.map.layerPointToLatLng !== "function") return null;
    const start = state.map.latLngToLayerPoint([edge.left.lat, edge.left.lng]);
    const end = state.map.latLngToLayerPoint([edge.right.lat, edge.right.lng]);
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const length = Math.sqrt(dx * dx + dy * dy);
    if (!Number.isFinite(length) || length < 18) return null;
    const unitX = dx / length;
    const unitY = dy / length;
    const tip = { x: start.x + dx * 0.78, y: start.y + dy * 0.78 };
    const back = { x: tip.x - unitX * 9, y: tip.y - unitY * 9 };
    const left = { x: back.x - unitY * 5, y: back.y + unitX * 5 };
    const right = { x: back.x + unitY * 5, y: back.y - unitX * 5 };
    return [state.map.layerPointToLatLng(left), state.map.layerPointToLatLng(tip), state.map.layerPointToLatLng(right)];
  }

  function drawChronologyEdge(edge) {
    const latlngs = [[edge.left.lat, edge.left.lng], [edge.right.lat, edge.right.lng]];
    const later = edge.kind === "later";
    const dashArray = later ? "8 7" : null;
    addChronologyStroke(latlngs, { color: CROP_CHARCOAL, opacity: 0.82, weight: later ? 5.2 : 4.8, dashArray });
    addChronologyStroke(latlngs, { color: later ? CROP_LIME : CROP_IVORY, opacity: 0.94, weight: later ? 2.1 : 1.9, dashArray });
    if (!later) return;
    const arrow = laterArrowLatLngs(edge);
    if (!arrow) return;
    addChronologyStroke(arrow, { color: CROP_CHARCOAL, opacity: 0.88, weight: 4.8 });
    addChronologyStroke(arrow, { color: CROP_LIME, opacity: 1, weight: 1.9 });
  }

  function renderChronologyViewport() {
    if (!state.enabled || !state.chronology.enabled || !state.chronology.layer || !state.map) return;
    state.chronology.layer.clearLayers();
    const visibleEdges = state.chronology.graphEdges.filter(edgeInViewport);
    const cap = chronologyEdgeCap();
    const sameDayEdges = visibleEdges.filter(function (edge) { return edge.kind === "same-day"; });
    const laterEdges = visibleEdges.filter(function (edge) { return edge.kind === "later"; });
    let selected;
    if (laterEdges.length && sameDayEdges.length && visibleEdges.length > cap) {
      const laterBudget = Math.min(laterEdges.length, Math.max(1, Math.floor(cap * 0.4)));
      const sameDayBudget = Math.min(sameDayEdges.length, cap - laterBudget);
      selected = sameDayEdges.slice(0, sameDayBudget).concat(laterEdges.slice(0, cap - sameDayBudget));
    } else {
      selected = visibleEdges.slice(0, cap);
    }
    for (const edge of selected) drawChronologyEdge(edge);
    if (!state.map.hasLayer(state.chronology.layer)) state.chronology.layer.addTo(state.map);
    state.chronology.renderedEdges = selected.length;
    state.chronology.capped = visibleEdges.length > cap;
    const sameDay = selected.filter(function (edge) { return edge.kind === "same-day"; }).length;
    const later = selected.length - sameDay;
    const scopeLabel = state.chronology.coordinateScope === "field" ? "exact + candidate fields" : "including locality centroids";
    const capNote = state.chronology.capped ? " View cap reached; zoom in to inspect more." : "";
    setChronologyStatus(
      selected.length.toLocaleString() + " catalog-date links shown (" + sameDay.toLocaleString() + " same-day" +
      (later ? ", " + later.toLocaleString() + " later-date" : "") + ") across " +
      state.chronology.eligibleNodes.toLocaleString() + " eligible dated positions, " + scopeLabel + "." + capNote
    );
  }

  function renderChronology(force) {
    if (!state.enabled || !state.chronology.enabled) {
      clearChronologyLayer();
      if (state.enabled) setChronologyStatus("Crop-to-crop progression is off.");
      return;
    }
    const context = extensionContext();
    if (!context || context.map !== state.map) return;
    const key = [viewKey(context), state.chronology.relation, state.chronology.coordinateScope, state.chronology.maxDistanceKm].join("|");
    if (force || key !== state.chronology.graphKey) {
      state.chronology.graphKey = key;
      buildChronologyGraph(context);
    }
    renderChronologyViewport();
  }

  function startPolling() {
    stopPolling();
    state.pollTimer = window.setInterval(function () {
      try {
        renderPoints(false);
        const context = extensionContext();
        const generation = context && Number.isFinite(Number(context.filterGeneration))
          ? Number(context.filterGeneration)
          : null;
        const traceContextKey = context ? String(context.traceContextKey || generation || "") : "";
        if (state.activeRow && traceContextKey !== state.lastTraceContextKey) {
          state.lastFilterGeneration = generation;
          state.lastTraceContextKey = traceContextKey;
          refreshUfoFocus("UFO filters changed");
        }
      } catch (error) {
        console.error(error);
      }
    }, POLL_INTERVAL_MS);
  }

  function stopPolling() {
    if (state.pollTimer) window.clearInterval(state.pollTimer);
    state.pollTimer = null;
  }

  function coordinateLabel(detail) {
    const evidenceClass = String(detail.coordinateEvidenceClass || "");
    const labels = {
      source_exact: "Source-supported site · uncertainty ≤100 m",
      source_bounded: "Source-supported bounded site · uncertainty ≤1 km",
      candidate_field_marker: "Candidate field marker · not source-bounded",
      locality_centroid: "Locality centroid · not the formation field",
      postal_centroid: "Postal centroid · not the formation field",
      approximate_map_pin: "Approximate map pin · not an exact field",
      source_regional: "Source-supported regional location · uncertainty >1 km",
      source_uncertainty_unknown: "Source-supported location · uncertainty unknown",
    };
    if (labels[evidenceClass]) return labels[evidenceClass];
    if (detail.exactCoordinate) return "Reviewed/corroborated exact field";
    if (detail.markerConfidence === "provisional") return "Provisional candidate field";
    return "Locality centroid · not the formation field";
  }

  function coordinateClass(detail) {
    const evidenceClass = String(detail.coordinateEvidenceClass || "");
    if (evidenceClass === "source_exact") return "is-exact";
    if (evidenceClass === "source_bounded" || evidenceClass === "candidate_field_marker") return "is-candidate";
    if (evidenceClass) return "is-locality";
    if (detail.exactCoordinate) return "is-exact";
    if (detail.markerConfidence === "provisional") return "is-candidate";
    return "is-locality";
  }

  function dateLabel(detail) {
    const iso = String(detail.dateIso || detail.dateRaw || "Unknown date");
    if (detail.datePrecision === "exact_day" || detail.datePrecision === "day") return iso;
    if (detail.datePrecision === "month" && iso.length >= 7) return iso.slice(0, 7) + " (month only)";
    if (detail.datePrecision === "year" && iso.length >= 4) return iso.slice(0, 4) + " (year only)";
    return iso + (detail.datePrecision ? " (" + detail.datePrecision + ")" : "");
  }

  function dateRoleLabel(detail) {
    const labels = {
      formation: "Formation date",
      formation_date: "Formation date",
      occurrence: "Occurrence date",
      occurrence_date: "Occurrence date",
      observed: "Observed date",
      discovered: "Discovery date",
      discovery_date: "Discovery date",
      reported: "Report date",
      report_date: "Report date",
      photography_date: "Photography date",
      catalog_date: "Catalog date",
      published: "Publication date",
      publication_date: "Publication date",
      catalog_unspecified: "Catalog date (role unspecified)",
    };
    return labels[String(detail.dateRole || "catalog_unspecified")] || "Catalog date (role unspecified)";
  }

  function dateCaveat(detail) {
    const role = String(detail.dateRole || "catalog_unspecified");
    if (role === "formation" || role === "formation_date") {
      return detail.formationDateKnown
        ? "The cited source identifies this as the exact formation date."
        : "The cited source labels this as a formation date, but this record does not establish an exact formation day.";
    }
    if (role === "occurrence" || role === "occurrence_date") {
      return "The cited source identifies this as the event occurrence date; authenticity and cause are not implied.";
    }
    const nonFormationLabels = {
      observed: "observed", discovered: "discovery", discovery_date: "discovery",
      reported: "report", report_date: "report", photography_date: "photography",
      catalog_date: "catalog", published: "publication", publication_date: "publication",
    };
    if (nonFormationLabels[role]) {
      return "This is the " + nonFormationLabels[role] + " date, not evidence of when the formation was created.";
    }
    return "The catalog date may reflect discovery, reporting, or publication. Formation time is not established by this record.";
  }

  function familyLabel(value) {
    return String(value || "design not documented")
      .replaceAll("_", " ")
      .replace(/\b\w/g, function (letter) { return letter.toUpperCase(); });
  }

  function metricNumber(value, fallback) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function polarPoint(cx, cy, radius, angle) {
    return [cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius];
  }

  function renderSchematicSvg(diagram) {
    if (!diagram || !diagram.family || diagram.family === "no_diagram" || diagram.family === "blank") {
      return '<svg viewBox="0 0 240 180" role="img" aria-label="Design not documented"><circle cx="120" cy="90" r="55" class="cc-schematic-guide"/><text x="120" y="99" text-anchor="middle" class="cc-schematic-question">?</text></svg>';
    }
    const family = diagram.family;
    const components = Math.max(1, Math.min(12, Math.round(metricNumber(diagram.components, 4))));
    const symmetry = Math.max(3, Math.min(12, Math.round(metricNumber(diagram.symmetryOrder, components))));
    const ringCount = Math.max(0, Math.min(4, Math.round(metricNumber(diagram.rings, 0))));
    const discCount = Math.max(0, Math.min(8, Math.round(metricNumber(diagram.discs, components))));
    let shapes = '<circle cx="120" cy="90" r="72" class="cc-schematic-guide"/>';

    if (family === "single_disc_or_circle") {
      shapes += '<circle cx="120" cy="90" r="34" class="cc-schematic-fill"/>';
    } else if (family === "ring_or_concentric_target") {
      const rings = Math.max(2, ringCount || 3);
      for (let index = 0; index < rings; index += 1) {
        shapes += '<circle cx="120" cy="90" r="' + (18 + index * 14) + '" class="cc-schematic-stroke"/>';
      }
      shapes += '<circle cx="120" cy="90" r="8" class="cc-schematic-fill"/>';
    } else if (family === "linear_circle_chain_or_axial_pair") {
      const count = Math.max(2, Math.min(7, components));
      shapes += '<path d="M45 90H195" class="cc-schematic-line"/>';
      for (let index = 0; index < count; index += 1) {
        const x = 55 + index * (130 / Math.max(1, count - 1));
        const radius = 7 + (index === Math.floor(count / 2) ? 7 : 0);
        shapes += '<circle cx="' + x.toFixed(1) + '" cy="90" r="' + radius + '" class="cc-schematic-fill"/>';
      }
    } else if (family === "multi_circle_cluster" || family === "radial_circle_cluster") {
      const count = Math.max(4, symmetry);
      shapes += '<circle cx="120" cy="90" r="17" class="cc-schematic-fill"/>';
      for (let index = 0; index < count; index += 1) {
        const point = polarPoint(120, 90, 47, (Math.PI * 2 * index) / count);
        shapes += '<circle cx="' + point[0].toFixed(1) + '" cy="' + point[1].toFixed(1) + '" r="' + (discCount ? 8 : 7) + '" class="cc-schematic-fill"/>';
      }
    } else if (family === "radial_rosette_or_star") {
      const points = [];
      for (let index = 0; index < symmetry * 2; index += 1) {
        const point = polarPoint(120, 90, index % 2 ? 25 : 59, -Math.PI / 2 + (Math.PI * index) / symmetry);
        points.push(point[0].toFixed(1) + "," + point[1].toFixed(1));
      }
      shapes += '<polygon points="' + points.join(" ") + '" class="cc-schematic-stroke cc-schematic-soft-fill"/><circle cx="120" cy="90" r="12" class="cc-schematic-fill"/>';
    } else if (family === "angular_or_linear_geometric" || family === "axial_angular_geometric") {
      shapes += '<path d="M48 126L84 54L120 126L156 54L192 126" class="cc-schematic-line"/>';
      shapes += '<circle cx="120" cy="90" r="12" class="cc-schematic-fill"/>';
      if (family === "axial_angular_geometric") shapes += '<path d="M38 90H202" class="cc-schematic-line"/>';
    } else if (family === "enclosed_or_looped_composite") {
      shapes += '<ellipse cx="120" cy="90" rx="67" ry="45" class="cc-schematic-stroke"/><ellipse cx="120" cy="90" rx="42" ry="24" class="cc-schematic-stroke"/><circle cx="120" cy="90" r="10" class="cc-schematic-fill"/>';
    } else if (family === "complex_composite_geometric") {
      shapes += '<circle cx="120" cy="90" r="28" class="cc-schematic-stroke"/><circle cx="120" cy="90" r="11" class="cc-schematic-fill"/>';
      const count = Math.max(5, symmetry);
      for (let index = 0; index < count; index += 1) {
        const inner = polarPoint(120, 90, 30, (Math.PI * 2 * index) / count);
        const outer = polarPoint(120, 90, 62, (Math.PI * 2 * index) / count);
        shapes += '<path d="M' + inner[0].toFixed(1) + ' ' + inner[1].toFixed(1) + 'L' + outer[0].toFixed(1) + ' ' + outer[1].toFixed(1) + '" class="cc-schematic-line"/>';
        shapes += '<circle cx="' + outer[0].toFixed(1) + '" cy="' + outer[1].toFixed(1) + '" r="6" class="cc-schematic-fill"/>';
      }
    } else if (family === "simple_non_circular_mark") {
      shapes += '<rect x="74" y="58" width="92" height="64" rx="27" class="cc-schematic-stroke cc-schematic-soft-fill"/><path d="M120 45V135" class="cc-schematic-line"/>';
    } else if (family === "irregular_or_figurative_complex") {
      shapes += '<path d="M47 108C65 43 101 142 120 70S176 38 193 110C162 151 83 145 47 108Z" class="cc-schematic-stroke cc-schematic-soft-fill"/>';
      shapes += '<circle cx="120" cy="90" r="9" class="cc-schematic-fill"/>';
    } else {
      shapes += '<path d="M53 116L78 58L120 78L158 48L190 120L138 136L91 127Z" class="cc-schematic-stroke cc-schematic-soft-fill"/>';
      shapes += '<circle cx="120" cy="90" r="10" class="cc-schematic-fill"/>';
    }
    return '<svg viewBox="0 0 240 180" role="img" aria-label="Approximate ' + escapeHtml(familyLabel(family)) + ' schematic">' + shapes + "</svg>";
  }

  function detailSources(detail) {
    const sources = [];
    const seen = new Set();
    function add(name, url, note) {
      const safeUrl = safeHttpUrl(url);
      if (!safeUrl || seen.has(safeUrl)) return;
      seen.add(safeUrl);
      sources.push({ name: name || "Source", url: safeUrl, note: note || "" });
    }
    const descriptions = normalizedSourceDescriptions(detail);
    for (const description of descriptions) {
      const sourceName = description.sourceName || "ICCRA";
      add(sourceName + " — source narrative", description.url, description.assertionId ? "Assertion " + description.assertionId : "Source for the displayed excerpt");
    }
    if (!descriptions.length && detail.sourceDescriptionUrl) {
      add(detail.sourceDescriptionLabel || "ICCRA — source narrative", detail.sourceDescriptionUrl, "Source for the displayed excerpt");
    }
    for (const source of detail.sources || []) {
      const sourceName = source.name || "Catalog source";
      add(sourceName + " — record page", source.recordUrl || source.url, source.pageNumber ? "Page " + source.pageNumber : source.listingText || "");
      add(sourceName + " — collection", source.collectionUrl, source.pageNumber ? "Page " + source.pageNumber : "Collection-level provenance");
    }
    for (const url of detail.links || []) {
      let host = "linked record";
      try { host = new URL(url).hostname.replace(/^www\./, ""); } catch (error) { /* ignored */ }
      add("Additional record — " + host, url, "");
    }
    for (const image of detail.images || []) add((image.source || "Image") + " — image source", image.pageUrl, image.rights || "");
    return sources;
  }

  function normalizedSourceDescriptions(detail) {
    const entries = Array.isArray(detail.sourceDescriptions) ? detail.sourceDescriptions : [];
    const descriptions = entries.filter(function (entry) {
      return entry && String(entry.text || "").trim();
    }).map(function (entry) {
      return {
        assertionId: String(entry.assertionId || "").trim(),
        text: String(entry.text || "").trim(),
        truncated: Boolean(entry.truncated),
        url: entry.url,
        sourceName: String(entry.sourceName || "").trim(),
        creditDisplay: String(entry.creditDisplay || "").trim(),
        attributionAvailable: Boolean(entry.attributionAvailable),
      };
    });
    if (descriptions.length) return descriptions;
    const singular = String(detail.sourceDescription || "").trim();
    if (!singular) return [];
    return [{
      assertionId: "",
      text: singular,
      truncated: Boolean(detail.sourceDescriptionTruncated),
      url: detail.sourceDescriptionUrl,
      sourceName: String(detail.sourceDescriptionLabel || "ICCRA").split(" — ")[0].trim() || "ICCRA",
      creditDisplay: String(detail.sourceDescriptionCreditDisplay || "").trim(),
      attributionAvailable: Boolean(detail.sourceDescriptionAttributionAvailable || detail.sourceDescriptionCredit),
    }];
  }

  function renderSourceDescriptions(detail) {
    const descriptions = normalizedSourceDescriptions(detail);
    if (!descriptions.length) {
      return '<section class="cc-source-description is-missing"><h4>Source description</h4><p>No source narrative currently captured for this record.</p></section>';
    }
    const plural = descriptions.length > 1;
    return '<section class="cc-source-descriptions"><h4>' + (plural ? "Source descriptions" : "Source description") + '</h4><div class="cc-source-description-list">' +
      descriptions.map(function (description) {
        const sourceName = description.sourceName || "Source narrative";
        const assertionLabel = description.assertionId ? "Assertion " + description.assertionId : "";
        const attribution = description.creditDisplay
          ? '<p class="cc-source-credit">Credit: ' + escapeHtml(description.creditDisplay) + "</p>"
          : description.attributionAvailable
            ? '<p class="cc-source-credit">Full attribution is available on the source page.</p>'
            : "";
        return '<article class="cc-source-description"><div class="cc-source-description-meta"><strong>' + escapeHtml(sourceName) + "</strong>" +
          (assertionLabel ? "<span>" + escapeHtml(assertionLabel) + "</span>" : "") + '</div><p>' + escapeHtml(description.text) +
          (description.truncated ? ' <span class="cc-detail-muted">[short excerpt]</span>' : "") + "</p>" + attribution + "</article>";
      }).join("") + "</div></section>";
  }

  function detailImage(detail) {
    return (detail.images || []).find(function (image) {
      return image.embeddingAllowed && safeHttpUrl(image.imageUrl);
    }) || null;
  }

  function detailField(label, value) {
    if (value == null || value === "" || value === "unknown") return "";
    return '<div class="cc-detail-field"><span>' + escapeHtml(label) + '</span><strong>' + escapeHtml(value) + "</strong></div>";
  }

  function renderDetail(detail) {
    state.activeDetail = detail;
    const diagrams = detail.morphology && detail.morphology.length ? detail.morphology : [null];
    state.activeDiagramIndex = Math.max(0, Math.min(state.activeDiagramIndex, diagrams.length - 1));
    const diagram = diagrams[state.activeDiagramIndex];
    const sources = detailSources(detail);
    const image = detailImage(detail);
    const tabs = diagrams.length > 1
      ? '<div class="cc-diagram-tabs" role="tablist" aria-label="Reported diagrams">' + diagrams.map(function (_, index) {
          return '<button type="button" role="tab" data-cc-diagram-index="' + index + '" aria-selected="' + (index === state.activeDiagramIndex ? "true" : "false") + '">Diagram ' + (index + 1) + "</button>";
        }).join("") + "</div>"
      : "";
    const sourceMarkup = sources.length
      ? '<ul class="cc-source-list">' + sources.slice(0, 10).map(function (source) {
          return '<li><a href="' + escapeHtml(source.url) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(source.name) + '</a>' + (source.note ? '<span>' + escapeHtml(source.note) + "</span>" : "") + "</li>";
        }).join("") + "</ul>"
      : '<p class="cc-detail-muted">No event-specific source link is available in this export.</p>';
    const imageMarkup = image
      ? '<div class="cc-source-image-shell"><button type="button" class="secondary-button" data-cc-load-image="' + escapeHtml(safeHttpUrl(image.imageUrl)) + '">Load licensed source photo</button><p>' + escapeHtml(image.rights || "Open-license source image") + '</p><img data-cc-source-image alt="Source photograph of this reported crop formation" hidden></div>'
      : "";
    const uncertaintyM = detail.coordinateUncertaintyM != null
      ? Number(detail.coordinateUncertaintyM)
      : detail.coordinateUncertaintyKm != null
        ? Number(detail.coordinateUncertaintyKm) * 1000
        : null;
    const uncertainty = Number.isFinite(uncertaintyM)
      ? (uncertaintyM >= 1000
        ? (uncertaintyM / 1000).toLocaleString(undefined, { maximumFractionDigits: 3 }) + " km"
        : uncertaintyM.toLocaleString(undefined, { maximumFractionDigits: 3 }) + " m") +
        " coordinate uncertainty"
      : "Coordinate uncertainty is not quantified";
    const morphologyName = diagram ? familyLabel(diagram.family) : "Design not documented";
    const sourceDescriptionMarkup = renderSourceDescriptions(detail);
    const catalogSummary = String(detail.catalogSummary || detail.description || "").trim();
    const catalogSummaryMarkup = catalogSummary
      ? '<section class="cc-catalog-summary"><h4>Catalog summary</h4><p>' + escapeHtml(catalogSummary) + "</p></section>"
      : "";
    const fields = [
      detailField(dateRoleLabel(detail), dateLabel(detail)),
      detailField("Crop", detail.crop),
      detailField("Reported size", detail.sizeText || (detail.reportedSizeM != null ? detail.reportedSizeM + " m" : "")),
      detailField("Morphology", morphologyName),
      detailField("Complexity", diagram && diagram.complexity != null ? diagram.complexity + (diagram.complexityTier ? " · " + diagram.complexityTier : "") : ""),
      detailField("Components", diagram && diagram.components),
      detailField("Symmetry", diagram && diagram.symmetryOrder != null ? "Order " + diagram.symmetryOrder : ""),
      detailField("Classification", detail.classification),
      detailField("Source assertions", detail.assertionCount),
    ].join("");

    const stackReturnMarkup = state.activePositionRows && state.activePositionRows.length > 1
      ? '<button type="button" class="secondary-button cc-stack-return" data-cc-stack-return>← ' + state.activePositionRows.length.toLocaleString() + " records at this position</button>"
      : "";
    panelBody.innerHTML = stackReturnMarkup +
      '<div class="cc-detail-heading"><div><p class="cc-detail-eyebrow">Crop Circle Atlas</p><h3>' + escapeHtml(detail.location || "Reported crop formation") + '</h3><p>' + escapeHtml(dateLabel(detail)) + '</p></div><span class="cc-coordinate-badge ' + coordinateClass(detail) + '">' + escapeHtml(coordinateLabel(detail)) + "</span></div>" +
      '<p class="cc-date-caveat"><strong>' + escapeHtml(dateRoleLabel(detail)) + ':</strong> ' + escapeHtml(dateCaveat(detail)) + "</p>" +
      '<p class="cc-detail-warning">' + escapeHtml(uncertainty) + "</p>" +
      sourceDescriptionMarkup +
      catalogSummaryMarkup +
      '<section class="cc-schematic-card">' + tabs + '<div class="cc-schematic" data-cc-schematic>' + renderSchematicSvg(diagram) + '</div><p><strong>Measurement-informed schematic</strong> — an approximate visual derived from catalog morphology, not an exact field diagram or photograph.</p></section>' +
      '<div class="cc-detail-grid">' + fields + "</div>" +
      (detail.mappingNotes ? '<p class="cc-detail-warning">' + escapeHtml(detail.mappingNotes) + "</p>" : "") +
      imageMarkup +
      '<section class="cc-detail-sources"><h4>Sources and provenance</h4>' + sourceMarkup + "</section>" +
      '<p class="cc-trace-policy"><strong>Separate relationship layers:</strong> this crop record is never inserted into the UFO chronology graph. Radius analysis highlights existing filtered UFO connectors and sighting-date candidates; crop progression remains a separate catalog-date layer. None of these links establishes formation time, causation, travel, or a shared craft.</p>';
    panel.hidden = false;
    panel.setAttribute("aria-hidden", "false");
  }

  function ordinalLabel(row) {
    const start = Number(row[ROW.start]);
    const end = Number(row[ROW.end]);
    function iso(ordinal) {
      if (!Number.isFinite(ordinal)) return "Unknown date";
      try { return new Date(ordinal * 86400000).toISOString().slice(0, 10); } catch (error) { return "Unknown date"; }
    }
    const precisionLabels = ["exact catalog day", "catalog month", "catalog year", "approximate catalog date", "catalog date range"];
    const precision = precisionLabels[Number(row[ROW.datePrecision])] || "catalog date";
    return (start === end ? iso(start) : iso(start) + " – " + iso(end)) + " · " + precision;
  }

  function coordinateCodeLabel(code) {
    return Number(code) === 0 ? "exact field" : Number(code) === 1 ? "candidate field" : "locality centroid";
  }

  function showPositionChooser(rows) {
    state.detailRequestGeneration += 1;
    state.activeRow = null;
    clearUfoFocus("choose a record from the stack");
    const ordered = rows.slice().sort(compareRowsByDate);
    state.activePositionRows = ordered;
    state.activeDetail = null;
    syncUfoFocusControlState();
    const first = ordered[0];
    panelBody.innerHTML =
      '<div class="cc-stack-heading"><p class="cc-detail-eyebrow">Shared mapped position</p><h3>' + ordered.length.toLocaleString() +
      ' crop-circle records</h3><p>' + escapeHtml(Number(first[ROW.lat]).toFixed(4) + ", " + Number(first[ROW.lon]).toFixed(4)) +
      '</p></div><p class="cc-date-caveat">Select a catalog record in date order. Shared coordinates often represent a town or locality centroid, not the same physical field.</p>' +
      '<ol class="cc-stack-list">' + ordered.map(function (row) {
        return '<li><button type="button" data-cc-record-id="' + escapeHtml(row[ROW.id]) + '"><strong>' + escapeHtml(ordinalLabel(row)) +
          '</strong><span>' + escapeHtml(coordinateCodeLabel(row[ROW.coordinate]) + " · " + String(row[ROW.id])) + "</span></button></li>";
      }).join("") + "</ol>";
    panel.hidden = false;
    panel.setAttribute("aria-hidden", "false");
  }

  async function openPosition(rows) {
    if (!rows.length) throw new Error("No crop-circle record is available at this position.");
    const ordered = rows.slice().sort(compareRowsByDate);
    state.activePositionRows = ordered;
    if (ordered.length > 1) {
      state.activeRow = null;
      state.activeDetail = null;
      clearUfoFocus("choose a record from the stack");
      syncUfoFocusControlState();
      showPositionChooser(ordered);
      return;
    }
    await openDetailForPoint(ordered[0]);
  }

  function showPanelLoading(row) {
    panelBody.innerHTML = '<div class="cc-detail-loading"><span class="cc-loading-spinner" aria-hidden="true"></span><p>Loading crop-circle details and schematic…</p></div>';
    panel.hidden = false;
    panel.setAttribute("aria-hidden", "false");
    const marker = state.markerById.get(String(row[ROW.id]));
    if (marker && state.map) state.map.panInside(marker.getLatLng(), { padding: [40, 40] });
  }

  function showPanelError(error) {
    if (!panelBody || !panel) return;
    panelBody.innerHTML = '<p class="cc-detail-error">' + escapeHtml(error && error.message ? error.message : String(error)) + "</p>";
    panel.hidden = false;
    panel.setAttribute("aria-hidden", "false");
  }

  function closePanel() {
    if (!panel) return;
    state.detailRequestGeneration += 1;
    panel.hidden = true;
    panel.setAttribute("aria-hidden", "true");
    state.activeDetail = null;
    state.activeRow = null;
    state.activePositionRows = null;
    state.activeDiagramIndex = 0;
    clearUfoFocus("crop detail closed");
    syncUfoFocusControlState();
  }

  function resetControls() {
    state.chronology.enabled = false;
    state.chronology.relation = "off";
    state.chronology.coordinateScope = "field";
    state.chronology.maxDistanceKm = 250;
    state.chronology.graphKey = "";
    state.chronology.graphEdges = [];
    state.chronology.eligibleNodes = 0;
    state.chronology.candidateEdges = 0;
    state.ufoFocus.relationWindow = "off";
    state.ufoFocus.positionQuality = "source";
    state.ufoFocus.cropPositionQuality = "field";
    state.ufoFocus.radiusKm = 25;
    state.ufoFocus.traceAnalysisEnabled = false;
    state.ufoFocus.hopDepth = 1;
    state.ufoFocus.hopDirection = "both";
    state.ufoFocus.showRadius = true;
    state.ufoFocus.emphasizeIntersections = true;
    state.ufoFocus.isolation = false;
    clearChronologyLayer();
    closePanel();
    syncChronologyControlState();
    setChronologyStatus("Crop-to-crop progression is off.");
    setUfoRelationStatus("Select a crop record to inspect nearby UFO relations and trace intersections.");
    return true;
  }

  async function detailChunk(chunkNumber) {
    if (state.detailChunkCache.has(chunkNumber)) {
      const cached = state.detailChunkCache.get(chunkNumber);
      state.detailChunkCache.delete(chunkNumber);
      state.detailChunkCache.set(chunkNumber, cached);
      return cached;
    }
    const pattern = state.manifest.details.chunkPattern;
    const chunkText = String(chunkNumber).padStart(3, "0");
    const path = pattern.replace("{chunk:03d}", chunkText).replace("{chunk}", String(chunkNumber));
    const detailPath = String(state.manifest.details.basePath || "") + path;
    const payload = await readAssetJson(detailPath);
    state.detailChunkCache.set(chunkNumber, payload);
    while (state.detailChunkCache.size > MAX_DETAIL_CHUNKS) {
      state.detailChunkCache.delete(state.detailChunkCache.keys().next().value);
    }
    return payload;
  }

  async function openDetailForPoint(row) {
    const generation = ++state.detailRequestGeneration;
    state.activeRow = null;
    state.activeDetail = null;
    clearUfoFocus("switching crop record");
    syncUfoFocusControlState();
    showPanelLoading(row);
    let chunk;
    try {
      chunk = await detailChunk(Number(row[ROW.chunk]));
    } catch (error) {
      if (generation !== state.detailRequestGeneration) return false;
      throw error;
    }
    if (generation !== state.detailRequestGeneration || !state.enabled) return false;
    const detail = chunk[String(row[ROW.id])];
    if (!detail) throw new Error("Crop-circle detail record was not found.");
    state.activeRow = row;
    state.activeDiagramIndex = 0;
    renderDetail(detail);
    syncUfoFocusControlState();
    const context = extensionContext();
    state.lastFilterGeneration = context && Number.isFinite(Number(context.filterGeneration))
      ? Number(context.filterGeneration)
      : null;
    state.lastTraceContextKey = context ? String(context.traceContextKey || state.lastFilterGeneration || "") : "";
    refreshUfoFocus("crop record selected");
    return true;
  }

  function installPanelInteractions() {
    if (!panel || panel.dataset.cropCircleReady === "1") return;
    panel.dataset.cropCircleReady = "1";
    panelClose.addEventListener("click", closePanel);
    panel.addEventListener("click", function (event) {
      event.stopPropagation();
      const recordButton = event.target.closest("[data-cc-record-id]");
      if (recordButton) {
        const row = state.rowById.get(String(recordButton.dataset.ccRecordId));
        if (row) {
          openDetailForPoint(row).catch(function (error) { showPanelError(error); });
        }
        return;
      }
      const stackReturn = event.target.closest("[data-cc-stack-return]");
      if (stackReturn && state.activePositionRows) {
        showPositionChooser(state.activePositionRows);
        return;
      }
      const tab = event.target.closest("[data-cc-diagram-index]");
      if (tab && state.activeDetail) {
        state.activeDiagramIndex = Number(tab.dataset.ccDiagramIndex) || 0;
        renderDetail(state.activeDetail);
        return;
      }
      const loadButton = event.target.closest("[data-cc-load-image]");
      if (!loadButton) return;
      const url = safeHttpUrl(loadButton.dataset.ccLoadImage);
      const image = panel.querySelector("[data-cc-source-image]");
      if (!url || !image) return;
      loadButton.disabled = true;
      loadButton.textContent = "Loading source photo…";
      image.onload = function () {
        image.hidden = false;
        loadButton.hidden = true;
      };
      image.onerror = function () {
        loadButton.disabled = false;
        loadButton.textContent = "Source blocked image loading — open its source link";
      };
      image.src = url;
    });
    ["pointerdown", "pointermove", "mousedown", "touchstart", "touchmove", "wheel", "dblclick"].forEach(function (eventName) {
      panel.addEventListener(eventName, function (event) { event.stopPropagation(); }, { passive: eventName === "wheel" || eventName === "touchmove" ? false : true });
    });
    if (window.L && window.L.DomEvent) {
      window.L.DomEvent.disableClickPropagation(panel);
      window.L.DomEvent.disableScrollPropagation(panel);
    }
  }

  async function setEnabled(enabled) {
    if (!enabled) {
      state.enableGeneration += 1;
      state.enabled = false;
      state.loading = false;
      stopPolling();
      if (state.map && state.layer && state.map.hasLayer(state.layer)) state.map.removeLayer(state.layer);
      if (state.layer) state.layer.clearLayers();
      state.markerById.clear();
      state.visibleRecords = null;
      state.visiblePositions = null;
      state.lastViewKey = "";
      state.chronology.enabled = false;
      state.chronology.relation = "off";
      state.chronology.graphKey = "";
      state.chronology.graphEdges = [];
      state.chronology.eligibleNodes = 0;
      state.chronology.candidateEdges = 0;
      clearChronologyLayer();
      removeMapHandlers();
      removeMarkerHitHandler();
      closePanel();
      setButtonState(false, false);
      syncChronologyControlState();
      setChronologyStatus("Crop-to-crop progression is off.");
      setUfoRelationStatus("Select a crop record to inspect nearby UFO relations and trace intersections.");
      setStatus("Crop circles are off. Turn the layer on to show catalog positions.");
      return false;
    }
    if (state.loading) return true;
    const generation = ++state.enableGeneration;
    state.loading = true;
    setButtonState(true, true);
    setStatus("Loading compact crop-circle locations…");
    try {
      const context = await waitForMap();
      if (generation !== state.enableGeneration || !state.loading) return false;
      await ensureData();
      if (generation !== state.enableGeneration || !state.loading) return false;
      ensureMapLayer(context);
      installPanelInteractions();
      state.enabled = true;
      installChronologyControls();
      syncChronologyControlState();
      installMapHandlers();
      installMarkerHitHandler();
      state.lastViewKey = "";
      renderPoints(true);
      startPolling();
      setButtonState(true, false);
      return true;
    } catch (error) {
      if (generation !== state.enableGeneration) return false;
      state.enabled = false;
      setButtonState(false, false);
      setStatus(error && error.message ? error.message : String(error), true);
      throw error;
    } finally {
      if (generation === state.enableGeneration) state.loading = false;
    }
  }

  window.UfoCropCircleLayer = Object.freeze({
    setEnabled,
    resetControls,
    setChronology: function (options) {
      const settings = options || {};
      if (["off", "same_day", "7", "30"].includes(settings.relation)) state.chronology.relation = settings.relation;
      if (Object.prototype.hasOwnProperty.call(settings, "enabled") && !settings.enabled) state.chronology.relation = "off";
      if (settings.enabled && state.chronology.relation === "off") state.chronology.relation = "same_day";
      state.chronology.enabled = Boolean(state.enabled && state.chronology.relation !== "off");
      if (settings.coordinateScope === "field" || settings.coordinateScope === "all") state.chronology.coordinateScope = settings.coordinateScope;
      if ([100, 250, 500, 1000].includes(Number(settings.maxDistanceKm))) state.chronology.maxDistanceKm = Number(settings.maxDistanceKm);
      state.chronology.graphKey = "";
      syncChronologyControlState();
      renderChronology(true);
      return state.chronology.enabled;
    },
    setUfoFocus: async function (options) {
      const settings = options || {};
      if (["off", "same_day", "after_1_7", "after_1_30"].includes(settings.relationWindow)) state.ufoFocus.relationWindow = settings.relationWindow;
      if (settings.positionQuality === "source" || settings.positionQuality === "all") state.ufoFocus.positionQuality = settings.positionQuality;
      if (settings.cropPositionQuality === "field" || settings.cropPositionQuality === "all") state.ufoFocus.cropPositionQuality = settings.cropPositionQuality;
      if ([5, 10, 25, 50, 100, 250, 500].includes(Number(settings.radiusKm))) state.ufoFocus.radiusKm = Number(settings.radiusKm);
      if (Object.prototype.hasOwnProperty.call(settings, "traceAnalysisEnabled")) state.ufoFocus.traceAnalysisEnabled = Boolean(settings.traceAnalysisEnabled);
      if ([1, 2, 3, 4].includes(Number(settings.hopDepth))) state.ufoFocus.hopDepth = Number(settings.hopDepth);
      if (["forward", "backward", "both"].includes(settings.hopDirection)) state.ufoFocus.hopDirection = settings.hopDirection;
      if (Object.prototype.hasOwnProperty.call(settings, "showRadius")) state.ufoFocus.showRadius = Boolean(settings.showRadius);
      if (Object.prototype.hasOwnProperty.call(settings, "emphasizeIntersections")) state.ufoFocus.emphasizeIntersections = Boolean(settings.emphasizeIntersections);
      if (Object.prototype.hasOwnProperty.call(settings, "isolation")) state.ufoFocus.isolation = Boolean(settings.isolation && state.ufoFocus.traceAnalysisEnabled);
      syncUfoFocusControlState();
      return refreshUfoFocus("API settings changed");
    },
    openRecord: async function (id) {
      if (!state.enabled) throw new Error("Enable crop circles before opening a record.");
      const row = state.rowById.get(String(id));
      if (!row) throw new Error("Crop-circle record was not found.");
      const rows = state.rowsByPosition.get(positionKey(row)) || [row];
      state.activePositionRows = rows.slice().sort(compareRowsByDate);
      return openDetailForPoint(row);
    },
    isEnabled: function () { return state.enabled; },
    getStatus: function () {
      return {
        enabled: state.enabled,
        loaded: Boolean(state.points),
        mappedCount: state.points ? state.points.length : 0,
        renderedCount: state.layer && typeof state.layer.getLayers === "function"
          ? state.layer.getLayers().reduce(function (total, marker) { return total + Number(marker.options.ccStackCount || 1); }, 0)
          : 0,
        renderedPositionCount: state.layer && typeof state.layer.getLayers === "function" ? state.layer.getLayers().length : 0,
        cachedDetailChunks: state.detailChunkCache.size,
        traceEligible: false,
        traceFocusActive: Boolean(state.activeRow),
        selectedRecordId: state.activeRow ? String(state.activeRow[ROW.id]) : null,
        ufoFocus: {
          relationWindow: state.ufoFocus.relationWindow,
          positionQuality: state.ufoFocus.positionQuality,
          cropPositionQuality: state.ufoFocus.cropPositionQuality,
          radiusKm: state.ufoFocus.radiusKm,
          traceAnalysisEnabled: state.ufoFocus.traceAnalysisEnabled,
          hopDepth: state.ufoFocus.hopDepth,
          hopDirection: state.ufoFocus.hopDirection,
          showRadius: state.ufoFocus.showRadius,
          emphasizeIntersections: state.ufoFocus.emphasizeIntersections,
          isolation: state.ufoFocus.isolation,
          result: state.ufoFocus.lastResult,
        },
        chronology: {
          enabled: state.chronology.enabled,
          relation: state.chronology.relation,
          coordinateScope: state.chronology.coordinateScope,
          maxDistanceKm: state.chronology.maxDistanceKm,
          eligibleNodes: state.chronology.eligibleNodes,
          candidateEdges: state.chronology.candidateEdges,
          renderedEdges: state.chronology.renderedEdges,
          capped: state.chronology.capped,
          traceEligible: false,
          role: "catalog_date_adjacency_only",
        },
      };
    },
  });
})();
