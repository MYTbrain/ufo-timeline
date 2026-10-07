(function (root, factory) {
  "use strict";

  const api = factory();
  if (typeof module === "object" && module && module.exports) module.exports = api;
  if (root) root.UfoTraceIntersectionLayer = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const PROFILE_PATHS = Object.freeze({
    buffer1: "./data/trace_intersection_feasibility_v1/strict_25km_7d_buffer1.json",
    buffer5: "./data/trace_intersection_feasibility_v1/strict_25km_7d_buffer5.json",
  });
  const DEFAULT_GRID_KEY = "equal_area_259_km2";
  const DAY_PER_YEAR = 365.2425;
  const FINE_CELL_THRESHOLD_KM2 = 30;
  const FINE_CELL_RECTANGLE_MIN_ZOOM = 7;
  const LIGHT_CRAFT_PATTERN = /(^|_)(light|lights|luminous)(_|$)/i;
  const CRAFT_LABELS = Object.freeze({
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
  const AXIS_LABELS = Object.freeze({
    north_south: "N–S",
    northeast_southwest: "NE–SW",
    east_west: "E–W",
    northwest_southeast: "NW–SE",
  });
  const SUPPORT_RANK = Object.freeze({
    descriptive_only: 0,
    limited_candidate: 1,
    repeated_candidate: 2,
  });

  const decodedPayloadCache = typeof WeakMap === "function" ? new WeakMap() : null;

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function humanCraft(key) {
    const normalized = String(key || "").trim();
    if (CRAFT_LABELS[normalized]) return CRAFT_LABELS[normalized];
    return normalized.replace(/_/g, " ").replace(/\b\w/g, function (letter) {
      return letter.toUpperCase();
    });
  }

  function formatNumber(value, digits) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "—";
    return numeric.toLocaleString(undefined, {
      minimumFractionDigits: digits || 0,
      maximumFractionDigits: digits || 0,
    });
  }

  function schemaIndex(schema) {
    const output = {};
    (schema || []).forEach(function (field, index) {
      output[field] = index;
    });
    return output;
  }

  function decodePayload(payload) {
    if (!payload || typeof payload !== "object") throw new Error("Intersection profile is missing.");
    if (decodedPayloadCache && decodedPayloadCache.has(payload)) return decodedPayloadCache.get(payload);
    const connectorFields = schemaIndex(payload.connectorRecordSchema);
    const crossingFields = schemaIndex(payload.crossingRecordSchema);
    const connectorByIndex = [];
    (payload.connectorRecords || []).forEach(function (record) {
      const connector = {
        index: Number(record[connectorFields.index]),
        eventIds: [
          Number(record[connectorFields.leftEventId]),
          Number(record[connectorFields.rightEventId]),
        ],
        startOrdinal: Number(record[connectorFields.startOrdinal]),
        endOrdinal: Number(record[connectorFields.endOrdinal]),
        midOrdinal: Number(record[connectorFields.midOrdinal]),
        midYear: Number(record[connectorFields.midYear]),
        craftClass: String(record[connectorFields.craftClass] || ""),
        endpointCrafts: Array.isArray(record[connectorFields.endpointCrafts])
          ? record[connectorFields.endpointCrafts].map(String)
          : [],
        axis: String(record[connectorFields.axis] || ""),
        sources: Array.isArray(record[connectorFields.sources]) ? record[connectorFields.sources].map(String) : [],
        timeBands: Array.isArray(record[connectorFields.timeBands])
          ? record[connectorFields.timeBands].map(Number)
          : [],
      };
      connectorByIndex[connector.index] = connector;
    });
    const crossings = (payload.crossingRecords || []).map(function (record) {
      return {
        lat: Number(record[crossingFields.lat]),
        lon: Number(record[crossingFields.lon]),
        firstConnectorIndex: Number(record[crossingFields.firstConnectorIndex]),
        secondConnectorIndex: Number(record[crossingFields.secondConnectorIndex]),
        angleDegrees: Number(record[crossingFields.angleDegrees]),
        sameFiveYearBand: Boolean(Number(record[crossingFields.sameFiveYearBand])),
      };
    });
    const decoded = { connectorByIndex: connectorByIndex, crossings: crossings };
    if (decodedPayloadCache) decodedPayloadCache.set(payload, decoded);
    return decoded;
  }

  function connectorSignature(connector) {
    if (!connector) return "unknown";
    if (connector.craftClass && connector.craftClass !== "mixed_endpoint_types") return connector.craftClass;
    return Array.from(new Set(connector.endpointCrafts || [])).sort().join("+") || "unknown";
  }

  function pairCrafts(first, second) {
    return Array.from(new Set(
      (first ? first.endpointCrafts : []).concat(second ? second.endpointCrafts : [])
    )).sort();
  }

  function containsExcludedLight(connector) {
    return Boolean(connector && (connector.endpointCrafts || []).some(function (craft) {
      return LIGHT_CRAFT_PATTERN.test(String(craft));
    }));
  }

  function connectorsShareEndpoint(first, second) {
    if (!first || !second) return true;
    return first.eventIds.some(function (eventId) {
      return second.eventIds.indexOf(eventId) !== -1;
    });
  }

  function connectorInsideTimeline(connector, timelineRange) {
    if (!timelineRange || !Number.isFinite(timelineRange.startOrdinal) || !Number.isFinite(timelineRange.endOrdinal)) {
      return false;
    }
    return connector.midOrdinal >= timelineRange.startOrdinal && connector.midOrdinal <= timelineRange.endOrdinal;
  }

  function pairMatches(first, second, options) {
    if (!first || !second || connectorsShareEndpoint(first, second)) return false;
    if (containsExcludedLight(first) || containsExcludedLight(second)) return false;
    const config = options || {};
    const crafts = pairCrafts(first, second);
    const craftScope = String(config.craftScope || "all_no_lights");
    if (craftScope === "cross_craft" && crafts.length < 2) return false;
    if (craftScope === "same_craft" && crafts.length !== 1) return false;
    if (craftScope.indexOf("craft:") === 0 && crafts.indexOf(craftScope.slice(6)) === -1) return false;

    const timeScope = String(config.timeScope || "all_time");
    if (timeScope === "timeline") {
      if (!connectorInsideTimeline(first, config.timelineRange) || !connectorInsideTimeline(second, config.timelineRange)) {
        return false;
      }
    } else {
      const match = /^within_(5|10|25|50)_years$/.exec(timeScope);
      if (match) {
        const maximumDays = Number(match[1]) * DAY_PER_YEAR;
        if (Math.abs(first.midOrdinal - second.midOrdinal) > maximumDays) return false;
      }
    }
    return true;
  }

  function cellIdForCoordinates(lat, lon, dimensions) {
    const nx = Number(dimensions && dimensions.longitudeCells);
    const ny = Number(dimensions && dimensions.equalAreaLatitudeBands);
    if (!(nx > 0) || !(ny > 0)) throw new Error("Equal-area grid dimensions are invalid.");
    const safeLat = Math.max(-90, Math.min(90, Number(lat)));
    let safeLon = Number(lon);
    safeLon = ((safeLon + 180) % 360 + 360) % 360 - 180;
    const x = Math.min(nx - 1, Math.max(0, Math.floor(((safeLon + 180) / 360) * nx)));
    const sinLat = Math.sin(safeLat * Math.PI / 180);
    const y = Math.min(ny - 1, Math.max(0, Math.floor(((sinLat + 1) / 2) * ny)));
    return x + ":" + y;
  }

  function cellBounds(cellId, dimensions) {
    const parts = String(cellId).split(":").map(Number);
    const x = parts[0];
    const y = parts[1];
    const nx = Number(dimensions.longitudeCells);
    const ny = Number(dimensions.equalAreaLatitudeBands);
    const west = -180 + (360 * x / nx);
    const east = -180 + (360 * (x + 1) / nx);
    const southSin = -1 + (2 * y / ny);
    const northSin = -1 + (2 * (y + 1) / ny);
    return {
      west: west,
      east: east,
      south: Math.asin(Math.max(-1, Math.min(1, southSin))) * 180 / Math.PI,
      north: Math.asin(Math.max(-1, Math.min(1, northSin))) * 180 / Math.PI,
    };
  }

  function angleBucket(angle) {
    if (angle < 30) return "15_to_30";
    if (angle < 60) return "30_to_60";
    return "60_to_90";
  }

  function increment(object, key, amount) {
    object[key] = (object[key] || 0) + (amount == null ? 1 : amount);
  }

  function createAccumulator(cellId, dimensions) {
    const bounds = cellBounds(cellId, dimensions);
    return {
      cellId: cellId,
      bounds: bounds,
      center: {
        lat: (bounds.south + bounds.north) / 2,
        lon: (bounds.west + bounds.east) / 2,
      },
      crossings: 0,
      connectorCrossingCounts: {},
      connectorIds: new Set(),
      craftInvolvementCounts: {},
      craftPairCounts: {},
      craftAxisConnectorIds: {},
      angleCounts: {},
      sources: new Set(),
      timeBands: new Set(),
      decades: new Set(),
      sameFiveYearBandCrossings: 0,
      sameCraftCrossings: 0,
      differentCraftCrossings: 0,
      mixedEndpointCraftCrossings: 0,
      examples: [],
    };
  }

  function addConnectorContext(accumulator, connector) {
    accumulator.connectorIds.add(connector.index);
    (connector.sources || []).forEach(function (source) { accumulator.sources.add(source); });
    (connector.timeBands || []).forEach(function (band) { accumulator.timeBands.add(band); });
    if (Number.isFinite(connector.midYear)) accumulator.decades.add(Math.floor(connector.midYear / 10) * 10);
    Array.from(new Set(connector.endpointCrafts || [])).forEach(function (craft) {
      const key = craft + "|" + connector.axis;
      if (!accumulator.craftAxisConnectorIds[key]) accumulator.craftAxisConnectorIds[key] = new Set();
      accumulator.craftAxisConnectorIds[key].add(connector.index);
    });
  }

  function screeningTier(crossings, uniqueConnectors, timeBandCount, dominantShare) {
    if (crossings >= 20 && uniqueConnectors >= 10 && timeBandCount >= 3 && dominantShare <= 0.35) {
      return "repeated_candidate";
    }
    if (crossings >= 5 && uniqueConnectors >= 4 && dominantShare <= 0.60) return "limited_candidate";
    return "descriptive_only";
  }

  function aggregateProfile(payload, options) {
    const config = Object.assign({
      gridKey: DEFAULT_GRID_KEY,
      craftScope: "all_no_lights",
      timeScope: "all_time",
      timelineRange: null,
    }, options || {});
    const grid = payload && payload.grids ? payload.grids[config.gridKey] : null;
    if (!grid) throw new Error("Requested intersection-cell resolution is unavailable.");
    const decoded = decodePayload(payload);
    const pairCache = new Map();
    function eligible(firstIndex, secondIndex) {
      const low = Math.min(firstIndex, secondIndex);
      const high = Math.max(firstIndex, secondIndex);
      const key = low + ":" + high;
      if (pairCache.has(key)) return pairCache.get(key);
      const matches = pairMatches(decoded.connectorByIndex[low], decoded.connectorByIndex[high], config);
      pairCache.set(key, matches);
      return matches;
    }

    const opportunitiesByCell = new Map();
    let totalOpportunities = 0;
    (grid.exposureCells || []).forEach(function (entry) {
      const cellId = String(entry[0]);
      const indexes = Array.isArray(entry[1]) ? entry[1].map(Number) : [];
      let opportunities = 0;
      for (let left = 0; left < indexes.length; left += 1) {
        for (let right = left + 1; right < indexes.length; right += 1) {
          if (eligible(indexes[left], indexes[right])) opportunities += 1;
        }
      }
      opportunitiesByCell.set(cellId, opportunities);
      totalOpportunities += opportunities;
    });

    const accumulators = new Map();
    let totalCrossings = 0;
    decoded.crossings.forEach(function (crossing) {
      if (!eligible(crossing.firstConnectorIndex, crossing.secondConnectorIndex)) return;
      const first = decoded.connectorByIndex[crossing.firstConnectorIndex];
      const second = decoded.connectorByIndex[crossing.secondConnectorIndex];
      const cellId = cellIdForCoordinates(crossing.lat, crossing.lon, grid.dimensions);
      let accumulator = accumulators.get(cellId);
      if (!accumulator) {
        accumulator = createAccumulator(cellId, grid.dimensions);
        accumulators.set(cellId, accumulator);
      }
      accumulator.crossings += 1;
      totalCrossings += 1;
      increment(accumulator.connectorCrossingCounts, first.index);
      increment(accumulator.connectorCrossingCounts, second.index);
      addConnectorContext(accumulator, first);
      addConnectorContext(accumulator, second);
      pairCrafts(first, second).forEach(function (craft) {
        increment(accumulator.craftInvolvementCounts, craft);
      });
      const signatures = [connectorSignature(first), connectorSignature(second)].sort();
      increment(accumulator.craftPairCounts, signatures.join(" x "));
      increment(accumulator.angleCounts, angleBucket(crossing.angleDegrees));
      accumulator.sameFiveYearBandCrossings += crossing.sameFiveYearBand ? 1 : 0;
      const firstCrafts = Array.from(new Set(first.endpointCrafts));
      const secondCrafts = Array.from(new Set(second.endpointCrafts));
      const allCrafts = pairCrafts(first, second);
      if (allCrafts.length === 1) accumulator.sameCraftCrossings += 1;
      else if (firstCrafts.length === 1 && secondCrafts.length === 1) accumulator.differentCraftCrossings += 1;
      else accumulator.mixedEndpointCraftCrossings += 1;
      if (accumulator.examples.length < 6) {
        accumulator.examples.push({
          lat: crossing.lat,
          lon: crossing.lon,
          angleDegrees: crossing.angleDegrees,
          craftPair: signatures.join(" x "),
          sameFiveYearBand: crossing.sameFiveYearBand,
        });
      }
    });

    const globalRate = totalOpportunities ? totalCrossings / totalOpportunities : 0;
    const cells = Array.from(accumulators.values()).map(function (accumulator) {
      const opportunities = opportunitiesByCell.get(accumulator.cellId) || 0;
      const expected = opportunities * globalRate;
      const connectorCounts = Object.keys(accumulator.connectorCrossingCounts).map(function (key) {
        return accumulator.connectorCrossingCounts[key];
      });
      const maxConnectorCrossings = connectorCounts.length ? Math.max.apply(Math, connectorCounts) : 0;
      const dominantShare = accumulator.crossings ? maxConnectorCrossings / accumulator.crossings : 0;
      const craftAxisConnectorCounts = {};
      Object.keys(accumulator.craftAxisConnectorIds).forEach(function (key) {
        const splitAt = key.lastIndexOf("|");
        const craft = key.slice(0, splitAt);
        const axis = key.slice(splitAt + 1);
        if (!craftAxisConnectorCounts[craft]) craftAxisConnectorCounts[craft] = {};
        craftAxisConnectorCounts[craft][axis] = accumulator.craftAxisConnectorIds[key].size;
      });
      const uniqueConnectors = accumulator.connectorIds.size;
      const timeBandCount = accumulator.timeBands.size;
      return {
        cellId: accumulator.cellId,
        bounds: accumulator.bounds,
        center: accumulator.center,
        crossings: accumulator.crossings,
        expectedFromLocalOpportunity: expected,
        opportunityNormalizedLift: (expected || accumulator.crossings)
          ? (accumulator.crossings + 0.5) / (expected + 0.5)
          : 0,
        localConnectorOpportunities: opportunities,
        uniqueCrossingConnectors: uniqueConnectors,
        dominantConnectorShare: dominantShare,
        sameFiveYearBandCrossings: accumulator.sameFiveYearBandCrossings,
        sameFiveYearBandShare: accumulator.crossings
          ? accumulator.sameFiveYearBandCrossings / accumulator.crossings
          : 0,
        fiveYearBandCount: timeBandCount,
        decadeCount: accumulator.decades.size,
        sourceCount: accumulator.sources.size,
        sameCraftCrossings: accumulator.sameCraftCrossings,
        differentCraftCrossings: accumulator.differentCraftCrossings,
        mixedEndpointCraftCrossings: accumulator.mixedEndpointCraftCrossings,
        craftPairCounts: accumulator.craftPairCounts,
        craftInvolvementCounts: accumulator.craftInvolvementCounts,
        craftAxisConnectorCounts: craftAxisConnectorCounts,
        angleCounts: accumulator.angleCounts,
        screeningTier: screeningTier(
          accumulator.crossings,
          uniqueConnectors,
          timeBandCount,
          dominantShare
        ),
        examples: accumulator.examples,
      };
    });
    cells.sort(function (left, right) {
      return right.opportunityNormalizedLift - left.opportunityNormalizedLift ||
        right.crossings - left.crossings || left.cellId.localeCompare(right.cellId);
    });
    const cellById = new Map(cells.map(function (cell) { return [cell.cellId, cell]; }));
    return {
      gridKey: config.gridKey,
      requestedCellAreaKm2: Number(grid.requestedCellAreaKm2),
      actualCellAreaKm2: Number(grid.actualCellAreaKm2),
      cells: cells,
      cellById: cellById,
      totalCrossings: totalCrossings,
      totalOpportunities: totalOpportunities,
      globalCrossingRate: globalRate,
      options: config,
    };
  }

  function addBufferSurvival(oneKmAggregation, fiveKmAggregation) {
    [oneKmAggregation, fiveKmAggregation].forEach(function (aggregation) {
      aggregation.cells.forEach(function (cell) {
        const one = oneKmAggregation.cellById.get(cell.cellId);
        const five = fiveKmAggregation.cellById.get(cell.cellId);
        cell.bufferOneKmCrossings = one ? one.crossings : 0;
        cell.bufferFiveKmCrossings = five ? five.crossings : 0;
        cell.bufferSurvivalPercent = one && one.crossings ? (cell.bufferFiveKmCrossings / one.crossings) * 100 : null;
      });
    });
  }

  function metricValue(cell, metric) {
    if (!cell) return 0;
    if (metric === "crossings") return Number(cell.crossings) || 0;
    if (metric === "unique_connectors") return Number(cell.uniqueCrossingConnectors) || 0;
    if (metric === "period_coverage") return Number(cell.fiveYearBandCount) || 0;
    if (metric === "same_period_share") return (Number(cell.sameFiveYearBandShare) || 0) * 100;
    if (metric === "buffer_survival") return Number(cell.bufferSurvivalPercent) || 0;
    return Number(cell.opportunityNormalizedLift) || 0;
  }

  function metricDigits(metric) {
    if (metric === "lift") return 2;
    if (metric === "same_period_share" || metric === "buffer_survival") return 1;
    return 0;
  }

  function metricSuffix(metric) {
    if (metric === "lift") return "×";
    if (metric === "same_period_share" || metric === "buffer_survival") return "%";
    return "";
  }

  function metricLabel(metric) {
    return {
      lift: "opportunity-normalized lift",
      crossings: "proper crossings",
      unique_connectors: "unique crossing connectors",
      period_coverage: "five-year periods represented",
      same_period_share: "same-period share",
      buffer_survival: "5 km endpoint-buffer survival",
    }[metric] || "opportunity-normalized lift";
  }

  function metricScale(cells, metric) {
    const values = (cells || []).map(function (cell) { return metricValue(cell, metric); }).filter(function (value) {
      return Number.isFinite(value) && value > 0;
    });
    return {
      minimum: values.length ? Math.min.apply(Math, values) : 0,
      maximum: values.length ? Math.max.apply(Math, values) : 0,
    };
  }

  function normalizedMetric(value, scale, metric) {
    if (!(value > 0) || !(scale.maximum > 0)) return 0;
    if (metric === "same_period_share" || metric === "buffer_survival") return Math.min(1, value / 100);
    if (metric === "lift") return Math.min(1, Math.log1p(value) / Math.log1p(scale.maximum));
    return Math.min(1, Math.log1p(value) / Math.log1p(scale.maximum));
  }

  function heatColor(t) {
    const value = Math.max(0, Math.min(1, Number(t) || 0));
    if (value < 0.5) {
      const ratio = value * 2;
      return "hsl(" + Math.round(205 - ratio * 60) + ", 83%, " + Math.round(45 + ratio * 10) + "%)";
    }
    const ratio = (value - 0.5) * 2;
    return "hsl(" + Math.round(145 - ratio * 135) + ", 86%, " + Math.round(55 - ratio * 3) + "%)";
  }

  function cellAreaLabel(areaKm2) {
    const squareMiles = Number(areaKm2) / 2.58998811;
    if (Math.abs(squareMiles - 10) < 1) return "10 mi²";
    if (Math.abs(squareMiles - 100) < 5) return "100 mi²";
    return formatNumber(squareMiles < 100 ? squareMiles : Math.round(squareMiles), squareMiles < 100 ? 1 : 0) + " mi²";
  }

  function timeScopeLabel(scope) {
    if (scope === "timeline") return "current Timeline range";
    const match = /^within_(\d+)_years$/.exec(String(scope || ""));
    if (match) return "connector dates within " + match[1] + " years";
    return "all catalog years, no separation limit";
  }

  function craftScopeLabel(scope) {
    if (scope === "cross_craft") return "cross-craft (mixed included)";
    if (scope === "same_craft") return "same-craft only";
    if (String(scope).indexOf("craft:") === 0) return humanCraft(String(scope).slice(6));
    return "all recognized craft, lights excluded";
  }

  function rankedEntries(object, limit) {
    return Object.keys(object || {}).map(function (key) {
      return [key, Number(object[key]) || 0];
    }).sort(function (left, right) {
      return right[1] - left[1] || left[0].localeCompare(right[0]);
    }).slice(0, limit || 6);
  }

  function rankListHtml(entries, labeler) {
    if (!entries.length) return '<p class="trace-intersection-empty-copy">None in this filtered cell.</p>';
    return '<ul class="trace-intersection-rank-list">' + entries.map(function (entry) {
      return '<li><span>' + escapeHtml(labeler(entry[0])) + '</span><strong>' + formatNumber(entry[1], 0) + '</strong></li>';
    }).join("") + "</ul>";
  }

  function humanSignature(signature) {
    return String(signature || "").split(" x ").map(function (connector) {
      return connector.split("+").map(humanCraft).join(" + ");
    }).join(" × ");
  }

  function axisSummaryHtml(counts) {
    const rows = Object.keys(counts || {}).map(function (craft) {
      const axes = counts[craft] || {};
      const total = Object.keys(axes).reduce(function (sum, axis) { return sum + (Number(axes[axis]) || 0); }, 0);
      return [craft, axes, total];
    }).sort(function (left, right) { return right[2] - left[2] || left[0].localeCompare(right[0]); }).slice(0, 5);
    if (!rows.length) return '<p class="trace-intersection-empty-copy">No axis summary.</p>';
    return '<ul class="trace-intersection-axis-list">' + rows.map(function (row) {
      const axes = Object.keys(row[1]).sort(function (left, right) { return row[1][right] - row[1][left]; }).map(function (axis) {
        return (AXIS_LABELS[axis] || axis) + " " + row[1][axis];
      }).join(" · ");
      return '<li><strong>' + escapeHtml(humanCraft(row[0])) + '</strong><span>' + escapeHtml(axes) + '</span></li>';
    }).join("") + "</ul>";
  }

  function Controller(options) {
    const config = options || {};
    this.map = config.map;
    this.L = config.L;
    this.root = config.root;
    this.resolveAssetPath = typeof config.resolveAssetPath === "function" ? config.resolveAssetPath : function (path) { return path; };
    this.getTimelineRange = typeof config.getTimelineRange === "function" ? config.getTimelineRange : function () { return null; };
    this.getTraceMode = typeof config.getTraceMode === "function" ? config.getTraceMode : function () { return "off"; };
    this.setTraceMode = typeof config.setTraceMode === "function" ? config.setTraceMode : null;
    this.onStatusChange = typeof config.onStatusChange === "function" ? config.onStatusChange : function () {};
    this.fetchImpl = config.fetchImpl || (typeof fetch === "function" ? fetch.bind(globalThis) : null);
    this.profiles = null;
    this.loadingPromise = null;
    this.layerGroup = null;
    this.renderer = null;
    this.selectedCellId = null;
    this.lastAggregation = null;
    this.lastVisibleCells = [];
    this.enabled = false;
    this.status = "off";
    this.error = null;
    this.savedTraceMode = null;
    this.traceModeChangeInternal = false;
    this.elements = {};
  }

  Controller.prototype.initialize = function () {
    if (!this.root || !this.map || !this.L) return this;
    const query = function (selector) { return this.root.querySelector(selector); }.bind(this);
    this.elements = {
      enabled: query("#trace-intersection-enabled"),
      hideTraces: query("#trace-intersection-hide-traces"),
      profile: query("#trace-intersection-endpoint-buffer"),
      resolution: query("#trace-intersection-resolution"),
      craft: query("#trace-intersection-craft-scope"),
      time: query("#trace-intersection-time-scope"),
      metric: query("#trace-intersection-metric"),
      support: query("#trace-intersection-support"),
      status: query("#trace-intersection-status"),
      legend: query("#trace-intersection-legend"),
      inspector: query("#trace-intersection-inspector"),
      cellSelect: query("#trace-intersection-cell-select"),
      zoomSelected: query("#trace-intersection-zoom-selected"),
      openOverlays: query("#trace-intersection-open-overlays"),
    };
    const redrawControls = [
      this.elements.profile,
      this.elements.resolution,
      this.elements.craft,
      this.elements.time,
      this.elements.metric,
      this.elements.support,
    ];
    if (this.elements.enabled) {
      this.elements.enabled.addEventListener("change", function () {
        this.setEnabled(Boolean(this.elements.enabled.checked));
      }.bind(this));
    }
    redrawControls.forEach(function (element) {
      if (!element) return;
      element.addEventListener("change", function () {
        if (this.enabled) this.refresh();
      }.bind(this));
    }, this);
    if (this.elements.hideTraces) {
      this.elements.hideTraces.addEventListener("change", function () {
        if (!this.enabled) return;
        if (this.elements.hideTraces.checked) this.suppressOrdinaryTraces();
        else this.restoreOrdinaryTraces();
        if (this.lastAggregation) this.renderAggregation(this.lastAggregation);
      }.bind(this));
    }
    if (this.elements.openOverlays) {
      this.elements.openOverlays.addEventListener("click", function () {
        const section = document.querySelector('[data-map-control-section="overlays"]');
        if (section) section.open = true;
      });
    }
    if (this.elements.cellSelect) {
      this.elements.cellSelect.addEventListener("change", function () {
        if (!this.elements.cellSelect.value) return;
        this.selectCell(this.elements.cellSelect.value, false);
      }.bind(this));
    }
    if (this.elements.zoomSelected) {
      this.elements.zoomSelected.addEventListener("click", function () {
        if (this.selectedCellId) this.selectCell(this.selectedCellId, true);
      }.bind(this));
    }
    this.map.on("zoomend", function () {
      if (this.enabled && this.lastAggregation) this.renderAggregation(this.lastAggregation);
    }, this);
    this.renderOffState();
    return this;
  };

  Controller.prototype.ensureLayers = function () {
    if (this.layerGroup) return;
    this.renderer = this.L.svg({ pane: "traceIntersectionPane", padding: 0.35 });
    this.layerGroup = this.L.layerGroup();
  };

  Controller.prototype.setStatus = function (status, message) {
    this.status = status;
    if (this.elements.status) {
      this.elements.status.textContent = message || status;
      this.elements.status.classList.toggle("is-error", status === "error");
    }
    this.onStatusChange(this.getStatus());
  };

  Controller.prototype.renderOffState = function () {
    if (this.layerGroup && this.map.hasLayer(this.layerGroup)) this.map.removeLayer(this.layerGroup);
    if (this.elements.legend) this.elements.legend.textContent = "Layer off · data loads only when enabled";
    if (this.elements.cellSelect) {
      this.elements.cellSelect.disabled = true;
      this.elements.cellSelect.innerHTML = '<option value="">Enable the layer first</option>';
    }
    if (this.elements.zoomSelected) this.elements.zoomSelected.disabled = true;
    if (this.elements.inspector) {
      this.elements.inspector.innerHTML = '<p class="trace-intersection-empty-copy">Enable the layer, then select a hotspot to inspect its craft mix, recurrence, and endpoint-buffer sensitivity.</p>';
    }
    this.setStatus("off", "Off. Facilities and other overlays are unchanged.");
  };

  Controller.prototype.requestTraceMode = function (mode) {
    if (!this.setTraceMode) return;
    this.traceModeChangeInternal = true;
    this.setTraceMode(mode);
    this.traceModeChangeInternal = false;
  };

  Controller.prototype.suppressOrdinaryTraces = function () {
    if (!this.setTraceMode) return;
    const current = String(this.getTraceMode() || "off");
    if (current !== "off") this.savedTraceMode = current;
    if (current !== "off") this.requestTraceMode("off");
  };

  Controller.prototype.restoreOrdinaryTraces = function () {
    if (!this.setTraceMode || !this.savedTraceMode) return;
    const restoreMode = this.savedTraceMode;
    this.savedTraceMode = null;
    if (String(this.getTraceMode() || "off") === "off") this.requestTraceMode(restoreMode);
  };

  Controller.prototype.notifyTraceModeChanged = function (mode) {
    if (this.traceModeChangeInternal || !this.enabled || !this.elements.hideTraces || !this.elements.hideTraces.checked) {
      return;
    }
    const nextMode = String(mode || "off");
    if (nextMode !== "off") {
      this.savedTraceMode = nextMode;
      this.requestTraceMode("off");
    }
  };

  Controller.prototype.setEnabled = function (enabled) {
    this.enabled = Boolean(enabled);
    if (this.elements.enabled) this.elements.enabled.checked = this.enabled;
    if (!this.enabled) {
      this.restoreOrdinaryTraces();
      this.renderOffState();
      return Promise.resolve(this.getStatus());
    }
    this.ensureLayers();
    if (this.elements.hideTraces && this.elements.hideTraces.checked) this.suppressOrdinaryTraces();
    if (!this.map.hasLayer(this.layerGroup)) this.layerGroup.addTo(this.map);
    this.setStatus("loading", "Loading qualified convergence profiles…");
    return this.loadProfiles().then(function () {
      this.populateCraftOptions();
      this.populateResolutionOptions();
      this.refresh();
      return this.getStatus();
    }.bind(this)).catch(function (error) {
      this.error = error;
      this.enabled = false;
      this.restoreOrdinaryTraces();
      if (this.elements.enabled) this.elements.enabled.checked = false;
      if (this.layerGroup && this.map.hasLayer(this.layerGroup)) this.map.removeLayer(this.layerGroup);
      this.setStatus("error", "Could not load convergence cells: " + (error && error.message ? error.message : error));
      return this.getStatus();
    }.bind(this));
  };

  Controller.prototype.loadProfiles = function () {
    if (this.profiles) return Promise.resolve(this.profiles);
    if (this.loadingPromise) return this.loadingPromise;
    if (!this.fetchImpl) return Promise.reject(new Error("Fetch is unavailable."));
    const load = function (path) {
      const url = this.resolveAssetPath(path);
      return this.fetchImpl(url).then(function (response) {
        if (!response || !response.ok) throw new Error("HTTP " + (response ? response.status : "failure") + " for " + path);
        return response.json();
      });
    }.bind(this);
    this.loadingPromise = Promise.all([load(PROFILE_PATHS.buffer1), load(PROFILE_PATHS.buffer5)]).then(function (profiles) {
      profiles.forEach(function (profile) { decodePayload(profile); });
      this.profiles = { buffer1: profiles[0], buffer5: profiles[1] };
      return this.profiles;
    }.bind(this));
    return this.loadingPromise;
  };

  Controller.prototype.populateCraftOptions = function () {
    if (!this.elements.craft || !this.profiles) return;
    const prior = this.elements.craft.value || "all_no_lights";
    const crafts = new Set();
    decodePayload(this.profiles.buffer5).connectorByIndex.forEach(function (connector) {
      if (!connector) return;
      (connector.endpointCrafts || []).forEach(function (craft) {
        if (!LIGHT_CRAFT_PATTERN.test(craft)) crafts.add(craft);
      });
    });
    this.elements.craft.innerHTML =
      '<option value="all_no_lights">All recognized craft — lights excluded</option>' +
      '<option value="cross_craft">Cross-craft — mixed endpoints included</option>' +
      '<option value="same_craft">Same-craft only</option>' +
      '<optgroup label="Includes selected craft">' +
      Array.from(crafts).sort(function (left, right) { return humanCraft(left).localeCompare(humanCraft(right)); }).map(function (craft) {
        return '<option value="craft:' + escapeHtml(craft) + '">' + escapeHtml(humanCraft(craft)) + '</option>';
      }).join("") + "</optgroup>";
    const values = Array.from(this.elements.craft.options).map(function (option) { return option.value; });
    this.elements.craft.value = values.indexOf(prior) !== -1 ? prior : "all_no_lights";
  };

  Controller.prototype.populateResolutionOptions = function () {
    if (!this.elements.resolution || !this.profiles) return;
    const prior = this.elements.resolution.value || DEFAULT_GRID_KEY;
    const grids = this.profiles.buffer5.grids || {};
    const keys = Object.keys(grids).sort(function (left, right) {
      return Number(grids[right].actualCellAreaKm2) - Number(grids[left].actualCellAreaKm2);
    });
    this.elements.resolution.innerHTML = keys.map(function (key) {
      return '<option value="' + escapeHtml(key) + '">' + escapeHtml(cellAreaLabel(grids[key].actualCellAreaKm2)) + " cells</option>";
    }).join("");
    this.elements.resolution.value = keys.indexOf(prior) !== -1 ? prior : (keys.indexOf(DEFAULT_GRID_KEY) !== -1 ? DEFAULT_GRID_KEY : keys[0]);
  };

  Controller.prototype.currentOptions = function () {
    return {
      gridKey: this.elements.resolution ? this.elements.resolution.value : DEFAULT_GRID_KEY,
      craftScope: this.elements.craft ? this.elements.craft.value : "all_no_lights",
      timeScope: this.elements.time ? this.elements.time.value : "all_time",
      timelineRange: this.getTimelineRange(),
    };
  };

  Controller.prototype.refresh = function () {
    if (!this.enabled || !this.profiles) return;
    const options = this.currentOptions();
    const one = aggregateProfile(this.profiles.buffer1, options);
    const five = aggregateProfile(this.profiles.buffer5, options);
    addBufferSurvival(one, five);
    const profileKey = this.elements.profile ? this.elements.profile.value : "buffer5";
    const aggregation = profileKey === "buffer1" ? one : five;
    aggregation.profileKey = profileKey;
    aggregation.oneKmAggregation = one;
    aggregation.fiveKmAggregation = five;
    this.lastAggregation = aggregation;
    if (this.selectedCellId && !aggregation.cellById.has(this.selectedCellId)) this.selectedCellId = null;
    this.renderAggregation(aggregation);
  };

  Controller.prototype.visibleCells = function (aggregation) {
    const minimumTier = this.elements.support ? this.elements.support.value : "limited_candidate";
    const minimumRank = minimumTier === "all" ? -1 : (SUPPORT_RANK[minimumTier] || 0);
    return aggregation.cells.filter(function (cell) {
      return (SUPPORT_RANK[cell.screeningTier] || 0) >= minimumRank;
    });
  };

  Controller.prototype.selectCell = function (cellId, zoomToCell) {
    if (!this.lastAggregation) return;
    const cell = this.lastAggregation.cellById.get(String(cellId || ""));
    if (!cell) return;
    this.selectedCellId = cell.cellId;
    this.renderAggregation(this.lastAggregation);
    this.renderInspector(cell);
    if (zoomToCell) {
      this.map.fitBounds([
        [cell.bounds.south, cell.bounds.west],
        [cell.bounds.north, cell.bounds.east],
      ], { padding: [36, 36], maxZoom: 9 });
    }
  };

  Controller.prototype.renderAggregation = function (aggregation) {
    if (!this.layerGroup) return;
    this.layerGroup.clearLayers();
    const metric = this.elements.metric ? this.elements.metric.value : "lift";
    const cells = this.visibleCells(aggregation);
    if (this.selectedCellId && !cells.some(function (cell) { return cell.cellId === this.selectedCellId; }, this)) {
      this.selectedCellId = null;
    }
    const scale = metricScale(cells, metric);
    const useCentroids = aggregation.actualCellAreaKm2 <= FINE_CELL_THRESHOLD_KM2 && this.map.getZoom() < FINE_CELL_RECTANGLE_MIN_ZOOM;
    cells.forEach(function (cell) {
      const value = metricValue(cell, metric);
      const normalized = normalizedMetric(value, scale, metric);
      const color = heatColor(normalized);
      const selected = cell.cellId === this.selectedCellId;
      const common = {
        pane: "traceIntersectionPane",
        renderer: this.renderer,
        color: selected ? "#ffffff" : color,
        weight: selected ? 3 : 1.25,
        opacity: 0.95,
        fillColor: color,
        fillOpacity: Math.max(0.28, 0.24 + normalized * 0.62),
        interactive: true,
        className: "trace-intersection-map-cell" + (selected ? " is-selected" : ""),
      };
      const valueText = formatNumber(value, metricDigits(metric)) + metricSuffix(metric);
      const ariaLabel = cellAreaLabel(aggregation.actualCellAreaKm2) + " convergence cell: " + valueText + " " +
        metricLabel(metric) + ", " + formatNumber(cell.crossings, 0) + " crossings";
      let layer;
      if (useCentroids) {
        const diameter = Math.round(Math.max(10, Math.min(22, 9 + normalized * 13)));
        const icon = this.L.divIcon({
          className: "trace-intersection-centroid-icon",
          html: '<button type="button" class="trace-intersection-centroid-button trace-intersection-map-cell' +
            (selected ? ' is-selected' : '') + '" aria-label="' + escapeHtml(ariaLabel) +
            '" style="--trace-intersection-cell-color:' + escapeHtml(color) + ';--trace-intersection-cell-size:' + diameter + 'px"></button>',
          iconSize: [diameter, diameter],
          iconAnchor: [diameter / 2, diameter / 2],
        });
        layer = this.L.marker([cell.center.lat, cell.center.lon], {
          pane: "traceIntersectionPane",
          icon: icon,
          interactive: true,
          keyboard: false,
        });
      } else {
        layer = this.L.rectangle([
          [cell.bounds.south, cell.bounds.west],
          [cell.bounds.north, cell.bounds.east],
        ], common);
      }
      layer.bindTooltip(
        '<strong>' + escapeHtml(valueText) + '</strong> ' + escapeHtml(metricLabel(metric)) +
        '<br>' + formatNumber(cell.crossings, 0) + ' crossings · ' + formatNumber(cell.uniqueCrossingConnectors, 0) + ' connectors',
        { sticky: true, direction: "top", opacity: 0.96 }
      );
      const selectCell = function () {
        this.selectCell(cell.cellId, false);
      }.bind(this);
      layer.on("click", selectCell);
      layer.addTo(this.layerGroup);
      const layerElement = typeof layer.getElement === "function" ? layer.getElement() : null;
      const element = useCentroids && layerElement
        ? layerElement.querySelector(".trace-intersection-centroid-button")
        : layerElement;
      if (element) {
        if (!useCentroids) {
          element.setAttribute("role", "button");
          element.setAttribute("tabindex", "0");
          element.setAttribute("aria-label", ariaLabel);
        }
        element.addEventListener("click", function (event) {
          event.stopPropagation();
          selectCell();
        });
        element.addEventListener("keydown", function (event) {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          selectCell();
        });
      }
    }, this);
    this.lastVisibleCells = cells;
    if (this.elements.cellSelect) {
      this.elements.cellSelect.disabled = cells.length === 0;
      this.elements.cellSelect.innerHTML = '<option value="">Select on the map or from this ranked list</option>' + cells.map(function (cell, index) {
        const value = metricValue(cell, metric);
        const label = "#" + (index + 1) + " · " + formatNumber(value, metricDigits(metric)) + metricSuffix(metric) +
          " · " + formatNumber(cell.crossings, 0) + " crossings · " +
          formatNumber(cell.center.lat, 2) + ", " + formatNumber(cell.center.lon, 2);
        return '<option value="' + escapeHtml(cell.cellId) + '">' + escapeHtml(label) + '</option>';
      }).join("");
      if (this.selectedCellId) this.elements.cellSelect.value = this.selectedCellId;
    }
    if (this.elements.zoomSelected) this.elements.zoomSelected.disabled = !this.selectedCellId;
    const area = cellAreaLabel(aggregation.actualCellAreaKm2);
    const visualization = useCentroids ? " · centroid symbols until zoom 7" : " · true cell footprints";
    if (this.elements.legend) {
      this.elements.legend.textContent = area + " · " + metricLabel(metric) + " " +
        formatNumber(scale.minimum, metricDigits(metric)) + metricSuffix(metric) + "–" +
        formatNumber(scale.maximum, metricDigits(metric)) + metricSuffix(metric) + visualization;
    }
    const supportLabel = this.elements.support && this.elements.support.value !== "all" ? " supported" : "";
    const traceVisibility = this.elements.hideTraces && this.elements.hideTraces.checked
      ? " Ordinary traces are hidden;"
      : " Facility markers remain independent and above the cells.";
    this.setStatus(
      "ready",
      "Showing " + formatNumber(cells.length, 0) + supportLabel + " hotspot" + (cells.length === 1 ? "" : "s") +
      " from " + formatNumber(aggregation.totalCrossings, 0) + " filtered crossings across " +
      timeScopeLabel(aggregation.options.timeScope) + "." + traceVisibility +
      (traceVisibility.indexOf("Ordinary traces") !== -1 ? " facility markers remain independent and above the cells." : "")
    );
    if (this.selectedCellId) {
      const selected = aggregation.cellById.get(this.selectedCellId);
      if (selected) this.renderInspector(selected);
    } else if (this.elements.inspector) {
      this.elements.inspector.innerHTML = '<p class="trace-intersection-empty-copy">Select a hotspot to inspect craft axes, recurrence, concentration, and endpoint-buffer survival. These are qualified report-neighbor connectors, not observed flight paths.</p>';
    }
  };

  Controller.prototype.renderInspector = function (cell) {
    if (!this.elements.inspector || !this.lastAggregation) return;
    const metric = this.elements.metric ? this.elements.metric.value : "lift";
    const value = metricValue(cell, metric);
    const craftEntries = rankedEntries(cell.craftInvolvementCounts, 6);
    const pairEntries = rankedEntries(cell.craftPairCounts, 6);
    this.elements.inspector.innerHTML =
      '<div class="trace-intersection-inspector-heading"><strong>Selected ' + escapeHtml(cellAreaLabel(this.lastAggregation.actualCellAreaKm2)) + ' cell</strong>' +
      '<span>' + escapeHtml(formatNumber(value, metricDigits(metric)) + metricSuffix(metric)) + ' ' + escapeHtml(metricLabel(metric)) + '</span></div>' +
      '<div class="trace-intersection-metrics">' +
        '<div><strong>' + formatNumber(cell.crossings, 0) + '</strong><span>crossings</span></div>' +
        '<div><strong>' + formatNumber(cell.opportunityNormalizedLift, 2) + '×</strong><span>lift</span></div>' +
        '<div><strong>' + formatNumber(cell.uniqueCrossingConnectors, 0) + '</strong><span>connectors</span></div>' +
        '<div><strong>' + formatNumber(cell.fiveYearBandCount, 0) + '</strong><span>5-year periods</span></div>' +
      '</div>' +
      '<p class="trace-intersection-sensitivity"><strong>Endpoint check:</strong> ' +
        formatNumber(cell.bufferOneKmCrossings, 0) + ' at 1 km; ' +
        formatNumber(cell.bufferFiveKmCrossings, 0) + ' at 5 km' +
        (cell.bufferSurvivalPercent == null ? "." : ' (' + formatNumber(cell.bufferSurvivalPercent, 1) + '% retained).') + '</p>' +
      '<details><summary>Craft involvement</summary>' + rankListHtml(craftEntries, humanCraft) + '</details>' +
      '<details><summary>Undirected axes by craft</summary><p class="trace-intersection-mini-note">Unique connectors; axes imply no heading.</p>' + axisSummaryHtml(cell.craftAxisConnectorCounts) + '</details>' +
      '<details><summary>Crossing craft signatures</summary>' + rankListHtml(pairEntries, humanSignature) + '</details>' +
      '<p class="trace-intersection-mini-note">' +
        formatNumber(cell.sameFiveYearBandCrossings, 0) + ' same-period crossings · ' +
        formatNumber(cell.differentCraftCrossings, 0) + ' homotypic cross-craft · ' +
        formatNumber(cell.mixedEndpointCraftCrossings, 0) + ' mixed-endpoint · ' +
        formatNumber(cell.dominantConnectorShare * 100, 1) + '% largest one-connector share · ' +
        formatNumber(cell.sourceCount, 0) + ' source collections.</p>' +
      '<p class="trace-intersection-mini-note"><strong>Scope:</strong> ' + escapeHtml(craftScopeLabel(this.lastAggregation.options.craftScope)) +
        '; ' + escapeHtml(timeScopeLabel(this.lastAggregation.options.timeScope)) + '.</p>';
  };

  Controller.prototype.notifyTimelineRangeChanged = function () {
    if (this.enabled && this.elements.time && this.elements.time.value === "timeline") this.refresh();
  };

  Controller.prototype.getSummaryText = function () {
    if (this.status === "loading") return "Loading";
    if (this.status === "error") return "Unavailable";
    if (!this.enabled || !this.lastAggregation) return "Off";
    return cellAreaLabel(this.lastAggregation.actualCellAreaKm2) + " · " + formatNumber(this.lastVisibleCells.length, 0) + " cells";
  };

  Controller.prototype.getStatus = function () {
    return {
      enabled: this.enabled,
      status: this.status,
      error: this.error ? String(this.error.message || this.error) : null,
      summary: this.getSummaryText(),
      visibleCells: this.lastVisibleCells.length,
      filteredCrossings: this.lastAggregation ? this.lastAggregation.totalCrossings : 0,
      selectedCellId: this.selectedCellId,
      options: this.lastAggregation ? this.lastAggregation.options : this.currentOptions(),
    };
  };

  function createController(options) {
    return new Controller(options);
  }

  return Object.freeze({
    CRAFT_LABELS: CRAFT_LABELS,
    DEFAULT_GRID_KEY: DEFAULT_GRID_KEY,
    PROFILE_PATHS: PROFILE_PATHS,
    Controller: Controller,
    addBufferSurvival: addBufferSurvival,
    aggregateProfile: aggregateProfile,
    cellAreaLabel: cellAreaLabel,
    cellBounds: cellBounds,
    cellIdForCoordinates: cellIdForCoordinates,
    craftScopeLabel: craftScopeLabel,
    createController: createController,
    heatColor: heatColor,
    humanCraft: humanCraft,
    metricScale: metricScale,
    metricValue: metricValue,
    normalizedMetric: normalizedMetric,
    pairMatches: pairMatches,
    screeningTier: screeningTier,
    timeScopeLabel: timeScopeLabel,
  });
});
