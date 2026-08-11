(function () {
  "use strict";

  const MANIFEST_URL = "./data/animal_mutilations/manifest.json";
  const POLL_INTERVAL_MS = 250;
  const MAX_DETAIL_CHUNKS = 5;
  const BROWSER_PAGE_SIZE = 100;
  const ROW = Object.freeze({
    id: 0, lat: 1, lon: 2, start: 3, end: 4, datePrecision: 5, species: 6, chunk: 7,
  });
  const CATALOG = Object.freeze({
    id: 0, title: 1, summary: 2, location: 3, dateStart: 4, dateEnd: 5,
    datePrecision: 6, species: 7, mapped: 8, chunk: 9, status: 10, commonNames: 11,
    searchText: 12,
  });

  const state = {
    enabled: false,
    loading: false,
    manifest: null,
    manifestPromise: null,
    manifestController: null,
    points: null,
    pointsPromise: null,
    pointsController: null,
    catalog: null,
    catalogPromise: null,
    catalogController: null,
    catalogById: new Map(),
    map: null,
    layer: null,
    markers: [],
    rowsByPosition: new Map(),
    detailChunkCache: new Map(),
    detailChunkPromises: new Map(),
    detailChunkControllers: new Map(),
    detailRequestGeneration: 0,
    detailReturnFocus: null,
    detailRestoresBrowser: false,
    visibleRecords: null,
    visiblePositions: null,
    lastViewKey: "",
    pollTimer: null,
    markerHitContainer: null,
    markerHitHandler: null,
    browserFilteredRows: [],
    browserRenderLimit: BROWSER_PAGE_SIZE,
    browserReturnFocus: null,
    browserOpen: false,
    browserRequestGeneration: 0,
    enableGeneration: 0,
    activePositionRows: [],
  };

  const toggle = document.querySelector("#overlay-animal-mutilations");
  const status = document.querySelector("#animal-mutilation-status");
  const browseOpen = document.querySelector("#animal-mutilation-browser-open");
  const browser = document.querySelector("#animal-mutilation-browser");
  const browserClose = document.querySelector("#animal-mutilation-browser-close");
  const browserSearch = document.querySelector("#animal-mutilation-search");
  const browserSpecies = document.querySelector("#animal-mutilation-species-filter");
  const browserMapped = document.querySelector("#animal-mutilation-mapped-filter");
  const browserDateScope = document.querySelector("#animal-mutilation-date-filter");
  const browserDateStart = document.querySelector("#animal-mutilation-date-start");
  const browserDateEnd = document.querySelector("#animal-mutilation-date-end");
  const browserReset = document.querySelector("#animal-mutilation-browser-reset");
  const browserSummary = document.querySelector("#animal-mutilation-browser-summary");
  const browserResults = document.querySelector("#animal-mutilation-browser-results");
  const browserMore = document.querySelector("#animal-mutilation-browser-more");
  const detailPanel = document.querySelector("#animal-mutilation-detail-panel");
  const detailBody = document.querySelector("#animal-mutilation-detail-body");
  const detailClose = document.querySelector("#animal-mutilation-detail-close");

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function safePublicHttpUrl(value) {
    try {
      const raw = String(value || "").trim();
      if (!raw) return "";
      const url = new URL(raw);
      if ((url.protocol !== "https:" && url.protocol !== "http:") || url.username || url.password) return "";
      const host = String(url.hostname || "").toLowerCase().replace(/^\[|\]$/g, "").replace(/\.$/, "");
      if (!host || host === "localhost" || host === "0.0.0.0" || host === "::1" || host.endsWith(".local")) return "";
      if (/^127\./.test(host) || /^169\.254\./.test(host) || /^10\./.test(host) || /^192\.168\./.test(host)) return "";
      const private172 = /^172\.(\d{1,3})\./.exec(host);
      if (private172 && Number(private172[1]) >= 16 && Number(private172[1]) <= 31) return "";
      if (host === "::" || /^f[cd][0-9a-f]:/i.test(host) || /^fe[89ab][0-9a-f]:/i.test(host)) return "";
      return url.href;
    } catch (error) {
      return "";
    }
  }

  function civilOrdinal(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || "").trim());
    if (!match) return null;
    let year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    if (month < 1 || month > 12 || day < 1 || day > 31) return null;
    year -= month <= 2 ? 1 : 0;
    const era = Math.floor(year / 400);
    const yearOfEra = year - era * 400;
    const monthPrime = month + (month > 2 ? -3 : 9);
    const dayOfYear = Math.floor((153 * monthPrime + 2) / 5) + day - 1;
    const dayOfEra = yearOfEra * 365 + Math.floor(yearOfEra / 4) - Math.floor(yearOfEra / 100) + dayOfYear;
    return era * 146097 + dayOfEra - 719468;
  }

  function plural(count, singular, pluralValue) {
    return Number(count).toLocaleString() + " " + (Number(count) === 1 ? singular : pluralValue);
  }

  function setStatus(message, isError) {
    if (!status) return;
    status.textContent = message || "";
    status.classList.toggle("is-error", Boolean(isError));
  }

  function setToggleState(enabled, busy) {
    if (toggle) {
      toggle.setAttribute("aria-pressed", enabled ? "true" : "false");
      toggle.classList.toggle("is-active", Boolean(enabled));
      toggle.disabled = Boolean(busy);
      if (busy) toggle.setAttribute("aria-busy", "true");
      else toggle.removeAttribute("aria-busy");
    }
    dispatchState({ busy: Boolean(busy) });
  }

  function dispatchState(extra) {
    if (typeof window.dispatchEvent !== "function" || typeof window.CustomEvent !== "function") return;
    window.dispatchEvent(new window.CustomEvent("ufo:animal-mutilation-statechange", {
      detail: Object.assign({
        enabled: state.enabled,
        visibleRecords: state.visibleRecords,
        visiblePositions: state.visiblePositions,
        totalRecords: state.manifest ? Number(state.manifest.counts.records) : null,
      }, extra || {}),
    }));
  }

  async function sha256Hex(bytes) {
    const cryptoObject = window.crypto || globalThis.crypto;
    if (!cryptoObject || !cryptoObject.subtle) return "";
    const digest = await cryptoObject.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest)).map(function (value) {
      return value.toString(16).padStart(2, "0");
    }).join("");
  }

  function makeAbortError(message) {
    if (typeof DOMException === "function") return new DOMException(message || "Request cancelled.", "AbortError");
    const error = new Error(message || "Request cancelled.");
    error.name = "AbortError";
    return error;
  }

  function isAbortError(error) {
    return Boolean(error && error.name === "AbortError");
  }

  function createRequestController() {
    return typeof AbortController === "function" ? new AbortController() : null;
  }

  function abortRequest(controller) {
    if (controller && controller.signal && !controller.signal.aborted) controller.abort();
  }

  function throwIfAborted(signal) {
    if (signal && signal.aborted) throw makeAbortError();
  }

  async function readManifest(signal) {
    throwIfAborted(signal);
    const response = await fetch(new URL(MANIFEST_URL, document.baseURI), { cache: "no-cache", signal: signal });
    if (!response.ok) throw new Error("Animal Mutilation Reports manifest request failed (" + response.status + ").");
    const manifest = await response.json();
    throwIfAborted(signal);
    return manifest;
  }

  async function readPayload(declaration, label, signal) {
    throwIfAborted(signal);
    let lastError = null;
    for (const candidate of payloadCandidates(declaration.path)) {
      try {
        const response = await fetch(candidate.url, { cache: "force-cache", signal: signal });
        if (!response.ok) throw new Error(label + " request failed (" + response.status + ").");
        const bytes = new Uint8Array(await response.arrayBuffer());
        throwIfAborted(signal);
        const expectedBytes = candidate.compressed
          ? declaration.bytes
          : (declaration.decodedBytes || declaration.decoded_bytes);
        if (Number.isFinite(Number(expectedBytes)) && bytes.length !== Number(expectedBytes)) {
          throw new Error(label + " failed its byte-count integrity check.");
        }
        if (candidate.compressed && declaration.sha256) {
          const actualHash = await sha256Hex(bytes);
          if (actualHash && actualHash !== String(declaration.sha256).toLowerCase()) {
            throw new Error(label + " failed its SHA-256 integrity check.");
          }
        }
        throwIfAborted(signal);
        let decoded;
        if (bytes.length > 1 && bytes[0] === 0x1f && bytes[1] === 0x8b) {
          if (typeof DecompressionStream !== "function") {
            throw new Error("This browser cannot decode the compact Animal Mutilation Reports data.");
          }
          const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
          decoded = await new Response(stream).text();
        } else {
          decoded = new TextDecoder("utf-8").decode(bytes);
        }
        throwIfAborted(signal);
        return JSON.parse(decoded);
      } catch (error) {
        if (isAbortError(error)) throw error;
        lastError = error;
      }
    }
    throw lastError || new Error(label + " is unavailable.");
  }

  function validateManifest(manifest) {
    const valid = manifest && manifest.schemaVersion === 1 &&
      /^animal-mutilations-v1-\d{8}$/.test(String(manifest.releaseId || "")) &&
      manifest.layerName === "Animal Mutilation Reports" && manifest.points && manifest.catalog &&
      manifest.details && manifest.delivery && manifest.policy &&
      manifest.policy.traceEligible === false && manifest.policy.traceRole === "context_only" &&
      manifest.policy.causality === "not_asserted" && manifest.policy.relationshipsEligible === false;
    if (!valid) throw new Error("Animal Mutilation Reports manifest is incompatible with this app release.");
    const declared = [manifest.points.path, manifest.catalog.path].concat(
      (manifest.details.files || []).map(function (item) { return item.path; })
    ).sort();
    const delivered = (manifest.delivery.r2OnlyPaths || []).slice().sort();
    if (JSON.stringify(declared) !== JSON.stringify(delivered)) {
      throw new Error("Animal Mutilation Reports manifest has an incomplete R2 payload declaration.");
    }
    return manifest;
  }

  function ensureManifest() {
    if (state.manifest) return Promise.resolve(state.manifest);
    if (state.manifestPromise) return state.manifestPromise;
    const controller = createRequestController();
    state.manifestController = controller;
    const tracked = readManifest(controller && controller.signal).then(validateManifest).then(function (manifest) {
      state.manifest = manifest;
      populateSpeciesFilter();
      return manifest;
    }).catch(function (error) {
      if (state.manifestPromise === tracked) state.manifestPromise = null;
      throw error;
    }).finally(function () {
      if (state.manifestController === controller) state.manifestController = null;
    });
    state.manifestPromise = tracked;
    return tracked;
  }

  function cancelUnusedManifestRequest() {
    if (state.manifest || state.enabled || state.loading || state.browserOpen) return;
    abortRequest(state.manifestController);
    state.manifestController = null;
    state.manifestPromise = null;
  }

  function assetBaseUrl() {
    if (state.manifest && state.manifest.assetBaseUrl) return new URL(state.manifest.assetBaseUrl, document.baseURI);
    return new URL("./data/animal_mutilations/", document.baseURI);
  }

  function payloadCandidates(pathValue) {
    const path = String(pathValue || "");
    const localPath = path.replace(/\.json\.gz$/i, ".json");
    const localUrl = new URL(localPath, new URL("./data/animal_mutilations/", document.baseURI));
    const remoteUrl = new URL(path, assetBaseUrl());
    const candidates = [{ url: localUrl, compressed: false }];
    if (remoteUrl.toString() !== localUrl.toString()) candidates.push({ url: remoteUrl, compressed: true });
    return candidates;
  }

  function positionKey(row) {
    return Number(row[ROW.lat]).toFixed(6) + "," + Number(row[ROW.lon]).toFixed(6);
  }

  function comparePointRows(left, right) {
    const leftStart = left[ROW.start] == null ? Number.POSITIVE_INFINITY : Number(left[ROW.start]);
    const rightStart = right[ROW.start] == null ? Number.POSITIVE_INFINITY : Number(right[ROW.start]);
    return leftStart - rightStart || String(left[ROW.id]).localeCompare(String(right[ROW.id]));
  }

  function ensurePoints() {
    if (state.points) return Promise.resolve(state.points);
    if (state.pointsPromise) return state.pointsPromise;
    let controller = null;
    const tracked = ensureManifest().then(function (manifest) {
      if (!state.loading) throw makeAbortError("Animal Mutilation Reports point loading was cancelled.");
      controller = createRequestController();
      state.pointsController = controller;
      return readPayload(manifest.points, "Animal Mutilation Reports point index", controller && controller.signal);
    }).then(function (points) {
      if (!Array.isArray(points) || points.length !== Number(state.manifest.counts.mapped)) {
        throw new Error("Animal Mutilation Reports point index failed its record-count check.");
      }
      state.points = points;
      state.rowsByPosition.clear();
      points.forEach(function (row) {
        const key = positionKey(row);
        if (!state.rowsByPosition.has(key)) state.rowsByPosition.set(key, []);
        state.rowsByPosition.get(key).push(row);
      });
      state.rowsByPosition.forEach(function (rows) { rows.sort(comparePointRows); });
      return points;
    }).catch(function (error) {
      if (state.pointsPromise === tracked) state.pointsPromise = null;
      throw error;
    }).finally(function () {
      if (state.pointsController === controller) state.pointsController = null;
    });
    state.pointsPromise = tracked;
    return tracked;
  }

  function cancelPointsRequest() {
    abortRequest(state.pointsController);
    state.pointsController = null;
    if (!state.points) state.pointsPromise = null;
  }

  function ensureCatalog() {
    if (state.catalog) return Promise.resolve(state.catalog);
    if (state.catalogPromise) return state.catalogPromise;
    let controller = null;
    const tracked = ensureManifest().then(function (manifest) {
      if (!state.browserOpen) throw makeAbortError("Animal Mutilation Reports catalog loading was cancelled.");
      controller = createRequestController();
      state.catalogController = controller;
      return readPayload(manifest.catalog, "Animal Mutilation Reports catalog", controller && controller.signal);
    }).then(function (catalog) {
      if (!Array.isArray(catalog) || catalog.length !== Number(state.manifest.counts.records)) {
        throw new Error("Animal Mutilation Reports catalog failed its all-record count check.");
      }
      state.catalog = catalog;
      state.catalogById.clear();
      catalog.forEach(function (row) { state.catalogById.set(String(row[CATALOG.id]), row); });
      return catalog;
    }).catch(function (error) {
      if (state.catalogPromise === tracked) state.catalogPromise = null;
      throw error;
    }).finally(function () {
      if (state.catalogController === controller) state.catalogController = null;
    });
    state.catalogPromise = tracked;
    return tracked;
  }

  function cancelCatalogRequest() {
    abortRequest(state.catalogController);
    state.catalogController = null;
    if (!state.catalog) state.catalogPromise = null;
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
        if (context && context.map) return resolve(context);
        if (Date.now() - started > 15000) return reject(new Error("The map was not ready for Animal Mutilation Reports."));
        window.setTimeout(poll, 60);
      }
      poll();
    });
  }

  function ensureMapLayer(context) {
    if (state.map === context.map && state.layer) {
      installMapHitHandler();
      return;
    }
    removeMapHitHandler();
    state.map = context.map;
    if (!state.map.getPane("animalMutilationPane")) {
      state.map.createPane("animalMutilationPane");
      const pane = state.map.getPane("animalMutilationPane");
      pane.style.zIndex = "608";
      pane.style.pointerEvents = "none";
    }
    state.layer = window.L.layerGroup();
    installMapHitHandler();
  }

  function viewKey(context) {
    return [
      context.timeRangeStartOrdinal, context.timeRangeEndOrdinal,
      context.timeRangeIsAllTime ? 1 : 0,
      context.hideLowPrecisionCoordinates ? 1 : 0,
      context.hideNonExactDates ? 1 : 0,
      context.filterGeneration,
    ].join("|");
  }

  function pointMatches(row, context) {
    if (context.hideLowPrecisionCoordinates) return false;
    if (context.hideNonExactDates && Number(row[ROW.datePrecision]) !== 0) return false;
    if (row[ROW.start] == null || row[ROW.end] == null) return Boolean(context.timeRangeIsAllTime);
    const start = Number(row[ROW.start]);
    const end = Number(row[ROW.end]);
    if (Number.isFinite(Number(context.timeRangeStartOrdinal)) && end < Number(context.timeRangeStartOrdinal)) return false;
    if (Number.isFinite(Number(context.timeRangeEndOrdinal)) && start > Number(context.timeRangeEndOrdinal)) return false;
    return true;
  }

  function markerForRows(rows) {
    const representative = rows[0];
    const radius = 6.5 + Math.min(5, Math.log2(Math.max(1, rows.length)) * 1.6);
    const iconSize = Math.round((radius + 4) * 2);
    const icon = window.L.divIcon({
      className: "animal-mutilation-map-icon",
      html: '<span class="animal-mutilation-map-cow" aria-hidden="true"></span>',
      iconSize: [iconSize, iconSize],
      iconAnchor: [iconSize / 2, iconSize / 2],
    });
    const marker = window.L.marker([representative[ROW.lat], representative[ROW.lon]], {
      pane: "animalMutilationPane",
      icon: icon,
      opacity: 0.94,
      interactive: false,
      keyboard: false,
      bubblingMouseEvents: false,
      animalHitRadius: radius,
    });
    marker._animalRows = rows.slice();
    marker.options.animalStackCount = rows.length;
    return marker;
  }

  function render(context, force) {
    if (!state.enabled || !state.points || !state.layer) return;
    const key = viewKey(context);
    if (!force && key === state.lastViewKey) return;
    state.lastViewKey = key;
    state.layer.clearLayers();
    state.markers = [];
    let visibleRecords = 0;
    state.rowsByPosition.forEach(function (rows) {
      const visibleRows = rows.filter(function (row) { return pointMatches(row, context); });
      if (!visibleRows.length) return;
      visibleRecords += visibleRows.length;
      const marker = markerForRows(visibleRows);
      state.markers.push(marker);
      state.layer.addLayer(marker);
    });
    if (!state.map.hasLayer(state.layer)) state.layer.addTo(state.map);
    state.visibleRecords = visibleRecords;
    state.visiblePositions = state.markers.length;
    if (context.hideLowPrecisionCoordinates) {
      setStatus("No animal reports remain: this dataset has zero reviewed exact coordinates. Clear Exact coordinates only to show generalized locations.");
    } else if (!visibleRecords) {
      setStatus("No mapped animal reports match the current date filters. Undated reports appear only in All Time; all reports remain available in Browse all reports.");
    } else {
      setStatus(
        plural(visibleRecords, "mapped report", "mapped reports") + " at " +
        plural(state.visiblePositions, "generalized position", "generalized positions") +
        ". " + plural(state.manifest.counts.unmapped, "unmapped report", "unmapped reports") +
        " remain available in Browse all reports."
      );
    }
    dispatchState();
  }

  function markerAtContainerPoint(point) {
    let best = null;
    let bestDistance = Number.POSITIVE_INFINITY;
    state.markers.forEach(function (marker) {
      const markerPoint = state.map.latLngToContainerPoint(marker.getLatLng());
      const dx = Number(markerPoint.x) - Number(point.x);
      const dy = Number(markerPoint.y) - Number(point.y);
      const distance = Math.sqrt(dx * dx + dy * dy);
      const hitRadius = Number(marker.options.animalHitRadius || 10) + 6;
      if (distance <= hitRadius && distance < bestDistance) {
        best = marker;
        bestDistance = distance;
      }
    });
    return best;
  }

  function installMapHitHandler() {
    if (!state.map || state.markerHitHandler) return;
    const container = state.map.getContainer();
    if (!container || typeof container.addEventListener !== "function") return;
    state.markerHitContainer = container;
    state.markerHitHandler = function (event) {
      if (!state.enabled || !state.markers.length) return;
      const target = event.target;
      if (target && typeof target.closest === "function" && target.closest(
        "#area-selection-draw-surface, .leaflet-control, .animal-mutilation-detail-panel, .animal-mutilation-browser, button, input, select, a"
      )) return;
      const marker = markerAtContainerPoint(state.map.mouseEventToContainerPoint(event));
      if (!marker) return;
      event.preventDefault();
      event.stopPropagation();
      if (typeof event.stopImmediatePropagation === "function") event.stopImmediatePropagation();
      openPosition(marker._animalRows || [], container).catch(reportError);
    };
    container.addEventListener("click", state.markerHitHandler, true);
  }

  function removeMapHitHandler() {
    if (state.markerHitContainer && state.markerHitHandler && typeof state.markerHitContainer.removeEventListener === "function") {
      state.markerHitContainer.removeEventListener("click", state.markerHitHandler, true);
    }
    state.markerHitContainer = null;
    state.markerHitHandler = null;
  }

  function detailDeclaration(chunkNumber) {
    const files = state.manifest && state.manifest.details ? state.manifest.details.files || [] : [];
    return files[Number(chunkNumber)] || null;
  }

  function loadDetailChunk(chunkNumber) {
    const key = Number(chunkNumber);
    if (state.detailChunkCache.has(key)) return Promise.resolve(state.detailChunkCache.get(key));
    if (state.detailChunkPromises.has(key)) return state.detailChunkPromises.get(key);
    const declaration = detailDeclaration(key);
    if (!declaration) return Promise.reject(new Error("Animal report detail chunk is not declared."));
    const controller = createRequestController();
    state.detailChunkControllers.set(key, controller);
    const tracked = readPayload(declaration, "Animal report detail", controller && controller.signal).then(function (records) {
      if (!records || typeof records !== "object" || Object.keys(records).length !== Number(declaration.recordCount)) {
        throw new Error("Animal report detail chunk failed its record-count check.");
      }
      throwIfAborted(controller && controller.signal);
      state.detailChunkCache.set(key, records);
      while (state.detailChunkCache.size > MAX_DETAIL_CHUNKS) {
        state.detailChunkCache.delete(state.detailChunkCache.keys().next().value);
      }
      return records;
    }).finally(function () {
      if (state.detailChunkPromises.get(key) === tracked) state.detailChunkPromises.delete(key);
      if (state.detailChunkControllers.get(key) === controller) state.detailChunkControllers.delete(key);
    });
    state.detailChunkPromises.set(key, tracked);
    return tracked;
  }

  function cancelDetailRequests(exceptChunk) {
    state.detailChunkControllers.forEach(function (controller, key) {
      if (exceptChunk == null || Number(key) !== Number(exceptChunk)) abortRequest(controller);
    });
    state.detailChunkPromises.forEach(function (promise, key) {
      if (exceptChunk == null || Number(key) !== Number(exceptChunk)) {
        state.detailChunkPromises.delete(key);
        state.detailChunkControllers.delete(key);
      }
    });
  }

  function formatDate(detail) {
    if (!detail.dateStart) return "Undated";
    if (detail.dateStart === detail.dateEnd) return detail.dateStart + " (exact day)";
    return detail.dateStart + " to " + detail.dateEnd + " (" + String(detail.datePrecision || "uncertain").replaceAll("_", " ") + ")";
  }

  function formatLocation(detail) {
    if (detail.privacyLevel === "internal_only") return "Withheld for privacy";
    if (!Array.isArray(detail.coordinates)) {
      return detail.location
        ? "No public map point supplied · Generalized place label: " + detail.location
        : "No public map point supplied";
    }
    return detail.location ? "Generalized location: " + detail.location : "Generalized location (place label not supplied)";
  }

  function sourceReferenceHtml(ref) {
    const sourceId = escapeHtml(ref && ref.sourceId ? ref.sourceId : "Source reference");
    const url = safePublicHttpUrl(ref && ref.url);
    const label = url
      ? '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">' + sourceId + "</a>"
      : sourceId;
    const locator = ref && ref.locator ? " — " + escapeHtml(ref.locator) : "";
    const hash = ref && ref.sourceHash ? '<code class="animal-hash">' + escapeHtml(ref.sourceHash) + "</code>" : "";
    return "<li>" + label + locator + (hash ? "<br>SHA-256: " + hash : "") + "</li>";
  }

  function renderDetail(detail, positionRows) {
    if (!detailPanel || !detailBody) return;
    const names = (detail.commonNames || []).map(function (value) { return String(value).replaceAll("_", " "); });
    const excerpts = (detail.evidenceExcerpts || []).length
      ? '<ul class="animal-detail-excerpts">' + detail.evidenceExcerpts.map(function (text) {
        return "<li>" + escapeHtml(text) + "</li>";
      }).join("") + "</ul>"
      : '<p class="animal-detail-muted">No public evidence excerpt was supplied.</p>';
    const refs = (detail.sourceRefs || []).length
      ? '<ul class="animal-detail-sources">' + detail.sourceRefs.map(sourceReferenceHtml).join("") + "</ul>"
      : '<p class="animal-detail-muted">No public source link was supplied; the lineage identifiers remain available below.</p>';
    const sharedRows = (positionRows || []).filter(function (row) { return String(row[ROW.id]) !== String(detail.id); });
    const shared = sharedRows.length
      ? '<div class="animal-detail-shared"><strong>' + escapeHtml(String(positionRows.length)) +
        " reports share this generalized position</strong><div>" + sharedRows.map(function (row) {
          return '<button class="secondary-button" type="button" data-animal-record-id="' + escapeHtml(row[ROW.id]) +
            '" data-animal-detail-chunk="' + escapeHtml(row[ROW.chunk]) + '">' + escapeHtml(row[ROW.id]) + "</button>";
        }).join("") + "</div></div>"
      : "";
    detailBody.innerHTML = [
      '<p class="animal-detail-eyebrow">Animal Mutilation Reports · context only</p>',
      "<h3>Reported animal mutilation — unreviewed</h3>",
      '<p class="animal-report-title"><strong>Report label:</strong> ' + escapeHtml(detail.title || detail.claimLabel || "Reported animal mutilation") + "</p>",
      '<p class="animal-content-warning"><strong>Content warning:</strong> ' + escapeHtml(detail.contentWarning || "Animal-death descriptions may be disturbing.") + "</p>",
      '<p class="animal-science-warning"><strong>Reported, unreviewed:</strong> This source report has not been scientifically verified. The layer asserts no UFO cause or other cause and cannot enter craft traces, relationships, chronology, or playback.</p>',
      '<dl class="animal-detail-grid">',
      "<div><dt>Status</dt><dd>" + escapeHtml(detail.status) + "</dd></div>",
      "<div><dt>Date</dt><dd>" + escapeHtml(formatDate(detail)) + "</dd></div>",
      "<div><dt>Location</dt><dd>" + escapeHtml(formatLocation(detail)) + "</dd></div>",
      "<div><dt>Species</dt><dd>" + escapeHtml(names.length ? names.join(", ") : "Unknown") + "</dd></div>",
      "<div><dt>Location precision</dt><dd>" + escapeHtml(detail.locationPrecision || "unknown") + "</dd></div>",
      "<div><dt>Privacy</dt><dd>" + escapeHtml(detail.privacyLevel || "unknown") + "</dd></div>",
      "</dl>",
      "<p>" + escapeHtml(detail.summary || "") + "</p>",
      "<h4>Public report excerpts</h4>", excerpts,
      "<h4>Provenance</h4>", refs,
      '<dl class="animal-detail-grid animal-provenance-grid">',
      "<div><dt>Stable report ID</dt><dd><code>" + escapeHtml(detail.id) + "</code></dd></div>",
      "<div><dt>Source incident ID</dt><dd><code>" + escapeHtml(detail.sourceIncidentId) + "</code></dd></div>",
      '<div><dt>Source incident SHA-256</dt><dd><code class="animal-hash">' + escapeHtml(detail.sourceIncidentSha256) + "</code></dd></div>",
      "<div><dt>Causality</dt><dd>not_asserted</dd></div>",
      "</dl>", shared,
    ].join("");
    detailPanel.hidden = false;
    detailPanel.setAttribute("aria-hidden", "false");
    if (detailClose && typeof detailClose.focus === "function") detailClose.focus();
  }

  function closeDetail(options) {
    state.detailRequestGeneration += 1;
    cancelDetailRequests();
    state.activePositionRows = [];
    if (detailPanel) {
      detailPanel.hidden = true;
      detailPanel.setAttribute("aria-hidden", "true");
    }
    if (detailBody) detailBody.innerHTML = "";
    const restoreFocus = !options || options.restoreFocus !== false;
    const restoreBrowser = restoreFocus && state.detailRestoresBrowser;
    const returnFocus = state.detailReturnFocus;
    state.detailRestoresBrowser = false;
    state.detailReturnFocus = null;
    if (restoreBrowser && browser) {
      state.browserOpen = true;
      state.browserRequestGeneration += 1;
      browser.hidden = false;
      browser.setAttribute("aria-hidden", "false");
    }
    if (restoreFocus) {
      const target = returnFocus && typeof returnFocus.focus === "function"
        ? returnFocus
        : (restoreBrowser ? browserSearch : null);
      if (target && typeof target.focus === "function") target.focus();
    }
  }

  function openDetailById(recordId, chunkNumber, positionRows, returnFocus, restoreBrowser) {
    const chunkKey = Number(chunkNumber);
    const generation = ++state.detailRequestGeneration;
    cancelDetailRequests(chunkKey);
    if (returnFocus) state.detailReturnFocus = returnFocus;
    if (restoreBrowser !== undefined) state.detailRestoresBrowser = Boolean(restoreBrowser);
    if (detailPanel) {
      detailPanel.hidden = false;
      detailPanel.setAttribute("aria-hidden", "false");
    }
    if (detailBody) detailBody.textContent = "Loading report details…";
    if (detailClose && typeof detailClose.focus === "function") detailClose.focus();
    return loadDetailChunk(chunkKey).then(function (records) {
      if (generation !== state.detailRequestGeneration) return null;
      const detail = records[String(recordId)];
      if (!detail) throw new Error("Animal report detail was not found in its declared chunk.");
      state.activePositionRows = positionRows || [];
      renderDetail(detail, state.activePositionRows);
      return detail;
    }).catch(function (error) {
      if (isAbortError(error) || generation !== state.detailRequestGeneration) return null;
      closeDetail();
      throw error;
    });
  }

  function openPosition(rows, returnFocus) {
    if (!rows.length) return Promise.resolve(null);
    const sorted = rows.slice().sort(comparePointRows);
    return openDetailById(sorted[0][ROW.id], sorted[0][ROW.chunk], sorted, returnFocus, false);
  }

  function reportError(error) {
    setStatus(error && error.message ? error.message : String(error), true);
    console.error(error);
  }

  function populateSpeciesFilter() {
    if (!browserSpecies || !state.manifest || browserSpecies.dataset.populated === "true") return;
    const codes = state.manifest.codes && state.manifest.codes.speciesGroup || {};
    Object.keys(codes).sort(function (left, right) { return Number(codes[left]) - Number(codes[right]); }).forEach(function (name) {
      const option = document.createElement("option");
      option.value = String(codes[name]);
      option.textContent = name.replaceAll("_", " ");
      browserSpecies.appendChild(option);
    });
    browserSpecies.dataset.populated = "true";
  }

  function catalogInterval(row) {
    return [civilOrdinal(row[CATALOG.dateStart]), civilOrdinal(row[CATALOG.dateEnd])];
  }

  function catalogMatches(row) {
    const query = String(browserSearch && browserSearch.value || "").trim().toLowerCase();
    if (query && String(row[CATALOG.searchText] || "").indexOf(query) === -1) return false;
    const species = String(browserSpecies && browserSpecies.value || "all");
    if (species !== "all" && !(row[CATALOG.species] || []).some(function (code) { return String(code) === species; })) return false;
    const mapped = String(browserMapped && browserMapped.value || "all");
    if (mapped === "mapped" && !row[CATALOG.mapped]) return false;
    if (mapped === "unmapped" && row[CATALOG.mapped]) return false;
    const dateScope = String(browserDateScope && browserDateScope.value || "all_time");
    const interval = catalogInterval(row);
    const dated = interval[0] != null && interval[1] != null;
    if (dateScope === "exact_day" && (!dated || Number(row[CATALOG.datePrecision]) !== 0)) return false;
    if (dateScope === "dated" && !dated) return false;
    if (dateScope === "undated" && dated) return false;
    const selectedStart = civilOrdinal(browserDateStart && browserDateStart.value);
    const selectedEnd = civilOrdinal(browserDateEnd && browserDateEnd.value);
    if (selectedStart != null || selectedEnd != null) {
      if (!dated) return false;
      if (selectedStart != null && interval[1] < selectedStart) return false;
      if (selectedEnd != null && interval[0] > selectedEnd) return false;
    }
    return true;
  }

  function catalogDateLabel(row) {
    if (!row[CATALOG.dateStart]) return "Undated";
    if (row[CATALOG.dateStart] === row[CATALOG.dateEnd]) return String(row[CATALOG.dateStart]);
    return String(row[CATALOG.dateStart]) + " – " + String(row[CATALOG.dateEnd]);
  }

  function renderBrowserResults(resetLimit) {
    if (!state.catalog || !browserResults) return;
    if (resetLimit) state.browserRenderLimit = BROWSER_PAGE_SIZE;
    state.browserFilteredRows = state.catalog.filter(catalogMatches);
    const visible = state.browserFilteredRows.slice(0, state.browserRenderLimit);
    browserResults.innerHTML = visible.map(function (row) {
      const commonNames = (row[CATALOG.commonNames] || []).map(function (value) {
        return String(value).replaceAll("_", " ");
      }).join(", ");
      return '<li><button type="button" class="animal-browser-result" data-animal-record-id="' +
        escapeHtml(row[CATALOG.id]) + '" data-animal-detail-chunk="' + escapeHtml(row[CATALOG.chunk]) + '">' +
        '<span class="animal-browser-result-title">' + escapeHtml(row[CATALOG.title] || "Reported animal mutilation") + "</span>" +
        '<span class="animal-browser-result-meta">' + escapeHtml(catalogDateLabel(row)) + " · " +
        escapeHtml(row[CATALOG.mapped]
          ? "Generalized location: " + (row[CATALOG.location] || "place label not supplied")
          : "No public map point supplied") + " · " +
        escapeHtml(commonNames || "species unknown") + " · " +
        (row[CATALOG.mapped] ? "mapped generalized position" : "unmapped") + "</span></button></li>";
    }).join("");
    if (browserSummary) {
      const scope = String(browserDateScope && browserDateScope.value || "all_time");
      browserSummary.textContent = plural(state.browserFilteredRows.length, "matching report", "matching reports") +
        (scope === "all_time" && !(browserDateStart && browserDateStart.value) && !(browserDateEnd && browserDateEnd.value)
          ? ", including undated reports."
          : ". Undated reports are excluded by the current date filter.");
    }
    if (browserMore) {
      browserMore.hidden = visible.length >= state.browserFilteredRows.length;
      browserMore.textContent = "Show next " + Math.min(BROWSER_PAGE_SIZE, state.browserFilteredRows.length - visible.length) + " reports";
    }
  }

  function resetBrowserFilters() {
    if (browserSearch) browserSearch.value = "";
    if (browserSpecies) browserSpecies.value = "all";
    if (browserMapped) browserMapped.value = "all";
    if (browserDateScope) browserDateScope.value = "all_time";
    if (browserDateStart) browserDateStart.value = "";
    if (browserDateEnd) browserDateEnd.value = "";
    renderBrowserResults(true);
    if (browserSearch && typeof browserSearch.focus === "function") browserSearch.focus();
  }

  function closeBrowser(options) {
    if (!browser) return;
    state.browserOpen = false;
    state.browserRequestGeneration += 1;
    cancelCatalogRequest();
    browser.hidden = true;
    browser.setAttribute("aria-hidden", "true");
    const restore = !options || options.restoreFocus !== false;
    if (restore && state.browserReturnFocus && typeof state.browserReturnFocus.focus === "function") {
      state.browserReturnFocus.focus();
    }
    cancelUnusedManifestRequest();
  }

  function openBrowser(returnFocus) {
    if (!browser) return Promise.reject(new Error("The all-record browser is unavailable."));
    const generation = ++state.browserRequestGeneration;
    state.browserOpen = true;
    state.browserReturnFocus = returnFocus || document.activeElement || browseOpen;
    if (browserSummary) browserSummary.textContent = "Loading all reports…";
    browser.hidden = false;
    browser.setAttribute("aria-hidden", "false");
    const initialFocus = browserSearch || browserClose || browser;
    if (initialFocus && typeof initialFocus.focus === "function") initialFocus.focus();
    return ensureCatalog().then(function () {
      if (generation !== state.browserRequestGeneration || !state.browserOpen) return state.catalog ? state.catalog.length : 0;
      renderBrowserResults(true);
      if (!state.enabled) {
        setStatus(
          plural(state.catalog.length, "report", "reports") +
          " are ready in Browse all reports. The map layer remains off and the point index has not been requested."
        );
      }
      return state.catalog.length;
    }).catch(function (error) {
      if (isAbortError(error) || generation !== state.browserRequestGeneration || !state.browserOpen) return state.catalog ? state.catalog.length : 0;
      closeBrowser({ restoreFocus: true });
      throw error;
    });
  }

  function setEnabled(enabled) {
    const next = Boolean(enabled);
    if (!next) {
      state.enableGeneration += 1;
      state.enabled = false;
      state.loading = false;
      cancelPointsRequest();
      state.lastViewKey = "";
      state.visibleRecords = 0;
      state.visiblePositions = 0;
      if (state.pollTimer) window.clearInterval(state.pollTimer);
      state.pollTimer = null;
      if (state.layer && typeof state.layer.clearLayers === "function") state.layer.clearLayers();
      if (state.map && state.layer && state.map.hasLayer(state.layer)) state.map.removeLayer(state.layer);
      state.markers = [];
      removeMapHitHandler();
      closeDetail({ restoreFocus: false });
      cancelUnusedManifestRequest();
      setToggleState(false, false);
      setStatus("Animal Mutilation Reports are off. Turn the layer on to show generalized positions; all reports remain available through Browse all reports.");
      return Promise.resolve(false);
    }
    if (state.enabled && !state.loading) return Promise.resolve(true);
    const generation = ++state.enableGeneration;
    state.loading = true;
    setToggleState(true, true);
    setStatus("Loading mapped Animal Mutilation Reports…");
    return Promise.all([ensurePoints(), waitForMap()]).then(function (values) {
      if (generation !== state.enableGeneration || !state.loading) return false;
      const context = values[1];
      ensureMapLayer(context);
      state.enabled = true;
      state.loading = false;
      setToggleState(true, false);
      render(context, true);
      if (state.pollTimer) window.clearInterval(state.pollTimer);
      state.pollTimer = window.setInterval(function () {
        if (!state.enabled) return;
        const current = extensionContext();
        if (current && current.map) render(current, false);
      }, POLL_INTERVAL_MS);
      return true;
    }).catch(function (error) {
      if (isAbortError(error) || generation !== state.enableGeneration) return false;
      state.enabled = false;
      state.loading = false;
      setToggleState(false, false);
      reportError(error);
      throw error;
    });
  }

  function openCatalogRecord(recordId, chunkNumber, returnFocus) {
    closeBrowser({ restoreFocus: false });
    return openDetailById(recordId, chunkNumber, [], returnFocus, true);
  }

  [browserSearch, browserSpecies, browserMapped, browserDateScope, browserDateStart, browserDateEnd].forEach(function (control) {
    if (!control) return;
    control.addEventListener(control === browserSearch ? "input" : "change", function () { renderBrowserResults(true); });
  });
  if (browserReset) browserReset.addEventListener("click", resetBrowserFilters);
  if (browserMore) browserMore.addEventListener("click", function () {
    state.browserRenderLimit += BROWSER_PAGE_SIZE;
    renderBrowserResults(false);
  });
  if (browserClose) browserClose.addEventListener("click", function () { closeBrowser(); });
  if (browserResults) browserResults.addEventListener("click", function (event) {
    const button = event.target.closest("[data-animal-record-id]");
    if (!button) return;
    openCatalogRecord(
      button.getAttribute("data-animal-record-id"),
      button.getAttribute("data-animal-detail-chunk"),
      button
    ).catch(reportError);
  });
  if (detailClose) detailClose.addEventListener("click", closeDetail);
  if (detailBody) detailBody.addEventListener("click", function (event) {
    const button = event.target.closest("[data-animal-record-id]");
    if (!button) return;
    openDetailById(
      button.getAttribute("data-animal-record-id"),
      button.getAttribute("data-animal-detail-chunk"),
      state.activePositionRows
    ).catch(reportError);
  });
  if (browser) browser.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeBrowser();
      return;
    }
    if (event.key !== "Tab" || typeof browser.querySelectorAll !== "function") return;
    const focusable = Array.from(browser.querySelectorAll("button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex='0']"))
      .filter(function (element) { return !element.hidden; });
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && detailPanel && !detailPanel.hidden) closeDetail();
  });

  window.UfoAnimalMutilationLayer = Object.freeze({
    setEnabled: setEnabled,
    openBrowser: openBrowser,
    closeBrowser: closeBrowser,
    getStatus: function () {
      return {
        enabled: state.enabled,
        loaded: Boolean(state.manifest && state.points),
        catalogLoaded: Boolean(state.catalog),
        visibleRecords: state.visibleRecords,
        visiblePositions: state.visiblePositions,
        totalRecords: state.manifest ? Number(state.manifest.counts.records) : null,
        mappedRecords: state.manifest ? Number(state.manifest.counts.mapped) : null,
        unmappedRecords: state.manifest ? Number(state.manifest.counts.unmapped) : null,
        detailChunksCached: state.detailChunkCache.size,
        traceEligible: false,
        relationshipsEligible: false,
        chronologyEligible: false,
        playbackEligible: false,
        causality: "not_asserted",
      };
    },
  });
})();
