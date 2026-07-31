import assert from "node:assert/strict";

import {
  TRACE_ARTIFACT_FIELD_REQUIREMENTS,
  TRACE_ARTIFACT_KINDS,
  aggregateTraceEventRows,
  decodePackedTraceRow,
  longitudeWithShortestDelta,
  traceEventRowsToVisibleSegments,
  validatePackedTraceByteLength,
  validatePackedTraceMetadata,
} from "../webapp/static/packed-trace-utils.mjs";

function fieldsFor(kind) {
  let offset = 0;
  return TRACE_ARTIFACT_FIELD_REQUIREMENTS[kind].map(([name, type, size]) => {
    const field = { name, type, size, offset };
    if (type === "lookup:uint32") {
      field.lookup_table = name === "level_id" ? "levels" : name === "source_id" ? "sources" : "gap_buckets";
      if (name === "chunk_id") field.lookup_table = "chunk_ids";
      if (name === "source_pair_id") field.lookup_table = "source_pairs";
      if (name === "bucket_id") field.lookup_table = "gap_buckets";
      if (name === "gap_bucket_id") field.lookup_table = "gap_buckets";
    }
    offset += size;
    return field;
  });
}

function metadataFor(kind, rowCount, lookupTables = {}) {
  const fields = fieldsFor(kind);
  return {
    schema_version: 1,
    row_count: rowCount,
    bytes_per_row: fields.reduce((maxOffset, field) => Math.max(maxOffset, field.offset + field.size), 0),
    endianness: "little",
    fields,
    lookup_tables: Object.assign({
      sources: [null, "mufon", "nuforc"],
      chunk_ids: [null, "chunk_000"],
      gap_buckets: [null, "gap_le_1"],
      source_pairs: [null, "mufon->nuforc"],
      levels: [null, "10deg"],
    }, lookupTables),
  };
}

function writeField(view, metadata, rowIndex, fieldName, value) {
  const field = metadata.fields.find((candidate) => candidate.name === fieldName);
  const offset = (rowIndex * metadata.bytes_per_row) + field.offset;
  if (field.type === "uint64") view.setBigUint64(offset, BigInt(value), true);
  else if (field.type === "float64") view.setFloat64(offset, value, true);
  else if (field.type === "float32") view.setFloat32(offset, value, true);
  else if (field.type === "int32") view.setInt32(offset, value, true);
  else if (field.type === "uint32" || field.type === "lookup:uint32") view.setUint32(offset, value, true);
  else if (field.type === "uint16") view.setUint16(offset, value, true);
  else throw new Error("unsupported field type " + field.type);
}

const eventMetadata = metadataFor(TRACE_ARTIFACT_KINDS.eventIndex, 3);
assert.deepEqual(validatePackedTraceMetadata(eventMetadata, TRACE_ARTIFACT_KINDS.eventIndex), {
  ok: true,
  rowCount: 3,
  bytesPerRow: 48,
});

const eventBuffer = new ArrayBuffer(eventMetadata.bytes_per_row * eventMetadata.row_count);
const eventView = new DataView(eventBuffer);
[
  { event_id: 10, lat: 1, lon: 2, sort_ordinal: 730121, sort_date_key: 20010101, source_id: 1, chunk_id: 1, detail_index: 0, sequence_index: 0 },
  { event_id: 20, lat: 3, lon: 4, sort_ordinal: 730121, sort_date_key: 20010101, source_id: 2, chunk_id: 1, detail_index: 1, sequence_index: 1 },
  { event_id: 30, lat: 5, lon: 6, sort_ordinal: 730121, sort_date_key: 20010101, source_id: 1, chunk_id: 1, detail_index: 2, sequence_index: 2 },
].forEach((row, rowIndex) => {
  for (const [fieldName, value] of Object.entries(row)) {
    writeField(eventView, eventMetadata, rowIndex, fieldName, value);
  }
});

assert.deepEqual(validatePackedTraceByteLength(eventMetadata, eventBuffer.byteLength), { ok: true });
const eventRows = [0, 1, 2].map((rowIndex) => decodePackedTraceRow(eventMetadata, eventBuffer, rowIndex));
assert.deepEqual(eventRows.map((row) => row.event_id), [10, 20, 30]);
assert.equal(eventRows[0].source_id, "mufon");

const filteredRows = [eventRows[0], eventRows[2]];
assert.deepEqual(traceEventRowsToVisibleSegments(filteredRows), [
  {
    from_event_id: 10,
    to_event_id: 30,
    from_lat: 1,
    from_lon: 2,
    to_lat: 5,
    to_lon: 6,
    from_sort_date_key: 20010101,
    to_sort_date_key: 20010101,
    gap_days: 0,
    gap_bucket: "gap_le_1",
    from_sequence_index: 0,
    to_sequence_index: 2,
  },
]);

assert.equal(longitudeWithShortestDelta(170, -170), 190);
const datedRows = [
  { event_id: 1, lat: 0, lon: 170, sort_date_key: 20010101, sequence_index: 0 },
  { event_id: 2, lat: 0, lon: -170, sort_date_key: 20010103, sequence_index: 1 },
];
const wrappedSegments = traceEventRowsToVisibleSegments(datedRows);
assert.equal(wrappedSegments[0].to_lon, 190);
assert.equal(wrappedSegments[0].gap_days, 2);
assert.equal(wrappedSegments[0].gap_bucket, "gap_le_2");

const filteredAggregates = aggregateTraceEventRows(filteredRows, [{ key: "10deg", cellSizeDegrees: 10 }]);
assert.deepEqual(filteredAggregates, [
  {
    level_id: "10deg",
    from_lon_cell: 18,
    from_lat_cell: 9,
    to_lon_cell: 18,
    to_lat_cell: 9,
    gap_bucket_id: "gap_le_1",
    segment_count: 1,
    from_lat_mean: 1,
    from_lon_mean: 2,
    to_lat_mean: 5,
    to_lon_mean: 6,
    min_sort_date_key: 20010101,
    max_sort_date_key: 20010101,
    min_sequence_index: 0,
    max_sequence_index: 2,
  },
]);

const aggregateMetadata = metadataFor(TRACE_ARTIFACT_KINDS.aggregateBins, 1);
assert.deepEqual(validatePackedTraceMetadata(aggregateMetadata, TRACE_ARTIFACT_KINDS.aggregateBins), {
  ok: true,
  rowCount: 1,
  bytesPerRow: 52,
});
const aggregateBuffer = new ArrayBuffer(aggregateMetadata.bytes_per_row);
const aggregateView = new DataView(aggregateBuffer);
writeField(aggregateView, aggregateMetadata, 0, "level_id", 1);
writeField(aggregateView, aggregateMetadata, 0, "from_lon_cell", 18);
writeField(aggregateView, aggregateMetadata, 0, "from_lat_cell", 9);
writeField(aggregateView, aggregateMetadata, 0, "to_lon_cell", 19);
writeField(aggregateView, aggregateMetadata, 0, "to_lat_cell", 9);
writeField(aggregateView, aggregateMetadata, 0, "gap_bucket_id", 1);
writeField(aggregateView, aggregateMetadata, 0, "segment_count", 7);
writeField(aggregateView, aggregateMetadata, 0, "from_lat_mean", 1.25);
writeField(aggregateView, aggregateMetadata, 0, "from_lon_mean", 2.5);
writeField(aggregateView, aggregateMetadata, 0, "to_lat_mean", 3.75);
writeField(aggregateView, aggregateMetadata, 0, "to_lon_mean", 4.5);
writeField(aggregateView, aggregateMetadata, 0, "min_sort_date_key", 20010101);
writeField(aggregateView, aggregateMetadata, 0, "max_sort_date_key", 20010131);
writeField(aggregateView, aggregateMetadata, 0, "min_sequence_index", 0);
writeField(aggregateView, aggregateMetadata, 0, "max_sequence_index", 99);

const aggregateRow = decodePackedTraceRow(aggregateMetadata, aggregateBuffer, 0);
assert.equal(aggregateRow.level_id, "10deg");
assert.equal(aggregateRow.gap_bucket_id, "gap_le_1");
assert.equal(aggregateRow.segment_count, 7);
assert.equal(aggregateRow.from_lon_cell, 18);

const unsupported = { ...eventMetadata, schema_version: 999 };
assert.match(
  validatePackedTraceMetadata(unsupported, TRACE_ARTIFACT_KINDS.eventIndex).reason,
  /Unsupported packed trace schema version/
);

console.log("packed trace frontend utility assertions passed");
