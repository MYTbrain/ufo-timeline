import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { webcrypto, createHash } from "node:crypto";
const require = createRequire(import.meta.url);
const quality = require("../quality_detail_overlay.js");
const original = { event_id: 123, canonical_event_id: "native-example", source_id: "456", chunk_id: "chunk_000000", detail_index: 2,
  source: "nuforc", sort_date_iso: "1968-06-01", date_precision: "exact_day", location_raw: "Ash Grove, MD",
  lat: null, lon: null, has_coordinates: false, coordinate_source: "unresolved", location_precision: "city",
  description: "The original account describes a Missouri farm and an uncertain day.", raw_fields: { Location: "Ash Grove, MD" } };
const guards = Object.fromEntries(["event_id", "canonical_event_id", "source_id", "chunk_id", "detail_index", "source", "sort_date_iso", "date_precision", "location_raw", "lat", "lon", "has_coordinates", "coordinate_source", "location_precision"].map((key) => [key, original[key]]));
const patch = { eventId: 123, chunkId: "chunk_000000", detailIndex: 2, guards,
  setFields: { lat: 37.31533, lon: -93.5852, has_coordinates: true, coordinate_source: "reviewed_locality_reference",
    location_precision: "approximate", date_precision: "approximate", estimated_utc_timestamp_ms: null,
    playback_sort_confidence: "none", quality_view_changes: { source_record_preserved: true, decisions: [{ decision_id: "example" }] } } };
const payload = { schemaVersion: 1, baseManifestSha256: "a".repeat(64), qualityManifestSha256: "b".repeat(64), patches: [patch] };
const config = { enabled: true, patchCount: 1, baseManifestSha256: payload.baseManifestSha256, qualityManifestSha256: payload.qualityManifestSha256 };
const index = quality.createIndex(payload, config);
const corrected = quality.apply(index, original);
assert.equal(corrected.date_precision, "approximate");
assert.equal(corrected.sort_date_iso, original.sort_date_iso);
assert.equal(corrected.description, original.description);
assert.deepEqual(corrected.raw_fields, original.raw_fields);
assert.equal(original.has_coordinates, false);
assert.equal(corrected.has_coordinates, true);
corrected.quality_view_changes.decisions[0].decision_id = "consumer mutation";
assert.equal(quality.apply(index, original).quality_view_changes.decisions[0].decision_id, "example");
assert.throws(() => { index.getPatch(123).setFields.lat = 0; });
for (const key of Object.keys(guards).filter((key) => key !== "event_id")) {
  assert.throws(() => quality.apply(index, { ...original, [key]: "stale" }), /stale/);
}
const unrelated = { event_id: 999, description: "Unchanged source record" };
assert.equal(quality.apply(index, unrelated), unrelated);
const metadataOnly = structuredClone(payload);
metadataOnly.patches[0].setFields = { quality_date_review: { confidence: "review_only" } };
const unmappedIndex = quality.createIndex(metadataOnly, config);
const prunedUnmapped = { ...original };
delete prunedUnmapped.lat;
delete prunedUnmapped.lon;
const annotated = quality.apply(unmappedIndex, prunedUnmapped);
assert.equal(annotated.has_coordinates, false);
assert.equal(Object.hasOwn(annotated, "lat"), false);
assert.equal(Object.hasOwn(annotated, "lon"), false);
assert.equal(Object.hasOwn(prunedUnmapped, "quality_date_review"), false);
assert.throws(() => quality.apply(unmappedIndex, { ...prunedUnmapped, lat: 0 }), /stale/);
function changedPayload(change) {
  const candidate = structuredClone(payload);
  change(candidate);
  return candidate;
}
assert.throws(() => quality.createIndex(payload, { ...config, qualityManifestSha256: "c".repeat(64) }), /stale/);
assert.throws(() => quality.createIndex(payload, { ...config, patchCount: 2 }), /partial/);
assert.throws(() => quality.createIndex(changedPayload((p) => p.patches[0].guards.lat = undefined), config));
assert.throws(() => quality.createIndex(changedPayload((p) => delete p.patches[0].guards.source), config), /incomplete/);
assert.throws(() => quality.createIndex(changedPayload((p) => p.patches[0].guards.event_id = 456), config), /locator/);
assert.throws(() => quality.createIndex(changedPayload((p) => p.patches[0].setFields.raw_fields = {}), config), /protected/);
assert.throws(() => quality.createIndex(changedPayload((p) => p.patches[0].setFields.sort_date_iso = "1900-01-01"), config), /protected/);
assert.throws(() => quality.createIndex(changedPayload((p) => delete p.patches[0].guards.date_precision), config), /precision/);
assert.throws(() => quality.createIndex(changedPayload((p) => p.patches[0].setFields.date_precision = "exact_day"), config), /precision/);
const invalidPoint = quality.createIndex(changedPayload((p) => p.patches[0].setFields.lat = 91), config);
assert.throws(() => quality.apply(invalidPoint, original), /invalid mapped/);
const duplicate = changedPayload((p) => p.patches.push(structuredClone(p.patches[0])));
assert.throws(() => quality.createIndex(duplicate, { ...config, patchCount: 2 }), /repeated/);
const bytes = Buffer.from("Pinned compressed bytes example");
const gzipSha256 = createHash("sha256").update(bytes).digest("hex");
await quality.verifyCompressedPayload(bytes, { gzipSha256 }, webcrypto.subtle);
await assert.rejects(quality.verifyCompressedPayload(bytes, { gzipSha256: "0".repeat(64) }, webcrypto.subtle), /hash mismatch/);
await assert.rejects(quality.verifyCompressedPayload(bytes, {}, webcrypto.subtle), /pin missing/);
console.log("Quality details: source preservation, approximate precision, identity/guard/field controls, isolation and compressed integrity passed.");
