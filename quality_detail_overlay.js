(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.UfoQualityDetailOverlay = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const CORE_GUARDS = ["source", "sort_date_iso", "location_raw", "lat", "lon", "coordinate_source", "location_precision", "has_coordinates"];
  const IDENTITY_GUARDS = ["event_id", "canonical_event_id", "source_id", "chunk_id", "detail_index"];
  const GUARDS = new Set(CORE_GUARDS.concat(IDENTITY_GUARDS, ["date_precision"]));
  const FIELDS = new Set([
    "lat", "lon", "has_coordinates", "coordinate_source", "location_precision",
    "location_raw", "city", "country", "state_province", "date_precision",
    "time_sort_kind", "time_sort_confidence", "time_bucket_label",
    "parsed_time_local_minutes", "parsed_time_local_range_start_minutes", "parsed_time_local_range_end_minutes",
    "resolved_timezone", "timezone_source", "timezone_confidence",
    "estimated_utc_timestamp_ms", "estimated_utc_range_start_ms", "estimated_utc_range_end_ms",
    "playback_sort_confidence", "playback_sort_reason", "playback_sort_key",
    "quality_view_changes", "quality_date_review", "quality_incident_relationships", "quality_original_account",
    "location_reference"
  ]);
  const REFERENCE_KINDS = new Set(["country", "state", "province", "locality", "compound_area", "source_coordinate"]);
  const REFERENCE_FIELDS = new Set(["kind", "label", "note", "authority_ids", "bounds", "radius_km", "evidence_id"]);
  const MAPPING_FIELDS = new Set(["lat", "lon", "has_coordinates", "coordinate_source", "location_precision", "location_reference"]);

  function requireValue(condition, message) {
    if (!condition) throw new Error("Quality detail correction refused: " + message);
  }

  function plain(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value) &&
      (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
  }

  function validHash(value) {
    return typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
  }

  function freezeTree(value) {
    if (value && typeof value === "object") {
      Object.values(value).forEach(freezeTree);
      Object.freeze(value);
    }
    return value;
  }

  function validateLocationReference(value) {
    requireValue(plain(value) && Object.keys(value).every((key) => REFERENCE_FIELDS.has(key)), "invalid location reference fields");
    requireValue(REFERENCE_KINDS.has(value.kind), "unsupported location reference kind");
    for (const [key, limit] of [["label", 160], ["note", 600], ["evidence_id", 160]]) {
      requireValue(typeof value[key] === "string" && value[key].trim().length > 0 && value[key].length <= limit &&
        !/[\u0000-\u001f\u007f]/.test(value[key]), "invalid location reference " + key);
    }
    if (Object.hasOwn(value, "authority_ids")) {
      requireValue(Array.isArray(value.authority_ids) && value.authority_ids.length > 0 && value.authority_ids.length <= 8 &&
        value.authority_ids.every((id) => typeof id === "string" && id.length <= 160 && /^[a-zA-Z0-9:_./#-]+$/.test(id)),
        "invalid location reference authorities");
    }
    if (Object.hasOwn(value, "bounds")) {
      const b = value.bounds;
      requireValue(Array.isArray(b) && b.length === 4 && b.every((n) => typeof n === "number" && Number.isFinite(n)) &&
        b[0] >= -180 && b[2] <= 180 && b[1] >= -90 && b[3] <= 90 && b[0] <= b[2] && b[1] <= b[3],
        "invalid location reference bounds");
    }
    if (Object.hasOwn(value, "radius_km")) {
      requireValue(typeof value.radius_km === "number" && Number.isFinite(value.radius_km) && value.radius_km > 0 && value.radius_km <= 20040,
        "invalid location reference radius");
    }
    requireValue(new TextEncoder().encode(JSON.stringify(value)).byteLength <= 1024, "location reference is too large");
    return value;
  }

  function createIndex(payload, config) {
    requireValue(plain(payload) && payload.schemaVersion === 1, "unsupported payload schema");
    requireValue(plain(config) && config.enabled === true, "delivery contract is disabled");
    for (const key of ["baseManifestSha256", "qualityManifestSha256"]) {
      requireValue(validHash(config[key]) && payload[key] === config[key], "stale " + key);
    }
    requireValue(Array.isArray(payload.patches) && Number.isSafeInteger(config.patchCount) && payload.patches.length === config.patchCount,
      "partial correction payload");
    const patches = new Map();
    for (const patch of payload.patches) {
      requireValue(plain(patch) && Number.isSafeInteger(patch.eventId) && patch.eventId >= 0, "invalid record identity");
      const id = String(patch.eventId);
      requireValue(!patches.has(id), "repeated record identity");
      requireValue(plain(patch.guards) && plain(patch.setFields), "missing exact guards or changes");
      requireValue(CORE_GUARDS.every((key) => Object.hasOwn(patch.guards, key)), "incomplete source guards");
      requireValue(IDENTITY_GUARDS.every((key) => Object.hasOwn(patch.guards, key)), "incomplete identity guards");
      requireValue(Object.keys(patch.guards).every((key) => GUARDS.has(key)), "unsupported source guard");
      requireValue(Object.values(patch.guards).every((value) => value === null || typeof value === "string" ||
        typeof value === "boolean" || (typeof value === "number" && Number.isFinite(value))), "unsupported source guard value");
      requireValue(typeof patch.chunkId === "string" && /^chunk_[0-9]{6}$/.test(patch.chunkId) &&
        Number.isSafeInteger(patch.detailIndex) && patch.detailIndex >= 0, "invalid detail locator");
      requireValue(patch.guards.event_id === patch.eventId && patch.guards.chunk_id === patch.chunkId && patch.guards.detail_index === patch.detailIndex,
        "conflicting detail locator");
      requireValue(Object.keys(patch.setFields).length > 0 && Object.keys(patch.setFields).every((key) => FIELDS.has(key)), "protected source field edit");
      if (Object.hasOwn(patch.setFields, "date_precision")) {
        requireValue(patch.guards.date_precision === "exact_day" && patch.setFields.date_precision === "approximate", "unsupported precision transition");
      }
      if (Object.hasOwn(patch.setFields, "location_reference")) validateLocationReference(patch.setFields.location_reference);
      patches.set(id, freezeTree(JSON.parse(JSON.stringify(patch))));
    }
    return Object.freeze({ patchCount: patches.size, hasPatch: (id) => patches.has(String(id)), getPatch: (id) => patches.get(String(id)) });
  }

  function createMappingIndex(payload, config) {
    requireValue(plain(payload) && Array.isArray(payload.patches), "invalid mapping recovery payload");
    for (const patch of payload.patches) {
      requireValue(plain(patch) && plain(patch.setFields) &&
        Object.keys(patch.setFields).every((key) => MAPPING_FIELDS.has(key)) &&
        Array.from(MAPPING_FIELDS).every((key) => Object.hasOwn(patch.setFields, key)), "incomplete or protected mapping recovery fields");
      const fields = patch.setFields;
      const reference = validateLocationReference(fields.location_reference);
      requireValue(fields.has_coordinates === true && typeof fields.coordinate_source === "string" &&
        fields.coordinate_source.length > 0 && fields.coordinate_source.length <= 100 && fields.coordinate_source !== "unresolved",
        "invalid mapping recovery source");
      requireValue(typeof fields.lat === "number" && Number.isFinite(fields.lat) && Math.abs(fields.lat) <= 90 &&
        typeof fields.lon === "number" && Number.isFinite(fields.lon) && Math.abs(fields.lon) <= 180,
        "invalid mapping recovery point");
      const precision = fields.location_precision;
      requireValue(typeof precision === "string" && new Set(["country", "state", "province", "approximate", "city", "exact_coords", "mapped"]).has(precision),
        "invalid mapping recovery precision");
      if (["country", "state", "province"].includes(reference.kind)) {
        requireValue(precision === reference.kind, "administrative reference precision mismatch");
      } else if (reference.kind === "compound_area") {
        requireValue(precision === "approximate", "compound area requires approximate precision");
      } else if (reference.kind === "locality") {
        requireValue(precision === "city" || precision === "approximate", "locality reference is not an exact position");
      }
    }
    return createIndex(payload, config);
  }

  function apply(index, original) {
    if (!original || original.event_id == null) return original;
    const patch = index.getPatch(original.event_id);
    if (!patch) return original;
    for (const [key, expected] of Object.entries(patch.guards)) {
      const actual = Object.hasOwn(original, key) ? original[key] : null;
      requireValue(actual === expected, "stale " + key + " for " + patch.eventId);
    }
    const effective = Object.assign({}, original, JSON.parse(JSON.stringify(patch.setFields)));
    if (effective.has_coordinates === true) {
      requireValue(typeof effective.lat === "number" && typeof effective.lon === "number" &&
        Number.isFinite(effective.lat) && Number.isFinite(effective.lon) && Math.abs(effective.lat) <= 90 && Math.abs(effective.lon) <= 180,
        "invalid mapped point");
    } else {
      requireValue(effective.has_coordinates === false && effective.lat == null && effective.lon == null, "inconsistent unmapped point");
    }
    return effective;
  }

  async function verifyCompressedPayload(bytes, config, subtle) {
    requireValue(validHash(config && config.gzipSha256), "compressed integrity pin missing");
    const engine = subtle || (typeof crypto !== "undefined" && crypto.subtle);
    requireValue(engine && typeof engine.digest === "function", "browser integrity verification unavailable");
    const digest = await engine.digest("SHA-256", bytes);
    const actual = Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
    requireValue(actual === config.gzipSha256, "compressed payload hash mismatch");
  }

  return Object.freeze({ createIndex, createMappingIndex, validateLocationReference, apply, verifyCompressedPayload });
});
