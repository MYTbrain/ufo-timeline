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

  function normalizeAreaDepth(value) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return 0;
    return Math.max(0, Math.min(4, Math.round(parsed)));
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

  function zeroHopSeedId(seed, key) {
    if (!seed) return "";
    return eventId(seed[key] != null ? seed[key] : seed.id);
  }

  function ensureZeroHopSegmentRecord(records, segment) {
    let record = records.get(segment.traceId);
    if (!record) {
      record = {
        segment,
        attributions: [],
        attributionKeys: new Set(),
        roles: new Set(),
        seedEventIds: new Set(),
        seedTraceIds: new Set(),
        regionIds: new Set(),
      };
      records.set(segment.traceId, record);
    }
    return record;
  }

  function addZeroHopSegmentAttribution(records, segment, attribution) {
    if (!segment) return;
    const record = ensureZeroHopSegmentRecord(records, segment);
    const regionIds = uniqueStrings(attribution.regionIds);
    const key = [
      attribution.role,
      attribution.relation,
      attribution.seedType,
      attribution.seedId,
      regionIds.join(","),
    ].join("|");
    if (!record.attributionKeys.has(key)) {
      record.attributionKeys.add(key);
      record.attributions.push({
        hop: 0,
        direction: "direct",
        role: attribution.role,
        relation: attribution.relation,
        seedType: attribution.seedType,
        seedId: attribution.seedId,
        regionIds,
      });
    }
    record.roles.add(attribution.role);
    if (attribution.seedType === "event") {
      record.seedEventIds.add(attribution.seedId);
    } else {
      record.seedTraceIds.add(attribution.seedId);
    }
    regionIds.forEach(function (regionId) {
      record.regionIds.add(regionId);
    });
  }

  function zeroHopSegmentFromRecord(record) {
    return Object.assign({}, record.segment, {
      neighborhood: {
        hop: 0,
        hops: [0],
        direction: "direct",
        directions: ["direct"],
        roles: Array.from(record.roles).sort(),
        seedEventIds: Array.from(record.seedEventIds).sort(),
        seedTraceIds: Array.from(record.seedTraceIds).sort(),
        regionIds: Array.from(record.regionIds).sort(),
        attributions: record.attributions.slice(),
      },
    });
  }

  function sortedZeroHopSegments(records) {
    return Array.from(records.values()).map(zeroHopSegmentFromRecord).sort(function (left, right) {
      const order = Number(left.sequenceIndex) - Number(right.sequenceIndex);
      return order || left.traceId.localeCompare(right.traceId);
    });
  }

  function addSegmentEndpoints(target, segment) {
    if (!segment) return;
    if (segment.fromEventId) target.add(String(segment.fromEventId));
    if (segment.toEventId) target.add(String(segment.toEventId));
  }

  function planAreaZeroHopSelection(options) {
    const config = options || {};
    const index = config.index || buildAdjacencyIndex(config.segments || [], config.generation);
    const records = new Map();
    const directEventIds = new Set();
    const directTraceIds = new Set();
    const directTraceEndpointIds = new Set();
    const incidentTraceIds = new Set();
    const incidentTraceEndpointIds = new Set();

    (Array.isArray(config.eventSeeds) ? config.eventSeeds : []).forEach(function (seed) {
      const seedId = zeroHopSeedId(seed, "eventId");
      if (!seedId) return;
      directEventIds.add(seedId);
      const incoming = index.incomingByEvent.get(seedId) || [];
      const outgoing = index.outgoingByEvent.get(seedId) || [];
      const incident = [];
      if (incoming.length) {
        incident.push({ segment: incoming[incoming.length - 1], relation: "incoming" });
      }
      if (outgoing.length) {
        incident.push({ segment: outgoing[0], relation: "outgoing" });
      }
      incident.forEach(function (entry) {
        const segment = entry.segment;
        incidentTraceIds.add(segment.traceId);
        addSegmentEndpoints(incidentTraceEndpointIds, segment);
        addZeroHopSegmentAttribution(records, segment, {
          role: "incident_from_event",
          relation: entry.relation,
          seedType: "event",
          seedId,
          regionIds: seed.regionIds || [],
        });
      });
    });

    (Array.isArray(config.traceSeeds) ? config.traceSeeds : []).forEach(function (seed) {
      const seedId = zeroHopSeedId(seed, "traceId");
      const segment = index.segmentById.get(seedId);
      if (!seedId || !segment) return;
      directTraceIds.add(seedId);
      addSegmentEndpoints(directTraceEndpointIds, segment);
      addZeroHopSegmentAttribution(records, segment, {
        role: "direct_trace",
        relation: "intersects_area",
        seedType: "trace",
        seedId,
        regionIds: seed.regionIds || [],
      });
    });

    const segments = sortedZeroHopSegments(records);
    const segmentIds = new Set(segments.map(function (segment) { return segment.traceId; }));
    const endpointEventIds = new Set();
    directTraceEndpointIds.forEach(function (id) { endpointEventIds.add(id); });
    incidentTraceEndpointIds.forEach(function (id) { endpointEventIds.add(id); });
    const plannedEventIds = new Set(directEventIds);
    endpointEventIds.forEach(function (id) { plannedEventIds.add(id); });

    return {
      generation: Number(index.generation) || 0,
      depth: 0,
      direction: "direct",
      directEventIds,
      directTraceIds,
      directTraceEndpointIds,
      incidentTraceIds,
      incidentTraceEndpointIds,
      endpointEventIds,
      plannedEventIds,
      segmentIds,
      segments,
      directTraceSegments: segments.filter(function (segment) {
        return directTraceIds.has(segment.traceId);
      }),
      incidentTraceSegments: segments.filter(function (segment) {
        return incidentTraceIds.has(segment.traceId);
      }),
      metrics: {
        indexedSegments: Array.isArray(index.segments) ? index.segments.length : 0,
        directEvents: directEventIds.size,
        directTraces: directTraceIds.size,
        incidentTraces: incidentTraceIds.size,
        plannedSegments: segments.length,
        plannedEvents: plannedEventIds.size,
      },
    };
  }

  function configuredBoolean(config, names, fallback) {
    for (const name of names) {
      if (Object.prototype.hasOwnProperty.call(config, name)) {
        return Boolean(config[name]);
      }
    }
    return Boolean(fallback);
  }

  function computeAreaZeroHopSelection(options) {
    const config = options || {};
    const plan = config.plan || planAreaZeroHopSelection(config);
    const selectEvents = configuredBoolean(config, ["selectEvents"], false);
    const selectTraces = configuredBoolean(config, ["selectTraces"], false);
    const showSelectedEvents = configuredBoolean(config, ["showSelectedEvents"], false);
    const showSelectedTraces = configuredBoolean(config, ["showSelectedTraces"], false);
    const showEventsFromTraces = configuredBoolean(config, [
      "showEventsAssociatedWithSelectedTraces",
      "showEventsFromTraces",
    ], false);
    const showTracesFromEvents = configuredBoolean(config, [
      "showTracesAssociatedWithSelectedEvents",
      "showTracesFromEvents",
    ], false);
    const selectedEventIds = selectEvents ? new Set(plan.directEventIds) : new Set();
    const selectedTraceIds = selectTraces ? new Set(plan.directTraceIds) : new Set();
    const visibleEventIds = new Set();
    const visibleTraceIds = new Set();
    const neighborhoodEventIds = new Set(selectedEventIds);
    const neighborhoodTraceIds = new Set();

    if (selectEvents && showSelectedEvents) {
      selectedEventIds.forEach(function (id) { visibleEventIds.add(id); });
    }
    if (selectTraces) {
      plan.directTraceEndpointIds.forEach(function (id) { neighborhoodEventIds.add(id); });
      plan.directTraceIds.forEach(function (id) { neighborhoodTraceIds.add(id); });
      if (showSelectedTraces) {
        plan.directTraceIds.forEach(function (id) { visibleTraceIds.add(id); });
      }
      if (showEventsFromTraces) {
        plan.directTraceEndpointIds.forEach(function (id) { visibleEventIds.add(id); });
      }
    }
    if (selectEvents) {
      plan.incidentTraceEndpointIds.forEach(function (id) { neighborhoodEventIds.add(id); });
      plan.incidentTraceIds.forEach(function (id) { neighborhoodTraceIds.add(id); });
      if (showTracesFromEvents) {
        plan.incidentTraceIds.forEach(function (id) { visibleTraceIds.add(id); });
      }
    }

    const neighborhoodSegments = plan.segments.filter(function (segment) {
      return neighborhoodTraceIds.has(segment.traceId);
    });
    const visibleTraceSegments = neighborhoodSegments.filter(function (segment) {
      return visibleTraceIds.has(segment.traceId);
    });
    return {
      generation: plan.generation,
      depth: 0,
      direction: "direct",
      selectedEventIds,
      selectedTraceIds,
      visibleEventIds,
      visibleTraceIds,
      visibleTraceSegments,
      neighborhoodSegments,
      neighborhoodEventIds,
      plan,
      metrics: {
        indexedSegments: plan.metrics.indexedSegments,
        reachedSegments: neighborhoodSegments.length,
        reachedEvents: neighborhoodEventIds.size,
        selectedEvents: selectedEventIds.size,
        selectedTraces: selectedTraceIds.size,
        visibleEvents: visibleEventIds.size,
        visibleTraces: visibleTraceIds.size,
      },
    };
  }

  const AREA_EVENT_REPRESENTATIONS = Object.freeze(["points", "clusters", "heatmap"]);

  function normalizeAreaEventRepresentation(value) {
    const representation = String(value == null ? "" : value).trim().toLowerCase();
    if (representation === "events" || representation === "event" || representation === "point") {
      return "points";
    }
    if (representation === "cluster") return "clusters";
    if (representation === "heat") return "heatmap";
    if (AREA_EVENT_REPRESENTATIONS.includes(representation) || representation === "auto") {
      return representation;
    }
    return "hidden";
  }

  function resolveAreaEventRepresentation(options) {
    const config = typeof options === "string" ? { requestedMode: options } : (options || {});
    if (config.active === false || config.showEvents === false) return "hidden";
    const requestedValue = config.requestedMode != null
      ? config.requestedMode
      : config.mapMode != null
        ? config.mapMode
        : config.mode != null
          ? config.mode
          : config.representation;
    const requested = normalizeAreaEventRepresentation(requestedValue);
    if (requested === "auto") {
      const effectiveValue = config.effectiveMode != null
        ? config.effectiveMode
        : config.resolvedMode != null
          ? config.resolvedMode
          : config.autoMode;
      const effective = normalizeAreaEventRepresentation(effectiveValue);
      return AREA_EVENT_REPRESENTATIONS.includes(effective) ? effective : "hidden";
    }
    return AREA_EVENT_REPRESENTATIONS.includes(requested) ? requested : "hidden";
  }

  function resolvedTransitionRepresentation(config, prefix) {
    const representationKey = prefix + "Representation";
    if (config[representationKey] != null) {
      return resolveAreaEventRepresentation(config[representationKey]);
    }
    const modeKey = prefix + "Mode";
    const effectiveModeKey = prefix + "EffectiveMode";
    const activeKey = prefix + "Active";
    const showEventsKey = prefix + "ShowEvents";
    return resolveAreaEventRepresentation({
      requestedMode: config[modeKey],
      effectiveMode: config[effectiveModeKey],
      active: Object.prototype.hasOwnProperty.call(config, activeKey) ? config[activeKey] : true,
      showEvents: Object.prototype.hasOwnProperty.call(config, showEventsKey) ? config[showEventsKey] : true,
    });
  }

  function planAreaEventLayerTransition(previousOrOptions, nextRepresentation) {
    const config = previousOrOptions && typeof previousOrOptions === "object" && nextRepresentation == null
      ? previousOrOptions
      : {
          previousRepresentation: previousOrOptions,
          nextRepresentation,
        };
    const previous = resolvedTransitionRepresentation(config, "previous");
    const next = resolvedTransitionRepresentation(config, "next");
    const removeRepresentations = AREA_EVENT_REPRESENTATIONS.filter(function (representation) {
      return representation !== next;
    });
    const clearRepresentations = AREA_EVENT_REPRESENTATIONS.includes(next) ? [next] : [];
    const operations = removeRepresentations.map(function (representation) {
      return { type: "remove", representation };
    });
    clearRepresentations.forEach(function (representation) {
      operations.push({ type: "clear", representation });
    });
    if (AREA_EVENT_REPRESENTATIONS.includes(next)) {
      operations.push({ type: "render", representation: next });
    }
    return {
      previousRepresentation: previous,
      nextRepresentation: next,
      changed: previous !== next,
      hidden: next === "hidden",
      removeRepresentations,
      clearRepresentations,
      renderRepresentation: AREA_EVENT_REPRESENTATIONS.includes(next) ? next : null,
      operations,
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

  const EARTH_RADIUS_KM = 6371.0088;

  function coordinatePair(value) {
    if (!Array.isArray(value) || value.length < 2) return null;
    const lat = Number(value[0]);
    const lon = Number(value[1]);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
    return [lat, lon];
  }

  function segmentCoordinates(segment) {
    if (!segment) return null;
    const from = coordinatePair(segment.from);
    const to = coordinatePair(segment.to);
    return from && to ? { from, to } : null;
  }

  function circleBounds(center, radiusKm) {
    const centerPair = coordinatePair(center);
    const radius = Number(radiusKm);
    if (!centerPair || !Number.isFinite(radius) || radius <= 0) return null;

    const centerLat = clamp(centerPair[0], -90, 90);
    const centerLon = normalizeLongitude(centerPair[1]);
    const angularRadius = Math.min(Math.PI, radius / EARTH_RADIUS_KM);
    const latitudeRadius = angularRadius * (180 / Math.PI);
    const boundsPadding = 1e-10;
    const south = clamp(centerLat - latitudeRadius - boundsPadding, -90, 90);
    const north = clamp(centerLat + latitudeRadius + boundsPadding, -90, 90);
    const reachesPole = angularRadius >= Math.PI || south <= -90 || north >= 90;
    const centerLatitudeRadians = centerLat * (Math.PI / 180);
    const longitudeRadius = reachesPole
      ? 180
      : Math.min(
        180,
        (Math.asin(clamp(
          Math.sin(angularRadius) / Math.cos(centerLatitudeRadians),
          -1,
          1
        )) * (180 / Math.PI)) + boundsPadding
      );
    return {
      south,
      north,
      west: centerLon - longitudeRadius,
      east: centerLon + longitudeRadius,
      referenceLongitude: centerLon,
    };
  }

  function unwrapSegmentNearLongitude(from, to, referenceLongitude) {
    const fromLon = normalizeLongitude(from[1]);
    let toLon = normalizeLongitude(to[1]);
    const normalizedReference = normalizeLongitude(referenceLongitude);
    if (![fromLon, toLon, normalizedReference].every(Number.isFinite)) return null;

    let longitudeDelta = toLon - fromLon;
    if (longitudeDelta > 180) longitudeDelta -= 360;
    if (longitudeDelta < -180) longitudeDelta += 360;
    toLon = fromLon + longitudeDelta;
    const midpointLon = (fromLon + toLon) / 2;
    const shift = Math.round((normalizedReference - midpointLon) / 360) * 360;
    return {
      from: [from[0], fromLon + shift],
      to: [to[0], toLon + shift],
      centerLon: normalizedReference,
    };
  }

  function pointAtFraction(from, to, fraction) {
    return [
      from[0] + ((to[0] - from[0]) * fraction),
      from[1] + ((to[1] - from[1]) * fraction),
    ];
  }

  function pointInsideCircle(point, center, radiusKm) {
    const pointPair = coordinatePair(point);
    const centerPair = coordinatePair(center);
    const radius = Number(radiusKm);
    if (!pointPair || !centerPair || !Number.isFinite(radius) || radius <= 0) return false;
    const toleranceKm = Math.max(1e-9, radius * 1e-12);
    const distance = haversineKm(centerPair, pointPair);
    return distance != null && distance <= radius + toleranceKm;
  }

  function sphericalPathEvaluation(from, to, center, fraction) {
    const radians = Math.PI / 180;
    const latitude = (from[0] + ((to[0] - from[0]) * fraction)) * radians;
    const longitudeDelta = (
      from[1] + ((to[1] - from[1]) * fraction) - center[1]
    ) * radians;
    const latitudeDelta = (to[0] - from[0]) * radians;
    const longitudeRate = (to[1] - from[1]) * radians;
    const centerLatitude = center[0] * radians;
    const sinLatitude = Math.sin(latitude);
    const cosLatitude = Math.cos(latitude);
    const sinLongitude = Math.sin(longitudeDelta);
    const cosLongitude = Math.cos(longitudeDelta);
    const sinCenter = Math.sin(centerLatitude);
    const cosCenter = Math.cos(centerLatitude);
    return {
      fraction,
      cosine: clamp(
        (sinCenter * sinLatitude) + (cosCenter * cosLatitude * cosLongitude),
        -1,
        1
      ),
      derivative:
        (sinCenter * latitudeDelta * cosLatitude) -
        (cosCenter * (
          (latitudeDelta * sinLatitude * cosLongitude) +
          (longitudeRate * cosLatitude * sinLongitude)
        )),
      secondDerivative:
        (-sinCenter * latitudeDelta * latitudeDelta * sinLatitude) -
        (cosCenter * (
          (((latitudeDelta * latitudeDelta) + (longitudeRate * longitudeRate)) *
            cosLatitude * cosLongitude) -
          (2 * latitudeDelta * longitudeRate * sinLatitude * sinLongitude)
        )),
    };
  }

  function safeguardedStationaryPoint(evaluate, left, right) {
    const derivativeTolerance = 1e-14;
    let low = left;
    let high = right;
    if (Math.abs(low.derivative) <= derivativeTolerance) return low;
    if (Math.abs(high.derivative) <= derivativeTolerance) return high;
    let current = evaluate((low.fraction + high.fraction) / 2);
    for (let iteration = 0; iteration < 18; iteration += 1) {
      if (Math.abs(current.derivative) <= derivativeTolerance) return current;
      if ((low.derivative < 0) !== (current.derivative < 0)) high = current;
      else low = current;
      let nextFraction = current.fraction -
        (current.derivative / current.secondDerivative);
      if (
        !Number.isFinite(nextFraction) ||
        nextFraction <= low.fraction ||
        nextFraction >= high.fraction
      ) {
        const denominator = high.derivative - low.derivative;
        nextFraction = denominator
          ? low.fraction -
            ((low.derivative * (high.fraction - low.fraction)) / denominator)
          : (low.fraction + high.fraction) / 2;
      }
      if (
        !Number.isFinite(nextFraction) ||
        nextFraction <= low.fraction ||
        nextFraction >= high.fraction
      ) {
        nextFraction = (low.fraction + high.fraction) / 2;
      }
      current = evaluate(nextFraction);
    }
    return Math.abs(low.derivative) <= Math.abs(high.derivative) ? low : high;
  }

  function safeguardedCircleBoundary(evaluate, threshold, left, right) {
    let low = left;
    let high = right;
    let lowDifference = low.cosine - threshold;
    let highDifference = high.cosine - threshold;
    const lowInside = lowDifference >= 0;
    for (let iteration = 0; iteration < 22; iteration += 1) {
      const denominator = highDifference - lowDifference;
      let nextFraction = denominator
        ? low.fraction -
          ((lowDifference * (high.fraction - low.fraction)) / denominator)
        : (low.fraction + high.fraction) / 2;
      if (
        !Number.isFinite(nextFraction) ||
        nextFraction <= low.fraction + 1e-15 ||
        nextFraction >= high.fraction - 1e-15
      ) {
        nextFraction = (low.fraction + high.fraction) / 2;
      }
      let current = evaluate(nextFraction);
      const difference = current.cosine - threshold;
      if (Math.abs(difference) <= 1e-15 || high.fraction - low.fraction <= 1e-13) {
        if ((difference >= 0) === lowInside) low = current;
        else high = current;
        break;
      }
      if ((difference >= 0) === lowInside) {
        low = current;
        lowDifference = difference;
      } else {
        high = current;
        highDifference = difference;
      }
      const newtonFraction = current.fraction - (difference / current.derivative);
      if (
        Number.isFinite(newtonFraction) &&
        newtonFraction > low.fraction + 1e-15 &&
        newtonFraction < high.fraction - 1e-15
      ) {
        current = evaluate(newtonFraction);
        const newtonDifference = current.cosine - threshold;
        if ((newtonDifference >= 0) === lowInside) {
          low = current;
          lowDifference = newtonDifference;
        } else {
          high = current;
          highDifference = newtonDifference;
        }
      }
    }
    return lowInside ? low : high;
  }

  function clipSegmentToCircle(segment, center, radiusKm, options) {
    const diagnostics = options && options.diagnostics && typeof options.diagnostics === "object"
      ? options.diagnostics
      : null;
    let pathEvaluationCount = 0;
    let exactDistanceEvaluationCount = 0;

    function finish(intersection) {
      const metrics = {
        pathEvaluationCount,
        exactDistanceEvaluationCount,
        totalEvaluationCount: pathEvaluationCount + exactDistanceEvaluationCount,
      };
      if (diagnostics) Object.assign(diagnostics, metrics);
      if (intersection) intersection.geometryMetrics = metrics;
      return intersection;
    }

    const coordinates = segmentCoordinates(segment);
    const centerPair = coordinatePair(center);
    const radius = Number(radiusKm);
    if (!coordinates || !centerPair || !Number.isFinite(radius) || radius <= 0) {
      return finish(null);
    }

    const unwrapped = unwrapSegmentNearLongitude(
      coordinates.from,
      coordinates.to,
      centerPair[1]
    );
    if (!unwrapped) return finish(null);
    const unwrappedCenter = [centerPair[0], unwrapped.centerLon];
    const evaluationCache = new Map();
    const evaluate = function (fraction) {
      const normalizedFraction = clamp(Number(fraction), 0, 1);
      if (evaluationCache.has(normalizedFraction)) {
        return evaluationCache.get(normalizedFraction);
      }
      pathEvaluationCount += 1;
      const result = sphericalPathEvaluation(
        unwrapped.from,
        unwrapped.to,
        unwrappedCenter,
        normalizedFraction
      );
      evaluationCache.set(normalizedFraction, result);
      return result;
    };
    const angularRadius = Math.min(Math.PI, radius / EARTH_RADIUS_KM);
    const threshold = Math.cos(angularRadius);
    const startValue = evaluate(0);
    const endValue = evaluate(1);
    const startInside = startValue.cosine >= threshold;
    const endInside = endValue.cosine >= threshold;
    const coordinateDelta =
      Math.abs(unwrapped.to[0] - unwrapped.from[0]) +
      Math.abs(unwrapped.to[1] - unwrapped.from[1]);

    if (angularRadius >= Math.PI || coordinateDelta <= 1e-14) {
      if (!startInside) return finish(null);
      return finish({
        startFraction: 0,
        endFraction: 1,
        from: unwrapped.from.slice(),
        to: unwrapped.to.slice(),
        startInside: true,
        endInside: true,
        fullyContained: true,
        tangent: false,
        intervals: [{
          startFraction: 0,
          endFraction: 1,
          from: unwrapped.from.slice(),
          to: unwrapped.to.slice(),
        }],
      });
    }

    const stationarySampleCount = 12;
    const derivativeSamples = [];
    for (let index = 0; index <= stationarySampleCount; index += 1) {
      derivativeSamples.push(evaluate(index / stationarySampleCount));
    }
    const stationaryPoints = [];
    const derivativeTolerance = 1e-14;
    derivativeSamples.forEach(function (sample) {
      if (Math.abs(sample.derivative) <= derivativeTolerance) {
        stationaryPoints.push(sample);
      }
    });
    for (let index = 1; index < derivativeSamples.length; index += 1) {
      const previous = derivativeSamples[index - 1];
      const current = derivativeSamples[index];
      if (
        Math.abs(previous.derivative) > derivativeTolerance &&
        Math.abs(current.derivative) > derivativeTolerance &&
        ((previous.derivative < 0) !== (current.derivative < 0))
      ) {
        stationaryPoints.push(safeguardedStationaryPoint(
          evaluate,
          previous,
          current
        ));
      }
    }

    const extrema = [startValue, endValue].concat(stationaryPoints).sort(function (left, right) {
      return left.fraction - right.fraction;
    });
    const knots = [];
    extrema.forEach(function (candidate) {
      const previous = knots[knots.length - 1];
      if (previous && Math.abs(previous.fraction - candidate.fraction) <= 1e-14) {
        if (candidate.cosine > previous.cosine) knots[knots.length - 1] = candidate;
        return;
      }
      knots.push(candidate);
    });

    let maximum = knots[0];
    knots.forEach(function (candidate) {
      if (
        candidate.cosine > maximum.cosine ||
        (candidate.cosine === maximum.cosine && candidate.fraction < maximum.fraction)
      ) {
        maximum = candidate;
      }
    });
    const tangentTolerance = 2e-14;
    if (maximum.cosine < threshold - tangentTolerance) return finish(null);

    const intervals = [];
    let intervalStart = knots[0].cosine >= threshold ? 0 : null;
    for (let index = 1; index < knots.length; index += 1) {
      const previous = knots[index - 1];
      const current = knots[index];
      const previousInside = previous.cosine >= threshold;
      const currentInside = current.cosine >= threshold;
      if (!previousInside && currentInside) {
        intervalStart = safeguardedCircleBoundary(
          evaluate,
          threshold,
          previous,
          current
        ).fraction;
      } else if (previousInside && !currentInside && intervalStart != null) {
        intervals.push({
          startFraction: intervalStart,
          endFraction: safeguardedCircleBoundary(
            evaluate,
            threshold,
            previous,
            current
          ).fraction,
        });
        intervalStart = null;
      }
    }
    if (intervalStart != null) {
      intervals.push({ startFraction: intervalStart, endFraction: 1 });
    }

    if (!intervals.length) {
      if (Math.abs(maximum.cosine - threshold) > tangentTolerance) return finish(null);
      intervals.push({
        startFraction: maximum.fraction,
        endFraction: maximum.fraction,
      });
    }
    function exactDistanceAtFraction(fraction) {
      exactDistanceEvaluationCount += 1;
      return haversineKm(
        unwrappedCenter,
        pointAtFraction(unwrapped.from, unwrapped.to, fraction)
      );
    }
    function nudgeBoundaryInside(fraction, interiorFraction) {
      if (exactDistanceAtFraction(fraction) <= radius) return fraction;
      const direction = Math.sign(interiorFraction - fraction);
      if (!direction) return fraction;
      let step = 1e-14;
      for (let iteration = 0; iteration < 8; iteration += 1) {
        const candidate = clamp(fraction + (direction * step), 0, 1);
        if (exactDistanceAtFraction(candidate) <= radius) return candidate;
        step *= 10;
      }
      return interiorFraction;
    }
    intervals.forEach(function (interval) {
      const originalStart = interval.startFraction;
      const originalEnd = interval.endFraction;
      interval.startFraction = nudgeBoundaryInside(originalStart, originalEnd);
      interval.endFraction = nudgeBoundaryInside(originalEnd, originalStart);
    });
    const primaryInterval = intervals.reduce(function (best, interval) {
      const bestLength = best.endFraction - best.startFraction;
      const intervalLength = interval.endFraction - interval.startFraction;
      return intervalLength > bestLength ? interval : best;
    }, intervals[0]);
    const clippedStart = clamp(primaryInterval.startFraction, 0, 1);
    const clippedEnd = clamp(primaryInterval.endFraction, 0, 1);
    const fractionTolerance = 1e-10;
    return finish({
      startFraction: clippedStart,
      endFraction: clippedEnd,
      from: pointAtFraction(unwrapped.from, unwrapped.to, clippedStart),
      to: pointAtFraction(unwrapped.from, unwrapped.to, clippedEnd),
      startInside,
      endInside,
      fullyContained:
        intervals.length === 1 &&
        clippedStart === 0 &&
        clippedEnd === 1,
      tangent: Math.abs(clippedEnd - clippedStart) <= fractionTolerance,
      intervals: intervals.map(function (interval) {
        return {
          startFraction: interval.startFraction,
          endFraction: interval.endFraction,
          from: pointAtFraction(unwrapped.from, unwrapped.to, interval.startFraction),
          to: pointAtFraction(unwrapped.from, unwrapped.to, interval.endFraction),
        };
      }),
    });
  }

  function queryCircleSpatialIndex(index, center, radiusKm) {
    const bounds = circleBounds(center, radiusKm);
    const eventIds = new Set();
    const traceIds = new Set();
    const traceIntersections = new Map();
    const metrics = {
      testedTraceCount: 0,
      pathEvaluationCount: 0,
      exactDistanceEvaluationCount: 0,
      maxPathEvaluationsPerTrace: 0,
      maxTotalEvaluationsPerTrace: 0,
    };
    if (!index || !bounds) {
      return {
        bounds,
        candidateEventIds: new Set(),
        candidateTraceIds: new Set(),
        eventIds,
        traceIds,
        traceIntersections,
        metrics,
      };
    }

    const candidates = querySpatialIndex(index, [bounds]);
    candidates.eventIds.forEach(function (id) {
      const event = index.eventById.get(String(id));
      if (!event) return;
      if (pointInsideCircle([event.lat, event.lon], center, radiusKm)) {
        eventIds.add(String(id));
      }
    });
    candidates.traceIds.forEach(function (id) {
      const segment = index.segmentById.get(String(id));
      if (!segment) return;
      const diagnostics = {};
      const intersection = clipSegmentToCircle(segment, center, radiusKm, { diagnostics });
      metrics.testedTraceCount += 1;
      metrics.pathEvaluationCount += Number(diagnostics.pathEvaluationCount) || 0;
      metrics.exactDistanceEvaluationCount += Number(diagnostics.exactDistanceEvaluationCount) || 0;
      metrics.maxPathEvaluationsPerTrace = Math.max(
        metrics.maxPathEvaluationsPerTrace,
        Number(diagnostics.pathEvaluationCount) || 0
      );
      metrics.maxTotalEvaluationsPerTrace = Math.max(
        metrics.maxTotalEvaluationsPerTrace,
        Number(diagnostics.totalEvaluationCount) || 0
      );
      if (!intersection) return;
      traceIds.add(String(id));
      traceIntersections.set(String(id), intersection);
    });
    return {
      bounds,
      candidateEventIds: candidates.eventIds,
      candidateTraceIds: candidates.traceIds,
      eventIds,
      traceIds,
      traceIntersections,
      metrics,
    };
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
    return EARTH_RADIUS_KM * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
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
    normalizeAreaDepth,
    normalizeDirection,
    buildAdjacencyIndex,
    buildSpatialIndex,
    buildNeighborhoodIndex,
    querySpatialIndex,
    circleBounds,
    pointInsideCircle,
    clipSegmentToCircle,
    queryCircleSpatialIndex,
    traverseNeighborhood,
    planAreaZeroHopSelection,
    computeAreaZeroHopSelection,
    AREA_EVENT_REPRESENTATIONS,
    normalizeAreaEventRepresentation,
    resolveAreaEventRepresentation,
    planAreaEventLayerTransition,
    midpoint,
    haversineKm,
  });
});
