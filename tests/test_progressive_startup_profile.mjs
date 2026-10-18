import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import zlib from "node:zlib";
import vm from "node:vm";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const profile = path.join(root, "data/startup_profiles/france_1954_flap");
const manifest = JSON.parse(fs.readFileSync(path.join(profile, "progressive_manifest.json")));
const bytes = fs.readFileSync(path.join(profile, manifest.artifact.file));
const raw = zlib.gunzipSync(bytes);
const hash = bytes => crypto.createHash("sha256").update(bytes).digest("hex");
assert.equal(bytes.length, manifest.artifact.gzipBytes);
assert.equal(hash(bytes), manifest.artifact.gzipSha256);
assert.equal(raw.length, manifest.artifact.decodedBytes);
assert.equal(hash(raw), manifest.artifact.decodedSha256);
assert.ok(bytes.length < 1024 * 1024, "The scoped view must remain below its explicit one MiB ceiling");
const payload = JSON.parse(raw);
assert.equal(payload.schemaId, "ufo-progressive-startup-view-v1");
assert.equal(payload.scope, "mapped_reports_in_initial_time_window");
assert.equal(manifest.policies.fullCatalogReady, false, "A ready initial map does not assert a ready global catalog");
assert.equal(manifest.policies.unmappedReportsIncluded, false);
assert.equal(manifest.policies.canonicalSourcesMutated, false);
assert.equal(payload.sourcePins.catalogCount, 702893);
assert.equal(payload.sourcePins.effectiveSummaryShards.length, 71);
assert.equal(payload.events.length, 2587);
assert.equal(payload.traceEventOrder.length, 2583);
assert.equal(new Set(payload.events.map(row => row.event_id)).size, payload.events.length);
const events = new Map(payload.events.map(row => [row.event_id, row]));
for (const row of payload.events) {
  assert.equal(row.has_coordinates, true);
  assert.ok(Number.isFinite(row.lat) && Number.isFinite(row.lon));
  const start = row.date_recovery_contract ? row.date_iso : row.sort_date_iso;
  const end = row.date_recovery_contract ? row.end_date_iso : row.sort_date_iso;
  assert.ok(start <= payload.dateRange.end && end >= payload.dateRange.start);
  assert.equal(row.encounterEvidenceReady, true, "Scoped map annotations use the actual complete pinned encounter evidence");
  assert.equal(row.encounterEvidenceProvenanceReady, true);
  assert.equal(row.encounterIdentityMismatch, false);
  assert.equal(Object.hasOwn(row, "description"), false, "Private full narratives are not introduced into the initial view");
}
for (const pin of payload.sourcePins.files) {
  assert.ok(!path.isAbsolute(pin.path), "Public provenance does not expose workstation paths");
  const bytes = fs.readFileSync(path.join(root, pin.path));
  assert.equal(bytes.length, pin.bytes);
  assert.equal(hash(bytes), pin.sha256, "Current scoped source pin drift: " + pin.path);
}

const chronology = require("../trace_chronology.js");
const directions = require("../trace_direction_summary.js");
const scopedIndex = chronology.createEvidenceIndex(payload.traceChronology);
const globalRaw = zlib.gunzipSync(fs.readFileSync(path.join(root, "data/trace_chronology/evidence.json.gz")));
assert.equal(hash(globalRaw), payload.sourcePins.globalTimingDecodedSha256);
const globalIndex = chronology.createEvidenceIndex(JSON.parse(globalRaw));
assert.equal(scopedIndex.rowCount, 1717);
assert.equal(scopedIndex.snapshot().excludedDateCount, 62);
for (const id of events.keys()) {
  assert.deepEqual(scopedIndex.interval(id), globalIndex.interval(id), "Scoped timing retains exact source bounds, code facts, and timezone identity");
  assert.deepEqual(scopedIndex.exclusion(id), globalIndex.exclusion(id), "Scoped occurrence-date exclusions cannot be dropped");
}
assert.equal(scopedIndex.interval(52735086719694), null, "An out-of-scope global account cannot acquire a scoped timing claim");

const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const begin = app.indexOf("  const CRAFT_ONLY_TYPE_LABELS = ");
const end = app.indexOf(";", begin) + 1;
const craftTypes = new Set(vm.runInNewContext(app.slice(begin, end) + "\nArray.from(CRAFT_ONLY_TYPE_LABELS)"));
const defaultIds = new Set(payload.events.filter(row => row.date_precision === "exact_day" && craftTypes.has(String(row.type || "").trim().toLowerCase())).map(row => row.event_id));
assert.equal(defaultIds.size, 770);

// Decode the current immutable packed trace source in place. Its order, rather
// than a new date/local-clock sort, establishes the application's actual chain.
const tracePin = payload.sourcePins.packedTraceIndex;
const packedPath = "C:/Users/jarod/Desktop/UFO Timeline map tool/data/releases/quality-20261007/map_delta/trace_event_index.bin.gz";
const compressed = fs.readFileSync(packedPath);
assert.equal(compressed.length, tracePin.bytes);
assert.equal(hash(compressed), tracePin.sha256);
const packed = zlib.gunzipSync(compressed);
assert.equal(packed.length, tracePin.decodedBytes);
assert.equal(hash(packed), tracePin.decodedSha256);
const globalScopedRows = [];
for (let offset = 0; offset < packed.length; offset += 48) {
  const id = Number(packed.readBigUInt64LE(offset));
  if (!events.has(id)) continue;
  const lat = packed.readDoubleLE(offset + 8), lon = packed.readDoubleLE(offset + 16);
  const ordinal = packed.readInt32LE(offset + 24);
  assert.equal(events.get(id).lat, lat);
  assert.equal(events.get(id).lon, lon);
  globalScopedRows.push([id, lat, lon, ordinal]);
}
assert.deepEqual(payload.traceEventOrder, globalScopedRows.map(row => row[0]), "Every scoped trace endpoint retains the complete packed source order");
const defaultRows = globalScopedRows.filter(row => defaultIds.has(row[0]));
function chain(index) {
  const result = [];
  for (let position = 1; position < defaultRows.length; position++) {
    const a = defaultRows[position - 1], b = defaultRows[position], gap = Math.abs(b[3] - a[3]);
    if (gap > 2) continue;
    result.push(chronology.orientSegment(index, { traceId: a[0] + "->" + b[0], fromEventId: a[0], toEventId: b[0],
      from: [a[1], a[2]], to: [b[1], b[2]], fromSortOrdinal: a[3], toSortOrdinal: b[3], gapDays: gap,
      bucket: { key: gap <= 1 ? "gap_le_1" : "gap_le_2" } }));
  }
  return result;
}
const initialTraces = chain(scopedIndex), completeTraces = chain(globalIndex);
assert.deepEqual(initialTraces, completeTraces, "Initial and complete views retain identical endpoints, gap bucket, orientation, and chronology basis");
assert.equal(initialTraces.length, 769, "721 observed render segments are a viewport count, not the raw window population");
assert.equal(hash(JSON.stringify(initialTraces.map(t => [t.fromEventId, t.toEventId, t.gapDays, t.chronology.status]))), manifest.traceParity.endpointsSha256);
assert.deepEqual(directions.summarizeDirections(initialTraces), manifest.traceParity.directions);
assert.deepEqual(directions.summarizeDirections(initialTraces), directions.summarizeDirections(completeTraces), "Radar counts and all eight direction sectors match the complete source");
assert.equal(manifest.traceParity.directions.orderedSegments, 263);
assert.equal(manifest.traceParity.directions.unorderedSegments, 504);
assert.equal(manifest.traceParity.directions.excludedCounts.zeroDistance, 2);
console.log("Progressive profile pins, current effective catalog scope, all encounter annotations, packed endpoint order, source-backed chronology and radar parity pass.");
