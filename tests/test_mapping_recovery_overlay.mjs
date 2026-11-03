import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const quality = require("../quality_detail_overlay.js");
const app = fs.readFileSync(new URL("../app.js", import.meta.url), "utf8");
const clone = value => structuredClone(value);
const original = { event_id: 123, canonical_event_id: "evt_fixture", source_id: "source-fixture", chunk_id: "chunk_000001", detail_index: 2,
  source: "nuforc", sort_date_iso: "1954-07-02", date_precision: "year", location_raw: "United States",
  lat: null, lon: null, has_coordinates: false, coordinate_source: "unresolved", location_precision: "country",
  description: "Preserved original account", raw_source_row: { Location: "United States" }, quality_date_review: { kept: true } };
const fields = ["event_id", "canonical_event_id", "source_id", "chunk_id", "detail_index", "source", "sort_date_iso", "location_raw", "lat", "lon", "has_coordinates", "coordinate_source", "location_precision"];
const reference = { kind: "country", label: "United States", note: "Approximate area reference; exact sighting position unknown.",
  authority_ids: ["geonames:6252001"], evidence_id: "area-reference:123", bounds: [-125, 24, -66, 49] };
const payload = { schemaVersion: 1, baseManifestSha256: "a".repeat(64), qualityManifestSha256: "b".repeat(64), patches: [{
  eventId: 123, chunkId: original.chunk_id, detailIndex: original.detail_index,
  guards: Object.fromEntries(fields.map(key => [key, original[key]])),
  setFields: { lat: 40, lon: -100, has_coordinates: true, coordinate_source: "reviewed_area_reference", location_precision: "country", location_reference: reference },
}] };
const config = { enabled: true, patchCount: 1, baseManifestSha256: payload.baseManifestSha256, qualityManifestSha256: payload.qualityManifestSha256 };
const index = quality.createMappingIndex(payload, config);
const mapped = quality.apply(index, original);
assert.equal(mapped.has_coordinates, true);
assert.deepEqual(mapped.raw_source_row, original.raw_source_row);
assert.deepEqual(mapped.quality_date_review, original.quality_date_review);
assert.equal(mapped.sort_date_iso, original.sort_date_iso, "earlier date repair is preserved");
assert.equal(original.has_coordinates, false);
assert.throws(() => quality.apply(index, { ...original, sort_date_iso: "1954-01-01" }), /stale/, "mapping guards require the date-repaired detail");
mapped.location_reference.label = "consumer mutation";
assert.equal(quality.apply(index, original).location_reference.label, "United States");
assert.throws(() => { index.getPatch(123).setFields.location_reference.label = "mutate index"; }, TypeError);
function refused(change, message) {
  const packet = clone(payload); change(packet.patches[0].setFields);
  assert.throws(() => quality.createMappingIndex(packet, config), message);
}
for (const key of ["description", "raw_fields", "location_raw", "sort_date_iso"]) refused(fields => { fields[key] = "overwritten"; }, /protected/);
refused(fields => { delete fields.location_reference; }, /incomplete/);
refused(fields => { fields.location_reference.kind = "exact_observer"; }, /kind/);
refused(fields => { fields.location_reference.extra = {}; }, /fields/);
refused(fields => { fields.location_reference.label = {}; }, /label/);
refused(fields => { fields.location_reference.note = "x".repeat(601); }, /note/);
refused(fields => { fields.location_reference.authority_ids = [{ id: "bad" }]; }, /authorities/);
refused(fields => { fields.location_reference.bounds = [-181, 0, 180, 90]; }, /bounds/);
refused(fields => { fields.location_reference.radius_km = Infinity; }, /radius/);
refused(fields => { fields.location_reference = JSON.parse('{"__proto__":{},"kind":"country","label":"US","note":"Area reference","evidence_id":"test"}'); }, /fields/);
refused(fields => { fields.location_precision = "exact_coords"; }, /precision mismatch/);
refused(fields => { fields.location_reference.kind = "compound_area"; }, /approximate/);
refused(fields => { fields.location_reference.kind = "locality"; fields.location_precision = "exact_coords"; }, /not an exact/);
refused(fields => { fields.lat = 91; }, /point/);
refused(fields => { fields.has_coordinates = false; }, /source/);
for (const source of ["reviewed_original_source_coordinate", "reviewed_area_reference", "reviewed_locality_reference"]) {
  const packet = clone(payload); packet.patches[0].setFields.coordinate_source = source;
  assert.equal(quality.createMappingIndex(packet, config).patchCount, 1);
}

function actual(name) {
  const start = app.indexOf("  function " + name + "(");
  const next = /\n  (?:async )?function |\n  const /g;
  next.lastIndex = start + 10;
  const end = next.exec(app);
  assert.ok(start >= 0 && end, name);
  return app.slice(start, end.index);
}
const escapeHtml = value => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const panel = { innerHTML: "" }, title = { textContent: "" };
const context = vm.createContext({ QUALITY_DETAILS: quality, console, escapeHtml, ENCOUNTERS: null, UFOCAT_REFERENCES: null,
  runtime: { mappingRecoveryDetailOverlay: index, catalogSummaryMemory: { fallbackPlaybackKeysReleased: 0, compactPlaybackKeys: 0, unusedPropertiesReleased: 0, prunedEvents: 0 },
    locationLabelOverlay: { status: "ready", patchesByEventId: new Map([["123", { location_precision: "city" }]]) } },
  activeCatalogUsesCanonicalWebArtifacts: () => true, canonicalPlaybackSortKeyIsDefaultFallback: () => false,
  internCanonicalSummaryString: value => value, isoToOrdinal: () => 0,
  DEFAULT_CANONICAL_PLAYBACK_SORT_KEY: [],
  PACKED_POINTS_STATUS: { READY: "ready" },
  els: { detailPanel: panel, detailStageTitle: title }, displayLocationForEvent: event => event.location_raw,
  eventDateLabel: event => event.sort_date_iso, locationPrecisionDisplayLabel: value => value,
  formatList: () => "", renderLinkList: () => "",
});
for (const name of ["locationReferenceForEvent", "eventHasAreaReference", "mappingStatusBadge", "locationReferencePopupRows",
  "compactCanonicalSummaryEventForRuntime", "augmentPackedMapEventDisplayFields", "applyMappingRecoveryDetailOverlay", "applyLocationLabelOverlay", "renderDetail"]) {
  vm.runInContext(actual(name), context);
}
const applied = context.applyMappingRecoveryDetailOverlay(original);
const compact = context.compactCanonicalSummaryEventForRuntime(applied);
assert.deepEqual(compact.location_reference, applied.location_reference, "catalog compaction retains the compact reference");
const packed = context.augmentPackedMapEventDisplayFields({ event_id: 123, has_coordinates: true, lat: compact.lat, lon: compact.lon }, compact);
assert.deepEqual(packed.location_reference, reference, "packed marker inherits reference metadata");
assert.match(context.mappingStatusBadge(packed), /Area ref/);
assert.doesNotMatch(context.mappingStatusBadge(packed), />Mapped</);
assert.match(context.mappingStatusBadge({ has_coordinates: false }), />Unmapped</);
assert.equal(context.applyLocationLabelOverlay(applied).location_precision, "country", "older label overlay cannot undo recovery precision");
const hostile = { ...applied, location_reference: { ...reference, label: '<img src=x onerror="alert(1)">', note: "</div><script>alert(1)</script>" } };
const popup = context.locationReferencePopupRows(hostile);
assert.match(popup, /&lt;img/); assert.doesNotMatch(popup, /<img|<script/);
context.renderDetail(hostile);
assert.match(panel.innerHTML, /Area Reference/);
assert.match(panel.innerHTML, /&lt;img/); assert.doesNotMatch(panel.innerHTML, /<img|<script/);
assert.equal(context.locationReferenceForEvent({ location_reference: { kind: "country" } }), null);
assert.match(app, /applyMappingRecoveryDetailOverlay\(applyAnalysisRepairDetailOverlay\(applyDetailQualityOverlay\(event\)\)\)/,
  "mapping overlay is applied after existing quality and date repair overlays");
assert.match(app, /measureStartupStep\("reviewed mapping recovery load", ensureMappingRecoveryDetailOverlayLoaded\)/);
assert.match(app, /JSON\.stringify\(runtime\.appConfig\.mappingRecoveryDetailOverlay \|\| \{\}\)/, "search cache includes mapping release identity");
console.log("Mapping recovery: exact guards, protected fields, bounded references, summary/packed retention, area badges, escaped details and overlay ordering passed.");
