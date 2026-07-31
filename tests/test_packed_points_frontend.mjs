import assert from "node:assert/strict";

import {
  computePackedPointFacetCounts,
  createPackedPointEventIdIndex,
  decodePackedPointField,
  decodePackedPointRow,
  filterPackedPointRows,
  metadataFieldByName,
  normalizeBigIntForPackedPointRuntime,
  packedPointsDataView,
  packedPointFilterRequiresFallback,
  projectDecodedPackedPointRow,
  projectPackedPointRow,
  validatePackedPointsByteLength,
  validatePackedPointsMetadata,
} from "../webapp/static/packed-points-utils.mjs";

const BYTES_PER_ROW = 72;
const MISSING_INT64 = -(2n ** 63n);
const UNSAFE_EVENT_ID = BigInt(Number.MAX_SAFE_INTEGER) + 2n;

const fieldMetadata = [
  { name: "event_id", offset: 0, type: "uint64", size: 8 },
  { name: "lat", offset: 8, type: "float64", size: 8 },
  { name: "lon", offset: 16, type: "float64", size: 8 },
  { name: "sort_date_key", offset: 24, type: "int32", size: 4 },
  { name: "sort_time_ms", offset: 28, type: "int64", size: 8 },
  { name: "source_id", offset: 36, type: "lookup:uint32", size: 4, lookup_table: "sources" },
  { name: "type_id", offset: 40, type: "lookup:uint32", size: 4, lookup_table: "types" },
  { name: "shape_id", offset: 44, type: "lookup:uint32", size: 4, lookup_table: "shapes" },
  { name: "visual_type_group_id", offset: 48, type: "lookup:uint32", size: 4, lookup_table: "visual_type_groups" },
  { name: "date_precision_id", offset: 52, type: "lookup:uint32", size: 4, lookup_table: "date_precisions" },
  { name: "location_precision_id", offset: 56, type: "lookup:uint32", size: 4, lookup_table: "location_precisions" },
  { name: "coordinate_source_id", offset: 60, type: "lookup:uint32", size: 4, lookup_table: "coordinate_sources" },
  { name: "chunk_id", offset: 64, type: "lookup:uint32", size: 4, lookup_table: "chunk_ids" },
  { name: "detail_index", offset: 68, type: "int32", size: 4 },
];

function createMetadata(overrides = {}) {
  return {
    schema_version: 2,
    row_count: 2,
    bytes_per_row: BYTES_PER_ROW,
    endianness: "little",
    struct_format: "<QddiqIIIIIIIIi",
    files: {
      points: "points.bin",
      metadata: "points_meta.json",
    },
    fields: fieldMetadata.map((field) => ({ ...field })),
    lookup_tables: {
      sources: [null, "Hatch", "NUFORC"],
      types: [null, "sighting", "radar"],
      shapes: [null, "Triangle", "Sphere"],
      visual_type_groups: [null, "Craft", "Unknown"],
      date_precisions: [null, "exact_day", "year", "month"],
      location_precisions: [null, "exact_coords", "city", "country"],
      coordinate_sources: [null, "raw_latlong", "geocoded"],
      chunk_ids: [null, "chunk_000", "chunk_001"],
    },
    nulls: {
      lookup_id: 0,
      sort_date_key: 0,
      sort_time_ms: Number(MISSING_INT64),
    },
    ...overrides,
  };
}

function cloneMetadata(metadata = createMetadata()) {
  return JSON.parse(JSON.stringify(metadata));
}

function writeRow(view, rowIndex, row) {
  const offset = rowIndex * BYTES_PER_ROW;
  view.setBigUint64(offset, BigInt(row.event_id), true);
  view.setFloat64(offset + 8, row.lat, true);
  view.setFloat64(offset + 16, row.lon, true);
  view.setInt32(offset + 24, row.sort_date_key, true);
  view.setBigInt64(offset + 28, BigInt(row.sort_time_ms), true);
  view.setUint32(offset + 36, row.source_id, true);
  view.setUint32(offset + 40, row.type_id, true);
  view.setUint32(offset + 44, row.shape_id, true);
  view.setUint32(offset + 48, row.visual_type_group_id, true);
  view.setUint32(offset + 52, row.date_precision_id, true);
  view.setUint32(offset + 56, row.location_precision_id, true);
  view.setUint32(offset + 60, row.coordinate_source_id, true);
  view.setUint32(offset + 64, row.chunk_id, true);
  view.setInt32(offset + 68, row.detail_index, true);
}

function createPackedBuffer() {
  const buffer = new ArrayBuffer(BYTES_PER_ROW * 2);
  const view = new DataView(buffer);

  writeRow(view, 0, {
    event_id: 42n,
    lat: 33.9425,
    lon: -118.4081,
    sort_date_key: 19470215,
    sort_time_ms: 1234567890n,
    source_id: 2,
    type_id: 1,
    shape_id: 1,
    visual_type_group_id: 1,
    date_precision_id: 1,
    location_precision_id: 1,
    coordinate_source_id: 1,
    chunk_id: 1,
    detail_index: 7,
  });
  writeRow(view, 1, {
    event_id: UNSAFE_EVENT_ID,
    lat: 51.533336,
    lon: -0.45,
    sort_date_key: 13221104,
    sort_time_ms: MISSING_INT64,
    source_id: 99,
    type_id: 0,
    shape_id: 2,
    visual_type_group_id: 2,
    date_precision_id: 2,
    location_precision_id: 2,
    coordinate_source_id: 2,
    chunk_id: 0,
    detail_index: -1,
  });

  return buffer;
}

function createFilterFixture() {
  const fixtureMetadata = createMetadata({ row_count: 4 });
  const fixtureBuffer = new ArrayBuffer(BYTES_PER_ROW * 4);
  const fixtureView = new DataView(fixtureBuffer);

  writeRow(fixtureView, 0, {
    event_id: 101n,
    lat: 33.9425,
    lon: -118.4081,
    sort_date_key: 19470215,
    sort_time_ms: 1n,
    source_id: 2,
    type_id: 1,
    shape_id: 1,
    visual_type_group_id: 1,
    date_precision_id: 1,
    location_precision_id: 1,
    coordinate_source_id: 1,
    chunk_id: 1,
    detail_index: 0,
  });
  writeRow(fixtureView, 1, {
    event_id: 102n,
    lat: 34,
    lon: -118,
    sort_date_key: 19520101,
    sort_time_ms: 2n,
    source_id: 1,
    type_id: 2,
    shape_id: 2,
    visual_type_group_id: 2,
    date_precision_id: 1,
    location_precision_id: 3,
    coordinate_source_id: 2,
    chunk_id: 1,
    detail_index: 1,
  });
  writeRow(fixtureView, 2, {
    event_id: 103n,
    lat: 35,
    lon: -117,
    sort_date_key: 19520615,
    sort_time_ms: 3n,
    source_id: 1,
    type_id: 1,
    shape_id: 1,
    visual_type_group_id: 1,
    date_precision_id: 3,
    location_precision_id: 1,
    coordinate_source_id: 1,
    chunk_id: 2,
    detail_index: 2,
  });
  writeRow(fixtureView, 3, {
    event_id: 104n,
    lat: 36,
    lon: -116,
    sort_date_key: 0,
    sort_time_ms: MISSING_INT64,
    source_id: 0,
    type_id: 0,
    shape_id: 0,
    visual_type_group_id: 0,
    date_precision_id: 2,
    location_precision_id: 2,
    coordinate_source_id: 2,
    chunk_id: 0,
    detail_index: -1,
  });

  return { metadata: fixtureMetadata, buffer: fixtureBuffer };
}

function mapEntries(map) {
  return [...map.entries()].sort((left, right) => left[0].localeCompare(right[0]));
}

const metadata = createMetadata();
const buffer = createPackedBuffer();

const metadataValidation = validatePackedPointsMetadata(metadata);
assert.deepEqual(metadataValidation, { ok: true, rowCount: 2, bytesPerRow: BYTES_PER_ROW });
assert.equal(metadataFieldByName(metadata, "sort_time_ms").offset, 28);
assert.equal(metadataFieldByName(metadata, "missing"), null);

assert.deepEqual(validatePackedPointsByteLength(metadata, buffer.byteLength), { ok: true });
assert.match(
  validatePackedPointsByteLength(metadata, buffer.byteLength - 1).reason,
  /Packed points binary length 143 does not match row_count \* bytes_per_row \(144\)\./
);

const firstRow = decodePackedPointRow(metadata, buffer, 0);
assert.deepEqual(firstRow, {
  event_id: 42,
  lat: 33.9425,
  lon: -118.4081,
  sort_date_key: 19470215,
  sort_time_ms: 1234567890,
  source_id: "NUFORC",
  type_id: "sighting",
  shape_id: "Triangle",
  visual_type_group_id: "Craft",
  date_precision_id: "exact_day",
  location_precision_id: "exact_coords",
  coordinate_source_id: "raw_latlong",
  chunk_id: "chunk_000",
  detail_index: 7,
});

const rawLookupRow = decodePackedPointRow(metadata, buffer, 0, { rawLookupIds: true });
assert.equal(rawLookupRow.source_id, 2);
assert.equal(rawLookupRow.type_id, 1);
assert.equal(rawLookupRow.visual_type_group_id, 1);
assert.equal(rawLookupRow.coordinate_source_id, 1);
assert.equal(rawLookupRow.chunk_id, 1);

assert.deepEqual(projectDecodedPackedPointRow(rawLookupRow, metadata), {
  event_id: 42,
  lat: 33.9425,
  lon: -118.4081,
  sort_date_key: 19470215,
  sort_date_iso: "1947-02-15",
  sort_time_ms: 1234567890,
  source: "NUFORC",
  type: "sighting",
  shape_normalized: "Triangle",
  visual_type_group: "Craft",
  date_precision: "exact_day",
  location_precision: "exact_coords",
  coordinate_source: "raw_latlong",
  chunk_id: "chunk_000",
  detail_index: 7,
  has_coordinates: true,
});

assert.deepEqual(projectDecodedPackedPointRow(firstRow, metadata), {
  event_id: 42,
  lat: 33.9425,
  lon: -118.4081,
  sort_date_key: 19470215,
  sort_date_iso: "1947-02-15",
  sort_time_ms: 1234567890,
  source: "NUFORC",
  type: "sighting",
  shape_normalized: "Triangle",
  visual_type_group: "Craft",
  date_precision: "exact_day",
  location_precision: "exact_coords",
  coordinate_source: "raw_latlong",
  chunk_id: "chunk_000",
  detail_index: 7,
  has_coordinates: true,
});

const paddedBuffer = new ArrayBuffer(4 + buffer.byteLength);
new Uint8Array(paddedBuffer).set(new Uint8Array(buffer), 4);
const paddedView = new DataView(paddedBuffer, 4, buffer.byteLength);
const secondRow = decodePackedPointRow(metadata, paddedView, 1);
assert.equal(secondRow.event_id, UNSAFE_EVENT_ID.toString());
assert.equal(secondRow.lat, 51.533336);
assert.equal(secondRow.lon, -0.45);
assert.equal(secondRow.sort_time_ms, MISSING_INT64.toString());
assert.equal(secondRow.source_id, null);
assert.equal(secondRow.type_id, null);
assert.equal(secondRow.shape_id, "Sphere");
assert.equal(secondRow.visual_type_group_id, "Unknown");
assert.equal(secondRow.date_precision_id, "year");
assert.equal(secondRow.location_precision_id, "city");
assert.equal(secondRow.coordinate_source_id, "geocoded");
assert.equal(secondRow.chunk_id, null);
assert.equal(secondRow.detail_index, -1);

assert.deepEqual(projectPackedPointRow(metadata, paddedView, 1), {
  event_id: UNSAFE_EVENT_ID.toString(),
  lat: 51.533336,
  lon: -0.45,
  sort_date_key: 13221104,
  sort_date_iso: "1322-11-04",
  sort_time_ms: null,
  source: null,
  type: null,
  shape_normalized: "Sphere",
  visual_type_group: "Unknown",
  date_precision: "year",
  location_precision: "city",
  coordinate_source: "geocoded",
  chunk_id: null,
  detail_index: -1,
  has_coordinates: true,
});
const projectedUnsafeRow = projectPackedPointRow(metadata, paddedView, 1);
assert.equal(projectedUnsafeRow.event_id, UNSAFE_EVENT_ID.toString());
assert.equal(typeof projectedUnsafeRow.event_id, "string");
assert.equal(projectedUnsafeRow.source, null);

assert.deepEqual(projectDecodedPackedPointRow({
  event_id: null,
  lat: Number.NaN,
  lon: undefined,
  sort_date_key: 0,
  sort_time_ms: MISSING_INT64.toString(),
  source_id: 0,
  type_id: undefined,
  shape_id: 99,
  visual_type_group_id: null,
  date_precision_id: 0,
  location_precision_id: "city",
  coordinate_source_id: "geocoded",
  chunk_id: 0,
}, metadata), {
  event_id: null,
  lat: null,
  lon: null,
  sort_date_key: null,
  sort_date_iso: null,
  sort_time_ms: null,
  source: null,
  type: null,
  shape_normalized: null,
  visual_type_group: null,
  date_precision: null,
  location_precision: "city",
  coordinate_source: "geocoded",
  chunk_id: null,
  detail_index: null,
  has_coordinates: false,
});
const projectedMissingDateRow = projectDecodedPackedPointRow({
  event_id: "unsafe-id-9007199254740993",
  lat: 10,
  lon: 20,
  sort_date_key: 0,
  source_id: 99,
}, metadata);
assert.equal(projectedMissingDateRow.sort_date_key, null);
assert.equal(projectedMissingDateRow.sort_date_iso, null);
assert.equal(projectedMissingDateRow.source, null);
assert.equal(projectedMissingDateRow.event_id, "unsafe-id-9007199254740993");

assert.equal(projectDecodedPackedPointRow(null, metadata), null);
assert.equal(projectPackedPointRow(metadata, buffer, 2), null);

assert.equal(decodePackedPointField(metadata, buffer, "lon", 0), -118.4081);
assert.equal(decodePackedPointField(metadata, buffer, "not_a_field", 0), null);
assert.equal(decodePackedPointRow(metadata, buffer, -1), null);
assert.equal(decodePackedPointRow(metadata, buffer, 2), null);

const eventIdIndex = createPackedPointEventIdIndex(metadata, buffer);
assert.equal(eventIdIndex.get("42"), 0);
assert.equal(eventIdIndex.get(UNSAFE_EVENT_ID.toString()), 1);
assert.equal(eventIdIndex.storageMode, "typed_open_addressing");
assert.equal(eventIdIndex.size, 2);
assert.equal(eventIdIndex.capacity, 4);
assert.equal(eventIdIndex.byteLength, 48);
assert.equal(eventIdIndex.fallbackSize, 1);
assert.equal(eventIdIndex.has(42), true);
assert.equal(eventIdIndex.has("missing"), false);

const typedBytes = new Uint8Array(buffer);
assert.equal(packedPointsDataView(typedBytes).byteLength, buffer.byteLength);
assert.equal(normalizeBigIntForPackedPointRuntime(42n), 42);
assert.equal(normalizeBigIntForPackedPointRuntime(UNSAFE_EVENT_ID), UNSAFE_EVENT_ID.toString());

const unsupportedSchema = cloneMetadata();
unsupportedSchema.schema_version = 1;
assert.match(validatePackedPointsMetadata(unsupportedSchema).reason, /Unsupported packed points schema version: 1\./);

const unsupportedEndianness = cloneMetadata();
unsupportedEndianness.endianness = "big";
assert.match(validatePackedPointsMetadata(unsupportedEndianness).reason, /Unsupported packed points endianness: big\./);

const missingField = cloneMetadata();
missingField.fields = missingField.fields.filter((field) => field.name !== "chunk_id");
assert.match(validatePackedPointsMetadata(missingField).reason, /Packed points field is missing: chunk_id\./);

const badRowSpan = cloneMetadata();
badRowSpan.bytes_per_row = BYTES_PER_ROW + 1;
assert.match(
  validatePackedPointsMetadata(badRowSpan).reason,
  /Packed points row field span 72 does not match bytes_per_row 73\./
);

const missingLookupTable = cloneMetadata();
delete missingLookupTable.lookup_tables.sources;
assert.match(validatePackedPointsMetadata(missingLookupTable).reason, /Packed points lookup table is missing: sources\./);

const filterFixture = createFilterFixture();
assert.deepEqual(
  filterPackedPointRows(filterFixture.metadata, filterFixture.buffer, { sources: ["NUFORC"] }),
  {
    ok: true,
    requiresFallback: false,
    unsupported: [],
    rowIndexes: [0],
    eventIds: [101],
    count: 1,
  }
);

assert.deepEqual(
  filterPackedPointRows(filterFixture.metadata, filterFixture.buffer, {
    startDate: "1952",
    endDate: "1952",
    hideNonExactDates: true,
  }).eventIds,
  [102]
);

assert.deepEqual(
  filterPackedPointRows(filterFixture.metadata, filterFixture.buffer, {
    selectedTypes: new Set(["sighting"]),
    hideLowPrecision: true,
  }).eventIds,
  [101, 103]
);

assert.equal(
  filterPackedPointRows(filterFixture.metadata, filterFixture.buffer, { sourceMode: "none" }).count,
  0
);

const keywordFallback = filterPackedPointRows(filterFixture.metadata, filterFixture.buffer, { keyword: "roswell" });
assert.equal(keywordFallback.ok, false);
assert.equal(keywordFallback.requiresFallback, true);
assert.deepEqual(keywordFallback.unsupported, ["keyword"]);
assert.equal(packedPointFilterRequiresFallback({ query: "foo" }).requiresFallback, true);

const facetResult = computePackedPointFacetCounts(filterFixture.metadata, filterFixture.buffer);
assert.equal(facetResult.ok, true);
assert.equal(facetResult.scannedRows, 4);
assert.deepEqual(mapEntries(facetResult.counts.source), [["Hatch", 2], ["NUFORC", 1]]);
assert.deepEqual(mapEntries(facetResult.counts.type), [["radar", 1], ["sighting", 2]]);
assert.deepEqual(mapEntries(facetResult.counts.precision), [["city", 1], ["country", 1], ["exact_coords", 2]]);

const exactOnlyFacetResult = computePackedPointFacetCounts(filterFixture.metadata, filterFixture.buffer, {
  hideNonExactDates: true,
  hideLowPrecision: true,
});
assert.deepEqual(mapEntries(exactOnlyFacetResult.counts.source), [["NUFORC", 1]]);
assert.deepEqual(mapEntries(exactOnlyFacetResult.counts.type), [["sighting", 1]]);
assert.deepEqual(mapEntries(exactOnlyFacetResult.counts.precision), [["exact_coords", 1]]);

const sourceScopedFacetResult = computePackedPointFacetCounts(filterFixture.metadata, filterFixture.buffer, {
  sources: ["Hatch"],
});
assert.deepEqual(mapEntries(sourceScopedFacetResult.counts.source), [["Hatch", 2], ["NUFORC", 1]]);
assert.deepEqual(mapEntries(sourceScopedFacetResult.counts.type), [["radar", 1], ["sighting", 1]]);
assert.deepEqual(mapEntries(sourceScopedFacetResult.counts.precision), [["country", 1], ["exact_coords", 1]]);

assert.equal(
  computePackedPointFacetCounts(filterFixture.metadata, filterFixture.buffer, { searchText: "saucer" }).requiresFallback,
  true
);

console.log("packed point frontend utility assertions passed");
