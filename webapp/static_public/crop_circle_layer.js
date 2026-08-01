(function () {
  "use strict";

  const MANIFEST_URL = "./data/crop_circles/manifest.json";
  const POLL_INTERVAL_MS = 250;
  const MAX_DETAIL_CHUNKS = 5;
  const CROP_COLOR = "#c34cff";
  const CROP_OUTLINE = "#74259a";
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
    manifest: null,
    points: null,
    map: null,
    renderer: null,
    layer: null,
    markerById: new Map(),
    detailChunkCache: new Map(),
    activeDetail: null,
    activeDiagramIndex: 0,
    lastViewKey: "",
    pollTimer: null,
  };

  const button = document.querySelector("#overlay-crop-circles");
  const status = document.querySelector("#crop-circle-status");
  const panel = document.querySelector("#crop-circle-detail-panel");
  const panelBody = document.querySelector("#crop-circle-detail-body");
  const panelClose = document.querySelector("#crop-circle-detail-close");

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
      const url = new URL(String(value || ""), document.baseURI);
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
  }

  async function readJson(url, compressed) {
    const response = await fetch(url, { cache: "force-cache" });
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

  async function ensureData() {
    if (state.manifest && state.points) return;
    const manifest = await readJson(new URL(MANIFEST_URL, document.baseURI), false);
    if (!manifest || manifest.schemaVersion !== 1 || !manifest.points) {
      throw new Error("Crop-circle manifest is incompatible with this app release.");
    }
    state.manifest = manifest;
    const pointsUrl = new URL(manifest.points.path, assetBaseUrl());
    const points = await readJson(pointsUrl, true);
    if (!Array.isArray(points) || points.length !== Number(manifest.counts.mapped)) {
      throw new Error("Crop-circle point index failed its record-count check.");
    }
    state.points = points;
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
      state.map.getPane("cropCirclePane").style.zIndex = "465";
    }
    state.renderer = window.L.canvas({ pane: "cropCirclePane", padding: 0.25, tolerance: 8 });
    state.layer = window.L.layerGroup();
  }

  function viewKey(context) {
    return [
      context.timeRangeStartOrdinal,
      context.timeRangeEndOrdinal,
      context.hideLowPrecisionCoordinates ? 1 : 0,
      context.hideNonExactDates ? 1 : 0,
      context.colorMode || "craft_type",
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

  function chronologyColor(row, context) {
    const start = Number(context.timeRangeStartOrdinal);
    const end = Number(context.timeRangeEndOrdinal);
    const ordinal = Number(row[ROW.start]);
    const denominator = Number.isFinite(start) && Number.isFinite(end) && end > start ? end - start : 1;
    const ratio = Math.max(0, Math.min(1, Number.isFinite(ordinal) ? (ordinal - start) / denominator : 0.5));
    const hue = Math.round(205 - (170 * ratio));
    return "hsl(" + hue + " 78% 55%)";
  }

  function markerStyle(row, context) {
    const coordinate = row[ROW.coordinate];
    const chronology = context.colorMode === "chronology";
    const fillColor = chronology ? chronologyColor(row, context) : CROP_COLOR;
    if (coordinate === 0) {
      return { color: chronology ? CROP_OUTLINE : "#5b176f", fillColor, fillOpacity: 0.88, weight: 2.1, radius: 5.2, dashArray: null };
    }
    if (coordinate === 1) {
      return { color: chronology ? CROP_OUTLINE : "#74259a", fillColor, fillOpacity: 0.48, weight: 1.8, radius: 5.4, dashArray: "3 2" };
    }
    return { color: chronology ? CROP_OUTLINE : CROP_COLOR, fillColor, fillOpacity: 0.08, weight: 1.55, radius: 5.1, dashArray: null };
  }

  function markerForRow(row, context) {
    const id = String(row[ROW.id]);
    let marker = state.markerById.get(id);
    const style = markerStyle(row, context);
    if (!marker) {
      marker = window.L.circleMarker([row[ROW.lat], row[ROW.lon]], Object.assign({
        pane: "cropCirclePane",
        renderer: state.renderer,
        interactive: true,
        bubblingMouseEvents: false,
        keyboard: false,
      }, style));
      marker.on("click", function (event) {
        if (event && event.originalEvent) {
          event.originalEvent.stopPropagation();
        }
        openDetailForPoint(row).catch(function (error) {
          showPanelError(error);
          console.error(error);
        });
      });
      state.markerById.set(id, marker);
    } else {
      marker.setStyle(style);
      marker.setRadius(style.radius);
    }
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
    let visible = 0;
    for (const row of state.points) {
      if (!pointMatches(row, context)) continue;
      state.layer.addLayer(markerForRow(row, context));
      visible += 1;
    }
    if (!state.map.hasLayer(state.layer)) state.layer.addTo(state.map);
    const exactNote = context.hideLowPrecisionCoordinates
      ? " Exact-coordinate filtering is active."
      : " Solid = exact field; dashed = candidate field; hollow = locality centroid.";
    setStatus(
      visible.toLocaleString() + " crop-circle locations visible (" +
      state.manifest.counts.events.toLocaleString() + " records total)." + exactNote
    );
  }

  function startPolling() {
    stopPolling();
    state.pollTimer = window.setInterval(function () {
      try {
        renderPoints(false);
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
    if (detail.exactCoordinate) return "Reviewed/corroborated exact field";
    if (detail.markerConfidence === "provisional") return "Provisional candidate field";
    return "Locality centroid — not the formation field";
  }

  function coordinateClass(detail) {
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
    for (const source of detail.sources || []) add(source.name, source.url, source.page ? "Page " + source.page : "");
    for (const url of detail.links || []) add("Source link", url, "");
    for (const image of detail.images || []) add(image.source || "Image source", image.pageUrl, image.rights || "");
    return sources;
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
    const uncertainty = detail.coordinateUncertaintyKm != null
      ? Number(detail.coordinateUncertaintyKm).toLocaleString() + " km estimated coordinate uncertainty"
      : "";
    const morphologyName = diagram ? familyLabel(diagram.family) : "Design not documented";
    const fields = [
      detailField("Crop", detail.crop),
      detailField("Reported size", detail.sizeText || (detail.reportedSizeM != null ? detail.reportedSizeM + " m" : "")),
      detailField("Morphology", morphologyName),
      detailField("Complexity", diagram && diagram.complexity != null ? diagram.complexity + (diagram.complexityTier ? " · " + diagram.complexityTier : "") : ""),
      detailField("Components", diagram && diagram.components),
      detailField("Symmetry", diagram && diagram.symmetryOrder != null ? "Order " + diagram.symmetryOrder : ""),
      detailField("Classification", detail.classification),
      detailField("Source assertions", detail.assertionCount),
    ].join("");

    panelBody.innerHTML =
      '<div class="cc-detail-heading"><div><p class="cc-detail-eyebrow">Crop Circle Atlas</p><h3>' + escapeHtml(detail.location || "Reported crop formation") + '</h3><p>' + escapeHtml(dateLabel(detail)) + '</p></div><span class="cc-coordinate-badge ' + coordinateClass(detail) + '">' + escapeHtml(coordinateLabel(detail)) + "</span></div>" +
      (uncertainty ? '<p class="cc-detail-warning">' + escapeHtml(uncertainty) + "</p>" : "") +
      '<section class="cc-schematic-card">' + tabs + '<div class="cc-schematic" data-cc-schematic>' + renderSchematicSvg(diagram) + '</div><p><strong>Measurement-informed schematic</strong> — an approximate visual derived from catalog morphology, not an exact field diagram or photograph.</p></section>' +
      '<div class="cc-detail-grid">' + fields + "</div>" +
      (detail.description ? '<p class="cc-detail-description">' + escapeHtml(detail.description) + "</p>" : "") +
      (detail.mappingNotes ? '<p class="cc-detail-warning">' + escapeHtml(detail.mappingNotes) + "</p>" : "") +
      imageMarkup +
      '<section class="cc-detail-sources"><h4>Sources and provenance</h4>' + sourceMarkup + "</section>" +
      '<p class="cc-trace-policy">Context only: this record is excluded from UFO travel traces and chronological-hop expansion.</p>';
    panel.hidden = false;
    panel.setAttribute("aria-hidden", "false");
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
    panel.hidden = true;
    panel.setAttribute("aria-hidden", "true");
    state.activeDetail = null;
    state.activeDiagramIndex = 0;
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
    const payload = await readJson(new URL(detailPath, assetBaseUrl()), true);
    state.detailChunkCache.set(chunkNumber, payload);
    while (state.detailChunkCache.size > MAX_DETAIL_CHUNKS) {
      state.detailChunkCache.delete(state.detailChunkCache.keys().next().value);
    }
    return payload;
  }

  async function openDetailForPoint(row) {
    showPanelLoading(row);
    const chunk = await detailChunk(Number(row[ROW.chunk]));
    const detail = chunk[String(row[ROW.id])];
    if (!detail) throw new Error("Crop-circle detail record was not found.");
    state.activeDiagramIndex = 0;
    renderDetail(detail);
  }

  function installPanelInteractions() {
    if (!panel || panel.dataset.cropCircleReady === "1") return;
    panel.dataset.cropCircleReady = "1";
    panelClose.addEventListener("click", closePanel);
    panel.addEventListener("click", function (event) {
      event.stopPropagation();
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
      state.enabled = false;
      stopPolling();
      if (state.map && state.layer && state.map.hasLayer(state.layer)) state.map.removeLayer(state.layer);
      closePanel();
      setButtonState(false, false);
      setStatus("Crop circles are off. The layer adds no startup data requests.");
      return false;
    }
    if (state.loading) return true;
    state.loading = true;
    setButtonState(true, true);
    setStatus("Loading compact crop-circle locations…");
    try {
      const context = await waitForMap();
      await ensureData();
      ensureMapLayer(context);
      installPanelInteractions();
      state.enabled = true;
      state.lastViewKey = "";
      renderPoints(true);
      startPolling();
      setButtonState(true, false);
      return true;
    } catch (error) {
      state.enabled = false;
      setButtonState(false, false);
      setStatus(error && error.message ? error.message : String(error), true);
      throw error;
    } finally {
      state.loading = false;
    }
  }

  window.UfoCropCircleLayer = Object.freeze({
    setEnabled,
    isEnabled: function () { return state.enabled; },
    getStatus: function () {
      return {
        enabled: state.enabled,
        loaded: Boolean(state.points),
        mappedCount: state.points ? state.points.length : 0,
        renderedCount: state.layer && typeof state.layer.getLayers === "function" ? state.layer.getLayers().length : 0,
        cachedDetailChunks: state.detailChunkCache.size,
      };
    },
  });
})();
