export const PACKED_TRACE_SUPPORTED_SCHEMA_VERSION = 1;

export const TRACE_ARTIFACT_KINDS = Object.freeze({
  eventIndex: "trace_event_index",
  segments: "trace_segments",
  aggregateBins: "trace_aggregate_bins",
});

export const DEFAULT_TRACE_AGGREGATE_LEVELS = Object.freeze([
  { key: "10deg", cellSizeDegrees: 10 },
  { key: "5deg", cellSizeDegrees: 5 },
  { key: "2_5deg", cellSizeDegrees: 2.5 },
]);

export const TRACE_GAP_BUCKETS = Object.freeze([
  { key: "gap_le_1", maxDays: 1 },
  { key: "gap_le_2", maxDays: 2 },
  { key: "gap_le_7", maxDays: 7 },
  { key: "gap_le_30", maxDays: 30 },
  { key: "gap_gt_30", maxDays: null },
]);

export const TRACE_ARTIFACT_FIELD_REQUIREMENTS = Object.freeze({
  [TRACE_ARTIFACT_KINDS.eventIndex]: [
    ["event_id", "uint64", 8],
    ["lat", "float64", 8],
    ["lon", "float64", 8],
    ["sort_ordinal", "int32", 4],
    ["sort_date_key", "int32", 4],
    ["source_id", "lookup:uint32", 4],
    ["chunk_id", "lookup:uint32", 4],
    ["detail_index", "int32", 4],
    ["sequence_index", "uint32", 4],
  ],
  [TRACE_ARTIFACT_KINDS.segments]: [
    ["from_event_id", "uint64", 8],
    ["to_event_id", "uint64", 8],
    ["from_lat", "float64", 8],
    ["from_lon", "float64", 8],
    ["to_lat", "float64", 8],
    ["to_lon", "float64", 8],
    ["from_sort_date_key", "int32", 4],
    ["to_sort_date_key", "int32", 4],
    ["gap_days", "int32", 4],
    ["bucket_id", "lookup:uint32", 4],
    ["source_pair_id", "lookup:uint32", 4],
    ["sequence_index", "uint32", 4],
  ],
  [TRACE_ARTIFACT_KINDS.aggregateBins]: [
    ["level_id", "lookup:uint32", 4],
    ["from_lon_cell", "uint16", 2],
    ["from_lat_cell", "uint16", 2],
    ["to_lon_cell", "uint16", 2],
    ["to_lat_cell", "uint16", 2],
    ["gap_bucket_id", "lookup:uint32", 4],
    ["segment_count", "uint32", 4],
    ["from_lat_mean", "float32", 4],
    ["from_lon_mean", "float32", 4],
    ["to_lat_mean", "float32", 4],
    ["to_lon_mean", "float32", 4],
    ["min_sort_date_key", "int32", 4],
    ["max_sort_date_key", "int32", 4],
    ["min_sequence_index", "uint32", 4],
    ["max_sequence_index", "uint32", 4],
  ],
});

export function validatePackedTraceMetadata(metadata, artifactKind, options = {}) {
  const supportedSchemaVersion = Number(
    options.supportedSchemaVersion || PACKED_TRACE_SUPPORTED_SCHEMA_VERSION
  );
  const fieldRequirements = TRACE_ARTIFACT_FIELD_REQUIREMENTS[artifactKind];
  if (!fieldRequirements) {
    return { ok: false, reason: "Unsupported packed trace artifact kind: " + artifactKind + "." };
  }
  if (!metadata || typeof metadata !== "object") {
    return { ok: false, reason: "Packed trace metadata is not an object." };
  }
  if (Number(metadata.schema_version) !== supportedSchemaVersion) {
    return {
      ok: false,
      reason: "Unsupported packed trace schema version: " + metadata.schema_version + ".",
    };
  }
  if (metadata.endianness && metadata.endianness !== "little") {
    return {
      ok: false,
      reason: "Unsupported packed trace endianness: " + metadata.endianness + ".",
    };
  }

  const rowCount = Number(metadata.row_count);
  const bytesPerRow = Number(metadata.bytes_per_row);
  if (!Number.isSafeInteger(rowCount) || rowCount < 0) {
    return { ok: false, reason: "Packed trace row_count is invalid." };
  }
  if (!Number.isSafeInteger(bytesPerRow) || bytesPerRow <= 0) {
    return { ok: false, reason: "Packed trace bytes_per_row is invalid." };
  }
  if (!Array.isArray(metadata.fields) || !metadata.fields.length) {
    return { ok: false, reason: "Packed trace fields metadata is missing." };
  }

  let rowSpan = 0;
  for (const requirement of fieldRequirements) {
    const field = packedTraceMetadataFieldByName(metadata, requirement[0]);
    if (!field) {
      return { ok: false, reason: "Packed trace field is missing: " + requirement[0] + "." };
    }
    if (field.type !== requirement[1]) {
      return {
        ok: false,
        reason: "Packed trace field " + requirement[0] + " has unsupported type " + field.type + ".",
      };
    }
    if (Number(field.size) !== requirement[2]) {
      return {
        ok: false,
        reason: "Packed trace field " + requirement[0] + " has unsupported size " + field.size + ".",
      };
    }
    if (!Number.isSafeInteger(Number(field.offset)) || Number(field.offset) < 0) {
      return {
        ok: false,
        reason: "Packed trace field " + requirement[0] + " has an invalid offset.",
      };
    }
    rowSpan = Math.max(rowSpan, Number(field.offset) + Number(field.size));
  }
  if (rowSpan !== bytesPerRow) {
    return {
      ok: false,
      reason: "Packed trace row field span " + rowSpan + " does not match bytes_per_row " + bytesPerRow + ".",
    };
  }

  const lookupTables = metadata.lookup_tables;
  if (!lookupTables || typeof lookupTables !== "object") {
    return { ok: false, reason: "Packed trace lookup_tables metadata is missing." };
  }
  for (const field of metadata.fields) {
    if (field && field.lookup_table && !Array.isArray(lookupTables[field.lookup_table])) {
      return {
        ok: false,
        reason: "Packed trace lookup table is missing: " + field.lookup_table + ".",
      };
    }
  }
  return { ok: true, rowCount, bytesPerRow };
}

export function validatePackedTraceByteLength(metadata, byteLength) {
  const rowCount = Number(metadata && metadata.row_count);
  const bytesPerRow = Number(metadata && metadata.bytes_per_row);
  const expectedLength = rowCount * bytesPerRow;
  if (!Number.isSafeInteger(expectedLength) || expectedLength !== byteLength) {
    return {
      ok: false,
      reason: "Packed trace binary length " + byteLength + " does not match row_count * bytes_per_row (" + expectedLength + ").",
    };
  }
  return { ok: true };
}

export function decodePackedTraceRow(metadata, bufferOrView, rowIndex, options = {}) {
  const rowCount = Number(metadata && metadata.row_count);
  if (!Number.isSafeInteger(rowCount) || !Number.isSafeInteger(rowIndex) || rowIndex < 0 || rowIndex >= rowCount) {
    return null;
  }
  const fields = Array.isArray(metadata && metadata.fields) ? metadata.fields : [];
  const row = {};
  for (const field of fields) {
    if (field && field.name) {
      row[field.name] = decodePackedTraceField(metadata, bufferOrView, field.name, rowIndex, options);
    }
  }
  return row;
}

export function decodePackedTraceField(metadata, bufferOrView, fieldName, rowIndex, options = {}) {
  const rowCount = Number(metadata && metadata.row_count);
  const bytesPerRow = Number(metadata && metadata.bytes_per_row);
  if (!Number.isSafeInteger(rowCount) || !Number.isSafeInteger(bytesPerRow)) return null;
  if (!Number.isSafeInteger(rowIndex) || rowIndex < 0 || rowIndex >= rowCount) return null;

  const field = packedTraceMetadataFieldByName(metadata, fieldName);
  if (!field) return null;

  const view = packedTraceDataView(bufferOrView);
  const offset = (rowIndex * bytesPerRow) + Number(field.offset);
  const littleEndian = true;
  let value;
  if (field.type === "uint64") {
    value = normalizePackedTraceBigInt(view.getBigUint64(offset, littleEndian));
  } else if (field.type === "int64") {
    value = normalizePackedTraceBigInt(view.getBigInt64(offset, littleEndian));
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

  if (field.lookup_table && !options.rawLookupIds) {
    const lookupTable = (metadata.lookup_tables && metadata.lookup_tables[field.lookup_table]) || [];
    return Object.prototype.hasOwnProperty.call(lookupTable, value) ? lookupTable[value] : null;
  }
  return value;
}

export function traceEventRowsToVisibleSegments(rows) {
  const visibleRows = Array.isArray(rows) ? rows.filter(Boolean) : [];
  const segments = [];
  for (let index = 1; index < visibleRows.length; index += 1) {
    const previous = visibleRows[index - 1];
    const current = visibleRows[index];
    if (!Number.isFinite(previous.lat) || !Number.isFinite(previous.lon)) continue;
    if (!Number.isFinite(current.lat) || !Number.isFinite(current.lon)) continue;
    segments.push({
      from_event_id: previous.event_id,
      to_event_id: current.event_id,
      from_lat: previous.lat,
      from_lon: previous.lon,
      to_lat: current.lat,
      to_lon: longitudeWithShortestDelta(previous.lon, current.lon),
      from_sort_date_key: previous.sort_date_key,
      to_sort_date_key: current.sort_date_key,
      gap_days: gapDaysBetweenSortDateKeys(previous.sort_date_key, current.sort_date_key),
      gap_bucket: traceGapBucketForDays(gapDaysBetweenSortDateKeys(previous.sort_date_key, current.sort_date_key)),
      from_sequence_index: previous.sequence_index,
      to_sequence_index: current.sequence_index,
    });
  }
  return segments;
}

export function aggregateTraceEventRows(rows, levels = DEFAULT_TRACE_AGGREGATE_LEVELS) {
  return aggregateTraceSegments(traceEventRowsToVisibleSegments(rows), levels);
}

export function aggregateTraceSegments(segments, levels = DEFAULT_TRACE_AGGREGATE_LEVELS) {
  const activeLevels = Array.isArray(levels) && levels.length ? levels : DEFAULT_TRACE_AGGREGATE_LEVELS;
  const aggregateMap = new Map();
  for (const segment of Array.isArray(segments) ? segments : []) {
    if (!Number.isFinite(segment.from_lat) || !Number.isFinite(segment.from_lon)) continue;
    if (!Number.isFinite(segment.to_lat) || !Number.isFinite(segment.to_lon)) continue;
    for (const level of activeLevels) {
      const levelKey = String(level.key || "");
      const cellSize = Number(level.cellSizeDegrees || level.cell_size_degrees);
      if (!levelKey || !Number.isFinite(cellSize) || cellSize <= 0) continue;
      const fromCell = traceCellForPoint(segment.from_lat, segment.from_lon, cellSize);
      const toCell = traceCellForPoint(segment.to_lat, segment.to_lon, cellSize);
      const gapBucket = segment.gap_bucket || traceGapBucketForDays(segment.gap_days);
      const key = [
        levelKey,
        fromCell.lonCell,
        fromCell.latCell,
        toCell.lonCell,
        toCell.latCell,
        gapBucket,
      ].join("|");
      const aggregate = aggregateMap.get(key) || {
        level_id: levelKey,
        from_lon_cell: fromCell.lonCell,
        from_lat_cell: fromCell.latCell,
        to_lon_cell: toCell.lonCell,
        to_lat_cell: toCell.latCell,
        gap_bucket_id: gapBucket,
        segment_count: 0,
        from_lat_sum: 0,
        from_lon_sum: 0,
        to_lat_sum: 0,
        to_lon_sum: 0,
        min_sort_date_key: null,
        max_sort_date_key: null,
        min_sequence_index: null,
        max_sequence_index: null,
      };
      aggregate.segment_count += 1;
      aggregate.from_lat_sum += segment.from_lat;
      aggregate.from_lon_sum += segment.from_lon;
      aggregate.to_lat_sum += segment.to_lat;
      aggregate.to_lon_sum += segment.to_lon;
      const fromDateKey = validSortDateKey(segment.from_sort_date_key) ? Number(segment.from_sort_date_key) : null;
      const toDateKey = validSortDateKey(segment.to_sort_date_key) ? Number(segment.to_sort_date_key) : null;
      for (const keyValue of [fromDateKey, toDateKey]) {
        if (keyValue == null) continue;
        aggregate.min_sort_date_key = aggregate.min_sort_date_key == null ? keyValue : Math.min(aggregate.min_sort_date_key, keyValue);
        aggregate.max_sort_date_key = aggregate.max_sort_date_key == null ? keyValue : Math.max(aggregate.max_sort_date_key, keyValue);
      }
      for (const sequenceValue of [segment.from_sequence_index, segment.to_sequence_index]) {
        if (!Number.isSafeInteger(Number(sequenceValue))) continue;
        const numericSequenceValue = Number(sequenceValue);
        aggregate.min_sequence_index = aggregate.min_sequence_index == null
          ? numericSequenceValue
          : Math.min(aggregate.min_sequence_index, numericSequenceValue);
        aggregate.max_sequence_index = aggregate.max_sequence_index == null
          ? numericSequenceValue
          : Math.max(aggregate.max_sequence_index, numericSequenceValue);
      }
      aggregateMap.set(key, aggregate);
    }
  }
  return Array.from(aggregateMap.values()).map((aggregate) => {
    const count = aggregate.segment_count || 1;
    return {
      level_id: aggregate.level_id,
      from_lon_cell: aggregate.from_lon_cell,
      from_lat_cell: aggregate.from_lat_cell,
      to_lon_cell: aggregate.to_lon_cell,
      to_lat_cell: aggregate.to_lat_cell,
      gap_bucket_id: aggregate.gap_bucket_id,
      segment_count: aggregate.segment_count,
      from_lat_mean: aggregate.from_lat_sum / count,
      from_lon_mean: aggregate.from_lon_sum / count,
      to_lat_mean: aggregate.to_lat_sum / count,
      to_lon_mean: aggregate.to_lon_sum / count,
      min_sort_date_key: aggregate.min_sort_date_key,
      max_sort_date_key: aggregate.max_sort_date_key,
      min_sequence_index: aggregate.min_sequence_index,
      max_sequence_index: aggregate.max_sequence_index,
    };
  });
}

export function traceCellForPoint(lat, lon, cellSizeDegrees) {
  const cellSize = Number(cellSizeDegrees);
  const latitude = Math.max(-90, Math.min(89.999999, Number(lat)));
  const longitude = Math.max(-180, Math.min(179.999999, normalizeLongitude(Number(lon))));
  return {
    lonCell: Math.floor((longitude + 180) / cellSize),
    latCell: Math.floor((latitude + 90) / cellSize),
  };
}

export function traceGapBucketForDays(gapDays) {
  const numericGap = Number(gapDays);
  if (!Number.isFinite(numericGap) || numericGap < 0) return "unknown_gap";
  for (const bucket of TRACE_GAP_BUCKETS) {
    if (bucket.maxDays == null || numericGap <= bucket.maxDays) return bucket.key;
  }
  return TRACE_GAP_BUCKETS[TRACE_GAP_BUCKETS.length - 1].key;
}

export function packedTraceMetadataFieldByName(metadata, fieldName) {
  const fields = Array.isArray(metadata && metadata.fields) ? metadata.fields : [];
  for (const field of fields) {
    if (field && field.name === fieldName) return field;
  }
  return null;
}

export function packedTraceDataView(bufferOrView) {
  if (bufferOrView instanceof DataView) return bufferOrView;
  if (bufferOrView instanceof ArrayBuffer) return new DataView(bufferOrView);
  if (ArrayBuffer.isView(bufferOrView)) {
    return new DataView(bufferOrView.buffer, bufferOrView.byteOffset, bufferOrView.byteLength);
  }
  throw new TypeError("Packed trace binary data must be an ArrayBuffer or DataView.");
}

export function normalizePackedTraceBigInt(value) {
  if (value <= BigInt(Number.MAX_SAFE_INTEGER) && value >= BigInt(Number.MIN_SAFE_INTEGER)) {
    return Number(value);
  }
  return value.toString();
}

export function gapDaysBetweenSortDateKeys(fromSortDateKey, toSortDateKey) {
  const fromDay = utcDayFromSortDateKey(fromSortDateKey);
  const toDay = utcDayFromSortDateKey(toSortDateKey);
  if (fromDay == null || toDay == null) return null;
  return Math.abs(toDay - fromDay);
}

export function longitudeWithShortestDelta(fromLon, toLon) {
  const from = normalizeLongitude(Number(fromLon));
  let to = normalizeLongitude(Number(toLon));
  let delta = to - from;
  if (delta > 180) delta -= 360;
  if (delta < -180) delta += 360;
  return from + delta;
}

export function normalizeLongitude(lon) {
  if (!Number.isFinite(lon)) return lon;
  let normalized = lon;
  while (normalized > 180) normalized -= 360;
  while (normalized < -180) normalized += 360;
  return normalized;
}

function utcDayFromSortDateKey(sortDateKey) {
  if (!validSortDateKey(sortDateKey)) return null;
  const value = Number(sortDateKey);
  const year = Math.floor(value / 10000);
  const month = Math.floor((value % 10000) / 100);
  const day = value % 100;
  const timestamp = Date.UTC(year, month - 1, day);
  if (!Number.isFinite(timestamp)) return null;
  return Math.floor(timestamp / 86400000);
}

function validSortDateKey(sortDateKey) {
  const value = Number(sortDateKey);
  if (!Number.isSafeInteger(value) || value <= 0) return false;
  const month = Math.floor((value % 10000) / 100);
  const day = value % 100;
  return month >= 1 && month <= 12 && day >= 1 && day <= 31;
}
