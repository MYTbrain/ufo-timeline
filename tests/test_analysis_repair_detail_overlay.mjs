import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { createHash, webcrypto } from "node:crypto";
import { readFileSync, existsSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const repair = require("../analysis_repair_detail_overlay.js");
const quality = require("../quality_detail_overlay.js");
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const shared = process.env.UFO_SHARED_DATA_ROOT || "C:/Users/jarod/Desktop/UFO Timeline map tool";
const hash = (value) => createHash("sha256").update(value).digest("hex");
const clone = (value) => structuredClone(value);
function freezeTree(value) {
  if (value && typeof value === "object") {
    Object.values(value).forEach(freezeTree);
    Object.freeze(value);
  }
  return value;
}
const core = ["event_id", "canonical_event_id", "source_id", "source", "date_raw", "date_iso",
  "end_date_iso", "sort_date_iso", "date_precision", "chunk_id", "detail_index"];
const rawKeys = ["id", "source", "source_id", "name", "date", "location", "city", "country", "description"];
const pins = Object.fromEntries(repair.SOURCE_PIN_KEYS.map((key) => [key, hash("synthetic fixture: " + key)]));
function guardsFor(row) {
  return core.map((key) => Object.hasOwn(row, key)
    ? { path: [key], exists: true, value: row[key] }
    : { path: [key], exists: false });
}
function interval(start, end) {
  const midpoint = new Date(Date.parse(start + "T00:00:00Z") +
    Math.floor((Date.parse(end + "T00:00:00Z") - Date.parse(start + "T00:00:00Z")) / 86400000 / 2) * 86400000)
    .toISOString().slice(0, 10);
  return { date_iso: start, end_date_iso: end, sort_date_iso: midpoint,
    date_interval_semantics: "source_calendar_precision_bounds_not_observed_days", exact_day_eligible: false };
}
const original = {
  event_id: 123, canonical_event_id: "mufon-example", source_id: "456", source: "mufon",
  date_raw: "1968-00-00", date_iso: null, end_date_iso: null, sort_date_iso: null, date_precision: "unknown",
  chunk_id: "chunk_000000", detail_index: 2, description: "The original source account remains unchanged.",
  lat: 37.3, lon: -93.5, has_coordinates: true, coordinate_source: "reviewed_locality_reference",
  quality_view_changes: { source_record_preserved: true, decisions: [{ decision_id: "earlier-review" }] },
  quality_date_review: { confidence: "review_only" }, raw_source_row: { date: "1968-00-00" }
};
function mufonPatch(row = original, start = "1968-01-01", end = "1968-12-31", precision = "year") {
  return { eventId: row.event_id, chunkId: row.chunk_id, detailIndex: row.detail_index,
    kind: "mufon_partial_date", guards: guardsFor(row), setFields: {
      ...interval(start, end), date_precision: precision,
      date_recovery_contract: "mufon_zero_calendar_components_v1",
      date_recovery_provenance: { overlay_id: "synthetic-mufon-example", original_date_precision: "unknown",
        source: "mufon", raw_date_sha256: hash(row.date_raw), original_detail_date_identity_sha256: hash("original example"),
        interval_bounds_are_observed_days: false, sort_midpoint_is_observed_day: false }
    } };
}
function packet(patches = [mufonPatch()]) {
  return { schemaId: repair.SCHEMA, schemaVersion: 1, sourcePins: clone(pins), patches };
}
function configFor(value) {
  return { enabled: true, sourcePins: clone(value.sourcePins), patchCount: value.patches.length };
}
const payload = packet();
const config = configFor(payload);
const index = repair.createIndex(payload, config);
assert.equal(index.patchCount, 1);
assert.equal(index.hasPatch("123"), true);
assert.equal(index.hasPatch(999), false);
assert.equal(globalThis.UfoAnalysisRepairDetailOverlay, repair);
const before = clone(original);
freezeTree(original);
const corrected = repair.apply(index, original);
assert.notEqual(corrected, original);
assert.equal(corrected.date_precision, "year");
assert.equal(corrected.date_iso, "1968-01-01");
assert.equal(corrected.end_date_iso, "1968-12-31");
assert.equal(corrected.sort_date_iso, "1968-07-01");
assert.equal(corrected.exact_day_eligible, false);
for (const field of ["date_raw", "description", "lat", "lon", "has_coordinates", "coordinate_source",
  "event_id", "canonical_event_id", "source_id", "source", "raw_source_row", "quality_view_changes", "quality_date_review"]) {
  assert.deepEqual(corrected[field], before[field], "preserved earlier source/quality field: " + field);
}
assert.deepEqual(original, before, "applying a repair cannot mutate the source detail");
corrected.date_recovery_provenance.overlay_id = "consumer mutation";
assert.equal(repair.apply(index, original).date_recovery_provenance.overlay_id, "synthetic-mufon-example");
assert.throws(() => { index.getPatch(123).setFields.date_precision = "exact_day"; }, TypeError);
assert.throws(() => { index.getPatch(123).guards[0].path.push("extra"); }, TypeError);
payload.patches[0].setFields.date_recovery_provenance.overlay_id = "input mutation";
assert.equal(repair.apply(index, original).date_recovery_provenance.overlay_id, "synthetic-mufon-example");
const unrelated = { event_id: 999, description: "Unchanged source record" };
assert.equal(repair.apply(index, unrelated), unrelated);
assert.equal(repair.apply(index, null), null);
const empty = packet([]);
assert.equal(repair.apply(repair.createIndex(empty, configFor(empty)), original), original);

for (const field of core.filter((key) => key !== "event_id")) {
  assert.throws(() => repair.apply(index, { ...original, [field]: "stale" }), /stale/, "source guard: " + field);
  const absent = clone(original);
  delete absent[field];
  assert.throws(() => repair.apply(index, absent), /stale/, "missing source guard: " + field);
}
const inheritedDate = Object.assign(Object.create({ date_iso: null }), original);
delete inheritedDate.date_iso;
assert.throws(() => repair.apply(index, inheritedDate), /stale/, "inherited source properties cannot satisfy guards");
const missingDate = clone(original);
delete missingDate.date_iso;
const missingPacket = packet([mufonPatch(missingDate)]);
const missingIndex = repair.createIndex(missingPacket, configFor(missingPacket));
assert.equal(repair.apply(missingIndex, missingDate).date_precision, "year");
assert.throws(() => repair.apply(missingIndex, { ...missingDate, date_iso: null }), /stale/,
  "explicit null differs from an absent source field");
const monthSource = { ...clone(original), date_raw: "1968-02-00" };
const monthPacket = packet([mufonPatch(monthSource, "1968-02-01", "1968-02-29", "month")]);
const monthResult = repair.apply(repair.createIndex(monthPacket, configFor(monthPacket)), monthSource);
assert.equal(monthResult.date_precision, "month");
assert.equal(monthResult.end_date_iso, "1968-02-29");
assert.equal(monthResult.sort_date_iso, "1968-02-15");

const raw = { id: 8, source: "phenomenainon_updb", source_id: "reviewed-8", name: "Original source name",
  date: "1900-01-01", location: "Original location", city: "Original city", country: "Original country",
  description: "A reviewed account gives an occurrence in 1954; its original narrative is retained." };
const reviewed = { ...clone(original), event_id: 124, canonical_event_id: "reviewed-example", source_id: "reviewed-8",
  source: "phenomenainon_updb", date_raw: "1900-01-01", date_iso: "1900-01-01", end_date_iso: "1900-01-01",
  sort_date_iso: "1900-01-01", date_precision: "exact_day", detail_index: 3, raw_source_row: [clone(raw)] };
function reviewedPatch(row = reviewed, array = true) {
  const sourceRow = array ? row.raw_source_row[0] : row.raw_source_row;
  return { eventId: row.event_id, chunkId: row.chunk_id, detailIndex: row.detail_index, kind: "source_reviewed_year",
    guards: [...guardsFor(row), ...rawKeys.map((key) => ({ path: array ? ["raw_source_row", 0, key] : ["raw_source_row", key],
      exists: true, value: sourceRow[key] }))], setFields: {
      ...interval("1954-01-01", "1954-12-31"), date_precision: "year",
      date_recovery_contract: "source_reviewed_occurrence_year_v1",
      date_recovery_provenance: { overlay_id: "synthetic-reviewed-year-example", original_date_was_reviewed_sentinel: true,
        source_review_sha256: pins.sourceReviewSha256, source_narrative_sha256: hash(sourceRow.description),
        original_detail_date_identity_sha256: hash("reviewed example"), interval_bounds_are_observed_days: false,
        sort_midpoint_is_observed_day: false }
    } };
}
const reviewedPacket = packet([reviewedPatch()]);
const reviewedIndex = repair.createIndex(reviewedPacket, configFor(reviewedPacket));
const reviewedBefore = clone(reviewed);
const reviewedResult = repair.apply(reviewedIndex, reviewed);
assert.equal(reviewedResult.date_precision, "year");
assert.equal(reviewedResult.sort_date_iso, "1954-07-02");
assert.equal(reviewedResult.exact_day_eligible, false);
assert.deepEqual(reviewedResult.raw_source_row, reviewedBefore.raw_source_row);
assert.deepEqual(reviewed, reviewedBefore);
for (const field of rawKeys) {
  const stale = clone(reviewed);
  stale.raw_source_row[0][field] = "stale raw source field";
  assert.throws(() => repair.apply(reviewedIndex, stale), /stale/, "nested source guard: " + field);
}
assert.throws(() => repair.apply(reviewedIndex, { ...reviewed, raw_source_row: { 0: raw } }), /stale/,
  "an indexed array guard cannot be satisfied by an object with a numeric property");
const reviewedObject = { ...clone(reviewed), raw_source_row: clone(raw) };
const reviewedObjectPacket = packet([reviewedPatch(reviewedObject, false)]);
assert.equal(repair.apply(repair.createIndex(reviewedObjectPacket, configFor(reviewedObjectPacket)), reviewedObject).date_precision, "year");
const inheritedRaw = { ...reviewedObject, raw_source_row: Object.assign(Object.create({ date: raw.date }), raw) };
delete inheritedRaw.raw_source_row.date;
assert.throws(() => repair.apply(repair.createIndex(reviewedObjectPacket, configFor(reviewedObjectPacket)), inheritedRaw), /stale/);

function refused(change, message = undefined, starting = packet()) {
  const candidate = clone(starting);
  change(candidate);
  assert.throws(() => repair.createIndex(candidate, configFor(candidate)), message);
}
assert.throws(() => repair.createIndex(packet(), { ...config, enabled: false }), /delivery contract/);
assert.throws(() => repair.createIndex(packet(), { ...config, patchCount: 2 }), /partial/);
assert.throws(() => repair.createIndex(packet(), { ...config, sourcePins: { ...pins, sourceReviewSha256: hash("wrong pin") } }), /stale source pins/);
refused((p) => { p.schemaId = "other-schema"; }, /schema/);
refused((p) => { p.schemaVersion = 2; }, /schema/);
refused((p) => { delete p.sourcePins.sourceReviewSha256; }, /source pins/);
refused((p) => { p.sourcePins.unpinnedExtra = hash("extra"); }, /source pins/);
refused((p) => { p.sourcePins.sourceReviewSha256 = "not-a-hash"; }, /source pins/);
refused((p) => { p.patches.push(clone(p.patches[0])); }, /repeated/);
refused((p) => { p.patches[0].guards[0].value = 555; }, /locator/);
refused((p) => { p.patches[0].guards.pop(); }, /source guards/);
refused((p) => { p.patches[0].guards.push(clone(p.patches[0].guards[0])); }, /source guards/);
refused((p) => { p.patches[0].guards[1].value = {}; }, /source guard/);
refused((p) => { p.patches[0].guards[1].value = Infinity; }, /source guard/);
refused((p) => { p.patches[0].guards[1].exists = "true"; }, /source guard/);
for (const path of [["lat"], ["raw_source_row", "extra"], ["raw_source_row", "0", "date"],
  ["raw_source_row", -1, "date"], ["raw_source_row", "nested", "date"], ["raw_source_row", 0, "date", "extra"],
  ["__proto__"], ["raw_source_row", "__proto__"], ["raw_source_row", "constructor"], ["raw_source_row", "prototype"]]) {
  refused((p) => { p.patches[0].guards.push({ path, exists: false }); }, /source guard/);
}
for (const field of ["description", "raw_source_row", "lat", "lon", "has_coordinates", "event_id", "canonical_event_id", "quality_view_changes"]) {
  refused((p) => { p.patches[0].setFields[field] = "protected overwrite"; }, /protected/, packet());
}
refused((p) => { delete p.patches[0].setFields.date_recovery_provenance; }, /incomplete/);
refused((p) => { p.patches[0].setFields.exact_day_eligible = true; }, /calendar interval/);
refused((p) => { p.patches[0].setFields.date_precision = "exact_day"; }, /year bounds/);
refused((p) => { p.patches[0].setFields.date_iso = "1968-01-02"; }, /year bounds/);
refused((p) => { p.patches[0].setFields.sort_date_iso = "1968-07-02"; }, /midpoint/);
refused((p) => { p.patches[0].setFields.date_iso = "1968-02-30"; }, /calendar interval/);
refused((p) => { p.patches[0].setFields.date_interval_semantics = "observed_days"; }, /calendar interval/);
refused((p) => { p.patches[0].setFields.date_recovery_provenance.interval_bounds_are_observed_days = true; }, /provenance/);
refused((p) => { p.patches[0].setFields.date_recovery_provenance.sort_midpoint_is_observed_day = true; }, /provenance/);
refused((p) => { p.patches[0].kind = "unreviewed_date"; }, /transition/);
refused((p) => { p.patches[0].guards.find((g) => g.path[0] === "date_raw").value = "1968-05-14"; }, /MUFON/);
refused((p) => { p.patches[0].guards.find((g) => g.path[0] === "source").value = "nuforc"; }, /MUFON/);
refused((p) => { p.patches[0].setFields.end_date_iso = "1968-02-28"; }, /month bounds/, monthPacket);
refused((p) => { p.patches[0].guards = p.patches[0].guards.filter((g) => g.path.at(-1) !== "description"); }, /raw-source guards/, reviewedPacket);
refused((p) => { p.patches[0].guards.find((g) => g.path[0] === "date_raw").value = "1954-01-01"; }, /reviewed occurrence/, reviewedPacket);

const pinnedBytes = Buffer.from("Synthetic integrity fixture, without persistent files.");
const byteConfig = { gzipBytes: pinnedBytes.byteLength, gzipSha256: hash(pinnedBytes), bytes: pinnedBytes.byteLength, sha256: hash(pinnedBytes) };
for (const [method, sizeKey, hashKey] of [["verifyCompressedPayload", "gzipBytes", "gzipSha256"], ["verifyDecodedPayload", "bytes", "sha256"]]) {
  await repair[method](pinnedBytes, byteConfig, webcrypto.subtle);
  await repair[method](pinnedBytes.buffer.slice(pinnedBytes.byteOffset, pinnedBytes.byteOffset + pinnedBytes.byteLength), byteConfig, webcrypto.subtle);
  await assert.rejects(repair[method](pinnedBytes, { ...byteConfig, [sizeKey]: pinnedBytes.byteLength + 1 }, webcrypto.subtle), /length/);
  await assert.rejects(repair[method](pinnedBytes, { ...byteConfig, [hashKey]: hash("wrong bytes") }, webcrypto.subtle), /hash mismatch/);
  const corrupt = Buffer.from(pinnedBytes);
  corrupt[0] ^= 1;
  await assert.rejects(repair[method](corrupt, byteConfig, webcrypto.subtle), /hash mismatch/);
  await assert.rejects(repair[method](pinnedBytes, {}, webcrypto.subtle), /pin missing/);
  await assert.rejects(repair[method](pinnedBytes, byteConfig, {}), /verification unavailable/);
}

// The release packet stays canonical in place. Read compressed source chunks only
// for a bounded representative sample; no source copies or persistent fixtures.
const generatedManifestPath = join(root, "data/analysis_repair_detail/manifest.json");
if (existsSync(generatedManifestPath)) {
  const manifest = JSON.parse(readFileSync(generatedManifestPath, "utf8"));
  const delivery = manifest.deliveryContract || manifest;
  const generatedConfig = { ...delivery, enabled: true };
  const compressed = readFileSync(join(dirname(generatedManifestPath), manifest.file || delivery.file));
  const decoded = gunzipSync(compressed);
  await repair.verifyCompressedPayload(compressed, generatedConfig, webcrypto.subtle);
  await repair.verifyDecodedPayload(decoded, generatedConfig, webcrypto.subtle);
  const generated = JSON.parse(decoded.toString("utf8"));
  const generatedIndex = repair.createIndex(generated, generatedConfig);
  const receipt = JSON.parse(readFileSync(join(dirname(generatedManifestPath), "receipt.json"), "utf8"));
  for (const pinName of repair.SOURCE_PIN_KEYS) {
    const sourcePin = receipt.sourcePins[pinName];
    assert.equal(sourcePin.sha256, generated.sourcePins[pinName], "receipt/packet source pin: " + pinName);
    const sourceBytes = readFileSync(sourcePin.path);
    assert.equal(sourceBytes.byteLength, sourcePin.bytes, "actual source length: " + pinName);
    assert.equal(hash(sourceBytes), sourcePin.sha256, "actual source hash: " + pinName);
  }
  assert.equal(generatedIndex.patchCount, 3900, "frozen repair packet contains the 3,898 partial dates and two reviewed years");
  assert.equal(generated.patches.filter((p) => p.kind === "mufon_partial_date").length, 3898);
  assert.equal(generated.patches.filter((p) => p.kind === "source_reviewed_year").length, 2);
  const representatives = [generated.patches.find((p) => p.kind === "mufon_partial_date" && p.setFields.date_precision === "year"),
    generated.patches.find((p) => p.kind === "mufon_partial_date" && p.setFields.date_precision === "month"),
    ...generated.patches.filter((p) => p.kind === "source_reviewed_year")].filter(Boolean);
  const appConfig = JSON.parse(readFileSync(join(root, "data/app_config.json"), "utf8"));
  const qualityPath = receipt.sourcePins.existingQualityOverlayGzipSha256.path;
  const qualityPayload = JSON.parse(gunzipSync(readFileSync(qualityPath)).toString("utf8"));
  const qualityIndex = quality.createIndex(qualityPayload, appConfig.detailQualityOverlay);
  const chunkCache = new Map();
  for (const patch of representatives) {
    if (!chunkCache.has(patch.chunkId)) {
      const sourcePin = receipt.sourceChunks.find((entry) =>
        basename(entry.path).replace(/\.gz$/, "").replace(/\.json$/, "") === patch.chunkId);
      const sourcePath = sourcePin?.path || join(shared, "data/canonical_web/event_chunks", patch.chunkId + ".json.gz");
      const sourceBytes = readFileSync(sourcePath);
      if (sourcePin) assert.equal(hash(sourceBytes), sourcePin.sha256, "exact frozen detail source pin");
      const chunk = JSON.parse((sourcePath.endsWith(".gz") ? gunzipSync(sourceBytes) : sourceBytes).toString("utf8"));
      chunkCache.set(patch.chunkId, Array.isArray(chunk) ? chunk : (chunk.events || chunk.rows || chunk.records));
    }
    const rows = chunkCache.get(patch.chunkId);
    assert.ok(Array.isArray(rows), "source detail chunk contains its event rows");
    const base = rows[patch.detailIndex];
    assert.equal(base.event_id, patch.eventId, "source chunk/detail locator is exact");
    const effective = quality.apply(qualityIndex, base);
    const preserved = clone(effective);
    const repaired = repair.apply(generatedIndex, effective);
    assert.equal(repaired.date_precision, patch.setFields.date_precision);
    assert.equal(repaired.sort_date_iso, patch.setFields.sort_date_iso);
    assert.equal(repaired.exact_day_eligible, false);
    assert.deepEqual(effective, preserved, "generated overlay preserves original detail and earlier quality corrections");
    for (const field of Object.keys(preserved).filter((key) => !Object.hasOwn(patch.setFields, key))) {
      assert.deepEqual(repaired[field], preserved[field], "generated overlay protected field: " + field);
    }
  }
  console.log("Generated repair packet: 3,900 pinned patches and " + representatives.length + " representative canonical details passed.");
} else {
  console.log("Generated repair packet unavailable; synthetic module contract checks passed.");
}
console.log("Analysis repair details: exact guards, partial/reviewed intervals, immutable source/quality preservation, protected fields and integrity checks passed.");
