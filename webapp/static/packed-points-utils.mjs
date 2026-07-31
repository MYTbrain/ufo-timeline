import { LOW_PRECISION_VALUES, normalizeDateBoundary } from "./app-utils.mjs";

export const PACKED_POINTS_SUPPORTED_SCHEMA_VERSION = 2;

export const PACKED_POINT_FIELD_REQUIREMENTS = [
  ["event_id", "uint64", 8],
  ["lat", "float64", 8],
  ["lon", "float64", 8],
  ["sort_date_key", "int32", 4],
  ["sort_time_ms", "int64", 8],
  ["source_id", "lookup:uint32", 4],
  ["type_id", "lookup:uint32", 4],
  ["shape_id", "lookup:uint32", 4],
  ["visual_type_group_id", "lookup:uint32", 4],
  ["date_precision_id", "lookup:uint32", 4],
  ["location_precision_id", "lookup:uint32", 4],
  ["coordinate_source_id", "lookup:uint32", 4],
  ["chunk_id", "lookup:uint32", 4],
  ["detail_index", "int32", 4],
];

export function metadataFieldByName(metadata, fieldName) {
  const fields = Array.isArray(metadata && metadata.fields) ? metadata.fields : [];
  for (const field of fields) {
    if (field && field.name === fieldName) {
      return field;
    }
  }
  return null;
}

export function validatePackedPointsMetadata(metadata, options = {}) {
  const supportedSchemaVersion = Number(
    options.supportedSchemaVersion || PACKED_POINTS_SUPPORTED_SCHEMA_VERSION
  );

  if (!metadata || typeof metadata !== "object") {
    return { ok: false, reason: "Packed points metadata is not an object." };
  }
  if (Number(metadata.schema_version) !== supportedSchemaVersion) {
    return {
      ok: false,
      reason: "Unsupported packed points schema version: " + metadata.schema_version + ".",
    };
  }
  if (metadata.endianness && metadata.endianness !== "little") {
    return {
      ok: false,
      reason: "Unsupported packed points endianness: " + metadata.endianness + ".",
    };
  }

  const rowCount = Number(metadata.row_count);
  const bytesPerRow = Number(metadata.bytes_per_row);
  if (!Number.isSafeInteger(rowCount) || rowCount < 0) {
    return { ok: false, reason: "Packed points row_count is invalid." };
  }
  if (!Number.isSafeInteger(bytesPerRow) || bytesPerRow <= 0) {
    return { ok: false, reason: "Packed points bytes_per_row is invalid." };
  }
  if (!Array.isArray(metadata.fields) || !metadata.fields.length) {
    return { ok: false, reason: "Packed points fields metadata is missing." };
  }

  let rowSpan = 0;
  for (const requirement of PACKED_POINT_FIELD_REQUIREMENTS) {
    const field = metadataFieldByName(metadata, requirement[0]);
    if (!field) {
      return { ok: false, reason: "Packed points field is missing: " + requirement[0] + "." };
    }
    if (field.type !== requirement[1]) {
      return {
        ok: false,
        reason: "Packed points field " + requirement[0] + " has unsupported type " + field.type + ".",
      };
    }
    if (Number(field.size) !== requirement[2]) {
      return {
        ok: false,
        reason: "Packed points field " + requirement[0] + " has unsupported size " + field.size + ".",
      };
    }
    if (!Number.isSafeInteger(Number(field.offset)) || Number(field.offset) < 0) {
      return {
        ok: false,
        reason: "Packed points field " + requirement[0] + " has an invalid offset.",
      };
    }
    rowSpan = Math.max(rowSpan, Number(field.offset) + Number(field.size));
  }
  if (rowSpan !== bytesPerRow) {
    return {
      ok: false,
      reason: "Packed points row field span " + rowSpan + " does not match bytes_per_row " + bytesPerRow + ".",
    };
  }

  const lookupTables = metadata.lookup_tables;
  if (!lookupTables || typeof lookupTables !== "object") {
    return { ok: false, reason: "Packed points lookup_tables metadata is missing." };
  }
  for (const field of metadata.fields) {
    if (!field || !field.lookup_table) {
      continue;
    }
    if (!Array.isArray(lookupTables[field.lookup_table])) {
      return {
        ok: false,
        reason: "Packed points lookup table is missing: " + field.lookup_table + ".",
      };
    }
  }

  return {
    ok: true,
    rowCount,
    bytesPerRow,
  };
}

export function validatePackedPointsByteLength(metadata, byteLength) {
  const rowCount = Number(metadata && metadata.row_count);
  const bytesPerRow = Number(metadata && metadata.bytes_per_row);
  const expectedLength = rowCount * bytesPerRow;
  if (!Number.isSafeInteger(expectedLength) || expectedLength !== byteLength) {
    return {
      ok: false,
      reason:
        "Packed points binary length " +
        formatPackedPointNumber(byteLength) +
        " does not match row_count * bytes_per_row (" +
        formatPackedPointNumber(expectedLength) +
        ").",
    };
  }
  return { ok: true };
}

export function decodePackedPointField(metadata, bufferOrView, fieldName, rowIndex, options = {}) {
  const rowCount = Number(metadata && metadata.row_count);
  const bytesPerRow = Number(metadata && metadata.bytes_per_row);
  if (!Number.isSafeInteger(rowCount) || !Number.isSafeInteger(bytesPerRow)) {
    return null;
  }
  if (!Number.isSafeInteger(rowIndex) || rowIndex < 0 || rowIndex >= rowCount) {
    return null;
  }

  const field = metadataFieldByName(metadata, fieldName);
  if (!field) {
    return null;
  }

  const view = packedPointsDataView(bufferOrView);
  const offset = (rowIndex * bytesPerRow) + Number(field.offset);
  const littleEndian = true;
  let value;
  if (field.type === "uint64") {
    value = normalizeBigIntForPackedPointRuntime(view.getBigUint64(offset, littleEndian));
  } else if (field.type === "int64") {
    value = normalizeBigIntForPackedPointRuntime(view.getBigInt64(offset, littleEndian));
  } else if (field.type === "float64") {
    value = view.getFloat64(offset, littleEndian);
  } else if (field.type === "int32") {
    value = view.getInt32(offset, littleEndian);
  } else if (field.type === "lookup:uint32") {
    value = view.getUint32(offset, littleEndian);
  } else {
    return null;
  }

  if (field.lookup_table && !options.rawLookupIds) {
    const lookupTable = (metadata.lookup_tables && metadata.lookup_tables[field.lookup_table]) || [];
    return Object.prototype.hasOwnProperty.call(lookupTable, value) ? lookupTable[value] : null;
  }
  return value;
}

export function decodePackedPointRow(metadata, bufferOrView, rowIndex, options = {}) {
  const fields = Array.isArray(metadata && metadata.fields) ? metadata.fields : [];
  const rowCount = Number(metadata && metadata.row_count);
  if (!Number.isSafeInteger(rowCount) || !Number.isSafeInteger(rowIndex) || rowIndex < 0 || rowIndex >= rowCount) {
    return null;
  }

  const row = {};
  for (const field of fields) {
    if (!field || !field.name) {
      continue;
    }
    row[field.name] = decodePackedPointField(metadata, bufferOrView, field.name, rowIndex, options);
  }
  return row;
}

export function projectDecodedPackedPointRow(row, metadata = null) {
  if (!row || typeof row !== "object") {
    return null;
  }

  const lat = normalizePackedPointMissingValue(row.lat, null);
  const lon = normalizePackedPointMissingValue(row.lon, null);
  const sortDateKey = normalizePackedPointMissingValue(
    row.sort_date_key,
    packedPointNullSentinel(metadata, "sort_date_key", 0)
  );
  return {
    event_id: normalizePackedPointMissingValue(row.event_id, null),
    lat,
    lon,
    sort_date_key: sortDateKey,
    sort_date_iso: packedPointSortDateIso(sortDateKey),
    sort_time_ms: normalizePackedPointMissingValue(
      row.sort_time_ms,
      packedPointNullSentinel(metadata, "sort_time_ms", Number.MIN_SAFE_INTEGER)
    ),
    source: resolvePackedPointLookupValue(metadata, "source_id", row.source_id),
    type: resolvePackedPointLookupValue(metadata, "type_id", row.type_id),
    shape_normalized: resolvePackedPointLookupValue(metadata, "shape_id", row.shape_id),
    visual_type_group: resolvePackedPointLookupValue(metadata, "visual_type_group_id", row.visual_type_group_id),
    date_precision: resolvePackedPointLookupValue(metadata, "date_precision_id", row.date_precision_id),
    location_precision: resolvePackedPointLookupValue(metadata, "location_precision_id", row.location_precision_id),
    coordinate_source: resolvePackedPointLookupValue(metadata, "coordinate_source_id", row.coordinate_source_id),
    chunk_id: resolvePackedPointLookupValue(metadata, "chunk_id", row.chunk_id),
    detail_index: normalizePackedPointMissingValue(row.detail_index, null),
    has_coordinates: Number.isFinite(lat) && Number.isFinite(lon),
  };
}

export function projectPackedPointRow(metadata, bufferOrView, rowIndex) {
  const row = decodePackedPointRow(metadata, bufferOrView, rowIndex, { rawLookupIds: true });
  return projectDecodedPackedPointRow(row, metadata);
}

export function createPackedPointEventIdIndex(metadata, bufferOrView) {
  const rowCount = Number(metadata && metadata.row_count);
  if (!Number.isSafeInteger(rowCount) || rowCount < 0) {
    return createEmptyPackedPointEventIdIndex();
  }

  const capacity = packedPointEventIdIndexCapacity(rowCount);
  const keys = new Float64Array(capacity);
  const rowIndexes = new Uint32Array(capacity);
  const fallback = new Map();
  const mask = capacity - 1;
  let collisions = 0;
  let maxProbe = 0;

  for (let rowIndex = 0; rowIndex < rowCount; rowIndex += 1) {
    const eventId = decodePackedPointField(metadata, bufferOrView, "event_id", rowIndex, { rawLookupIds: true });
    const numericEventId = packedPointIndexNumericEventId(eventId);
    if (numericEventId == null) {
      fallback.set(String(eventId), rowIndex);
      continue;
    }
    let slot = packedPointEventIdHashSlot(numericEventId, capacity);
    let probe = 0;
    while (rowIndexes[slot] && keys[slot] !== numericEventId) {
      slot = (slot + 1) & mask;
      probe += 1;
    }
    if (probe) collisions += 1;
    if (probe > maxProbe) maxProbe = probe;
    keys[slot] = numericEventId;
    rowIndexes[slot] = rowIndex + 1;
  }

  return {
    storageMode: "typed_open_addressing",
    size: rowCount,
    capacity,
    byteLength: keys.byteLength + rowIndexes.byteLength,
    collisions,
    maxProbe,
    fallbackSize: fallback.size,
    get(eventId) {
      const numericEventId = packedPointIndexNumericEventId(eventId);
      if (numericEventId == null) {
        return fallback.get(String(eventId));
      }
      let slot = packedPointEventIdHashSlot(numericEventId, capacity);
      let probe = 0;
      while (rowIndexes[slot]) {
        if (keys[slot] === numericEventId) {
          return rowIndexes[slot] - 1;
        }
        slot = (slot + 1) & mask;
        probe += 1;
        if (probe >= capacity) break;
      }
      return undefined;
    },
    has(eventId) {
      return this.get(eventId) != null;
    },
  };
}

function createEmptyPackedPointEventIdIndex() {
  return {
    storageMode: "typed_open_addressing",
    size: 0,
    capacity: 0,
    byteLength: 0,
    collisions: 0,
    maxProbe: 0,
    fallbackSize: 0,
    get() {
      return undefined;
    },
    has() {
      return false;
    },
  };
}

function packedPointEventIdIndexCapacity(rowCount) {
  const target = Math.max(4, Math.ceil(Number(rowCount || 0) / 0.68));
  let capacity = 1;
  while (capacity < target) {
    capacity *= 2;
  }
  return capacity;
}

function packedPointIndexNumericEventId(eventId) {
  if (typeof eventId === "number") {
    return Number.isSafeInteger(eventId) ? eventId : null;
  }
  const text = String(eventId == null ? "" : eventId).trim();
  if (!/^-?\d+$/.test(text)) return null;
  const numeric = Number(text);
  return Number.isSafeInteger(numeric) ? numeric : null;
}

function packedPointEventIdHashSlot(eventId, capacity) {
  if (!capacity) return 0;
  const remainder = eventId % capacity;
  return remainder < 0 ? remainder + capacity : remainder;
}

export function packedPointFilterRequiresFallback(filters = {}) {
  const unsupported = [];
  for (const key of ["keyword", "searchText", "query"]) {
    if (String(filters[key] || "").trim()) {
      unsupported.push(key);
    }
  }
  if (!unsupported.length) {
    return { requiresFallback: false, unsupported };
  }
  return {
    requiresFallback: true,
    unsupported,
    reason: "Packed point rows do not include full searchable text; use the catalog/detail search path.",
  };
}

export function filterPackedPointRows(metadata, bufferOrView, filters = {}) {
  const unsupported = packedPointFilterRequiresFallback(filters);
  if (unsupported.requiresFallback) {
    return {
      ok: false,
      requiresFallback: true,
      reason: unsupported.reason,
      unsupported: unsupported.unsupported,
      rowIndexes: [],
      eventIds: [],
      count: 0,
    };
  }

  const context = createPackedPointFilterContext(filters);
  const prepared = preparePackedPointScan(metadata, bufferOrView);
  if (!prepared.ok) {
    return {
      ok: false,
      requiresFallback: false,
      reason: prepared.reason,
      unsupported: [],
      rowIndexes: [],
      eventIds: [],
      count: 0,
    };
  }

  const rowIndexes = [];
  const eventIds = [];
  for (let rowIndex = 0; rowIndex < prepared.rowCount; rowIndex += 1) {
    if (!packedPointRowMatchesFilters(metadata, prepared.view, rowIndex, context)) {
      continue;
    }
    rowIndexes.push(rowIndex);
    eventIds.push(decodePackedPointField(metadata, prepared.view, "event_id", rowIndex, { rawLookupIds: true }));
  }

  return {
    ok: true,
    requiresFallback: false,
    unsupported: [],
    rowIndexes,
    eventIds,
    count: rowIndexes.length,
  };
}

export function computePackedPointFacetCounts(metadata, bufferOrView, filters = {}) {
  const unsupported = packedPointFilterRequiresFallback(filters);
  if (unsupported.requiresFallback) {
    return {
      ok: false,
      requiresFallback: true,
      reason: unsupported.reason,
      unsupported: unsupported.unsupported,
      counts: createEmptyPackedPointFacetCounts(),
      scannedRows: 0,
    };
  }

  const prepared = preparePackedPointScan(metadata, bufferOrView);
  if (!prepared.ok) {
    return {
      ok: false,
      requiresFallback: false,
      reason: prepared.reason,
      unsupported: [],
      counts: createEmptyPackedPointFacetCounts(),
      scannedRows: 0,
    };
  }

  const context = createPackedPointFilterContext(filters);
  const counts = createEmptyPackedPointFacetCounts();
  for (let rowIndex = 0; rowIndex < prepared.rowCount; rowIndex += 1) {
    accumulatePackedPointFacetCountsForRow(metadata, prepared.view, rowIndex, context, counts);
  }

  return {
    ok: true,
    requiresFallback: false,
    unsupported: [],
    counts,
    scannedRows: prepared.rowCount,
  };
}

export function packedPointsDataView(bufferOrView) {
  if (bufferOrView instanceof DataView) {
    return bufferOrView;
  }
  if (bufferOrView instanceof ArrayBuffer) {
    return new DataView(bufferOrView);
  }
  if (ArrayBuffer.isView(bufferOrView)) {
    return new DataView(bufferOrView.buffer, bufferOrView.byteOffset, bufferOrView.byteLength);
  }
  throw new TypeError("Packed points binary data must be an ArrayBuffer or DataView.");
}

export function normalizeBigIntForPackedPointRuntime(value) {
  const max = BigInt(Number.MAX_SAFE_INTEGER);
  const min = BigInt(Number.MIN_SAFE_INTEGER);
  if (value <= max && value >= min) {
    return Number(value);
  }
  return value.toString();
}

function formatPackedPointNumber(value) {
  if (Number.isFinite(Number(value))) {
    return Number(value).toLocaleString("en-US");
  }
  return String(value);
}

function resolvePackedPointLookupValue(metadata, fieldName, value) {
  const normalizedValue = normalizePackedPointMissingValue(
    value,
    packedPointNullSentinel(metadata, "lookup_id", 0)
  );
  if (normalizedValue === null || normalizedValue === undefined) {
    return null;
  }
  if (typeof normalizedValue !== "number" || !Number.isInteger(normalizedValue)) {
    return normalizedValue;
  }

  const field = metadataFieldByName(metadata, fieldName);
  const tableName = field && field.lookup_table;
  const lookupTable = tableName && metadata && metadata.lookup_tables && metadata.lookup_tables[tableName];
  if (!Array.isArray(lookupTable)) {
    return normalizedValue;
  }
  return Object.prototype.hasOwnProperty.call(lookupTable, normalizedValue) ? lookupTable[normalizedValue] : null;
}

function preparePackedPointScan(metadata, bufferOrView) {
  const metadataValidation = validatePackedPointsMetadata(metadata);
  if (!metadataValidation.ok) {
    return metadataValidation;
  }
  let view;
  try {
    view = packedPointsDataView(bufferOrView);
  } catch (error) {
    return { ok: false, reason: error && error.message ? error.message : String(error) };
  }
  const byteLengthValidation = validatePackedPointsByteLength(metadata, view.byteLength);
  if (!byteLengthValidation.ok) {
    return byteLengthValidation;
  }
  return {
    ok: true,
    view,
    rowCount: metadataValidation.rowCount,
    bytesPerRow: metadataValidation.bytesPerRow,
  };
}

function createPackedPointFilterContext(filters = {}) {
  return {
    sourceMode: String(filters.sourceMode || "some"),
    typeMode: String(filters.typeMode || "some"),
    precisionMode: String(filters.precisionMode || "some"),
    selectedSources: normalizePackedPointFilterSet(filters.selectedSources || filters.sources),
    selectedTypes: normalizePackedPointFilterSet(filters.selectedTypes || filters.types),
    selectedPrecisions: normalizePackedPointFilterSet(filters.selectedPrecisions || filters.precisions),
    hideLowPrecision: Boolean(filters.hideLowPrecision),
    hideNonExactDates: Boolean(filters.hideNonExactDates),
    startDateKey: packedPointBoundarySortDateKey(filters.startDate || filters.startDateIso, "start"),
    endDateKey: packedPointBoundarySortDateKey(filters.endDate || filters.endDateIso, "end"),
  };
}

function normalizePackedPointFilterSet(values) {
  if (!values) {
    return new Set();
  }
  if (values instanceof Set) {
    return new Set([...values].map((value) => String(value)));
  }
  if (Array.isArray(values)) {
    return new Set(values.map((value) => String(value)));
  }
  return new Set([String(values)]);
}

function packedPointBoundarySortDateKey(value, side) {
  const normalized = normalizeDateBoundary(value, side);
  if (!normalized) {
    return null;
  }
  const dateKey = Number(normalized.replaceAll("-", ""));
  return Number.isInteger(dateKey) ? dateKey : null;
}

function packedPointRowMatchesFilters(metadata, view, rowIndex, context) {
  if (context.sourceMode === "none" || context.typeMode === "none" || context.precisionMode === "none") {
    return false;
  }

  const sortDateKey = normalizePackedPointMissingValue(
    decodePackedPointField(metadata, view, "sort_date_key", rowIndex, { rawLookupIds: true }),
    packedPointNullSentinel(metadata, "sort_date_key", 0)
  );
  if (context.startDateKey !== null && sortDateKey !== null && sortDateKey < context.startDateKey) {
    return false;
  }
  if (context.endDateKey !== null && sortDateKey !== null && sortDateKey > context.endDateKey) {
    return false;
  }

  const sourceValue = decodePackedPointField(metadata, view, "source_id", rowIndex) || "";
  if (context.selectedSources.size && !context.selectedSources.has(sourceValue)) {
    return false;
  }

  const typeValue = decodePackedPointField(metadata, view, "type_id", rowIndex) || "";
  if (context.selectedTypes.size && !context.selectedTypes.has(typeValue)) {
    return false;
  }

  const precisionValue = decodePackedPointField(metadata, view, "location_precision_id", rowIndex) || "";
  if (context.selectedPrecisions.size && !context.selectedPrecisions.has(precisionValue)) {
    return false;
  }
  if (context.hideLowPrecision && LOW_PRECISION_VALUES.has(precisionValue)) {
    return false;
  }

  const datePrecisionValue = decodePackedPointField(metadata, view, "date_precision_id", rowIndex) || "";
  if (context.hideNonExactDates && datePrecisionValue !== "exact_day") {
    return false;
  }

  return true;
}

function createEmptyPackedPointFacetCounts() {
  return {
    source: new Map(),
    type: new Map(),
    precision: new Map(),
  };
}

function accumulatePackedPointFacetCountsForRow(metadata, view, rowIndex, context, counts) {
  const sortDateKey = normalizePackedPointMissingValue(
    decodePackedPointField(metadata, view, "sort_date_key", rowIndex, { rawLookupIds: true }),
    packedPointNullSentinel(metadata, "sort_date_key", 0)
  );
  if (context.startDateKey !== null && sortDateKey !== null && sortDateKey < context.startDateKey) {
    return;
  }
  if (context.endDateKey !== null && sortDateKey !== null && sortDateKey > context.endDateKey) {
    return;
  }

  const sourceValue = decodePackedPointField(metadata, view, "source_id", rowIndex) || "";
  const typeValue = decodePackedPointField(metadata, view, "type_id", rowIndex) || "";
  const precisionValue = decodePackedPointField(metadata, view, "location_precision_id", rowIndex) || "";
  const datePrecisionValue = decodePackedPointField(metadata, view, "date_precision_id", rowIndex) || "";

  if (context.hideLowPrecision && LOW_PRECISION_VALUES.has(precisionValue)) {
    return;
  }
  if (context.hideNonExactDates && datePrecisionValue !== "exact_day") {
    return;
  }

  const sourceSubsetActive = context.selectedSources.size > 0;
  const typeSubsetActive = context.selectedTypes.size > 0;
  const precisionSubsetActive = context.selectedPrecisions.size > 0;

  const sourceFacetEligible =
    context.typeMode !== "none" &&
    context.precisionMode !== "none" &&
    (!typeSubsetActive || context.selectedTypes.has(typeValue)) &&
    (!precisionSubsetActive || context.selectedPrecisions.has(precisionValue));
  if (sourceFacetEligible && sourceValue) {
    counts.source.set(sourceValue, (counts.source.get(sourceValue) || 0) + 1);
  }

  const typeFacetEligible =
    context.sourceMode !== "none" &&
    context.precisionMode !== "none" &&
    (!sourceSubsetActive || context.selectedSources.has(sourceValue)) &&
    (!precisionSubsetActive || context.selectedPrecisions.has(precisionValue));
  if (typeFacetEligible && typeValue) {
    counts.type.set(typeValue, (counts.type.get(typeValue) || 0) + 1);
  }

  const precisionFacetEligible =
    context.sourceMode !== "none" &&
    context.typeMode !== "none" &&
    (!sourceSubsetActive || context.selectedSources.has(sourceValue)) &&
    (!typeSubsetActive || context.selectedTypes.has(typeValue));
  if (precisionFacetEligible && precisionValue) {
    counts.precision.set(precisionValue, (counts.precision.get(precisionValue) || 0) + 1);
  }
}

function normalizePackedPointMissingValue(value, missingSentinel) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return null;
  }
  if (missingSentinel !== null && missingSentinel !== undefined && String(value) === String(missingSentinel)) {
    return null;
  }
  if (String(value) === "-9223372036854775808" && Number(missingSentinel) < Number.MIN_SAFE_INTEGER) {
    return null;
  }
  return value;
}

function packedPointSortDateIso(sortDateKey) {
  if (!Number.isInteger(sortDateKey) || sortDateKey <= 0) {
    return null;
  }

  const padded = String(sortDateKey).padStart(8, "0");
  return padded.slice(0, 4) + "-" + padded.slice(4, 6) + "-" + padded.slice(6, 8);
}

function packedPointNullSentinel(metadata, name, fallback) {
  if (metadata && metadata.nulls && Object.prototype.hasOwnProperty.call(metadata.nulls, name)) {
    return metadata.nulls[name];
  }
  return fallback;
}
