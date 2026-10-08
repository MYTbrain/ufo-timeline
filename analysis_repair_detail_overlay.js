(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisRepairDetailOverlay = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const SCHEMA = "ufo-analysis-repair-detail-overlay-v1";
  const SOURCE_PIN_KEYS = Object.freeze(["baseQualityManifestSha256", "mufonPatchSha256", "mufonRepairManifestSha256",
    "reviewedYearPatchSha256", "reviewedYearManifestSha256", "sourceReviewSha256", "existingQualityOverlayGzipSha256"]);
  const CORE_GUARDS = Object.freeze(["event_id", "canonical_event_id", "source_id", "source", "date_raw", "date_iso",
    "end_date_iso", "sort_date_iso", "date_precision", "chunk_id", "detail_index"]);
  const RAW_GUARDS = new Set(["id", "source", "source_id", "name", "date", "location", "city", "country", "description"]);
  const FIELDS = new Set(["date_iso", "end_date_iso", "sort_date_iso", "date_precision", "date_interval_semantics",
    "exact_day_eligible", "date_recovery_contract", "date_recovery_provenance"]);
  const FORBIDDEN = new Set(["__proto__", "prototype", "constructor"]);
  function requireValue(condition, message) { if (!condition) throw new Error("Analysis detail correction refused: " + message); }
  function plain(value) { return value !== null && typeof value === "object" && !Array.isArray(value) &&
    (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null); }
  function validHash(value) { return typeof value === "string" && /^[a-f0-9]{64}$/.test(value); }
  function scalar(value) { return value === null || typeof value === "string" || typeof value === "boolean" || typeof value === "number" && Number.isFinite(value); }
  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function freezeTree(value) { if (value && typeof value === "object") { Object.values(value).forEach(freezeTree); Object.freeze(value); } return value; }
  function guardPath(path) {
    if (!Array.isArray(path) || path.some(function (part) { return FORBIDDEN.has(part); })) return false;
    if (path.length === 1) return CORE_GUARDS.includes(path[0]);
    return path[0] === "raw_source_row" && (path.length === 2 && RAW_GUARDS.has(path[1]) ||
      path.length === 3 && Number.isSafeInteger(path[1]) && path[1] >= 0 && RAW_GUARDS.has(path[2]));
  }
  function valueAt(original, path) {
    let value = original;
    for (const part of path) {
      if (value === null || typeof value !== "object" || !Object.hasOwn(value, part)) return { exists: false };
      if (typeof part === "number" && !Array.isArray(value)) return { exists: false };
      value = value[part];
    }
    return { exists: true, value };
  }
  function dateNumber(value) {
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
    const n = Date.parse(value + "T00:00:00Z");
    return Number.isFinite(n) && new Date(n).toISOString().slice(0, 10) === value ? n : null;
  }
  function validateFields(patch) {
    const fields = patch.setFields;
    requireValue(plain(fields) && Object.keys(fields).every(function (key) { return FIELDS.has(key); }) &&
      Array.from(FIELDS).every(function (key) { return Object.hasOwn(fields, key); }), "protected or incomplete field edit");
    const start = dateNumber(fields.date_iso), end = dateNumber(fields.end_date_iso), sort = dateNumber(fields.sort_date_iso);
    requireValue(start !== null && end !== null && sort !== null && start <= sort && sort <= end &&
      fields.exact_day_eligible === false && fields.date_interval_semantics === "source_calendar_precision_bounds_not_observed_days",
      "unsupported calendar interval");
    const provenance = fields.date_recovery_provenance;
    requireValue(plain(provenance) && provenance.interval_bounds_are_observed_days === false && provenance.sort_midpoint_is_observed_day === false &&
      typeof provenance.overlay_id === "string" && validHash(provenance.original_detail_date_identity_sha256), "missing reviewed provenance");
    const byPath = new Map(patch.guards.map(function (guard) { return [JSON.stringify(guard.path), guard]; }));
    const value = function (key) { const guard = byPath.get(JSON.stringify([key])); return guard && guard.exists ? guard.value : null; };
    requireValue(value("event_id") === patch.eventId && value("chunk_id") === patch.chunkId && value("detail_index") === patch.detailIndex,
      "conflicting record locator");
    const year = fields.date_iso.slice(0, 4), first = year + "-01-01", last = year + "-12-31";
    if (patch.kind === "mufon_partial_date") {
      const raw = value("date_raw"), match = typeof raw === "string" && /^(\d{4})-(\d{2})-00$/.exec(raw);
      requireValue(value("source") === "mufon" && value("date_precision") === "unknown" && value("date_iso") === null &&
        value("end_date_iso") === null && value("sort_date_iso") === null && match && match[1] === year &&
        fields.date_recovery_contract === "mufon_zero_calendar_components_v1" && provenance.original_date_precision === "unknown" &&
        provenance.source === "mufon" && validHash(provenance.raw_date_sha256), "unsupported MUFON source transition");
      if (match[2] === "00") requireValue(fields.date_precision === "year" && fields.date_iso === first && fields.end_date_iso === last, "invalid recovered year bounds");
      else {
        const month = Number(match[2]), monthStart = year + "-" + match[2] + "-01";
        const monthEnd = month >= 1 && month <= 12 ? new Date(Date.UTC(Number(year), month, 0)).toISOString().slice(0, 10) : null;
        requireValue(fields.date_precision === "month" && fields.date_iso === monthStart && fields.end_date_iso === monthEnd, "invalid recovered month bounds");
      }
    } else {
      requireValue(patch.kind === "source_reviewed_year" && value("source") === "phenomenainon_updb" && value("date_precision") === "exact_day" &&
        value("date_raw") === "1900-01-01" && value("sort_date_iso") === "1900-01-01" && fields.date_precision === "year" &&
        fields.date_iso === first && fields.end_date_iso === last && fields.date_recovery_contract === "source_reviewed_occurrence_year_v1" &&
        provenance.original_date_was_reviewed_sentinel === true && validHash(provenance.source_review_sha256) && validHash(provenance.source_narrative_sha256),
        "unsupported reviewed occurrence-year transition");
      requireValue(Array.from(RAW_GUARDS).every(function (key) { return patch.guards.some(function (guard) { return guard.path[0] === "raw_source_row" && guard.path[guard.path.length - 1] === key && guard.exists; }); }),
        "incomplete reviewed raw-source guards");
    }
    requireValue(sort === start + Math.floor((end - start) / 86400000 / 2) * 86400000, "ordering midpoint differs from reviewed contract");
  }
  function createIndex(payload, config) {
    requireValue(plain(payload) && payload.schemaId === SCHEMA && payload.schemaVersion === 1, "unsupported payload schema");
    requireValue(plain(config) && config.enabled === true && plain(config.sourcePins) && plain(payload.sourcePins), "disabled or incomplete delivery contract");
    requireValue(Object.keys(payload.sourcePins).length === SOURCE_PIN_KEYS.length && Object.keys(config.sourcePins).length === SOURCE_PIN_KEYS.length &&
      SOURCE_PIN_KEYS.every(function (key) { return validHash(config.sourcePins[key]) && config.sourcePins[key] === payload.sourcePins[key]; }), "stale source pins");
    requireValue(Number.isSafeInteger(config.patchCount) && config.patchCount >= 0 && Array.isArray(payload.patches) && payload.patches.length === config.patchCount,
      "partial correction packet");
    const patches = new Map();
    for (const patch of payload.patches) {
      requireValue(plain(patch) && Number.isSafeInteger(patch.eventId) && patch.eventId >= 0 && typeof patch.chunkId === "string" && /^chunk_\d{6}$/.test(patch.chunkId) &&
        Number.isSafeInteger(patch.detailIndex) && patch.detailIndex >= 0 && !patches.has(String(patch.eventId)), "invalid or repeated record locator");
      requireValue(Array.isArray(patch.guards) && patch.guards.length > 0 && patch.guards.every(function (guard) { return plain(guard) && guardPath(guard.path) &&
        typeof guard.exists === "boolean" && (!guard.exists || scalar(guard.value)); }), "unsupported source guard");
      const paths = new Set(patch.guards.map(function (guard) { return JSON.stringify(guard.path); }));
      requireValue(paths.size === patch.guards.length && CORE_GUARDS.every(function (key) { return paths.has(JSON.stringify([key])); }), "incomplete or repeated source guards");
      validateFields(patch);
      patches.set(String(patch.eventId), freezeTree(clone(patch)));
    }
    return Object.freeze({ patchCount: patches.size, hasPatch: function (id) { return patches.has(String(id)); }, getPatch: function (id) { return patches.get(String(id)); } });
  }
  function apply(index, original) {
    if (!original || original.event_id == null) return original;
    const patch = index.getPatch(original.event_id);
    if (!patch) return original;
    for (const guard of patch.guards) {
      const actual = valueAt(original, guard.path);
      requireValue(actual.exists === guard.exists && (!guard.exists || actual.value === guard.value), "stale " + guard.path.join(".") + " for " + patch.eventId);
    }
    return Object.assign({}, original, clone(patch.setFields));
  }
  async function verifyBytes(bytes, size, hash, subtle, label) {
    requireValue(Number.isSafeInteger(size) && size >= 0 && bytes && bytes.byteLength === size && validHash(hash), label + " length or hash pin missing/mismatched");
    const engine = subtle || (typeof crypto !== "undefined" && crypto.subtle);
    requireValue(engine && typeof engine.digest === "function", "browser integrity verification unavailable");
    const digest = await engine.digest("SHA-256", bytes);
    const actual = Array.from(new Uint8Array(digest), function (value) { return value.toString(16).padStart(2, "0"); }).join("");
    requireValue(actual === hash, label + " hash mismatch");
  }
  function verifyCompressedPayload(bytes, config, subtle) { return verifyBytes(bytes, config && config.gzipBytes, config && config.gzipSha256, subtle, "compressed payload"); }
  function verifyDecodedPayload(bytes, config, subtle) { return verifyBytes(bytes, config && config.bytes, config && config.sha256, subtle, "decoded payload"); }
  return Object.freeze({ SCHEMA, SOURCE_PIN_KEYS, createIndex, apply, verifyCompressedPayload, verifyDecodedPayload });
});
