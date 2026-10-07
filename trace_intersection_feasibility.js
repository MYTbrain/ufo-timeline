(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module && module.exports) module.exports = api;
  if (root) root.TraceIntersectionFeasibility = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const PROFILE_PATHS = Object.freeze({
    buffer1: "./data/trace_intersection_feasibility_v1/strict_25km_7d_buffer1.json",
    buffer5: "./data/trace_intersection_feasibility_v1/strict_25km_7d_buffer5.json",
  });

  const CRAFT_LABELS = Object.freeze({
    all_no_lights: "All recognized craft — lights excluded",
    chevron_boomerang: "Chevron / boomerang",
    cigar_cylinder: "Cigar / cylinder",
    cone: "Cone",
    diamond: "Diamond",
    disc_saucer: "Disc / saucer",
    dumbbell_barbell: "Dumbbell / barbell",
    oval_egg: "Oval / egg",
    rectangle_box: "Rectangle / box",
    sphere_orb: "Sphere / orb",
    teardrop: "Teardrop",
    triangle: "Triangle",
  });

  const METRIC_COPY = Object.freeze({
    lift: {
      title: "Opportunity-normalized lift",
      note: "Lift compares crossings with local connector-pair opportunities. It is a screening statistic, not a formal significance test.",
    },
    raw: {
      title: "Raw interior crossings",
      note: "Raw counts are shown for diagnosis. Dense reporting areas naturally create more opportunities to cross.",
    },
    persistence: {
      title: "Five-year periods represented",
      note: "Period coverage is descriptive. It does not establish that the same object or route recurred.",
    },
    same_craft: {
      title: "Same-craft connector crossings",
      note: "Both intersecting connectors have matching craft types at both of their endpoints.",
    },
    different_craft: {
      title: "Different-craft connector crossings",
      note: "The two intersecting connectors are each homotypic but represent different craft types.",
    },
    mixed: {
      title: "Mixed-endpoint connector crossings",
      note: "At least one connector joins reports with different craft classifications. Full endpoint signatures remain in the inspector.",
    },
    craft: {
      title: "Crossings involving selected craft",
      note: "Craft involvement counts retain a craft anywhere among the four connector endpoints; they are not opportunity-normalized.",
    },
  });

  const SCREENING_RANK = Object.freeze({ descriptive_only: 0, limited_candidate: 1, repeated_candidate: 2 });
  const AXIS_LABELS = Object.freeze({
    north_south: "N–S",
    northeast_southwest: "NE–SW",
    east_west: "E–W",
    northwest_southeast: "NW–SE",
  });

  function formatNumber(value, digits) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "—";
    return numeric.toLocaleString(undefined, { maximumFractionDigits: digits == null ? 1 : digits });
  }

  function humanCraft(value) {
    return CRAFT_LABELS[value] || String(value || "Unknown").replace(/_/g, " ").replace(/\b\w/g, function (letter) {
      return letter.toUpperCase();
    });
  }

  function humanSignature(value) {
    return String(value || "")
      .split(" x ")
      .map(function (connector) {
        return connector.split("+").map(humanCraft).join(" + ");
      })
      .join(" × ");
  }

  function metricValue(cell, metric, craft) {
    if (!cell) return 0;
    if (metric === "raw") return Number(cell.crossings) || 0;
    if (metric === "persistence") return Number(cell.fiveYearBandCount) || 0;
    if (metric === "same_craft") return Number(cell.sameCraftCrossings) || 0;
    if (metric === "different_craft") return Number(cell.differentCraftCrossings) || 0;
    if (metric === "mixed") return Number(cell.mixedEndpointCraftCrossings) || 0;
    if (metric === "craft") {
      if (craft === "all_no_lights") return Number(cell.crossings) || 0;
      return Number(cell.craftInvolvementCounts && cell.craftInvolvementCounts[craft]) || 0;
    }
    return Number(cell.opportunityNormalizedLift) || 0;
  }

  function screeningTierRank(value) {
    return Object.prototype.hasOwnProperty.call(SCREENING_RANK, value) ? SCREENING_RANK[value] : -1;
  }

  function filterCells(cells, options) {
    const config = options || {};
    const minimumRank = config.minimumTier === "all" ? -1 : screeningTierRank(config.minimumTier);
    return (Array.isArray(cells) ? cells : []).filter(function (cell) {
      if (screeningTierRank(cell.screeningTier) < minimumRank) return false;
      return metricValue(cell, config.metric || "lift", config.craft || "triangle") > 0;
    });
  }

  function quantile(values, probability) {
    if (!values.length) return 0;
    const sorted = values.slice().sort(function (a, b) { return a - b; });
    const index = Math.min(sorted.length - 1, Math.max(0, Math.floor((sorted.length - 1) * probability)));
    return sorted[index];
  }

  function metricScale(cells, metric, craft) {
    const values = cells.map(function (cell) { return metricValue(cell, metric, craft); }).filter(function (value) { return value > 0; });
    return {
      minimum: values.length ? Math.min.apply(null, values) : 0,
      maximum: values.length ? quantile(values, 0.95) || Math.max.apply(null, values) : 1,
    };
  }

  function normalizedMetric(value, scale, metric) {
    if (!value) return 0;
    if (metric === "lift") {
      const high = Math.max(1.05, scale.maximum);
      return Math.max(0, Math.min(1, Math.log2(Math.max(1, value)) / Math.log2(high)));
    }
    const high = Math.max(1, scale.maximum);
    return Math.max(0, Math.min(1, Math.log1p(value) / Math.log1p(high)));
  }

  function heatColor(normalized) {
    const t = Math.max(0, Math.min(1, Number(normalized) || 0));
    if (t < 0.34) return "#155f73";
    if (t < 0.67) return "#36d5ad";
    return "#ffdb74";
  }

  function screeningLabel(value) {
    if (value === "repeated_candidate") return "Repeated candidate";
    if (value === "limited_candidate") return "Limited candidate";
    return "Descriptive only";
  }

  function gridLabel(grid) {
    const km2 = Number(grid && grid.actualCellAreaKm2) || 0;
    const mi2 = km2 * 0.386102159;
    return formatNumber(km2, 0) + " km² · " + formatNumber(mi2, 0) + " mi²";
  }

  function rankedEntries(record, limit) {
    return Object.keys(record || {}).map(function (key) {
      return { key: key, value: Number(record[key]) || 0 };
    }).sort(function (a, b) {
      return b.value - a.value || a.key.localeCompare(b.key);
    }).slice(0, limit || 8);
  }

  function rankListHtml(entries, labelFormatter) {
    if (!entries.length) return '<p class="small-note">No supported entries in this cell.</p>';
    const max = Math.max.apply(null, entries.map(function (entry) { return entry.value; })) || 1;
    return '<div class="rank-list">' + entries.map(function (entry) {
      return '<div class="rank-row"><span class="rank-label">' + escapeHtml(labelFormatter(entry.key)) + '</span>' +
        '<span class="rank-value">' + formatNumber(entry.value, 0) + '</span>' +
        '<span class="rank-track"><span class="rank-fill" style="width:' + Math.max(3, entry.value / max * 100).toFixed(1) + '%"></span></span></div>';
    }).join("") + '</div>';
  }

  function axisTableHtml(craftAxisCounts) {
    const rows = Object.keys(craftAxisCounts || {}).map(function (craft) {
      const axes = craftAxisCounts[craft] || {};
      const total = Object.values(axes).reduce(function (sum, value) {
        return sum + Number(value || 0);
      }, 0);
      return { craft: craft, axes: axes, total: total };
    }).sort(function (left, right) {
      return right.total - left.total || humanCraft(left.craft).localeCompare(humanCraft(right.craft));
    }).slice(0, 6);
    if (!rows.length) return '<p class="small-note">No axis summary is available for this cell.</p>';
    const axes = Object.keys(AXIS_LABELS);
    return '<div class="axis-table-wrap"><table class="axis-table"><thead><tr><th>Craft</th>' + axes.map(function (axis) {
      return '<th>' + AXIS_LABELS[axis] + '</th>';
    }).join("") + '</tr></thead><tbody>' + rows.map(function (row) {
      return '<tr><th>' + escapeHtml(humanCraft(row.craft)) + '</th>' + axes.map(function (axis) {
        return '<td>' + formatNumber(row.axes[axis] || 0, 0) + '</td>';
      }).join("") + '</tr>';
    }).join("") + '</tbody></table></div>';
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function initBrowser() {
    const mapElement = document.querySelector("#intersection-map");
    if (!mapElement || typeof L === "undefined") return;

    const elements = {
      loadStatus: document.querySelector("#load-status"),
      profile: document.querySelector("#profile-select"),
      resolution: document.querySelector("#resolution-select"),
      metric: document.querySelector("#metric-select"),
      craftField: document.querySelector("#craft-field"),
      craft: document.querySelector("#craft-select"),
      support: document.querySelector("#support-select"),
      summary: document.querySelector("#summary-cards"),
      legendTitle: document.querySelector("#legend-title"),
      legendRange: document.querySelector("#legend-range"),
      legendNote: document.querySelector("#legend-note"),
      inspector: document.querySelector("#cell-inspector"),
    };
    const state = {
      profiles: {},
      layer: null,
      selectedCellId: "",
      map: L.map(mapElement, { worldCopyJump: true, minZoom: 2 }).setView([31, -28], 2),
    };

    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png", {
      subdomains: "abcd",
      maxZoom: 18,
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    }).addTo(state.map);

    function currentProfile() {
      return state.profiles[elements.profile.value] || null;
    }

    function currentGrid() {
      const profile = currentProfile();
      return profile && profile.grids ? profile.grids[elements.resolution.value] : null;
    }

    function populateControls() {
      const profile = currentProfile();
      const priorResolution = elements.resolution.value;
      elements.resolution.innerHTML = "";
      Object.keys(profile.grids).sort(function (left, right) {
        return profile.grids[right].actualCellAreaKm2 - profile.grids[left].actualCellAreaKm2;
      }).forEach(function (key) {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = gridLabel(profile.grids[key]);
        if (key === priorResolution) option.selected = true;
        elements.resolution.append(option);
      });
      elements.resolution.value = priorResolution && profile.grids[priorResolution]
        ? priorResolution
        : (profile.grids.equal_area_259_km2 ? "equal_area_259_km2" : Object.keys(profile.grids)[0]);

      const crafts = Object.keys(profile.connectors.craftClassCounts || {}).filter(function (craft) {
        return craft !== "mixed_endpoint_types";
      }).sort(function (left, right) {
        return humanCraft(left).localeCompare(humanCraft(right));
      });
      elements.craft.innerHTML = '<option value="all_no_lights">All recognized craft — lights excluded</option>' + crafts.map(function (craft) {
        return '<option value="' + escapeHtml(craft) + '">' + escapeHtml(humanCraft(craft)) + '</option>';
      }).join("");
      elements.craft.value = "all_no_lights";
    }

    function renderSummary(grid, visibleCells) {
      const profile = currentProfile();
      elements.summary.innerHTML = [
        [profile.connectors.count, "qualified connectors", ""],
        [grid.totalCrossings, "proper interior crossings", ""],
        [visibleCells.length, "visible crossing cells", ""],
        [profile.parameters.endpointBufferKm, "endpoint buffer", " km"],
      ].map(function (item) {
        return '<div class="summary-card"><strong>' + formatNumber(item[0], 1) + escapeHtml(item[2]) + '</strong><span>' + escapeHtml(item[1]) + '</span></div>';
      }).join("");
    }

    function renderLegend(cells, scale) {
      const metric = elements.metric.value;
      const copy = METRIC_COPY[metric] || METRIC_COPY.lift;
      elements.legendTitle.textContent = metric === "craft" ? copy.title + ": " + humanCraft(elements.craft.value) : copy.title;
      elements.legendRange.textContent = formatNumber(scale.minimum, metric === "lift" ? 2 : 0) + "–" + formatNumber(scale.maximum, metric === "lift" ? 2 : 0);
      elements.legendNote.textContent = copy.note + (cells.length ? " The upper color bound uses the visible-cell 95th percentile." : "");
    }

    function matchingSensitivityCell(cell) {
      const alternateKey = elements.profile.value === "buffer1" ? "buffer5" : "buffer1";
      const alternate = state.profiles[alternateKey];
      if (!alternate || !alternate.grids[elements.resolution.value]) return null;
      return alternate.grids[elements.resolution.value].cells.find(function (candidate) {
        return candidate.cellId === cell.cellId;
      }) || null;
    }

    function renderInspector(cell) {
      state.selectedCellId = cell.cellId;
      const alternate = matchingSensitivityCell(cell);
      const oneKmCrossings = elements.profile.value === "buffer1" ? cell.crossings : (alternate ? alternate.crossings : 0);
      const fiveKmCrossings = elements.profile.value === "buffer5" ? cell.crossings : (alternate ? alternate.crossings : 0);
      const survival = oneKmCrossings ? fiveKmCrossings / oneKmCrossings * 100 : 0;
      const pairEntries = rankedEntries(cell.craftPairCounts, 8);
      const craftEntries = rankedEntries(cell.craftInvolvementCounts, 8);
      const angleEntries = rankedEntries(cell.angleCounts, 3);
      const examples = (cell.examples || []).slice(0, 6);
      elements.inspector.innerHTML =
        '<div class="inspector-title-row"><div><p class="eyebrow">Selected cell</p><h2>' + escapeHtml(cell.cellId) + '</h2></div><span class="cell-badge">' + escapeHtml(screeningLabel(cell.screeningTier)) + '</span></div>' +
        '<p class="inspector-location">Center ' + formatNumber(cell.center.lat, 3) + '°, ' + formatNumber(cell.center.lon, 3) + '°</p>' +
        '<div class="inspector-metrics">' +
          '<div class="metric-card"><strong>' + formatNumber(cell.crossings, 0) + '</strong><span>proper crossings</span></div>' +
          '<div class="metric-card"><strong>' + formatNumber(cell.opportunityNormalizedLift, 2) + '×</strong><span>opportunity-normalized lift</span></div>' +
          '<div class="metric-card"><strong>' + formatNumber(cell.uniqueCrossingConnectors, 0) + '</strong><span>unique crossing connectors</span></div>' +
          '<div class="metric-card"><strong>' + formatNumber(cell.fiveYearBandCount, 0) + '</strong><span>five-year periods represented</span></div>' +
        '</div>' +
        '<p class="sensitivity-callout"><strong>Endpoint sensitivity:</strong> ' + formatNumber(oneKmCrossings, 0) + ' crossings after 1 km exclusion; ' + formatNumber(fiveKmCrossings, 0) + ' after 5 km (' + formatNumber(survival, 1) + '% retained).</p>' +
        '<section class="inspector-section"><h3>Craft involvement</h3>' + rankListHtml(craftEntries, humanCraft) + '</section>' +
        '<section class="inspector-section"><h3>Undirected connector axes by craft</h3><p class="small-note">Counts are unique crossing connectors. Mixed-endpoint connectors count toward both endpoint crafts. Axes do not imply heading.</p>' + axisTableHtml(cell.craftAxisConnectorCounts) + '</section>' +
        '<section class="inspector-section"><h3>Connector craft signatures</h3><p class="small-note">A plus sign joins the two endpoint classifications of one connector; × separates the two intersecting connectors.</p>' + rankListHtml(pairEntries, humanSignature) + '</section>' +
        '<section class="inspector-section"><h3>Crossing angles</h3>' + rankListHtml(angleEntries, function (value) { return value.replace(/_/g, "–") + "°"; }) + '</section>' +
        '<section class="inspector-section"><h3>Concentration checks</h3><div class="inspector-metrics">' +
          '<div class="metric-card"><strong>' + formatNumber(cell.dominantConnectorShare * 100, 1) + '%</strong><span>largest one-connector share</span></div>' +
          '<div class="metric-card"><strong>' + formatNumber(cell.sourceCount, 0) + '</strong><span>qualified source collections</span></div>' +
          '<div class="metric-card"><strong>' + formatNumber(cell.sameFiveYearBandCrossings, 0) + '</strong><span>same-period crossings</span></div>' +
          '<div class="metric-card"><strong>' + formatNumber(cell.differentCraftCrossings, 0) + '</strong><span>homotypic cross-craft crossings</span></div>' +
          '<div class="metric-card"><strong>' + formatNumber(cell.mixedEndpointCraftCrossings, 0) + '</strong><span>mixed-endpoint crossings</span></div>' +
        '</div></section>' +
        '<section class="inspector-section"><h3>Bounded examples</h3><div class="example-list">' + examples.map(function (example) {
          return '<div class="example-row"><strong>' + escapeHtml(humanSignature(example.craftPair)) + '</strong>' +
            formatNumber(example.lat, 3) + '°, ' + formatNumber(example.lon, 3) + '° · ' + formatNumber(example.angleDegrees, 1) + '° crossing angle' +
            (example.sameFiveYearBand ? ' · same five-year period' : '') + '</div>';
        }).join("") + '</div></section>';
    }

    function renderEmptyInspector() {
      elements.inspector.innerHTML =
        '<div class="empty-inspector"><p class="eyebrow">Cell inspector</p><h2>Select a hotspot</h2>' +
        '<p>Choose a cell to compare raw density with opportunity-normalized lift, endpoint-buffer sensitivity, craft signatures, temporal recurrence, and connector dominance.</p></div>';
    }

    function renderMap() {
      const grid = currentGrid();
      if (!grid) return;
      const metric = elements.metric.value;
      const craft = elements.craft.value;
      elements.craftField.hidden = metric !== "craft";
      const visibleCells = filterCells(grid.cells, {
        metric: metric,
        craft: craft,
        minimumTier: elements.support.value,
      });
      const scale = metricScale(visibleCells, metric, craft);
      if (state.layer) state.map.removeLayer(state.layer);
      state.layer = L.layerGroup().addTo(state.map);
      visibleCells.forEach(function (cell) {
        const value = metricValue(cell, metric, craft);
        const normalized = normalizedMetric(value, scale, metric);
        const bounds = [[cell.bounds.south, cell.bounds.west], [cell.bounds.north, cell.bounds.east]];
        const selected = cell.cellId === state.selectedCellId;
        const rectangle = L.rectangle(bounds, {
          className: "intersection-cell",
          color: selected ? "#ffffff" : "#8fffe0",
          weight: selected ? 2.4 : 0.65,
          opacity: selected ? 1 : 0.64,
          fillColor: heatColor(normalized),
          fillOpacity: 0.18 + normalized * 0.68,
        });
        rectangle.bindTooltip(
          '<strong>' + formatNumber(value, metric === "lift" ? 2 : 0) + '</strong> · ' + escapeHtml(METRIC_COPY[metric].title) +
          '<br>' + formatNumber(cell.crossings, 0) + ' raw crossings · ' + formatNumber(cell.opportunityNormalizedLift, 2) + '× lift',
          { sticky: true }
        );
        function selectCell() {
          renderInspector(cell);
          renderMap();
        }
        rectangle.on("click", selectCell);
        rectangle.addTo(state.layer);
        const path = rectangle.getElement();
        if (path) {
          path.dataset.cellId = cell.cellId;
          path.setAttribute("role", "button");
          path.setAttribute("tabindex", "0");
          path.setAttribute("aria-label", "Inspect crossing cell " + cell.cellId);
          path.addEventListener("keydown", function (event) {
            if (event.key !== "Enter" && event.key !== " ") return;
            event.preventDefault();
            selectCell();
          });
        }
      });
      renderSummary(grid, visibleCells);
      renderLegend(visibleCells, scale);
    }

    [elements.profile, elements.resolution, elements.metric, elements.craft, elements.support].forEach(function (element) {
      element.addEventListener("change", function () {
        if (element === elements.profile) populateControls();
        state.selectedCellId = "";
        renderEmptyInspector();
        renderMap();
      });
    });

    Promise.all(Object.keys(PROFILE_PATHS).map(function (key) {
      return fetch(PROFILE_PATHS[key], { cache: "no-store" }).then(function (response) {
        if (!response.ok) throw new Error("Failed to load " + PROFILE_PATHS[key] + " (" + response.status + ")");
        return response.json();
      }).then(function (payload) {
        state.profiles[key] = payload;
      });
    })).then(function () {
      elements.loadStatus.textContent = "Ready";
      populateControls();
      renderMap();
      window.setTimeout(function () { state.map.invalidateSize(); }, 80);
    }).catch(function (error) {
      elements.loadStatus.textContent = "Load failed";
      elements.loadStatus.classList.add("is-error");
      elements.inspector.innerHTML = '<div class="empty-inspector"><h2>Prototype data could not load</h2><p>' + escapeHtml(error && error.message ? error.message : error) + '</p></div>';
      console.error(error);
    });
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initBrowser);
    else initBrowser();
  }

  return {
    CRAFT_LABELS: CRAFT_LABELS,
    filterCells: filterCells,
    heatColor: heatColor,
    humanCraft: humanCraft,
    humanSignature: humanSignature,
    metricScale: metricScale,
    metricValue: metricValue,
    normalizedMetric: normalizedMetric,
    screeningTierRank: screeningTierRank,
  };
});
