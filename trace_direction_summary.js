(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module && module.exports) module.exports = api;
  if (root) root.UfoTraceDirectionSummary = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const RAD = Math.PI / 180;
  const MAX_MAP_LATITUDE = 85.0511287798066;
  const EPSILON = 1e-12;
  const SECTORS = Object.freeze([
    ["N", "North", "#f5f5f5", "#111111"],
    ["NE", "Northeast", "#dedede", "#111111"],
    ["E", "East", "#c7c7c7", "#111111"],
    ["SE", "Southeast", "#afafaf", "#111111"],
    ["S", "South", "#969696", "#111111"],
    ["SW", "Southwest", "#767676", "#ffffff"],
    ["W", "West", "#606060", "#ffffff"],
    ["NW", "Northwest", "#454545", "#ffffff"],
  ].map(function (row, index) {
    return Object.freeze({ key: row[0], label: row[1], tone: row[2], ink: row[3], index, bearing: index * 45 });
  }));

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (character) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character];
    });
  }

  function numericCoordinate(value) {
    if (typeof value !== "number" && typeof value !== "string") return null;
    if (typeof value === "string" && !value.trim()) return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function coordinatePair(value) {
    if (!Array.isArray(value) || value.length < 2) return null;
    const lat = numericCoordinate(value[0]);
    const lon = numericCoordinate(value[1]);
    if (lat == null || lon == null || lat < -90 || lat > 90) return null;
    // Longitudes may already be unwrapped by the map renderer.
    return [lat, lon];
  }

  function normalizeLongitudeDelta(value) {
    return ((((value + 180) % 360) + 360) % 360) - 180;
  }

  function normalizeBearing(value) {
    return ((value % 360) + 360) % 360;
  }

  function sameLocation(from, to) {
    return Math.abs(from[0] - to[0]) < EPSILON && (
      Math.abs(normalizeLongitudeDelta(to[1] - from[1])) < EPSILON ||
      Math.abs(Math.abs(from[0]) - 90) < EPSILON
    );
  }

  function initialBearing(fromValue, toValue) {
    const from = coordinatePair(fromValue);
    const to = coordinatePair(toValue);
    if (!from || !to || sameLocation(from, to)) return null;
    const phi1 = from[0] * RAD;
    const phi2 = to[0] * RAD;
    const lambda = normalizeLongitudeDelta(to[1] - from[1]) * RAD;
    const x = Math.sin(lambda) * Math.cos(phi2);
    const y = (Math.cos(phi1) * Math.sin(phi2)) - (Math.sin(phi1) * Math.cos(phi2) * Math.cos(lambda));
    // An antipodal pair has no unique shortest great-circle bearing.
    if (Math.abs(x) < EPSILON && Math.abs(y) < EPSILON) return null;
    return normalizeBearing(Math.atan2(x, y) / RAD);
  }

  function mapBearing(fromValue, toValue) {
    const from = coordinatePair(fromValue);
    const to = coordinatePair(toValue);
    if (!from || !to || sameLocation(from, to)) return null;
    const latitude1 = Math.max(-MAX_MAP_LATITUDE, Math.min(MAX_MAP_LATITUDE, from[0]));
    const latitude2 = Math.max(-MAX_MAP_LATITUDE, Math.min(MAX_MAP_LATITUDE, to[0]));
    const deltaLongitude = normalizeLongitudeDelta(to[1] - from[1]) * RAD;
    const deltaMercator = Math.log(Math.tan((Math.PI / 4) + (latitude2 * RAD / 2))) -
      Math.log(Math.tan((Math.PI / 4) + (latitude1 * RAD / 2)));
    if (Math.abs(deltaLongitude) < EPSILON && Math.abs(deltaMercator) < EPSILON) return null;
    // Matches a straight connection in the Leaflet Web Mercator map, including
    // its latitude clamp and shortest longitude wrap. This is a rhumb bearing,
    // not the initial great-circle bearing or a measured object's trajectory.
    return normalizeBearing(Math.atan2(deltaLongitude, deltaMercator) / RAD);
  }

  function sectorForBearing(value) {
    const bearing = numericCoordinate(value);
    if (bearing == null) return null;
    // Eight half-open sectors; N spans [337.5, 360) and [0, 22.5).
    return SECTORS[Math.floor((normalizeBearing(bearing) + 22.5) / 45) % SECTORS.length];
  }

  function normalizeDirection(value) {
    const direction = String(value || "forward").toLowerCase();
    return direction === "both" || direction === "backward" ? direction : "forward";
  }

  function segmentDirection(segment, fallback) {
    const neighborhood = segment && segment.neighborhood;
    if (neighborhood && neighborhood.direction) {
      // Direct zero-hop traces retain earlier -> later orientation.
      return normalizeDirection(neighborhood.direction);
    }
    if (neighborhood && Array.isArray(neighborhood.directions)) {
      const directions = neighborhood.directions;
      if (directions.includes("forward") && directions.includes("backward")) return "both";
      if (directions.includes("backward")) return "backward";
      if (directions.includes("forward") || directions.includes("direct")) return "forward";
    }
    return normalizeDirection(fallback);
  }

  function segmentOrderUncertain(segment) {
    if (!segment || typeof segment !== "object") return false;
    if (segment.sameDayOrderKnown === false) return true;
    if (segment.sameDayOrderKnown === true) return false;
    // An exact shared catalog day establishes no within-day ordering. Null,
    // blank, boolean and missing gaps must not accidentally become zero.
    return numericCoordinate(segment.gapDays) === 0;
  }

  function orientationAxisLabel(bearing) {
    const sector = sectorForBearing(bearing);
    return sector ? ["North–South", "Northeast–Southwest", "East–West", "Southeast–Northwest"][sector.index % 4] : "";
  }

  function describeSegment(segment, options) {
    const config = options || {};
    const from = coordinatePair(segment && segment.from);
    const to = coordinatePair(segment && segment.to);
    if (!from || !to) return { valid: false, reason: "invalidCoordinates", directions: [] };
    if (sameLocation(from, to)) return { valid: false, reason: "zeroDistance", directions: [] };
    const orderUncertain = segmentOrderUncertain(segment);
    const direction = segmentDirection(segment, config.direction);
    const bearingFunction = !orderUncertain && config.bearingMode === "greatCircle" ? initialBearing : mapBearing;
    const forward = bearingFunction(from, to);
    if (forward == null) return { valid: false, reason: "undefinedBearing", directions: [] };
    if (orderUncertain) {
      const axisBearing = forward % 180;
      return {
        valid: true,
        reason: null,
        orderUncertain: true,
        direction: "unordered",
        directions: [],
        orientation: {
          direction: "unordered",
          orderUncertain: true,
          bearing: axisBearing,
          axisLabel: orientationAxisLabel(axisBearing),
          sector: "unordered",
          label: "Chronological order unknown",
          tone: "#969696",
          ink: "#111111",
        },
      };
    }
    const steps = direction === "both" ? ["forward", "backward"] : [direction];
    const directions = steps.map(function (step) {
      // On an exact 180-degree longitude tie the renderer chooses its -180
      // segment. Reversing that drawn segment must reverse its actual arrow.
      const bearing = step === "backward"
        ? config.bearingMode === "greatCircle"
          ? initialBearing(to, from)
          : normalizeBearing(forward + 180)
        : forward;
      const sector = sectorForBearing(bearing);
      return { direction: step, bearing, sector: sector.key, label: sector.label, tone: sector.tone, ink: sector.ink };
    });
    return { valid: true, reason: null, orderUncertain: false, direction, directions };
  }

  function segmentDirections(segment, options) {
    return describeSegment(segment, options).directions;
  }

  function canonicalConnectionEndpoint(value) {
    const pair = coordinatePair(value);
    if (!pair) return null;
    const lat = Math.round(pair[0] * 1e6) / 1e6;
    const lon = Math.round(normalizeLongitudeDelta(pair[1]) * 1e6) / 1e6;
    // Rounding a value immediately below 180 can reach 180; retain the same
    // canonical endpoint as the equivalent -180 value after rounding.
    return [lat, lon >= 180 ? -180 : lon];
  }

  function groupUnorderedConnections(segments, options) {
    const config = options || {};
    const project = typeof config.project === "function" ? config.project : null;
    const configuredTolerance = numericCoordinate(config.pixelTolerance);
    const tolerance = configuredTolerance == null ? 1 : Math.max(0, configuredTolerance);
    const toleranceSquared = tolerance * tolerance;
    const groups = [];
    const geographicGroups = new Map();
    const bins = new Map();
    const groupProjection = new Map();
    const projectedExactGroups = new Map();
    const keyCounts = new Map();
    const groupMembers = new Map();
    const groupOrder = new Map();
    const retiredGroups = new Set();

    function projectEndpoint(value) {
      try {
        // Give the callback a numeric copy so even a mutating projector cannot
        // alter catalog records. The original world longitude is retained.
        const result = project(coordinatePair(value));
        if (!Array.isArray(result) || result.length < 2) return null;
        const x = numericCoordinate(result[0]);
        const y = numericCoordinate(result[1]);
        return x == null || y == null ? null : [x, y];
      } catch (_) {
        return null;
      }
    }

    function makeGroup(key, segment) {
      const occurrence = keyCounts.get(key) || 0;
      keyCounts.set(key, occurrence + 1);
      // At extreme zoom a rounded geographic pair can project into separately
      // visible paths. Keep their group keys distinct without merging records.
      const group = { key: occurrence ? key + "|display:" + occurrence : key, segments: [], representative: segment };
      groupOrder.set(group, groups.length);
      groupMembers.set(group, []);
      groups.push(group);
      return group;
    }

    function exactProjectedKey(from, to) {
      const first = from[0] < to[0] || (from[0] === to[0] && from[1] <= to[1]);
      return JSON.stringify(first ? [from, to] : [to, from]);
    }

    function binKey(point) {
      return Math.floor(point[0] / tolerance) + "," + Math.floor(point[1] / tolerance);
    }

    function indexEndpoint(point, group) {
      const key = binKey(point);
      if (!bins.has(key)) bins.set(key, new Set());
      bins.get(key).add(group);
    }

    function unindexGroup(group) {
      const endpoints = groupProjection.get(group);
      if (!endpoints) return;
      [endpoints.from, endpoints.to].forEach(function (point) {
        const key = binKey(point);
        const entries = bins.get(key);
        if (!entries) return;
        entries.delete(group);
        if (!entries.size) bins.delete(key);
      });
    }

    function nearbyGroups(point) {
      const result = new Set();
      const column = Math.floor(point[0] / tolerance);
      const row = Math.floor(point[1] / tolerance);
      for (let dx = -1; dx <= 1; dx += 1) {
        for (let dy = -1; dy <= 1; dy += 1) {
          const candidates = bins.get((column + dx) + "," + (row + dy));
          if (candidates) candidates.forEach(function (group) { result.add(group); });
        }
      }
      return result;
    }

    function pointsNear(left, right) {
      const dx = left[0] - right[0];
      const dy = left[1] - right[1];
      return (dx * dx) + (dy * dy) <= toleranceSquared;
    }

    function lengthSquared(endpoints) {
      const dx = endpoints.to[0] - endpoints.from[0];
      const dy = endpoints.to[1] - endpoints.from[1];
      return (dx * dx) + (dy * dy);
    }

    function pathsMatch(left, right) {
      const directFrom = pointsNear(left.from, right.from);
      const directTo = pointsNear(left.to, right.to);
      const reverseFrom = pointsNear(left.from, right.to);
      const reverseTo = pointsNear(left.to, right.from);
      const matchingEndpoints = (directFrom && directTo) || (reverseFrom && reverseTo);
      // A shared endpoint anchors overlapping paths. Collinearity alone never
      // combines unrelated interior crossings or nearby parallel routes.
      if (!directFrom && !directTo && !reverseFrom && !reverseTo) return false;
      const leftLength = lengthSquared(left);
      const rightLength = lengthSquared(right);
      const longer = leftLength >= rightLength ? left : right;
      const shorter = leftLength >= rightLength ? right : left;
      const longLengthSquared = Math.max(leftLength, rightLength);
      if (!longLengthSquared) return matchingEndpoints;
      const dx = longer.to[0] - longer.from[0];
      const dy = longer.to[1] - longer.from[1];
      const intervals = [];
      for (const point of [shorter.from, shorter.to]) {
        const px = point[0] - longer.from[0];
        const py = point[1] - longer.from[1];
        const cross = (px * dy) - (py * dx);
        if ((cross * cross) > toleranceSquared * longLengthSquared) return false;
        intervals.push(((px * dx) + (py * dy)) / longLengthSquared);
      }
      const overlapStart = Math.max(0, Math.min(intervals[0], intervals[1]));
      const overlapEnd = Math.min(1, Math.max(intervals[0], intervals[1]));
      return overlapEnd - overlapStart > EPSILON;
    }

    (Array.isArray(segments) ? segments : []).forEach(function (segment, position) {
      const description = describeSegment(segment);
      if (!description.valid || !description.orderUncertain) return;
      const from = canonicalConnectionEndpoint(segment.from);
      const to = canonicalConnectionEndpoint(segment.to);
      const fromComesFirst = from[0] < to[0] || (from[0] === to[0] && from[1] <= to[1]);
      const key = JSON.stringify(fromComesFirst ? [from, to] : [to, from]);
      let group = null;
      const projectedFrom = project ? projectEndpoint(segment.from) : null;
      const projectedTo = project ? projectEndpoint(segment.to) : null;
      if (!project || !projectedFrom || !projectedTo) {
        // Failed projection falls back to geographic endpoint identity, never
        // to a shared (0,0) placeholder that could merge unrelated paths.
        group = geographicGroups.get(key);
        if (!group) {
          group = makeGroup(key, segment);
          geographicGroups.set(key, group);
        }
      } else if (!tolerance) {
        const projectedKey = exactProjectedKey(projectedFrom, projectedTo);
        group = projectedExactGroups.get(projectedKey);
        if (!group) {
          group = makeGroup(key, segment);
          projectedExactGroups.set(projectedKey, group);
        }
      } else {
        const projected = { from: projectedFrom, to: projectedTo };
        const candidates = nearbyGroups(projectedFrom);
        nearbyGroups(projectedTo).forEach(function (candidate) { candidates.add(candidate); });
        const matches = [];
        candidates.forEach(function (candidate) {
          const endpoints = groupProjection.get(candidate);
          if (pathsMatch(projected, endpoints)) matches.push(candidate);
        });
        if (!matches.length) {
          group = makeGroup(key, segment);
          groupProjection.set(group, projected);
          indexEndpoint(projectedFrom, group);
          indexEndpoint(projectedTo, group);
        } else {
          let longest = { endpoints: projected, segment, length: lengthSquared(projected), order: Infinity };
          matches.forEach(function (candidate) {
            const endpoints = groupProjection.get(candidate);
            const length = lengthSquared(endpoints);
            const order = groupOrder.get(candidate);
            if (length > longest.length || (length === longest.length && order < longest.order)) {
              longest = { endpoints, segment: candidate.representative, length, order };
            }
          });
          // A tiny common-origin segment must not join two long divergent
          // routes. Every merged representative must also match the longest.
          const compatible = matches.filter(function (candidate) {
            return pathsMatch(longest.endpoints, groupProjection.get(candidate));
          }).sort(function (left, right) { return groupOrder.get(left) - groupOrder.get(right); });
          group = compatible[0];
          compatible.forEach(function (candidate) {
            unindexGroup(candidate);
            if (candidate === group) return;
            groupMembers.get(candidate).forEach(function (member) { groupMembers.get(group).push(member); });
            groupMembers.delete(candidate);
            groupProjection.delete(candidate);
            retiredGroups.add(candidate);
          });
          group.representative = longest.segment;
          groupProjection.set(group, longest.endpoints);
          indexEndpoint(longest.endpoints.from, group);
          indexEndpoint(longest.endpoints.to, group);
        }
      }
      // This aggregates UI badges only. Retain all report links and their
      // original input order, including reciprocal and repeated ids.
      groupMembers.get(group).push({ segment, position });
    });
    return groups.filter(function (group) { return !retiredGroups.has(group); }).map(function (group) {
      group.segments = groupMembers.get(group).sort(function (left, right) { return left.position - right.position; })
        .map(function (member) { return member.segment; });
      return group;
    });
  }

  function segmentIdentity(segment) {
    if (!segment || typeof segment !== "object") return null;
    if (segment.traceId != null && segment.traceId !== "") return String(segment.traceId);
    if (segment.trace_id != null && segment.trace_id !== "") return String(segment.trace_id);
    if (segment.fromEventId != null && segment.toEventId != null) {
      return JSON.stringify([segment.fromEventId, segment.toEventId]);
    }
    return null;
  }

  function summarizeDirections(segments, options) {
    const config = options || {};
    const rows = Array.isArray(segments) ? segments : [];
    const sectors = SECTORS.map(function (sector) { return Object.assign({}, sector, { count: 0, percentage: 0 }); });
    const seen = new Set();
    const excludedCounts = { invalidCoordinates: 0, zeroDistance: 0, undefinedBearing: 0 };
    let uniqueSegments = 0;
    let validSegments = 0;
    let orderedSegments = 0;
    let unorderedSegments = 0;
    let bothDirectionSegments = 0;
    let duplicatesIgnored = 0;
    let denominator = 0;
    rows.forEach(function (segment) {
      const identity = segmentIdentity(segment);
      if (identity != null && seen.has(identity)) { duplicatesIgnored += 1; return; }
      if (identity != null) seen.add(identity);
      uniqueSegments += 1;
      const description = describeSegment(segment, config);
      if (!description.valid) { excludedCounts[description.reason] += 1; return; }
      validSegments += 1;
      if (description.orderUncertain) { unorderedSegments += 1; return; }
      orderedSegments += 1;
      if (description.direction === "both") bothDirectionSegments += 1;
      description.directions.forEach(function (entry) {
        sectors[sectorForBearing(entry.bearing).index].count += 1;
        denominator += 1;
      });
    });
    sectors.forEach(function (sector) { sector.percentage = denominator ? sector.count * 100 / denominator : 0; });
    return {
      title: "Report-link directions",
      bearingMode: config.bearingMode === "greatCircle" ? "greatCircle" : "map",
      sectors,
      denominator,
      directionCount: denominator,
      inputSegments: rows.length,
      uniqueSegments,
      validSegments,
      orderedSegments,
      unorderedSegments,
      bothDirectionSegments,
      excludedSegments: uniqueSegments - validSegments,
      excludedCounts,
      duplicatesIgnored,
    };
  }

  function formatPercentage(value) {
    return (Math.round(value * 10) / 10).toFixed(1).replace(/\.0$/, "") + "%";
  }

  function directionBadgeMarkup(entry, options) {
    if (!entry || sectorForBearing(entry.bearing) == null) return "";
    const config = options || {};
    const sector = sectorForBearing(entry.bearing);
    const configuredAngle = numericCoordinate(config.arrowAngle);
    const angle = configuredAngle == null ? entry.bearing - 90 : configuredAngle;
    if (entry.orderUncertain) {
      const accessibleLabel = orientationAxisLabel(entry.bearing) + " map connection; chronological order unknown";
      return '<span class="trace-direction-badge sector-unordered is-order-uncertain" style="--direction-tone:#969696;--direction-ink:#111111;--direction-arrow-angle:' +
        angle.toFixed(1) + 'deg;border-style:dashed" role="img" title="' + escapeHtml(accessibleLabel) + '" aria-label="' + escapeHtml(accessibleLabel) +
        '"><span class="trace-direction-badge-arrow" aria-hidden="true">↔</span></span>';
    }
    const accessibleLabel = sector.label + " report connection (" + Math.round(entry.bearing) + "°)";
    return '<span class="trace-direction-badge sector-' + sector.key.toLowerCase() + '" style="--direction-tone:' +
      sector.tone + ';--direction-ink:' + sector.ink + ';--direction-arrow-angle:' + angle.toFixed(1) +
      'deg" role="img" title="' + escapeHtml(accessibleLabel) + '" aria-label="' + escapeHtml(accessibleLabel) +
      '"><span class="trace-direction-badge-arrow" aria-hidden="true">➜</span></span>';
  }

  function pointAt(bearing, radius) {
    return [110 + (Math.sin(bearing * RAD) * radius), 110 - (Math.cos(bearing * RAD) * radius)];
  }

  function pointText(point) {
    return point[0].toFixed(2) + "," + point[1].toFixed(2);
  }

  function radialChartMarkup(summary) {
    const maximum = Math.max.apply(null, summary.sectors.map(function (sector) { return sector.percentage; }));
    if (!maximum) return "";
    const radius = 72;
    const scaleLabel = "Each outer spoke marks " + formatPercentage(maximum) + ".";
    const description = summary.sectors.map(function (sector) {
      return sector.label + ": " + sector.count + " (" + formatPercentage(sector.percentage) + ")";
    }).join("; ");
    const rings = [0.25, 0.5, 0.75, 1].map(function (fraction) {
      return '<polygon points="' + SECTORS.map(function (sector) { return pointText(pointAt(sector.bearing, radius * fraction)); }).join(" ") +
        '" fill="none" stroke="currentColor" stroke-opacity="0.22" stroke-width="1"/>';
    }).join("");
    const axes = SECTORS.map(function (sector) {
      const point = pointAt(sector.bearing, radius);
      const label = pointAt(sector.bearing, 96);
      return '<line x1="110" y1="110" x2="' + point[0].toFixed(2) + '" y2="' + point[1].toFixed(2) +
        '" stroke="currentColor" stroke-opacity="0.22"/><text x="' + label[0].toFixed(2) + '" y="' + label[1].toFixed(2) +
        '" text-anchor="middle" dominant-baseline="middle" fill="currentColor" font-size="11">' + sector.key + "</text>";
    }).join("");
    const values = summary.sectors.map(function (sector) { return pointAt(sector.bearing, radius * sector.percentage / maximum); });
    const dots = values.map(function (point, index) {
      return '<circle cx="' + point[0].toFixed(2) + '" cy="' + point[1].toFixed(2) + '" r="3" fill="currentColor"><title>' +
        escapeHtml(summary.sectors[index].key + ": " + formatPercentage(summary.sectors[index].percentage)) + "</title></circle>";
    }).join("");
    return '<figure class="trace-direction-chart"><svg viewBox="0 0 220 220" role="img" aria-label="' + escapeHtml("Report-link direction distribution. " + description + ". " + scaleLabel) +
      '"><title>Report-link direction distribution</title><desc>' + escapeHtml(description + ". " + scaleLabel) +
      "</desc>" + rings + axes + '<polygon points="' + values.map(pointText).join(" ") +
      '" fill="currentColor" fill-opacity="0.16" stroke="currentColor" stroke-width="2"/>' + dots +
      '</svg><figcaption>Radial scale: 0–' + formatPercentage(maximum) + "</figcaption></figure>";
  }

  function summaryMarkup(summary, options) {
    const config = options || {};
    const modeDescription = summary.bearingMode === "greatCircle"
      ? "Initial great-circle bearings between report locations."
      : "Compass bearings of straight map connections between report locations.";
    const orderedSegments = summary.orderedSegments == null ? summary.validSegments : summary.orderedSegments;
    const unorderedSegments = summary.unorderedSegments || 0;
    const denominatorText = summary.denominator + " direction" + (summary.denominator === 1 ? "" : "s") +
      " across " + orderedSegments + " ordered report link" + (orderedSegments === 1 ? "" : "s");
    const bothText = summary.bothDirectionSegments
      ? " Links reached in both chronology directions count once in each direction (" + summary.bothDirectionSegments + " links)."
      : summary.denominator ? " Each ordered link counts once in its displayed chronology direction." : "";
    const uncertaintyText = unorderedSegments
      ? '<p class="trace-direction-uncertainty">' + unorderedSegments + " valid map link" + (unorderedSegments === 1 ? " has" : "s have") +
        " unknown chronological order and " + (unorderedSegments === 1 ? "is" : "are") +
        " excluded from directional counts and percentages. Double-headed arrows show map connection axes only.</p>"
      : "";
    const excludedText = summary.excludedSegments
      ? '<p class="trace-direction-exclusions">Excluded ' + summary.excludedSegments + " links: " +
        summary.excludedCounts.invalidCoordinates + " invalid coordinates, " + summary.excludedCounts.zeroDistance +
        " coincident endpoints, " + summary.excludedCounts.undefinedBearing + " undefined bearings.</p>"
      : "";
    const rows = summary.sectors.map(function (sector) {
      const selected = Array.isArray(config.selectedSectors) && config.selectedSectors.includes(sector.key);
      return '<tr' + (selected ? ' class="is-selected-direction"' : "") + '><th scope="row"><span class="trace-direction-swatch" aria-hidden="true" style="background:' +
        sector.tone + '"></span><abbr title="' + sector.label + '">' + sector.key + "</abbr></th><td>" +
        sector.count + "</td><td>" + formatPercentage(sector.percentage) + "</td></tr>";
    }).join("");
    const dataMarkup = summary.denominator ? '<div class="trace-direction-data">' + radialChartMarkup(summary) +
      '<table class="trace-direction-table"><caption class="sr-only">Direction counts and shares of all ' + summary.denominator +
      ' ordered link directions</caption><thead><tr><th scope="col">Direction</th><th scope="col">Count</th><th scope="col">Share</th></tr></thead><tbody>' +
      rows + "</tbody></table></div>" : '<p class="trace-direction-empty">No report links with known chronological order in this selection.</p>';
    return '<section class="trace-direction-summary"><h4>Report-link directions</h4><p class="trace-direction-denominator">' +
      denominatorText + '</p><p class="trace-direction-note">' + modeDescription +
      " Directions describe chronological report ordering, not reported flight paths." + bothText +
      "</p>" + uncertaintyText + dataMarkup + excludedText + "</section>";
  }

  return Object.freeze({
    SECTORS,
    MAX_MAP_LATITUDE,
    coordinatePair,
    initialBearing,
    mapBearing,
    sectorForBearing,
    segmentDirection,
    segmentOrderUncertain,
    describeSegment,
    segmentDirections,
    groupUnorderedConnections,
    summarizeDirections,
    formatPercentage,
    directionBadgeMarkup,
    radialChartMarkup,
    summaryMarkup,
  });
});
