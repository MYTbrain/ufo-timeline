(function (root, factory) {
  "use strict";
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.UfoMufonDateReview = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const REVIEW_ID = "mufon-occurrence-date-20261019-v1";
  const SOURCE_DATE = "1890-04-01";
  const REASON = "The source date 1890-04-01 conflicts with the account or lacks occurrence-date support; no replacement occurrence date is established.";
  // These are reviewed representations, not a date-wide replacement rule.
  // Locators pin the current published catalog; full records also retain source-row guards.
  const TARGETS = Object.freeze([
    {event_id:343118950126607, canonical_event_id:"evt_2541aaa4470d1a09ad7a5163", chunk_id:"chunk_000157", detail_index:2418,
      source_native_id:"8882", source_row_number:8094, source_row_hash:"1c1102c34960326a9bd11db62cf28314877ffe37", canonical_input_id:"cin_7df8db704f1bf3e24f4313ba"},
    {event_id:2622942896863721, canonical_event_id:"evt_ed402082486fff62ee2ef303", chunk_id:"chunk_000211", detail_index:1327,
      source_native_id:"9920", source_row_number:9105, source_row_hash:"c0a765843a994a2e15ac364c076d1361b0a517d7", canonical_input_id:"cin_b24994d8c27fc61547e2149c"},
    {event_id:4288152570535824, canonical_event_id:"evt_702ff478d439a48de2463a87", chunk_id:"chunk_000168", detail_index:1070,
      source_native_id:"12619", source_row_number:11730, source_row_hash:"40d6b60be4dcb9b8ac21f874a16b17034e538753", canonical_input_id:"cin_87bb5f23c1e9056cdf2636f2"},
    {event_id:1996462471622897, canonical_event_id:"evt_a29467a0e04ba64cbea5af59", chunk_id:"chunk_000017", detail_index:444,
      source_native_id:"18815", source_row_number:17625, source_row_hash:"d873e1c85158af98d3d2c245547e80aef76f114a", canonical_input_id:"cin_0b99d6037f0bf66577e6b62f"},
    {event_id:814453687151247, canonical_event_id:"evt_46412a9c78f891af4470ffc6", chunk_id:"chunk_000142", detail_index:1809,
      source_native_id:"30468", source_row_number:28811, source_row_hash:"2a951f6cf5709af778ee14007c3502a0e367cd65", canonical_input_id:"cin_6ff74cd08d4c00e5e1c5c5dd"},
  ].map(target => Object.freeze({...target, source:"mufon", source_file:"mufonpy.csv"})));
  const byId = new Map(TARGETS.map(target => [target.event_id, target]));
  const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
  const present = value => value !== undefined && value !== null && value !== "";
  const id = value => typeof value === "number" && Number.isSafeInteger(value) && value > 0 ? value
    : typeof value === "string" && /^[1-9][0-9]*$/.test(value) && Number.isSafeInteger(Number(value)) ? Number(value) : null;
  const reviewed = event => object(event.date_review) && event.date_review.review_id === REVIEW_ID && event.date_review.status === "unverified_source_date";
  const NULL_FIELDS = Object.freeze([
    "date_iso", "end_date_iso", "sort_date_iso", "sort_ordinal", "sort_date_key", "sort_time_ms",
    "parsed_time_local_minutes", "parsed_time_local_range_start_minutes", "parsed_time_local_range_end_minutes",
    "estimated_utc_timestamp_ms", "estimated_utc_range_start_ms", "estimated_utc_range_end_ms",
    "time_bucket_label", "resolved_timezone", "playback_sort_key",
  ]);
  const UNKNOWN_FIELDS = Object.freeze({date_precision:"unknown", exact_day_eligible:false, time_sort_kind:"unknown",
    time_sort_confidence:"none", timezone_source:"unknown", timezone_confidence:"none", playback_sort_confidence:"none",
    playback_sort_reason:"unverified_source_date"});
  function guardedTarget(event, packed) {
    if (!object(event)) return null;
    const target = byId.get(id(event.event_id));
    if (!target || event.source !== target.source || (!packed && event.date_raw !== SOURCE_DATE) ||
        (packed && present(event.date_raw) && event.date_raw !== SOURCE_DATE) ||
        event.chunk_id !== target.chunk_id || event.detail_index !== target.detail_index) return null;
    // A later source-supported correction must win over this old review and raw source claim.
    if (["date_iso", "sort_date_iso", "end_date_iso"].some(key => present(event[key]) && event[key] !== SOURCE_DATE)) return null;
    const originalDate = packed ? event.sort_date_iso === SOURCE_DATE : [event.date_iso, event.sort_date_iso].some(value => value === SOURCE_DATE);
    if (!originalDate && !reviewed(event)) return null;
    for (const key of ["canonical_event_id", "source_file", "source_row_number", "source_row_hash", "canonical_input_id"]) {
      if (present(event[key]) && event[key] !== target[key]) return null;
    }
    for (const key of ["source_native_id", "source_id"]) {
      if (present(event[key]) && String(event[key]) !== target.source_native_id) return null;
    }
    if (present(event.source_name) && event.source_name !== target.source) return null;
    if (present(event.canonical_input_ids) && (!Array.isArray(event.canonical_input_ids) || !event.canonical_input_ids.includes(target.canonical_input_id))) return null;
    for (const key of ["raw_fields", "raw_source_row"]) {
      if (object(event[key]) && present(event[key].No) && String(event[key].No) !== target.source_native_id) return null;
    }
    if (present(event.source_provenance)) {
      if (!Array.isArray(event.source_provenance)) return null;
      const member = event.source_provenance.find(value => object(value) && value.canonical_input_id === target.canonical_input_id);
      if (!member || member.source_name !== target.source || member.source_file !== target.source_file ||
          String(member.source_native_id) !== target.source_native_id || member.source_row_number !== target.source_row_number ||
          member.source_row_hash !== target.source_row_hash) return null;
    }
    return target;
  }
  function applyReviewed(event) {
    if (reviewed(event) && event.date_review.reason === REASON && NULL_FIELDS.every(key => event[key] === null) &&
        Object.entries(UNKNOWN_FIELDS).every(([key, value]) => event[key] === value)) return event;
    const result = {...event, ...UNKNOWN_FIELDS, date_review:{review_id:REVIEW_ID, status:"unverified_source_date", reason:REASON}};
    for (const key of NULL_FIELDS) result[key] = null;
    return result;
  }
  function apply(event) {
    return guardedTarget(event, false) ? applyReviewed(event) : event;
  }
  function applyPacked(event) {
    // Packed points omit verbatim raw fields; their exact published row locator
    // and original normalized date supply the additional required identity pins.
    return guardedTarget(event, true) ? applyReviewed(event) : event;
  }
  function isTargetId(eventId) { return byId.has(id(eventId)); }
  function displayDate(event, fallback) {
    if (object(event) && reviewed(event)) {
      // Canonical review metadata survives rebuilt chunk locators and deduplication.
      // This affects the label only; applying a correction still requires every row pin.
      const canonicalReview = event.source === "mufon" && event.date_raw === SOURCE_DATE && event.date_precision === "unknown" &&
        ["date_iso", "end_date_iso", "sort_date_iso"].every(key => event[key] === undefined || event[key] === null);
      if (canonicalReview || guardedTarget(event, false) || guardedTarget(event, true)) return "Date unverified";
    }
    if (present(fallback)) return fallback;
    if (!object(event)) return "Unknown date";
    return event.date_raw || event.sort_date_iso || event.date_iso || "Unknown date";
  }
  return Object.freeze({apply, applyPacked, isTargetId, displayDate, REVIEW_ID, TARGETS});
});
