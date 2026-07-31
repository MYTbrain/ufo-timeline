(function (root, factory) {
  "use strict";

  const api = factory();
  if (typeof module === "object" && module && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.UfoTraceNeighborhood = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const CRAFT_TYPE_ORDER = Object.freeze([
    "disc_saucer",
    "sphere_orb",
    "triangle",
    "cigar_cylinder",
    "oval_egg",
    "chevron_boomerang",
    "rectangle_box",
    "fireball_meteor_like",
    "formation",
    "cone",
    "diamond",
    "teardrop",
    "dumbbell_barbell",
    "light",
    "conventional_or_explained",
    "non_ufo_context",
    "unknown",
  ]);

  const CRAFT_TYPE_LABELS = Object.freeze({
    disc_saucer: "Disc / saucer",
    sphere_orb: "Sphere / orb",
    triangle: "Triangle",
    cigar_cylinder: "Cigar / cylinder",
    oval_egg: "Oval / egg",
    chevron_boomerang: "Chevron / boomerang",
    rectangle_box: "Rectangle / box",
    fireball_meteor_like: "Fireball / meteor-like",
    formation: "Formation",
    cone: "Cone",
    diamond: "Diamond",
    teardrop: "Teardrop",
    dumbbell_barbell: "Dumbbell / barbell",
    light: "Light",
    conventional_or_explained: "Conventional / explained",
    non_ufo_context: "Non-UFO context",
    unknown: "Unknown",
  });

  const CRAFT_TYPE_COLORS = Object.freeze({
    disc_saucer: "#38bdf8",
    sphere_orb: "#22c55e",
    triangle: "#f97316",
    cigar_cylinder: "#a78bfa",
    oval_egg: "#facc15",
    chevron_boomerang: "#fb7185",
    rectangle_box: "#60a5fa",
    fireball_meteor_like: "#ef4444",
    formation: "#14b8a6",
    cone: "#e879f9",
    diamond: "#2dd4bf",
    teardrop: "#0ea5e9",
    dumbbell_barbell: "#c084fc",
    light: "#b517ff",
    conventional_or_explained: "#94a3b8",
    non_ufo_context: "#64748b",
    unknown: "#7e8f88",
  });

  function eventId(value) {
    if (value == null || value === "") return "";
    return String(value);
  }

  function humanizeCraftTypeKey(value) {
    const key = String(value || "unknown").trim() || "unknown";
    return key.replace(/_/g, " ").replace(/\b\w/g, function (character) {
      return character.toUpperCase();
    });
  }

  function canonicalCraftTypeKey(value) {
    const raw = value && typeof value === "object"
      ? value.craft_type_inferred
      : value;
    return String(raw || "unknown").trim() || "unknown";
  }

  function resolveCraftType(value, palette) {
    const colors = palette || CRAFT_TYPE_COLORS;
    const key = canonicalCraftTypeKey(value);
    return {
      key,
      label: CRAFT_TYPE_LABELS[key] || humanizeCraftTypeKey(key),
      color: colors[key] || colors.unknown || CRAFT_TYPE_COLORS.unknown,
      unknown: key === "unknown" || !Object.prototype.hasOwnProperty.call(colors, key),
    };
  }

  function resolveCraftEndpointStyle(fromEvent, toEvent, palette) {
    const from = resolveCraftType(fromEvent, palette);
    const to = resolveCraftType(toEvent, palette);
    return {
      fromKey: from.key,
      fromLabel: from.label,
      fromColor: from.color,
      toKey: to.key,
      toLabel: to.label,
      toColor: to.color,
      continuous: from.key === to.key,
    };
  }

  function nearestPointHit(target, candidates, defaultTolerance) {
    const targetX = Number(target && target.x);
    const targetY = Number(target && target.y);
    if (!Number.isFinite(targetX) || !Number.isFinite(targetY)) return null;

    const fallbackTolerance = Math.max(0, Number(defaultTolerance) || 0);
    let best = null;
    (Array.isArray(candidates) ? candidates : []).forEach(function (candidate, index) {
      const x = Number(candidate && candidate.x);
      const y = Number(candidate && candidate.y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return;
      const radius = Math.max(0, Number(candidate.radius) || 0);
      const candidateTolerance = Number(candidate.tolerance);
      const tolerance = Number.isFinite(candidateTolerance)
        ? Math.max(0, candidateTolerance)
        : fallbackTolerance;
      const hitRadius = radius + tolerance;
      const deltaX = x - targetX;
      const deltaY = y - targetY;
      const distanceSquared = (deltaX * deltaX) + (deltaY * deltaY);
      if (distanceSquared > hitRadius * hitRadius) return;
      if (
        !best ||
        distanceSquared < best.distanceSquared ||
        (distanceSquared === best.distanceSquared && index < best.index)
      ) {
        best = {
          candidate,
          distanceSquared,
          distance: Math.sqrt(distanceSquared),
          index,
        };
      }
    });
    return best;
  }

  function normalizeDepth(value) {
    const parsed = Math.round(Number(value) || 1);
    return Math.max(1, Math.min(4, parsed));
  }

  function normalizeDirection(value) {
    const direction = String(value || "forward").toLowerCase();
    return direction === "backward" || direction === "both" ? direction : "forward";
  }

  function directionSteps(direction) {
    const normalized = normalizeDirection(direction);
    return normalized === "both" ? ["forward", "backward"] : [normalized];
  }

  function segmentTraceId(segment) {
    if (!segment) return "";
    return String(
      segment.traceId ||
      segment.trace_id ||
      (eventId(segment.fromEventId) + "->" + eventId(segment.toEventId))
    );
  }

  function normalizedSegment(segment, index) {
    if (!segment) return null;
    const fromEventId = eventId(
      segment.fromEventId != null
        ? segment.fromEventId
        : Array.isArray(segment.eventIds)
          ? segment.eventIds[0]
          : ""
    );
    const toEventId = eventId(
      segment.toEventId != null
        ? segment.toEventId
        : Array.isArray(segment.eventIds)
          ? segment.eventIds[1]
          : ""
    );
    const traceId = segmentTraceId(Object.assign({}, segment, { fromEventId, toEventId }));
    if (!traceId || !fromEventId || !toEventId) return null;
    return Object.assign({}, segment, {
      traceId,
      fromEventId,
      toEventId,
      eventIds: [fromEventId, toEventId],
      sequenceIndex: Number.isFinite(Number(segment.sequenceIndex))
        ? Number(segment.sequenceIndex)
        : index,
    });
  }

  function appendMapList(map, key, value) {
    const list = map.get(key);
    if (list) {
      list.push(value);
    } else {
      map.set(key, [value]);
    }
  }

  function sortSegmentLists(map) {
    map.forEach(function (list) {
      list.sort(function (left, right) {
        const order = Number(left.sequenceIndex) - Number(right.sequenceIndex);
        return order || left.traceId.localeCompare(right.traceId);
      });
    });
  }

  function buildAdjacencyIndex(segments, generation) {
    const normalizedSegments = [];
    const segmentById = new Map();
    const outgoingByEvent = new Map();
    const incomingByEvent = new Map();

    (Array.isArray(segments) ? segments : []).forEach(function (segment, index) {
      const row = normalizedSegment(segment, index);
      if (!row || segmentById.has(row.traceId)) return;
      normalizedSegments.push(row);
      segmentById.set(row.traceId, row);
      appendMapList(outgoingByEvent, row.fromEventId, row);
      appendMapList(incomingByEvent, row.toEventId, row);
    });

    normalizedSegments.sort(function (left, right) {
      const order = Number(left.sequenceIndex) - Number(right.sequenceIndex);
      return order || left.traceId.localeCompare(right.traceId);
    });
    sortSegmentLists(outgoingByEvent);
    sortSegmentLists(incomingByEvent);

    return {
      generation: Number(generation) || 0,
      segments: normalizedSegments,
      segmentById,
      outgoingByEvent,
      incomingByEvent,
      eventCount: new Set(normalizedSegments.flatMap(function (segment) {
        return [segment.fromEventId, segment.toEventId];
      })).size,
    };
  }

  function uniqueStrings(values) {
    return Array.from(new Set((Array.isArray(values) ? values : []).map(String).filter(Boolean))).sort();
  }

  function attributionKey(attribution) {
    return [
      attribution.hop,
      attribution.direction,
      attribution.seedType,
      attribution.seedId,
      uniqueStrings(attribution.regionIds).join(","),
    ].join("|");
  }

  function mergeAttribution(record, attribution) {
    const key = attributionKey(attribution);
    if (record.attributionKeys.has(key)) return;
    record.attributionKeys.add(key);
    record.attributions.push({
      hop: attribution.hop,
      direction: attribution.direction,
      seedType: attribution.seedType,
      seedId: attribution.seedId,
      regionIds: uniqueStrings(attribution.regionIds),
    });
    record.hops.add(attribution.hop);
    record.directions.add(attribution.direction);
    if (attribution.seedType === "event") {
      record.seedEventIds.add(attribution.seedId);
    } else {
      record.seedTraceIds.add(attribution.seedId);
    }
    uniqueStrings(attribution.regionIds).forEach(function (regionId) {
      record.regionIds.add(regionId);
    });
  }

  function traverseNeighborhood(options) {
    const config = options || {};
    const index = config.index || buildAdjacencyIndex(config.segments || [], config.generation);
    const depth = normalizeDepth(config.depth);
    const direction = normalizeDirection(config.direction);
    const segmentRecords = new Map();
    const eventRecords = new Map();

    function ensureSegmentRecord(segment) {
      let record = segmentRecords.get(segment.traceId);
      if (!record) {
        record = {
          traceId: segment.traceId,
          segment,
          attributions: [],
          attributionKeys: new Set(),
          hops: new Set(),
          directions: new Set(),
          seedEventIds: new Set(),
          seedTraceIds: new Set(),
          regionIds: new Set(),
        };
        segmentRecords.set(segment.traceId, record);
      }
      return record;
    }

    function ensureEventRecord(id) {
      let record = eventRecords.get(id);
      if (!record) {
        record = {
          eventId: id,
          attributions: [],
          attributionKeys: new Set(),
          hops: new Set(),
          directions: new Set(),
          seedEventIds: new Set(),
          seedTraceIds: new Set(),
          regionIds: new Set(),
        };
        eventRecords.set(id, record);
      }
      return record;
    }

    function addReachedSegment(segment, attribution) {
      const record = ensureSegmentRecord(segment);
      mergeAttribution(record, attribution);
      [segment.fromEventId, segment.toEventId].forEach(function (id) {
        const eventRecord = ensureEventRecord(id);
        mergeAttribution(eventRecord, attribution);
      });
    }

    function walkFromEvent(startEventId, stepDirection, startHop, seedType, seedId, regionIds) {
      let cursor = eventId(startEventId);
      for (let hop = startHop; hop <= depth; hop += 1) {
        const candidates = stepDirection === "forward"
          ? index.outgoingByEvent.get(cursor)
          : index.incomingByEvent.get(cursor);
        if (!candidates || !candidates.length) break;
        const segment = stepDirection === "forward"
          ? candidates[0]
          : candidates[candidates.length - 1];
        addReachedSegment(segment, {
          hop,
          direction: stepDirection,
          seedType,
          seedId,
          regionIds,
        });
        cursor = stepDirection === "forward" ? segment.toEventId : segment.fromEventId;
      }
    }

    (Array.isArray(config.eventSeeds) ? config.eventSeeds : []).forEach(function (seed) {
      const seedId = eventId(seed && (seed.eventId != null ? seed.eventId : seed.id));
      if (!seedId) return;
      directionSteps(direction).forEach(function (stepDirection) {
        walkFromEvent(seedId, stepDirection, 1, "event", seedId, seed.regionIds || []);
      });
    });

    (Array.isArray(config.traceSeeds) ? config.traceSeeds : []).forEach(function (seed) {
      const seedId = String(seed && (seed.traceId || seed.id) || "");
      const segment = index.segmentById.get(seedId);
      if (!segment) return;
      directionSteps(direction).forEach(function (stepDirection) {
        addReachedSegment(segment, {
          hop: 1,
          direction: stepDirection,
          seedType: "trace",
          seedId,
          regionIds: seed.regionIds || [],
        });
        const nextEventId = stepDirection === "forward" ? segment.toEventId : segment.fromEventId;
        walkFromEvent(nextEventId, stepDirection, 2, "trace", seedId, seed.regionIds || []);
      });
    });

    const segments = Array.from(segmentRecords.values()).map(function (record) {
      const hops = Array.from(record.hops).sort(function (left, right) { return left - right; });
      const directions = Array.from(record.directions).sort();
      return Object.assign({}, record.segment, {
        neighborhood: {
          hop: hops.length ? hops[0] : 1,
          hops,
          direction: directions.length === 1 ? directions[0] : "both",
          directions,
          seedEventIds: Array.from(record.seedEventIds).sort(),
          seedTraceIds: Array.from(record.seedTraceIds).sort(),
          regionIds: Array.from(record.regionIds).sort(),
          attributions: record.attributions.slice(),
        },
      });
    }).sort(function (left, right) {
      const hopOrder = left.neighborhood.hop - right.neighborhood.hop;
      return hopOrder || (Number(left.sequenceIndex) - Number(right.sequenceIndex)) || left.traceId.localeCompare(right.traceId);
    });

    const events = Array.from(eventRecords.values()).map(function (record) {
      const hops = Array.from(record.hops).sort(function (left, right) { return left - right; });
      const directions = Array.from(record.directions).sort();
      return {
        eventId: record.eventId,
        neighborhood: {
          hop: hops.length ? hops[0] : 1,
          hops,
          direction: directions.length === 1 ? directions[0] : "both",
          directions,
          seedEventIds: Array.from(record.seedEventIds).sort(),
          seedTraceIds: Array.from(record.seedTraceIds).sort(),
          regionIds: Array.from(record.regionIds).sort(),
          attributions: record.attributions.slice(),
        },
      };
    }).sort(function (left, right) {
      return left.eventId.localeCompare(right.eventId);
    });

    return {
      generation: index.generation,
      depth,
      direction,
      segments,
      events,
      segmentIds: new Set(segments.map(function (segment) { return segment.traceId; })),
      eventIds: new Set(events.map(function (event) { return event.eventId; })),
      metrics: {
        indexedSegments: index.segments.length,
        reachedSegments: segments.length,
        reachedEvents: events.length,
      },
    };
  }

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  function normalizeLongitude(value) {
    let longitude = Number(value);
    if (!Number.isFinite(longitude)) return null;
    while (longitude < -180) longitude += 360;
    while (longitude >= 180) longitude -= 360;
    return longitude;
  }

  function gridCell(value, origin, cellSize) {
    return Math.floor((Number(value) - origin) / cellSize);
  }

  function gridKey(latCell, lonCell) {
    return latCell + "|" + lonCell;
  }

  function addToSetMap(map, key, value) {
    let set = map.get(key);
    if (!set) {
      set = new Set();
      map.set(key, set);
    }
    set.add(value);
  }

  function normalizedSegmentBounds(segment) {
    if (!segment || !Array.isArray(segment.from) || !Array.isArray(segment.to)) return null;
    const fromLat = Number(segment.from[0]);
    const toLat = Number(segment.to[0]);
    const fromLon = normalizeLongitude(segment.from[1]);
    let toLon = normalizeLongitude(segment.to[1]);
    if (![fromLat, toLat, fromLon, toLon].every(Number.isFinite)) return null;
    let delta = toLon - fromLon;
    if (delta > 180) delta -= 360;
    if (delta < -180) delta += 360;
    toLon = fromLon + delta;
    const midpoint = (fromLon + toLon) / 2;
    const shift = Math.floor((midpoint + 180) / 360) * 360;
    return {
      south: Math.min(fromLat, toLat),
      north: Math.max(fromLat, toLat),
      west: Math.min(fromLon - shift, toLon - shift),
      east: Math.max(fromLon - shift, toLon - shift),
    };
  }

  function buildSpatialIndex(events, segments, options) {
    const config = options || {};
    const cellSize = clamp(Number(config.cellSizeDegrees) || 12, 2, 30);
    const maxSegmentCells = Math.max(4, Math.round(Number(config.maxSegmentCells) || 64));
    const eventCells = new Map();
    const segmentCells = new Map();
    const broadSegmentLatCells = new Map();
    const eventById = new Map();
    const segmentById = new Map();

    (Array.isArray(events) ? events : []).forEach(function (event) {
      const id = eventId(event && (event.event_id != null ? event.event_id : event.eventId));
      const lat = Number(event && event.lat);
      const lon = normalizeLongitude(event && event.lon);
      if (!id || !Number.isFinite(lat) || !Number.isFinite(lon)) return;
      eventById.set(id, event);
      addToSetMap(
        eventCells,
        gridKey(gridCell(clamp(lat, -90, 90), -90, cellSize), gridCell(lon, -180, cellSize)),
        id
      );
    });

    (Array.isArray(segments) ? segments : []).forEach(function (rawSegment, index) {
      const segment = normalizedSegment(rawSegment, index);
      const bounds = normalizedSegmentBounds(segment);
      if (!segment || !bounds) return;
      segmentById.set(segment.traceId, segment);
      const minLatCell = gridCell(clamp(bounds.south, -90, 90), -90, cellSize);
      const maxLatCell = gridCell(clamp(bounds.north, -90, 90), -90, cellSize);
      const minLonCell = gridCell(bounds.west, -180, cellSize);
      const maxLonCell = gridCell(bounds.east, -180, cellSize);
      const cellCount = (maxLatCell - minLatCell + 1) * (maxLonCell - minLonCell + 1);
      if (cellCount > maxSegmentCells) {
        for (let latCell = minLatCell; latCell <= maxLatCell; latCell += 1) {
          addToSetMap(broadSegmentLatCells, String(latCell), segment.traceId);
        }
        return;
      }
      for (let latCell = minLatCell; latCell <= maxLatCell; latCell += 1) {
        for (let lonCell = minLonCell; lonCell <= maxLonCell; lonCell += 1) {
          addToSetMap(segmentCells, gridKey(latCell, lonCell), segment.traceId);
        }
      }
    });

    return {
      cellSizeDegrees: cellSize,
      maxSegmentCells,
      eventCells,
      segmentCells,
      broadSegmentLatCells,
      eventById,
      segmentById,
    };
  }

  function shiftedLongitudeBounds(bounds) {
    if (!bounds) return [];
    const west = Number(bounds.west);
    const east = Number(bounds.east);
    if (!Number.isFinite(west) || !Number.isFinite(east)) return [];
    const span = east - west;
    if (!Number.isFinite(span) || span >= 360) {
      return [{ west: -540, east: 540 }];
    }
    const output = [];
    for (let shiftIndex = -2; shiftIndex <= 2; shiftIndex += 1) {
      output.push({
        west: west + (shiftIndex * 360),
        east: east + (shiftIndex * 360),
      });
    }
    return output;
  }

  function querySpatialIndex(index, boundsList) {
    const eventIds = new Set();
    const traceIds = new Set();
    if (!index) return { eventIds, traceIds };
    const cellSize = index.cellSizeDegrees;

    (Array.isArray(boundsList) ? boundsList : []).forEach(function (bounds) {
      if (!bounds) return;
      const south = clamp(Number(bounds.south), -90, 90);
      const north = clamp(Number(bounds.north), -90, 90);
      if (!Number.isFinite(south) || !Number.isFinite(north)) return;
      const minLatCell = gridCell(Math.min(south, north), -90, cellSize);
      const maxLatCell = gridCell(Math.max(south, north), -90, cellSize);
      const longitudeBounds = shiftedLongitudeBounds(bounds);

      for (let latCell = minLatCell; latCell <= maxLatCell; latCell += 1) {
        const broad = index.broadSegmentLatCells.get(String(latCell));
        if (broad) broad.forEach(function (traceId) { traceIds.add(traceId); });

        longitudeBounds.forEach(function (longitudeRange) {
          const minLonCell = gridCell(longitudeRange.west, -180, cellSize);
          const maxLonCell = gridCell(longitudeRange.east, -180, cellSize);
          for (let lonCell = minLonCell; lonCell <= maxLonCell; lonCell += 1) {
            const key = gridKey(latCell, lonCell);
            const points = index.eventCells.get(key);
            const traces = index.segmentCells.get(key);
            if (points) points.forEach(function (id) { eventIds.add(id); });
            if (traces) traces.forEach(function (id) { traceIds.add(id); });
          }
        });
      }
    });

    return { eventIds, traceIds };
  }

  function buildNeighborhoodIndex(segments, events, generation, options) {
    const adjacency = buildAdjacencyIndex(segments, generation);
    return Object.assign(adjacency, {
      spatial: buildSpatialIndex(events, adjacency.segments, options),
    });
  }

  function midpoint(from, to) {
    if (!Array.isArray(from) || !Array.isArray(to)) return null;
    return [
      (Number(from[0]) + Number(to[0])) / 2,
      (Number(from[1]) + Number(to[1])) / 2,
    ];
  }

  function haversineKm(from, to) {
    if (!Array.isArray(from) || !Array.isArray(to)) return null;
    const lat1 = Number(from[0]);
    const lon1 = Number(from[1]);
    const lat2 = Number(to[0]);
    const lon2 = Number(to[1]);
    if (![lat1, lon1, lat2, lon2].every(Number.isFinite)) return null;
    const radians = Math.PI / 180;
    const deltaLat = (lat2 - lat1) * radians;
    let deltaLonDegrees = lon2 - lon1;
    if (deltaLonDegrees > 180) deltaLonDegrees -= 360;
    if (deltaLonDegrees < -180) deltaLonDegrees += 360;
    const deltaLon = deltaLonDegrees * radians;
    const sinLat = Math.sin(deltaLat / 2);
    const sinLon = Math.sin(deltaLon / 2);
    const a = (sinLat * sinLat) +
      (Math.cos(lat1 * radians) * Math.cos(lat2 * radians) * sinLon * sinLon);
    return 6371.0088 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
  }

  return Object.freeze({
    CRAFT_TYPE_ORDER,
    CRAFT_TYPE_LABELS,
    CRAFT_TYPE_COLORS,
    humanizeCraftTypeKey,
    canonicalCraftTypeKey,
    resolveCraftType,
    resolveCraftEndpointStyle,
    nearestPointHit,
    normalizeDepth,
    normalizeDirection,
    buildAdjacencyIndex,
    buildSpatialIndex,
    buildNeighborhoodIndex,
    querySpatialIndex,
    traverseNeighborhood,
    midpoint,
    haversineKm,
  });
});
