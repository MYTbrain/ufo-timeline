(function () {
  "use strict";

  const EARTH_RADIUS_METERS = 6371008.8;
  const CELL_SIZE_DEGREES = 1;
  const WORLD_LON_CELL_COUNT = Math.ceil(360 / CELL_SIZE_DEGREES);
  const WORLD_LAT_CELL_COUNT = Math.ceil(180 / CELL_SIZE_DEGREES);
  const TRACE_VIEWPORT_LAT_PAD = 4;
  const TRACE_VIEWPORT_LON_PAD = 8;
  const EVIDENCE_MODE_SOURCE_COORDINATES = "source_coordinates";
  const EVIDENCE_MODE_INCLUDE_GENERALIZED = "include_generalized";
  const EVIDENCE_CLASS_SUPPORTED = "supported";
  const EVIDENCE_CLASS_POSSIBLE = "possible";
  let facilityIndexCacheKey = "";
  let facilityIndexCache = null;
  let traceEventIndexCacheKey = "";
  let traceEventIndexCache = null;

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function normalizeLongitude(longitude) {
    const value = Number(longitude);
    if (!Number.isFinite(value)) return 0;
    return ((((value + 180) % 360) + 360) % 360) - 180;
  }

  function normalizeLongitudeDelta(delta) {
    const value = Number(delta);
    if (!Number.isFinite(value)) return 0;
    return ((((value + 180) % 360) + 360) % 360) - 180;
  }

  function normalizeBigIntForRuntime(value) {
    if (typeof value !== "bigint") return value;
    const asNumber = Number(value);
    return Number.isSafeInteger(asNumber) ? asNumber : value.toString();
  }

  function metadataFieldByName(metadata, fieldName) {
    const fields = Array.isArray(metadata && metadata.fields) ? metadata.fields : [];
    return fields.find(function (field) {
      return field && field.name === fieldName;
    }) || null;
  }

  function packedTraceDataView(bufferOrView) {
    if (bufferOrView instanceof DataView) return bufferOrView;
    if (bufferOrView instanceof ArrayBuffer) return new DataView(bufferOrView);
    if (ArrayBuffer.isView(bufferOrView)) {
      return new DataView(bufferOrView.buffer, bufferOrView.byteOffset, bufferOrView.byteLength);
    }
    return null;
  }

  async function fetchArrayBufferFromWorker(url) {
    const response = await fetch(url, { cache: "force-cache" });
    if (!response.ok) {
      throw new Error("Worker fetch failed for " + url + " with HTTP " + response.status + ".");
    }
    return response.arrayBuffer();
  }

  async function fetchGzipArrayBufferFromWorker(url) {
    if (typeof DecompressionStream !== "function") {
      throw new Error("Worker gzip decoding is not supported in this browser.");
    }
    const response = await fetch(url, { cache: "force-cache" });
    if (!response.ok) {
      throw new Error("Worker gzip fetch failed for " + url + " with HTTP " + response.status + ".");
    }
    if (!response.body) {
      throw new Error("Worker gzip fetch returned no response body for " + url + ".");
    }
    const stream = response.body.pipeThrough(new DecompressionStream("gzip"));
    return new Response(stream).arrayBuffer();
  }

  async function fetchArrayBufferPreferGzipFromWorker(rawUrl, gzipUrl) {
    if (gzipUrl) {
      try {
        return await fetchGzipArrayBufferFromWorker(gzipUrl);
      } catch (error) {
        if (!rawUrl) throw error;
      }
    }
    if (!rawUrl) {
      throw new Error("Worker packed trace binary URL is missing.");
    }
    return fetchArrayBufferFromWorker(rawUrl);
  }

  function decodePackedTraceField(metadata, bufferOrView, fieldName, rowIndex) {
    const rowCount = Number(metadata && metadata.row_count);
    const bytesPerRow = Number(metadata && metadata.bytes_per_row);
    if (!Number.isSafeInteger(rowCount) || !Number.isSafeInteger(bytesPerRow)) return null;
    if (!Number.isSafeInteger(rowIndex) || rowIndex < 0 || rowIndex >= rowCount) return null;
    const field = metadataFieldByName(metadata, fieldName);
    const view = packedTraceDataView(bufferOrView);
    if (!field || !view) return null;
    const offset = (rowIndex * bytesPerRow) + Number(field.offset);
    const littleEndian = true;
    let value;
    if (field.type === "uint64") {
      value = normalizeBigIntForRuntime(view.getBigUint64(offset, littleEndian));
    } else if (field.type === "int64") {
      value = normalizeBigIntForRuntime(view.getBigInt64(offset, littleEndian));
    } else if (field.type === "float64") {
      value = view.getFloat64(offset, littleEndian);
    } else if (field.type === "float32") {
      value = view.getFloat32(offset, littleEndian);
    } else if (field.type === "int32") {
      value = view.getInt32(offset, littleEndian);
    } else if (field.type === "uint32" || field.type === "lookup:uint32") {
      value = view.getUint32(offset, littleEndian);
    } else if (field.type === "uint16") {
      value = view.getUint16(offset, littleEndian);
    } else {
      return null;
    }
    if (field.lookup_table) {
      const lookupTable = (metadata.lookup_tables && metadata.lookup_tables[field.lookup_table]) || [];
      return Object.prototype.hasOwnProperty.call(lookupTable, value) ? lookupTable[value] : null;
    }
    return value;
  }

  function parseIsoParts(isoDate) {
    const match = /^(-?\d{1,6})-(\d{2})-(\d{2})$/.exec(String(isoDate || ""));
    if (!match) return null;
    return {
      year: Number(match[1]),
      month: Number(match[2]),
      day: Number(match[3]),
    };
  }

  function daysFromCivil(year, month, day) {
    let y = Number(year);
    const m = Number(month);
    const d = Number(day);
    y -= m <= 2 ? 1 : 0;
    const era = y >= 0 ? Math.floor(y / 400) : Math.floor((y - 399) / 400);
    const yearOfEra = y - era * 400;
    const monthPrime = m + (m > 2 ? -3 : 9);
    const dayOfYear = Math.floor((153 * monthPrime + 2) / 5) + d - 1;
    const dayOfEra = yearOfEra * 365 + Math.floor(yearOfEra / 4) - Math.floor(yearOfEra / 100) + dayOfYear;
    return era * 146097 + dayOfEra - 719468;
  }

  function isoToOrdinal(isoDate) {
    const parts = parseIsoParts(isoDate);
    if (!parts) return null;
    return daysFromCivil(parts.year, parts.month, parts.day);
  }

  function sortDateIsoFromPackedKey(sortDateKey) {
    if (!Number.isSafeInteger(sortDateKey) || sortDateKey <= 0) return null;
    const value = String(sortDateKey).padStart(8, "0");
    return value.slice(0, 4) + "-" + value.slice(4, 6) + "-" + value.slice(6, 8);
  }

  function normalizedPackedTraceSortOrdinal(metadata, view, rowIndex) {
    const sortDateKey = Number(decodePackedTraceField(metadata, view, "sort_date_key", rowIndex));
    const sortDateIso = sortDateIsoFromPackedKey(sortDateKey);
    if (sortDateIso) {
      const ordinal = isoToOrdinal(sortDateIso);
      if (Number.isFinite(ordinal)) return ordinal;
    }
    const rawSortOrdinal = Number(decodePackedTraceField(metadata, view, "sort_ordinal", rowIndex));
    return Number.isFinite(rawSortOrdinal) ? rawSortOrdinal : null;
  }

  function decodePackedTraceEventIndexRow(metadata, view, rowIndex) {
    const eventId = decodePackedTraceField(metadata, view, "event_id", rowIndex);
    if (eventId == null) return null;
    const lat = Number(decodePackedTraceField(metadata, view, "lat", rowIndex));
    const lon = Number(decodePackedTraceField(metadata, view, "lon", rowIndex));
    const sortOrdinal = normalizedPackedTraceSortOrdinal(metadata, view, rowIndex);
    const sequenceIndex = Number(decodePackedTraceField(metadata, view, "sequence_index", rowIndex));
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || !Number.isFinite(sortOrdinal)) return null;
    return {
      event_id: eventId,
      lat,
      lon,
      sort_ordinal: sortOrdinal,
      sequence_index: Number.isFinite(sequenceIndex) ? sequenceIndex : rowIndex,
    };
  }

  function packedTraceSortOrdinalLowerBound(cache, targetOrdinal) {
    let low = 0;
    let high = cache && cache.rowCount ? cache.rowCount : 0;
    while (low < high) {
      const mid = Math.floor((low + high) / 2);
      const value = normalizedPackedTraceSortOrdinal(cache.metadata, cache.view, mid);
      if (value == null || value >= targetOrdinal) high = mid;
      else low = mid + 1;
    }
    return low;
  }

  function packedTraceSortOrdinalUpperBound(cache, targetOrdinal) {
    let low = 0;
    let high = cache && cache.rowCount ? cache.rowCount : 0;
    while (low < high) {
      const mid = Math.floor((low + high) / 2);
      const value = normalizedPackedTraceSortOrdinal(cache.metadata, cache.view, mid);
      if (value == null || value > targetOrdinal) high = mid;
      else low = mid + 1;
    }
    return low;
  }

  function packedTraceOrdinalScanRange(cache, payload) {
    const rowCount = cache && cache.rowCount ? cache.rowCount : 0;
    const startOrdinal = Number(payload && payload.startOrdinal);
    const endOrdinal = Number(payload && payload.endOrdinal);
    if (!rowCount || !Number.isFinite(startOrdinal) || !Number.isFinite(endOrdinal)) {
      return { startRow: 0, endRow: rowCount, bounded: false };
    }
    const startRow = packedTraceSortOrdinalLowerBound(cache, Math.min(startOrdinal, endOrdinal));
    const endRow = packedTraceSortOrdinalUpperBound(cache, Math.max(startOrdinal, endOrdinal));
    return {
      startRow: clamp(startRow, 0, rowCount),
      endRow: clamp(endRow, 0, rowCount),
      bounded: true,
    };
  }

  function bucketKeyForGapDays(gapDays) {
    const safeGap = Math.max(0, Number(gapDays) || 0);
    if (safeGap <= 1) return "gap_le_1";
    if (safeGap <= 2) return "gap_le_2";
    if (safeGap <= 7) return "gap_le_7";
    if (safeGap <= 30) return "gap_le_30";
    return "gap_gt_30";
  }

  function canonicalTraceId(fromEventId, toEventId) {
    return String(fromEventId) + "->" + String(toEventId);
  }

  function shortestWrappedSegment(previousEvent, currentEvent) {
    const fromLon = normalizeLongitude(previousEvent.lon);
    const deltaLon = shortestLongitudeDelta(fromLon, normalizeLongitude(currentEvent.lon));
    return {
      from: [previousEvent.lat, fromLon],
      to: [currentEvent.lat, fromLon + deltaLon],
    };
  }

  function traceSegmentMayIntersectSerializedBounds(segment, bounds) {
    if (!segment || !segment.from || !segment.to || !bounds) return true;
    const south = Number(bounds.south) - TRACE_VIEWPORT_LAT_PAD;
    const north = Number(bounds.north) + TRACE_VIEWPORT_LAT_PAD;
    const minLat = Math.min(Number(segment.from[0]), Number(segment.to[0]));
    const maxLat = Math.max(Number(segment.from[0]), Number(segment.to[0]));
    if (maxLat < south || minLat > north) return false;
    const west = Number(bounds.west) - TRACE_VIEWPORT_LON_PAD;
    const east = Number(bounds.east) + TRACE_VIEWPORT_LON_PAD;
    if (!Number.isFinite(west) || !Number.isFinite(east) || (east - west) >= 360 || east < west) return true;
    const minLon = Math.min(Number(segment.from[1]), Number(segment.to[1]));
    const maxLon = Math.max(Number(segment.from[1]), Number(segment.to[1]));
    return !(maxLon < west || minLon > east);
  }

  function unwrapLongitudeNear(lon, anchorLon) {
    return Number(anchorLon) + normalizeLongitudeDelta(Number(lon) - Number(anchorLon));
  }

  function shortestLongitudeDelta(fromLon, toLon) {
    return normalizeLongitudeDelta(Number(toLon) - Number(fromLon));
  }

  function distanceMetersBetweenLatLngs(lat1, lon1, lat2, lon2) {
    const phi1 = (Number(lat1) * Math.PI) / 180;
    const phi2 = (Number(lat2) * Math.PI) / 180;
    const deltaPhi = ((Number(lat2) - Number(lat1)) * Math.PI) / 180;
    const deltaLambda = (shortestLongitudeDelta(Number(lon1), Number(lon2)) * Math.PI) / 180;
    const sinPhi = Math.sin(deltaPhi / 2);
    const sinLambda = Math.sin(deltaLambda / 2);
    const a = (sinPhi * sinPhi) + (Math.cos(phi1) * Math.cos(phi2) * sinLambda * sinLambda);
    return EARTH_RADIUS_METERS * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
  }

  function traceFacilityPointCellKey(lat, lon) {
    const latCell = Math.floor((clamp(Number(lat), -90, 89.999999) + 90) / CELL_SIZE_DEGREES);
    const lonCell = Math.floor((normalizeLongitude(Number(lon)) + 180) / CELL_SIZE_DEGREES);
    return latCell + ":" + lonCell;
  }

  function temporalOrdinal(value) {
    if (value == null || value === "") return null;
    const ordinal = Number(value);
    return Number.isNaN(ordinal) ? null : ordinal;
  }

  function normalizeTemporalInterval(interval) {
    if (!interval) return null;
    const rawStart = Array.isArray(interval)
      ? interval[0]
      : (interval.startOrdinal != null ? interval.startOrdinal : interval.start);
    const rawEnd = Array.isArray(interval)
      ? interval[1]
      : (interval.endOrdinal != null ? interval.endOrdinal : interval.end);
    let startOrdinal = temporalOrdinal(rawStart);
    let endOrdinal = temporalOrdinal(rawEnd);
    if (startOrdinal == null && endOrdinal == null) return null;
    if (startOrdinal == null) startOrdinal = Number.NEGATIVE_INFINITY;
    if (endOrdinal == null) endOrdinal = Number.POSITIVE_INFINITY;
    if (startOrdinal > endOrdinal) {
      const swap = startOrdinal;
      startOrdinal = endOrdinal;
      endOrdinal = swap;
    }
    let startBoundaryEndOrdinal = temporalOrdinal(
      !Array.isArray(interval) ? interval.startBoundaryEndOrdinal : null
    );
    let endBoundaryStartOrdinal = temporalOrdinal(
      !Array.isArray(interval) ? interval.endBoundaryStartOrdinal : null
    );
    if (startBoundaryEndOrdinal != null) {
      startBoundaryEndOrdinal = clamp(startBoundaryEndOrdinal, startOrdinal, endOrdinal);
    }
    if (endBoundaryStartOrdinal != null) {
      endBoundaryStartOrdinal = clamp(endBoundaryStartOrdinal, startOrdinal, endOrdinal);
    }
    return {
      startOrdinal,
      endOrdinal,
      startBoundaryEndOrdinal,
      endBoundaryStartOrdinal,
    };
  }

  function normalizeTemporalIntervals(point) {
    const normalized = [];
    const rawIntervals = Array.isArray(point && point.temporalIntervals)
      ? point.temporalIntervals
      : [];
    rawIntervals.forEach(function (interval) {
      const value = normalizeTemporalInterval(interval);
      if (value) normalized.push(value);
    });
    if (normalized.length) return normalized;
    const scalarInterval = normalizeTemporalInterval({
      startOrdinal: point && point.startOrdinal,
      endOrdinal: point && point.endOrdinal,
      startBoundaryEndOrdinal: point && point.startBoundaryEndOrdinal,
      endBoundaryStartOrdinal: point && point.endBoundaryStartOrdinal,
    });
    return scalarInterval ? [scalarInterval] : [];
  }

  function normalizedEventIdSet(values) {
    return new Set((Array.isArray(values) ? values : []).map(String));
  }

  function buildFacilityIndex(points, evidenceContext) {
    const index = {
      points: [],
      grid: new Map(),
      sourceCoordinateEventIds: normalizedEventIdSet(
        evidenceContext && evidenceContext.sourceCoordinateEventIds
      ),
      exactDateEventIds: normalizedEventIdSet(
        evidenceContext && evidenceContext.exactDateEventIds
      ),
    };
    if (!Array.isArray(points)) return index;
    points.forEach(function (point, pointIndex) {
      const lat = Number(point && point.lat);
      const lon = normalizeLongitude(Number(point && point.lon));
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
      const facility = {
        lat,
        lon,
        source: point.source || "",
        id: point.id || ("facility:" + pointIndex),
        facilityKey: String(point.facilityKey || ((point.source || "facility") + ":" + (point.id || ("facility:" + pointIndex)))),
        temporalKnown: point.temporalKnown === true,
        temporalIntervals: normalizeTemporalIntervals(point),
      };
      index.points.push(facility);
      const key = traceFacilityPointCellKey(lat, lon);
      const bucket = index.grid.get(key) || [];
      bucket.push(facility);
      index.grid.set(key, bucket);
    });
    return index;
  }

  function facilityKey(facility) {
    if (!facility) return "";
    return String(facility.facilityKey || ((facility.source || "facility") + ":" + (facility.id || "unknown")));
  }

  function uniqueFacilities(facilities) {
    const unique = [];
    const seen = new Set();
    (facilities || []).forEach(function (facility) {
      const key = facilityKey(facility);
      if (!key || seen.has(key)) return;
      seen.add(key);
      unique.push(facility);
    });
    return unique;
  }

  function normalizedEvidenceMode(payload) {
    const filter = payload && payload.filter ? payload.filter : {};
    const rawMode = String(
      (payload && payload.evidenceMode) || filter.evidenceMode || EVIDENCE_MODE_SOURCE_COORDINATES
    );
    return rawMode === EVIDENCE_MODE_INCLUDE_GENERALIZED
      ? EVIDENCE_MODE_INCLUDE_GENERALIZED
      : EVIDENCE_MODE_SOURCE_COORDINATES;
  }

  function sourceCoordinateEventIdSet(payload) {
    if (Array.isArray(payload && payload.sourceCoordinateEventIds)) {
      return normalizedEventIdSet(payload.sourceCoordinateEventIds);
    }
    const index = payload && payload.__facilityIndex;
    return index && index.sourceCoordinateEventIds instanceof Set
      ? index.sourceCoordinateEventIds
      : new Set();
  }

  function exactDateEventIdSet(payload) {
    if (Array.isArray(payload && payload.exactDateEventIds)) {
      return normalizedEventIdSet(payload.exactDateEventIds);
    }
    const index = payload && payload.__facilityIndex;
    return index && index.exactDateEventIds instanceof Set
      ? index.exactDateEventIds
      : new Set();
  }

  function facilitySourceIsClaimed(facility) {
    return String(facility && facility.source || "").toLowerCase() === "claimedufobases";
  }

  function ordinalIsInRange(ordinal, startOrdinal, endOrdinal) {
    return ordinal >= startOrdinal && ordinal <= endOrdinal;
  }

  function rangesOverlap(startA, endA, startB, endB) {
    return startA <= endB && endA >= startB;
  }

  function intervalBoundaryContainsOrdinal(interval, ordinal) {
    return Boolean(
      (interval.startBoundaryEndOrdinal != null && ordinalIsInRange(
        ordinal,
        interval.startOrdinal,
        interval.startBoundaryEndOrdinal
      )) ||
      (interval.endBoundaryStartOrdinal != null && ordinalIsInRange(
        ordinal,
        interval.endBoundaryStartOrdinal,
        interval.endOrdinal
      ))
    );
  }

  function intervalBoundaryOverlapsRange(interval, startOrdinal, endOrdinal) {
    return Boolean(
      (interval.startBoundaryEndOrdinal != null && rangesOverlap(
        startOrdinal,
        endOrdinal,
        interval.startOrdinal,
        interval.startBoundaryEndOrdinal
      )) ||
      (interval.endBoundaryStartOrdinal != null && rangesOverlap(
        startOrdinal,
        endOrdinal,
        interval.endBoundaryStartOrdinal,
        interval.endOrdinal
      ))
    );
  }

  function facilityTemporalEvaluationAtOrdinal(facility, sortOrdinal) {
    if (!facility || facility.temporalKnown !== true) {
      return { status: "unknown", reason: "facility_time_unknown" };
    }
    const ordinal = temporalOrdinal(sortOrdinal);
    const intervals = Array.isArray(facility.temporalIntervals) ? facility.temporalIntervals : [];
    if (ordinal == null || !intervals.length) {
      return { status: "unknown", reason: "facility_time_unknown" };
    }
    let boundaryUnknown = false;
    let active = false;
    intervals.forEach(function (interval) {
      if (!ordinalIsInRange(ordinal, interval.startOrdinal, interval.endOrdinal)) return;
      if (intervalBoundaryContainsOrdinal(interval, ordinal)) boundaryUnknown = true;
      else active = true;
    });
    if (active) return { status: "active", reason: "" };
    if (boundaryUnknown) return { status: "unknown", reason: "facility_time_boundary" };
    return { status: "inactive", reason: "" };
  }

  function facilityTemporalStatusAtOrdinal(facility, sortOrdinal) {
    return facilityTemporalEvaluationAtOrdinal(facility, sortOrdinal).status;
  }

  function facilityTemporalEvaluationForSegment(facility, fromOrdinal, toOrdinal) {
    if (!facility || facility.temporalKnown !== true) {
      return { status: "unknown", reason: "facility_time_unknown" };
    }
    const from = temporalOrdinal(fromOrdinal);
    const to = temporalOrdinal(toOrdinal);
    const intervals = Array.isArray(facility.temporalIntervals) ? facility.temporalIntervals : [];
    if (from == null || to == null || !intervals.length) {
      return { status: "unknown", reason: "facility_time_unknown" };
    }
    const startOrdinal = Math.min(from, to);
    const endOrdinal = Math.max(from, to);
    let boundaryUnknown = false;
    let active = false;
    intervals.forEach(function (interval) {
      if (!rangesOverlap(startOrdinal, endOrdinal, interval.startOrdinal, interval.endOrdinal)) return;
      if (intervalBoundaryOverlapsRange(interval, startOrdinal, endOrdinal)) boundaryUnknown = true;
      else active = true;
    });
    // A chronological connector that touches an imprecise opening/closing year
    // remains uncertain even when another portion overlaps the known interior.
    if (boundaryUnknown) return { status: "unknown", reason: "facility_time_boundary" };
    if (active) return { status: "active", reason: "" };
    return { status: "inactive", reason: "" };
  }

  function facilityTemporalStatusForSegment(facility, fromOrdinal, toOrdinal) {
    return facilityTemporalEvaluationForSegment(facility, fromOrdinal, toOrdinal).status;
  }

  function segmentEndpointContext(segment, endpointName, sourceCoordinateEventIds, exactDateEventIds) {
    const isFrom = endpointName === "from";
    const eventId = isFrom ? segment.fromEventId : segment.toEventId;
    const sortOrdinal = isFrom
      ? (segment.fromSortOrdinal != null ? segment.fromSortOrdinal : segment.fromOrdinal)
      : (segment.toSortOrdinal != null ? segment.toSortOrdinal : segment.toOrdinal);
    return {
      eventId,
      sortOrdinal: temporalOrdinal(sortOrdinal),
      sourceCoordinates: eventId != null && sourceCoordinateEventIds.has(String(eventId)),
      exactDate: eventId != null && exactDateEventIds.has(String(eventId)),
    };
  }

  function endpointFacilityEvidence(facilities, endpointContext) {
    const evidence = [];
    (facilities || []).forEach(function (facility) {
      const temporalEvaluation = facilityTemporalEvaluationAtOrdinal(facility, endpointContext.sortOrdinal);
      if (temporalEvaluation.status === "inactive") return;
      const reasons = [];
      if (!endpointContext.sourceCoordinates) reasons.push("generalized_location");
      if (!endpointContext.exactDate) reasons.push("non_exact_date");
      if (temporalEvaluation.status === "unknown") reasons.push(temporalEvaluation.reason);
      if (facilitySourceIsClaimed(facility)) reasons.push("claimed_facility_source");
      const evidenceClass = (
        endpointContext.sourceCoordinates &&
        endpointContext.exactDate &&
        temporalEvaluation.status === "active" &&
        !facilitySourceIsClaimed(facility)
      ) ? EVIDENCE_CLASS_SUPPORTED : EVIDENCE_CLASS_POSSIBLE;
      evidence.push({ facility, evidenceClass, reasons });
    });
    return evidence;
  }

  function passFacilityEvidence(facilities, fromContext, toContext) {
    const evidence = [];
    (facilities || []).forEach(function (facility) {
      const temporalEvaluation = facilityTemporalEvaluationForSegment(
        facility,
        fromContext.sortOrdinal,
        toContext.sortOrdinal
      );
      if (temporalEvaluation.status === "inactive") {
        return;
      }
      const reasons = ["connector_intersection"];
      if (temporalEvaluation.status === "unknown") reasons.push(temporalEvaluation.reason);
      if (facilitySourceIsClaimed(facility)) reasons.push("claimed_facility_source");
      evidence.push({ facility, evidenceClass: EVIDENCE_CLASS_POSSIBLE, reasons });
    });
    return evidence;
  }

  function preferredEndpointEvidence(evidence) {
    const supported = (evidence || []).filter(function (entry) {
      return entry.evidenceClass === EVIDENCE_CLASS_SUPPORTED;
    });
    if (supported.length) return supported;
    return (evidence || []).filter(function (entry) {
      return entry.evidenceClass === EVIDENCE_CLASS_POSSIBLE;
    });
  }

  function evidenceAllowedInMode(evidence, evidenceMode) {
    if (evidenceMode === EVIDENCE_MODE_INCLUDE_GENERALIZED) return evidence || [];
    return (evidence || []).filter(function (entry) {
      return entry.evidenceClass === EVIDENCE_CLASS_SUPPORTED;
    });
  }

  function traceEndpointFacilitiesNear(lat, lon, index, radiusMeters) {
    if (!index || !index.points.length) return [];
    const pointLat = Number(lat);
    const pointLon = normalizeLongitude(Number(lon));
    if (!Number.isFinite(pointLat) || !Number.isFinite(pointLon)) return [];
    const radiusKm = radiusMeters / 1000;
    const latDelta = radiusKm / 110.574;
    const lonDenominator = Math.max(0.08, Math.abs(Math.cos((pointLat * Math.PI) / 180))) * 111.32;
    const lonDelta = Math.min(180, radiusKm / lonDenominator);
    const minLatCell = Math.floor((clamp(pointLat - latDelta, -90, 89.999999) + 90) / CELL_SIZE_DEGREES);
    const maxLatCell = Math.floor((clamp(pointLat + latDelta, -90, 89.999999) + 90) / CELL_SIZE_DEGREES);
    const minLonCell = Math.floor((normalizeLongitude(pointLon - lonDelta) + 180) / CELL_SIZE_DEGREES);
    const maxLonCell = Math.floor((normalizeLongitude(pointLon + lonDelta) + 180) / CELL_SIZE_DEGREES);
    const lonCells = [];
    if (minLonCell <= maxLonCell) {
      for (let cell = minLonCell; cell <= maxLonCell; cell += 1) lonCells.push(cell);
    } else {
      for (let cell = 0; cell <= maxLonCell; cell += 1) lonCells.push(cell);
      for (let cell = minLonCell; cell < WORLD_LON_CELL_COUNT; cell += 1) lonCells.push(cell);
    }
    const matches = [];
    const seen = new Set();
    for (let latCell = minLatCell; latCell <= maxLatCell; latCell += 1) {
      if (latCell < 0 || latCell >= WORLD_LAT_CELL_COUNT) continue;
      for (const lonCell of lonCells) {
        const candidates = index.grid.get(latCell + ":" + lonCell) || [];
        for (const facility of candidates) {
          if (distanceMetersBetweenLatLngs(pointLat, pointLon, facility.lat, facility.lon) <= radiusMeters) {
            const key = facilityKey(facility);
            if (key && !seen.has(key)) {
              seen.add(key);
              matches.push(facility);
            }
          }
        }
      }
    }
    return matches;
  }

  function traceEndpointNearFacility(lat, lon, index, radiusMeters) {
    return traceEndpointFacilitiesNear(lat, lon, index, radiusMeters).length > 0;
  }

  function traceFacilityCandidatePointsForSegment(segment, index, radiusMeters, stats) {
    if (!segment || !index || !index.points.length) return [];
    const fromLat = Number(segment.from && segment.from[0]);
    const fromLon = Number(segment.from && segment.from[1]);
    const toLat = Number(segment.to && segment.to[0]);
    const toLon = fromLon + normalizeLongitudeDelta(Number(segment.to && segment.to[1]) - fromLon);
    if (![fromLat, fromLon, toLat, toLon].every(Number.isFinite)) return [];

    const radiusKm = radiusMeters / 1000;
    const minLat = clamp(Math.min(fromLat, toLat) - (radiusKm / 110.574), -90, 89.999999);
    const maxLat = clamp(Math.max(fromLat, toLat) + (radiusKm / 110.574), -90, 89.999999);
    const referenceLat = clamp((fromLat + toLat) / 2, -89.5, 89.5);
    const lonDenominator = Math.max(0.08, Math.abs(Math.cos((referenceLat * Math.PI) / 180))) * 111.32;
    const lonDelta = Math.min(180, radiusKm / lonDenominator);
    const minLon = Math.min(fromLon, toLon) - lonDelta;
    const maxLon = Math.max(fromLon, toLon) + lonDelta;
    const minLatCell = Math.floor((minLat + 90) / CELL_SIZE_DEGREES);
    const maxLatCell = Math.floor((maxLat + 90) / CELL_SIZE_DEGREES);
    const minLonCell = Math.floor((minLon + 180) / CELL_SIZE_DEGREES);
    const maxLonCell = Math.floor((maxLon + 180) / CELL_SIZE_DEGREES);
    const estimatedCells = Math.max(0, maxLatCell - minLatCell + 1) * Math.max(0, maxLonCell - minLonCell + 1);
    if (estimatedCells > 5000) {
      stats.passesSkippedSegments += 1;
      return [];
    }

    const candidates = [];
    const seen = new Set();
    for (let latCell = minLatCell; latCell <= maxLatCell; latCell += 1) {
      if (latCell < 0 || latCell >= WORLD_LAT_CELL_COUNT) continue;
      for (let lonCell = minLonCell; lonCell <= maxLonCell; lonCell += 1) {
        const wrappedLonCell = ((lonCell % WORLD_LON_CELL_COUNT) + WORLD_LON_CELL_COUNT) % WORLD_LON_CELL_COUNT;
        const bucket = index.grid.get(latCell + ":" + wrappedLonCell) || [];
        for (const facility of bucket) {
          const key = facility.source + ":" + facility.id;
          if (seen.has(key)) continue;
          seen.add(key);
          candidates.push(facility);
        }
      }
    }
    return candidates;
  }

  function distanceMetersFromFacilityToTraceSegment(facility, segment) {
    const fromLat = Number(segment.from && segment.from[0]);
    const fromLon = Number(segment.from && segment.from[1]);
    const toLat = Number(segment.to && segment.to[0]);
    const toLon = fromLon + normalizeLongitudeDelta(Number(segment.to && segment.to[1]) - fromLon);
    const facilityLat = Number(facility && facility.lat);
    const facilityLon = unwrapLongitudeNear(Number(facility && facility.lon), fromLon);
    if (![fromLat, fromLon, toLat, toLon, facilityLat, facilityLon].every(Number.isFinite)) {
      return Number.POSITIVE_INFINITY;
    }

    const metersPerDegreeLat = 111320;
    const referenceLat = clamp((fromLat + toLat + facilityLat) / 3, -89.5, 89.5);
    const metersPerDegreeLon = Math.max(1, Math.cos((referenceLat * Math.PI) / 180) * metersPerDegreeLat);
    const ax = fromLon * metersPerDegreeLon;
    const ay = fromLat * metersPerDegreeLat;
    const bx = toLon * metersPerDegreeLon;
    const by = toLat * metersPerDegreeLat;
    const px = facilityLon * metersPerDegreeLon;
    const py = facilityLat * metersPerDegreeLat;
    const dx = bx - ax;
    const dy = by - ay;
    const denominator = (dx * dx) + (dy * dy);
    if (!denominator) return Math.hypot(px - ax, py - ay);
    const ratio = clamp(((px - ax) * dx + (py - ay) * dy) / denominator, 0, 1);
    return Math.hypot(px - (ax + dx * ratio), py - (ay + dy * ratio));
  }

  function segmentFacilitiesPassedNear(segment, index, radiusMeters, stats) {
    const candidates = traceFacilityCandidatePointsForSegment(segment, index, radiusMeters, stats);
    const matches = [];
    for (const facility of candidates) {
      if (distanceMetersFromFacilityToTraceSegment(facility, segment) <= radiusMeters) {
        matches.push(facility);
      }
    }
    return uniqueFacilities(matches);
  }

  function segmentPassesNearFacility(segment, index, radiusMeters, stats) {
    return segmentFacilitiesPassedNear(segment, index, radiusMeters, stats).length > 0;
  }

  function defaultStats(scope) {
    return {
      scope: scope || "worker",
      enabled: true,
      candidateSegments: 0,
      matchedSegments: 0,
      hiddenSegments: 0,
      startSegments: 0,
      endSegments: 0,
      betweenSegments: 0,
      passesSegments: 0,
      passesSkippedSegments: 0,
      supportedSegments: 0,
      possibleSegments: 0,
      excludedEvidenceSegments: 0,
      excludedEvidenceReasons: {},
      generalizedEndpointSegments: 0,
      temporalUnknownSegments: 0,
      knownInactiveFacilitiesExcluded: 0,
      noEndpointMatchSegments: 0,
      disabledClassSegments: 0,
    };
  }

  function recordExcludedEvidenceReasons(stats, reasons) {
    const uniqueReasons = new Set((reasons || []).filter(Boolean));
    if (!uniqueReasons.size) uniqueReasons.add("possible_evidence");
    uniqueReasons.forEach(function (reason) {
      stats.excludedEvidenceReasons[reason] = (stats.excludedEvidenceReasons[reason] || 0) + 1;
    });
  }

  function evidenceReasons(evidence) {
    const reasons = [];
    (evidence || []).forEach(function (entry) {
      (Array.isArray(entry && entry.reasons) ? entry.reasons : []).forEach(function (reason) {
        if (reason) reasons.push(reason);
      });
    });
    return reasons;
  }

  function record(stats, classKey, visible, reason, evidenceClass, excludedReasons) {
    stats.candidateSegments += 1;
    if (visible) {
      stats.matchedSegments += 1;
      if (classKey === "start") stats.startSegments += 1;
      if (classKey === "end") stats.endSegments += 1;
      if (classKey === "between") stats.betweenSegments += 1;
      if (classKey === "passes") stats.passesSegments += 1;
      if (evidenceClass === EVIDENCE_CLASS_SUPPORTED) stats.supportedSegments += 1;
      if (evidenceClass === EVIDENCE_CLASS_POSSIBLE) stats.possibleSegments += 1;
      return;
    }
    stats.hiddenSegments += 1;
    if (reason === "location_evidence_excluded") {
      stats.excludedEvidenceSegments += 1;
      recordExcludedEvidenceReasons(stats, excludedReasons);
    } else if (reason === "disabled_class") {
      stats.disabledClassSegments += 1;
    } else {
      stats.noEndpointMatchSegments += 1;
    }
  }

  function classifySegment(
    segment,
    index,
    radiusMeters,
    classes,
    stats,
    evidenceMode,
    sourceCoordinateEventIds,
    exactDateEventIds
  ) {
    if (!segment || !Array.isArray(segment.from) || !Array.isArray(segment.to)) {
      record(stats, null, false, "invalid_segment");
      return null;
    }
    const fromContext = segmentEndpointContext(
      segment,
      "from",
      sourceCoordinateEventIds,
      exactDateEventIds
    );
    const toContext = segmentEndpointContext(
      segment,
      "to",
      sourceCoordinateEventIds,
      exactDateEventIds
    );
    const rawFromFacilities = traceEndpointFacilitiesNear(segment.from[0], segment.from[1], index, radiusMeters);
    const rawToFacilities = traceEndpointFacilitiesNear(segment.to[0], segment.to[1], index, radiusMeters);
    const inactiveFacilityKeys = new Set();
    let temporalUnknown = false;

    rawFromFacilities.forEach(function (facility) {
      const temporalEvaluation = facilityTemporalEvaluationAtOrdinal(facility, fromContext.sortOrdinal);
      if (temporalEvaluation.status === "inactive") inactiveFacilityKeys.add(facilityKey(facility));
      if (temporalEvaluation.status === "unknown") temporalUnknown = true;
    });
    rawToFacilities.forEach(function (facility) {
      const temporalEvaluation = facilityTemporalEvaluationAtOrdinal(facility, toContext.sortOrdinal);
      if (temporalEvaluation.status === "inactive") inactiveFacilityKeys.add(facilityKey(facility));
      if (temporalEvaluation.status === "unknown") temporalUnknown = true;
    });
    if (
      (rawFromFacilities.length && !fromContext.sourceCoordinates) ||
      (rawToFacilities.length && !toContext.sourceCoordinates)
    ) {
      stats.generalizedEndpointSegments += 1;
    }

    const preferredFromEvidence = preferredEndpointEvidence(
      endpointFacilityEvidence(rawFromFacilities, fromContext)
    );
    const preferredToEvidence = preferredEndpointEvidence(
      endpointFacilityEvidence(rawToFacilities, toContext)
    );
    const fromEvidence = evidenceAllowedInMode(preferredFromEvidence, evidenceMode);
    const toEvidence = evidenceAllowedInMode(preferredToEvidence, evidenceMode);
    let passesEvidence = [];
    let preferredPassesEvidence = [];
    if (
      !fromEvidence.length &&
      !toEvidence.length &&
      classes.passes &&
      (
        evidenceMode === EVIDENCE_MODE_INCLUDE_GENERALIZED ||
        (!preferredFromEvidence.length && !preferredToEvidence.length)
      )
    ) {
      const rawPassFacilities = segmentFacilitiesPassedNear(segment, index, radiusMeters, stats);
      rawPassFacilities.forEach(function (facility) {
        const temporalEvaluation = facilityTemporalEvaluationForSegment(
          facility,
          fromContext.sortOrdinal,
          toContext.sortOrdinal
        );
        if (temporalEvaluation.status === "inactive") inactiveFacilityKeys.add(facilityKey(facility));
        if (temporalEvaluation.status === "unknown") temporalUnknown = true;
      });
      preferredPassesEvidence = passFacilityEvidence(rawPassFacilities, fromContext, toContext);
      passesEvidence = evidenceAllowedInMode(preferredPassesEvidence, evidenceMode);
    }

    if (temporalUnknown) stats.temporalUnknownSegments += 1;
    stats.knownInactiveFacilitiesExcluded += inactiveFacilityKeys.size;

    const classKey = fromEvidence.length && toEvidence.length
      ? "between"
      : fromEvidence.length
        ? "start"
        : toEvidence.length
          ? "end"
          : passesEvidence.length
            ? "passes"
            : null;
    if (!classKey) {
      const excludedEvidence = evidenceMode === EVIDENCE_MODE_SOURCE_COORDINATES
        ? preferredFromEvidence.concat(preferredToEvidence, preferredPassesEvidence)
        : [];
      record(
        stats,
        null,
        false,
        excludedEvidence.length ? "location_evidence_excluded" : "no_endpoint_match",
        null,
        evidenceReasons(excludedEvidence)
      );
      return null;
    }
    if (!classes[classKey]) {
      record(stats, classKey, false, "disabled_class");
      return null;
    }
    const evidence = classKey === "between"
      ? fromEvidence.concat(toEvidence)
      : classKey === "start"
        ? fromEvidence
        : classKey === "end"
          ? toEvidence
          : passesEvidence;
    const evidenceClass = evidence.some(function (entry) {
      return entry.evidenceClass === EVIDENCE_CLASS_POSSIBLE;
    }) ? EVIDENCE_CLASS_POSSIBLE : EVIDENCE_CLASS_SUPPORTED;
    record(stats, classKey, true, "matched", evidenceClass);
    const facilities = evidence.map(function (entry) { return entry.facility; });
    const supportedFacilities = evidence.filter(function (entry) {
      return entry.evidenceClass === EVIDENCE_CLASS_SUPPORTED;
    }).map(function (entry) { return entry.facility; });
    const possibleFacilities = evidence.filter(function (entry) {
      return entry.evidenceClass === EVIDENCE_CLASS_POSSIBLE;
    }).map(function (entry) { return entry.facility; });
    return {
      classKey,
      evidenceClass,
      facilityKeys: uniqueFacilities(
        evidenceClass === EVIDENCE_CLASS_SUPPORTED ? supportedFacilities : facilities
      ).map(facilityKey),
      supportedFacilityKeys: uniqueFacilities(supportedFacilities).map(facilityKey),
      possibleFacilityKeys: uniqueFacilities(possibleFacilities).map(facilityKey),
    };
  }

  function classifySegments(payload) {
    const segments = Array.isArray(payload.segments) ? payload.segments : [];
    const filter = payload.filter || {};
    const classes = Object.assign({ start: false, end: false, between: false, passes: false }, filter.classes || {});
    const radiusMeters = Math.max(0, Number(filter.radiusMeters) || 0);
    const evidenceMode = normalizedEvidenceMode(payload);
    const index = payload.facilityIndexKey && payload.facilityIndexKey === facilityIndexCacheKey && facilityIndexCache
      ? facilityIndexCache
      : buildFacilityIndex(payload.facilities || [], payload);
    const evidencePayload = Object.assign({ __facilityIndex: index }, payload);
    evidencePayload.__facilityIndex = index;
    const sourceCoordinateEventIds = sourceCoordinateEventIdSet(evidencePayload);
    const exactDateEventIds = exactDateEventIdSet(evidencePayload);
    const stats = defaultStats(payload.scope || "worker");
    const matches = [];
    if (!radiusMeters || !index.points.length) {
      segments.forEach(function () {
        record(stats, null, false, "missing_facility_context");
      });
      return { matches, stats, facilityCount: index.points.length, evidenceMode };
    }
    segments.forEach(function (segment, indexValue) {
      const match = classifySegment(
        segment,
        index,
        radiusMeters,
        classes,
        stats,
        evidenceMode,
        sourceCoordinateEventIds,
        exactDateEventIds
      );
      if (match) matches.push({
        index: indexValue,
        traceId: segment.traceId || "",
        classKey: match.classKey,
        evidenceClass: match.evidenceClass,
        facilityKeys: match.facilityKeys,
        supportedFacilityKeys: match.supportedFacilityKeys,
        possibleFacilityKeys: match.possibleFacilityKeys,
      });
    });
    return { matches, stats, facilityCount: index.points.length, evidenceMode };
  }

  async function configureTraceEventIndex(message) {
    const metadata = message.metadata || {};
    const loadMode = message.buffer ? "message_buffer" : "worker_fetch";
    const buffer = message.buffer || await fetchArrayBufferPreferGzipFromWorker(message.binaryUrl || "", message.gzipBinaryUrl || "");
    const view = packedTraceDataView(buffer);
    const rowCount = Number(metadata.row_count);
    const bytesPerRow = Number(metadata.bytes_per_row);
    if (!view || !Number.isSafeInteger(rowCount) || !Number.isSafeInteger(bytesPerRow)) {
      throw new Error("Trace facility worker received an invalid packed trace event index.");
    }
    if (view.byteLength !== rowCount * bytesPerRow) {
      throw new Error("Packed trace event index byte length does not match metadata.");
    }
    traceEventIndexCacheKey = String(message.traceIndexKey || "");
    traceEventIndexCache = {
      metadata,
      view,
      rowCount,
      bytesPerRow,
    };
    return {
      traceIndexKey: traceEventIndexCacheKey,
      rowCount,
      bytesPerRow,
      loadMode,
    };
  }

  function buildAndClassifyPackedTraceFacilitySegments(payload) {
    const cacheKey = String(payload.traceIndexKey || "");
    const cache = cacheKey && cacheKey === traceEventIndexCacheKey ? traceEventIndexCache : null;
    if (!cache) {
      throw new Error("Trace facility worker packed trace event index is not configured.");
    }
    const index = payload.facilityIndexKey && payload.facilityIndexKey === facilityIndexCacheKey && facilityIndexCache
      ? facilityIndexCache
      : buildFacilityIndex(payload.facilities || [], payload);
    const filter = payload.filter || {};
    const classes = Object.assign({ start: false, end: false, between: false, passes: false }, filter.classes || {});
    const radiusMeters = Math.max(0, Number(filter.radiusMeters) || 0);
    const evidenceMode = normalizedEvidenceMode(payload);
    const evidencePayload = Object.assign({ __facilityIndex: index }, payload);
    evidencePayload.__facilityIndex = index;
    const sourceCoordinateEventIds = sourceCoordinateEventIdSet(evidencePayload);
    const exactDateEventIds = exactDateEventIdSet(evidencePayload);
    const stats = defaultStats(payload.scope || "packed-static-worker");
    const filteredEventIds = new Set((Array.isArray(payload.filteredEventIds) ? payload.filteredEventIds : []).map(String));
    const activeBucketKeys = new Set(Array.isArray(payload.activeBucketKeys) ? payload.activeBucketKeys : []);
    const scanRange = packedTraceOrdinalScanRange(cache, payload);
    const bounds = payload.bounds || null;
    const segments = [];
    let previousEvent = null;
    let totalSegments = 0;
    let viewportSourceSegments = 0;

    if (!radiusMeters || !index.points.length || !filteredEventIds.size || !activeBucketKeys.size) {
      return {
        segments,
        stats,
        facilityCount: index.points.length,
        totalSegments: 0,
        viewportSourceSegments: 0,
        viewportWindowed: Boolean(bounds),
        scannedRows: Math.max(0, scanRange.endRow - scanRange.startRow),
        rowScanBoundedByTimeRange: scanRange.bounded,
        evidenceMode,
      };
    }

    for (let rowIndex = scanRange.startRow; rowIndex < scanRange.endRow; rowIndex += 1) {
      const currentEvent = decodePackedTraceEventIndexRow(cache.metadata, cache.view, rowIndex);
      if (!currentEvent || !filteredEventIds.has(String(currentEvent.event_id))) continue;
      if (previousEvent) {
        const gapDays = Math.abs((currentEvent.sort_ordinal || 0) - (previousEvent.sort_ordinal || 0));
        const bucketKey = bucketKeyForGapDays(gapDays);
        if (activeBucketKeys.has(bucketKey)) {
          const shortestSegment = shortestWrappedSegment(previousEvent, currentEvent);
          const segment = {
            traceId: canonicalTraceId(previousEvent.event_id, currentEvent.event_id),
            fromEventId: previousEvent.event_id,
            toEventId: currentEvent.event_id,
            fromSortOrdinal: previousEvent.sort_ordinal,
            toSortOrdinal: currentEvent.sort_ordinal,
            eventIds: [previousEvent.event_id, currentEvent.event_id],
            bucketKey,
            gapDays,
            from: shortestSegment.from,
            to: shortestSegment.to,
            source: "canonical_trace_event_index",
            sequenceIndex: totalSegments,
          };
          totalSegments += 1;
          if (!bounds || traceSegmentMayIntersectSerializedBounds(segment, bounds)) {
            viewportSourceSegments += 1;
            const match = classifySegment(
              segment,
              index,
              radiusMeters,
              classes,
              stats,
              evidenceMode,
              sourceCoordinateEventIds,
              exactDateEventIds
            );
            if (match) {
              segment.facilityTraceClass = match.classKey;
              segment.facilityTraceEvidenceClass = match.evidenceClass;
              segment.evidenceClass = match.evidenceClass;
              segment.facilityKeys = match.facilityKeys;
              segment.supportedFacilityKeys = match.supportedFacilityKeys;
              segment.possibleFacilityKeys = match.possibleFacilityKeys;
              segments.push(segment);
            }
          }
        }
      }
      previousEvent = currentEvent;
    }

    const maxSequenceIndex = Math.max(totalSegments - 1, 1);
    segments.forEach(function (segment) {
      segment.sequenceRatio = totalSegments <= 1 ? 1 : segment.sequenceIndex / maxSequenceIndex;
    });

    return {
      segments,
      stats,
      facilityCount: index.points.length,
      totalSegments,
      viewportSourceSegments,
      viewportWindowed: Boolean(bounds),
      scannedRows: Math.max(0, scanRange.endRow - scanRange.startRow),
      rowScanBoundedByTimeRange: scanRange.bounded,
      evidenceMode,
    };
  }

  self.onmessage = function (event) {
    const message = event.data || {};
    if (message.type === "configureTraceFacilityIndex") {
      try {
        facilityIndexCacheKey = String(message.facilityIndexKey || "");
        facilityIndexCache = buildFacilityIndex(message.facilities || [], message);
        self.postMessage({
          type: "traceFacilityIndexConfigured",
          requestId: message.requestId,
          generation: Number(message.generation) || 0,
          result: {
            facilityIndexKey: facilityIndexCacheKey,
            facilityCount: facilityIndexCache.points.length,
            sourceCoordinateEventCount: facilityIndexCache.sourceCoordinateEventIds.size,
            exactDateEventCount: facilityIndexCache.exactDateEventIds.size,
          },
        });
      } catch (error) {
        self.postMessage({
          type: "traceFacilityWorkerError",
          requestId: message.requestId,
          generation: Number(message.generation) || 0,
          error: error && error.message ? error.message : String(error),
        });
      }
      return;
    }
    if (message.type === "configureTraceEventIndex") {
      configureTraceEventIndex(message).then(function (result) {
        self.postMessage({
          type: "traceEventIndexConfigured",
          requestId: message.requestId,
          generation: Number(message.generation) || 0,
          result,
        });
      }).catch(function (error) {
        self.postMessage({
          type: "traceFacilityWorkerError",
          requestId: message.requestId,
          generation: Number(message.generation) || 0,
          error: error && error.message ? error.message : String(error),
        });
      });
      return;
    }
    if (message.type === "buildAndClassifyPackedTraceFacilitySegments") {
      try {
        const result = buildAndClassifyPackedTraceFacilitySegments(message);
        self.postMessage({
          type: "packedTraceFacilitySegmentsBuilt",
          requestId: message.requestId,
          generation: Number(message.generation) || 0,
          result,
        });
      } catch (error) {
        self.postMessage({
          type: "traceFacilityWorkerError",
          requestId: message.requestId,
          generation: Number(message.generation) || 0,
          error: error && error.message ? error.message : String(error),
        });
      }
      return;
    }
    if (message.type !== "classifyTraceFacilitySegments") return;
    try {
      const result = classifySegments(message);
      self.postMessage({
        type: "traceFacilitySegmentsClassified",
        requestId: message.requestId,
        generation: Number(message.generation) || 0,
        result,
      });
    } catch (error) {
      self.postMessage({
        type: "traceFacilityWorkerError",
        requestId: message.requestId,
        generation: Number(message.generation) || 0,
        error: error && error.message ? error.message : String(error),
      });
    }
  };
})();
